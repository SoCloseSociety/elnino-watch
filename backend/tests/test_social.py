"""Social collectors against REAL payloads captured 2026-09-24 (no network)."""

import json
from pathlib import Path

import httpx
import pytest
import respx

from app import accounts as A
from app import db
from app.collectors import social as S
from app.collectors.base import SourceChanged, run_collector
from app.config import settings

FIX = Path(__file__).parent / "fixtures" / "social"


def fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


def fj(name: str):
    return json.loads(fx(name))


@pytest.fixture(autouse=True)
def mem_db(monkeypatch):
    db.reset_for_tests()
    # fixtures are from 2026-09-24: do not let the live-feed age cut drop them later
    monkeypatch.setattr(S, "MAX_AGE_DAYS", 100_000)
    monkeypatch.setattr(S.XPosts, "gap_s", 0.0)
    monkeypatch.setattr(S.BlueskyAccounts, "gap_s", 0.0)
    for k in ("x_bearer_token", "x_auth_token", "x_ct0", "bluesky_handle",
              "bluesky_app_password"):
        monkeypatch.setattr(settings, k, "")
    S._nitter_health.clear()


async def run(col) -> dict:
    async with httpx.AsyncClient() as c:
        return await run_collector(col, c)


def feed(source: str) -> list[dict]:
    return db.query("SELECT * FROM feed_items WHERE source=? ORDER BY published_at DESC",
                    (source,))


def last_run(source: str) -> dict:
    return db.query("SELECT * FROM source_runs WHERE source=? ORDER BY id DESC LIMIT 1",
                    (source,))[0]


# ---------------------------------------------------------------- accounts

def test_accounts_are_well_formed():
    seen = set()
    for a in A.ACCOUNTS:
        assert a["platform"] in {"x", "bluesky", "telegram"}
        assert a["kind"] in {"agency", "scientist", "media", "local"}
        assert a["verified_at"] and a["why"]
        assert "@" not in a["handle"]
        key = (a["platform"], a["handle"].lower())
        assert key not in seen
        seen.add(key)
    # rejected during verification: must not come back silently
    handles = {a["handle"] for a in A.ACCOUNTS}
    assert not handles & {"NationThailand", "DrLHeureux", "IRI_Columbia", "noaa.gov"}


# ---------------------------------------------------------------- Bluesky

def test_parse_bsky_author_feed():
    payload = fj("bsky_feed_zeke.json")
    all_posts = S.parse_bsky_feed(payload, "all")
    reposts = sum(1 for f in payload["feed"] if f.get("reason"))
    assert len(all_posts) == len(payload["feed"]) - reposts
    p = all_posts[0]
    assert p["ext_id"].startswith("at://did:plc:")
    assert p["url"].startswith("https://bsky.app/profile/zekehausfather.com/post/")
    assert p["author"] == "Zeke Hausfather (@zekehausfather.com)"
    assert p["published_at"] == "2026-09-24T05:10:07+00:00"
    filtered = S.parse_bsky_feed(payload, "impact")
    assert 0 < len(filtered) < len(all_posts)
    assert all("bluesky" in i["tags"] for i in filtered)


def test_parse_bsky_rejects_unknown_shape():
    with pytest.raises(SourceChanged):
        S.parse_bsky_feed({"error": "x"}, "all")


@respx.mock
async def test_bluesky_accounts_collect(monkeypatch):
    monkeypatch.setattr(S, "accounts", lambda p: [
        {"platform": "bluesky", "handle": "zekehausfather.com", "name": "Zeke Hausfather"},
        {"platform": "bluesky", "handle": "tdiliberto.bsky.social", "name": "Tom Di Liberto"},
    ])
    route = respx.get(f"{S.BSKY_PUBLIC}/app.bsky.feed.getAuthorFeed")
    route.side_effect = [httpx.Response(200, content=fx("bsky_feed_zeke.json")),
                         httpx.Response(502)]
    res = await run(S.BlueskyAccounts())
    assert res["ok"] and res["items"] > 0
    per = last_run("bluesky_accounts")["detail"]["accounts"]
    assert isinstance(per["zekehausfather.com"], int)
    assert per["tdiliberto.bsky.social"].startswith("error")


async def test_bluesky_search_needs_config():
    res = await run(S.BlueskySearch())
    assert res["needs_config"] == ["bluesky_handle", "bluesky_app_password"]
    assert last_run("bluesky_search")["error"].startswith("needs_config")


# ---------------------------------------------------------------- Mastodon

def test_parse_mastodon():
    items = S.parse_mastodon(fj("mastodon_elnino.json"), "all")
    assert len(items) == 10
    assert "# climate" not in items[0]["title"]  # hashtag spans joined back
    assert items[0]["url"].startswith("https://")
    # the captured #KohSamui page is 10 tourism posts, none about weather: all dropped
    assert S.parse_mastodon(fj("mastodon_kohsamui.json"), "impact") == []
    assert len(S.parse_mastodon(fj("mastodon_kohsamui.json"), "all")) == 10


@respx.mock
async def test_mastodon_collect_dedupes_across_instances():
    respx.get(url__regex=r"https://[^/]+/api/v1/timelines/tag/ElNino").mock(
        return_value=httpx.Response(200, content=fx("mastodon_elnino.json")))
    respx.get(url__regex=r"https://[^/]+/api/v1/timelines/tag/.*").mock(
        return_value=httpx.Response(200, content=b"[]"))
    res = await run(S.MastodonTags())
    assert res["ok"] and res["items"] == 10  # same statuses on both instances -> 10 rows
    assert len(feed("mastodon_tags")) == 10


# ---------------------------------------------------------------- Reddit

def test_parse_reddit():
    enso = S.parse_reddit(fx("reddit_enso.xml"), "enso")
    assert enso and all("enso" in i["tags"] for i in enso)
    assert enso[0]["ext_id"].startswith("t3_")
    assert " in r/" in enso[0]["author"]
    th = S.parse_reddit(fx("reddit_thailand.xml"), "impact")
    assert any("samui" in i["tags"] for i in th)


def test_reddit_alternates_queries():
    col = S.RedditSearch()
    assert col.pick(0)[0] != col.pick(col.interval_s)[0]


@respx.mock
async def test_reddit_collect_and_rate_limit():
    route = respx.get(url__startswith="https://www.reddit.com/r/")
    route.side_effect = [httpx.Response(200, content=fx("reddit_enso.xml")),
                         httpx.Response(429)]
    col = S.RedditSearch()
    col.pick = lambda now=None: S.REDDIT_QUERIES[0]
    res = await run(col)
    assert res["ok"] and res["items"] > 0
    res = await run(col)
    assert not res["ok"] and last_run("reddit_search")["http_status"] == 429


# ---------------------------------------------------------------- X

def test_parse_fx_timeline_and_search():
    tl = S.parse_fx(fj("fx_nwscpc.json"), "all")
    assert len(tl) == 10
    assert tl[0]["url"] == f"https://x.com/NWSCPC/status/{tl[0]['ext_id']}"
    assert tl[0]["published_at"].startswith("2026-09-10")
    search = S.parse_fx(fj("fx_search.json"), "enso_ctx")
    raw = fj("fx_search.json")["results"]
    assert 0 < len(search) < len(raw)
    assert not any("elninodivino" in i["author"] for i in search)  # reply, nickname


def test_nitter_antibot_page_is_detected():
    with pytest.raises(SourceChanged):
        S.parse_nitter_rss(fx("nitter_antibot.html"), "NOAA", "all")


@respx.mock
async def test_x_keyless_fxtwitter(monkeypatch):
    monkeypatch.setattr(S, "accounts", lambda p: [{"platform": "x", "handle": "NWSCPC",
                                                   "keep_all": True}])
    respx.get(f"{S.FX_API}/profile/NWSCPC/statuses").mock(
        return_value=httpx.Response(200, content=fx("fx_nwscpc.json")))
    respx.get(f"{S.FX_API}/search").mock(
        return_value=httpx.Response(200, content=fx("fx_search.json")))
    res = await run(S.XPosts())
    assert res["ok"] and res["items"] > 10
    d = last_run("x_posts")["detail"]
    assert d["strategy"] == "fxtwitter"
    assert d["tried"]["api_v2"].startswith("skipped")


@respx.mock
async def test_x_all_keyless_down_is_needs_config(monkeypatch):
    monkeypatch.setattr(S, "accounts", lambda p: [{"platform": "x", "handle": "NOAA"}])
    respx.get(url__startswith=S.FX_API).mock(return_value=httpx.Response(503))
    respx.get(url__startswith=S.SYNDICATION).mock(
        return_value=httpx.Response(429, content=b"Rate limit exceeded"))
    respx.get(url__regex=r"https://[^/]+/NOAA/rss").mock(
        return_value=httpx.Response(200, content=fx("nitter_antibot.html")))
    res = await run(S.XPosts())
    assert not res["ok"] and "needs_config" in res
    assert "x_bearer_token" in last_run("x_posts")["error"]
    assert all(h["dead_until"] > 0 for h in S._nitter_health.values())


@respx.mock
async def test_x_api_v2_when_token_set(monkeypatch):
    monkeypatch.setattr(settings, "x_bearer_token", "t")
    payload = {"data": [{"id": "1", "text": "El Niño rains flood Peru", "author_id": "9",
                         "created_at": "2026-09-24T10:00:00.000Z", "lang": "en"}],
               "includes": {"users": [{"id": "9", "username": "someone", "name": "Some One"}]}}
    route = respx.get(S.X_API_SEARCH).mock(return_value=httpx.Response(200, json=payload))
    res = await run(S.XPosts())
    assert res["ok"] and res["items"] == 1
    assert route.calls[0].request.headers["Authorization"] == "Bearer t"
    assert last_run("x_posts")["detail"]["strategy"] == "api_v2"


# ---------------------------------------------------------------- Telegram

def test_parse_telegram():
    html = fx("telegram_thethaiger.html").decode()
    items = S.parse_telegram(html, "thethaiger", "The Thaiger", "impact")
    ids = {i["ext_id"] for i in items}
    assert "TheThaiger/33650" in ids  # "Foreign man missing as overnight floods hit Pattaya"
    it = next(i for i in items if i["ext_id"] == "TheThaiger/33650")
    assert it["url"].startswith("https://thethaiger.com/")
    assert "https://" not in it["title"]
    assert it["published_at"].startswith("2026-09-24")
    everything = S.parse_telegram(html, "thethaiger", "The Thaiger", "all")
    assert len(everything) == 20
    with pytest.raises(SourceChanged):
        S.parse_telegram("<html>nope</html>", "x", "x", "all")
