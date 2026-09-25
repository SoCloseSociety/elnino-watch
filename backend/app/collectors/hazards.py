"""Hazards: geolocated events for the map + the El Nino impact signals of SE Asia.

All keyless, all verified live on 2026-09-24.

- gdacs              GDACS (EC JRC / UN OCHA) current alerts: cyclones, floods, droughts,
                     wildfires, volcanoes, earthquakes. EVENTS4APP is capped at the 100 most
                     recent current events (wildfires crowd it out), so floods / cyclones /
                     volcanoes and droughts are also read from the SEARCH API.
- eonet              NASA EONET v3 open events (storms with their track, wildfires, ...).
- firms_fires        NASA FIRMS VIIRS S-NPP active fires, last 24 h, SE Asia (incl. Indonesia),
                     Australia/NZ, South America. FIRMS publishes these regional files
                     KEYLESS, so no MAP_KEY is needed; detections are clustered on a 0.5 deg
                     grid for the map.
- tmd_warnings_en    Thai Meteorological Department warning bulletins, English edition
                     (the Thai RSS is already read by app.local `tmd_warnings`).
- asmc_haze_alerts   ASEAN Specialised Meteorological Centre transboundary haze alert
                     levels (southern ASEAN / Mekong).
- asmc_hotspots      ASMC daily VIIRS hotspot counts per ASEAN sub-region.
- thaiwater_dams_national  ThaiWater / RID: the 35 large reservoirs of Thailand + the national
                     total (the El Nino drought signal for Thai water supply).

Not collected:
- NOAA NWS api.weather.gov/alerts/active: US-only, ~130 Severe/Extreme alerts at any time
  (verified 200 on 2026-09-24), mostly marine/flood warnings with no ENSO or Koh Samui
  relevance; US landfalling cyclones already arrive through GDACS and EONET.
- data.tmd.go.th WeatherWarningNews: the documented demo key returns a 2022 item; real
  use needs a registered key. The www.tmd.go.th RSS "warning-news" stopped in 04/2025.
"""

from __future__ import annotations

import csv
import html
import io
import re
import ssl
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import httpx

from .. import db
from ..config import settings
from .base import DAY, HOUR, Collector, RunContext, SourceChanged


def _utc(s: str | None) -> str | None:
    """'2026-09-20T09:00:00' (UTC, naive) or '...Z' -> ISO with offset."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _text(markup: str) -> str:
    s = re.sub(r"<br\s*/?>|</p>|</strong>", "\n", markup, flags=re.IGNORECASE)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")
    lines = [re.sub(r"[ \t\r]+", " ", x).strip() for x in s.split("\n")]
    return "\n".join(x for x in lines if x)


# --------------------------------------------------------------------------- GDACS

GDACS_BASE = "https://www.gdacs.org/gdacsapi/api/events/geteventlist"
GDACS_APP_URL = f"{GDACS_BASE}/EVENTS4APP"
GDACS_SEARCH_URL = f"{GDACS_BASE}/SEARCH"
GDACS_CATEGORY = {"TC": "cyclone", "FL": "flood", "DR": "drought", "WF": "wildfire",
                  "VO": "volcano", "EQ": "earthquake", "TS": "other"}
GDACS_SEVERITY = {"green": "green", "orange": "orange", "red": "red"}


def parse_gdacs(payload: dict, current_only: bool = True) -> list[dict]:
    feats = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(feats, list):
        raise SourceChanged("GDACS: no 'features' list")
    out = []
    for f in feats:
        p = f.get("properties") or {}
        g = f.get("geometry") or {}
        et, eid = p.get("eventtype"), p.get("eventid")
        if not et or eid is None:
            continue
        if current_only and str(p.get("iscurrent")).lower() != "true":
            continue
        coords = g.get("coordinates") if g.get("type") == "Point" else None
        if not coords or len(coords) < 2:
            continue
        urls = p.get("url") or {}
        sev = p.get("severitydata") or {}
        out.append({
            "ext_id": f"{et}_{eid}",
            "category": GDACS_CATEGORY.get(et, "other"),
            "title": p.get("name") or p.get("description") or f"{et} {eid}",
            "url": urls.get("report"),
            "severity": GDACS_SEVERITY.get(str(p.get("alertlevel", "")).lower(), "info"),
            "lat": float(coords[1]), "lon": float(coords[0]),
            "started_at": _utc(p.get("fromdate")),
            "updated_at": _utc(p.get("datemodified")) or _utc(p.get("todate")),
            "geometry": {"type": "Point", "coordinates": [float(coords[0]), float(coords[1])]},
            "payload": {
                "eventtype": et, "eventid": eid, "episodeid": p.get("episodeid"),
                "alertlevel": p.get("alertlevel"), "alertscore": p.get("alertscore"),
                "episodealertlevel": p.get("episodealertlevel"),
                "country": p.get("country"), "iso3": p.get("iso3"),
                "affected_countries": [c.get("countryname") for c in
                                       p.get("affectedcountries") or [] if c.get("countryname")],
                "severity_text": sev.get("severitytext"), "severity_value": sev.get("severity"),
                "severity_unit": sev.get("severityunit"),
                "from": _utc(p.get("fromdate")), "to": _utc(p.get("todate")),
                "source": p.get("source"), "description": p.get("htmldescription"),
                "report_url": urls.get("report"), "details_url": urls.get("details"),
                # for cyclones this returns the track + forecast cone polygons (GeoJSON)
                "geometry_url": urls.get("geometry"),
                "icon": p.get("icon"),
            },
        })
    return out


class GdacsEvents(Collector):
    name = "gdacs"
    freshness_basis = "events"
    max_age_s = 1 * HOUR  # the global list changes every few minutes
    title = "GDACS -- current disaster alerts"
    category = "disaster"
    provider = "GDACS (EC Joint Research Centre / UN OCHA)"
    homepage = "https://www.gdacs.org/"
    endpoint = GDACS_APP_URL
    interval_s = 15 * 60
    description = ("Current cyclones, floods, droughts, wildfires, volcanoes and earthquakes, "
                   "with the GDACS alert level (green/orange/red) and a link to the report.")
    max_pages = 3

    async def collect(self, ctx: RunContext) -> int:
        events: dict[str, dict] = {}
        for e in parse_gdacs((await ctx.get(GDACS_APP_URL)).json()):
            events[e["ext_id"]] = e
        today = datetime.now(UTC).date()
        common = {"alertlevel": "Green;Orange;Red"}
        # EVENTS4APP stops at 100 events: page through the non-wildfire types too.
        for page in range(1, self.max_pages + 1):
            r = await ctx.get(GDACS_SEARCH_URL, params={
                **common, "eventlist": "TC;FL;VO",
                "fromdate": (today - timedelta(days=60)).isoformat(),
                "todate": today.isoformat(), "pagenumber": page})
            payload = r.json()
            cur = parse_gdacs(payload)
            for e in cur:
                events.setdefault(e["ext_id"], e)
            if not cur or len(payload.get("features") or []) < 100:
                break
        # droughts last months: their fromdate is long before any date window
        r = await ctx.get(GDACS_SEARCH_URL, params={**common, "eventlist": "DR"})
        for e in parse_gdacs(r.json()):
            events.setdefault(e["ext_id"], e)
        rows = list(events.values())
        return db.replace_events(self.name, rows)


# --------------------------------------------------------------------------- NASA EONET

EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
EONET_CATEGORY = {"wildfires": "wildfire", "volcanoes": "volcano", "floods": "flood",
                  "drought": "drought", "dustHaze": "haze", "tempExtremes": "heat",
                  "earthquakes": "earthquake", "landslides": "other", "snow": "other",
                  "waterColor": "other", "manmade": "other"}
EONET_SKIP = {"seaLakeIce"}  # icebergs: no ENSO / SE Asia relevance
_CYCLONE_RE = re.compile(r"typhoon|hurricane|cyclone|tropical storm|tropical depression", re.IGNORECASE)


def _point_of(geom: dict) -> tuple[float, float] | None:
    c = geom.get("coordinates")
    if geom.get("type") == "Point" and c and len(c) >= 2:
        return float(c[0]), float(c[1])
    if geom.get("type") == "Polygon" and c and c[0]:
        ring = c[0]
        return (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))
    return None


def parse_eonet(payload: dict) -> list[dict]:
    evs = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(evs, list):
        raise SourceChanged("EONET: no 'events' list")
    out = []
    for e in evs:
        cats = [c.get("id") for c in e.get("categories") or []]
        if not cats or cats[0] in EONET_SKIP:
            continue
        geoms = sorted((g for g in e.get("geometry") or [] if _point_of(g)),
                       key=lambda g: g.get("date") or "")
        if not geoms:
            continue
        last = geoms[-1]
        lon, lat = _point_of(last)
        cat = cats[0]
        category = EONET_CATEGORY.get(cat, "other")
        if cat == "severeStorms":
            category = "cyclone" if _CYCLONE_RE.search(e.get("title") or "") else "storm"
        pts = [list(_point_of(g)) for g in geoms]
        geometry = ({"type": "LineString", "coordinates": pts} if len(pts) > 1
                    else {"type": "Point", "coordinates": pts[0]})
        out.append({
            "ext_id": e["id"], "category": category, "title": e.get("title"),
            "url": ((e.get("sources") or [{}])[0].get("url")) or e.get("link"),
            "severity": "info", "lat": lat, "lon": lon,
            "started_at": _utc(geoms[0].get("date")), "updated_at": _utc(last.get("date")),
            "geometry": geometry,
            "payload": {
                "categories": cats, "eonet_link": e.get("link"),
                "sources": e.get("sources"), "magnitude": last.get("magnitudeValue"),
                "magnitude_unit": last.get("magnitudeUnit"), "points": len(pts),
            },
        })
    return out


class EonetEvents(Collector):
    name = "eonet"
    freshness_basis = "events"
    max_age_s = 3 * DAY  # curated, events are updated every few days
    title = "NASA EONET -- open natural events"
    category = "disaster"
    provider = "NASA Earth Observatory Natural Event Tracker (EONET v3)"
    homepage = "https://eonet.gsfc.nasa.gov/"
    endpoint = EONET_URL + "?status=open&days=60"
    interval_s = 15 * 60
    description = ("Open events from the last 60 days (storms with their tracks, "
                   "fires, volcanoes...). Icebergs are ignored.")

    async def collect(self, ctx: RunContext) -> int:
        r = await ctx.get(EONET_URL, params={"status": "open", "days": 60})
        return db.replace_events(self.name, parse_eonet(r.json()))


# --------------------------------------------------------------------------- NASA FIRMS

FIRMS_REGION_URL = ("https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/"
                    "csv/SUOMI_VIIRS_C2_{region}_24h.csv")
FIRMS_REGIONS = ("SouthEast_Asia", "Australia_NewZealand", "South_America")
FIRMS_GRID_DEG = 0.5
FIRMS_MIN_DETECTIONS = 3


def parse_firms_csv(text: str, region: str) -> list[dict]:
    """VIIRS 24 h CSV -> clusters on a 0.5 deg grid (>= 3 non-low-confidence detections)."""
    rdr = csv.DictReader(io.StringIO(text))
    need = {"latitude", "longitude", "confidence", "frp", "acq_date", "acq_time"}
    if not rdr.fieldnames or not need <= set(rdr.fieldnames):
        raise SourceChanged(f"FIRMS CSV columns changed: {rdr.fieldnames}")
    cells: dict[tuple[float, float], list[dict]] = defaultdict(list)
    for row in rdr:
        if (row.get("confidence") or "").lower() in ("low", "l"):
            continue
        try:
            lat, lon = float(row["latitude"]), float(row["longitude"])
            frp = float(row["frp"]) if row.get("frp") else 0.0
        except ValueError:
            continue
        key = (round(lat / FIRMS_GRID_DEG) * FIRMS_GRID_DEG,
               round(lon / FIRMS_GRID_DEG) * FIRMS_GRID_DEG)
        t = row["acq_time"].zfill(4)
        cells[key].append({"lat": lat, "lon": lon, "frp": frp,
                           "at": f"{row['acq_date']}T{t[:2]}:{t[2:]}:00+00:00"})
    out = []
    for (glat, glon), det in cells.items():
        if len(det) < FIRMS_MIN_DETECTIONS:
            continue
        n = len(det)
        lat = round(sum(d["lat"] for d in det) / n, 4)
        lon = round(sum(d["lon"] for d in det) / n, 4)
        out.append({
            "ext_id": f"{glat:.1f}_{glon:.1f}", "category": "wildfire",
            "title": f"Active fires: {n} VIIRS detections in 24 h",
            "url": f"https://firms.modaps.eosdis.nasa.gov/map/#d:24hrs;@{lon:.2f},{lat:.2f},9.00z",
            "severity": "red" if n >= 100 else "orange" if n >= 25 else "green",
            "lat": lat, "lon": lon,
            "started_at": min(d["at"] for d in det), "updated_at": max(d["at"] for d in det),
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "payload": {"detections": n, "frp_total_mw": round(sum(d["frp"] for d in det), 1),
                        "frp_max_mw": max(d["frp"] for d in det), "grid_deg": FIRMS_GRID_DEG,
                        "region": region, "sensor": "VIIRS S-NPP (375 m)"},
        })
    return out


class FirmsFires(Collector):
    name = "firms_fires"
    freshness_basis = "events"
    max_age_s = 18 * HOUR  # 24 h VIIRS file, 2 passes a day + ~3 h latency
    title = "NASA FIRMS -- active fires (VIIRS, 24 h)"
    category = "satellite"
    provider = "NASA FIRMS (LANCE, VIIRS S-NPP 375 m)"
    homepage = "https://firms.modaps.eosdis.nasa.gov/"
    endpoint = FIRMS_REGION_URL.format(region="SouthEast_Asia")
    interval_s = 3 * 3600
    description = ("Fire detections from the last 24 hours (Southeast Asia incl. "
                   "Indonesia, Australia, South America), grouped into 0.5 deg squares "
                   "(at least 3 detections, low confidence excluded). Green < 25, orange >= 25, "
                   "red >= 100 detections. Public regional files, no key.")

    async def collect(self, ctx: RunContext) -> int:
        cells: dict[str, dict] = {}
        counts = {}
        for region in FIRMS_REGIONS:
            r = await ctx.get(FIRMS_REGION_URL.format(region=region))
            clusters = parse_firms_csv(r.text, region)
            counts[region] = len(clusters)
            for c in clusters:  # the regional files overlap (Cape York is in both SE Asia
                cells.setdefault(c["ext_id"], c)  # and Australia): one event per cell
        ctx.notes = {"clusters": counts}
        return db.replace_events(self.name, list(cells.values()))


# --------------------------------------------------------------------------- TMD (English)

TMD_WARN_EN_URL = "https://www.tmd.go.th/en/warning-and-events/warning-storm"
TMD_BASE = "https://www.tmd.go.th"
_TMD_ITEM_RE = re.compile(
    r'link-list-title"><a href="(?P<href>[^"]+)">(?P<title>.*?)</a>.*?'
    r'link-list-description">\s*<a[^>]*>(?P<desc>.*?)</a>.*?'
    r'Date:</div>\s*<div>(?P<date>[^<]+)</div>', re.DOTALL)
_SAMUI_RE = re.compile(r"samui|surat thani", re.IGNORECASE)


def parse_tmd_warnings_en(markup: str) -> list[dict]:
    out = []
    for m in _TMD_ITEM_RE.finditer(markup):
        # the live page has stray leading ": " on some titles
        title = re.sub(r"\s+", " ", html.unescape(m["title"])).strip().lstrip(": ").strip()
        desc = re.sub(r"\s+", " ", html.unescape(m["desc"])).strip()
        try:
            pub = (datetime.strptime(m["date"].strip(), "%d %B %Y")
                   .replace(tzinfo=UTC).date().isoformat())
        except ValueError:
            pub = None
        num = re.search(r"\((\d+/\d{4})\)", title)
        out.append({
            "ext_id": num.group(1) if num else m["href"].rsplit("/", 1)[-1],
            "kind": "official", "title": title, "summary": desc,
            "url": TMD_BASE + m["href"] if m["href"].startswith("/") else m["href"],
            "author": "Thai Meteorological Department", "lang": "en", "published_at": pub,
            "tags": ["thailand", "tmd"] + (["samui"] if _SAMUI_RE.search(title + desc) else []),
        })
    if not out:
        raise SourceChanged("TMD warning page: no bulletin found (markup changed?)")
    return out


def _tmd_verify() -> ssl.SSLContext | bool:
    """www.tmd.go.th omits its intermediate certificate; app.local ships it and builds a
    strict context that includes it. Fall back to default verification without it."""
    try:
        from ..local.collectors import tmd_ssl_context
    except ImportError:
        return True
    return tmd_ssl_context()


class TmdWarningsEn(Collector):
    name = "tmd_warnings_en"
    freshness_basis = "run"
    max_age_s = 3 * HOUR  # bulletins only exist when there is weather to warn about
    title = "TMD -- weather warnings (English edition)"
    category = "official"
    provider = "Thai Meteorological Department"
    homepage = TMD_WARN_EN_URL
    endpoint = TMD_WARN_EN_URL
    interval_s = 3600
    description = ("The last 10 TMD warning bulletins (heavy rain, storms, "
                   "waves) in English, with a link to the full text.")

    async def collect(self, ctx: RunContext) -> int:
        async with httpx.AsyncClient(verify=_tmd_verify(), timeout=60.0, follow_redirects=True,
                                     headers={"User-Agent": settings.user_agent}) as client:
            r = await client.get(TMD_WARN_EN_URL)
        ctx.last_status = r.status_code
        r.raise_for_status()
        return db.upsert_feed_items(self.name, parse_tmd_warnings_en(r.text))


# --------------------------------------------------------------------------- ASMC haze

ASMC_ALERTS_URL = "https://asmc.asean.org/asmc-alerts/"
ASMC_HOTSPOT_URL = ("https://asmc.asean.org/wp-content/themes/asmctheme/page-functions/"
                    "functions-ajax-haze-daily-hotspot-count-new.php")
ASMC_REGION_GROUPS = (("Thailand", "Myanmar", "Cambodia", "Vietnam", "Lao_PDR"),
                      ("Philippines", "P_Malaysia", "SabahSarawak", "Sumatra", "Kalimantan"))
_ASMC_ROW_RE = re.compile(
    r'<tr class="(?P<year>\d{4}) alert(?P<lvl>\d)\s*">\s*<td>(?P<date>[^<]+)</td>\s*'
    r'<td[^>]*>(?P<label>[^<]*)</td>\s*<td>(?P<body>.*?)</td>\s*</tr>', re.DOTALL)


def _asmc_subregion(text: str) -> str:
    t = text.lower()
    if "mekong" in t:
        return "mekong"
    if "southern asean" in t:
        return "southern"
    return "other"


def parse_asmc_alerts(markup: str) -> list[dict]:
    out = []
    for m in _ASMC_ROW_RE.finditer(markup):
        body = _text(m["body"])
        head = re.search(r"<strong>(.*?)</strong>", m["body"], re.DOTALL)
        title = _text(head.group(1)) if head else body.split("\n", 1)[0]
        try:
            issued = (datetime.strptime(m["date"].strip(), "%d %b %Y")
                      .replace(tzinfo=UTC).date().isoformat())
        except ValueError:
            continue
        out.append({"issued": issued, "level": int(m["lvl"]), "label": m["label"].strip(),
                    "title": title, "text": body, "subregion": _asmc_subregion(title)})
    if not out:
        raise SourceChanged("ASMC alerts table not found")
    out.sort(key=lambda a: a["issued"], reverse=True)
    return out


def parse_asmc_hotspots(payload: list) -> list[dict]:
    """[{date, <Region>: n, <Region>LineColor: ...}] -> [{date, region, count}]."""
    if not isinstance(payload, list):
        raise SourceChanged("ASMC hotspot count: not a list")
    out = []
    for row in payload:
        d = row.get("date")
        for k, v in row.items():
            if k == "date" or k.endswith("LineColor") or not isinstance(v, int | float):
                continue
            out.append({"date": d, "region": k, "count": v})
    return out


class AsmcHazeAlerts(Collector):
    name = "asmc_haze_alerts"
    freshness_basis = "run"
    max_age_s = 9 * HOUR  # alert levels only change when haze does
    title = "ASMC -- transboundary haze alert level"
    category = "official"
    provider = "ASEAN Specialised Meteorological Centre (ASMC)"
    homepage = ASMC_ALERTS_URL
    endpoint = ASMC_ALERTS_URL
    interval_s = 3 * 3600
    description = ("ASMC 0-3 alert level for fire haze (southern ASEAN: "
                   "Sumatra, Kalimantan; Mekong sub-region, including Thailand).")

    async def collect(self, ctx: RunContext) -> int:
        alerts = parse_asmc_alerts((await ctx.get(ASMC_ALERTS_URL)).text)
        latest = {}
        for a in alerts:  # newest first
            latest.setdefault(a["subregion"], {k: a[k] for k in
                                               ("issued", "level", "label", "title")})
        db.set_status("asmc_haze_alert", {"southern": latest.get("southern"),
                                          "mekong": latest.get("mekong"),
                                          "url": ASMC_ALERTS_URL})
        feed = [{
            "ext_id": f"{a['issued']}_{a['subregion']}", "kind": "official",
            "title": f"ASMC {a['label']}: {a['title']}", "summary": a["text"][:1500],
            "url": ASMC_ALERTS_URL, "author": "ASMC", "lang": "en",
            "published_at": a["issued"],
            "tags": ["haze", "asean"] + (["thailand"] if a["subregion"] == "mekong"
                                         or "thailand" in a["text"].lower() else []),
        } for a in alerts[:20]]
        return db.upsert_feed_items(self.name, feed)


class AsmcHotspots(Collector):
    name = "asmc_hotspots"
    freshness_basis = "observations"
    max_age_s = 3 * DAY  # daily counts
    title = "ASMC -- VIIRS hotspots by country/region"
    category = "satellite"
    provider = "ASEAN Specialised Meteorological Centre (ASMC)"
    homepage = "https://asmc.asean.org/asmc-haze-hotspot-daily-new/"
    endpoint = ASMC_HOTSPOT_URL
    interval_s = 6 * 3600
    description = ("Daily hotspot counts (VIIRS, daytime, high confidence) over 14 "
                   "days: Thailand, Myanmar, Cambodia, Vietnam, Laos, Philippines, Malaysia, "
                   "Sumatra, Kalimantan. Rising = fires = haze.")

    async def collect(self, ctx: RunContext) -> int:
        day = datetime.now(UTC).date()
        rows = []
        for group in ASMC_REGION_GROUPS:
            r = await ctx.client.post(ASMC_HOTSPOT_URL, data={
                "date": f"{day.day} {day.strftime('%b')}, {day.year}", "pastDays": 14,
                "regions[]": list(group), "daynight": "day", "conf": "High"})
            ctx.last_status = r.status_code
            r.raise_for_status()
            for x in parse_asmc_hotspots(r.json()):
                rows.append({"series": f"asmc_hotspots_{x['region'].lower()}", "ts": x["date"],
                             "value": x["count"], "unit": "hotspots",
                             "meta": {"region": x["region"], "daynight": "day",
                                      "confidence": "High", "product": "ASMC VIIRS daily"}})
        if not rows:
            raise SourceChanged("ASMC hotspot counts empty for every region")
        return db.upsert_observations(self.name, rows)


# --------------------------------------------------------------------------- ThaiWater dams

THAIWATER_DAM_URL = "https://api-v3.thaiwater.net/api/v1/thaiwater30/analyst/dam_load"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def parse_thai_dams(payload: dict) -> dict:
    """RID large dams (daily) -> {date, total_storage_pct, dams: [...]}."""
    try:
        rows = payload["dam_data"]["data"]
    except (KeyError, TypeError) as e:
        raise SourceChanged("thaiwater dam_load: no dam_data.data") from e
    dams = []
    for x in rows:
        agency = ((x.get("agency") or {}).get("agency_shortname") or {}).get("en")
        dam = x.get("dam") or {}
        name = (dam.get("dam_name") or {}).get("en")
        # EGAT rows duplicate RID dams with many zero percentages: RID only.
        if agency != "RID" or not name or x.get("dam_storage_percent") is None:
            continue
        geo = x.get("geocode") or {}
        dams.append({
            "id": dam.get("id"), "slug": _slug(name), "name": name,
            "name_th": (dam.get("dam_name") or {}).get("th"),
            "date": x.get("dam_date"), "storage_pct": float(x["dam_storage_percent"]),
            "storage_mcm": x.get("dam_storage"), "normal_storage_mcm": dam.get("normal_storage"),
            "usable_pct": x.get("dam_uses_water_percent"), "inflow_mcm": x.get("dam_inflow"),
            "released_mcm": x.get("dam_released"),
            "province": (geo.get("province_name") or {}).get("en"),
            "basin": ((x.get("basin") or {}).get("basin_name") or {}).get("en"),
            "lat": dam.get("dam_lat"), "lon": dam.get("dam_long"),
        })
    if not dams:
        raise SourceChanged("thaiwater dam_load: no RID dam rows")
    date_ = max(d["date"] for d in dams if d["date"])
    same_day = [d for d in dams if d["date"] == date_ and d["storage_mcm"] is not None
                and d["normal_storage_mcm"]]
    total = None
    if same_day:
        total = round(100 * sum(d["storage_mcm"] for d in same_day)
                      / sum(d["normal_storage_mcm"] for d in same_day), 2)
    return {"date": date_, "total_storage_pct": total, "total_dams": len(same_day),
            "dams": sorted(dams, key=lambda d: d["storage_pct"])}


class ThaiDamsNational(Collector):
    name = "thaiwater_dams_national"
    freshness_basis = "observations"
    max_age_s = 3 * DAY  # daily RID report
    title = "Thailand -- large dam storage"
    category = "disaster"
    provider = "ThaiWater (HII) / Royal Irrigation Department"
    homepage = "https://www.thaiwater.net/water/dam"
    endpoint = THAIWATER_DAM_URL
    interval_s = 6 * 3600
    description = ("Daily storage of the 35 large RID dams and the national total "
                   "(storage / normal capacity). El Nino = less monsoon rain = "
                   "low reservoirs in the dry season.")

    async def collect(self, ctx: RunContext) -> int:
        doc = parse_thai_dams((await ctx.get(THAIWATER_DAM_URL)).json())
        doc["url"] = self.homepage
        db.set_status("thai_dams", doc)
        rows = [{"series": f"dam_{d['slug']}_storage_pct", "ts": d["date"],
                 "value": d["storage_pct"], "unit": "%",
                 "meta": {k: d[k] for k in ("name", "province", "usable_pct", "storage_mcm",
                                            "lat", "lon")}}
                for d in doc["dams"] if d["date"]]
        if doc["total_storage_pct"] is not None:
            rows.append({"series": "thai_large_dams_storage_pct", "ts": doc["date"],
                         "value": doc["total_storage_pct"], "unit": "%",
                         "meta": {"dams": doc["total_dams"], "basis": "sum storage / "
                                  "sum normal storage, RID large dams"}})
        return db.upsert_observations(self.name, rows)


COLLECTORS = [GdacsEvents, EonetEvents, FirmsFires, TmdWarningsEn, AsmcHazeAlerts,
              AsmcHotspots, ThaiDamsNational]
