"""ENSO index collectors (observations).

Every parser works on the raw text / JSON the agency serves and raises
SourceChanged when the payload no longer looks like the documented format.

Timestamp conventions (see CLAUDE.md):
- 3-month seasons (ONI, RONI): the center month's 15th, DJF 2026 -> 2026-01-15.
  CPC labels every season with the year of its center month.
- 2-month seasons (MEI.v2): the boundary between the two months, i.e. the 1st of
  the second month (DJ 2026 = Dec 2025 + Jan 2026 -> 2026-01-01).
- Monthly values (SOI): the month's 15th.
- Weekly Nino SST: the week-center date CPC prints.
- Daily OISST (Climate Reanalyzer): the day itself.
"""

from __future__ import annotations

import asyncio
import calendar
import json
import re
import urllib.request
from datetime import date, timedelta

from .. import db
from ..config import settings
from .base import DAY, Collector, RunContext, SourceChanged

SEASONS3 = {
    "DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
    "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12,
}
MEI_SEASONS = ["DJ", "JF", "FM", "MA", "AM", "MJ", "JJ", "JA", "AS", "SO", "ON", "ND"]
MONTHS = {m.upper(): i for i, m in enumerate(calendar.month_abbr) if m}


def _mid(year: int, month: int) -> str:
    return date(year, month, 15).isoformat()


# ---------------------------------------------------------------- parsers


def parse_oni(text: str) -> list[dict]:
    """oni.ascii.txt: `SEAS YR TOTAL ANOM` -> rows for `oni` (anom) and `oni_total`."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines or lines[0].split() != ["SEAS", "YR", "TOTAL", "ANOM"]:
        raise SourceChanged("ONI header is not 'SEAS YR TOTAL ANOM'")
    out = []
    for ln in lines[1:]:
        p = ln.split()
        if len(p) != 4 or p[0] not in SEASONS3:
            raise SourceChanged(f"unexpected ONI row: {ln!r}")
        ts = _mid(int(p[1]), SEASONS3[p[0]])
        meta = {"season": f"{p[0]} {p[1]}"}
        out.append({"series": "oni", "ts": ts, "value": float(p[3]), "unit": "degC", "meta": meta})
        out.append({"series": "oni_total", "ts": ts, "value": float(p[2]), "unit": "degC",
                    "meta": meta})
    if not out:
        raise SourceChanged("ONI file has no rows")
    return out


def parse_roni(text: str) -> list[dict]:
    """RONI.ascii.txt: `SEAS YR ANOM` -> `roni`."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines or lines[0].split() != ["SEAS", "YR", "ANOM"]:
        raise SourceChanged("RONI header is not 'SEAS YR ANOM'")
    out = []
    for ln in lines[1:]:
        p = ln.split()
        if len(p) != 3 or p[0] not in SEASONS3:
            raise SourceChanged(f"unexpected RONI row: {ln!r}")
        out.append({"series": "roni", "ts": _mid(int(p[1]), SEASONS3[p[0]]),
                    "value": float(p[2]), "unit": "degC", "meta": {"season": f"{p[0]} {p[1]}"}})
    if not out:
        raise SourceChanged("RONI file has no rows")
    return out


_WK_ROW = re.compile(r"^\s*(\d{2})([A-Z]{3})(\d{4})\s+(.*)$")
_NUM = re.compile(r"-?\d+\.\d")
WK_REGIONS = ("nino12", "nino3", "nino34", "nino4")


def parse_weekly_sst(text: str) -> list[dict]:
    """wksst9120.for: `02SEP1981     20.6-0.1     24.8-0.1 ...` (values can touch)."""
    if "Nino34" not in text or "SSTA" not in text:
        raise SourceChanged("weekly SST header (Nino34 / SSTA) not found")
    out = []
    for ln in text.splitlines():
        m = _WK_ROW.match(ln)
        if not m:
            continue
        mon = MONTHS.get(m.group(2))
        nums = _NUM.findall(m.group(4))
        if mon is None or len(nums) != 8:
            raise SourceChanged(f"unexpected weekly SST row: {ln!r}")
        ts = date(int(m.group(3)), mon, int(m.group(1))).isoformat()
        for i, region in enumerate(WK_REGIONS):
            out.append({"series": f"{region}_weekly_sst", "ts": ts,
                        "value": float(nums[2 * i]), "unit": "degC"})
            out.append({"series": f"{region}_weekly_anom", "ts": ts,
                        "value": float(nums[2 * i + 1]), "unit": "degC"})
    if not out:
        raise SourceChanged("weekly SST file has no data rows")
    return out


def _fixed_months(line: str) -> tuple[int, list[str]]:
    """CPC SOI rows: 4-char year then 12 fields of width 6 (they can touch: -1.8-999.9)."""
    year = int(line[:4])
    body = line[4:].rstrip()
    return year, [body[i:i + 6].strip() for i in range(0, 72, 6)]


def parse_cpc_soi(text: str) -> list[dict]:
    """CPC `soi`: two tables (ANOMALY, then STANDARDIZED DATA). We keep the
    standardized one as `soi`. Missing = -999.9."""
    lines = text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if "STANDARDIZED" in ln)
    except StopIteration:
        raise SourceChanged("CPC SOI: STANDARDIZED table not found") from None
    out = []
    for ln in lines[start + 1:]:
        if not re.match(r"^\d{4}", ln):
            if out and "STAND" in ln:
                break  # a further table would start here
            continue
        year, fields = _fixed_months(ln)
        for m, f in enumerate(fields, start=1):
            if not f:
                continue
            v = float(f)
            if v <= -999:
                continue
            out.append({"series": "soi", "ts": _mid(year, m), "value": v, "unit": "std"})
    if not out:
        raise SourceChanged("CPC SOI: no standardized values")
    return out


def parse_mei(text: str) -> list[dict]:
    """meiv2.data: first line `1979 2026`, then `YEAR DJ JF ... ND`, -999.00 = missing."""
    lines = text.splitlines()
    head = lines[0].split() if lines else []
    if len(head) != 2 or not all(h.isdigit() for h in head):
        raise SourceChanged("MEI.v2 first line is not 'START END'")
    y0, y1 = int(head[0]), int(head[1])
    out = []
    for ln in lines[1:]:
        p = ln.split()
        if len(p) != 13 or not p[0].isdigit():
            continue
        year = int(p[0])
        if not y0 <= year <= y1:
            continue
        for i, raw in enumerate(p[1:]):
            v = float(raw)
            if v <= -999:
                continue
            # season i covers months i and i+1 (1-based: DJ = Dec(prev) + Jan)
            ts = date(year, i + 1, 1).isoformat()
            out.append({"series": "mei_v2", "ts": ts, "value": v, "unit": "index",
                        "meta": {"season": f"{MEI_SEASONS[i]} {year}"}})
    if not out:
        raise SourceChanged("MEI.v2: no values")
    return out


def parse_bom_soi(text: str) -> list[dict]:
    """BoM soiplaintext.html: <pre> `Year Jan ... Dec` whitespace table, SOI x10 units
    (Troup SOI, roughly -35..+35); blank for months not yet published."""
    m = re.search(r"<pre>(.*?)</pre>", text, re.DOTALL | re.IGNORECASE)
    if not m or "Monthly Southern Oscillation Index" not in text:
        raise SourceChanged("BoM SOI: <pre> table not found")
    out = []
    rows = m.group(1).splitlines()
    if not rows or not any(r.split()[:2] == ["Year", "Jan"] for r in rows if r.strip()):
        raise SourceChanged("BoM SOI: header 'Year Jan ...' not found")
    for ln in rows:
        p = ln.split()
        if not p or not p[0].isdigit():
            continue
        year = int(p[0])
        vals = p[1:]
        if len(vals) > 12:
            raise SourceChanged(f"BoM SOI: too many values in {ln!r}")
        for mth, raw in enumerate(vals, start=1):
            out.append({"series": "bom_soi", "ts": _mid(year, mth), "value": float(raw),
                        "unit": "soi"})
    if not out:
        raise SourceChanged("BoM SOI: no values")
    return out


def _doy_index(d: date) -> int:
    """Climate Reanalyzer aligns years and climatology by day-of-year slot (the
    same index in each 366-long array), so we do too, to match their anomalies."""
    return d.timetuple().tm_yday - 1


def parse_cr_daily(payload: list, series: tuple[str, str, str], years_back: int = 2,
                   clim_key: str = "1991-2020") -> list[dict]:
    """Climate Reanalyzer json_2clim: [{name: '2026'|'Preliminary'|'1991-2020', data: [366]}].

    Year arrays are indexed from Jan 1 (non-leap years leave slot 365 null).
    'Preliminary' holds the most recent days before they become final; they are
    stored with meta.preliminary and overwritten when the final value lands.
    `series` = (sst, anomaly vs clim_key, climatology line for the latest year)."""
    s_sst, s_anom, s_clim = series
    if not isinstance(payload, list) or not payload:
        raise SourceChanged("Climate Reanalyzer: expected a non-empty list")
    by_name = {}
    for e in payload:
        if not isinstance(e, dict) or "name" not in e or not isinstance(e.get("data"), list):
            raise SourceChanged("Climate Reanalyzer: entry without name/data")
        by_name[str(e["name"])] = e["data"]
    years = sorted(int(n) for n in by_name if re.fullmatch(r"\d{4}", n))
    clim = by_name.get(clim_key)
    if not years or clim is None or len(clim) != 366:
        raise SourceChanged(f"Climate Reanalyzer: no year arrays or no {clim_key} climatology")
    last_year = years[-1]
    out: list[dict] = []

    def emit(d: date, v: float, prelim: bool) -> None:
        meta = {"preliminary": True} if prelim else None
        out.append({"series": s_sst, "ts": d.isoformat(), "value": round(v, 3),
                    "unit": "degC", "meta": meta})
        c = clim[_doy_index(d)]
        if c is not None:
            out.append({"series": s_anom, "ts": d.isoformat(),
                        "value": round(v - c, 3), "unit": "degC",
                        "meta": {"baseline": clim_key, **(meta or {})}})

    for y in years:
        if y < last_year - years_back:
            continue
        start = date(y, 1, 1)
        for i, v in enumerate(by_name[str(y)]):
            if v is None:
                continue
            d = start + timedelta(days=i)
            if d.year != y:
                raise SourceChanged(f"Climate Reanalyzer: {y} has a value past Dec 31")
            emit(d, float(v), False)
    finals = {r["ts"] for r in out if r["series"] == s_sst}
    prelim = by_name.get("Preliminary") or []
    start = date(last_year, 1, 1)
    for i, v in enumerate(prelim):
        if v is None:
            continue
        d = start + timedelta(days=i)
        if d.year == last_year and d.isoformat() not in finals:
            emit(d, float(v), True)
    if not any(r["series"] == s_sst for r in out):
        raise SourceChanged("Climate Reanalyzer: no recent daily values")
    # climatology line for every observed day (the chart's "normal"); never future-dated
    for r in [r for r in out if r["series"] == s_sst]:
        cv = clim[_doy_index(date.fromisoformat(r["ts"]))]
        if cv is not None:
            out.append({"series": s_clim, "ts": r["ts"], "value": cv, "unit": "degC",
                        "meta": {"baseline": clim_key}})
    return out


# ---------------------------------------------------------------- collectors


def _store(source: str, rows: list[dict], ctx: RunContext) -> int:
    n = db.upsert_observations(source, rows)
    latest: dict[str, tuple[str, float]] = {}
    for r in rows:
        cur = latest.get(r["series"])
        if cur is None or r["ts"] > cur[0]:
            latest[r["series"]] = (r["ts"], r["value"])
    ctx.notes["latest"] = {k: {"ts": v[0], "value": v[1]} for k, v in sorted(latest.items())}
    return n


class _TextIndex(Collector):
    category = "ocean_index"
    interval_s = 6 * 3600
    parser = staticmethod(lambda text: [])  # overridden

    async def collect(self, ctx: RunContext) -> int:
        r = await ctx.get(self.endpoint)
        return _store(self.name, type(self).parser(r.text), ctx)


class CpcOni(_TextIndex):
    name = "cpc_oni"
    freshness_basis = "observations"
    max_age_s = 90 * DAY  # JJA is dated Jul 15 and JAS only lands with the 2nd-Thursday update in October (~85 d)
    title = "Oceanic Nino Index (ONI)"
    provider = "NOAA CPC"
    homepage = ("https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/"
                "ensostuff/ONI_v5.php")
    endpoint = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
    description = ("3-month running mean of ERSSTv5 Nino 3.4 SST anomalies. The official NOAA "
                   "El Nino index (+0.5 = El Nino threshold). Series: oni, oni_total.")
    parser = staticmethod(parse_oni)


class CpcRoni(_TextIndex):
    name = "cpc_roni"
    freshness_basis = "observations"
    max_age_s = 90 * DAY  # same cadence as ONI
    title = "Relative Oceanic Nino Index (RONI)"
    provider = "NOAA CPC"
    homepage = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/"
    endpoint = "https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt"
    description = ("Nino 3.4 anomaly relative to the tropical-mean anomaly (removes the "
                   "global warming trend). CPC's primary index since 2026. Series: roni.")
    parser = staticmethod(parse_roni)


class CpcWeeklySst(_TextIndex):
    name = "cpc_weekly_sst"
    freshness_basis = "observations"
    max_age_s = 12 * DAY  # week centred on a Wednesday, published the next Monday
    title = "Weekly Nino region SST (OISST)"
    provider = "NOAA CPC"
    homepage = "https://www.cpc.ncep.noaa.gov/data/indices/"
    endpoint = "https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for"
    description = ("Weekly OISST.v2 SST and anomaly (1991-2020 base) for Nino 1+2, 3, 3.4, 4. "
                   "Series: nino{12,3,34,4}_weekly_sst / _weekly_anom.")
    parser = staticmethod(parse_weekly_sst)


class CpcSoi(_TextIndex):
    name = "cpc_soi"
    freshness_basis = "observations"
    max_age_s = 60 * DAY  # monthly value dated the 15th, published early the next month
    title = "Southern Oscillation Index (CPC, standardized)"
    provider = "NOAA CPC"
    homepage = "https://www.cpc.ncep.noaa.gov/data/indices/"
    endpoint = "https://www.cpc.ncep.noaa.gov/data/indices/soi"
    description = ("Standardized Tahiti minus Darwin sea-level pressure. Sustained negative "
                   "values = El Nino-like atmosphere. Series: soi.")
    parser = staticmethod(parse_cpc_soi)


class PslMei(_TextIndex):
    name = "psl_mei"
    freshness_basis = "observations"
    max_age_s = 80 * DAY  # bi-monthly season dated the 1st of its 2nd month, published ~10th of the next
    title = "Multivariate ENSO Index (MEI.v2)"
    provider = "NOAA PSL"
    homepage = "https://psl.noaa.gov/enso/mei/"
    endpoint = "https://psl.noaa.gov/enso/mei/data/meiv2.data"
    description = ("Bi-monthly combined ocean-atmosphere ENSO index (SLP, SST, winds, OLR). "
                   "Series: mei_v2 (ts = 1st of the season's second month).")
    parser = staticmethod(parse_mei)


class BomSoi(Collector):
    name = "bom_soi"
    freshness_basis = "observations"
    max_age_s = 60 * DAY  # monthly value dated the 15th
    title = "Southern Oscillation Index (BoM, Troup)"
    category = "ocean_index"
    provider = "Australian Bureau of Meteorology"
    homepage = "http://www.bom.gov.au/climate/enso/"
    # www.bom.gov.au blocks non-browser clients (403, "does not support web scraping")
    # and points to its anonymous FTP channel, which serves the same monthly table.
    endpoint = "ftp://ftp.bom.gov.au/anon/home/ncc/www/sco/soi/soiplaintext.html"
    interval_s = 6 * 3600
    description = ("BoM monthly SOI (Troup method, x10 scale; below -7 sustained = El Nino). "
                   "Fetched from BoM's anonymous FTP because the website blocks bots. "
                   "Series: bom_soi.")

    def fetch(self) -> str:
        req = urllib.request.Request(self.endpoint, headers={"User-Agent": settings.user_agent})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("latin-1")

    async def collect(self, ctx: RunContext) -> int:
        text = await asyncio.to_thread(self.fetch)
        ctx.notes["transport"] = "ftp"
        return _store(self.name, parse_bom_soi(text), ctx)


class _ClimateReanalyzer(Collector):
    category = "ocean_index"
    provider = "Climate Reanalyzer (Univ. of Maine) / NOAA OISST v2.1"
    homepage = "https://climatereanalyzer.org/clim/sst_daily/"
    interval_s = 6 * 3600
    series: tuple[str, str, str] = ("", "", "")

    async def collect(self, ctx: RunContext) -> int:
        r = await ctx.get(self.endpoint)
        try:
            payload = r.json()
        except json.JSONDecodeError as e:
            raise SourceChanged(f"not JSON: {e}") from e
        return _store(self.name, parse_cr_daily(payload, self.series), ctx)


class CrWorldSst(_ClimateReanalyzer):
    name = "cr_world_sst"
    freshness_basis = "observations"
    max_age_s = 4 * DAY  # daily OISST, 1-2 days behind
    title = "Daily world sea surface temperature (60S-60N)"
    endpoint = ("https://climatereanalyzer.org/clim/sst_daily/json_2clim/"
                "oisst2.1_world2_sst_day.json")
    description = ("Daily area-mean SST 60S-60N from OISST v2.1, last ~3 years, plus the "
                   "1991-2020 mean. Series: world_sst_daily, world_sst_anom, "
                   "world_sst_clim.")
    series = ("world_sst_daily", "world_sst_anom", "world_sst_clim")


class CrNino34Daily(_ClimateReanalyzer):
    name = "cr_nino34_daily"
    freshness_basis = "observations"
    max_age_s = 4 * DAY  # daily OISST, 1-2 days behind
    title = "Daily Nino 3.4 SST"
    endpoint = ("https://climatereanalyzer.org/clim/sst_daily/json_2clim/"
                "oisst2.1_nino3.4_sst_day.json")
    description = ("Daily OISST v2.1 Nino 3.4 (5S-5N, 170W-120W) SST and anomaly vs "
                   "1991-2020, last ~3 years. Faster than the weekly CPC value. "
                   "Series: nino34_daily_sst, nino34_daily_anom, nino34_daily_clim.")
    series = ("nino34_daily_sst", "nino34_daily_anom", "nino34_daily_clim")


COLLECTORS = [CpcOni, CpcRoni, CpcWeeklySst, CpcSoi, PslMei, BomSoi, CrWorldSst, CrNino34Daily]
