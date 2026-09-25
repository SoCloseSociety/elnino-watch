// API response types. Source of truth: ../../CLAUDE.md "API contract".
// Fields marked optional are either optional in the contract or assumed by the
// dashboard while the backend is still being built; every consumer guards them.

export interface Health {
  status: string
  collectors: number
  home: string
}

export interface LatestPoint extends ValueKindFields {
  source: string
  series: string
  ts: string
  value: number | null
  unit: string | null
  prev_value: number | null
}

export interface SeriesPoint extends ValueKindFields {
  ts: string
  value: number | null
  unit?: string | null
  meta?: Record<string, unknown> | string | null
}

export interface SeriesResponse {
  source: string
  series: string
  points: SeriesPoint[]
}

export interface CatalogEntry extends ValueKindFields {
  source: string
  series: string
  unit: string | null
  points: number
  first: string
  last: string
}

export interface StatusDoc<T = unknown> {
  value: T
  updated_at: string
}

export type StatusMap = Record<string, StatusDoc>

export interface CpcAlert {
  status?: string
  synopsis?: string
  issued?: string
  url?: string
}

export interface IriProbability {
  season: string
  la_nina: number | null
  neutral: number | null
  el_nino: number | null
}

export interface IriPlume {
  issued?: string
  url?: string
  probabilities?: IriProbability[]
}

export interface BomOutlook {
  status?: string
  issued?: string
  url?: string
}

export interface BriefingSection {
  id: string
  title: string
  bullets: string[]
  sources?: { title: string; url: string }[]
}

/** GET /api/briefing (round 2). Older status-key shape only had {text, model, generated_at}. */
export interface Briefing {
  generated_at?: string | null
  method?: 'llm' | 'rules' | string | null
  model?: string | null
  headline?: string | null
  sections?: BriefingSection[] | null
  text?: string | null
}

export interface TaoBuoy {
  // Assumed shape: the contract only says "list with lat/lon/sst".
  id?: string
  station?: string
  name?: string
  lat: number
  lon: number
  sst?: number | null
  sst_anom?: number | null
  ts?: string
  observed_at?: string
  url?: string
}

export type FeedKind = 'official' | 'news' | 'social' | 'research'

export interface FeedItem {
  source: string
  ext_id: string
  kind: FeedKind | string
  title: string | null
  summary: string | null
  url: string | null
  author: string | null
  lang: string | null
  image: string | null
  published_at: string | null
  fetched_at: string
  lat: number | null
  lon: number | null
  tags: string[] | string | null
}

export type Severity = 'green' | 'orange' | 'red' | 'info'

export interface EventItem {
  source: string
  ext_id: string
  category: string
  title: string | null
  url: string | null
  severity: Severity | string | null
  lat: number
  lon: number
  started_at: string | null
  updated_at: string | null
  geometry: unknown
  payload: unknown
  /** round 2: set when the request used near=lat,lon */
  distance_km?: number | null
}

/** GET /api/feed/facets, /api/events/facets: counts per value; each facet ignores its own filter. */
export interface FacetValue {
  value: string | null
  count: number
}
export interface Facets {
  total: number
  [facet: string]: FacetValue[] | number
}

/** Value kind tagged by the backend on factors, signals and series points (precision round). */
export type ValueKindKey = 'observed' | 'forecast' | 'model_analysis' | 'reanalysis' | 'bulletin' | 'documented'
export interface ValueKindFields {
  kind?: ValueKindKey | string | null
  /** date/time the value is valid for (forecast target, bulletin validity); "start/end" for an interval */
  valid_for?: string | null
  /** human unit, e.g. "degC feels-like" -> "°C feels-like" */
  unit_label?: string | null
  /** round 3: time zone of valid_for ("ICT (UTC+7)" or "UTC") */
  tz?: string | null
  /** round 3: agency publication time */
  issued_at?: string | null
  /** round 3: our last successful fetch (UTC) */
  retrieved_at?: string | null
  /** round 3: the time to show = observed_at or issued_at or retrieved_at */
  as_of?: string | null
}

/** Round 3: one number a factor used, each with its own provenance. */
export interface FactorInput extends ValueKindFields {
  name: string
  value: number | string | null
  value_raw?: number | string | null
  unit?: string | null
  source?: string | null
  url?: string | null
  note?: string | null
}

export type SourceState = 'ok' | 'stale' | 'empty' | 'error' | 'needs_config' | 'pending'

export interface SourceRun {
  started_at: string
  ok: number | boolean
  items: number | null
  http_status: number | null
  latency_ms: number | null
  error: string | null
}

export interface SourceFreshness {
  newest_data_at: string | null
  max_age_s: number | null
  age_s: number | null
  stale: boolean
  basis?: 'observations' | 'feed' | 'events' | 'status' | 'run' | string
}

export interface SourceInfo {
  name: string
  title: string
  category: string
  provider: string
  homepage: string
  endpoint: string
  interval_s: number
  description: string
  needs: string[]
  state: SourceState
  last_run: SourceRun | null
  success_rate: number | null
  last_ok_at: string | null
  missing_config: string[]
  /** round 2: data age, independent of fetch success */
  freshness?: SourceFreshness | null
  /** a documented reason when the feed is known to be silent (state stays "stale", but it is expected) */
  expected_stale?: string | null
}

export interface RunResult {
  source: string
  ok: boolean
  items?: number
  ms?: number
  error?: string
  needs_config?: string | string[]
}

export interface AlertRow {
  id: number
  created_at: string
  level: string
  kind: string
  title: string
  body: string | null
  dedup_key: string | null
  delivered: string | null
  url?: string | null
}

export type LevelKey = 'normal' | 'vigilance' | 'prepare' | 'act' | 'leave'

export interface RiskFactor extends ValueKindFields {
  id: string
  label: string
  level: number | null
  level_key: LevelKey | string | null
  value: number | string | null
  unit: string | null
  threshold: string | number | null
  explanation: string | null
  source: string | null
  url: string | null
  observed_at: string | null
  /** set by the risk engine when the underlying data is too old */
  stale?: boolean
  /** level -> threshold text, e.g. {"1": "ONI >= +0.5"} */
  steps?: Record<string, string> | null
  /** what would move this factor up */
  next?: string | null
  details?: Record<string, unknown> | null
  /** round 3 */
  value_raw?: number | string | null
  value_label?: string | null
  summary?: string | null
  inputs?: FactorInput[] | null
}

export interface LevelText {
  level_key: LevelKey | string
  text: string
}

export interface LocalRisk {
  level: number | null
  level_key: LevelKey | string | null
  level_label?: string | null
  headline: string | null
  evaluated_at: string | null
  home: { name: string; lat: number; lon: number; radius_km?: number }
  factors: RiskFactor[]
  actions: LevelText[]
  triggers: LevelText[]
  url?: string
  /** round 2: how many factors have data; level is null when critical ones are missing */
  coverage?: Coverage | null
  /** lowest level the known factors already justify (shown when level is null) */
  level_floor?: number | null
  level_floor_key?: LevelKey | string | null
  /** rules that set the level, e.g. "R1 max of factors (enso)" */
  rules?: string[] | null
  /** plain-text note on the current season */
  season?: string | null
  season_context?: SeasonContext | null
  /** when the level became unknown (critical data missing), else null */
  unknown_since?: string | null
  /** true when every critical factor has data */
  complete?: boolean | null
  /** round 3 */
  headline_local?: string | null
  engine_version?: number | null
  time_basis?: Record<string, string> | null
  next_risk?: string | null
}

export interface SeasonContext {
  id?: string
  label?: string
  focus?: string[]
  note?: string
}

export interface Coverage {
  total: number
  with_data: number
  missing: string[]
  critical_missing: string[]
  /** factors whose data is present but too old */
  stale?: string[]
  /** ids of factors that must have data for the level to be computed */
  critical?: string[]
  level_floor?: number | null
  level_floor_key?: string | null
}

export type SignalStatus = 'ok' | 'caution' | 'blocked' | 'unknown'

export interface ExitSignal extends ValueKindFields {
  id: string
  label: string
  status: SignalStatus | string
  value: string | number | null
  unit?: string | null
  threshold?: string | null
  reason?: string | null
  source: string | null
  url: string | null
  observed_at: string | null
}

export interface ExitRoute {
  id: string
  mode: 'ferry' | 'air' | 'road' | 'rail' | string
  operator: string | null
  from: string | null
  to: string | null
  url: string | null
  notes: string | null
}

export interface ExitWindow extends ValueKindFields {
  date: string
  /** round 3: "Thu 24 Sep" */
  label?: string | null
  ok: boolean
  status?: 'ok' | 'caution' | 'blocked' | 'unknown' | string
  reason: string | null
  wave_max_m?: number | null
  gust_max_kmh?: number | null
}

/** GET /api/local/exit (round 2) */
export interface ExitPlan {
  recommendation: string | null
  signals: ExitSignal[]
  routes: ExitRoute[]
  checklist: { id: string; label: string; priority: string }[]
  windows: ExitWindow[]
  generated_at?: string | null
  evaluated_at?: string | null
  /** date the route list (operators, links) was last checked */
  verified_at?: string | null
  notes?: string[] | null
}

export interface LocalHistoryPoint {
  evaluated_at: string
  level: number | null
}

// /api/local/weather: the contract only says "the local series (forecast + recent)".
// Accepted shapes (normalised in lib/weather.ts):
//  a) {series: {name: [{ts, value, ...}]}} or {name: [{ts, value}]}
//  b) {series: [{series, points: [...]}, ...]} or [{series, points}]
export type LocalWeather = unknown

export type Priority = 'must' | 'should' | 'nice'

export interface PrepItem {
  id: string
  label: string
  qty: number | null
  per: string | null // e.g. "person_day", "person", "household"
  unit?: string | null
  priority: Priority | string
  note: string | null
}

export interface PrepCategory {
  id: string
  title: string
  why: string | null
  items: PrepItem[]
}

export interface PrepScenario {
  id?: string
  title?: string
  name?: string
  summary?: string
  description?: string
  level_key?: string
  steps?: string[]
  actions?: string[]
  [k: string]: unknown
}

export interface PrepContact {
  name?: string
  label?: string
  title?: string
  number?: string
  phone?: string
  url?: string
  note?: string
  [k: string]: unknown
}

export interface PrepSource {
  id?: string
  title?: string
  name?: string
  url: string
  used_for?: string
}

export interface Preparedness {
  categories: PrepCategory[]
  scenarios: PrepScenario[]
  contacts: PrepContact[]
  sources?: (PrepSource | string)[]
}

export interface Household {
  adults: number
  children: number
  days: number
}

export interface PrepState {
  checked: Record<string, boolean>
  household: Household
}

export interface MapLayer {
  id: string
  title: string
  url_template: string
  max_zoom?: number | null
  default_date_offset_days?: number | null
  /** latest date GIBS actually serves (from its capabilities), when known */
  default_date?: string | null
  legend_url?: string | null
  attribution?: string | null
  description?: string | null
  /** provider id: nasa_gibs | rainviewer | ... (help: source_<id>) */
  source?: string | null
  /** daily | latest | resolved (time already resolved by the server, see `time`) */
  time_mode?: string | null
  /** resolved frame time (ISO, UTC) for time_mode "resolved" */
  time?: string | null
  /** GIBS layer identifier (older name `gibs_layer`) */
  gibs_id?: string | null
  gibs_layer?: string | null
  date_source?: string | null
  format?: string | null
  verified?: string | boolean | null
}

/** GET /api/access */
export interface Access {
  public_mode: boolean
  admin: boolean
  admin_header?: string
}

export type CamStatus = 'live' | 'online' | 'reachable' | 'stale' | 'offline' | 'error' | string

/** GET /api/webcams -> webcams[] (rule 11: owner-published public feeds only). */
export interface Webcam {
  id: string
  title: string
  place: string | null
  area: string
  lat: number | null
  lon: number | null
  coord_precision?: string | null
  kind: string
  provider: string | null
  publisher: string | null
  page_url: string | null
  embed_url: string | null
  snapshot_url: string | null
  stream_type: string | null
  /** embed = owner's player, proxy = still image we may show, link = official page only */
  mode: 'embed' | 'proxy' | 'link' | string
  snapshot_allowed: boolean
  refresh_s: number | null
  max_image_age_s: number | null
  license_note: string | null
  why: string | null
  status: CamStatus
  ok: boolean
  live_basis: string | null
  detail: string | null
  last_checked: string | null
  last_ok: string | null
  image_updated_at: string | null
  image_age_s: number | null
  help_id: string | null
  snapshot_proxy: string | null
  distance_km?: number | null
}

export interface WebcamsResponse {
  updated_at: string | null
  parts: Record<string, { updated_at: string; count: number; ok: number } | null> | null
  count: number
  webcams: Webcam[]
  home?: { name: string; lat: number; lon: number }
}

// ---------------------------------------------------------------------------- El Nino analogs
// GET /api/local/analogs (backend/app/local/analogs.py `build`; contract in docs/reports/REVIEW_2026-09-24.md).

/** A peak index value read from the stored NOAA CPC series (never typed in). */
export interface AnalogIndex extends ValueKindFields {
  value: number | null
  season?: string | null
  ts?: string | null
  source?: string
  unit?: string
}

/** One season's rain vs the 1991-2020 normal of the same ERA5 cell. Null = a month is missing. */
export interface AnalogSeasonRain {
  rain_mm: number | null
  normal_mm: number | null
  pct: number | null
  months: string[]
}

export interface AnalogMonth {
  month: string
  rain_mm: number | null
  n_days: number | null
  normal_mm: number | null
  pct: number | null
  app_max: number | null
  heat_days: number | null
  dry_days: number | null
  complete: boolean
}

export interface AnalogHeat {
  max_feels_like: number | null
  max_feels_like_month?: string | null
  max_feels_like_day: string | null
  max_temp: number | null
  heat_days: number | null
  months: string[]
  normal_heat_days: number | null
  normal_max_feels_like: number | null
}

/** The flat numbers of an event's water year (all null while the history is loading). */
export interface AnalogSamui {
  ne_monsoon_rain_pct: number | null
  dry_season_rain_pct: number | null
  feb_apr_rain_pct: number | null
  year_rain_pct: number | null
  max_feels_like: number | null
  max_feels_like_day: string | null
  max_temp: number | null
  heat_days: number | null
  longest_dry_spell_days: number | null
  longest_dry_spell_ne_days: number | null
  ne_monsoon_rain_mm: number | null
  dry_season_rain_mm: number | null
  feb_apr_rain_mm: number | null
  complete: boolean
  kind: 'reanalysis' | string
}

export interface AnalogDetail {
  water_year: string
  sw_monsoon: AnalogSeasonRain | null
  ne_monsoon: AnalogSeasonRain | null
  dry_season: AnalogSeasonRain | null
  feb_apr: AnalogSeasonRain | null
  year: AnalogSeasonRain | null
  heat: AnalogHeat | null
  longest_dry_spell_days: number | null
  longest_dry_spell_ne_days: number | null
  monthly: AnalogMonth[]
  complete: boolean
}

/** A dated report whose URL was checked live (kind "documented"); `quote` is verbatim. */
export interface AnalogImpact {
  date: string
  type: string
  area: string
  events: string[]
  enso: string
  text: string
  source_title: string
  url: string
  publisher: string
  published: string
  quote: string
  checked_at: string
  note: string | null
  kind: 'documented' | string
}

export interface AnalogEvent {
  id: string
  years: number[]
  listed_as?: string
  note: string | null
  peak_oni: AnalogIndex | null
  peak_roni: AnalogIndex | null
  strength: string | null
  oni_jja: number | null
  roni_jja: number | null
  samui: AnalogSamui
  detail: AnalogDetail
  impacts: AnalogImpact[]
}

export interface AnalogMetricStat {
  label: string
  unit: string
  unit_label: string
  median: number | null
  mean: number | null
  min: number | null
  max: number | null
  n: number
}

export interface AnalogCurrentEvent {
  id: string
  years: number[]
  oni: AnalogIndex | null
  roni: AnalogIndex | null
  nino34_weekly: AnalogIndex | null
  strength: string | null
  month: string
  so_far: {
    sw_monsoon: AnalogSeasonRain | null
    ne_monsoon: AnalogSeasonRain | null
    monthly: AnalogMonth[]
    last_day: string | null
    kind: string
  } | null
  impacts: AnalogImpact[]
}

export interface Analogs {
  generated_at: string
  point: { lat: number | null; lon: number | null; elevation?: number | null }
  history: {
    from: string | null
    to: string | null
    last_day: string | null
    months: number
    /** decade windows still to fetch: while non-empty the numbers are "loading, not estimated" */
    windows_pending: string[]
    updated_at: string | null
    stats_version?: number | null
  }
  events: AnalogEvent[]
  neutral_baseline: { years: number[]; n: number; rule: string; metrics: Record<string, AnalogMetricStat> }
  normal: { period: string; months: Record<string, { rain_mm: number; app_max: number; tmax_max: number; heat_days: number; dry_days: number; years: number }> | null }
  current_event: AnalogCurrentEvent
  takeaways: string[]
  other_impacts: AnalogImpact[]
  impacts_not_found: string[]
  kinds: Record<string, string>
  method: string
  sources: { id: string; title: string; url: string }[]
}

/** GET /api/local/analogs/history: the raw monthly ERA5 table behind the analogs (for charts). */
export interface AnalogsHistory {
  /** "YYYY-MM" -> one row per `fields` (rain_mm, n_days, tmax_max, tmax_mean, app_max, app_mean, heat_days, ...) */
  months: Record<string, (number | null)[]>
  fields: string[]
  normals: Record<string, { rain_mm: number; app_max: number; tmax_max: number; heat_days: number; dry_days: number; years: number }> | null
  point?: { lat: number | null; lon: number | null; elevation?: number | null } | null
  last_day?: string | null
  windows?: Record<string, { fetched_at: string; start: string; end: string } | null> | null
  updated_at: string | null
  kind?: string
  source?: string
  url?: string
}
