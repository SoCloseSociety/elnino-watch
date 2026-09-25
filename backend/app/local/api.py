"""HTTP routes for the Koh Samui watch and the preparedness page (mounted by app.main)."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import db
from . import provenance as P
from . import risk
from .collectors import CLIM_NOTE, COLLECTORS, today_bkk
from .preparedness import DEFAULT_STATE, preparedness

router = APIRouter()

FORECAST_SERIES = {
    "samui_temp_max": "temp_max", "samui_temp_min": "temp_min",
    "samui_apparent_temp_max": "apparent_temp_max", "samui_precip": "precip",
    "samui_precip_prob": "precip_prob", "samui_wind_gust_max": "wind_gust_max",
    "samui_uv_max": "uv_max",
}
UNITS = {"temp_max": "degC", "temp_min": "degC", "apparent_temp_max": "degC", "precip": "mm",
         "precip_prob": "%", "wind_gust_max": "km/h", "uv_max": "index", "era5_precip": "mm",
         "era5_temp_max": "degC", "era5_temp_min": "degC", "normal_precip": "mm",
         "normal_temp_max": "degC", "normal_temp_min": "degC",
         "normal_apparent_temp_max": "degC"}
ERA5_SERIES = {"samui_era5_precip": "era5_precip", "samui_era5_temp_max": "era5_temp_max",
               "samui_era5_temp_min": "era5_temp_min"}


@router.get("/api/local")
def local() -> dict:
    s = db.get_status("local_risk")
    if s is None:
        return risk.evaluate(save=True)
    return s["value"]


@router.get("/api/local/history")
def local_history() -> list[dict]:
    s = db.get_status("local_risk_history")
    return s["value"] if s else []


@router.get("/api/local/exit")
def local_exit() -> dict:
    from .exit import exit_plan

    return exit_plan()


@router.post("/api/local/evaluate")
async def local_evaluate() -> dict:
    from . import evaluate_and_alert

    return await evaluate_and_alert()


def _source_info(name: str) -> dict:
    col = next((c for c in COLLECTORS if c.name == name), None)
    last = db.query("SELECT started_at FROM source_runs WHERE source=? AND ok=1 "
                    "ORDER BY id DESC LIMIT 1", (name,))
    return {"name": name, "provider": col.provider if col else None,
            "url": col.homepage if col else None,
            "last_ok_at": last[0]["started_at"] if last else None}


@router.get("/api/local/weather")
def local_weather() -> dict:
    """Last 92 days + 16-day forecast (today + 15), with the 1991-2020 ERA5 normal for each day."""
    today = today_bkk()
    start, end = today - timedelta(days=92), today + timedelta(days=15)
    days: dict[str, dict] = {}
    for i in range((end - start).days + 1):
        d = (start + timedelta(days=i)).isoformat()
        # kind of the Open-Meteo columns of that day: TODAY's daily total / max still
        # contains forecast hours, so it is a forecast too; era5_* columns are reanalysis
        days[d] = {"date": d, "forecast": d > today.isoformat(),
                   "kind": "forecast" if d >= today.isoformat() else "model_analysis",
                   "partial_day": d == today.isoformat()}
    for src, mapping in (("openmeteo_samui", FORECAST_SERIES),
                         ("openmeteo_samui_era5", ERA5_SERIES)):
        rows = db.query(
            "SELECT series, ts, value FROM observations WHERE source=? AND ts>=? AND ts<=?",
            (src, start.isoformat(), end.isoformat()))
        for r in rows:
            if r["ts"] in days and r["series"] in mapping:
                days[r["ts"]][mapping[r["series"]]] = r["value"]
    clim = db.get_status("samui_climatology")
    cdays = clim["value"]["days"] if clim else {}
    for d, row in days.items():
        n = cdays.get("02-28" if d[5:10] == "02-29" else d[5:10])
        if n:
            row.update(normal_precip=n[0], normal_temp_max=n[1], normal_temp_min=n[2],
                       normal_apparent_temp_max=n[3])
    clim_meta = None
    if clim:
        clim_meta = {k: v for k, v in clim["value"].items() if k != "days"}
        clim_meta["updated_at"] = clim["updated_at"]
        clim_meta["note"] = CLIM_NOTE  # code-authored text; older stored copies were French
    seasonal = db.get_status("samui_seasonal")
    gauge = risk.latest_obs("samui_gauge_rain_24h", "thaiwater_samui_rain")
    dam = risk.latest_obs("surat_ratchaprapa_storage_pct", "thaiwater_dams")
    return {
        "today": today.isoformat(),
        "tz": "ICT (UTC+7): every date is a local Samui day",
        "units": {k: {"unit": u, "unit_label": P.unit_label(u)} for k, u in UNITS.items()},
        "kinds": {"precip, temp_*, apparent_temp_max, precip_prob, wind_gust_max, uv_max":
                  "the day's `kind` (forecast from today on, model_analysis before)",
                  "era5_*": "reanalysis", "normal_*": "1991-2020 ERA5 climatology",
                  "gauge": "observed", "ratchaprapa": "observed", "seasonal": "forecast"},
        "days": list(days.values()),
        "rain_windows": risk.rain_windows(clim["value"]) if clim else None,
        "climatology": clim_meta,
        "seasonal": seasonal["value"] | {"updated_at": seasonal["updated_at"]}
        if seasonal else None,
        "gauge": gauge,
        "ratchaprapa": dam,
        "sources": [_source_info(n) for n in ("openmeteo_samui", "openmeteo_samui_era5",
                                              "openmeteo_samui_seasonal",
                                              "thaiwater_samui_rain", "thaiwater_dams")],
        "notes": [("Past days: forecast model analyses (not measurements); 'era5_*' = "
                   "ERA5 reanalysis (~5 days behind), comparable with the normal."),
                  "Normal = smoothed ERA5 1991-2020, same source as era5_* (bias cancels out)."],
    }


@router.get("/api/preparedness")
def get_preparedness() -> dict:
    return preparedness()


class Household(BaseModel):
    adults: int = Field(1, ge=0, le=50)
    children: int = Field(0, ge=0, le=50)
    days: int = Field(14, ge=1, le=365)


class PrepState(BaseModel):
    checked: dict[str, bool] = Field(default_factory=dict)
    household: Household = Field(default_factory=Household)


def _known_ids() -> set[str]:
    return {it["id"] for c in preparedness()["categories"] for it in c["items"]}


@router.get("/api/preparedness/state")
def get_prep_state() -> dict:
    s = db.get_status("prep_state")
    return s["value"] if s else DEFAULT_STATE


@router.put("/api/preparedness/state")
def put_prep_state(state: PrepState) -> dict:
    unknown = set(state.checked) - _known_ids()
    if unknown:
        raise HTTPException(422, f"unknown item ids: {sorted(unknown)[:10]}")
    value = {"checked": {k: True for k, v in state.checked.items() if v},
             "household": state.household.model_dump()}
    db.set_status("prep_state", value)
    return value
