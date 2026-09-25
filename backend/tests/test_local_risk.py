"""Risk engine thresholds and combination rules (synthetic inputs: logic tests only)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app import db
from app.local import risk
from app.local.collectors import today_bkk


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


def ok_run(source: str) -> None:
    db.record_run(source, db.now_iso(), ok=True, items=1)


def f(fid: str, level):
    return {"id": fid, "level": level}


# ------------------------------------------------------------------ thresholds

@pytest.mark.parametrize("v,lv", [(0.3, 0), (0.5, 1), (1.2, 1), (1.49, 1), (1.5, 2), (2.8, 2)])
def test_oni_level(v, lv):
    assert risk.oni_level(v) == lv


@pytest.mark.parametrize("pct,lv", [(None, None), (103, 0), (75, 0), (74, 1), (60, 1), (59, 2),
                                    (40, 2), (39, 3), (5, 3)])
def test_rain_deficit_level(pct, lv):
    assert risk.rain_deficit_level(pct) == lv


@pytest.mark.parametrize("mx,days,lv", [(37, 0, 0), (39, 0, 1), (41, 1, 2), (42, 2, 2),
                                        (42, 3, 3), (55, 5, 4)])
def test_heat_level(mx, days, lv):
    assert risk.heat_level(mx, days) == lv


@pytest.mark.parametrize("m24,s72,lv", [(20, 40, 0), (35, 40, 0), (35.1, 40, 1), (10, 100, 1),
                                        (91, 100, 2), (40, 150, 2), (150, 150, 3),
                                        (60, 250, 3)])
def test_rain_level_tmd_classes(m24, s72, lv):
    assert risk.rain_level(m24, s72) == lv


@pytest.mark.parametrize("g,lv", [(60, 0), (75, 1), (88, 1), (89, 2), (117, 2), (118, 3)])
def test_gust_level(g, lv):
    assert risk.gust_level(g) == lv


@pytest.mark.parametrize("h,lv", [(0.5, 0), (1.5, 1), (2.0, 2), (2.9, 2), (3.0, 3)])
def test_wave_level(h, lv):
    assert risk.wave_level(h) == lv


@pytest.mark.parametrize("pm,lv", [(10, 0), (37.5, 0), (37.6, 1), (75, 1), (75.1, 2), (126, 3)])
def test_pm25_level(pm, lv):
    assert risk.pm25_level(pm) == lv


@pytest.mark.parametrize("d,lv", [(2, 0), (4, 1), (8, 2)])
def test_dhw_level(d, lv):
    assert risk.dhw_level(d) == lv


def test_cyclone_distance_rules():
    ev = lambda d, s: {"distance_km": d, "severity": s, "title": "x"}
    assert risk.cyclone_level([])[0] == 0
    assert risk.cyclone_level([ev(250, "red")])[0] == 4
    assert risk.cyclone_level([ev(250, "green")])[0] == 3
    assert risk.cyclone_level([ev(600, "orange")])[0] == 2
    assert risk.cyclone_level([ev(600, "green")])[0] == 1
    assert risk.cyclone_level([ev(1500, "red")])[0] == 0
    lv, worst = risk.cyclone_level([ev(700, "green"), ev(280, "orange")])
    assert lv == 4 and worst["distance_km"] == 280


def test_haversine_samui_bangkok():
    assert 450 < risk.haversine_km(9.512, 100.013, 13.75, 100.5) < 480


# ------------------------------------------------------------------ combination

def test_combine_enso_capped_at_prepare():
    assert risk.combine([f("enso", 2)])[0] == 2


def test_combine_single_hazard_never_leave():
    assert risk.combine([f("flood", 3), f("heat", 3)])[0] == 3
    assert risk.combine([f("water", 4)])[0] == 3


def test_combine_news_never_sole_trigger():
    assert risk.combine([f("news", 1), f("heat", 0)])[0] == 0
    assert risk.combine([f("news", 1), f("heat", 1)])[0] == 1


def test_combine_compound_rule():
    lv, rules = risk.combine([f("flood", 2), f("sea_state", 2)])
    assert lv == 3 and any(r.startswith("R3") for r in rules)
    # ENSO + marine heat are not physical hazards
    assert risk.combine([f("enso", 2), f("marine_heat", 2)])[0] == 2


def test_combine_level_four_rules():
    lv, rules = risk.combine([f("cyclone_wind", 4)])
    assert lv == 4 and any(r.startswith("R4a") for r in rules)
    lv, rules = risk.combine([f("heat", 3), f("water", 3)])
    assert lv == 4 and any(r.startswith("R4b") for r in rules)


def test_combine_ignores_missing():
    assert risk.combine([f("flood", None), f("heat", None)])[0] == 0


# ------------------------------------------------------------------ evaluate on a DB

def test_empty_db_is_unknown_not_safe():
    r = risk.evaluate(save=False)
    assert all(x["level"] is None for x in r["factors"])
    assert not r["complete"] and len(r["missing"]) == len(r["factors"])
    assert all(x["explanation"].startswith(risk.NA) for x in r["factors"])
    assert r["level"] is None and r["level_key"] == "unknown"
    assert "cannot be assessed" in r["headline"]
    assert "No immediate threat" not in r["headline"]
    cov = r["coverage"]
    assert cov["with_data"] == 0 and cov["total"] == len(r["factors"])
    assert set(cov["critical_missing"]) == set(risk.CRITICAL)
    assert r["actions"][0]["level_key"] == "unknown"


def _forecast(series: str, values: list[float], source="openmeteo_samui"):
    t = today_bkk()
    db.upsert_observations(source, [
        {"series": series, "ts": (t + timedelta(days=i)).isoformat(), "value": v}
        for i, v in enumerate(values)])


def test_evaluate_heavy_rain_and_waves_compound():
    _forecast("samui_precip", [120, 60, 10])
    _forecast("samui_wave_height", [2.4, 2.1], source="openmeteo_marine")
    ok_run("openmeteo_samui")
    ok_run("openmeteo_marine")
    r = risk.evaluate(save=True)
    by = {x["id"]: x for x in r["factors"]}
    assert by["flood"]["level"] == 2 and by["sea_state"]["level"] == 2
    # enso / water / heat / cyclone have no data: level unknown, but "at least act"
    assert r["level"] is None and r["level_floor"] == 3
    assert "At least Act" in r["headline"]
    assert db.get_status("local_risk")["value"]["level_floor"] == 3
    assert any(t["level_key"] == "leave" for t in r["triggers"])


def test_evaluate_red_cyclone_close_means_leave():
    db.upsert_events("gdacs", [{"ext_id": "TC1", "category": "cyclone", "title": "TC TEST",
                                "severity": "red", "lat": 10.5, "lon": 101.0}])
    ok_run("gdacs")
    r = risk.evaluate(save=False)
    cyc = next(x for x in r["factors"] if x["id"] == "cyclone_wind")
    assert cyc["level"] == 4 and cyc["value"] < 300
    assert r["level_floor"] == 4 and "At least Leave" in r["headline"]


def test_stale_zero_is_reported_unknown():
    _forecast("samui_apparent_temp_max", [33, 34, 35])
    # no successful run recorded -> stale
    heat = risk.f_heat()
    assert heat["level"] is None and heat["stale"]


def test_water_factor_from_era5_vs_climatology():
    days = {}
    d0 = datetime(2001, 1, 1, tzinfo=UTC)
    for i in range(365):
        days[(d0 + timedelta(days=i)).strftime("%m-%d")] = [5.0, 31.0, 25.0, 35.0]
    db.set_status("samui_climatology", {"days": days})
    end = today_bkk() - timedelta(days=5)
    db.upsert_observations("openmeteo_samui_era5", [
        {"series": "samui_era5_precip", "ts": (end - timedelta(days=i)).isoformat(),
         "value": 1.0} for i in range(200)])
    ok_run("openmeteo_samui_era5")
    w = risk.f_water(enso_level=0, news_water_samui=0)
    assert w["value"] == 20 and w["level"] == 3  # 1 mm/day vs 5 mm/day normal
    w4 = risk.f_water(enso_level=0, news_water_samui=3)
    assert w4["level"] == 4


def test_news_counts_keywords():
    db.upsert_feed_items("gnews", [
        {"ext_id": "1", "kind": "news", "title": "Koh Samui water shortage worsens",
         "tags": ["samui"], "published_at": datetime.now(UTC).isoformat()},
        {"ext_id": "2", "kind": "news", "title": "Flood in Hat Yai", "tags": ["thailand"],
         "published_at": datetime.now(UTC).isoformat()},
        {"ext_id": "3", "kind": "news", "title": "Unrelated tourism", "tags": ["samui"],
         "published_at": datetime.now(UTC).isoformat()},
    ])
    c = risk.news_counts()
    assert c["water_samui"] == 1 and c["flood_thailand"] == 1 and c["flood_samui"] == 0
    assert risk.f_news(c)["level"] == 0


def test_history_throttled():
    risk._append_history({"evaluated_at": "2026-09-24T00:00:00+00:00", "level": 1})
    risk._append_history({"evaluated_at": "2026-09-24T00:10:00+00:00", "level": 1})
    risk._append_history({"evaluated_at": "2026-09-24T00:11:00+00:00", "level": 2})
    risk._append_history({"evaluated_at": "2026-09-24T00:45:00+00:00", "level": 2})
    h = db.get_status("local_risk_history")["value"]
    assert [x["level"] for x in h] == [1, 2, 2]
