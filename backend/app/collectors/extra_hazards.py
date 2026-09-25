"""Extra hazard sources for Koh Samui (gap fill, 2026-09-24).

- jma_typhoons      JMA RSMC Tokyo: every active West Pacific tropical cyclone, track +
                    5-day forecast (events, category cyclone). Gulf of Thailand storms come
                    from the West Pacific / South China Sea.
- jtwc_warnings     US Joint Typhoon Warning Center: NW Pacific + North Indian Ocean warnings
                    (events) and the Significant Tropical Weather Advisory (official feed).
- usgs_quakes_region  USGS M4.5+ earthquakes of the past week within 3000 km (events).
- ptwc_tsunami      NOAA Pacific Tsunami Warning Center latest message (official feed).
- reliefweb_reports ReliefWeb reports on El Nino / Thailand disasters (needs an approved
                    appname, env RELIEFWEB_APPNAME).

Severity for storms is by distance to the home point (settings.home_*), so the map
shows what matters here: red = the analysis or forecast track comes within 300 km,
orange = within home_radius_km (800 km default), green = further away.
"""

from __future__ import annotations

import math
import os
import re
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import feedparser

from .. import db
from ..config import settings
from .base import DAY, HOUR, Collector, NeedsConfig, RunContext, SourceChanged

NEAR_KM = 300.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def home_km(lat: float, lon: float) -> float:
    return round(haversine_km(settings.home_lat, settings.home_lon, lat, lon), 1)


def track_severity(min_km: float | None) -> str:
    if min_km is None:
        return "info"
    if min_km <= NEAR_KM:
        return "red"
    if min_km <= settings.home_radius_km:
        return "orange"
    return "green"


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat()


# ------------------------------------------------------------------ JMA typhoons

JMA_TC_BASE = "https://www.jma.go.jp/bosai/typhoon/data/"
JMA_TARGET_URL = JMA_TC_BASE + "targetTc.json"
JMA_TC_PAGE = "https://www.jma.go.jp/bosai/map.html#contents=typhoon&lang=en"
JMA_CLASS = {
    "TD": "Tropical Depression", "TS": "Tropical Storm", "STS": "Severe Tropical Storm",
    "TY": "Typhoon", "LOW": "Extratropical Low", "L": "Low",
}


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _wind_kt(part: dict, which: str) -> int | None:
    try:
        return int((part.get("maximumWind") or {}).get(which, {}).get("kt"))
    except (TypeError, ValueError):
        return None


def parse_jma_tc(tc_id: str, forecast: list, specs: list) -> dict:
    if not isinstance(forecast, list) or not isinstance(specs, list) or not forecast or not specs:
        raise SourceChanged(f"JMA {tc_id}: forecast/specifications are not non-empty lists")
    title = specs[0] if specs[0].get("part") == "title" else None
    if title is None or "issue" not in title:
        raise SourceChanged(f"JMA {tc_id}: no title part")
    parts = [p for p in specs[1:] if isinstance(p.get("advancedHours"), int)]
    fparts = {p.get("advancedHours"): p for p in forecast[1:] if isinstance(p, dict)}
    analysis = next((p for p in parts if p["advancedHours"] == 0), None)
    if analysis is None or "position" not in analysis:
        raise SourceChanged(f"JMA {tc_id}: no analysis position")
    lat, lon = analysis["position"]["deg"]
    points = []
    for p in parts:
        pos = (p.get("position") or {}).get("deg")
        if not pos:
            continue
        vt = (fparts.get(p["advancedHours"]) or {}).get("validtime", {}).get("UTC")
        vt = _iso(datetime.fromisoformat(vt)) if vt else None
        points.append({
            "hours": p["advancedHours"], "valid_at": vt, "lat": pos[0], "lon": pos[1],
            "class": (p.get("category") or {}).get("en"),
            "wind_kt": _wind_kt(p, "sustained"), "gust_kt": _wind_kt(p, "gust"),
            "pressure_hpa": _int(p.get("pressure")), "distance_km": home_km(pos[0], pos[1]),
        })
    track = (fparts.get(0) or {}).get("track") or {}
    past = [pt for key in ("preTyphoon", "typhoon") for pt in track.get(key) or []]
    line = [[pt[1], pt[0]] for pt in past] + [[p["lon"], p["lat"]] for p in points]
    closest = min(points, key=lambda p: p["distance_km"])
    cls = (analysis.get("category") or {}).get("en") or (title.get("category") or {}).get("en")
    name = (title.get("name") or {}).get("en") or tc_id
    number = title.get("typhoonNumber")
    label = JMA_CLASS.get(cls or "", cls or "Tropical cyclone")
    return {
        "ext_id": tc_id, "category": "cyclone",
        "title": f"{label} {name} (JMA {number})",
        "url": JMA_TC_PAGE, "severity": track_severity(closest["distance_km"]),
        "lat": lat, "lon": lon,
        "started_at": None, "updated_at": _iso(datetime.fromisoformat(title["issue"]["UTC"])),
        "geometry": {"type": "LineString", "coordinates": line} if len(line) > 1 else
        {"type": "Point", "coordinates": [lon, lat]},
        "payload": {
            "agency": "JMA RSMC Tokyo", "name": name, "number": number, "class": cls,
            "class_label": label, "wind_kt": _wind_kt(analysis, "sustained"),
            "gust_kt": _wind_kt(analysis, "gust"), "pressure_hpa": _int(analysis.get("pressure")),
            "distance_km": home_km(lat, lon), "closest_km": closest["distance_km"],
            "closest_at": closest["valid_at"], "closest_hours": closest["hours"],
            "forecast": points, "wind_basis": "10-minute sustained (JMA)",
        },
    }


class JmaTyphoons(Collector):
    name = "jma_typhoons"
    title = "JMA RSMC Tokyo -- West Pacific tropical cyclones (track + 5-day forecast)"
    category = "disaster"
    provider = "Japan Meteorological Agency (RSMC Tokyo)"
    homepage = JMA_TC_PAGE
    endpoint = JMA_TARGET_URL
    interval_s = 30 * 60
    freshness_basis = "run"  # publishes only while a storm exists
    max_age_s = 3 * HOUR
    description = ("Official WMO regional centre for West Pacific / South China Sea typhoons. "
                   "Every active storm with its past track, 5-day forecast positions, winds, "
                   "and its closest forecast approach to Koh Samui. Severity: red = within "
                   "300 km, orange = within the watch radius, green = further.")

    async def collect(self, ctx: RunContext) -> int:
        targets = (await ctx.get(JMA_TARGET_URL)).json()
        if not isinstance(targets, list):
            raise SourceChanged("JMA targetTc is not a list")
        events = []
        for t in targets:
            tc = t.get("tropicalCyclone")
            if not tc or not re.fullmatch(r"TC\d{4}", tc):
                raise SourceChanged(f"JMA targetTc: odd id {tc!r}")
            fc = (await ctx.get(f"{JMA_TC_BASE}{tc}/forecast.json")).json()
            sp = (await ctx.get(f"{JMA_TC_BASE}{tc}/specifications.json")).json()
            events.append(parse_jma_tc(tc, fc, sp))
        ctx.notes["storms"] = [f"{e['title']} {e['payload']['closest_km']} km" for e in events]
        # targetTc is the authoritative list of active storms: an empty list is a quiet ocean
        db.replace_events(self.name, events, allow_empty=True)
        return len(events)


# ------------------------------------------------------------------ JTWC

JTWC_RSS = "https://www.metoc.navy.mil/jtwc/rss/jtwc.rss"
JTWC_PAGE = "https://www.metoc.navy.mil/jtwc/jtwc.html"
JTWC_BASINS = ("NWPAC-NIO-WARNINGS",)
_WARN_LINK = re.compile(r"https://www\.metoc\.navy\.mil/jtwc/products/((?:wp|io|sh)\d{4})web\.txt")
_ADV_LINK = re.compile(r"https://www\.metoc\.navy\.mil/jtwc/products/(abp[a-z]+)web\.txt")
_SUBJ = re.compile(r"SUBJ/(.+?) WARNING NR (\d+)", re.DOTALL)
_POS = re.compile(r"(\d{6})Z --- (?:NEAR )?(\d+\.\d)([NS]) (\d+\.\d)([EW])")
_WIND = re.compile(r"MAX SUSTAINED WINDS - (\d+) KT, GUSTS (\d+) KT")


def _dtg(dtg: str, ref: datetime) -> datetime:
    """DDHHMM (UTC) -> the datetime closest to `ref` among the previous, current and next
    month. A warning spans up to 5 days: its forecast positions cross a month change
    forwards (issued 29 Sep, valid 4 Oct) and its analysis crosses one backwards (issued
    1 Oct, position of 30 Sep), so the day number alone does not name the month."""
    day, hh, mm = int(dtg[:2]), int(dtg[2:4]), int(dtg[4:6])
    cands = []
    for step in (-1, 0, 1):
        y, m = ref.year, ref.month + step
        if m == 0:
            y, m = y - 1, 12
        elif m == 13:
            y, m = y + 1, 1
        try:
            cands.append(datetime(y, m, day, hh, mm, tzinfo=UTC))
        except ValueError:
            continue  # e.g. day 31 in a 30-day month
    if not cands:
        raise SourceChanged(f"JTWC: impossible date-time group {dtg!r}")
    return min(cands, key=lambda t: abs((t - ref).total_seconds()))


def _latlon(g: tuple) -> tuple[float, float]:
    """(lat, N|S, lon, E|W) -> signed degrees."""
    lat = float(g[0]) * (1 if g[1] == "N" else -1)
    lon = float(g[2]) * (1 if g[3] == "E" else -1)
    return lat, lon


def parse_jtwc_warning(text: str, code: str, ref: datetime) -> dict:
    subj = _SUBJ.search(text)
    blocks = re.split(r"\n\s*---\s*\n", text)
    if not subj or "WARNING POSITION" not in text:
        raise SourceChanged(f"JTWC {code}: no SUBJ/WARNING POSITION")
    name = re.sub(r"\s+", " ", subj.group(1)).strip().title()
    points = []
    for b in blocks:
        for pm in _POS.finditer(b):
            lat, lon = _latlon(pm.groups()[1:])
            w = _WIND.search(b[pm.end():])
            t = _dtg(pm.group(1), ref)
            if any(p["valid_at"] == _iso(t) for p in points):
                continue
            points.append({"valid_at": _iso(t), "lat": lat, "lon": lon,
                           "wind_kt": int(w.group(1)) if w else None,
                           "gust_kt": int(w.group(2)) if w else None,
                           "distance_km": home_km(lat, lon)})
    if not points:
        raise SourceChanged(f"JTWC {code}: no positions")
    now = points[0]
    closest = min(points, key=lambda p: p["distance_km"])
    final = "FINAL WARNING" in text.upper()
    return {
        "ext_id": code, "category": "cyclone",
        "title": f"{name} (JTWC warning {int(subj.group(2))}{', final' if final else ''})",
        "url": f"https://www.metoc.navy.mil/jtwc/products/{code}web.txt",
        "severity": "green" if final else track_severity(closest["distance_km"]),
        "lat": now["lat"], "lon": now["lon"], "started_at": None, "updated_at": now["valid_at"],
        "geometry": {"type": "LineString", "coordinates": [[p["lon"], p["lat"]] for p in points]}
        if len(points) > 1 else {"type": "Point", "coordinates": [now["lon"], now["lat"]]},
        "payload": {
            "agency": "JTWC", "warning_nr": int(subj.group(2)), "final": final,
            "wind_kt": now["wind_kt"], "gust_kt": now["gust_kt"],
            "distance_km": now["distance_km"], "closest_km": closest["distance_km"],
            "closest_at": closest["valid_at"], "forecast": points,
            "wind_basis": "1-minute sustained (JTWC)",
            "graphic": f"https://www.metoc.navy.mil/jtwc/products/{code}.gif",
        },
    }


def parse_jtwc_rss(xml: bytes) -> tuple[datetime, list[str], list[str], bool]:
    """-> (pubDate, warning codes in our basins, advisory names, basin item present)."""
    f = feedparser.parse(xml)
    if not f.entries or "JTWC" not in (f.feed.get("title") or ""):
        raise SourceChanged("JTWC RSS: no entries / unexpected title")
    ref = datetime.now(UTC)
    if f.feed.get("updated"):
        try:
            ref = parsedate_to_datetime(f.feed["updated"]).astimezone(UTC)
        except (TypeError, ValueError):
            pass
    codes: list[str] = []
    advisories: list[str] = []
    found = False
    for e in f.entries:
        body = " ".join(c.get("value", "") for c in e.get("content", [])) or e.get("summary", "")
        if e.get("id") in JTWC_BASINS:
            found = True
            codes += [c for c in _WARN_LINK.findall(body) if c not in codes]
        advisories += [a for a in _ADV_LINK.findall(body) if a not in advisories]
    return ref, codes, advisories, found


def parse_jtwc_advisory(text: str, name: str, ref: datetime) -> dict | None:
    head = re.search(r"SUBJ/(.+?)//", text, re.DOTALL)
    if not head:
        return None
    subj = re.sub(r"\s+", " ", head.group(1)).strip()
    dtg = re.search(r"^[A-Z]{4}\d\d PGTW (\d{6})", text, re.MULTILINE)
    pub = _iso(_dtg(dtg.group(1), ref)) if dtg else None
    body = text[head.end():].replace("NNNN", "").strip()
    malay = "MALAY PENINSULA" in text
    return {
        "ext_id": f"{name}-{dtg.group(1) if dtg else pub}", "kind": "official",
        "title": f"JTWC {subj.title()}", "summary": re.sub(r"\s+", " ", body)[:1000],
        "url": f"https://www.metoc.navy.mil/jtwc/products/{name}web.txt", "author": "JTWC",
        "lang": "en", "published_at": pub,
        "tags": ["storm"] + (["thailand"] if malay else []),
    }


class JtwcWarnings(Collector):
    name = "jtwc_warnings"
    title = "JTWC -- tropical cyclone warnings (NW Pacific, North Indian Ocean)"
    category = "disaster"
    provider = "US Joint Typhoon Warning Center"
    homepage = JTWC_PAGE
    endpoint = JTWC_RSS
    interval_s = 30 * 60
    freshness_basis = "run"
    max_age_s = 3 * HOUR
    description = ("JTWC warnings for every tropical cyclone in the NW Pacific and North Indian "
                   "Ocean (current position, winds, 5-day forecast track, closest approach to "
                   "Koh Samui) plus the daily Significant Tropical Weather Advisory, which also "
                   "lists developing disturbances west to the Malay Peninsula.")

    async def collect(self, ctx: RunContext) -> int:
        ref, codes, advisories, found = parse_jtwc_rss((await ctx.get(JTWC_RSS)).content)
        if not found:
            raise SourceChanged("JTWC RSS: NW Pacific / North IO item missing")
        events = []
        for code in codes:
            txt = (await ctx.get(f"https://www.metoc.navy.mil/jtwc/products/{code}web.txt")).text
            events.append(parse_jtwc_warning(txt, code, ref))
        items = []
        for adv in advisories:
            if not adv.startswith(("abpw", "abio")):
                continue
            r = await ctx.client.get(f"https://www.metoc.navy.mil/jtwc/products/{adv}web.txt")
            if r.status_code == 200:
                it = parse_jtwc_advisory(r.text, adv, ref)
                if it:
                    items.append(it)
        db.replace_events(self.name, events, allow_empty=True)
        if items:
            db.upsert_feed_items(self.name, items)
        ctx.notes.update(warnings=codes, advisories=[i["ext_id"] for i in items])
        return len(events) + len(items)


# ------------------------------------------------------------------ USGS earthquakes

USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"
QUAKE_RADIUS_KM = 3000.0


def parse_usgs(payload: dict, radius_km: float = QUAKE_RADIUS_KM) -> list[dict]:
    feats = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(feats, list) or (payload.get("metadata") or {}).get("status") != 200:
        raise SourceChanged("USGS: no features / status != 200")
    out = []
    for f in feats:
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        c = g.get("coordinates") or []
        if len(c) < 2 or p.get("mag") is None:
            continue
        lon, lat = float(c[0]), float(c[1])
        d = home_km(lat, lon)
        if d > radius_km:
            continue
        mag = float(p["mag"])
        tsunami = bool(p.get("tsunami"))
        sev = "red" if mag >= 7 or tsunami else "orange" if mag >= 6 else "green"
        out.append({
            "ext_id": f.get("id") or p.get("code"), "category": "earthquake",
            "title": p.get("title") or f"M {mag}", "url": p.get("url"), "severity": sev,
            "lat": lat, "lon": lon,
            "started_at": _iso(datetime.fromtimestamp(p["time"] / 1000, UTC)),
            "updated_at": _iso(datetime.fromtimestamp((p.get("updated") or p["time"]) / 1000,
                                                      UTC)),
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "payload": {"mag": mag, "mag_type": p.get("magType"), "depth_km": c[2] if len(c) > 2
                        else None, "place": p.get("place"), "tsunami_flag": tsunami,
                        "pager_alert": p.get("alert"), "distance_km": d},
        })
    return out


class UsgsQuakesRegion(Collector):
    name = "usgs_quakes_region"
    title = "USGS -- M4.5+ earthquakes within 3000 km (past 7 days)"
    category = "disaster"
    provider = "USGS Earthquake Hazards Program"
    homepage = "https://earthquake.usgs.gov/earthquakes/map/"
    endpoint = USGS_URL
    interval_s = 30 * 60
    freshness_basis = "run"
    max_age_s = 3 * HOUR
    description = ("Magnitude 4.5+ earthquakes of the last week within 3000 km of Koh Samui "
                   "(Sumatra-Andaman, Myanmar, Philippines, Indonesia). Not an El Nino effect: "
                   "shown so that a tsunami-capable quake in the region is never missed. "
                   "Severity: red = M7+ or tsunami flag, orange = M6+, green = smaller.")

    async def collect(self, ctx: RunContext) -> int:
        ev = parse_usgs((await ctx.get(USGS_URL)).json())
        db.replace_events(self.name, ev, allow_empty=True)  # rolling 7-day list
        ctx.notes["count"] = len(ev)
        return len(ev)


# ------------------------------------------------------------------ PTWC tsunami messages

PTWC_URL = "https://www.tsunami.gov/events/xml/PHEBAtom.xml"


def parse_ptwc(xml: bytes) -> list[dict]:
    f = feedparser.parse(xml)
    if "TSUNAMI" not in (f.feed.get("title") or "").upper() and not f.entries:
        raise SourceChanged("PTWC atom: not a tsunami feed")
    head = re.sub(r"\s+", " ", f.feed.get("title") or "").strip()
    out = []
    for e in f.entries:
        lat, lon = e.get("geo_lat"), e.get("geo_long")
        summary = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", e.get("summary", ""))).strip()
        cat = re.search(r"Category:\s*(\w+)", summary)
        link = next((ln.get("href") for ln in e.get("links", []) if ln.get("title") == "Bulletin"),
                    e.get("link"))
        out.append({
            "ext_id": e.get("id") or link, "kind": "official",
            "title": f"PTWC {head.title()} -- {(e.get('title') or '').strip().title()}",
            "summary": summary[:1000], "url": link, "author": "NOAA PTWC", "lang": "en",
            "published_at": _iso(datetime(*e.updated_parsed[:6], tzinfo=UTC))
            if e.get("updated_parsed") else None,
            "lat": float(lat) if lat else None, "lon": float(lon) if lon else None,
            "tags": ["tsunami", (cat.group(1).lower() if cat else "information")],
        })
    return out


class PtwcTsunami(Collector):
    name = "ptwc_tsunami"
    title = "NOAA PTWC -- latest tsunami message (Pacific)"
    category = "disaster"
    provider = "NOAA Pacific Tsunami Warning Center"
    homepage = "https://www.tsunami.gov/"
    endpoint = PTWC_URL
    interval_s = 15 * 60
    freshness_basis = "run"
    max_age_s = 2 * HOUR
    description = ("The latest message from the Pacific Tsunami Warning Center (information "
                   "statement, advisory, watch or warning). Most are 'information' messages that "
                   "say there is no threat. The Gulf of Thailand is sheltered; the Andaman coast "
                   "(Phuket, Krabi) is exposed to Indian Ocean tsunamis.")

    async def collect(self, ctx: RunContext) -> int:
        items = parse_ptwc((await ctx.get(PTWC_URL)).content)
        if items:
            db.upsert_feed_items(self.name, items)
        ctx.notes["latest"] = items[0]["title"] if items else None
        return len(items)


# ------------------------------------------------------------------ ReliefWeb (needs appname)

RELIEFWEB_URL = "https://api.reliefweb.int/v2/reports"
RELIEFWEB_ENV = "RELIEFWEB_APPNAME"


def reliefweb_appname() -> str | None:
    return getattr(settings, "reliefweb_appname", None) or os.environ.get(RELIEFWEB_ENV) or None


def parse_reliefweb(payload: dict) -> list[dict]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise SourceChanged("ReliefWeb: no data list")
    out = []
    for d in data:
        f = d.get("fields") or {}
        title = f.get("title")
        if not title:
            continue
        countries = [c.get("name") for c in f.get("country") or [] if c.get("name")]
        tags = ["enso"] if re.search(r"el ni[nñ]o", title, re.IGNORECASE) else []
        if "Thailand" in countries:
            tags.append("thailand")
        out.append({
            "ext_id": str(d.get("id")), "kind": "official", "title": title,
            "summary": (f.get("body") or "")[:1000] or None,
            "url": f.get("url_alias") or f.get("url") or d.get("href"),
            "author": ", ".join(s.get("name", "") for s in f.get("source") or [])[:200] or None,
            "lang": "en", "published_at": (f.get("date") or {}).get("created"), "tags": tags,
        })
    return out


class ReliefWebReports(Collector):
    name = "reliefweb_reports"
    title = "ReliefWeb -- humanitarian reports on El Nino and Thailand"
    category = "disaster"
    provider = "UN OCHA ReliefWeb"
    homepage = "https://reliefweb.int/"
    endpoint = RELIEFWEB_URL
    interval_s = 3 * HOUR
    freshness_basis = "feed"
    max_age_s = 7 * DAY
    needs = ("reliefweb_appname",)
    description = ("Situation reports, appeals and assessments from UN agencies and NGOs that "
                   "mention El Nino, or concern Thailand. The ReliefWeb API requires an approved "
                   "appname since 2025: request one (free) at "
                   "https://apidoc.reliefweb.int/parameters#appname and set RELIEFWEB_APPNAME.")

    def missing_config(self) -> list[str]:
        return [] if reliefweb_appname() else ["reliefweb_appname (env RELIEFWEB_APPNAME)"]

    async def collect(self, ctx: RunContext) -> int:
        app = reliefweb_appname()
        if not app:
            raise NeedsConfig("RELIEFWEB_APPNAME")
        since = (datetime.now(UTC) - timedelta(days=60)).strftime("%Y-%m-%dT00:00:00+00:00")
        body = {
            "query": {"value": '"El Nino" OR "El Niño" OR country.exact:"Thailand"'},
            "filter": {"field": "date.created", "value": {"from": since}},
            "fields": {"include": ["title", "url_alias", "date.created", "source.name",
                                   "country.name", "body"]},
            "sort": ["date.created:desc"], "limit": 50,
        }
        r = await ctx.client.post(RELIEFWEB_URL, params={"appname": app}, json=body)
        ctx.last_status = r.status_code
        if r.status_code == 403:
            raise NeedsConfig(f"ReliefWeb refused appname {app!r} (not approved)")
        r.raise_for_status()
        items = parse_reliefweb(r.json())
        return db.upsert_feed_items(self.name, items) if items else 0


COLLECTORS = [JmaTyphoons, JtwcWarnings, UsgsQuakesRegion, PtwcTsunami, ReliefWebReports]
