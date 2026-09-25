"""Social collectors: Bluesky, Mastodon, Reddit, X, Telegram public channels.

Accounts come from app.accounts (each one verified against the live
platform). Posts are stored as feed_items kind="social". General accounts
are filtered to ENSO / climate-impact topics; accounts flagged keep_all are
stored in full. Nothing is synthesized: a strategy that fails is reported in
ctx.notes and, if nothing works, the collector says so (error or
needs_config) instead of returning a quiet zero.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import feedparser
import httpx

from .. import db
from ..accounts import accounts
from ..config import settings
from .base import DAY, Collector, NeedsConfig, RunContext, SourceChanged
from .news import (
    build_item,
    clean_text,
    dedupe,
    freshest,
    is_relevant,
    stable_id,
    strip_urls,
    to_iso,
)

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


# A live feed: posts older than this are not stored (timelines of quiet
# accounts otherwise surface months-old posts).
MAX_AGE_DAYS = 45


def recent(items: list[dict], now: datetime | None = None) -> list[dict]:
    cutoff = ((now or datetime.now(UTC)) - timedelta(days=MAX_AGE_DAYS)).isoformat()
    return [i for i in items if (i.get("published_at") or "9999") >= cutoff]


def _title(text: str, n: int = 200) -> str:
    t = strip_urls(clean_text(text)) or clean_text(text)
    return t if len(t) <= n else t[: n - 3].rstrip() + "..."


# --------------------------------------------------------------------------
# Bluesky
# --------------------------------------------------------------------------

BSKY_PUBLIC = "https://public.api.bsky.app/xrpc"
BSKY_PDS = "https://bsky.social/xrpc"
BSKY_SEARCH_TERMS = ("El Niño", "El Nino", "ENSO", "เอลนีโญ", "Koh Samui", "Thailand drought")


def parse_bsky_feed(payload: dict, scope: str) -> list[dict]:
    """app.bsky.feed.getAuthorFeed / searchPosts -> feed items (reposts skipped)."""
    if "feed" in payload:
        posts = [f.get("post") for f in payload["feed"] if not f.get("reason")]
    elif "posts" in payload:
        posts = payload["posts"]
    else:
        raise SourceChanged("Bluesky: neither 'feed' nor 'posts' in payload")
    out = []
    for p in posts:
        if not p or "record" not in p:
            continue
        rec = p["record"]
        text = rec.get("text") or ""
        ext = (rec.get("embed") or {}).get("external") or {}
        link_text = f"{ext.get('title', '')} {ext.get('description', '')}"
        if not is_relevant(f"{text} {link_text}", scope):
            continue
        author = p.get("author") or {}
        handle = author.get("handle", "")
        rkey = p["uri"].rsplit("/", 1)[-1]
        image = None
        emb = p.get("embed") or {}
        if emb.get("images"):
            image = emb["images"][0].get("thumb")
        elif (emb.get("external") or {}).get("thumb"):
            image = emb["external"]["thumb"]
        langs = rec.get("langs") or []
        out.append(build_item(
            ext_id=p["uri"], kind="social", title=_title(text or ext.get("title", "")),
            url=f"https://bsky.app/profile/{handle}/post/{rkey}",
            author=f"{author.get('displayName') or handle} (@{handle})",
            lang=langs[0][:2] if langs else None, published_at=to_iso(rec.get("createdAt")),
            summary=clean_text(f"{text} {link_text}", 1000), image=image,
            extra_tags=["bluesky"],
        ))
    return out


class BlueskyAccounts(Collector):
    name = "bluesky_accounts"
    freshness_basis = "feed"
    max_age_s = 1 * DAY
    title = "Bluesky -- verified ENSO scientists, agencies and media"
    category = "social"
    provider = "Bluesky public AppView"
    homepage = "https://bsky.app/"
    endpoint = f"{BSKY_PUBLIC}/app.bsky.feed.getAuthorFeed"
    interval_s = 15 * 60
    description = ("Author feeds of verified Bluesky accounts (NOAA, NWS, WMO, Copernicus, "
                   "ECMWF, Zeke Hausfather, Daniel Swain, Gavin Schmidt, Carbon Brief, ...), "
                   "keyless. Posts filtered to El Nino / climate-impact topics. Public search is "
                   "403 without login: see bluesky_search.")

    gap_s: ClassVar[float] = 0.3

    async def collect(self, ctx: RunContext) -> int:
        items: list[dict] = []
        per: dict[str, int | str] = {}
        for i, acc in enumerate(accounts("bluesky")):
            if i:
                await asyncio.sleep(self.gap_s)
            h = acc["handle"]
            try:
                r = await ctx.get(f"{BSKY_PUBLIC}/app.bsky.feed.getAuthorFeed",
                                  params={"actor": h, "limit": 30, "filter": "posts_no_replies"})
                got = parse_bsky_feed(r.json(), "all" if acc.get("keep_all") else "impact")
            except (httpx.HTTPError, ValueError, SourceChanged) as e:
                per[h] = f"error: {type(e).__name__}: {e}"[:120]
                continue
            per[h] = len(got)
            items += got
        ctx.notes["accounts"] = per
        if not any(isinstance(v, int) for v in per.values()):
            raise RuntimeError(f"Bluesky: every author feed failed: {per}")
        items = dedupe(recent(items))
        ctx.notes["freshest"] = freshest(items)
        return db.upsert_feed_items(self.name, items) if items else 0


class BlueskySearch(Collector):
    name = "bluesky_search"
    freshness_basis = "feed"
    max_age_s = 1 * DAY
    title = "Bluesky -- live search (El Nino, ENSO, Koh Samui)"
    category = "social"
    provider = "Bluesky (authenticated app password)"
    homepage = "https://bsky.app/search"
    endpoint = f"{BSKY_PDS}/app.bsky.feed.searchPosts"
    interval_s = 15 * 60
    description = ("Full-network Bluesky post search (sort=latest). The public AppView answers "
                   "403 to unauthenticated searchPosts, so this needs a Bluesky handle + app "
                   "password (Settings -> App passwords).")
    needs = ("bluesky_handle", "bluesky_app_password")

    async def collect(self, ctx: RunContext) -> int:
        r = await ctx.client.post(f"{BSKY_PDS}/com.atproto.server.createSession", json={
            "identifier": settings.bluesky_handle, "password": settings.bluesky_app_password})
        ctx.last_status = r.status_code
        if r.status_code in (400, 401):
            raise NeedsConfig(f"Bluesky login rejected ({r.status_code}): check the app password")
        r.raise_for_status()
        token = r.json()["accessJwt"]
        headers = {"Authorization": f"Bearer {token}"}
        items: list[dict] = []
        per: dict[str, int | str] = {}
        for term in BSKY_SEARCH_TERMS:
            try:
                rr = await ctx.get(f"{BSKY_PDS}/app.bsky.feed.searchPosts", headers=headers,
                                   params={"q": term, "sort": "latest", "limit": 50})
                got = parse_bsky_feed(rr.json(), "enso_ctx" if "El Ni" in term else "impact")
            except (httpx.HTTPError, ValueError, SourceChanged) as e:
                per[term] = f"error: {e}"[:120]
                continue
            per[term] = len(got)
            items += got
        ctx.notes["queries"] = per
        items = dedupe(recent(items))
        ctx.notes["freshest"] = freshest(items)
        return db.upsert_feed_items(self.name, items) if items else 0


# --------------------------------------------------------------------------
# Mastodon hashtag timelines
# --------------------------------------------------------------------------

# Verified 200 on 2026-09-24. Hashtag timelines show what each instance
# federates, so two big general instances cover more than one.
MASTODON_INSTANCES = ("mastodon.social", "mas.to")
# (tag, scope): ENSO tags are stored in full, local tags need an impact term.
MASTODON_TAGS = (("ElNino", "all"), ("ENSO", "impact"),  # #ElNiño is the same tag server-side
                 ("KohSamui", "impact"), ("Samui", "impact"), ("Thailand", "impact"))


def parse_mastodon(payload: list, scope: str) -> list[dict]:
    if not isinstance(payload, list):
        raise SourceChanged("Mastodon: tag timeline is not a list")
    out = []
    for s in payload:
        s = s.get("reblog") or s
        text = clean_text(s.get("content"))
        card = s.get("card") or {}
        if not is_relevant(f"{text} {card.get('title') or ''}", scope):
            continue
        acct = (s.get("account") or {}).get("acct", "")
        media = s.get("media_attachments") or []
        out.append(build_item(
            ext_id=stable_id(s.get("uri") or s.get("url") or s["id"]), kind="social",
            title=_title(text or card.get("title") or ""), url=s.get("url") or s.get("uri"),
            author=f"{(s.get('account') or {}).get('display_name') or acct} (@{acct})",
            lang=(s.get("language") or None), published_at=to_iso(s.get("created_at")),
            summary=text[:1000], image=(media[0].get("preview_url") if media else card.get("image")),
            extra_tags=["mastodon"],
        ))
    return out


class MastodonTags(Collector):
    name = "mastodon_tags"
    freshness_basis = "feed"
    max_age_s = 1 * DAY
    title = "Mastodon -- #ElNino #ENSO #KohSamui hashtag timelines"
    category = "social"
    provider = "Mastodon public API"
    homepage = "https://mastodon.social/tags/ElNino"
    endpoint = "https://mastodon.social/api/v1/timelines/tag/ElNino"
    interval_s = 15 * 60
    description = ("Public hashtag timelines on mastodon.social and mas.to (keyless): #ElNino, "
                   "#ElNiño stored in full; #ENSO, #KohSamui, #Samui, #Thailand kept only when "
                   "they mention ENSO or an impact (drought, flood, storm, heat, haze, ...).")

    async def collect(self, ctx: RunContext) -> int:
        items: list[dict] = []
        per: dict[str, int | str] = {}
        for inst in MASTODON_INSTANCES:
            for tag, scope in MASTODON_TAGS:
                key = f"{inst}#{tag}"
                try:
                    r = await ctx.get(f"https://{inst}/api/v1/timelines/tag/{tag}",
                                      params={"limit": 40})
                    got = parse_mastodon(r.json(), scope)
                except (httpx.HTTPError, ValueError, SourceChanged) as e:
                    per[key] = f"error: {type(e).__name__}"
                    continue
                per[key] = len(got)
                items += got
        ctx.notes["timelines"] = per
        if not any(isinstance(v, int) for v in per.values()):
            raise RuntimeError(f"Mastodon: every timeline failed: {per}")
        items = dedupe(recent(items))
        ctx.notes["freshest"] = freshest(items)
        return db.upsert_feed_items(self.name, items) if items else 0


# --------------------------------------------------------------------------
# Reddit (search RSS; JSON API is 403 without OAuth)
# --------------------------------------------------------------------------

REDDIT_QUERIES = (
    # (label, multi-subreddit, query, scope)
    ("enso", "weather+climate+climatechange+TropicalWeather+meteorology",
     '"el nino" OR "el niño" OR ENSO', "enso"),
    ("thailand", "Thailand+kohsamui+ThailandTourism+Bangkok",
     'flood OR drought OR storm OR "el nino" OR monsoon OR haze OR "water shortage"', "impact"),
)


def parse_reddit(xml: bytes | str, scope: str) -> list[dict]:
    f = feedparser.parse(xml)
    if not f.entries and (f.bozo or "atom" not in (f.version or "")):
        raise SourceChanged("Reddit: search RSS is not an Atom feed")
    out = []
    for e in f.entries:
        title = clean_text(e.get("title"))
        body = clean_text(e.get("summary"), 1000)
        if not title or not is_relevant(f"{title} {body}", scope):
            continue
        sub = (e.get("tags") or [{}])[0].get("term")
        thumb = (e.get("media_thumbnail") or [{}])[0].get("url")
        out.append(build_item(
            ext_id=e.get("id") or stable_id(e.get("link", title)), kind="social", title=title,
            url=e.get("link"), author=f"{e.get('author', '')} in r/{sub}" if sub else e.get("author"),
            lang=None, published_at=to_iso(e.get("published_parsed") or e.get("updated_parsed")),
            summary=body, image=thumb, extra_tags=["reddit"],
        ))
    return out


class RedditSearch(Collector):
    name = "reddit_search"
    freshness_basis = "feed"
    max_age_s = 1 * DAY
    title = "Reddit -- r/weather r/climate (El Nino) + r/Thailand r/kohsamui (impacts)"
    category = "social"
    provider = "Reddit search RSS"
    homepage = "https://www.reddit.com/r/kohsamui/"
    endpoint = "https://www.reddit.com/r/Thailand+kohsamui+ThailandTourism+Bangkok/search.rss"
    interval_s = 10 * 60
    description = ("Reddit search RSS, keyless (search.json is 403). Reddit allows ~1 anonymous "
                   "request per minute, so each run sends one query and the two queries "
                   "alternate: El Nino on weather/climate subs, impacts on Thai subs.")

    def pick(self, now: float | None = None) -> tuple[str, str, str, str]:
        slot = int((now if now is not None else time.time()) // self.interval_s)
        return REDDIT_QUERIES[slot % len(REDDIT_QUERIES)]

    async def collect(self, ctx: RunContext) -> int:
        label, subs, q, scope = self.pick()
        r = await ctx.get(f"https://www.reddit.com/r/{subs}/search.rss",
                          params={"q": q, "restrict_sr": "on", "sort": "new", "limit": 50})
        items = recent(parse_reddit(r.content, scope))
        ctx.notes["query"] = label
        ctx.notes["freshest"] = freshest(items)
        return db.upsert_feed_items(self.name, items) if items else 0


# --------------------------------------------------------------------------
# X / Twitter
# --------------------------------------------------------------------------

X_API_SEARCH = "https://api.x.com/2/tweets/search/recent"
FX_API = "https://api.fxtwitter.com/2"
SYNDICATION = "https://syndication.twitter.com/srv/timeline-profile/screen-name"
# Probed 2026-09-24: every one answered an anti-bot page, 403, 451 or timed out.
# Kept as a health-tracked last resort because mirrors come and go.
NITTER_MIRRORS = ("nitter.privacyredirect.com", "nitter.tiekoetter.com", "nitter.space",
                  "lightbrd.com", "nitter.catsarch.com", "nitter.poast.org", "xcancel.com")
_nitter_health: dict[str, dict] = {}
X_SEARCHES = (
    ('"El Niño" OR "El Nino" OR #ElNino', "enso_ctx"),
    ("เอลนีโญ", "enso"),
    ('"Koh Samui" OR เกาะสมุย OR "Surat Thani"', "impact"),
)


def _x_item(*, tid: str, text: str, handle: str, name: str, created, lang, image=None,
            scope: str) -> dict | None:
    if not is_relevant(text, scope):
        return None
    return build_item(
        ext_id=str(tid), kind="social", title=_title(text),
        url=f"https://x.com/{handle}/status/{tid}", author=f"{name or handle} (@{handle})",
        lang=(lang if lang and lang not in ("und", "zxx", "qme") else None),
        published_at=to_iso(created), summary=clean_text(text, 1000), image=image,
        extra_tags=["x"],
    )


def parse_fx(payload: dict, scope: str, skip_replies: bool = True) -> list[dict]:
    if not isinstance(payload, dict) or "results" not in payload:
        raise SourceChanged("FxTwitter: no 'results' in payload")
    out = []
    for t in payload["results"] or []:
        if t.get("type") != "status" or (skip_replies and t.get("replying_to")):
            continue
        a = t.get("author") or {}
        photos = ((t.get("media") or {}).get("photos") or [])
        it = _x_item(tid=t["id"], text=t.get("text", ""), handle=a.get("screen_name", ""),
                     name=a.get("name", ""), created=t.get("created_timestamp"),
                     lang=t.get("lang"), image=photos[0].get("url") if photos else None,
                     scope=scope)
        if it:
            out.append(it)
    return out


def parse_x_api(payload: dict, scope: str) -> list[dict]:
    users = {u["id"]: u for u in (payload.get("includes") or {}).get("users", [])}
    out = []
    for t in payload.get("data") or []:
        u = users.get(t.get("author_id"), {})
        it = _x_item(tid=t["id"], text=t.get("text", ""), handle=u.get("username", "i"),
                     name=u.get("name", ""), created=t.get("created_at"), lang=t.get("lang"),
                     scope=scope)
        if it:
            out.append(it)
    return out


def parse_syndication(html_text: str, scope: str) -> list[dict]:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                  html_text, re.DOTALL)
    if not m:
        raise SourceChanged("X syndication: no __NEXT_DATA__")
    data = json.loads(m.group(1))
    entries = (((data.get("props") or {}).get("pageProps") or {}).get("timeline") or {}).get(
        "entries") or []
    out = []
    for e in entries:
        t = (e.get("content") or {}).get("tweet") or {}
        if not t.get("id_str"):
            continue
        u = t.get("user") or {}
        it = _x_item(tid=t["id_str"], text=t.get("full_text") or t.get("text", ""),
                     handle=u.get("screen_name", ""), name=u.get("name", ""),
                     created=t.get("created_at"), lang=t.get("lang"), scope=scope)
        if it:
            out.append(it)
    return out


def parse_nitter_rss(xml: bytes | str, handle: str, scope: str) -> list[dict]:
    f = feedparser.parse(xml)
    if not f.entries or "rss" not in (f.version or ""):
        raise SourceChanged("nitter: not an RSS feed (anti-bot page?)")
    out = []
    for e in f.entries:
        m = re.search(r"/status/(\d+)", e.get("link", ""))
        if not m:
            continue
        it = _x_item(tid=m.group(1), text=clean_text(e.get("title")), handle=handle,
                     name=handle, created=e.get("published_parsed"), lang=None, scope=scope)
        if it:
            out.append(it)
    return out


class XPosts(Collector):
    name = "x_posts"
    freshness_basis = "feed"
    max_age_s = 1 * DAY
    title = "X (Twitter) -- verified accounts + El Nino / Koh Samui search"
    category = "social"
    provider = "X API v2 / cookie session / keyless (FxTwitter, syndication, nitter)"
    homepage = "https://x.com/NWSCPC"
    endpoint = f"{FX_API}/profile/NWSCPC/statuses"
    interval_s = 15 * 60
    description = ("Strategies in order, first that works wins: (a) X API v2 recent search if "
                   "X_BEARER_TOKEN; (b) cookie session via twscrape if X_AUTH_TOKEN + X_CT0; "
                   "(c) keyless: FxTwitter public API (verified account timelines + search), "
                   "then syndication.twitter.com timelines, then nitter mirror RSS. "
                   "ctx notes record which strategy worked.")

    gap_s: ClassVar[float] = 1.0

    # ---- (a) official API
    async def _api_v2(self, ctx: RunContext) -> list[dict]:
        headers = {"Authorization": f"Bearer {settings.x_bearer_token}"}
        froms = " OR ".join(f"from:{a['handle']}" for a in accounts("x")[:20])
        items: list[dict] = []
        for q, scope in [('("El Niño" OR "El Nino" OR #ENSO OR เอลนีโญ) -is:retweet', "enso_ctx"),
                         ('("Koh Samui" OR เกาะสมุย) -is:retweet', "impact"),
                         (f"({froms}) -is:retweet -is:reply", "impact")]:
            r = await ctx.get(X_API_SEARCH, headers=headers, params={
                "query": q, "max_results": 50, "tweet.fields": "created_at,lang,author_id",
                "expansions": "author_id", "user.fields": "username,name"})
            items += parse_x_api(r.json(), scope)
        return items

    # ---- (b) cookie session (optional dependency, lazy import)
    async def _cookie(self, ctx: RunContext) -> list[dict]:
        try:
            from twscrape import API  # type: ignore[import-not-found]
        except ImportError as e:
            raise RuntimeError("twscrape not installed (uv add twscrape)") from e
        pool = settings.db_path.parent / "twscrape_accounts.db"
        api = API(str(pool))
        cookies = f"auth_token={settings.x_auth_token}; ct0={settings.x_ct0}"
        await api.pool.add_account("elnino_cookie", "x", "x@invalid", "x", cookies=cookies)
        items: list[dict] = []
        for q, scope in X_SEARCHES:
            async for t in api.search(f"{q} -filter:replies", limit=40):
                it = _x_item(tid=str(t.id), text=t.rawContent, handle=t.user.username,
                             name=t.user.displayname, created=t.date.isoformat(), lang=t.lang,
                             scope=scope)
                if it:
                    items.append(it)
        return items

    # ---- (c) keyless
    async def _fx(self, ctx: RunContext, per: dict) -> tuple[list[dict], int]:
        items: list[dict] = []
        ok = 0
        headers = {"User-Agent": BROWSER_UA}
        for acc in accounts("x"):
            h = acc["handle"]
            try:
                r = await ctx.get(f"{FX_API}/profile/{h}/statuses", headers=headers)
                got = parse_fx(r.json(), "all" if acc.get("keep_all") else "impact")
                # timelines include reposts of other accounts: keep them, they were
                # chosen by a verified account, but only if on topic
                ok += 1
                per[f"fx:@{h}"] = len(got)
                items += got
            except (httpx.HTTPError, ValueError, SourceChanged) as e:
                per[f"fx:@{h}"] = f"error: {type(e).__name__}"[:80]
            await asyncio.sleep(self.gap_s)
        for q, scope in X_SEARCHES:
            try:
                r = await ctx.get(f"{FX_API}/search", headers=headers, params={"q": q})
                got = parse_fx(r.json(), scope)
                ok += 1
                per[f"fx:search:{q}"] = len(got)
                items += got
            except (httpx.HTTPError, ValueError, SourceChanged) as e:
                per[f"fx:search:{q}"] = f"error: {type(e).__name__}"[:80]
            await asyncio.sleep(self.gap_s)
        return items, ok

    async def _syndication(self, ctx: RunContext, per: dict) -> tuple[list[dict], int]:
        items: list[dict] = []
        ok = 0
        for acc in accounts("x"):
            h = acc["handle"]
            try:
                r = await ctx.client.get(f"{SYNDICATION}/{h}", headers={
                    "User-Agent": BROWSER_UA, "Referer": "https://twitter.com/"})
                if r.status_code == 429:
                    per["syndication"] = "429 rate-limited"
                    break
                r.raise_for_status()
                got = parse_syndication(r.text, "all" if acc.get("keep_all") else "impact")
                ok += 1
                items += got
                per[f"syn:@{h}"] = len(got)
            except (httpx.HTTPError, ValueError, SourceChanged) as e:
                per[f"syn:@{h}"] = f"error: {type(e).__name__}"[:80]
                break  # one failure = the endpoint is down for us; don't hammer
        return items, ok

    async def _nitter(self, ctx: RunContext, per: dict) -> tuple[list[dict], int]:
        now = time.time()
        alive = [m for m in NITTER_MIRRORS
                 if _nitter_health.get(m, {}).get("dead_until", 0) < now]
        items: list[dict] = []
        ok = 0
        for m in alive:
            h = accounts("x")[0]["handle"]
            try:
                r = await ctx.client.get(f"https://{m}/{h}/rss",
                                         headers={"User-Agent": BROWSER_UA}, timeout=15.0)
                r.raise_for_status()
                parse_nitter_rss(r.content, h, "all")  # probe: raises on anti-bot pages
            except (httpx.HTTPError, SourceChanged) as e:
                fails = _nitter_health.get(m, {}).get("fails", 0) + 1
                _nitter_health[m] = {"fails": fails, "dead_until": now + min(3600, 300 * fails),
                                     "last_error": f"{type(e).__name__}"}
                per[f"nitter:{m}"] = f"dead ({type(e).__name__})"
                continue
            _nitter_health[m] = {"fails": 0, "dead_until": 0}
            per[f"nitter:{m}"] = "alive"
            for acc in accounts("x"):
                try:
                    rr = await ctx.client.get(f"https://{m}/{acc['handle']}/rss",
                                              headers={"User-Agent": BROWSER_UA}, timeout=15.0)
                    rr.raise_for_status()
                    items += parse_nitter_rss(rr.content, acc["handle"],
                                              "all" if acc.get("keep_all") else "impact")
                    ok += 1
                except (httpx.HTTPError, SourceChanged):
                    continue
                await asyncio.sleep(self.gap_s)
            break
        return items, ok

    async def collect(self, ctx: RunContext) -> int:
        per: dict[str, int | str] = {}
        tried: dict[str, str] = {}
        items: list[dict] = []
        used = None
        if settings.x_bearer_token:
            try:
                items = await self._api_v2(ctx)
                used = "api_v2"
            except Exception as e:  # noqa: BLE001 -- fall through to the next strategy
                tried["api_v2"] = f"{type(e).__name__}: {e}"[:160]
        else:
            tried["api_v2"] = "skipped: no x_bearer_token"
        if used is None and settings.x_auth_token and settings.x_ct0:
            try:
                items = await self._cookie(ctx)
                used = "cookie_session"
            except Exception as e:  # noqa: BLE001
                tried["cookie_session"] = f"{type(e).__name__}: {e}"[:160]
        elif used is None:
            tried["cookie_session"] = "skipped: no x_auth_token + x_ct0"
        if used is None:
            for label, fn in (("fxtwitter", self._fx), ("syndication", self._syndication),
                              ("nitter", self._nitter)):
                got, ok = await fn(ctx, per)
                if ok:
                    items, used = got, label
                    break
                tried[label] = "no successful response"
        ctx.notes["strategy"] = used
        ctx.notes["tried"] = tried
        ctx.notes["calls"] = per
        if used is None:
            if not (settings.x_bearer_token or (settings.x_auth_token and settings.x_ct0)):
                raise NeedsConfig("keyless X access failed (fxtwitter, syndication, nitter); set "
                                  "x_bearer_token or x_auth_token + x_ct0")
            raise RuntimeError(f"every X strategy failed: {tried}")
        ctx.last_status = 200
        items = dedupe(recent(items))
        ctx.notes["freshest"] = freshest(items)
        return db.upsert_feed_items(self.name, items) if items else 0


# --------------------------------------------------------------------------
# Telegram public channels (t.me/s web preview, keyless)
# --------------------------------------------------------------------------

_TG_MSG = re.compile(
    r'<div class="tgme_widget_message [^"]*"[^>]*data-post="(?P<post>[^"]+)"(?P<body>.*?)'
    r'(?=<div class="tgme_widget_message_wrap|\Z)', re.DOTALL)
_TG_TEXT = re.compile(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.DOTALL)
_TG_TIME = re.compile(r'<time[^>]+datetime="([^"]+)"')
_TG_LINK = re.compile(r'<a[^>]+href="(https?://(?!t\.me)[^"]+)"')


def parse_telegram(html_text: str, channel: str, name: str, scope: str) -> list[dict]:
    if "tgme_channel_info" not in html_text and "tgme_widget_message" not in html_text:
        raise SourceChanged(f"Telegram t.me/s/{channel}: not a channel preview page")
    out = []
    for m in _TG_MSG.finditer(html_text):
        body = m.group("body")
        tm = _TG_TEXT.search(body)
        if not tm:
            continue
        text = clean_text(tm.group(1))
        if not text or not is_relevant(text, scope):
            continue
        link = _TG_LINK.search(tm.group(1))
        ts = _TG_TIME.search(body)
        out.append(build_item(
            ext_id=m.group("post"), kind="social", title=_title(text),
            url=link.group(1) if link else f"https://t.me/{m.group('post')}",
            author=f"{name} (t.me/{channel})", lang=None,
            published_at=to_iso(ts.group(1)) if ts else None, summary=text[:1000],
            extra_tags=["telegram"],
        ))
    return out


class TelegramChannels(Collector):
    name = "telegram_channels"
    freshness_basis = "feed"
    max_age_s = 3 * DAY  # few channels, filtered to impacts
    title = "Telegram -- public channels (web preview)"
    category = "social"
    provider = "Telegram t.me/s preview"
    homepage = "https://t.me/s/thethaiger"
    endpoint = "https://t.me/s/thethaiger"
    interval_s = 15 * 60
    description = ("Keyless read of verified public Telegram channels via t.me/s/<channel>, "
                   "filtered to El Nino / impact posts. Channels whose preview is empty or "
                   "stale were left out (see app/accounts.py).")

    async def collect(self, ctx: RunContext) -> int:
        items: list[dict] = []
        per: dict[str, int | str] = {}
        for acc in accounts("telegram"):
            ch = acc["handle"]
            try:
                r = await ctx.get(f"https://t.me/s/{ch}", headers={"User-Agent": BROWSER_UA})
                got = parse_telegram(r.text, ch, acc["name"],
                                     "all" if acc.get("keep_all") else "impact")
            except (httpx.HTTPError, SourceChanged) as e:
                per[ch] = f"error: {type(e).__name__}"
                continue
            per[ch] = len(got)
            items += got
        items = recent(items)
        ctx.notes["channels"] = per
        if not any(isinstance(v, int) for v in per.values()):
            raise RuntimeError(f"Telegram: every channel failed: {per}")
        ctx.notes["freshest"] = freshest(items)
        return db.upsert_feed_items(self.name, items) if items else 0


COLLECTORS = [BlueskyAccounts, BlueskySearch, MastodonTags, RedditSearch, XPosts,
              TelegramChannels]
