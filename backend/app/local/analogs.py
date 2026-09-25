"""Historical El Nino analogs for Koh Samui: what the strong events did to the island.

Two parts:

1. Collector `samui_era5_history` (Open-Meteo archive, ECMWF ERA5, the same grid cell and
   sea-level correction as `openmeteo_samui_era5`): daily rain, maximum temperature and
   maximum feels-like temperature since 1950, fetched ONCE in decade windows (one window
   per run, never in the first minutes after start-up: the Open-Meteo quota is shared with
   the live Koh Samui collectors) and reduced to a compact MONTHLY table kept in status
   `samui_era5_history` (rain total, day count, max / mean temperatures, days at or above
   39 C feels-like, dry days and the dry-run bookkeeping that lets
   a dry spell be measured across month ends). The current year is refreshed daily (one
   light request). Monthly rain and maxima are also written as observation series for the
   charts (`samui_era5_month_precip`, `samui_era5_month_temp_max`,
   `samui_era5_month_apparent_max`, dated the 15th).

2. `build()` (served by app.analogs_api as GET /api/local/analogs): for each strong / very
   strong El Nino since 1950 the peak ONI and RONI are read from the NOAA CPC series already
   in the DB (never typed in), and the island's "water year" around the event (July of the
   developing year to June of the next) is reconstructed from the monthly table: NE-monsoon
   (Oct-Dec) and dry-season (Jan-May, Feb-Apr) rain against the 1991-2020 normal of the same
   ERA5 cell, heat (max feels-like, days >= 39 C feels-like), longest dry
   spell; the same numbers for ENSO-neutral years give the baseline. Documented impacts
   (news / agency / peer-reviewed, each URL checked live) are attached per event, kind
   "documented"; every reanalysis number is kind "reanalysis". Takeaways are sentences
   generated from those numbers only.

Limits (said on the page too): ERA5 is a ~30 km reanalysis (it under-reads the island's
rain and smooths its heat), the sample is 6-7 events, each El Nino differs, and the climate
has warmed since 1982, so an old analog understates today's heat.
"""

from __future__ import annotations

import statistics
import time
from datetime import UTC, date, datetime
from typing import ClassVar

from .. import db
from ..collectors.base import DAY, HOUR, Collector, RunContext, SourceChanged
from . import provenance as P
from .collectors import ARCHIVE_URL, _home_params, archive_end_date, today_bkk
from .risk import enso_strength

STATUS_KEY = "samui_era5_history"
STATS_VERSION = 1
HISTORY_START = 1950                 # ONI starts in 1950 (ERA5 goes back to 1940)
NORMAL_YEARS = (1991, 2020)
HEAT_FEELS_C = 39.0                  # the risk engine's "watch" threshold for feels-like
HOT_DAY_C = 35.0
DRY_DAY_MM = 1.0                     # < 1 mm = a dry day (WMO practice)
DAILY_VARS = ("precipitation_sum", "temperature_2m_max", "apparent_temperature_max")
# one monthly row = [rain_mm, n_days, tmax_max, tmax_mean, app_max, app_mean, heat39,
#                    hot35, dry_days, run_start, run_end, run_max, app_max_day, last_day]
M_FIELDS = ("rain_mm", "n_days", "tmax_max", "tmax_mean", "app_max", "app_mean", "heat_days",
            "hot_days", "dry_days", "run_start", "run_end", "run_max", "app_max_day",
            "last_day")
COMPLETE_MONTH_DAYS = 25             # a month with fewer valid days does not count

HEAVY_MIN_UPTIME_S = 300             # no history window in the first 5 min after start-up
CURRENT_REFRESH_S = 24 * HOUR
_STARTED = time.monotonic()

# The strong / very strong El Nino events since 1950 as commonly listed (NOAA CPC's ONI
# table with the >= +1.5 C bands); `peak_oni` / `peak_roni` are READ from the DB, and the
# page says when the stored index disagrees with the list (1987-88 peaks at +1.49 in the
# current ONI, i.e. just under "strong").
EVENTS: tuple[tuple[str, int], ...] = (
    ("1982-83", 1982), ("1987-88", 1987), ("1991-92", 1991), ("1997-98", 1997),
    ("2009-10", 2009), ("2015-16", 2015), ("2023-24", 2023),
)
CURRENT_EVENT = ("2026-27", 2026)

SOURCES = [
    {"id": "openmeteo_archive", "title": "Open-Meteo historical weather API (ECMWF ERA5)",
     "url": "https://open-meteo.com/en/docs/historical-weather-api"},
    {"id": "era5", "title": "Hersbach et al. (2020), The ERA5 global reanalysis, QJRMS 146",
     "url": "https://doi.org/10.1002/qj.3803"},
    {"id": "oni", "title": "NOAA CPC Oceanic Nino Index (ONI), ERSSTv5",
     "url": "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"},
    {"id": "roni", "title": "NOAA CPC Relative Oceanic Nino Index (RONI)",
     "url": "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/"},
    {"id": "oni_table", "title": "NOAA CPC -- Cold and warm episodes by season (ONI table)",
     "url": "https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/"
            "ONI_v5.php"},
]

# Documented impacts: each entry was fetched live on `checked_at` (HTTP 200) and the text
# only repeats what the page says (app.local.analogs_impacts holds the list so this module
# stays about numbers).
from .analogs_impacts import IMPACTS, NOT_FOUND


def impacts_for(eid: str) -> list[dict]:
    return [dict(i, kind="documented") for i in IMPACTS if eid in i.get("events", [])]


# --------------------------------------------------------------------------- monthly table

def _mean(xs: list[float]) -> float | None:
    return round(statistics.fmean(xs), 2) if xs else None


def month_table(payload: dict) -> dict[str, list]:
    """Open-Meteo daily block -> {"YYYY-MM": [M_FIELDS...]}. Days with a null rain or
    temperature are skipped (never stored as 0); a month keeps its own day count."""
    daily = payload.get("daily")
    if not isinstance(daily, dict) or "time" not in daily:
        raise SourceChanged("ERA5 archive: no daily.time")
    missing = [k for k in DAILY_VARS if k not in daily]
    if missing:
        raise SourceChanged(f"ERA5 archive lacks {missing}")
    by: dict[str, list[tuple[int, float, float, float]]] = {}
    for i, ts in enumerate(daily["time"]):
        p, tx, ap = (daily[k][i] for k in DAILY_VARS)
        if p is None or tx is None or ap is None:
            continue
        by.setdefault(ts[:7], []).append((int(ts[8:10]), float(p), float(tx), float(ap)))
    out: dict[str, list] = {}
    for key, days in by.items():
        days.sort()
        rain = [d[1] for d in days]
        tmax = [d[2] for d in days]
        app = [d[3] for d in days]
        dry = [d[1] < DRY_DAY_MM for d in days]
        run_start = 0
        for x in dry:
            if not x:
                break
            run_start += 1
        run_end = 0
        for x in reversed(dry):
            if not x:
                break
            run_end += 1
        run_max = cur = 0
        for x in dry:
            cur = cur + 1 if x else 0
            run_max = max(run_max, cur)
        i_app = max(range(len(app)), key=lambda j: app[j])
        out[key] = [round(sum(rain), 1), len(days), round(max(tmax), 1), _mean(tmax),
                    round(max(app), 1), _mean(app), sum(1 for a in app if a >= HEAT_FEELS_C),
                    sum(1 for t in tmax if t >= HOT_DAY_C), sum(dry), run_start, run_end,
                    run_max, days[i_app][0], days[-1][0]]
    if not out:
        raise SourceChanged("ERA5 archive: no valid day in the window")
    return out


def m(row: list | None, field: str):
    """Field of a monthly row (None when the month is missing)."""
    return None if row is None else row[M_FIELDS.index(field)]


def _key(y: int, mo: int) -> str:
    return f"{y:04d}-{mo:02d}"


def _months(y: int, mo_from: int, mo_to: int) -> list[str]:
    return [_key(y, mo) for mo in range(mo_from, mo_to + 1)]


def _complete(months: dict, keys: list[str]) -> bool:
    return all(months.get(k) is not None and m(months[k], "n_days") >= COMPLETE_MONTH_DAYS
               for k in keys)


def normals(months: dict, years: tuple[int, int] = NORMAL_YEARS) -> dict:
    """Per calendar month, the 1991-2020 mean of the monthly rain total, max feels-like,
    heat days and hot days (only from complete months; a month needs >= 20 of the 30 years)."""
    out: dict[str, dict] = {}
    for mo in range(1, 13):
        rows = [months[_key(y, mo)] for y in range(years[0], years[1] + 1)
                if months.get(_key(y, mo)) is not None
                and m(months[_key(y, mo)], "n_days") >= COMPLETE_MONTH_DAYS]
        if len(rows) < 20:
            continue
        out[f"{mo:02d}"] = {
            "rain_mm": _mean([m(r, "rain_mm") for r in rows]),
            "app_max": _mean([m(r, "app_max") for r in rows]),
            "tmax_max": _mean([m(r, "tmax_max") for r in rows]),
            "heat_days": _mean([m(r, "heat_days") for r in rows]),
            "dry_days": _mean([m(r, "dry_days") for r in rows]),
            "years": len(rows),
        }
    return out


def season_rain(months: dict, keys: list[str], norm: dict | None,
                partial: bool = False) -> dict | None:
    """Rain over `keys` vs the normal of the same months. With `partial`, the leading run
    of complete months is used (for the season under way) and `months` says which."""
    if partial:
        done = []
        for k in keys:
            if months.get(k) is None or m(months[k], "n_days") < COMPLETE_MONTH_DAYS:
                break
            done.append(k)
        keys = done
    if not keys or not _complete(months, keys):
        return None
    total = round(sum(m(months[k], "rain_mm") for k in keys), 1)
    out = {"rain_mm": total, "normal_mm": None, "pct": None, "months": keys}
    if norm and all(k[5:] in norm for k in keys):
        normal = round(sum(norm[k[5:]]["rain_mm"] for k in keys), 1)
        out["normal_mm"] = normal
        out["pct"] = round(100 * total / normal) if normal > 0 else None
    return out


def longest_dry_spell(months: dict, keys: list[str]) -> int | None:
    """Longest run of dry days (< 1 mm) across consecutive complete months."""
    if not _complete(months, keys):
        return None
    best = carry = 0
    for k in keys:
        row = months[k]
        n, run_s, run_e, run_m, dry = (m(row, f) for f in ("n_days", "run_start", "run_end",
                                                             "run_max", "dry_days"))
        if dry == n:  # the whole month is dry: the run continues
            carry += n
            best = max(best, carry)
            continue
        best = max(best, carry + run_s, run_m)
        carry = run_e
    return best


def heat_stats(months: dict, keys: list[str], norm: dict | None) -> dict | None:
    if not _complete(months, keys):
        return None
    peak = max(keys, key=lambda k: m(months[k], "app_max"))
    out = {"max_feels_like": m(months[peak], "app_max"), "max_feels_like_month": peak,
           "max_feels_like_day": f"{peak}-{m(months[peak], 'app_max_day'):02d}",
           "max_temp": round(max(m(months[k], "tmax_max") for k in keys), 1),
           "heat_days": sum(m(months[k], "heat_days") for k in keys),
           "months": keys, "normal_heat_days": None, "normal_max_feels_like": None}
    if norm and all(k[5:] in norm for k in keys):
        out["normal_heat_days"] = round(sum(norm[k[5:]]["heat_days"] for k in keys), 1)
        out["normal_max_feels_like"] = round(max(norm[k[5:]]["app_max"] for k in keys), 1)
    return out


def year_stats(months: dict, y1: int, norm: dict | None) -> dict:
    """The island's water year around an event: July `y1` (developing year) to June y1+1.
    Every number is None when a month is missing or incomplete (never guessed)."""
    y2 = y1 + 1
    ne = _months(y1, 10, 12)
    dry = _months(y2, 1, 5)
    fa = _months(y2, 2, 4)
    sw = _months(y1, 6, 9)
    wy = _months(y1, 7, 12) + _months(y2, 1, 6)
    monthly = []
    for k in wy:
        row = months.get(k)
        n = (norm or {}).get(k[5:])
        rain = m(row, "rain_mm")
        monthly.append({
            "month": k, "rain_mm": rain, "n_days": m(row, "n_days"),
            "normal_mm": n["rain_mm"] if n else None,
            "pct": (round(100 * rain / n["rain_mm"]) if rain is not None and n
                    and n["rain_mm"] else None),
            "app_max": m(row, "app_max"), "heat_days": m(row, "heat_days"),
            "dry_days": m(row, "dry_days"),
            "complete": bool(row is not None and m(row, "n_days") >= COMPLETE_MONTH_DAYS),
        })
    return {
        "water_year": f"{y1}-07/{y2}-06",
        "sw_monsoon": season_rain(months, sw, norm),        # Jun-Sep y1 (developing)
        "ne_monsoon": season_rain(months, ne, norm),        # Oct-Dec y1 (refill)
        "dry_season": season_rain(months, dry, norm),       # Jan-May y2
        "feb_apr": season_rain(months, fa, norm),           # Feb-Apr y2 (danger window)
        "year": season_rain(months, wy, norm),
        "heat": heat_stats(months, dry, norm),
        "longest_dry_spell_days": longest_dry_spell(months, dry),
        "longest_dry_spell_ne_days": longest_dry_spell(months, ne),
        "monthly": monthly,
        "complete": _complete(months, wy),
    }


# --------------------------------------------------------------------------- ENSO events

def _series(series: str, since: str, until: str) -> list[dict]:
    return db.query("SELECT ts, value, meta FROM observations WHERE series=? AND ts>=? AND "
                    "ts<=? ORDER BY ts", (series, since, until))


def _season(row: dict) -> str | None:
    meta = row.get("meta") or {}
    return meta.get("season") if isinstance(meta, dict) else None


def peak_index(series: str, y1: int) -> dict | None:
    """Highest 3-month value between MAM of the developing year and MJJ of the next."""
    rows = _series(series, f"{y1}-04-15", f"{y1 + 1}-06-15")
    if not rows:
        return None
    top = max(rows, key=lambda r: r["value"])
    return {"value": top["value"], "season": _season(top) or top["ts"][:7], "ts": top["ts"],
            "valid_for": P.series_valid_for("cpc_oni", top["ts"]), "kind": "observed",
            "source": "NOAA CPC", "unit": "degC", "unit_label": "°C"}


def index_at(series: str, y1: int, ts_suffix: str = "-07-15") -> float | None:
    rows = _series(series, f"{y1}{ts_suffix}", f"{y1}{ts_suffix}")
    return rows[0]["value"] if rows else None


def neutral_years(y_from: int = HISTORY_START, y_to: int | None = None,
                  band: float = 0.5) -> list[int]:
    """Water years y1 whose ONI stayed within +-band from SON(y1) to FMA(y1+1): neither an
    El Nino nor a La Nina winter (NOAA's episode threshold is +-0.5 C)."""
    y_to = y_to or (today_bkk().year - 1)
    rows = db.query("SELECT ts, value FROM observations WHERE series='oni' AND ts>=? ORDER BY ts",
                    (f"{y_from}-01-01",))
    by_ts = {r["ts"]: r["value"] for r in rows}
    out = []
    for y1 in range(y_from, y_to + 1):
        keys = [f"{y1}-10-15", f"{y1}-11-15", f"{y1}-12-15", f"{y1 + 1}-01-15",
                f"{y1 + 1}-02-15", f"{y1 + 1}-03-15"]
        vals = [by_ts.get(k) for k in keys]
        if any(v is None for v in vals):
            continue
        if max(abs(v) for v in vals) < band:
            out.append(y1)
    return out


# --------------------------------------------------------------------------- baseline / build

def _median(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    v = round(statistics.median(xs), 1)
    return int(v) if v == int(v) else v


def fmt_mon(k: str) -> str:
    return date(int(k[:4]), int(k[5:7]), 1).strftime("%b")


def _get(stats: dict, *path):
    cur: object = stats
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


METRICS = (  # (id, label, unit, path in year_stats, better_when)
    ("ne_monsoon_rain_pct", "Oct-Dec rain, % of normal", "%", ("ne_monsoon", "pct")),
    ("dry_season_rain_pct", "Jan-May rain, % of normal", "%", ("dry_season", "pct")),
    ("feb_apr_rain_pct", "Feb-Apr rain, % of normal", "%", ("feb_apr", "pct")),
    ("year_rain_pct", "Jul-Jun rain, % of normal", "%", ("year", "pct")),
    ("max_feels_like", "Max feels-like, Jan-May", "degC", ("heat", "max_feels_like")),
    ("heat_days", "Days >= 39 °C feels-like, Jan-May", "days", ("heat", "heat_days")),
    ("longest_dry_spell_days", "Longest dry spell, Jan-May", "days",
     ("longest_dry_spell_days",)),
)


def baseline(months: dict, years: list[int], norm: dict | None) -> dict:
    per = {y: year_stats(months, y, norm) for y in years}
    complete = [y for y, s in per.items() if s["complete"]]
    out: dict = {"years": complete, "n": len(complete), "metrics": {}}
    for mid, label, unit, path in METRICS:
        vals = [_get(per[y], *path) for y in complete]
        vals = [v for v in vals if v is not None]
        out["metrics"][mid] = {"label": label, "unit": unit, "unit_label": P.unit_label(unit),
                               "median": _median(vals), "mean": _mean(vals),
                               "min": min(vals) if vals else None,
                               "max": max(vals) if vals else None, "n": len(vals)}
    return out


def _flat(stats: dict) -> dict:
    """The event summary block (flat numbers the page shows in a table)."""
    return {mid: _get(stats, *path) for mid, _l, _u, path in METRICS} | {
        "ne_monsoon_rain_mm": _get(stats, "ne_monsoon", "rain_mm"),
        "dry_season_rain_mm": _get(stats, "dry_season", "rain_mm"),
        "feb_apr_rain_mm": _get(stats, "feb_apr", "rain_mm"),
        "max_feels_like_day": _get(stats, "heat", "max_feels_like_day"),
        "max_temp": _get(stats, "heat", "max_temp"),
        "longest_dry_spell_ne_days": stats.get("longest_dry_spell_ne_days"),
        "complete": stats.get("complete"),
    }


def _count(events: list[dict], key: str, pred) -> tuple[int, int, list[str]]:
    have = [e for e in events if e["samui"].get(key) is not None]
    hit = [e for e in have if pred(e["samui"][key])]
    return len(hit), len(have), [e["id"] for e in hit]


def takeaways(events: list[dict], base: dict, current: dict) -> list[str]:
    """Plain-English statements, every number taken from the payload above."""
    out: list[str] = []
    n_ev = sum(1 for e in events if e["samui"].get("complete"))
    if not n_ev:
        return ["No reconstructed event yet: the ERA5 history is still being fetched."]
    bm = base["metrics"]
    k, n, ids = _count(events, "feb_apr_rain_pct", lambda v: v < 60)
    if n:
        nb = bm["feb_apr_rain_pct"]
        out.append(f"In {k} of {n} strong El Ninos, Samui's Feb-Apr rain was below 60% of the "
                   f"1991-2020 normal ({', '.join(ids) or 'none'}); the neutral-year median "
                   f"is {nb['median']}% (n={nb['n']}).")
    k, n, ids = _count(events, "dry_season_rain_pct", lambda v: v < 75)
    if n:
        ev_med = _median([e["samui"]["dry_season_rain_pct"] for e in events])
        out.append(f"Jan-May rain (the dry season after the peak) was below 75% of normal in "
                   f"{k} of {n} events ({', '.join(ids) or 'none'}): event median {ev_med}% "
                   f"vs {bm['dry_season_rain_pct']['median']}% in neutral years.")
    k, n, ids = _count(events, "ne_monsoon_rain_pct", lambda v: v < 80)
    if n:
        ev_med = _median([e["samui"]["ne_monsoon_rain_pct"] for e in events])
        out.append(f"The Oct-Dec refill (NE monsoon) was below 80% of normal in {k} of {n} "
                   f"events ({', '.join(ids) or 'none'}); event median {ev_med}% vs "
                   f"{bm['ne_monsoon_rain_pct']['median']}% in neutral years: a strong El Nino "
                   "does not guarantee a weak monsoon on the Gulf coast.")
    hot = [e for e in events if e["samui"].get("max_feels_like") is not None]
    if hot:
        top = max(hot, key=lambda e: e["samui"]["max_feels_like"])
        out.append(f"Dry-season heat: max feels-like reached {top['samui']['max_feels_like']} °C "
                   f"in {top['id']} (on {top['samui']['max_feels_like_day']}); event median "
                   f"{_median([e['samui']['max_feels_like'] for e in hot])} °C vs "
                   f"{bm['max_feels_like']['median']} °C in neutral years (ERA5 cell values, "
                   "cooler than a Samui thermometer).")
    hd = [e for e in events if e["samui"].get("heat_days") is not None]
    if hd:
        out.append(f"Days at or above 39 °C feels-like in Jan-May: event median "
                   f"{_median([e['samui']['heat_days'] for e in hd])} vs neutral median "
                   f"{bm['heat_days']['median']}; the most was {max(e['samui']['heat_days'] for e in hd)} "
                   f"in {max(hd, key=lambda e: e['samui']['heat_days'])['id']}.")
    ds = [e for e in events if e["samui"].get("longest_dry_spell_days") is not None]
    if ds:
        top = max(ds, key=lambda e: e["samui"]["longest_dry_spell_days"])
        out.append(f"Longest dry spell (days under 1 mm) in Jan-May: event median "
                   f"{_median([e['samui']['longest_dry_spell_days'] for e in ds])} days vs "
                   f"{bm['longest_dry_spell_days']['median']} in neutral years; longest "
                   f"{top['samui']['longest_dry_spell_days']} days in {top['id']}.")
    oni_now = current.get("oni")
    same = [(e["id"], e.get("oni_jja")) for e in events if e.get("oni_jja") is not None]
    if oni_now and oni_now.get("value") is not None and same:
        above = [i for i, v in same if oni_now["value"] > v]
        out.append(f"At the same stage (JJA), ONI {oni_now['value']:+.2f} °C in 2026 is above "
                   f"{len(above)} of {len(same)} analogs "
                   f"({', '.join(f'{i} {v:+.2f}' for i, v in sorted(same, key=lambda x: -x[1])[:3])}"
                   " were the highest); the 2026 event started early and fast.")
    so_far = current.get("so_far") or {}
    sw = so_far.get("sw_monsoon")
    if sw and sw.get("pct") is not None:
        a, b = sw["months"][0], sw["months"][-1]
        span = (f"{fmt_mon(a)}-{fmt_mon(b)} {b[:4]}" if a != b else f"{fmt_mon(a)} {a[:4]}")
        out.append(f"So far in 2026 ({span}, the complete months; ERA5 through "
                   f"{so_far.get('last_day')}): {sw['rain_mm']:.0f} mm = {sw['pct']}% of the "
                   "normal for those months; the decisive months (the Oct-Dec refill, then "
                   "Feb-Apr 2027) are still ahead.")
    out.append(f"Sample: {n_ev} events and {base['n']} neutral years from one ~30 km ERA5 grid "
               "cell; each El Nino differs and the climate has warmed since 1982, so use these "
               "as ranges, not forecasts.")
    return out


def _doc() -> dict | None:
    s = db.get_status(STATUS_KEY)
    return s["value"] if s else None


def build(now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    doc = _doc() or {}
    months = doc.get("months") or {}
    norm = doc.get("normals") or (normals(months) if months else None)
    windows = doc.get("windows") or {}
    events = []
    for eid, y1 in EVENTS:
        oni, roni = peak_index("oni", y1), peak_index("roni", y1)
        stats = year_stats(months, y1, norm) if months else {"complete": False, "monthly": []}
        listed = "strong / very strong (NOAA CPC ONI table)"
        note = None
        if oni and oni["value"] < 1.5:
            note = (f"listed as strong in older tables, but the current CPC ONI peaks at "
                    f"{oni['value']:+.2f} °C ({oni['season']}), just under the +1.5 °C band")
        events.append({
            "id": eid, "years": [y1, y1 + 1], "listed_as": listed, "note": note,
            "peak_oni": oni, "peak_roni": roni,
            "strength": enso_strength(oni["value"]) if oni else None,
            "oni_jja": index_at("oni", y1), "roni_jja": index_at("roni", y1),
            "samui": _flat(stats) | {"kind": "reanalysis"},
            "detail": stats,
            "impacts": impacts_for(eid),
        })
    neutral = neutral_years() if months else []
    base = baseline(months, neutral, norm) if months else {"years": [], "n": 0, "metrics": {}}
    latest = {}
    for s in ("oni", "roni", "nino34_weekly_anom"):
        rows = db.query("SELECT ts, value, meta FROM observations WHERE series=? ORDER BY ts DESC "
                        "LIMIT 1", (s,))
        latest[s] = ({"value": rows[0]["value"], "ts": rows[0]["ts"],
                      "season": _season(rows[0]), "kind": "observed"} if rows else None)
    so_far = year_stats(months, CURRENT_EVENT[1], norm) if months else None
    if so_far:
        y1 = CURRENT_EVENT[1]
        so_far["sw_monsoon"] = season_rain(months, _months(y1, 6, 9), norm, partial=True)
        so_far["ne_monsoon"] = season_rain(months, _months(y1, 10, 12), norm, partial=True)
    current = {
        "id": CURRENT_EVENT[0], "years": list(CURRENT_EVENT[1:]) + [CURRENT_EVENT[1] + 1],
        "oni": latest["oni"], "roni": latest["roni"], "nino34_weekly": latest["nino34_weekly_anom"],
        "strength": enso_strength(latest["oni"]["value"]) if latest["oni"] else None,
        "month": now.astimezone(P.BKK).strftime("%Y-%m"),
        "so_far": ({k: so_far[k] for k in ("sw_monsoon", "ne_monsoon", "monthly")}
                   | {"last_day": doc.get("last_day"), "kind": "reanalysis"}) if so_far else None,
    }
    listed = {e for e, _ in EVENTS}
    other_impacts = [dict(i, kind="documented") for i in IMPACTS
                     if not (set(i.get("events") or []) & listed)]
    return {
        "generated_at": now.replace(microsecond=0).isoformat(),
        "point": doc.get("point") or {"lat": None, "lon": None},
        "history": {"from": doc.get("first_month"), "to": doc.get("last_month"),
                    "last_day": doc.get("last_day"), "months": len(months),
                    "windows_pending": [w for w, v in windows.items() if not v],
                    "updated_at": (db.get_status(STATUS_KEY) or {}).get("updated_at"),
                    "stats_version": doc.get("version")},
        "events": events,
        "neutral_baseline": base | {"rule": "ONI within +-0.5 °C from SON to FMA (no El Nino "
                                            "and no La Nina winter)"},
        "normal": {"period": f"{NORMAL_YEARS[0]}-{NORMAL_YEARS[1]}", "months": norm},
        "current_event": current | {"impacts": impacts_for(CURRENT_EVENT[0])},
        "takeaways": takeaways(events, base, current),
        "other_impacts": [i for i in other_impacts if CURRENT_EVENT[0] not in i["events"]],
        "impacts_not_found": NOT_FOUND,
        "kinds": {"reanalysis": "ERA5 grid-cell values (Open-Meteo archive), not station "
                                "measurements", "observed": "NOAA CPC indices",
                  "documented": "a dated report from the source linked, checked live"},
        "method": METHOD,
        "sources": SOURCES + [{"id": f"impact_{i}", "title": x["source_title"], "url": x["url"]}
                              for i, x in enumerate(IMPACTS)],
    }


METHOD = (
    "Events: the strong / very strong El Ninos of the NOAA CPC ONI table since 1950; their peak "
    "ONI and RONI are read from the CPC series stored by this app (series oni, roni). For each "
    "event the island's water year (July of the developing year to June of the next) is rebuilt "
    "from ERA5 daily data for the Maenam grid cell (Open-Meteo archive, models=era5, elevation "
    "10 m, the same cell as the live rain-deficit factor): Oct-Dec (NE monsoon refill), Jan-May "
    "(dry season) and Feb-Apr rain as % of the 1991-2020 mean of the same cell; max feels-like "
    "and days at or above 39 °C feels-like / 35 °C in Jan-May; the longest run of days under "
    "1 mm. Neutral years (ONI within +-0.5 °C from SON to FMA) give the baseline (median). "
    "Numbers are monthly aggregates computed once from the daily data (fetched in decade "
    "windows, one per run, to respect the shared Open-Meteo quota) and cached in status "
    "samui_era5_history; the current year is refreshed daily. Documented impacts come from "
    "dated reports whose URL was checked live; nothing is inferred from the numbers."
)


# --------------------------------------------------------------------------- collector

def decade_windows(start_year: int = HISTORY_START, today: date | None = None
                   ) -> list[tuple[str, str, str]]:
    """[(id, start, end)] decade windows up to the current year (last window = this year,
    ending on the latest day the archive accepts: today in UTC)."""
    today = today or archive_end_date()
    out = []
    y = start_year
    while y < today.year:
        y_end = min(y + 9, today.year - 1)
        out.append((f"{y}-{y_end}", f"{y}-01-01", f"{y_end}-12-31"))
        y = y_end + 1
    out.append((f"{today.year}", f"{today.year}-01-01", today.isoformat()))
    return out


def om_weight(n_vars: int, n_days: int) -> float:
    """Open-Meteo's fair-use accounting: > 10 variables or > 2 weeks counts as extra calls."""
    return max(1.0, n_vars / 10) * max(1.0, n_days / 14)


class SamuiEra5History(Collector):
    name = "samui_era5_history"
    title = "Koh Samui -- ERA5 monthly history since 1950 (El Nino analogs)"
    category = "local"
    provider = "Open-Meteo archive (ECMWF ERA5)"
    homepage = "https://open-meteo.com/en/docs/historical-weather-api"
    endpoint = ARCHIVE_URL
    interval_s = HOUR
    freshness_basis = "status"
    freshness_status_key = STATUS_KEY
    max_age_s = 3 * DAY
    description = ("Daily ERA5 rain, maximum and feels-like temperature for the Maenam grid "
                   "cell since 1950, fetched once in decade windows (one per run) and kept as "
                   "monthly totals, maxima, heat days and dry-spell counts: the data behind "
                   "the El Nino analogs page (GET /api/local/analogs). The current year is "
                   "refreshed daily. Status key samui_era5_history; series "
                   "samui_era5_month_precip / _temp_max / _apparent_max (dated the 15th).")
    min_uptime_s: ClassVar[float] = HEAVY_MIN_UPTIME_S

    async def _fetch(self, ctx: RunContext, start: str, end: str) -> dict:
        r = await ctx.get(ARCHIVE_URL, params=_home_params() | {
            "daily": ",".join(DAILY_VARS), "timezone": "Asia/Bangkok", "models": "era5",
            "start_date": start, "end_date": end})
        return r.json()

    async def collect(self, ctx: RunContext) -> int:
        today = archive_end_date()
        doc = _doc() or {}
        if doc.get("version") != STATS_VERSION:
            doc = {"version": STATS_VERSION, "months": {}, "windows": {}}
        months: dict = doc.get("months") or {}
        windows: dict = doc.get("windows") or {}
        plan = decade_windows(HISTORY_START, today=today)
        current_id = plan[-1][0]
        for wid, _s, _e in plan:
            windows.setdefault(wid, None)
        fetched: list[str] = []
        weight = 0.0
        # 1. the current year: light, refreshed daily
        cur = windows.get(current_id)
        cur_at = P.parse_dt(cur["fetched_at"]) if cur else None
        if cur_at is None or (datetime.now(UTC) - cur_at).total_seconds() > CURRENT_REFRESH_S:
            _wid, s, e = plan[-1]
            payload = await self._fetch(ctx, s, e)
            months.update(month_table(payload))
            windows[current_id] = {"fetched_at": db.now_iso(), "start": s, "end": e}
            fetched.append(current_id)
            weight += om_weight(len(DAILY_VARS), (date.fromisoformat(e) - date.fromisoformat(s)).days + 1)
            doc["point"] = {"lat": payload.get("latitude"), "lon": payload.get("longitude"),
                            "elevation": payload.get("elevation")}
        # 2. one missing decade window per run, never right after start-up. Newest decade
        #    first: the 1991-2020 normal (4 windows) and the recent events (2009-10, 2015-16,
        #    2023-24) become available after 4 runs instead of 7, the 1950s-70s last.
        pending = [w for w in reversed(plan[:-1]) if not windows.get(w[0])]
        if pending and time.monotonic() - _STARTED >= self.min_uptime_s:
            wid, s, e = pending[0]
            payload = await self._fetch(ctx, s, e)
            months.update(month_table(payload))
            windows[wid] = {"fetched_at": db.now_iso(), "start": s, "end": e}
            fetched.append(wid)
            weight += om_weight(len(DAILY_VARS), (date.fromisoformat(e) - date.fromisoformat(s)).days + 1)
            pending = pending[1:]
            doc.setdefault("point", {"lat": payload.get("latitude"),
                                     "lon": payload.get("longitude"),
                                     "elevation": payload.get("elevation")})
        if not months:
            raise SourceChanged("ERA5 history: no month stored")
        keys = sorted(months)
        doc.update(months=months, windows=windows, first_month=keys[0], last_month=keys[-1],
                   last_day=_last_day(months), normals=normals(months),
                   source="Open-Meteo archive (ECMWF ERA5)", url=ARCHIVE_URL,
                   fields=list(M_FIELDS), thresholds={"heat_feels_like_c": HEAT_FEELS_C,
                                                      "hot_day_c": HOT_DAY_C,
                                                      "dry_day_mm": DRY_DAY_MM},
                   quota={"last_run_weight": round(weight, 1), "fetched": fetched})
        db.set_status(STATUS_KEY, doc)
        ctx.notes.update(fetched=fetched, pending=[w[0] for w in pending], months=len(months),
                         weight=round(weight, 1))
        rows = []
        for k in (keys if fetched else []):
            ts = f"{k}-15"
            rows += [{"series": "samui_era5_month_precip", "ts": ts, "value": m(months[k], "rain_mm"),
                      "unit": "mm", "meta": {"days": m(months[k], "n_days")}},
                     {"series": "samui_era5_month_temp_max", "ts": ts,
                      "value": m(months[k], "tmax_max"), "unit": "degC"},
                     {"series": "samui_era5_month_apparent_max", "ts": ts,
                      "value": m(months[k], "app_max"), "unit": "degC",
                      "meta": {"heat_days_39": m(months[k], "heat_days")}}]
        if rows:
            db.upsert_observations(self.name, rows)
        return len(months)


def _last_day(months: dict) -> str | None:
    """Last day with valid ERA5 data (the newest month is partial: ERA5 lags ~5 days)."""
    if not months:
        return None
    k = max(months)
    d = m(months[k], "last_day")
    return f"{k}-{d:02d}" if d else None


COLLECTORS = [SamuiEra5History]
