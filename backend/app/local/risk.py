"""Koh Samui risk engine: explainable, rule based, no black-box score.

Each factor reads real data from the DB (this package's collectors and the
other domains: indices, official, maritime, hazards, news, social) and returns

    {id, label, level (0..4 | None), level_key, value, value_raw, unit, unit_label,
     value_label, kind, valid_for, tz, issued_at, retrieved_at, observed_at, as_of,
     threshold, explanation, summary, source, url, stale, details, inputs, next, steps}

PROVENANCE (see provenance.py): `kind` says what the headline value IS -- observed,
forecast, model_analysis, reanalysis or bulletin -- and `valid_for` which day or period
it describes. `observed_at` is only set for values that describe the past (it is null
for a forecast: a forecast is never "observed"); `as_of` is the time to show next to
the value (observation time, else issue time, else the time we fetched it). `inputs`
lists every number the factor used, each with its own kind / valid_for / source.

`level=None` means "no current data": missing data is NEVER read as safe, and the
explanation then says what is missing, why, and what to check by hand (with a link).
A factor whose data is stale and would read 0 is also reported as None.

Levels: 0 normal, 1 vigilance (Watch), 2 prepare, 3 act, 4 leave.

COVERAGE (see `coverage`): the critical factors are enso, water, heat, flood,
cyclone_wind and sea_state. If any of them has no data or stale data, the overall
`level` is None ("unknown") and the headline names what is missing; `level_floor`
(= R1-R4 over the factors that do have a level) says "at least ...".

SEASONS (see `season_context`, `water_season`, `f_flood`): Samui's rainy season is the
NE monsoon, October-January (November wettest); the dry season runs February-May,
and with El Nino February-April 2027 is the water danger window.
  - water: in the dry season the 180-day window (which holds the last monsoon refill)
    drives the level if it is worse than 90 days; in October-December a deficit under a
    strong El Nino is at least 'prepare' (the reservoirs refill only now).
  - flood: +1 level when heavy rain is forecast on ground saturated by the past
    7 days of rain (>= 150 mm), which is typical of the NE monsoon.
  - sea state: only Gulf wave warnings count (TMD Andaman-only warnings are ignored).

FALLBACKS (a factor is 'no data' only when every source below is missing):
  water  ERA5 reanalysis -> Open-Meteo past-day model analyses (vs the same ERA5 normal,
         flagged) ; + PWA notices, ThaiWater dam, ECMWF SEAS5, news as modifiers.
  air    PCD Air4Thai measured (nearest fresh ground station) and/or CAMS model.
  flood  Open-Meteo forecast and/or ThaiWater island gauges and/or TMD bulletins.
  sea    Open-Meteo Marine and/or TMD Gulf wave bulletins.

OVERALL COMBINATION (documented rules, see `combine`):
  R1  overall = max over factors of min(level, CAP[factor]).
      CAP: enso 2 (a background driver, it can say "prepare", never "act"),
      water 3, heat 3, flood 3, cyclone_wind 3, sea_state 3, air 3,
      marine_heat 1 (context), news 1 (context).
  R2  news counts only if another factor is >= 1 (never the sole trigger).
  R3  two physical hazards >= 2 at the same time (among water, heat, flood,
      cyclone_wind, sea_state, air) -> at least 3 "act" (compound risk, e.g.
      flooding while the sea cuts the island off).
  R4  level 4 "leave" ONLY when a hazard directly threatens safety or basic
      supplies:
      R4a an orange/red GDACS tropical cyclone within 300 km (cyclone_wind = 4);
      R4b extreme heat (heat >= 3) together with a water supply crisis (water >= 3).
"""

from __future__ import annotations

import math
import re
from datetime import UTC, date, datetime, timedelta

from .. import db
from ..config import settings
from . import provenance as P
from .collectors import BKK, tmd_summary_en, today_bkk
from .provenance import fmt_day, fmt_ict, fmt_period, fmt_short, fmt_val, interval

ENGINE_VERSION = 3  # 3 = precision audit 2026-09-24 (kind / valid_for / unit_label)
LEVEL_KEYS = ["normal", "vigilance", "prepare", "act", "leave"]
LEVEL_LABELS = {"normal": "Normal", "vigilance": "Watch", "prepare": "Prepare",
                "act": "Act", "leave": "Leave"}
NA = "No current data"
# Verified 2026-09-24: PWA rotating supply on Samui from 3 Aug 2026 (El Nino dry spell).
SAMUI_RATIONING_2026_URL = ("https://www.bangkokpost.com/thailand/general/3293479/"
                            "koh-samui-faces-water-rationing")

CAP = {"enso": 2, "water": 3, "heat": 3, "flood": 3, "cyclone_wind": 3, "sea_state": 3,
       "air": 3, "marine_heat": 1, "news": 1}
PHYSICAL = ("water", "heat", "flood", "cyclone_wind", "sea_state", "air")

URLS = {
    "cpc": "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml",
    # NOAA CPC classifies ENSO with the relative index (RONI) since 2026; ONI kept alongside.
    "oni": "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/",
    "era5": "https://open-meteo.com/en/docs/historical-weather-api",
    "forecast": "https://open-meteo.com/en/docs",
    "air": "https://open-meteo.com/en/docs/air-quality-api",
    "pcd": "https://air4thai.pcd.go.th/webV3/",
    "gdacs": "https://www.gdacs.org/",
    "tmd": "https://www.tmd.go.th/",
    "tmd_warn": "https://www.tmd.go.th/en/warning-and-events/warning-storm",
    "tmd_week": "https://www.tmd.go.th/en/forecast/weekly",
    "marine": "https://open-meteo.com/en/docs/marine-weather-api",
    "crw": "https://coralreefwatch.noaa.gov/product/5km/index_5km_dhw.php",
    "crw_gulf": "https://coralreefwatch.noaa.gov/product/vs/gauges/west_gulf_of_thailand.php",
    "thaiwater": "https://www.thaiwater.net/",
    "pwa": "https://www.pwa.co.th/news/call1662",
}

# What the owner can check by hand when a factor has no data (links verified HTTP 200
# on 2026-09-24).
MANUAL = {
    "enso": [("NOAA CPC ENSO discussion", URLS["cpc"])],
    "water": [("PWA water-interruption notices (choose branch Ko Samui), or call PWA 1662",
               URLS["pwa"])],
    "heat": [("TMD 7-day forecast", URLS["tmd_week"])],
    "flood": [("TMD warnings", URLS["tmd_warn"]), ("ThaiWater rain map", URLS["thaiwater"])],
    "cyclone_wind": [("GDACS cyclone list", URLS["gdacs"]), ("TMD warnings", URLS["tmd_warn"])],
    "sea_state": [("TMD warnings (Gulf wave warnings)", URLS["tmd_warn"]),
                  ("Seatran ferry departures", "https://www.seatranferry.com/")],
    "air": [("Air4Thai (PCD) station map", URLS["pcd"])],
    "marine_heat": [("NOAA Coral Reef Watch, West Gulf of Thailand", URLS["crw_gulf"])],
    "news": [("Bangkok Post, Thailand news", "https://www.bangkokpost.com/thailand")],
}


# --------------------------------------------------------------------------- helpers

def level_key(level: int | None) -> str | None:
    return None if level is None else LEVEL_KEYS[max(0, min(4, level))]


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_ts(ts: str) -> datetime:
    return P.parse_dt(ts)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def latest_obs(series: str, source: str | None = None) -> dict | None:
    sql = "SELECT source, series, ts, value, unit, meta FROM observations WHERE series=?"
    p: list = [series]
    if source:
        sql += " AND source=?"
        p.append(source)
    rows = db.query(sql + " ORDER BY ts DESC LIMIT 1", tuple(p))
    return rows[0] if rows else None


def _points(series: str, since: str | None = None, until: str | None = None,
            source: str | None = None) -> list[dict]:
    sql = "SELECT source, ts, value, meta FROM observations WHERE series=?"
    p: list = [series]
    if source:
        sql += " AND source=?"
        p.append(source)
    if since:
        sql += " AND ts >= ?"
        p.append(since)
    if until:
        sql += " AND ts < ?"
        p.append(until)
    return db.query(sql + " ORDER BY ts", tuple(p))


def _status(key: str) -> dict | None:
    s = db.get_status(key)
    return s["value"] if s else None


def _last_ok_age_s(source_like: str) -> float | None:
    rows = db.query("SELECT finished_at FROM source_runs WHERE source LIKE ? AND ok=1 "
                    "ORDER BY id DESC LIMIT 1", (source_like,))
    if not rows or not rows[0]["finished_at"]:
        return None
    return (_now() - _parse_ts(rows[0]["finished_at"])).total_seconds()


def _stale(source: str, max_age_s: float) -> bool:
    age = _last_ok_age_s(source)
    return age is None or age > max_age_s


def why_no_data(source_like: str, label: str) -> str:
    """Precise reason a source gave nothing, from its run log."""
    rows = db.query("SELECT started_at, ok, error FROM source_runs WHERE source LIKE ? "
                    "ORDER BY id DESC LIMIT 1", (source_like,))
    ok = db.query("SELECT finished_at FROM source_runs WHERE source LIKE ? AND ok=1 "
                  "ORDER BY id DESC LIMIT 1", (source_like,))
    last_ok = fmt_ict(ok[0]["finished_at"]) if ok else None
    if not rows:
        return f"{label} has not been fetched yet since the service started"
    r = rows[0]
    if not r["ok"]:
        err = (r["error"] or "unknown error").splitlines()[0][:140]
        return (f"the last fetch of {label} failed at {fmt_ict(r['started_at'])} ({err}); "
                f"last success {last_ok or 'never'}")
    return (f"{label} answered (last success {last_ok}) but holds no value for the "
            "dates needed")


def _manual(fid: str) -> str:
    return "; ".join(f"{t}: {u}" for t, u in MANUAL.get(fid, []))


def factor(fid: str, label: str, level: int | None, value=None, unit: str | None = None,
           threshold: str = "", explanation: str = "", source: str = "", url: str = "",
           observed_at: str | None = None, stale: bool = False, details: dict | None = None,
           steps: dict[int, str] | None = None, *, kind: str | None = None,
           valid_for: str | None = None, issued_at: str | None = None,
           retrieved: str | None = None, unit_text: str | None = None,
           value_label: str | None = None, summary: str | None = None,
           inputs: list[dict] | None = None, decimals: int | None = None,
           tz: str = P.TZ_LOCAL) -> dict:
    """steps: {current_level: condition that raises this factor by one level}."""
    if stale and level == 0:
        # never report "safe" from old data
        level = None
        explanation = f"{explanation} Data too old to conclude: level unknown."
    if kind == "forecast":
        observed_at = None  # a forecast describes the future: nothing was observed
    shown = P.rnd(value, unit, decimals) if isinstance(value, (int, float)) \
        and not isinstance(value, bool) else value
    return {"id": fid, "label": label, "level": level, "level_key": level_key(level),
            "value": shown, "value_raw": value, "unit": unit,
            "unit_label": unit_text or P.unit_label(unit), "value_label": value_label,
            "kind": kind, "valid_for": valid_for, "tz": tz if kind else None,
            "issued_at": issued_at, "retrieved_at": retrieved, "observed_at": observed_at,
            "as_of": observed_at or issued_at or retrieved,
            "threshold": threshold, "explanation": explanation.strip(), "summary": summary,
            "source": source, "url": url, "stale": stale, "details": details or {},
            "inputs": inputs or [],
            "next": (steps or {}).get(level) if level is not None else None,
            "steps": {str(k + 1): v for k, v in (steps or {}).items()}}


def missing(fid: str, label: str, source: str, url: str, why: str = "",
            steps: dict[int, str] | None = None, what: str = "") -> dict:
    """No usable data: say exactly what is missing, why, and what to check by hand."""
    parts = [f"{NA}: {what or label.lower()}."]
    if why:
        parts.append(f"Why: {why.rstrip('.')}.")
    man = _manual(fid)
    if man:
        parts.append(f"Check by hand meanwhile: {man}.")
    return factor(fid, label, None, explanation=" ".join(parts), source=source, url=url,
                  steps=steps, details={"manual_check": [{"title": t, "url": u}
                                                         for t, u in MANUAL.get(fid, [])]},
                  summary=f"{label}: no current data")


# --------------------------------------------------------------------------- ENSO

def oni_level(v: float) -> int:
    """NOAA CPC ONI strength bands (ONI_v5 table conventions):
    < +0.5 neutral -> 0 ; +0.5..+1.0 weak and +1.0..+1.5 moderate -> 1 ;
    >= +1.5 strong (and >= +2.0 very strong) -> 2. Capped at 2 in the overall:
    ENSO is the background driver, not an immediate local hazard."""
    if v >= 1.5:
        return 2
    if v >= 0.5:
        return 1
    return 0


def enso_strength(v: float) -> str:
    """Conventional NOAA strength words for a 3-month index value (mirrored for La Nina)."""
    a = abs(v)
    if a < 0.5:
        return "ENSO-neutral"
    phase = "El Nino" if v > 0 else "La Nina"
    size = ("weak" if a < 1.0 else "moderate" if a < 1.5 else "strong" if a < 2.0
            else "very strong")
    return f"{size} {phase}"


def seasons_interval(codes: list[str], issued: str | None) -> str | None:
    """`valid_for` of a run of 3-month seasons ("SON", "OND", ... "MJJ") issued on `issued`
    (YYYY-MM-DD): the first day of the first season to the last day of the last one, as an
    ISO interval. The first season is the first match at or after the issue month (an IRI /
    CPC update issued in September starts with SON of that year). Returns None when the
    codes cannot be placed (the UI then shows no period rather than "--"; QA 24 Sep 2026:
    the previous "SON..MJJ" text rendered as "Forecast for --")."""
    ring = "JFMAMJJASOND"
    if not codes or not issued or len(issued) < 7:
        return None
    try:
        y, m = int(issued[:4]), int(issued[5:7])
    except ValueError:
        return None
    first = (codes[0] or "").upper()
    for k in range(12):
        i = (m - 1 + k) % 12
        if len(first) == 3 and all(ring[(i + j) % 12] == first[j] for j in range(3)):
            break
    else:
        return None
    start_idx = (y * 12 + m - 1) + k                   # month index of the first season
    end_idx = start_idx + (len(codes) - 1) + 2         # last month of the last season
    start = date(start_idx // 12, start_idx % 12 + 1, 1)
    ey, em = end_idx // 12, end_idx % 12 + 1
    end = (date(ey + (em == 12), em % 12 + 1, 1) - timedelta(days=1))
    return P.interval(start, end)


def _season(row: dict) -> str:
    return (row.get("meta") or {}).get("season") or row["ts"][:7]


def f_enso() -> dict:
    label = "El Nino (event strength)"
    roni = latest_obs("roni")
    oni_raw = latest_obs("oni")
    idx = roni or oni_raw  # official index first (RONI since 2026), ONI as fallback
    wk = latest_obs("nino34_weekly_anom")
    dy = latest_obs("nino34_daily_anom")
    cpc = _status("cpc_alert")
    iri = _status("iri_plume")
    if not idx and not wk:
        return missing("enso", label, "NOAA CPC", URLS["oni"],
                       why_no_data("cpc_%", "NOAA CPC"),
                       what="no RONI, ONI or weekly Nino 3.4 value stored")
    lv_idx = oni_level(idx["value"]) if idx else None
    lv_wk = oni_level(wk["value"]) if wk else None
    level = max(x for x in (lv_idx, lv_wk) if x is not None)
    # the headline value is the index that sets the level (ties: the official 3-month one)
    driver = wk if wk and (lv_idx is None or lv_wk > lv_idx) else idx
    inputs, parts = [], []
    wk_iv = None
    if wk:
        a, b = P.cpc_week(wk["ts"])
        wk_iv = interval(a, b)
        parts.append(f"Nino 3.4 weekly SST anomaly {fmt_val(wk['value'], 'degC', 1, True)} "
                     f"(week {fmt_period(a, b)} {b[:4]}, centred on {fmt_day(wk['ts'])}; "
                     "NOAA CPC OISST, observed, 1991-2020 base)")
        inputs.append(P.evidence("Nino 3.4 weekly anomaly", wk["value"], "degC", "observed",
                                 wk_iv, "NOAA CPC (OISST v2.1)", "https://www.cpc.ncep.noaa.gov/"
                                 "data/indices/wksst9120.for", decimals=1,
                                 retrieved=P.retrieved_at("cpc_weekly_sst"), tz=P.TZ_UTC))
    for row, name, src, url in ((roni, "RONI", "cpc_roni", URLS["oni"]),
                                (oni_raw, "ONI", "cpc_oni", ("https://origin.cpc.ncep.noaa.gov/"
                                 "products/analysis_monitoring/ensostuff/ONI_v5.php"))):
        if not row:
            continue
        a, b = P.season_interval(row["ts"])
        official = " (NOAA's official index since 2026)" if name == "RONI" else ""
        parts.append(f"{name}{official} {fmt_val(row['value'], 'degC', 2, True)} for "
                     f"{_season(row)} = {enso_strength(row['value'])} range")
        inputs.append(P.evidence(name, row["value"], "degC", "observed", interval(a, b),
                                 "NOAA CPC", url, decimals=2, retrieved=P.retrieved_at(src),
                                 tz=P.TZ_UTC, note=_season(row)))
    if dy:
        pre = (dy.get("meta") or {}).get("preliminary")
        parts.append(f"daily Nino 3.4 {fmt_val(dy['value'], 'degC', 2, True)} on "
                     f"{fmt_day(dy['ts'], True)} (OISST via Climate Reanalyzer"
                     f"{', preliminary' if pre else ''})")
        inputs.append(P.evidence("Nino 3.4 daily anomaly", dy["value"], "degC", "observed",
                                 dy["ts"][:10], "Climate Reanalyzer (NOAA OISST v2.1)",
                                 "https://climatereanalyzer.org/clim/sst_daily/", decimals=2,
                                 retrieved=P.retrieved_at("cr_nino34_daily"), tz=P.TZ_UTC,
                                 note="preliminary" if pre else None))
    if cpc and cpc.get("status"):
        nxt = f", next {fmt_short(cpc['next_issue'])}" if cpc.get("next_issue") else ""
        syn = f": {cpc['synopsis'].rstrip('.')}" if cpc.get("synopsis") else ""
        parts.append(f"NOAA CPC status {cpc['status']} (issued "
                     f"{fmt_short(cpc['issued']) if cpc.get('issued') else '?'}{nxt}){syn}")
        inputs.append(P.evidence("NOAA CPC ENSO alert status", cpc["status"], None, "bulletin",
                                 cpc.get("issued"), "NOAA CPC", URLS["cpc"],
                                 issued_at=cpc.get("issued"),
                                 retrieved=P.retrieved_at("cpc_discussion"), tz=P.TZ_UTC))
    iri_max = None
    if iri and isinstance(iri.get("probabilities"), list) and iri["probabilities"]:
        probs = [p for p in iri["probabilities"] if p.get("el_nino") is not None]
        if probs:
            iri_max = max(p["el_nino"] * 100 if p["el_nino"] <= 1 else p["el_nino"]
                          for p in probs)
            last = probs[-1]
            top = [p["season"] for p in probs if p["el_nino"] >= iri_max]
            span = f"{top[0]}-{top[-1]}" if len(top) > 1 else top[0]
            parts.append(f"IRI model forecast (issued {fmt_short(iri['issued'])}): El Nino "
                         f"{iri_max:.0f}% for {span}, {last['el_nino']:.0f}% by "
                         f"{last['season']}")
            inputs.append(P.evidence("IRI El Nino probability (max)", iri_max, "%", "forecast",
                                     seasons_interval([p["season"] for p in probs],
                                                      iri.get("issued")), "IRI (Columbia)",
                                     iri.get("url") or "", issued_at=iri.get("issued"),
                                     retrieved=P.retrieved_at("iri_plume"), tz=P.TZ_UTC))
    why = ("the weekly Nino 3.4" if driver is wk else _season(idx) + " " +
           ("RONI" if idx is roni else "ONI"))
    expl = ("; ".join(parts) + f". Level set by {why}. A strong El Nino usually means "
            "below-normal rain in Thailand and a hotter, longer dry season: for Samui the "
            "water risk window is February-April 2027. On its own this factor never goes "
            "above 'prepare': it is a warning sign, not a direct threat.")
    stale = bool(idx and (_now() - _parse_ts(idx["ts"])).days > 120)
    # short phrase for the headline
    bits = []
    if oni_raw:
        bits.append(f"ONI {fmt_val(oni_raw['value'], 'degC', 2, True)} {_season(oni_raw)}")
    if roni:
        bits.append(f"RONI {fmt_val(roni['value'], 'degC', 2, True)}")
    if wk:
        bits.append(f"Nino 3.4 {fmt_val(wk['value'], 'degC', 1, True)} week of "
                    f"{fmt_short(wk['ts'])}")
    strength = enso_strength(max(v["value"] for v in (roni, oni_raw) if v)) \
        if (roni or oni_raw) else "El Nino"
    phrase = f"{strength} ({'; '.join(bits)})"
    if driver is wk:
        valid, dec, vlab = wk_iv, 1, (f"{fmt_val(wk['value'], 'degC', 1, True)} (Nino 3.4, "
                                      f"week of {fmt_short(wk['ts'])})")
    else:
        a, b = P.season_interval(idx["ts"])
        valid, dec = interval(a, b), 2
        vlab = (f"{fmt_val(idx['value'], 'degC', 2, True)} "
                f"({'RONI' if idx is roni else 'ONI'} {_season(idx)})")
    return factor("enso", label, level, driver["value"], "degC",
                  "RONI/ONI or weekly Nino 3.4 >= +0.5 °C watch, >= +1.5 °C (strong) prepare",
                  expl, "NOAA CPC (RONI, ONI, Nino 3.4) + IRI", URLS["oni"],
                  driver["ts"], stale=stale, kind="observed", valid_for=valid,
                  retrieved=P.retrieved_at("cpc_weekly_sst" if driver is wk else
                                           ("cpc_roni" if idx is roni else "cpc_oni")),
                  tz=P.TZ_UTC, decimals=dec, value_label=vlab, summary=phrase,
                  inputs=inputs,
                  details={"roni": roni and roni["value"], "oni": oni_raw and oni_raw["value"],
                           "index_ts": idx and idx["ts"], "index_season": idx and _season(idx),
                           "nino34_weekly": wk and wk["value"], "nino34_ts": wk and wk["ts"],
                           "nino34_daily": dy and dy["value"], "nino34_daily_ts": dy and dy["ts"],
                           "cpc_status": cpc and cpc.get("status"),
                           "cpc_issued": cpc and cpc.get("issued"),
                           "iri_el_nino_max_pct": iri_max, "driver": "nino34_weekly"
                           if driver is wk else ("roni" if idx is roni else "oni"),
                           "phrase": phrase},
                  steps={0: "RONI/ONI >= +0.5 °C (El Nino)",
                         1: "RONI/ONI or weekly Nino 3.4 >= +1.5 °C (strong El Nino)"})


# --------------------------------------------------------------------------- water

ERA5_SRC, ERA5_SERIES = "openmeteo_samui_era5", "samui_era5_precip"
MODEL_SRC, MODEL_SERIES = "openmeteo_samui", "samui_precip"


def rain_windows(clim: dict, end: date | None = None, series: str = ERA5_SERIES,
                 source: str = ERA5_SRC) -> dict | None:
    """Rain over 30/60/90/180 days ending at `end` (default: the source's last day; for
    the model fallback: yesterday, ICT), vs the 1991-2020 ERA5 normal for the same
    calendar days. Each window carries its start/end dates."""
    if not clim or not clim.get("days"):
        return None
    if end is None:
        if source == MODEL_SRC:
            end = today_bkk() - timedelta(days=1)
        else:
            last = latest_obs(series, source)
            if not last:
                return None
            end = date.fromisoformat(last["ts"][:10])
    out = {"end": end.isoformat(), "series": series, "source": source,
           "kind": "model_analysis" if source == MODEL_SRC else "reanalysis"}
    for n in (30, 60, 90, 180):
        start = end - timedelta(days=n - 1)
        pts = _points(series, start.isoformat(), (end + timedelta(days=1)).isoformat(), source)
        if len(pts) < n * 0.9:
            out[f"d{n}"] = None
            continue
        obs = sum(p["value"] for p in pts)
        normal = 0.0
        for i in range(n):
            k = (start + timedelta(days=i)).strftime("%m-%d")
            normal += clim["days"].get("02-28" if k == "02-29" else k, [0])[0]
        out[f"d{n}"] = {"obs_mm": round(obs, 1), "normal_mm": round(normal, 1),
                        "pct": round(100 * obs / normal) if normal > 0 else None,
                        "start": start.isoformat(), "end": end.isoformat(), "days": len(pts)}
    return out


def rain_deficit_level(pct90: float | None) -> int | None:
    """90-day rain as % of the 1991-2020 normal. Basis: the WMO/TMD practice of
    reading rain < 80% of normal as 'below normal'; tighter bands because an
    island with small reservoirs feels a long deficit quickly (Samui rationing in
    2016 and from 3 Aug 2026 followed long dry spells).
      >= 75%: 0 ; 60-75%: 1 ; 40-60%: 2 ; < 40%: 3"""
    if pct90 is None:
        return None
    if pct90 < 40:
        return 3
    if pct90 < 60:
        return 2
    if pct90 < 75:
        return 1
    return 0


def water_season(m: int) -> str:
    """Samui's water year (ERA5 1991-2020 normals at the home grid cell: Oct 282 mm,
    Nov 284 mm, Dec 148 mm = ~47% of the ~1530 mm year; Feb only 39 mm):
      refill (Oct-Dec)  NE monsoon: the reservoirs and aquifer fill NOW or not at all;
                        a deficit is the key PREDICTOR of the next dry season.
      dry    (Jan-May)  consumption season; with El Nino, February-April 2027 is the
                        danger window: a deficit has direct CONSEQUENCES (rationing).
      sw     (Jun-Sep)  SW monsoon: Samui is sheltered, rain is modest and matters less."""
    if m in (10, 11, 12):
        return "refill"
    if m in (1, 2, 3, 4, 5):
        return "dry"
    return "sw"


# a rain-only level 3 ("act") needs a real volume missing, not a percentage of a tiny
# dry-season normal (40% of 60 mm is 36 mm short: not an emergency by itself)
MIN_DEFICIT_MM_FOR_ACT = 100
PWA_LONG_H = 48  # a notice lasting longer than this = a supply problem, not a repair
ERA5_MAX_LAG_DAYS = 10


def pwa_supply(now: datetime | None = None) -> dict:
    """Active PWA Ko Samui notices (collector `pwa_samui_notices`)."""
    s = db.get_status("pwa_samui_notices")
    fresh = not _stale("pwa_samui_notices", 12 * 3600)
    if not s:
        return {"known": False, "fresh": False, "active": [], "long": []}
    now = now or _now()
    active = []
    for it in s["value"].get("items", []):
        if it.get("status") in ("done", "cancelled"):
            continue
        end = _parse_ts(it["end"]) if it.get("end") else None
        start = _parse_ts(it["start"]) if it.get("start") else None
        if end and end < now:
            continue
        if start and start > now + timedelta(days=2):
            continue
        hours = (end - start).total_seconds() / 3600 if (end and start) else None
        active.append(it | {"hours": hours})
    long_ = [a for a in active if a["kind"] == "no_supply" or (a["hours"] or 0) > PWA_LONG_H]
    return {"known": True, "fresh": fresh, "active": active, "long": long_,
            "fetched_at": s["value"].get("fetched_at")}


def _win_txt(w: dict, n: int) -> str:
    return (f"{n} d ({fmt_period(w['start'], w['end'])}): {w['obs_mm']:,.0f} mm = {w['pct']}% "
            f"of normal ({w['normal_mm']:,.0f} mm)")


def f_water(enso_level: int | None, news_water_samui: int) -> dict:
    label = "Rain deficit / water shortage"
    clim = _status("samui_climatology")
    steps = {0: "90-day rain < 75% of normal or a PWA Samui notice",
             1: "90-day rain < 60% of normal or a PWA notice > 48 h",
             2: "90-day rain < 40% of normal (>= 100 mm short)",
             3: "shortage confirmed on the island"}
    win = rain_windows(clim) if clim else None
    fallback_note = None
    era5_ok = bool(win and win.get("d90")) and (
        today_bkk() - date.fromisoformat(win["end"])).days <= ERA5_MAX_LAG_DAYS \
        and not _stale(ERA5_SRC, 3 * 86400)
    if not era5_ok and clim:
        alt = rain_windows(clim, series=MODEL_SERIES, source=MODEL_SRC)
        if alt and alt.get("d90") and not _stale(MODEL_SRC, 36 * 3600):
            fallback_note = ("ERA5 reanalysis unavailable (" + why_no_data(ERA5_SRC, "ERA5")
                             + "): using Open-Meteo's past-day model analyses instead, against "
                             "the same ERA5 normal. Model analyses usually run WETTER than "
                             "ERA5 at this cell, so a deficit is if anything understated.")
            win = alt
    if not win or not win.get("d90"):
        why = ("the 1991-2020 ERA5 normal has not been computed yet"
               if not clim else why_no_data(ERA5_SRC, "the ERA5 archive"))
        return missing("water", label, "Open-Meteo ERA5", URLS["era5"], why, steps=steps,
                       what="90-day rain total vs the 1991-2020 normal (ERA5 and the "
                            "model-analysis fallback are both missing)")
    kind = win["kind"]
    src_name = ("ERA5 reanalysis" if kind == "reanalysis"
                else "Open-Meteo model analyses (fallback)")
    today = today_bkk()
    season = water_season(today.month)
    d90, d180 = win["d90"], win.get("d180")
    pct90 = d90["pct"]
    pct60 = (win.get("d60") or {}).get("pct")
    pct180 = d180["pct"] if d180 else None
    drive, basis = d90, "90 d"
    if season == "dry" and d180 and pct180 is not None and pct180 < pct90:
        drive, basis = d180, "180 d"
    level = rain_deficit_level(drive["pct"])
    deficit_mm = round(drive["normal_mm"] - drive["obs_mm"], 1)
    reasons = [f"{src_name}, rain on the home grid cell: " + "; ".join(
        _win_txt(win[f"d{n}"], n) for n in (90, 30, 60, 180) if win.get(f"d{n}"))]
    if basis != "90 d":
        reasons.append(f"the 180-day window (it holds the last monsoon refill) drives the "
                       f"level: {pct180}% of normal, {deficit_mm:,.0f} mm short")
    if level == 3 and deficit_mm < MIN_DEFICIT_MM_FOR_ACT:
        level = 2
        reasons.append(f"only {deficit_mm:,.0f} mm short in absolute terms: rain alone "
                       "stays at 'prepare'")
    if pct60 is not None and pct60 < 50 and level < 1:
        level = 1
        reasons.append(f"60 days at only {pct60}% of normal")
    if pct180 is not None and pct180 < 75 and level < 1:
        level = 1
    strong = enso_level is not None and enso_level >= 2
    if season == "refill" and strong and pct90 < 75 and level < 2:
        level = 2
        reasons.append("rain short during the October-December refill season with a strong "
                       "El Nino: the reservoirs will not fill before the 2027 dry season")
    if strong and season == "dry":
        floor = 2 if drive["pct"] < 75 else 1
        if level < floor:
            level = floor
            reasons.append("dry season during a strong El Nino (February-April is the "
                           "critical water window on Samui)")
    inputs = [P.evidence(f"rain {n} d, % of 1991-2020 normal", win[f"d{n}"]["pct"], "%", kind,
                         interval(win[f"d{n}"]["start"], win[f"d{n}"]["end"]), src_name,
                         URLS["era5"], retrieved=P.retrieved_at(win["source"]),
                         note=f"{win[f'd{n}']['obs_mm']} mm vs {win[f'd{n}']['normal_mm']} mm")
              for n in (30, 60, 90, 180) if win.get(f"d{n}")]
    seas = _status("samui_seasonal")
    seas_pct, seas_months = None, []
    if seas and seas.get("months"):
        cur = today.strftime("%Y-%m")
        nxt = [m for m in seas["months"] if m["month"] > cur][:3]
        seas_months = [m for m in nxt if m.get("precip_pct_of_model_normal") is not None]
        if seas_months:
            seas_pct = round(sum(m["precip_pct_of_model_normal"] for m in seas_months)
                             / len(seas_months))
            months_txt = ", ".join(
                f"{date.fromisoformat(m['month'] + '-01'):%b} "
                f"{m['precip_pct_of_model_normal']:.0f}%" for m in seas_months)
            reasons.append(f"ECMWF SEAS5 seasonal forecast (fetched "
                           f"{fmt_ict(seas.get('fetched_at')) or '?'}): next 3 months "
                           f"{seas_pct}% of the model normal ({months_txt})")
            inputs.append(P.evidence("SEAS5 rain, next 3 months, % of model normal", seas_pct,
                                     "%", "forecast", interval(seas_months[0]["month"] + "-01",
                                                               seas_months[-1]["month"] + "-28"),
                                     "ECMWF SEAS5 via Open-Meteo", seas.get("url") or "",
                                     retrieved=seas.get("fetched_at")))
            if seas_pct < 80 and level < 1:
                level = 1
    dam = latest_obs("surat_ratchaprapa_storage_pct", "thaiwater_dams")
    if dam:
        dtxt = (f"Ratchaprapa dam (mainland Surat Thani, regional indicator only, it does not "
                f"feed the island): {dam['value']:.1f}% full on {fmt_day(dam['ts'])} "
                "(RID via ThaiWater, reported)")
        reasons.append(dtxt)
        inputs.append(P.evidence("Ratchaprapa dam storage", dam["value"], "%", "observed",
                                 dam["ts"][:10], "RID via ThaiWater", URLS["thaiwater"],
                                 decimals=1, retrieved=P.retrieved_at("thaiwater_dams")))
        if dam["value"] < 25 and level < 2:
            level = 2
        elif dam["value"] < 40 and level < 1:
            level = 1
    pwa = pwa_supply()
    if pwa["active"]:
        a = pwa["active"][0]
        when = ""
        if a.get("start") or a.get("end"):
            when = f", {fmt_ict(a.get('start')) or '?'} to {fmt_ict(a.get('end')) or '?'}"
        reasons.append(f"PWA Ko Samui notice in force: {a['kind_label']}{when} "
                       f"({len(pwa['active'])} active)")
        level = max(level, 2 if pwa["long"] else 1)
    elif pwa["known"] and pwa["fresh"]:
        reasons.append(f"no PWA Ko Samui interruption notice in force (list checked "
                       f"{fmt_ict(pwa.get('fetched_at')) or '?'})")
    else:
        reasons.append("PWA Ko Samui notices: " + why_no_data("pwa_samui_notices",
                                                              "the PWA notice API"))
    inputs.append(P.evidence("PWA Ko Samui notices in force", len(pwa["active"]), "count",
                             "bulletin", None, "PWA", URLS["pwa"],
                             retrieved=pwa.get("fetched_at")))
    if level >= 3 and (news_water_samui >= 2 or pwa["long"]):
        level = 4
        reasons.append("shortage confirmed (Samui news reports or a long PWA notice)")
    season_txt = {
        "refill": ("October-December is when Samui's reservoirs refill (about half of the "
                   "year's rain): a deficit now is the strongest warning for the 2027 dry "
                   "season."),
        "dry": ("Dry season: the water stored during the last monsoon is being used up; "
                "with El Nino, February-April 2027 is the danger window."),
        "sw": ("Southwest monsoon (June-September): Samui is sheltered and rain is modest; "
               "the refill season starts in October."),
    }[season]
    expl = ("; ".join(reasons) + f". {season_txt} Samui relies on small reservoirs, "
            "desalination plants and an undersea pipeline from the mainland (~16,000 m³/day "
            "for ~34,000 m³/day of demand, per the PWA). In late July 2026 the El Nino "
            "drought cut supply and the PWA announced rotating supply by zone from "
            "3 August 2026 (Bangkok Post, 29 Jul 2026). Not published in any machine-readable "
            "form (checked 24 Sep 2026): the levels of the island's own reservoirs and the "
            f"PWA rotation schedule. Check them by hand: {_manual('water')}.")
    if fallback_note:
        expl = f"{fallback_note} {expl}"
    ended = _parse_ts(win["end"])
    stale = (_now() - ended).days > ERA5_MAX_LAG_DAYS if kind == "reanalysis" else \
        _stale(MODEL_SRC, 36 * 3600)
    if kind == "reanalysis":
        stale = stale or _stale(ERA5_SRC, 3 * 86400)
    period = fmt_period(d90["start"], d90["end"])
    summary = f"rain {pct90}% of normal (90 d to {fmt_short(d90['end'])})"
    return factor(
        "water", label, level, pct90, "%",
        "90 d (180 d in the dry season) < 75% watch, < 60% prepare, < 40% and >= 100 mm "
        "short act; PWA notice watch, > 48 h prepare; + confirmed shortage = 4",
        expl, f"Open-Meteo {'ERA5' if kind == 'reanalysis' else 'model analyses'} vs "
        "1991-2020 ERA5 normal, ECMWF SEAS5, PWA, ThaiWater", URLS["era5"],
        win["end"], stale=stale, kind=kind, valid_for=interval(d90["start"], d90["end"]),
        retrieved=P.retrieved_at(win["source"]), unit_text="% of 1991-2020 normal (90 d)",
        value_label=f"{pct90}% of normal ({period}: {d90['obs_mm']:,.0f} mm vs "
                    f"{d90['normal_mm']:,.0f} mm normal)",
        summary=summary, inputs=inputs,
        details={"windows": win, "season": season, "driving_window": basis,
                 "deficit_mm": deficit_mm, "seasonal_next3_pct": seas_pct,
                 "ratchaprapa_pct": dam and dam["value"], "ratchaprapa_date": dam and dam["ts"],
                 "news_water_samui_14d": news_water_samui,
                 "pwa_notices_active": [{k: a.get(k) for k in ("kind_label", "start", "end",
                                                                "url", "area_th")}
                                        for a in pwa["active"]][:5],
                 "pwa_fetched_at": pwa.get("fetched_at"),
                 "context_url": SAMUI_RATIONING_2026_URL, "fallback": bool(fallback_note),
                 "not_tracked": ["Samui reservoir levels", "PWA Samui rotation schedule"],
                 "manual_check": [{"title": t, "url": u} for t, u in MANUAL["water"]]},
        steps=steps)


# --------------------------------------------------------------------------- heat

def heat_level(max_app: float, danger_days: int) -> int:
    """Apparent temperature bands of the NWS heat index, also used by the Thai
    Meteorological Department / Department of Health heat warnings:
    27-32 caution, 32-41 extreme caution, 41-54 danger, >= 54 extreme danger.
    On Samui 32-38 is an ordinary day, so:
      < 39: 0 ; 39-41: 1 ; >= 41 on 1-2 days: 2 ; >= 41 on 3+ days: 3 ; >= 54: 4"""
    if max_app >= 54:
        return 4
    if max_app >= 41:
        return 3 if danger_days >= 3 else 2
    if max_app >= 39:
        return 1
    return 0


def f_heat() -> dict:
    label = "Extreme heat"
    today = today_bkk()
    pts = _points("samui_apparent_temp_max", today.isoformat(),
                  (today + timedelta(days=7)).isoformat(), "openmeteo_samui")
    if not pts:
        return missing("heat", label, "Open-Meteo", URLS["forecast"],
                       why_no_data("openmeteo_samui", "the Open-Meteo forecast"),
                       what="7-day forecast of the maximum feels-like temperature")
    mx = max(pts, key=lambda p: p["value"])
    danger_days = sum(1 for p in pts if p["value"] >= 41)
    level = heat_level(mx["value"], danger_days)
    got = P.retrieved_at("openmeteo_samui")
    first, last = pts[0]["ts"][:10], pts[-1]["ts"][:10]
    reasons = [(f"Forecast max feels-like {fmt_val(mx['value'], 'degC', 1)} on "
                f"{fmt_day(mx['ts'])} (Open-Meteo, fetched {fmt_ict(got) or '?'}); "
                f"{danger_days} of the {len(pts)} days {fmt_period(first, last)} reach 41 °C")]
    inputs = [P.evidence("max feels-like temperature, next 7 days", mx["value"], "degC",
                         "forecast", mx["ts"][:10], "Open-Meteo", URLS["forecast"],
                         retrieved=got, decimals=1,
                         note=f"window {interval(first, last)}")]
    anom = None
    clim = _status("samui_climatology")
    if clim:
        start = today - timedelta(days=37)
        era = _points("samui_era5_temp_max", start.isoformat(), None, ERA5_SRC)[-30:]
        diffs = [p["value"] - clim["days"][p["ts"][5:10] if p["ts"][5:10] != "02-29" else
                                          "02-28"][1] for p in era]
        if len(diffs) >= 20:
            anom = round(sum(diffs) / len(diffs), 1)
            a, b = era[0]["ts"][:10], era[-1]["ts"][:10]
            reasons.append(f"ERA5 reanalysis: daily max temperature over {fmt_period(a, b)} "
                           f"averaged {fmt_val(anom, 'degC', 1, True)} vs 1991-2020")
            inputs.append(P.evidence("Tmax anomaly, last 30 ERA5 days", anom, "degC",
                                     "reanalysis", interval(a, b), "ERA5 via Open-Meteo",
                                     URLS["era5"], retrieved=P.retrieved_at(ERA5_SRC),
                                     decimals=1))
            if anom >= 2.5 and level < 2:
                level = 2
            elif anom >= 1.5 and level < 1:
                level = 1
    expl = ("; ".join(reasons) + ". Above 41 °C feels-like (the 'danger' threshold), "
            "heatstroke is possible, especially for children, older people and during "
            "exertion. Power cuts (no air conditioning) make it worse. El Nino makes "
            "March-May 2027 likely hotter than normal.")
    return factor("heat", label, level, mx["value"], "degC",
                  ">= 39 °C watch, >= 41 °C (danger) prepare, 3 days >= 41 °C act, "
                  ">= 54 °C leave; or 30-day Tmax >= +1.5 / +2.5 °C", expl,
                  "Open-Meteo (forecast) + ERA5", URLS["forecast"], None,
                  stale=_stale("openmeteo_samui", 36 * 3600), kind="forecast",
                  valid_for=mx["ts"][:10], retrieved=got, decimals=1,
                  unit_text="°C feels-like (forecast max)",
                  value_label=(f"{fmt_val(mx['value'], 'degC', 1)} feels-like, forecast for "
                               f"{fmt_day(mx['ts'])}"),
                  summary=f"feels-like max {fmt_val(mx['value'], 'degC', 1)} (forecast "
                          f"{fmt_day(mx['ts'])})",
                  inputs=inputs,
                  details={"danger_days_7d": danger_days, "tmax_anom_30d": anom,
                           "forecast_window": interval(first, last)},
                  steps={0: "feels-like >= 39 °C", 1: "feels-like >= 41 °C",
                         2: "3 days >= 41 °C", 3: "feels-like >= 54 °C or water shortage"})


# --------------------------------------------------------------------------- flood

def rain_level(max24: float, sum72: float) -> int:
    """TMD 24 h rain classes: 10.1-35 moderate, 35.1-90 heavy, > 90 very heavy.
      max 24 h < 35.1 and 72 h < 100: 0 ; heavy (35.1-90) or 72 h >= 100: 1 ;
      very heavy (> 90) or 72 h >= 150: 2 ; 24 h >= 150 or 72 h >= 250: 3.
    (Southern Thailand floods, e.g. Jan 2017, came with multi-day totals of
    several hundred mm.) Capped at 3."""
    if max24 >= 150 or sum72 >= 250:
        return 3
    if max24 > 90 or sum72 >= 150:
        return 2
    if max24 > 35 or sum72 >= 100:
        return 1
    return 0


# Antecedent 7-day rain. ERA5 normal for a November week at the home cell is ~65 mm;
# forecast-model analyses run higher than ERA5, so 150 mm (~2x) = saturated ground.
ANTE7_SATURATED_MM = 150
ANTE7_VERY_WET_MM = 250


def _tmd_active(filter_fn) -> list[dict]:
    tmd = _status("tmd_warnings")
    if not tmd:
        return []
    today = today_bkk().isoformat()
    return [it for it in tmd.get("items", [])
            if it.get("until") and it["until"] >= today and it.get("affects_samui")
            and filter_fn(it)]


def tmd_text(it: dict) -> str:
    return it.get("summary_en") or tmd_summary_en(it)


def f_flood() -> dict:
    label = "Heavy rain / flooding"
    today = today_bkk()
    pts = _points("samui_precip", today.isoformat(), (today + timedelta(days=3)).isoformat(),
                  "openmeteo_samui")
    fc_ok = bool(pts) and not _stale("openmeteo_samui", 36 * 3600)
    gauge = latest_obs("samui_gauge_rain_24h", "thaiwater_samui_rain")
    gauge_fresh = bool(gauge and (_now() - _parse_ts(gauge["ts"])).total_seconds() < 6 * 3600)
    warns = _tmd_active(lambda it: it.get("heavy_rain"))
    tmd_fresh = not _stale("tmd_warnings", 6 * 3600)
    if not pts and not gauge_fresh and not (warns and tmd_fresh):
        return missing("flood", label, "Open-Meteo / ThaiWater / TMD", URLS["forecast"],
                       why_no_data("openmeteo_samui", "the Open-Meteo forecast") + "; "
                       + why_no_data("thaiwater_samui_rain", "the ThaiWater island gauges"),
                       what="3-day rain forecast and island rain-gauge readings")
    level = 0
    reasons, inputs = [], []
    max24 = sum72 = None
    got = P.retrieved_at("openmeteo_samui")
    mxp = None
    if pts:
        mxp = max(pts, key=lambda p: p["value"])
        max24 = mxp["value"]
        sum72 = round(sum(p["value"] for p in pts), 1)
        level = rain_level(max24, sum72)
        a, b = pts[0]["ts"][:10], pts[-1]["ts"][:10]
        reasons.append(f"Forecast rain {fmt_period(a, b)}: {sum72:,.0f} mm in total, wettest "
                       f"day {fmt_day(mxp['ts'])} {max24:,.0f} mm (Open-Meteo, fetched "
                       f"{fmt_ict(got) or '?'}; today's total includes hours still ahead)")
        inputs += [P.evidence("wettest day, next 3 days", max24, "mm", "forecast",
                              mxp["ts"][:10], "Open-Meteo", URLS["forecast"], retrieved=got),
                   P.evidence("rain total, next 3 days", sum72, "mm", "forecast",
                              interval(a, b), "Open-Meteo", URLS["forecast"], retrieved=got)]
    if gauge:
        g = gauge["value"]
        st = (gauge.get("meta") or {}).get("stations") or []
        wet = max(st, key=lambda s: s["rain_24h"]) if st else None
        where = f", {wet['name']}" if wet and g > 0 else ""
        if gauge_fresh:
            reasons.append(f"ThaiWater rain gauges ({len(st)} on Ko Samui, observed): max "
                           f"{g:,.0f} mm in the 24 h to {fmt_ict(gauge['ts'])}{where}")
            level = max(level, rain_level(g, 0))
        else:
            reasons.append(f"ThaiWater island gauges: last reading {fmt_ict(gauge['ts'])}, "
                           "too old to use (> 6 h)")
        inputs.append(P.evidence("island gauges, max 24 h rain", g, "mm", "observed",
                                 gauge["ts"], "ThaiWater (HII / TMD gauges)",
                                 URLS["thaiwater"], retrieved=P.retrieved_at(
                                     "thaiwater_samui_rain")))
    if warns:
        w = warns[0]
        reasons.append(f"{tmd_text(w)} (in force until {fmt_day(w['until'])}; it names the "
                       "South, Samui is on the Gulf side)")
        level = max(level, 1)
        inputs.append(P.evidence("TMD heavy-rain bulletin", w["issue"], None, "bulletin",
                                 interval(w.get("from") or w["until"], w["until"]), "TMD",
                                 URLS["tmd_warn"], retrieved=P.retrieved_at("tmd_warnings")))
    elif tmd_fresh:
        reasons.append("no TMD heavy-rain bulletin covering the South / Gulf in force")
    past = _points("samui_precip", (today - timedelta(days=7)).isoformat(),
                   today.isoformat(), "openmeteo_samui")
    ante7 = round(sum(p["value"] for p in past), 1) if len(past) >= 6 else None
    if ante7 is not None:
        a, b = past[0]["ts"][:10], past[-1]["ts"][:10]
        reasons.append(f"past 7 days ({fmt_period(a, b)}, model analyses, not gauges): "
                       f"{ante7:,.0f} mm")
        inputs.append(P.evidence("rain, past 7 days", ante7, "mm", "model_analysis",
                                 interval(a, b), "Open-Meteo", URLS["forecast"], retrieved=got))
        if ante7 >= ANTE7_SATURATED_MM and 1 <= level < 3:
            level += 1
            reasons.append("heavy rain forecast on saturated ground: raised one level")
        elif ante7 >= ANTE7_VERY_WET_MM and level < 1:
            level = 1
            reasons.append("ground saturated (landslides, slow drainage)")
    m = today.month
    monsoon = m in (10, 11, 12, 1)
    season = ("October-January is the northeast monsoon rainy season on Samui (November is "
              "the wettest month): the heaviest rain and floods of the year. El Nino does "
              "not prevent floods." if monsoon else
              "Reminder: the northeast monsoon (October-December) brings Samui's heaviest "
              "rain, even during an El Nino.")
    expl = "; ".join(reasons) + f". {season} Coastal and Lamai/Chaweng roads can flood, "\
        "landslides are possible on slopes."
    if pts and (fc_ok or not gauge_fresh):
        value, unit, kind, valid, vlab = (max24, "mm", "forecast", mxp["ts"][:10],
                                          (f"{max24:,.0f} mm on {fmt_day(mxp['ts'])} (forecast "
                                          f"wettest day; {sum72:,.0f} mm over 3 days)"))
        summary = f"forecast {sum72:,.0f} mm over 3 days"
    elif gauge_fresh:
        value, unit, kind, valid, vlab = (gauge["value"], "mm", "observed", gauge["ts"],
                                          (f"{gauge['value']:,.0f} mm in 24 h (island gauges, "
                                          f"to {fmt_ict(gauge['ts'])})"))
        summary = f"gauges {gauge['value']:,.0f} mm in 24 h"
    else:
        w = warns[0]
        value, unit, kind, valid, vlab = (w["issue"], None, "bulletin", interval(
            w.get("from") or w["until"], w["until"]), tmd_text(w))
        summary = "TMD heavy-rain bulletin in force"
    if warns:
        summary = (f"TMD heavy-rain bulletin {warns[0]['issue']} for the South, in force to "
                   f"{fmt_day(warns[0]['until'])} ({summary})")
    return factor("flood", label, level, value, unit,
                  "TMD: 35.1-90 mm heavy, > 90 mm very heavy in 24 h; 72 h >= 100/150/250 mm; "
                  f"+1 level if the past 7 days >= {ANTE7_SATURATED_MM} mm", expl,
                  "Open-Meteo, ThaiWater (HII/TMD), TMD", URLS["forecast"],
                  gauge["ts"] if (kind == "observed") else None,
                  stale=bool(pts) and not fc_ok and not gauge_fresh, kind=kind,
                  valid_for=valid, retrieved=got if kind == "forecast" else
                  P.retrieved_at("thaiwater_samui_rain"),
                  unit_text="mm in 24 h" if unit else None, value_label=vlab, summary=summary,
                  inputs=inputs,
                  details={"sum72_mm": sum72, "gauge_max_24h": gauge and gauge["value"],
                           "gauge_ts": gauge and gauge["ts"], "gauge_fresh": gauge_fresh,
                           "past7_mm": ante7, "ne_monsoon": monsoon,
                           "tmd_active": [w["issue"] for w in warns][:3],
                           "tmd_active_en": [tmd_text(w) for w in warns][:3]},
                  steps={0: "> 35 mm in 24 h or 100 mm in 72 h", 1: "> 90 mm in 24 h or 150 mm "
                         "in 72 h", 2: ">= 150 mm in 24 h or 250 mm in 72 h"})


# --------------------------------------------------------------------------- cyclone / wind

def gust_level(g: float) -> int:
    """Beaufort scale applied to forecast gusts (km/h): Samui often sees 55-70 km/h
    gusts in the monsoons, so vigilance starts at strong gale.
      < 75: 0 ; 75-88 (force 9): 1 ; 89-117 (force 10-11): 2 ; >= 118 (force 12): 3"""
    if g >= 118:
        return 3
    if g >= 89:
        return 2
    if g >= 75:
        return 1
    return 0


def cyclone_level(events: list[dict]) -> tuple[int, dict | None]:
    """GDACS tropical cyclones by distance of the reported position to home:
      orange/red <= 300 km: 4 ; any <= 300 km: 3 ; orange/red <= 800 km: 2 ;
      any <= home_radius_km (800): 1"""
    best, worst = 0, None
    for e in events:
        d = e["distance_km"]
        sev = (e.get("severity") or "").lower()
        big = sev in ("orange", "red")
        lv = 0
        if d <= 300:
            lv = 4 if big else 3
        elif d <= 800 and big:
            lv = 2
        elif d <= settings.home_radius_km:
            lv = 1
        if lv > best or (lv == best and worst and d < worst["distance_km"]):
            best, worst = lv, e
    return best, worst


SOURCE_NAMES = {"gdacs": "GDACS", "jtwc_warnings": "JTWC", "jma_typhoons": "JMA",
                "eonet": "NASA EONET"}
SOURCE_RANK = {"gdacs": 0, "jma_typhoons": 1, "jtwc_warnings": 2, "eonet": 3}


def _src_name(s: str) -> str:
    return SOURCE_NAMES.get(s, s)


def f_cyclone_wind() -> dict:
    label = "Tropical cyclone / wind"
    today = today_bkk()
    gdacs_ok = not _stale("gdacs%", 3 * 3600)
    tmd_ok = not _stale("tmd_warnings", 6 * 3600)
    evs = []
    for e in db.query("SELECT source, ext_id, title, url, severity, lat, lon, updated_at, "
                      "started_at FROM events WHERE category='cyclone' AND lat IS NOT NULL"):
        e["distance_km"] = round(haversine_km(settings.home_lat, settings.home_lon,
                                              e["lat"], e["lon"]))
        evs.append(e)
    # nearest first; at the same position prefer the official alert system (GDACS)
    evs.sort(key=lambda e: (e["distance_km"], SOURCE_RANK.get(e["source"], 9)))
    cyc_lv, worst = cyclone_level(evs)
    gusts = _points("samui_wind_gust_max", today.isoformat(),
                    (today + timedelta(days=3)).isoformat(), "openmeteo_samui")
    storms = _tmd_active(lambda it: it.get("storm"))
    radius = settings.home_radius_km
    got = P.retrieved_at("openmeteo_samui")
    if not gdacs_ok and not tmd_ok and not evs:
        f = missing("cyclone_wind", label, "GDACS / TMD", URLS["gdacs"],
                    why_no_data("gdacs", "GDACS") + "; " + why_no_data("tmd_warnings", "TMD"),
                    what="the cyclone lists of GDACS and the TMD (a cyclone cannot be ruled "
                         "out)")
        if gusts:
            f["details"]["gust_max_72h"] = max(p["value"] for p in gusts)
        return f
    level = cyc_lv
    reasons, inputs = [], []
    nearest = evs[0] if evs else None
    if worst:
        reasons.append(f"{worst['title'] or 'Tropical cyclone'} ({worst.get('severity')} "
                       f"alert, {_src_name(worst['source'])}) {worst['distance_km']:,} km away, "
                       f"position of {fmt_ict(worst.get('updated_at')) or '?'}")
    elif gdacs_ok:
        near = (f"; nearest: {nearest['title']} ({nearest.get('severity')}, "
                f"{_src_name(nearest['source'])}), {nearest['distance_km']:,} km away"
                if nearest else "; no active tropical cyclone listed anywhere")
        reasons.append(f"No tropical cyclone within {radius:,.0f} km (GDACS checked "
                       f"{fmt_ict(P.retrieved_at('gdacs')) or '?'}){near}")
    else:
        reasons.append("GDACS not fetched recently (" + why_no_data("gdacs", "GDACS")
                       + "): using the stored cyclone positions and TMD bulletins")
    if nearest:
        inputs.append(P.evidence("nearest tropical cyclone", nearest["distance_km"], "km",
                                 "bulletin", (nearest.get("updated_at") or "")[:10] or None,
                                 _src_name(nearest["source"]), nearest.get("url") or URLS["gdacs"],
                                 issued_at=nearest.get("updated_at"),
                                 retrieved=P.retrieved_at(nearest["source"]),
                                 note=f"{nearest['title']} ({nearest.get('severity')})",
                                 tz=P.TZ_UTC))
    gmax = gp = None
    if gusts:
        gp = max(gusts, key=lambda p: p["value"])
        gmax = gp["value"]
        a, b = gusts[0]["ts"][:10], gusts[-1]["ts"][:10]
        reasons.append(f"forecast max gust {gmax:,.0f} km/h on {fmt_day(gp['ts'])} "
                       f"(Open-Meteo, {fmt_period(a, b)})")
        inputs.append(P.evidence("max gust, next 3 days", gmax, "km/h", "forecast",
                                 gp["ts"][:10], "Open-Meteo", URLS["forecast"], retrieved=got))
        level = max(level, gust_level(gmax))
    if storms:
        reasons.append(f"{tmd_text(storms[0])} (TMD storm warning)")
        level = max(level, 2)
    expl = ("; ".join(reasons) + ". Cyclones are rare on Samui but destructive "
            "(tropical storm Harriet 1962, typhoon Gay 1989, storm Pabuk January 2019). "
            "They mostly arrive from October to January through the Gulf of Thailand.")
    if worst:
        value, unit, kind, valid = worst["distance_km"], "km", "bulletin", \
            (worst.get("updated_at") or "")[:10] or None
        vlab = f"{worst['distance_km']:,} km ({worst['title']}, {worst.get('severity')})"
        summary = f"{worst['title']} {worst['distance_km']:,} km away"
    else:
        value, unit, kind = gmax, "km/h", "forecast"
        valid = gp["ts"][:10] if gp else None
        vlab = (f"{gmax:,.0f} km/h max gust, forecast for {fmt_day(gp['ts'])}; no cyclone "
                f"within {radius:,.0f} km") if gp else f"no cyclone within {radius:,.0f} km"
        summary = f"no cyclone within {radius:,.0f} km" + (
            f" (nearest {nearest['distance_km']:,} km)" if nearest else "")
    return factor("cyclone_wind", label, level, value, unit,
                  "cyclone <= 800 km watch, orange/red <= 800 km prepare, <= 300 km"
                  " act, orange/red <= 300 km leave; gusts >= 75/89/118 km/h", expl,
                  "GDACS, JTWC/JMA/EONET positions, Open-Meteo, TMD",
                  (worst or {}).get("url") or URLS["gdacs"],
                  None, stale=not gdacs_ok and not tmd_ok, kind=kind, valid_for=valid,
                  issued_at=(worst or {}).get("updated_at"),
                  retrieved=P.retrieved_at("gdacs") if worst else got,
                  value_label=vlab, summary=summary, inputs=inputs,
                  tz=P.TZ_UTC if worst else P.TZ_LOCAL,
                  details={"cyclones": evs[:5], "nearest": nearest,
                           "gust_max_72h": gmax, "gdacs_fresh": gdacs_ok,
                           "tmd_storm_warnings": [s["issue"] for s in storms],
                           "partial": not gdacs_ok},
                  steps={0: "cyclone within 800 km or gusts >= 75 km/h",
                         1: "orange/red cyclone within 800 km",
                         2: "cyclone within 300 km",
                         3: "orange/red cyclone within 300 km"})


# --------------------------------------------------------------------------- sea state

def wave_level(h: float) -> int:
    """Significant wave height in the Gulf near Samui (m). TMD wind-wave warnings
    advise small boats to stay ashore at 2-3 m; ferries (Seatran, Raja, Lomprayah)
    reduce or cancel crossings in such seas, which cuts the island off.
      < 1.5: 0 ; 1.5-2: 1 ; 2-3: 2 ; >= 3: 3"""
    if h >= 3:
        return 3
    if h >= 2:
        return 2
    if h >= 1.5:
        return 1
    return 0


def tmd_gulf_wave_warnings() -> list[dict]:
    """Active TMD bulletins with a wave warning for the GULF (Andaman-only ones excluded).
    Status rows stored before `strong_waves_gulf` existed fall back to `strong_waves`."""
    return _tmd_active(lambda it: it.get("strong_waves_gulf", it.get("strong_waves"))
                       or it.get("small_boats_ashore"))


def tmd_wave_level(warns: list[dict]) -> int:
    """A TMD Gulf wave warning = 1; 'small boats stay ashore' (TMD issues it for 2-3 m
    seas) = 2; a TMD wave height is read with `wave_level`."""
    lv = 0
    for w in warns:
        lv = max(lv, 1, 2 if w.get("small_boats_ashore") else 0,
                 wave_level(w["wave_m_max"]) if w.get("wave_m_max") else 0)
    return lv


def f_sea_state() -> dict:
    label = "Sea state (ferries, isolation)"
    today = today_bkk()
    pts = _points("samui_wave_height", today.isoformat(),
                  (today + timedelta(days=3)).isoformat())
    warns = tmd_gulf_wave_warnings()
    tmd_fresh = not _stale("tmd_warnings", 6 * 3600)
    steps = {0: "waves >= 1.5 m or a TMD Gulf wave warning",
             1: "waves >= 2 m or TMD 'small boats stay ashore'", 2: "waves >= 3 m"}
    tmd_lv = tmd_wave_level(warns)
    if not pts:
        f = missing("sea_state", label, "Open-Meteo Marine", URLS["marine"],
                    why_no_data("openmeteo_marine", "Open-Meteo Marine"), steps=steps,
                    what="3-day wave-height forecast for the sea off Samui")
        if warns:
            w = warns[0]
            f.update(level=tmd_lv, level_key=level_key(tmd_lv), kind="bulletin",
                     valid_for=interval(w.get("from") or w["until"], w["until"]),
                     tz=P.TZ_LOCAL, value=w.get("wave_m_max"), unit="m" if w.get(
                         "wave_m_max") else None, retrieved_at=P.retrieved_at("tmd_warnings"),
                     summary=f"TMD Gulf wave warning {w['issue']}")
            f["explanation"] = (f"Wave forecast unavailable ({why_no_data('openmeteo_marine', 'Open-Meteo Marine')}), "
                                f"but a TMD rough-sea warning for the Gulf is in force: "
                                f"{tmd_text(w)}.")
        return f
    mx = max(pts, key=lambda p: p["value"])
    level = wave_level(mx["value"])
    src = mx["source"]
    got = P.retrieved_at(src)
    a, b = pts[0]["ts"][:10], pts[-1]["ts"][:10]
    reasons = [(f"Forecast max significant wave height {mx['value']:.1f} m on "
               f"{fmt_day(mx['ts'])} (Open-Meteo Marine, open water at 9.5 N 100.1 E off the "
               f"east coast, {fmt_period(a, b)}, fetched {fmt_ict(got) or '?'})")]
    inputs = [P.evidence("max wave height, next 3 days", mx["value"], "m", "forecast",
                         mx["ts"][:10], "Open-Meteo Marine", URLS["marine"], retrieved=got,
                         decimals=1)]
    if warns:
        level = max(level, tmd_lv)
        w = warns[0]
        extra = " -- small boats should stay ashore" if w.get("small_boats_ashore") else ""
        hm = f", waves up to {w['wave_m_max']:g} m" if w.get("wave_m_max") else ""
        reasons.append(f"{tmd_text(w)}{hm}{extra}")
        inputs.append(P.evidence("TMD Gulf wave bulletin", w["issue"], None, "bulletin",
                                 interval(w.get("from") or w["until"], w["until"]), "TMD",
                                 URLS["tmd_warn"], retrieved=P.retrieved_at("tmd_warnings")))
    elif tmd_fresh:
        reasons.append("no TMD wave warning for the Gulf in force")
    expl = ("; ".join(reasons) + ". Above 2 m small boats stay in port and ferries may be "
            "cancelled: the island is then cut off (supplies, evacuation, water by barge). "
            "Only the airport (Bangkok Airways) remains, with limited capacity.")
    return factor("sea_state", label, level, mx["value"], "m",
                  "1.5 m watch, 2 m prepare (small boats stay in port), 3 m act", expl,
                  "Open-Meteo Marine" + (", TMD" if warns else ""), URLS["marine"], None,
                  stale=_stale(src, 24 * 3600), kind="forecast", valid_for=mx["ts"][:10],
                  retrieved=got, decimals=1, unit_text="m (significant wave height)",
                  value_label=f"{mx['value']:.1f} m, forecast max on {fmt_day(mx['ts'])}",
                  summary=f"waves max {mx['value']:.1f} m (forecast to {fmt_day(b)})",
                  inputs=inputs,
                  details={"tmd_wave_warnings": [w["issue"] for w in warns],
                           "forecast_window": interval(a, b)},
                  steps=steps)


# --------------------------------------------------------------------------- air

def pm25_level(pm: float) -> int:
    """Thai Pollution Control Department PM2.5 24 h bands (revised 2023):
    0-15 very good, 15.1-25 good, 25.1-37.5 moderate, 37.6-75 starts to affect
    health, > 75 affects health. Above 125.4 = US EPA 'very unhealthy'.
      <= 37.5: 0 ; 37.6-75: 1 ; 75.1-125: 2 ; > 125: 3"""
    if pm > 125:
        return 3
    if pm > 75:
        return 2
    if pm > 37.5:
        return 1
    return 0


AIR4THAI_MAX_AGE_H = 6
KIND_RANK = {"observed": 0, "model_analysis": 1, "reanalysis": 1, "forecast": 2,
             "bulletin": 3}


def air4thai_nearest(now: datetime | None = None) -> dict | None:
    """Nearest PCD ground station with a PM2.5 reading younger than 6 h (status
    `air4thai_samui`, written by the air4thai_south collector)."""
    s = _status("air4thai_samui")
    if not s:
        return None
    now = now or _now()
    for st in sorted(s.get("stations") or [s], key=lambda x: x.get("distance_km") or 1e9):
        if st.get("pm25") is None or not st.get("observed_at"):
            continue
        if now - _parse_ts(st["observed_at"]) <= timedelta(hours=AIR4THAI_MAX_AGE_H):
            return st
    return None


def f_air() -> dict:
    label = "Air quality (PM2.5, haze)"
    now = _now()
    since = (now - timedelta(hours=24)).isoformat()
    past = _points("samui_pm2_5", since, now.isoformat(), "openmeteo_samui_air")
    fut = _points("samui_pm2_5", now.isoformat(), (now + timedelta(hours=72)).isoformat(),
                  "openmeteo_samui_air")
    st = air4thai_nearest(now)
    cams_ok = (len(past) >= 12 or len(fut) >= 24) and not _stale("openmeteo_samui_air",
                                                                   12 * 3600)
    if not cams_ok and not st:
        return missing("air", label, "Open-Meteo (CAMS) / Air4Thai (PCD)", URLS["pcd"],
                       why_no_data("openmeteo_samui_air", "the CAMS air-quality model") + "; "
                       + why_no_data("air4thai_south", "Air4Thai"),
                       what="PM2.5 from the CAMS model at Samui and from the PCD ground "
                            "stations")
    cands, parts, inputs = [], [], []
    got_cams = P.retrieved_at("openmeteo_samui_air")
    mean24 = fmax = None
    if st:
        band = f", Thai AQI {st['aqi']:.0f} '{st['band_label']}'" if st.get("aqi") is not None \
            and st.get("band_label") else ""
        parts.append(f"Measured: PM2.5 {fmt_val(st['pm25'], 'ug/m3', 1)} at {st['name']} "
                     f"({st['distance_km']:.0f} km, mainland; Koh Samui has no PCD station), "
                     f"{fmt_ict(st['observed_at'])}{band} (PCD Air4Thai)")
        cands.append(("observed", st["pm25"], st["observed_at"], st["observed_at"]))
        inputs.append(P.evidence(f"PM2.5 measured, {st['name']}", st["pm25"], "ug/m3",
                                 "observed", st["observed_at"], "PCD Air4Thai", URLS["pcd"],
                                 retrieved=P.retrieved_at("air4thai_south"), decimals=1,
                                 note=f"{st['distance_km']:.0f} km from home"))
    if cams_ok:
        if past:
            mean24 = round(sum(p["value"] for p in past) / len(past), 1)
            parts.append(f"CAMS model at Samui: 24 h mean {fmt_val(mean24, 'ug/m3', 1)} to "
                         f"{fmt_ict(past[-1]['ts'])} (model analysis)")
            cands.append(("model_analysis", mean24, past[-1]["ts"],
                          interval(past[0]["ts"][:10], past[-1]["ts"][:10])))
            inputs.append(P.evidence("PM2.5 24 h mean, CAMS", mean24, "ug/m3", "model_analysis",
                                     interval(past[0]["ts"][:10], past[-1]["ts"][:10]),
                                     "Copernicus CAMS via Open-Meteo", URLS["air"],
                                     retrieved=got_cams, decimals=1, tz=P.TZ_UTC))
        worst = None
        for i in range(max(0, len(fut) - 23)):
            w = fut[i:i + 24]
            m = sum(p["value"] for p in w) / 24
            if worst is None or m > worst[0]:
                worst = (m, w[0]["ts"], w[-1]["ts"])
        if worst:
            fmax = round(worst[0], 1)
            parts.append(f"worst forecast 24 h mean in the next 72 h "
                         f"{fmt_val(fmax, 'ug/m3', 1)} ({fmt_ict(worst[1])} to "
                         f"{fmt_ict(worst[2])})")
            cands.append(("forecast", fmax, worst[1], interval(worst[1][:10], worst[2][:10])))
            inputs.append(P.evidence("PM2.5 worst 24 h mean, next 72 h", fmax, "ug/m3",
                                     "forecast", interval(worst[1][:10], worst[2][:10]),
                                     "Copernicus CAMS via Open-Meteo", URLS["air"],
                                     retrieved=got_cams, decimals=1, tz=P.TZ_UTC))
    else:
        parts.append("CAMS model: " + why_no_data("openmeteo_samui_air", "CAMS"))
    # level from the worst of all; the shown value is the one that sets it (a measured
    # value wins a tie, then the model analysis, then the forecast)
    kind, ref, t, valid = max(cands, key=lambda c: (pm25_level(c[1]), -KIND_RANK[c[0]]))
    level = max(pm25_level(c[1]) for c in cands)
    aqi = latest_obs("samui_us_aqi", "openmeteo_samui_air")
    expl = ("; ".join(parts) + ". Samui is usually clean, but El Nino years bring haze from "
            "fires in Indonesia and Malaysia (2015, 2019).")
    where = f"at {st['name']}" if kind == "observed" else "CAMS model at Samui"
    return factor("air", label, level, ref, "ug/m3",
                  "PCD 24 h PM2.5: > 37.5 µg/m³ watch, > 75 prepare, > 125 act", expl,
                  "PCD Air4Thai (measured) + Copernicus CAMS (model)", URLS["pcd"],
                  t if kind != "forecast" else None,
                  stale=False, kind=kind,
                  valid_for=valid,
                  retrieved=P.retrieved_at("air4thai_south") if kind == "observed"
                  else got_cams, decimals=1, unit_text="µg/m³ PM2.5",
                  value_label=f"{fmt_val(ref, 'ug/m3', 1)} PM2.5 ({P.KIND_LABELS[kind]}, "
                              f"{where})",
                  summary=f"PM2.5 {fmt_val(ref, 'ug/m3', 1)} ({P.KIND_LABELS[kind]})",
                  inputs=inputs, tz=P.TZ_UTC,
                  details={"pm25_mean_24h": mean24, "pm25_worst_24h_forecast": fmax,
                           "us_aqi_latest": aqi and aqi["value"],
                           "air4thai_station": st and {k: st.get(k) for k in (
                               "station", "name", "distance_km", "pm25", "aqi", "band_label",
                               "observed_at")}},
                  steps={0: "PM2.5 > 37.5 µg/m³", 1: "PM2.5 > 75 µg/m³",
                         2: "PM2.5 > 125 µg/m³"})


# --------------------------------------------------------------------------- marine heat

BAA_LABELS = {0: "No Stress", 1: "Bleaching Watch", 2: "Bleaching Warning",
              3: "Alert Level 1", 4: "Alert Level 2", 5: "Alert Level 3",
              6: "Alert Level 4", 7: "Alert Level 5"}


def dhw_level(dhw: float) -> int:
    """NOAA Coral Reef Watch: DHW >= 4 degC-weeks Alert 1 (significant bleaching),
    >= 8 Alert 2 (severe bleaching, mortality). Context only (capped at 1)."""
    if dhw >= 8:
        return 2
    if dhw >= 4:
        return 1
    return 0


def f_marine_heat() -> dict:
    label = "Marine heat / coral bleaching"
    rows = db.query("SELECT o.source, o.series, o.ts, o.value FROM observations o JOIN "
                    "(SELECT series, MAX(ts) m FROM observations WHERE series LIKE 'crw_%dhw' "
                    "GROUP BY series) x ON x.series=o.series AND x.m=o.ts")
    if not rows:
        return missing("marine_heat", label, "NOAA Coral Reef Watch", URLS["crw"],
                       why_no_data("crw_vs", "NOAA Coral Reef Watch"),
                       what="Degree Heating Weeks for the Gulf of Thailand")
    pref = [r for r in rows if any(k in r["series"] for k in ("samui", "thailand", "gulf"))]
    r = max(pref or rows, key=lambda x: x["value"])
    level = dhw_level(r["value"])
    base = r["series"][:-len("_dhw")]
    station = base.removeprefix("crw_").replace("_", " ").title().replace(" Of ", " of ")
    alert = latest_obs(base + "_alert")
    ssta = latest_obs(base + "_ssta")
    extra = []
    if alert and alert["ts"] == r["ts"]:
        extra.append(f"bleaching alert: {BAA_LABELS.get(int(alert['value']), alert['value'])}")
    if ssta and ssta["ts"] == r["ts"]:
        extra.append(f"SST anomaly {fmt_val(ssta['value'], 'degC', 2, True)}")
    expl = (f"Degree Heating Weeks {r['value']:.1f} °C-weeks on {fmt_day(r['ts'], True)} "
            f"(NOAA Coral Reef Watch 5 km virtual station {station}, satellite, observed"
            + (f"; {'; '.join(extra)}" if extra else "") + "). Bleaching hurts the island's "
            "diving, fishing and tourism; it does not directly threaten safety (low weight).")
    return factor("marine_heat", label, level, r["value"], "degC-weeks",
                  "CRW: DHW >= 4 °C-weeks Alert 1, >= 8 Alert 2", expl, "NOAA Coral Reef Watch",
                  URLS["crw"], r["ts"], stale=(_now() - _parse_ts(r["ts"])).days > 10,
                  kind="observed", valid_for=r["ts"][:10], retrieved=P.retrieved_at("crw_vs"),
                  decimals=1, tz=P.TZ_UTC,
                  value_label=f"{r['value']:.1f} °C-weeks ({station}, {fmt_short(r['ts'])})",
                  summary=f"DHW {r['value']:.1f} °C-weeks",
                  details={"series": r["series"], "station": station,
                           "alert": alert and alert["value"], "ssta": ssta and ssta["value"]})


# --------------------------------------------------------------------------- news

WATER_WORDS = ["water shortage", "water crisis", "water rationing", "drought", "dry spell",
               "penurie d'eau", "secheresse", "sécheresse", "pénurie",
               "ขาดแคลนน้ำ", "ภัยแล้ง", "น้ำประปา", "แล้ง"]
FLOOD_WORDS = ["flood", "inondation", "landslide", "น้ำท่วม", "ดินถล่ม"]
NEWS_DAYS = 14


def news_counts(days: int = NEWS_DAYS) -> dict | None:
    since = (_now() - timedelta(days=days)).isoformat()
    has_any = db.query("SELECT 1 FROM feed_items WHERE kind IN ('news','social') LIMIT 1")
    if not has_any:
        return None
    rows = db.query(
        "SELECT source, title, summary, url, tags, COALESCE(published_at, fetched_at) AS t "
        "FROM feed_items WHERE kind IN ('news','social') AND COALESCE(published_at, fetched_at)"
        " >= ? AND (tags LIKE '%samui%' OR tags LIKE '%thailand%')", (since,))
    out = {"water_samui": 0, "water_thailand": 0, "flood_samui": 0, "flood_thailand": 0,
           "examples": [], "since": since}
    for r in rows:
        text = f"{r['title'] or ''} {r['summary'] or ''}".lower()
        tags = r["tags"] if isinstance(r["tags"], list) else []
        samui = "samui" in tags or "samui" in text or "สมุย" in text
        for kind, words in (("water", WATER_WORDS), ("flood", FLOOD_WORDS)):
            if any(re.search(re.escape(w), text) for w in words):
                out[f"{kind}_{'samui' if samui else 'thailand'}"] += 1
                if samui and len(out["examples"]) < 5:
                    out["examples"].append({"title": r["title"], "url": r["url"], "t": r["t"]})
    return out


def f_news(counts: dict | None) -> dict:
    label = "Media / social signal (Samui, Thailand)"
    if counts is None:
        return missing("news", label, "News / social feeds", "",
                       "no news or social item has been collected yet",
                       what="news and social posts about Samui / Thailand")
    samui = counts["water_samui"] + counts["flood_samui"]
    thai = counts["water_thailand"] + counts["flood_thailand"]
    level = 1 if (samui >= 3 or thai >= 10) else 0
    start = (_now().astimezone(BKK).date() - timedelta(days=NEWS_DAYS - 1))
    end = _now().astimezone(BKK).date()
    expl = (f"{fmt_period(start, end)} (last {NEWS_DAYS} days): {counts['water_samui']} "
            f"articles/posts about water and {counts['flood_samui']} about flooding mention "
            f"Samui; {thai} more about water or flooding elsewhere in Thailand. A keyword count "
            "over the app's news/social feeds: low weight, never a trigger on its own.")
    return factor("news", label, level, samui, "count",
                  ">= 3 Samui mentions or >= 10 Thailand: watch (capped at 1)", expl,
                  "The app's news/social feeds", "/api/feed?q=samui",
                  db.now_iso(), details=counts, kind="observed",
                  valid_for=interval(start, end), retrieved=db.now_iso(),
                  unit_text=f"Samui articles/posts ({NEWS_DAYS} d)",
                  value_label=f"{samui} Samui items in {NEWS_DAYS} days",
                  summary=f"{samui} Samui news items ({NEWS_DAYS} d)")


# --------------------------------------------------------------------------- combine

def combine(factors: list[dict]) -> tuple[int, list[str]]:
    """Apply R1-R4 (see module docstring). Returns (level, rules fired)."""
    lv = {f["id"]: f["level"] for f in factors if f["level"] is not None}
    rules = []
    others = [v for k, v in lv.items() if k != "news"]
    contrib = {}
    for k, v in lv.items():
        if k == "news" and not any(o >= 1 for o in others):
            continue  # R2
        contrib[k] = min(v, CAP.get(k, 3))
    level = max(contrib.values(), default=0)
    if contrib:
        top = [k for k, v in contrib.items() if v == level and v > 0]
        if top:
            rules.append(f"R1 max of factors ({', '.join(top)})")
    hot = [k for k in PHYSICAL if contrib.get(k, 0) >= 2]
    if len(hot) >= 2 and level < 3:
        level = 3
        rules.append(f"R3 combined hazards ({', '.join(hot)})")
    if lv.get("cyclone_wind") == 4:
        level = 4
        rules.append("R4a orange/red cyclone within 300 km")
    if lv.get("heat", 0) >= 3 and lv.get("water", 0) >= 3:
        level = 4
        rules.append("R4b extreme heat + water crisis")
    return level, rules


LEVEL_ACTIONS = {
    "normal": [
        "Nothing urgent. Keep a basic stock: 3 days of water and food.",
        "Once a month, check the Preparedness page and tick off what is missing.",
    ],
    "vigilance": [
        "Check this page daily and follow TMD warnings.",
        "Build the stock up to 7 days of drinking water (4-5 L/person/day in the heat).",
        "Check the house cistern / tank and look for leaks.",
        ("Note ferry (Seatran, Raja, Lomprayah) and airport schedules and contacts, "
         "without booking."),
    ],
    "prepare": [
        "Build 14 days of self-sufficiency: water, no-cook food, medication (30 days).",
        ("Fill and clean the cistern; fit a filter and keep purification tablets."),
        "Charge power banks, headlamps, batteries; test the generator/solar panel.",
        "Mosquito nets and repellent: dengue rises with heat and rain.",
        "Copies of documents (passport, visa, insurance) in a waterproof bag + online.",
        "Decide your departure threshold in advance (e.g. water cut for more than 3 days).",
    ],
    "act": [
        "Apply the matching scenario (Preparedness page) now.",
        "Stock up on water and fuel before the crowds; withdraw cash (THB).",
        "Pack the go-bag and keep it by the door.",
        "Check ferries and flights every morning; have a flexible ticket in mind.",
        "Tell someone off the island about your plan and your contact points.",
    ],
    "leave": [
        ("Leave the island while ferries and flights are running, or follow the "
         "authorities' instructions (DDPM 1784)."),
        "Take the go-bag, documents, medication and cash.",
        "Shut off water/power/gas, move valuables up high, lock the house.",
        "If you cannot leave: shelter on high ground, away from the shore, radio on.",
    ],
}

FACTOR_ACTIONS = {
    "water": "Cut water use, fill jerrycans, watch PWA Samui announcements; line up a "
             "water-truck supplier.",
    "heat": "Avoid exertion between 11:00 and 16:00, drink regularly, oral rehydration "
            "salts (ORS), battery fan; check on vulnerable people.",
    "flood": "Keep documents and electronics high and dry, avoid flooded roads and "
             "slopes (landslides), never cross moving water.",
    "cyclone_wind": "Bring in or tie down anything that can fly, ready tarps and rope, "
                    "follow the TMD and the DDPM (1784).",
    "sea_state": "Shop and refuel before ferry cancellations; do not go out in a small "
                 "boat.",
    "air": "N95/KN95 masks outdoors, windows closed, a HEPA purifier in one room.",
    "marine_heat": "Diving/snorkelling: avoid touching stressed corals.",
    "news": "Check local information (Samui groups, PWA, municipality) before acting.",
    "enso": "Strong El Nino: prepare for the 2027 dry season now (cistern, water "
            "stock, a plan if ferries stop).",
}


def build_actions(level: int, factors: list[dict], coverage: dict | None = None) -> list[dict]:
    key = LEVEL_KEYS[level]
    out = []
    if coverage and coverage["critical_missing"]:
        names = ", ".join(FACTOR_NAMES.get(i, i) for i in coverage["critical_missing"])
        out.append({"level_key": "unknown", "text": (
            f"No current data for: {names}. Until it is back, check the TMD (tmd.go.th, "
            "hotline 1182) and the ferry operators directly, and act on the highest level "
            "you can confirm.")})
    out += [{"level_key": key, "text": t} for t in LEVEL_ACTIONS[key]]
    for f in sorted(factors, key=lambda f: -(f["level"] or 0)):
        if f["level"] and f["level"] >= 1 and f["id"] in FACTOR_ACTIONS:
            out.append({"level_key": f["level_key"], "text": FACTOR_ACTIONS[f["id"]],
                        "factor": f["id"]})
    return out


def build_triggers(level: int, factors: list[dict]) -> list[dict]:
    """What would move the OVERALL level to the next one, factor by factor."""
    if level >= 4:
        return [{"level_key": "leave", "text": "Maximum level reached."}]
    target = level + 1
    nxt = LEVEL_KEYS[target]
    out = []
    for f in factors:
        if target > CAP.get(f["id"], 3) and not (target == 4 and f["id"] == "cyclone_wind"):
            continue
        cond = (f.get("steps") or {}).get(str(target))
        if cond and (f["level"] is None or f["level"] < target):
            out.append({"level_key": nxt, "text": f"{f['label']}: {cond}", "factor": f["id"]})
    if target == 3:
        out.append({"level_key": "act", "text": "Two physical hazards at 'prepare' "
                    "at the same time (e.g. heavy rain + 2 m seas)."})
    if target == 4:
        out.append({"level_key": "leave", "text": "Extreme heat ('act' level) together with a "
                    "water crisis ('act' level) on the island."})
    return out or [{"level_key": nxt, "text": "No trigger identified."}]


# Factors without which the overall level is NOT assessable: each can on its own move the
# level to 'act' or 'leave', or (enso) sets the background of the whole season.
CRITICAL = ("enso", "water", "heat", "flood", "cyclone_wind", "sea_state")
FACTOR_NAMES = {"enso": "El Nino", "water": "water / rain", "heat": "heat",
                "flood": "heavy rain / flood", "cyclone_wind": "cyclone / wind",
                "sea_state": "sea state", "air": "air quality", "marine_heat": "marine heat",
                "news": "news"}
UNKNOWN_ALERT_AFTER = timedelta(hours=6)


def coverage(factors: list[dict]) -> dict:
    """Which factors carry current data. A critical factor with no data (level None) or
    whose data is stale counts as missing for the overall assessment."""
    ids = {f["id"] for f in factors}
    miss = [f["id"] for f in factors if f["level"] is None]
    stale = [f["id"] for f in factors if f["level"] is not None and f.get("stale")]
    crit = [i for i in CRITICAL if i not in ids or i in miss or i in stale]
    return {"total": len(factors), "with_data": len(factors) - len(miss), "missing": miss,
            "stale": stale, "critical": list(CRITICAL), "critical_missing": crit}


def next_risk(d: date) -> str:
    """What comes next in Samui's year, with El Nino (the season windows of this module)."""
    y_dry = d.year + 1 if d.month >= 6 else d.year
    m = d.month
    if m in (6, 7, 8, 9):
        return (f"Next risk: NE-monsoon heavy rain and rough seas Oct-Dec {d.year} (November "
                f"wettest); water stress Feb-Apr {y_dry}.")
    if m in (10, 11, 12):
        return (f"Now: NE-monsoon heavy rain and rough seas (November wettest); next: water "
                f"stress Feb-Apr {y_dry}, heat peak Mar-May {y_dry}.")
    if m == 1:
        return (f"Next risk: water stress Feb-Apr {d.year} and heat peak Mar-May {d.year}; "
                "late NE-monsoon rain still possible in January.")
    return (f"Now: the dry-season water window (Feb-Apr) and heat peak (Mar-May {d.year}); "
            f"next: NE-monsoon rain from October {d.year}.")


def headline(level: int | None, factors: list[dict], rules: list[str],
             cov: dict | None = None, floor: int | None = None,
             today: date | None = None) -> str:
    """Specific one-paragraph verdict: level -- ENSO state; local numbers with their dates
    and kinds; what is on watch; what is missing; the next seasonal risk."""
    return " ".join(headline_parts(level, factors, cov, floor, today))


def headline_parts(level: int | None, factors: list[dict], cov: dict | None = None,
                   floor: int | None = None, today: date | None = None) -> list[str]:
    """[verdict sentence, local sentences...]; the briefing reuses parts[1:]."""
    cov = cov or coverage(factors)
    today = today or today_bkk()
    by = {f["id"]: f for f in factors}
    enso = by.get("enso") or {}
    enso_txt = (enso.get("details") or {}).get("phrase") if enso.get("level") is not None \
        else None
    if level is None:
        crit = cov["critical_missing"]
        names = ", ".join(FACTOR_NAMES.get(i, i) for i in crit)
        parts = [(f"Level cannot be assessed: no current data for {names} "
                  f"({len(crit)} critical factor(s)).")]
        fl = floor or 0
        drivers = [f for f in factors if f["level"] is not None and f["level"] >= max(1, fl)]
        if fl >= 1:
            parts.append(f"At least {LEVEL_LABELS[LEVEL_KEYS[fl]]}"
                         + (f" ({', '.join(f['label'] for f in drivers[:3])})" if drivers
                            else "") + ".")
        else:
            parts.append("The factors that do have data show nothing abnormal, which is "
                         "not enough to call the island safe.")
        known = [by[i]["summary"] for i in ("water", "sea_state", "cyclone_wind", "flood",
                                            "heat") if i in by and by[i]["level"] is not None
                 and by[i].get("summary")]
        if known:
            parts.append("Known: " + "; ".join(known) + ".")
        man = "; ".join(f"{FACTOR_NAMES.get(i, i)}: {MANUAL[i][0][1]}" for i in crit
                        if MANUAL.get(i))
        if man:
            parts.append(f"Check by hand: {man}.")
        return parts
    key = LEVEL_KEYS[level]
    first = LEVEL_LABELS[key] + (f" -- {enso_txt}" if enso_txt else "")
    parts = [first + "."]
    top = [f for f in factors if f["id"] in PHYSICAL and f["level"] is not None
           and f["level"] >= 3]
    if level <= 2 and not top:
        calm = [by[i]["summary"] for i in ("water", "sea_state", "cyclone_wind")
                if i in by and by[i]["level"] is not None and by[i].get("summary")]
        parts.append("No immediate threat on Samui" + (": " + ", ".join(calm) if calm else "")
                     + ".")
    else:
        parts.append("Main hazards: " + "; ".join(
            f"{f['label']} ({LEVEL_LABELS[f['level_key']]}): {f.get('summary') or ''}".rstrip(
                ": ") for f in sorted(top, key=lambda f: -f["level"])[:3]) + ".")
    watch = [f for f in factors if f["id"] in PHYSICAL and f["level"] in (1, 2)
             and f not in top]
    if watch:
        parts.append("Watch: " + "; ".join(
            f"{FACTOR_NAMES.get(f['id'], f['id'])} -- {f.get('summary') or f['label']}"
            for f in sorted(watch, key=lambda f: -f["level"])[:3]) + ".")
    if cov["missing"] or cov["stale"]:
        ids = cov["missing"] + cov["stale"]
        parts.append(f"{len(ids)} secondary factor(s) without current data "
                     f"({', '.join(FACTOR_NAMES.get(i, i) for i in ids)}).")
    parts.append(next_risk(today))
    return parts


def evaluate(save: bool = True) -> dict:
    counts = news_counts()
    enso = f_enso()
    water_news = (counts or {}).get("water_samui", 0)
    factors = [enso, f_water(enso["level"], water_news), f_heat(), f_flood(),
               f_cyclone_wind(), f_sea_state(), f_air(), f_marine_heat(), f_news(counts)]
    cov = coverage(factors)
    floor, rules = combine(factors)  # every known level; stale non-zero levels are kept
    level = None if cov["critical_missing"] else floor
    now_iso = db.now_iso()
    unknown_since = None
    if level is None:
        prev = db.get_status("local_risk")
        pv = prev["value"] if prev else {}
        unknown_since = (pv.get("unknown_since") if pv.get("level", 0) is None else None) \
            or now_iso
    today = today_bkk()
    hparts = headline_parts(level, factors, cov, floor, today)
    risk = {
        "level": level,
        "level_key": LEVEL_KEYS[level] if level is not None else "unknown",
        "level_label": LEVEL_LABELS[LEVEL_KEYS[level]] if level is not None else "Unknown",
        "level_floor": floor, "level_floor_key": LEVEL_KEYS[floor],
        "headline": " ".join(hparts),
        "headline_local": " ".join(hparts[1:]),
        "evaluated_at": now_iso, "unknown_since": unknown_since,
        "engine_version": ENGINE_VERSION,
        "time_basis": {"local_days": P.TZ_LOCAL, "global_indices": P.TZ_UTC,
                       "timestamps": "ISO 8601, UTC unless a date is a local (ICT) day"},
        "home": {"name": settings.home_name, "lat": settings.home_lat,
                 "lon": settings.home_lon},
        "factors": factors, "rules": rules,
        "coverage": cov,
        "complete": all(f["level"] is not None for f in factors),
        "missing": cov["missing"],
        "actions": build_actions(floor, factors, cov),
        "triggers": build_triggers(floor, factors),
        "season": season_note(today),
        "season_context": season_context(today),
        "next_risk": next_risk(today),
    }
    if save:
        db.set_status("local_risk", risk)
        _append_history(risk)
    return risk


def season_note(d: date) -> str:
    m = d.month
    if m in (10, 11, 12):
        return ("Northeast monsoon: the wettest season on Samui (flood and rough-sea risk). "
                "A rain deficit now points to a hard 2027 dry season.")
    if m in (1, 2, 3, 4):
        return ("Dry season. With El Nino, February-April 2027 is the critical window for "
                "water and heat.")
    if m == 5:
        return "End of the dry season, peak heat; the rains return gradually."
    return ("Southwest monsoon: Samui is relatively sheltered, with moderate rain. The real "
            "rainy season starts in October.")


def season_context(d: date) -> dict:
    """What the engine weighs most at this time of year (documented, see each factor)."""
    m = d.month
    if m in (10, 11, 12, 1):
        return {"id": "ne_monsoon", "label": "Northeast monsoon (October-January)",
                "focus": ["flood", "sea_state", "cyclone_wind", "water"],
                "note": ("Wettest months (November peak): flood thresholds, saturated ground "
                         "and rough seas matter most; Gulf cyclones arrive October-January. "
                         "Rain now also refills the reservoirs: a deficit is flagged "
                         "earlier under a strong El Nino.")}
    if m in (2, 3, 4, 5):
        return {"id": "dry_season", "label": "Dry / hot season (February-May)",
                "focus": ["water", "heat", "air"],
                "note": ("With El Nino, February-April 2027 is the danger window for water: "
                         "the 180-day rain window (holding the last monsoon) drives the water "
                         "level, and a strong El Nino alone keeps it at 'watch' or above. "
                         "March-May is the heat peak.")}
    return {"id": "sw_monsoon", "label": "Southwest monsoon (June-September)",
            "focus": ["sea_state", "air"],
            "note": ("Samui is sheltered from the SW monsoon: moderate rain; Andaman-side "
                     "wave warnings do not apply to the Gulf.")}


HISTORY_LEGACY_NOTE = ("recorded before the 2026-09-24 precision audit (engine v2): the level "
                       "is valid, but that engine did not label forecast vs observed values")


def _append_history(risk: dict) -> None:
    """Keep the last 1000 points. Append when the level changes or every 30 min, so
    the scheduler's frequent hooks do not flood the history. Each entry carries the
    engine version; entries from older engines are annotated once (never rewritten)."""
    h = _status("local_risk_history") or []
    for e in h:
        if "engine_version" not in e:
            e["engine_version"] = 2
            e["note"] = HISTORY_LEGACY_NOTE
    entry = {"evaluated_at": risk["evaluated_at"], "level": risk["level"],
             "level_key": risk.get("level_key"),
             "engine_version": risk.get("engine_version", ENGINE_VERSION)}
    if h:
        last = h[-1]
        age = (_parse_ts(entry["evaluated_at"]) - _parse_ts(last["evaluated_at"]))
        if last["level"] == entry["level"] and age < timedelta(minutes=30):
            db.set_status("local_risk_history", h[-1000:])
            return
    h.append(entry)
    db.set_status("local_risk_history", h[-1000:])
