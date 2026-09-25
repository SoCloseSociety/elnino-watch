"""Public webcams: see conditions with your own eyes (sea state, rain, haze, storms).

RULE 11 -- PUBLIC FEEDS ONLY. Every camera here is one its owner deliberately
publishes for public viewing: venue / hotel streams on the owner's own YouTube
channel, tourism webcam portals (SkylineWebcams, link-only), official agency
feeds (NOAA NDBC BuoyCAMs, JMA Himawari, NOAA NESDIS GOES), the Bangkok city
traffic portal, and the Windy Webcams API (needs a free key). Never unsecured
cameras, directories of them, or anything behind access control. Evidence for
every cam considered (included or not) is in backend/docs/WEBCAMS.md.

Three collectors, each re-checking availability and writing its own status part,
then rebuilding the combined status `webcams` (the list the API serves):
- webcams_images  (30 min): still-image feeds with a real image timestamp
  (NDBC BuoyCAMs, JMA Himawari sectors, GOES-West / GOES-East full disk).
  `status` = live when the newest image is younger than `max_image_age_s`,
  stale when older (never shown as live), error when the fetch failed.
- webcams_streams (60 min): YouTube venue streams (official oEmbed endpoint:
  still published, still embeddable, still by the same channel), SkylineWebcams
  pages (their own OFFLINE flag) and owner pages we can only link to.
- webcams_windy   (60 min): Windy Webcams API v3 near Koh Samui and the ferry
  route. Needs WINDY_WEBCAMS_KEY (free at https://api.windy.com/keys).

Per-cam display mode (`mode`):
- "proxy": public-domain / open-licence still image; the API may proxy it
  (GET /api/webcams/{id}/snapshot) with attribution in `license_note`.
- "embed": the owner offers an embeddable player (YouTube, Windy player).
- "link":  the provider does not allow reuse (SkylineWebcams terms, owner pages
  whose player is locked to their own domain): open `page_url`.

`status` values: live (fresh image) | online (provider says the stream is up) |
reachable (published and embeddable/reachable, live state not measurable) |
stale | offline | error | pending. `ok` = live, online or reachable.
"""

from __future__ import annotations

import asyncio
import os
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, ClassVar

import httpx

from .. import db
from ..config import ROOT
from .base import HOUR, Collector, NeedsConfig, RunContext, SourceChanged

STATUS_KEY = "webcams"
PART_KEYS = ("webcams_images", "webcams_streams", "webcams_windy")
OK_STATES = ("live", "online", "reachable")

NDBC_BUOYCAMS_URL = "https://www.ndbc.noaa.gov/buoycams.php"
NDBC_IMG_BASE = "https://www.ndbc.noaa.gov/images/buoycam/"
NDBC_STATION_PAGE = "https://www.ndbc.noaa.gov/station_page.php?station={id}"
JMA_PAGE = "https://www.data.jma.go.jp/mscweb/data/himawari/sat_img.php?area={area}"
JMA_IMG = "https://www.data.jma.go.jp/mscweb/data/himawari/img/{area}/{area}_{band}_{hhmm}.jpg"
GOES_BASE = "https://cdn.star.nesdis.noaa.gov/{sat}/ABI/FD/{band}/1808x1808.jpg"
YT_OEMBED = "https://www.youtube.com/oembed"
WINDY_API = "https://api.windy.com/webcams/api/v3/webcams"
WINDY_KEY_ENV = "WINDY_WEBCAMS_KEY"

LICENSE_NOAA = ("NOAA / US Government work, public domain. Proxy allowed; credit "
                "'NOAA'.")
LICENSE_JMA = ("Japan Meteorological Agency, Public Data License 1.0 (CC BY 4.0 "
               "compatible). Proxy allowed; credit 'Source: Japan Meteorological Agency'.")
LICENSE_YT = ("Published by the channel owner on YouTube; show only through the "
              "official YouTube embed player (YouTube Terms). No snapshot reuse.")
LICENSE_SKYLINE = ("SkylineWebcams terms forbid copying frames or re-streaming: "
                   "link to the official page only.")
LICENSE_WINDY = ("Windy Webcams API terms: show only through Windy's player/URLs, "
                 "link to the webcam page, credit 'Webcams provided by windy.com'.")

CONCURRENCY = 4


# --------------------------------------------------------------------------- helpers

def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _iso(t: datetime | None) -> str | None:
    return None if t is None else t.astimezone(UTC).replace(microsecond=0).isoformat()


def http_date(value: str | None) -> datetime | None:
    """Last-Modified header -> aware UTC datetime (None if absent / unparseable)."""
    if not value:
        return None
    try:
        t = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)


def env_value(name: str) -> str:
    """os.environ first, then the project .env (pydantic only loads declared fields)."""
    v = os.environ.get(name, "").strip()
    if v:
        return v
    path = ROOT / ".env"
    try:
        for line in path.read_text().splitlines():
            k, sep, val = line.partition("=")
            if sep and k.strip() == name:
                return val.strip().strip("'\"")
    except OSError:
        pass
    return ""


def cam(**kw: Any) -> dict:
    """One catalog entry with every documented field present."""
    base = {
        "id": None, "title": None, "place": None, "area": None, "lat": None, "lon": None,
        "coord_precision": "approx", "kind": None, "provider": None, "publisher": None,
        "page_url": None, "embed_url": None, "snapshot_url": None, "stream_type": None,
        "mode": "link", "snapshot_allowed": False, "refresh_s": None,
        "max_image_age_s": None, "license_note": None, "why": None,
        "status": "pending", "ok": False, "live_basis": None, "detail": None,
        "last_checked": None, "last_ok": None, "image_updated_at": None, "image_age_s": None,
    }
    base.update(kw)
    return base


def _mark(c: dict, status: str, *, detail: str | None = None, basis: str | None = None,
          image_at: datetime | None = None, now: datetime | None = None) -> dict:
    now = now or _now()
    c["status"] = status
    c["ok"] = status in OK_STATES
    c["detail"] = detail
    c["live_basis"] = basis
    c["last_checked"] = _iso(now)
    if image_at is not None:
        c["image_updated_at"] = _iso(image_at)
        c["image_age_s"] = max(0, int((now - image_at).total_seconds()))
    if c["ok"]:
        c["last_ok"] = _iso(now)
    return c


def _image_state(c: dict, image_at: datetime | None, now: datetime) -> dict:
    if image_at is None:
        return _mark(c, "reachable", detail="image answered but carries no timestamp", now=now)
    age = (now - image_at).total_seconds()
    if c["max_image_age_s"] and age > c["max_image_age_s"]:
        return _mark(c, "stale", image_at=image_at, now=now,
                     detail=f"newest image is {int(age // 60)} min old "
                            f"(limit {c['max_image_age_s'] // 60} min)")
    return _mark(c, "live", basis="image_time", image_at=image_at, now=now)


def _carry_last_ok(cams: list[dict], previous: list[dict] | None) -> None:
    """A failed check keeps the last time the cam did work (never invents one)."""
    prev = {p["id"]: p.get("last_ok") for p in (previous or []) if isinstance(p, dict)}
    for c in cams:
        if not c["ok"] and not c.get("last_ok"):
            c["last_ok"] = prev.get(c["id"])


def _prev(key: str) -> list[dict] | None:
    s = db.get_status(key)
    v = s["value"] if s else None
    return v.get("webcams") if isinstance(v, dict) else None


def rebuild_combined() -> list[dict]:
    """status `webcams` = every part's cams (sorted: area, kind, title)."""
    out: list[dict] = []
    parts: dict[str, Any] = {}
    for key in PART_KEYS:
        s = db.get_status(key)
        if not s or not isinstance(s["value"], dict):
            parts[key] = None
            continue
        for c in s["value"].get("webcams", []):
            c["help_id"] = HELP_BY_KIND.get(c.get("kind"), "webcams")
            out.append(c)
        parts[key] = {"updated_at": s["updated_at"], "count": len(s["value"].get("webcams", [])),
                      "ok": sum(1 for c in s["value"].get("webcams", []) if c.get("ok"))}
    out.sort(key=lambda c: (AREA_ORDER.get(c.get("area"), 99), c.get("kind") or "",
                            c.get("title") or ""))
    db.set_status(STATUS_KEY, out)
    db.set_status(STATUS_KEY + "_parts", parts)
    return out


HELP_BY_KIND = {"buoy": "webcams_buoycams", "satellite": "webcams_space_cams",
                "beach": "webcams_sea_state", "pier": "webcams_sea_state"}
AREA_ORDER = {"samui": 0, "ferry_route": 1, "thailand": 2, "space": 3, "pacific": 4,
              "peru_ecuador": 5, "australia": 6, "indonesia": 7}


async def _gather_limited(coros: list) -> list:
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(co):
        async with sem:
            return await co

    return await asyncio.gather(*(one(c) for c in coros))


# --------------------------------------------------------------------------- NDBC BuoyCAMs

def is_pacific(lon: float) -> bool:
    """Pacific basin: east of 150 E or west of 115 W (excludes Gulf / Atlantic / Great Lakes)."""
    return lon >= 150 or lon <= -115


def ndbc_image_time(img: str) -> datetime | None:
    """'W24A_2026_09_24_1310.jpg' -> 2026-09-24T13:10Z (NDBC names images by UTC time)."""
    m = re.search(r"_(\d{4})_(\d{2})_(\d{2})_(\d{2})(\d{2})\.jpe?g$", img or "")
    if not m:
        return None
    y, mo, d, h, mi = (int(x) for x in m.groups())
    return datetime(y, mo, d, h, mi, tzinfo=UTC)


def parse_ndbc_buoycams(payload: Any) -> list[dict]:
    """buoycams.php JSON -> Pacific BuoyCAM entries (image may be None = no photo now)."""
    if not isinstance(payload, list) or not payload:
        raise SourceChanged("NDBC buoycams.php: expected a non-empty JSON list")
    out = []
    for b in payload:
        try:
            sid, name, lat, lon = str(b["id"]), str(b["name"]).strip(), float(b["lat"]), \
                float(b["lng"])
        except (KeyError, TypeError, ValueError) as e:
            raise SourceChanged(f"NDBC buoycams.php: bad row {b!r:.120}") from e
        if not is_pacific(lon):
            continue
        img = b.get("img")
        out.append(cam(
            id=f"ndbc_{sid}", title=f"NOAA BuoyCAM {sid}", place=re.sub(r"\s+", " ", name),
            area="pacific", lat=lat, lon=lon, coord_precision="exact", kind="buoy",
            provider="NOAA NDBC", publisher="NOAA National Data Buoy Center",
            page_url=NDBC_STATION_PAGE.format(id=sid),
            snapshot_url=(NDBC_IMG_BASE + img) if img else None,
            stream_type="image", mode="proxy", snapshot_allowed=True, refresh_s=3600,
            max_image_age_s=3 * HOUR, license_note=LICENSE_NOAA,
            why=("Open-ocean Pacific horizon photos (6 directions in one strip): whitecaps, "
                 "swell and squalls far from land. Daylight only."),
            _img=img,
        ))
    return out


async def check_ndbc(ctx: RunContext) -> list[dict]:
    r = await ctx.get(NDBC_BUOYCAMS_URL)
    try:
        payload = r.json()
    except ValueError as e:
        raise SourceChanged("NDBC buoycams.php did not return JSON") from e
    cams = parse_ndbc_buoycams(payload)
    now = _now()

    async def one(c: dict) -> dict:
        img = c.pop("_img", None)
        if not img:
            return _mark(c, "offline", detail="NDBC lists no current photo for this buoy",
                         now=now)
        try:
            h = await ctx.client.head(c["snapshot_url"])
            if h.status_code != 200:
                return _mark(c, "error", detail=f"image HTTP {h.status_code}", now=now)
        except httpx.HTTPError as e:
            return _mark(c, "error", detail=f"{type(e).__name__}", now=now)
        return _image_state(c, ndbc_image_time(img), now)

    return await _gather_limited([one(c) for c in cams])


# --------------------------------------------------------------------------- JMA Himawari

JMA_AREAS = {
    "se1": {"place": "Southeast Asia 1: Myanmar, Thailand, Gulf of Thailand, Vietnam",
            "area": "samui", "lat": 12.0, "lon": 102.0},
    "fd_": {"place": "Full disk centred on 140.7 E (Asia, Australia, West/Central Pacific)",
            "area": "space", "lat": 0.0, "lon": 140.7},
}
JMA_BANDS = {
    "b13": ("infrared (B13, day and night)",
            "Cloud-top temperature: bright white = cold, tall storm tops. Works at night."),
    "trm": ("true colour (daytime only)",
            "What the eye would see from space: cloud, haze and smoke. Black at night."),
}


def parse_jma_latest(html: str) -> tuple[str, datetime]:
    """sat_img.php -> (file time HHMM, image time) from the first slt_time option.

    File names are keyed by scan start (value) and the label is the nominal image
    time, e.g. value=1350 -> '14:00 UTC 24 September 2026'."""
    i = html.find('name="slt_time"')
    m = re.search(r"<option value=\"?(\d{4})\"?>\s*(\d{2}:\d{2}) UTC (\d{1,2} \w+ \d{4})",
                  html[i:] if i >= 0 else "")
    if not m:
        raise SourceChanged("JMA sat_img.php: no slt_time option found")
    try:
        t = datetime.strptime(f"{m.group(3)} {m.group(2)}", "%d %B %Y %H:%M").replace(tzinfo=UTC)
    except ValueError as e:
        raise SourceChanged(f"JMA sat_img.php: bad time label {m.group(0)!r}") from e
    return m.group(1), t


async def check_jma(ctx: RunContext) -> list[dict]:
    now = _now()
    out: list[dict] = []
    for area, meta in JMA_AREAS.items():
        page = JMA_PAGE.format(area=area)
        cams = [cam(
            id=f"himawari_{area.strip('_')}_{band}",
            title=f"Himawari-9 {meta['place'].split(':')[0]} -- {label}",
            place=meta["place"], area=meta["area"], lat=meta["lat"], lon=meta["lon"],
            coord_precision="sector_centre", kind="satellite",
            provider="JMA Meteorological Satellite Center", publisher="Japan Meteorological Agency",
            page_url=page, stream_type="image", mode="proxy", snapshot_allowed=True,
            refresh_s=600, max_image_age_s=HOUR, license_note=LICENSE_JMA, why=why,
        ) for band, (label, why) in JMA_BANDS.items()]
        try:
            r = await ctx.get(page)
            hhmm, t = parse_jma_latest(r.text)
        except (httpx.HTTPError, SourceChanged) as e:
            out += [_mark(c, "error", detail=f"{type(e).__name__}: {e}"[:160], now=now)
                    for c in cams]
            continue
        for c, band in zip(cams, JMA_BANDS, strict=True):
            c["snapshot_url"] = JMA_IMG.format(area=area, band=band, hhmm=hhmm)
            try:
                h = await ctx.client.head(c["snapshot_url"])
            except httpx.HTTPError as e:
                out.append(_mark(c, "error", detail=type(e).__name__, now=now))
                continue
            if h.status_code != 200:
                out.append(_mark(c, "error", detail=f"image HTTP {h.status_code}", now=now))
                continue
            out.append(_image_state(c, t, now))
    return out


# --------------------------------------------------------------------------- GOES

GOES_CAMS = [
    ("goes18_fd_geocolor", "GOES18", "GEOCOLOR", "GOES-West full disk -- GeoColor",
     ("Eastern and central Pacific incl. the Nino 3.4 region: GeoColor = true colour by "
      "day, infrared cloud + city lights at night."), -137.2),
    ("goes18_fd_ir", "GOES18", "13", "GOES-West full disk -- infrared (band 13)",
     ("Eastern and central Pacific cloud tops day and night: deep tropical convection "
      "shifting east is an El Nino fingerprint."), -137.2),
    ("goes19_fd_geocolor", "GOES19", "GEOCOLOR", "GOES-East full disk -- GeoColor",
     "The Americas incl. the Peru / Ecuador coast, where El Nino brings heavy rain.", -75.2),
]


async def check_goes(ctx: RunContext) -> list[dict]:
    now = _now()

    async def one(spec) -> dict:
        cid, sat, band, title, why, lon = spec
        c = cam(id=cid, title=title, place=f"Full disk centred on {abs(lon)} W", area="space",
                lat=0.0, lon=lon, coord_precision="sector_centre", kind="satellite",
                provider="NOAA NESDIS STAR", publisher="NOAA NESDIS",
                page_url=f"https://www.star.nesdis.noaa.gov/GOES/fulldisk.php?sat=G{sat[-2:]}",
                snapshot_url=GOES_BASE.format(sat=sat, band=band), stream_type="image",
                mode="proxy", snapshot_allowed=True, refresh_s=600, max_image_age_s=HOUR,
                license_note=LICENSE_NOAA, why=why)
        try:
            h = await ctx.client.head(c["snapshot_url"])
        except httpx.HTTPError as e:
            return _mark(c, "error", detail=type(e).__name__, now=now)
        if h.status_code != 200:
            return _mark(c, "error", detail=f"image HTTP {h.status_code}", now=now)
        return _image_state(c, http_date(h.headers.get("last-modified")), now)

    return await _gather_limited([one(s) for s in GOES_CAMS])


# --------------------------------------------------------------------------- streams catalog

WHY_SEA = "Sea state off {p}: whitecaps, swell and rain squalls before a boat trip."
WHY_STREET = "Street-level rain and standing water in {p}; how busy / normal it looks."


def yt(vid: str, title: str, place: str, area: str, lat: float, lon: float, kind: str,
       publisher: str, why: str, page_url: str | None = None) -> dict:
    return cam(id=f"yt_{vid}", title=title, place=place, area=area, lat=lat, lon=lon,
               kind=kind, provider="YouTube", publisher=publisher,
               page_url=page_url or f"https://www.youtube.com/watch?v={vid}",
               embed_url=f"https://www.youtube-nocookie.com/embed/{vid}",
               stream_type="youtube", mode="embed", license_note=LICENSE_YT, why=why,
               _video=vid)


def skyline(path: str, title: str, place: str, area: str, lat: float, lon: float, kind: str,
            why: str) -> dict:
    slug = path.rsplit("/", 1)[-1]
    return cam(id=f"skyline_{slug.replace('-', '_')}", title=title, place=place, area=area,
               lat=lat, lon=lon, kind=kind, provider="SkylineWebcams", publisher="SkylineWebcams",
               page_url=f"https://www.skylinewebcams.com/en/webcam/{path}.html",
               stream_type="hls", mode="link", license_note=LICENSE_SKYLINE, why=why,
               _check="skyline")


def page(cid: str, title: str, place: str, area: str, lat: float, lon: float, kind: str,
         publisher: str, url: str, why: str, license_note: str) -> dict:
    return cam(id=cid, title=title, place=place, area=area, lat=lat, lon=lon, kind=kind,
               provider=publisher, publisher=publisher, page_url=url, stream_type="iframe",
               mode="link", license_note=license_note, why=why, _check="page")


RSW = "The Real Samui Webcam"
SOT = "STREETS OF THAILAND"

STREAM_CATALOG: list[dict] = [
    # ---- Koh Samui: sea / beach views (ferry + swim decisions)
    yt("CSp55hSd_6A", "Fisherman's Village beach (El Gaucho), Bophut", "Bophut, north coast",
       "samui", 9.5605, 100.0280, "beach", RSW,
       "North-coast sea state toward Koh Phangan -- the side the Bophut / Big Buddha / "
       "Maenam ferries cross. Whitecaps here = a rough crossing."),
    yt("x73IEW0fOo0", "Floating Lotus, Big Buddha / Bangrak", "Bangrak (Big Buddha), NE coast",
       "samui", 9.5700, 100.0600, "beach", RSW,
       "Bay next to the Big Buddha and Bangrak piers (Lomprayah / Seatran Discovery to "
       "Phangan and Tao): check wind chop before the boat."),
    yt("RN2miwo_S-o", "Sunset Bar, Bang Rak beach", "Bangrak, NE coast", "samui",
       9.5680, 100.0550, "beach", SOT, WHY_SEA.format(p="Bangrak (near the Big Buddha piers)")),
    yt("J9g4uE0gvm4", "Karma Two Palms Beach Club, Bang Po", "Bang Po, NW coast", "samui",
       9.5740, 99.9680, "beach", SOT,
       "North-west coast facing the Nathon / Donsak ferry lane and the mainland: "
       "sea state and incoming squalls from the west."),
    yt("3N3ZwIB_X4Y", "Crystal Bay Yacht Club, Lamai", "Crystal Bay, east coast", "samui",
       9.4870, 100.0670, "beach", RSW,
       "East coast open to the Gulf: the first place NE-monsoon swell (Oct-Dec) shows up."),
    yt("Fw9hgttWzIg", "Crystal Bay Beach Resort, Lamai", "Crystal Bay, east coast", "samui",
       9.4860, 100.0660, "beach", RSW, WHY_SEA.format(p="the east coast (Crystal Bay)")),
    yt("Szx0K7gZBx8", "Villa Tao sea view, Lamai", "Lamai, east coast", "samui",
       9.4700, 100.0500, "beach", RSW, WHY_SEA.format(p="Lamai")),
    yt("Tpj0cmMVOd0", "Baobab beach cam, Lamai", "Lamai, south-east coast", "samui",
       9.4600, 100.0450, "beach", RSW, WHY_SEA.format(p="Lamai")),
    yt("NwnRppDlkX8", "Black Pearl, Lamai beach", "Lamai, east coast", "samui",
       9.4690, 100.0470, "beach", SOT, WHY_SEA.format(p="Lamai beach")),
    yt("ZAGJyPv4mNU", "Teddy Weed beach club, Lamai", "Lamai, east coast", "samui",
       9.4630, 100.0470, "beach", SOT, WHY_SEA.format(p="Lamai beach")),
    yt("wP6hpWgPJ98", "Banyan Tree Samui (Lamai Bay)", "Lamai Bay, south-east coast", "samui",
       9.4440, 100.0330, "beach", "Banyan Tree Samui",
       "Hotel's own stream over Lamai Bay: swell, rain curtains and visibility (haze)."),
    skyline("thailand/surat-thani/ko-samui/choengmon-beach", "Choengmon Beach (SkylineWebcams)",
            "Choeng Mon, NE tip", "samui", 9.5720, 100.0780, "beach",
            WHY_SEA.format(p="Choeng Mon (NE tip, exposed to NE monsoon)")),
    skyline("thailand/surat-thani/ko-samui/lamai", "Lamai (SkylineWebcams)", "Lamai, east coast",
            "samui", 9.4690, 100.0450, "beach", WHY_SEA.format(p="Lamai")),
    # ---- Koh Samui: street views (rain / flooding / normal life)
    yt("DwKCna1mumk", "Hush Bar, Soi Green Mango, Chaweng", "Chaweng", "samui", 9.5375,
       100.0615, "city", RSW, WHY_STREET.format(p="central Chaweng (Soi Green Mango)")),
    yt("yFgVmioYkys", "Soi Green Mango / Munchies, Chaweng", "Chaweng", "samui", 9.5375,
       100.0610, "city", RSW, WHY_STREET.format(p="central Chaweng")),
    yt("Ajo0iFkX3EY", "Henry Africa's, Soi Green Mango, Chaweng", "Chaweng", "samui", 9.5378,
       100.0612, "city", RSW, WHY_STREET.format(p="central Chaweng")),
    yt("OdY-pbgl1Mk", "Jimmy Woo's, Soi Green Mango, Chaweng", "Chaweng", "samui", 9.5372,
       100.0613, "city", "Jimmywoo's Samui", WHY_STREET.format(p="central Chaweng")),
    yt("Jv_2vPCbZUo", "Bondi Aussie Bar, Chaweng", "Chaweng Beach Road", "samui", 9.5310,
       100.0620, "city", RSW, WHY_STREET.format(p="Chaweng Beach Road")),
    yt("HdaWcBamcSA", "Bondi Aussie Bar, Lamai", "Lamai", "samui", 9.4690, 100.0450, "city",
       RSW, WHY_STREET.format(p="Lamai town")),
    yt("bbBGNNPu0rg", "The Shack, Fisherman's Village street", "Bophut", "samui", 9.5605,
       100.0275, "city", RSW, WHY_STREET.format(p="Fisherman's Village (Bophut)")),
    yt("FyFAqPHBKiQ", "El Gaucho street, Fisherman's Village", "Bophut", "samui", 9.5603,
       100.0278, "city", RSW, WHY_STREET.format(p="Fisherman's Village (Bophut)")),
    # ---- Ferry route: Koh Phangan, Koh Tao
    yt("gtSsnmLXJV4", "Koh Tao -- Mae Haad Bay / Koh Nang Yuan", "Koh Tao (west coast)",
       "ferry_route", 10.0950, 99.8280, "pier", "Scuba Birds PADI 5 * IDC Dive Center, Koh Tao",
       "Koh Tao's west coast by Mae Haad, where the Lomprayah / Seatran boats dock: sea "
       "state at the far end of the Samui-Phangan-Tao ferry line.",
       page_url="https://www.scubabirds.com/ko-tao/koh-tao-live-stream.html"),
    yt("MW3fisTCXRQ", "Koh Phangan -- Haad Rin beach (House of Sanskara)", "Haad Rin, Koh Phangan",
       "ferry_route", 9.6760, 100.0660, "beach", "Teleport.camera",
       "Haad Rin faces the channel between Phangan and Samui (Haad Rin Queen ferry to Big "
       "Buddha pier): chop in the strait the boats cross."),
    # ---- Wider Thailand
    yt("UemFRPrl1hk", "Bangkok -- Sukhumvit Soi 11 (El Gaucho)", "Bangkok", "thailand", 13.7420,
       100.5560, "city", RSW, WHY_STREET.format(p="Bangkok (Sukhumvit)")),
    yt("Q71sLS8h9a4", "Bangkok -- Sukhumvit Soi 19 (El Gaucho)", "Bangkok", "thailand", 13.7380,
       100.5610, "city", RSW, WHY_STREET.format(p="Bangkok (Sukhumvit)")),
    yt("a_bUVExv_Cg", "Bangkok -- Petchaburi Road", "Bangkok", "thailand", 13.7500, 100.5400,
       "city", "Tahug", WHY_STREET.format(p="Bangkok (Petchaburi Road)")),
    page("bma_traffic", "Bangkok BMA Traffic CCTV portal", "Bangkok (city-wide)", "thailand",
         13.7563, 100.5018, "traffic", "Bangkok Metropolitan Administration",
         "http://www.bmatraffic.com/",
         "The city's own public CCTV map (hundreds of cameras): check flooded roads "
         "before driving to / from Don Mueang or Suvarnabhumi.",
         "Official public portal of the Bangkok Metropolitan Administration: open it "
         "there (no reuse of frames)."),
    yt("Qa5LqU9xxtc", "Pattaya -- Beach Road", "Pattaya (Gulf of Thailand, east shore)",
       "thailand", 12.9350, 100.8830, "beach", "PattayaBob360IRL",
       WHY_SEA.format(p="the upper Gulf of Thailand (Pattaya)")),
    yt("_nvG0c9keWI", "Phuket -- Patong, Sainamyen Road", "Patong, Phuket", "thailand", 7.8940,
       98.2980, "city", "Randomly Entertained", WHY_STREET.format(p="Patong (Phuket)")),
    page("phuket101_patong", "Phuket -- Patong Bay from Patong Tower", "Patong, Phuket",
         "thailand", 7.8925, 98.2950, "beach", "Phuket 101 (phuket101.net)",
         "https://www.phuket101.net/phuket-webcams/",
         "Andaman Sea side (SW monsoon, May-Oct): swell and squalls over Patong Bay.",
         "Owner's player is locked to phuket101.net (CSP frame-ancestors): link only."),
    page("sss_kata", "Phuket -- Kata Beach (SSS Dive & Surf)", "Kata, Phuket", "thailand",
         7.8195, 98.2975, "beach", "SSS Phuket Dive & Surf Center",
         "https://www.sssphuket.com/kata-beach-live-cam/",
         "Surf-school cam over the Kata break: wave height on the Andaman side.",
         "Owner's public stream page; watch it there (no reuse of frames)."),
    yt("cD5ZEBOf2Tg", "Khao Lak (Phang Nga)", "Khao Lak, Andaman coast", "thailand", 8.6400,
       98.2500, "beach", "Khao Lak Land Discovery", WHY_SEA.format(p="Khao Lak (Andaman coast)")),
    # ---- Peru / Ecuador (El Nino costero rains, warm coastal sea)
    skyline("peru/piura/talara/mancora", "Mancora beach, Piura", "Mancora, northern Peru",
            "peru_ecuador", -4.1050, -81.0500, "beach",
            "Northern Peru coast, the first place El Nino rains and warm-sea swell hit."),
    skyline("peru/lambayeque/chiclayo/pimentel", "Pimentel pier, Lambayeque",
            "Pimentel, northern Peru", "peru_ecuador", -6.8380, -79.9400, "pier",
            "Desert coast that floods in strong El Nino years (1983, 1998, 2017, 2023)."),
    skyline("peru/department-of-la-libertad/trujillo/playa-huanchaco", "Huanchaco beach, Trujillo",
            "Huanchaco, northern Peru", "peru_ecuador", -8.0800, -79.1200, "beach",
            "Trujillo coast: El Nino costero rain and flooding show up as grey skies here."),
    skyline("peru/lima/lima/miraflores", "Lima -- Miraflores coast", "Lima, Peru",
            "peru_ecuador", -12.1200, -77.0400, "city",
            "Lima's usual winter overcast ('garua') thins when the coastal sea warms."),
    skyline("ecuador/santa-elena/santa-elena/montanita", "Montanita, Santa Elena",
            "Montanita, Ecuador", "peru_ecuador", -1.8260, -80.7530, "beach",
            "Ecuador's Pacific coast: El Nino brings heavy rain and big warm-water swell."),
    skyline("ecuador/santa-elena/salinas/paco-illescas", "Salinas, Santa Elena",
            "Salinas, Ecuador", "peru_ecuador", -2.2150, -80.9550, "beach",
            "Westernmost Ecuador coast, close to the Nino 1+2 ocean region."),
    skyline("ecuador/galapagos/santa-cruz-island/galapagos-ecuador", "Galapagos -- Santa Cruz",
            "Santa Cruz, Galapagos", "peru_ecuador", -0.7400, -90.3100, "beach",
            "Galapagos sit in the eastern equatorial Pacific: warm, rainy El Nino conditions."),
    # ---- Australia (drought, heat, bushfire smoke in El Nino years)
    yt("5uZa3-RMFos", "Sydney Harbour (WebcamSydney)", "Sydney, Australia", "australia",
       -33.8570, 151.2100, "city", "WebcamSydney",
       "Bushfire smoke haze over Sydney in dry El Nino springs/summers."),
    yt("dypAtzvl24s", "Port of Newcastle harbour cam", "Newcastle NSW, Australia", "australia",
       -32.9200, 151.7800, "pier", "Port of Newcastle",
       "Official port cam: smoke haze and East Coast Low storms on the NSW coast."),
    skyline("australia/victoria/raglan/mount-cole", "Mount Cole forest, Victoria",
            "Mount Cole, Victoria", "australia", -37.2500, 143.2000, "city",
            "Forest ridge in western Victoria: smoke plumes on high fire-danger days."),
    # ---- Indonesia (drought, haze from peat fires in El Nino years)
    yt("L1duJDAqbJY", "Bali -- Bukit Jimbaran panorama", "Bali, Indonesia", "indonesia",
       -8.7900, 115.1600, "city", "Bali Weather Live Stream",
       "El Nino dry season in Indonesia: clear, dry skies or regional smoke haze."),
    yt("RsPsUMd7Wu4", "Gunungkidul -- Drini beach (Kominfo CCTV)", "Gunungkidul, Java",
       "indonesia", -8.1400, 110.5800, "beach", "Kominfo Gunungkidul",
       "Regional government's own public beach CCTV on Java's south coast (Indian Ocean swell)."),
]


async def check_youtube(ctx: RunContext, c: dict, now: datetime) -> dict:
    vid = c.pop("_video")
    try:
        r = await ctx.client.get(YT_OEMBED, params={
            "url": f"https://www.youtube.com/watch?v={vid}", "format": "json"})
    except httpx.HTTPError as e:
        return _mark(c, "error", detail=type(e).__name__, now=now)
    if r.status_code in (401, 403):
        return _mark(c, "offline", detail="the owner disabled embedding", now=now)
    if r.status_code == 404:
        return _mark(c, "offline", detail="video removed or made private", now=now)
    if r.status_code != 200:
        return _mark(c, "error", detail=f"oEmbed HTTP {r.status_code}", now=now)
    try:
        author = r.json().get("author_name")
    except ValueError:
        return _mark(c, "error", detail="oEmbed answer was not JSON", now=now)
    if _norm(author) != _norm(c["publisher"]):
        return _mark(c, "offline", now=now,
                     detail=f"now published by {author!r}, not {c['publisher']!r}: re-verify")
    return _mark(c, "reachable", basis="published", now=now,
                 detail="published and embeddable; live state shows in the player")


def _norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").casefold())


def skyline_is_offline(html: str) -> bool:
    return ">OFFLINE<" in html


async def check_skyline(ctx: RunContext, c: dict, now: datetime) -> dict:
    c.pop("_check", None)
    try:
        r = await ctx.client.get(c["page_url"])
    except httpx.HTTPError as e:
        return _mark(c, "error", detail=type(e).__name__, now=now)
    if r.status_code != 200:
        return _mark(c, "offline" if r.status_code in (404, 410) else "error",
                     detail=f"page HTTP {r.status_code}", now=now)
    if skyline_is_offline(r.text):
        return _mark(c, "offline", detail="SkylineWebcams marks this cam OFFLINE", now=now)
    if "m3u8" not in r.text and "videoId" not in r.text:
        return _mark(c, "error", detail="no player found on the page (layout changed?)",
                     now=now)
    return _mark(c, "online", basis="provider_flag", now=now,
                 detail="provider page shows the player, not OFFLINE")


async def check_page(ctx: RunContext, c: dict, now: datetime) -> dict:
    c.pop("_check", None)
    try:
        r = await ctx.client.head(c["page_url"])
        if r.status_code in (405, 501):
            r = await ctx.client.get(c["page_url"])
    except httpx.HTTPError as e:
        return _mark(c, "error", detail=type(e).__name__, now=now)
    if r.status_code != 200:
        return _mark(c, "error", detail=f"page HTTP {r.status_code}", now=now)
    return _mark(c, "reachable", basis="page", now=now,
                 detail="owner page answers; stream state is only visible there")


# --------------------------------------------------------------------------- collectors

class _CamsBase(Collector):
    category = "local"
    freshness_basis = "status"
    part_key: ClassVar[str]

    def _store(self, cams: list[dict]) -> int:
        _carry_last_ok(cams, _prev(self.part_key))
        for c in cams:
            for k in [k for k in c if k.startswith("_")]:
                c.pop(k)
        db.set_status(self.part_key, {"checked_at": _iso(_now()), "webcams": cams})
        rebuild_combined()
        return sum(1 for c in cams if c["ok"])


class WebcamImages(_CamsBase):
    name = "webcams_images"
    title = "Webcams: buoy and satellite still images"
    provider = "NOAA NDBC / JMA MSC / NOAA NESDIS STAR"
    homepage = "https://www.ndbc.noaa.gov/buoycams.php"
    endpoint = NDBC_BUOYCAMS_URL
    interval_s = 1800
    max_age_s = 2 * HOUR
    part_key = "webcams_images"
    freshness_status_key = "webcams_images"
    description = ("Re-checks the official still-image cams every 30 min: NOAA BuoyCAMs in the "
                   "Pacific, Himawari-9 (JMA) over the Gulf of Thailand and the full disk, "
                   "GOES-West / GOES-East full disk. Image time comes from the file name, the "
                   "JMA page or Last-Modified; an old image is marked stale, never live.")

    async def collect(self, ctx: RunContext) -> int:
        cams: list[dict] = []
        errors: dict[str, str] = {}
        for label, fn in (("ndbc", check_ndbc), ("jma", check_jma), ("goes", check_goes)):
            try:
                cams += await fn(ctx)
            except (httpx.HTTPError, SourceChanged) as e:
                errors[label] = f"{type(e).__name__}: {e}"[:200]
        if not cams:
            raise SourceChanged(f"no image cam could be checked: {errors}")
        ctx.notes.update(errors=errors or None,
                         states=_count_states(cams))
        return self._store(cams)


class WebcamStreams(_CamsBase):
    name = "webcams_streams"
    title = "Webcams: Koh Samui, ferry route, Thailand and ENSO-region streams"
    provider = "YouTube (venue channels) / SkylineWebcams / owner pages"
    homepage = "https://www.skylinewebcams.com/en/webcam/thailand/surat-thani/ko-samui.html"
    endpoint = YT_OEMBED
    interval_s = 3600
    max_age_s = 3 * HOUR
    part_key = "webcams_streams"
    freshness_status_key = "webcams_streams"
    description = ("Curated owner-published live streams (beach, pier, street) re-checked "
                   "hourly: YouTube via the official oEmbed endpoint (still published, "
                   "embeddable, same channel), SkylineWebcams pages via their OFFLINE flag "
                   "(link only), owner pages via a HEAD request.")

    async def collect(self, ctx: RunContext) -> int:
        now = _now()
        cams = [dict(c) for c in STREAM_CATALOG]

        async def one(c: dict) -> dict:
            if "_video" in c:
                return await check_youtube(ctx, c, now)
            if c.get("_check") == "skyline":
                return await check_skyline(ctx, c, now)
            return await check_page(ctx, c, now)

        cams = await _gather_limited([one(c) for c in cams])
        ctx.notes.update(states=_count_states(cams))
        return self._store(cams)


WINDY_QUERIES = [
    # (label, lat, lon, radius_km, area)
    ("Koh Samui", 9.512, 100.013, 30, "samui"),
    ("Koh Phangan / Koh Tao", 9.90, 99.95, 40, "ferry_route"),
    ("Surat Thani / Donsak pier", 9.25, 99.55, 50, "ferry_route"),
]


def parse_windy(payload: Any, area: str) -> list[dict]:
    """Windy v3 /webcams (include=location,player,urls) -> catalog entries (no images:
    Windy image URLs carry 10-minute tokens and may only be shown via their URLs)."""
    if not isinstance(payload, dict) or not isinstance(payload.get("webcams"), list):
        raise SourceChanged("Windy webcams: expected {total, webcams: [...]}")
    out = []
    for w in payload["webcams"]:
        try:
            wid = int(w["webcamId"])
            loc = w["location"]
            lat, lon = float(loc["latitude"]), float(loc["longitude"])
        except (KeyError, TypeError, ValueError) as e:
            raise SourceChanged(f"Windy webcams: bad row {w!r:.120}") from e
        player = w.get("player") or {}
        urls = w.get("urls") or {}
        place = ", ".join(x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x)
        c = cam(id=f"windy_{wid}", title=str(w.get("title") or f"Windy webcam {wid}"), place=place,
                area=area, lat=lat, lon=lon, coord_precision="provider", kind="city",
                provider="Windy Webcams", publisher="Windy.com (owner-submitted webcam)",
                page_url=urls.get("detail") or f"https://www.windy.com/webcams/{wid}",
                embed_url=player.get("live") or player.get("day"), stream_type="iframe",
                mode="embed", license_note=LICENSE_WINDY,
                why="Owner-submitted webcam listed by Windy near this area: sky, rain, sea.")
        t = http_iso(w.get("lastUpdatedOn"))
        status = str(w.get("status") or "")
        now = _now()
        if status != "active":
            _mark(c, "offline", detail=f"Windy status {status!r}", now=now)
        elif t is None:
            _mark(c, "reachable", basis="provider_flag", now=now, detail="Windy lists it active")
        else:
            c["max_image_age_s"] = 3 * HOUR
            _image_state(c, t, now)
        out.append(c)
    return out


def http_iso(s: Any) -> datetime | None:
    if not isinstance(s, str) or not s:
        return None
    try:
        t = datetime.fromisoformat(s)
    except ValueError:
        return None
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)


class WindyWebcams(_CamsBase):
    name = "webcams_windy"
    title = "Webcams: Windy Webcams API (Samui, ferry route)"
    provider = "Windy.com Webcams API v3"
    homepage = "https://api.windy.com/webcams"
    endpoint = WINDY_API
    interval_s = 3600
    max_age_s = 3 * HOUR
    needs = (WINDY_KEY_ENV,)
    part_key = "webcams_windy"
    freshness_status_key = "webcams_windy"
    description = ("Owner-submitted webcams listed by Windy within 30-50 km of Koh Samui, "
                   "Koh Phangan / Koh Tao and Donsak pier. Needs a free key in "
                   "WINDY_WEBCAMS_KEY (https://api.windy.com/keys). Shown via Windy's player.")

    def missing_config(self) -> list[str]:
        return [] if env_value(WINDY_KEY_ENV) else [WINDY_KEY_ENV]

    async def collect(self, ctx: RunContext) -> int:
        key = env_value(WINDY_KEY_ENV)
        if not key:
            raise NeedsConfig(WINDY_KEY_ENV)
        seen: dict[str, dict] = {}
        for _label, lat, lon, radius, area in WINDY_QUERIES:
            r = await ctx.get(WINDY_API, headers={"x-windy-api-key": key}, params={
                "nearby": f"{lat},{lon},{radius}", "limit": 50,
                "include": "location,player,urls", "lang": "en"})
            for c in parse_windy(r.json(), area):
                seen.setdefault(c["id"], c)
        cams = list(seen.values())
        ctx.notes.update(states=_count_states(cams))
        return self._store(cams)


def _count_states(cams: list[dict]) -> dict:
    out: dict[str, int] = {}
    for c in cams:
        out[c["status"]] = out.get(c["status"], 0) + 1
    return out


COLLECTORS = [WebcamImages, WebcamStreams, WindyWebcams]
