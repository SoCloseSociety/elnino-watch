"""Official agency bulletins: status snapshots + feed_items (kind=official).

- CPC ENSO Diagnostic Discussion -> status `cpc_alert` + one feed item per issue.
- IRI ENSO forecast -> status `iri_plume` (probabilities read from the matplotlib
  SVG the IRI page embeds; it is the only machine-readable copy they publish).
- JMA El Nino Outlook -> status `jma_outlook` + one feed item per issue.
- climate.gov ENSO blog RSS -> feed items.
- WMO El Nino/La Nina Updates (+ ENSO press releases/news) -> feed items.

BoM's climate driver update is not collected: www.bom.gov.au answers 403 to
non-browser clients and explicitly asks automated clients to stop. The BoM SOI
series comes from their anonymous FTP instead (see indices.BomSoi).
"""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin

import feedparser
from dateutil import parser as dateparser

from .. import db
from .base import DAY, Collector, RunContext, SourceChanged

BLOCK_TAGS = {"p", "br", "div", "tr", "td", "th", "li", "ul", "ol", "table", "h1", "h2",
              "h3", "h4", "h5", "h6", "pre", "section", "article", "header", "footer"}
_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{4})\b")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_lines(markup: str) -> list[str]:
    """Visible text of an HTML page, one entry per block, whitespace collapsed."""
    p = _TextExtractor()
    p.feed(markup)
    p.close()
    text = "".join(p.parts).replace("\xa0", " ")
    return [ln for ln in (re.sub(r"\s+", " ", x).strip() for x in text.split("\n")) if ln]


def _iso_date(s: str) -> str | None:
    m = _DATE_RE.search(s)
    if not m:
        return None
    return datetime.strptime(" ".join(m.groups()), "%d %B %Y").replace(tzinfo=UTC).date().isoformat()


def _place_tags(*texts: str) -> list[str]:
    blob = " ".join(t for t in texts if t).lower()
    tags = []
    if "samui" in blob:
        tags.append("samui")
    if "thailand" in blob or "thai " in blob:
        tags.append("thailand")
    return tags


def _excerpt(s: str, n: int = 600) -> str:
    return s if len(s) <= n else s[: n - 3].rsplit(" ", 1)[0] + "..."


# ------------------------------------------------------------------ CPC


def parse_cpc_discussion(markup: str, url: str) -> dict:
    lines = html_lines(markup)
    joined = "\n".join(lines)
    m = re.search(r"ENSO Alert System Status:\s*(.+)", joined)
    if not m:
        raise SourceChanged("CPC: 'ENSO Alert System Status:' not found")
    status = m.group(1).strip()
    syn = re.search(r"Synopsis:\s*(.+)", joined)
    if not syn:
        raise SourceChanged("CPC: 'Synopsis:' not found")
    issued = None
    for ln in lines[: lines.index(next(x for x in lines if x.startswith("ENSO Alert System")))]:
        if _DATE_RE.fullmatch(ln):
            issued = _iso_date(ln)
    if not issued:
        raise SourceChanged("CPC: issue date not found above the alert status")
    syn_idx = next(i for i, x in enumerate(lines) if x.startswith("Synopsis:"))
    body = next((x for x in lines[syn_idx + 1:] if len(x) > 200), "")
    nxt = re.search(r"next ENSO Diagnostics? Discussion is scheduled for ([^.]+)", joined, re.IGNORECASE)
    return {
        "status": status,
        "synopsis": syn.group(1).strip(),
        "issued": issued,
        "next_issue": _iso_date(nxt.group(1)) if nxt else None,
        "url": url,
        "text_excerpt": _excerpt(body),
    }


class CpcDiscussion(Collector):
    name = "cpc_discussion"
    freshness_basis = "feed"
    max_age_s = 40 * DAY  # monthly, 2nd Thursday
    title = "CPC ENSO Diagnostic Discussion"
    category = "official"
    provider = "NOAA CPC"
    homepage = ("https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/"
                "ensodisc.shtml")
    endpoint = homepage
    interval_s = 3 * 3600
    description = ("Monthly official NOAA ENSO status (Watch / Advisory / Final Advisory) and "
                   "synopsis, issued the 2nd Thursday. Status key: cpc_alert.")

    async def collect(self, ctx: RunContext) -> int:
        r = await ctx.get(self.endpoint)
        st = parse_cpc_discussion(r.text, self.endpoint)
        db.set_status("cpc_alert", st)
        return db.upsert_feed_items(self.name, [{
            "ext_id": st["issued"], "kind": "official", "lang": "en",
            "title": f"CPC ENSO Diagnostic Discussion {st['issued']}: {st['status']}",
            "summary": f"{st['synopsis']} {st['text_excerpt']}".strip(),
            "url": self.endpoint, "author": "NOAA Climate Prediction Center",
            "published_at": st["issued"], "tags": ["enso", "cpc", *_place_tags(st["synopsis"])],
        }])


# ------------------------------------------------------------------ IRI

_FIG3_RE = re.compile(r"https://ensoforecast\.iri\.columbia\.edu/figure3_plot/\d{4}/\d{1,2}")
_BAR_COLORS = {"#0000ff": "la_nina", "#aaaaaa": "neutral", "#ff0000": "el_nino"}


def _nums(s: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s)]


def parse_iri_figure3(svg: str) -> dict:
    """Read the bar chart back out of IRI's matplotlib SVG.

    Calibrates the y axis from its tick marks (labelled 0..100), maps bars to
    seasons by the nearest x tick, and to categories by fill colour (legend:
    blue = La Nina, grey = Neutral, red = El Nino)."""
    if "Probabilistic ENSO Forecast" not in svg:
        raise SourceChanged("IRI figure 3: title not found")
    title = re.search(r"<!-- ([^>]*Probabilistic ENSO Forecasts?) -->", svg)
    axes = svg.split('<g id="legend_1">')[0]
    xt = re.findall(r'<g id="xtick_\d+">.*?<use [^>]*x="([\d.]+)".*?<!-- (\w+) -->', axes, re.DOTALL)
    yt = re.findall(r'<g id="ytick_\d+">.*?<use [^>]*y="([\d.]+)".*?<!-- ([\d.]+) -->', axes,
                    re.DOTALL)
    if len(xt) < 3 or len(yt) < 2:
        raise SourceChanged("IRI figure 3: axis ticks not found")
    y_a, v_a = float(yt[0][0]), float(yt[0][1])
    y_b, v_b = float(yt[-1][0]), float(yt[-1][1])
    scale = (v_b - v_a) / (y_b - y_a)  # percent per SVG unit (negative: y grows downward)
    seasons = [(float(x), label) for x, label in xt]
    probs: dict[str, dict] = {label: {"season": label} for _, label in seasons}
    for m in re.finditer(r'<g id="patch_\d+">\s*<path d="([^"]*)"([^>]*)/>', axes):
        fill = re.search(r"fill:\s*(#[0-9a-f]{6})", m.group(2))
        if not fill or fill.group(1) not in _BAR_COLORS:
            continue
        pts = _nums(m.group(1))
        xs, ys = pts[0::2], pts[1::2]
        cx = (min(xs) + max(xs)) / 2
        label = min(seasons, key=lambda s: abs(s[0] - cx))[1]
        height = (min(ys) - max(ys)) * scale  # top edge minus baseline, in percent
        probs[label][_BAR_COLORS[fill.group(1)]] = round(height, 1) + 0.0  # + 0.0 turns -0.0 into 0.0
    out = []
    for _, label in seasons:
        p = probs[label]
        if not all(k in p for k in ("la_nina", "neutral", "el_nino")):
            raise SourceChanged(f"IRI figure 3: missing bars for {label}")
        total = p["la_nina"] + p["neutral"] + p["el_nino"]
        if abs(total - 100) > 2:
            raise SourceChanged(f"IRI figure 3: {label} probabilities sum to {total}")
        out.append(p)
    return {"title": title.group(1) if title else None, "probabilities": out}


def parse_iri_page(markup: str) -> dict:
    m = _FIG3_RE.search(markup)
    if not m:
        raise SourceChanged("IRI page: figure3_plot image not found")
    issued = re.search(r"Technical ENSO Update \[([A-Za-z]+ \d{1,2}, \d{4})\]", markup)
    summary = None
    lines = html_lines(markup)
    for i, ln in enumerate(lines):
        if ln.startswith("A monthly summary of the status of El Ni"):
            summary = next((x for x in lines[i + 1:i + 6] if len(x) > 100), None)
            break
    return {
        "figure_url": m.group(0),
        "issued": (datetime.strptime(issued.group(1), "%B %d, %Y").replace(tzinfo=UTC)
                   .date().isoformat() if issued else None),
        "summary": summary,
    }


class IriPlume(Collector):
    name = "iri_plume"
    freshness_basis = "feed"
    max_age_s = 40 * DAY  # monthly, around the 19th
    title = "IRI ENSO forecast probabilities"
    category = "official"
    provider = "IRI / Columbia University (CCSR)"
    homepage = "https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/"
    endpoint = homepage
    interval_s = 12 * 3600
    description = ("Model-based (22-model plume) probabilities of La Nina / Neutral / El Nino "
                   "for the next 9 overlapping seasons. Status key: iri_plume.")

    async def collect(self, ctx: RunContext) -> int:
        page = parse_iri_page((await ctx.get(self.endpoint)).text)
        fig = parse_iri_figure3((await ctx.get(page["figure_url"])).text)
        if not page["issued"]:
            raise SourceChanged("IRI page: 'Technical ENSO Update [date]' not found")
        st = {"issued": page["issued"], "url": self.endpoint, "figure_url": page["figure_url"],
              "title": fig["title"], "summary": page["summary"],
              "probabilities": fig["probabilities"]}
        db.set_status("iri_plume", st)
        first = fig["probabilities"][0]
        return db.upsert_feed_items(self.name, [{
            "ext_id": page["issued"], "kind": "official", "lang": "en",
            "title": (f"IRI ENSO forecast {page['issued']}: El Nino {first['el_nino']:.0f}% "
                      f"for {first['season']}"),
            "summary": page["summary"], "url": self.endpoint,
            "author": "IRI / Columbia University", "published_at": page["issued"],
            "tags": ["enso", "iri", "forecast"],
        }])


# ------------------------------------------------------------------ JMA


def parse_jma_outlook(markup: str, url: str) -> dict:
    text = " ".join(html_lines(markup))
    upd = re.search(r"Last Updated:\s*(\d{1,2} \w+ \d{4})", text)
    if not upd:
        raise SourceChanged("JMA: 'Last Updated:' not found")
    period = re.search(r"El Ni\S* Outlook \(\s*(.+?)\s*\)", text)
    nxt = re.search(r"Next update will be on\s*(\d{1,2} \w+ \d{4})\s*\)", text)
    head = re.search(r"Next update will be on[^)]*\)\s*(.+?)\s*\[El Ni", text)
    body = re.search(r"\[El Ni\S* / La Ni\S*\]\s*(.+?)\s*(?:\[|$)", text)
    if not head:
        raise SourceChanged("JMA: headline between the dates and '[El Nino / La Nina]' missing")
    return {"status": head.group(1), "issued": _iso_date(upd.group(1)),
            "period": period.group(1) if period else None,
            "next_issue": _iso_date(nxt.group(1)) if nxt else None, "url": url,
            "text_excerpt": _excerpt(body.group(1)) if body else ""}


class JmaOutlook(Collector):
    name = "jma_outlook"
    freshness_basis = "feed"
    max_age_s = 40 * DAY  # monthly, around the 10th
    title = "JMA El Nino Outlook"
    category = "official"
    provider = "Japan Meteorological Agency (Tokyo Climate Center)"
    homepage = "https://ds.data.jma.go.jp/tcc/tcc/products/elnino/"
    endpoint = "https://ds.data.jma.go.jp/tcc/tcc/products/elnino/outlook.html"
    interval_s = 6 * 3600
    description = ("Monthly JMA ENSO assessment and 6-month outlook (NINO.3 based). "
                   "Status key: jma_outlook.")

    async def collect(self, ctx: RunContext) -> int:
        r = await ctx.get(self.endpoint)
        st = parse_jma_outlook(r.text, self.endpoint)
        db.set_status("jma_outlook", st)
        return db.upsert_feed_items(self.name, [{
            "ext_id": st["issued"], "kind": "official", "lang": "en",
            "title": f"JMA El Nino Outlook {st['issued']}",
            "summary": f"{st['status']} {st['text_excerpt']}".strip(), "url": self.endpoint,
            "author": "Japan Meteorological Agency", "published_at": st["issued"],
            "tags": ["enso", "jma", *_place_tags(st["text_excerpt"])],
        }])


# ------------------------------------------------------------------ RSS / WMO


def parse_rss(text: str, default_author: str) -> list[dict]:
    feed = feedparser.parse(text)
    if feed.bozo and not feed.entries:
        raise SourceChanged(f"RSS did not parse: {feed.bozo_exception}")
    out = []
    for e in feed.entries:
        link = (e.get("link") or "").strip()
        title = html.unescape((e.get("title") or "").strip())
        if not link or not title:
            continue
        pub = None
        if e.get("published_parsed"):
            pub = datetime(*e.published_parsed[:6], tzinfo=UTC).isoformat()
        elif e.get("published"):
            try:
                dt = dateparser.parse(e.published)
            except (ValueError, OverflowError):
                dt = None  # one odd date must not drop the whole feed
            if dt is not None:
                # a naive date is UTC, not this Mac's local time zone
                pub = (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone(UTC).isoformat()
        summary = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ",
                                                            e.get("summary") or ""))).strip()
        out.append({
            "ext_id": (e.get("id") or link).strip(), "kind": "official", "lang": "en",
            "title": title, "summary": summary or None, "url": link,
            "author": (e.get("author") or default_author).strip(), "published_at": pub,
            "tags": ["enso", *_place_tags(title, summary)],
        })
    return out


class ClimateGovEnsoBlog(Collector):
    name = "climategov_enso_blog"
    freshness_basis = "feed"
    max_age_s = 45 * DAY  # monthly posts when alive (silent since 2025-06: shows stale)
    expected_stale = ("NOAA's ENSO blog RSS has published no post since 2025-06-12; the feed "
                      "still answers, so the source is kept and shown as stale on purpose")
    title = "climate.gov ENSO blog"
    category = "official"
    provider = "NOAA climate.gov"
    homepage = "https://www.climate.gov/news-features/department/enso-blog"
    endpoint = "https://www.climate.gov/feeds/news-features/enso.rss"
    interval_s = 3600
    description = ("NOAA's ENSO blog posts (explainers of each monthly update). Note: the "
                   "feed has not published a new post since June 2025.")

    async def collect(self, ctx: RunContext) -> int:
        r = await ctx.get(self.endpoint)
        rows = parse_rss(r.text, "NOAA climate.gov")
        if rows:
            newest = max((x["published_at"] or "") for x in rows)
            ctx.notes["newest_item"] = newest
        return db.upsert_feed_items(self.name, rows)


_WMO_CARD = re.compile(r'<a href="([^"]+)" class="group[^"]*"[^>]*>(.*?)</a>', re.DOTALL)


def parse_wmo_cards(markup: str, base: str) -> list[dict]:
    """WMO Drupal listing cards: <a class="group ..."> <span>date</span> <h2>title</h2>."""
    out = []
    for m in _WMO_CARD.finditer(markup):
        body = m.group(2)
        d = re.search(r'<span class="text-sm md:text-base">([^<]+)</span>', body)
        t = re.search(r"<h2[^>]*>(.*?)</h2>", body, re.DOTALL)
        kind = re.search(r"label-icon[^>]*></span>\s*([^<]+?)\s*<", body)
        if not t:
            continue
        title = html.unescape(re.sub(r"<[^>]+>", "", t.group(1))).strip()
        if not re.search(r"El Ni|La Ni|ENSO", title, re.IGNORECASE):
            continue
        slug = m.group(1).rstrip("/").rsplit("/", 1)[-1]
        out.append({
            "ext_id": slug, "kind": "official", "lang": "en", "title": title,
            "summary": None,
            "url": urljoin(base, m.group(1)), "author": "World Meteorological Organization",
            "published_at": _iso_date(d.group(1)) if d else None,
            "tags": ["enso", "wmo",
                     *([kind.group(1).strip().lower()] if kind else []), *_place_tags(title)],
        })
    return out


class WmoEnsoUpdates(Collector):
    name = "wmo_enso"
    freshness_basis = "feed"
    max_age_s = 120 * DAY  # quarterly Update + irregular press releases
    title = "WMO El Nino/La Nina Updates"
    category = "official"
    provider = "World Meteorological Organization"
    homepage = "https://wmo.int/publication-series/el-ninola-nina-updates"
    endpoint = homepage
    theme_url = "https://wmo.int/themes/el-nino-la-nina-phenomena"
    interval_s = 6 * 3600
    description = ("WMO's quarterly El Nino/La Nina Update, its press releases and ENSO news "
                   "(WMO publishes no RSS; parsed from the listing pages).")

    async def collect(self, ctx: RunContext) -> int:
        rows: dict[str, dict] = {}
        for url in (self.endpoint, self.theme_url):
            r = await ctx.get(url)
            for row in parse_wmo_cards(r.text, url):
                rows.setdefault(row["ext_id"], row)
        if not rows:
            raise SourceChanged("WMO: no El Nino/La Nina cards found on the listing pages")
        return db.upsert_feed_items(self.name, list(rows.values()))


COLLECTORS = [CpcDiscussion, IriPlume, JmaOutlook, ClimateGovEnsoBlog, WmoEnsoUpdates]
