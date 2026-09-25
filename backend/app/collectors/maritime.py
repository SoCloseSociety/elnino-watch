"""Maritime sources: the equatorial Pacific buoys, coral bleaching stress, Samui waters.

All keyless, all verified live on 2026-09-24.

- tao_buoys        TAO/TRITON moorings (NOAA NDBC). The classic NDBC realtime2 files
                   (www.ndbc.noaa.gov/data/realtime2/<id>.txt) return 404 for every TAO
                   station and they are absent from latest_obs.txt. The PMEL ERDDAP copy
                   (pmelTaoDy*) lags by ~3 weeks. What IS live is the JSON API behind the
                   NDBC TAO station pages: tao.ndbc.noaa.gov/api/data.php?station=<id>
                   (10-minute data, last 5 days, UTC). Station list from activestations.xml.
- crw_vs           NOAA Coral Reef Watch 5 km Virtual Stations (daily SST, SST anomaly,
                   Degree Heating Weeks, Bleaching Alert Area) for the Gulf of Thailand
                   and the Thai Andaman coast.
- openmeteo_marine Open-Meteo Marine (waves + SST) for the waters off Koh Samui.

Parsers are pure functions (`parse_*`) so tests feed them real captured payloads.
"""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta

from .. import db
from .base import DAY, HOUR, Collector, RunContext, SourceChanged

# --------------------------------------------------------------------------- TAO/TRITON

NDBC_ACTIVE_URL = "https://www.ndbc.noaa.gov/activestations.xml"
TAO_DATA_URL = "https://tao.ndbc.noaa.gov/api/data.php"
TAO_STATION_PAGE = "https://tao.ndbc.noaa.gov/station.php?station={id}"
# A sensor deeper than this is not a sea-surface temperature any more.
TAO_SST_MAX_DEPTH_M = 5
TAO_HISTORY_HOURS = 5 * 24  # the API always returns ~5 days; we keep the hourly marks


def parse_active_tao(xml_text: str) -> list[dict]:
    """activestations.xml -> [{id, name, lat, lon}] for type="tao"."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise SourceChanged(f"activestations.xml is not XML: {e}") from e
    out = []
    for st in root.iter("station"):
        if st.get("type") != "tao":
            continue
        try:
            out.append({"id": st.get("id"), "name": st.get("name"),
                        "lat": float(st.get("lat")), "lon": float(st.get("lon"))})
        except (TypeError, ValueError):
            continue
    if not out:
        raise SourceChanged("activestations.xml lists no type=\"tao\" station")
    return out


def _tao_ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)


def _latest(meas: dict | None) -> tuple[str, float] | None:
    """Most recent (ts ISO UTC, value) of a measurement, skipping nulls."""
    if not meas:
        return None
    best = None
    for k, v in (meas.get("obs") or {}).items():
        if v is None:
            continue
        try:
            t = _tao_ts(k)
        except ValueError:
            continue
        if best is None or t > best[0]:
            best = (t, float(v))
    return (best[0].isoformat(), best[1]) if best else None


def parse_tao_station(payload: dict) -> dict:
    """data.php JSON -> {sst_depth, sst_hourly: [(ts, v)], sst, air_temp, wind, wind_dir,
    observed_at}. Values are None when the buoy has no such sensor reporting."""
    if not isinstance(payload, dict) or "meas" not in payload:
        raise SourceChanged("TAO data.php: no 'meas' key")
    if payload.get("errormsg"):
        raise SourceChanged(f"TAO data.php error: {payload['errormsg']}")
    meas = payload.get("meas") or []

    def pick(mtype: str) -> dict | None:
        c = [m for m in meas if m.get("meas_type") == mtype and m.get("obs")]
        return min(c, key=lambda m: m.get("mooring_depth") or 0) if c else None

    wt = [m for m in meas if m.get("meas_type") == "WATER TEMPERATURE" and m.get("obs")
          and m.get("mooring_depth") is not None and m["mooring_depth"] <= TAO_SST_MAX_DEPTH_M]
    sst_m = min(wt, key=lambda m: m["mooring_depth"]) if wt else None
    hourly = []
    if sst_m:
        for k, v in sst_m["obs"].items():
            if v is None or not k.endswith(":00:00"):
                continue
            try:
                hourly.append((_tao_ts(k).isoformat(), float(v)))
            except ValueError:
                continue
        hourly.sort()
    sst = _latest(sst_m)
    air = _latest(pick("AIR TEMPERATURE"))
    wind = _latest(pick("WIND SPEED"))
    wdir = _latest(pick("WIND DIRECTION"))
    return {
        "sst_depth": sst_m["mooring_depth"] if sst_m else None,
        "sst_hourly": hourly[-TAO_HISTORY_HOURS:],
        "sst": sst[1] if sst else None,
        "air_temp": air[1] if air else None,
        "wind": wind[1] if wind else None,
        "wind_dir": wdir[1] if wdir else None,
        "observed_at": sst[0] if sst else (air or wind or (None, None))[0],
    }


class TaoBuoys(Collector):
    name = "tao_buoys"
    freshness_basis = "observations"
    max_age_s = 12 * HOUR  # hourly buoy data
    title = "TAO/TRITON buoys (equatorial Pacific)"
    category = "maritime"
    provider = "NOAA NDBC / PMEL (Global Tropical Moored Buoy Array)"
    homepage = "https://tao.ndbc.noaa.gov/"
    endpoint = TAO_DATA_URL + "?station=32303"
    interval_s = 3 * 3600
    description = ("Surface temperature (sensor <= 5 m), air and wind from the ~48 moored "
                   "buoys of the equatorial Pacific, El Nino's front line. 10-min data, "
                   "hourly points are kept.")
    concurrency = 3

    async def collect(self, ctx: RunContext) -> int:
        stations = parse_active_tao((await ctx.get(NDBC_ACTIVE_URL)).text)
        sem = asyncio.Semaphore(self.concurrency)

        async def one(st: dict) -> tuple[dict, dict | None, str | None]:
            async with sem:
                try:
                    r = await ctx.client.get(TAO_DATA_URL, params={"station": st["id"]})
                    r.raise_for_status()
                    return st, parse_tao_station(r.json()), None
                except Exception as e:  # noqa: BLE001 -- one buoy must not sink the array
                    return st, None, f"{type(e).__name__}: {e}"[:160]

        results = await asyncio.gather(*(one(s) for s in stations))
        rows, status, failed, no_sst = [], [], {}, []
        for st, res, err in results:
            if err:
                failed[st["id"]] = err
                continue
            doc = {**st, "sst": res["sst"], "sst_depth_m": res["sst_depth"],
                   "air_temp": res["air_temp"], "wind": res["wind"], "wind_dir": res["wind_dir"],
                   "observed_at": res["observed_at"],
                   "url": TAO_STATION_PAGE.format(id=st["id"])}
            status.append(doc)
            if not res["sst_hourly"]:
                no_sst.append(st["id"])
                continue
            meta = {"depth_m": res["sst_depth"], "lat": st["lat"], "lon": st["lon"],
                    "name": st["name"]}
            rows += [{"series": f"tao_{st['id']}_sst", "ts": ts, "value": v, "unit": "degC",
                      "meta": meta} for ts, v in res["sst_hourly"]]
        if not status:
            raise SourceChanged(f"every TAO station failed: {list(failed.values())[:3]}")
        ctx.last_status = 200
        ctx.notes = {"stations": len(stations), "with_sst": len(status) - len(no_sst),
                     "no_sst": no_sst, "failed": failed}
        db.set_status("tao_buoys", sorted(status, key=lambda s: s["id"]))
        return db.upsert_observations(self.name, rows)


# --------------------------------------------------------------------------- Coral Reef Watch

CRW_VS_URL = "https://coralreefwatch.noaa.gov/product/vs/data/{station}.txt"
CRW_VS_PAGE = "https://coralreefwatch.noaa.gov/product/vs/gauges/{station}.php"
# Station file names verified 2026-09-24 (the VS index pages were 503, the data files 200).
CRW_STATIONS = ("west_gulf_of_thailand", "east_gulf_of_thailand", "southwestern_thailand")
CRW_HISTORY_DAYS = 365
# Bleaching Alert Area (7-day max), CRW v3.1 incl. the Dec 2023 Alert Level 3-5 extension.
BAA_LABELS = {0: "No Stress", 1: "Bleaching Watch", 2: "Bleaching Warning",
              3: "Alert Level 1", 4: "Alert Level 2", 5: "Alert Level 3",
              6: "Alert Level 4", 7: "Alert Level 5"}


def parse_crw_vs(text: str) -> dict:
    """CRW virtual-station text file -> {name, lat, lon, mmm, rows: [...]}."""
    lines = text.splitlines()

    def after(label: str) -> str | None:
        for i, ln in enumerate(lines):
            if ln.strip().rstrip(":") == label and i + 1 < len(lines):
                return lines[i + 1].strip()
        return None

    try:
        hdr = next(i for i, ln in enumerate(lines) if ln.startswith("YYYY MM DD"))
    except StopIteration as e:
        raise SourceChanged("CRW VS file: no 'YYYY MM DD' header") from e
    cols = lines[hdr].split()
    need = ["SST@90th_HS", "SSTA@90th_HS", "DHW_from_90th_HS>1", "BAA_7day_max"]
    if any(c not in cols for c in need):
        raise SourceChanged(f"CRW VS columns changed: {cols}")
    ix = {c: cols.index(c) for c in cols}
    rows = []
    for ln in lines[hdr + 1:]:
        p = ln.split()
        if len(p) != len(cols):
            continue
        try:
            rows.append({
                "date": date(int(p[0]), int(p[1]), int(p[2])).isoformat(),
                "sst": float(p[ix["SST@90th_HS"]]),
                "ssta": float(p[ix["SSTA@90th_HS"]]),
                "dhw": float(p[ix["DHW_from_90th_HS>1"]]),
                "alert": int(float(p[ix["BAA_7day_max"]])),
            })
        except ValueError:
            continue
    if not rows:
        raise SourceChanged("CRW VS file has no data rows")
    try:
        lat = float(after("Polygon Middle Latitude"))
        lon = float(after("Polygon Middle Longitude"))
        mmm = float(after("Averaged Maximum Monthly Mean"))
    except (TypeError, ValueError) as e:
        raise SourceChanged("CRW VS header (lat/lon/MMM) missing") from e
    return {"name": after("Name"), "lat": lat, "lon": lon, "mmm": mmm, "rows": rows}


class CoralReefWatch(Collector):
    name = "crw_vs"
    freshness_basis = "observations"
    max_age_s = 4 * DAY  # daily product, one day behind
    title = "Coral Reef Watch -- heat stress (Gulf of Thailand)"
    category = "maritime"
    provider = "NOAA Coral Reef Watch (5 km Virtual Stations v3.1)"
    homepage = "https://coralreefwatch.noaa.gov/product/vs/"
    endpoint = CRW_VS_URL.format(station=CRW_STATIONS[0])
    interval_s = 12 * 3600
    description = ("SST, anomaly, Degree Heating Weeks and bleaching alert level for the "
                   "western and eastern Gulf of Thailand (Samui is in the western station) "
                   "and the Andaman coast. Daily product, one day behind.")

    async def collect(self, ctx: RunContext) -> int:
        cutoff = (datetime.now(UTC).date() - timedelta(days=CRW_HISTORY_DAYS)).isoformat()
        rows, status, events, failed = [], [], [], {}
        for st in CRW_STATIONS:
            url = CRW_VS_URL.format(station=st)
            try:
                vs = parse_crw_vs((await ctx.get(url)).text)
            except Exception as e:  # noqa: BLE001 -- keep the other stations
                failed[st] = f"{type(e).__name__}: {e}"[:160]
                continue
            meta = {"station": vs["name"], "lat": vs["lat"], "lon": vs["lon"]}
            for r in vs["rows"]:
                if r["date"] < cutoff:
                    continue
                rows += [
                    {"series": f"crw_{st}_sst", "ts": r["date"], "value": r["sst"],
                     "unit": "degC", "meta": meta},
                    {"series": f"crw_{st}_ssta", "ts": r["date"], "value": r["ssta"],
                     "unit": "degC", "meta": meta},
                    {"series": f"crw_{st}_dhw", "ts": r["date"], "value": r["dhw"],
                     "unit": "degC-weeks", "meta": meta},
                    {"series": f"crw_{st}_alert", "ts": r["date"], "value": r["alert"],
                     "unit": "level", "meta": {**meta, "label": BAA_LABELS.get(r["alert"])}},
                ]
            last = vs["rows"][-1]
            doc = {"station": st, "name": vs["name"], "lat": vs["lat"], "lon": vs["lon"],
                   "date": last["date"], "sst": last["sst"], "ssta": last["ssta"],
                   "dhw": last["dhw"], "alert": last["alert"],
                   "alert_label": BAA_LABELS.get(last["alert"], str(last["alert"])),
                   "mmm": vs["mmm"], "url": url, "page": CRW_VS_PAGE.format(station=st)}
            status.append(doc)
            if last["alert"] >= 1:
                events.append({
                    "ext_id": st, "category": "bleaching",
                    "title": f"{vs['name']}: {doc['alert_label']} (DHW {last['dhw']:.1f})",
                    "url": doc["page"],
                    "severity": "red" if last["alert"] >= 3 else
                                "orange" if last["alert"] == 2 else "info",
                    "lat": vs["lat"], "lon": vs["lon"], "updated_at": last["date"],
                    "geometry": {"type": "Point", "coordinates": [vs["lon"], vs["lat"]]},
                    "payload": doc,
                })
        if not status:
            raise SourceChanged(f"every CRW station failed: {failed}")
        ctx.notes = {"failed": failed} if failed else {}
        db.set_status("crw_bleaching", status)
        # "no station in alert" is a legitimate empty list; a station that failed to
        # answer keeps its previous event instead of vanishing from the map.
        db.replace_events(self.name, events, allow_empty=True,
                          scope_ext_ids=[s["station"] for s in status])
        return db.upsert_observations(self.name, rows)


# --------------------------------------------------------------------------- Open-Meteo Marine

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
# Open water off Samui's east coast (the island cell itself has no sea state).
SAMUI_SEA_LAT, SAMUI_SEA_LON = 9.5, 100.1


def parse_marine(payload: dict, today: date | None = None) -> dict:
    """Open-Meteo marine JSON -> {rows (daily series), now, next_72h, grid}."""
    h, d = payload.get("hourly"), payload.get("daily")
    if not isinstance(h, dict) or not isinstance(d, dict):
        raise SourceChanged("marine response lacks hourly/daily blocks")
    need_h = ["time", "wave_height", "sea_surface_temperature", "swell_wave_height"]
    if any(k not in h for k in need_h) or "wave_height_max" not in d:
        raise SourceChanged("marine response lacks expected variables")
    today = today or (datetime.now(UTC) + timedelta(hours=7)).date()  # rows are Bangkok days
    grid = [payload.get("latitude"), payload.get("longitude")]
    by_day: dict[str, dict[str, list[float]]] = {}
    for i, t in enumerate(h["time"]):
        day = by_day.setdefault(t[:10], {"sst": [], "swell": []})
        if h["sea_surface_temperature"][i] is not None:
            day["sst"].append(h["sea_surface_temperature"][i])
        if h["swell_wave_height"][i] is not None:
            day["swell"].append(h["swell_wave_height"][i])
    rows = []
    for i, ts in enumerate(d["time"]):
        meta = {"forecast": ts > today.isoformat(), "grid": grid, "tz": "Asia/Bangkok"}
        if d["wave_height_max"][i] is not None:
            rows.append({"series": "samui_wave_height", "ts": ts, "unit": "m", "meta": meta,
                         "value": float(d["wave_height_max"][i])})
        day = by_day.get(ts) or {}
        if day.get("sst"):
            rows.append({"series": "samui_sst", "ts": ts, "unit": "degC", "meta": meta,
                         "value": round(sum(day["sst"]) / len(day["sst"]), 2)})
        if day.get("swell"):
            rows.append({"series": "samui_swell_height", "ts": ts, "unit": "m", "meta": meta,
                         "value": max(day["swell"])})
    if not rows:
        raise SourceChanged("marine response has no values")
    hourly = [{"time": t, "wave_height": h["wave_height"][i],
               "sst": h["sea_surface_temperature"][i], "swell": h["swell_wave_height"][i],
               "wave_period": (h.get("wave_period") or [None] * len(h["time"]))[i]}
              for i, t in enumerate(h["time"])]
    return {"rows": rows, "grid": grid, "hourly": hourly}


class OpenMeteoMarine(Collector):
    name = "openmeteo_marine"
    freshness_basis = "run"
    max_age_s = 3 * HOUR  # forecast: its dates run ahead, the fetch time is what ages
    title = "Sea around Koh Samui (waves, swell, SST)"
    category = "maritime"
    provider = "Open-Meteo Marine (MeteoFrance MFWAM / ECMWF WAM, SST)"
    homepage = "https://open-meteo.com/en/docs/marine-weather-api"
    endpoint = MARINE_URL
    interval_s = 3600
    description = ("Max wave height, swell and sea surface temperature off Samui, "
                   "past 7 days + 7-day forecast (daily values).")

    async def collect(self, ctx: RunContext) -> int:
        r = await ctx.get(MARINE_URL, params={
            "latitude": SAMUI_SEA_LAT, "longitude": SAMUI_SEA_LON,
            "hourly": "wave_height,sea_surface_temperature,swell_wave_height,wave_period",
            "daily": "wave_height_max", "timezone": "Asia/Bangkok",
            "past_days": 7, "forecast_days": 7,
        })
        res = parse_marine(r.json())
        now_local = datetime.now(UTC) + timedelta(hours=7)
        key = now_local.strftime("%Y-%m-%dT%H:00")
        upcoming = [x for x in res["hourly"] if x["time"] >= key][:72]
        waves = [x["wave_height"] for x in upcoming if x["wave_height"] is not None]
        db.set_status("samui_marine", {
            "grid": res["grid"], "now": upcoming[0] if upcoming else None,
            "max_wave_next_72h": max(waves) if waves else None,
            "next_72h": upcoming, "url": "https://open-meteo.com/en/docs/marine-weather-api",
            "tz": "Asia/Bangkok",
        })
        return db.upsert_observations(self.name, res["rows"])


COLLECTORS = [TaoBuoys, CoralReefWatch, OpenMeteoMarine]
