// Formatting + domain helpers (English UI).
import type { LocalRisk } from '../api/types'

export function parseTs(ts: string | null | undefined): Date | null {
  if (!ts) return null
  // Bare dates are treated as UTC midnight so they do not shift a day.
  const s = /^\d{4}-\d{2}-\d{2}$/.test(ts) ? `${ts}T00:00:00Z` : ts
  const d = new Date(s)
  return Number.isNaN(d.getTime()) ? null : d
}

export function ageMs(ts: string | null | undefined): number | null {
  const d = parseTs(ts)
  return d ? Date.now() - d.getTime() : null
}

export function relTime(ts: string | null | undefined): string {
  const ms = ageMs(ts)
  if (ms === null) return 'unknown date'
  const future = ms < 0
  const a = Math.abs(ms)
  const m = Math.round(a / 60000)
  let s: string
  if (m < 1) return future ? 'in a moment' : 'just now'
  if (m < 60) s = `${m} min`
  else if (m < 60 * 24) s = `${Math.round(m / 60)} h`
  else if (m < 60 * 24 * 45) s = `${Math.round(m / 1440)} d`
  else if (m < 60 * 24 * 400) s = `${Math.round(m / 43200)} mo`
  else s = `${(m / 525600).toFixed(1)} yr`
  return future ? `in ${s}` : `${s} ago`
}

export const LOCALE = 'en-GB'
const dFmt = new Intl.DateTimeFormat(LOCALE, { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
const dtFmt = new Intl.DateTimeFormat(LOCALE, {
  day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
})
const mFmt = new Intl.DateTimeFormat(LOCALE, { month: 'short', year: 'numeric', timeZone: 'UTC' })
const dmFmt = new Intl.DateTimeFormat(LOCALE, { day: 'numeric', month: 'short', timeZone: 'UTC' })

export function fmtDate(ts: string | null | undefined): string {
  if (ts && ts.includes('/')) return fmtDateTz(ts, 'UTC')
  const d = parseTs(ts)
  if (!d) return '--'
  return ts && ts.length <= 10 ? dFmt.format(d) : dtFmt.format(d)
}
export function fmtMonth(ts: string | null | undefined): string {
  const d = parseTs(ts)
  return d ? mFmt.format(d) : '--'
}
export function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '--'
  return v.toLocaleString(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits })
}
export function fmtSigned(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '--'
  const s = fmtNum(Math.abs(v), digits)
  return v > 0 ? `+${s}` : v < 0 ? `-${s}` : s
}

/** ENSO strength label for a Nino 3.4 / ONI anomaly. */
export function strength(v: number | null | undefined): { label: string; tone: 'warm' | 'cold' | 'neutral' } {
  if (v === null || v === undefined) return { label: '--', tone: 'neutral' }
  const a = Math.abs(v)
  const phase = v > 0 ? 'El Nino' : 'La Nina'
  const tone = v > 0 ? 'warm' : 'cold'
  if (a >= 2) return { label: `${phase} very strong`, tone }
  if (a >= 1.5) return { label: `${phase} strong`, tone }
  if (a >= 1.0) return { label: `${phase} moderate`, tone }
  if (a >= 0.5) return { label: `${phase} weak`, tone }
  return { label: 'Neutral', tone: 'neutral' }
}

export function anomColor(v: number | null | undefined): string {
  if (v === null || v === undefined) return 'var(--neutral)'
  if (v >= 1.5) return 'var(--warm-2)'
  if (v >= 0.5) return 'var(--warm)'
  if (v <= -1.5) return 'var(--cold-2)'
  if (v <= -0.5) return 'var(--cold)'
  return 'var(--neutral)'
}

export const LEVELS = [
  { key: 'normal', label: 'Normal', color: 'var(--good)', icon: '●' },
  { key: 'vigilance', label: 'Watch', color: 'var(--warning)', icon: '▲' },
  { key: 'prepare', label: 'Prepare', color: 'var(--serious)', icon: '▲' },
  { key: 'act', label: 'Act', color: 'var(--critical)', icon: '■' },
  { key: 'leave', label: 'Leave', color: 'var(--extreme)', icon: '■' },
] as const

export function levelMeta(level: number | null | undefined, key?: string | null) {
  if (key) {
    // 'watch' accepted as an alias of the 'vigilance' key
    const k = key === 'watch' ? 'vigilance' : key
    const f = LEVELS.find((l) => l.key === k)
    if (f) return { ...f, n: LEVELS.indexOf(f) }
  }
  if (level === null || level === undefined || level < 0 || level > 4) return null
  return { ...LEVELS[level], n: level }
}

export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371
  const r = Math.PI / 180
  const dLat = (lat2 - lat1) * r
  const dLon = (lon2 - lon1) * r
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

/**
 * The watched place (the same point as backend settings.home_*). The distance filters, the home
 * circle and "near Samui" use it. Defaults to the centre of Koh Samui; override at build time with
 * VITE_HOME_NAME / VITE_HOME_LAT / VITE_HOME_LON / VITE_HOME_RADIUS_KM (frontend/.env.local).
 */
const env = import.meta.env
const num = (v: unknown, d: number) => (v === undefined || v === '' || Number.isNaN(Number(v)) ? d : Number(v))
export const HOME = {
  name: (env.VITE_HOME_NAME as string | undefined) || 'Koh Samui',
  lat: num(env.VITE_HOME_LAT, 9.512),
  lon: num(env.VITE_HOME_LON, 100.013),
  radiusKm: num(env.VITE_HOME_RADIUS_KM, 800),
}

export function tagsOf(t: string[] | string | null | undefined): string[] {
  if (!t) return []
  if (Array.isArray(t)) return t.map(String)
  try {
    const j = JSON.parse(t)
    return Array.isArray(j) ? j.map(String) : [String(t)]
  } catch {
    return t.split(',').map((s) => s.trim()).filter(Boolean)
  }
}

export function isoDaysAgo(days: number): string {
  return new Date(Date.now() - days * 86400000).toISOString().slice(0, 10)
}

export const DAY = 86400000

/** Readable text colour derived from a fill colour (mixes toward --ink so it passes WCAG AA in both themes). */
export function toneText(c: string): string {
  return `color-mix(in srgb, ${c} 58%, var(--ink))`
}

/** Compact duration from seconds: 45 min, 6 h, 12 d, 3 mo. */
export function fmtDuration(s: number | null | undefined): string {
  if (s === null || s === undefined || !Number.isFinite(s)) return '--'
  const a = Math.abs(s)
  if (a < 3600) return `${Math.max(1, Math.round(a / 60))} min`
  if (a < 2 * 86400) return `${Math.round(a / 3600)} h`
  if (a < 60 * 86400) return `${Math.round(a / 86400)} d`
  if (a < 730 * 86400) return `${Math.round(a / (30 * 86400))} mo`
  return `${(a / (365 * 86400)).toFixed(1)} yr`
}

/** Minimum level the known factors justify when the overall level is unknown (round 2). */
export function riskFloor(r: LocalRisk | null | undefined): { level: number | null; key: string | null } | null {
  if (!r) return null
  const level = r.level_floor ?? r.coverage?.level_floor ?? null
  const key = r.level_floor_key ?? r.coverage?.level_floor_key ?? null
  return level === null && !key ? null : { level, key }
}

/** Unit strings from the API use "degC"; the UI writes "C". Raw ISO datetimes in API prose are shown in local time. */
/** Display text for units and unit-bearing text: machine codes (degC, ug/m3) become °C and µg/m³ (round 3 rule). */
export function fmtUnit(u: string | null | undefined): string {
  return (u ?? '')
    .replace(/\bdeg\s?C\b/g, '°C')
    .replace(/\bdegC(?=-)/g, '°C')
    .replace(/\bug\/m3\b/g, 'µg/m³')
    .replace(/\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})/g, (m) => fmtDate(m))
}

/** Display time zones: ICT (Asia/Bangkok, UTC+7) for Koh Samui values, UTC for global ones. */
export type DisplayTz = 'ICT' | 'UTC'
/** Backend `tz` ("ICT (UTC+7)" | "UTC") -> display zone. */
export const tzOf = (tz: string | null | undefined, fallback: DisplayTz = 'UTC'): DisplayTz => (tz ? (/ICT|\+7/.test(tz) ? 'ICT' : 'UTC') : fallback)
const TZ_NAME: Record<DisplayTz, string> = { ICT: 'Asia/Bangkok', UTC: 'UTC' }
const tzFmt: Partial<Record<DisplayTz, Intl.DateTimeFormat>> = {}

/** Date (+ time when the value has one) in the given zone, with the zone label: "24 Sept 2026, 21:00 ICT". */
export function fmtDateTz(ts: string | null | undefined, tz: DisplayTz = 'UTC'): string {
  // round 3 `valid_for` interval "start/end" (both days inclusive)
  if (ts && ts.includes('/')) {
    const [a, b] = ts.split('/')
    if (a.length <= 10 && b.length <= 10 && a.slice(0, 4) === b.slice(0, 4)) {
      const da = parseTs(a), db = parseTs(b)
      if (da && db) return `${dmFmt.format(da)} to ${dFmt.format(db)}`
    }
    return `${fmtDateTz(a, tz)} to ${fmtDateTz(b, tz)}`
  }
  const d = parseTs(ts)
  if (!ts) return '--'
  if (!d) return ts // a period the backend wrote as text (e.g. a season code): show it, never "--"
  if (ts.length <= 10) return dFmt.format(d) // a calendar date has no zone
  const f = (tzFmt[tz] ??= new Intl.DateTimeFormat(LOCALE, {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: TZ_NAME[tz],
  }))
  return `${f.format(d)} ${tz}`
}

/** Value kinds the backend tags on factors / series (round 3). */
export type ValueKind = 'observed' | 'forecast' | 'model_analysis' | 'reanalysis' | 'bulletin' | 'documented'
export const VALUE_KIND: Record<ValueKind, { label: string; color: string; icon: string; hint: string }> = {
  observed: { label: 'Observed', color: 'var(--good-ink)', icon: '●', hint: 'Measured value (instrument, station, satellite or buoy) at the time shown' },
  forecast: { label: 'Forecast', color: 'var(--s7)', icon: '◇', hint: 'A model forecast for the date shown, not a measurement: it can change at each update' },
  model_analysis: { label: 'Model', color: 'var(--s4)', icon: '◆', hint: 'A model analysis (best estimate combining observations and a model), not a direct measurement' },
  reanalysis: { label: 'Reanalysis', color: 'var(--s1)', icon: '◈', hint: 'A reanalysis (e.g. ERA5): observations blended by a model after the fact, usually a few days behind' },
  bulletin: { label: 'Bulletin', color: 'var(--s5)', icon: '■', hint: 'An official bulletin or warning text issued by an agency' },
  documented: { label: 'Documented', color: 'var(--s6)', icon: '▣', hint: 'A dated report (press, agency or peer-reviewed) whose link was checked live; the quote is verbatim' },
}

/** Infer the kind when the backend does not send one yet: a date in the future is a forecast. */
export function inferKind(kind: string | null | undefined, ts?: string | null): ValueKind | null {
  if (kind && kind in VALUE_KIND) return kind as ValueKind
  const d = parseTs(ts)
  if (d && d.getTime() > Date.now() + 3600000) return 'forecast'
  return null
}
