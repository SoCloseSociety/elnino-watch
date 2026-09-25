import { useMemo, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, ErrorBar, Legend as RLegend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { AsOf, Card, Seg } from '../ui'
import { ChartFrame } from '../charts'
import { fmtMonth } from '../../lib/format'
import { MONTHS, PLACE_COLORS, type PlaceDetail } from './api'
import { PlaceTip, fmt, signed } from './common'

type ClimMetric = 'temp' | 'rain' | 'sun' | 'days'
const CLIM: Record<ClimMetric, { label: string; unit: string }> = {
  temp: { label: 'Temperature', unit: 'C' },
  rain: { label: 'Rain', unit: 'mm / month' },
  sun: { label: 'Sunshine', unit: 'hours / month' },
  days: { label: 'Heat and frost days', unit: 'days / month' },
}

function Tip({ active, payload, label, unit }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string; unit: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border border-line-strong bg-surface px-2.5 py-1.5 text-[12px] shadow-lg">
      <div className="mb-0.5 font-semibold text-ink">{label}</div>
      {payload.map((r) => (
        <div key={r.name} className="flex items-center gap-2 text-ink-2">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: r.color }} />
          <span className="flex-1">{r.name}</span>
          <span className="tnum font-semibold text-ink">{fmt(r.value, 1)} {unit}</span>
        </div>
      ))}
    </div>
  )
}

export function ClimateCharts({ places }: { places: PlaceDetail[] }) {
  const [m, setM] = useState<ClimMetric>('temp')
  const withN = places.filter((p) => p.normals)
  const rows = useMemo(() => MONTHS.map((mon, i) => {
    const r: Record<string, string | number | null> = { month: mon }
    for (const p of withN) {
      const n = p.normals!.months[i]
      if (m === 'temp') { r[`${p.id}`] = n.t_mean; r[`${p.id}__max`] = n.t_max; r[`${p.id}__min`] = n.t_min }
      if (m === 'rain') r[p.id] = n.precip_mm
      if (m === 'sun') r[p.id] = n.sunshine_h
      if (m === 'days') { r[`${p.id}__heat`] = n.heat_days; r[`${p.id}__frost`] = n.frost_days }
    }
    return r
  }), [withN, m])
  const color = (id: string) => PLACE_COLORS[places.findIndex((p) => p.id === id) % PLACE_COLORS.length]
  const unit = CLIM[m].unit
  const series = m === 'days'
    ? withN.flatMap((p) => [
      { key: `${p.id}__heat`, name: `${p.short_name} heat days (feels-like > 35 °C)`, color: color(p.id), dashed: false },
      { key: `${p.id}__frost`, name: `${p.short_name} frost days (min < 0 °C)`, color: color(p.id), dashed: true },
    ])
    : m === 'temp'
      ? withN.flatMap((p) => [
        { key: p.id, name: `${p.short_name} mean`, color: color(p.id), dashed: false },
        { key: `${p.id}__max`, name: `${p.short_name} mean max`, color: color(p.id), dashed: true },
      ])
      : withN.map((p) => ({ key: p.id, name: p.short_name, color: color(p.id), dashed: false }))

  const table = () => (
    <table className="w-full text-[12px] tnum">
      <thead className="sticky top-0 bg-surface text-left text-ink-3">
        <tr><th className="py-1 pr-3 font-medium">Month</th>{series.map((s) => <th key={s.key} className="py-1 pr-3 text-right font-medium">{s.name}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={String(r.month)} className="border-t border-line">
            <td className="py-0.5 pr-3 text-ink-2">{r.month}</td>
            {series.map((s) => <td key={s.key} className="py-0.5 pr-3 text-right">{fmt(r[s.key] as number | null, 1)}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  )

  return (
    <Card title="Monthly climate, 1991-2020" help={<PlaceTip id="place_climate_charts" />}
      right={<Seg value={m} onChange={setM} label="Climate variable" options={(Object.keys(CLIM) as ClimMetric[]).map((k) => ({ v: k, l: CLIM[k].label }))} />}
      footer={withN[0]?.normals ? <AsOf ts={withN[0].normals.updated_at} source={`${withN[0].normals.source}, ${withN[0].normals.period}`} href={withN[0].normals.url} label="computed" kind="reanalysis" /> : null}>
      {withN.length === 0 ? <p className="text-[12.5px] text-ink-3">Climate normals are computed once per place, one place per run: no data yet.</p> : (
        <ChartFrame table={table}>
          <p className="mb-1 text-[11px] text-ink-3">Axis: <b className="text-ink-2">{unit}</b>{withN.length < places.length ? ` · missing: ${places.filter((p) => !p.normals).map((p) => p.short_name).join(', ')}` : ''}</p>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              {m === 'rain' ? (
                <BarChart data={rows} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="month" tickLine={false} />
                  <YAxis width={40} tickLine={false} axisLine={false} />
                  <Tooltip content={<Tip unit={unit} />} cursor={{ fill: 'var(--band)' }} />
                  <RLegend wrapperStyle={{ fontSize: 12 }} />
                  {series.map((s) => <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} isAnimationActive={false} radius={[2, 2, 0, 0]} />)}
                </BarChart>
              ) : (
                <LineChart data={rows} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="month" tickLine={false} />
                  <YAxis width={40} tickLine={false} axisLine={false} />
                  {m === 'temp' && <ReferenceLine y={0} stroke="var(--axis)" strokeWidth={1.5} />}
                  <Tooltip content={<Tip unit={unit} />} />
                  <RLegend wrapperStyle={{ fontSize: 12 }} />
                  {series.map((s) => (
                    <Line key={s.key} dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={s.dashed ? 1.5 : 2.25}
                      strokeDasharray={s.dashed ? '5 4' : undefined} dot={false} isAnimationActive={false} />
                  ))}
                </LineChart>
              )}
            </ResponsiveContainer>
          </div>
        </ChartFrame>
      )}
    </Card>
  )
}

type ProjMetric = 't_mean' | 'hot_days_yr' | 'frost_days_yr' | 'precip_pct'
const PROJ: Record<ProjMetric, { label: string; unit: string; d: number }> = {
  t_mean: { label: 'Warming', unit: 'C', d: 2 },
  hot_days_yr: { label: 'Hot days > 35 °C', unit: 'days/yr', d: 1 },
  frost_days_yr: { label: 'Frost days', unit: 'days/yr', d: 1 },
  precip_pct: { label: 'Rain', unit: '%', d: 1 },
}

export function ProjectionChart({ places }: { places: PlaceDetail[] }) {
  const [m, setM] = useState<ProjMetric>('t_mean')
  const withP = places.filter((p) => p.projection)
  const rows = withP.map((p) => {
    const e = p.projection!.delta[m]
    return { name: p.short_name, id: p.id, mean: e.mean, range: [e.mean - e.min, e.max - e.mean], min: e.min, max: e.max,
      base: p.projection!.baseline_mean[m === 'precip_pct' ? 'precip_mm_yr' : m]?.mean ?? null }
  })
  const unit = PROJ[m].unit
  const color = (id: string) => PLACE_COLORS[places.findIndex((p) => p.id === id) % PLACE_COLORS.length]
  const table = () => (
    <table className="w-full text-[12px] tnum">
      <thead className="text-left text-ink-3"><tr><th className="py-1 pr-3 font-medium">Place</th><th className="py-1 pr-3 text-right font-medium">1991-2020 (models)</th><th className="py-1 pr-3 text-right font-medium">Change, mean</th><th className="py-1 pr-3 text-right font-medium">Model range</th></tr></thead>
      <tbody>{rows.map((r) => (
        <tr key={r.id} className="border-t border-line"><td className="py-0.5 pr-3">{r.name}</td><td className="py-0.5 pr-3 text-right">{fmt(r.base, 1)}</td>
          <td className="py-0.5 pr-3 text-right">{signed(r.mean, PROJ[m].d)} {unit}</td><td className="py-0.5 pr-3 text-right">{signed(r.min, PROJ[m].d)} to {signed(r.max, PROJ[m].d)}</td></tr>
      ))}</tbody>
    </table>
  )
  const first = withP[0]?.projection
  return (
    <Card title="Change by 2050 (2036-2050 vs 1991-2020)" help={<PlaceTip id="place_projection" />}
      right={<Seg value={m} onChange={setM} label="Projected variable" options={(Object.keys(PROJ) as ProjMetric[]).map((k) => ({ v: k, l: PROJ[k].label }))} />}
      footer={first ? <AsOf ts={first.updated_at} source={`${first.source}; ${first.n_models} models; ${first.scenario}`} href={first.url} label="computed" /> : null}>
      {withP.length === 0 ? <p className="text-[12.5px] text-ink-3">Projections are computed once per place (two requests on two runs, to spare the shared quota): no data yet.</p> : (
        <ChartFrame table={table}>
          <p className="mb-1 text-[11px] text-ink-3">Bar = mean of the models; whisker = lowest to highest model. Axis: <b className="text-ink-2">{unit}</b>{withP.length < places.length ? ` · not computed yet: ${places.filter((p) => !p.projection).map((p) => p.short_name).join(', ')}` : ''}</p>
          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="name" tickLine={false} />
                <YAxis width={44} tickLine={false} axisLine={false} />
                <ReferenceLine y={0} stroke="var(--axis)" strokeWidth={1.5} />
                <Tooltip cursor={{ fill: 'var(--band)' }} content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const r = payload[0].payload as (typeof rows)[number]
                  return (
                    <div className="rounded-md border border-line-strong bg-surface px-2.5 py-1.5 text-[12px] shadow-lg">
                      <div className="font-semibold">{r.name}</div>
                      <div>Mean change: <b className="tnum">{signed(r.mean, PROJ[m].d)} {unit}</b></div>
                      <div className="text-ink-2">Models: {signed(r.min, PROJ[m].d)} to {signed(r.max, PROJ[m].d)}</div>
                    </div>
                  )
                }} />
                <Bar dataKey="mean" isAnimationActive={false} radius={[3, 3, 0, 0]}>
                  {rows.map((r) => <Cell key={r.id} fill={color(r.id)} />)}
                  <ErrorBar dataKey="range" width={8} strokeWidth={1.5} stroke="var(--ink-2)" direction="y" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          {first && <p className="mt-1 text-[11px] text-ink-3">{first.note}</p>}
        </ChartFrame>
      )}
    </Card>
  )
}

export function SeasonalTable({ places }: { places: PlaceDetail[] }) {
  const months = Array.from(new Set(places.flatMap((p) => p.seasonal?.months.map((x) => x.month) ?? []))).sort().slice(0, 6)
  const first = places.find((p) => p.seasonal)?.seasonal
  const cellColor = (t: number | null | undefined) => (t === null || t === undefined ? undefined
    : t >= 1 ? 'var(--warm)' : t <= -1 ? 'var(--cold)' : undefined)
  return (
    <Card title="Next 6 months (ECMWF seasonal)" help={<PlaceTip id="place_seasonal" />}
      footer={first ? <AsOf ts={first.updated_at} source={first.model} href={first.url} kind="forecast" label="issued/fetched" /> : null}>
      {!months.length ? <p className="text-[12.5px] text-ink-3">No seasonal forecast collected yet.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px] text-[12px] tnum">
            <thead className="text-left text-ink-3">
              <tr><th className="py-1 pr-2 font-medium">Place</th>{months.map((mo) => <th key={mo} className="px-1 py-1 text-right font-medium">{fmtMonth(`${mo}-15`)}</th>)}</tr>
            </thead>
            <tbody>
              {places.map((p) => (
                <tr key={p.id} className="border-t border-line align-top">
                  <th scope="row" className="py-1.5 pr-2 text-left font-medium">{p.short_name}</th>
                  {months.map((mo) => {
                    const x = p.seasonal?.months.find((s) => s.month === mo)
                    return (
                      <td key={mo} className="px-1 py-1.5 text-right">
                        <div style={{ color: cellColor(x?.temp_anomaly_c) }}>{signed(x?.temp_anomaly_c ?? null, 1)} °C</div>
                        <div className="text-ink-3">{x?.precip_pct_of_model_normal === null || x?.precip_pct_of_model_normal === undefined ? '--' : `${x.precip_pct_of_model_normal.toFixed(0)}% rain`}</div>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-1.5 text-[11px] text-ink-3">Temperature anomaly vs the model's own normal (red: +1 °C or more, blue: -1 °C or less); rain as % of the model normal. Tendencies, not daily weather.</p>
        </div>
      )}
    </Card>
  )
}
