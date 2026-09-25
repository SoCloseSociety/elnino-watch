"""Collectors for the Places comparison (all keyless, verified live on 2026-09-24).

Every collector loops over the configured places (app.places.config) and writes one
status document per place and kind, key `place:<id>:<kind>`, so adding a place needs
no schema change. A failing place never blocks the others: its error is recorded in
the run notes, and the run fails only if every place failed.

- places_forecast    Open-Meteo forecast: current conditions + 16-day daily + past 30 days
- places_climate     Open-Meteo ERA5 archive: 1991-2020 monthly normals (computed ONCE per
                     place, cached in `place:<id>:normals`) + the last 400 days (ERA5: one
                     bulk request per place under the heavy budget, then daily top-ups)
- places_air         Open-Meteo air quality (CAMS): current + 72 h forecast, pollen where
                     CAMS Europe covers it; plus the last 365 days of PM2.5 (global CAMS,
                     refreshed monthly) for a comparable annual mean
- places_marine      Open-Meteo marine: waves + sea temperature where a sea cell is near
- places_seasonal    Open-Meteo seasonal (ECMWF SEAS5): monthly anomalies, 6 months
- places_projection  Open-Meteo climate API (CMIP6 HighResMIP, bias-corrected on ERA5-Land):
                     1991-2020 vs 2036-2050 (computed ONCE per place)
- places_flood       Open-Meteo flood API (GloFAS v4): the largest river cell within ~15 km,
                     its 1991-2020 flood levels (ONCE) and the discharge forecast
- places_quakes      USGS FDSN: M2.5+ within 300 km (30 days) and M4.5+ within 300 km since
                     1976 (refreshed monthly)
- places_fires       NASA FIRMS VIIRS 24 h regional files: detections within 100 km
- places_warnings    Official warnings: Meteoalarm (EUMETNET; for France it carries the
                     Meteo-France vigilance) and the Hydrometcenter of Russia daily bulletin
                     of dangerous weather. Thailand: the TMD bulletins are already collected
                     by app.local (`tmd_warnings`), the engine reads them.
- places_advisories  Official travel advice: UK FCDO (GOV.UK content API), US State
                     Department (RSS), France Diplomatie (conseils aux voyageurs page)

Parsers are pure functions (`parse_*` / `build_*`) fed with real captured payloads in
tests/fixtures/places.
"""

from __future__ import annotations

import csv
import html
import io
import math
import re
import statistics
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from .. import db
from ..collectors.base import DAY, HOUR, Collector, RunContext, SourceChanged
from . import config

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
SEASONAL_URL = "https://seasonal-api.open-meteo.com/v1/seasonal"
CLIMATE_URL = "https://climate-api.open-meteo.com/v1/climate"
FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
FIRMS_URL = ("https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/"
             "SUOMI_VIIRS_C2_{region}_24h.csv")
METEOALARM_URL = "https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-{feed}"
HYDROMET_RU_URL = "https://meteoinfo.ru/hazardsbull"
FCDO_API = "https://www.gov.uk/api/content/foreign-travel-advice/{slug}"
FCDO_PAGE = "https://www.gov.uk/foreign-travel-advice/{slug}"
STATE_RSS = "https://travel.state.gov/_res/rss/TAsTWs.xml"
FR_DIPLO = ("https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/"
            "conseils-par-pays-destination/{slug}/")

NORMALS_START, NORMALS_END = "1991-01-01", "2020-12-31"
RIVER_START, RIVER_DAYS = "2001-01-01", 7305   # GloFAS flood levels: 2001-2020
PROJ_BASE = (1991, 2020)
PROJ_FUTURE = (2036, 2050)
# NICAM16_8S is left out to keep the request light (Open-Meteo weighs calls by variables x
# days); 6 models still give a spread.
CMIP6_MODELS = ("CMCC_CM2_VHR4", "FGOALS_f3_H", "HiRAM_SIT_HR", "MRI_AGCM3_2_S",
                "EC_Earth3P_HR", "MPI_ESM1_2_XR")
PROJ_DAILY = ("temperature_2m_max", "temperature_2m_min", "precipitation_sum")

QUAKE_RADIUS_KM = 300
FIRE_RADIUS_KM = 100
HEAT_FEELS_C = 35.0      # "heat day": ERA5 apparent (feels-like) max > 35 C
HOT_DAY_C = 35.0         # projections: air temperature max > 35 C (no feels-like in CMIP6)
HEAVY_RAIN_MM = 50.0
GUST_KMH = 75.0          # Beaufort 9 (strong gale) gust

FORECAST_DAILY = ("temperature_2m_max", "temperature_2m_min", "apparent_temperature_max",
                  "apparent_temperature_min", "precipitation_sum",
                  "precipitation_probability_max", "wind_gusts_10m_max", "uv_index_max",
                  "snowfall_sum")
FORECAST_CURRENT = ("temperature_2m", "apparent_temperature", "relative_humidity_2m",
                    "precipitation", "weather_code", "wind_speed_10m", "wind_gusts_10m",
                    "is_day")
NORMALS_DAILY = ("temperature_2m_mean", "temperature_2m_max", "temperature_2m_min",
                 "apparent_temperature_max", "precipitation_sum", "snowfall_sum",
                 "sunshine_duration", "wind_gusts_10m_max", "et0_fao_evapotranspiration")
AIR_CURRENT = ("pm2_5", "pm10", "us_aqi", "european_aqi", "alder_pollen", "birch_pollen",
               "grass_pollen", "mugwort_pollen", "olive_pollen", "ragweed_pollen")
POLLEN = AIR_CURRENT[4:]


def status_key(pid: str, kind: str) -> str:
    return f"place:{pid}:{kind}"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _today(tz: str) -> date:
    try:
        return datetime.now(ZoneInfo(tz)).date()
    except Exception:  # noqa: BLE001 -- unknown zone name: fall back to UTC
        return datetime.now(UTC).date()


def _num(v) -> float | None:
    return None if v is None else float(v)


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 2) if xs else None


def _need(block: dict | None, keys, what: str) -> dict:
    if not isinstance(block, dict) or "time" not in block:
        raise SourceChanged(f"{what}: no time axis")
    miss = [k for k in keys if k not in block]
    if miss:
        raise SourceChanged(f"{what}: missing {miss}")
    return block


# =========================================================================== parsers

def parse_forecast(payload: dict, today: date) -> dict:
    """Open-Meteo forecast (current + daily) -> {current, daily: [...], grid}.
    Days after `today` carry forecast=true; past days are model analyses."""
    daily = _need(payload.get("daily"), FORECAST_DAILY, "forecast daily")
    cur = payload.get("current")
    if not isinstance(cur, dict) or "time" not in cur:
        raise SourceChanged("forecast: no current block")
    days = []
    for i, ts in enumerate(daily["time"]):
        row = {"date": ts, "forecast": date.fromisoformat(ts) > today}
        for k in FORECAST_DAILY:
            row[k] = _num(daily[k][i])
        days.append(row)
    off = int(payload.get("utc_offset_seconds") or 0)
    cur_t = datetime.fromisoformat(cur["time"]).replace(tzinfo=UTC) - timedelta(seconds=off)
    return {
        "current": {k: _num(cur.get(k)) for k in FORECAST_CURRENT}
        | {"time": cur_t.isoformat(), "kind": "model_analysis"},
        "daily": days,
        "grid": {"lat": payload.get("latitude"), "lon": payload.get("longitude"),
                 "elevation": payload.get("elevation")},
        "units": payload.get("daily_units"),
    }


def build_normals(payload: dict, min_years: int = 25) -> dict:
    """ERA5 daily 1991-2020 -> monthly normals + annual indicators.

    Per calendar month, averaged over the years: mean of daily mean/max/min temperature;
    totals of precipitation, snowfall, sunshine, daylight and reference evapotranspiration
    (ET0); counts of rain days (>= 1 mm), heat days (feels-like max > 35 C), frost days
    (min < 0 C), heavy-rain days (>= 50 mm) and gust days (>= 75 km/h)."""
    d = _need(payload.get("daily"), NORMALS_DAILY, "ERA5 archive")
    per: dict[tuple[int, int], dict] = {}
    for i, ts in enumerate(d["time"]):
        y, m = int(ts[:4]), int(ts[5:7])
        v = {k: d[k][i] for k in NORMALS_DAILY}
        if v["temperature_2m_mean"] is None or v["precipitation_sum"] is None:
            continue
        a = per.setdefault((y, m), defaultdict(float) | {"tmean": [], "tmax": [], "tmin": []})
        a["tmean"].append(v["temperature_2m_mean"])
        a["tmax"].append(v["temperature_2m_max"])
        a["tmin"].append(v["temperature_2m_min"])
        a["precip"] += v["precipitation_sum"]
        a["snow"] += v["snowfall_sum"] or 0.0
        a["sun_h"] += (v["sunshine_duration"] or 0.0) / 3600
        a["et0"] += v["et0_fao_evapotranspiration"] or 0.0
        a["rain_days"] += v["precipitation_sum"] >= 1.0
        a["heavy_days"] += v["precipitation_sum"] >= HEAVY_RAIN_MM
        a["heat_days"] += (v["apparent_temperature_max"] or -99) > HEAT_FEELS_C
        a["frost_days"] += (v["temperature_2m_min"] if v["temperature_2m_min"] is not None
                            else 99) < 0
        a["gust_days"] += (v["wind_gusts_10m_max"] or 0) >= GUST_KMH
        a["n"] += 1
    years = sorted({y for y, _ in per})
    if len(years) < min_years:
        raise SourceChanged(f"ERA5 normals: only {len(years)} years")
    months = []
    for m in range(1, 13):
        rows = [per[(y, m)] for y in years if (y, m) in per and per[(y, m)]["n"] >= 25]
        if not rows:
            raise SourceChanged(f"ERA5 normals: no complete month {m}")

        def avg(k: str, rows=rows) -> float:
            return round(statistics.fmean(r[k] for r in rows), 2)

        def avg_list(k: str, rows=rows) -> float:
            return round(statistics.fmean(statistics.fmean(r[k]) for r in rows), 2)

        months.append({
            "month": m, "t_mean": avg_list("tmean"), "t_max": avg_list("tmax"),
            "t_min": avg_list("tmin"), "precip_mm": avg("precip"), "rain_days": avg("rain_days"),
            "sunshine_h": avg("sun_h"), "snow_cm": avg("snow"),
            "et0_mm": avg("et0"), "heat_days": avg("heat_days"), "frost_days": avg("frost_days"),
            "heavy_rain_days": avg("heavy_days"), "gust_days": avg("gust_days"),
        })
    tot = {k: round(sum(x[k] for x in months), 1) for k in (
        "precip_mm", "rain_days", "sunshine_h", "snow_cm", "et0_mm", "heat_days",
        "frost_days", "heavy_rain_days", "gust_days")}
    dry_months = [x["month"] for x in months if x["precip_mm"] < 0.5 * x["et0_mm"]]
    return {
        "source": "Open-Meteo archive (ECMWF ERA5 reanalysis)",
        "url": "https://open-meteo.com/en/docs/historical-weather-api",
        "period": f"{years[0]}-{years[-1]}", "years": len(years),
        "grid": {"lat": payload.get("latitude"), "lon": payload.get("longitude"),
                 "elevation": payload.get("elevation")},
        "months": months,
        "annual": tot | {
            "t_mean": round(statistics.fmean(x["t_mean"] for x in months), 2),
            "coldest_month_t_mean": min(x["t_mean"] for x in months),
            "warmest_month_t_mean": max(x["t_mean"] for x in months),
            "aridity_index": round(tot["precip_mm"] / tot["et0_mm"], 2) if tot["et0_mm"] else None,
            "dry_months": dry_months,
        },
        "notes": ("ERA5 is a ~30 km reanalysis: it smooths local extremes (rain peaks, "
                  "island and valley effects). Use these normals to compare places with each "
                  "other, not as station records."),
    }


def parse_recent(payload: dict) -> dict:
    """ERA5 last ~120 days -> daily precipitation and temperature list."""
    d = _need(payload.get("daily"), ("precipitation_sum", "temperature_2m_max",
                                     "temperature_2m_min"), "ERA5 recent")
    days = [{"date": ts, "precip": _num(d["precipitation_sum"][i]),
             "tmax": _num(d["temperature_2m_max"][i]), "tmin": _num(d["temperature_2m_min"][i])}
            for i, ts in enumerate(d["time"])]
    days = [x for x in days if x["precip"] is not None]
    if not days:
        raise SourceChanged("ERA5 recent: no data")
    return {"days": days, "last_day": days[-1]["date"]}


def parse_air(payload: dict, now: datetime | None = None) -> dict:
    """Air quality (GMT) -> current values + hourly PM2.5 (past 24 h and next 72 h)."""
    cur = payload.get("current")
    hourly = _need(payload.get("hourly"), ("pm2_5",), "air hourly")
    if not isinstance(cur, dict) or "time" not in cur:
        raise SourceChanged("air: no current block")
    if payload.get("utc_offset_seconds", 0) != 0:
        raise SourceChanged("air: expected GMT")
    now = now or datetime.now(UTC)
    pts = []
    for i, ts in enumerate(hourly["time"]):
        v = hourly["pm2_5"][i]
        if v is None:
            continue
        t = datetime.fromisoformat(ts).replace(tzinfo=UTC)
        pts.append({"ts": t.isoformat(), "pm2_5": float(v), "forecast": t > now})
    pollen = {k: _num(cur.get(k)) for k in POLLEN}
    return {
        "current": {k: _num(cur.get(k)) for k in AIR_CURRENT[:4]}
        | {"time": datetime.fromisoformat(cur["time"]).replace(tzinfo=UTC).isoformat()},
        "pollen": pollen if any(v is not None for v in pollen.values()) else None,
        "hourly_pm2_5": pts,
        "grid": {"lat": payload.get("latitude"), "lon": payload.get("longitude")},
    }


def build_air_year(payload: dict, min_days: int = 200) -> dict:
    """365 days of hourly PM2.5 (CAMS global) -> annual mean and daily exceedances.
    WHO 2021: annual guideline 5 ug/m3, 24 h guideline 15 ug/m3."""
    hourly = _need(payload.get("hourly"), ("pm2_5",), "air year")
    by_day: dict[str, list[float]] = defaultdict(list)
    for i, ts in enumerate(hourly["time"]):
        v = hourly["pm2_5"][i]
        if v is not None:
            by_day[ts[:10]].append(float(v))
    daily = {d: statistics.fmean(v) for d, v in by_day.items() if len(v) >= 18}
    if len(daily) < min_days:
        raise SourceChanged(f"air year: only {len(daily)} complete days")
    vals = list(daily.values())
    by_month: dict[str, list[float]] = defaultdict(list)
    for d, v in daily.items():
        by_month[d[5:7]].append(v)
    return {
        "period": f"{min(daily)} to {max(daily)}", "days": len(daily),
        "pm25_annual_mean": round(statistics.fmean(vals), 1),
        "days_over_15": sum(v > 15 for v in vals),
        "days_over_37_5": sum(v > 37.5 for v in vals),
        "worst_day": round(max(vals), 1),
        "monthly_mean": {m: round(statistics.fmean(v), 1) for m, v in sorted(by_month.items())},
        "model": "CAMS global (Open-Meteo air quality, domains=cams_global)",
    }


def parse_marine(payload: dict, lat: float, lon: float) -> dict:
    """Marine API snaps to the nearest sea cell. Inland points come back with nulls."""
    cur = payload.get("current")
    if not isinstance(cur, dict) or "time" not in cur:
        raise SourceChanged("marine: no current block")
    wh, sst = _num(cur.get("wave_height")), _num(cur.get("sea_surface_temperature"))
    daily = payload.get("daily") or {}
    days = [{"date": ts, "wave_height_max": _num((daily.get("wave_height_max") or [])[i])}
            for i, ts in enumerate(daily.get("time") or [])]
    clat, clon = payload.get("latitude"), payload.get("longitude")
    dist = (round(haversine_km(lat, lon, clat, clon), 1)
            if clat is not None and clon is not None else None)
    sea = wh is not None or sst is not None
    return {"sea_cell": sea, "cell": {"lat": clat, "lon": clon},
            "cell_distance_km": dist if sea else None,
            "current": {"wave_height": wh, "sea_surface_temperature": sst,
                        "time": datetime.fromisoformat(cur["time"]).replace(tzinfo=UTC).isoformat()},
            "daily": days if sea else []}


def _proj_window(payload: dict, models: tuple[str, ...], years: tuple[int, int],
                 min_cover: float) -> dict[str, dict]:
    """One window of CMIP6 daily data -> per-model yearly statistics. The daily mean is
    taken as (max + min) / 2 (the usual approximation; saves a variable in the request)."""
    d = payload.get("daily")
    if not isinstance(d, dict) or "time" not in d:
        raise SourceChanged("climate API: no daily.time")
    out = {}
    need = (years[1] - years[0] + 1) * 365.25 * min_cover
    for m in models:
        keys = {v: f"{v}_{m}" for v in PROJ_DAILY}
        if any(k not in d for k in keys.values()):
            continue
        tmean, precip, hot, frost = [], [], 0, 0
        for i, ts in enumerate(d["time"]):
            if not years[0] <= int(ts[:4]) <= years[1]:
                continue
            tx, tn, pr = (d[keys[v]][i] for v in PROJ_DAILY)
            if tx is None or tn is None or pr is None:
                continue
            tmean.append((tx + tn) / 2)
            precip.append(pr)
            hot += tx > HOT_DAY_C
            frost += tn < 0
        n = len(tmean)
        if n < need or n == 0:
            continue
        out[m] = {"t_mean": round(statistics.fmean(tmean), 2),
                  "precip_mm_yr": round(sum(precip) / n * 365.25, 0),
                  "hot_days_yr": round(hot / n * 365.25, 1),
                  "frost_days_yr": round(frost / n * 365.25, 1)}
    return out


def build_projection(base_payload: dict, fut_payload: dict,
                     base_years: tuple[int, int] = (1991, 2020),
                     future: tuple[int, int] = PROJ_FUTURE,
                     models: tuple[str, ...] = CMIP6_MODELS, min_cover: float = 0.8,
                     min_models: int = 3) -> dict:
    """CMIP6 daily: baseline window vs future window, per model, then the ensemble mean
    change with the model range. Only models with >= 80% valid days in both windows."""
    base = _proj_window(base_payload, models, base_years, min_cover)
    fut = _proj_window(fut_payload, models, future, min_cover)
    return combine_projection(base, fut, base_years, future, min_models,
                              {"lat": base_payload.get("latitude"),
                               "lon": base_payload.get("longitude")})


def combine_projection(base: dict, fut: dict, base_years: tuple[int, int] = (1991, 2020),
                       future: tuple[int, int] = PROJ_FUTURE, min_models: int = 3,
                       grid: dict | None = None) -> dict:
    out_models = {}
    for m in sorted(set(base) & set(fut)):
        b, f = base[m], fut[m]
        out_models[m] = {"baseline": b, "future": f, "delta": {
            "t_mean": round(f["t_mean"] - b["t_mean"], 2),
            "precip_pct": round(100 * (f["precip_mm_yr"] - b["precip_mm_yr"])
                                / b["precip_mm_yr"], 1) if b["precip_mm_yr"] else None,
            "hot_days_yr": round(f["hot_days_yr"] - b["hot_days_yr"], 1),
            "frost_days_yr": round(f["frost_days_yr"] - b["frost_days_yr"], 1)}}
    if len(out_models) < min_models:
        raise SourceChanged(f"climate API: only {len(out_models)} usable models")

    def ens(section: str, k: str) -> dict:
        vals = [x[section][k] for x in out_models.values() if x[section][k] is not None]
        return {"mean": round(statistics.fmean(vals), 2), "min": min(vals), "max": max(vals)}

    keys = ("t_mean", "precip_mm_yr", "hot_days_yr", "frost_days_yr")
    return {
        "source": "Open-Meteo climate API (CMIP6 HighResMIP, bias-corrected on ERA5-Land 10 km)",
        "url": "https://open-meteo.com/en/docs/climate-api",
        "scenario": "HighResMIP future forcing, as close to RCP8.5 / SSP5-8.5 as CMIP6 allows",
        "baseline": f"{base_years[0]}-{base_years[1]}", "future": f"{future[0]}-{future[1]}",
        "models": sorted(out_models), "n_models": len(out_models),
        "per_model": out_models,
        "baseline_mean": {k: ens("baseline", k) for k in keys},
        "future_mean": {k: ens("future", k) for k in keys},
        "delta": {k: ens("delta", k) for k in
                  ("t_mean", "precip_pct", "hot_days_yr", "frost_days_yr")},
        "grid": grid,
        "note": ("Daily mean = (max + min) / 2. Hot day = model daily max > 35 C (air "
                 "temperature, not feels-like). Models are ~20-50 km, statistically "
                 "downscaled; the spread between models is part of the answer."),
    }


def grid_points(lat: float, lon: float, n: int = 3, step: float = 0.05) -> list[tuple]:
    return [(round(lat + i * step, 4), round(lon + j * step, 4))
            for i in range(-n, n + 1) for j in range(-n, n + 1)]


def choose_river_cell(payload: list | dict, lat: float, lon: float,
                      min_mean_m3s: float = 1.0) -> dict | None:
    """Multi-location flood API answer -> the cell with the largest mean discharge
    (the main river near the place). None if nothing reaches `min_mean_m3s`."""
    rows = payload if isinstance(payload, list) else [payload]
    best = None
    for r in rows:
        q = [v for v in ((r.get("daily") or {}).get("river_discharge") or []) if v is not None]
        if not q:
            continue
        m = statistics.fmean(q)
        if best is None or m > best["mean_m3s"]:
            best = {"lat": r.get("latitude"), "lon": r.get("longitude"),
                    "elevation": r.get("elevation"), "mean_m3s": round(m, 2)}
    if best is None:
        raise SourceChanged("flood API: no discharge in any cell")
    if best["mean_m3s"] < min_mean_m3s:
        return None
    best["distance_km"] = round(haversine_km(lat, lon, best["lat"], best["lon"]), 1)
    return best


def build_river_climate(payload: dict, min_years: int = 10) -> dict:
    """GloFAS reanalysis 2001-2020 daily discharge at one cell -> flood reference levels:
    median annual maximum (~2-year flood), 90th percentile of annual maxima (~10-year),
    and the daily 99th percentile."""
    d = _need(payload.get("daily"), ("river_discharge",), "flood history")
    by_year: dict[str, list[float]] = defaultdict(list)
    allv = []
    for i, ts in enumerate(d["time"]):
        v = d["river_discharge"][i]
        if v is not None:
            by_year[ts[:4]].append(float(v))
            allv.append(float(v))
    maxima = sorted(max(v) for v in by_year.values() if len(v) >= 300)
    if len(maxima) < min_years:
        raise SourceChanged(f"flood history: only {len(maxima)} complete years")
    q = statistics.quantiles(allv, n=100)
    return {"years": len(maxima), "period": f"{min(by_year)}-{max(by_year)}",
            "mean_m3s": round(statistics.fmean(allv), 2),
            "p99_daily_m3s": round(q[98], 2),
            "q2_m3s": round(statistics.median(maxima), 2),
            "q10_m3s": round(statistics.quantiles(maxima, n=10)[8], 2),
            "max_m3s": round(maxima[-1], 2)}


def parse_flood_forecast(payload: dict) -> dict:
    d = _need(payload.get("daily"), ("river_discharge", "river_discharge_max"), "flood fc")
    days = [{"date": ts, "q": _num(d["river_discharge"][i]),
             "q_ens_max": _num(d["river_discharge_max"][i])} for i, ts in enumerate(d["time"])]
    return {"days": [x for x in days if x["q"] is not None]}


def parse_usgs_near(payload: dict, lat: float, lon: float) -> list[dict]:
    if payload.get("type") != "FeatureCollection" or "features" not in payload:
        raise SourceChanged("USGS: not a FeatureCollection")
    out = []
    for f in payload["features"]:
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        c = g.get("coordinates") or []
        if p.get("mag") is None or len(c) < 2:
            continue
        out.append({"id": f.get("id"), "mag": float(p["mag"]), "place": p.get("place"),
                    "time": datetime.fromtimestamp(p["time"] / 1000, UTC).isoformat(),
                    "url": p.get("url"), "lat": c[1], "lon": c[0],
                    "depth_km": c[2] if len(c) > 2 else None,
                    "distance_km": round(haversine_km(lat, lon, c[1], c[0]), 0)})
    return sorted(out, key=lambda q: q["time"], reverse=True)


def firms_region(lat: float, lon: float) -> str | None:
    """Which FIRMS regional file covers a point. Extents checked on the live 24 h files
    (2026-09-24): Europe -21.8..35.0 E, 34..66 N; Russia_Asia 26..179 E, 9..72 N;
    SouthEast_Asia 93.8..160.7 E, -12..30.6 N. First match wins."""
    if -12 <= lat <= 29 and 89 <= lon <= 161:
        return "SouthEast_Asia"
    if 34 <= lat <= 72 and -25 <= lon <= 35:
        return "Europe"
    if 30 <= lat <= 82 and 26 <= lon <= 180:
        return "Russia_Asia"
    if 0 <= lat <= 40 and 60 <= lon <= 99:
        return "South_Asia"
    if -40 <= lat <= 38 and -20 <= lon <= 55:
        return "Northern_and_Central_Africa" if lat > -5 else "Southern_Africa"
    if lat >= 12 and lon <= -50:
        return "USA_contiguous_and_Hawaii" if lat < 50 else "Canada"
    if lat < 12 and lon <= -30:
        return "South_America"
    if lat < -10 and lon >= 110:
        return "Australia_NewZealand"
    return None


def parse_firms_near(text: str, lat: float, lon: float, radius_km: float = FIRE_RADIUS_KM
                     ) -> dict:
    rdr = csv.DictReader(io.StringIO(text))
    need = {"latitude", "longitude", "confidence", "frp", "acq_date", "acq_time"}
    if not rdr.fieldnames or not need <= set(rdr.fieldnames):
        raise SourceChanged(f"FIRMS CSV columns changed: {rdr.fieldnames}")
    det, newest = [], None
    for row in rdr:
        if (row.get("confidence") or "").lower() in ("low", "l"):
            continue
        try:
            la, lo = float(row["latitude"]), float(row["longitude"])
        except ValueError:
            continue
        if abs(la - lat) > 2 or abs(lo - lon) > 3:
            continue
        dk = haversine_km(lat, lon, la, lo)
        if dk <= radius_km:
            t = row["acq_time"].zfill(4)
            at = f"{row['acq_date']}T{t[:2]}:{t[2:]}:00+00:00"
            newest = max(newest or at, at)
            det.append({"d": dk, "frp": float(row["frp"] or 0)})
    return {"radius_km": radius_km, "count": len(det),
            "count_50km": sum(1 for x in det if x["d"] <= 50),
            "nearest_km": round(min(x["d"] for x in det), 1) if det else None,
            "frp_total_mw": round(sum(x["frp"] for x in det), 1), "newest": newest}


CAP_NS = {"atom": "http://www.w3.org/2005/Atom", "cap": "urn:oasis:names:tc:emergency:cap:1.2"}
SEVERITY_LEVEL = {"minor": 0, "moderate": 1, "severe": 2, "extreme": 3}
COLOUR = {0: "green", 1: "yellow", 2: "orange", 3: "red"}


def parse_meteoalarm(xml_text: str) -> dict:
    """Meteoalarm legacy Atom (CAP 1.2 fields) -> list of warnings. Minor = green,
    Moderate = yellow, Severe = orange, Extreme = red (Meteoalarm colour convention)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise SourceChanged(f"Meteoalarm: not XML ({e})") from e
    if not root.tag.endswith("feed"):
        raise SourceChanged("Meteoalarm: not an Atom feed")
    out = []
    for e in root.findall("atom:entry", CAP_NS):
        def t(tag: str, e=e) -> str | None:
            x = e.find(tag, CAP_NS)
            return x.text.strip() if x is not None and x.text else None
        sev = (t("cap:severity") or "").lower()
        lvl = SEVERITY_LEVEL.get(sev)
        out.append({"area": t("cap:areaDesc"), "event": t("cap:event"), "severity": sev,
                    "level": lvl, "colour": COLOUR.get(lvl) if lvl is not None else None,
                    "title": t("atom:title"), "onset": t("cap:onset"),
                    "effective": t("cap:effective"), "expires": t("cap:expires"),
                    "sent": t("cap:sent"),
                    "emma_id": t("cap:geocode/atom:value")})
    updated = root.find("atom:updated", CAP_NS)
    return {"updated": updated.text if updated is not None else None, "warnings": out}


def meteoalarm_for(doc: dict, areas: list[str], now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(UTC)
    wanted = {a.casefold() for a in areas}
    out = []
    for w in doc.get("warnings") or []:
        if (w.get("area") or "").casefold() not in wanted:
            continue
        exp = w.get("expires")
        try:
            if exp and datetime.fromisoformat(exp) < now:
                continue
        except ValueError:
            pass
        out.append(w)
    return out


_TAG = re.compile(r"<[^>]+>")
RU_MONTHS = {m: i + 1 for i, m in enumerate([
    "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября",
    "октября", "ноября", "декабря"])}
# wording of the most severe phenomena in the bulletin (Roshydromet "opasnye yavleniya")
RU_SEVERE = ("очень сильн", "ураган", "смерч", "сильная жара", "аномально", "сильный мороз",
             "крупный град", "сильный ливень")


def _text(fragment: str) -> str:
    t = html.unescape(_TAG.sub(" ", fragment.replace("<br>", "\n").replace("<br />", "\n")))
    return re.sub(r"[ \t\xa0]+", " ", t).strip()


def parse_hydromet_bulletin(markup: str) -> dict:
    """Hydrometcenter of Russia 'bulletin of dangerous and adverse weather' page ->
    {number, date, forecast: {district: text}, observed: {district: text}}.
    Russian text is third-party content and kept as published."""
    i = markup.find('<div id="div_1">')
    if i < 0:
        raise SourceChanged("meteoinfo bulletin: div_1 not found")
    j = markup.find("</table>", i)
    body = markup[i:j if j > 0 else i + 60000]
    head = re.search(r"№\s*(\d+)\s+(\d{1,2})\s+([а-я]+)\s+(\d{4})", _text(body))
    if not head or head.group(3) not in RU_MONTHS:
        raise SourceChanged("meteoinfo bulletin: no number/date header")
    issued = date(int(head.group(4)), RU_MONTHS[head.group(3)], int(head.group(2)))
    split = body.find("ФАКТИЧЕСКИЕ")
    parts = {"forecast": body[:split] if split > 0 else body,
             "observed": body[split:] if split > 0 else ""}
    out: dict = {"number": int(head.group(1)), "date": issued.isoformat(),
                 "url": HYDROMET_RU_URL}
    for k, frag in parts.items():
        sec: dict[str, str] = {}
        for m in re.finditer(r"<b>\s*([^<]*?)\.\s*</b>(.*?)(?=<b>|</p>|$)", frag, re.DOTALL):
            name = _text(m.group(1))
            if name:
                sec[name] = _text(m.group(2))
        out[k] = sec
    if not out["forecast"]:
        raise SourceChanged("meteoinfo bulletin: no district sections")
    return out


def hydromet_for(bulletin: dict, stem: str) -> dict:
    """Sentences of the bulletin that name the region (by stem), forecast and observed."""
    def hits(sec: dict) -> list[str]:
        out = []
        for district, text in sec.items():
            for s in re.split(r"(?<=\.)\s+", text):
                if stem.casefold() in s.casefold():
                    out.append(f"{district}: {s.strip()}")
        return out
    fc, ob = hits(bulletin.get("forecast") or {}), hits(bulletin.get("observed") or {})
    severe = any(w in s.casefold() for s in fc for w in RU_SEVERE)
    return {"forecast_mentions": fc, "observed_mentions": ob, "severe_wording": severe}


FCDO_ALERTS = {
    "avoid_all_travel_to_whole_country": "Advises against all travel to the whole country",
    "avoid_all_travel_to_parts": "Advises against all travel to parts of the country",
    "avoid_all_but_essential_travel_to_whole_country":
        "Advises against all but essential travel to the whole country",
    "avoid_all_but_essential_travel_to_parts":
        "Advises against all but essential travel to parts of the country",
}


def parse_fcdo(payload: dict, slug: str) -> dict:
    det = payload.get("details")
    if not isinstance(det, dict) or "alert_status" not in det:
        raise SourceChanged("FCDO: no details.alert_status")
    alerts = det.get("alert_status") or []
    return {"provider": "UK FCDO", "title": payload.get("title"),
            "updated": payload.get("public_updated_at"),
            "reviewed": det.get("reviewed_at"),
            "headline": "; ".join(FCDO_ALERTS.get(a, a.replace("_", " ")) for a in alerts)
            or "No FCDO advice against travel",
            "alert_status": alerts,
            "latest_change": (det.get("change_description") or "").strip() or None,
            "url": FCDO_PAGE.format(slug=slug)}


def parse_state_rss(xml_text: str) -> dict[str, dict]:
    """US State Department advisories RSS -> {country title: {level, headline, date, url}}."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise SourceChanged(f"State RSS: not XML ({e})") from e
    out = {}
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        m = re.match(r"(.+?) - Level (\d): (.+)", title)
        if not m:
            continue
        pub = it.findtext("pubDate")
        pub_iso = None
        if pub:
            try:
                pub_iso = parsedate_to_datetime(pub).date().isoformat()
            except (TypeError, ValueError):
                try:  # the feed often has no time: "Tue, 07 Jul 2026"
                    pub_iso = (datetime.strptime(pub.strip(), "%a, %d %b %Y")
                               .replace(tzinfo=UTC).date().isoformat())
                except ValueError:
                    pub_iso = None
        out[m.group(1).strip()] = {"provider": "US Department of State",
                                   "level": int(m.group(2)),
                                   "headline": f"Level {m.group(2)}: {m.group(3).strip()}",
                                   "updated": pub_iso, "url": (it.findtext("link") or "").strip()}
    if not out:
        raise SourceChanged("State RSS: no 'Country - Level N' items")
    return out


FR_MONTHS = {m: i + 1 for i, m in enumerate([
    "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
    "octobre", "novembre", "décembre"])}


def parse_fr_diplomatie(markup: str, url: str) -> dict:
    m = re.search(r"Derni[eè]re mise [àa] jour le\s*:\s*(\d{1,2})\s+([a-zéû]+)\s+(\d{4})",
                  markup)
    if not m or m.group(2) not in FR_MONTHS:
        raise SourceChanged("France Diplomatie: no 'Derniere mise a jour' date")
    upd = date(int(m.group(3)), FR_MONTHS[m.group(2)], int(m.group(1))).isoformat()
    heads, links = [], []
    for href, title in re.findall(
            r'<a href="(/fr/information-par-pays/alertes/[^"]+)"[^>]*class="fr-card__link"[^>]*>'
            r'(.*?)</a>', markup, re.DOTALL):
        t = _text(title)
        if t and t not in heads:
            heads.append(t)
            links.append("https://www.diplomatie.gouv.fr" + href)
    heads, links = heads[:3], links[:3]
    return {"provider": "France Diplomatie (conseils aux voyageurs)", "updated": upd,
            "headline": heads[0] if heads else None, "headlines": heads,
            "headline_urls": links, "lang": "fr",
            "url": url}


# =========================================================================== collectors

PlaceFn = Callable[[RunContext, dict], Awaitable[int]]


async def for_each_place(ctx: RunContext, fn: PlaceFn) -> int:
    """Run fn for every place. Errors are recorded per place in ctx.notes; the run fails
    only if every place failed (so one bad place never hides the others)."""
    places = config.list_places()
    n, errors = 0, {}
    for p in places:
        try:
            n += await fn(ctx, p)
        except Exception as e:  # noqa: BLE001 -- recorded, see below
            errors[p["id"]] = f"{type(e).__name__}: {e}"[:300]
    if errors:
        ctx.notes["errors"] = errors
    if places and len(errors) == len(places):
        raise SourceChanged(f"all places failed: {errors}")
    return n


def _save(pid: str, kind: str, doc: dict) -> None:
    db.set_status(status_key(pid, kind), doc | {"fetched_at": db.now_iso()})


def _cached(pid: str, kind: str) -> dict | None:
    s = db.get_status(status_key(pid, kind))
    return s["value"] if s else None


def _pt(p: dict) -> dict:
    return {"latitude": p["lat"], "longitude": p["lon"]}


class _PlacesCollector(Collector):
    category = "places"
    homepage = "https://open-meteo.com/en/docs"


class PlacesForecast(_PlacesCollector):
    name = "places_forecast"
    title = "Places -- current conditions + 16-day forecast"
    provider = "Open-Meteo (best-match weather models)"
    endpoint = FORECAST_URL
    interval_s = 3 * HOUR
    description = ("Current conditions, 16-day forecast and the past 30 days for every "
                   "place on the Places page. Future days carry forecast=true.")

    async def collect(self, ctx: RunContext) -> int:
        async def one(ctx: RunContext, p: dict) -> int:
            params = _pt(p) | {"elevation": p.get("elevation_m"), "timezone": p["timezone"],
                               "daily": ",".join(FORECAST_DAILY),
                               "current": ",".join(FORECAST_CURRENT),
                               "forecast_days": 16, "past_days": 30}
            params = {k: v for k, v in params.items() if v is not None}
            r = await ctx.get(FORECAST_URL, params=params)
            _save(p["id"], "forecast", parse_forecast(r.json(), _today(p["timezone"])))
            return 1
        return await for_each_place(ctx, one)


_STARTED = time.monotonic()
_last_heavy: list[float] = []   # monotonic time of the last heavy request (any collector)
HEAVY_MIN_UPTIME_S = 300        # no heavy request in the first 5 min after start-up ...
HEAVY_GAP_S = 60 * 60           # ... nor within an hour of the previous one
HEAVY_DAILY_WEIGHT = 5000       # estimated Open-Meteo 'calls' per UTC day for heavy requests
HEAVY_KEY = "places_heavy_budget"


def om_weight(n_vars: int, n_days: int, n_locations: int = 1) -> float:
    """Open-Meteo's fair-use weight of a request, as its docs describe it: a call with more
    than 10 variables or more than 2 weeks of data counts as several calls."""
    return max(1.0, n_vars / 10) * max(1.0, n_days / 14) * n_locations


class HeavyBudget:
    """Multi-year requests (30 years of ERA5, CMIP6, GloFAS) weigh hundreds to thousands of
    'calls' in Open-Meteo's fair-use accounting (free tier: 600/min, 5000/h, 10000/day; on
    2026-09-24 a few of them exhausted the hourly archive quota), and the Koh Samui watch
    shares the same quota. So a heavy request is made only if: at most one per run, not in
    the first minutes after start-up, at least HEAVY_GAP_S after the previous one, the
    estimated daily total stays under HEAVY_DAILY_WEIGHT (persisted in status
    `places_heavy_budget`), and no 429 was seen in this run. Places that wait are listed in
    notes.pending and filled on later runs (the one-time data takes a few days)."""

    def __init__(self, ctx: RunContext, n: int = 1) -> None:
        self.ctx, self.left = ctx, n

    def take(self, pid: str, weight: float) -> bool:
        now = time.monotonic()
        day = datetime.now(UTC).date().isoformat()
        st = (db.get_status(HEAVY_KEY) or {}).get("value") or {}
        used = st.get("used", 0.0) if st.get("day") == day else 0.0
        blocked = (self.left <= 0 or now - _STARTED < HEAVY_MIN_UPTIME_S
                   or (_last_heavy and now - _last_heavy[-1] < HEAVY_GAP_S)
                   or used + weight > HEAVY_DAILY_WEIGHT)
        if blocked:
            pending = self.ctx.notes.setdefault("pending", [])
            if pid not in pending:
                pending.append(pid)
            return False
        self.left -= 1
        _last_heavy[:] = [now]
        db.set_status(HEAVY_KEY, {"day": day, "used": round(used + weight, 1),
                                  "limit": HEAVY_DAILY_WEIGHT})
        return True

    def hit_429(self, e: Exception) -> None:
        if getattr(getattr(e, "response", None), "status_code", None) == 429:
            self.left = 0


RECENT_DAYS = 400          # the temperate water rule needs 365-day windows (+ ERA5 lag)
RECENT_LIGHT_DAYS = 120    # what is fetched while the 400-day bulk request waits its turn
RECENT_TOPUP_DAYS = 14     # daily top-up: re-fetch the tail (ERA5 revises its last ~5 days)
RECENT_VARS = "precipitation_sum,temperature_2m_max,temperature_2m_min"


def merge_recent(cached: dict | None, new: dict, keep_days: int = RECENT_DAYS) -> dict:
    """Cached days + newly fetched days (new values win for the same date), trimmed to the
    last `keep_days` calendar days before the newest day."""
    by = {d["date"]: d for d in (cached or {}).get("days") or []}
    by.update({d["date"]: d for d in new["days"]})
    last = max(by)
    cut = (date.fromisoformat(last) - timedelta(days=keep_days - 1)).isoformat()
    days = [by[k] for k in sorted(by) if k >= cut]
    return {"days": days, "last_day": last, "first_day": days[0]["date"],
            "window_days": keep_days if len(days) >= 0.9 * keep_days else len(days)}


class PlacesClimate(_PlacesCollector):
    name = "places_climate"
    title = "Places -- 1991-2020 climate normals + last 400 days (ERA5)"
    provider = "Open-Meteo archive (ECMWF ERA5)"
    homepage = "https://open-meteo.com/en/docs/historical-weather-api"
    endpoint = ARCHIVE_URL
    interval_s = HOUR  # one heavy request per hour (HEAVY_GAP_S): normals, then bulks
    max_age_s = 3 * DAY
    description = ("Monthly climate normals 1991-2020 (temperature, rain, sunshine, heat and "
                   "frost days, snow, gusts, evapotranspiration), computed once per place (one "
                   "place per run, to spare the shared Open-Meteo quota), and the last 400 "
                   "days of ERA5 (about 5 days behind): one bulk request per place under the "
                   "same budget, then a light daily top-up of the last two weeks, so the "
                   "365- and 180-day rain windows of temperate places can be rated. Until the "
                   "bulk request has run, the last 120 days are fetched as before.")

    async def collect(self, ctx: RunContext) -> int:
        def base(p: dict) -> dict:
            b = _pt(p) | {"timezone": p["timezone"], "models": "era5"}
            if p.get("elevation_m") is not None:
                b["elevation"] = p["elevation_m"]
            return b

        budget = HeavyBudget(ctx)

        async def fetch_days(p: dict, start: date, end: date) -> dict:
            r = await ctx.get(ARCHIVE_URL, params=base(p) | {
                "start_date": start.isoformat(), "end_date": end.isoformat(),
                "daily": RECENT_VARS})
            return parse_recent(r.json())

        async def recent(ctx: RunContext, p: dict) -> int:
            # the archive refuses an end_date after today in UTC (a Bangkok day is ahead of
            # UTC for 7 hours: the old 120-day request failed nightly for Maenam)
            end = min(_today(p["timezone"]), datetime.now(UTC).date())
            cached = _cached(p["id"], "recent")
            long_ok = bool(cached and cached.get("window_days", 0) >= RECENT_DAYS
                           and cached.get("days"))
            if long_ok:  # daily top-up: the tail only (light)
                start = date.fromisoformat(cached["last_day"]) - timedelta(
                    days=RECENT_TOPUP_DAYS)
                doc = merge_recent(cached, await fetch_days(p, start, end))
                doc["bulk_fetched_at"] = cached.get("bulk_fetched_at")
                doc["topped_up_at"] = db.now_iso()
            elif budget.take(p["id"], om_weight(3, RECENT_DAYS + 1)):  # one bulk per run
                try:
                    doc = merge_recent(None, await fetch_days(
                        p, end - timedelta(days=RECENT_DAYS), end))
                except Exception as e:
                    budget.hit_429(e)
                    raise
                doc["bulk_fetched_at"] = db.now_iso()
                ctx.notes.setdefault("recent_bulk", []).append(p["id"])
            else:  # the bulk request waits its turn: the light window as before
                doc = merge_recent(None, await fetch_days(
                    p, end - timedelta(days=RECENT_LIGHT_DAYS), end), RECENT_LIGHT_DAYS)
            _save(p["id"], "recent", doc)
            return 1

        # 1. the 1991-2020 normals first (one place per run): without them the water factor
        #    of every place is "unknown" and the whole Places page shows no level. The
        #    400-day bulk request only refines temperate places, so it waits its turn behind
        #    the normals (QA 24 Sep 2026: on the VPS the bulks took the first three heavy
        #    slots and the page stayed "unknown" for half a day).
        n = 0
        for p in config.list_places():
            if _cached(p["id"], "normals") or not budget.take(
                    p["id"], om_weight(len(NORMALS_DAILY), 10957)):
                continue
            try:
                r = await ctx.get(ARCHIVE_URL, params=base(p) | {
                    "start_date": NORMALS_START, "end_date": NORMALS_END,
                    "daily": ",".join(NORMALS_DAILY)})
                _save(p["id"], "normals", build_normals(r.json()))
                ctx.notes.setdefault("normals_computed", []).append(p["id"])
                n += 1
            except Exception as e:  # noqa: BLE001 -- recorded; retried on a later run
                budget.hit_429(e)
                ctx.notes.setdefault("errors", {})[f"normals:{p['id']}"] = (
                    f"{type(e).__name__}: {e}"[:300])
        # 2. recent days: light 120-day window always, the 400-day bulk when the budget allows
        n += await for_each_place(ctx, recent)
        return n


class PlacesAir(_PlacesCollector):
    name = "places_air"
    title = "Places -- air quality and pollen (CAMS)"
    provider = "Open-Meteo air quality (Copernicus CAMS)"
    homepage = "https://open-meteo.com/en/docs/air-quality-api"
    endpoint = AIR_URL
    interval_s = 3 * HOUR
    description = ("Modelled PM2.5, PM10, US and European AQI, pollen (Europe only), past 24 h "
                   "+ 72 h forecast; and the last 365 days of PM2.5 from the global CAMS model "
                   "(refreshed every 30 days) for a like-for-like annual mean.")

    async def collect(self, ctx: RunContext) -> int:
        async def one(ctx: RunContext, p: dict) -> int:
            r = await ctx.get(AIR_URL, params=_pt(p) | {
                "current": ",".join(AIR_CURRENT), "hourly": "pm2_5", "timezone": "GMT",
                "past_days": 1, "forecast_days": 4})
            _save(p["id"], "air", parse_air(r.json()))
            year = db.get_status(status_key(p["id"], "air_year"))
            if year is None or _age_days(year["updated_at"]) > 30:
                end = datetime.now(UTC).date() - timedelta(days=1)
                r = await ctx.get(AIR_URL, params=_pt(p) | {
                    "hourly": "pm2_5", "timezone": "GMT", "domains": "cams_global",
                    "start_date": (end - timedelta(days=364)).isoformat(),
                    "end_date": end.isoformat()})
                _save(p["id"], "air_year", build_air_year(r.json()))
            return 1
        return await for_each_place(ctx, one)


def _age_days(ts: str | None) -> float:
    if not ts:
        return 1e9
    t = datetime.fromisoformat(ts)
    t = t if t.tzinfo else t.replace(tzinfo=UTC)
    return (datetime.now(UTC) - t).total_seconds() / 86400


class PlacesMarine(_PlacesCollector):
    name = "places_marine"
    title = "Places -- sea state near the coast (waves, sea temperature)"
    provider = "Open-Meteo Marine (MeteoFrance MFWAM / ECMWF WAM, SST)"
    homepage = "https://open-meteo.com/en/docs/marine-weather-api"
    endpoint = MARINE_URL
    interval_s = 3 * HOUR
    description = ("Wave height and sea temperature at the nearest sea cell. Inland places "
                   "get no sea cell (shown as 'inland'); the distance to the cell is a rough "
                   "distance to the coast.")

    async def collect(self, ctx: RunContext) -> int:
        async def one(ctx: RunContext, p: dict) -> int:
            r = await ctx.get(MARINE_URL, params=_pt(p) | {
                "current": "wave_height,sea_surface_temperature", "daily": "wave_height_max",
                "forecast_days": 7, "timezone": p["timezone"]})
            _save(p["id"], "marine", parse_marine(r.json(), p["lat"], p["lon"]))
            return 1
        return await for_each_place(ctx, one)


class PlacesSeasonal(_PlacesCollector):
    name = "places_seasonal"
    title = "Places -- seasonal outlook (ECMWF SEAS5, 6 months)"
    provider = "Open-Meteo seasonal (ECMWF SEAS5)"
    homepage = "https://open-meteo.com/en/docs/seasonal-forecast-api"
    endpoint = SEASONAL_URL
    interval_s = 24 * HOUR
    description = "Monthly rain and temperature anomalies for the next 6 months, per place."

    async def collect(self, ctx: RunContext) -> int:
        from ..local.collectors import parse_seasonal_monthly

        async def one(ctx: RunContext, p: dict) -> int:
            r = await ctx.get(SEASONAL_URL, params=_pt(p) | {
                "models": "ecmwf_seas5",
                "monthly": "precipitation_mean,precipitation_anomaly,temperature_2m_mean,"
                           "temperature_2m_anomaly"})
            _save(p["id"], "seasonal", parse_seasonal_monthly(r.json()))
            return 1
        return await for_each_place(ctx, one)


class PlacesProjection(_PlacesCollector):
    name = "places_projection"
    title = "Places -- climate projections to 2050 (CMIP6)"
    provider = "Open-Meteo climate API (CMIP6 HighResMIP)"
    homepage = "https://open-meteo.com/en/docs/climate-api"
    endpoint = CLIMATE_URL
    interval_s = 2 * HOUR
    freshness_basis = "run"
    description = ("Change in mean temperature, yearly rain, hot days (> 35 C) and frost days "
                   "between 1991-2020 and 2036-2050, 6 high-resolution CMIP6 models (high "
                   "emission pathway). Computed once per place, one place per run.")

    async def collect(self, ctx: RunContext) -> int:
        budget = HeavyBudget(ctx)

        async def one(ctx: RunContext, p: dict) -> int:
            if _cached(p["id"], "projection"):
                return 1
            # two stages on two runs (baseline, then future): two lighter requests
            base = _cached(p["id"], "projection_base")
            years = PROJ_BASE if base is None else PROJ_FUTURE
            n_days = (years[1] - years[0] + 1) * 365
            if not budget.take(p["id"], om_weight(len(PROJ_DAILY) * len(CMIP6_MODELS), n_days)):
                return 0
            try:
                r = await ctx.get(CLIMATE_URL, params=_pt(p) | {
                    "models": ",".join(CMIP6_MODELS), "daily": ",".join(PROJ_DAILY),
                    "start_date": f"{years[0]}-01-01", "end_date": f"{years[1]}-12-31"})
            except Exception as e:
                budget.hit_429(e)
                raise
            payload = r.json()
            stats = _proj_window(payload, CMIP6_MODELS, years, 0.8)
            if base is None:
                if len(stats) < 3:
                    raise SourceChanged(f"climate API: only {len(stats)} usable models")
                _save(p["id"], "projection_base", {"models": stats, "years": list(years),
                                                   "grid": {"lat": payload.get("latitude"),
                                                            "lon": payload.get("longitude")}})
                ctx.notes.setdefault("baseline_done", []).append(p["id"])
                return 1
            _save(p["id"], "projection", combine_projection(
                base["models"], stats, tuple(base["years"]), PROJ_FUTURE, grid=base.get("grid")))
            ctx.notes.setdefault("computed", []).append(p["id"])
            return 1
        return await for_each_place(ctx, one)


class PlacesFlood(_PlacesCollector):
    name = "places_flood"
    title = "Places -- river discharge of the nearest river (GloFAS)"
    provider = "Open-Meteo flood API (Copernicus GloFAS v4)"
    homepage = "https://open-meteo.com/en/docs/flood-api"
    endpoint = FLOOD_URL
    interval_s = 6 * HOUR
    description = ("Finds the largest river cell within about 15 km of each place (5 km "
                   "GloFAS grid), its 1991-2020 flood levels (computed once) and the "
                   "discharge forecast for the next weeks.")

    async def collect(self, ctx: RunContext) -> int:
        budget = HeavyBudget(ctx)

        async def one(ctx: RunContext, p: dict) -> int:
            river = _cached(p["id"], "river")
            if river is None:
                # 49 cells x 30 days: a light request (the 30-year history comes later)
                pts = grid_points(p["lat"], p["lon"])
                end = datetime.now(UTC).date()
                r = await ctx.get(FLOOD_URL, params={
                    "latitude": ",".join(str(a) for a, _ in pts),
                    "longitude": ",".join(str(b) for _, b in pts),
                    "daily": "river_discharge",
                    "start_date": (end - timedelta(days=30)).isoformat(),
                    "end_date": end.isoformat()})
                river = {"cell": choose_river_cell(r.json(), p["lat"], p["lon"]),
                         "search": "7 x 7 GloFAS cells, 0.05 deg apart (about 15 km around "
                                   "the place), largest 30-day mean discharge"}
                _save(p["id"], "river", river)
            cell = river.get("cell")
            if not cell:
                return 1
            if not river.get("climate") and budget.take(p["id"], om_weight(1, RIVER_DAYS)):
                try:
                    h = await ctx.get(FLOOD_URL, params={
                        "latitude": cell["lat"], "longitude": cell["lon"],
                        "daily": "river_discharge", "start_date": RIVER_START,
                        "end_date": NORMALS_END})
                except Exception as e:
                    budget.hit_429(e)
                    raise
                river["climate"] = build_river_climate(h.json())
                _save(p["id"], "river", river)
            r = await ctx.get(FLOOD_URL, params={
                "latitude": cell["lat"], "longitude": cell["lon"],
                "daily": "river_discharge,river_discharge_max", "past_days": 7,
                "forecast_days": 30})
            _save(p["id"], "flood", parse_flood_forecast(r.json()))
            return 1
        return await for_each_place(ctx, one)


class PlacesQuakes(_PlacesCollector):
    name = "places_quakes"
    title = "Places -- earthquakes within 300 km (USGS)"
    provider = "USGS Earthquake Hazards Program (FDSN event service)"
    homepage = "https://earthquake.usgs.gov/earthquakes/search/"
    endpoint = USGS_URL
    interval_s = HOUR
    description = ("M2.5+ earthquakes within 300 km in the last 30 days, and M4.5+ within "
                   "300 km since 1976 (the long-term record, refreshed monthly).")

    async def collect(self, ctx: RunContext) -> int:
        async def one(ctx: RunContext, p: dict) -> int:
            base = {"format": "geojson", "latitude": p["lat"], "longitude": p["lon"],
                    "maxradiuskm": QUAKE_RADIUS_KM, "orderby": "time"}
            since = (datetime.now(UTC) - timedelta(days=30)).date().isoformat()
            r = await ctx.get(USGS_URL, params=base | {"starttime": since, "minmagnitude": 2.5})
            recent = parse_usgs_near(r.json(), p["lat"], p["lon"])
            _save(p["id"], "quakes_recent", {"since": since, "min_mag": 2.5,
                                             "radius_km": QUAKE_RADIUS_KM, "events": recent})
            hist = db.get_status(status_key(p["id"], "quakes_hist"))
            if hist is None or _age_days(hist["updated_at"]) > 30:
                r = await ctx.get(USGS_URL, params=base | {"starttime": "1976-01-01",
                                                           "minmagnitude": 4.5,
                                                           "limit": 20000})
                ev = parse_usgs_near(r.json(), p["lat"], p["lon"])
                _save(p["id"], "quakes_hist", {
                    "since": "1976-01-01", "min_mag": 4.5, "radius_km": QUAKE_RADIUS_KM,
                    "count": len(ev), "max_mag": max((q["mag"] for q in ev), default=None),
                    "strongest": sorted(ev, key=lambda q: -q["mag"])[:5],
                    "nearest": sorted(ev, key=lambda q: q["distance_km"])[:3]})
            return 1
        return await for_each_place(ctx, one)


class PlacesFires(_PlacesCollector):
    name = "places_fires"
    title = "Places -- active fires within 100 km (NASA FIRMS, 24 h)"
    provider = "NASA FIRMS (LANCE, VIIRS S-NPP 375 m)"
    homepage = "https://firms.modaps.eosdis.nasa.gov/"
    endpoint = FIRMS_URL.format(region="Europe")
    interval_s = 6 * HOUR
    description = ("Satellite fire detections of the last 24 h within 100 km of each place, "
                   "from the public regional VIIRS files (low-confidence detections excluded).")

    async def collect(self, ctx: RunContext) -> int:
        cache: dict[str, str] = {}

        async def one(ctx: RunContext, p: dict) -> int:
            region = firms_region(p["lat"], p["lon"])
            if region is None:
                _save(p["id"], "fires", {"region": None, "count": None,
                                         "note": "no FIRMS regional file covers this place"})
                return 0
            if region not in cache:
                cache[region] = (await ctx.get(FIRMS_URL.format(region=region))).text
            doc = parse_firms_near(cache[region], p["lat"], p["lon"])
            _save(p["id"], "fires", doc | {"region": region, "window": "24 h",
                                           "url": ("https://firms.modaps.eosdis.nasa.gov/map/"
                                                   f"#d:24hrs;@{p['lon']:.2f},{p['lat']:.2f},"
                                                   "9.00z")})
            return 1
        return await for_each_place(ctx, one)


class PlacesWarnings(_PlacesCollector):
    name = "places_warnings"
    title = "Places -- official weather warnings (Meteoalarm / Meteo-France, Roshydromet)"
    provider = "Meteoalarm (EUMETNET; Meteo-France vigilance) + Hydrometcenter of Russia"
    homepage = "https://meteoalarm.org/"
    endpoint = METEOALARM_URL.format(feed="france")
    interval_s = HOUR
    description = ("Active yellow/orange/red warnings for the place's area from Meteoalarm "
                   "(an empty feed means no warning above green), and the Hydrometcenter of "
                   "Russia daily bulletin of dangerous weather (sentences naming the region). "
                   "Thailand: TMD bulletins come from the Koh Samui watch (tmd_warnings).")

    async def collect(self, ctx: RunContext) -> int:
        places = config.list_places()
        feeds = sorted({(p.get("warnings") or {}).get("meteoalarm", {}).get("feed")
                        for p in places} - {None})
        n, errors = 0, {}
        for feed in feeds:
            try:
                r = await ctx.get(METEOALARM_URL.format(feed=feed))
                doc = parse_meteoalarm(r.text) | {"feed": feed,
                                                  "url": METEOALARM_URL.format(feed=feed)}
                db.set_status(f"places_meteoalarm:{feed}", doc | {"fetched_at": db.now_iso()})
                n += 1
            except Exception as e:  # noqa: BLE001
                errors[f"meteoalarm:{feed}"] = f"{type(e).__name__}: {e}"[:300]
        if any((p.get("warnings") or {}).get("hydromet_ru") for p in places):
            try:
                r = await ctx.get(HYDROMET_RU_URL)
                doc = parse_hydromet_bulletin(r.text)
                db.set_status("places_hydromet_ru", doc | {"fetched_at": db.now_iso()})
                n += 1
            except Exception as e:  # noqa: BLE001
                errors["hydromet_ru"] = f"{type(e).__name__}: {e}"[:300]
        if errors:
            ctx.notes["errors"] = errors
            if n == 0:
                raise SourceChanged(f"all warning sources failed: {errors}")
        return n


class PlacesAdvisories(_PlacesCollector):
    name = "places_advisories"
    title = "Places -- official travel advice (FCDO, US State, France Diplomatie)"
    provider = "UK FCDO (GOV.UK), US Department of State, France Diplomatie"
    homepage = "https://www.gov.uk/foreign-travel-advice"
    endpoint = STATE_RSS
    interval_s = 12 * HOUR
    description = ("Headline and last-updated date of each government's travel advice for the "
                   "country of every place, with the link. Shown as published, not rated.")

    async def collect(self, ctx: RunContext) -> int:
        places = config.list_places()
        by_cc: dict[str, dict] = {}
        for p in places:
            if p.get("country_code"):
                by_cc.setdefault(p["country_code"], p.get("advisory_slugs") or {})
        out: dict[str, dict] = {}
        errors: dict[str, str] = {}
        state: dict[str, dict] = {}
        try:
            state = parse_state_rss((await ctx.get(STATE_RSS)).text)
        except Exception as e:  # noqa: BLE001
            errors["state"] = f"{type(e).__name__}: {e}"[:300]
        for cc, slugs in by_cc.items():
            row: dict = {}
            if slugs.get("fcdo"):
                try:
                    r = await ctx.get(FCDO_API.format(slug=slugs["fcdo"]))
                    row["fcdo"] = parse_fcdo(r.json(), slugs["fcdo"])
                except Exception as e:  # noqa: BLE001
                    errors[f"fcdo:{cc}"] = f"{type(e).__name__}: {e}"[:300]
            if slugs.get("state") and slugs["state"] in state:
                row["state"] = state[slugs["state"]]
            if slugs.get("fr_diplomatie"):
                url = FR_DIPLO.format(slug=slugs["fr_diplomatie"])
                try:
                    r = await ctx.get(url)
                    row["fr_diplomatie"] = parse_fr_diplomatie(r.text, str(r.url))
                except Exception as e:  # noqa: BLE001
                    errors[f"fr_diplomatie:{cc}"] = f"{type(e).__name__}: {e}"[:300]
            out[cc] = row
        if errors:
            ctx.notes["errors"] = errors
        n = sum(len(v) for v in out.values())
        if n == 0 and errors:
            raise SourceChanged(f"all advisory sources failed: {errors}")
        db.set_status("places_advisories", {"countries": out, "fetched_at": db.now_iso()})
        return n


COLLECTORS = [PlacesForecast, PlacesClimate, PlacesAir, PlacesMarine, PlacesSeasonal,
              PlacesProjection, PlacesFlood, PlacesQuakes, PlacesFires, PlacesWarnings,
              PlacesAdvisories]
