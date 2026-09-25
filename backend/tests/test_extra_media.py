"""extra_media collectors against REAL payloads captured 2026-09-24 (no network).

Every YouTube channel id was resolved live on 2026-09-24 (the feed's own <title> is
checked on every run, see parse_youtube)."""

from pathlib import Path

import httpx
import pytest
import respx

from app import db
from app.collectors import extra_media as M
from app.collectors.base import SourceChanged, run_collector

FIX = Path(__file__).parent / "fixtures" / "extra"
NEWSLETTER_FIX = {
    "The Climate Brink": "rss_climatebrink.xml",
    "Yale Climate Connections": "rss_yaleclimateconnections.xml",
    "Climate Signals": "rss_climatesignals.xml",
}


def fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


@respx.mock
async def test_youtube_channels_filtered():
    for cid, *_ in M.YOUTUBE_CHANNELS:
        respx.get(M.YT_FEED.format(cid)).mock(
            return_value=httpx.Response(200, content=fx(f"yt_{cid}.xml")))
    async with httpx.AsyncClient() as c:
        res = await run_collector(M.YoutubeChannels(), c)
    assert res["ok"], res
    items = db.query("SELECT * FROM feed_items WHERE source='youtube_channels'")
    titles = {i["title"] for i in items}
    assert 'How "Super El Niño" Could Cause Worldwide Weather Chaos' in titles
    assert all("video" in i["tags"] for i in items)
    assert all(i["url"].startswith("https://www.youtube.com/watch?v=") for i in items)
    thai = [i for i in items if i["author"] == "Thai PBS (YouTube)"]
    assert thai and all(i["lang"] == "th" and "thailand" in i["tags"] for i in thai)
    # international channels only keep El Nino items
    for i in items:
        if i["author"] != "Thai PBS (YouTube)":
            assert "enso" in i["tags"], i["title"]


def test_youtube_recycled_channel_id_is_source_changed():
    with pytest.raises(SourceChanged):
        M.parse_youtube(fx("yt_UCe9IxQeBttZIYl5c43ycf9g.xml"), "NASA", "NASA", "en", "enso")


@respx.mock
async def test_newsletters():
    for url, name, *_ in M.NEWSLETTERS:
        respx.get(url).mock(return_value=httpx.Response(200, content=fx(NEWSLETTER_FIX[name])))
    async with httpx.AsyncClient() as c:
        res = await run_collector(M.NewslettersRss(), c)
    assert res["ok"], res
    items = db.query("SELECT * FROM feed_items WHERE source='newsletters_rss'")
    by_title = {i["title"]: i for i in items}
    brink = by_title["The Strongest El Niño Ever"]
    assert brink["kind"] == "research" and brink["author"] == "The Climate Brink"
    assert "enso" in brink["tags"] and "newsletter" in brink["tags"]


@respx.mock
async def test_one_dead_feed_is_not_fatal():
    for url, name, *_ in M.NEWSLETTERS:
        if name == "The Climate Brink":
            respx.get(url).mock(return_value=httpx.Response(503))
        else:
            respx.get(url).mock(return_value=httpx.Response(200, content=fx(NEWSLETTER_FIX[name])))
    async with httpx.AsyncClient() as c:
        res = await run_collector(M.NewslettersRss(), c)
    assert res["ok"]
    run = db.query("SELECT detail FROM source_runs WHERE source='newsletters_rss'")[0]
    assert run["detail"]["feeds"]["The Climate Brink"] == "http 503"
