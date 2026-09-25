"""News collectors: GDELT DOC API, Google News RSS (multi-language), direct RSS.

Everything here is keyless. What a collector stores is exactly what the
source returned: titles, links, publishers, dates. Tags and approximate
coordinates are derived from the text (place mentions) or, for GDELT, from
the publisher's country, and are marked as approximate in `tags`.

Shared text helpers (`topic_tags`, `is_relevant`, `place_geo`) are also used
by app.collectors.social.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import ClassVar

import feedparser
import httpx

from .. import db
from ..config import settings
from .base import DAY, Collector, RunContext, SourceChanged

# --------------------------------------------------------------------------
# Text helpers (shared with social.py)
# --------------------------------------------------------------------------

ENSO_TERMS = (
    r"el ?ni[nñ]o", r"la ?ni[nñ]a", r"\benso\b", r"elnino", r"elniño", r"เอลนีโญ", r"ลานีญา",
    r"super el", r"nino ?3\.4", r"niño ?3\.4", r"oceanic ni[nñ]o index",
)
# Impact vocabulary, several languages. Kept specific on purpose: general
# feeds are filtered with it, so a vague word here floods the feed.
IMPACT_TERMS: dict[str, tuple[str, ...]] = {
    "drought": (r"drought", r"dry spell", r"water shortage", r"water crisis", r"water supply",
                r"reservoir", r"sécheresse", r"sequía", r"seca\b", r"kekeringan", r"hạn hán",
                r"ภัยแล้ง", r"แล้ง", r"ขาดแคลนน้ำ", r"น้ำประปา", r"อ่างเก็บน้ำ",
                r"saltwater intrusion", r"xâm nhập mặn"),
    "flood": (r"flood", r"flash flood", r"inondation", r"inundaci", r"enchente", r"banjir",
              r"lũ lụt", r"ngập lụt", r"ท่วม", r"น้ำป่า", r"landslide", r"ดินถล่ม", r"heavy rain",
              r"ฝนตกหนัก", r"torrential"),
    "storm": (r"\bstorm\b", r"typhoon", r"cyclone", r"tropical depression", r"tempête", r"tormenta",
              r"huracán", r"hurricane", r"badai", r"bão", r"พายุ", r"ดีเปรสชัน", r"คลื่นลมแรง",
              r"rough sea", r"monsoon", r"มรสุม", r"mousson", r"monzón"),
    "heat": (r"heatwave", r"heat wave", r"extreme heat", r"record heat", r"heat stroke",
             r"hottest", r"canicule", r"ola de calor", r"onda de calor", r"gelombang panas",
             r"nắng nóng", r"คลื่นความร้อน", r"อากาศร้อนจัด", r"heat deaths"),
    "haze": (r"\bhaze\b", r"pm ?2\.5", r"forest fire", r"wildfire", r"bushfire", r"peatland fire",
             r"kebakaran hutan", r"karhutla", r"หมอกควัน", r"ฝุ่น", r"ไฟป่า", r"incendie"),
    "bleaching": (r"coral bleaching", r"bleaching", r"blanchiment", r"blanqueamiento",
                  r"ปะการังฟอกขาว", r"marine heatwave"),
    "weather": (r"weather warning", r"meteorolog", r"อุตุนิยมวิทยา", r"กรมอุตุ", r"rainfall",
                r"pluviom", r"lluvias", r"chuvas"),
}
PLACES: tuple[tuple[str, str, float, float], ...] = (
    # (tag, regex, lat, lon) -- most specific first
    ("samui", r"samui|สมุย", 9.512, 100.013),
    ("samui", r"koh phangan|ko pha ?ngan|พะงัน", 9.73, 100.03),
    ("samui", r"koh tao|เกาะเต่า", 10.09, 99.84),
    ("thailand", r"surat thani|สุราษฎร์", 9.14, 99.33),
    ("thailand", r"nakhon si thammarat|นครศรีธรรมราช", 8.43, 99.96),
    ("thailand", r"phuket|ภูเก็ต", 7.88, 98.39),
    ("thailand", r"chiang mai|เชียงใหม่", 18.79, 98.98),
    ("thailand", r"pattaya|พัทยา", 12.93, 100.88),
    ("thailand", r"bangkok|กรุงเทพ", 13.75, 100.50),
    ("thailand", r"thailand|\bthai\b|ประเทศไทย|ไทย|thaïlande|tailandia", 15.87, 100.99),
    ("peru", r"\bperu\b|pérou|perú", -9.19, -75.02),
    ("ecuador", r"ecuador|équateur", -1.83, -78.18),
    ("indonesia", r"indonesia|indonésie", -0.79, 113.92),
    ("philippines", r"philippines|filipinas", 12.88, 121.77),
    ("vietnam", r"vietnam|việt nam|viet nam", 14.06, 108.28),
    ("malaysia", r"malaysia|malaisie", 4.21, 101.98),
    ("australia", r"australia|australie", -25.27, 133.78),
    ("india", r"\bindia\b|\binde\b", 20.59, 78.96),
    ("california", r"california|californie", 36.78, -119.42),
    ("brazil", r"brazil|brasil|brésil", -14.24, -51.93),
    ("southern_africa", r"southern africa|zimbabwe|zambia|malawi|mozambique", -18.0, 30.0),
)

_ENSO_RE = re.compile("|".join(ENSO_TERMS), re.IGNORECASE)
_IMPACT_RE = {k: re.compile("|".join(v), re.IGNORECASE) for k, v in IMPACT_TERMS.items()}
_PLACE_RE = [(t, re.compile(p, re.IGNORECASE), la, lo) for t, p, la, lo in PLACES]
# "El Nino" is also a nickname (footballers, singers): open searches need a
# climate word next to it.
CLIMATE_CTX = (
    r"climat", r"clima", r"weather", r"ocean", r"pacific", r"pac[ií]fico", r"temperat", r"\brain",
    r"forecast", r"noaa", r"ph[eé]nom[eè]n", r"fen[oó]meno", r"fenômeno", r"lluvia", r"chuva",
    r"pluie", r"iklim", r"cuaca", r"hujan", r"khí hậu", r"thời tiết", r"\bmưa", r"ภูมิอากาศ",
    r"อากาศ", r"ฝน", r"ปรากฏการณ์", r"super ?el", r"\benso\b", r"la ni[nñ]a", r"warming",
    r"sst\b", r"monsoon", r"mousson", r"harvest", r"crop", r"cosecha", r"safra", r"agricult",
    r"global", r"heat", r"calor", r"chaleur", r"panas", r"nóng", r"ร้อน",
)
_CTX_RE = re.compile("|".join(CLIMATE_CTX), re.IGNORECASE)
_INLINE_TAG_RE = re.compile(r"</?(?:span|a|b|i|em|strong)\b[^>]*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+")


def strip_urls(s: str) -> str:
    return re.sub(r"\s+", " ", _URL_RE.sub("", s)).strip()


def clean_text(s: str | None, limit: int | None = None) -> str:
    if not s:
        return ""
    s = html.unescape(_TAG_RE.sub(" ", _INLINE_TAG_RE.sub("", s)))
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit] if limit else s


def mentions_enso(text: str) -> bool:
    return bool(_ENSO_RE.search(text or ""))


def impact_tags(text: str) -> list[str]:
    return [k for k, rx in _IMPACT_RE.items() if rx.search(text or "")]


def topic_tags(text: str) -> list[str]:
    """enso + impact categories + place tags (thailand/samui/...)."""
    tags: list[str] = []
    if mentions_enso(text):
        tags.append("enso")
    tags += impact_tags(text)
    for tag, rx, _la, _lo in _PLACE_RE:
        if rx.search(text or "") and tag not in tags:
            tags.append(tag)
    if "samui" in tags and "thailand" not in tags:
        tags.append("thailand")
    return tags


def is_relevant(text: str, scope: str) -> bool:
    """scope: 'all' keeps everything, 'enso' needs an ENSO mention,
    'enso_ctx' an ENSO mention plus a climate/impact word (open searches),
    'impact' needs ENSO or an impact term."""
    if scope == "all":
        return True
    if scope == "enso":
        return mentions_enso(text)
    if scope == "enso_ctx":
        return mentions_enso(text) and (bool(_CTX_RE.search(text)) or bool(impact_tags(text)))
    return mentions_enso(text) or bool(impact_tags(text))


def place_geo(text: str) -> tuple[float, float] | None:
    """Approximate coordinates of the most specific place the text mentions."""
    for _tag, rx, la, lo in _PLACE_RE:
        if rx.search(text or ""):
            return la, lo
    return None


def stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:20]


def to_iso(value) -> str | None:
    """struct_time / RFC 822 / ISO -> ISO 8601 UTC (seconds)."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, time.struct_time):
            dt = datetime(*value[:6], tzinfo=UTC)
        elif isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value, UTC)
        elif isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}", value):
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
        else:
            dt = parsedate_to_datetime(str(value))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).replace(microsecond=0).isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


def build_item(*, ext_id: str, kind: str, title: str, url: str | None, author: str | None,
               lang: str | None, published_at: str | None, summary: str = "",
               image: str | None = None, extra_tags: list[str] | None = None,
               geo: tuple[float, float] | None = None) -> dict:
    text = f"{title} {summary}"
    tags = topic_tags(text)
    for t in extra_tags or []:
        if t not in tags:
            tags.append(t)
    g = place_geo(text) or geo
    return {
        "ext_id": ext_id, "kind": kind, "title": title[:500], "summary": summary[:1000] or None,
        "url": url, "author": author, "lang": lang, "image": image,
        "published_at": published_at, "lat": g[0] if g else None, "lon": g[1] if g else None,
        "tags": tags,
    }


def freshest(items: list[dict]) -> str | None:
    ts = [i["published_at"] for i in items if i.get("published_at")]
    return max(ts) if ts else None


def dedupe(items: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for it in items:
        if it["ext_id"] in seen:
            for t in it["tags"]:
                if t not in seen[it["ext_id"]]["tags"]:
                    seen[it["ext_id"]]["tags"].append(t)
        else:
            seen[it["ext_id"]] = it
    return list(seen.values())


def _image_of(entry) -> str | None:
    for mc in entry.get("media_content", []) or []:
        if mc.get("url") and (mc.get("medium") == "image" or "image" in mc.get("type", "image")):
            return mc["url"]
    for mt in entry.get("media_thumbnail", []) or []:
        if mt.get("url"):
            return mt["url"]
    for enc in entry.get("enclosures", []) or []:
        if enc.get("type", "").startswith("image/") and enc.get("href"):
            return enc["href"]
    return None


# --------------------------------------------------------------------------
# GDELT DOC 2.0 API
# --------------------------------------------------------------------------

GDELT_DOC = "https://api.gdeltproject.org/api/v2/doc/doc"
_ENSO_Q = '("El Nino" OR "El Niño" OR ENSO)'
# (label, query). Language queries use GDELT's machine-translated index plus
# the sourcelang: filter, so the English keyword matches native coverage.
GDELT_QUERIES: tuple[tuple[str, str], ...] = (
    ("enso_all", _ENSO_Q),  # every language GDELT covers, newest first
    ("enso_th", f"{_ENSO_Q} sourcelang:thai"),
    ("enso_id", f"{_ENSO_Q} sourcelang:indonesian"),
    ("enso_vi", f"{_ENSO_Q} sourcelang:vietnamese"),
    ("enso_fr", f"{_ENSO_Q} sourcelang:french"),
    ("drought_thailand", "drought Thailand"),
    ("samui", '"Koh Samui" (water OR drought OR flood OR storm)'),
    ("coral_bleaching", '"coral bleaching"'),
    ("peru_floods", "Peru (floods OR flooding)"),
    ("indonesia_fires", 'Indonesia (wildfire OR "forest fire" OR haze)'),
    ("australia_drought", "Australia drought"),
    ("india_monsoon", "India monsoon (deficit OR drought OR rainfall)"),
)
GDELT_LANG = {
    "english": "en", "french": "fr", "spanish": "es", "thai": "th", "indonesian": "id",
    "vietnamese": "vi", "portuguese": "pt", "german": "de", "italian": "it", "japanese": "ja",
    "chinese": "zh", "korean": "ko", "malay": "ms", "tagalog": "tl", "hindi": "hi",
    "arabic": "ar", "russian": "ru", "dutch": "nl", "turkish": "tr", "polish": "pl",
    "hungarian": "hu", "malayalam": "ml", "hebrew": "he", "romanian": "ro", "czech": "cs",
    "greek": "el", "ukrainian": "uk", "bengali": "bn", "tamil": "ta", "urdu": "ur",
}
# GDELT sourcecountry (publisher country, English name) -> approximate centroid.
COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "united states": (39.83, -98.58), "united kingdom": (54.0, -2.0), "thailand": (15.87, 100.99),
    "australia": (-25.27, 133.78), "india": (20.59, 78.96), "indonesia": (-0.79, 113.92),
    "philippines": (12.88, 121.77), "vietnam": (14.06, 108.28), "malaysia": (4.21, 101.98),
    "singapore": (1.35, 103.82), "peru": (-9.19, -75.02), "ecuador": (-1.83, -78.18),
    "chile": (-35.68, -71.54), "colombia": (4.57, -74.30), "mexico": (23.63, -102.55),
    "brazil": (-14.24, -51.93), "argentina": (-38.42, -63.62), "canada": (56.13, -106.35),
    "france": (46.23, 2.21), "spain": (40.46, -3.75), "portugal": (39.40, -8.22),
    "germany": (51.17, 10.45), "italy": (41.87, 12.57), "japan": (36.20, 138.25),
    "china": (35.86, 104.20), "south korea": (35.91, 127.77), "taiwan": (23.70, 120.96),
    "new zealand": (-40.90, 174.89), "south africa": (-30.56, 22.94), "kenya": (-0.02, 37.91),
    "nigeria": (9.08, 8.68), "pakistan": (30.38, 69.35), "bangladesh": (23.68, 90.36),
    "sri lanka": (7.87, 80.77), "myanmar": (21.91, 95.96), "burma": (21.91, 95.96),
    "cambodia": (12.57, 104.99), "laos": (19.86, 102.50), "ireland": (53.41, -8.24),
    "venezuela": (6.42, -66.59), "bolivia": (-16.29, -63.59), "guatemala": (15.78, -90.23),
    "honduras": (15.20, -86.24), "costa rica": (9.75, -83.75), "panama": (8.54, -80.78),
    "papua new guinea": (-6.31, 143.96), "fiji": (-17.71, 178.07), "zimbabwe": (-19.02, 29.15),
    "zambia": (-13.13, 27.85), "mozambique": (-18.67, 35.53), "ethiopia": (9.15, 40.49),
    "netherlands": (52.13, 5.29), "belgium": (50.50, 4.47), "switzerland": (46.82, 8.23),
    "hong kong": (22.32, 114.17), "qatar": (25.35, 51.18), "united arab emirates": (23.42, 53.85),
}

# One GDELT client-wide gate: 1 request / 5 s is the documented limit.
_gdelt_lock = asyncio.Lock()
_gdelt_last = 0.0


def parse_gdelt(payload: dict, label: str) -> list[dict]:
    if not isinstance(payload, dict):
        raise SourceChanged("GDELT: payload is not an object")
    arts = payload.get("articles", [])
    if not isinstance(arts, list):
        raise SourceChanged("GDELT: 'articles' is not a list")
    out = []
    for a in arts:
        url = a.get("url")
        # GDELT tokenizes titles ("word , word"): undo the space before , and .
        title = re.sub(r"\s+([,.])(\s|$)", r"\1\2", clean_text(a.get("title")))
        if not url or not title:
            continue
        seen = a.get("seendate") or ""
        pub = None
        m = re.match(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z", seen)
        if m:
            pub = datetime(*map(int, m.groups()), tzinfo=UTC).isoformat()
        country = (a.get("sourcecountry") or "").strip()
        geo = COUNTRY_CENTROIDS.get(country.lower())
        # the query matched the article body even when the title does not say it
        extra = ["enso"] if label.startswith("enso") else []
        if geo and not place_geo(title):
            extra.append("geo_publisher_country")  # approximate: where the outlet is
        out.append(build_item(
            ext_id=stable_id(url), kind="news", title=title, url=url,
            author=a.get("domain"), lang=GDELT_LANG.get((a.get("language") or "").lower()),
            published_at=pub, image=a.get("socialimage") or None, extra_tags=extra, geo=geo,
        ))
    return out


class GdeltNews(Collector):
    name = "gdelt_news"
    freshness_basis = "feed"
    max_age_s = 2 * DAY
    title = "GDELT -- El Nino & impacts news (multi-language)"
    category = "news"
    provider = "GDELT Project DOC 2.0 API"
    homepage = "https://www.gdeltproject.org/"
    endpoint = GDELT_DOC
    interval_s = 20 * 60
    description = ("Worldwide news search: El Nino / ENSO in every language GDELT indexes (plus "
                   "th, id, vi, fr focus) and impact queries (Thailand drought, Koh Samui, coral "
                   "bleaching, Peru floods, Indonesia fires, Australia drought, India monsoon). "
                   "GDELT throttles harder than its documented 1 req / 5 s (a 2nd request 6 s "
                   "later got 429 on 2026-09-24): each run sends the global ENSO query + one "
                   "rotating query (3-day window), 20 s apart, backs off once and stops at the "
                   "next 429. Coordinates are approximate: place named in the title, else "
                   "publisher country centroid (tag geo_publisher_country).")

    gap_s: ClassVar[float] = 20.0
    backoff_s: ClassVar[float] = 30.0
    per_run: ClassVar[int] = 1

    def plan(self, now: float | None = None) -> list[tuple[str, str, str]]:
        """(label, query, timespan): the global query + a time-rotated slice."""
        rest = GDELT_QUERIES[1:]
        slot = int((now if now is not None else time.time()) // self.interval_s)
        start = (slot * self.per_run) % len(rest)
        picked = [rest[(start + i) % len(rest)] for i in range(min(self.per_run, len(rest)))]
        # rotated queries come around every ~len/per_run runs: look back 3 days
        return [(*GDELT_QUERIES[0], "1d")] + [(lbl, q, "3d") for lbl, q in picked]

    async def _fetch(self, ctx: RunContext, query: str, timespan: str) -> httpx.Response:
        global _gdelt_last
        params = {"query": query, "mode": "artlist", "format": "json", "maxrecords": "100",
                  "timespan": timespan, "sort": "datedesc"}
        async with _gdelt_lock:
            wait = self.gap_s - (time.monotonic() - _gdelt_last)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                r = await ctx.client.get(GDELT_DOC, params=params, timeout=60.0)
            finally:
                _gdelt_last = time.monotonic()
            ctx.last_status = r.status_code
            return r

    async def collect(self, ctx: RunContext) -> int:
        items: list[dict] = []
        per_query: dict[str, int | str] = {}
        retried = False
        plan = self.plan()
        i = 0
        while i < len(plan):
            label, q, span = plan[i]
            try:
                r = await self._fetch(ctx, q, span)
            except httpx.HTTPError as e:
                per_query[label] = f"error: {type(e).__name__}"
                i += 1
                continue
            if r.status_code == 429:
                if not retried:  # one polite backoff per run, then give up until next run
                    retried = True
                    await asyncio.sleep(self.backoff_s)
                    continue
                per_query[label] = "429 rate-limited"
                break
            i += 1
            if r.status_code != 200:
                per_query[label] = f"http {r.status_code}"
                continue
            body = r.text.strip()
            if not body or body == "{}":  # GDELT's "no match" answer
                per_query[label] = 0
                continue
            try:
                payload = r.json()
            except ValueError as e:
                # GDELT answers query-syntax errors with a plain-text 200.
                per_query[label] = f"not json: {body[:80]}"
                if label == GDELT_QUERIES[0][0]:
                    raise SourceChanged(f"GDELT returned non-JSON: {body[:120]}") from e
                continue
            got = parse_gdelt(payload, label)
            per_query[label] = len(got)
            items += got
        ctx.notes["queries"] = per_query
        if not any(isinstance(v, int) for v in per_query.values()):
            raise RuntimeError(f"GDELT: no query succeeded: {per_query}")
        items = dedupe(items)
        ctx.notes["freshest"] = freshest(items)
        return db.upsert_feed_items(self.name, items) if items else 0


# --------------------------------------------------------------------------
# Google News RSS
# --------------------------------------------------------------------------

GNEWS = "https://news.google.com/rss/search"
# (query, hl, gl, ceid, lang, window)
GNEWS_QUERIES: tuple[tuple[str, str, str, str, str, str], ...] = (
    ('"El Niño" OR "El Nino"', "en-US", "US", "US:en", "en", "2d"),
    ("El Niño", "fr", "FR", "FR:fr", "fr", "2d"),
    ("เอลนีโญ", "th", "TH", "TH:th", "th", "3d"),
    ("El Niño", "es-419", "MX", "MX:es-419", "es", "2d"),
    ("El Nino", "id", "ID", "ID:id", "id", "2d"),
    ("El Nino", "vi", "VN", "VN:vi", "vi", "3d"),
    ("El Nino", "en-AU", "AU", "AU:en", "en", "2d"),
    ("El Niño", "pt-BR", "BR", "BR:pt-419", "pt", "2d"),
    ("El Nino Thailand", "en-US", "US", "US:en", "en", "7d"),
    ("เอลนีโญ ภัยแล้ง", "th", "TH", "TH:th", "th", "7d"),
    ("Koh Samui water shortage", "en-US", "US", "US:en", "en", "30d"),
    ("เกาะสมุย น้ำ", "th", "TH", "TH:th", "th", "14d"),
    ("Koh Samui flood", "en-US", "US", "US:en", "en", "30d"),
    ("Surat Thani storm", "en-US", "US", "US:en", "en", "30d"),
)


def parse_gnews(xml: bytes | str, lang: str, label: str) -> list[dict]:
    f = feedparser.parse(xml)
    if f.bozo and not f.entries:
        raise SourceChanged(f"Google News: unparseable RSS ({f.get('bozo_exception')})")
    if "rss" not in (f.version or "") and not f.entries:
        raise SourceChanged("Google News: not an RSS document")
    out = []
    for e in f.entries:
        title = clean_text(e.get("title"))
        src = e.get("source") or {}
        publisher = clean_text(src.get("title")) or None
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -len(publisher) - 3].rstrip()
        if not title:
            continue
        guid = e.get("id") or e.get("link")
        extra = []
        if "samui" in label.lower() or "สมุย" in label:
            extra.append("samui")
        out.append(build_item(
            ext_id=stable_id(guid), kind="news", title=title, url=e.get("link"),
            author=publisher, lang=lang, published_at=to_iso(e.get("published_parsed")),
            extra_tags=extra,
        ))
    return out


class GoogleNews(Collector):
    name = "google_news"
    freshness_basis = "feed"
    max_age_s = 2 * DAY
    title = "Google News -- El Nino in 8 languages + Thailand / Koh Samui"
    category = "news"
    provider = "Google News RSS"
    homepage = "https://news.google.com/"
    endpoint = GNEWS
    interval_s = 20 * 60
    description = ("Google News search RSS for El Nino in en-US, fr-FR, th-TH, es-419, id-ID, "
                   "vi-VN, en-AU, pt-BR and local queries (El Nino Thailand, drought, Koh Samui "
                   "water / flood, Surat Thani storm). Publisher = the RSS <source>.")

    gap_s: ClassVar[float] = 1.0

    async def collect(self, ctx: RunContext) -> int:
        items: list[dict] = []
        per_query: dict[str, int | str] = {}
        for i, (q, hl, gl, ceid, lang, window) in enumerate(GNEWS_QUERIES):
            if i:
                await asyncio.sleep(self.gap_s)
            label = f"{q} [{hl}]"
            try:
                r = await ctx.get(GNEWS, params={"q": f"{q} when:{window}", "hl": hl, "gl": gl,
                                                 "ceid": ceid})
            except httpx.HTTPError as e:
                per_query[label] = f"error: {e}"[:120]
                continue
            got = parse_gnews(r.content, lang, q)
            per_query[label] = len(got)
            items += got
        ctx.notes["queries"] = per_query
        if all(isinstance(v, str) for v in per_query.values()):
            raise RuntimeError(f"Google News: every query failed: {per_query}")
        items = dedupe(items)
        ctx.notes["freshest"] = freshest(items)
        return db.upsert_feed_items(self.name, items) if items else 0


# --------------------------------------------------------------------------
# Direct RSS (agencies, science, Thai / regional press)
# --------------------------------------------------------------------------

# name, url, lang, scope (all | enso | impact). Every URL here returned 200
# with items on 2026-09-24. Feeds that failed that check and were left out:
# BoM (403), WMO (404), ECMWF (404), Nation Thailand + Thai PBS World (no feed,
# HTML only), Samui Times (feed 404, sitemap stale since 2025), climate.gov ENSO
# RSS (last item 2025-06; handled by the official domain anyway), TMD (TLS error).
AGENCY_FEEDS: tuple[tuple[str, str, str, str], ...] = (
    ("NOAA", "https://www.noaa.gov/rss.xml", "en", "impact"),
    ("NASA Earth Observatory", "https://science.nasa.gov/feed/?science_org=19791%2C22453", "en",
     "impact"),
    ("Copernicus C3S", "https://climate.copernicus.eu/rss.xml", "en", "impact"),
    ("Carbon Brief", "https://www.carbonbrief.org/feed/", "en", "enso"),
    ("Inside Climate News", "https://insideclimatenews.org/feed/", "en", "enso"),
    ("Yale Environment 360", "https://e360.yale.edu/feed.xml", "en", "enso"),
    ("Guardian Environment", "https://www.theguardian.com/environment/rss", "en", "enso"),
    ("BBC Science & Environment", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
     "en", "enso"),
    ("Mongabay", "https://news.mongabay.com/feed/", "en", "enso"),
    ("Phys.org Earth", "https://phys.org/rss-feed/earth-news/", "en", "enso"),
    ("ScienceDaily Climate", "https://www.sciencedaily.com/rss/earth_climate/climate.xml", "en",
     "enso"),
    ("Severe Weather Europe", "https://www.severe-weather.eu/feed/", "en", "enso"),
    ("ReliefWeb", "https://reliefweb.int/updates/rss.xml", "en", "enso"),
)
THAI_FEEDS: tuple[tuple[str, str, str, str], ...] = (
    ("The Thaiger -- Koh Samui", "https://thethaiger.com/tag/koh-samui/feed", "en", "impact"),
    ("The Thaiger -- National", "https://thethaiger.com/news/national/feed", "en", "impact"),
    ("Bangkok Post -- Thailand", "https://www.bangkokpost.com/rss/data/thailand.xml", "en",
     "impact"),
    ("Bangkok Post -- Top stories", "https://www.bangkokpost.com/rss/data/topstories.xml", "en",
     "impact"),
    ("Khaosod English", "https://www.khaosodenglish.com/feed/", "en", "impact"),
    ("Thai Examiner", "https://www.thaiexaminer.com/feed/", "en", "impact"),
    ("Thairath", "https://www.thairath.co.th/rss/news", "th", "impact"),
    ("Matichon", "https://www.matichon.co.th/feed", "th", "impact"),
    ("Khaosod", "https://www.khaosod.co.th/feed", "th", "impact"),
    ("CNA Asia", "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511",
     "en", "impact"),
    ("SCMP Asia", "https://www.scmp.com/rss/3/feed", "en", "impact"),
    ("VnExpress International", "https://e.vnexpress.net/rss/news.rss", "en", "impact"),
)


# Thai domestic outlets: every item is about Thailand even when the text does
# not name the country (Thai-language headlines name the province).
THAI_DOMESTIC = {"The Thaiger -- Koh Samui", "The Thaiger -- National", "Bangkok Post -- Thailand",
                 "Khaosod English", "Thai Examiner", "Thairath", "Matichon", "Khaosod"}


def parse_feed(xml: bytes | str, feed_name: str, lang: str, scope: str) -> tuple[int, list[dict]]:
    """Returns (entries_in_feed, relevant_items)."""
    f = feedparser.parse(xml)
    if not f.entries:
        if f.bozo:
            raise SourceChanged(f"{feed_name}: unparseable feed ({f.get('bozo_exception')})")
        return 0, []
    out = []
    for e in f.entries:
        title = clean_text(e.get("title"))
        summary = clean_text(e.get("summary"), 600)
        if not title or not is_relevant(f"{title} {summary}", scope):
            continue
        link = e.get("link")
        out.append(build_item(
            ext_id=stable_id(e.get("id") or link or title), kind="news", title=title, url=link,
            author=feed_name, lang=lang,
            published_at=to_iso(e.get("published_parsed") or e.get("updated_parsed")),
            summary=summary, image=_image_of(e),
            extra_tags=["thailand"] if feed_name in THAI_DOMESTIC else None,
        ))
    return len(f.entries), out


class _FeedSet(Collector):
    feeds: ClassVar[tuple[tuple[str, str, str, str], ...]] = ()

    async def _one(self, ctx: RunContext, name: str, url: str, lang: str, scope: str):
        r = await ctx.client.get(url, headers={"User-Agent": settings.user_agent})
        if r.status_code != 200:
            return name, f"http {r.status_code}", []
        n, items = parse_feed(r.content, name, lang, scope)
        if n == 0:
            return name, "no entries", []
        return name, f"{len(items)}/{n}", items

    async def collect(self, ctx: RunContext) -> int:
        sem = asyncio.Semaphore(4)

        async def guarded(f):
            async with sem:
                try:
                    return await self._one(ctx, *f)
                except (httpx.HTTPError, SourceChanged) as e:
                    return f[0], f"error: {type(e).__name__}: {e}"[:160], []

        results = await asyncio.gather(*(guarded(f) for f in self.feeds))
        items: list[dict] = []
        ok = 0
        for _name, _state, got in results:
            items += got
        ctx.notes["feeds"] = {name: state for name, state, _ in results}
        ok = sum(1 for _n, s, _ in results if "/" in s)
        ctx.last_status = 200 if ok else ctx.last_status
        if ok == 0:
            raise RuntimeError(f"all {len(self.feeds)} feeds failed: {ctx.notes['feeds']}")
        items = dedupe(items)
        ctx.notes["freshest"] = freshest(items)
        return db.upsert_feed_items(self.name, items) if items else 0


class AgencyScienceRss(_FeedSet):
    name = "news_science_rss"
    freshness_basis = "feed"
    max_age_s = 7 * DAY  # filtered to ENSO mentions: days without one are normal
    title = "Agency & climate-science RSS (NOAA, NASA, Copernicus, Carbon Brief, ...)"
    category = "news"
    provider = "Publisher RSS feeds"
    homepage = "https://www.carbonbrief.org/"
    endpoint = "https://www.noaa.gov/rss.xml"
    interval_s = 30 * 60
    description = ("Direct RSS of NOAA, NASA Earth Observatory, Copernicus C3S, Carbon Brief, "
                   "Inside Climate News, Yale e360, Guardian Environment, BBC, Mongabay, Phys.org, "
                   "ScienceDaily, Severe Weather Europe, ReliefWeb. General feeds are filtered to "
                   "items that mention El Nino / ENSO (agency feeds: ENSO or impacts).")
    feeds = AGENCY_FEEDS


class ThaiRegionalRss(_FeedSet):
    name = "news_thailand_rss"
    freshness_basis = "feed"
    max_age_s = 2 * DAY
    title = "Thai & regional press RSS (Thaiger Koh Samui, Bangkok Post, Thairath, ...)"
    category = "news"
    provider = "Publisher RSS feeds"
    homepage = "https://thethaiger.com/tag/koh-samui"
    endpoint = "https://thethaiger.com/tag/koh-samui/feed"
    interval_s = 15 * 60
    description = ("Thai and Southeast Asian press (English + Thai): The Thaiger (Koh Samui tag, "
                   "national), Bangkok Post, Khaosod English, Thai Examiner, Thairath, Matichon, "
                   "Khaosod, CNA Asia, SCMP Asia, VnExpress. Filtered to El Nino and impact items "
                   "(drought, flood, storm, heat, haze, bleaching, water, weather warnings).")
    feeds = THAI_FEEDS


COLLECTORS = [GdeltNews, GoogleNews, AgencyScienceRss, ThaiRegionalRss]
