"""Collector registry.

Each domain module exposes `COLLECTORS: list[type[Collector]]`. Adding a
source = adding a class to one of these lists; nothing else to wire.
"""

from __future__ import annotations

import importlib
import logging

from .base import Collector

log = logging.getLogger(__name__)

DOMAIN_MODULES = (
    "indices",      # NOAA CPC / PSL / BoM / Climate Reanalyzer numeric series
    "official",     # CPC alert status, IRI plume, BoM/WMO bulletins, ENSO blog
    "maritime",     # TAO/TRITON buoys, Coral Reef Watch, marine weather
    "hazards",      # GDACS, NASA EONET, NOAA/other warnings
    "news",         # GDELT, Google News RSS (multi-language), agency RSS
    "social",       # X, Bluesky, Mastodon, Reddit, Telegram channels
    # extra source sets (skipped while a module does not exist yet)
    "extra_ocean", "extra_atmos", "extra_hazards", "extra_thailand", "extra_media",
    "extra_nasa", "extra_agencies",
    "extra_cams",   # public webcams (buoy, satellite, beach/street streams)
)


def all_collectors() -> list[Collector]:
    out: list[Collector] = []
    seen: set[str] = set()
    mods = [f"{__name__}.{m}" for m in DOMAIN_MODULES] + [
        "app.local.collectors", "app.places.collectors",
        "app.local.analogs",  # ERA5 history behind the El Nino analogs page
    ]
    for mod_name in mods:
        try:
            mod = importlib.import_module(mod_name)
        except ModuleNotFoundError as e:
            if e.name == mod_name:
                continue  # domain not written yet
            raise
        for cls in getattr(mod, "COLLECTORS", []):
            if cls.name in seen:
                raise RuntimeError(f"duplicate collector name {cls.name}")
            seen.add(cls.name)
            out.append(cls())
    return out


def source_state(col: Collector, now=None) -> dict:
    """describe() + run health + freshness, i.e. one row of GET /api/sources.

    state: pending | needs_config | error | empty | stale | ok. `stale` = the last
    fetch worked but the newest data it serves is older than the collector's
    max_age_s ("fetch ok" and "data fresh" are different things)."""
    from .. import db

    d = col.describe()
    runs = db.query(
        "SELECT started_at, ok, items, http_status, latency_ms, error FROM source_runs "
        "WHERE source=? ORDER BY id DESC LIMIT 20",
        (col.name,),
    )
    last = runs[0] if runs else None
    ok_runs = [r for r in runs if r["ok"]]
    fresh = col.freshness(now)
    if last is None:
        state = "pending"
    elif last["error"] and last["error"].startswith("needs_config"):
        state = "needs_config"
    elif not last["ok"]:
        state = "error"
    elif last["items"] == 0:
        state = "empty"
    elif fresh["stale"]:
        state = "stale"
    else:
        state = "ok"
    d.update(
        state=state, last_run=last,
        success_rate=round(len(ok_runs) / len(runs), 2) if runs else None,
        last_ok_at=ok_runs[0]["started_at"] if ok_runs else None,
        missing_config=col.missing_config(),
        freshness=fresh,
    )
    return d


def source_report(now=None) -> list[dict]:
    return [source_state(c, now) for c in all_collectors()]
