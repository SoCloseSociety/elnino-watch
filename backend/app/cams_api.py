"""GET /api/webcams (+ /{id}, /{id}/snapshot): public webcams for "see it yourself".

The list comes from status `webcams`, rebuilt by the collectors in
app/collectors/extra_cams.py (rule 11: owner-published public feeds only).
Snapshots are proxied ONLY for cams whose provider allows redistribution
(`snapshot_allowed`: NOAA public domain, JMA open licence). Everything else is
shown through the owner's embed player or linked (`mode`: embed | link) and the
snapshot endpoint answers 409 with the official page instead.
"""

from __future__ import annotations

import asyncio
import math
import time

import httpx
from fastapi import APIRouter, HTTPException, Query, Response

from . import db
from .collectors.extra_cams import OK_STATES, STATUS_KEY
from .config import settings

router = APIRouter()

SNAPSHOT_TTL_S = 120          # short cache: satellites / buoys update every 10-60 min
SNAPSHOT_MAX_BYTES = 5_000_000
# Worst case SNAPSHOT_CACHE_MAX x SNAPSHOT_MAX_BYTES stays resident (the VPS service is
# capped at 550 MB): 6 x 5 MB = 30 MB, enough for the few cams a page shows at once.
SNAPSHOT_CACHE_MAX = 6
_cache: dict[str, tuple[float, bytes, dict]] = {}
_lock = asyncio.Lock()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _load() -> tuple[list[dict], str | None, dict | None]:
    s = db.get_status(STATUS_KEY)
    parts = db.get_status(STATUS_KEY + "_parts")
    cams = s["value"] if s and isinstance(s["value"], list) else []
    return cams, (s["updated_at"] if s else None), (parts["value"] if parts else None)


def _parse_near(near: str) -> tuple[float, float]:
    try:
        lat_s, lon_s = near.split(",")
        lat, lon = float(lat_s), float(lon_s)
    except ValueError:
        raise HTTPException(422, "near must be 'lat,lon'") from None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(422, "near out of range")
    return lat, lon


@router.get("/api/webcams")
def list_webcams(kind: str | None = None, area: str | None = None, near: str | None = None,
                 radius_km: float = Query(300.0, gt=0, le=20000),
                 alive: bool | None = None, confirmed: bool = False) -> dict:
    """kind: beach|pier|city|airport|buoy|satellite|traffic (comma list ok).
    near=lat,lon (+ radius_km) filters and sorts by distance (satellites have no
    meaningful position and are left out of a `near` query).
    alive=true: status live|online|reachable; alive=false: the rest.
    confirmed=true: only `live` (fresh image) and `online` (provider flag)."""
    cams, updated_at, parts = _load()
    out = [dict(c) for c in cams]
    if kind:
        kinds = {k.strip() for k in kind.split(",") if k.strip()}
        out = [c for c in out if c.get("kind") in kinds]
    if area:
        areas = {a.strip() for a in area.split(",") if a.strip()}
        out = [c for c in out if c.get("area") in areas]
    if alive is not None:
        out = [c for c in out if (c.get("status") in OK_STATES) == alive]
    if confirmed:
        out = [c for c in out if c.get("status") in ("live", "online")]
    if near:
        lat, lon = _parse_near(near)
        keep = []
        for c in out:
            if c.get("kind") == "satellite" or c.get("lat") is None or c.get("lon") is None:
                continue
            d = haversine_km(lat, lon, c["lat"], c["lon"])
            if d <= radius_km:
                c["distance_km"] = round(d, 1)
                keep.append(c)
        out = sorted(keep, key=lambda c: c["distance_km"])
    for c in out:
        c["snapshot_proxy"] = (f"/api/webcams/{c['id']}/snapshot"
                               if c.get("snapshot_allowed") and c.get("snapshot_url") else None)
    return {"updated_at": updated_at, "parts": parts, "count": len(out), "webcams": out,
            "home": {"name": settings.home_name, "lat": settings.home_lat,
                     "lon": settings.home_lon}}


def _find(cam_id: str) -> dict:
    cams, _, _ = _load()
    for c in cams:
        if c.get("id") == cam_id:
            return c
    raise HTTPException(404, f"unknown webcam {cam_id!r}")


@router.get("/api/webcams/{cam_id}")
def get_webcam(cam_id: str) -> dict:
    return _find(cam_id)


@router.get("/api/webcams/{cam_id}/snapshot")
async def snapshot(cam_id: str) -> Response:
    c = _find(cam_id)
    if not c.get("snapshot_allowed") or not c.get("snapshot_url"):
        raise HTTPException(409, {
            "error": "link_only", "mode": c.get("mode"), "page_url": c.get("page_url"),
            "embed_url": c.get("embed_url"), "license_note": c.get("license_note")})
    url = c["snapshot_url"]
    async with _lock:
        hit = _cache.get(url)
        if hit and time.monotonic() - hit[0] < SNAPSHOT_TTL_S:
            body, meta = hit[1], hit[2]
        else:
            body, meta = await _fetch(url)
            if len(_cache) >= SNAPSHOT_CACHE_MAX:
                _cache.pop(min(_cache, key=lambda k: _cache[k][0]))
            _cache[url] = (time.monotonic(), body, meta)
    headers = {
        "Cache-Control": f"public, max-age={SNAPSHOT_TTL_S}",
        "X-Cam-Status": str(c.get("status")),
        "X-Image-Updated-At": str(c.get("image_updated_at") or ""),
        "X-Source-Url": url,
        "X-License": (c.get("license_note") or "")[:200],
    }
    if meta.get("last-modified"):
        headers["Last-Modified"] = meta["last-modified"]
    return Response(content=body, media_type=meta.get("content-type", "image/jpeg"),
                    headers=headers)


async def _fetch(url: str) -> tuple[bytes, dict]:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0),
                                     follow_redirects=True,
                                     headers={"User-Agent": settings.user_agent}) as client:
            r = await client.get(url)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"upstream {type(e).__name__}") from None
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise HTTPException(502, f"upstream HTTP {r.status_code} ({ctype or 'no type'})")
    if len(r.content) > SNAPSHOT_MAX_BYTES:
        raise HTTPException(502, "upstream image too large to proxy")
    return r.content, {"content-type": ctype, "last-modified": r.headers.get("last-modified")}
