"""Server-side filters + facets on /api/feed, /api/events, /api/series, /api/sources,
/api/alerts (all optional; no parameter = the previous behaviour)."""

from __future__ import annotations

import os

os.environ.setdefault("SCHEDULER", "false")

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app

c = TestClient(app)


@pytest.fixture(autouse=True)
def seed():
    db.reset_for_tests()
    db.upsert_feed_items("google_news", [
        {"ext_id": "1", "kind": "news", "title": "El Nino drought Thailand", "lang": "en",
         "published_at": "2026-09-20T00:00:00+00:00", "tags": ["enso", "thailand"],
         "lat": 15.0, "lon": 100.0},
        {"ext_id": "2", "kind": "news", "title": "El Niño Pérou", "lang": "fr",
         "published_at": "2026-09-22T00:00:00+00:00", "tags": ["enso", "peru"]},
    ])
    db.upsert_feed_items("x_posts", [
        {"ext_id": "3", "kind": "social", "title": "Samui flood", "lang": "en",
         "published_at": "2026-09-23T00:00:00+00:00", "tags": ["flood", "samui", "thailand"],
         "lat": 9.5, "lon": 100.0},
    ])
    db.upsert_events("gdacs", [
        {"ext_id": "a", "category": "cyclone", "severity": "orange", "lat": 18.0, "lon": 84.0,
         "updated_at": "2026-09-24T00:00:00+00:00"},
        {"ext_id": "b", "category": "flood", "severity": "green", "lat": 5.0, "lon": 102.0,
         "updated_at": "2026-09-20T00:00:00+00:00"},
        {"ext_id": "c", "category": "volcano", "severity": "red", "lat": -15.0, "lon": -175.0,
         "updated_at": "2026-09-23T00:00:00+00:00"},
    ])
    db.upsert_events("eonet", [
        {"ext_id": "d", "category": "wildfire", "severity": "info", "lat": 0.0, "lon": 178.0}])


def ids(rows, key="ext_id"):
    return sorted(r[key] for r in rows)


def test_feed_filters():
    assert ids(c.get("/api/feed").json()) == ["1", "2", "3"]
    assert ids(c.get("/api/feed?kind=news,social&lang=en").json()) == ["1", "3"]
    assert ids(c.get("/api/feed?source=x_posts").json()) == ["3"]
    assert ids(c.get("/api/feed?tag=peru,samui").json()) == ["2", "3"]
    assert ids(c.get("/api/feed?since=2026-09-21&until=2026-09-22T12:00").json()) == ["2"]
    assert ids(c.get("/api/feed?has_geo=true").json()) == ["1", "3"]
    assert ids(c.get("/api/feed?has_geo=false").json()) == ["2"]
    assert ids(c.get("/api/feed?q=Samui").json()) == ["3"]
    page = c.get("/api/feed?limit=1&offset=1").json()
    assert [r["ext_id"] for r in page] == ["2"]  # newest first: 3, 2, 1


def test_feed_facets_ignore_their_own_dimension():
    f = c.get("/api/feed/facets?kind=news").json()
    assert f["total"] == 2
    assert {x["value"]: x["count"] for x in f["kind"]} == {"news": 2, "social": 1}
    assert {x["value"]: x["count"] for x in f["tag"]} == {"enso": 2, "thailand": 1, "peru": 1}
    assert {x["value"]: x["count"] for x in f["source"]} == {"google_news": 2}


def test_events_filters_bbox_near():
    assert ids(c.get("/api/events?category=cyclone,flood").json()) == ["a", "b"]
    assert ids(c.get("/api/events?severity=red&source=gdacs").json()) == ["c"]
    assert ids(c.get("/api/events?since=2026-09-22").json()) == ["a", "c"]
    assert ids(c.get("/api/events?bbox=80,0,110,20").json()) == ["a", "b"]
    # across the antimeridian: 170E .. 170W
    assert ids(c.get("/api/events?bbox=170,-20,-170,5").json()) == ["c", "d"]
    near = c.get("/api/events?near=9.512,100.013&radius_km=800").json()
    assert ids(near) == ["b"] and 500 < near[0]["distance_km"] < 700
    assert len(c.get("/api/events?limit=2").json()) == 2
    assert c.get("/api/events?bbox=1,2,3").status_code == 422


def test_events_paged_keeps_the_plain_list_contract():
    # no `paged`: the original contract, a plain list of every matching row
    plain = c.get("/api/events").json()
    assert isinstance(plain, list) and len(plain) == 4
    p = c.get("/api/events?paged=1").json()
    assert p["total"] == 4 and p["limit"] == 500 and p["offset"] == 0
    assert [e["ext_id"] for e in p["items"]] == [e["ext_id"] for e in plain]  # newest first
    p2 = c.get("/api/events?paged=1&limit=2&offset=1").json()
    assert p2["total"] == 4 and [e["ext_id"] for e in p2["items"]] == ["c", "b"]
    assert all("kind" in e for e in p2["items"])
    # filters + paging compose (total counts the filtered set)
    p3 = c.get("/api/events?paged=1&source=gdacs&limit=1").json()
    assert p3["total"] == 3 and len(p3["items"]) == 1
    # offset past the end: an empty page, never an error
    assert c.get("/api/events?paged=1&offset=99").json()["items"] == []


def test_status_listing_omits_heavy_documents_unless_full():
    from app import main as M

    db.set_status("small", {"a": 1})
    db.set_status("heavy", {"blob": "x" * (M.STATUS_LIST_MAX_BYTES + 100)})
    s = c.get("/api/status").json()
    assert s["small"]["value"] == {"a": 1} and "omitted" not in s["small"]
    assert s["heavy"]["value"] is None and s["heavy"]["omitted"] is True
    assert s["heavy"]["url"] == "/api/status/heavy" and s["heavy"]["bytes"] > M.STATUS_LIST_MAX_BYTES
    assert s["heavy"]["updated_at"]
    full = c.get("/api/status?full=1").json()
    assert full["heavy"]["value"]["blob"].startswith("xxx") and "omitted" not in full["heavy"]
    assert c.get("/api/status/heavy").json()["value"]["blob"].startswith("xxx")


def test_events_facets():
    f = c.get("/api/events/facets?source=gdacs").json()
    assert f["total"] == 3
    assert {x["value"]: x["count"] for x in f["source"]} == {"gdacs": 3, "eonet": 1}
    assert {x["value"] for x in f["severity"]} == {"orange", "green", "red"}


def test_series_until_and_downsample():
    db.upsert_observations("tao_buoys", [
        {"series": "tao_1_sst", "ts": f"2026-09-2{d}T{h:02d}:00:00+00:00", "value": float(h)}
        for d in (1, 2) for h in range(24)])
    base = "/api/series?source=tao_buoys&series=tao_1_sst"
    assert len(c.get(base).json()["points"]) == 48
    daily = c.get(base + "&downsample=daily").json()["points"]
    assert [(p["ts"], p["value"], p["meta"]["n"]) for p in daily] == [
        ("2026-09-21", 11.5, 24), ("2026-09-22", 11.5, 24)]
    nth = c.get(base + "&downsample=10").json()["points"]
    assert len(nth) == 5 and nth[-1]["ts"] == "2026-09-22T23:00:00+00:00"  # newest kept
    assert len(c.get(base + "&until=2026-09-21T23:59").json()["points"]) == 24
    assert c.get(base + "&downsample=x").status_code == 422


def test_catalog_filters():
    db.upsert_observations("cpc_oni", [{"series": "oni", "ts": "2026-07-15", "value": 1.8}])
    db.upsert_observations("tao_buoys", [{"series": "tao_1_sst", "ts": "2026-09-21",
                                          "value": 29.0}])
    assert ids(c.get("/api/series/catalog?category=ocean_index").json(), "series") == ["oni"]
    assert ids(c.get("/api/series/catalog?q=tao").json(), "series") == ["tao_1_sst"]
    assert ids(c.get("/api/series/catalog?source=cpc_oni,tao_buoys").json(), "series") == [
        "oni", "tao_1_sst"]


def test_sources_and_alerts_filters():
    rows = c.get("/api/sources?category=ocean_index&state=pending").json()
    assert rows and all(r["category"] == "ocean_index" for r in rows)
    assert c.get("/api/sources?state=stale").json() == []
    db.add_alert("act", "local_level", "t1", "b", "k1")
    db.add_alert("vigilance", "hazard", "t2", "b", "k2")
    assert [a["title"] for a in c.get("/api/alerts?level=act").json()] == ["t1"]
    assert [a["title"] for a in c.get("/api/alerts?kind=hazard,x").json()] == ["t2"]
    assert len(c.get("/api/alerts?since=2000-01-01").json()) == 2
    assert c.get("/api/alerts?since=2999-01-01").json() == []


def test_series_batch_answers_many_series_in_one_request():
    """QA 24 Sep 2026: the Indices page fired ~80 GET /api/series at once and the public nginx
    rate limit (10 r/s, burst 40) answered 429 to half of them. `keys=source:series,...`
    returns every series in one response; unknown keys come back empty and listed."""
    db.upsert_observations("cpc_oni", [{"series": "oni", "ts": "2026-07-15", "value": 1.8},
                                       {"series": "oni", "ts": "2026-06-15", "value": 1.39}])
    db.upsert_observations("cpc_roni", [{"series": "roni", "ts": "2026-07-15", "value": 1.36}])
    r = c.get("/api/series/batch?keys=cpc_oni:oni,cpc_roni:roni,nope:missing,cpc_oni:oni")
    assert r.status_code == 200
    body = r.json()
    assert [(it["source"], it["series"], len(it["points"])) for it in body["items"]] == [
        ("cpc_oni", "oni", 2), ("cpc_roni", "roni", 1), ("nope", "missing", 0)]
    assert body["missing"] == ["nope:missing"]
    # the shared parameters apply to every key, exactly like GET /api/series
    since = c.get("/api/series/batch?keys=cpc_oni:oni&since=2026-07-01").json()
    assert [p["ts"] for p in since["items"][0]["points"]] == ["2026-07-15"]
    assert since["items"][0] == c.get("/api/series?source=cpc_oni&series=oni&since=2026-07-01").json()
    assert c.get("/api/series/batch?keys=oni").status_code == 422
    assert c.get("/api/series/batch?keys=").status_code == 422
    too_many = ",".join(f"s{i}:x" for i in range(61))
    assert c.get(f"/api/series/batch?keys={too_many}").status_code == 422
