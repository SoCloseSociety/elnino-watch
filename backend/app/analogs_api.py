"""GET /api/local/analogs: what past strong El Ninos did to Koh Samui (mounted by app.main).

Response (see app/local/analogs.py `build`):
  {generated_at, point, history: {from, to, last_day, months, windows_pending, updated_at},
   events: [{id, years, peak_oni, peak_roni, strength, note, oni_jja, roni_jja,
             samui: {ne_monsoon_rain_pct, dry_season_rain_pct, feb_apr_rain_pct, year_rain_pct,
                     max_feels_like, max_feels_like_day, max_temp, heat_days, hot_days,
                     longest_dry_spell_days, longest_dry_spell_ne_days, *_rain_mm, complete,
                     kind: "reanalysis"},
             detail: {sw_monsoon, ne_monsoon, dry_season, feb_apr, year, heat, monthly[12]},
             impacts: [{date, type, area, text, source_title, url, publisher, quote,
                        checked_at, kind: "documented"}]}],
   neutral_baseline: {years, n, rule, metrics: {id: {label, unit, median, mean, min, max, n}}},
   normal: {period, months}, current_event: {id, oni, roni, nino34_weekly, strength, month,
   so_far}, takeaways: [str], other_impacts, kinds, method, sources}
"""

from __future__ import annotations

from fastapi import APIRouter

from .local import analogs

router = APIRouter()


@router.get("/api/local/analogs")
def local_analogs() -> dict:
    return analogs.build()


@router.get("/api/local/analogs/history")
def local_analogs_history() -> dict:
    """The raw monthly table behind the analogs (status samui_era5_history) for charts."""
    s = analogs.db.get_status(analogs.STATUS_KEY)
    if not s:
        return {"months": {}, "fields": list(analogs.M_FIELDS), "updated_at": None}
    v = s["value"]
    return {"months": v.get("months") or {}, "fields": v.get("fields") or list(analogs.M_FIELDS),
            "normals": v.get("normals"), "point": v.get("point"), "last_day": v.get("last_day"),
            "windows": v.get("windows"), "updated_at": s["updated_at"], "kind": "reanalysis",
            "source": v.get("source"), "url": v.get("url")}
