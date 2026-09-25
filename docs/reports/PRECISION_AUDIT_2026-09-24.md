# Precision audit -- 24 September 2026

Scope: every value exposed by `/api/local`, `/api/local/exit`, `/api/local/weather`,
`/api/briefing`, `/api/latest`, `/api/status/*`, `/api/events`, `/api/feed`, `/api/sources`.
Reviewed as a meteorologist (what each number means, observed vs forecast, periods,
thresholds) and as a data engineer (does the stored value equal the upstream value, units,
rounding, time zones).

## 1. Live cross-check against the upstream sources

Method: for each headline number, the upstream file / API was re-fetched live on
2026-09-24 between 21:30 and 21:45 ICT (14:30-14:45 UTC) with the app's own parsers, and
compared with the value the app stores / shows (same value, same unit, same date). The
check script (read-only, hits the network) was run from `backend/` twice: before and after
the fixes below; both runs matched. A "match" on a forecast means the same model run
(forecasts change with each run; a re-fetch after a new run may differ).

| # | Quantity | App value (unit, date) | Upstream (live) | Match | Fix |
|---|----------|------------------------|-----------------|-------|-----|
| 1 | RONI (NOAA official since 2026) | +1.36 °C, JJA 2026 (Jun-Aug) | `RONI.ascii.txt` last row `JJA 2026 1.36` | yes | label: `valid_for` 2026-06-01/2026-08-31, "moderate El Nino range" |
| 2 | ONI | +1.80 °C, JJA 2026 | `oni.ascii.txt` `JJA 2026 29.09 1.80` | yes | same period labelling |
| 3 | Nino 3.4 weekly SST anomaly | +3.0 °C, week centred Wed 16 Sep 2026 | `wksst9120.for` `16SEP2026 ... 29.6 3.0` | yes | now says "week 13-19 Sep 2026 (UTC)", was a bare date |
| 4 | Nino 3.4 daily anomaly (OISST, Climate Reanalyzer) | +3.018 °C on 22 Sep (preliminary) | +3.018, 22 Sep, `Preliminary` array | yes | shown as +3.02 °C and marked "preliminary" in factor and briefing |
| 5 | SOI (NOAA CPC, standardized) | -1.1 σ, Aug 2026 | `soi` STANDARDIZED table Aug 2026 -1.1 | yes | added to the briefing with its month; unit label "σ (standardized)" |
| 6 | SOI (BoM, Troup) | -14.6, Aug 2026 | BoM FTP `soiplaintext.html` Aug 2026 -14.6 | yes | added to the briefing |
| 7 | MEI.v2 | +2.54, JA 2026 (Jul-Aug) | `meiv2.data` 2026 JA 2.54 | yes | `valid_for` 2026-07-01/2026-08-31 in /api/latest; added to briefing |
| 8 | NOAA CPC ENSO alert status | El Niño Advisory, issued 10 Sep 2026, next 8 Oct | ensodisc.shtml "El Niño Advisory", 10 September 2026 | yes | kind `bulletin`, weekday dates (Thu 10 Sep 2026) |
| 9 | CPC synopsis | "El Niño is strengthening, with a greater than 90% chance of a very strong event ..." | same text (HTML entities decoded) | yes | trailing double period removed in the factor text |
| 10 | IRI El Nino probabilities | SON-FMA 100%, MAM 99%, AMJ 90%, MJJ 61% (issued 21 Sep) | figure 3 SVG of the 21 Sep update: identical 9 seasons | yes | kind `forecast`, issue date shown |
| 11 | Samui rain 30 d (ERA5) | 130.2 mm = 112% of 116.1 mm, 20 Aug-18 Sep | ERA5 archive sum 130.2 mm | yes | window dates now shown |
| 12 | Samui rain 60 d | 200.4 mm = 101% of 198.3 mm, 21 Jul-18 Sep | 200.4 mm | yes | -- |
| 13 | Samui rain 90 d | 287.4 mm = 103% of 279.1 mm, 21 Jun-18 Sep | 287.4 mm | yes | kind `reanalysis`, `valid_for` 2026-06-21/2026-09-18 |
| 14 | Samui rain 180 d | 527.8 mm = 89% of 590.6 mm, 23 Mar-18 Sep | 527.8 mm | yes | -- |
| 15 | ERA5 last available day | 18 Sep 2026 | archive API: last non-null day 18 Sep | yes | -- |
| 16 | Max feels-like temperature, next 7 days | 37.2 °C on Wed 30 Sep | Open-Meteo forecast (same run): 37.2 °C on 2026-09-30 | yes | **was reported as observed_at 2026-09-30**: now kind `forecast`, `observed_at` null, `valid_for` 2026-09-30, text "Forecast max feels-like 37.2 °C on Wed 30 Sep (Open-Meteo, fetched 24 Sep 20:09 ICT)" |
| 17 | Max gust, next 72 h | 50.8 km/h on Thu 24 Sep | Open-Meteo: 50.8 km/h, 2026-09-24 | yes | shown as 51 km/h (integer), kind `forecast` |
| 18 | Rain forecast next 3 days | 32.9 mm total, wettest day 15.7 mm (Sat 26 Sep) | 32.9 mm / 15.7 mm | yes | shown 33 mm / 16 mm, kind `forecast`; the date of the wettest day is now given |
| 19 | Max significant wave height, next 72 h | 0.46 m on Thu 24 Sep | Open-Meteo Marine (9.5 N 100.1 E): 0.46 m | yes | shown 0.5 m, `value_raw` 0.46; kind `forecast` (was observed_at = forecast date) |
| 20 | PM2.5 CAMS 24 h mean | 3.7 µg/m³ to 21:00 ICT | Open-Meteo air quality, last 24 h mean 3.7 | yes | kind `model_analysis`; no longer mixed with the forecast in one number |
| 21 | PM2.5 measured (Air4Thai, nearest station) | 7.0 µg/m³, Surat Thani (42t, 87 km), 17:00 ICT | Air4Thai `getNewAQI_JSON` 42t PM25 7.0, 2026-09-24 17:00 | yes | **new input**: the air factor now uses the measured station (kind `observed`) as well as CAMS |
| 22 | Coral Reef Watch DHW, West Gulf of Thailand | 0.0 °C-weeks, 22 Sep | CRW VS file last row 2026-09-22 DHW 0.0 | yes | alert level (Bleaching Watch) and SST anomaly (+0.72 °C) added |
| 23 | Ratchaprapa dam storage | 72.84 %, 24 Sep | ThaiWater `thailand_main` 72.84, 2026-09-24 | yes | shown 72.8% and "regional indicator only" |
| 24 | Nearest tropical cyclone | Tropical Cyclone ONE-26 (GDACS orange), 2,002 km | GDACS EVENTS4APP: ONE-26 orange 2,002 km (then SURIGAE-26 3,640 km) | yes | nearest now named in the headline; GDACS preferred over JTWC 01B for the same storm |
| 25 | PWA Ko Samui notices in force | 0 | PWA listPublish branch 1206: 0 items | yes | check time stated ("list checked 24 Sep 20:57 ICT") |
| 26 | TMD bulletins | 223/2569, 222/2569, 221/2569 | TMD storm-tracking RSS: same three newest | yes | English summary + period added (see section 3) |

No stored value differed from its source. All the defects found were in labelling,
units, dates and completeness, fixed below.

## 2. Defects found and fixed

| Where | Defect | Fix |
|-------|--------|-----|
| `/api/local` heat, sea_state, cyclone_wind, flood | Forecast values carried `observed_at` = the forecast date (heat 2026-09-30); the UI labelled them "observed" | Every factor has `kind`; forecasts have `observed_at` null, `valid_for` (the day predicted), `retrieved_at`, `as_of` |
| `/api/local` all factors | No period for the value (90-day window, 3-month season, CPC week) | `valid_for` (date or interval), `tz` (ICT or UTC), `inputs` list with per-number provenance |
| `/api/local` enso | Shown value RONI +1.36 (level 1) while the level (prepare) came from the weekly Nino 3.4 +3.0 | The shown value is the index that sets the level; the others are in `inputs` and the text |
| `/api/local` air | One number = max(model analysis, forecast), described as "PM2.5 24 h mean"; no measurement used | Measured Air4Thai station + CAMS analysis + CAMS forecast, each labelled; level = worst; shown value = the one that sets the level |
| `/api/local` flood | "TMD warning in force for the South (223/2569)" without hazard, period or area | "TMD bulletin No. 7 (223/2569): heavy to very heavy rain -- North, lower Northeast, Central, Bangkok, East, South; 24-27 Sep 2026" |
| `/api/local` headline | "Prepare. Main factors: El Nino (event strength). No immediate danger on the island." | Specific: ENSO numbers with periods, local numbers with dates and kinds, watch items, next seasonal risk (section 5) |
| Missing data text | "data unavailable." | "No current data: <what>. Why: <last run, error, last success>. Check by hand meanwhile: <verified links>" + `details.manual_check` |
| Units | "degC", "ug/m3", "degC feels-like", "% of normal, 90 d" in text and `unit` | `unit` = machine code, `unit_label` = °C / µg/m³ / ...; all user-facing text uses °C, µg/m³, m³ |
| Rounding | 0.46 m, 50.8 km/h, 15.7 mm shown raw; RONI at 2 dp but weekly at 1 dp mixed | Display rounding per quantity (units_display help topic), `value_raw` kept |
| Dates | ISO dates and bare "2026-09-16" in prose | Weekday dates computed from the calendar ("Wed 30 Sep"), times in ICT with the label, UTC stated for global indices |
| `/api/local/exit` | Wave/gust/rain signals: `observed_at` = forecast date; unit "mm/24 h" | kind / valid_for / retrieved_at / unit_label; windows labelled forecast, rounded |
| `/api/latest` | Today's Open-Meteo daily row (day not over: partly forecast) returned as the "latest observed" value | Excluded; rows carry kind / valid_for / tz / unit_label |
| `/api/local/weather` | "forecast" flag false for today (partial day) | Per-day `kind` + `partial_day`; `units` and `tz` blocks |
| `/api/status/*`, `/api/events` | No kind | `kind` on each status envelope and event row |
| `/api/briefing` | "ONI ... degC"; factor lines "(observed 2026-09-30)" for a forecast; SOI / MEI absent; weekly given as a bare date | Bullets with kinds and periods; SOI (CPC + BoM), MEI, preliminary daily Nino 3.4; headline includes the Samui summary |
| Events (history hygiene) | CRW bleaching events still titled in French ("Veille blanchissement") by an earlier version | Re-fetched after restart: now "Bleaching Watch (DHW 0.0)" |
| `local_risk_history` (history hygiene) | Rows from the previous engine indistinguishable | Annotated once: `engine_version: 2` + note (levels unchanged); new rows carry `engine_version: 3`, `level_key` |
| Preparedness text | "41 degC", "75 ug/m3" | "41 °C", "75 µg/m³" |

## 3. Completeness: fallbacks added and remaining true gaps

| Factor | Primary | Fallback / complement (added) | True gap and what to check by hand |
|--------|---------|-------------------------------|------------------------------------|
| water | ERA5 reanalysis vs 1991-2020 ERA5 normal | Open-Meteo past-day model analyses (92 d) vs the same normal, flagged `model_analysis` (runs wetter than ERA5: a deficit is understated, never invented); PWA notices, Ratchaprapa dam, ECMWF SEAS5 | Island reservoir levels and the PWA rotation schedule are not published machine-readably (checked 24 Sep 2026): PWA notices https://www.pwa.co.th/news/call1662 (branch Ko Samui) or call PWA 1662 |
| air | CAMS model at Samui | PCD Air4Thai measured PM2.5, nearest fresh station (< 6 h) | Koh Samui has no PCD station (nearest Surat Thani, 87 km): https://air4thai.pcd.go.th/webV3/ |
| flood | Open-Meteo 3-day forecast | ThaiWater island gauges (observed), TMD heavy-rain bulletins (a bulletin alone now keeps the factor assessable) | -- |
| sea_state | Open-Meteo Marine | TMD Gulf wave bulletins | No wave buoy near Samui publishes data; TMD warnings https://www.tmd.go.th/en/warning-and-events/warning-storm |
| cyclone_wind | GDACS | JTWC / JMA / EONET positions, TMD storm bulletins | -- |
| heat | Open-Meteo forecast | ERA5 30-day Tmax anomaly | No public keyless station feed for Samui's own thermometer; TMD 7-day forecast https://www.tmd.go.th/en/forecast/weekly |

## 4. Precision rules applied

| Quantity | Display | Notes |
|----------|---------|-------|
| ONI / RONI | 0.01 °C | CPC's own precision |
| Weekly Nino 3.4 | 0.1 °C | CPC's own precision |
| Daily Nino 3.4 (OISST) | 0.01 °C | "preliminary" when the source says so |
| Rain totals | integer mm | percentages of normal: integer |
| Waves | 0.1 m | raw kept in `value_raw` |
| Gusts | integer km/h | |
| PM2.5 | 0.1 µg/m³ | |
| Temperatures | 0.1 °C | |
| DHW | 0.1 °C-weeks | |
| Distances | integer km, thousands separator | |
| Times | "24 Sep 20:05 ICT" in text; ISO 8601 UTC in fields | local days are ICT, global indices UTC |

## 5. Live result after the fixes (24 Sep 2026, ~21:45 ICT)

Samui headline:

> Prepare -- strong El Nino (ONI +1.80 °C JJA 2026; RONI +1.36 °C; Nino 3.4 +3.0 °C week of
> 16 Sep). No immediate threat on Samui: rain 103% of normal (90 d to 18 Sep), waves max
> 0.5 m (forecast to Sat 26 Sep), no cyclone within 800 km (nearest 2,002 km). Watch: heavy
> rain / flood -- TMD heavy-rain bulletin 223/2569 for the South, in force to Sun 27 Sep
> (forecast 33 mm over 3 days). Next risk: NE-monsoon heavy rain and rough seas Oct-Dec 2026
> (November wettest); water stress Feb-Apr 2027.

Briefing headline:

> Strong El Nino (ONI +1.80 °C, JJA 2026; RONI +1.36 °C; Nino 3.4 +3.0 °C week of 16 Sep);
> NOAA CPC: El Niño Advisory (10 Sep). Koh Samui: PREPARE. No immediate threat on Samui: ...
> (same local text as above).

## 6. Endpoints without measurement values

- `/api/feed`: documents (news, posts, bulletins); `kind` there is the document type
  (official / news / social / research), `published_at` / `fetched_at` are ISO UTC. Third-
  party titles stay in their language (rule 9); TMD bulletins get an English `summary_en`
  in `status/tmd_warnings`.
- `/api/sources`: run and freshness timestamps (ISO UTC) only; checked consistent with
  `source_runs`.
