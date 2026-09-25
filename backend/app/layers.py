"""Raster map layers for the MapLibre map: NASA GIBS (WMTS, keyless) + RainViewer radar.

Every GIBS layer below was checked on 2026-09-24 against the live service: the
identifier and tile matrix set come from the GIBS WMTSCapabilities (epsg3857/best),
and a z3 tile over SE Asia returned HTTP 200 with an image for the date shown in
`verified`. GIBS answers 404 (not a blank tile) for a date it does not have, so the
date is resolved from the capabilities `<Default>` at request time rather than guessed
from a fixed offset (SMAP, for instance, skips days). The fixed offset is only the
fallback when the capabilities document cannot be fetched.

Dropped after checking: VIIRS / MODIS thermal anomalies (GIBS serves them in EPSG:3857
only as Mapbox vector tiles, not raster; fires are on the map through FIRMS events).
"""

from __future__ import annotations

import re
import time
from datetime import UTC, date, datetime, timedelta

import httpx

GIBS_BASE = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best"
GIBS_CAPS_URL = f"{GIBS_BASE}/1.0.0/WMTSCapabilities.xml"
GIBS_LEGEND = "https://gibs.earthdata.nasa.gov/legends/{name}_H.svg"
RAINVIEWER_URL = "https://api.rainviewer.com/public/weather-maps.json"
# z3 tile x=6 y=3 covers 90-135 E, 0-41 N (Thailand, Indochina, S China Sea).
PROBE_Z, PROBE_Y, PROBE_X = 3, 3, 6

_EXT = {"png": "png", "jpeg": "jpg"}


def _gibs(layer: str, level: int, fmt: str, timed: bool = True) -> str:
    t = "{time}/" if timed else ""
    return (f"{GIBS_BASE}/{layer}/default/{t}GoogleMapsCompatible_Level{level}"
            f"/{{z}}/{{y}}/{{x}}.{_EXT[fmt]}")


# time_mode: "daily" -> url has {time} = YYYY-MM-DD ; "latest" -> no time (GIBS default).
# complete_day: prefer yesterday over a partial "today" mosaic (polar-orbit swath products).
LAYERS: list[dict] = [
    {
        "id": "sst_anomaly", "gibs_id": "GHRSST_L4_MUR_Sea_Surface_Temperature_Anomalies",
        "title": "Sea surface temperature anomaly",
        "url_template": _gibs("GHRSST_L4_MUR_Sea_Surface_Temperature_Anomalies", 7, "png"),
        "max_zoom": 7, "format": "png", "time_mode": "daily", "default_date_offset_days": 1,
        "legend_url": GIBS_LEGEND.format(name="GHRSST_Sea_Surface_Temperature_Anomalies"),
        "attribution": "NASA GIBS / JPL MUR SST (GHRSST L4)",
        "description": ("Ocean temperature departure from normal, in degrees C. The red "
                        "tongue along the equator in the Pacific is the signature of "
                        "El Nino."),
        "verified": {"date": "2026-09-23", "http": 200, "latency_ms": 1505},
    },
    {
        "id": "sst", "gibs_id": "GHRSST_L4_MUR_Sea_Surface_Temperature",
        "title": "Sea surface temperature",
        "url_template": _gibs("GHRSST_L4_MUR_Sea_Surface_Temperature", 7, "png"),
        "max_zoom": 7, "format": "png", "time_mode": "daily", "default_date_offset_days": 1,
        "legend_url": GIBS_LEGEND.format(name="GHRSST_Sea_Surface_Temperature"),
        "attribution": "NASA GIBS / JPL MUR SST (GHRSST L4)",
        "description": ("Ocean surface temperature (daily 1 km analysis). "
                        "Above ~30 degrees C around Samui, corals suffer."),
        "verified": {"date": "2026-09-23", "http": 200, "latency_ms": 1612},
    },
    {
        "id": "precip_imerg", "gibs_id": "IMERG_Precipitation_Rate",
        "title": "Rain (GPM IMERG, daily rate)",
        "url_template": _gibs("IMERG_Precipitation_Rate", 6, "png"),
        "max_zoom": 6, "format": "png", "time_mode": "daily", "default_date_offset_days": 1,
        "legend_url": GIBS_LEGEND.format(name="GPM_Precipitation_Rate"),
        "attribution": "NASA GIBS / GPM IMERG",
        "description": ("Satellite-estimated rain intensity. El Nino shifts rain toward "
                        "the central Pacific and dries out Southeast Asia."),
        "verified": {"date": "2026-09-23", "http": 200, "latency_ms": 1384},
    },
    {
        "id": "ir_himawari", "gibs_id": "Himawari_AHI_Band13_Clean_Infrared",
        "title": "Infrared clouds (Himawari, 10 min)",
        "url_template": _gibs("Himawari_AHI_Band13_Clean_Infrared", 6, "png", timed=False),
        "max_zoom": 6, "format": "png", "time_mode": "latest", "default_date_offset_days": None,
        "legend_url": GIBS_LEGEND.format(name="Clean_Longwave_Infrared_Window_Band"),
        "attribution": "NASA GIBS / JMA Himawari-9 AHI",
        "description": ("Latest infrared image from the Japanese geostationary satellite: "
                        "storms and typhoons over Asia and the western Pacific, day and night."),
        "verified": {"date": "latest", "http": 200, "latency_ms": 1793},
    },
    {
        "id": "truecolor_viirs", "gibs_id": "VIIRS_SNPP_CorrectedReflectance_TrueColor",
        "title": "True-colour satellite image (VIIRS)",
        "url_template": _gibs("VIIRS_SNPP_CorrectedReflectance_TrueColor", 9, "jpeg"),
        "max_zoom": 9, "format": "jpeg", "time_mode": "daily", "default_date_offset_days": 1,
        "complete_day": True, "legend_url": None,
        "attribution": "NASA GIBS / Suomi NPP VIIRS",
        "description": ("Today's view from the Suomi NPP satellite: clouds, fire smoke, "
                        "haze plumes."),
        "verified": {"date": "2026-09-23", "http": 200, "latency_ms": 1748},
    },
    {
        "id": "truecolor_modis", "gibs_id": "MODIS_Terra_CorrectedReflectance_TrueColor",
        "title": "True-colour satellite image (MODIS Terra)",
        "url_template": _gibs("MODIS_Terra_CorrectedReflectance_TrueColor", 9, "jpeg"),
        "max_zoom": 9, "format": "jpeg", "time_mode": "daily", "default_date_offset_days": 1,
        "complete_day": True, "legend_url": None,
        "attribution": "NASA GIBS / Terra MODIS",
        "description": "Today's view from the Terra satellite (morning pass).",
        "verified": {"date": "2026-09-23", "http": 200, "latency_ms": 1484},
    },
    {
        "id": "aerosol", "gibs_id": "MODIS_Combined_Value_Added_AOD",
        "title": "Aerosols / smoke (optical depth)",
        "url_template": _gibs("MODIS_Combined_Value_Added_AOD", 6, "png"),
        "max_zoom": 6, "format": "png", "time_mode": "daily", "default_date_offset_days": 1,
        "legend_url": GIBS_LEGEND.format(name="MODIS_Combined_Value_Added_AOD"),
        "attribution": "NASA GIBS / MODIS Terra+Aqua (MAIAC value-added AOD)",
        "description": ("Amount of particles in the air. Fires in Sumatra and Kalimantan "
                        "in El Nino years produce the regional haze."),
        "verified": {"date": "2026-09-23", "http": 200, "latency_ms": 1674},
    },
    {
        "id": "chlorophyll", "gibs_id": "OCI_PACE_Chlorophyll_a",
        "title": "Chlorophyll (PACE)",
        "url_template": _gibs("OCI_PACE_Chlorophyll_a", 7, "png"),
        "max_zoom": 7, "format": "png", "time_mode": "daily", "default_date_offset_days": 1,
        "complete_day": True,
        "legend_url": GIBS_LEGEND.format(name="MODIS_Chlorophyll"),
        "attribution": "NASA GIBS / PACE OCI",
        "description": ("Surface plankton. El Nino shuts off the upwelling of cold, "
                        "nutrient-rich water off Peru: chlorophyll drops there."),
        "verified": {"date": "2026-09-23", "http": 200, "latency_ms": 1956},
    },
    {
        "id": "soil_moisture", "gibs_id": "SMAP_L4_Analyzed_Root_Zone_Soil_Moisture",
        "title": "Soil moisture (root zone, SMAP)",
        "url_template": _gibs("SMAP_L4_Analyzed_Root_Zone_Soil_Moisture", 6, "png"),
        "max_zoom": 6, "format": "png", "time_mode": "daily", "default_date_offset_days": 3,
        "legend_url": GIBS_LEGEND.format(name="SMAP_Analyzed_Soil_Moisture"),
        "attribution": "NASA GIBS / SMAP L4",
        "description": ("Water available to crops. Dry soils in Thailand and Indonesia are "
                        "the first sign of El Nino drought."),
        "verified": {"date": "2026-09-21", "http": 200, "latency_ms": 2193},
    },
    {
        "id": "land_temp_day", "gibs_id": "MODIS_Terra_Land_Surface_Temp_Day",
        "title": "Land surface temperature (day, MODIS)",
        "url_template": _gibs("MODIS_Terra_Land_Surface_Temp_Day", 7, "png"),
        "max_zoom": 7, "format": "png", "time_mode": "daily", "default_date_offset_days": 1,
        "complete_day": True,
        "legend_url": GIBS_LEGEND.format(name="MODIS_Land_Surface_Temp"),
        "attribution": "NASA GIBS / Terra MODIS LST",
        "description": "Daytime land surface temperature: heatwaves.",
        "verified": {"date": "2026-09-23", "http": 200, "latency_ms": 1775},
    },
]

LAYERS_BY_ID = {x["id"]: x for x in LAYERS}


# --------------------------------------------------------------------------- dates

def parse_time_dimensions(caps_xml: str, ids: set[str]) -> dict[str, dict]:
    """GIBS capabilities -> {gibs_id: {default, ranges: [(start, end)]}} for daily layers."""
    out: dict[str, dict] = {}
    for block in re.findall(r"<Layer>(.*?)</Layer>", caps_xml, re.DOTALL):
        m = re.search(r"<ows:Identifier>(.*?)</ows:Identifier>", block)
        if not m or m.group(1) not in ids:
            continue
        dflt = re.search(r"<Default>(.*?)</Default>", block)
        ranges = []
        for v in re.findall(r"<Value>(.*?)</Value>", block):
            parts = v.split("/")
            if len(parts) >= 2 and len(parts[0]) == 10 and len(parts[1]) == 10:
                ranges.append((parts[0], parts[1]))
        out[m.group(1)] = {"default": dflt.group(1) if dflt else None, "ranges": ranges}
    return out


def _available(day: str, ranges: list[tuple[str, str]]) -> bool:
    return any(a <= day <= b for a, b in ranges)


def resolve_date(layer: dict, dims: dict | None, today: date) -> tuple[str | None, str]:
    """-> (date or None for latest-mode layers, how it was resolved)."""
    if layer["time_mode"] != "daily":
        return None, "latest"
    d = (dims or {}).get(layer["gibs_id"])
    if d and d.get("default"):
        chosen = d["default"][:10]
        if layer.get("complete_day") and chosen >= today.isoformat():
            y = (today - timedelta(days=1)).isoformat()
            if _available(y, d["ranges"]):
                chosen = y
        return chosen, "capabilities"
    return (today - timedelta(days=layer["default_date_offset_days"])).isoformat(), "offset"


def probe_url(layer: dict, day: str | None) -> str:
    return (layer["url_template"].replace("{time}", day or "")
            .replace("{z}", str(PROBE_Z)).replace("{y}", str(PROBE_Y))
            .replace("{x}", str(PROBE_X)))


async def verify_layer(client: httpx.AsyncClient, layer: dict, day: str | None) -> dict:
    t0 = time.monotonic()
    try:
        r = await client.get(probe_url(layer, day))
        ok = r.status_code == 200 and r.headers.get("content-type", "").startswith("image/")
        return {"id": layer["id"], "date": day or "latest", "http": r.status_code, "ok": ok,
                "content_type": r.headers.get("content-type"), "bytes": len(r.content),
                "latency_ms": int((time.monotonic() - t0) * 1000)}
    except httpx.HTTPError as e:
        return {"id": layer["id"], "date": day or "latest", "http": None, "ok": False,
                "error": f"{type(e).__name__}: {e}"[:200],
                "latency_ms": int((time.monotonic() - t0) * 1000)}


# --------------------------------------------------------------------------- RainViewer

def parse_rainviewer(payload: dict) -> dict:
    """weather-maps.json -> the latest past radar frame as a layer."""
    try:
        host = payload["host"]
        frame = payload["radar"]["past"][-1]
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError("RainViewer weather-maps.json: no radar.past frame") from e
    ts = datetime.fromtimestamp(frame["time"], UTC).isoformat()
    return {
        "id": "radar_rainviewer", "title": "Rain radar (RainViewer, latest frame)",
        "url_template": f"{host}{frame['path']}/256/{{z}}/{{x}}/{{y}}/2/1_1.png",
        # the public API serves real radar data up to z7 (z8 returns a placeholder tile)
        "max_zoom": 7, "format": "png", "time_mode": "resolved", "time": ts,
        "default_date_offset_days": None, "legend_url": None,
        "attribution": "RainViewer.com (national radar networks)",
        "description": ("Latest rain radar image (updated every 10 min). Coverage depends "
                        "on the national radars shared with RainViewer."),
        "frames": len(payload["radar"]["past"]),
    }


# --------------------------------------------------------------------------- caches

class TTLCache:
    def __init__(self, ttl_s: float) -> None:
        self.ttl_s = ttl_s
        self.value = None
        self.at = 0.0

    def get(self):
        return self.value if self.value is not None and time.monotonic() - self.at < self.ttl_s \
            else None

    def put(self, v):
        self.value, self.at = v, time.monotonic()
        return v
