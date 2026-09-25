import { useMemo, useState, type ReactNode } from 'react'
import { useQueries } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchSeries, useCatalog, useLatest, useSources, type SeriesParams } from '../api/client'
import type { CatalogEntry, SeriesPoint, SourceInfo } from '../api/types'
import { SLOTS, Sparkline, TimeChart, type ChartSeries } from '../components/charts'
import { ChipSelect, FilterBar, FilteredEmpty, FilterGroup, MultiSelect, SearchFilter } from '../components/filters'
import { AsOf, Card, Empty, ErrorBox, KindBadge, PageHeader, Seg, Skeleton } from '../components/ui'
import { LOCALE, fmtDate, fmtNum, isoDaysAgo, parseTs } from '../lib/format'
import { GROUPS, seriesMeta, sourceLink, staleAfterMs, unitLabel } from '../lib/series'
import { useUrlFilters } from '../lib/urlFilters'
import { HelpFor, HelpTip, InfoTip, PageGuide, Term, seriesTopic, sourceTopic } from '../help'

type Range = '6m' | '2y' | '10y' | 'all'
const RANGES: { v: Range; l: string }[] = [
  { v: '6m', l: '6 months' }, { v: '2y', l: '2 years' }, { v: '10y', l: '10 years' }, { v: 'all', l: 'All' },
]
const sinceOf = (r: Range) => (r === '6m' ? isoDaysAgo(183) : r === '2y' ? isoDaysAgo(730) : r === '10y' ? isoDaysAgo(3653) : undefined)
const NOW = () => Date.now() + 3600000
const isFuture = (ts: string) => (parseTs(ts)?.getTime() ?? 0) > NOW()
const metaOf = (p?: SeriesPoint) => (p && p.meta && typeof p.meta === 'object' ? p.meta as Record<string, unknown> : {})
const GRID = 'grid grid-cols-1 gap-4 min-[80rem]:grid-cols-2 min-[112.5rem]:grid-cols-3 min-[150rem]:grid-cols-4'

interface ChartSpec {
  id: string
  title: string
  entries: CatalogEntry[]
  unit: string | null
  diverging: boolean | 'inverted'
  bands: boolean
  zero: boolean
  note?: string
  refLines?: { y: number; label: string }[]
}

function buildSpecs(groupId: string, entries: CatalogEntry[]): ChartSpec[] {
  const specs: ChartSpec[] = []
  if (['oni', 'soi', 'mei', 'local', 'other'].includes(groupId)) {
    for (const e of entries) {
      const m = seriesMeta(e.series)
      specs.push({
        id: `${e.source}:${e.series}`, title: m.label, entries: [e], unit: e.unit,
        diverging: m.anomaly && m.monthly && !m.refLines ? (groupId === 'soi' ? 'inverted' : true) : false,
        bands: m.ensoBands, zero: m.anomaly, note: m.note, refLines: m.refLines,
      })
    }
    return specs
  }
  // one chart per family (or unit + anomaly), never two y-scales on one plot
  const byKey = new Map<string, CatalogEntry[]>()
  for (const e of entries) {
    const m = seriesMeta(e.series)
    const k = `${m.family ?? ''}|${e.unit ?? ''}|${m.anomaly ? 'a' : 'v'}`
    byKey.set(k, [...(byKey.get(k) ?? []), e])
  }
  for (const [k, es] of byKey) {
    const anom = k.endsWith('|a')
    const order = ['nino12', 'nino3', 'nino34', 'nino4']
    es.sort((a, b) => {
      const ia = order.findIndex((o) => a.series.startsWith(o + '_'))
      const ib = order.findIndex((o) => b.series.startsWith(o + '_'))
      return ia - ib || a.series.localeCompare(b.series)
    })
    const m0 = seriesMeta(es[0].series)
    const title = m0.family
      ? (es.length > 1 ? (m0.familyTitle ?? m0.label) : m0.label)
      : groupId === 'daily' ? (anom ? 'Daily Nino 3.4 anomaly' : 'Nino 3.4: SST vs climatology')
        : groupId === 'weekly' ? (anom ? 'Weekly anomalies by region' : 'Absolute temperature (weekly)')
          : groupId === 'world' ? (anom ? 'Global SST anomaly' : 'Global SST vs climatology') : `Series (${unitLabel(es[0].unit) || 'unitless'})`
    specs.push({
      id: `${groupId}:${k}`, title, entries: es.slice(0, 8), unit: es[0].unit,
      diverging: false, bands: anom && es.some((e) => seriesMeta(e.series).ensoBands), zero: anom,
      note: m0.note, refLines: m0.refLines,
    })
  }
  return specs
}

/** The last chart of a grid row that would stay alone widens to fill the row (2, 3 and 4 columns). */
function lastSpan(i: number, n: number): string {
  if (i !== n - 1) return 'min-w-0'
  const c: string[] = ['min-w-0']
  c.push(n % 2 === 1 ? 'min-[80rem]:col-span-2' : '')
  c.push(n % 3 === 1 ? 'min-[112.5rem]:col-span-3' : n % 3 === 2 ? 'min-[112.5rem]:col-span-2' : 'min-[112.5rem]:col-span-1')
  c.push(n % 4 === 1 ? 'min-[150rem]:col-span-4' : n % 4 === 2 ? 'min-[150rem]:col-span-3' : n % 4 === 3 ? 'min-[150rem]:col-span-2' : 'min-[150rem]:col-span-1')
  return c.join(' ')
}

function useSeriesData(entries: CatalogEntry[], since?: string, extra: Record<string, string | number> = {}) {
  return useQueries({
    queries: entries.map((e) => {
      // long hourly series: one mean per day keeps the chart light
      const downsample = !since && e.points > 5000 ? 'daily' : undefined
      const p = { source: e.source, series: e.series, since, limit: 20000, downsample, ...extra }
      return {
        queryKey: ['series', p],
        // coalesced into GET /api/series/batch (client.ts): ~80 series on this page, one nginx budget
        queryFn: () => fetchSeries(p as SeriesParams),
      }
    }),
  })
}

function latestObserved(points: SeriesPoint[] = []): SeriesPoint | undefined {
  for (let i = points.length - 1; i >= 0; i--) if (points[i].value !== null && !isFuture(points[i].ts)) return points[i]
  return undefined
}

function SourceLinks({ entries, sources, ts, staleMs, kind, validFor }: {
  entries: CatalogEntry[]; sources?: SourceInfo[]; ts: string; staleMs?: number; kind?: string | null; validFor?: string | null
}) {
  const provs = [...new Set(entries.map((e) => e.source))]
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
      {provs.map((s) => {
        const p = sourceLink(sources, s)
        return (
          <span key={s} className="inline-flex items-center gap-1">
            <AsOf ts={ts} label="latest value" source={p.title} href={p.href} staleMs={staleMs} kind={kind} validFor={validFor} tz="UTC" />
            <HelpFor id={sourceTopic(s)} appId={s} kind="source" title={p.title} text={sources?.find((x) => x.name === s)?.description} />
          </span>
        )
      })}
    </div>
  )
}

function SeriesChart({ spec, since, tour, fallback }: { spec: ChartSpec; since?: string; tour?: string; fallback: string }) {
  const sources = useSources()
  const qs2 = useSeriesData(spec.entries, since)
  const loading = qs2.some((q) => q.isLoading)
  const err = qs2.find((q) => q.error)?.error
  const series: ChartSeries[] = spec.entries.map((e, i) => {
    const m = seriesMeta(e.series)
    const isClim = /clim|normal|mean/.test(e.series)
    return {
      key: `k${i}`, label: spec.entries.length > 1 ? m.short : m.label,
      color: isClim ? 'var(--ink-3)' : SLOTS[i % 8], dashed: isClim,
      points: (qs2[i].data?.points ?? []).map((p) => ({ ts: p.ts, value: p.value })),
    }
  })
  const empty = !loading && series.every((s) => !s.points.length)
  const allPts = qs2.flatMap((q) => q.data?.points ?? [])
  const future = allPts.filter((p) => isFuture(p.ts))
  const lastFuture = future.reduce((m, p) => (p.ts > m ? p.ts : m), '')
  const latests = spec.entries.map((e, i) => ({ e, p: latestObserved(qs2[i].data?.points) }))
  const lastObs = latests.reduce((m, x) => (x.p && x.p.ts > m ? x.p.ts : m), '')
  const e0 = spec.entries[0]
  const kind = e0.kind ?? latests[0]?.p?.kind ?? null
  const uLabel = e0.unit_label ?? unitLabel(spec.unit)
  return (
    <Card title={spec.title} tour={tour} className="h-full"
      help={<HelpFor id={seriesTopic(e0.series)} appId={e0.series} kind="series" title={spec.title} text={fallback} />}
      right={<>
        {future.length > 0 && <KindBadge kind="forecast" ts={lastFuture} validFor={lastFuture} tz="UTC" compact />}
        {spec.note && <span className="text-[11px] text-ink-3">{spec.note}</span>}
      </>}
      footer={
        <div className="space-y-1">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-[12px] tnum">
            {latests.filter((x) => x.p).map(({ e, p }) => (
              <span key={e.series} className="text-ink-2">
                {spec.entries.length > 1 && <span className="text-ink-3">{seriesMeta(e.series).short}: </span>}
                <b className="text-ink">{fmtNum(p!.value, Math.abs(p!.value ?? 0) >= 100 ? 0 : 2)}</b> {uLabel}
                {spec.entries.length === 1 && <span className="text-ink-3"> ({fmtDate(p!.ts)})</span>}
              </span>
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <SourceLinks entries={spec.entries} sources={sources.data} ts={lastObs || spec.entries.reduce((m, e) => (e.last > m ? e.last : m), '')}
              staleMs={staleAfterMs(e0.series)} kind={kind} validFor={e0.valid_for} />
            <span className="text-[11px] text-ink-3 tnum">{spec.entries.reduce((n, e) => n + e.points, 0).toLocaleString(LOCALE)} points in total</span>
          </div>
        </div>
      }>
      {loading ? <Skeleton h={220} /> : err ? <ErrorBox error={err} what={spec.title} /> : empty ? (
        <p className="text-[13px] text-ink-3">No points in this period. Pick a longer period.</p>
      ) : (
        <TimeChart series={series} unit={uLabel} zeroLine={spec.zero} bands={spec.bands} diverging={spec.diverging}
          refLines={spec.refLines} height={230} nowLine={future.length > 0} />
      )}
    </Card>
  )
}

/** Thai AQI bands (Pollution Control Department). */
function thaiAqiBand(v: number | null | undefined): { label: string; color: string } | null {
  if (v === null || v === undefined) return null
  if (v <= 25) return { label: 'Very good', color: '#3b9cdb' }
  if (v <= 50) return { label: 'Good', color: '#2e9e44' }
  if (v <= 100) return { label: 'Moderate', color: '#c9a400' }
  if (v <= 200) return { label: 'Starting to affect health', color: '#e0782b' }
  return { label: 'Affects health', color: '#d03b3b' }
}

/** Air4Thai: one card per station (AQI, PM2.5, PM10), latest reading. */
function AirStations({ entries }: { entries: CatalogEntry[] }) {
  const sources = useSources()
  const q = useSeriesData(entries, isoDaysAgo(7))
  const stations = useMemo(() => {
    const m = new Map<string, { code: string; meta: Record<string, unknown>; vals: Record<string, SeriesPoint | undefined> }>()
    entries.forEach((e, i) => {
      const mm = e.series.match(/^air4thai_(\w+?)_(aqi|pm25|pm10)$/)
      if (!mm) return
      const p = latestObserved(q[i].data?.points)
      const st = m.get(mm[1]) ?? { code: mm[1], meta: {}, vals: {} }
      st.vals[mm[2]] = p
      if (p) st.meta = { ...metaOf(p), ...st.meta }
      m.set(mm[1], st)
    })
    return [...m.values()].sort((a, b) => Number(a.meta.distance_km ?? 1e9) - Number(b.meta.distance_km ?? 1e9))
  }, [entries, q])
  const loading = q.some((x) => x.isLoading)
  const newest = entries.reduce((m, e) => (e.last > m ? e.last : m), '')
  return (
    <Card title={`Stations (${stations.length})`} help={<HelpTip id="aqi" />}
      footer={<SourceLinks entries={entries} sources={sources.data} ts={newest} staleMs={6 * 3600000} kind="observed" />}>
      {loading ? <Skeleton h={160} /> : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-2">
          {stations.map((s) => {
            const aqi = s.vals.aqi
            const band = thaiAqiBand(aqi?.value)
            const t = aqi?.ts ?? s.vals.pm25?.ts
            return (
              <div key={s.code} className="rounded-lg border border-line p-2.5">
                <div className="text-[12px] font-semibold leading-tight">{String(s.meta.name ?? `Station ${s.code.toUpperCase()}`)}</div>
                <div className="text-[11px] text-ink-3">{String(s.meta.area ?? '')}{s.meta.distance_km !== undefined ? ` · ${fmtNum(Number(s.meta.distance_km), 0)} km from Samui` : ''}</div>
                <div className="mt-1.5 flex items-baseline gap-2 tnum">
                  <span className="text-[22px] font-semibold" style={{ color: band?.color }}>{aqi ? fmtNum(aqi.value, 0) : '--'}</span>
                  <span className="text-[11px] text-ink-2">Thai AQI{band ? ` · ${band.label}` : ''}</span>
                </div>
                <div className="flex flex-wrap gap-x-3 text-[12px] text-ink-2 tnum">
                  <span>PM2.5 <b className="text-ink">{s.vals.pm25 ? fmtNum(s.vals.pm25.value, 0) : '--'}</b> µg/m³ <HelpTip id="pm25" /></span>
                  {s.vals.pm10 && <span>PM10 <b className="text-ink">{fmtNum(s.vals.pm10.value, 0)}</b> µg/m³</span>}
                </div>
                <div className="mt-1 text-[11px] text-ink-3">{t ? fmtDate(t) : 'no reading in 7 days'}</div>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

/** Dam storage: compact bars, Samui's reservoir and the national total first, then lowest storage first. */
function DamStorage({ entries }: { entries: CatalogEntry[] }) {
  const sources = useSources()
  const q = useSeriesData(entries, isoDaysAgo(30))
  const rows = entries.map((e, i) => ({ e, p: latestObserved(q[i].data?.points) }))
    .sort((a, b) => {
      const pri = (x: CatalogEntry) => (x.series.startsWith('surat_') ? 0 : x.series.startsWith('thai_large') ? 1 : 2)
      return pri(a.e) - pri(b.e) || (a.p?.value ?? 999) - (b.p?.value ?? 999)
    })
  const loading = q.some((x) => x.isLoading)
  const newest = entries.reduce((m, e) => (e.last > m ? e.last : m), '')
  return (
    <Card title={`Reservoirs (${entries.length})`} help={<HelpTip id="samui_water_supply" />}
      right={<span className="text-[11px] text-ink-3">% of capacity · lowest first</span>}
      footer={<SourceLinks entries={entries} sources={sources.data} ts={newest} staleMs={3 * 86400000} kind="observed" />}>
      {loading ? <Skeleton h={160} /> : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(230px,1fr))] gap-x-4 gap-y-2">
          {rows.map(({ e, p }) => {
            const m = metaOf(p)
            const v = p?.value ?? null
            const key = e.series.startsWith('surat_') || e.series.startsWith('thai_large')
            return (
              <div key={`${e.source}:${e.series}`} className={`min-w-0 ${key ? 'rounded-md border border-line p-1.5' : ''}`}>
                <div className="flex items-baseline justify-between gap-2 text-[12px]">
                  <span className="truncate font-medium" title={seriesMeta(e.series).label}>{seriesMeta(e.series).short}</span>
                  <b className="tnum">{v === null ? '--' : `${fmtNum(v, 0)} %`}</b>
                </div>
                <div className="mt-0.5 h-1.5 overflow-hidden rounded-full bg-surface-2" role="img" aria-label={`${seriesMeta(e.series).short}: ${v ?? 'no data'} % of capacity`}>
                  <div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, v ?? 0))}%`, background: 'var(--s1)' }} />
                </div>
                <div className="truncate text-[10px] text-ink-3">
                  {m.province ? `${String(m.province)} · ` : ''}{m.usable_pct !== undefined ? `usable ${fmtNum(Number(m.usable_pct), 0)} % · ` : ''}{p ? fmtDate(p.ts) : 'no data'}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

/** Hotspots: small multiples (one sparkline per region, same period). */
function Hotspots({ entries, since }: { entries: CatalogEntry[]; since?: string }) {
  const sources = useSources()
  const q = useSeriesData(entries, since)
  const rows = entries.map((e, i) => ({ e, pts: q[i].data?.points ?? [], p: latestObserved(q[i].data?.points) }))
    .sort((a, b) => (b.p?.value ?? -1) - (a.p?.value ?? -1))
  const loading = q.some((x) => x.isLoading)
  const newest = entries.reduce((m, e) => (e.last > m ? e.last : m), '')
  return (
    <Card title="Hotspots per day, by region" help={<HelpTip id="hotspots" />}
      right={<span className="text-[11px] text-ink-3">highest first · each line on its own scale</span>}
      footer={<SourceLinks entries={entries} sources={sources.data} ts={newest} staleMs={3 * 86400000} kind="observed" />}>
      {loading ? <Skeleton h={160} /> : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(170px,1fr))] gap-2">
          {rows.map(({ e, pts, p }, i) => (
            <div key={e.series} className="rounded-lg border border-line p-2">
              <div className="flex items-baseline justify-between gap-2">
                <span className="truncate text-[12px] font-medium">{seriesMeta(e.series).short}</span>
                <b className="text-[15px] tnum">{p ? fmtNum(p.value, 0) : '--'}</b>
              </div>
              <Sparkline points={pts} color={SLOTS[i % 8]} height={34} />
              <div className="text-[10px] text-ink-3">{p ? fmtDate(p.ts) : 'no data'} · {pts.length} days</div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function TaoSection({ entries, since }: { entries: CatalogEntry[]; since?: string }) {
  const latest = useLatest()
  const sources = useSources()
  const [sel, setSel] = useState<string>('')
  const names = new Set(entries.map((e) => `${e.source}:${e.series}`))
  const rows = (latest.data ?? []).filter((l) => names.has(`${l.source}:${l.series}`)).sort((a, b) => a.series.localeCompare(b.series))
  const chosen = entries.find((e) => `${e.source}:${e.series}` === sel) ?? entries[0]
  const isSel = (k: string) => chosen && `${chosen.source}:${chosen.series}` === k
  const newest = rows.reduce((m, r) => (r.ts > m ? r.ts : m), '')
  return (
    <div className="grid gap-4 min-[64rem]:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] min-[112.5rem]:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
      <Card title={`Buoys (${rows.length})`} pad={false} className="h-full" help={<HelpTip id="tao_buoys" />}
        footer={<SourceLinks entries={entries.slice(0, 1)} sources={sources.data} ts={newest} staleMs={2 * 86400000} kind="observed" />}>
        {/* table on md+, cards on phones */}
        <div className="hidden max-h-[330px] overflow-auto md:block">
          <table className="w-full text-[12px] tnum">
            <thead className="sticky top-0 bg-surface text-left text-ink-3">
              <tr>
                <th className="px-3 py-1.5 font-medium">Station</th>
                <th className="px-3 py-1.5 text-right font-medium">SST</th>
                <th className="px-3 py-1.5 text-right font-medium"><span className="inline-flex items-center gap-1">Change <InfoTip title="Change" text="Difference from the previous reading of the same buoy (usually one hour earlier), in C. It is not an anomaly." /></span></th>
                <th className="px-3 py-1.5 font-medium">Time (UTC)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const k = `${r.source}:${r.series}`
                const d = r.value !== null && r.prev_value !== null ? r.value - r.prev_value : null
                return (
                  <tr key={k} className={`cursor-pointer border-t border-line hover:bg-surface-2 ${isSel(k) ? 'bg-surface-2' : ''}`} onClick={() => setSel(k)}
                    tabIndex={0} onKeyDown={(ev) => { if (ev.key === 'Enter') setSel(k) }} aria-selected={isSel(k)}>
                    <td className="px-3 py-1">{seriesMeta(r.series).short}</td>
                    <td className="px-3 py-1 text-right">{fmtNum(r.value, 2)} {unitLabel(r.unit)}</td>
                    <td className="px-3 py-1 text-right text-ink-2">{d === null ? '--' : `${d > 0 ? '+' : ''}${fmtNum(d, 2)}`}</td>
                    <td className="px-3 py-1 text-ink-3">{fmtDate(r.ts)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <div className="grid max-h-[300px] grid-cols-2 gap-1.5 overflow-auto p-2 md:hidden">
          {rows.map((r) => {
            const k = `${r.source}:${r.series}`
            return (
              <button key={k} type="button" onClick={() => setSel(k)} aria-pressed={isSel(k)}
                className={`min-h-10 rounded-md border px-2 py-1 text-left text-[12px] tnum ${isSel(k) ? 'border-accent bg-surface-2' : 'border-line'}`}>
                <div className="font-medium">{seriesMeta(r.series).short}</div>
                <div className="text-ink-2">{fmtNum(r.value, 2)} {unitLabel(r.unit)}</div>
              </button>
            )
          })}
        </div>
      </Card>
      {chosen && (
        <SeriesChart since={since} fallback="Hourly sea surface temperature measured by one TAO/TRITON buoy." spec={{
          id: `tao:${chosen.series}`, title: seriesMeta(chosen.series).label, entries: [chosen], unit: chosen.unit,
          diverging: false, bands: false, zero: seriesMeta(chosen.series).anomaly,
        }} />
      )}
    </div>
  )
}

export default function Indices() {
  const cat = useCatalog()
  const sources = useSources()
  const rf = useUrlFilters({ range: 'str' })
  const range: Range = (RANGES.some((r) => r.v === rf.values.range) ? rf.values.range : '10y') as Range
  const since = sinceOf(range)
  const f = useUrlFilters({ group: 'list', source: 'list', q: 'str' })
  const q = f.values.q.toLowerCase()
  // phones: the filter bar would cover the screen if sticky, and 18 group chips are collapsed
  const narrow = typeof window !== 'undefined' && window.innerWidth < 768

  const all = cat.data ?? []
  const matchQ = (e: CatalogEntry) => !q || e.series.toLowerCase().includes(q) || seriesMeta(e.series).label.toLowerCase().includes(q)
  const matchSrc = (e: CatalogEntry) => !f.values.source.length || f.values.source.includes(e.source)
  const matchGrp = (e: CatalogEntry) => !f.values.group.length || f.values.group.includes(seriesMeta(e.series).group)
  const shown = all.filter((e) => matchQ(e) && matchSrc(e) && matchGrp(e))

  // facet counts: each ignores its own filter
  const groupCounts = new Map<string, number>()
  for (const e of all) if (matchQ(e) && matchSrc(e)) { const g = seriesMeta(e.series).group; groupCounts.set(g, (groupCounts.get(g) ?? 0) + 1) }
  const srcCounts = new Map<string, number>()
  for (const e of all) if (matchQ(e) && matchGrp(e)) srcCounts.set(e.source, (srcCounts.get(e.source) ?? 0) + 1)

  const groups = useMemo(() => {
    const by = new Map<string, CatalogEntry[]>()
    for (const e of shown) {
      const g = seriesMeta(e.series).group
      by.set(g, [...(by.get(g) ?? []), e])
    }
    return GROUPS.map((g) => ({ ...g, entries: by.get(g.id) ?? [] }))
  }, [shown]) // eslint-disable-line react-hooks/exhaustive-deps

  const groupOpts = GROUPS.filter((g) => all.some((e) => seriesMeta(e.series).group === g.id)).map((g) => ({
    value: g.id, text: g.title, count: groupCounts.get(g.id) ?? 0,
    help: g.topic ? <HelpTip id={g.topic} /> : undefined,
  }))
  const srcTitle = (s: string) => sources.data?.find((x) => x.name === s)?.title ?? s
  const srcOpts = [...new Set(all.map((e) => e.source))].sort().map((s) => ({ value: s, text: srcTitle(s), count: srcCounts.get(s) ?? 0 }))
  const activeDesc = [
    ...f.values.group.map((g) => `group: ${GROUPS.find((x) => x.id === g)?.title ?? g}`),
    ...f.values.source.map((s) => `source: ${srcTitle(s)}`),
    ...(f.values.q ? [`name contains "${f.values.q}"`] : []),
  ]
  let firstChart = true
  const tourOnce = () => { if (firstChart) { firstChart = false; return 'indices-chart' } return undefined }

  return (
    <div>
      <PageHeader title="Indices" help={<HelpTip id="time_resolution" size="md" />}
        sub={<>All collected series, grouped by indicator. Most values are an <Term id="anomaly">anomaly</Term> (difference from normal); the shaded band is <Term id="neutral">neutral</Term> (-0.5 to +0.5 °C).</>}
        right={<span data-tour="indices-range" className="flex items-center gap-1.5">
          <Seg label="Period" value={range} options={RANGES} onChange={(v) => rf.set('range', v === '10y' ? '' : v)} />
          <HelpTip id="time_resolution" label="Which period to pick?" />
        </span>} />
      <PageGuide page="indices" className="mb-3" />

      <FilterBar active={f.active} onReset={f.reset} className="mb-4" sticky={!narrow}
        summary={cat.data ? <><b className="text-ink">{shown.length}</b> of {all.length} series shown in {groups.filter((g) => g.entries.length).length} groups</> : 'Loading series...'}>
        <div data-tour="indices-groups" className="min-w-0 basis-full">
          <FilterGroup label="Group" help={<HelpTip id="nino_regions" label="What are the groups?" />}>
            <ChipSelect options={groupOpts} selected={f.values.group} onToggle={(v) => f.toggle('group', v)} limit={narrow ? 5 : 20} allLabel="All" onAll={() => f.set('group', [])} />
          </FilterGroup>
        </div>
        <FilterGroup label="Source" help={<HelpTip id="sources_page" label="About the sources" />}>
          <MultiSelect label="Source" options={srcOpts} selected={f.values.source} onToggle={(v) => f.toggle('source', v)} onClear={() => f.set('source', [])} placeholder="Search sources" />
        </FilterGroup>
        <FilterGroup label="Series name" help={<HelpTip id="filters_series" label="How does the search work?" />} className="min-w-[200px] flex-1">
          <SearchFilter value={f.values.q} onChange={(v) => f.set('q', v)} placeholder="e.g. nino34, dhw, samui" label="Search series" className="w-full max-w-[360px]" />
        </FilterGroup>
      </FilterBar>

      {cat.isLoading ? <Skeleton h={300} /> : cat.isError ? <ErrorBox error={cat.error} what="series catalogue" /> : !all.length ? (
        <Empty what="No series in the catalogue" source="index collectors (NOAA CPC, PSL, BoM...)" />
      ) : !shown.length ? (
        <FilteredEmpty what="series" filters={activeDesc} onReset={f.reset} total={all.length} />
      ) : (
        <div className="space-y-8">
          {groups.map((g) => {
            if (!g.entries.length) {
              if (f.active || g.id === 'other' || g.id === 'local') return null
              return (
                <section key={g.id} id={`g-${g.id}`}>
                  <GroupHead g={g} n={0} />
                  <p className="text-[12px] text-ink-3">No data for this group yet. <Link className="link" to="/sources">See Sources</Link></p>
                </section>
              )
            }
            let body: ReactNode
            if (g.layout === 'tao') body = <TaoSection entries={g.entries} since={since} />
            else if (g.id === 'air') body = <AirStations entries={g.entries} />
            else if (g.id === 'water') body = <DamStorage entries={g.entries} />
            else if (g.id === 'fire') body = <Hotspots entries={g.entries} since={since} />
            else body = (
              <div className={GRID}>
                {buildSpecs(g.id, g.entries).map((s, i, arr) => (
                  <div key={s.id} className={lastSpan(i, arr.length)}>
                    <SeriesChart spec={s} since={since} tour={tourOnce()} fallback={g.blurb} />
                  </div>
                ))}
              </div>
            )
            return (
              <section key={g.id} id={`g-${g.id}`} className="scroll-mt-4">
                <GroupHead g={g} n={g.entries.length} />
                {body}
              </section>
            )
          })}
        </div>
      )}
    </div>
  )
}

function GroupHead({ g, n }: { g: (typeof GROUPS)[number]; n: number }) {
  return (
    <div className="mb-3">
      <h2 className="flex items-center gap-1.5 text-[15px] font-semibold">
        {g.title}
        <HelpFor id={g.topic ?? null} appId={g.id} kind="series group" title={g.title} text={g.blurb} />
        {n > 0 && <span className="text-[12px] font-normal text-ink-3 tnum">{n} series</span>}
      </h2>
      {g.blurb && <p className="text-[12px] text-ink-2">{g.blurb}</p>}
    </div>
  )
}
