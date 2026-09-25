import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

/** How each filter is stored in the URL: list = comma list, str = plain string, bool = "1". */
export type FilterKind = 'list' | 'str' | 'bool'
export type FilterSpec = Record<string, FilterKind>

type Values<S extends FilterSpec> = {
  [K in keyof S]: S[K] extends 'list' ? string[] : S[K] extends 'bool' ? boolean : string
}

/**
 * Filters kept in the URL query string (shareable, survive reload, back button works).
 * Keys can be prefixed (e.g. "al_") when two filter sets live on one page.
 *
 *   const f = useUrlFilters({ kind: 'list', q: 'str', geo: 'bool' })
 *   f.values.kind   // string[]
 *   f.toggle('kind', 'news'); f.set('q', 'samui'); f.reset()
 */
export function useUrlFilters<S extends FilterSpec>(spec: S, prefix = '') {
  const [params, setParams] = useSearchParams()
  const keys = Object.keys(spec) as (keyof S & string)[]

  const values = useMemo(() => {
    const out: Record<string, unknown> = {}
    for (const k of keys) {
      const raw = params.get(prefix + k)
      if (spec[k] === 'list') out[k] = raw ? raw.split(',').map((x) => x.trim()).filter(Boolean) : []
      else if (spec[k] === 'bool') out[k] = raw === '1' || raw === 'true'
      else out[k] = raw ?? ''
    }
    return out as Values<S>
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, prefix])

  const write = useCallback((mut: (p: URLSearchParams) => void) => {
    setParams((prev) => {
      // react-router evaluates this updater against the params of the last RENDER, not the
      // last write: two set() calls in one event handler (the map layer picker did
      // `set('layer', id); set('date', '')`) made the second one drop the first, so picking a
      // satellite layer did nothing (QA 24 Sep 2026). Start from the live URL instead.
      const live = typeof window !== 'undefined' ? window.location.search : null
      const p = new URLSearchParams(live ?? prev)
      mut(p)
      return p
    }, { replace: true })
  }, [setParams])

  const set = useCallback(<K extends keyof S & string>(k: K, v: Values<S>[K]) => {
    write((p) => {
      const name = prefix + k
      if (Array.isArray(v)) (v.length ? p.set(name, v.join(',')) : p.delete(name))
      else if (typeof v === 'boolean') (v ? p.set(name, '1') : p.delete(name))
      else (v ? p.set(name, String(v)) : p.delete(name))
    })
  }, [write, prefix])

  /** Several keys in ONE navigation (preferred over consecutive set() calls). */
  const setMany = useCallback((patch: Partial<Values<S>>) => {
    write((p) => {
      for (const [k, v] of Object.entries(patch) as [keyof S & string, unknown][]) {
        const name = prefix + k
        if (Array.isArray(v)) (v.length ? p.set(name, v.join(',')) : p.delete(name))
        else if (typeof v === 'boolean') (v ? p.set(name, '1') : p.delete(name))
        else (v ? p.set(name, String(v)) : p.delete(name))
      }
    })
  }, [write, prefix])

  const toggle = useCallback((k: keyof S & string, value: string) => {
    write((p) => {
      const name = prefix + k
      const cur = (p.get(name) ?? '').split(',').filter(Boolean)
      const next = cur.includes(value) ? cur.filter((x) => x !== value) : [...cur, value]
      if (next.length) p.set(name, next.join(','))
      else p.delete(name)
    })
  }, [write, prefix])

  const reset = useCallback(() => {
    write((p) => { for (const k of keys) p.delete(prefix + k) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [write, prefix])

  /** number of active filters (a list with 2 values counts once) */
  const active = keys.filter((k) => {
    const v = values[k] as unknown
    return Array.isArray(v) ? v.length > 0 : !!v
  }).length

  /** API query params: lists joined with commas, empty values dropped, booleans as "true" */
  const api = useMemo(() => {
    const out: Record<string, string | undefined> = {}
    for (const k of keys) {
      const v = values[k] as unknown
      out[k] = Array.isArray(v) ? (v.length ? v.join(',') : undefined) : typeof v === 'boolean' ? (v ? 'true' : undefined) : (v as string) || undefined
    }
    return out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [values])

  return { values, set, setMany, toggle, reset, active, api }
}

export function useDebounced<T>(v: T, ms = 350): T {
  const [d, setD] = useState(v)
  useEffect(() => {
    const t = setTimeout(() => setD(v), ms)
    return () => clearTimeout(t)
  }, [v, ms])
  return d
}

/** "7d" / "24h" / "90d" / ISO date -> ISO timestamp for `since` params. */
export function sinceFromPreset(v: string | null | undefined): string | undefined {
  if (!v) return undefined
  const m = v.match(/^(\d+)([hd])$/)
  if (m) {
    const ms = Number(m[1]) * (m[2] === 'h' ? 3600000 : 86400000)
    // floored to 10 min so the query key (and the request) stays stable between renders
    const now = Math.floor(Date.now() / 600000) * 600000
    return new Date(now - ms).toISOString().slice(0, 19) + 'Z'
  }
  return /^\d{4}-\d{2}-\d{2}/.test(v) ? v : undefined
}
