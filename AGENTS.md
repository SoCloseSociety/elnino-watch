# El Nino Watch -- developer and agent guide

Live tracker for the 2026-27 El Nino (ENSO) event, with an explainable risk watch for one
place (default: **Koh Samui, Thailand**; `HOME_*` settings move the point) that says when to
adjust, prepare, or leave, and a preparedness page for those who stay. This file is the
contract a contributor (human or coding agent) needs: rules, layout, data conventions and
the API contract the frontend depends on. The friendlier tour is in [README.md](README.md);
the short version of the rules is in [CONTRIBUTING.md](CONTRIBUTING.md).

Context: a strong El Nino is under way (NOAA CPC ONI +1.80 for JJA 2026). This is not a
toy: wrong or stale data can lead to a bad real-world decision.

## Stack and ports
- backend/: Python 3.12+, FastAPI, httpx, stdlib sqlite3 (data/elnino.db), uv.
  API on **127.0.0.1:8911**. Run: `cd backend && uv run uvicorn app.main:app --port 8911`
- frontend/: React 19 + Vite + TypeScript + Tailwind 4 + MapLibre GL + Recharts.
  Dev server **5211** proxies `/api` to 8911. `npm run build` -> frontend/dist,
  which the API serves at `/` (single localhost URL: http://127.0.0.1:8911).

## Hard rules
1. **Never fabricate data.** Everything shown came from a real response. No
   placeholder numbers, no mock posts, no invented social handles. A social
   account goes in the list only after its handle was resolved against the live
   platform API (and the check is kept as a test or a script).
2. **No silent failure.** Every collector records a `source_runs` row (the base
   runner does it). Missing credential -> `NeedsConfig` -> shown as
   `needs_config`. Format change -> `SourceChanged`. Empty result -> state `empty`.
3. **Freshness is part of the data.** Every value shown in the UI carries its
   timestamp and source link. Stale sources are visibly marked.
4. **Respect the sources.** Each collector's `interval_s` matches how often the
   source actually updates (monthly index: 6-12 h; GDACS: 10-15 min; GDELT: >= 15 min,
   it rate-limits at 1 req / 5 s). Identify with settings.user_agent.
5. **Free, keyless first.** Paid/credentialed sources (X API, Bluesky search, Windy,
   the LLM rewrite) are optional and degrade to `needs_config`.
6. **Risk levels are explainable.** Every Koh Samui factor ships with its value,
   threshold, explanation, source and link. No black-box score.
7. Tests never hit the network (respx fixtures from REAL captured payloads).
   `scripts/verify_sources.py` is the one thing that hits reality on purpose.
8. No em dashes in code, docs, or UI text (use `--`).
9. **The product is English-only.** Every user-facing string (UI, risk labels,
   explanations, actions, preparedness data, layer/source descriptions, alerts)
   is English. Only third-party content (news titles, posts) stays in its
   original language.
10. **Nothing ships without its explanation.** The readers are not meteorologists.
   Every new source, series, status, layer, map item, factor, filter or page must come
   with a help entry: what it is, how to read it (units, colours, thresholds), why it
   matters for Koh Samui / ENSO, its limits, and 1-3 checked source links. Help topics
   live in frontend/src/help/content.ts (see frontend/src/help/README.md); backend-only
   agents write theirs to backend/docs/help_topics/<id>.md (same fields) for merging.
11. **Cameras: public feeds only.** Only webcams their owner publishes for public viewing
   (tourism/beach cams, official weather/traffic/port cams, NOAA BuoyCAMs, Windy Webcams
   API). Never unsecured private cameras or anything reached by bypassing access control.

## Backend layout
- `app/config.py` settings (env / ../.env). `app/db.py` storage helpers.
- `app/collectors/base.py` the Collector contract (READ IT FIRST).
- `app/collectors/<domain>.py` each exposes `COLLECTORS = [Cls, ...]`.
  Domains: indices, official, maritime, hazards, news, social.
- `app/local/` Koh Samui watch: `collectors.py` (COLLECTORS), `risk.py` (engine),
  `alerts.py` (delivery), `preparedness.py` (checklist data), `api.py` (router),
  `__init__.py` registers the post-run hook via `scheduler.register_post_hook`.
- `app/places/` Places comparison (config, collectors, engine, enso, api).
- `app/shopping/` curated shopping catalog + budget (no runtime scraping).
- `app/seo.py` server-rendered summaries, JSON-LD, sitemap, robots, OG image, IndexNow.
- `app/security.py` public mode: admin gate, CSP, headers, private state, caches.
- `app/scheduler.py` runs collectors on their interval, then post hooks.
- `app/main.py` API. `app/briefing.py` rules briefing + optional LLM rewrite.
- `scripts/verify_sources.py` hits every source for real (the only networked script).
- Frontend: `src/pages/*` (11 pages), `src/help/` (topics, tours, guides; see its README),
  `src/components/`, `src/api/` (client + types), `src/lib/` (format, geo, urlFilters).

## Data conventions
- observations.series naming: lowercase snake, region explicit:
  `oni`, `roni`, `nino34_weekly_anom`, `nino12_weekly_anom`, `nino3_weekly_anom`,
  `nino4_weekly_anom`, `nino34_weekly_sst`, `soi`, `mei_v2`, `world_sst_daily`,
  `tao_<station>_sst`, `samui_temp_max`, ... `ts` = ISO date (YYYY-MM-DD, month
  indices use the center month's 15th, e.g. JJA 2026 -> 2026-07-15) or ISO datetime UTC.
- feed_items.kind: `official` (agency bulletins), `news`, `social`, `research`.
  `tags` is a list; include `"samui"`/`"thailand"` when the item mentions them.
- events.category: cyclone | flood | drought | wildfire | heat | storm | volcano |
  earthquake | bleaching | haze | other. severity: green | orange | red | info.

## API contract (frontend depends on this)
- `GET /api/health`
- `GET /api/latest` -> [{source, series, ts, value, unit, prev_value}]
- `GET /api/series?source=&series=&since=` -> {points: [{ts, value, unit, meta}]}
- `GET /api/series/catalog`
- `GET /api/status` -> {key: {value, updated_at}} ; `GET /api/status/{key}`
  Status keys: `cpc_alert` {status, synopsis, issued, url}, `iri_plume`
  {issued, url, probabilities: [{season, la_nina, neutral, el_nino}]},
  `bom_outlook` {status, issued, url}, `local_risk` (below), `briefing` {text, model, generated_at}.
- `GET /api/feed?kind=&source=&q=&lang=&limit=&before=`
- `GET /api/events?category=&source=` (all have lat/lon)
- `GET /api/sources` -> collector descriptions + state (ok|empty|error|needs_config|pending),
  last_run, success_rate, last_ok_at. `POST /api/sources/verify` runs all now.
  `POST /api/sources/{name}/run`.
- `GET /api/alerts`
- `GET /api/local` -> local_risk:
  ```
  {level: 0..4, level_key: normal|vigilance|prepare|act|leave, headline, evaluated_at,
   home: {name, lat, lon},
   factors: [{id, label, level, level_key, value, unit, threshold, explanation,
              source, url, observed_at}],
   actions: [{level_key, text}],        # what to do at the current level
   triggers: [{level_key, text}]}       # what would move us to the next level
  ```
- `GET /api/local/history` -> [{evaluated_at, level}]
- `GET /api/local/weather` -> the local series (forecast + recent) for charts.
- `GET /api/preparedness` -> {categories: [{id, title, why, items: [{id, label, qty,
  per, priority: must|should|nice, note}]}], scenarios: [...], contacts: [...]}
- `GET/PUT /api/preparedness/state` -> {checked: {item_id: true}, household: {adults, children, days}}

## API contract, round 2 (improvements, 2026-09-24)
- `GET /api/sources` rows gain `freshness`: {newest_data_at, max_age_s, age_s, stale: bool,
  basis: "observations"|"feed"|"events"|"status"|"run"}. "Fetch ok" and "data fresh" are
  different things: a source can answer 200 with data weeks old (climate.gov RSS).
  Row `state` gains `stale` (last fetch ok, newest data older than max_age_s). Every
  collector declares `max_age_s` + `freshness_basis` (base.py docstring; default basis
  "run", max age 3 x interval). Rows also carry `max_age_s` at top level.
- `GET /api/briefing` -> {generated_at, method: "llm"|"rules", model, headline,
  sections: [{id, title, bullets: [str], sources: [{title, url}]}], text, local_level,
  local_level_key, llm_error?, rules_text? (when method=llm)}. Rules-based
  briefing always works; the LLM (an Anthropic-Messages-shaped endpoint, settings.computeforge_url / briefing_model) only rewrites it
  and needs COMPUTEFORGE_KEY (else method "rules"). An LLM text containing any number
  absent from the rules text is rejected (llm_error says why). Regenerated every 6 h and
  when the local level changes. `POST /api/briefing/refresh` forces it. Section ids:
  enso, forecast, local, hazards, official, gaps.
- `GET /api/latest` returns the latest NON-FORECAST point (ts <= now, and not today's
  partial Open-Meteo day): forecast rows are excluded so a forecast is never shown as the
  current value (round 3 adds kind / valid_for / tz / unit_label per row).
- `GET /api/status/maintenance` -> {last_prune, pruned: {feed_items, events}, last_vacuum,
  policy}. Retention: news/social/research feed_items > 180 d deleted (official kept),
  events not listed by any fetch for 30 d deleted (events.seen_at), source_runs last 200
  per source, VACUUM weekly. Collector runs are capped at min(interval, 300 s).
- Filters (all optional; every list filter takes a comma list, e.g. `kind=news,social`):
  - `GET /api/feed`: kind, source, lang, tag (ANY of the tags), q (title/summary/author),
    since, until, before (ISO, on published_at else fetched_at), has_geo (bool), limit
    (<= 500), offset. `GET /api/feed/facets` (same params) -> {total, kind, source, lang,
    tag: [{value, count}]} (tag top 50); each facet ignores its own filter.
  - `GET /api/events`: category, source, severity, since (updated_at else started_at),
    bbox=minLon,minLat,maxLon,maxLat (minLon > maxLon = crosses the antimeridian),
    near=lat,lon + radius_km (default home_radius_km; rows gain distance_km), limit.
    `GET /api/events/facets` -> {total, category, source, severity: [{value, count}]}.
  - `GET /api/series`: + until, limit (<= 100000), downsample=daily (daily mean, ts =
    date, meta {n, downsample}) | N (every Nth point, newest kept).
    `GET /api/series/catalog`: source, category (collector category), q (series substring).
  - `GET /api/sources`: category, state (incl. stale). `GET /api/alerts`: level, kind,
    since (created_at), limit (<= 1000).
- `GET /api/local` gains `coverage`: {total, with_data, missing: [factor ids],
  critical_missing: [ids]}. If critical factors lack data the overall `level` is null,
  `level_key` "unknown", and the headline says data is insufficient (never "no danger").
- `GET /api/local/exit` -> {recommendation, signals: [{id, label, status: ok|caution|
  blocked|unknown, value, source, url, observed_at}], routes: [{id, mode: ferry|air|road,
  operator, from, to, url, notes}], checklist: [{id, label, priority}], windows:
  [{date, ok: bool, reason}]} (next 7 days of sea/wind conditions for leaving by ferry).

## API contract, round 3 (precision audit, 2026-09-24; see docs/reports/PRECISION_AUDIT_2026-09-24.md)
Provenance vocabulary (backend/app/local/provenance.py):
- `kind`: `observed` (measured, or an index computed from measurements: ONI, RONI,
  OISST Nino 3.4, SOI, MEI, DHW, gauges, Air4Thai) | `forecast` (model prediction; TODAY's
  daily total/max of Open-Meteo is a forecast too, the day is not over) | `model_analysis`
  (a model's estimate of a past hour/day: Open-Meteo past_days, CAMS before now) |
  `reanalysis` (ERA5) | `bulletin` (agency statement: CPC status, TMD, PWA, GDACS...).
  Never label a forecast "observed".
- `valid_for`: date `YYYY-MM-DD`, ISO datetime, or interval `start/end` (both days
  inclusive) that the value describes. ONI/RONI JJA 2026 -> `2026-06-01/2026-08-31`;
  weekly Nino 3.4 dated 2026-09-16 -> `2026-09-13/2026-09-19`; MEI JA -> Jul 1-Aug 31.
- `tz`: `ICT (UTC+7)` for Samui local days, `UTC` for global indices / satellites /
  any ISO datetime.
- `issued_at` (agency publication), `retrieved_at` (our last successful fetch, UTC),
  `as_of` = observed_at or issued_at or retrieved_at (the time to show).
- `unit` = machine code (degC, mm, m, km/h, ug/m3, degC-weeks, %, km, count...),
  `unit_label` = display (°C, mm, m, km/h, µg/m³, °C-weeks...). User-facing text uses
  °C / µg/m³, never degC / ug/m3. `value` is rounded for display (rain mm and % integers,
  waves 0.1 m, gusts integer km/h, PM2.5 0.1, temperatures 0.1 °C, RONI/ONI 0.01 °C),
  `value_raw` keeps the source's exact number (thresholds use the raw value).
Changes:
- `GET /api/local` factors: + `value_raw, unit_label, value_label, kind, valid_for, tz,
  issued_at, retrieved_at, as_of, summary, inputs: [{name, value, value_raw, unit,
  unit_label, kind, valid_for, tz, issued_at, retrieved_at, source, url, note}]`.
  `observed_at` is null when kind = forecast. `unit` is now the machine code (was a
  phrase such as "degC feels-like": that text is in `unit_label`). A factor with no data
  has an explanation "No current data: <what>. Why: <run log>. Check by hand meanwhile:
  <links>" and `details.manual_check`. Top level: + `headline_local` (headline minus its
  first sentence), `engine_version` (3), `time_basis`, `next_risk`.
  Headline form: "<Level> -- <ENSO phrase>. No immediate threat on Samui: <water>,
  <waves>, <cyclone>. Watch: ... Next risk: ...".
- `GET /api/local/history` rows: + `level_key`, `engine_version`; rows written before
  v3 carry `engine_version: 2` and a `note` (levels unchanged).
- `GET /api/local/exit` signals: + `unit_label, kind, valid_for, retrieved_at, as_of`
  (observed_at null for forecasts); windows: + `label` ("Thu 24 Sep"), `kind`, `valid_for`;
  wave_max_m rounded 0.1, gust_max_kmh integer.
- `GET /api/local/weather`: + `tz`, `units` {column: {unit, unit_label}}, `kinds`; each day
  + `kind` (forecast from today on, model_analysis before) and `partial_day` (today).
- `GET /api/latest`: rows + `kind, valid_for, tz, unit_label`; TODAY's Open-Meteo daily
  rows (samui / marine) are excluded too (the day still holds forecast hours).
- `GET /api/status` entries and `GET /api/status/{key}`: + `kind` (null = derived by the
  app, e.g. local_risk, briefing). `GET /api/events` rows: + `kind` (bulletin for agency
  alerts, observed for FIRMS / CRW / USGS detections).
- `tmd_warnings` items: + `from` (period start), `summary_en` (English one-liner from
  explicit Thai keywords: hazard, regions, dates).

## API contract, round 4 (past El Ninos page + review leftovers, 2026-09-24)
- `GET /api/local/analogs` and `/api/local/analogs/history` (docs/reports/REVIEW_2026-09-24.md
  section 4) feed the `/history` page ("Past El Ninos"); `history.windows_pending` non-empty
  or `samui.complete: false` = "loading, not estimated" (the UI shows blanks, never fills).
- `GET /api/events`: unchanged without parameters (every matching row). New `paged=1`
  answers `{total, limit, offset, items}` with a default `limit` of 500 (`offset` for
  paging). The frontend passes an explicit `limit` (map 5000, Overview mini map 2000).
- `GET /api/status`: documents over 12 KB are listed with `value: null, omitted: true,
  bytes, url` (the listing was 460 KB); `?full=1` returns every value and
  `GET /api/status/{key}` is unchanged. Every entry now carries `bytes`.
- `GET /api/sources` rows: + `expected_stale` (a documented reason when a feed is known to
  be silent, e.g. climategov_enso_blog). The state stays `stale`; the header badge and
  scripts/verify_sources.py's exit code ignore expected-stale rows.
- Retention: hourly `tao_*` observations older than 365 days are folded into one daily
  mean per day (`db.downsample_hourly`, meta `{n, downsample: "daily_mean"}`); daily and
  monthly series are kept forever. `GET /api/status/maintenance` reports
  `pruned.observations_hourly / observations_days` and `policy.observations`.
