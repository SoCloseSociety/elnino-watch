"""Places engine: comparable, explainable factors per place. No black-box score.

Two views, both built only from stored real data (collectors.py) and curated, sourced
context (enso.py, config.py):

1. CURRENT factors (0-4, the Koh Samui watch level names normal / vigilance (shown as
   Watch) / prepare / act / leave): what the weather, air, rivers, fires, quakes and
   official warnings say NOW and over the next 7 days. Each factor carries value,
   threshold, explanation, source, url, observed_at, kind (observed | forecast |
   model_analysis | reanalysis | bulletin) and stale. Missing data is never read as safe.
   Overall = max over factors of min(level, CAP) (rule R1) and at least 3 when two
   physical hazards are >= 2 together (R3, as on the Samui watch). If a critical factor
   (heat, water, flood, storm) has no current data, the level is unknown.

2. LONG-TERM exposure matrix (0-4 = very low, low, moderate, high, very high; higher =
   more exposed): 1991-2020 climate normals, 2050 projections, the earthquake record,
   the ENSO teleconnection. Each cell has value, unit, rule, note, source.

The ranking is a transparent weighted mean of (4 - exposure) over the dimensions that
have data, with the weights returned and adjustable. It is a decision aid only.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from .. import db
from . import config
from . import enso as enso_ctx
from .collectors import FIRE_RADIUS_KM, QUAKE_RADIUS_KM, haversine_km, status_key

LEVEL_KEYS = ["normal", "vigilance", "prepare", "act", "leave"]
EXPOSURE_LABELS = ["very low", "low", "moderate", "high", "very high"]
CAP = {"heat": 4, "cold": 3, "water": 3, "flood": 3, "storm": 4, "air": 3, "wildfire": 3,
       "earthquake": 2, "warnings": 3}
CRITICAL = ("heat", "water", "flood", "storm")
PHYSICAL = ("heat", "cold", "water", "flood", "storm", "air", "wildfire")
DISCLAIMER = ("Decision aid only. The ranking is a weighted average of the exposure scores "
              "below, with the weights you choose; it leaves out cost of living, visas, "
              "healthcare, family and everything else that is not in this data. Read the "
              "notes of each row before deciding.")

URLS = {
    "forecast": "https://open-meteo.com/en/docs",
    "era5": "https://open-meteo.com/en/docs/historical-weather-api",
    "air": "https://open-meteo.com/en/docs/air-quality-api",
    "marine": "https://open-meteo.com/en/docs/marine-weather-api",
    "flood": "https://open-meteo.com/en/docs/flood-api",
    "climate": "https://open-meteo.com/en/docs/climate-api",
    "usgs": "https://earthquake.usgs.gov/earthquakes/search/",
    "gem": "https://www.globalquakemodel.org/product/global-seismic-hazard-map",
    "firms": "https://firms.modaps.eosdis.nasa.gov/",
    "gdacs": "https://www.gdacs.org/",
    "nws_heat": "https://www.weather.gov/ama/heatindex",
    "nws_cold": "https://www.weather.gov/safety/cold-wind-chill-chart",
    "pcd": "https://air4thai.pcd.go.th/",
    "who_air": "https://www.who.int/publications/i/item/9789240034228",
    "aridity": "https://wad.jrc.ec.europa.eu/patternsaridity",
    "meteoalarm": "https://meteoalarm.org/",
    "hydromet": "https://meteoinfo.ru/hazardsbull",
    "tmd": "https://www.tmd.go.th/",
}

# Max age per stored doc kind before its data counts as stale (seconds).
MAX_AGE = {"forecast": 12 * 3600, "air": 12 * 3600, "marine": 12 * 3600,
           "flood": 3 * 86400, "quakes_recent": 6 * 3600, "fires": 18 * 3600,
           "seasonal": 3 * 86400, "recent": 3 * 86400}

WMO_CODES = {0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog",
             48: "Rime fog", 51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
             56: "Freezing drizzle", 57: "Freezing drizzle", 61: "Light rain", 63: "Rain",
             65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain", 71: "Light snow",
             73: "Snow", 75: "Heavy snow", 77: "Snow grains", 80: "Rain showers",
             81: "Rain showers", 82: "Violent rain showers", 85: "Snow showers",
             86: "Heavy snow showers", 95: "Thunderstorm", 96: "Thunderstorm with hail",
             99: "Thunderstorm with heavy hail"}


# --------------------------------------------------------------------------- helpers

def level_key(level: int | None) -> str | None:
    return None if level is None else LEVEL_KEYS[max(0, min(4, level))]


def _now() -> datetime:
    return datetime.now(UTC)


def _doc(pid: str, kind: str) -> tuple[dict | None, str | None]:
    s = db.get_status(status_key(pid, kind))
    return (s["value"], s["updated_at"]) if s else (None, None)


def _age_s(ts: str | None, now: datetime) -> float | None:
    if not ts:
        return None
    t = datetime.fromisoformat(ts)
    t = t if t.tzinfo else t.replace(tzinfo=UTC)
    return (now - t).total_seconds()


def _is_stale(kind: str, updated_at: str | None, now: datetime) -> bool:
    a = _age_s(updated_at, now)
    return a is None or a > MAX_AGE.get(kind, 3 * 86400)


def factor(fid: str, label: str, level: int | None, value=None, unit: str | None = None,
           threshold: str = "", explanation: str = "", source: str = "", url: str = "",
           observed_at: str | None = None, kind: str | None = None, stale: bool = False,
           details: dict | None = None, critical: bool = False) -> dict:
    if stale and level == 0:
        level = None
        explanation = f"{explanation} Data too old to conclude: level unknown."
    return {"id": fid, "label": label, "level": level, "level_key": level_key(level),
            "value": value, "unit": unit, "threshold": threshold,
            "explanation": explanation.strip(), "source": source, "url": url,
            "observed_at": observed_at, "kind": kind, "stale": stale,
            "critical": critical, "details": details or {}}


def missing(fid: str, label: str, source: str, url: str, why: str = "",
            critical: bool = False) -> dict:
    return factor(fid, label, None, explanation=f"data unavailable. {why}".strip(),
                  source=source, url=url, critical=critical)


def _place_today(p: dict) -> date:
    try:
        return datetime.now(ZoneInfo(p["timezone"])).date()
    except Exception:  # noqa: BLE001
        return _now().date()


def _future_days(fc: dict, p: dict, n: int = 7) -> list[dict]:
    today = _place_today(p).isoformat()
    return [d for d in fc.get("daily", []) if d["date"] >= today][:n]


# --------------------------------------------------------------------------- current factors

def heat_level(app_max: float, danger_days: int) -> int:
    """Samui bands (NWS heat index categories, see app/local/risk.py heat_level):
    < 39: 0 ; 39-41: 1 ; >= 41 on 1-2 days: 2 ; >= 41 on 3+ days: 3 ; >= 54: 4."""
    if app_max >= 54:
        return 4
    if app_max >= 41:
        return 3 if danger_days >= 3 else 2
    if app_max >= 39:
        return 1
    return 0


def f_heat(p: dict, now: datetime) -> dict:
    label = "Heat (feels-like, next 7 days)"
    fc, upd = _doc(p["id"], "forecast")
    days = [d for d in _future_days(fc, p) if d.get("apparent_temperature_max") is not None] \
        if fc else []
    if not days:
        return missing("heat", label, "Open-Meteo", URLS["forecast"], critical=True)
    mx = max(d["apparent_temperature_max"] for d in days)
    danger = sum(1 for d in days if d["apparent_temperature_max"] >= 41)
    lv = heat_level(mx, danger)
    hottest = max(days, key=lambda d: d["apparent_temperature_max"])
    return factor("heat", label, lv, round(mx, 1), "°C feels-like",
                  ">= 39 watch, >= 41 prepare, 3 days >= 41 act, >= 54 leave (NWS heat index)",
                  f"Highest forecast feels-like temperature over the next {len(days)} days: "
                  f"{mx:.1f} °C on {hottest['date']} ({danger} day(s) >= 41 °C).",
                  "Open-Meteo forecast", URLS["nws_heat"], hottest["date"], "forecast",
                  _is_stale("forecast", upd, now), {"danger_days": danger}, critical=True)


def cold_level(app_min: float) -> int:
    """Frostbite-risk bands on the feels-like (wind chill) minimum, after the NWS wind chill
    chart and Environment Canada's risk bands: > -10: 0 ; -10..-28: 1 ; -28..-40: 2
    (frostbite possible in 10-30 min) ; -40..-48: 3 (5-10 min) ; <= -48: 4."""
    if app_min <= -48:
        return 4
    if app_min <= -40:
        return 3
    if app_min <= -28:
        return 2
    if app_min <= -10:
        return 1
    return 0


def f_cold(p: dict, now: datetime) -> dict:
    label = "Cold (feels-like minimum, next 7 days)"
    fc, upd = _doc(p["id"], "forecast")
    days = [d for d in _future_days(fc, p) if d.get("apparent_temperature_min") is not None] \
        if fc else []
    if not days:
        return missing("cold", label, "Open-Meteo", URLS["forecast"])
    coldest = min(days, key=lambda d: d["apparent_temperature_min"])
    mn = coldest["apparent_temperature_min"]
    snow = round(sum(d.get("snowfall_sum") or 0 for d in days), 1)
    return factor("cold", label, cold_level(mn), round(mn, 1), "°C feels-like",
                  "<= -10 watch, <= -28 prepare, <= -40 act, <= -48 leave (frostbite risk)",
                  f"Lowest forecast feels-like temperature over the next {len(days)} days: "
                  f"{mn:.1f} °C on {coldest['date']}. Snowfall forecast: {snow} cm.",
                  "Open-Meteo forecast", URLS["nws_cold"], coldest["date"], "forecast",
                  _is_stale("forecast", upd, now), {"snow_cm_7d": snow})


def rain_deficit_level(pct: float) -> int:
    """Same bands as the Koh Samui water factor: >= 75%: 0 ; 60-75: 1 ; 40-60: 2 ; < 40: 3."""
    if pct < 40:
        return 3
    if pct < 60:
        return 2
    if pct < 75:
        return 1
    return 0


def normal_for_days(normals: dict, days: list[str]) -> float:
    """Normal rain for a list of dates: each day gets 1/n of its month's normal total."""
    months = {m["month"]: m for m in normals["months"]}
    tot = 0.0
    for d in days:
        y, m = int(d[:4]), int(d[5:7])
        nd = (date(y + (m == 12), m % 12 + 1, 1) - date(y, m, 1)).days
        tot += months[m]["precip_mm"] / nd
    return tot


# ------------------------------------------------------------------ water profiles
#
# Why profiles. A rain deficit only matters through the store that supplies the water, and
# stores differ by climate:
#
# - TROPICAL (Koppen A: coldest month mean >= 18 C, not dry). Rain comes in wet seasons and
#   supply leans on surface stores that a dry quarter drains. Koh Samui (small island
#   reservoirs, PWA rationing from 3 Aug 2026 after a long dry spell) is the reference: the
#   90-day window with the Koh Samui watch bands (app/local/risk.py). Unchanged.
# - TEMPERATE HUMID (coldest month < 18 C and aridity index P/ET0 >= 0.5: Koppen C/D, e.g.
#   Normandy's oceanic climate, Vladimir Oblast's humid continental one). Soil and aquifers
#   are recharged over the winter half-year and carry supply through summer, so a dry
#   quarter is common and mostly buffered; what hurts is a deficit over 6-12 months (a missed
#   winter recharge). WMO's SPI guide ties 1-3 month accumulations to soil moisture and
#   6-24 month ones to groundwater and reservoirs, which is why the 180- and 365-day windows
#   drive this profile: a shorter window can sit at most one level above the longest window
#   available (a dry spring-summer after a normal year is Watch, not Prepare), and 90 days
#   alone can raise at most Watch (Prepare only when no longer window can be computed, so a
#   severe short deficit is not dismissed).
# - DRY (aridity index P/ET0 < 0.5: semi-arid and drier, UNEP classes). No bands tuned for
#   dry climates are defined yet: the default 90-day Koh Samui bands are used, and the
#   explanation says so.
#
# Band values (percent of the 1991-2020 ERA5 normal for the same calendar days). WMO's SPI
# categories are -1 moderately dry, -1.5 severely dry, -2 extremely dry. The stored normals
# keep only monthly means (no per-year totals), so SPI cannot be fitted per place; the
# temperate bands approximate those categories for the year-to-year variability typical of
# temperate humid rain totals (larger, in relative terms, for short windows than long ones):
#   365 d: < 85% Watch, < 75% Prepare, < 65% Act
#   180 d: < 75% Watch, < 60% Prepare, < 50% Act
#    90 d: < 60% Watch, < 35% Prepare (capped, see above)
# The level is the highest (capped) window level; on a tie the longest window is named.
# As on the Samui watch, a rain-only Act also needs >= 100 mm actually missing.
#
# Not an SPEI (rain minus reference evapotranspiration, standardised): the recent ERA5
# series stored per place holds rain and temperature but no ET0, and the normals hold no
# per-year distribution to standardise against. Windows longer than the stored series are
# never estimated: the collector keeps the last 120 days of ERA5, so until it stores a
# longer series the temperate profile degrades to its 90-day window and says so.
#
# References:
# - WMO (2012), Standardized Precipitation Index User Guide, WMO-No. 1090:
#   https://library.wmo.int/idurl/4/39629
# - Vicente-Serrano, Begueria, Lopez-Moreno (2010), A multiscalar drought index sensitive
#   to global warming: the SPEI, J. Climate 23: https://doi.org/10.1175/2009JCLI2909.1
# - BRGM, French groundwater situation bulletins (winter recharge sets summer aquifer
#   levels): https://www.brgm.fr
# Koppen A threshold (coldest month >= 18 C): Peel, Finlayson, McMahon (2007), HESS 11:
# https://doi.org/10.5194/hess-11-1633-2007

MIN_DEFICIT_MM_FOR_ACT = 100
WINDOW_COVERAGE = 0.9   # a window needs >= 90% of its days in the stored ERA5 series
LEVEL_WORDS = ["Normal", "Watch", "Prepare", "Act", "Leave"]

WATER_PROFILES: dict[str, dict] = {
    "tropical": {
        "label": "tropical, surface stores",
        "windows": ((90, (75, 60, 40)),),
    },
    "temperate": {
        "label": "temperate humid, groundwater-buffered",
        "windows": ((365, (85, 75, 65)), (180, (75, 60, 50)), (90, (60, 35, None))),
        "short_days": 90,
        "short_cap_with_long": 1,     # a longer window exists: 90 days alone -> max Watch
        "short_cap_without_long": 2,  # no longer window: max Prepare, and said so
    },
    "dry": {
        "label": "dry climate, default bands",
        "windows": ((90, (75, 60, 40)),),
    },
}


def pct_level(pct: float, edges: tuple) -> int:
    """edges = (watch, prepare, act) upper bounds in % of normal; None = level not used."""
    lv = 0
    for i, e in enumerate(edges, start=1):
        if e is not None and pct < e:
            lv = i
    return lv


def water_profile(p: dict, normals: dict) -> tuple[str, str]:
    """(profile key, reason) from the place's ERA5 1991-2020 normals, or a `water_profile`
    set on the place itself."""
    forced = p.get("water_profile")
    if forced in WATER_PROFILES:
        return forced, "set for this place"
    a = normals.get("annual") or {}
    cold, ai = a.get("coldest_month_t_mean"), a.get("aridity_index")
    if ai is not None and ai < 0.5:
        return "dry", f"aridity index P/ET0 {ai:.2f} < 0.5"
    if cold is None:
        return "tropical", "climate class unknown (no coldest-month value), default bands"
    ai_txt = f", aridity index P/ET0 {ai:.2f}" if ai is not None else ""
    if cold >= 18:
        return "tropical", f"coldest month {cold:.1f} °C >= 18 °C{ai_txt}"
    return "temperate", f"coldest month {cold:.1f} °C < 18 °C{ai_txt}"


def _rain_window(rec: dict, normals: dict, n: int) -> dict:
    """Rain over the n days ending at the last stored ERA5 day vs the normal for the same
    days. available=False when the stored series does not cover the window."""
    last = date.fromisoformat(rec["last_day"])
    start = last - timedelta(days=n - 1)
    days = [d for d in rec["days"] if start.isoformat() <= d["date"] <= rec["last_day"]]
    w: dict = {"days": n, "start": start.isoformat(), "end": rec["last_day"],
               "days_with_data": len(days)}
    if len(days) < WINDOW_COVERAGE * n:
        return w | {"available": False}
    obs = sum(d["precip"] for d in days)
    norm = normal_for_days(normals, [d["date"] for d in days])
    return w | {"available": True, "rain_mm": round(obs, 0), "normal_mm": round(norm, 0),
                "pct": round(100 * obs / norm, 0) if norm >= 30 else None,
                "_obs": obs, "_norm": norm, "_pct": 100 * obs / norm if norm else None}


def _bands_txt(n: int, edges: tuple) -> str:
    parts = [f"< {e}% {LEVEL_WORDS[i].lower()}" for i, e in enumerate(edges, start=1)
             if e is not None]
    return f"{n} d: " + ", ".join(parts)


def f_water(p: dict, now: datetime) -> dict:
    rec, _ = _doc(p["id"], "recent")
    normals, _ = _doc(p["id"], "normals")
    if not rec or not normals:
        return missing("water", "Water (rain of the last 90 days vs normal)",
                       "Open-Meteo ERA5", URLS["era5"],
                       "Needs the 1991-2020 normals (computed once, one place per run) and "
                       "the recent ERA5 series.", critical=True)
    prof, why = water_profile(p, normals)
    if prof == "temperate":
        return _water_temperate(p, now, rec, normals, why)
    return _water_short(now, rec, normals, prof, why)


def _water_short(now: datetime, rec: dict, normals: dict, prof: str, why: str) -> dict:
    """Tropical and dry profiles: 90-day window with the Koh Samui bands (the original
    behaviour, unchanged; only the profile sentence is added to the explanation)."""
    label = "Water (rain of the last 90 days vs normal)"
    if prof == "tropical":
        prof_txt = (f" Profile: tropical ({why}). Supply leans on surface stores that a dry "
                    "quarter drains, so the 90-day window with the Koh Samui bands is used.")
    else:
        prof_txt = (f" Profile: dry climate ({why}). No bands tuned for dry climates are "
                    "defined yet, so the default 90-day window with the Koh Samui bands is "
                    "used.")
    extra = {"profile": prof, "profile_label": WATER_PROFILES[prof]["label"],
             "profile_reason": why, "window_days": 90}
    days = rec["days"][-90:]
    obs = sum(d["precip"] for d in days)
    norm = normal_for_days(normals, [d["date"] for d in days])
    last = rec["last_day"]
    stale = (_age_s(last + "T00:00:00+00:00", now) or 1e9) > 12 * 86400
    if norm < 30:
        return factor("water", label, 0, round(obs, 0), "mm in 90 days",
                      "< 75% watch, < 60% prepare, < 40% act (not rated when the normal is "
                      "under 30 mm)",
                      f"{obs:.0f} mm in the 90 days to {last}; the normal for this dry period "
                      f"is only {norm:.0f} mm, so a percentage would mean little." + prof_txt,
                      "Open-Meteo ERA5", URLS["era5"], last, "reanalysis", stale,
                      {"normal_mm": round(norm, 0)} | extra, critical=True)
    pct = 100 * obs / norm
    lv = rain_deficit_level(pct)
    if lv == 3 and norm - obs < MIN_DEFICIT_MM_FOR_ACT:
        lv = 2  # as on the Samui watch: a rain-only 'act' needs >= 100 mm missing
    return factor("water", label, lv, round(pct, 0), "% of normal",
                  "< 75% watch, < 60% prepare, < 40% and >= 100 mm short act",
                  f"{obs:.0f} mm fell in the 90 days to {last} (ERA5), against a 1991-2020 "
                  f"normal of {norm:.0f} mm for the same days ({pct:.0f}%). ERA5 against "
                  "ERA5, so the model bias cancels out." + prof_txt,
                  "Open-Meteo ERA5", URLS["era5"], last, "reanalysis", stale,
                  {"rain_mm": round(obs, 0), "normal_mm": round(norm, 0)} | extra,
                  critical=True)


def _water_temperate(p: dict, now: datetime, rec: dict, normals: dict, why: str) -> dict:
    """Temperate humid profile: 365/180/90-day windows, long windows drive the level (see
    the WATER_PROFILES rationale above)."""
    cfg = WATER_PROFILES["temperate"]
    label = "Water (rain of the last 90 to 365 days vs normal)"
    last = rec["last_day"]
    stale = (_age_s(last + "T00:00:00+00:00", now) or 1e9) > 12 * 86400
    wins = [_rain_window(rec, normals, n) | {"bands": edges} for n, edges in cfg["windows"]]
    long_ok = any(w["available"] and w["days"] > cfg["short_days"] for w in wins)
    short_cap = cfg["short_cap_with_long"] if long_ok else cfg["short_cap_without_long"]
    rated = []
    for w in wins:  # longest first
        if not w["available"] or w["pct"] is None:
            w["level"] = None
            continue
        lv = pct_level(w["_pct"], w["bands"])
        if lv == 3 and w["_norm"] - w["_obs"] < MIN_DEFICIT_MM_FOR_ACT:
            lv = 2
        w["raw_level"] = lv
        if rated:  # a shorter window: at most one step above the longest rated window
            top = rated[0]
            w_cap, why_cap = top["level"] + 1, f"at most one step above the {top['days']}-day window"
            if w["days"] == cfg["short_days"] and short_cap < w_cap:
                w_cap, why_cap = short_cap, f"90 days alone can raise at most {LEVEL_WORDS[short_cap]}"
            if lv > w_cap:
                w["capped"], lv = why_cap, w_cap
        elif w["days"] == cfg["short_days"] and lv > short_cap:
            w["capped"], lv = f"90 days alone can raise at most {LEVEL_WORDS[short_cap]}", short_cap
        w["level"] = lv
        rated.append(w)
    threshold = ("; ".join(_bands_txt(n, e) for n, e in cfg["windows"])
                 + "; a shorter window can sit at most one step above the longest window "
                 "available, and 90 d alone at most Watch (Prepare when no longer window "
                 "exists); act also needs >= 100 mm short")
    head = (f"Profile: temperate humid, groundwater-buffered ({why}). Soil and aquifers are "
            "refilled each winter and carry supply through a dry quarter, so the 180- and "
            "365-day windows count most.")
    missing_w = [w for w in wins if not w["available"]]
    details_w = [{k: v for k, v in w.items() if not k.startswith("_") and k != "bands"}
                 | {"bands_pct": list(w["bands"])} for w in wins]
    if not rated:
        return factor("water", label, None, None, "% of normal", threshold,
                      f"{head} No window could be rated: the stored ERA5 series has "
                      f"{len(rec['days'])} days to {last}.",
                      "Open-Meteo ERA5", URLS["era5"], last, "reanalysis", stale,
                      {"profile": "temperate", "profile_label": cfg["label"],
                       "profile_reason": why, "windows": details_w}, critical=True)
    # the window with the highest level decides; on a tie the longest one
    drive = max(rated, key=lambda w: (w["level"], w["days"]))
    parts = []
    for w in wins:
        if not w["available"]:
            continue
        if w["pct"] is None:
            parts.append(f"{w['days']} d: {w['_obs']:.0f} mm, normal only {w['_norm']:.0f} "
                         "mm (not rated)")
            continue
        s = (f"{w['days']} d: {w['_obs']:.0f} mm = {w['pct']:.0f}% of normal "
             f"({w['_norm']:.0f} mm) -> {LEVEL_WORDS[w['level']]}")
        if w.get("capped"):
            s += (f" (raw {LEVEL_WORDS[w['raw_level']]}, capped: {w['capped']}, because "
                  "groundwater carries supply through shorter dry spells)")
        parts.append(s)
    expl = f"{head} ERA5 rain to {last} against its own 1991-2020 normal for the same days: "
    expl += "; ".join(parts) + f". Level set by the {drive['days']}-day window."
    if missing_w:
        names = " and ".join(f"{w['days']}-day" for w in reversed(missing_w))
        expl += (f" The {names} window{'s' if len(missing_w) > 1 else ''} could not be "
                 f"computed: only {len(rec['days'])} days of ERA5 are stored (the collector "
                 "keeps the last 120 days), and a longer window is never estimated.")
        if not long_ok:
            expl += " So this level rests on 90 days only and is provisional"
            expl += ("; a short dry spell here is often buffered by groundwater."
                     if drive["level"] > 0 else ".")
    return factor("water", label, drive["level"], drive["pct"], "% of normal", threshold,
                  expl, "Open-Meteo ERA5", URLS["era5"], last, "reanalysis", stale,
                  {"rain_mm": drive["rain_mm"], "normal_mm": drive["normal_mm"],
                   "window_days": drive["days"], "profile": "temperate",
                   "profile_label": cfg["label"], "profile_reason": why,
                   "windows": details_w}, critical=True)


def rain_level(max24: float, sum72: float) -> int:
    """TMD rain classes (as on the Samui watch): > 35 mm/24 h heavy -> 1 ; > 90 or 72 h
    >= 150 -> 2 ; 24 h >= 150 or 72 h >= 250 -> 3."""
    if max24 >= 150 or sum72 >= 250:
        return 3
    if max24 > 90 or sum72 >= 150:
        return 2
    if max24 > 35 or sum72 >= 100:
        return 1
    return 0


def river_level(qmax: float, clim: dict) -> int:
    if qmax >= clim["q10_m3s"]:
        return 3
    if qmax >= clim["q2_m3s"]:
        return 2
    if qmax >= clim["p99_daily_m3s"]:
        return 1
    return 0


def f_flood(p: dict, now: datetime) -> dict:
    label = "Flood (heavy rain + river, next days)"
    fc, upd = _doc(p["id"], "forecast")
    days = _future_days(fc, p) if fc else []
    rain = [d.get("precipitation_sum") or 0.0 for d in days]
    if not rain:
        return missing("flood", label, "Open-Meteo", URLS["forecast"], critical=True)
    max24 = max(rain)
    sum72 = max(sum(rain[i:i + 3]) for i in range(max(1, len(rain) - 2)))
    lv = rain_level(max24, sum72)
    expl = [f"Forecast rain: up to {max24:.0f} mm in a day, {sum72:.0f} mm in 3 days."]
    details: dict = {"rain_max_24h": round(max24, 1), "rain_max_72h": round(sum72, 1)}
    river, _ = _doc(p["id"], "river")
    flood, _ = _doc(p["id"], "flood")
    if river and river.get("cell") and river.get("climate") and flood and flood.get("days"):
        cell, clim = river["cell"], river["climate"]
        qmax = max(max(d["q"], d.get("q_ens_max") or 0) for d in flood["days"])
        rl = river_level(qmax, clim)
        above = (p.get("elevation_m") or 0) - (cell.get("elevation") or 0)
        details |= {"river_q_max_forecast": round(qmax, 1), "river_q2": clim["q2_m3s"],
                    "river_distance_km": cell["distance_km"], "height_above_river_m": above}
        note = (f"Nearest large river cell ({cell['distance_km']} km, GloFAS): forecast up to "
                f"{qmax:.0f} m3/s (2-year flood level {clim['q2_m3s']:.0f} m3/s).")
        if above >= 30 and rl > 1:
            rl = 1
            note += f" The place sits about {above:.0f} m above that cell: capped at Watch."
        expl.append(note)
        lv = max(lv, rl)
    elif river is not None and not river.get("cell"):
        expl.append("No river with a mean flow of 1 m3/s or more within about 15 km (GloFAS).")
    return factor("flood", label, lv, round(max24, 1), "mm / 24 h (max)",
                  "rain: > 35 mm/24 h watch, > 90 prepare, >= 150 act; river: above the "
                  "99th percentile watch, 2-year flood prepare, 10-year flood act",
                  " ".join(expl), "Open-Meteo forecast + GloFAS", URLS["flood"],
                  days[0]["date"] if days else None, "forecast",
                  _is_stale("forecast", upd, now), details, critical=True)


def gust_level(g: float) -> int:
    """Beaufort gust bands (as on the Samui watch): >= 75 km/h (9) 1 ; >= 89 (10-11) 2 ;
    >= 118 (12) 3."""
    if g >= 118:
        return 3
    if g >= 89:
        return 2
    if g >= 75:
        return 1
    return 0


def events_near(lat: float, lon: float, radius_km: float,
                categories: tuple[str, ...] | None = None) -> list[dict]:
    rows = db.query("SELECT source, ext_id, category, title, url, severity, lat, lon, "
                    "started_at, updated_at FROM events WHERE lat IS NOT NULL")
    out = []
    for r in rows:
        if categories and r["category"] not in categories:
            continue
        d = haversine_km(lat, lon, r["lat"], r["lon"])
        if d <= radius_km:
            out.append(r | {"distance_km": round(d)})
    return sorted(out, key=lambda r: r["distance_km"])


def f_storm(p: dict, now: datetime) -> dict:
    label = "Storm / wind (gusts, tropical cyclones)"
    fc, upd = _doc(p["id"], "forecast")
    days = [d for d in _future_days(fc, p) if d.get("wind_gusts_10m_max") is not None] \
        if fc else []
    if not days:
        return missing("storm", label, "Open-Meteo", URLS["forecast"], critical=True)
    top = max(days, key=lambda d: d["wind_gusts_10m_max"])
    g = top["wind_gusts_10m_max"]
    lv = gust_level(g)
    expl = f"Strongest forecast gust over the next {len(days)} days: {g:.0f} km/h ({top['date']})."
    tcs = events_near(p["lat"], p["lon"], 800, ("cyclone",))
    if tcs:
        t = tcs[0]
        expl += (f" Tropical cyclone '{t['title']}' ({t['source']}, {t['severity']}) "
                 f"{t['distance_km']} km away.")
        if t["severity"] in ("orange", "red") and t["distance_km"] <= 300:
            lv = 4
        elif t["severity"] in ("orange", "red") and t["distance_km"] <= 500:
            lv = max(lv, 3)
        else:
            lv = max(lv, 1)
    return factor("storm", label, lv, round(g, 0), "km/h gust",
                  "gusts >= 75 watch, >= 89 prepare, >= 118 act; cyclone within 800 km watch, "
                  "orange/red <= 500 km act, <= 300 km leave (as on the Samui watch)",
                  expl, "Open-Meteo forecast + GDACS/EONET", URLS["forecast"], top["date"],
                  "forecast", _is_stale("forecast", upd, now),
                  {"cyclones": tcs[:3]}, critical=True)


def pm25_level(v: float) -> int:
    """Thai PCD PM2.5 bands (24 h mean): > 37.5 watch, > 75 prepare, > 125 act. Applied to
    every place for comparability; the WHO 24 h guideline (15 µg/m³) is stricter."""
    if v > 125:
        return 3
    if v > 75:
        return 2
    if v > 37.5:
        return 1
    return 0


def f_air(p: dict, now: datetime) -> dict:
    label = "Air quality (PM2.5, 24 h mean)"
    air, upd = _doc(p["id"], "air")
    pts = (air or {}).get("hourly_pm2_5") or []
    if len(pts) < 24:
        return missing("air", label, "Open-Meteo (CAMS)", URLS["air"])
    past = [x["pm2_5"] for x in pts if not x["forecast"]][-24:]
    fut = [x["pm2_5"] for x in pts if x["forecast"]][:72]
    m24 = sum(past) / len(past) if past else None
    worst = max((sum(fut[i:i + 24]) / 24 for i in range(max(1, len(fut) - 23))),
                default=None) if len(fut) >= 24 else None
    ref = max(x for x in (m24, worst) if x is not None)
    pol = (air or {}).get("pollen")
    parts = []
    if m24 is not None:
        parts.append(f"PM2.5 last 24 h (CAMS model analysis): {m24:.1f} µg/m³")
    if worst is not None:
        parts.append(f"worst 24 h mean forecast in the next 72 h: {worst:.1f} µg/m³")
    expl = ("; ".join(parts) + ". The higher of the two is rated." if len(parts) == 2
            else ("; ".join(parts) + "." if parts else "PM2.5"))
    return factor("air", label, pm25_level(ref), round(ref, 1), "µg/m³ (24 h)",
                  "PCD bands: > 37.5 watch, > 75 prepare, > 125 act (WHO guideline: 15)",
                  expl,
                  "Open-Meteo (Copernicus CAMS)", URLS["air"],
                  (air or {}).get("current", {}).get("time"), "model_analysis",
                  _is_stale("air", upd, now),
                  {"pm25_mean_24h": round(m24, 1) if m24 is not None else None,
                   "pm25_worst_24h_forecast": round(worst, 1) if worst is not None else None,
                   "us_aqi": (air or {}).get("current", {}).get("us_aqi"),
                   "european_aqi": (air or {}).get("current", {}).get("european_aqi"),
                   "pollen": pol})


def f_wildfire(p: dict, now: datetime) -> dict:
    label = f"Wildfire (satellite detections within {FIRE_RADIUS_KM} km, 24 h)"
    fires, upd = _doc(p["id"], "fires")
    if not fires or fires.get("count") is None:
        return missing("wildfire", label, "NASA FIRMS", URLS["firms"],
                       (fires or {}).get("note", ""))
    n, n50 = fires["count"], fires["count_50km"]
    lv = 3 if n50 >= 100 else 2 if n50 >= 25 else 1 if n >= 3 else 0
    ev = events_near(p["lat"], p["lon"], FIRE_RADIUS_KM, ("wildfire",))
    ev = [e for e in ev if e["source"] != "firms_fires"]
    if ev and lv < 1:
        lv = 1
    expl = (f"{n} VIIRS fire detections within {FIRE_RADIUS_KM} km in the last 24 h "
            f"({n50} within 50 km).")
    if ev:
        expl += f" Open wildfire event: {ev[0]['title']} ({ev[0]['distance_km']} km)."
    return factor("wildfire", label, lv, n, "detections",
                  ">= 3 within 100 km watch, >= 25 within 50 km prepare, >= 100 act", expl,
                  "NASA FIRMS (VIIRS)", fires.get("url") or URLS["firms"],
                  fires.get("newest") or upd, "observed", _is_stale("fires", upd, now),
                  {"count_50km": n50, "nearest_km": fires.get("nearest_km"), "events": ev[:3]})


def f_earthquake(p: dict, now: datetime) -> dict:
    label = f"Earthquakes (within {QUAKE_RADIUS_KM} km, 30 days)"
    q, upd = _doc(p["id"], "quakes_recent")
    if q is None:
        return missing("earthquake", label, "USGS", URLS["usgs"])
    ev = q["events"]
    lv = 0
    for e in ev:
        if e["mag"] >= 7:
            lv = max(lv, 3)
        elif e["mag"] >= 6:
            lv = max(lv, 2)
        elif e["mag"] >= 5 and e["distance_km"] <= 150:
            lv = max(lv, 1)
    big = max(ev, key=lambda e: e["mag"]) if ev else None
    expl = (f"{len(ev)} M2.5+ earthquake(s) within {QUAKE_RADIUS_KM} km in 30 days"
            + (f"; strongest M{big['mag']} {big['place']} ({big['distance_km']:.0f} km)."
               if big else "."))
    return factor("earthquake", label, lv, big["mag"] if big else 0, "max magnitude",
                  "M5+ within 150 km watch, M6+ within 300 km prepare (aftershocks), M7+ act",
                  expl, "USGS", URLS["usgs"], big["time"] if big else upd, "observed",
                  _is_stale("quakes_recent", upd, now), {"count": len(ev), "events": ev[:5]})


def f_warnings(p: dict, now: datetime) -> dict:
    label = "Official weather warnings"
    w = p.get("warnings") or {}
    if w.get("meteoalarm"):
        feed = w["meteoalarm"]["feed"]
        s = db.get_status(f"places_meteoalarm:{feed}")
        if not s:
            return missing("warnings", label, "Meteoalarm", URLS["meteoalarm"])
        from .collectors import meteoalarm_for

        act = meteoalarm_for(s["value"], w["meteoalarm"]["areas"], now)
        lv = max((x["level"] or 0 for x in act), default=0)
        expl = ("No yellow, orange or red warning for "
                f"{', '.join(w['meteoalarm']['areas'])} in the Meteoalarm feed."
                if not act else "; ".join(f"{x['title']} (until {x['expires']})" for x in act))
        return factor("warnings", label, lv, len(act), "active warnings",
                      "yellow watch, orange prepare, red act (Meteoalarm colours)", expl,
                      "Meteoalarm (EUMETNET) -- national service: "
                      + ("Meteo-France vigilance" if feed == "france" else feed),
                      "https://vigilance.meteofrance.fr/fr/calvados" if feed == "france"
                      else URLS["meteoalarm"], s["value"].get("updated") or s["updated_at"],
                      "bulletin", _is_stale("forecast", s["updated_at"], now),
                      {"warnings": act, "feed": s["value"].get("url")})
    if w.get("hydromet_ru"):
        s = db.get_status("places_hydromet_ru")
        if not s:
            return missing("warnings", label, "Hydrometcenter of Russia", URLS["hydromet"])
        from .collectors import hydromet_for

        b = s["value"]
        hit = hydromet_for(b, w["hydromet_ru"]["stem"])
        lv = (2 if hit["severe_wording"] else 1) if hit["forecast_mentions"] else 0
        issued = b.get("date")
        old = issued and (now.date() - date.fromisoformat(issued)).days > 2
        expl = (f"Bulletin No {b['number']} of {issued}: "
                + ("the region is named in the forecast of dangerous/adverse weather."
                   if hit["forecast_mentions"] else
                   "the region is not named in the forecast of dangerous/adverse weather."))
        return factor("warnings", label, lv, len(hit["forecast_mentions"]), "mentions",
                      "region named: watch; named with 'very heavy', 'hurricane', 'severe "
                      "frost'... wording: prepare", expl,
                      "Hydrometcenter of Russia (Roshydromet)", URLS["hydromet"], issued,
                      "bulletin", bool(old) or _is_stale("forecast", s["updated_at"], now),
                      hit | {"district_text": (b.get("forecast") or {}).get(
                          next((k for k in (b.get("forecast") or {})
                                if k.startswith(w["hydromet_ru"].get("district", "~"))), ""))})
    if w.get("tmd"):
        s = db.get_status("tmd_warnings")
        if not s:
            return missing("warnings", label, "Thai Meteorological Department", URLS["tmd"],
                           "Collected by the Koh Samui watch (tmd_warnings).")
        today = _place_today(p).isoformat()
        act = [it for it in s["value"].get("items", [])
               if it.get("until") and it["until"] >= today and it.get("affects_samui")]
        # Same reading as the Koh Samui watch (local/risk.py): a regional heavy-rain
        # bulletin that names the South is a watch (level 1); a bulletin that names Samui /
        # Surat Thani, a storm or strong waves in the Gulf is a prepare (level 2).
        lv = 0
        if act:
            lv = 2 if any(it.get("mentions_samui") or it.get("strong_waves_gulf")
                          or it.get("storm") for it in act) else 1
        latest = act[0] if act else None
        expl = ("No active TMD bulletin for the Gulf side / Surat Thani." if not act else
                f"{len(act)} TMD bulletin(s) in force (each update of a warning is a new "
                f"issue); latest: {latest.get('summary_en') or latest['title']}"
                + (" (names Samui / Surat Thani)" if latest.get("mentions_samui") else
                   " (regional bulletin, Samui not named)"))
        return factor("warnings", label, lv, len(act), "active bulletins",
                      "regional heavy-rain bulletin: watch; bulletin naming Samui / Surat "
                      "Thani, a storm or strong Gulf waves: prepare", expl,
                      "Thai Meteorological Department", URLS["tmd"],
                      s["updated_at"], "bulletin", _is_stale("forecast", s["updated_at"], now),
                      {"items": act[:3]})
    return missing("warnings", label, "", "",
                   "No keyless official warning feed is connected for this place.")


FACTORS = (f_heat, f_cold, f_water, f_flood, f_storm, f_air, f_wildfire, f_earthquake,
           f_warnings)


def combine(factors: list[dict]) -> dict:
    lv = {f["id"]: f["level"] for f in factors if f["level"] is not None}
    contrib = {k: min(v, CAP.get(k, 3)) for k, v in lv.items()}
    level = max(contrib.values(), default=0)
    rules = ["R1 overall = highest factor, each capped (earthquake at 2)"]
    hot = [k for k in PHYSICAL if contrib.get(k, 0) >= 2]
    if len(hot) >= 2 and level < 3:
        level = 3
        rules.append(f"R3 two hazards at 'prepare' together ({', '.join(hot)}) -> act")
    miss = [f["id"] for f in factors if f["id"] in CRITICAL and f["level"] is None]
    if miss:
        return {"level": None, "level_key": "unknown", "level_floor": level,
                "level_floor_key": level_key(level), "rules": rules,
                "missing_critical": miss}
    return {"level": level, "level_key": level_key(level), "level_floor": level,
            "level_floor_key": level_key(level), "rules": rules, "missing_critical": []}


def current_conditions(p: dict) -> dict | None:
    fc, upd = _doc(p["id"], "forecast")
    if not fc:
        return None
    c = fc["current"]
    code = c.get("weather_code")
    return c | {"weather": WMO_CODES.get(int(code)) if code is not None else None,
                "updated_at": upd, "source": "Open-Meteo forecast", "url": URLS["forecast"]}


# --------------------------------------------------------------------------- exposure matrix

DIMENSIONS = [
    {"id": "heat_stress", "label": "Heat stress", "rank": True},
    {"id": "cold", "label": "Cold / winter severity", "rank": True},
    {"id": "water", "label": "Water / drought", "rank": True},
    {"id": "flood", "label": "Flood", "rank": True},
    {"id": "storms", "label": "Storms / cyclones", "rank": True},
    {"id": "air", "label": "Air quality", "rank": True},
    {"id": "wildfire", "label": "Wildfire (fire-weather)", "rank": True},
    {"id": "earthquakes", "label": "Earthquakes", "rank": True},
    {"id": "enso", "label": "ENSO sensitivity", "rank": True},
    {"id": "trend_2050", "label": "Climate trend to 2050", "rank": True},
    {"id": "coverage", "label": "Data coverage", "rank": False},
]


def band(v: float, edges: tuple[float, ...]) -> int:
    """edges = upper bounds of scores 0..3; above the last edge -> 4."""
    for i, e in enumerate(edges):
        if v < e:
            return i
    return 4


def cell(score: int | None, value, unit: str | None, rule: str, note: str, source: str,
         url: str, as_of: str | None, details: dict | None = None) -> dict:
    return {"score": score, "label": None if score is None else EXPOSURE_LABELS[score],
            "value": value, "unit": unit, "rule": rule, "note": note, "source": source,
            "url": url, "as_of": as_of, "details": details or {}}


def _longest_circular_run(months: list[int]) -> int:
    s = set(months)
    if len(s) == 12:
        return 12
    best = run = 0
    for m in list(range(1, 13)) * 2:
        run = run + 1 if m in s else 0
        best = max(best, run)
    return min(best, 12)


def exposure(p: dict) -> dict[str, dict]:
    pid = p["id"]
    normals, n_upd = _doc(pid, "normals")
    proj, p_upd = _doc(pid, "projection")
    air_year, a_upd = _doc(pid, "air_year")
    marine, _ = _doc(pid, "marine")
    river, _ = _doc(pid, "river")
    qh, q_upd = _doc(pid, "quakes_hist")
    ctx_notes = {c["dimension"]: c for c in p.get("context") or []}
    out: dict[str, dict] = {}
    na = "no data yet"
    era5_src = f"ERA5 1991-2020 ({normals['period']})" if normals else "ERA5 1991-2020"

    if normals:
        a = normals["annual"]
        out["heat_stress"] = cell(
            band(a["heat_days"], (5, 30, 90, 180)), a["heat_days"], "days/yr",
            "days with feels-like max > 35 °C: < 5 very low, 5-30 low, 30-90 moderate, "
            "90-180 high, >= 180 very high",
            f"Warmest month mean {a['warmest_month_t_mean']:.1f} °C.", era5_src, URLS["era5"],
            n_upd)
        cm = a["coldest_month_t_mean"]
        out["cold"] = cell(
            band(-cm, (-10, -3, 3, 10)), cm, "°C (coldest month mean)",
            "coldest month mean: >= 10 °C very low, 3-10 low, -3..3 moderate, -10..-3 high, "
            "< -10 very high",
            f"{a['frost_days']:.0f} frost days/yr, {a['snow_cm']:.0f} cm of snowfall/yr.",
            era5_src, URLS["era5"], n_upd,
            {"frost_days": a["frost_days"], "snow_cm": a["snow_cm"]})
        ai = a["aridity_index"]
        run = _longest_circular_run(a["dry_months"])
        s = 0 if ai >= 0.65 else 1 if ai >= 0.5 else 2 if ai >= 0.2 else 3 if ai >= 0.05 else 4
        s = min(4, s + (1 if run >= 3 else 0))
        note = (f"Rain {a['precip_mm']:.0f} mm/yr vs potential evaporation {a['et0_mm']:.0f} "
                f"mm/yr; {run} consecutive month(s) where rain < half of evaporation.")
        if "water" in ctx_notes:
            note += " " + ctx_notes["water"]["text"]
        out["water"] = cell(
            s, ai, "aridity index (P/ET0)",
            "UNEP aridity class (>= 0.65 humid 0, 0.5-0.65 dry sub-humid 1, 0.2-0.5 "
            "semi-arid 2, 0.05-0.2 arid 3, < 0.05 hyper-arid 4), +1 if 3+ consecutive "
            "months get less than half of their evaporation", note, era5_src, URLS["aridity"],
            n_upd, {"dry_run_months": run, "context": ctx_notes.get("water")})
        rain_s = band(a["heavy_rain_days"], (0.5, 2, 5, 10))
        parts = [(f"{a['heavy_rain_days']:.1f} days/yr with >= 50 mm of rain (ERA5 smooths "
                  "peaks: real local extremes are higher).")]
        river_s = coast_s = 0
        if river and river.get("cell"):
            c = river["cell"]
            above = (p.get("elevation_m") or 0) - (c.get("elevation") or 0)
            river_s = 3 if above < 3 else 2 if above < 10 else 1 if above < 30 else 0
            parts.append(f"River cell {c['distance_km']} km away, mean flow "
                         f"{c['mean_m3s']:.0f} m3/s; the place is about {above:.0f} m above "
                         "that cell.")
        elif river is not None:
            parts.append("No river of 1 m3/s or more within about 15 km.")
        if marine and marine.get("sea_cell") and (marine.get("cell_distance_km") or 99) <= 10:
            el = p.get("elevation_m") or 0
            coast_s = 3 if el < 5 else 2 if el < 10 else 1 if el < 20 else 0
            parts.append(f"Coastal: sea cell {marine['cell_distance_km']} km away, elevation "
                         f"{el:.0f} m (storm surge / coastal flooding exposure).")
        out["flood"] = cell(
            max(rain_s, river_s, coast_s), a["heavy_rain_days"], "days/yr >= 50 mm",
            "max of: heavy-rain days (< 0.5, 0.5-2, 2-5, 5-10, >= 10), height above the "
            "nearest river cell (< 3 m 3, < 10 m 2, < 30 m 1), coastal and < 5 / 10 / 20 m "
            "(3 / 2 / 1)", " ".join(parts), era5_src + " + GloFAS + Open-Meteo Marine",
            URLS["flood"], n_upd, {"rain": rain_s, "river": river_s, "coast": coast_s})
        s = band(a["gust_days"], (0.5, 2, 5, 15))
        note = (f"{a['gust_days']:.1f} days/yr with gusts >= 75 km/h (ERA5, ~30 km: "
                "it underestimates local gusts).")
        if "storms" in ctx_notes:
            note += " " + ctx_notes["storms"]["text"]
        out["storms"] = cell(
            s, a["gust_days"], "days/yr gust >= 75 km/h",
            "gust days: < 0.5 very low, 0.5-2 low, 2-5 moderate, 5-15 high, >= 15 very high",
            note, era5_src, URLS["era5"], n_upd, {"context": ctx_notes.get("storms")})
        fire_m = [m["month"] for m in normals["months"]
                  if m["t_max"] >= 20 and m["precip_mm"] < 0.5 * m["et0_mm"]]
        out["wildfire"] = cell(
            band(len(fire_m), (1, 3, 5, 7)), len(fire_m), "warm dry months/yr",
            "proxy: months with mean max >= 20 °C and rain < half of evaporation: 0 very low, "
            "1-2 low, 3-4 moderate, 5-6 high, >= 7 very high",
            "A fire-weather proxy from the climate normals, not a fire record (the FIRMS "
            "archive needs a key). The 24 h satellite detections are in the current factors.",
            era5_src, URLS["era5"], n_upd, {"months": fire_m})
    else:
        for k in ("heat_stress", "cold", "water", "flood", "storms", "wildfire"):
            out[k] = cell(None, None, None, "", na + " (1991-2020 normals are computed once "
                          "per place, one place per run)", "ERA5", URLS["era5"], None)

    if air_year:
        v = air_year["pm25_annual_mean"]
        out["air"] = cell(
            band(v, (5, 10, 15, 25)), v, "µg/m³ PM2.5 (annual mean)",
            "WHO 2021: <= 5 guideline (very low), 5-10 low (IT-4), 10-15 moderate (IT-3), "
            "15-25 high (IT-2), > 25 very high",
            f"Last 365 days, CAMS global model: {air_year['days_over_15']} days above the WHO "
            f"24 h guideline (15), {air_year['days_over_37_5']} above 37.5; worst day "
            f"{air_year['worst_day']}.", "Open-Meteo air quality (CAMS global)", URLS["who_air"],
            a_upd, {"monthly_mean": air_year.get("monthly_mean")})
    else:
        out["air"] = cell(None, None, None, "", na, "CAMS", URLS["air"], None)

    if qh is not None:
        n = qh["count"]
        out["earthquakes"] = cell(
            band(n, (1, 6, 26, 101)), n, f"M4.5+ within {QUAKE_RADIUS_KM} km since 1976",
            "count: 0 very low, 1-5 low, 6-25 moderate, 26-100 high, > 100 very high",
            (f"Strongest: M{qh['max_mag']}. " if qh.get("max_mag") else "")
            + "A catalogue count, not a hazard map: see the GEM global seismic hazard map.",
            "USGS catalogue", URLS["gem"], q_upd, {"strongest": qh.get("strongest", [])[:3]})
    else:
        out["earthquakes"] = cell(None, None, None, "", na, "USGS", URLS["usgs"], None)

    e = enso_ctx.assess(p["lat"], p["lon"])
    out["enso"] = cell(e["strength"], e["strength_label"], "teleconnection",
                       "curated from agency and peer-reviewed sources: 0 none known ... "
                       "4 very strong", e["el_nino_effect"] or e["mechanism"],
                       ", ".join(s["title"].split(" -- ")[0] for s in e["sources"][:2]),
                       e["sources"][0]["url"], "2026-09-24", {"region": e["region_label"]})

    if proj:
        dt = proj["delta"]["t_mean"]["mean"]
        dh = proj["delta"]["hot_days_yr"]["mean"]
        s = band(dt, (0.75, 1.25, 1.75, 2.5))
        if dh >= 30:
            s = max(s, 3)
        elif dh >= 10:
            s = max(s, 2)
        out["trend_2050"] = cell(
            s, round(dt, 2), f"°C warming ({proj['future']} vs {proj['baseline']})",
            "warming < 0.75 very low, 0.75-1.25 low, 1.25-1.75 moderate, 1.75-2.5 high, "
            ">= 2.5 very high; at least moderate if +10 hot days/yr, high if +30",
            f"{proj['n_models']} models: warming {proj['delta']['t_mean']['min']:+.1f} to "
            f"{proj['delta']['t_mean']['max']:+.1f} °C; hot days (> 35 °C) {dh:+.0f}/yr; "
            f"frost days {proj['delta']['frost_days_yr']['mean']:+.0f}/yr; rain "
            f"{proj['delta']['precip_pct']['mean']:+.0f}% (range "
            f"{proj['delta']['precip_pct']['min']:+.0f} to "
            f"{proj['delta']['precip_pct']['max']:+.0f}%). High-emission pathway.",
            "Open-Meteo climate API (CMIP6 HighResMIP)", URLS["climate"], p_upd)
    else:
        out["trend_2050"] = cell(None, None, None, "", na + " (computed once per place)",
                                 "CMIP6", URLS["climate"], None)

    scored = [k for k, v in out.items() if v["score"] is not None]
    ranked = [d["id"] for d in DIMENSIONS if d["rank"]]
    have = len([k for k in ranked if k in scored])
    miss = [k for k in ranked if k not in scored]
    out["coverage"] = cell(band(len(miss), (1, 2, 4, 6)), f"{have}/{len(ranked)}", "dimensions",
                           "missing dimensions: 0 very low ... 6+ very high (not ranked)",
                           ("All dimensions have data." if not miss else
                            f"Missing: {', '.join(miss)}."), "this engine", "", db.now_iso(),
                           {"missing": miss})
    return out


# --------------------------------------------------------------------------- ENSO live

def enso_now() -> dict:
    def latest(series: str) -> dict | None:
        r = db.query("SELECT source, ts, value FROM observations WHERE series=? AND ts<=? "
                     "ORDER BY ts DESC LIMIT 1", (series, db.now_iso()))
        return r[0] if r else None

    iri = db.get_status("iri_plume")
    cpc = db.get_status("cpc_alert")
    return {"roni": latest("roni"), "oni": latest("oni"),
            "nino34_weekly": latest("nino34_weekly_anom"),
            "cpc_status": (cpc["value"].get("status") if cpc else None),
            "cpc_issued": (cpc["value"].get("issued") if cpc else None),
            "iri_issued": (iri["value"].get("issued") if iri else None),
            "iri_probabilities": (iri["value"].get("probabilities", [])[:6] if iri else [])}


# --------------------------------------------------------------------------- assembly

def _headline(p: dict, comb: dict, factors: list[dict]) -> str:
    if comb["level"] is None:
        return (f"{p['short_name']}: level unknown -- no current data for "
                f"{', '.join(comb['missing_critical'])}.")
    drivers = [f["label"].split(" (")[0] for f in factors
               if f["level"] is not None and f["level"] >= max(1, comb["level"])]
    if comb["level"] == 0:
        return f"{p['short_name']}: nothing abnormal in the current data."
    return f"{p['short_name']}: {level_key(comb['level'])} -- {', '.join(drivers)}."


def place_summary(p: dict, now: datetime | None = None) -> dict:
    now = now or _now()
    factors = [f(p, now) for f in FACTORS]
    comb = combine(factors)
    out = {k: p.get(k) for k in ("id", "name", "short_name", "admin", "country",
                                 "country_code", "lat", "lon", "elevation_m", "timezone",
                                 "role", "geocode", "added_by")}
    out |= comb | {"headline": _headline(p, comb, factors), "evaluated_at": db.now_iso(),
                   "current": current_conditions(p), "factors": factors}
    if p.get("warnings", {}).get("tmd"):
        s = db.get_status("local_risk")
        if s:
            v = s["value"]
            out["samui_watch"] = {k: v.get(k) for k in ("level", "level_key", "headline",
                                                        "evaluated_at")} | {"url": "/samui"}
    return out


def place_detail(p: dict, now: datetime | None = None) -> dict:
    now = now or _now()
    out = place_summary(p, now)
    fc, fupd = _doc(p["id"], "forecast")
    normals, nupd = _doc(p["id"], "normals")
    seasonal, supd = _doc(p["id"], "seasonal")
    proj, pupd = _doc(p["id"], "projection")
    marine, mupd = _doc(p["id"], "marine")
    river, _ = _doc(p["id"], "river")
    flood, flupd = _doc(p["id"], "flood")
    rec, rupd = _doc(p["id"], "recent")
    qh, _ = _doc(p["id"], "quakes_hist")
    out |= {
        "forecast": {"daily": fc["daily"], "updated_at": fupd, "units": fc.get("units"),
                     "source": "Open-Meteo forecast", "url": URLS["forecast"]} if fc else None,
        "normals": normals | {"updated_at": nupd} if normals else None,
        "recent": {"last_day": rec["last_day"], "updated_at": rupd,
                   "rain_30d": round(sum(d["precip"] for d in rec["days"][-30:]), 1),
                   "rain_90d": round(sum(d["precip"] for d in rec["days"][-90:]), 1)}
        if rec else None,
        "seasonal": seasonal | {"updated_at": supd} if seasonal else None,
        "projection": proj | {"updated_at": pupd} if proj else None,
        "marine": marine | {"updated_at": mupd} if marine else None,
        "river": river | {"forecast": flood, "forecast_updated_at": flupd} if river else None,
        "quakes_history": qh,
        "events_near": events_near(p["lat"], p["lon"], 500)[:20],
        "exposure": exposure(p),
        "enso": enso_ctx.assess(p["lat"], p["lon"]) | {"now": enso_now()},
        "advisories": advisories_for(p),
        "context": p.get("context") or [],
    }
    return out


def advisories_for(p: dict) -> dict:
    s = db.get_status("places_advisories")
    if not s or not p.get("country_code"):
        return {}
    return (s["value"].get("countries") or {}).get(p["country_code"], {}) | {
        "fetched_at": s["updated_at"]}


def parse_weights(raw: str | None) -> dict[str, float]:
    ranked = [d["id"] for d in DIMENSIONS if d["rank"]]
    w = {k: 1.0 for k in ranked}
    for part in (raw or "").split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            k = k.strip()
            if k in w:
                try:
                    w[k] = max(0.0, min(10.0, float(v)))
                except ValueError:
                    pass
    return w


def ranking(expo: dict[str, dict[str, dict]], weights: dict[str, float]) -> list[dict]:
    rows = []
    for pid, dims in expo.items():
        num = den = 0.0
        used, skipped = [], []
        for k, w in weights.items():
            if w <= 0:
                continue
            s = dims.get(k, {}).get("score")
            if s is None:
                skipped.append(k)
                continue
            num += w * (4 - s)
            den += w
            used.append(k)
        score = round(100 * num / (4 * den), 1) if den else None
        rows.append({"id": pid, "score": score, "used": used, "missing": skipped})
    rows.sort(key=lambda r: -1 if r["score"] is None else r["score"], reverse=True)
    for i, r in enumerate(rows):
        r["rank"] = i + 1 if r["score"] is not None else None
    return rows


def best_for(expo: dict[str, dict[str, dict]], names: dict[str, str]) -> list[dict]:
    """Factual 'which is better for what': for each ranked dimension, the least and most
    exposed places with their values. No weighting, no opinion."""
    out = []
    for d in DIMENSIONS:
        if not d["rank"]:
            continue
        vals = [(pid, dims[d["id"]]) for pid, dims in expo.items()
                if dims.get(d["id"], {}).get("score") is not None]
        if len(vals) < 2:
            continue
        lo = min(v[1]["score"] for v in vals)
        hi = max(v[1]["score"] for v in vals)

        def fmt(pid: str, c: dict) -> str:
            v = c["value"]
            v = f"{v:g}" if isinstance(v, float) else str(v)
            return f"{names[pid]} ({v} {c['unit'] or ''}, {c['label']})".replace(" ,", ",")

        best = [fmt(pid, c) for pid, c in vals if c["score"] == lo]
        worst = [fmt(pid, c) for pid, c in vals if c["score"] == hi]
        text = (f"{d['label']}: all places score the same ({EXPOSURE_LABELS[lo]})."
                if lo == hi else
                f"{d['label']}: least exposed {' / '.join(best)}; most exposed "
                f"{' / '.join(worst)}.")
        out.append({"dimension": d["id"], "label": d["label"], "text": text,
                    "best": [pid for pid, c in vals if c["score"] == lo],
                    "worst": [pid for pid, c in vals if c["score"] == hi] if lo != hi else []})
    return out


def compare(weights_raw: str | None = None, now: datetime | None = None) -> dict:
    now = now or _now()
    places = config.list_places()
    summaries = [place_summary(p, now) for p in places]
    expo = {p["id"]: exposure(p) for p in places}
    names = {p["id"]: p["short_name"] for p in places}
    weights = parse_weights(weights_raw)
    return {
        "evaluated_at": db.now_iso(),
        "places": [{k: s[k] for k in ("id", "name", "short_name", "country", "country_code",
                                      "lat", "lon", "role", "level", "level_key", "headline",
                                      "current")} for s in summaries],
        "dimensions": DIMENSIONS,
        "exposure_labels": EXPOSURE_LABELS,
        "matrix": {d["id"]: {pid: expo[pid].get(d["id"]) for pid in expo} for d in DIMENSIONS},
        "current": {s["id"]: {f["id"]: {k: f[k] for k in ("level", "level_key", "value",
                                                          "unit", "observed_at", "kind",
                                                          "stale")}
                              for f in s["factors"]} for s in summaries},
        "weights": weights,
        "ranking": ranking(expo, weights),
        "summary": best_for(expo, names),
        "advisories": {p["id"]: advisories_for(p) for p in places},
        "enso_now": enso_now(),
        "disclaimer": DISCLAIMER,
    }
