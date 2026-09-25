"""El Nino analogs (app/local/analogs.py, app/analogs_api.py) on REAL captured payloads:
- tests/fixtures/local/era5_history_1996_1998.json: Open-Meteo ERA5 daily for the Maenam
  cell, 1996-07-01 .. 1998-06-30 (captured 2026-09-24);
- tests/fixtures/indices/oni_full.ascii.txt / RONI_full.ascii.txt: the full NOAA CPC files
  (captured 2026-09-24). No network."""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

os.environ.setdefault("SCHEDULER", "false")

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import analogs_api, db
from app.collectors.base import run_collector
from app.collectors.indices import parse_oni, parse_roni
from app.local import analogs as A
from app.local import analogs_impacts as AI
from app.local import provenance as P

FIX = Path(__file__).parent / "fixtures"


def payload() -> dict:
    return json.loads((FIX / "local" / "era5_history_1996_1998.json").read_text())


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


def seed_oni():
    db.upsert_observations("cpc_oni", parse_oni((FIX / "indices" / "oni_full.ascii.txt").read_text()))
    db.upsert_observations("cpc_roni", parse_roni((FIX / "indices" / "RONI_full.ascii.txt")
                                                  .read_text()))


# ------------------------------------------------------------------ monthly table


def test_month_table_matches_the_daily_data():
    p = payload()
    d = p["daily"]
    mt = A.month_table(p)
    assert len(mt) == 24 and min(mt) == "1996-07" and max(mt) == "1998-06"
    # Feb-Apr 1998, recomputed straight from the daily arrays
    idx = [i for i, t in enumerate(d["time"]) if "1998-02" <= t[:7] <= "1998-04"]
    rain = round(sum(d["precipitation_sum"][i] for i in idx), 1)
    got = round(sum(A.m(mt[k], "rain_mm") for k in ("1998-02", "1998-03", "1998-04")), 1)
    assert got == pytest.approx(rain, abs=0.2)
    assert max(d["apparent_temperature_max"][i] for i in idx) == max(
        A.m(mt[k], "app_max") for k in ("1998-02", "1998-03", "1998-04"))
    mar = mt["1998-03"]
    assert A.m(mar, "n_days") == 31 and A.m(mar, "last_day") == 31
    assert A.m(mar, "dry_days") == sum(1 for i in idx if d["time"][i][:7] == "1998-03"
                                       and d["precipitation_sum"][i] < A.DRY_DAY_MM)
    assert A.m(mar, "run_max") <= 31 and A.m(mar, "run_start") + A.m(mar, "run_end") <= 62
    day = A.m(mar, "app_max_day")
    i_day = d["time"].index(f"1998-03-{day:02d}")
    assert d["apparent_temperature_max"][i_day] == A.m(mar, "app_max")


def test_month_table_skips_null_days_and_rejects_bad_payloads():
    p = payload()
    p["daily"]["precipitation_sum"][-3:] = [None, None, None]  # ERA5 lag on the last days
    mt = A.month_table(p)
    assert A.m(mt["1998-06"], "n_days") == 27 and A.m(mt["1998-06"], "last_day") == 27
    with pytest.raises(A.SourceChanged):
        A.month_table({"daily": {"time": []}})
    with pytest.raises(A.SourceChanged):
        A.month_table({"daily": {"time": ["1998-01-01"], "precipitation_sum": [1.0]}})


def test_longest_dry_spell_crosses_month_ends():
    mt = A.month_table(payload())
    # brute force on the daily series for Jan-May 1998
    d = payload()["daily"]
    best = cur = 0
    for i, t in enumerate(d["time"]):
        if "1998-01" <= t[:7] <= "1998-05":
            cur = cur + 1 if d["precipitation_sum"][i] < A.DRY_DAY_MM else 0
            best = max(best, cur)
    assert A.longest_dry_spell(mt, A._months(1998, 1, 5)) == best == 50
    # a synthetic fully-dry month chains through
    row = list(mt["1998-03"])
    fields = A.M_FIELDS
    row[fields.index("dry_days")] = 31
    row[fields.index("run_start")] = row[fields.index("run_end")] = row[fields.index("run_max")] = 31
    mt2 = dict(mt) | {"1998-03": row}
    assert A.longest_dry_spell(mt2, A._months(1998, 1, 5)) >= 31 + A.m(mt["1998-04"], "run_start")
    assert A.longest_dry_spell(mt, ["1995-01"]) is None  # month not stored


def test_year_stats_1997_98_from_real_era5():
    mt = A.month_table(payload())
    st = A.year_stats(mt, 1997, None)
    assert st["complete"] and st["water_year"] == "1997-07/1998-06"
    assert st["ne_monsoon"]["months"] == ["1997-10", "1997-11", "1997-12"]
    assert st["dry_season"]["rain_mm"] == pytest.approx(143.6, abs=0.2)
    assert st["feb_apr"]["rain_mm"] == pytest.approx(16.6, abs=0.2)
    assert st["heat"]["max_feels_like"] == 39.5 and st["heat"]["max_feels_like_day"] == "1998-05-01"
    assert st["heat"]["heat_days"] == 7 and st["longest_dry_spell_days"] == 50
    assert st["feb_apr"]["pct"] is None  # no normals given
    assert len(st["monthly"]) == 12 and st["monthly"][0]["month"] == "1997-07"
    # normals from the (2-year) table itself: percentages become available
    norm = A.normals(mt, years=(1996, 1998))
    assert not norm  # a month needs >= 20 years
    assert A.year_stats(mt, 1996, None)["complete"] is True   # Jul 1996 .. Jun 1997 is there
    assert A.year_stats(mt, 1995, None)["complete"] is False  # Jul 1995 .. Jun 1996 is not


def test_normals_and_percentages():
    mt = A.month_table(payload())
    # replicate the two captured years across 1991-2020 to exercise the normal machinery
    big = {}
    for y in range(1991, 2021):
        src = 1996 if y % 2 == 0 else 1997
        for mo in range(1, 13):
            k = f"{src}-{mo:02d}" if f"{src}-{mo:02d}" in mt else f"{src + 1}-{mo:02d}"
            big[f"{y}-{mo:02d}"] = mt[k]
    norm = A.normals(big)
    assert set(norm) == {f"{m:02d}" for m in range(1, 13)} and norm["11"]["years"] == 30
    st = A.year_stats(big | mt, 1997, norm)
    assert st["feb_apr"]["normal_mm"] > 0 and st["feb_apr"]["pct"] is not None
    assert st["heat"]["normal_heat_days"] is not None and "hot_days" not in st["heat"]
    # the season under way: only the leading complete months count
    part = dict(mt)
    part["1998-05"] = list(mt["1998-05"])
    part["1998-05"][A.M_FIELDS.index("n_days")] = 12
    sw = A.season_rain(part, A._months(1998, 3, 6), None, partial=True)
    assert sw["months"] == ["1998-03", "1998-04"]
    assert A.season_rain(part, A._months(1998, 5, 6), None, partial=True) is None


# ------------------------------------------------------------------ ENSO side


def test_peak_indices_and_neutral_years_come_from_the_cpc_files():
    seed_oni()
    assert A.peak_index("oni", 1997) == {
        "value": 2.37, "season": "NDJ 1997", "ts": "1997-12-15", "kind": "observed",
        "valid_for": "1997-11-01/1998-01-31", "source": "NOAA CPC", "unit": "degC",
        "unit_label": "°C"}
    assert A.peak_index("roni", 1982)["value"] == 2.4
    assert A.peak_index("oni", 1987)["value"] == 1.49          # under the "strong" band
    assert A.peak_index("oni", 2015)["value"] == 2.59
    assert A.index_at("oni", 2026) == 1.8 and A.index_at("oni", 1997) == 1.48
    assert A.peak_index("oni", 1940) is None
    neutral = A.neutral_years(y_to=2025)
    assert 1997 not in neutral and 2015 not in neutral and 2010 not in neutral  # La Nina
    assert len(neutral) >= 8 and all(1950 <= y <= 2025 for y in neutral)
    for y in neutral:
        vals = [r["value"] for r in A._series("oni", f"{y}-10-15", f"{y + 1}-03-15")]
        assert max(abs(v) for v in vals) < 0.5


# ------------------------------------------------------------------ build + API


def _seed_history():
    mt = A.month_table(payload())
    db.set_status(A.STATUS_KEY, {"version": A.STATS_VERSION, "months": mt, "windows": {},
                                  "first_month": "1996-07", "last_month": "1998-06",
                                  "last_day": "1998-06-30", "point": {"lat": 9.5, "lon": 100.0},
                                  "normals": {}})


def test_build_has_every_documented_field():
    seed_oni()
    _seed_history()
    doc = A.build(datetime(2026, 9, 24, 12, 0, tzinfo=UTC))
    ids = [e["id"] for e in doc["events"]]
    assert ids == ["1982-83", "1987-88", "1991-92", "1997-98", "2009-10", "2015-16", "2023-24"]
    e97 = doc["events"][3]
    assert e97["peak_oni"]["value"] == 2.37 and e97["strength"] == "very strong El Nino"
    assert e97["samui"]["complete"] and e97["samui"]["kind"] == "reanalysis"
    assert e97["samui"]["longest_dry_spell_days"] == 50 and e97["samui"]["max_feels_like"] == 39.5
    assert e97["samui"]["feb_apr_rain_mm"] == pytest.approx(16.6, abs=0.2)
    assert all(i["kind"] == "documented" and i["url"].startswith("https://")
               for i in e97["impacts"]) and len(e97["impacts"]) >= 2
    e87 = doc["events"][1]
    assert e87["note"] and "+1.49" in e87["note"] and e87["strength"] == "moderate El Nino"
    assert doc["events"][0]["samui"]["complete"] is False  # 1982: not in the fixture
    cur = doc["current_event"]
    assert cur["oni"]["value"] == 1.8 and cur["id"] == "2026-27" and cur["strength"]
    assert cur["impacts"] and cur["impacts"][0]["date"] == "2026-07-29"
    # the fixture holds one complete neutral water year (1996-97: ONI within +-0.5 SON-FMA)
    assert doc["neutral_baseline"]["years"] == [1996] and doc["neutral_baseline"]["n"] == 1
    assert doc["neutral_baseline"]["metrics"]["longest_dry_spell_days"]["median"] is not None
    assert "ONI +1.80 °C in 2026 is above" in " ".join(doc["takeaways"])
    assert any("1997-98" in t and "50 days" in t for t in doc["takeaways"])
    assert doc["kinds"]["documented"] and doc["method"] and len(doc["sources"]) > 10
    assert doc["impacts_not_found"] == AI.NOT_FOUND
    # nothing in other_impacts belongs to a listed event, and nothing is invented
    listed = {e for e, _ in A.EVENTS}
    assert not any(set(i["events"]) & listed for i in doc["other_impacts"])
    assert all(i["checked_at"] == AI.CHECKED and i["quote"] for i in AI.IMPACTS)


def test_build_before_any_history_is_honest():
    seed_oni()
    doc = A.build()
    assert doc["history"]["months"] == 0
    assert doc["takeaways"] == [("No reconstructed event yet: the ERA5 history is still being "
                                 "fetched.")]
    assert all(e["samui"]["complete"] is False for e in doc["events"])
    assert doc["events"][3]["peak_oni"]["value"] == 2.37  # the index part still works


def test_api_routes():
    seed_oni()
    _seed_history()
    app = FastAPI()
    app.include_router(analogs_api.router)
    c = TestClient(app)
    r = c.get("/api/local/analogs")
    assert r.status_code == 200 and r.json()["events"][3]["id"] == "1997-98"
    h = c.get("/api/local/analogs/history").json()
    assert h["kind"] == "reanalysis" and "1998-03" in h["months"] and h["fields"] == list(A.M_FIELDS)
    assert P.STATUS_KINDS[A.STATUS_KEY] == "reanalysis"


# ------------------------------------------------------------------ collector


@respx.mock
async def test_collector_fetches_one_window_per_run_and_refreshes_the_year(monkeypatch):
    monkeypatch.setattr(A, "HISTORY_START", 1996)
    calls: list[tuple[str, str]] = []

    def reply(request):
        s, e = request.url.params["start_date"], request.url.params["end_date"]
        calls.append((s, e))
        p = payload()
        d = p["daily"]
        keep = [i for i, t in enumerate(d["time"]) if s <= t <= e]
        p["daily"] = {k: [v[i] for i in keep] for k, v in d.items()}
        return httpx.Response(200, json=p)
    respx.get(url__startswith=A.ARCHIVE_URL).mock(side_effect=reply)
    today = date(1998, 6, 15)
    monkeypatch.setattr(A, "archive_end_date", lambda *a, **k: today)
    col = A.SamuiEra5History()
    col.min_uptime_s = 0
    async with httpx.AsyncClient() as client:
        r1 = await run_collector(col, client)
        assert r1["ok"], r1
        assert calls == [("1998-01-01", "1998-06-15"), ("1996-01-01", "1997-12-31")]
        doc = db.get_status(A.STATUS_KEY)["value"]
        assert doc["windows"]["1998"]["fetched_at"] and doc["windows"]["1996-1997"]["fetched_at"]
        assert doc["first_month"] == "1996-07" and doc["last_month"] == "1998-06"
        assert doc["last_day"] == "1998-06-15" and doc["point"]["lat"] == 9.5
        rows = db.query("SELECT series, COUNT(*) n FROM observations WHERE source=? GROUP BY series",
                        (col.name,))
        assert {r["series"]: r["n"] for r in rows} == {
            "samui_era5_month_precip": 24, "samui_era5_month_temp_max": 24,
            "samui_era5_month_apparent_max": 24}
        pt = db.query("SELECT ts, value FROM observations WHERE series='samui_era5_month_precip' "
                      "AND ts='1998-03-15'")[0]
        assert pt["value"] == A.m(doc["months"]["1998-03"], "rain_mm")
        assert P.annotate_point({"source": col.name, "series": "x", "ts": "1998-03-15",
                                 "unit": "mm"})["valid_for"] == "1998-03-01/1998-03-31"
        # second run within a day: nothing to fetch, the run stays "ok" with the month count
        calls.clear()
        r2 = await run_collector(col, client)
        assert r2["ok"] and r2["items"] == 24 and calls == []
    # the uptime gate: right after start-up only the light current-year request is made
    db.reset_for_tests()
    calls.clear()
    col2 = A.SamuiEra5History()
    col2.min_uptime_s = 10 ** 9
    async with httpx.AsyncClient() as client:
        r3 = await run_collector(col2, client)
    assert r3["ok"] and calls == [("1998-01-01", "1998-06-15")]
    run = db.query("SELECT detail FROM source_runs ORDER BY id DESC LIMIT 1")[0]["detail"]
    assert run["pending"] == ["1996-1997"] and run["fetched"] == ["1998"]


def test_decade_windows_end_on_the_archive_limit():
    w = A.decade_windows(1950, today=date(2026, 9, 24))
    assert w[0] == ("1950-1959", "1950-01-01", "1959-12-31")
    assert w[-2] == ("2020-2025", "2020-01-01", "2025-12-31")
    assert w[-1] == ("2026", "2026-01-01", "2026-09-24")
    assert A.om_weight(3, 3653) == pytest.approx(3653 / 14)


def test_decade_windows_are_fetched_newest_first():
    """QA 24 Sep 2026: with the 1950s first, the 1991-2020 normal (and so every percentage on
    the Past El Ninos page) waited for the 7th hourly run; newest first, it needs 4."""
    from datetime import date
    plan = A.decade_windows(A.HISTORY_START, today=date(2026, 9, 24))
    pending = [w for w in reversed(plan[:-1])]
    assert [w[0] for w in pending][:4] == ["2020-2025", "2010-2019", "2000-2009", "1990-1999"]
    assert pending[-1][0] == "1950-1959"
