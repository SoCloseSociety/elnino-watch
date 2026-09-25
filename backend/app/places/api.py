"""HTTP routes of the Places comparison (mounted by app.main: `app.places.api.router`).

GET    /api/places                 list + current level per place
GET    /api/places/compare         matrix, ranking (weights=dim:w,...), summary, advisories
GET    /api/places/search?q=       geocoder proxy (Open-Meteo geocoding / GeoNames)
GET    /api/places/preview?...     light live data for a place that is NOT collected
                                   (the browser-only personal list)
GET    /api/places/{id}            full detail
POST   /api/places                 add a place from a search result (admin)
DELETE /api/places/{id}            remove a place (admin)

Admin: when settings.public_mode is true, POST/DELETE need the header X-Admin-Token equal
to settings.admin_token (both optional settings; on the default localhost install the
owner is the admin and no token is needed). If app.auth.require_admin exists, it is used
instead, so the project has a single admin rule.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import importlib
import time
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .. import db
from ..config import settings
from . import config, engine
from . import enso as enso_ctx
from .collectors import FORECAST_CURRENT, FORECAST_DAILY, FORECAST_URL, parse_forecast

router = APIRouter()

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
MAX_PLACES = 12
LIGHT_COLLECTORS = {"places_forecast", "places_air", "places_marine", "places_seasonal",
                    "places_quakes", "places_fires", "places_warnings", "places_advisories"}


def _core_admin():
    with contextlib.suppress(ModuleNotFoundError):
        return getattr(importlib.import_module("app.auth"), "require_admin", None)
    return None


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    core = _core_admin()
    if core is not None:
        core(x_admin_token)  # the project-wide rule, if one exists
        return
    if not getattr(settings, "public_mode", False):
        return  # personal localhost install: the owner is the admin
    token = getattr(settings, "admin_token", "") or ""
    if not token or not hmac.compare_digest(x_admin_token or "", token):
        raise HTTPException(403, "admin only: adding or removing places needs the admin token "
                                 "in public mode (keep a personal list in your browser instead)")


def _can_edit() -> bool:
    return not getattr(settings, "public_mode", False)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0), follow_redirects=True,
                             headers={"User-Agent": settings.user_agent})


def _get(pid: str) -> dict:
    p = config.get_place(pid)
    if p is None:
        raise HTTPException(404, f"unknown place '{pid}'")
    return p


@router.get("/api/places")
def places() -> dict:
    now = datetime.now(UTC)
    out = []
    for p in config.list_places():
        s = engine.place_summary(p, now)
        s.pop("factors", None)
        out.append(s)
    return {"places": out, "public_mode": bool(getattr(settings, "public_mode", False)),
            "can_edit": _can_edit(), "max_places": MAX_PLACES}


@router.get("/api/places/compare")
def compare(weights: str | None = Query(None, description="dim:weight,... (0-10)")) -> dict:
    return engine.compare(weights)


class BoundedCache:
    """Small insertion-ordered cache: the oldest entry goes when `max_items` is reached.
    Both public GETs below are keyed by visitor input (any search string, any lat/lon),
    so an unbounded dict would let a crawler grow the process without limit."""

    def __init__(self, max_items: int) -> None:
        self.max_items = max_items
        self._d: dict = {}

    def get(self, key, ttl_s: float):
        hit = self._d.get(key)
        if hit and time.monotonic() - hit[0] < ttl_s:
            return hit[1]
        return None

    def put(self, key, value) -> None:
        self._d.pop(key, None)
        while len(self._d) >= self.max_items:
            self._d.pop(next(iter(self._d)))
        self._d[key] = (time.monotonic(), value)

    def clear(self) -> None:
        self._d.clear()

    def __len__(self) -> int:
        return len(self._d)


class UpstreamBudget:
    """At most `limit` upstream calls per rolling `window_s`. The Open-Meteo quota is shared
    with the Koh Samui collectors: a visitor (or a crawler) must not be able to spend it
    through these two proxies. Cache hits cost nothing."""

    def __init__(self, limit: int, window_s: float = 3600.0) -> None:
        self.limit, self.window_s = limit, window_s
        self._times: list[float] = []

    def take(self) -> bool:
        now = time.monotonic()
        self._times = [t for t in self._times if now - t < self.window_s]
        if len(self._times) >= self.limit:
            return False
        self._times.append(now)
        return True

    def reset(self) -> None:
        self._times.clear()


SEARCH_CACHE_MAX, SEARCH_TTL_S = 500, 3600.0
PREVIEW_CACHE_MAX, PREVIEW_TTL_S = 200, 1800.0
SEARCH_PER_HOUR, PREVIEW_PER_HOUR = 120, 120
_search_cache = BoundedCache(SEARCH_CACHE_MAX)
_search_budget = UpstreamBudget(SEARCH_PER_HOUR)
_preview_cache = BoundedCache(PREVIEW_CACHE_MAX)
_preview_budget = UpstreamBudget(PREVIEW_PER_HOUR)
BUDGET_MSG = ("upstream budget for this hour is used up (the geocoder / Open-Meteo quota is "
              "shared with the Koh Samui watch): try again later")


@router.get("/api/places/search")
async def search(q: str = Query(..., min_length=2, max_length=80)) -> dict:
    key = q.strip().lower()
    hit = _search_cache.get(key, SEARCH_TTL_S)
    if hit is not None:
        return {"query": q, "results": hit, "source": "Open-Meteo geocoding (GeoNames)"}
    if not _search_budget.take():
        raise HTTPException(429, BUDGET_MSG)
    async with _client() as c:
        r = await c.get(GEOCODE_URL, params={"name": q.strip(), "count": 10,
                                             "language": "en", "format": "json"})
    if r.status_code != 200:
        raise HTTPException(502, f"geocoder answered {r.status_code}")
    res = [{k: x.get(k) for k in ("id", "name", "latitude", "longitude", "elevation",
                                  "timezone", "country", "country_code", "admin1", "admin2",
                                  "admin3", "feature_code", "population")}
           for x in (r.json().get("results") or [])]
    _search_cache.put(key, res)
    return {"query": q, "results": res, "source": "Open-Meteo geocoding (GeoNames)",
            "url": "https://open-meteo.com/en/docs/geocoding-api"}


@router.get("/api/places/preview")
async def preview(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
                  name: str = Query("", max_length=80), timezone: str = Query("GMT", max_length=60),
                  country_code: str = Query("", max_length=2)) -> dict:
    """Light, uncached-by-server data for a browser-only place: current conditions and the
    7-day forecast (one Open-Meteo call, cached 30 min), the ENSO assessment and the stored
    advisories for its country. No long-term matrix: that needs the place to be collected."""
    key = f"{lat:.3f},{lon:.3f}"
    fc = _preview_cache.get(key, PREVIEW_TTL_S)
    if fc is None:
        if not _preview_budget.take():
            raise HTTPException(429, BUDGET_MSG)
        async with _client() as c:
            r = await c.get(FORECAST_URL, params={
                "latitude": lat, "longitude": lon, "timezone": timezone or "GMT",
                "daily": ",".join(FORECAST_DAILY), "current": ",".join(FORECAST_CURRENT),
                "forecast_days": 7})
        if r.status_code != 200:
            raise HTTPException(502, f"Open-Meteo answered {r.status_code}")
        fc = parse_forecast(r.json(), datetime.now(UTC).date())
        fc["fetched_at"] = db.now_iso()
        _preview_cache.put(key, fc)
    adv = db.get_status("places_advisories")
    code = (country_code or "").upper()
    cur = fc["current"]
    return {"name": name, "lat": lat, "lon": lon, "timezone": timezone,
            "current": cur | {"weather": engine.WMO_CODES.get(int(cur["weather_code"]))
                              if cur.get("weather_code") is not None else None},
            "daily": fc["daily"][:7],
            "fetched_at": fc["fetched_at"], "source": "Open-Meteo forecast",
            "url": "https://open-meteo.com/en/docs",
            "enso": enso_ctx.assess(lat, lon),
            "advisories": ((adv or {}).get("value", {}).get("countries", {}).get(code)
                           if adv and code else None),
            "note": ("Personal list: stored in this browser only. Long-term climate, "
                     "projections and hazards need the place to be added on the server.")}


@router.get("/api/places/{pid}")
def place(pid: str) -> dict:
    return engine.place_detail(_get(pid))


class NewPlace(BaseModel):
    """A geocoding search result (GET /api/places/search) chosen by the user."""
    id: int | None = None
    name: str = Field(..., min_length=1, max_length=80)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    elevation: float | None = None
    timezone: str | None = Field(None, max_length=60)
    country: str | None = Field(None, max_length=80)
    country_code: str | None = Field(None, max_length=2)
    admin1: str | None = Field(None, max_length=120)
    admin2: str | None = Field(None, max_length=120)
    admin3: str | None = Field(None, max_length=120)
    role: str = Field("candidate", pattern="^(candidate|home)$")


async def _refresh(names: set[str]) -> None:
    from ..collectors.base import run_collector
    from .collectors import COLLECTORS

    async with _client() as c:
        for cls in COLLECTORS:
            if cls.name in names:
                await run_collector(cls(), c)


@router.post("/api/places", dependencies=[Depends(require_admin)])
async def add_place(body: NewPlace) -> dict:
    if len(config.list_places()) >= MAX_PLACES:
        raise HTTPException(409, f"at most {MAX_PLACES} places")
    for p in config.list_places():
        if engine.haversine_km(p["lat"], p["lon"], body.latitude, body.longitude) < 1:
            raise HTTPException(409, f"already tracked as '{p['id']}'")
    elev = None
    async with _client() as c:
        with contextlib.suppress(httpx.HTTPError, ValueError, KeyError, IndexError):
            r = await c.get(ELEVATION_URL, params={"latitude": body.latitude,
                                                   "longitude": body.longitude})
            if r.status_code == 200:
                elev = float(r.json()["elevation"][0])
    place = config.add_place(config.build_user_place(body.model_dump(), elev, body.role))
    task = asyncio.create_task(_refresh(LIGHT_COLLECTORS))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"place": place, "collecting": sorted(LIGHT_COLLECTORS),
            "note": ("Current data arrives within a minute. Climate normals, projections and "
                     "river levels are computed once, one place per scheduler run (hours).")}


_tasks: set[asyncio.Task] = set()


@router.delete("/api/places/{pid}", dependencies=[Depends(require_admin)])
def delete_place(pid: str) -> dict:
    _get(pid)
    if len(config.list_places()) <= 1:
        raise HTTPException(409, "keep at least one place")
    config.remove_place(pid)
    return {"removed": pid}
