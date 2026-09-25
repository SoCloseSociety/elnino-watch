"""Precision audit 2026-09-24: kind / valid_for / units / rounding / fallbacks / headline.

Synthetic DB inputs (the upstream values themselves were cross-checked live, see
docs/reports/PRECISION_AUDIT_2026-09-24.md). No network."""

from __future__ import annotations

import os

os.environ.setdefault("SCHEDULER", "false")

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import db
from app.local import exit as exit_mod
from app.local import provenance as P
from app.local import risk
from app.local.collectors import parse_tmd_storm_tracking, tmd_period, today_bkk


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


def ok_run(source: str) -> None:
    db.record_run(source, db.now_iso(), ok=True, items=1)


def daily(source: str, series: str, values: list[float], start: date | None = None) -> None:
    start = start or today_bkk()
    db.upsert_observations(source, [
        {"series": series, "ts": (start + timedelta(days=i)).isoformat(), "value": v}
        for i, v in enumerate(values)])


def climatology(mm_per_day: float) -> None:
    d0 = date(2001, 1, 1)
    db.set_status("samui_climatology", {"days": {
        (d0 + timedelta(days=i)).strftime("%m-%d"): [mm_per_day, 31.0, 25.0, 35.0]
        for i in range(365)}})


# ------------------------------------------------------------------ provenance helpers

def test_weekday_is_computed_not_guessed():
    assert P.fmt_day("2026-09-30") == "Wed 30 Sep"       # not "Tue 30 Sep"
    assert P.fmt_day("2026-09-10", True) == "Thu 10 Sep 2026"
    assert P.fmt_period("2026-06-21", "2026-09-18") == "21 Jun-18 Sep"
    assert P.fmt_ict("2026-09-24T13:05:00+00:00") == "24 Sep 20:05 ICT"


def test_index_periods():
    assert P.season_interval("2026-07-15") == ("2026-06-01", "2026-08-31")   # JJA
    assert P.season_interval("2026-01-15") == ("2025-12-01", "2026-02-28")   # DJF
    assert P.cpc_week("2026-09-16") == ("2026-09-13", "2026-09-19")
    assert P.series_valid_for("psl_mei", "2026-08-01") == "2026-07-01/2026-08-31"   # JA
    assert P.series_valid_for("cpc_soi", "2026-08-15") == "2026-08-01/2026-08-31"
    assert P.series_valid_for("cr_nino34_daily", "2026-09-22") == "2026-09-22"
    assert P.series_tz("openmeteo_samui", "2026-09-22") == "ICT (UTC+7)"
    assert P.series_tz("openmeteo_samui_air", "2026-09-24T14:00:00+00:00") == "UTC"
    assert P.series_tz("cpc_oni", "2026-07-15") == "UTC"


def test_series_kind_rules():
    today = date(2026, 9, 24)
    now = datetime(2026, 9, 24, 14, 0, tzinfo=UTC)
    assert P.series_kind("openmeteo_samui", "2026-09-24", now, today) == "forecast"  # partial
    assert P.series_kind("openmeteo_samui", "2026-09-23", now, today) == "model_analysis"
    assert P.series_kind("openmeteo_marine", "2026-09-30", now, today) == "forecast"
    assert P.series_kind("openmeteo_samui_air", "2026-09-24T13:00:00+00:00", now,
                         today) == "model_analysis"
    assert P.series_kind("openmeteo_samui_air", "2026-09-24T15:00:00+00:00", now,
                         today) == "forecast"
    assert P.series_kind("openmeteo_samui_era5", "2026-09-18", now, today) == "reanalysis"
    assert P.series_kind("cpc_roni", "2026-07-15", now, today) == "observed"
    assert P.series_kind("openmeteo_samui_seasonal", "2026-10-01", now, today) == "forecast"


def test_units_and_rounding():
    assert P.unit_label("degC") == "°C" and P.unit_label("ug/m3") == "µg/m³"
    assert P.rnd(0.46, "m") == 0.5 and P.rnd(50.8, "km/h") == 51
    assert isinstance(P.rnd(50.8, "km/h"), int)
    assert P.fmt_val(3.0, "degC", 1, True) == "+3.0 °C"
    assert P.fmt_val(103, "%") == "103%"


# ------------------------------------------------------------------ factors

def test_heat_forecast_is_never_observed():
    daily("openmeteo_samui", "samui_apparent_temp_max", [35.5, 34, 33, 36, 35, 36, 37.2])
    ok_run("openmeteo_samui")
    f = risk.f_heat()
    last = (today_bkk() + timedelta(days=6)).isoformat()
    assert f["kind"] == "forecast" and f["observed_at"] is None
    assert f["valid_for"] == last and f["as_of"] == f["retrieved_at"] is not None
    assert f["unit"] == "degC" and f["unit_label"].startswith("°C")
    assert f"Forecast max feels-like 37.2 °C on {P.fmt_day(last)}" in f["explanation"]
    assert "degC" not in f["explanation"] + f["threshold"] + f["value_label"]
    assert f["inputs"][0]["kind"] == "forecast"


def test_sea_state_rounded_with_raw_value_kept():
    daily("openmeteo_marine", "samui_wave_height", [0.46, 0.4, 0.3])
    ok_run("openmeteo_marine")
    f = risk.f_sea_state()
    assert f["value"] == 0.5 and f["value_raw"] == 0.46 and f["kind"] == "forecast"
    assert f["observed_at"] is None and f["valid_for"] == today_bkk().isoformat()


def test_enso_value_is_the_driver_with_its_week():
    db.upsert_observations("cpc_roni", [{"series": "roni", "ts": "2026-07-15", "value": 1.36,
                                         "meta": {"season": "JJA 2026"}}])
    db.upsert_observations("cpc_weekly_sst", [{"series": "nino34_weekly_anom",
                                               "ts": "2026-09-16", "value": 3.0}])
    f = risk.f_enso()
    assert f["level"] == 2 and f["value"] == 3.0 and f["details"]["driver"] == "nino34_weekly"
    assert f["valid_for"] == "2026-09-13/2026-09-19" and f["tz"] == "UTC"
    assert f["kind"] == "observed"
    roni = next(i for i in f["inputs"] if i["name"] == "RONI")
    assert roni["valid_for"] == "2026-06-01/2026-08-31" and roni["value"] == 1.36
    assert "RONI (NOAA's official index since 2026) +1.36 °C for JJA 2026" in f["explanation"]
    assert "moderate El Nino range" in f["explanation"]


def test_water_falls_back_to_model_analyses_when_era5_is_missing():
    climatology(5.0)
    y = today_bkk() - timedelta(days=1)
    db.upsert_observations("openmeteo_samui", [
        {"series": "samui_precip", "ts": (y - timedelta(days=i)).isoformat(), "value": 5.0}
        for i in range(92)])
    ok_run("openmeteo_samui")
    w = risk.f_water(enso_level=0, news_water_samui=0)
    assert w["level"] == 0 and w["value"] == 100
    assert w["kind"] == "model_analysis" and w["details"]["fallback"]
    assert "ERA5 reanalysis unavailable" in w["explanation"]
    assert w["valid_for"] == f"{(y - timedelta(days=89)).isoformat()}/{y.isoformat()}"


def test_water_missing_says_what_why_and_where_to_check():
    w = risk.f_water(enso_level=0, news_water_samui=0)
    assert w["level"] is None
    e = w["explanation"]
    assert e.startswith("No current data:") and "Why:" in e
    assert "https://www.pwa.co.th/news/call1662" in e
    assert "data unavailable" not in e


def _air4thai(pm25: float, age_h: float = 1.0) -> None:
    t = (datetime.now(UTC) - timedelta(hours=age_h)).replace(microsecond=0).isoformat()
    db.set_status("air4thai_samui", {"stations": [{
        "station": "42t", "name": "Environment Agency Section 14, Surat Thani",
        "distance_km": 87.0, "pm25": pm25, "aqi": 12.0, "band_label": "Very good",
        "observed_at": t}]})


def test_air_uses_measured_station_when_cams_is_missing():
    _air4thai(7.0)
    f = risk.f_air()
    assert f["level"] == 0 and f["kind"] == "observed" and f["value"] == 7.0
    assert "Koh Samui has no PCD station" in f["explanation"]
    assert "µg/m³" in f["explanation"]


def test_air_level_is_the_worst_of_measured_and_model():
    _air4thai(80.0)
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    db.upsert_observations("openmeteo_samui_air", [
        {"series": "samui_pm2_5", "ts": (now - timedelta(hours=h)).isoformat(), "value": 10.0}
        for h in range(1, 24)])
    ok_run("openmeteo_samui_air")
    f = risk.f_air()
    assert f["level"] == 2 and f["kind"] == "observed" and f["value"] == 80.0


def test_stale_station_is_not_used():
    _air4thai(7.0, age_h=9)
    assert risk.air4thai_nearest() is None
    assert risk.f_air()["level"] is None


# ------------------------------------------------------------------ TMD

TMD_XML = """<rss><channel><item>
<title>ฝนตกหนักถึงหนักมากบริเวณประเทศไทย (มีผลกระทบจนถึงวันที่ 27 กันยายน 2569) ฉบับที่ 7 (223/2569)</title>
<description>ในช่วงวันที่ 24 – 27 ก.ย. 69 บริเวณภาคเหนือ ภาคตะวันออกเฉียงเหนือตอนล่าง ภาคกลาง รวมทั้งกรุงเทพมหานครและปริมณฑล ภาคตะวันออก และภาคใต้ จะมีฝนตกหนักหลายพื้นที่</description>
</item></channel></rss>"""


def test_tmd_period_and_english_summary():
    doc = parse_tmd_storm_tracking(TMD_XML, today=date(2026, 9, 24))
    it = doc["items"][0]
    assert it["from"] == "2026-09-24" and it["until"] == "2026-09-27"
    assert it["summary_en"] == ("TMD bulletin No. 7 (223/2569): heavy to very heavy rain -- "
                                "North, lower Northeast, Central, Bangkok, East, South; "
                                "24-27 Sep 2026")
    assert tmd_period("x", "วันที่ 30 ก.ย. - 2 ต.ค. 69") == ("2026-09-30", "2026-10-02")


# ------------------------------------------------------------------ headline / history

def benign_island() -> None:
    db.upsert_observations("cpc_oni", [{"series": "oni", "value": 1.8, "ts": "2026-07-15",
                                        "meta": {"season": "JJA 2026"}}])
    climatology(5.0)
    end = today_bkk() - timedelta(days=5)
    db.upsert_observations("openmeteo_samui_era5", [
        {"series": "samui_era5_precip", "ts": (end - timedelta(days=i)).isoformat(),
         "value": 5.15} for i in range(200)])
    ok_run("openmeteo_samui_era5")
    daily("openmeteo_samui", "samui_apparent_temp_max", [34] * 7)
    daily("openmeteo_samui", "samui_precip", [5, 5, 5])
    daily("openmeteo_samui", "samui_wind_gust_max", [30, 30, 30])
    ok_run("openmeteo_samui")
    ok_run("gdacs")
    daily("openmeteo_marine", "samui_wave_height", [0.46, 0.6, 0.5])
    ok_run("openmeteo_marine")


def test_headline_is_specific():
    benign_island()
    r = risk.evaluate(save=False)
    h = r["headline"]
    assert h.startswith("Prepare -- strong El Nino (ONI +1.80 °C JJA 2026)")
    assert "No immediate threat on Samui: rain 103% of normal (90 d to" in h
    assert "waves max 0.6 m (forecast to" in h and "no cyclone within 800 km" in h
    assert "Next risk:" in h or "Now:" in h
    assert "degC" not in h
    assert r["headline_local"] and not r["headline_local"].startswith("Prepare")
    assert r["engine_version"] == risk.ENGINE_VERSION


def test_every_factor_carries_provenance_fields():
    benign_island()
    r = risk.evaluate(save=False)
    for f in r["factors"]:
        for k in ("kind", "valid_for", "tz", "unit_label", "value_label", "as_of", "inputs"):
            assert k in f, (f["id"], k)
        if f["level"] is not None:
            assert f["kind"] in P.KINDS, f["id"]
        if f["kind"] == "forecast":
            assert f["observed_at"] is None, f["id"]


def test_legacy_history_rows_are_annotated_not_rewritten():
    db.set_status("local_risk_history", [{"evaluated_at": "2026-09-24T12:32:58+00:00",
                                          "level": 2}])
    risk._append_history({"evaluated_at": "2026-09-24T14:00:00+00:00", "level": 2,
                          "level_key": "prepare", "engine_version": 3})
    h = db.get_status("local_risk_history")["value"]
    assert h[0]["level"] == 2 and h[0]["engine_version"] == 2 and "before" in h[0]["note"]
    assert h[1]["engine_version"] == 3 and h[1]["level_key"] == "prepare"


# ------------------------------------------------------------------ exit + API

def test_exit_signals_label_forecasts():
    daily("openmeteo_marine", "samui_wave_height", [0.46, 0.4, 0.3])
    daily("openmeteo_samui", "samui_wind_gust_max", [50.8, 40, 30])
    ok_run("openmeteo_marine")
    ok_run("openmeteo_samui")
    t = today_bkk()
    w = exit_mod.sea_signal(t)
    g = exit_mod.gust_signal(t)
    for s in (w, g):
        assert s["kind"] == "forecast" and s["observed_at"] is None and s["valid_for"]
    assert w["value"] == 0.5 and g["value"] == 51 and g["unit_label"] == "km/h"
    assert "forecast max 0.5 m on" in w["reason"]


def test_api_latest_skips_todays_partial_model_day_and_annotates():
    from app.main import app
    y = today_bkk() - timedelta(days=1)
    daily("openmeteo_samui", "samui_temp_max", [30.0, 31.0], start=y)   # yesterday, today
    db.upsert_observations("cpc_oni", [{"series": "oni", "ts": "2026-07-15", "value": 1.8,
                                        "unit": "degC"}])
    db.set_status("cpc_alert", {"status": "El Niño Advisory"})
    c = TestClient(app)
    rows = {r["series"]: r for r in c.get("/api/latest").json()}
    assert rows["samui_temp_max"]["ts"] == y.isoformat()
    assert rows["samui_temp_max"]["kind"] == "model_analysis"
    assert rows["oni"]["kind"] == "observed" and rows["oni"]["unit_label"] == "°C"
    assert rows["oni"]["valid_for"] == "2026-06-01/2026-08-31" and rows["oni"]["tz"] == "UTC"
    assert c.get("/api/status/cpc_alert").json()["kind"] == "bulletin"


def test_iri_seasons_interval_is_an_iso_interval():
    """QA 24 Sep 2026: the IRI input carried valid_for "SON..MJJ", which the UI could not
    format ("Forecast for --" on the Samui El Nino card). Nine seasons from SON, issued
    21 Sep 2026 -> 1 Sep 2026 to 31 Jul 2027."""
    from app.local.risk import seasons_interval
    codes = ["SON", "OND", "NDJ", "DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ"]
    assert seasons_interval(codes, "2026-09-21") == "2026-09-01/2027-07-31"
    assert seasons_interval(["DJF"], "2026-11-10") == "2026-12-01/2027-02-28"
    assert seasons_interval(["ASO"], "2026-09-10") == "2027-08-01/2027-10-31"  # next year
    assert seasons_interval([], "2026-09-21") is None
    assert seasons_interval(["XYZ"], "2026-09-21") is None
    assert seasons_interval(codes, None) is None
