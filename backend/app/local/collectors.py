"""Koh Samui local collectors (all keyless, all verified live on 2026-09-24).

- openmeteo_samui          Open-Meteo forecast: 16-day forecast + 92 past days (model analyses)
- openmeteo_samui_era5     Open-Meteo ERA5 archive: last 200 days + the 1991-2020 climatology
                           (computed ONCE, cached in status `samui_climatology`)
- openmeteo_samui_air      Open-Meteo air quality (CAMS): PM2.5, PM10, US AQI, hourly
- openmeteo_samui_seasonal Open-Meteo seasonal (ECMWF SEAS5): monthly anomalies, 6 months
- thaiwater_samui_rain     ThaiWater (HII) rain gauges on Ko Samui district, observed 24 h rain
- thaiwater_dams           ThaiWater (RID) large dams: Ratchaprapa (Surat Thani) storage
- tmd_warnings             Thai Meteorological Department warning bulletins (RSS)
- pwa_samui_notices        PWA Ko Samui branch water-interruption notices (JSON API)

Gap (checked 2026-09-24): no keyless machine-readable source publishes the levels of
Samui's own reservoirs or the PWA Samui rotation schedule. ThaiWater `waterlevel_load`
(province 84) has no Ko Samui station (river levels on the mainland only); the RID
medium-reservoir API (app.rid.go.th/reservoir/api/rsvmiddles, region "s") lists no
reservoir on the island (the Surat Thani ones, Bang Sai Nuan and Khlong Suan Nang, are
on the mainland); PWA branch pages / Facebook are not machine-readable. The water
factor says so explicitly.

Every value stored came from a real response. Parsers are pure functions
(`parse_*`) so tests can feed them real captured payloads.
"""

from __future__ import annotations

import re
import ssl
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import certifi
import httpx

from .. import db
from ..collectors.base import Collector, RunContext, SourceChanged
from ..config import settings

BKK = ZoneInfo("Asia/Bangkok")

# The home is on the coast. Open-Meteo's DEM cell for Samui is the island's
# 457 m interior; `elevation=10` makes it downscale temperatures to sea level
# (lapse-rate correction) instead of reporting hill-top temperatures.
HOME_ELEVATION_M = 10

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
SEASONAL_URL = "https://seasonal-api.open-meteo.com/v1/seasonal"
THAIWATER_RAIN_URL = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/rain_24h"
THAIWATER_MAIN_URL = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/thailand_main"
# The large-dam table alone (RID daily report). thailand_main carries the same dam rows
# inside a ~10.7 MB page-wide document (measured 2026-09-24); dam_load is ~0.5 MB.
THAIWATER_DAMS_URL = "https://api-v3.thaiwater.net/api/v1/thaiwater30/analyst/dam_load"
TMD_STORM_URL = "https://www.tmd.go.th/api/xml/storm-tracking"

CLIM_START, CLIM_END = "1991-01-01", "2020-12-31"

# Open-Meteo daily variable -> (our series, unit)
FORECAST_DAILY = {
    "temperature_2m_max": ("samui_temp_max", "degC"),
    "temperature_2m_min": ("samui_temp_min", "degC"),
    "apparent_temperature_max": ("samui_apparent_temp_max", "degC"),
    "precipitation_sum": ("samui_precip", "mm"),
    "precipitation_probability_max": ("samui_precip_prob", "%"),
    "wind_gusts_10m_max": ("samui_wind_gust_max", "km/h"),
    "uv_index_max": ("samui_uv_max", "index"),
}
ERA5_DAILY = {
    "precipitation_sum": ("samui_era5_precip", "mm"),
    "temperature_2m_max": ("samui_era5_temp_max", "degC"),
    "temperature_2m_min": ("samui_era5_temp_min", "degC"),
    "apparent_temperature_max": ("samui_era5_apparent_temp_max", "degC"),
}
AIR_HOURLY = {
    "pm2_5": ("samui_pm2_5", "ug/m3"),
    "pm10": ("samui_pm10", "ug/m3"),
    "us_aqi": ("samui_us_aqi", "US AQI"),
}


def _home_params() -> dict:
    return {"latitude": settings.home_lat, "longitude": settings.home_lon,
            "elevation": HOME_ELEVATION_M}


def today_bkk() -> date:
    return datetime.now(BKK).date()


def archive_end_date(local_today: date | None = None) -> date:
    """Latest `end_date` the Open-Meteo archive accepts: it refuses any date after TODAY IN
    UTC ("end_date is out of allowed range from 1940-01-01 to <UTC today>", verified
    2026-09-24 at 17:21 UTC = 00:21 ICT). A local (ICT, UTC+7) day therefore cannot be asked
    for between 00:00 and 07:00 Samui time; the previous code did, and every ERA5 request
    failed nightly for those hours."""
    return min(local_today or today_bkk(), datetime.now(UTC).date())


# --------------------------------------------------------------------------- parsers

def parse_daily(payload: dict, mapping: dict, today: date | None = None) -> list[dict]:
    """Open-Meteo `daily` block -> observation rows. Null values are skipped
    (Open-Meteo returns nulls for days a model does not cover): never stored as 0."""
    daily = payload.get("daily")
    if not isinstance(daily, dict) or "time" not in daily:
        raise SourceChanged("Open-Meteo response has no daily.time")
    missing = [k for k in mapping if k not in daily]
    if missing:
        raise SourceChanged(f"Open-Meteo daily lacks {missing}")
    rows = []
    for i, ts in enumerate(daily["time"]):
        d = date.fromisoformat(ts)
        for var, (series, unit) in mapping.items():
            v = daily[var][i]
            if v is None:
                continue
            meta = None
            if today is not None:
                meta = {"forecast": d > today}
            rows.append({"series": series, "ts": ts, "value": float(v), "unit": unit,
                         "meta": meta})
    return rows


def parse_hourly_utc(payload: dict, mapping: dict, now: datetime | None = None) -> list[dict]:
    """Open-Meteo `hourly` block requested with timezone=GMT -> rows with UTC ts."""
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict) or "time" not in hourly:
        raise SourceChanged("Open-Meteo response has no hourly.time")
    if payload.get("utc_offset_seconds", 0) != 0:
        raise SourceChanged("expected hourly data in GMT")
    now = now or datetime.now(UTC)
    rows = []
    for i, ts in enumerate(hourly["time"]):
        t = datetime.fromisoformat(ts).replace(tzinfo=UTC)
        for var, (series, unit) in mapping.items():
            v = (hourly.get(var) or [None] * (i + 1))[i]
            if v is None:
                continue
            rows.append({"series": series, "ts": t.isoformat(), "value": float(v),
                         "unit": unit, "meta": {"forecast": t > now}})
    return rows


CLIM_NOTE = ("ERA5 is a ~30 km reanalysis: it underestimates the rain measured at "
             "Samui's stations. Anomalies are computed ERA5 against ERA5, so the bias "
             "cancels out.")


def build_climatology(payload: dict) -> dict:
    """ERA5 1991-2020 daily -> day-of-year normals.

    For each calendar day (MM-DD, Feb 29 folded into Feb 28) we average the
    30 years, then smooth with a centered circular window (31 days for rain,
    which is very noisy day to day; 15 days for temperatures). Returns a compact
    dict {"days": {"MM-DD": [precip_mm, tmax, tmin, apparent_tmax]}, ...}.
    """
    daily = payload.get("daily") or {}
    need = ["time", "precipitation_sum", "temperature_2m_max", "temperature_2m_min",
            "apparent_temperature_max"]
    if any(k not in daily for k in need):
        raise SourceChanged("ERA5 archive lacks expected daily variables")
    acc: dict[str, list[list[float]]] = {}
    for i, ts in enumerate(daily["time"]):
        key = ts[5:10]
        if key == "02-29":
            key = "02-28"
        vals = [daily[k][i] for k in need[1:]]
        if any(v is None for v in vals):
            continue
        acc.setdefault(key, []).append(vals)
    ref = [(date(2001, 1, 1) + timedelta(days=i)).strftime("%m-%d") for i in range(365)]
    if len(acc) < 360:
        raise SourceChanged(f"ERA5 climatology incomplete ({len(acc)} calendar days)")
    raw = []
    for k in ref:
        rows = acc.get(k) or []
        raw.append([sum(r[j] for r in rows) / len(rows) for j in range(4)] if rows else None)

    def smooth(j: int, half: int) -> list[float]:
        out = []
        for i in range(365):
            window = [raw[(i + o) % 365] for o in range(-half, half + 1)]
            vals = [w[j] for w in window if w is not None]
            out.append(sum(vals) / len(vals))
        return out

    p, tx, tn, ax = smooth(0, 15), smooth(1, 7), smooth(2, 7), smooth(3, 7)
    days = {k: [round(p[i], 2), round(tx[i], 2), round(tn[i], 2), round(ax[i], 2)]
            for i, k in enumerate(ref)}
    years = {ts[:4] for ts in daily["time"]}
    return {
        "source": "Open-Meteo ERA5 archive (ECMWF ERA5 reanalysis)",
        "url": ARCHIVE_URL,
        "period": f"{min(years)}-{max(years)}",
        "grid": {"lat": payload.get("latitude"), "lon": payload.get("longitude"),
                 "elevation": payload.get("elevation")},
        "fields": ["precip_mm", "temp_max", "temp_min", "apparent_temp_max"],
        "smoothing": "circular running mean: 31 d (precip), 15 d (temperatures)",
        "annual_precip_mm": round(sum(p), 1),
        "note": CLIM_NOTE,
        "days": days,
    }


def parse_seasonal_monthly(payload: dict) -> dict:
    m = payload.get("monthly")
    need = ["time", "precipitation_mean", "precipitation_anomaly", "temperature_2m_mean",
            "temperature_2m_anomaly"]
    if not isinstance(m, dict) or any(k not in m for k in need):
        raise SourceChanged("seasonal response lacks monthly variables")
    months = []
    for i, ts in enumerate(m["time"]):
        pm, pa = m["precipitation_mean"][i], m["precipitation_anomaly"][i]
        tm, ta = m["temperature_2m_mean"][i], m["temperature_2m_anomaly"][i]
        if pm is None and tm is None:
            continue
        pct = None
        # anomaly is relative to the model's own climate: model normal = mean - anomaly
        if pm is not None and pa is not None and (pm - pa) > 0:
            pct = round(100.0 * pm / (pm - pa), 0)
        months.append({"month": ts[:7], "precip_mean_mm": pm, "precip_anomaly_mm": pa,
                       "precip_pct_of_model_normal": pct, "temp_mean_c": tm,
                       "temp_anomaly_c": ta})
    if not months:
        raise SourceChanged("seasonal response has no months")
    return {
        "model": "ECMWF SEAS5 (ensemble mean, via Open-Meteo)",
        "url": "https://open-meteo.com/en/docs/seasonal-forecast-api",
        "grid": {"lat": payload.get("latitude"), "lon": payload.get("longitude")},
        "months": months,
    }


def _bkk_to_utc(s: str) -> str:
    fmt = "%Y-%m-%d %H:%M" if len(s) <= 16 else "%Y-%m-%d %H:%M:%S"
    return datetime.strptime(s, fmt).replace(tzinfo=BKK).astimezone(UTC).isoformat()


def parse_thaiwater_samui_rain(payload: dict) -> dict | None:
    """ThaiWater rain_24h (province 84) -> the Ko Samui district gauges.
    Returns {ts (UTC, latest reading), value (max 24 h rain across gauges), stations}."""
    if payload.get("result") != "OK" or not isinstance(payload.get("data"), list):
        raise SourceChanged("thaiwater rain_24h: unexpected payload")
    stations = []
    for x in payload["data"]:
        geo = x.get("geocode") or {}
        if (geo.get("amphoe_name") or {}).get("en") != "Ko Samui District":
            continue
        if x.get("rain_24h") is None or not x.get("rainfall_datetime"):
            continue
        st = x.get("station") or {}
        name = st.get("tele_station_name") or {}
        stations.append({
            "name": name.get("en") or name.get("th"),
            "tambon": (geo.get("tumbon_name") or {}).get("en"),
            "agency": ((x.get("agency") or {}).get("agency_shortname") or {}).get("en"),
            "lat": st.get("tele_station_lat"), "lon": st.get("tele_station_long"),
            "rain_24h": float(x["rain_24h"]), "at": _bkk_to_utc(x["rainfall_datetime"]),
        })
    if not stations:
        return None
    # ignore gauges whose last report is > 6 h older than the freshest one (offline)
    latest = max(datetime.fromisoformat(s["at"]) for s in stations)
    stations = [s for s in stations
                if latest - datetime.fromisoformat(s["at"]) <= timedelta(hours=6)]
    return {"ts": max(s["at"] for s in stations),
            "value": max(s["rain_24h"] for s in stations), "stations": stations}


def parse_thaiwater_dams(payload: dict, names: tuple[str, ...] = ("Ratchaprapa",)) -> list[dict]:
    """Large-dam rows -> the named dams. Accepts both ThaiWater shapes: `analyst/dam_load`
    (dam_data.data, ~0.5 MB, what the collector fetches) and the 10 MB `public/thailand_main`
    (dam.data.data). EGAT duplicates of RID dams are skipped; one row per dam (newest)."""
    rows = None
    if isinstance(payload, dict):
        if isinstance(payload.get("dam_data"), dict):
            rows = payload["dam_data"].get("data")
        elif isinstance(payload.get("dam"), dict):
            rows = ((payload["dam"].get("data") or {}).get("data")
                    if isinstance(payload["dam"].get("data"), dict) else None)
    if not isinstance(rows, list):
        raise SourceChanged("thaiwater dams: no dam_data.data (dam_load) / dam.data.data")
    out: dict[str, dict] = {}
    for x in rows:
        dam = x.get("dam") or {}
        en = (dam.get("dam_name") or {}).get("en")
        if en not in names or x.get("dam_storage_percent") is None:
            continue
        agency = ((x.get("agency") or {}).get("agency_shortname") or {}).get("en")
        if agency and agency != "RID":
            continue
        prev = out.get(en)
        if prev and (prev["date"] or "") >= (x.get("dam_date") or ""):
            continue
        out[en] = ({
            "name": en, "date": x.get("dam_date"),
            "storage_pct": float(x["dam_storage_percent"]),
            "storage_mcm": x.get("dam_storage"),
            "usable_pct": x.get("dam_uses_water_percent"),
            "inflow_mcm": x.get("dam_inflow"),
            "inflow_acc_pct_of_avg": x.get("dam_inflow_acc_percent"),
            "province": ((x.get("geocode") or {}).get("province_name") or {}).get("en"),
            "lat": dam.get("dam_lat"), "lon": dam.get("dam_long"),
        })
    return list(out.values())


# TMD bulletins are Thai-language. We only classify with explicit keywords:
TH_SOUTH = "ภาคใต้"
TH_SOUTH_WEST = "ภาคใต้ฝั่งตะวันตก"      # Andaman side (not Samui)
TH_SOUTH_EAST = "ภาคใต้ฝั่งตะวันออก"     # Gulf side (Samui)
TH_GULF = "อ่าวไทย"                       # Gulf of Thailand
TH_SURAT = "สุราษฎร์ธานี"
TH_SAMUI = "สมุย"
TH_HEAVY_RAIN = "ฝนตกหนัก"
TH_WAVES = "คลื่นลมแรง"
TH_STORM = "พายุ"
TH_ANDAMAN = "อันดามัน"                  # Andaman Sea (west coast, not Samui)
TH_SMALL_BOATS = "เรือเล็ก"               # "small boats ..."
TH_STAY_ASHORE = "งดออกจากฝั่ง"           # "... should stay ashore"
# "คลื่นสูง 2-3 เมตร" / "คลื่นสูงกว่า 3 เมตร" (waves 2-3 m / higher than 3 m)
_TH_WAVE_M = re.compile(r"คลื่น(?:ลม)?(?:จะ)?(?:มี)?สูง\s*(?:กว่า|ประมาณ)?\s*(\d+(?:\.\d+)?)"
                        r"(?:\s*(?:-|–|ถึง)\s*(\d+(?:\.\d+)?))?\s*เมตร")
TH_MONTHS = {m: i + 1 for i, m in enumerate([
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม",
    "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"])}


def _tmd_until(title: str) -> date | None:
    """'(... จนถึงวันที่ 27 กันยายน 2569)' or '(... วันที่ 23 - 27 กันยายน 2569)'
    -> last day of effect (Buddhist era -> CE)."""
    months = "|".join(TH_MONTHS)
    m = re.search(rf"(\d{{1,2}})\s*({months})\s*(25\d\d)", title)
    if not m:
        return None
    try:
        return date(int(m.group(3)) - 543, TH_MONTHS[m.group(2)], int(m.group(1)))
    except ValueError:
        return None


TH_MONTH_ABBR = {"ม.ค.": 1, "ก.พ.": 2, "มี.ค.": 3, "เม.ย.": 4, "พ.ค.": 5, "มิ.ย.": 6,
                 "ก.ค.": 7, "ส.ค.": 8, "ก.ย.": 9, "ต.ค.": 10, "พ.ย.": 11, "ธ.ค.": 12}
_TH_MON_ANY = "|".join(re.escape(m) for m in sorted(list(TH_MONTHS) + list(TH_MONTH_ABBR),
                                                   key=len, reverse=True))
# "วันที่ 24 – 27 ก.ย. 69", "วันที่ 23 - 27 กันยายน 2569", "วันที่ 30 ก.ย. - 2 ต.ค. 69"
_TH_PERIOD = re.compile(rf"วันที่\s*(\d{{1,2}})\s*({_TH_MON_ANY})?\s*(?:–|-|ถึง)\s*"
                        rf"(\d{{1,2}})\s*({_TH_MON_ANY})\s*(\d{{2,4}})")
_TH_BULLETIN_NO = re.compile(r"ฉบับที่\s*(\d+)")
# Thai region names -> English, longest first (several contain each other)
TH_REGIONS = (("ภาคตะวันออกเฉียงเหนือตอนล่าง", "lower Northeast"),
              ("ภาคตะวันออกเฉียงเหนือ", "Northeast"), ("ภาคใต้ฝั่งตะวันออก",
                                                     "South (Gulf coast)"),
              ("ภาคใต้ฝั่งตะวันตก", "South (Andaman coast)"), ("ภาคตะวันออก", "East"),
              ("ภาคเหนือ", "North"), ("ภาคกลาง", "Central"), ("กรุงเทพมหานคร", "Bangkok"),
              ("ภาคใต้", "South"), ("อ่าวไทย", "Gulf of Thailand"),
              ("ทะเลอันดามัน", "Andaman Sea"), (TH_SURAT, "Surat Thani"),
              (TH_SAMUI, "Samui"))


def _th_month(s: str) -> int:
    return TH_MONTHS.get(s) or TH_MONTH_ABBR[s]


def tmd_period(title: str, desc: str) -> tuple[str, str] | None:
    """Stated period of effect of a TMD bulletin (first match in description, then title)
    -> (start, end) ISO dates (Buddhist era -> CE; '69' = 2569 BE = 2026)."""
    for text in (desc, title):
        m = _TH_PERIOD.search(text or "")
        if not m:
            continue
        y = int(m.group(5))
        y = (y + 2500 if y < 100 else y) - 543
        try:
            end = date(y, _th_month(m.group(4)), int(m.group(3)))
            sm = _th_month(m.group(2)) if m.group(2) else end.month
            start = date(y - (sm > end.month), sm, int(m.group(1)))
        except (ValueError, KeyError):
            continue
        return start.isoformat(), end.isoformat()
    return None


def tmd_summary_en(item: dict) -> str:
    """English one-liner for a (Thai) TMD bulletin, built only from explicit keywords:
    'TMD bulletin No. 7 (223/2569): heavy to very heavy rain -- North, ..., South;
    24-27 Sep 2026'. Pure, so it also works on status rows stored by older code."""
    title, desc = item.get("title") or "", item.get("description") or ""
    text = f"{title} {desc}"
    hz = []
    if "ฝนตกหนักถึงหนักมาก" in text:
        hz.append("heavy to very heavy rain")
    elif TH_HEAVY_RAIN in text:
        hz.append("heavy rain")
    if TH_WAVES in text:
        hz.append("strong winds and high waves")
    if TH_STORM in title:
        hz.append("storm")
    work, regions = text, []
    for th, en in TH_REGIONS:
        i = work.find(th)
        if i >= 0:
            regions.append((i, en))
            work = work.replace(th, " " * len(th))
    regions = [en for _, en in sorted(regions)]
    no = _TH_BULLETIN_NO.search(title)
    per = tmd_period(title, desc)
    head = f"TMD bulletin{' No. ' + no.group(1) if no else ''} ({item.get('issue')})"
    s = f"{head}: {', '.join(hz) or 'weather warning'}"
    if regions:
        s += f" -- {', '.join(regions)}"
    if per:
        a, b = date.fromisoformat(per[0]), date.fromisoformat(per[1])
        s += (f"; {a.day}-{b.day} {b:%b} {b.year}" if a.month == b.month
              else f"; {a.day} {a:%b}-{b.day} {b:%b} {b.year}")
    elif item.get("until"):
        s += f"; until {item['until']}"
    return s


def _tmd_sea(title: str, desc: str) -> dict:
    """Sea-state content of a TMD bulletin, as it concerns the GULF (Samui's sea).

    TMD titles name the sea of a wave warning ("... คลื่นลมแรงบริเวณทะเลอันดามัน" =
    strong waves in the Andaman Sea). A wave warning counts for the Gulf unless it names
    the Andaman Sea only; when the sea is not named at all we assume the Gulf
    (conservative: a false 'caution' is better than a missed one)."""
    text = f"{title} {desc}"
    waves = TH_WAVES in text

    def about_gulf(s: str) -> bool:
        i = s.find(TH_WAVES)
        if i < 0:
            return False
        seg = s[i:i + 80]
        return TH_GULF in seg or TH_ANDAMAN not in seg

    gulf = waves and (about_gulf(title) or about_gulf(desc))
    heights = [float(x) for m in _TH_WAVE_M.finditer(text) for x in m.groups() if x]
    boats = TH_SMALL_BOATS in text and TH_STAY_ASHORE in text
    return {"strong_waves_gulf": bool(gulf),
            "small_boats_ashore": bool(boats and (gulf or TH_GULF in text)),
            "wave_m_max": max(heights) if heights else None}


def parse_tmd_storm_tracking(xml_text: str, today: date | None = None, limit: int = 15) -> dict:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise SourceChanged(f"TMD RSS not XML: {e}") from e
    items = root.findall("./channel/item")
    if not items:
        raise SourceChanged("TMD RSS has no items")
    today = today or today_bkk()
    out = []
    for it in items[: limit * 3]:
        title = (it.findtext("title") or "").strip()
        desc = (it.findtext("description") or "").strip()
        m = re.search(r"\((\d+)/(25\d\d)\)", title)
        if not m:
            continue
        text = f"{title} {desc}"
        south = TH_SOUTH in text
        south_west_only = (TH_SOUTH_WEST in text and TH_SOUTH_EAST not in text
                           and text.count(TH_SOUTH) == text.count(TH_SOUTH_WEST))
        until = _tmd_until(title)
        per = tmd_period(title, desc)
        if per and not until:
            until = date.fromisoformat(per[1])
        out.append({
            "from": per[0] if per else None,
            "issue": f"{m.group(1)}/{m.group(2)}",
            "seq": int(m.group(2)) * 1000 + int(m.group(1)),
            "title": title, "description": desc[:600],
            "until": until.isoformat() if until else None,
            "active": bool(until and until >= today),
            "mentions_samui": TH_SURAT in text or TH_SAMUI in text,
            "affects_samui": bool(TH_SURAT in text or TH_SAMUI in text or TH_GULF in text
                                  or TH_SOUTH_EAST in text or (south and not south_west_only)),
            "heavy_rain": TH_HEAVY_RAIN in text,
            "strong_waves": TH_WAVES in text,
            "storm": TH_STORM in title,
        } | _tmd_sea(title, desc))
        out[-1]["summary_en"] = tmd_summary_en(out[-1])
    out.sort(key=lambda x: x["seq"], reverse=True)
    return {"url": TMD_STORM_URL, "items": out[:limit]}


# PWA (Provincial Waterworks Authority) water-interruption notices, the JSON API behind
# https://www.pwa.co.th/news/call1662 ("ข่าวหยุดจ่ายน้ำ"). Keyless, verified 2026-09-24.
# Branch 1206 = "การประปาส่วนภูมิภาคสาขาเกาะสมุย" (PWA Ko Samui branch), from that page's
# branch selector. The list holds current / recent notices only.
PWA_NOTICES_URL = "https://api-mg.pwa.co.th:8065/news/api/listPublish"
PWA_NOTICES_PAGE = "https://www.pwa.co.th/news/call1662"
PWA_SAMUI_BA = "1206"
PWA_KINDS = (  # title prefix (Thai) -> (kind, English label)
    ("ประกาศไม่สามารถจ่ายน้ำ", "no_supply", "Water cannot be supplied"),
    ("ประกาศท่อประปาแตก", "pipe_burst", "Emergency pipe burst"),
    ("ประกาศสำรองน้ำ", "store_water", "Planned interruption: store water"),
    ("ประกาศหยุดจ่ายน้ำ", "no_supply", "Supply stopped"),
    ("ประกาศน้ำไหลอ่อน", "low_pressure", "Low pressure"),
)
PWA_STATUS = {"กำลังดำเนินการ": "in_progress", "ดำเนินการแล้วเสร็จ": "done", "ยกเลิก": "cancelled"}


def _pwa_time(s) -> str | None:
    if not s or s == "None":
        return None
    try:
        return _bkk_to_utc(str(s).strip()[:19])
    except ValueError:
        return None


def parse_pwa_notices(payload: dict) -> list[dict]:
    """PWA listPublish JSON -> notices with UTC times. `end` = the extended end if any.
    Thai free text (cause, area) is kept as published (third-party content)."""
    if not isinstance(payload, dict) or "data" not in payload or "total" not in payload:
        raise SourceChanged("PWA notices: no total/data")
    if not isinstance(payload["data"], list):
        raise SourceChanged("PWA notices: data is not a list")
    out = []
    for x in payload["data"]:
        title = (x.get("title") or "").strip()
        kind, label = "other", "Water supply notice"
        for prefix, k, lab in PWA_KINDS:
            if title.startswith(prefix):
                kind, label = k, lab
                break
        start, end = _pwa_time(x.get("start_date")), _pwa_time(x.get("end_date"))
        ext = _pwa_time(x.get("extend_end_date"))
        out.append({
            "id": (x.get("link") or "").rsplit("/", 1)[-1].split("?")[0] or title[:40],
            "branch": x.get("branch_name"), "kind": kind, "kind_label": label,
            "status": PWA_STATUS.get((x.get("working_status_name") or "").strip(), "unknown"),
            "start": start, "end": max(e for e in (end, ext) if e) if (end or ext) else None,
            "title_th": title, "cause_th": (x.get("cause") or "").strip()[:400],
            "area_th": (x.get("affected_area") or "").strip()[:400],
            "url": x.get("link") or PWA_NOTICES_PAGE,
        })
    return out


# --------------------------------------------------------------------------- collectors

# www.tmd.go.th does not send its intermediate certificate (verified 2026-09-24 with
# `openssl s_client`: "unable to verify the first certificate"), so a strict client
# fails. We ship that intermediate (GlobalSign GCC R6 AlphaSSL CA 2025, sha256
# A8:83:55:92:...:08:CA, valid to 2027-05-21, verified to chain to the GlobalSign R6
# root in certifi) and still require a full chain to a certifi root: TLS
# verification is NOT disabled.
TMD_INTERMEDIATE = Path(__file__).parent / "certs" / "globalsign_gcc_r6_alphassl_ca_2025.pem"


def tmd_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=certifi.where())
    if TMD_INTERMEDIATE.is_file():
        ctx.load_verify_locations(cafile=str(TMD_INTERMEDIATE))
    if hasattr(ssl, "VERIFY_X509_PARTIAL_CHAIN"):
        ctx.verify_flags &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
    return ctx


class OpenMeteoSamui(Collector):
    name = "openmeteo_samui"
    title = "Koh Samui -- 16-day forecast + past 92 days"
    category = "local"
    provider = "Open-Meteo (DWD ICON, ECMWF IFS, NOAA GFS... best match)"
    homepage = "https://open-meteo.com/en/docs"
    endpoint = FORECAST_URL
    interval_s = 3 * 3600
    description = ("Temperatures, feels-like temperature, rain, rain probability, gusts and "
                   "UV for Koh Samui. Future days carry meta.forecast=true.")

    async def collect(self, ctx: RunContext) -> int:
        params = _home_params() | {
            "daily": ",".join(FORECAST_DAILY), "timezone": "Asia/Bangkok",
            "forecast_days": 16, "past_days": 92,
        }
        r = await ctx.get(FORECAST_URL, params=params)
        rows = parse_daily(r.json(), FORECAST_DAILY, today=today_bkk())
        return db.upsert_observations(self.name, rows)


class OpenMeteoSamuiEra5(Collector):
    name = "openmeteo_samui_era5"
    title = "Koh Samui -- ERA5 observed (200 d) + 1991-2020 normals"
    category = "local"
    provider = "Open-Meteo archive (ECMWF ERA5)"
    homepage = "https://open-meteo.com/en/docs/historical-weather-api"
    endpoint = ARCHIVE_URL
    interval_s = 12 * 3600
    freshness_basis = "observations"
    max_age_s = 10 * 86400  # ERA5 runs ~5 days behind
    description = ("Reanalysed rain and temperatures (ERA5, ~5 days behind) for 30/60/90-day "
                   "totals, compared with the 1991-2020 normal (computed once).")

    async def collect(self, ctx: RunContext) -> int:
        n = 0
        base = _home_params() | {"daily": ",".join(ERA5_DAILY), "timezone": "Asia/Bangkok",
                                 "models": "era5"}
        clim = db.get_status("samui_climatology")
        if clim is None or not clim["value"].get("days"):
            r = await ctx.get(ARCHIVE_URL, params=base | {"start_date": CLIM_START,
                                                          "end_date": CLIM_END})
            db.set_status("samui_climatology", build_climatology(r.json()))
            ctx.notes["climatology"] = "computed"
            n += 1
        end = archive_end_date()
        start = end - timedelta(days=200)
        r = await ctx.get(ARCHIVE_URL, params=base | {"start_date": start.isoformat(),
                                                      "end_date": end.isoformat()})
        rows = parse_daily(r.json(), ERA5_DAILY)
        if rows:
            ctx.notes["last_day"] = max(x["ts"] for x in rows)
        return n + db.upsert_observations(self.name, rows)


class OpenMeteoSamuiAir(Collector):
    name = "openmeteo_samui_air"
    title = "Koh Samui -- air quality (PM2.5, PM10, AQI)"
    category = "local"
    provider = "Open-Meteo air quality (Copernicus CAMS)"
    homepage = "https://open-meteo.com/en/docs/air-quality-api"
    endpoint = AIR_URL
    interval_s = 3 * 3600
    description = ("Hourly modelled PM2.5 / PM10 / US AQI (CAMS): past 3 days + "
                   "4-day forecast. A model, not a monitoring station.")

    async def collect(self, ctx: RunContext) -> int:
        params = {"latitude": settings.home_lat, "longitude": settings.home_lon,
                  "hourly": ",".join(AIR_HOURLY), "timezone": "GMT",
                  "past_days": 3, "forecast_days": 4}
        r = await ctx.get(AIR_URL, params=params)
        return db.upsert_observations(self.name, parse_hourly_utc(r.json(), AIR_HOURLY))


class OpenMeteoSamuiSeasonal(Collector):
    name = "openmeteo_samui_seasonal"
    title = "Koh Samui -- seasonal forecast (6 months)"
    category = "local"
    provider = "Open-Meteo seasonal (ECMWF SEAS5)"
    homepage = "https://open-meteo.com/en/docs/seasonal-forecast-api"
    endpoint = SEASONAL_URL
    interval_s = 24 * 3600
    freshness_basis = "status"
    freshness_status_key = "samui_seasonal"
    description = "Forecast monthly rain and temperature anomalies for the next 6 months."

    async def collect(self, ctx: RunContext) -> int:
        params = {"latitude": settings.home_lat, "longitude": settings.home_lon,
                  "models": "ecmwf_seas5",
                  "monthly": "precipitation_mean,precipitation_anomaly,"
                             "temperature_2m_mean,temperature_2m_anomaly"}
        r = await ctx.get(SEASONAL_URL, params=params)
        doc = parse_seasonal_monthly(r.json())
        doc["fetched_at"] = db.now_iso()
        db.set_status("samui_seasonal", doc)
        return len(doc["months"])


class ThaiWaterSamuiRain(Collector):
    name = "thaiwater_samui_rain"
    title = "Koh Samui -- rain gauges (observed 24 h rain)"
    category = "local"
    provider = "ThaiWater / HII (Hydro-Informatics Institute), stations HII + TMD"
    homepage = "https://www.thaiwater.net/"
    endpoint = THAIWATER_RAIN_URL + "?province_code=84"
    interval_s = 3600
    freshness_basis = "observations"
    max_age_s = 6 * 3600
    description = "Maximum 24 h rain measured across the rain gauges of Ko Samui district."

    async def collect(self, ctx: RunContext) -> int:
        r = await ctx.get(THAIWATER_RAIN_URL, params={"province_code": "84"})
        res = parse_thaiwater_samui_rain(r.json())
        if res is None:
            return 0
        return db.upsert_observations(self.name, [{
            "series": "samui_gauge_rain_24h", "ts": res["ts"], "value": res["value"],
            "unit": "mm", "meta": {"stations": res["stations"]},
        }])


class ThaiWaterDams(Collector):
    name = "thaiwater_dams"
    title = "Surat Thani -- Ratchaprapa dam (storage)"
    category = "local"
    provider = "ThaiWater / Royal Irrigation Department"
    homepage = "https://www.thaiwater.net/"
    endpoint = THAIWATER_DAMS_URL
    interval_s = 6 * 3600
    freshness_basis = "observations"
    max_age_s = 4 * 86400
    description = ("Storage of the province's large dam (Ratchaprapa / Chiew Larn), from the "
                   "RID daily large-dam table. A regional water-stress indicator, not the "
                   "island's direct supply.")

    async def collect(self, ctx: RunContext) -> int:
        r = await ctx.get(THAIWATER_DAMS_URL)
        dams = parse_thaiwater_dams(r.json())
        rows = [{"series": f"surat_{d['name'].lower()}_storage_pct", "ts": d["date"],
                 "value": d["storage_pct"], "unit": "%", "meta": d} for d in dams if d["date"]]
        return db.upsert_observations(self.name, rows)


class TmdWarnings(Collector):
    name = "tmd_warnings"
    title = "TMD -- weather warnings (heavy rain, waves, storms)"
    category = "local"
    provider = "Thai Meteorological Department"
    homepage = "https://www.tmd.go.th/"
    endpoint = TMD_STORM_URL
    interval_s = 3600
    freshness_basis = "status"
    freshness_status_key = "tmd_warnings"
    max_age_s = 6 * 3600
    description = ("TMD warning bulletins (in Thai). We detect those aimed at the Gulf side of "
                   "the South / Surat Thani and their end date.")

    async def collect(self, ctx: RunContext) -> int:
        async with httpx.AsyncClient(verify=tmd_ssl_context(), timeout=60.0,
                                     headers={"User-Agent": settings.user_agent},
                                     follow_redirects=True) as client:
            r = await client.get(TMD_STORM_URL)
        ctx.last_status = r.status_code
        r.raise_for_status()
        doc = parse_tmd_storm_tracking(r.text)
        doc["fetched_at"] = db.now_iso()
        db.set_status("tmd_warnings", doc)
        feed = [{
            "ext_id": it["issue"], "kind": "official", "title": it["title"],
            "summary": it["description"], "url": TMD_STORM_URL, "author": "TMD", "lang": "th",
            "tags": ["thailand", "tmd"] + (["samui"] if it["mentions_samui"] else []),
        } for it in doc["items"]]
        db.upsert_feed_items(self.name, feed)
        return len(doc["items"])


class PwaSamuiNotices(Collector):
    name = "pwa_samui_notices"
    title = "Koh Samui -- PWA water-supply interruption notices"
    category = "local"
    provider = "PWA (Provincial Waterworks Authority), Ko Samui branch"
    homepage = PWA_NOTICES_PAGE
    endpoint = PWA_NOTICES_URL
    interval_s = 3 * 3600
    freshness_basis = "status"
    freshness_status_key = "pwa_samui_notices"
    description = ("Official PWA notices for the Ko Samui branch: pipe bursts, planned "
                   "interruptions, 'water cannot be supplied'. An empty list means no "
                   "notice is published, not that supply is guaranteed. Island reservoir "
                   "levels are not published in a machine-readable form.")

    async def collect(self, ctx: RunContext) -> int:
        r = await ctx.client.post(PWA_NOTICES_URL, json={"ba": [PWA_SAMUI_BA], "page": 1,
                                                          "limit": 50})
        ctx.last_status = r.status_code
        r.raise_for_status()
        items = parse_pwa_notices(r.json())
        db.set_status("pwa_samui_notices", {"items": items, "branch": PWA_SAMUI_BA,
                                            "url": PWA_NOTICES_PAGE,
                                            "fetched_at": db.now_iso()})
        db.upsert_feed_items(self.name, [{
            "ext_id": it["id"], "kind": "official", "title": it["title_th"],
            "summary": f"{it['kind_label']}. {it['area_th']}"[:600], "url": it["url"],
            "author": "PWA Ko Samui", "lang": "th", "published_at": it["start"],
            "tags": ["thailand", "samui", "water"]} for it in items])
        return len(items)


COLLECTORS = [OpenMeteoSamui, OpenMeteoSamuiEra5, OpenMeteoSamuiAir, OpenMeteoSamuiSeasonal,
              ThaiWaterSamuiRain, ThaiWaterDams, TmdWarnings, PwaSamuiNotices]
