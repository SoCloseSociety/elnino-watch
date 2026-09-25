"""In-process scheduler: each collector runs on its own interval.

Every collector runs as its own task, so a slow source (GDELT backs off for
30 s, X walks ~40 timelines) never delays a fast one (GDACS every 15 min).
Each run is capped at min(interval, 300 s) by the runner (base.run_timeout):
a source that hangs is cancelled and recorded as an error, it cannot stall
anything.

After runs complete, the post-run hooks fire (local risk engine, alert
dispatch), then the briefing is refreshed if it is due. Hooks are registered
by app.local so the core stays domain-free. A daily maintenance task prunes
old rows (db.prune) and VACUUMs once a week.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import httpx

from . import db
from .collectors import all_collectors
from .collectors.base import Collector, parse_when, run_collector
from .config import settings

log = logging.getLogger("elnino.scheduler")

PostHook = Callable[[], Awaitable[None]]
_post_hooks: list[PostHook] = []
_running: set[str] = set()
_hooks_lock = asyncio.Lock()

TICK_S = 15
MAX_PARALLEL = 6
RETRY_AFTER_ERROR_S = 30 * 60   # a failed run is retried sooner than its interval ...
MAINTENANCE_EVERY_S = 24 * 3600
VACUUM_EVERY_S = 7 * 24 * 3600


def register_post_hook(fn: PostHook) -> None:
    _post_hooks.append(fn)


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=True,
        headers={"User-Agent": settings.user_agent},
    )


async def run_hooks() -> None:
    async with _hooks_lock:  # never two risk evaluations / alert dispatches at once
        for fn in _post_hooks:
            try:
                await fn()
            except Exception:
                log.exception("post hook %s failed", getattr(fn, "__name__", fn))
        try:
            from . import briefing

            await briefing.refresh_if_due()
        except Exception:
            log.exception("briefing refresh failed")


async def run_one(col: Collector, client: httpx.AsyncClient) -> dict:
    if col.name in _running:
        return {"source": col.name, "ok": False, "error": "already running"}
    _running.add(col.name)
    try:
        return await run_collector(col, client)
    finally:
        _running.discard(col.name)


async def run_all(names: set[str] | None = None) -> list[dict]:
    cols = [c for c in all_collectors() if names is None or c.name in names]
    async with make_client() as client:
        sem = asyncio.Semaphore(MAX_PARALLEL)

        async def guarded(c: Collector) -> dict:
            async with sem:
                return await run_one(c, client)

        results = await asyncio.gather(*(guarded(c) for c in cols))
    await run_hooks()
    return list(results)


def _last_run(name: str) -> dict | None:
    rows = db.query(
        "SELECT started_at, ok, http_status, error FROM source_runs WHERE source=? "
        "ORDER BY id DESC LIMIT 1", (name,))
    return rows[0] if rows else None


def next_delay(col: Collector, result: dict | None) -> float:
    """Seconds until the next run after `result` (None = unknown / first run).

    ... unless it was rate-limited (429: wait the full interval, hammering makes it
    worse) or it needs configuration (nothing will change until someone edits .env)."""
    if result is None or result.get("ok") or result.get("needs_config"):
        return float(col.interval_s)
    if result.get("http_status") == 429 or "429" in str(result.get("error") or ""):
        return float(col.interval_s)
    return float(min(col.interval_s, RETRY_AFTER_ERROR_S))


def initial_delay(col: Collector, now: datetime | None = None) -> float:
    """Resume the cadence across restarts instead of hammering every source."""
    last = _last_run(col.name)
    if last is None:
        return 0.0
    t = parse_when(last["started_at"])
    if t is None:
        return 0.0
    age = ((now or datetime.now(UTC)) - t).total_seconds()
    res = {"ok": bool(last["ok"]), "http_status": last["http_status"],
           "error": last["error"],
           "needs_config": (last["error"] or "").startswith("needs_config") or None}
    return max(0.0, next_delay(col, res) - age)


async def maintenance(force_vacuum: bool = False) -> dict:
    """Retention + weekly VACUUM. State kept in status `maintenance`."""
    prev = (db.get_status("maintenance") or {}).get("value") or {}
    out = await asyncio.to_thread(db.prune)
    last_vac = parse_when(prev.get("last_vacuum"))
    now = datetime.now(UTC)
    if force_vacuum or last_vac is None or now - last_vac >= timedelta(seconds=VACUUM_EVERY_S):
        await asyncio.to_thread(db.vacuum)
        out["vacuumed"] = True
        last_vac = now
    doc = {"last_prune": db.now_iso(), "pruned": {"feed_items": out["feed_items"],
                                                  "events": out["events"],
                                                  "observations_hourly": out["observations_hourly"],
                                                  "observations_days": out["observations_days"]},
           "last_vacuum": last_vac.replace(microsecond=0).isoformat(),
           "policy": {"feed_items_days": db.FEED_KEEP_DAYS, "official": "kept forever",
                      "events_closed_days": db.EVENT_CLOSED_DAYS,
                      "source_runs": "last 200 per source", "vacuum": "weekly",
                      "observations": (f"hourly buoy points (series {db.HOURLY_SERIES_LIKE}) older "
                                       f"than {db.HOURLY_KEEP_DAYS} days become one daily mean; "
                                       "daily and monthly series are kept forever")}}
    db.set_status("maintenance", doc)
    log.info("maintenance: %s", doc)
    return doc


def _maintenance_due() -> float:
    prev = (db.get_status("maintenance") or {}).get("value") or {}
    t = parse_when(prev.get("last_prune"))
    if t is None:
        return 60.0  # first start: let the collectors go first
    age = (datetime.now(UTC) - t).total_seconds()
    return max(60.0, MAINTENANCE_EVERY_S - age)


async def loop() -> None:
    cols = all_collectors()
    log.info("scheduler: %d collectors", len(cols))
    now = time.monotonic()
    next_at = {c.name: now + initial_delay(c) for c in cols}
    maint_at = now + _maintenance_due()
    sem = asyncio.Semaphore(MAX_PARALLEL)
    tasks: dict[str, asyncio.Task] = {}
    hooks_pending = False

    async with make_client() as client:

        async def one(c: Collector) -> None:
            nonlocal hooks_pending
            res: dict | None = None
            try:
                async with sem:
                    res = await run_one(c, client)
            except Exception:  # run_collector already records; this is belt and braces
                log.exception("collector %s crashed the runner", c.name)
            finally:
                next_at[c.name] = time.monotonic() + next_delay(c, res)
                hooks_pending = True

        try:
            while True:
                now = time.monotonic()
                for c in cols:
                    if next_at[c.name] <= now and c.name not in tasks:
                        next_at[c.name] = float("inf")  # set for real when the run ends
                        t = asyncio.create_task(one(c), name=f"collect:{c.name}")
                        tasks[c.name] = t
                        t.add_done_callback(lambda _t, n=c.name: tasks.pop(n, None))
                if hooks_pending:
                    hooks_pending = False
                    await run_hooks()
                else:
                    # the briefing is also time-based (every 6 h), not only run-based
                    try:
                        from . import briefing

                        await briefing.refresh_if_due()
                    except Exception:
                        log.exception("briefing refresh failed")
                if now >= maint_at:
                    maint_at = now + MAINTENANCE_EVERY_S
                    try:
                        await maintenance()
                    except Exception:
                        log.exception("maintenance failed")
                await asyncio.sleep(TICK_S)
        finally:
            for t in list(tasks.values()):
                t.cancel()
