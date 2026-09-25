import { useMemo, useState, type ReactNode } from 'react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceArea, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { LOCALE, anomColor, fmtDate, fmtNum, parseTs } from '../lib/format'

export interface ChartSeries {
  key: string
  label: string
  color: string
  points: { ts: string; value: number | null }[]
  dashed?: boolean
  width?: number
}

export const SLOTS = ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)', 'var(--s5)', 'var(--s6)', 'var(--s7)', 'var(--s8)']

const DAY = 86400000

/** Pad the data extent a little instead of Recharts' coarse "nice" rounding. */
const NICE_DOMAIN: [(v: number) => number, (v: number) => number] = [
  (min) => {
    if (min >= 0 && min < 1) return 0 // non-negative quantities (rain, PM) start at zero
    const pad = Math.max(Math.abs(min) * 0.05, 0.2)
    const v = Math.floor((min - pad) * 2) / 2
    return min >= 0 ? Math.max(0, v) : v
  },
  (max) => { const pad = Math.max(Math.abs(max) * 0.05, 0.2); return Math.ceil((max + pad) * 2) / 2 },
]

function tickFmt(span: number) {
  return (t: number) => {
    const d = new Date(t)
    // multi-year axis: recharts places ~2 ticks a year, so a bare year printed twice ("2017 2017
    // 2018 2018", QA 24 Sep 2026); name the mid-year tick by its month instead
    if (span > 3 * 365 * DAY) return d.getUTCMonth() < 3 || d.getUTCMonth() > 9 ? String(d.getUTCFullYear()) : d.toLocaleDateString(LOCALE, { month: 'short', year: '2-digit', timeZone: 'UTC' })
    if (span > 120 * DAY) return d.toLocaleDateString(LOCALE, { month: 'short', year: '2-digit', timeZone: 'UTC' })
    return d.toLocaleDateString(LOCALE, { day: 'numeric', month: 'short', timeZone: 'UTC' })
  }
}

function Legend({ series, unit }: { series: ChartSeries[]; unit?: string }) {
  if (series.length < 2 && !unit) return null
  return (
    <ul className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-ink-2">
      {unit && <li className="mr-auto text-[11px] text-ink-3" title="Unit of the vertical axis">Axis: <b className="font-semibold text-ink-2">{unit}</b></li>}
      {series.length > 1 && series.map((s) => (
        <li key={s.key} className="flex items-center gap-1.5">
          <svg width="16" height="8" aria-hidden>
            <line x1="0" y1="4" x2="16" y2="4" stroke={s.color} strokeWidth="2.5" strokeDasharray={s.dashed ? '4 3' : undefined} />
          </svg>
          {s.label}
        </li>
      ))}
    </ul>
  )
}

interface TipRow { name: string; color: string; value: number | null }
function TipBox({ title, rows, unit }: { title: string; rows: TipRow[]; unit?: string }) {
  return (
    <div className="rounded-md border border-line-strong bg-surface px-2.5 py-1.5 text-[12px] shadow-lg">
      <div className="mb-0.5 font-semibold text-ink">{title}</div>
      {rows.map((r) => (
        <div key={r.name} className="flex items-center gap-2 text-ink-2">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: r.color }} />
          <span className="flex-1">{r.name}</span>
          <span className="tnum font-semibold text-ink">
            {r.value === null || r.value === undefined ? '--' : `${fmtNum(r.value, 2)}${unit ? ` ${unit}` : ''}`}
          </span>
        </div>
      ))}
    </div>
  )
}

/** Toggle between the chart and an accessible table view. */
export function ChartFrame({ children, table }: { children: ReactNode; table: () => ReactNode }) {
  const [asTable, setAsTable] = useState(false)
  return (
    <div>
      <div className="-mt-1 mb-1 flex justify-end">
        <button type="button" className="rounded px-1 text-[11px] text-ink-2 hover:text-ink" aria-pressed={asTable} onClick={() => setAsTable((v) => !v)}>
          {asTable ? 'Show chart' : 'Show table'}
        </button>
      </div>
      {asTable ? <div className="max-h-72 overflow-auto">{table()}</div> : children}
    </div>
  )
}

function DataTable({ series, unit }: { series: ChartSeries[]; unit?: string }) {
  const rows = useMemo(() => {
    const m = new Map<string, Record<string, number | null>>()
    for (const s of series) for (const p of s.points) {
      const r = m.get(p.ts) ?? {}
      r[s.key] = p.value
      m.set(p.ts, r)
    }
    return [...m.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1)).slice(0, 400)
  }, [series])
  return (
    <table className="w-full text-[12px] tnum">
      <thead className="sticky top-0 bg-surface text-left text-ink-3">
        <tr>
          <th className="py-1 pr-3 font-medium">Date</th>
          {series.map((s) => (
            <th key={s.key} className="py-1 pr-3 text-right font-medium">
              {s.label}
              {unit ? ` (${unit})` : ''}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map(([ts, r]) => (
          <tr key={ts} className="border-t border-line">
            <td className="py-0.5 pr-3 text-ink-2">{fmtDate(ts)}</td>
            {series.map((s) => (
              <td key={s.key} className="py-0.5 pr-3 text-right">
                {fmtNum(r[s.key] ?? null, 2)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function TimeChart({
  series, height = 240, unit, zeroLine = false, bands = false, diverging = false, refLines = [], area = false, yDomain,
  curve = 'monotone', nowLine = false,
}: {
  series: ChartSeries[]
  height?: number
  unit?: string
  zeroLine?: boolean
  bands?: boolean
  /** single series drawn as bars coloured by sign/strength (blue cold / red warm);
   *  'inverted' for indices where negative = El Nino (SOI) */
  diverging?: boolean | 'inverted'
  refLines?: { y: number; label: string; color?: string }[]
  area?: boolean
  yDomain?: [number | string, number | string]
  curve?: 'monotone' | 'linear'
  /** vertical "aujourd'hui" marker (forecast boundary) */
  nowLine?: boolean
}) {
  const data = useMemo(() => {
    const m = new Map<number, Record<string, number | null>>()
    for (const s of series) for (const p of s.points) {
      const d = parseTs(p.ts)
      if (!d) continue
      const t = d.getTime()
      const r = m.get(t) ?? { t }
      r[s.key] = p.value
      m.set(t, r)
    }
    return [...m.values()].sort((a, b) => (a.t as number) - (b.t as number))
  }, [series])

  const col = (v: number | null) => anomColor(v === null ? null : diverging === 'inverted' ? -v : v)
  if (!data.length) return null
  const t0 = data[0].t as number
  const t1 = data[data.length - 1].t as number
  const span = t1 - t0
  const fmt = tickFmt(span)
  const tipTitle = (t: number) => fmtDate(new Date(t).toISOString().slice(0, span > 60 * DAY ? 10 : 16))

  const common = (
    <>
      <CartesianGrid vertical={false} strokeWidth={1} />
      {bands && <ReferenceArea y1={-0.5} y2={0.5} fill="var(--band)" fillOpacity={1} ifOverflow="hidden" />}
      {bands && <ReferenceLine y={0.5} stroke="var(--warm)" strokeOpacity={0.45} strokeWidth={1} />}
      {bands && <ReferenceLine y={-0.5} stroke="var(--cold)" strokeOpacity={0.45} strokeWidth={1} />}
      {zeroLine && <ReferenceLine y={0} stroke="var(--axis)" strokeWidth={1.5} />}
      {refLines.map((r) => (
        <ReferenceLine key={r.label} y={r.y} stroke={r.color ?? 'var(--ink-3)'} strokeWidth={1}
          label={{ value: r.label, position: 'insideTopRight', fill: 'var(--ink-3)', fontSize: 10 }} />
      ))}
      <YAxis width={40} tickLine={false} axisLine={false} domain={yDomain ?? NICE_DOMAIN}
        tickFormatter={(v: number) => fmtNum(v, Math.abs(v) >= 10 ? 0 : 1)} />
    </>
  )

  const chart = diverging && series.length === 1 ? (
    <BarChart data={data} margin={{ top: 6, right: 8, left: 0, bottom: 0 }} barCategoryGap={data.length > 120 ? 0 : 1}>
      {common}
      <XAxis dataKey="t" tickFormatter={fmt} tickLine={false} minTickGap={36} />
      <Tooltip cursor={{ fill: 'var(--band)' }} content={({ active, payload }) => {
        if (!active || !payload?.length) return null
        const r = payload[0].payload as Record<string, number>
        const v = r[series[0].key] ?? null
        return <TipBox title={tipTitle(r.t)} unit={unit} rows={[{ name: series[0].label, color: col(v), value: v }]} />
      }} />
      <Bar dataKey={series[0].key} isAnimationActive={false} radius={data.length > 120 ? 0 : [2, 2, 2, 2]}>
        {data.map((d) => <Cell key={d.t as number} fill={col(d[series[0].key] as number | null)} />)}
      </Bar>
    </BarChart>
  ) : (
    (() => {
      const C = area && series.length === 1 ? AreaChart : LineChart
      return (
        <C data={data} margin={{ top: nowLine ? 18 : 6, right: 8, left: 0, bottom: 0 }}>
          {common}
          <XAxis dataKey="t" type="number" scale="time" domain={[t0, t1]} tickFormatter={fmt} tickLine={false} minTickGap={36} />
          {nowLine && Date.now() > t0 && Date.now() < t1 && (
            <ReferenceLine x={Date.now()} stroke="var(--ink-3)" strokeWidth={1}
              label={{ value: 'today', position: 'top', fill: 'var(--ink-3)', fontSize: 10 }} />
          )}
          <Tooltip content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null
            const r = payload[0].payload as Record<string, number>
            return <TipBox title={tipTitle(Number(label ?? r.t))} unit={unit}
              rows={series.map((s) => ({ name: s.label, color: s.color, value: r[s.key] ?? null }))} />
          }} />
          {series.map((s) =>
            area && series.length === 1 ? (
              <Area key={s.key} dataKey={s.key} stroke={s.color} fill={s.color} fillOpacity={0.12} strokeWidth={2}
                dot={false} isAnimationActive={false} connectNulls type="monotone" />
            ) : (
              <Line key={s.key} dataKey={s.key} stroke={s.color} strokeWidth={s.width ?? 2} dot={false}
                strokeDasharray={s.dashed ? '5 4' : undefined} activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }}
                isAnimationActive={false} connectNulls type={curve} />
            ),
          )}
        </C>
      )
    })()
  )

  return (
    <ChartFrame table={() => <DataTable series={series} unit={unit} />}>
      <Legend series={series} unit={unit} />
      {diverging && series.length === 1 && <DivergingKey inverted={diverging === 'inverted'} />}
      <div style={{ height }} className="w-full">
        <ResponsiveContainer width="100%" height="100%">{chart}</ResponsiveContainer>
      </div>
    </ChartFrame>
  )
}

export function Sparkline({ points, color = 'var(--s1)', height = 36, zero = false }: {
  points: { ts: string; value: number | null }[]; color?: string; height?: number; zero?: boolean
}) {
  const data = points.filter((p) => p.value !== null).map((p) => ({ ts: p.ts, v: p.value }))
  if (data.length < 2) return <div style={{ height }} />
  return (
    <div style={{ height }} className="w-full" aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 3, right: 2, bottom: 3, left: 2 }}>
          {zero && <ReferenceLine y={0} stroke="var(--axis)" />}
          <YAxis hide domain={['auto', 'auto']} />
          <Line dataKey="v" stroke={color} strokeWidth={1.75} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Lines over a categorical x axis (e.g. months since onset). */
export function CategoryLines({ rows, xKey, series, height = 260, unit, bands = true }: {
  rows: Record<string, string | number | null>[]
  xKey: string
  series: { key: string; label: string; color: string; width?: number; dashed?: boolean }[]
  height?: number
  unit?: string
  bands?: boolean
}) {
  const asChartSeries: ChartSeries[] = series.map((s) => ({ ...s, points: [] }))
  return (
    <ChartFrame table={() => (
      <table className="w-full text-[12px] tnum">
        <thead className="sticky top-0 bg-surface text-left text-ink-3">
          <tr><th className="py-1 pr-3 font-medium">Month</th>{series.map((s) => <th key={s.key} className="py-1 pr-3 text-right font-medium">{s.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={String(r[xKey])} className="border-t border-line">
              <td className="py-0.5 pr-3 text-ink-2">{r[xKey]}</td>
              {series.map((s) => <td key={s.key} className="py-0.5 pr-3 text-right">{fmtNum(r[s.key] as number | null, 2)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    )}>
      <Legend series={asChartSeries} unit={unit} />
      <div style={{ height }} className="w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} />
            {bands && <ReferenceArea y1={-0.5} y2={0.5} fill="var(--band)" fillOpacity={1} />}
            <ReferenceLine y={0} stroke="var(--axis)" strokeWidth={1.5} />
            <XAxis dataKey={xKey} tickLine={false} interval="preserveStartEnd" minTickGap={16} />
            <YAxis width={36} tickLine={false} axisLine={false} domain={NICE_DOMAIN} tickFormatter={(v: number) => fmtNum(v, 1)} />
            <Tooltip content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null
              const r = payload[0].payload as Record<string, number | null>
              return <TipBox title={String(label)} unit={unit} rows={series.map((s) => ({ name: s.label, color: s.color, value: r[s.key] ?? null }))} />
            }} />
            {series.map((s) => (
              <Line key={s.key} dataKey={s.key} stroke={s.color} strokeWidth={s.width ?? 2} dot={false}
                strokeDasharray={s.dashed ? '5 4' : undefined} activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }}
                isAnimationActive={false} connectNulls={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartFrame>
  )
}

export function DivergingKey({ inverted = false }: { inverted?: boolean }) {
  const items: [string, string][] = inverted
    ? [['var(--cold-2)', '>= +1.5 (La Nina)'], ['var(--cold)', '+0.5 to +1.5'], ['var(--neutral)', 'neutral'],
      ['var(--warm)', '-1.5 to -0.5'], ['var(--warm-2)', '<= -1.5 (El Nino)']]
    : [['var(--cold-2)', '<= -1.5'], ['var(--cold)', '-1.5 to -0.5'], ['var(--neutral)', 'neutral'],
      ['var(--warm)', '+0.5 to +1.5'], ['var(--warm-2)', '>= +1.5']]
  return (
    <ul className="mb-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ink-3" aria-label="Anomaly scale">
      {items.map(([c, l]) => (
        <li key={l} className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: c }} />
          {l}
        </li>
      ))}
    </ul>
  )
}
