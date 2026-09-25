"""Coverage (missing data never reads as safe), season-aware rules, PWA notices,
TMD Gulf-only waves, data-gap alerts. Synthetic DB inputs: logic tests only."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app import db
from app.local import alerts, risk
from app.local.collectors import today_bkk


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


def ok_run(source: str) -> None:
    db.record_run(source, db.now_iso(), ok=True, items=1)


def series(source: str, name: str, values: list[float], start: date | None = None) -> None:
    start = start or today_bkk()
    db.upsert_observations(source, [
        {"series": name, "ts": (start + timedelta(days=i)).isoformat(), "value": v}
        for i, v in enumerate(values)])


def climatology(mm_per_day: float) -> None:
    d0 = date(2001, 1, 1)
    db.set_status("samui_climatology", {"days": {
        (d0 + timedelta(days=i)).strftime("%m-%d"): [mm_per_day, 31.0, 25.0, 35.0]
        for i in range(365)}})


def era5(values_newest_first: list[float]) -> None:
    end = today_bkk() - timedelta(days=5)
    db.upsert_observations("openmeteo_samui_era5", [
        {"series": "samui_era5_precip", "ts": (end - timedelta(days=i)).isoformat(), "value": v}
        for i, v in enumerate(values_newest_first)])
    ok_run("openmeteo_samui_era5")


def benign_island(waves: bool = True) -> None:
    """Every critical factor has fresh, unremarkable data."""
    db.upsert_observations("cpc_oni", [{"series": "oni", "value": 0.2,
                                        "ts": (today_bkk() - timedelta(days=60)).isoformat()}])
    climatology(5.0)
    era5([5.0] * 200)
    series("openmeteo_samui", "samui_apparent_temp_max", [34] * 7)
    series("openmeteo_samui", "samui_precip", [5, 5, 5])
    series("openmeteo_samui", "samui_wind_gust_max", [30, 30, 30])
    ok_run("openmeteo_samui")
    ok_run("gdacs")
    if waves:
        series("openmeteo_marine", "samui_wave_height", [0.5, 0.6, 0.5])
        ok_run("openmeteo_marine")


def by_id(r: dict) -> dict:
    return {f["id"]: f for f in r["factors"]}


# ------------------------------------------------------------------ coverage

def test_complete_benign_island_is_normal():
    benign_island()
    r = risk.evaluate(save=False)
    assert r["coverage"]["critical_missing"] == []
    assert r["level"] == 0 and r["level_key"] == "normal"
    assert "No immediate threat" in r["headline"]


def test_one_critical_factor_missing_means_unknown():
    benign_island(waves=False)
    r = risk.evaluate(save=False)
    assert r["level"] is None and r["level_key"] == "unknown" and r["level_label"] == "Unknown"
    assert r["coverage"]["critical_missing"] == ["sea_state"]
    assert "sea state" in r["headline"] and "cannot be assessed" in r["headline"]
    assert "No immediate threat" not in r["headline"]
    assert r["level_floor"] == 0


def test_strong_el_nino_known_but_water_missing_gives_floor():
    db.upsert_observations("cpc_oni", [{"series": "oni", "value": 1.8,
                                        "ts": (today_bkk() - timedelta(days=60)).isoformat()}])
    r = risk.evaluate(save=False)
    assert r["level"] is None and r["level_floor"] == 2
    assert r["headline"].count("At least Prepare (El Nino") == 1
    assert "enso" not in r["coverage"]["critical_missing"]


def test_stale_critical_factor_counts_as_missing():
    benign_island(waves=False)
    series("openmeteo_marine", "samui_wave_height", [2.5, 2.2])  # no fresh run -> stale
    r = risk.evaluate(save=False)
    sea = by_id(r)["sea_state"]
    assert sea["level"] == 2 and sea["stale"]
    assert r["coverage"]["stale"] == ["sea_state"]
    assert r["level"] is None and r["level_floor"] == 2


def test_unknown_since_is_kept_across_evaluations():
    a = risk.evaluate(save=True)
    b = risk.evaluate(save=True)
    assert a["unknown_since"] and b["unknown_since"] == a["unknown_since"]
    benign_island()
    assert risk.evaluate(save=True)["unknown_since"] is None


# ------------------------------------------------------------------ water, season-aware

def test_water_dry_season_uses_180_day_window(monkeypatch):
    climatology(5.0)
    era5([4.5] * 90 + [0.5] * 110)  # recent 90 d fine (90%), the monsoon before was dry
    monkeypatch.setattr(risk, "today_bkk", lambda: date(2027, 2, 15))
    w = risk.f_water(enso_level=0, news_water_samui=0)
    assert w["details"]["driving_window"] == "180 d" and w["level"] == 2
    monkeypatch.setattr(risk, "today_bkk", lambda: date(2026, 9, 15))
    w = risk.f_water(enso_level=0, news_water_samui=0)
    assert w["details"]["driving_window"] == "90 d" and w["level"] == 1


def test_water_refill_season_strong_el_nino_prepares(monkeypatch):
    climatology(5.0)
    era5([3.5] * 200)  # 70% of normal
    monkeypatch.setattr(risk, "today_bkk", lambda: date(2026, 11, 10))
    assert risk.f_water(enso_level=0, news_water_samui=0)["level"] == 1
    assert risk.f_water(enso_level=2, news_water_samui=0)["level"] == 2


def test_water_small_absolute_deficit_is_not_act():
    climatology(0.5)            # 45 mm normal over 90 days
    era5([0.1] * 200)           # 20% of normal but only 36 mm short
    w = risk.f_water(enso_level=0, news_water_samui=0)
    assert w["value"] == 20 and w["level"] == 2
    climatology(5.0)
    era5([1.0] * 200)           # 20% and 360 mm short
    assert risk.f_water(enso_level=0, news_water_samui=0)["level"] == 3


def test_water_mainland_dam_no_longer_confirms_shortage():
    climatology(5.0)
    era5([1.0] * 200)
    db.upsert_observations("thaiwater_dams", [{"series": "surat_ratchaprapa_storage_pct",
                                               "ts": today_bkk().isoformat(), "value": 20.0}])
    assert risk.f_water(enso_level=0, news_water_samui=0)["level"] == 3


def _pwa(kind: str, start_h: float, end_h: float, status: str = "in_progress") -> dict:
    now = datetime.now(UTC)
    return {"id": f"x{kind}", "kind": kind, "kind_label": kind, "status": status,
            "start": (now + timedelta(hours=start_h)).isoformat(),
            "end": (now + timedelta(hours=end_h)).isoformat(), "url": "u", "area_th": ""}


def test_water_pwa_notices_raise_the_level():
    climatology(5.0)
    era5([5.0] * 200)
    db.set_status("pwa_samui_notices", {"items": [_pwa("pipe_burst", -1, 3)]})
    ok_run("pwa_samui_notices")
    w = risk.f_water(enso_level=0, news_water_samui=0)
    assert w["level"] == 1 and "PWA Ko Samui notice" in w["explanation"]
    db.set_status("pwa_samui_notices", {"items": [_pwa("store_water", -10, 60)]})
    assert risk.f_water(enso_level=0, news_water_samui=0)["level"] == 2
    db.set_status("pwa_samui_notices", {"items": [_pwa("no_supply", -1, 3, "done"),
                                                  _pwa("pipe_burst", -9, -2)]})
    w = risk.f_water(enso_level=0, news_water_samui=0)
    assert w["level"] == 0 and w["details"]["pwa_notices_active"] == []
    # rain-driven 'act' + a long PWA notice = confirmed shortage
    era5([1.0] * 200)
    db.set_status("pwa_samui_notices", {"items": [_pwa("no_supply", -1, 3)]})
    assert risk.f_water(enso_level=0, news_water_samui=0)["level"] == 4


# ------------------------------------------------------------------ flood antecedent rain

def test_flood_heavy_rain_on_saturated_ground_goes_up():
    series("openmeteo_samui", "samui_precip", [40, 10, 10])
    ok_run("openmeteo_samui")
    assert risk.f_flood()["level"] == 1
    series("openmeteo_samui", "samui_precip", [30] * 7, start=today_bkk() - timedelta(days=7))
    f = risk.f_flood()
    assert f["details"]["past7_mm"] == 210 and f["level"] == 2


def test_flood_very_wet_week_alone_is_watch():
    series("openmeteo_samui", "samui_precip", [40] * 7 + [5, 5, 5],
           start=today_bkk() - timedelta(days=7))
    ok_run("openmeteo_samui")
    assert risk.f_flood()["level"] == 1


# ------------------------------------------------------------------ sea state: Gulf only

def _tmd(**kw) -> dict:
    return {"issue": "1/2569", "until": (today_bkk() + timedelta(days=2)).isoformat(),
            "affects_samui": True, "heavy_rain": True, "strong_waves": True} | kw


def test_andaman_only_wave_warning_ignored_for_samui():
    series("openmeteo_marine", "samui_wave_height", [0.5, 0.5])
    ok_run("openmeteo_marine")
    db.set_status("tmd_warnings", {"items": [_tmd(strong_waves_gulf=False)]})
    assert risk.f_sea_state()["level"] == 0
    db.set_status("tmd_warnings", {"items": [_tmd(strong_waves_gulf=True)]})
    assert risk.f_sea_state()["level"] == 1
    db.set_status("tmd_warnings", {"items": [_tmd(strong_waves_gulf=True,
                                                  small_boats_ashore=True, wave_m_max=3.0)]})
    assert risk.f_sea_state()["level"] == 3


def test_season_context():
    assert risk.season_context(date(2026, 11, 5))["id"] == "ne_monsoon"
    assert "flood" in risk.season_context(date(2026, 11, 5))["focus"]
    assert risk.season_context(date(2027, 3, 1))["id"] == "dry_season"
    assert risk.season_context(date(2026, 7, 1))["id"] == "sw_monsoon"
    assert risk.water_season(11) == "refill" and risk.water_season(3) == "dry"


# ------------------------------------------------------------------ alerts on unknown

def _unknown(hours_ago: float) -> dict:
    since = (datetime.now(UTC) - timedelta(hours=hours_ago)).isoformat()
    return {"level": None, "level_key": "unknown", "headline": "Level cannot be assessed.",
            "unknown_since": since, "factors": [],
            "coverage": {"critical_missing": ["water", "sea_state"]}}


def test_data_gap_alert_after_six_hours_once_a_day():
    assert alerts.plan_alerts(_unknown(1), previous_level=2) == []
    planned = alerts.plan_alerts(_unknown(7), previous_level=None)
    assert [a["kind"] for a in planned] == ["data_gap"]
    assert planned[0]["dedup_key"] == f"data_gap:{today_bkk().isoformat()}"
    assert "water, sea_state" in planned[0]["body"]


async def test_data_gap_dispatch_dedups():
    assert len(await alerts.dispatch(_unknown(8), previous_level=None)) == 1
    assert await alerts.dispatch(_unknown(9), previous_level=None) == []
