"""Collector contract.

A collector is one source. It declares what it is (for the Sources page) and
implements `collect()`, which writes through `app.db` and returns how many
items it stored. The runner times it, records a source_runs row either way,
and never lets one failing source take the others down.

Rules every collector follows:
- Only data that came from a real response is stored. Never fabricate.
- A source that needs a credential that is not configured raises
  NeedsConfig: it shows up as "needs_config", not as a silent zero.
- Parse defensively and raise SourceChanged when the payload no longer
  looks like what we expect, so a format change is visible, not silent.

Freshness ("fetch ok" is not "data fresh"): each collector declares
- `max_age_s`: how old its newest data may be before the source counts as stale
  (default: 3 x interval_s, at least 1 h), and
- `freshness_basis`: where its newest data timestamp lives:
    "observations" -> MAX(observations.ts) of this source, ignoring future (forecast) rows
    "feed"         -> MAX(feed_items.published_at) of this source, ignoring future dates
    "events"       -> MAX(COALESCE(events.updated_at, started_at)) of this source
    "status"       -> status.updated_at of `freshness_status_key`
    "run"          -> the last successful run (forecasts, alert pages that only
                      publish when something happens)
`freshness()` returns {newest_data_at, max_age_s, age_s, stale, basis}.
- `expected_stale`: a one-line reason when the source is KNOWN to be silent (a feed its
  publisher stopped updating). The row still says `stale` (the data really is old), but
  carries `expected_stale` so the Sources page can label it and scripts/verify_sources.py
  does not fail the whole check on it.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar

import httpx

from .. import db
from ..config import settings

HOUR = 3600
DAY = 24 * HOUR


class NeedsConfig(Exception):
    """A credential / setting is missing. Not an outage."""


class SourceChanged(Exception):
    """The response parsed but did not look like the documented format."""


@dataclass
class RunContext:
    client: httpx.AsyncClient
    last_status: int | None = None
    notes: dict = field(default_factory=dict)

    async def get(self, url: str, **kw) -> httpx.Response:
        r = await self.client.get(url, **kw)
        self.last_status = r.status_code
        r.raise_for_status()
        return r


class Collector:
    name: ClassVar[str]            # unique slug, e.g. "cpc_oni"
    title: ClassVar[str]           # human label
    category: ClassVar[str]        # ocean_index | official | maritime | satellite | weather
    #                                | disaster | news | social | local
    provider: ClassVar[str]        # "NOAA CPC", "GDACS (EC JRC / UN)", ...
    homepage: ClassVar[str]        # human page for the source
    endpoint: ClassVar[str]        # main URL actually fetched (shown + health-checked)
    interval_s: ClassVar[int]      # how often to run
    description: ClassVar[str] = ""
    needs: ClassVar[tuple[str, ...]] = ()  # settings names required, e.g. ("x_bearer_token",)
    max_age_s: ClassVar[int | None] = None  # None -> 3 x interval_s (>= 1 h)
    freshness_basis: ClassVar[str] = "run"  # observations | feed | events | status | run
    freshness_status_key: ClassVar[str | None] = None
    expected_stale: ClassVar[str | None] = None  # documented reason when the feed is silent

    async def collect(self, ctx: RunContext) -> int:
        raise NotImplementedError

    def missing_config(self) -> list[str]:
        return [n for n in self.needs if not getattr(settings, n, None)]

    @classmethod
    def describe(cls) -> dict:
        return {
            "name": cls.name, "title": cls.title, "category": cls.category,
            "provider": cls.provider, "homepage": cls.homepage, "endpoint": cls.endpoint,
            "interval_s": cls.interval_s, "description": cls.description,
            "needs": list(cls.needs), "max_age_s": cls.effective_max_age(),
            "expected_stale": cls.expected_stale,
        }

    @classmethod
    def effective_max_age(cls) -> int:
        return int(cls.max_age_s or max(3 * cls.interval_s, 3600))

    @classmethod
    def newest_data_at(cls, now: datetime | None = None) -> str | None:
        now_s = (now or datetime.now(UTC)).replace(microsecond=0).isoformat()
        basis = cls.freshness_basis
        if basis == "observations":
            sql = "SELECT MAX(ts) AS t FROM observations WHERE source=? AND ts<=?"
            p: tuple = (cls.name, now_s)
        elif basis == "feed":
            sql = ("SELECT MAX(published_at) AS t FROM feed_items WHERE source=? "
                   "AND published_at<=?")
            p = (cls.name, now_s)
        elif basis == "events":
            sql = ("SELECT MAX(COALESCE(updated_at, started_at)) AS t FROM events "
                   "WHERE source=?")
            p = (cls.name,)
        elif basis == "status":
            sql = "SELECT updated_at AS t FROM status WHERE key=?"
            p = (cls.freshness_status_key or cls.name,)
        else:
            sql = ("SELECT finished_at AS t FROM source_runs WHERE source=? AND ok=1 "
                   "ORDER BY id DESC LIMIT 1")
            p = (cls.name,)
        rows = db.query(sql, p)
        return rows[0]["t"] if rows and rows[0]["t"] else None

    @classmethod
    def freshness(cls, now: datetime | None = None) -> dict:
        now = now or datetime.now(UTC)
        newest = cls.newest_data_at(now)
        max_age = cls.effective_max_age()
        t = parse_when(newest)
        age = None if t is None else max(0, int((now - t).total_seconds()))
        return {"newest_data_at": newest, "max_age_s": max_age, "age_s": age,
                "stale": age is None or age > max_age, "basis": cls.freshness_basis}


def parse_when(s: str | None) -> datetime | None:
    """ISO date or datetime -> aware UTC datetime. A bare date counts from its
    start (00:00 UTC), the conservative reading for freshness."""
    if not s:
        return None
    try:
        t = datetime.fromisoformat(s)
    except ValueError:
        return None
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)


MAX_RUN_S = 300


def run_timeout(col: Collector) -> float:
    """A run may take at most min(interval, 5 min): a hung source must not stall the rest."""
    return float(min(col.interval_s, MAX_RUN_S))


async def run_collector(col: Collector, client: httpx.AsyncClient,
                        timeout_s: float | None = None) -> dict:
    started = db.now_iso()
    t0 = time.monotonic()
    ctx = RunContext(client=client)
    missing = col.missing_config()
    if missing:
        db.record_run(col.name, started, ok=False, error=f"needs_config: {', '.join(missing)}")
        return {"source": col.name, "ok": False, "needs_config": missing}
    limit = run_timeout(col) if timeout_s is None else timeout_s
    try:
        try:
            n = await asyncio.wait_for(col.collect(ctx), timeout=limit)
        except TimeoutError:
            if time.monotonic() - t0 < limit - 0.5:
                raise  # a socket timeout inside the collector, not our run limit
            raise TimeoutError(f"run exceeded {limit:.0f} s and was cancelled") from None
        ms = int((time.monotonic() - t0) * 1000)
        db.record_run(col.name, started, ok=True, items=n, http_status=ctx.last_status,
                      latency_ms=ms, detail=ctx.notes or None)
        return {"source": col.name, "ok": True, "items": n, "ms": ms}
    except NeedsConfig as e:
        db.record_run(col.name, started, ok=False, error=f"needs_config: {e}")
        return {"source": col.name, "ok": False, "needs_config": str(e)}
    except Exception as e:  # noqa: BLE001 -- one source must never kill the loop
        ms = int((time.monotonic() - t0) * 1000)
        status = getattr(getattr(e, "response", None), "status_code", ctx.last_status)
        db.record_run(col.name, started, ok=False, http_status=status, latency_ms=ms,
                      error=f"{type(e).__name__}: {e}"[:500])
        return {"source": col.name, "ok": False, "error": str(e)[:200], "http_status": status}
