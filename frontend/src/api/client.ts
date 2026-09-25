import { useQuery, type UseQueryOptions } from '@tanstack/react-query'
import type {
  Access, AlertRow, Analogs, AnalogsHistory, Briefing, Facets, CatalogEntry, ExitPlan, EventItem, FeedItem, Health, LatestPoint, LocalHistoryPoint,
  LocalRisk, LocalWeather, MapLayer, Preparedness, PrepState, SeriesResponse, SourceInfo,
  StatusDoc, StatusMap, WebcamsResponse,
} from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/**
 * Admin token for the public site (PUBLIC_MODE): writes need the X-Admin-Token header. It is kept in
 * this browser only (same key the Places page used) and sent with every API call when set.
 */
export const ADMIN_TOKEN_KEY = 'elnino.places.admin_token'
export function adminToken(): string {
  try { return window.localStorage.getItem(ADMIN_TOKEN_KEY) ?? '' } catch { return '' }
}
export function setAdminToken(t: string) {
  try {
    if (t) window.localStorage.setItem(ADMIN_TOKEN_KEY, t)
    else window.localStorage.removeItem(ADMIN_TOKEN_KEY)
  } catch { /* storage blocked: token lives for this page only */ }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const tok = adminToken()
  const r = await fetch(`/api${path}`, {
    ...init,
    headers: {
      Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(tok ? { 'X-Admin-Token': tok } : {}), ...init?.headers,
    },
  })
  if (!r.ok) {
    let msg = r.statusText
    try {
      const j = await r.json()
      msg = typeof j?.detail === 'string' ? j.detail : JSON.stringify(j?.detail ?? j)
    } catch {
      /* not json */
    }
    throw new ApiError(r.status, msg)
  }
  const ct = r.headers.get('content-type') ?? ''
  // the SPA fallback answers unknown /api paths with index.html: treat as "not built yet"
  if (!ct.includes('json')) throw new ApiError(404, `endpoint missing: /api${path}`)
  return r.json() as Promise<T>
}

export function qs(params: Record<string, string | number | undefined | null>): string {
  const u = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') u.set(k, String(v))
  const s = u.toString()
  return s ? `?${s}` : ''
}

/** 404 = "not produced yet": return null instead of an error. */
async function orNull<T>(p: Promise<T>): Promise<T | null> {
  try {
    return await p
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }
}

type Opts<T> = Omit<UseQueryOptions<T, Error, T, readonly unknown[]>, 'queryKey' | 'queryFn'>

export const useHealth = () =>
  useQuery({ queryKey: ['health'], queryFn: () => api<Health>('/health'), refetchInterval: 30_000, retry: 0 })

/**
 * GET /api/access: {public_mode, admin}. `canWrite` = the server accepts writes from this browser
 * (private install, or public site with a valid admin token). While loading, canWrite is false so
 * admin-only buttons never flash on the public site.
 */
export function useAccess() {
  const q = useQuery({ queryKey: ['access'], queryFn: () => orNull(api<Access>('/access')), refetchInterval: false, staleTime: 5 * 60_000 })
  const a = q.data
  // an API without /api/access (older backend) is a private install
  const publicMode = a ? a.public_mode : false
  const admin = a ? a.admin : false
  return { loaded: q.isFetched, publicMode, admin, canWrite: q.isFetched && (!publicMode || admin) }
}

export const useWebcams = (params: Record<string, string | number | boolean | undefined | null> = {}) =>
  useQuery({
    queryKey: ['webcams', params],
    queryFn: () => orNull(api<WebcamsResponse>(`/webcams${qs(Object.fromEntries(Object.entries(params).map(([k, v]) => [k, typeof v === 'boolean' ? String(v) : v])))}`)),
    refetchInterval: 5 * 60_000,
  })

export const useLatest = () => useQuery({ queryKey: ['latest'], queryFn: () => api<LatestPoint[]>('/latest') })

export const useCatalog = () => useQuery({ queryKey: ['catalog'], queryFn: () => api<CatalogEntry[]>('/series/catalog') })

export interface SeriesParams {
  source: string
  series: string
  since?: string
  until?: string
  limit?: number
  downsample?: string
}

/**
 * Series requests made in the same tick are coalesced into `GET /api/series/batch` calls (<= 40
 * keys each, one call per distinct since/until/limit/downsample). The Indices page draws ~80
 * series: one request each tripped the public site's nginx rate limit (10 r/s, burst 40) and half
 * the charts showed "--" (QA, 24 Sep 2026). A backend without the batch route (404) falls back to
 * one GET /api/series per key.
 */
const SERIES_BATCH_MAX = 40
type Waiter = { key: string; resolve: (r: SeriesResponse) => void; reject: (e: unknown) => void }
const seriesQueue = new Map<string, { common: Omit<SeriesParams, 'source' | 'series'>; waiters: Waiter[] }>()
let seriesFlushTimer: ReturnType<typeof setTimeout> | null = null

async function flushSeriesQueue() {
  seriesFlushTimer = null
  const groups = [...seriesQueue.values()]
  seriesQueue.clear()
  for (const g of groups) {
    const byKey = new Map<string, Waiter[]>()
    for (const w of g.waiters) byKey.set(w.key, [...(byKey.get(w.key) ?? []), w])
    const keys = [...byKey.keys()]
    for (let i = 0; i < keys.length; i += SERIES_BATCH_MAX) {
      const chunk = keys.slice(i, i + SERIES_BATCH_MAX)
      const settle = (key: string, r: SeriesResponse) => byKey.get(key)?.forEach((w) => w.resolve(r))
      const fail = (key: string, e: unknown) => byKey.get(key)?.forEach((w) => w.reject(e))
      try {
        const res = await api<{ items: SeriesResponse[] }>(`/series/batch${qs({ ...g.common, keys: chunk.join(',') })}`)
        const got = new Map(res.items.map((it) => [`${it.source}:${it.series}`, it]))
        for (const key of chunk) {
          const [source, series] = key.split(':', 2)
          settle(key, got.get(key) ?? { source, series, points: [] })
        }
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          // older backend: one request per series
          await Promise.all(chunk.map(async (key) => {
            const [source, series] = key.split(':', 2)
            try { settle(key, await api<SeriesResponse>(`/series${qs({ ...g.common, source, series })}`)) } catch (err) { fail(key, err) }
          }))
        } else {
          for (const key of chunk) fail(key, e)
        }
      }
    }
  }
}

export function fetchSeries(p: SeriesParams): Promise<SeriesResponse> {
  const common = { since: p.since, until: p.until, limit: p.limit, downsample: p.downsample }
  const groupId = JSON.stringify([p.since ?? '', p.until ?? '', p.limit ?? '', p.downsample ?? ''])
  return new Promise<SeriesResponse>((resolve, reject) => {
    const g = seriesQueue.get(groupId) ?? { common, waiters: [] }
    g.waiters.push({ key: `${p.source}:${p.series}`, resolve, reject })
    seriesQueue.set(groupId, g)
    if (seriesFlushTimer === null) seriesFlushTimer = setTimeout(() => { void flushSeriesQueue() }, 10)
  })
}

export const useSeries = (source: string | undefined, series: string | undefined, since?: string, opts?: Opts<SeriesResponse>) =>
  useQuery({
    queryKey: ['series', source, series, since ?? ''],
    queryFn: () => fetchSeries({ source: source!, series: series!, since }),
    enabled: !!source && !!series,
    ...opts,
  })

export const useStatusAll = () => useQuery({ queryKey: ['status'], queryFn: () => api<StatusMap>('/status') })

export function useStatus<T>(key: string) {
  return useQuery({
    queryKey: ['status', key],
    queryFn: () => orNull(api<StatusDoc<T>>(`/status/${encodeURIComponent(key)}`)),
  })
}

export const useFeed = (params: Record<string, string | number | undefined>) =>
  useQuery({ queryKey: ['feed', params], queryFn: () => api<FeedItem[]>(`/feed${qs(params)}`) })

export const useEvents = () => useQuery({ queryKey: ['events'], queryFn: () => api<EventItem[]>('/events') })

export const useSources = () => useQuery({ queryKey: ['sources'], queryFn: () => api<SourceInfo[]>('/sources') })

export const useAlerts = () => useQuery({ queryKey: ['alerts'], queryFn: () => api<AlertRow[]>('/alerts?limit=20') })

export const useLocal = () => useQuery({ queryKey: ['local'], queryFn: () => orNull(api<LocalRisk>('/local')) })

export const useLocalHistory = () =>
  useQuery({ queryKey: ['local', 'history'], queryFn: () => orNull(api<LocalHistoryPoint[]>('/local/history')) })

export const useLocalWeather = () =>
  useQuery({ queryKey: ['local', 'weather'], queryFn: () => orNull(api<LocalWeather>('/local/weather')) })

export const usePreparedness = () =>
  useQuery({ queryKey: ['prep'], queryFn: () => orNull(api<Preparedness>('/preparedness')), refetchInterval: false })

/** Server-side checklist state. Disabled on the public site (it is per-browser there: localStorage). */
export const usePrepState = (enabled = true) =>
  useQuery({ queryKey: ['prep', 'state'], queryFn: () => orNull(api<PrepState>('/preparedness/state')), refetchInterval: false, enabled })

export const useLayers = () =>
  useQuery({ queryKey: ['layers'], queryFn: async () => {
    const r = await orNull(api<MapLayer[] | { layers: MapLayer[] }>('/layers'))
    if (!r) return []
    return Array.isArray(r) ? r : (r.layers ?? [])
  }, refetchInterval: 10 * 60_000 })

export const useBriefing = () =>
  useQuery({ queryKey: ['briefing'], queryFn: () => orNull(api<Briefing>('/briefing')), refetchInterval: 5 * 60_000 })

export const useLocalExit = () =>
  useQuery({ queryKey: ['local', 'exit'], queryFn: () => orNull(api<ExitPlan>('/local/exit')), refetchInterval: 5 * 60_000 })

type Params = Record<string, string | number | boolean | undefined | null>
const clean = (p: Params) => Object.fromEntries(Object.entries(p).filter(([, v]) => v !== undefined && v !== null && v !== '').map(([k, v]) => [k, typeof v === 'boolean' ? String(v) : v])) as Record<string, string | number>

/** Round-2 filtered lists and facet counts (every list filter takes a comma list). */
export const useFeedFacets = (params: Params) =>
  useQuery({ queryKey: ['feed-facets', clean(params)], queryFn: () => orNull(api<Facets>(`/feed/facets${qs(clean(params))}`)) })

export const useEventsQ = (params: Params, opts?: { enabled?: boolean }) =>
  useQuery({ queryKey: ['events', clean(params)], queryFn: () => api<EventItem[]>(`/events${qs(clean(params))}`), ...opts })

export const useEventFacets = (params: Params) =>
  useQuery({ queryKey: ['events-facets', clean(params)], queryFn: () => orNull(api<Facets>(`/events/facets${qs(clean(params))}`)) })

export const useAlertsQ = (params: Params) =>
  useQuery({ queryKey: ['alerts', clean(params)], queryFn: () => api<AlertRow[]>(`/alerts${qs(clean(params))}`) })

export const useSourcesQ = (params: Params) =>
  useQuery({ queryKey: ['sources', clean(params)], queryFn: () => api<SourceInfo[]>(`/sources${qs(clean(params))}`) })

export const useCatalogQ = (params: Params) =>
  useQuery({ queryKey: ['catalog', clean(params)], queryFn: () => api<CatalogEntry[]>(`/series/catalog${qs(clean(params))}`) })

/** Facet list helper: [{value, count}] for one facet name (empty when absent). */
export function facet(f: Facets | null | undefined, name: string): { value: string; count: number }[] {
  const v = f?.[name]
  return Array.isArray(v) ? v.filter((x) => x.value !== null && x.value !== '').map((x) => ({ value: String(x.value), count: x.count })) : []
}

/** GET /api/local/analogs: what past strong El Ninos did to Koh Samui (ERA5 + documented reports). */
export const useAnalogs = () =>
  useQuery({ queryKey: ['local', 'analogs'], queryFn: () => orNull(api<Analogs>('/local/analogs')), refetchInterval: 10 * 60_000 })

/** GET /api/local/analogs/history: the monthly ERA5 table (charts of the Past El Ninos page). */
export const useAnalogsHistory = () =>
  useQuery({ queryKey: ['local', 'analogs', 'history'], queryFn: () => orNull(api<AnalogsHistory>('/local/analogs/history')), refetchInterval: 10 * 60_000 })
