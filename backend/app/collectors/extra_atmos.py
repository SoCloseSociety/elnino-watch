"""Extra ENSO atmosphere sources (gap fill, 2026-09-24).

- cpc_atmos_indices  CPC monthly 850 hPa trade-wind indices (W/C/E Pacific), 200 hPa
                     zonal wind and the dateline OLR index (observations)
- psl_mjo_romi       NOAA PSL real-time OLR MJO index (ROMI), daily (observations)

El Nino is a coupled ocean-atmosphere event: weaker trade winds (negative 850 hPa
anomalies, i.e. westerly anomalies) and more rain clouds near the dateline (negative
OLR anomalies) are the atmosphere's half of the story.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta

from .base import DAY, HOUR, Collector, RunContext, SourceChanged
from .extra_ocean import mid, store_obs

CPC_IDX = "https://www.cpc.ncep.noaa.gov/data/indices/"
# file -> (series, header must contain, unit, region)
CPC_ATMOS = {
    "wpac850": ("trade_wind_850_wpac_anom", "WEST PACIFIC", "m/s", "5N-5S, 135E-180W"),
    "cpac850": ("trade_wind_850_cpac_anom", "CENTRAL PACIFIC", "m/s", "5N-5S, 175W-140W"),
    "epac850": ("trade_wind_850_epac_anom", "EAST PACIFIC", "m/s", "5N-5S, 135W-120W"),
    "zwnd200": ("zonal_wind_200_anom", "200 MB ZONAL WINDS", "m/s", "Equator, 165W-110W"),
    "olr": ("olr_dateline_anom", "OUTGOING LONG WAVE RADIATION", "W/m2", "Equator, 160E-160W"),
}
_YEAR_ROW = re.compile(r"^(\d{4})((?:\s*-?\d+\.\d)+)\s*$")


def _section(lines: list[str], label: str) -> list[str]:
    """Rows of the block whose second header line is ORIGINAL / ANOMALY / STANDARDIZED."""
    out: list[str] = []
    active = False
    for ln in lines:
        head = ln.strip().upper()
        if head.startswith(("ORIGINAL", "ANOMALY", "STANDARDIZED")):
            active = head.startswith(label)
            continue
        if active:
            if _YEAR_ROW.match(ln.rstrip()):
                out.append(ln.rstrip())
            elif out and ln.strip() and not ln.startswith("YEAR"):
                active = False  # next block's title line
    return out


def _values(row: str) -> tuple[int, list[float]]:
    y = int(row[:4])
    body = row[4:]
    # fixed width: 12 columns of 6 characters (values run together at -999.9)
    cells = [body[i:i + 6] for i in range(0, 72, 6)]
    if len(cells) != 12 or any(not c.strip() for c in cells):
        raise SourceChanged(f"CPC: unexpected row width {row!r}")
    return y, [float(c) for c in cells]


def parse_cpc_monthly(text: str, fname: str) -> list[dict]:
    series, must, unit, region = CPC_ATMOS[fname]
    lines = text.splitlines()
    if not lines or must not in text[:400].upper():
        raise SourceChanged(f"CPC {fname}: header does not mention {must!r}")
    anom = _section(lines, "ANOMALY")
    std = {r[:4]: r for r in _section(lines, "STANDARDIZED")}
    if not anom:
        raise SourceChanged(f"CPC {fname}: no ANOMALY block")
    out = []
    for row in anom:
        y, vals = _values(row)
        svals = _values(std[row[:4]])[1] if row[:4] in std else [None] * 12
        for m, (v, sv) in enumerate(zip(vals, svals, strict=True), start=1):
            if v <= -999:
                continue
            meta = {"region": region}
            if sv is not None and sv > -999:
                meta["standardized"] = sv
            out.append({"series": series, "ts": mid(y, m), "value": v, "unit": unit,
                        "meta": meta})
    if not out:
        raise SourceChanged(f"CPC {fname}: no values")
    return out


class CpcAtmosIndices(Collector):
    name = "cpc_atmos_indices"
    title = "Trade winds, upper winds and dateline convection (CPC)"
    category = "ocean_index"
    provider = "NOAA CPC"
    homepage = "https://www.cpc.ncep.noaa.gov/data/indices/"
    endpoint = CPC_IDX + "cpac850"
    interval_s = 12 * HOUR
    freshness_basis = "observations"
    max_age_s = 60 * DAY
    description = ("Monthly atmospheric ENSO indices from CPC: 850 hPa trade-wind anomalies over "
                   "the west, central and east Pacific (negative = weaker trades / westerly "
                   "anomaly, typical of El Nino), 200 hPa zonal wind anomaly, and the outgoing "
                   "long-wave radiation anomaly near the dateline (negative = more rain clouds, "
                   "typical of El Nino). Series trade_wind_850_{wpac,cpac,epac}_anom, "
                   "zonal_wind_200_anom (m/s), olr_dateline_anom (W/m2).")

    async def collect(self, ctx: RunContext) -> int:
        rows: list[dict] = []
        for fname in CPC_ATMOS:
            rows += parse_cpc_monthly((await ctx.get(CPC_IDX + fname)).text, fname)
        return store_obs(self.name, [r for r in rows if r["ts"] >= "1979-01-01"], ctx)


# ------------------------------------------------------------ MJO (ROMI)

PSL_ROMI_URL = "https://psl.noaa.gov/mjo/mjoindex/romi.cpcolr.1x.txt"
_ROMI_ROW = re.compile(r"^\s*(\d{4})\s+(\d{1,2})\s+(\d{1,2})\s+\d+\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)"
                       r"\s+(\d+\.\d+)\s*$")


def parse_romi(text: str, days_back: int = 730, today: date | None = None) -> list[dict]:
    today = today or datetime.now(UTC).date()
    cut = today - timedelta(days=days_back)
    out = []
    bad = 0
    for ln in text.splitlines():
        if not ln.strip():
            continue
        m = _ROMI_ROW.match(ln)
        if not m:
            bad += 1
            continue
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d < cut:
            continue
        ts = d.isoformat()
        pc1, pc2, amp = float(m.group(4)), float(m.group(5)), float(m.group(6))
        out.append({"series": "mjo_romi_amplitude", "ts": ts, "value": amp, "unit": "index",
                    "meta": {"pc1": pc1, "pc2": pc2}})
        out.append({"series": "mjo_romi_pc1", "ts": ts, "value": pc1, "unit": "index"})
        out.append({"series": "mjo_romi_pc2", "ts": ts, "value": pc2, "unit": "index"})
    if bad > 5 or not out:
        raise SourceChanged(f"PSL ROMI: {bad} unparseable rows, {len(out)} values kept")
    return out


class PslMjoRomi(Collector):
    name = "psl_mjo_romi"
    title = "Madden-Julian Oscillation (real-time OMI, NOAA PSL)"
    category = "ocean_index"
    provider = "NOAA PSL"
    homepage = "https://psl.noaa.gov/mjo/"
    endpoint = PSL_ROMI_URL
    interval_s = 12 * HOUR
    freshness_basis = "observations"
    max_age_s = 12 * DAY  # published with a ~5 day lag
    description = ("Daily real-time OLR-based MJO index (ROMI). The MJO is a pulse of tropical "
                   "rain clouds that travels east around the equator every 30-60 days; when it is "
                   "active (amplitude above 1) over the Indian Ocean / Maritime Continent it "
                   "brings wetter spells to southern Thailand, and its westerly wind bursts can "
                   "boost El Nino. Series mjo_romi_amplitude, mjo_romi_pc1, mjo_romi_pc2.")

    async def collect(self, ctx: RunContext) -> int:
        return store_obs(self.name, parse_romi((await ctx.get(PSL_ROMI_URL)).text), ctx)


COLLECTORS = [CpcAtmosIndices, PslMjoRomi]
