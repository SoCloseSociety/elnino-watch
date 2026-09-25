"""Extra media sources (gap fill, 2026-09-24).

- youtube_channels  keyless YouTube channel RSS of agencies and broadcasters (feed, kind news,
                    tag "video"). Every channel id below was resolved against the live
                    feed on 2026-09-24 and the feed title must still match, so a recycled or
                    wrong id shows up as an error instead of silently posting someone else.
- newsletters_rss   climate newsletters / explainers (The Climate Brink, Yale Climate
                    Connections, Climate Signals).

International channels are filtered to items that mention El Nino / ENSO; Thai PBS
(Thai-language national broadcaster) to ENSO or impact items (flood, drought, storm,
heat, haze) because those are the local consequences.
"""

from __future__ import annotations

import asyncio
from typing import ClassVar

import feedparser
import httpx

from .. import db
from ..config import settings
from .base import DAY, Collector, RunContext, SourceChanged
from .news import build_item, clean_text, dedupe, freshest, is_relevant, stable_id, to_iso

YT_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
# (channel id, feed title as published, display name, language, relevance scope)
YOUTUBE_CHANNELS: tuple[tuple[str, str, str, str, str], ...] = (
    ("UCe9IxQeBttZIYl5c43ycf9g", "noaa", "NOAA", "en", "enso"),
    ("UCLA_DiR1FfKNvjuUpBHmylQ", "NASA", "NASA", "en", "enso"),
    ("UCMCDaG2oNwzEZLTk4ZJiWjg", "World Meteorological Organization - WMO", "WMO", "en",
     "enso"),
    ("UCdK5sfMQcJ64q8AGR_7-ZRw", "Copernicus ECMWF", "Copernicus ECMWF", "en", "enso"),
    ("UC5TOFhyb_LxL2VG_Zenhpzw", "Thai PBS", "Thai PBS", "th", "impact"),
    ("UCGTUbwceCMibvpbd2NaIP7A", "The Weather Channel", "The Weather Channel", "en", "enso"),
)


def parse_youtube(xml: bytes | str, expect_title: str, display: str, lang: str,
                  scope: str) -> tuple[int, list[dict]]:
    f = feedparser.parse(xml)
    title = (f.feed.get("title") or "").strip()
    if not title:
        raise SourceChanged(f"YouTube {display}: not a channel feed")
    if title != expect_title:
        raise SourceChanged(f"YouTube {display}: feed title is {title!r}, expected "
                            f"{expect_title!r} (channel id reused or wrong)")
    out = []
    for e in f.entries:
        vt = clean_text(e.get("title"))
        desc = clean_text(e.get("summary") or (e.get("media_description") or ""), 600)
        if not vt or not is_relevant(f"{vt} {desc}", scope):
            continue
        thumb = next((t.get("url") for t in e.get("media_thumbnail", []) or [] if t.get("url")),
                     None)
        vid = e.get("yt_videoid") or stable_id(e.get("link") or vt)
        out.append(build_item(
            ext_id=f"yt:{vid}", kind="news", title=vt, url=e.get("link"),
            author=f"{display} (YouTube)", lang=lang,
            published_at=to_iso(e.get("published_parsed") or e.get("published")),
            summary=desc, image=thumb, extra_tags=["video"],
        ))
    return len(f.entries), out


# (url, display name, language, scope, kind)
NEWSLETTERS: tuple[tuple[str, str, str, str, str], ...] = (
    ("https://www.theclimatebrink.com/feed", "The Climate Brink", "en", "impact", "research"),
    ("https://yaleclimateconnections.org/feed/", "Yale Climate Connections", "en", "enso",
     "news"),
    ("https://www.climatesignals.org/rss.xml", "Climate Signals", "en", "enso", "research"),
)


def parse_newsletter(xml: bytes | str, display: str, lang: str, scope: str,
                     kind: str) -> tuple[int, list[dict]]:
    f = feedparser.parse(xml)
    if not f.entries:
        if f.bozo:
            raise SourceChanged(f"{display}: unparseable feed ({f.get('bozo_exception')})")
        return 0, []
    out = []
    for e in f.entries:
        t = clean_text(e.get("title"))
        s = clean_text(e.get("summary"), 600)
        if not t or not is_relevant(f"{t} {s}", scope):
            continue
        link = e.get("link")
        out.append(build_item(
            ext_id=stable_id(e.get("id") or link or t), kind=kind, title=t, url=link,
            author=display, lang=lang,
            published_at=to_iso(e.get("published_parsed") or e.get("updated_parsed")),
            summary=s, extra_tags=["newsletter"],
        ))
    return len(f.entries), out


class _MultiFeed(Collector):
    """Fetch several feeds; one broken feed is reported in the notes, not fatal."""

    fetches: ClassVar[tuple] = ()

    def _url(self, spec) -> str:
        raise NotImplementedError

    def _parse(self, spec, content: bytes) -> tuple[int, list[dict]]:
        raise NotImplementedError

    def _label(self, spec) -> str:
        raise NotImplementedError

    async def collect(self, ctx: RunContext) -> int:
        sem = asyncio.Semaphore(3)

        async def one(spec):
            async with sem:
                try:
                    r = await ctx.client.get(self._url(spec),
                                             headers={"User-Agent": settings.user_agent})
                    if r.status_code != 200:
                        return self._label(spec), f"http {r.status_code}", []
                    n, items = self._parse(spec, r.content)
                    return self._label(spec), f"{len(items)}/{n}", items
                except (httpx.HTTPError, SourceChanged) as e:
                    return self._label(spec), f"error: {type(e).__name__}: {e}"[:200], []

        results = await asyncio.gather(*(one(s) for s in self.fetches))
        ctx.notes["feeds"] = {name: state for name, state, _ in results}
        ok = sum(1 for _n, s, _ in results if "/" in s)
        if ok == 0:
            raise RuntimeError(f"all {len(self.fetches)} feeds failed: {ctx.notes['feeds']}")
        ctx.last_status = 200
        items = dedupe([i for _n, _s, got in results for i in got])
        ctx.notes["freshest"] = freshest(items)
        return db.upsert_feed_items(self.name, items) if items else 0


class YoutubeChannels(_MultiFeed):
    name = "youtube_channels"
    title = "YouTube -- NOAA, NASA, WMO, Copernicus, Thai PBS, The Weather Channel"
    category = "news"
    provider = "YouTube channel RSS (keyless)"
    homepage = "https://www.youtube.com/@NOAA"
    endpoint = YT_FEED.format(YOUTUBE_CHANNELS[0][0])
    interval_s = 60 * 60
    freshness_basis = "feed"
    max_age_s = 14 * DAY  # filtered to ENSO / impact videos: quiet weeks are normal
    description = ("New videos from agency and broadcaster YouTube channels (NOAA, NASA, WMO, "
                   "Copernicus ECMWF, Thai PBS, The Weather Channel), read from YouTube's public "
                   "RSS. International channels: El Nino / ENSO videos only; Thai PBS: El Nino "
                   "or impact videos (flood, drought, storm, heat, haze). Tagged 'video'.")
    fetches = YOUTUBE_CHANNELS

    def _url(self, spec) -> str:
        return YT_FEED.format(spec[0])

    def _label(self, spec) -> str:
        return spec[2]

    def _parse(self, spec, content):
        return parse_youtube(content, spec[1], spec[2], spec[3], spec[4])


class NewslettersRss(_MultiFeed):
    name = "newsletters_rss"
    title = "Climate newsletters (The Climate Brink, Yale Climate Connections, Climate Signals)"
    category = "news"
    provider = "Publisher RSS feeds"
    homepage = "https://www.theclimatebrink.com/"
    endpoint = NEWSLETTERS[0][0]
    interval_s = 2 * 60 * 60
    freshness_basis = "feed"
    max_age_s = 45 * DAY  # filtered to ENSO posts: a month without one happens
    description = ("Scientist-written newsletters and explainers: The Climate Brink (Zeke "
                   "Hausfather, Andrew Dessler; El Nino or impact posts), Yale Climate "
                   "Connections and Climate Signals (El Nino posts only).")
    fetches = NEWSLETTERS

    def _url(self, spec) -> str:
        return spec[0]

    def _label(self, spec) -> str:
        return spec[1]

    def _parse(self, spec, content):
        return parse_newsletter(content, spec[1], spec[2], spec[3], spec[4])


COLLECTORS = [YoutubeChannels, NewslettersRss]
