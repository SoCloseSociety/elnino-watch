"""NASA deep sources (all keyless, verified live 2026-09-24).

- nasa_power_samui         NASA POWER daily point data for Koh Samui + 2001-2020 monthly
                           climatology; cross-checked against Open-Meteo ERA5.
- nasa_gistemp             NASA GISS GISTEMP v4 global monthly temperature anomaly.
- nasa_worldview_snapshots NASA Worldview Snapshots: verified image URLs (Samui, Gulf of
                           Thailand, SE Asia haze, equatorial Pacific SST anomaly).
- nasa_cmr_latency         NASA Earthdata CMR: newest granule of key datasets (proves how
                           fresh the upstream satellite data is).
- nasa_grace_drought       NASA GRACE-FO data-assimilation drought indicator maps for Asia.
- nasa_gmao_s2s            NASA GMAO GEOS-S2S-3 Nino / Indian Ocean plume images.
- nasa_eo_iotd             NASA Earth Observatory Image of the Day, filtered to ENSO impacts.

Optional credential: none of these needs one. NASA Earthdata login (env EARTHDATA_TOKEN,
read with os.environ because config.py is not ours) would only be needed to download the
granules themselves, which we do not do; see EARTHDATA_TOKEN_ENV below.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import re
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import ClassVar
from urllib.parse import urlencode

import feedparser
import httpx

from .. import db
from ..config import settings
from .base import DAY, HOUR, Collector, RunContext, SourceChanged

EARTHDATA_TOKEN_ENV = "EARTHDATA_TOKEN"


def earthdata_token() -> str | None:
    """NASA Earthdata bearer token, if the owner set one (not needed by any collector here)."""
    return os.environ.get(EARTHDATA_TOKEN_ENV) or None


def _latest_notes(rows: list[dict], ctx: RunContext) -> None:
    latest: dict[str, tuple[str, float]] = {}
    for r in rows:
        cur = latest.get(r["series"])
        if cur is None or r["ts"] > cur[0]:
            latest[r["series"]] = (r["ts"], r["value"])
    ctx.notes["latest"] = {k: {"ts": v[0], "value": v[1]} for k, v in sorted(latest.items())}


def _http_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(UTC).replace(microsecond=0).isoformat()
    except (TypeError, ValueError):
        return None


async def get_retry(ctx: RunContext, url: str, tries: int = 2, **kw):
    """ctx.get with one retry on a connection-level error (some NASA hosts drop the odd
    TCP connect). HTTP errors are not retried: they are real answers."""
    for i in range(tries):
        try:
            return await ctx.get(url, **kw)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            if i == tries - 1:
                raise
            await asyncio.sleep(2)
    raise AssertionError("unreachable")


def _is_image(r) -> bool:
    return r.status_code == 200 and r.headers.get("content-type", "").startswith("image/")


# =========================================================================== NASA POWER

POWER_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_CLIM_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"
POWER_FILL = -999.0
# POWER parameter -> (series, unit)
POWER_DAILY = {
    "T2M": ("samui_power_t2m", "degC"),
    "T2M_MAX": ("samui_power_t2m_max", "degC"),
    "T2M_MIN": ("samui_power_t2m_min", "degC"),
    "PRECTOTCORR": ("samui_power_precip", "mm"),
    "RH2M": ("samui_power_rh", "%"),
    "WS10M": ("samui_power_wind10m", "m/s"),
    "ALLSKY_SFC_SW_DWN": ("samui_power_solar", "kWh/m2/day"),
}
POWER_CLIM_PARAMS = ("T2M", "T2M_MAX", "PRECTOTCORR", "ALLSKY_SFC_SW_DWN")
MONTHS3 = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def parse_power_daily(payload: dict) -> list[dict]:
    """POWER daily JSON -> rows. -999 (fill) days are skipped, never stored."""
    try:
        params = payload["properties"]["parameter"]
        fill = float(payload.get("header", {}).get("fill_value", POWER_FILL))
    except (KeyError, TypeError, AttributeError) as e:
        raise SourceChanged(f"POWER daily: no properties.parameter ({e})") from None
    missing = [p for p in POWER_DAILY if p not in params]
    if missing:
        raise SourceChanged(f"POWER daily lacks {missing}")
    rows = []
    for p, (series, unit) in POWER_DAILY.items():
        for day, v in params[p].items():
            if not re.fullmatch(r"\d{8}", day):
                raise SourceChanged(f"POWER daily: bad date key {day!r}")
            if v is None or float(v) <= fill:
                continue
            ts = f"{day[:4]}-{day[4:6]}-{day[6:]}"
            rows.append({"series": series, "ts": ts, "value": float(v), "unit": unit,
                         "meta": {"time_standard": "LST"}})
    return rows


def parse_power_climatology(payload: dict) -> dict:
    """POWER climatology JSON -> {period, units, months: {PARAM: {JAN..DEC, ANN}}}."""
    try:
        params = payload["properties"]["parameter"]
        header = payload.get("header", {})
    except (KeyError, TypeError) as e:
        raise SourceChanged(f"POWER climatology: no properties.parameter ({e})") from None
    out = {}
    for p in POWER_CLIM_PARAMS:
        m = params.get(p)
        if not isinstance(m, dict) or not all(k in m for k in MONTHS3):
            raise SourceChanged(f"POWER climatology lacks monthly values for {p}")
        out[p] = {k: float(m[k]) for k in [*MONTHS3, "ANN"] if k in m}
    units = {p: (payload.get("parameters", {}).get(p) or {}).get("units") for p in out}
    return {"period": header.get("range"), "units": units, "months": out}


def power_anomalies(rows: list[dict], clim: dict) -> list[dict]:
    """Daily mean temperature minus the 2001-2020 POWER mean of the same month."""
    t2m = clim["months"]["T2M"]
    out = []
    for r in rows:
        if r["series"] != "samui_power_t2m":
            continue
        month = MONTHS3[int(r["ts"][5:7]) - 1]
        out.append({"series": "samui_power_t2m_anom", "ts": r["ts"],
                    "value": round(r["value"] - t2m[month], 2), "unit": "degC",
                    "meta": {"baseline": "POWER 2001-2020 monthly mean", "normal": t2m[month]}})
    return out


def power_summary(rows: list[dict], clim: dict, days: int = 30) -> dict:
    """Last-N-days totals vs the POWER climatology (same-day expected values)."""
    by: dict[str, dict[str, float]] = {}
    for r in rows:
        by.setdefault(r["series"], {})[r["ts"]] = r["value"]
    rain = by.get("samui_power_precip", {})
    temp = by.get("samui_power_t2m", {})
    if not rain or not temp:
        return {}
    last = max(set(rain) & set(temp)) if set(rain) & set(temp) else max(rain)
    end = date.fromisoformat(last)
    window = [(end - timedelta(days=i)).isoformat() for i in range(days)]
    rain_days = [d for d in window if d in rain]
    temp_days = [d for d in window if d in temp]
    pm = clim["months"]["PRECTOTCORR"]
    tm = clim["months"]["T2M"]

    def mon(d: str) -> str:
        return MONTHS3[int(d[5:7]) - 1]

    rain_total = sum(rain[d] for d in rain_days)
    rain_normal = sum(pm[mon(d)] for d in rain_days)
    t_mean = sum(temp[d] for d in temp_days) / len(temp_days) if temp_days else None
    t_norm = sum(tm[mon(d)] for d in temp_days) / len(temp_days) if temp_days else None
    return {
        "last_day": last, "window_days": days,
        "days_with_rain_data": len(rain_days), "days_with_temp_data": len(temp_days),
        "precip_total_mm": round(rain_total, 1), "precip_normal_mm": round(rain_normal, 1),
        "precip_pct_of_normal": round(100 * rain_total / rain_normal) if rain_normal else None,
        "t2m_mean": None if t_mean is None else round(t_mean, 2),
        "t2m_normal": None if t_norm is None else round(t_norm, 2),
        "t2m_anom": None if t_mean is None else round(t_mean - t_norm, 2),
        "normal_period": clim.get("period"),
    }


def crosscheck_era5(rows: list[dict]) -> dict:
    """Compare POWER (MERRA-2 based) with Open-Meteo ERA5 already in the DB for the same days.
    Two independent reanalyses agreeing = more trust; a big gap = treat single-day values
    with care. Nothing is computed when the ERA5 series is not there yet."""
    pairs = {"samui_power_t2m_max": "samui_era5_temp_max",
             "samui_power_t2m_min": "samui_era5_temp_min",
             "samui_power_precip": "samui_era5_precip"}
    out = {}
    for ours, theirs in pairs.items():
        mine = {r["ts"]: r["value"] for r in rows if r["series"] == ours}
        if not mine:
            continue
        other = db.query(
            "SELECT ts, value FROM observations WHERE source='openmeteo_samui_era5' "
            "AND series=? AND ts>=?", (theirs, min(mine)))
        common = [(mine[o["ts"]], o["value"]) for o in other if o["ts"] in mine
                  and o["value"] is not None]
        if not common:
            out[ours] = {"compared_with": theirs, "days": 0}
            continue
        diffs = [a - b for a, b in common]
        entry = {"compared_with": theirs, "days": len(common),
                 "mean_diff": round(sum(diffs) / len(diffs), 2),
                 "mean_abs_diff": round(sum(abs(d) for d in diffs) / len(diffs), 2)}
        if ours == "samui_power_precip":
            entry["power_total_mm"] = round(sum(a for a, _ in common), 1)
            entry["era5_total_mm"] = round(sum(b for _, b in common), 1)
        out[ours] = entry
    return out


class NasaPowerSamui(Collector):
    name = "nasa_power_samui"
    title = "NASA POWER -- Koh Samui daily weather, sunshine and 2001-2020 normals"
    category = "local"
    provider = "NASA Langley POWER (MERRA-2, GEOS-IT, CERES FLASHFlux)"
    homepage = "https://power.larc.nasa.gov/"
    endpoint = POWER_DAILY_URL
    interval_s = 12 * HOUR
    freshness_basis = "observations"
    max_age_s = 6 * DAY  # temperature/rain lag ~2-3 days; solar ~5-7 days (only one series)
    description = (
        "NASA's satellite and model-based daily weather for the Koh Samui grid cell (about "
        "50 km wide, so it mixes land and sea): mean/max/min temperature, rain, humidity, wind "
        "and sunshine energy, plus the 2001-2020 monthly normals. Used as an independent "
        "cross-check of the Open-Meteo ERA5 numbers (status samui_power_crosscheck) and to say "
        "whether the last 30 days were wetter/drier and warmer than normal (status "
        "samui_power). Series: samui_power_t2m, samui_power_t2m_max, samui_power_t2m_min, "
        "samui_power_t2m_anom, samui_power_precip, samui_power_rh, samui_power_wind10m, "
        "samui_power_solar.")
    lookback_days: ClassVar[int] = 60

    def _params(self, today: date) -> dict:
        return {"parameters": ",".join(POWER_DAILY), "community": "RE",
                "longitude": settings.home_lon, "latitude": settings.home_lat,
                "start": (today - timedelta(days=self.lookback_days)).strftime("%Y%m%d"),
                "end": today.strftime("%Y%m%d"), "format": "JSON"}

    async def collect(self, ctx: RunContext) -> int:
        today = datetime.now(UTC).date()
        r = await ctx.get(POWER_DAILY_URL, params=self._params(today))
        rows = parse_power_daily(r.json())
        if not rows:
            return 0
        rc = await ctx.get(POWER_CLIM_URL, params={
            "parameters": ",".join(POWER_CLIM_PARAMS), "community": "RE",
            "longitude": settings.home_lon, "latitude": settings.home_lat, "format": "JSON"})
        clim = parse_power_climatology(rc.json())
        rows += power_anomalies(rows, clim)
        summary = power_summary(rows, clim)
        db.set_status("samui_power", {**summary, "source": "NASA POWER",
                                      "url": "https://power.larc.nasa.gov/data-access-viewer/",
                                      "climatology": clim})
        db.set_status("samui_power_crosscheck", {
            "checked_at": db.now_iso(), "pairs": crosscheck_era5(rows),
            "note": ("POWER uses a ~50 km grid cell (MERRA-2) and ERA5 a ~30 km one: both "
                     "smooth the island's own weather. Differences of 1-2 degC in daily "
                     "maxima are normal; use the trend, not a single day.")})
        _latest_notes(rows, ctx)
        return db.upsert_observations(self.name, rows)


# =========================================================================== GISTEMP

GISTEMP_URL = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
GISTEMP_ZON_URL = "https://data.giss.nasa.gov/gistemp/tabledata_v4/ZonAnn.Ts+dSST.csv"
_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_gistemp_monthly(text: str) -> list[dict]:
    """GLB.Ts+dSST.csv: title line, then `Year,Jan..Dec,J-D,...`; *** = not yet available."""
    lines = text.splitlines()
    try:
        hi = next(i for i, ln in enumerate(lines) if ln.startswith("Year,Jan,Feb"))
    except StopIteration:
        raise SourceChanged("GISTEMP: header 'Year,Jan,Feb,...' not found") from None
    rdr = csv.DictReader(lines[hi:])
    out = []
    for row in rdr:
        if not (row.get("Year") or "").isdigit():
            continue
        y = int(row["Year"])
        for i, m in enumerate(_MON, start=1):
            v = (row.get(m) or "").strip()
            if not v or v.startswith("*"):
                continue
            out.append({"series": "gistemp_global_anom", "ts": date(y, i, 15).isoformat(),
                        "value": float(v), "unit": "degC",
                        "meta": {"baseline": "1951-1980"}})
    if not out:
        raise SourceChanged("GISTEMP: no monthly values")
    return out


def parse_gistemp_zonal(text: str) -> list[dict]:
    """ZonAnn.Ts+dSST.csv: annual means by latitude band. We keep the tropics (24S-24N)."""
    rdr = csv.DictReader(io.StringIO(text))
    if not rdr.fieldnames or "24S-24N" not in rdr.fieldnames:
        raise SourceChanged("GISTEMP zonal: column 24S-24N not found")
    out = []
    for row in rdr:
        v = (row.get("24S-24N") or "").strip()
        if not (row.get("Year") or "").isdigit() or not v or v.startswith("*"):
            continue
        out.append({"series": "gistemp_tropics_annual_anom", "ts": f"{row['Year']}-07-01",
                    "value": float(v), "unit": "degC",
                    "meta": {"baseline": "1951-1980", "band": "24S-24N"}})
    if not out:
        raise SourceChanged("GISTEMP zonal: no values")
    return out


class NasaGistemp(Collector):
    name = "nasa_gistemp"
    title = "NASA GISTEMP v4 -- global temperature anomaly (monthly)"
    category = "ocean_index"
    provider = "NASA Goddard Institute for Space Studies (GISS)"
    homepage = "https://data.giss.nasa.gov/gistemp/"
    endpoint = GISTEMP_URL
    interval_s = 12 * HOUR
    freshness_basis = "observations"
    max_age_s = 60 * DAY  # month M is dated the 15th and published ~10th of month M+1
    description = (
        "How much warmer the whole planet (land + ocean) was each month than the 1951-1980 "
        "average, from NASA GISS. El Nino adds roughly 0.1-0.2 degC to the global number a few "
        "months after it peaks, on top of the long-term warming. Series: gistemp_global_anom "
        "(monthly), gistemp_tropics_annual_anom (yearly, 24S-24N).")

    async def collect(self, ctx: RunContext) -> int:
        rows = parse_gistemp_monthly((await ctx.get(GISTEMP_URL)).text)
        rows += parse_gistemp_zonal((await ctx.get(GISTEMP_ZON_URL)).text)
        _latest_notes(rows, ctx)
        return db.upsert_observations(self.name, rows)


# =========================================================================== Worldview

WVS_URL = "https://wvs.earthdata.nasa.gov/api/v1/snapshot"
WORLDVIEW_APP = "https://worldview.earthdata.nasa.gov/"
# An empty (no-data) snapshot is a ~1.2 kB black JPEG: anything this small is not an image.
WVS_MIN_BYTES = 5000

# id, title, bbox (S,W,N,E in EPSG:4326), layers, width, height, date offset days, description
SNAPSHOTS: tuple[dict, ...] = (
    {"id": "samui_truecolor", "title": "Koh Samui, true colour (VIIRS NOAA-20)",
     "bbox": (8.9, 99.4, 10.1, 100.6), "layers": ("VIIRS_NOAA20_CorrectedReflectance_TrueColor",
                                                   "Coastlines_15m"),
     "size": (720, 720), "lag": 1,
     "description": "Yesterday's satellite photo of Koh Samui, Koh Phangan and the coast: "
                    "clouds, storms, smoke and muddy river plumes."},
    {"id": "gulf_thailand_truecolor", "title": "Gulf of Thailand, true colour (VIIRS NOAA-20)",
     "bbox": (5.0, 98.0, 14.0, 106.0), "layers": ("VIIRS_NOAA20_CorrectedReflectance_TrueColor",
                                                   "Coastlines_15m"),
     "size": (720, 810), "lag": 1,
     "description": "The whole Gulf: storm systems approaching Samui and haze drifting in."},
    {"id": "seasia_aerosol", "title": "Southeast Asia smoke and haze (aerosol optical depth)",
     "bbox": (-10.0, 90.0, 25.0, 130.0), "layers": ("MODIS_Combined_Value_Added_AOD",
                                                     "Coastlines_15m"),
     "size": (800, 700), "lag": 1,
     "description": "Particles in the air. Yellow to red = thick smoke/haze; El Nino droughts "
                    "bring big fire-haze seasons in Sumatra and Borneo."},
    {"id": "pacific_ssta_east", "title": "Central and eastern Pacific SST anomaly (MUR)",
     "bbox": (-30.0, -180.0, 30.0, -70.0), "layers": (
         "GHRSST_L4_MUR_Sea_Surface_Temperature_Anomalies", "Coastlines_15m"),
     "size": (1100, 600), "lag": 1,
     "description": "Ocean temperature compared with normal. The dark red band along the "
                    "equator is El Nino's warm water."},
    {"id": "pacific_ssta_west", "title": "Western Pacific and Maritime Continent SST anomaly",
     "bbox": (-30.0, 90.0, 30.0, 180.0), "layers": (
         "GHRSST_L4_MUR_Sea_Surface_Temperature_Anomalies", "Coastlines_15m"),
     "size": (900, 600), "lag": 1,
     "description": "Ocean temperature compared with normal around Southeast Asia and the "
                    "western Pacific, including the Gulf of Thailand."},
)


def snapshot_url(snap: dict, day: str) -> str:
    s, w, n, e = snap["bbox"]
    q = {"REQUEST": "GetSnapshot", "TIME": day, "BBOX": f"{s},{w},{n},{e}",
         "CRS": "EPSG:4326", "LAYERS": ",".join(snap["layers"]), "FORMAT": "image/jpeg",
         "WIDTH": snap["size"][0], "HEIGHT": snap["size"][1]}
    return f"{WVS_URL}?{urlencode(q, safe=',:')}"


def worldview_link(snap: dict, day: str) -> str:
    s, w, n, e = snap["bbox"]
    return (f"{WORLDVIEW_APP}?v={w},{s},{e},{n}&l={','.join(snap['layers'])}&t={day}")


class NasaWorldviewSnapshots(Collector):
    name = "nasa_worldview_snapshots"
    title = "NASA Worldview snapshots -- Samui, Gulf of Thailand, SE Asia haze, Pacific SST"
    category = "satellite"
    provider = "NASA Worldview Snapshots (GIBS imagery)"
    homepage = WORLDVIEW_APP
    endpoint = WVS_URL
    interval_s = 6 * HOUR
    freshness_basis = "status"
    freshness_status_key = "snapshots"
    max_age_s = 2 * DAY
    description = (
        "Ready-made satellite pictures (not tiles) for a quick look: Koh Samui and the Gulf "
        "of Thailand in true colour, Southeast Asia smoke/haze, and the Pacific sea-surface "
        "temperature anomaly that shows El Nino. Each image URL is downloaded once to check it "
        "really contains data before it is listed. Status key: snapshots.")
    concurrency: ClassVar[int] = 2

    async def _one(self, ctx: RunContext, snap: dict, today: date) -> dict:
        last_err = None
        for lag in (snap["lag"], snap["lag"] + 1):
            day = (today - timedelta(days=lag)).isoformat()
            url = snapshot_url(snap, day)
            r = await ctx.client.get(url, timeout=120)
            if _is_image(r) and len(r.content) >= WVS_MIN_BYTES:
                return {"id": snap["id"], "title": snap["title"], "date": day, "url": url,
                        "worldview_url": worldview_link(snap, day),
                        "layers": list(snap["layers"]), "bbox": list(snap["bbox"]),
                        "width": snap["size"][0], "height": snap["size"][1],
                        "bytes": len(r.content), "description": snap["description"],
                        "verified_at": db.now_iso()}
            last_err = f"{day}: http {r.status_code} {r.headers.get('content-type')} " \
                       f"{len(r.content)} B"
        return {"id": snap["id"], "error": last_err}

    async def collect(self, ctx: RunContext) -> int:
        today = datetime.now(UTC).date()
        sem = asyncio.Semaphore(self.concurrency)

        async def guarded(s):
            async with sem:
                try:
                    return await self._one(ctx, s, today)
                except Exception as e:  # noqa: BLE001 -- one image must not sink the rest
                    return {"id": s["id"], "error": f"{type(e).__name__}: {e}"[:200]}

        res = await asyncio.gather(*(guarded(s) for s in SNAPSHOTS))
        ok = [x for x in res if "url" in x]
        ctx.notes["snapshots"] = {x["id"]: x.get("date") or x.get("error") for x in res}
        if not ok:
            raise RuntimeError(f"no snapshot verified: {ctx.notes['snapshots']}")
        ctx.last_status = 200
        db.set_status("snapshots", {"items": ok, "failed": [x for x in res if "error" in x],
                                    "source": "NASA Worldview Snapshots",
                                    "url": WORLDVIEW_APP})
        return len(ok)


# =========================================================================== CMR latency

CMR_GRANULES_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"
# short_name, label, why it matters, expected max lag (hours) between data end and now
CMR_DATASETS: tuple[dict, ...] = (
    {"id": "mur_sst", "short_name": "MUR-JPL-L4-GLOB-v4.1",
     "title": "MUR sea surface temperature (daily, 1 km)",
     "why": "Feeds the SST and SST-anomaly map layers.", "max_lag_h": 72},
    {"id": "oisst", "short_name": "AVHRR_OI-NCEI-L4-GLOB-v2.1",
     "title": "NOAA OISST v2.1 (daily, 25 km)",
     "why": "Basis of the daily Nino 3.4 and world SST series.", "max_lag_h": 72},
    {"id": "imerg_30min", "short_name": "GPM_3IMERGHHE",
     "title": "GPM IMERG Early, 30-minute rain",
     "why": "Near-real-time satellite rain (the 30-min rain layer).", "max_lag_h": 12},
    {"id": "imerg_daily_early", "short_name": "GPM_3IMERGDE", "title": "GPM IMERG Early, daily",
     "why": "Daily satellite rain (the daily rain layer).", "max_lag_h": 48},
    {"id": "imerg_daily_late", "short_name": "GPM_3IMERGDL", "title": "GPM IMERG Late, daily",
     "why": "Better-calibrated daily rain, about 14 h later.", "max_lag_h": 72},
    {"id": "smap_l4", "short_name": "SPL4SMGP", "title": "SMAP L4 soil moisture (3-hourly)",
     "why": "Root-zone soil moisture layer: drought in Thailand's farmland.", "max_lag_h": 96},
    {"id": "smap_l3", "short_name": "SPL3SMP_E", "title": "SMAP L3 surface soil moisture (daily)",
     "why": "Direct satellite soil-moisture measurement.", "max_lag_h": 72},
    {"id": "grace_fo", "short_name": "TELLUS_GRFO_L3_JPL_RL06.3_LND_v04",
     "title": "GRACE-FO land water storage (monthly)",
     "why": "Total water stored on land (groundwater, soil, lakes).", "max_lag_h": 120 * 24},
    {"id": "grace_dadm", "short_name": "GRACEDADM_CLSM025GL_7D",
     "title": "GRACE data-assimilation drought indicators (weekly)",
     "why": "Groundwater / soil drought percentiles (published maps lag ~2 months).",
     "max_lag_h": 120 * 24},
    {"id": "sentinel6_nrt", "short_name": "JASON_CS_S6A_L2_ALT_LR_STD_OST_NRT_F",
     "title": "Sentinel-6 Michael Freilich altimetry (near real time)",
     "why": "Sea surface height: the Kelvin waves that carry El Nino east.", "max_lag_h": 24},
    {"id": "nasa_ssh_grid", "short_name": "NASA_SSH_REF_SIMPLE_GRID_V1",
     "title": "NASA-SSH gridded sea surface height (science quality)",
     "why": "Science-quality sea level grids (lag several months).", "max_lag_h": 200 * 24},
)


def parse_cmr_latest(payload: dict, ds: dict, now: datetime) -> dict:
    try:
        entries = payload["feed"]["entry"]
    except (KeyError, TypeError) as e:
        raise SourceChanged(f"CMR: no feed.entry ({e})") from None
    base = {"id": ds["id"], "short_name": ds["short_name"], "title": ds["title"],
            "why": ds["why"], "max_lag_h": ds["max_lag_h"],
            "search_url": f"https://search.earthdata.nasa.gov/search?q={ds['short_name']}"}
    if not entries:
        return {**base, "state": "no_granules"}
    e = entries[0]
    end = e.get("time_end") or e.get("time_start")
    t = datetime.fromisoformat(end)
    lag_h = round((now - t).total_seconds() / 3600, 1)
    return {**base, "granule": e.get("producer_granule_id") or e.get("title"),
            "time_start": e.get("time_start"), "time_end": e.get("time_end"),
            "updated": e.get("updated"), "data_center": e.get("data_center"),
            "collection_concept_id": e.get("collection_concept_id"),
            "lag_h": lag_h, "late": lag_h > ds["max_lag_h"], "state": "ok"}


class NasaCmrLatency(Collector):
    name = "nasa_cmr_latency"
    title = "NASA Earthdata CMR -- how fresh key satellite datasets are"
    category = "satellite"
    provider = "NASA Earthdata Common Metadata Repository (CMR)"
    homepage = "https://cmr.earthdata.nasa.gov/search/"
    endpoint = CMR_GRANULES_URL
    interval_s = 3 * HOUR
    freshness_basis = "status"
    freshness_status_key = "nasa_dataset_latency"
    max_age_s = 12 * HOUR
    description = (
        "Asks NASA's catalogue for the newest file of each key dataset (MUR and OISST sea "
        "temperature, GPM IMERG rain, SMAP soil moisture, GRACE-FO water storage, Sentinel-6 "
        "sea level) and how many hours old its data is. It shows whether a map layer is "
        "behind because NASA itself is late. Status key: nasa_dataset_latency.")

    async def collect(self, ctx: RunContext) -> int:
        now = datetime.now(UTC)
        out = []
        for ds in CMR_DATASETS:
            try:
                r = await ctx.get(CMR_GRANULES_URL, params={
                    "short_name": ds["short_name"], "sort_key": "-start_date", "page_size": 1})
                out.append(parse_cmr_latest(r.json(), ds, now))
            except SourceChanged:
                raise
            except Exception as e:  # noqa: BLE001 -- keep the other datasets
                out.append({"id": ds["id"], "short_name": ds["short_name"],
                            "title": ds["title"], "state": "error",
                            "error": f"{type(e).__name__}: {e}"[:200]})
        ok = [d for d in out if d["state"] == "ok"]
        if not ok:
            raise RuntimeError(f"CMR: no dataset answered: {[d.get('error') for d in out]}")
        db.set_status("nasa_dataset_latency", {"checked_at": now.replace(microsecond=0)
                                               .isoformat(), "datasets": out,
                                               "url": "https://cmr.earthdata.nasa.gov/search/"})
        ctx.notes["lag_h"] = {d["id"]: d.get("lag_h") for d in out}
        return len(ok)


# =========================================================================== GRACE drought

GRACE_BASE = "https://nasagrace.unl.edu"
GRACE_DIR = f"{GRACE_BASE}/globaldata/"
GRACE_MAPS = (
    ("GWS", "Shallow groundwater drought"),
    ("RTZSM", "Root-zone soil moisture drought"),
    ("SFSM", "Surface soil moisture drought"),
)


def parse_grace_index(markup: str) -> list[str]:
    days = re.findall(r'HREF="/globaldata/(\d{8})/"', markup, re.IGNORECASE)
    if not days:
        raise SourceChanged("GRACE globaldata: no dated directories")
    return sorted(days)


def parse_grace_dir(markup: str, day: str, region: str = "AS") -> list[dict]:
    files = set(re.findall(r'HREF="(/globaldata/\d{8}/[^"]+)"', markup, re.IGNORECASE))
    out = []
    for code, label in GRACE_MAPS:
        png = f"/globaldata/{day}/GRACE_{code}_{region}_{day}.png"
        pdf = f"/globaldata/{day}/GRACE_{code}_{region}_{day}.pdf"
        if png in files:
            out.append({"id": code.lower(), "title": label, "url": GRACE_BASE + png,
                        "pdf": GRACE_BASE + pdf if pdf in files else None})
    return out


class NasaGraceDrought(Collector):
    name = "nasa_grace_drought"
    title = "NASA GRACE-FO drought indicators -- Asia maps (weekly)"
    category = "satellite"
    provider = "NASA GSFC / University of Nebraska-Lincoln NDMC (GRACE-FO data assimilation)"
    homepage = "https://nasagrace.unl.edu/"
    endpoint = GRACE_DIR
    interval_s = 12 * HOUR
    freshness_basis = "feed"
    max_age_s = 16 * DAY  # weekly maps (Mondays), posted the next day
    description = (
        "Weekly NASA maps of how wet or dry the ground is compared with 1948-2012, from the "
        "GRACE-FO gravity satellites combined with a land model: shallow groundwater, root-zone "
        "and surface soil moisture, as percentiles (dark red = driest 2 % of years). They show "
        "El Nino drought building in Thailand and Indonesia. Status key: grace_drought_asia.")

    async def collect(self, ctx: RunContext) -> int:
        days = parse_grace_index((await ctx.get(GRACE_DIR)).text)
        for day in reversed(days[-3:]):  # newest directory may still be filling
            maps = parse_grace_dir((await ctx.get(f"{GRACE_DIR}{day}/")).text, day)
            if len(maps) == len(GRACE_MAPS):
                break
        else:
            raise SourceChanged(f"GRACE: no complete Asia map set in {days[-3:]}")
        head = await ctx.client.head(maps[0]["url"])
        if head.status_code != 200:
            raise SourceChanged(f"GRACE: map image answered {head.status_code}")
        iso = f"{day[:4]}-{day[4:6]}-{day[6:]}"
        st = {"date": iso, "region": "Asia", "maps": maps, "baseline": "1948-2012",
              "posted_at": _http_date(head.headers.get("last-modified")),
              "url": "https://nasagrace.unl.edu/", "legend": (
                  "Wetness percentile: dark red <= 2, red 2-5, orange 5-10, tan 10-20, "
                  "yellow 20-30, white 30-70 (normal), light to dark blue 70-100 (wet).")}
        db.set_status("grace_drought_asia", st)
        ctx.notes["date"] = iso
        return db.upsert_feed_items(self.name, [{
            "ext_id": iso, "kind": "research", "lang": "en",
            "title": f"GRACE-based groundwater and soil moisture drought maps, Asia, {iso}",
            "summary": "Weekly NASA GRACE-FO drought indicator maps (wetness percentiles "
                       "vs 1948-2012) for groundwater, root-zone and surface soil moisture.",
            "url": maps[0]["url"], "image": maps[0]["url"], "author": "NASA / NDMC",
            "published_at": iso, "tags": ["drought", "thailand"]}])


# =========================================================================== GMAO GEOS-S2S

GMAO_PAGE = "https://gmao.gsfc.nasa.gov/gmao-products/geos-s2s-3/forecast-data_geos-s2s-3/plumes"
GMAO_LOOKUP = "https://gmao.gsfc.nasa.gov/lookup_images/"
GMAO_SLUG = "seasonal-decadal-analysis-prediction-v3"
GMAO_INDICES = (
    ("nino3.4", "Nino 3.4 (central Pacific, the main El Nino index)"),
    ("nino3", "Nino 3 (eastern Pacific)"),
    ("nino4", "Nino 4 (western-central Pacific)"),
    ("nino1.2", "Nino 1+2 (coast of Peru)"),
    ("idm", "Indian Ocean Dipole (west minus east Indian Ocean)"),
)
# gmao.gsfc.nasa.gov sometimes needs >10 s to accept a new TCP connection (seen 2026-09-24)
GMAO_TIMEOUT = httpx.Timeout(60.0, connect=30.0)
MON_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class NasaGmaoS2s(Collector):
    name = "nasa_gmao_s2s"
    title = "NASA GMAO GEOS-S2S-3 -- El Nino and Indian Ocean forecast plumes"
    category = "official"
    provider = "NASA Global Modeling and Assimilation Office (GMAO)"
    homepage = GMAO_PAGE
    endpoint = GMAO_LOOKUP
    interval_s = 12 * HOUR
    freshness_basis = "feed"
    max_age_s = 45 * DAY  # one release per month (early in the month)
    description = (
        "NASA's own seasonal forecast model: plume charts of where the Nino 3.4, 3, 4, 1+2 "
        "temperatures and the Indian Ocean Dipole are heading over the next 9 months (red line "
        "= average of the runs). Images only: NASA does not publish the numbers in a "
        "machine-readable form, so no value is extracted. Status key: gmao_s2s_plume.")

    async def _month(self, ctx: RunContext, y: int, m: int) -> list[dict]:
        out = []
        for idx, label in GMAO_INDICES:
            r = await get_retry(ctx, GMAO_LOOKUP, params={
                "slug": GMAO_SLUG, "type": "plumes", "month": MON_ABBR[m - 1], "year": y,
                "field1": idx, "field2": "gmao"}, timeout=GMAO_TIMEOUT)
            try:
                js = r.json()
            except json.JSONDecodeError:
                raise SourceChanged("GMAO lookup_images: not JSON") from None
            if not isinstance(js, dict) or "success" not in js:
                raise SourceChanged("GMAO lookup_images: no 'success' field")
            imgs = [u for u in js.get("images") or [] if "unavailable" not in u
                    and "coming-soon" not in u]
            if js["success"] and imgs:
                out.append({"index": idx, "title": label, "url": imgs[0]})
        return out

    async def collect(self, ctx: RunContext) -> int:
        now = datetime.now(UTC)
        y, m = now.year, now.month
        plumes: list[dict] = []
        for _ in range(3):
            plumes = await self._month(ctx, y, m)
            if plumes:
                break
            y, m = (y, m - 1) if m > 1 else (y - 1, 12)
        if not plumes:
            return 0
        first = await get_retry(ctx, plumes[0]["url"], timeout=GMAO_TIMEOUT)
        if not _is_image(first):
            raise SourceChanged(f"GMAO plume image answered {first.status_code}")
        posted = _http_date(first.headers.get("last-modified"))
        release = f"{y}-{m:02d}"
        st = {"release": release, "posted_at": posted, "model": "GEOS-S2S-3",
              "plumes": plumes, "url": GMAO_PAGE,
              "how_to_read": ("Each dashed line is one model run started on the date in the "
                              "legend; the thick red line is their average (ensemble mean). "
                              "Values are degrees C above (+) or below (-) normal. Above +0.5 "
                              "for Nino 3.4 = El Nino, above +1.5 = strong.")}
        db.set_status("gmao_s2s_plume", st)
        ctx.notes["release"] = release
        return db.upsert_feed_items(self.name, [{
            "ext_id": release, "kind": "official", "lang": "en",
            "title": f"NASA GMAO GEOS-S2S-3 ENSO forecast plumes, {release} release",
            "summary": "Nino 3.4 / 3 / 4 / 1+2 and Indian Ocean Dipole forecast plumes from "
                       "NASA's GEOS-S2S-3 seasonal model.",
            "url": GMAO_PAGE, "image": plumes[0]["url"], "author": "NASA GMAO",
            "published_at": posted or f"{release}-01", "tags": ["forecast"]}])


# =========================================================================== EO Image of the Day

EO_IOTD_URL = "https://earthobservatory.nasa.gov/feeds/image-of-the-day.rss"
EO_FILTER = re.compile(
    r"el ni[nñ]o|la ni[nñ]a|\benso\b|drought|heat ?wave|record heat|wildfire|fire|smoke|haze|"
    r"flood|monsoon|typhoon|cyclone|tropical storm|coral|bleach|marine heat|sea surface temp|"
    r"ocean temp|sea level|rainfall|thailand|samui|indonesia|borneo|sumatra|malaysia|vietnam|"
    r"cambodia|laos|myanmar|philippines|mekong|pacific|indian ocean|southeast asia",
    re.IGNORECASE)


EO_EXCLUDE = re.compile(r"aurora|\bmars\b|perseverance|\bmoon\b|lunar|space station|comet",
                        re.IGNORECASE)


def parse_eo_iotd(content: bytes) -> list[dict]:
    f = feedparser.parse(content)
    if not f.entries and (f.bozo or not f.feed):
        raise SourceChanged("EO Image of the Day: not an RSS feed")
    out = []
    for e in f.entries:
        title = e.get("title", "")
        summary = re.sub(r"<[^>]+>", " ", e.get("summary", "") or "")
        summary = re.sub(r"\s+", " ", summary).strip()
        blob = f"{title} {summary}"
        if not EO_FILTER.search(blob) or EO_EXCLUDE.search(title):
            continue
        pub = None
        if e.get("published_parsed"):
            pub = datetime(*e.published_parsed[:6], tzinfo=UTC).isoformat()
        tags = [t for t, rx in (("samui", r"samui"), ("thailand", r"thailand|thai\b"))
                if re.search(rx, blob, re.IGNORECASE)]
        if re.search(r"el ni[nñ]o|\benso\b", blob, re.IGNORECASE):
            tags.append("enso")
        img = None
        for m in e.get("media_content", []) or []:
            if m.get("url"):
                img = m["url"]
                break
        out.append({"ext_id": e.get("id") or e.get("link"), "kind": "research", "lang": "en",
                    "title": title, "summary": summary[:600], "url": e.get("link"),
                    "author": "NASA Earth Observatory", "image": img, "published_at": pub,
                    "tags": tags})
    return out


class NasaEoImageOfTheDay(Collector):
    name = "nasa_eo_iotd"
    title = "NASA Earth Observatory -- Image of the Day (ENSO and impact stories)"
    category = "news"
    provider = "NASA Earth Observatory"
    homepage = "https://earthobservatory.nasa.gov/topic/image-of-the-day"
    endpoint = EO_IOTD_URL
    interval_s = 6 * HOUR
    freshness_basis = "run"  # filtered: weeks without a matching story are normal
    description = (
        "NASA's daily satellite story, kept only when it is about El Nino, drought, heat, "
        "fire/haze, floods, storms, coral bleaching, the oceans or Southeast Asia. Explains "
        "impacts with images. Stored as feed items (kind research).")

    async def collect(self, ctx: RunContext) -> int:
        r = await ctx.get(EO_IOTD_URL)
        items = [i for i in parse_eo_iotd(r.content) if i["ext_id"]]
        ctx.notes["kept"] = len(items)
        return db.upsert_feed_items(self.name, items) if items else 0


COLLECTORS = [NasaPowerSamui, NasaGistemp, NasaWorldviewSnapshots, NasaCmrLatency,
              NasaGraceDrought, NasaGmaoS2s, NasaEoImageOfTheDay]
