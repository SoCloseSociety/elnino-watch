"""News collectors against REAL payloads captured 2026-09-24 (no network)."""

import json
import re
from pathlib import Path

import httpx
import pytest
import respx

from app import db
from app.collectors import news as N
from app.collectors.base import run_collector

FIX = Path(__file__).parent / "fixtures" / "news"


def fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


@pytest.fixture(autouse=True)
def mem_db(monkeypatch):
    db.reset_for_tests()
    monkeypatch.setattr(N.GdeltNews, "gap_s", 0.0)
    monkeypatch.setattr(N.GdeltNews, "backoff_s", 0.0)
    monkeypatch.setattr(N.GoogleNews, "gap_s", 0.0)


async def run(col) -> dict:
    async with httpx.AsyncClient() as c:
        return await run_collector(col, c)


def feed(source: str) -> list[dict]:
    return db.query("SELECT * FROM feed_items WHERE source=? ORDER BY published_at DESC",
                    (source,))


def last_run(source: str) -> dict:
    return db.query("SELECT * FROM source_runs WHERE source=? ORDER BY id DESC LIMIT 1",
                    (source,))[0]


# ---------------------------------------------------------------- helpers

def test_topic_tags_and_geo():
    t = N.topic_tags("Koh Samui faces water shortage as El Nino drought bites")
    assert {"enso", "drought", "samui", "thailand"} <= set(t)
    assert N.place_geo("flooded Pattaya streets") == (12.93, 100.88)
    assert N.place_geo("เกาะสมุย ขาดแคลนน้ำ") == (9.512, 100.013)
    assert N.topic_tags("เอลนีโญ ภัยแล้ง")[:2] == ["enso", "drought"]


def test_relevance_scopes():
    assert N.is_relevant("anything", "all")
    assert not N.is_relevant("Puripol wins the 100m", "impact")
    assert N.is_relevant("Visitor goes missing in flooded Pattaya", "impact")
    assert not N.is_relevant("Flood in Nepal", "enso")
    # "El Nino" as a nickname needs a climate word in open searches
    assert not N.is_relevant("o el nino decidiu virar el macho", "enso_ctx")
    assert N.is_relevant("Nairobi prepares for El Niño rains", "enso_ctx")


# ---------------------------------------------------------------- Google News

def test_parse_gnews_publisher_and_title():
    items = N.parse_gnews(fx("gnews_en.xml"), "en", "El Niño")
    assert len(items) == 12
    first = items[0]
    assert first["author"] == "reuters.com"            # from <source>
    assert not first["title"].endswith("reuters.com")  # " - Publisher" stripped
    assert first["published_at"] == "2026-09-24T09:34:18+00:00"
    assert first["kind"] == "news" and first["lang"] == "en"
    # ext_id is stable (hash of the RSS guid)
    again = N.parse_gnews(fx("gnews_en.xml"), "en", "El Niño")
    assert [i["ext_id"] for i in items] == [i["ext_id"] for i in again]


def test_parse_gnews_thai():
    items = N.parse_gnews(fx("gnews_th.xml"), "th", "เอลนีโญ")
    assert len(items) == 8
    assert all(i["lang"] == "th" for i in items)
    assert "enso" in items[0]["tags"] and "thailand" in items[0]["tags"]


@respx.mock
async def test_google_news_collect():
    respx.get(url__startswith=N.GNEWS).mock(return_value=httpx.Response(200,
                                                                      content=fx("gnews_en.xml")))
    res = await run(N.GoogleNews())
    assert res["ok"], res
    rows = feed("google_news")
    assert len(rows) == 12  # same fixture for every query: deduplicated by ext_id
    samui_rows = [r for r in rows if "samui" in r["tags"]]
    assert samui_rows  # items that came from a Koh Samui query carry the samui tag
    detail = last_run("google_news")["detail"]
    assert detail["queries"]["Koh Samui flood [en-US]"] == 12


# ---------------------------------------------------------------- direct RSS

def test_parse_feed_filters_general_feeds():
    n, items = N.parse_feed(fx("rss_bangkokpost_thailand.xml"), "Bangkok Post", "en", "impact")
    assert n == 10
    assert [i["title"] for i in items] == ["Visitor goes missing in flooded Pattaya"]
    assert items[0]["lat"] == 12.93 and "flood" in items[0]["tags"]

    n, items = N.parse_feed(fx("rss_carbonbrief.xml"), "Carbon Brief", "en", "enso")
    assert n == 4
    assert len(items) == 1 and "El Niño" in items[0]["title"]

    n, items = N.parse_feed(fx("rss_thaiger_samui.xml"), "Thaiger", "en", "impact")
    assert n == 6 and items == []  # crime stories on the Samui tag are not ENSO impacts


@respx.mock
async def test_thai_rss_collect_records_per_feed_state():
    for name, url, *_ in N.THAI_FEEDS:
        if "bangkokpost.com/rss/data/thailand" in url:
            respx.get(url).mock(return_value=httpx.Response(200,
                                                            content=fx("rss_bangkokpost_thailand.xml")))
        else:
            respx.get(url).mock(return_value=httpx.Response(404))
    res = await run(N.ThaiRegionalRss())
    assert res["ok"] and res["items"] == 1
    detail = last_run("news_thailand_rss")["detail"]
    assert detail["feeds"]["Bangkok Post -- Thailand"] == "1/10"
    assert detail["feeds"]["Thairath"] == "http 404"


@respx.mock
async def test_rss_all_feeds_down_is_an_error():
    for _name, url, *_ in N.AGENCY_FEEDS:
        respx.get(url).mock(return_value=httpx.Response(503))
    res = await run(N.AgencyScienceRss())
    assert not res["ok"]
    assert last_run("news_science_rss")["error"].startswith("RuntimeError: all")


# ---------------------------------------------------------------- GDELT

def test_parse_gdelt():
    items = N.parse_gdelt(json.loads(fx("gdelt_enso.json")), "enso_all")
    assert len(items) == 15
    first = items[0]
    assert first["published_at"] == "2026-09-24T12:15:00+00:00"
    assert first["lang"] == "es" and first["author"] == "eltiempo.com"
    # no place in the title -> publisher-country centroid, marked approximate
    assert (first["lat"], first["lon"]) == N.COUNTRY_CENTROIDS["colombia"]
    assert "geo_publisher_country" in first["tags"]
    assert all("enso" in i["tags"] for i in items)
    ecuador = next(i for i in items if "Ecuador" in i["title"])
    assert (ecuador["lat"], ecuador["lon"]) == (-1.83, -78.18)
    assert "geo_publisher_country" not in ecuador["tags"]
    polo = next(i for i in items if i["title"].startswith("Polo"))
    assert polo["title"].startswith("Polo, el 2.")  # GDELT " , " tokenization undone


def test_gdelt_plan_rotates():
    col = N.GdeltNews()
    a, b = col.plan(0), col.plan(col.interval_s)
    assert a[0][0] == b[0][0] == "enso_all"
    assert len(a) == 1 + col.per_run
    assert a[1:] != b[1:]
    seen = set()
    for k in range(len(N.GDELT_QUERIES)):
        seen |= {p[0] for p in col.plan(k * col.interval_s)[1:]}
    assert seen == {q[0] for q in N.GDELT_QUERIES[1:]}


@respx.mock
async def test_gdelt_backs_off_once_on_429_then_collects():
    extra = N.GdeltNews.per_run
    route = respx.get(N.GDELT_DOC).mock(side_effect=[
        httpx.Response(429, content=fx("gdelt_429.txt")),
        httpx.Response(200, content=fx("gdelt_enso.json")),
        *[httpx.Response(200, content=b"{}") for _ in range(extra)],
    ])
    res = await run(N.GdeltNews())
    assert res["ok"] and res["items"] == 15
    assert route.call_count == 2 + extra
    q = last_run("gdelt_news")["detail"]["queries"]
    assert q["enso_all"] == 15 and list(q.values())[1:] == [0] * extra


@respx.mock
async def test_gdelt_rate_limited_is_reported_not_silent():
    respx.get(N.GDELT_DOC).mock(return_value=httpx.Response(429, content=fx("gdelt_429.txt")))
    res = await run(N.GdeltNews())
    assert not res["ok"]
    err = last_run("gdelt_news")["error"]
    assert "429" in err and re.search(r"no query succeeded", err)
