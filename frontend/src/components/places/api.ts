// Types + hooks for the Places page (/api/places*). Mirrors backend/app/places/{engine,api}.py.
import { useQueries, useQuery } from '@tanstack/react-query'
import { api, ApiError, qs } from '../../api/client'

export interface Source { title: string; url: string }

export interface PlaceFactor {
  id: string
  label: string
  level: number | null
  level_key: string | null
  value: number | string | null
  unit: string | null
  threshold: string
  explanation: string
  source: string
  url: string
  observed_at: string | null
  kind: string | null
  /** round-3 provenance, when the places engine sends it */
  unit_label?: string | null
  valid_for?: string | null
  as_of?: string | null
  retrieved_at?: string | null
  stale: boolean
  critical: boolean
  details: Record<string, unknown>
}

export interface CurrentConditions {
  time: string
  kind: string
  temperature_2m: number | null
  apparent_temperature: number | null
  relative_humidity_2m: number | null
  precipitation: number | null
  weather_code: number | null
  wind_speed_10m: number | null
  wind_gusts_10m: number | null
  is_day: number | null
  weather: string | null
  updated_at: string | null
  source: string
  url: string
}

export interface PlaceBase {
  id: string
  name: string
  short_name: string
  admin?: string
  country: string | null
  country_code: string | null
  lat: number
  lon: number
  elevation_m?: number | null
  timezone?: string
  role: 'home' | 'candidate'
  geocode?: { source: string; url: string | null; checked: string; note?: string }
  added_by?: string | null
}

export interface PlaceSummary extends PlaceBase {
  level: number | null
  level_key: string | null
  level_floor: number | null
  level_floor_key: string | null
  rules: string[]
  missing_critical: string[]
  headline: string
  evaluated_at: string
  current: CurrentConditions | null
  factors?: PlaceFactor[]
  samui_watch?: { level: number | null; level_key: string | null; headline: string; evaluated_at: string; url: string }
}

export interface MonthNormal {
  month: number
  t_mean: number; t_max: number; t_min: number
  precip_mm: number; rain_days: number; sunshine_h: number; snow_cm: number; et0_mm: number
  heat_days: number; frost_days: number; heavy_rain_days: number; gust_days: number
}

export interface Normals {
  source: string; url: string; period: string; years: number
  months: MonthNormal[]
  annual: Record<string, number | number[] | null>
  notes: string
  updated_at: string
}

export interface Ens { mean: number; min: number; max: number }
export interface Projection {
  source: string; url: string; scenario: string; baseline: string; future: string
  models: string[]; n_models: number
  baseline_mean: Record<string, Ens>; future_mean: Record<string, Ens>
  delta: { t_mean: Ens; precip_pct: Ens; hot_days_yr: Ens; frost_days_yr: Ens }
  note: string; updated_at: string
}

export interface SeasonalMonth {
  month: string; precip_mean_mm: number | null; precip_anomaly_mm: number | null
  precip_pct_of_model_normal: number | null; temp_mean_c: number | null; temp_anomaly_c: number | null
}

export interface DailyForecast {
  date: string; forecast: boolean
  temperature_2m_max: number | null; temperature_2m_min: number | null
  apparent_temperature_max: number | null; apparent_temperature_min: number | null
  precipitation_sum: number | null; precipitation_probability_max: number | null
  wind_gusts_10m_max: number | null; uv_index_max: number | null; snowfall_sum: number | null
}

export interface ExposureCell {
  score: number | null; label: string | null; value: number | string | null; unit: string | null
  rule: string; note: string; source: string; url: string; as_of: string | null
  details: Record<string, unknown>
}

export interface EnsoAssessment {
  assessed: boolean; region: string | null; region_label: string | null
  strength: number | null; strength_label: string
  mechanism: string; el_nino_effect: string | null; outlook_2026_27: string | null
  sources: Source[]
}

export interface EnsoNow {
  roni: { ts: string; value: number; source: string } | null
  oni: { ts: string; value: number; source: string } | null
  nino34_weekly: { ts: string; value: number; source: string } | null
  cpc_status: string | null; cpc_issued: string | null
  iri_issued: string | null
  iri_probabilities: { season: string; la_nina: number; neutral: number; el_nino: number }[]
}

export interface Advisory {
  provider: string; updated: string | null; headline: string | null; url: string
  level?: number; alert_status?: string[]; latest_change?: string | null
  headlines?: string[]; headline_urls?: string[]; lang?: string; reviewed?: string | null
}
export interface Advisories { fcdo?: Advisory; state?: Advisory; fr_diplomatie?: Advisory; fetched_at?: string }

export interface ContextNote { dimension: string; text: string; sources: Source[] }

export interface PlaceDetail extends PlaceSummary {
  forecast: { daily: DailyForecast[]; updated_at: string; source: string; url: string } | null
  normals: Normals | null
  recent: { last_day: string; updated_at: string; rain_30d: number; rain_90d: number } | null
  seasonal: { model: string; url: string; months: SeasonalMonth[]; updated_at: string } | null
  projection: Projection | null
  marine: { sea_cell: boolean; cell_distance_km: number | null; current: { wave_height: number | null; sea_surface_temperature: number | null; time: string }; updated_at: string } | null
  river: { cell: { lat: number; lon: number; mean_m3s: number; distance_km: number; elevation: number | null } | null; climate?: { q2_m3s: number; q10_m3s: number; p99_daily_m3s: number; period?: string }; forecast?: { days: { date: string; q: number; q_ens_max: number | null }[] } | null; forecast_updated_at?: string | null } | null
  quakes_history: { count: number; max_mag: number | null; since: string; radius_km: number } | null
  events_near: { source: string; category: string; title: string; url: string; severity: string; distance_km: number; updated_at: string | null }[]
  exposure: Record<string, ExposureCell>
  enso: EnsoAssessment & { now: EnsoNow }
  advisories: Advisories
  context: ContextNote[]
}

export interface Dimension { id: string; label: string; rank: boolean }

export interface Compare {
  evaluated_at: string
  places: (PlaceBase & { level: number | null; level_key: string | null; headline: string; current: CurrentConditions | null })[]
  dimensions: Dimension[]
  exposure_labels: string[]
  matrix: Record<string, Record<string, ExposureCell>>
  weights: Record<string, number>
  ranking: { id: string; score: number | null; rank: number | null; used: string[]; missing: string[] }[]
  summary: { dimension: string; label: string; text: string; best: string[]; worst: string[] }[]
  advisories: Record<string, Advisories>
  enso_now: EnsoNow
  disclaimer: string
}

export interface PlacesList { places: PlaceSummary[]; public_mode: boolean; can_edit: boolean; max_places: number }

export interface GeoResult {
  id: number | null; name: string; latitude: number; longitude: number; elevation: number | null
  timezone: string | null; country: string | null; country_code: string | null
  admin1: string | null; admin2: string | null; admin3: string | null; feature_code: string | null; population: number | null
}

export interface Preview {
  name: string; lat: number; lon: number; timezone: string
  current: CurrentConditions; daily: DailyForecast[]; fetched_at: string; source: string; url: string
  enso: EnsoAssessment; advisories: Advisories | null; note: string
}

async function orNull<T>(p: Promise<T>): Promise<T | null> {
  try {
    return await p
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }
}

export const usePlacesList = () =>
  useQuery({ queryKey: ['places'], queryFn: () => orNull(api<PlacesList>('/places')), refetchInterval: 5 * 60_000 })

export const useCompare = () =>
  useQuery({ queryKey: ['places', 'compare'], queryFn: () => orNull(api<Compare>('/places/compare')), refetchInterval: 10 * 60_000 })

export function usePlaceDetails(ids: string[]) {
  return useQueries({
    queries: ids.map((id) => ({
      queryKey: ['places', 'detail', id],
      queryFn: () => api<PlaceDetail>(`/places/${encodeURIComponent(id)}`),
      refetchInterval: 10 * 60_000,
    })),
  })
}

export const searchPlaces = (q: string) =>
  api<{ query: string; results: GeoResult[]; source: string }>(`/places/search${qs({ q })}`)

export const previewPlace = (g: GeoResult) =>
  api<Preview>(`/places/preview${qs({ lat: g.latitude, lon: g.longitude, name: g.name, timezone: g.timezone ?? 'GMT', country_code: g.country_code ?? '' })}`)

export function usePreviews(items: GeoResult[]) {
  return useQueries({
    queries: items.map((g) => ({
      queryKey: ['places', 'preview', g.latitude.toFixed(3), g.longitude.toFixed(3)],
      queryFn: () => previewPlace(g),
      staleTime: 30 * 60_000,
      refetchInterval: 30 * 60_000,
    })),
  })
}

export async function addPlace(g: GeoResult, token?: string): Promise<{ place: PlaceBase; note: string }> {
  return api('/places', {
    method: 'POST',
    body: JSON.stringify({ ...g, role: 'candidate' }),
    headers: token ? { 'X-Admin-Token': token } : undefined,
  })
}

export async function removePlace(id: string, token?: string): Promise<{ removed: string }> {
  return api(`/places/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: token ? { 'X-Admin-Token': token } : undefined,
  })
}

/** Exposure score colours: same scale as the risk levels (0 good ... 4 extreme). */
export const EXPOSURE_COLORS = ['var(--good)', 'var(--warning)', 'var(--serious)', 'var(--critical)', 'var(--extreme)']

/** Dimension id -> help topic id (frontend/src/help/topics/places.ts). */
export const DIMENSION_TOPIC: Record<string, string> = {
  heat_stress: 'place_heat_stress', cold: 'place_cold', water: 'place_water', flood: 'place_flood',
  storms: 'place_storms', air: 'place_air', wildfire: 'place_wildfire', earthquakes: 'place_earthquakes',
  enso: 'place_enso', trend_2050: 'place_trend_2050', coverage: 'place_coverage',
}

/** Current factor id -> help topic id. */
export const FACTOR_TOPIC_PLACES: Record<string, string> = {
  heat: 'place_levels', cold: 'place_levels', water: 'place_water', flood: 'place_river', storm: 'place_storms',
  air: 'place_air', wildfire: 'place_wildfire', earthquake: 'place_earthquakes', warnings: 'place_warnings',
}

/** Series colours per place, in list order (theme tokens). */
export const PLACE_COLORS = ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s5)', 'var(--s7)', 'var(--s4)', 'var(--s6)', 'var(--s8)']

export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// ---------------------------------------------------------------- browser-only state

const LS_WEIGHTS = 'elnino.places.weights'
const LS_PERSONAL = 'elnino.places.personal'
const LS_TOKEN = 'elnino.places.admin_token'

function lsGet(k: string): string | null {
  try { return window.localStorage.getItem(k) } catch { return null }
}
function lsSet(k: string, v: string | null) {
  try {
    if (v === null) window.localStorage.removeItem(k)
    else window.localStorage.setItem(k, v)
  } catch { /* storage unavailable: keep in memory only */ }
}

export function loadWeights(): Record<string, number> | null {
  const v = lsGet(LS_WEIGHTS)
  if (!v) return null
  try { return JSON.parse(v) as Record<string, number> } catch { return null }
}
export const saveWeights = (w: Record<string, number> | null) => lsSet(LS_WEIGHTS, w ? JSON.stringify(w) : null)

export function loadPersonal(): GeoResult[] {
  const v = lsGet(LS_PERSONAL)
  if (!v) return []
  try {
    const a = JSON.parse(v)
    return Array.isArray(a) ? (a as GeoResult[]).filter((g) => Number.isFinite(g.latitude) && Number.isFinite(g.longitude)) : []
  } catch { return [] }
}
export const savePersonal = (a: GeoResult[]) => lsSet(LS_PERSONAL, JSON.stringify(a.slice(0, 20)))

export const loadToken = () => lsGet(LS_TOKEN) ?? ''
export const saveToken = (t: string) => lsSet(LS_TOKEN, t || null)

/** Transparent ranking: weighted mean of (4 - exposure) over dimensions with data, 0-100. */
export function rankPlaces(matrix: Compare['matrix'], dims: Dimension[], weights: Record<string, number>, ids: string[]) {
  const rows = ids.map((id) => {
    let num = 0
    let den = 0
    const used: string[] = []
    const missing: string[] = []
    for (const d of dims) {
      if (!d.rank) continue
      const w = weights[d.id] ?? 1
      if (w <= 0) continue
      const s = matrix[d.id]?.[id]?.score
      if (s === null || s === undefined) { missing.push(d.id); continue }
      num += w * (4 - s)
      den += w
      used.push(d.id)
    }
    return { id, score: den ? Math.round((1000 * num) / (4 * den)) / 10 : null, used, missing }
  })
  return rows.sort((a, b) => (b.score ?? -1) - (a.score ?? -1))
}
