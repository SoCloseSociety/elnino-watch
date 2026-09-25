"""Extra ENSO ocean sources (gap fill, 2026-09-24).

- cpc_enso_probs     NOAA CPC official ENSO probabilities + strength probabilities (status)
- cpc_heat_content   CPC equatorial upper-300 m heat content anomaly (observations)
- pmel_wwv           PMEL/TAO warm water volume + 0-300 m temperature (observations)
- jma_sst_indices    JMA Indian Ocean Dipole (DMI, west/east poles), NINO.WEST, NINO.3
- ecmwf_nino_plume   ECMWF SEAS5 Nino plume chart (status, image links)

Every parser works on the raw payload the agency serves and raises SourceChanged
when it no longer looks like the documented format. Monthly values are dated on
the month's 15th (CLAUDE.md convention).
"""

from __future__ import annotations

import html
import re
from datetime import date

from .. import db
from .base import DAY, HOUR, Collector, RunContext, SourceChanged

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
MONTH_NAMES = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September",
     "October", "November", "December"], start=1)}


def mid(year: int, month: int) -> str:
    return date(year, month, 15).isoformat()


def store_obs(source: str, rows: list[dict], ctx: RunContext) -> int:
    """Upsert + record the latest value of every series in the run notes."""
    if not rows:
        return 0
    n = db.upsert_observations(source, rows)
    latest: dict[str, tuple[str, float]] = {}
    for r in rows:
        cur = latest.get(r["series"])
        if cur is None or r["ts"] > cur[0]:
            latest[r["series"]] = (r["ts"], r["value"])
    ctx.notes["latest"] = {k: {"ts": v[0], "value": v[1]} for k, v in sorted(latest.items())}
    return n


def set_status_if_changed(key: str, value: dict, ignore: tuple[str, ...] = ()) -> bool:
    """Write a status document only when its content changed, so status.updated_at
    says when the source last published something new (freshness basis "status")."""
    cur = db.get_status(key)
    if cur is not None:
        old = {k: v for k, v in cur["value"].items() if k not in ignore}
        new = {k: v for k, v in value.items() if k not in ignore}
        if old == new:
            return False
    db.set_status(key, value)
    return True


def _text(markup: str) -> str:
    s = re.sub(r"<[^>]+>", " ", markup)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


# ------------------------------------------------------------ CPC ENSO probabilities

CPC_PROBS_URL = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/probabilities/"
CPC_STRENGTHS_URL = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/strengths/"
STRENGTH_KEYS = (
    "la_nina_very_strong", "la_nina_strong", "la_nina_moderate", "la_nina_weak", "neutral",
    "el_nino_weak", "el_nino_moderate", "el_nino_strong", "el_nino_very_strong",
)
STRENGTH_LABELS = {
    "la_nina_very_strong": "Very strong La Nina (index <= -2.0 C)",
    "la_nina_strong": "Strong La Nina (-2.0 to -1.5 C)",
    "la_nina_moderate": "Moderate La Nina (-1.5 to -1.0 C)",
    "la_nina_weak": "Weak La Nina (-1.0 to -0.5 C)",
    "neutral": "Neutral (-0.5 to +0.5 C)",
    "el_nino_weak": "Weak El Nino (+0.5 to +1.0 C)",
    "el_nino_moderate": "Moderate El Nino (+1.0 to +1.5 C)",
    "el_nino_strong": "Strong El Nino (+1.5 to +2.0 C)",
    "el_nino_very_strong": "Very strong El Nino (index >= +2.0 C)",
}
_ROW_RE = re.compile(
    r"<tr>\s*<th[^>]*>\s*<abbr>\s*([A-Z]{3})\s*<span[^>]*>([^<]*)</span>\s*</abbr>\s*</th>(.*?)</tr>",
    re.DOTALL)
_TD_RE = re.compile(r"<td>\s*(-?\d+(?:\.\d+)?)\s*</td>")
_ISSUED_RE = re.compile(r"<h2>\s*Issued\s+([A-Z][a-z]+)\s+(\d{4})\s*</h2>")


def _cpc_table(page: str, ncols: int, what: str) -> tuple[str, list[tuple[str, str, list[float]]]]:
    m = _ISSUED_RE.search(page)
    if not m or m.group(1) not in MONTH_NAMES:
        raise SourceChanged(f"CPC {what}: no 'Issued <Month> <Year>' heading")
    issued = f"{int(m.group(2)):04d}-{MONTH_NAMES[m.group(1)]:02d}"
    rows = []
    for season, months, body in _ROW_RE.findall(page):
        vals = [float(v) for v in _TD_RE.findall(body)]
        if len(vals) != ncols:
            raise SourceChanged(f"CPC {what}: season {season} has {len(vals)} cells, not {ncols}")
        rows.append((season, months.strip(), vals))
    if len(rows) < 3:
        raise SourceChanged(f"CPC {what}: {len(rows)} season rows")
    return issued, rows


def parse_cpc_enso_probs(probs_html: str, strengths_html: str) -> dict:
    if "La Ni" not in probs_html or "El Ni" not in probs_html:
        raise SourceChanged("CPC probabilities: La Nina / El Nino columns missing")
    if "Index &ge; 2.0" not in strengths_html and "Index ≥ 2.0" not in strengths_html:
        raise SourceChanged("CPC strengths: the 'Index >= 2.0 C' column is gone")
    issued, prob_rows = _cpc_table(probs_html, 3, "probabilities")
    issued_s, str_rows = _cpc_table(strengths_html, 9, "strengths")
    probabilities = []
    for season, months, (ln, ne, en) in prob_rows:
        if abs(ln + ne + en - 100) > 1.5:
            raise SourceChanged(f"CPC probabilities: {season} does not sum to 100")
        probabilities.append({"season": season, "months": months, "la_nina": ln,
                              "neutral": ne, "el_nino": en})
    strengths = []
    for season, months, vals in str_rows:
        if abs(sum(vals) - 100) > 1.5:
            raise SourceChanged(f"CPC strengths: {season} does not sum to 100")
        strengths.append({"season": season, "months": months,
                          "categories": dict(zip(STRENGTH_KEYS, vals, strict=True))})
    first = strengths[0]
    top = max(STRENGTH_KEYS, key=lambda k: first["categories"][k])
    summary = (f"CPC ({issued}): {STRENGTH_LABELS[top]} is the most likely category for "
               f"{first['season']} ({first['months']}), {first['categories'][top]:.0f}%. "
               f"El Nino chance {probabilities[0]['el_nino']:.0f}% for {probabilities[0]['season']}.")
    return {"issued": issued, "strengths_issued": issued_s, "url": CPC_PROBS_URL,
            "strengths_url": CPC_STRENGTHS_URL, "probabilities": probabilities,
            "strengths": strengths, "strength_labels": STRENGTH_LABELS, "summary": summary,
            "verification_index": "RONI (relative Nino-3.4 index), 1991-2020 base"}


class CpcEnsoProbs(Collector):
    name = "cpc_enso_probs"
    title = "CPC official ENSO probabilities + strength probabilities"
    category = "official"
    provider = "NOAA CPC"
    homepage = CPC_STRENGTHS_URL
    endpoint = CPC_PROBS_URL
    interval_s = 6 * HOUR
    freshness_basis = "status"
    freshness_status_key = "cpc_enso_probs"
    max_age_s = 45 * DAY  # issued monthly on the 2nd Thursday
    description = ("NOAA CPC's official ENSO outlook in numbers: the chance of La Nina / "
                   "neutral / El Nino for the next 9 overlapping seasons, and the chance of each "
                   "strength class (weak, moderate, strong, very strong). Updated monthly with "
                   "the ENSO Diagnostic Discussion. Status key `cpc_enso_probs`.")

    async def collect(self, ctx: RunContext) -> int:
        probs = (await ctx.get(CPC_PROBS_URL)).text
        strengths = (await ctx.get(CPC_STRENGTHS_URL)).text
        doc = parse_cpc_enso_probs(probs, strengths)
        changed = set_status_if_changed("cpc_enso_probs", doc)
        ctx.notes.update(issued=doc["issued"], changed=changed, summary=doc["summary"])
        return len(doc["probabilities"]) + len(doc["strengths"])


# ------------------------------------------------------------ CPC heat content

CPC_HC_URL = ("https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ocean/index/"
              "heat_content_index.txt")
HC_SERIES = ("heat_content_130e_80w_anom", "heat_content_160e_80w_anom",
             "heat_content_180w_100w_anom")


def parse_heat_content(text: str) -> list[dict]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 3 or "300m" not in lines[0] or "130E-80W" not in lines[1] \
            or "180W-100W" not in lines[1]:
        raise SourceChanged("CPC heat content: header changed")
    out = []
    for ln in lines[2:]:
        p = ln.split()
        if len(p) != 5:
            raise SourceChanged(f"CPC heat content: bad row {ln!r}")
        y, m = int(p[0]), int(p[1])
        for s, v in zip(HC_SERIES, p[2:], strict=True):
            out.append({"series": s, "ts": mid(y, m), "value": float(v), "unit": "degC",
                        "meta": {"base": "1981-2010", "depth": "0-300 m"}})
    if not out:
        raise SourceChanged("CPC heat content: no rows")
    return out


class CpcHeatContent(Collector):
    name = "cpc_heat_content"
    title = "Equatorial Pacific upper-ocean heat content (0-300 m)"
    category = "ocean_index"
    provider = "NOAA CPC"
    homepage = "https://www.cpc.ncep.noaa.gov/products/GODAS/"
    endpoint = CPC_HC_URL
    interval_s = 12 * HOUR
    freshness_basis = "observations"
    max_age_s = 60 * DAY  # monthly; the value for month M lands early in M+1
    description = ("Monthly average temperature anomaly of the top 300 m of the equatorial "
                   "Pacific (130E-80W, 160E-80W, 180W-100W). Warm water below the surface is "
                   "the fuel of El Nino: it leads the surface by months. Series "
                   "heat_content_*_anom (degC, 1981-2010 base).")

    async def collect(self, ctx: RunContext) -> int:
        return store_obs(self.name, parse_heat_content((await ctx.get(CPC_HC_URL)).text), ctx)


# ------------------------------------------------------------ PMEL warm water volume

PMEL_BASE = "https://www.pmel.noaa.gov/tao/wwv/data/"
# file -> (series prefix, what, unit scale)
PMEL_FILES = {
    "wwv.dat": ("wwv", "Warm Water Volume", 1e14),
    "wwv_west.dat": ("wwv_west", "Warm Water Volume", 1e14),
    "wwv_east.dat": ("wwv_east", "Warm Water Volume", 1e14),
    "t300.dat": ("t300", "Depth Averaged Temps", 1.0),
    "t300_west.dat": ("t300_west", "Depth Averaged Temps", 1.0),
    "t300_east.dat": ("t300_east", "Depth Averaged Temps", 1.0),
}
_PMEL_ROW = re.compile(r"^\s*(\d{4})(\d{2})\s+(-?[\d.]+E[+-]\d+)\s+(-?[\d.]*E[+-]\d+)\s*$")


def parse_pmel(text: str, fname: str) -> list[dict]:
    prefix, what, scale = PMEL_FILES[fname]
    first = text.lstrip().splitlines()[0] if text.strip() else ""
    if what not in first:
        raise SourceChanged(f"PMEL {fname}: header is not '{what} ...'")
    region = re.search(r"\d+N-\d+S,\s*\d+[EW]-\d+[EW]", first)
    unit = "1e14 m3" if scale != 1.0 else "degC"
    out = []
    for ln in text.splitlines():
        m = _PMEL_ROW.match(ln)
        if not m:
            continue
        y, mo = int(m.group(1)), int(m.group(2))
        total, anom = float(m.group(3)), float(m.group(4))
        meta = {"region": region.group(0) if region else None}
        out.append({"series": f"{prefix}_anom", "ts": mid(y, mo), "value": round(anom / scale, 4),
                    "unit": unit, "meta": meta})
        if prefix in ("wwv", "t300"):
            out.append({"series": f"{prefix}_total", "ts": mid(y, mo),
                        "value": round(total / scale, 4), "unit": unit, "meta": meta})
    if not out:
        raise SourceChanged(f"PMEL {fname}: no data rows")
    return out


class PmelWwv(Collector):
    name = "pmel_wwv"
    title = "Warm water volume + 0-300 m temperature (TAO/PMEL)"
    category = "ocean_index"
    provider = "NOAA PMEL (GTMBA / TAO)"
    homepage = "https://www.pmel.noaa.gov/tao/wwv/index.html"
    endpoint = PMEL_BASE + "wwv.dat"
    interval_s = 12 * HOUR
    freshness_basis = "observations"
    max_age_s = 60 * DAY
    description = ("Monthly volume of water warmer than 20 C above the thermocline in the "
                   "equatorial Pacific (5N-5S, 120E-80W), whole basin and west/east halves, plus "
                   "the 0-300 m average temperature. A high warm water volume before and during "
                   "an El Nino means more heat to discharge. Series wwv_anom (1e14 m3), "
                   "wwv_west_anom, wwv_east_anom, t300_anom (degC), t300_west_anom, t300_east_anom.")

    async def collect(self, ctx: RunContext) -> int:
        rows: list[dict] = []
        for fname in PMEL_FILES:
            rows += parse_pmel((await ctx.get(PMEL_BASE + fname)).text, fname)
        return store_obs(self.name, rows, ctx)


# ------------------------------------------------------------ JMA IOD + NINO.WEST

JMA_IDX = "https://ds.data.jma.go.jp/tcc/tcc/products/elnino/index/sstindex/base_period_9120/"
JMA_SERIES = {
    "DMI": "dmi_jma_anom",
    "WIN": "iod_west_jma_anom",
    "EIN": "iod_east_jma_anom",
    "Nino_West": "nino_west_jma_anom",
    "Nino_3": "nino3_jma_anom",
}
JMA_REGIONS = {
    "DMI": "Dipole Mode Index = west pole (10N-10S, 50-70E) minus east pole (0-10S, 90-110E)",
    "WIN": "10N-10S, 50E-70E",
    "EIN": "0-10S, 90E-110E",
    "Nino_West": "Eq-15N, 130E-150E",
    "Nino_3": "5N-5S, 150W-90W",
}


def parse_jma_monthly(text: str, series: str, since_year: int = 1980) -> list[dict]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    rows = [ln.split() for ln in lines if re.match(r"^\d{4}\s", ln)]
    if not rows or any(len(r) != 13 for r in rows):
        raise SourceChanged(f"JMA {series}: rows are not 'YEAR + 12 months'")
    out = []
    for r in rows:
        y = int(r[0])
        if y < since_year:
            continue
        for mo, v in enumerate(r[1:], start=1):
            val = float(v)
            if val >= 99.0:  # 99.9 = not yet available
                continue
            out.append({"series": series, "ts": mid(y, mo), "value": val, "unit": "degC",
                        "meta": {"base": "1991-2020", "analysis": "JMA MGDSST"}})
    if not out:
        raise SourceChanged(f"JMA {series}: no values")
    return out


class JmaSstIndices(Collector):
    name = "jma_sst_indices"
    title = "Indian Ocean Dipole (DMI) + NINO.WEST (JMA)"
    category = "ocean_index"
    provider = "JMA Tokyo Climate Center"
    homepage = "https://ds.data.jma.go.jp/tcc/tcc/products/elnino/index/iod_index.html"
    endpoint = JMA_IDX + "DMI/anomaly"
    interval_s = 12 * HOUR
    freshness_basis = "observations"
    max_age_s = 60 * DAY
    description = ("Monthly SST anomalies from JMA: the Indian Ocean Dipole Mode Index "
                   "(dmi_jma_anom) with its west and east poles, the western Pacific warm pool "
                   "(nino_west_jma_anom) and JMA's NINO.3 (nino3_jma_anom). A positive IOD "
                   "together with El Nino usually means a drier season over Thailand and the "
                   "Maritime Continent.")

    async def collect(self, ctx: RunContext) -> int:
        rows: list[dict] = []
        for key, series in JMA_SERIES.items():
            text = (await ctx.get(JMA_IDX + key + "/anomaly")).text
            part = parse_jma_monthly(text, series)
            for r in part:
                r["meta"]["region"] = JMA_REGIONS[key]
            rows += part
        return store_obs(self.name, rows, ctx)


# ------------------------------------------------------------ ECMWF SEAS5 Nino plume

ECMWF_API = "https://charts.ecmwf.int/opencharts-api/v1"
ECMWF_PRODUCT = "seasonal_system5_nino_plumes"
ECMWF_AXIS_URL = f"{ECMWF_API}/packages/opencharts/products/{ECMWF_PRODUCT}/axis/"
ECMWF_PRODUCT_URL = f"{ECMWF_API}/products/{ECMWF_PRODUCT}/"
ECMWF_PAGE = f"https://charts.ecmwf.int/products/{ECMWF_PRODUCT}"
ECMWF_AREAS = {"nino34": "NINO3-4", "nino34_relative": "NINO3-4_rel"}


def parse_ecmwf_axis(payload: dict) -> tuple[str, str]:
    """-> (base_time value like 202609010000, label like 'Sep 2026') of the newest run."""
    try:
        axis = {a["name"]: a for a in payload["axis"]}
        vals = axis["base_time"]["values"]
        areas = {v["value"] for v in axis["nino_area"]["values"]}
    except (KeyError, TypeError) as e:
        raise SourceChanged(f"ECMWF axis: {e}") from None
    if not vals or not set(ECMWF_AREAS.values()) <= areas:
        raise SourceChanged("ECMWF axis: no base_time or NINO3-4 area")
    newest = max(vals, key=lambda v: v["value"])
    if not re.fullmatch(r"\d{12}", newest["value"]):
        raise SourceChanged(f"ECMWF axis: odd base_time {newest['value']!r}")
    return newest["value"], newest.get("label") or newest["value"]


def parse_ecmwf_product(payload: dict) -> str:
    try:
        link = payload["data"]["link"]
    except (KeyError, TypeError):
        raise SourceChanged(f"ECMWF product: no data.link ({payload.get('error')})") from None
    if link.get("type") != "image/png" or not str(link.get("href", "")).startswith("https://"):
        raise SourceChanged("ECMWF product: link is not a PNG")
    return link["href"]


class EcmwfNinoPlume(Collector):
    name = "ecmwf_nino_plume"
    title = "ECMWF SEAS5 Nino 3.4 forecast plume"
    category = "official"
    provider = "ECMWF (Copernicus C3S SEAS5)"
    homepage = ECMWF_PAGE
    endpoint = ECMWF_AXIS_URL
    interval_s = 12 * HOUR
    freshness_basis = "run"
    description = ("The monthly ECMWF SEAS5 seasonal forecast of Nino 3.4 SST anomaly: 51 "
                   "ensemble members for the next 6 months, as a chart (absolute and relative "
                   "index). Status key `ecmwf_nino_plume` {issued, label, images, url}. "
                   "Licence CC-BY-4.0.")

    async def collect(self, ctx: RunContext) -> int:
        base, label = parse_ecmwf_axis((await ctx.get(ECMWF_AXIS_URL)).json())
        bt = f"{base[:4]}-{base[4:6]}-{base[6:8]}T{base[8:10]}:00:00Z"
        images = {}
        for key, area in ECMWF_AREAS.items():
            r = await ctx.get(ECMWF_PRODUCT_URL, params={"base_time": bt, "nino_area": area})
            images[key] = parse_ecmwf_product(r.json())
        issued = f"{base[:4]}-{base[4:6]}-{base[6:8]}"
        db.set_status("ecmwf_nino_plume", {
            "issued": issued, "label": label, "images": images, "url": ECMWF_PAGE,
            "licence": "CC-BY-4.0 (c) ECMWF", "model": "SEAS5",
        })
        ctx.notes.update(issued=issued)
        return len(images)


COLLECTORS = [CpcEnsoProbs, CpcHeatContent, PmelWwv, JmaSstIndices, EcmwfNinoPlume]
