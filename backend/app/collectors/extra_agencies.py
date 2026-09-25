"""Other agencies' deep sources (all keyless, verified live 2026-09-24).

- noaa_sla_regions      NOAA CoastWatch blended satellite sea level anomaly (daily, 0.25 deg),
                        averaged over Nino 3.4, Nino 1+2, the western Pacific warm pool, the
                        South China Sea, the Gulf of Thailand and the sea around Koh Samui.
- c3s_climate_pulse     Copernicus C3S Climate Pulse: daily ERA5 global air temperature and
                        60S-60N sea surface temperature with 1991-2020 anomalies.
- ncei_cag              NOAA NCEI Climate at a Glance: global and Asia monthly anomalies.
- ncei_monthly_report   NOAA NCEI monthly global climate / drought / cyclone reports (RSS).
- metoffice_hadobs      UK Met Office Hadley Centre HadCRUT5 + HadSST4 monthly anomalies.
- ecmwf_seas5_asia      ECMWF SEAS5 seasonal outlook maps for Asia: 3-month rain and
                        temperature (open charts API, CC-BY-4.0). The Nino plume is
                        extra_ocean.ecmwf_nino_plume, not duplicated here.
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import ClassVar

import feedparser
import httpx

from .. import db
from .base import DAY, HOUR, Collector, RunContext, SourceChanged


def _latest_notes(rows: list[dict], ctx: RunContext) -> None:
    latest: dict[str, tuple[str, float]] = {}
    for r in rows:
        cur = latest.get(r["series"])
        if cur is None or r["ts"] > cur[0]:
            latest[r["series"]] = (r["ts"], r["value"])
    ctx.notes["latest"] = {k: {"ts": v[0], "value": v[1]} for k, v in sorted(latest.items())}


def _mid(y: int, m: int) -> str:
    return date(y, m, 15).isoformat()


# =========================================================================== sea level

SLA_DATASET = "https://coastwatch.noaa.gov/erddap/griddap/noaacwBLENDEDsshDaily"
SLA_INFO = "https://coastwatch.noaa.gov/cw_html/SSH_SeaLevelAnomaly.html"
SLA_TIMEOUT = httpx.Timeout(90.0, connect=20.0)
# id -> (series, label, south, north, west, east, stride in 0.25 deg cells)
SLA_REGIONS: dict[str, tuple[str, str, float, float, float, float, int]] = {
    "nino34": ("sla_nino34", "Nino 3.4 box (5S-5N, 170W-120W)",
               -4.875, 4.875, -169.875, -120.125, 4),
    "nino12": ("sla_nino12", "Nino 1+2 box off Peru (10S-0, 90W-80W)",
               -9.875, -0.125, -89.875, -80.125, 4),
    "west_pacific": ("sla_west_pacific", "Western Pacific warm pool (5S-5N, 130E-160E)",
                     -4.875, 4.875, 130.125, 159.875, 4),
    "south_china_sea": ("sla_south_china_sea", "South China Sea (0-21N, 105E-121E)",
                        0.125, 20.875, 105.125, 120.875, 4),
    "gulf_thailand": ("sla_gulf_thailand", "Gulf of Thailand (6N-13N, 99E-105E)",
                      6.125, 12.875, 99.125, 104.875, 2),
    "samui": ("sla_samui_coast", "Sea around Koh Samui (9.1N-10.4N, 99.9E-100.6E)",
              9.125, 10.375, 99.875, 100.625, 1),
}
SLA_LOOKBACK_DAYS = 15


def sla_url(region: str, days: int = SLA_LOOKBACK_DAYS) -> str:
    _, _, s, n, w, e, k = SLA_REGIONS[region]
    return (f"{SLA_DATASET}.csv?sla[last-{days - 1}:last][({s}):{k}:({n})]"
            f"[({w}):{k}:({e})]")


def parse_sla_csv(text: str, region: str) -> list[dict]:
    """ERDDAP griddap CSV (header, units row, then time,lat,lon,sla in metres) -> one
    area-mean row per day, in centimetres. NaN (land / no data) cells are skipped."""
    lines = text.splitlines()
    if len(lines) < 2 or lines[0].strip() != "time,latitude,longitude,sla":
        raise SourceChanged("ERDDAP SLA: header is not time,latitude,longitude,sla")
    if lines[1].split(",")[-1].strip() != "m":
        raise SourceChanged("ERDDAP SLA: sla unit is not metres")
    series, label, *_ = SLA_REGIONS[region]
    acc: dict[str, list[float]] = defaultdict(list)
    total: dict[str, int] = defaultdict(int)
    for row in csv.reader(lines[2:]):
        if len(row) != 4:
            continue
        day = row[0][:10]
        total[day] += 1
        if row[3] in ("", "NaN"):
            continue
        v = float(row[3])
        if abs(v) < 3:  # fill value is -3.2767
            acc[day].append(v)
    out = []
    for day, vals in sorted(acc.items()):
        if len(vals) < max(1, total[day] // 4):  # too few ocean cells with data that day
            continue
        out.append({"series": series, "ts": day,
                    "value": round(100 * sum(vals) / len(vals), 2), "unit": "cm",
                    "meta": {"region": label, "cells": len(vals), "cells_total": total[day],
                             "reference": "DTU15 mean sea surface (includes long-term rise)"}})
    return out


def sla_gradient(rows: list[dict]) -> list[dict]:
    """Nino 3.4 minus western Pacific: the east-west tilt of the Pacific sea surface.
    The global rise is in both terms and cancels out, leaving the ENSO signal."""
    east = {r["ts"]: r["value"] for r in rows if r["series"] == "sla_nino34"}
    west = {r["ts"]: r["value"] for r in rows if r["series"] == "sla_west_pacific"}
    return [{"series": "sla_pacific_east_minus_west", "ts": d,
             "value": round(east[d] - west[d], 2), "unit": "cm",
             "meta": {"formula": "sla_nino34 - sla_west_pacific"}}
            for d in sorted(set(east) & set(west))]


class NoaaSlaRegions(Collector):
    name = "noaa_sla_regions"
    title = "Satellite sea level anomaly -- Pacific, South China Sea, Gulf of Thailand, Samui"
    category = "maritime"
    provider = "NOAA NESDIS CoastWatch (blended multi-mission altimetry, ERDDAP)"
    homepage = SLA_INFO
    endpoint = SLA_DATASET
    interval_s = 12 * HOUR
    freshness_basis = "observations"
    max_age_s = 5 * DAY  # daily grid, about 2 days behind
    description = (
        "How high the sea surface stands compared with the long-term mean, measured by radar "
        "satellites (Sentinel-6, Jason-3, SWOT, Sentinel-3, CryoSat-2). El Nino piles warm "
        "water up in the east Pacific (+20 to +40 cm) and lowers it in the west. Daily box "
        "averages in cm: sla_nino34, sla_nino12, sla_west_pacific, sla_south_china_sea, "
        "sla_gulf_thailand, sla_samui_coast, and the east-west tilt "
        "sla_pacific_east_minus_west (global sea level rise cancels out in it).")

    async def _region(self, ctx: RunContext, region: str) -> list[dict]:
        r = await ctx.get(sla_url(region), timeout=SLA_TIMEOUT)
        return parse_sla_csv(r.text, region)

    async def collect(self, ctx: RunContext) -> int:
        rows: list[dict] = []
        state: dict[str, str] = {}
        for region in SLA_REGIONS:  # sequential: ERDDAP is a shared, sometimes slow server
            try:
                got = await self._region(ctx, region)
                rows += got
                state[region] = f"{len(got)} days"
            except SourceChanged:
                raise
            except (httpx.TransportError, httpx.HTTPStatusError) as e:
                state[region] = f"error: {type(e).__name__}: {e}"[:160]
                status = getattr(getattr(e, "response", None), "status_code", 0)
                if not isinstance(e, httpx.HTTPStatusError) or status >= 500:
                    # the server is down or overloaded (seen: 502/503 after 60 s): asking
                    # for the other regions would only hit the run time limit
                    break
        ctx.notes["regions"] = state
        if not rows:
            raise RuntimeError(f"ERDDAP SLA: no region answered: {state}")
        rows += sla_gradient(rows)
        _latest_notes(rows, ctx)
        return db.upsert_observations(self.name, rows)


# =========================================================================== Climate Pulse

PULSE_BASE = "https://sites.ecmwf.int/data/climatepulse/data/series/"
PULSE_2T_URL = PULSE_BASE + "era5_daily_series_2t_global.csv"
PULSE_SST_URL = PULSE_BASE + "era5_daily_series_sst_60S-60N_ocean.csv"


def parse_pulse(text: str, value_col: str, series: tuple[str, str],
                years_back: int = 3, today: date | None = None) -> list[dict]:
    """Climate Pulse CSV: '#' comment lines, then `date,<var>,clim_91-20,ano_91-20,status`."""
    body = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    if not body:
        raise SourceChanged("Climate Pulse: no data lines")
    rdr = csv.DictReader(body)
    need = {"date", value_col, "ano_91-20", "status"}
    if not rdr.fieldnames or not need <= set(rdr.fieldnames):
        raise SourceChanged(f"Climate Pulse: columns {rdr.fieldnames} lack {need}")
    cut = ((today or datetime.now(UTC).date()) - timedelta(days=366 * years_back)).isoformat()
    s_abs, s_anom = series
    out = []
    for row in rdr:
        d = row["date"]
        if d < cut or not row[value_col]:
            continue
        meta = {"status": row["status"].lower(), "baseline": "1991-2020"}
        out.append({"series": s_abs, "ts": d, "value": float(row[value_col]), "unit": "degC",
                    "meta": meta})
        if row["ano_91-20"]:
            out.append({"series": s_anom, "ts": d, "value": float(row["ano_91-20"]),
                        "unit": "degC", "meta": meta})
    if not out:
        raise SourceChanged("Climate Pulse: no recent values")
    return out


class C3sClimatePulse(Collector):
    name = "c3s_climate_pulse"
    title = "Copernicus Climate Pulse -- daily global air and sea temperature (ERA5)"
    category = "ocean_index"
    provider = "Copernicus Climate Change Service (C3S) / ECMWF"
    homepage = "https://pulse.climate.copernicus.eu/"
    endpoint = PULSE_2T_URL
    interval_s = 6 * HOUR
    freshness_basis = "observations"
    max_age_s = 5 * DAY  # 2 days behind real time (preliminary, final at ~5 days)
    description = (
        "Europe's daily global thermometer: the planet's average air temperature at 2 m and "
        "the average sea surface temperature between 60S and 60N, with the difference from "
        "1991-2020. A strong El Nino pushes both to record highs a few months after its "
        "peak. Series: era5_global_t2m, era5_global_t2m_anom, era5_sst_6060, "
        "era5_sst_6060_anom (the last 2 days are preliminary).")

    async def collect(self, ctx: RunContext) -> int:
        rows = parse_pulse((await ctx.get(PULSE_2T_URL)).text, "2t",
                           ("era5_global_t2m", "era5_global_t2m_anom"))
        rows += parse_pulse((await ctx.get(PULSE_SST_URL)).text, "sst",
                            ("era5_sst_6060", "era5_sst_6060_anom"))
        _latest_notes(rows, ctx)
        return db.upsert_observations(self.name, rows)


# =========================================================================== NCEI

CAG_BASE = "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series/"


def cag_url(path: str, start: int, year: int | None = None) -> str:
    """NCEI rejects an end year in the future (404), so it is always the current year."""
    return f"{CAG_BASE}{path}/1/0/{start}-{year or datetime.now(UTC).year}/data.csv"


CAG_GLOBAL = ("globe/land_ocean", 1850)
CAG_ASIA = ("asia/land", 1910)
CAG_GLOBAL_URL = cag_url(*CAG_GLOBAL)
NCEI_RSS_URL = "https://www.ncei.noaa.gov/access/monitoring/monthly-report/rss.xml"


def parse_cag_csv(text: str, series: str) -> list[dict]:
    """CAG CSV: '#' header lines (title, units, base period), then `Date,Anomaly` YYYYMM."""
    base = re.search(r"# Base Period:\s*(\S+)", text)
    body = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    if not body or not body[0].lower().startswith("date,"):
        raise SourceChanged("Climate at a Glance: no 'Date,...' header")
    out = []
    for ln in body[1:]:
        p = ln.split(",")
        if len(p) != 2 or not re.fullmatch(r"\d{6}", p[0]):
            raise SourceChanged(f"Climate at a Glance: unexpected row {ln!r}")
        if p[1] in ("", "-999", "-99.99"):
            continue
        out.append({"series": series, "ts": _mid(int(p[0][:4]), int(p[0][4:])),
                    "value": float(p[1]), "unit": "degC",
                    "meta": {"baseline": base.group(1) if base else None}})
    if not out:
        raise SourceChanged("Climate at a Glance: no values")
    return out


class NceiClimateAtAGlance(Collector):
    name = "ncei_cag"
    title = "NOAA NCEI Climate at a Glance -- global and Asia monthly temperature anomaly"
    category = "ocean_index"
    provider = "NOAA National Centers for Environmental Information (NOAAGlobalTemp)"
    homepage = "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series"
    endpoint = CAG_GLOBAL_URL
    interval_s = 12 * HOUR
    freshness_basis = "observations"
    max_age_s = 60 * DAY  # month M dated the 15th, published ~10th of month M+1
    description = (
        "NOAA's official monthly temperature departures from the 1901-2000 average: the whole "
        "globe (land + ocean) and the Asian land mass. Shows how the El Nino year stacks up "
        "against the record. Series: ncei_global_anom, ncei_asia_land_anom.")

    async def collect(self, ctx: RunContext) -> int:
        rows = parse_cag_csv((await ctx.get(cag_url(*CAG_GLOBAL))).text, "ncei_global_anom")
        rows += parse_cag_csv((await ctx.get(cag_url(*CAG_ASIA))).text, "ncei_asia_land_anom")
        _latest_notes(rows, ctx)
        return db.upsert_observations(self.name, rows)


NCEI_KEEP = re.compile(r"Global Climate Report|Global Drought|Tropical Cyclones",
                       re.IGNORECASE)


def parse_ncei_rss(content: bytes) -> list[dict]:
    f = feedparser.parse(content)
    if not f.entries:
        raise SourceChanged("NCEI monthly report RSS: no entries")
    out = []
    for e in f.entries:
        title = e.get("title", "")
        if not NCEI_KEEP.search(title):
            continue
        pub = (datetime(*e.published_parsed[:6], tzinfo=UTC).isoformat()
               if e.get("published_parsed") else None)
        summary = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", e.get("summary", ""))).strip()
        out.append({"ext_id": e.get("id") or e.get("link"), "kind": "official", "lang": "en",
                    "title": title, "summary": summary[:600], "url": e.get("link"),
                    "author": "NOAA NCEI", "published_at": pub, "tags": []})
    return out


class NceiMonthlyReport(Collector):
    name = "ncei_monthly_report"
    title = "NOAA NCEI monthly global climate, drought and tropical cyclone reports"
    category = "official"
    provider = "NOAA National Centers for Environmental Information"
    homepage = "https://www.ncei.noaa.gov/access/monitoring/monthly-report/"
    endpoint = NCEI_RSS_URL
    interval_s = 12 * HOUR
    freshness_basis = "feed"
    max_age_s = 40 * DAY  # one set per month, around the 10th
    description = (
        "NOAA's monthly State of the Climate reports (global temperature and rain, global "
        "drought, tropical cyclones), with their headline numbers. Feed items (kind official).")

    async def collect(self, ctx: RunContext) -> int:
        items = [i for i in parse_ncei_rss((await ctx.get(NCEI_RSS_URL)).content)
                 if i["ext_id"]]
        return db.upsert_feed_items(self.name, items) if items else 0


# =========================================================================== Met Office

HADCRUT_URL = ("https://www.metoffice.gov.uk/hadobs/hadcrut5/data/HadCRUT.5.1.0.0/analysis/"
               "diagnostics/HadCRUT.5.1.0.0.analysis.summary_series.global.monthly.csv")
HADSST_GLOBE_URL = ("https://www.metoffice.gov.uk/hadobs/hadsst4/data/data/"
                    "HadSST.4.2.0.0_monthly_GLOBE.csv")
HADSST_TROP_URL = ("https://www.metoffice.gov.uk/hadobs/hadsst4/data/data/"
                   "HadSST.4.2.0.0_monthly_TROP.csv")


def parse_hadcrut(text: str) -> list[dict]:
    rdr = csv.DictReader(io.StringIO(text))
    if not rdr.fieldnames or rdr.fieldnames[:2] != ["Time", "Anomaly (deg C)"]:
        raise SourceChanged(f"HadCRUT5: unexpected columns {rdr.fieldnames}")
    out = []
    for row in rdr:
        m = re.fullmatch(r"(\d{4})-(\d{2})", row["Time"] or "")
        if not m or not row["Anomaly (deg C)"]:
            continue
        out.append({"series": "hadcrut5_global_anom", "ts": _mid(int(m[1]), int(m[2])),
                    "value": round(float(row["Anomaly (deg C)"]), 3), "unit": "degC",
                    "meta": {"baseline": "1961-1990",
                             "ci95": [round(float(row["Lower confidence limit (2.5%)"]), 3),
                                      round(float(row["Upper confidence limit (97.5%)"]), 3)]}})
    if not out:
        raise SourceChanged("HadCRUT5: no values")
    return out


def parse_hadsst(text: str, series: str) -> list[dict]:
    rdr = csv.DictReader(io.StringIO(text))
    if not rdr.fieldnames or rdr.fieldnames[:4] != ["year", "month", "anomaly",
                                                     "total_uncertainty"]:
        raise SourceChanged(f"HadSST4: unexpected columns {rdr.fieldnames}")
    out = []
    for row in rdr:
        if not row["anomaly"]:
            continue
        out.append({"series": series, "ts": _mid(int(row["year"]), int(row["month"])),
                    "value": round(float(row["anomaly"]), 3), "unit": "degC",
                    "meta": {"baseline": "1961-1990",
                             "uncertainty": round(float(row["total_uncertainty"]), 3)}})
    if not out:
        raise SourceChanged("HadSST4: no values")
    return out


class MetOfficeHadObs(Collector):
    name = "metoffice_hadobs"
    title = "UK Met Office HadCRUT5 and HadSST4 -- monthly global and tropical anomalies"
    category = "ocean_index"
    provider = "UK Met Office Hadley Centre (with UEA CRU for HadCRUT5)"
    homepage = "https://www.metoffice.gov.uk/hadobs/"
    endpoint = HADCRUT_URL
    interval_s = 12 * HOUR
    freshness_basis = "observations"
    max_age_s = 75 * DAY  # month M dated the 15th, released late in month M+1
    description = (
        "The UK's long-running global records, relative to 1961-1990: HadCRUT5 (land + sea "
        "surface temperature, with a 95 % range) and HadSST4 (sea surface only, global and "
        "tropics 30S-30N). The tropical ocean warms fastest in an El Nino. Series: "
        "hadcrut5_global_anom, hadsst4_global_anom, hadsst4_tropics_anom.")

    async def collect(self, ctx: RunContext) -> int:
        rows = parse_hadcrut((await ctx.get(HADCRUT_URL)).text)
        rows += parse_hadsst((await ctx.get(HADSST_GLOBE_URL)).text, "hadsst4_global_anom")
        rows += parse_hadsst((await ctx.get(HADSST_TROP_URL)).text, "hadsst4_tropics_anom")
        _latest_notes(rows, ctx)
        return db.upsert_observations(self.name, rows)


# =========================================================================== ECMWF

ECMWF_API = "https://charts.ecmwf.int/opencharts-api/v1/products/"
ECMWF_PAGE = "https://charts.ecmwf.int/products/seasonal_system5_standard_rain"
# The Nino plume itself is collected by extra_ocean.ecmwf_nino_plume; here only the
# regional outlook maps. product, label, how many 3-month seasons ahead to keep, how to read
ECMWF_CHARTS: tuple[dict, ...] = (
    {"id": "asia_rain", "product": "seasonal_system5_standard_rain", "seasons": 4,
     "title": "SEAS5 3-month rain outlook, Asia",
     "how_to_read": "Probability of the most likely rain category vs 1993-2016. Brown/orange "
                    "= drier than normal favoured (darker = more likely, up to 70-100 %), "
                    "green/teal = wetter than normal favoured, white = no clear signal. Look "
                    "at southern Thailand and the Gulf of Thailand."},
    {"id": "asia_t2m", "product": "seasonal_system5_standard_2mtm", "seasons": 2,
     "title": "SEAS5 3-month temperature outlook, Asia",
     "how_to_read": "Probability of the most likely temperature category vs 1993-2016. "
                    "Orange/red = warmer than normal favoured, blue = colder, white = no "
                    "clear signal."},
)
SEASON_LETTERS = "JFMAMJJASOND"


def season_label(valid_time: str) -> str:
    """'2026-10-02T00:00:00Z' -> 'OND 2026' (3-month mean starting that month)."""
    y, m = int(valid_time[:4]), int(valid_time[5:7])
    return "".join(SEASON_LETTERS[(m - 1 + i) % 12] for i in range(3)) + f" {y}"


def _available(payload: dict, dim: str) -> list[str]:
    """ECMWF answers a request for an unavailable time with the list of available ones."""
    msg = " ".join(payload.get("error") or []) + str(payload.get("message") or "")
    m = re.search(rf"available {dim} \[([^\]]*)\]", msg)
    if not m:
        raise SourceChanged(f"ECMWF: {dim} list not found in the error message")
    times = re.findall(r"'(\d{4}-\d{2}-\d{2}T\d{2}:00:00Z)'", m.group(1))
    if not times:
        raise SourceChanged(f"ECMWF: empty {dim} list")
    return times


def parse_base_times(payload: dict) -> list[str]:
    return sorted(_available(payload, "base_time"), reverse=True)


def parse_valid_times(payload: dict) -> list[str]:
    return sorted(_available(payload, "valid_time"))


def parse_chart(payload: dict) -> str:
    try:
        link = payload["data"]["link"]
    except (KeyError, TypeError):
        raise SourceChanged(f"ECMWF chart: no data.link ({str(payload)[:160]})") from None
    if link.get("type") != "image/png" or not link.get("href", "").startswith("https://"):
        raise SourceChanged(f"ECMWF chart: unexpected link {link}")
    return link["href"]


class EcmwfSeas5Asia(Collector):
    name = "ecmwf_seas5_asia"
    title = "ECMWF SEAS5 -- 3-month rain and temperature outlook maps for Asia"
    category = "official"
    provider = "European Centre for Medium-Range Weather Forecasts (open charts, CC-BY-4.0)"
    homepage = ECMWF_PAGE
    endpoint = ECMWF_API + "seasonal_system5_standard_rain/"
    interval_s = 12 * HOUR
    freshness_basis = "feed"
    max_age_s = 40 * DAY  # base time = 1st of the month, charts out ~5th, next ~5th
    description = (
        "Europe's seasonal forecast (SEAS5, 51 runs) as maps: are the next 3-month periods "
        "likely to be wetter or drier, warmer or colder than normal over Asia, including "
        "southern Thailand? Rain for the next 4 overlapping seasons (covering Samui's "
        "monsoon peak and the dry season), temperature for the next 2. Chart images only. "
        "Status key: ecmwf_seas5_asia. (The Nino 3.4 plume is collector ecmwf_nino_plume.)")
    probe_time: ClassVar[str] = "2099-01-01T00:00:00Z"

    async def _probe(self, ctx: RunContext, product: str, params: dict) -> dict:
        r = await ctx.client.get(ECMWF_API + product + "/", params=params)
        ctx.last_status = r.status_code
        try:
            return r.json()
        except ValueError:
            raise SourceChanged(f"ECMWF {product}: probe answer is not JSON") from None

    async def collect(self, ctx: RunContext) -> int:
        first = ECMWF_CHARTS[0]["product"]
        base = parse_base_times(await self._probe(
            ctx, first, {"area": "ASIA", "base_time": self.probe_time}))[0]
        valid = parse_valid_times(await self._probe(
            ctx, first, {"area": "ASIA", "base_time": base, "valid_time": self.probe_time}))
        charts = []
        for c in ECMWF_CHARTS:
            for vt in valid[: c["seasons"]]:
                rr = await ctx.get(ECMWF_API + c["product"] + "/",
                                   params={"area": "ASIA", "base_time": base, "valid_time": vt})
                charts.append({"id": f"{c['id']}_{vt[:7]}", "kind": c["id"],
                               "title": f"{c['title']} -- {season_label(vt)}",
                               "season": season_label(vt), "valid_time": vt,
                               "url": parse_chart(rr.json()), "how_to_read": c["how_to_read"],
                               "page": f"https://charts.ecmwf.int/products/{c['product']}"})
        img = await ctx.client.get(charts[0]["url"])
        if img.status_code != 200 or not img.headers.get("content-type", "").startswith("image/"):
            raise SourceChanged(f"ECMWF chart image answered {img.status_code}")
        issued = base[:10]
        db.set_status("ecmwf_seas5_asia", {"base_time": base, "charts": charts,
                                           "climate_period": "1993-2016",
                                           "licence": "CC-BY-4.0 (c) ECMWF",
                                           "url": ECMWF_PAGE})
        ctx.notes.update(base_time=base, seasons=[season_label(v) for v in valid])
        return db.upsert_feed_items(self.name, [{
            "ext_id": issued, "kind": "official", "lang": "en",
            "title": f"ECMWF SEAS5 seasonal outlook for Asia, {base[:7]} run",
            "summary": "3-month rain and temperature outlook maps for Asia: "
                       + ", ".join(season_label(v) for v in valid[:4]) + ".",
            "url": ECMWF_PAGE, "image": charts[0]["url"], "author": "ECMWF",
            "published_at": issued, "tags": ["forecast", "thailand"]}])


COLLECTORS = [NoaaSlaRegions, C3sClimatePulse, NceiClimateAtAGlance, NceiMonthlyReport,
              MetOfficeHadObs, EcmwfSeas5Asia]
