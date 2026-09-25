"""Regression tests for the fixes of the senior review (docs/reports/REVIEW_2026-09-24.md).

Every fixture is a REAL captured payload (tests/fixtures/*); no network."""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("SCHEDULER", "false")

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import cams_api, db, security
from app.collectors import extra_hazards as H
from app.collectors.base import SourceChanged, run_collector
from app.config import settings
from app.local import collectors as lc
from app.local import provenance as P
from app.main import app
from app.places import api as places_api

FIX = Path(__file__).parent / "fixtures"
TOKEN = "t" * 64
ADMIN = {security.ADMIN_HEADER: TOKEN}
PREP = {"checked": {}, "household": {"adults": 2, "children": 1, "days": 21}}
c = TestClient(app)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    db.reset_for_tests()
    monkeypatch.setattr(settings, "public_mode", False)
    monkeypatch.setattr(settings, "admin_token", "")
    places_api._search_cache.clear()
    places_api._preview_cache.clear()
    places_api._search_budget.reset()
    places_api._preview_budget.reset()
    cams_api._cache.clear()


@pytest.fixture
def public(monkeypatch):
    monkeypatch.setattr(settings, "public_mode", True)
    monkeypatch.setattr(settings, "admin_token", TOKEN)


# ------------------------------------------------------------------ 1. prep_state side door


@pytest.mark.usefixtures("public")
def test_owner_household_never_leaks_through_status_routes():
    assert c.put("/api/preparedness/state", json=PREP, headers=ADMIN).status_code == 200
    # the generic status routes must hide it exactly like /api/preparedness/state does
    assert "prep_state" not in c.get("/api/status").json()
    assert c.get("/api/status/prep_state").status_code == 404
    assert c.get("/api/status/prep_state/").status_code == 404
    # the owner still sees it, and other status keys stay public
    db.set_status("cpc_alert", {"status": "El Nino Advisory"})
    assert c.get("/api/status/prep_state", headers=ADMIN).json()["value"]["household"][
        "adults"] == 2
    assert c.get("/api/status", headers=ADMIN).json()["prep_state"]["value"] == PREP
    assert c.get("/api/status/cpc_alert").status_code == 200
    assert "cpc_alert" in c.get("/api/status").json()


def test_prep_state_visible_on_the_localhost_install():
    c.put("/api/preparedness/state", json=PREP)
    assert c.get("/api/status/prep_state").status_code == 200
    assert "prep_state" in c.get("/api/status").json()


# ------------------------------------------------------------------ 2. JTWC month rollover


def test_jtwc_dtg_resolves_forward_across_a_month_change():
    ref = datetime(2026, 9, 29, 9, 0, tzinfo=UTC)  # warning issued 29 Sep 09Z
    assert H._dtg("290600", ref) == datetime(2026, 9, 29, 6, 0, tzinfo=UTC)
    assert H._dtg("011800", ref) == datetime(2026, 10, 1, 18, 0, tzinfo=UTC)   # TAU 60
    assert H._dtg("040600", ref) == datetime(2026, 10, 4, 6, 0, tzinfo=UTC)    # TAU 120
    # backwards still works (issued 1 Oct, analysis position of 30 Sep) and across a year
    ref = datetime(2027, 1, 1, 3, 0, tzinfo=UTC)
    assert H._dtg("311800", ref) == datetime(2026, 12, 31, 18, 0, tzinfo=UTC)
    assert H._dtg("050000", ref) == datetime(2027, 1, 5, 0, 0, tzinfo=UTC)
    with pytest.raises(SourceChanged):
        H._dtg("990000", ref)


def test_jtwc_forecast_track_dates_are_monotonic_across_month_end():
    """The real 25W warning (issued 24 Sep) re-read as if issued on 29 Sep: every forecast
    position must be dated after the previous one (the old code sent day 1-4 of October
    back to 1-4 September)."""
    text = (FIX / "extra" / "jtwc_wp2526web.txt").read_text()
    shifted = text
    for old, new in (("29", "04"), ("28", "03"), ("27", "02"), ("26", "01"), ("25", "30"),
                     ("24", "29")):
        shifted = shifted.replace(f"\n   {old}0600Z", f"\n   {new}0600Z").replace(
            f"\n   {old}1800Z", f"\n   {new}1800Z")
    ev = H.parse_jtwc_warning(shifted, "wp2526", datetime(2026, 9, 29, 9, 0, tzinfo=UTC))
    dates = [p["valid_at"] for p in ev["payload"]["forecast"]]
    assert dates == sorted(dates) and len(dates) == 9
    assert dates[0].startswith("2026-09-29") and dates[-1].startswith("2026-10-04")
    assert ev["updated_at"] == "2026-09-29T06:00:00+00:00"


# ------------------------------------------------------------------ 3. Ratchaprapa from dam_load


def test_ratchaprapa_from_the_light_dam_table():
    doc = json.loads((FIX / "hazards" / "thaiwater_dam_load.json").read_text())
    dams = lc.parse_thaiwater_dams(doc)
    assert [d["name"] for d in dams] == ["Ratchaprapa"]
    d = dams[0]
    assert d["date"] == "2026-09-24" and d["storage_pct"] == 72.84
    assert d["province"] == "Surat Thani" and d["storage_mcm"] == 4107.23
    # the old 10 MB thailand_main shape still parses to the same row
    main = json.loads((FIX / "local" / "thaiwater_main_dam.json").read_text())
    assert lc.parse_thaiwater_dams(main)[0]["name"] == "Ratchaprapa"
    with pytest.raises(SourceChanged):
        lc.parse_thaiwater_dams({"dam_data": {"data": "nope"}})


def test_dam_rows_prefer_rid_and_the_newest_date():
    row = json.loads((FIX / "hazards" / "thaiwater_dam_load.json").read_text())
    r = next(x for x in row["dam_data"]["data"] if x["dam"]["dam_name"]["en"] == "Ratchaprapa")
    egat = json.loads(json.dumps(r))
    egat["agency"]["agency_shortname"]["en"] = "EGAT"
    egat["dam_storage_percent"] = 1.0
    older = json.loads(json.dumps(r))
    older["dam_date"] = "2026-09-20"
    older["dam_storage_percent"] = 70.0
    out = lc.parse_thaiwater_dams({"dam_data": {"data": [egat, older, r]}})
    assert len(out) == 1 and out[0]["storage_pct"] == 72.84 and out[0]["date"] == "2026-09-24"


@respx.mock
async def test_dam_collector_fetches_dam_load_not_thailand_main():
    route = respx.get(lc.THAIWATER_DAMS_URL).mock(return_value=httpx.Response(
        200, content=(FIX / "hazards" / "thaiwater_dam_load.json").read_bytes()))
    big = respx.get(lc.THAIWATER_MAIN_URL).mock(return_value=httpx.Response(500))
    async with httpx.AsyncClient() as client:
        res = await run_collector(lc.ThaiWaterDams(), client)
    assert res["ok"] and res["items"] == 1, res
    assert route.called and not big.called
    row = db.query("SELECT * FROM observations WHERE source='thaiwater_dams'")[0]
    assert row["series"] == "surat_ratchaprapa_storage_pct" and row["value"] == 72.84
    assert lc.ThaiWaterDams.endpoint == lc.THAIWATER_DAMS_URL


# ------------------------------------------------------------------ 4. places proxies: bounded


@pytest.fixture
def pclient():
    a = FastAPI()
    a.include_router(places_api.router)
    return TestClient(a)


def _geo():
    return httpx.Response(200, content=(FIX / "places" / "geocode_gorokhovets.json").read_bytes())


@respx.mock
def test_search_cache_is_bounded_and_upstream_calls_budgeted(pclient, monkeypatch):
    route = respx.get(places_api.GEOCODE_URL).mock(return_value=_geo())
    monkeypatch.setattr(places_api._search_cache, "max_items", 3)
    monkeypatch.setattr(places_api._search_budget, "limit", 4)
    for q in ("Gorokhovets", "Vladimir", "Moscow", "Suzdal"):
        assert pclient.get(f"/api/places/search?q={q}").status_code == 200
    assert len(places_api._search_cache) == 3          # oldest entry evicted
    assert pclient.get("/api/places/search?q=Suzdal").status_code == 200  # cache hit: free
    r = pclient.get("/api/places/search?q=Kovrov")       # 5th upstream call in the hour
    assert r.status_code == 429 and "budget" in r.json()["detail"]
    assert route.call_count == 4


@respx.mock
def test_preview_cache_is_bounded_and_upstream_calls_budgeted(pclient, monkeypatch):
    route = respx.get(places_api.FORECAST_URL).mock(return_value=httpx.Response(
        200, content=(FIX / "places" / "forecast_maenam.json").read_bytes()))
    monkeypatch.setattr(places_api._preview_cache, "max_items", 2)
    monkeypatch.setattr(places_api._preview_budget, "limit", 3)
    for lat in (9.5, 9.6, 9.7):
        r = pclient.get(f"/api/places/preview?lat={lat}&lon=100.0&name=x&timezone=Asia/Bangkok")
        assert r.status_code == 200, r.text
    assert len(places_api._preview_cache) == 2
    assert pclient.get("/api/places/preview?lat=9.7&lon=100.0").status_code == 200  # cached
    assert pclient.get("/api/places/preview?lat=9.8&lon=100.0").status_code == 429
    assert route.call_count == 3


def test_upstream_budget_window_rolls():
    b = places_api.UpstreamBudget(2, window_s=0.0)  # a zero window: every call is fresh
    assert b.take() and b.take() and b.take()
    b = places_api.UpstreamBudget(1, window_s=3600)
    assert b.take() and not b.take()
    b.reset()
    assert b.take()


# ------------------------------------------------------------------ 5. snapshot cache bound


def test_snapshot_cache_stays_small():
    assert cams_api.SNAPSHOT_CACHE_MAX * cams_api.SNAPSHOT_MAX_BYTES <= 40_000_000


# ------------------------------------------------------------------ 6. provenance kinds


def test_climate_pulse_is_labelled_reanalysis_not_observed():
    row = {"source": "c3s_climate_pulse", "series": "era5_global_t2m_anom", "ts": "2026-09-22",
           "value": 0.7, "unit": "degC"}
    assert P.annotate_point(row)["kind"] == "reanalysis"
    assert P.series_kind("cpc_oni", "2026-07-15") == "observed"


# ------------------------------------------------------------------ 7. places: 400-day ERA5


from app.places import collectors as pc
from app.places import config as pconfig
from app.places import engine as pengine


def _pl(name: str):
    return json.loads((FIX / "places" / name).read_text())


def test_merge_recent_new_values_win_and_window_is_trimmed():
    full = pc.parse_recent(_pl("era5_recent400_saint_gatien.json"))
    top = pc.parse_recent(_pl("era5_topup20_saint_gatien.json"))
    assert len(full["days"]) >= 390 and top["last_day"] == full["last_day"]
    cached = pc.merge_recent(None, full)
    assert cached["window_days"] == 400 and cached["first_day"] == full["days"][0]["date"]
    # a revised tail (ERA5 re-runs its last days): the new value replaces the old one
    revised = {"days": [d | {"precip": d["precip"] + 5.0} for d in top["days"][-3:]],
               "last_day": top["last_day"]}
    merged = pc.merge_recent(cached, revised)
    by = {d["date"]: d for d in merged["days"]}
    for d in revised["days"]:
        assert by[d["date"]]["precip"] == pytest.approx(d["precip"])
    assert len(merged["days"]) == len(cached["days"]) and merged["window_days"] == 400
    # a top-up that adds newer days pushes the oldest ones out of the 400-day window
    newer = {"days": [{"date": "2026-10-01", "precip": 1.0, "tmax": 15.0, "tmin": 8.0}],
             "last_day": "2026-10-01"}
    m2 = pc.merge_recent(cached, newer)
    assert m2["last_day"] == "2026-10-01" and m2["days"][0]["date"] > cached["first_day"]
    assert (date.fromisoformat(m2["last_day"]) - date.fromisoformat(m2["first_day"])).days < 400


@respx.mock
async def test_places_climate_bulk_then_daily_topup(monkeypatch):
    monkeypatch.setattr(pc, "HEAVY_MIN_UPTIME_S", 0)
    monkeypatch.setattr(pc, "HEAVY_GAP_S", 0)
    monkeypatch.setattr(pc, "_last_heavy", [])
    calls: list[tuple[str, str]] = []

    def reply(request):
        s, e = request.url.params["start_date"], request.url.params["end_date"]
        calls.append((s, e))
        span = (date.fromisoformat(e) - date.fromisoformat(s)).days
        if s.startswith("1991"):
            return httpx.Response(429, text="quota")            # normals: not in this test
        if span >= 300:
            return httpx.Response(200, json=_pl("era5_recent400_saint_gatien.json"))
        if span <= 30:
            return httpx.Response(200, json=_pl("era5_topup20_saint_gatien.json"))
        return httpx.Response(200, json=_pl("era5_recent_saint_gatien.json"))  # 120 d
    respx.get(url__startswith=pc.ARCHIVE_URL).mock(side_effect=reply)
    ids = [p["id"] for p in pconfig.list_places()]
    assert ids == ["maenam", "saint_gatien", "gorokhovets"]
    # the normals come first since the QA of 24 Sep 2026 (see the test below): seed them so
    # this test keeps exercising the bulk / top-up logic of the recent series
    for pid in ids:
        db.set_status(pc.status_key(pid, "normals"), _pl("normals_doc_saint_gatien.json"))
    async with httpx.AsyncClient() as client:
        r1 = await run_collector(pc.PlacesClimate(), client)
        assert r1["ok"], r1
        docs = {i: db.get_status(pc.status_key(i, "recent"))["value"] for i in ids}
        assert docs["maenam"]["window_days"] == 400 and len(docs["maenam"]["days"]) >= 390
        assert docs["saint_gatien"]["window_days"] == 120     # waits for its bulk turn
        assert docs["gorokhovets"]["window_days"] == 120
        assert r1["items"] == 3
        run = db.query("SELECT detail FROM source_runs WHERE source='places_climate' "
                       "ORDER BY id DESC LIMIT 1")[0]["detail"]
        assert run["recent_bulk"] == ["maenam"] and "saint_gatien" in run["pending"]
        # next run: Maenam gets a light top-up (last 14 days only), Saint-Gatien its bulk
        calls.clear()
        r2 = await run_collector(pc.PlacesClimate(), client)
        assert r2["ok"], r2
        docs = {i: db.get_status(pc.status_key(i, "recent"))["value"] for i in ids}
        assert docs["saint_gatien"]["window_days"] == 400
        assert docs["maenam"]["window_days"] == 400 and docs["maenam"]["topped_up_at"]
        top = calls[0]
        assert (date.fromisoformat(top[1]) - date.fromisoformat(top[0])).days <= 30
        assert top[0] == (date.fromisoformat(docs["maenam"]["last_day"])
                          - timedelta(days=pc.RECENT_TOPUP_DAYS)).isoformat()
        # the top-up did not shrink the series
        assert len(docs["maenam"]["days"]) >= 390
    # and the temperate water rule can now rate the 365-day window
    db.set_status(pc.status_key("saint_gatien", "normals"), _pl("normals_doc_saint_gatien.json"))
    f = pengine.f_water(next(p for p in pconfig.DEFAULT_PLACES if p["id"] == "saint_gatien"),
                        datetime(2026, 9, 24, 15, 0, tzinfo=UTC))
    w = {x["days"]: x for x in f["details"]["windows"]}
    assert w[365]["available"] and w[180]["available"] and w[365]["pct"] == 87
    assert f["details"]["window_days"] in (90, 180, 365) and f["level"] == 1


def test_places_climate_bulk_weight_is_small_but_budgeted():
    # 3 variables x 401 days: ~29 'calls', a fraction of a normals request (~780)
    assert pc.om_weight(3, pc.RECENT_DAYS + 1) < 30
    assert pc.om_weight(len(pc.NORMALS_DAILY), 10957) > 700


# ------------------------------------------------------------------ 8. archive end date


def test_archive_end_date_never_asks_for_a_utc_tomorrow(monkeypatch):
    """Open-Meteo's archive refuses end_date > today in UTC (verified 2026-09-24 17:21 UTC:
    "end_date is out of allowed range from 1940-01-01 to 2026-09-24"). At 00:21 ICT the
    local day is already 25 Sep: the old requests failed every night from 00:00 to 07:00."""
    class FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            t = datetime(2026, 9, 24, 17, 21, tzinfo=UTC)
            return t.astimezone(tz) if tz else t.replace(tzinfo=None)
    monkeypatch.setattr(lc, "datetime", FakeDT)
    assert lc.today_bkk() == date(2026, 9, 25)
    assert lc.archive_end_date() == date(2026, 9, 24)
    assert lc.archive_end_date(date(2026, 9, 20)) == date(2026, 9, 20)


@respx.mock
async def test_era5_collector_requests_end_on_the_utc_day(monkeypatch):
    monkeypatch.setattr(lc, "archive_end_date", lambda *a, **k: date(2026, 9, 24))
    db.set_status("samui_climatology", {"days": {"01-01": [1, 30, 24, 33]}})  # skip the 30-year fetch
    seen = {}

    def reply(request):
        seen["end"] = request.url.params["end_date"]
        return httpx.Response(200, content=(FIX / "local" / "archive_recent.json").read_bytes())
    respx.get(url__startswith=lc.ARCHIVE_URL).mock(side_effect=reply)
    async with httpx.AsyncClient() as client:
        res = await run_collector(lc.OpenMeteoSamuiEra5(), client)
    # the captured fixture predates the apparent-temperature-min column, so the parser may
    # reject it: what this test pins is the DATE the collector asked for
    assert seen["end"] == "2026-09-24" and res.get("http_status") in (200, None)


@respx.mock
async def test_places_normals_take_the_first_heavy_slots(monkeypatch):
    """QA 24 Sep 2026: on the VPS the three 400-day bulk requests used the first three heavy
    slots (one per run, 2 h apart) and, the normals still missing, every place stayed
    "level unknown -- no current data for water" for half a day. Now the normals (the only
    heavy document the water factor cannot do without) are computed first, one place per
    run, hourly; the bulks follow."""
    monkeypatch.setattr(pc, "HEAVY_MIN_UPTIME_S", 0)
    monkeypatch.setattr(pc, "HEAVY_GAP_S", 0)
    monkeypatch.setattr(pc, "_last_heavy", [])
    real_build = pc.build_normals
    monkeypatch.setattr(pc, "build_normals", lambda payload: real_build(payload, min_years=2))
    calls: list[tuple[str, str]] = []

    def reply(request):
        s, e = request.url.params["start_date"], request.url.params["end_date"]
        calls.append((s, e))
        if s.startswith("1991"):
            return httpx.Response(200, json=_pl("era5_normals_gorokhovets_1991_1992.json"))
        return httpx.Response(200, json=_pl("era5_recent_saint_gatien.json"))  # 120 d
    respx.get(url__startswith=pc.ARCHIVE_URL).mock(side_effect=reply)
    assert pc.PlacesClimate.interval_s == 3600
    async with httpx.AsyncClient() as client:
        r1 = await run_collector(pc.PlacesClimate(), client)
        assert r1["ok"], r1
        run = db.query("SELECT detail FROM source_runs WHERE source='places_climate' "
                       "ORDER BY id DESC LIMIT 1")[0]["detail"]
        assert run["normals_computed"] == ["maenam"] and "recent_bulk" not in run
        assert db.get_status(pc.status_key("maenam", "normals"))
        assert calls[0] == ("1991-01-01", "2020-12-31")          # the normals went first
        assert all(not s.startswith("1991") for s, _ in calls[1:])
        # every place still got its light 120-day series in the same run
        for pid in ("maenam", "saint_gatien", "gorokhovets"):
            assert db.get_status(pc.status_key(pid, "recent"))["value"]["window_days"] == 120
        r2 = await run_collector(pc.PlacesClimate(), client)
        run2 = db.query("SELECT detail FROM source_runs WHERE source='places_climate' "
                        "ORDER BY id DESC LIMIT 1")[0]["detail"]
        assert r2["ok"] and run2["normals_computed"] == ["saint_gatien"]
