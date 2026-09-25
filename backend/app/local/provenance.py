"""Provenance of every number the app shows: what KIND of value it is, which date or
period it describes, when it was issued / fetched, and how to write it for people.

KINDS (the `kind` field):
  observed        measured (station, gauge, buoy, satellite) or an index computed from
                  measurements (ONI, RONI, weekly/daily OISST Nino 3.4, SOI, MEI, DHW).
  forecast        a model prediction for a date that has not happened yet (Open-Meteo
                  daily/hourly future steps, TODAY's daily total or maximum -- the day is
                  not over, so it still contains forecast hours --, ECMWF SEAS5, IRI).
  model_analysis  a weather model's own estimate of a PAST hour/day (Open-Meteo
                  `past_days`, CAMS air quality before now). Not a measurement.
  reanalysis      ERA5 / MERRA-2: past weather rebuilt from all observations by a model
                  (~5 days behind for ERA5); the reference used against the 1991-2020 normal.
  bulletin        an agency statement (NOAA CPC status, TMD warning, PWA notice, GDACS
                  alert): its date is the issue date and its period the stated validity.

`valid_for` = the date (YYYY-MM-DD) or ISO 8601 interval (start/end, both inclusive
calendar days) the value describes. Local Samui days are ICT (Asia/Bangkok, UTC+7);
global indices use UTC dates (see `tz`).

Units: `unit` is a machine code (degC, mm, m, km/h, ug/m3, ...) that never changes;
`unit_label` is the display form (degC -> °C, ug/m3 -> µg/m³). User-facing text uses the
display form.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from .. import db
from .collectors import BKK, today_bkk

KINDS = ("observed", "forecast", "model_analysis", "reanalysis", "bulletin")
KIND_LABELS = {"observed": "observed", "forecast": "forecast",
               "model_analysis": "model analysis (not a measurement)",
               "reanalysis": "ERA5 reanalysis", "bulletin": "official bulletin"}
TZ_LOCAL = "ICT (UTC+7)"
TZ_UTC = "UTC"

UNIT_LABELS = {
    "degC": "°C", "degC-weeks": "°C-weeks", "ug/m3": "µg/m³", "km/h": "km/h", "m": "m",
    "mm": "mm", "%": "%", "km": "km", "std": "σ (standardized)", "soi": "SOI (Troup, x10)",
    "index": "index", "US AQI": "US AQI", "Thai AQI": "Thai AQI", "W/m2": "W/m²",
    "m/s": "m/s", "1e14 m3": "10^14 m³", "hotspots": "hotspots", "level": "alert level",
    "count": "items",
}

# decimals used for display, by machine unit (source precision is kept in value_raw)
DECIMALS = {"mm": 0, "%": 0, "km/h": 0, "km": 0, "m": 1, "ug/m3": 1, "degC-weeks": 1,
            "degC": 1, "count": 0}


def unit_label(unit: str | None) -> str | None:
    if unit is None:
        return None
    return UNIT_LABELS.get(unit, unit)


def rnd(v: float | None, unit: str | None = None, decimals: int | None = None) -> float | None:
    if v is None:
        return None
    d = decimals if decimals is not None else DECIMALS.get(unit or "", 2)
    out = round(float(v), d)
    return int(out) if d == 0 else out


def fmt_num(v: float, unit: str | None = None, decimals: int | None = None,
            signed: bool = False) -> str:
    d = decimals if decimals is not None else DECIMALS.get(unit or "", 2)
    s = f"{v:+,.{d}f}" if signed else f"{v:,.{d}f}"
    return s


def fmt_val(v: float, unit: str | None, decimals: int | None = None,
            signed: bool = False) -> str:
    lab = unit_label(unit) or ""
    sep = "" if lab in ("%",) else " "
    return f"{fmt_num(v, unit, decimals, signed)}{sep}{lab}".strip()


# ------------------------------------------------------------------ dates

def _d(x: str | date) -> date:
    return x if isinstance(x, date) else date.fromisoformat(str(x)[:10])


def fmt_day(x: str | date, year: bool = False) -> str:
    """'2026-09-30' -> 'Wed 30 Sep' (the weekday is computed, never guessed)."""
    d = _d(x)
    s = f"{d:%a} {d.day} {d:%b}"
    return f"{s} {d.year}" if year else s


def fmt_short(x: str | date) -> str:
    d = _d(x)
    return f"{d.day} {d:%b}"


def fmt_period(start: str | date, end: str | date) -> str:
    a, b = _d(start), _d(end)
    if a == b:
        return fmt_day(a)
    if a.year == b.year and a.month == b.month:
        return f"{a.day}-{b.day} {b:%b}"
    return f"{a.day} {a:%b}-{b.day} {b:%b}"


def interval(start: str | date, end: str | date) -> str:
    a, b = _d(start).isoformat(), _d(end).isoformat()
    return a if a == b else f"{a}/{b}"


def parse_dt(ts: str) -> datetime:
    if len(ts) == 10:
        return datetime.fromisoformat(ts).replace(tzinfo=BKK)
    t = datetime.fromisoformat(ts)
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def fmt_ict(ts: str | None) -> str | None:
    """ISO datetime (UTC) -> '24 Sep 20:05 ICT'."""
    if not ts:
        return None
    t = parse_dt(ts).astimezone(BKK)
    return f"{t.day} {t:%b} {t:%H:%M} ICT"


def retrieved_at(source: str) -> str | None:
    """Finish time (UTC) of the source's last successful fetch = when we got the data."""
    rows = db.query("SELECT finished_at FROM source_runs WHERE source=? AND ok=1 "
                    "ORDER BY id DESC LIMIT 1", (source,))
    return rows[0]["finished_at"] if rows else None


def cpc_week(ts: str) -> tuple[str, str]:
    """CPC weekly OISST rows are dated on the week's centre (a Wednesday): the week is
    centre - 3 d .. centre + 3 d."""
    c = _d(ts)
    return (c - timedelta(days=3)).isoformat(), (c + timedelta(days=3)).isoformat()


def season_interval(center_ts: str) -> tuple[str, str]:
    """3-month index dated on its centre month's 15th -> first and last day of the season."""
    c = _d(center_ts)
    s = date(c.year, c.month, 1)
    s = (s - timedelta(days=1)).replace(day=1)
    e_month = date(c.year + (c.month == 12), c.month % 12 + 1, 1)
    e = (date(e_month.year + (e_month.month == 12), e_month.month % 12 + 1, 1)
         - timedelta(days=1))
    return s.isoformat(), e.isoformat()


# ------------------------------------------------------------------ series kinds

OBSERVED_SOURCES = {
    "cpc_oni", "cpc_roni", "cpc_weekly_sst", "cpc_soi", "psl_mei", "bom_soi", "cr_world_sst",
    "cr_nino34_daily", "tao_buoys", "crw_vs", "jma_sst_indices", "pmel_wwv", "cpc_heat_content",
    "cpc_atmos_indices", "psl_mjo_romi", "air4thai_south", "thaiwater_dams",
    "thaiwater_dams_national", "thaiwater_samui_rain", "asmc_hotspots", "nasa_gistemp",
}
# ERA5 / MERRA-2 products (Climate Pulse is the daily global ERA5 series, samui_era5_history
# the 1950+ ERA5 monthly table behind the El Nino analogs)
REANALYSIS_SOURCES = {"openmeteo_samui_era5", "nasa_power_samui", "c3s_climate_pulse",
                      "samui_era5_history"}
FORECAST_SOURCES = {"openmeteo_samui_seasonal", "ecmwf_nino_plume", "cpc_enso_probs",
                    "nasa_gmao_s2s", "ecmwf_seas5"}
# forecast-model sources whose past steps are the model's own analyses
MODEL_DAILY_SOURCES = {"openmeteo_samui", "openmeteo_marine"}
MODEL_HOURLY_SOURCES = {"openmeteo_samui_air"}


def series_kind(source: str, ts: str, now: datetime | None = None,
                today: date | None = None) -> str:
    now = now or datetime.now(UTC)
    today = today or today_bkk()
    if source in MODEL_DAILY_SOURCES:
        return "forecast" if ts[:10] >= today.isoformat() else "model_analysis"
    if source in MODEL_HOURLY_SOURCES:
        return "forecast" if parse_dt(ts) > now else "model_analysis"
    if source in REANALYSIS_SOURCES:
        return "reanalysis"
    if source in FORECAST_SOURCES:
        return "forecast"
    return "observed"


LOCAL_DAY_SOURCES = ("openmeteo_samui", "openmeteo_marine", "thaiwater_")


def series_tz(source: str, ts: str = "") -> str:
    """Clock of a stored ts: datetimes are always UTC; bare dates are Samui (ICT) days for
    the local sources, UTC days for global indices and satellites."""
    if len(ts) > 10:
        return TZ_UTC
    return TZ_LOCAL if source.startswith(LOCAL_DAY_SOURCES) else TZ_UTC


def evidence(name: str, value, unit: str | None, kind: str, valid_for: str | None,
             source: str, url: str = "", issued_at: str | None = None,
             retrieved: str | None = None, note: str | None = None,
             decimals: int | None = None, tz: str = TZ_LOCAL) -> dict:
    """One number behind a factor, with its full provenance."""
    assert kind in KINDS, kind
    return {"name": name, "value": rnd(value, unit, decimals) if isinstance(value, (int, float))
            and not isinstance(value, bool) else value,
            "value_raw": value, "unit": unit, "unit_label": unit_label(unit), "kind": kind,
            "valid_for": valid_for, "tz": tz, "issued_at": issued_at, "retrieved_at": retrieved,
            "source": source, "url": url, "note": note}


MONTHLY_SOURCES = {"cpc_soi", "bom_soi", "cpc_atmos_indices", "cpc_heat_content",
                   "jma_sst_indices", "pmel_wwv", "nasa_gistemp", "samui_era5_history"}


def _month_end(d: date) -> date:
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


def series_valid_for(source: str, ts: str) -> str:
    """The period a stored point describes (see the timestamp conventions in CLAUDE.md)."""
    if source in ("cpc_oni", "cpc_roni"):
        return interval(*season_interval(ts))
    if source == "cpc_weekly_sst":
        return interval(*cpc_week(ts))
    if source == "psl_mei":  # 2-month season dated the 1st of its second month
        d = _d(ts)
        first = (d - timedelta(days=1)).replace(day=1)
        return interval(first, _month_end(d))
    if source in MONTHLY_SOURCES and len(ts) == 10 and ts.endswith("-15"):
        d = _d(ts)
        return interval(d.replace(day=1), _month_end(d))
    return ts


# kind of the documents under /api/status/{key} (None = derived by this app)
STATUS_KINDS = {
    "cpc_alert": "bulletin", "iri_plume": "forecast", "jma_outlook": "bulletin",
    "bom_outlook": "bulletin", "cpc_enso_probs": "forecast", "ecmwf_nino_plume": "forecast",
    "samui_seasonal": "forecast", "samui_marine": "forecast", "samui_climatology": "reanalysis",
    "tmd_warnings": "bulletin", "pwa_samui_notices": "bulletin", "air4thai_samui": "observed",
    "crw_bleaching": "observed", "tao_buoys": "observed", "thai_dams": "observed",
    "asmc_haze_alert": "bulletin", "asmc_seasonal_outlook": "forecast",
    "samui_power": "reanalysis", "samui_power_crosscheck": "reanalysis",
    "samui_era5_history": "reanalysis",
}

# kind of the events of each source (/api/events)
EVENT_KINDS = {"firms_fires": "observed", "crw_vs": "observed", "usgs_quakes_region": "observed",
               "asmc_hotspots": "observed"}


def event_kind(source: str) -> str:
    """GDACS / EONET / JTWC / JMA / PTWC / ReliefWeb events are agency alerts or reports."""
    return EVENT_KINDS.get(source, "bulletin")


def annotate_point(row: dict, now: datetime | None = None, today: date | None = None) -> dict:
    """Add kind / valid_for / tz / unit_label to an observations row (source, ts, unit)."""
    src, ts = row.get("source") or "", row["ts"]
    return row | {"kind": series_kind(src, ts, now, today),
                  "valid_for": series_valid_for(src, ts), "tz": series_tz(src, ts),
                  "unit_label": unit_label(row.get("unit"))}
