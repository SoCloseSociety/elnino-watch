import type { TaoBuoy } from '../api/types'

/** tao_buoys status value: accept a bare list or {buoys|stations|items: [...]} */
export function buoysFrom(v: unknown): TaoBuoy[] {
  const arr = Array.isArray(v) ? v : v && typeof v === 'object'
    ? ((v as Record<string, unknown>).buoys ?? (v as Record<string, unknown>).stations ?? (v as Record<string, unknown>).items)
    : null
  if (!Array.isArray(arr)) return []
  return arr
    .map((b) => {
      const o = b as Record<string, unknown>
      const num = (x: unknown) => (typeof x === 'number' ? x : typeof x === 'string' && x.trim() !== '' ? Number(x) : null)
      return {
        ...(o as object),
        lat: num(o.lat ?? o.latitude) as number,
        lon: num(o.lon ?? o.lng ?? o.longitude) as number,
        sst: num(o.sst ?? o.value ?? o.temp),
        sst_anom: num(o.sst_anom ?? o.anom ?? o.anomaly),
      } as TaoBuoy
    })
    .filter((b) => Number.isFinite(b.lat) && Number.isFinite(b.lon))
}

export interface NamedSeries {
  name: string
  unit?: string | null
  points: { ts: string; value: number | null }[]
}

function toPoints(a: unknown): { ts: string; value: number | null }[] {
  if (!Array.isArray(a)) return []
  return a
    .map((p) => {
      const o = p as Record<string, unknown>
      const ts = (o.ts ?? o.time ?? o.date) as string | undefined
      const v = o.value ?? o.v
      return ts ? { ts: String(ts), value: typeof v === 'number' ? v : v === null || v === undefined ? null : Number(v) } : null
    })
    .filter((x): x is { ts: string; value: number | null } => !!x)
}

/** /api/local/weather: accept several reasonable shapes, return named series. */
export function weatherSeries(w: unknown): NamedSeries[] {
  if (!w) return []
  // shape used by the backend: {days: [{date, forecast, precip, era5_precip, normal_precip, ...}]}
  const days = (w as Record<string, unknown>).days
  if (Array.isArray(days)) {
    const by = new Map<string, { ts: string; value: number | null }[]>()
    for (const d of days as Record<string, unknown>[]) {
      const ts = String(d.date ?? d.ts ?? '')
      if (!ts) continue
      for (const [k, v] of Object.entries(d)) {
        if (k === 'date' || k === 'ts' || typeof v !== 'number') continue
        if (!by.has(k)) by.set(k, [])
        by.get(k)!.push({ ts, value: v })
      }
    }
    return [...by.entries()].map(([name, points]) => ({ name, points }))
  }
  const root = (w as Record<string, unknown>).series ?? w
  const out: NamedSeries[] = []
  if (Array.isArray(root)) {
    for (const s of root) {
      const o = s as Record<string, unknown>
      const name = (o.series ?? o.name ?? o.id) as string | undefined
      if (name) out.push({ name, unit: (o.unit as string) ?? null, points: toPoints(o.points ?? o.data) })
    }
  } else if (root && typeof root === 'object') {
    for (const [name, v] of Object.entries(root as Record<string, unknown>)) {
      if (Array.isArray(v)) out.push({ name, points: toPoints(v) })
      else if (v && typeof v === 'object' && Array.isArray((v as Record<string, unknown>).points)) {
        const o = v as Record<string, unknown>
        out.push({ name, unit: (o.unit as string) ?? null, points: toPoints(o.points) })
      }
    }
  }
  return out.filter((s) => s.points.length)
}
