"""Places comparison: parsers, collectors, engine and routes, fed with REAL payloads
captured on 2026-09-24 (tests/fixtures/places/*, some trimmed to a subset of rows/years).
No network: every HTTP call is mocked with respx."""

from __future__ import annotations

import json
import os

os.environ.setdefault("SCHEDULER", "false")

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import db
from app.collectors.base import SourceChanged, run_collector
from app.config import settings
from app.places import api, config, engine, enso
from app.places import collectors as pc

FX = Path(__file__).parent / "fixtures" / "places"
NOW = datetime(2026, 9, 24, 15, 0, tzinfo=UTC)


def load(name: str):
    p = FX / name
    return json.loads(p.read_text()) if p.suffix == ".json" else p.read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


def place(pid: str) -> dict:
    return next(p for p in config.DEFAULT_PLACES if p["id"] == pid)


# ------------------------------------------------------------------ config / geocodes

def test_default_places_are_the_three_geocoded_towns():
    ids = [p["id"] for p in config.list_places()]
    assert ids == ["maenam", "saint_gatien", "gorokhovets"]
    m = place("maenam")
    # OSM village point in Ko Samui district (not the misfiled GeoNames point)
    assert (m["lat"], m["lon"]) == (9.5705, 99.9957) and "Surat Thani" in m["admin"]
    assert place("saint_gatien")["timezone"] == "Europe/Paris"
    assert place("gorokhovets")["country_code"] == "RU"


def test_add_and_remove_place_persist():
    geo = load("geocode_gorokhovets.json")["results"][1]  # the Leningrad Oblast namesake
    p = config.add_place(config.build_user_place(geo, 55.0))
    assert p["id"].startswith("gorokhovets") and p["id"] != "gorokhovets"
    assert p["admin"].endswith("Russia") and p["elevation_m"] == 55.0
    assert config.get_place(p["id"]) is not None
    assert config.remove_place("saint_gatien")
    assert [x["id"] for x in config.list_places()] == ["maenam", "gorokhovets", p["id"]]
    assert "saint_gatien" in db.get_status(config.STATUS_KEY)["value"]["removed_defaults"]


# ------------------------------------------------------------------ parsers

def test_parse_forecast_flags_future_days_and_current_utc():
    fc = pc.parse_forecast(load("forecast_gorokhovets.json"), date(2026, 9, 24))
    assert len(fc["daily"]) == 46
    fut = [d for d in fc["daily"] if d["forecast"]]
    assert fut[0]["date"] == "2026-09-25" and len(fut) == 15
    assert fc["current"]["time"].endswith("+00:00")
    assert fc["current"]["kind"] == "model_analysis"
    with pytest.raises(SourceChanged):
        pc.parse_forecast({"daily": {"time": []}}, date(2026, 9, 24))


def test_build_normals_from_real_era5():
    n = pc.build_normals(load("era5_normals_gorokhovets_1991_1992.json"), min_years=2)
    assert n["period"] == "1991-1992" and len(n["months"]) == 12
    jan, jul = n["months"][0], n["months"][6]
    assert jan["t_mean"] < -3 and jul["t_mean"] > 15      # continental climate
    assert jan["frost_days"] > 20 and jan["heat_days"] == 0
    a = n["annual"]
    assert a["coldest_month_t_mean"] == min(m["t_mean"] for m in n["months"])
    assert a["aridity_index"] == round(a["precip_mm"] / a["et0_mm"], 2)
    with pytest.raises(SourceChanged):
        pc.build_normals(load("era5_normals_gorokhovets_1991_1992.json"))  # 25 years needed


def test_parse_recent_uses_era5_daily():
    r = pc.parse_recent(load("era5_normals_gorokhovets_1991_1992.json"))
    assert r["last_day"] == "1992-12-31" and len(r["days"]) == 731


def test_parse_air_and_year():
    a = pc.parse_air(load("air_saint_gatien.json"), now=NOW)
    assert a["current"]["pm2_5"] is not None and a["pollen"] is not None  # CAMS Europe
    assert any(x["forecast"] for x in a["hourly_pm2_5"])
    y = pc.build_air_year(load("air_year_maenam_mar_apr.json"), min_days=50)
    assert y["days"] == 61 and 0 < y["pm25_annual_mean"] < 200
    assert set(y["monthly_mean"]) == {"03", "04"}
    with pytest.raises(SourceChanged):
        pc.build_air_year(load("air_year_maenam_mar_apr.json"))


def test_parse_marine_coastal_and_inland():
    m = pc.parse_marine(load("marine_maenam.json"), 9.5705, 99.9957)
    assert m["sea_cell"] and m["cell_distance_km"] < 10 and m["daily"]
    g = pc.parse_marine(load("marine_gorokhovets_inland.json"), 56.2066, 42.679)
    assert not g["sea_cell"] and g["cell_distance_km"] is None and g["daily"] == []


def test_river_cell_and_flood_levels():
    cell = pc.choose_river_cell(load("flood_grid_saint_gatien.json"), 49.3489, 0.1851)
    assert cell["mean_m3s"] > 100 and 5 < cell["distance_km"] < 20  # the Seine estuary
    clim = pc.build_river_climate(load("flood_history_klyazma_2001_2003.json"), min_years=3)
    assert clim["years"] == 3 and clim["q2_m3s"] <= clim["max_m3s"]
    fc = pc.parse_flood_forecast(load("flood_forecast_klyazma.json"))
    assert len(fc["days"]) >= 30 and all(d["q"] >= 0 for d in fc["days"])
    tiny = [{"latitude": 1, "longitude": 1, "daily": {"river_discharge": [0.1, 0.2]}}]
    assert pc.choose_river_cell(tiny, 1, 1) is None
    with pytest.raises(SourceChanged):
        pc.choose_river_cell([{"daily": {}}], 1, 1)


def test_projection_windows():
    base = load("climate_saint_gatien_1991_1992.json")
    fut = load("climate_saint_gatien_2049_2050.json")
    pr = pc.build_projection(base, fut, base_years=(1991, 1992), future=(2049, 2050))
    assert pr["n_models"] >= 3 and pr["future"] == "2049-2050"
    d = pr["delta"]["t_mean"]
    assert d["min"] <= d["mean"] <= d["max"]
    assert set(pr["per_model"]) <= set(pc.CMIP6_MODELS)


def test_usgs_and_firms():
    q = pc.parse_usgs_near(load("usgs_hist_maenam.json"), 9.5705, 99.9957)
    assert q and max(x["mag"] for x in q) >= 4.5 and all(x["distance_km"] <= 300 for x in q)
    assert pc.parse_usgs_near(load("usgs_recent_gorokhovets_empty.json"), 56.2, 42.7) == []
    assert pc.firms_region(49.35, 0.19) == "Europe"
    assert pc.firms_region(56.2, 42.7) == "Russia_Asia"  # Europe file stops at 35 E
    assert pc.firms_region(9.57, 99.99) == "SouthEast_Asia"
    f = pc.parse_firms_near(load("firms_Europe_near.csv"), 49.3489, 0.1851)
    assert f["count"] >= 0 and f["count_50km"] <= f["count"]
    with pytest.raises(SourceChanged):
        pc.parse_firms_near("a,b\n1,2\n", 0, 0)


def test_meteoalarm():
    doc = pc.parse_meteoalarm(load("meteoalarm_spain.xml"))
    w = doc["warnings"][0]
    assert w["colour"] == "yellow" and w["level"] == 1 and w["emma_id"] == "ES131"
    area = w["area"]
    now = datetime.fromisoformat(w["effective"])
    assert pc.meteoalarm_for(doc, [area], now) and not pc.meteoalarm_for(doc, ["Calvados"], now)
    later = datetime(2030, 1, 1, tzinfo=UTC)
    assert pc.meteoalarm_for(doc, [area], later) == []  # expired
    empty = pc.parse_meteoalarm(load("meteoalarm_france_empty.xml"))
    assert empty["warnings"] == [] and empty["updated"]
    with pytest.raises(SourceChanged):
        pc.parse_meteoalarm("<html/>")


def test_hydromet_bulletin():
    b = pc.parse_hydromet_bulletin(load("meteoinfo_hazardsbull.html"))
    assert b["number"] == 267 and b["date"] == "2026-09-24"
    assert "Центральный федеральный округ" in b["forecast"] and b["observed"]
    vl = pc.hydromet_for(b, "Владимирск")
    assert vl["forecast_mentions"] == []
    lp = pc.hydromet_for(b, "Липецк")
    assert lp["forecast_mentions"] and not lp["severe_wording"]
    kr = pc.hydromet_for(b, "Краснодарск")
    assert kr["severe_wording"]  # "сильный и очень сильный дождь"
    with pytest.raises(SourceChanged):
        pc.parse_hydromet_bulletin("<html></html>")


def test_advisories():
    ru = pc.parse_fcdo(load("fcdo_russia.json"), "russia")
    assert ru["alert_status"] == ["avoid_all_travel_to_whole_country"]
    assert ru["headline"].startswith("Advises against all travel") and ru["updated"]
    fr = pc.parse_fcdo(load("fcdo_france.json"), "france")
    assert fr["headline"] == "No FCDO advice against travel"
    st = pc.parse_state_rss(load("state_advisories_3.xml"))
    assert st["Russia"]["level"] == 4 and st["Thailand"]["level"] == 1
    assert st["France"]["updated"] == "2025-05-28"
    d = pc.parse_fr_diplomatie(load("fr_diplomatie_russie.html"), "https://x")
    assert d["updated"] == "2026-09-10" and d["headline"] and d["lang"] == "fr"
    assert all(u.startswith("https://www.diplomatie.gouv.fr/") for u in d["headline_urls"])
    with pytest.raises(SourceChanged):
        pc.parse_fcdo({"details": {}}, "x")


# ------------------------------------------------------------------ collectors

@respx.mock
async def test_forecast_collector_one_place_failing_does_not_hide_others():
    def reply(request):
        lat = float(request.url.params["latitude"])
        if lat > 50:
            return httpx.Response(503)
        return httpx.Response(200, json=load("forecast_maenam.json"))
    respx.get(url__startswith=pc.FORECAST_URL).mock(side_effect=reply)
    async with httpx.AsyncClient() as client:
        res = await run_collector(pc.PlacesForecast(), client)
    assert res["ok"] and res["items"] == 2
    run = db.query("SELECT detail FROM source_runs WHERE source='places_forecast'")[0]
    assert list(run["detail"]["errors"]) == ["gorokhovets"]
    assert db.get_status("place:maenam:forecast") is not None


@respx.mock
async def test_collector_fails_when_every_place_fails():
    respx.get(url__startswith=pc.FORECAST_URL).mock(return_value=httpx.Response(500))
    async with httpx.AsyncClient() as client:
        res = await run_collector(pc.PlacesForecast(), client)
    assert not res["ok"]


@respx.mock
async def test_warnings_and_advisories_collectors():
    respx.get(pc.METEOALARM_URL.format(feed="france")).mock(
        return_value=httpx.Response(200, text=load("meteoalarm_france_empty.xml")))
    respx.get(pc.HYDROMET_RU_URL).mock(
        return_value=httpx.Response(200, text=load("meteoinfo_hazardsbull.html")))
    respx.get(pc.STATE_RSS).mock(
        return_value=httpx.Response(200, text=load("state_advisories_3.xml")))
    for slug in ("thailand", "france", "russia"):
        respx.get(pc.FCDO_API.format(slug=slug)).mock(
            return_value=httpx.Response(200, json=load(f"fcdo_{slug}.json")))
    respx.get(url__startswith="https://www.diplomatie.gouv.fr/").mock(
        return_value=httpx.Response(200, text=load("fr_diplomatie_russie.html")))
    async with httpx.AsyncClient() as client:
        w = await run_collector(pc.PlacesWarnings(), client)
        a = await run_collector(pc.PlacesAdvisories(), client)
    assert w["ok"] and w["items"] == 2
    assert a["ok"]
    adv = db.get_status("places_advisories")["value"]["countries"]
    assert adv["RU"]["state"]["level"] == 4 and "fr_diplomatie" not in adv["FR"]


@respx.mock
async def test_projection_collector_two_stages(monkeypatch):
    monkeypatch.setattr(pc, "HEAVY_MIN_UPTIME_S", 0)
    monkeypatch.setattr(pc, "HEAVY_GAP_S", 0)
    monkeypatch.setattr(pc, "_last_heavy", [])
    monkeypatch.setattr(pc, "PROJ_BASE", (1991, 1992))
    monkeypatch.setattr(pc, "PROJ_FUTURE", (2049, 2050))

    def reply(request):
        start = request.url.params["start_date"]
        name = ("climate_saint_gatien_1991_1992.json" if start.startswith("1991")
                else "climate_saint_gatien_2049_2050.json")
        return httpx.Response(200, json=load(name))
    route = respx.get(url__startswith=pc.CLIMATE_URL).mock(side_effect=reply)
    async with httpx.AsyncClient() as client:
        r1 = await run_collector(pc.PlacesProjection(), client)
        assert r1["ok"] and route.call_count == 1           # one heavy request per run
        assert db.get_status("place:maenam:projection_base") is not None
        await run_collector(pc.PlacesProjection(), client)
        assert db.get_status("place:maenam:projection") is not None
        assert route.call_count == 2
    pr = db.get_status("place:maenam:projection")["value"]
    assert pr["baseline"] == "1991-1992" and pr["future"] == "2049-2050"
    run = db.query("SELECT detail FROM source_runs WHERE source='places_projection' "
                   "ORDER BY id DESC LIMIT 1")[0]
    assert "saint_gatien" in run["detail"]["pending"]


def test_water_factor_percent_of_normal(monkeypatch):
    # Gorokhovets normals (coldest month -8 C) -> temperate profile; the stored series is
    # 121 days, so only the 90-day window exists and the explanation says why
    normals = pc.build_normals(load("era5_normals_gorokhovets_1991_1992.json"), min_years=2)
    rec = pc.parse_recent(load("era5_recent_saint_gatien.json"))
    seed("gorokhovets", normals=normals, recent=rec)
    f = engine.f_water(place("gorokhovets"), NOW)
    days = [d["date"] for d in rec["days"][-90:]]
    norm = engine.normal_for_days(normals, days)
    assert f["details"]["normal_mm"] == round(norm, 0) and f["kind"] == "reanalysis"
    assert f["details"]["profile"] == "temperate" and f["details"]["window_days"] == 90
    assert not f["stale"] and f["level"] == min(engine.pct_level(f["value"], (60, 35, None)), 2)
    assert "could not be computed" in f["explanation"]


# Real ERA5 captured 2026-09-24: Maenam and Saint-Gatien 1991-2020 normals docs (built by
# pc.build_normals from the full archive), Maenam last 120 days, Saint-Gatien last 400 days.

def _scaled(rec: dict, k: float) -> dict:
    return rec | {"days": [d | {"precip": d["precip"] * k} for d in rec["days"]]}


def _samui_rule(rec: dict, normals: dict) -> tuple[int, float]:
    """The water rule as it was before the profiles (and as on the Koh Samui watch)."""
    days = rec["days"][-90:]
    obs = sum(d["precip"] for d in days)
    norm = engine.normal_for_days(normals, [d["date"] for d in days])
    pct = 100 * obs / norm
    lv = 3 if pct < 40 else 2 if pct < 60 else 1 if pct < 75 else 0
    if lv == 3 and norm - obs < 100:
        lv = 2
    return lv, round(pct, 0)


def test_water_profiles_from_normals():
    mae, sg = load("normals_doc_maenam.json"), load("normals_doc_saint_gatien.json")
    assert engine.water_profile(place("maenam"), mae)[0] == "tropical"
    assert engine.water_profile(place("saint_gatien"), sg)[0] == "temperate"
    dry = json.loads(json.dumps(sg))
    dry["annual"]["aridity_index"] = 0.3
    assert engine.water_profile(place("saint_gatien"), dry)[0] == "dry"
    forced = place("saint_gatien") | {"water_profile": "tropical"}
    assert engine.water_profile(forced, sg) == ("tropical", "set for this place")


@pytest.mark.parametrize("k", [1.0, 0.6, 0.3, 0.05])
def test_water_samui_unchanged(k):
    normals = load("normals_doc_maenam.json")
    rec = _scaled(pc.parse_recent(load("era5_recent_maenam.json")), k)
    seed("maenam", normals=normals, recent=rec)
    f = engine.f_water(place("maenam"), NOW)
    lv, pct = _samui_rule(rec, normals)
    assert (f["level"], f["value"], f["unit"]) == (lv, pct, "% of normal")
    assert f["label"] == "Water (rain of the last 90 days vs normal)"
    assert f["threshold"] == "< 75% watch, < 60% prepare, < 40% and >= 100 mm short act"
    assert f["details"]["profile"] == "tropical" and "Profile: tropical" in f["explanation"]
    if k == 1.0:
        assert f["level"] == 0  # 2026-09-18: 287 mm vs 289 mm normal
    if k == 0.05:
        assert f["level"] == 3


def test_water_normandy_dry_quarter_with_normal_year_is_not_act():
    normals = load("normals_doc_saint_gatien.json")
    rec = pc.parse_recent(load("era5_recent400_saint_gatien.json"))
    seed("saint_gatien", normals=normals, recent=rec)
    f = engine.f_water(place("saint_gatien"), NOW)
    w = {x["days"]: x for x in f["details"]["windows"]}
    assert w[90]["pct"] == 38 and w[365]["pct"] == 87      # real values to 2026-09-18
    assert _samui_rule(rec, normals)[0] == 3                # the old rule said "act"
    assert f["level"] == 1 and f["level_key"] == "vigilance"
    assert w[180]["raw_level"] == 2 and w[180]["level"] == 1  # capped by the normal year
    assert "365 d: 678 mm = 87% of normal" in f["explanation"]
    assert "could not be computed" not in f["explanation"]
    # only 120 days stored (the collector today): degrades to 90 days, says so, not act
    short = pc.parse_recent(load("era5_recent_saint_gatien.json"))
    seed("saint_gatien", recent=short)
    g = engine.f_water(place("saint_gatien"), NOW)
    assert g["level"] == 1 and g["details"]["window_days"] == 90
    assert "The 180-day and 365-day windows could not be computed" in g["explanation"]
    assert not any(x["available"] for x in g["details"]["windows"] if x["days"] > 90)


def test_water_temperate_long_drought_still_escalates():
    normals = load("normals_doc_saint_gatien.json")
    rec = pc.parse_recent(load("era5_recent400_saint_gatien.json"))
    seed("saint_gatien", normals=normals, recent=_scaled(rec, 0.6))  # 365 d at ~52%
    f = engine.f_water(place("saint_gatien"), NOW)
    assert f["level"] == 3 and f["details"]["window_days"] == 365
    seed("saint_gatien", recent=_scaled(rec, 0.9))  # 365 d ~78% Watch, 180 d ~53% Prepare
    g = engine.f_water(place("saint_gatien"), NOW)
    assert g["level"] == 2 and g["details"]["window_days"] == 180
    # 90 days alone never reaches act, even when nearly dry
    short = pc.parse_recent(load("era5_recent_saint_gatien.json"))
    seed("saint_gatien", recent=_scaled(short, 0.2))
    h = engine.f_water(place("saint_gatien"), NOW)
    assert h["level"] == 2 and "provisional" in h["explanation"]


def test_heavy_budget_gates(monkeypatch):
    from types import SimpleNamespace

    ctx = SimpleNamespace(notes={})
    monkeypatch.setattr(pc, "HEAVY_MIN_UPTIME_S", 0)
    monkeypatch.setattr(pc, "HEAVY_GAP_S", 0)
    monkeypatch.setattr(pc, "_last_heavy", [])
    b = pc.HeavyBudget(ctx)
    assert b.take("a", 100) and not b.take("b", 100)  # one per run
    assert ctx.notes["pending"] == ["b"]
    b2 = pc.HeavyBudget(ctx)
    assert not b2.take("c", pc.HEAVY_DAILY_WEIGHT)     # daily weight cap
    monkeypatch.setattr(pc, "HEAVY_GAP_S", 3600)
    assert not pc.HeavyBudget(ctx).take("d", 1)       # too soon after the last one
    assert pc.om_weight(9, 10957) == pytest.approx(10957 / 14)
    assert pc.om_weight(18, 14) == pytest.approx(1.8)


# ------------------------------------------------------------------ engine

def seed(pid: str, **docs) -> None:
    for kind, value in docs.items():
        db.set_status(pc.status_key(pid, kind), value)


def test_levels_bands():
    assert engine.heat_level(38.9, 0) == 0 and engine.heat_level(41, 3) == 3
    assert engine.cold_level(-5) == 0 and engine.cold_level(-30) == 2
    assert engine.cold_level(-50) == 4
    assert engine.rain_deficit_level(80) == 0 and engine.rain_deficit_level(39) == 3
    assert engine.gust_level(90) == 2 and engine.pm25_level(40) == 1
    assert engine.band(0.4, (0.5, 2, 5, 10)) == 0 and engine.band(12, (0.5, 2, 5, 10)) == 4


def test_unknown_level_without_data_never_normal():
    s = engine.place_summary(place("saint_gatien"), NOW)
    assert s["level"] is None and s["level_key"] == "unknown"
    assert set(s["missing_critical"]) == {"heat", "water", "flood", "storm"}


def test_place_with_real_data_gets_explainable_factors(monkeypatch):
    monkeypatch.setattr(engine, "_place_today", lambda p: date(2026, 9, 24))
    fc = pc.parse_forecast(load("forecast_gorokhovets.json"), date(2026, 9, 24))
    normals = pc.build_normals(load("era5_normals_gorokhovets_1991_1992.json"), min_years=2)
    seed("gorokhovets", forecast=fc, normals=normals,
         recent=pc.parse_recent(load("era5_normals_gorokhovets_1991_1992.json")),
         air=pc.parse_air(load("air_saint_gatien.json"), now=NOW))
    s = engine.place_summary(place("gorokhovets"), NOW)
    ids = [f["id"] for f in s["factors"]]
    assert ids == ["heat", "cold", "water", "flood", "storm", "air", "wildfire",
                   "earthquake", "warnings"]
    for f in s["factors"]:
        assert f["threshold"] or f["level"] is None
        assert f["explanation"]
    heat = s["factors"][0]
    assert heat["kind"] == "forecast" and heat["level"] == 0
    # the recent ERA5 fixture ends in 1992: too old, the water factor cannot say "normal"
    water = s["factors"][2]
    assert water["stale"] and water["level"] in (None, 1, 2, 3)
    ex = engine.exposure(place("gorokhovets"))
    assert ex["cold"]["score"] >= 3 and ex["heat_stress"]["score"] == 0
    assert ex["enso"]["score"] == 1 and ex["trend_2050"]["score"] is None
    assert "trend_2050" in ex["coverage"]["details"]["missing"]


def test_combine_rules():
    f = [engine.factor("heat", "h", 2), engine.factor("flood", "f", 2),
         engine.factor("water", "w", 0), engine.factor("storm", "s", 0),
         engine.factor("earthquake", "q", 3)]
    c = engine.combine(f)
    assert c["level"] == 3 and any(r.startswith("R3") for r in c["rules"])
    c2 = engine.combine([engine.factor("earthquake", "q", 3), engine.factor("heat", "h", 0),
                         engine.factor("water", "w", 0), engine.factor("flood", "f", 0),
                         engine.factor("storm", "s", 0)])
    assert c2["level"] == 2  # earthquake capped at prepare


def test_ranking_weights_and_missing():
    expo = {"a": {"heat_stress": {"score": 4}, "cold": {"score": 0}},
            "b": {"heat_stress": {"score": 0}, "cold": {"score": 4}}}
    w = engine.parse_weights("heat_stress:1,cold:0,bogus:5")
    assert w["cold"] == 0 and "bogus" not in w
    r = engine.ranking(expo, w)
    assert r[0]["id"] == "b" and r[0]["score"] == 100.0
    assert "water" in r[0]["missing"]
    r2 = engine.ranking(expo, engine.parse_weights("heat_stress:1,cold:3"))
    assert r2[0]["id"] == "a"


def test_enso_assessment_per_place():
    assert enso.assess(9.5705, 99.9957)["strength"] == 3
    assert enso.assess(49.3489, 0.1851)["region"] == "western_europe"
    assert enso.assess(56.2066, 42.679)["region"] == "european_russia"
    na = enso.assess(-33.9, 18.4)
    assert not na["assessed"] and na["strength"] is None
    for r in enso.REGIONS:
        assert r["sources"] and all(s in enso.SOURCES for s in r["sources"])


def test_compare_summary_is_factual():
    normals = pc.build_normals(load("era5_normals_gorokhovets_1991_1992.json"), min_years=2)
    seed("gorokhovets", normals=normals)
    hot = json.loads(json.dumps(normals))
    hot["annual"]["heat_days"], hot["annual"]["coldest_month_t_mean"] = 200.0, 25.0
    seed("maenam", normals=hot)
    out = engine.compare("heat_stress:2")
    assert out["weights"]["heat_stress"] == 2 and out["disclaimer"].startswith("Decision aid")
    heat = next(x for x in out["summary"] if x["dimension"] == "heat_stress")
    assert heat["best"] == ["gorokhovets"] and heat["worst"] == ["maenam"]
    assert out["matrix"]["heat_stress"]["saint_gatien"]["score"] is None
    assert [d["id"] for d in out["dimensions"]][-1] == "coverage"


# ------------------------------------------------------------------ routes

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def test_routes_list_detail_compare(client):
    r = client.get("/api/places")
    assert r.status_code == 200 and len(r.json()["places"]) == 3
    assert r.json()["can_edit"] is True
    d = client.get("/api/places/maenam").json()
    assert d["enso"]["strength"] == 3 and "exposure" in d and d["level_key"] == "unknown"
    assert client.get("/api/places/nowhere").status_code == 404
    c = client.get("/api/places/compare?weights=cold:3").json()
    assert c["weights"]["cold"] == 3 and len(c["ranking"]) == 3


@respx.mock
def test_add_place_admin_only_in_public_mode(client, monkeypatch):
    async def no_refresh(names):
        return None
    monkeypatch.setattr(api, "_refresh", no_refresh)
    respx.get(api.ELEVATION_URL).mock(return_value=httpx.Response(200, json={"elevation": [55.0]}))
    geo = load("geocode_gorokhovets.json")["results"][1]
    body = {k: geo.get(k) for k in ("id", "name", "latitude", "longitude", "elevation",
                                    "timezone", "country", "country_code", "admin1")}
    monkeypatch.setattr(settings, "public_mode", True, raising=False)
    monkeypatch.setattr(settings, "admin_token", "s3cret", raising=False)
    assert client.post("/api/places", json=body).status_code == 403
    assert client.delete("/api/places/maenam").status_code == 403
    r = client.post("/api/places", json=body, headers={"X-Admin-Token": "s3cret"})
    assert r.status_code == 200 and r.json()["place"]["elevation_m"] == 55.0
    pid = r.json()["place"]["id"]
    assert client.post("/api/places", json=body,
                       headers={"X-Admin-Token": "s3cret"}).status_code == 409  # duplicate
    assert client.delete(f"/api/places/{pid}",
                         headers={"X-Admin-Token": "s3cret"}).json() == {"removed": pid}


@respx.mock
def test_search_proxies_geocoder(client):
    respx.get(api.GEOCODE_URL).mock(
        return_value=httpx.Response(200, json=load("geocode_gorokhovets.json")))
    r = client.get("/api/places/search?q=Gorokhovets").json()
    assert r["results"][0]["admin1"] == "Vladimir Oblast"
