"""The places being compared: a config list (DEFAULT_PLACES) plus user-added places.

Every default place was geocoded on 2026-09-24 against two independent keyless
geocoders and its admin area confirmed:
- OpenStreetMap Nominatim (https://nominatim.openstreetmap.org, identified with
  settings.user_agent) -> lat/lon + the administrative chain;
- Open-Meteo geocoding (GeoNames) -> timezone, GeoNames id;
- Open-Meteo elevation API (Copernicus DEM GLO-90) -> elevation_m at the point.

Maenam: GeoNames 6692479 lists "Mae Nam" at 9.5691, 100.0033 but files it under
Nakhon Si Thammarat (wrong); OSM places the village "Ban Mae Nam" at 9.5705, 99.9957
inside Ko Samui district, Surat Thani 84330, which is correct. We use the OSM point.

The live list is the status doc `places_config` (created from DEFAULT_PLACES on first
read). POST /api/places adds a place (admin), DELETE removes one; default places can be
removed too (the removal is recorded, so they do not come back on restart).
"""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy

from .. import db

STATUS_KEY = "places_config"

GEOCODE_CHECKED = "2026-09-24"

DEFAULT_PLACES: list[dict] = [
    {
        "id": "maenam",
        "name": "Maenam, Koh Samui",
        "short_name": "Maenam",
        "admin": "Maenam (Mae Nam) subdistrict, Ko Samui district, Surat Thani, Thailand",
        "country": "Thailand", "country_code": "TH",
        "lat": 9.5705, "lon": 99.9957, "elevation_m": 8.0, "timezone": "Asia/Bangkok",
        "role": "home",
        "coastal_hint": True,
        "geocode": {
            "source": "OpenStreetMap Nominatim (village 'Ban Mae Nam') + Open-Meteo elevation",
            "url": "https://www.openstreetmap.org/?mlat=9.5705&mlon=99.9957#map=14/9.5705/99.9957",
            "checked": GEOCODE_CHECKED,
            "note": ("GeoNames 6692479 'Mae Nam' (9.5691, 100.0033) files it under Nakhon Si "
                     "Thammarat, which is wrong: OSM places it in Ko Samui district, Surat "
                     "Thani (postcode 84330)."),
        },
        # official warning feeds that cover this place (see collectors.py)
        "warnings": {"tmd": True},
        # curated, sourced context shown in the matrix notes (never changes a score)
        "context": [
            {"dimension": "water",
             "text": ("Island supply: PWA put Koh Samui on rotating water supply from 3 "
                      "August 2026 after a long dry spell."),
             "sources": [{"title": "Bangkok Post, 29/07/2026 -- Koh Samui faces water "
                                   "rationing",
                          "url": "https://www.bangkokpost.com/thailand/general/3293479/"
                                 "koh-samui-faces-water-rationing"}]},
            {"dimension": "storms",
             "text": ("Tropical storms are rare this far south but do happen: Typhoon Gay "
                      "(November 1989, landfall in Chumphon) and Tropical Storm Pabuk "
                      "(January 2019, landfall at Pak Phanang), both about 135 km from "
                      "Maenam."),
             "sources": [{"title": "Wikipedia -- Typhoon Gay (1989)",
                          "url": "https://en.wikipedia.org/wiki/Typhoon_Gay_(1989)"},
                         {"title": "Wikipedia -- Tropical Storm Pabuk (2019)",
                          "url": "https://en.wikipedia.org/wiki/Tropical_Storm_Pabuk_(2019)"}]},
        ],
        "advisory_slugs": {"fcdo": "thailand", "state": "Thailand", "fr_diplomatie": "thailande"},
    },
    {
        "id": "saint_gatien",
        "name": "Saint-Gatien-des-Bois",
        "short_name": "Saint-Gatien",
        "admin": "Saint-Gatien-des-Bois, Lisieux arrondissement, Calvados (14), Normandy, France",
        "country": "France", "country_code": "FR",
        "lat": 49.3489, "lon": 0.1851, "elevation_m": 150.0, "timezone": "Europe/Paris",
        "role": "candidate",
        "coastal_hint": False,
        "geocode": {
            "source": "OpenStreetMap Nominatim (commune boundary) + GeoNames 2980046",
            "url": "https://www.openstreetmap.org/?mlat=49.3489&mlon=0.1851#map=13/49.3489/0.1851",
            "checked": GEOCODE_CHECKED,
            "note": "About 6 km south of Honfleur and 9 km east of Deauville, on the plateau.",
        },
        "warnings": {"meteoalarm": {"feed": "france", "areas": ["Calvados"]}},
        "advisory_slugs": {"fcdo": "france", "state": "France", "fr_diplomatie": None},
    },
    {
        "id": "gorokhovets",
        "name": "Gorokhovets",
        "short_name": "Gorokhovets",
        "admin": "Gorokhovets, Gorokhovetsky District, Vladimir Oblast, Russia",
        "country": "Russia", "country_code": "RU",
        "lat": 56.2066, "lon": 42.6790, "elevation_m": 84.0, "timezone": "Europe/Moscow",
        "role": "candidate",
        "coastal_hint": False,
        "geocode": {
            "source": "OpenStreetMap Nominatim (town) + GeoNames 559459 (PPLA2)",
            "url": "https://www.openstreetmap.org/?mlat=56.2066&mlon=42.6790#map=13/56.2066/42.6790",
            "checked": GEOCODE_CHECKED,
            "note": "On the Klyazma river; the town centre is on the right-bank hills.",
        },
        # Hydrometcenter of Russia bulletin: the oblast is named in the genitive
        # ("во Владимирской области"), so we match the stem.
        "warnings": {"hydromet_ru": {"stem": "Владимирск", "district": "Центральный"}},
        "advisory_slugs": {"fcdo": "russia", "state": "Russia", "fr_diplomatie": "russie"},
    },
]

# Advisory slugs for countries a user may add later (FCDO / US State title / France
# Diplomatie). Unknown countries get a best-effort FCDO slug and no France Diplomatie link.
ADVISORY_SLUGS: dict[str, dict] = {
    p["country_code"]: p["advisory_slugs"] for p in DEFAULT_PLACES
} | {
    "PT": {"fcdo": "portugal", "state": "Portugal", "fr_diplomatie": "portugal"},
    "ES": {"fcdo": "spain", "state": "Spain", "fr_diplomatie": "espagne"},
    "IT": {"fcdo": "italy", "state": "Italy", "fr_diplomatie": "italie"},
    "DE": {"fcdo": "germany", "state": "Germany", "fr_diplomatie": "allemagne"},
    "GB": {"fcdo": None, "state": "United Kingdom", "fr_diplomatie": "royaume-uni"},
    "VN": {"fcdo": "vietnam", "state": "Vietnam", "fr_diplomatie": "vietnam"},
    "MY": {"fcdo": "malaysia", "state": "Malaysia", "fr_diplomatie": "malaisie"},
    "ID": {"fcdo": "indonesia", "state": "Indonesia", "fr_diplomatie": "indonesie"},
    "GE": {"fcdo": "georgia", "state": "Georgia", "fr_diplomatie": "georgie"},
    "US": {"fcdo": "usa", "state": None, "fr_diplomatie": "etats-unis"},
}

# Meteoalarm legacy Atom feed slug per country (EUMETNET members publish there).
METEOALARM_FEEDS = {
    "FR": "france", "ES": "spain", "PT": "portugal", "IT": "italy", "DE": "germany",
    "BE": "belgium", "NL": "netherlands", "AT": "austria", "CH": "switzerland",
    "IE": "ireland", "GB": "united-kingdom", "NO": "norway", "SE": "sweden", "FI": "finland",
    "DK": "denmark", "PL": "poland", "CZ": "czechia", "GR": "greece", "HR": "croatia",
}


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40] or "place"


def _doc() -> dict:
    s = db.get_status(STATUS_KEY)
    if s is None:
        doc = {"places": deepcopy(DEFAULT_PLACES), "removed_defaults": []}
        db.set_status(STATUS_KEY, doc)
        return doc
    return s["value"]


def list_places() -> list[dict]:
    return _doc()["places"]


def get_place(pid: str) -> dict | None:
    return next((p for p in list_places() if p["id"] == pid), None)


def add_place(place: dict) -> dict:
    doc = _doc()
    ids = {p["id"] for p in doc["places"]}
    base = place.get("id") or slugify(place["name"])
    pid, i = base, 2
    while pid in ids:
        pid, i = f"{base}_{i}", i + 1
    place = {**place, "id": pid}
    doc["places"].append(place)
    if pid in doc.get("removed_defaults", []):
        doc["removed_defaults"].remove(pid)
    db.set_status(STATUS_KEY, doc)
    return place


def remove_place(pid: str) -> bool:
    doc = _doc()
    before = len(doc["places"])
    doc["places"] = [p for p in doc["places"] if p["id"] != pid]
    if len(doc["places"]) == before:
        return False
    if any(p["id"] == pid for p in DEFAULT_PLACES):
        doc.setdefault("removed_defaults", []).append(pid)
    db.set_status(STATUS_KEY, doc)
    # drop the cached per-place data
    with db._lock:
        c = db.conn()
        c.execute("DELETE FROM status WHERE key LIKE ?", (f"place:{pid}:%",))
        c.commit()
    return True


def build_user_place(geo: dict, elevation_m: float | None, role: str = "candidate") -> dict:
    """A place from an Open-Meteo geocoding result (+ the elevation API). Warning feeds and
    advisory slugs are derived from the country; nothing is invented for the rest."""
    cc = (geo.get("country_code") or "").upper()
    admin = ", ".join(x for x in (geo.get("name"), geo.get("admin3"), geo.get("admin2"),
                                  geo.get("admin1"), geo.get("country")) if x)
    warnings: dict = {}
    if cc in METEOALARM_FEEDS:
        areas = [a for a in (geo.get("admin2"), geo.get("admin1")) if a]
        warnings["meteoalarm"] = {"feed": METEOALARM_FEEDS[cc], "areas": areas}
    slugs = ADVISORY_SLUGS.get(cc) or {
        "fcdo": slugify(geo.get("country") or "").replace("_", "-") or None,
        "state": geo.get("country"), "fr_diplomatie": None}
    lat, lon = round(float(geo["latitude"]), 4), round(float(geo["longitude"]), 4)
    return {
        "name": geo["name"] if not geo.get("admin1") else f"{geo['name']}, {geo['admin1']}",
        "short_name": geo["name"],
        "admin": admin,
        "country": geo.get("country"), "country_code": cc or None,
        "lat": lat, "lon": lon,
        "elevation_m": elevation_m if elevation_m is not None else geo.get("elevation"),
        "timezone": geo.get("timezone") or "GMT",
        "role": role,
        "coastal_hint": None,
        "geocode": {
            "source": f"Open-Meteo geocoding (GeoNames {geo.get('id')}) + Open-Meteo elevation",
            "url": f"https://www.geonames.org/{geo.get('id')}" if geo.get("id") else None,
            "checked": db.now_iso()[:10],
            "note": "Added by search. Check the admin area above before relying on it.",
        },
        "warnings": warnings,
        "advisory_slugs": slugs,
        "added_by": "user",
        "added_at": db.now_iso(),
    }
