import { useCatalog, useSeries, useSources } from '../api/client'
import type { CatalogEntry } from '../api/types'
import { findCatalog, sourceLink } from './series'

/** Resolve a series by name via the catalog (whatever collector publishes it), then fetch it. */
export function useNamedSeries(series: string, since?: string, match?: (c: CatalogEntry) => boolean) {
  const cat = useCatalog()
  const sources = useSources()
  const entry = findCatalog(cat.data, match ?? ((c) => c.series === series))
  const q = useSeries(entry?.source, entry?.series, since)
  const link = entry ? sourceLink(sources.data, entry.source) : null
  return {
    entry,
    link,
    points: q.data?.points ?? [],
    isLoading: cat.isLoading || (!!entry && q.isLoading),
    error: cat.error ?? q.error,
    catalogReady: !!cat.data,
  }
}

const SEASON_LETTERS = 'JFMAMJJASOND'
/** Center-month ts -> 3-month season code, e.g. 2026-07-15 -> "JJA 2026". */
export function seasonLabel(ts: string | null | undefined): string {
  if (!ts) return '--'
  const m = Number(ts.slice(5, 7)) - 1
  const y = ts.slice(0, 4)
  if (Number.isNaN(m)) return ts
  const l = (k: number) => SEASON_LETTERS[(k + 12) % 12]
  return `${l(m - 1)}${l(m)}${l(m + 1)} ${y}`
}
