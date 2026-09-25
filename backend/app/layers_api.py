"""GET /api/layers (map raster catalog) + GET /api/layers/verify (live tile check).

Dates of the GIBS layers come from the live WMTS capabilities (cached 6 h); the
RainViewer radar frame is resolved server-side (cached 10 min). A failing upstream
is reported in the response (`errors`), never hidden.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter

from . import layers as L
from .config import settings
from .layers_extra import EXTRA_LAYERS

# Merge the extra verified GIBS layers (NASA agent, layers_extra.py) into the one catalog.
for _x in EXTRA_LAYERS:
    if _x["id"] not in L.LAYERS_BY_ID:
        L.LAYERS.append(_x)
        L.LAYERS_BY_ID[_x["id"]] = _x

router = APIRouter()

_caps = L.TTLCache(6 * 3600)
_radar = L.TTLCache(600)
_verify = L.TTLCache(3600)
_lock = asyncio.Lock()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True,
                             headers={"User-Agent": settings.user_agent})


async def _dims(client: httpx.AsyncClient, errors: dict) -> dict | None:
    if (v := _caps.get()) is not None:
        return v
    try:
        r = await client.get(L.GIBS_CAPS_URL)
        r.raise_for_status()
        ids = {x["gibs_id"] for x in L.LAYERS}
        return _caps.put(L.parse_time_dimensions(r.text, ids))
    except Exception as e:  # noqa: BLE001
        errors["gibs_capabilities"] = f"{type(e).__name__}: {e}"[:200]
        return None


async def _radar_layer(client: httpx.AsyncClient, errors: dict) -> dict | None:
    if (v := _radar.get()) is not None:
        return v
    try:
        r = await client.get(L.RAINVIEWER_URL)
        r.raise_for_status()
        return _radar.put(L.parse_rainviewer(r.json()))
    except Exception as e:  # noqa: BLE001
        errors["rainviewer"] = f"{type(e).__name__}: {e}"[:200]
        return None


async def build_catalog(client: httpx.AsyncClient) -> dict:
    errors: dict[str, str] = {}
    dims, radar = await asyncio.gather(_dims(client, errors), _radar_layer(client, errors))
    today = datetime.now(UTC).date()
    out = []
    for layer in L.LAYERS:
        day, how = L.resolve_date(layer, dims, today)
        d = {k: v for k, v in layer.items() if k != "gibs_id"}
        d.update(source="nasa_gibs", gibs_layer=layer["gibs_id"], default_date=day,
                 date_source=how,
                 tiles=layer["url_template"].replace("{time}", day) if day else
                 layer["url_template"])
        out.append(d)
    if radar:
        out.append({**radar, "source": "rainviewer", "tiles": radar["url_template"],
                    "default_date": None, "date_source": "rainviewer"})
    return {"generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "layers": out, "errors": errors}


@router.get("/api/layers")
async def get_layers() -> dict:
    async with _client() as client:
        return await build_catalog(client)


@router.get("/api/layers/verify")
async def verify_layers(force: bool = False) -> dict:
    """Fetch one real tile per layer (z3 over SE Asia) for the date the catalog serves."""
    async with _lock:
        if not force and (v := _verify.get()) is not None:
            return v
        async with _client() as client:
            cat = await build_catalog(client)
            checks = []
            for layer in cat["layers"]:
                # `tiles` already has the date filled in; {z}/{x}/{y} are replaced by name
                res = await L.verify_layer(client, {**layer, "url_template": layer["tiles"]},
                                           None)
                res["date"] = layer.get("default_date") or layer.get("time") or "latest"
                checks.append(res)
        return _verify.put({"checked_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                            "checks": checks, "errors": cat["errors"]})
