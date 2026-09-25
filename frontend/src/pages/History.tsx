/**
 * /history: what past strong El Ninos did to Koh Samui (GET /api/local/analogs +
 * /api/local/analogs/history). Every number is the backend's; nothing is estimated here.
 * While the ERA5 history is still being fetched, the numbers that need a missing month are
 * blank and labelled "loading, not estimated" (history.windows_pending, samui.complete).
 */
import { useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useAnalogs, useAnalogsHistory } from '../api/client'
import type { AnalogEvent, AnalogImpact, AnalogIndex, Analogs, AnalogsHistory } from '../api/types'
import { ChartFrame } from '../components/charts'
import { ChipSelect, FilterGroup, FilteredEmpty } from '../components/filters'
import { AsOf, Card, Empty, ErrorBox, KindBadge, PageHeader, Skeleton } from '../components/ui'
import { HelpFor, HelpTip, PageGuide, Term, type TopicId } from '../help'
import { fmtDate, fmtNum, fmtSigned, toneText } from '../lib/format'
import { safeUrl } from '../lib/geo'
import { staleAfterMs } from '../lib/series'
import { useUrlFilters } from '../lib/urlFilters'

// --------------------------------------------------------------------------- constants

/** One colour per event, the same as the Overview ONI chart where the event appears there. */
const EVENT_COLOR: Record<string, string> = {
  '1982-83': 'var(--s4)', '1987-88': 'var(--s8)', '1991-92': 'var(--s5)', '1997-98': 'var(--s1)',
  '2009-10': 'var(--s6)', '2015-16': 'var(--s3)', '2023-24': 'var(--s7)', '2026-27': 'var(--s2)',
}
const CURRENT = '2026-27'
/** Water-year axis: June of the developing year (Y) to May of the next (Y+1). */
const WY_MONTHS = [6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5]
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const COMPLETE_MONTH_DAYS = 25 // backend analogs.COMPLETE_MONTH_DAYS
const HEAT_WATCH_C = 39 // backend HEAT_FEELS_C (the risk engine's heat "watch" threshold)

const IMPACT_TYPE: Record<string, { label: string; color: string; topic: TopicId }> = {
  water_shortage: { label: 'Water shortage', color: 'var(--critical)', topic: 'samui_water_supply' },
  drought: { label: 'Drought', color: 'var(--serious)', topic: 'factor_water' },
  flood: { label: 'Flood', color: 'var(--cold)', topic: 'factor_flood' },
  storm: { label: 'Storm', color: 'var(--s7)', topic: 'tropical_cyclone' },
  haze: { label: 'Haze', color: 'var(--s4)', topic: 'asmc_haze' },
  heat: { label: 'Heat', color: 'var(--warm)', topic: 'factor_heat' },
  bleaching: { label: 'Coral bleaching', color: 'var(--s5)', topic: 'coral_reef_watch' },
  paper: { label: 'Research paper', color: 'var(--ink-3)', topic: 'analogs_impacts' },
}
const typeMeta = (t: string) => IMPACT_TYPE[t] ?? { label: t.replace(/_/g, ' '), color: 'var(--ink-3)', topic: 'analogs_impacts' as TopicId }

// --------------------------------------------------------------------------- small helpers

/** Rain as % of normal: the live water factor's bands (< 60 serious, < 75 watch), > 125 wet. */
const rainTone = (p: number | null | undefined) => (p === null || p === undefined ? undefined : p < 60 ? 'var(--critical)' : p < 75 ? 'var(--serious)' : p > 125 ? 'var(--cold)' : undefined)
const heatTone = (v: number | null | undefined) => (v === null || v === undefined ? undefined : v >= 40 ? 'var(--critical)' : v >= HEAT_WATCH_C ? 'var(--serious)' : undefined)
const heatDaysTone = (n: number | null | undefined) => (n === null || n === undefined ? undefined : n >= 7 ? 'var(--critical)' : n >= 3 ? 'var(--serious)' : undefined)
const dryTone = (d: number | null | undefined) => (d === null || d === undefined ? undefined : d >= 45 ? 'var(--critical)' : d >= 30 ? 'var(--serious)' : undefined)

function Cell({ v, unit = '', digits = 0, tone, sub, loading }: {
  v: number | null | undefined; unit?: string; digits?: number; tone?: string; sub?: ReactNode
  /** the number is missing because the history is incomplete (not because it is zero) */
  loading?: boolean
}) {
  if (v === null || v === undefined) {
    return <span className="text-ink-3" title={loading ? 'Loading: a month of the ERA5 history is not stored yet. Not estimated.' : 'No value'}>{loading ? '-- loading' : '--'}</span>
  }
  return (
    <span className="inline-flex flex-col items-end">
      <b className="rounded px-1 tnum" style={tone ? { color: toneText(tone), background: `color-mix(in srgb, ${tone} 16%, transparent)` } : undefined}>
        {fmtNum(v, digits)}{unit}
      </b>
      {sub && <span className="text-[10px] text-ink-3">{sub}</span>}
    </span>
  )
}

function idx(x: AnalogIndex | null | undefined, digits = 2): ReactNode {
  if (!x || x.value === null || x.value === undefined) return <span className="text-ink-3">--</span>
  return <span className="tnum"><b>{fmtSigned(x.value, digits)} °C</b>{x.season ? <span className="text-ink-3"> · {x.season}</span> : x.ts ? <span className="text-ink-3"> · {fmtDate(x.ts)}</span> : null}</span>
}

const EventChip = ({ id }: { id: string }) => (
  <span className="inline-flex items-center gap-1.5 font-semibold whitespace-nowrap">
    <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: EVENT_COLOR[id] ?? 'var(--ink-3)' }} aria-hidden />{id}
  </span>
)

// --------------------------------------------------------------------------- history status

function StatusCard({ d }: { d: Analogs }) {
  const h = d.history
  const pending = h.windows_pending ?? []
  const complete = pending.length === 0 && h.months > 0
  return (
    <Card title="The ERA5 history behind this page" help={<HelpTip id="analogs_history_status" />} className="min-h-[96px]"
      right={<KindBadge kind="reanalysis" compact />}
      footer={<AsOf ts={h.updated_at} label="history updated" tz="UTC" source="Open-Meteo archive (ECMWF ERA5), Maenam grid cell" href="https://open-meteo.com/en/docs/historical-weather-api" staleMs={3 * 86400000} />}>
      {complete ? (
        <p className="text-[13px] text-ink-2">
          <b style={{ color: 'var(--good-ink)' }}>● Complete:</b> {h.months.toLocaleString('en-GB')} months from {h.from} to {h.to}, ERA5 through <b className="text-ink">{fmtDate(h.last_day)}</b> (the reanalysis lags about 5 days).
          {d.point?.lat !== null && d.point?.lat !== undefined && <> Grid cell {fmtNum(d.point.lat, 2)} N, {fmtNum(d.point.lon, 2)} E, the same cell as the live rain factor.</>}
        </p>
      ) : (
        <div className="text-[13px] text-ink-2" role="status">
          <p><b style={{ color: 'var(--warning)' }}>▲ Loading, not estimated:</b> {pending.length} decade window{pending.length === 1 ? '' : 's'} of ERA5 data still to fetch ({pending.join(', ')}); {h.months} months stored so far{h.from ? ` (${h.from} to ${h.to})` : ''}.</p>
          <p className="mt-1">One window is fetched per hour (about 8 hours on a fresh install). Every number that needs a missing month is shown as "-- loading" below; nothing is filled in. Progress is on the <Link className="link" to="/sources?q=samui_era5_history">Sources page</Link>.</p>
        </div>
      )}
    </Card>
  )
}

// --------------------------------------------------------------------------- takeaways

function Takeaways({ d }: { d: Analogs }) {
  const items = d.takeaways ?? []
  return (
    <Card title="Takeaways" help={<><HelpTip id="analogs" /><HelpTip id="analogs_reading" label="How are these sentences built?" /></>} tour="history-takeaways"
      right={<span className="text-[11px] text-ink-3">every number is in the tables below</span>} className="min-h-[200px]">
      {items.length ? (
        <ol className="list-decimal space-y-2 pl-6 text-[14px] leading-relaxed text-ink marker:font-semibold marker:text-ink-3">
          {items.map((t, i) => <li key={i} className={/^Sample:/.test(t) ? 'text-[12px] text-ink-2' : ''}>{t}</li>)}
        </ol>
      ) : <Empty what="No takeaways yet" source="analogs engine (/api/local/analogs)" />}
    </Card>
  )
}

// --------------------------------------------------------------------------- events table

function EventsTable({ d }: { d: Analogs }) {
  const cur = d.current_event
  const notes = d.events.filter((e) => e.note)
  const th = 'px-2 py-1.5 text-left text-[11px] font-semibold tracking-wide text-ink-3 uppercase whitespace-nowrap'
  const td = 'px-2 py-1.5 align-top'
  return (
    <Card title="Seven strong El Ninos vs 2026-27" help={<><HelpTip id="analogs_events_table" /><HelpTip id="strength_categories" label="What do the strength bands mean?" /></>}
      tour="history-events" pad={false} className="min-h-[300px]"
      right={<><KindBadge kind="observed" compact /><span className="text-[11px] text-ink-3">peaks read from the NOAA CPC series</span></>}
      footer={<AsOf ts={cur.oni?.ts} label="latest ONI" tz="UTC" kind="observed" validFor={cur.oni?.valid_for} source="NOAA CPC ONI / RONI (series oni, roni)" href="https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt" staleMs={staleAfterMs('oni')} />}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-[13px]">
          <thead className="bg-surface-2">
            <tr>
              <th className={th}>Event</th>
              <th className={th}>Peak <Term id="oni">ONI</Term></th>
              <th className={th}>Peak <Term id="roni">RONI</Term></th>
              <th className={th}>Strength</th>
              <th className={th}><abbr title="June-July-August of the developing year: the season the 2026 event has reached">ONI at JJA</abbr></th>
              <th className={th}>RONI at JJA</th>
              <th className={th}>Documented impacts</th>
            </tr>
          </thead>
          <tbody>
            {d.events.map((e) => (
              <tr key={e.id} className="border-t border-line">
                <td className={td}><EventChip id={e.id} />{e.note && <span className="ml-1 text-ink-3" title={e.note} aria-label="note below">*</span>}</td>
                <td className={td}>{idx(e.peak_oni)}</td>
                <td className={td}>{idx(e.peak_roni)}</td>
                <td className={td}>{e.strength ?? <span className="text-ink-3">--</span>}</td>
                <td className={`${td} tnum`}>{e.oni_jja === null ? '--' : `${fmtSigned(e.oni_jja, 2)} °C`}</td>
                <td className={`${td} tnum`}>{e.roni_jja === null ? '--' : `${fmtSigned(e.roni_jja, 2)} °C`}</td>
                <td className={`${td} tnum`}>{e.impacts.length ? <a className="link" href="#history-impacts">{e.impacts.length}</a> : <span className="text-ink-3">none found</span>}</td>
              </tr>
            ))}
            <tr className="border-t-2 border-line-strong" style={{ background: 'color-mix(in srgb, var(--s2) 10%, transparent)' }}>
              <td className={td}><EventChip id={cur.id} /><div className="text-[11px] font-normal text-ink-2">so far ({cur.month})</div></td>
              <td className={td}>{idx(cur.oni)}<div className="text-[10px] text-ink-3">latest, not the peak</div></td>
              <td className={td}>{idx(cur.roni)}</td>
              <td className={td}>{cur.strength ?? '--'}{cur.nino34_weekly?.value !== null && cur.nino34_weekly?.value !== undefined && <div className="text-[11px] text-ink-2 tnum">weekly Nino 3.4 {fmtSigned(cur.nino34_weekly.value, 1)} °C ({fmtDate(cur.nino34_weekly.ts)})</div>}</td>
              <td className={`${td} tnum`}>{cur.oni?.season?.startsWith('JJA') ? `${fmtSigned(cur.oni.value, 2)} °C` : '--'}</td>
              <td className={`${td} tnum`}>{cur.roni?.season?.startsWith('JJA') ? `${fmtSigned(cur.roni.value, 2)} °C` : '--'}</td>
              <td className={`${td} tnum`}>{cur.impacts.length || <span className="text-ink-3">none yet</span>}</td>
            </tr>
          </tbody>
        </table>
      </div>
      {notes.length > 0 && (
        <ul className="border-t border-line px-4 py-2 text-[11px] text-ink-3">
          {notes.map((e) => <li key={e.id}>* {e.id}: {e.note}</li>)}
        </ul>
      )}
    </Card>
  )
}

// --------------------------------------------------------------------------- Samui metrics table

function MetricsTable({ d }: { d: Analogs }) {
  const nb = d.neutral_baseline
  const bm = nb.metrics ?? {}
  const cur = d.current_event
  const sf = cur.so_far
  const th = 'px-2 py-1.5 text-right text-[11px] font-semibold tracking-wide text-ink-3 uppercase whitespace-nowrap first:text-left'
  const td = 'px-2 py-1.5 text-right align-top tnum first:text-left'
  const legend = (
    <ul className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-3" aria-label="Colour scale">
      <li>Rain, % of the {d.normal.period} normal:</li>
      <li><span className="rounded px-1 font-semibold" style={{ color: toneText('var(--critical)'), background: 'color-mix(in srgb, var(--critical) 16%, transparent)' }}>&lt; 60%</span></li>
      <li><span className="rounded px-1 font-semibold" style={{ color: toneText('var(--serious)'), background: 'color-mix(in srgb, var(--serious) 16%, transparent)' }}>60-74%</span></li>
      <li><span className="rounded px-1 font-semibold" style={{ color: toneText('var(--cold)'), background: 'color-mix(in srgb, var(--cold) 16%, transparent)' }}>&gt; 125%</span></li>
      <li>· heat from {HEAT_WATCH_C} °C feels-like · dry spell from 30 days</li>
    </ul>
  )
  return (
    <Card title="What Samui got: rain, heat and dry spells per event" help={<><HelpTip id="analogs_colour_scale" /><HelpTip id="rain_vs_normal" label="What is % of normal?" /></>}
      tour="history-metrics" pad={false} className="min-h-[360px]"
      right={<><KindBadge kind="reanalysis" compact /><span className="text-[11px] text-ink-3">ERA5 grid cell, {d.normal.period} normal</span></>}
      footer={<div className="flex flex-wrap items-center justify-between gap-2">{legend}<AsOf ts={d.history.last_day} label="ERA5 through" source="Open-Meteo archive (ECMWF ERA5)" href="https://open-meteo.com/en/docs/historical-weather-api" /></div>}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px] text-[13px]">
          <thead className="bg-surface-2">
            <tr>
              <th className={th}>Event (water year)</th>
              <th className={th}><abbr title="October to December of the developing year: the northeast-monsoon refill">Oct-Dec rain</abbr></th>
              <th className={th}><abbr title="January to May after the peak: the dry season">Jan-May rain</abbr></th>
              <th className={th}><abbr title="February to April: the danger window for water">Feb-Apr rain</abbr></th>
              <th className={th}>Max <Term id="heat_index">feels-like</Term> (Jan-May)</th>
              <th className={th}>Days &gt;= {HEAT_WATCH_C} °C</th>
              <th className={th}>Longest dry spell</th>
            </tr>
          </thead>
          <tbody>
            {d.events.map((e) => {
              const s = e.samui
              const ld = !s.complete
              return (
                <tr key={e.id} className="border-t border-line">
                  <td className={td}><EventChip id={e.id} /><div className="text-[10px] font-normal text-ink-3">{e.detail?.water_year ?? `${e.years[0]}-07/${e.years[1]}-06`}</div></td>
                  <td className={td}><Cell v={s.ne_monsoon_rain_pct} unit="%" tone={rainTone(s.ne_monsoon_rain_pct)} loading={ld} sub={s.ne_monsoon_rain_mm !== null ? `${fmtNum(s.ne_monsoon_rain_mm, 0)} mm` : undefined} /></td>
                  <td className={td}><Cell v={s.dry_season_rain_pct} unit="%" tone={rainTone(s.dry_season_rain_pct)} loading={ld} sub={s.dry_season_rain_mm !== null ? `${fmtNum(s.dry_season_rain_mm, 0)} mm` : undefined} /></td>
                  <td className={td}><Cell v={s.feb_apr_rain_pct} unit="%" tone={rainTone(s.feb_apr_rain_pct)} loading={ld} sub={s.feb_apr_rain_mm !== null ? `${fmtNum(s.feb_apr_rain_mm, 0)} mm` : undefined} /></td>
                  <td className={td}><Cell v={s.max_feels_like} unit=" °C" digits={1} tone={heatTone(s.max_feels_like)} loading={ld} sub={s.max_feels_like_day ? fmtDate(s.max_feels_like_day) : undefined} /></td>
                  <td className={td}><Cell v={s.heat_days} tone={heatDaysTone(s.heat_days)} loading={ld} /></td>
                  <td className={td}><Cell v={s.longest_dry_spell_days} unit=" d" tone={dryTone(s.longest_dry_spell_days)} loading={ld} sub={s.longest_dry_spell_ne_days !== null ? `Oct-Dec: ${s.longest_dry_spell_ne_days} d` : undefined} /></td>
                </tr>
              )
            })}
            <tr className="border-t-2 border-line-strong bg-surface-2/60">
              <td className={td}><b>Neutral years, median</b><div className="text-[10px] font-normal text-ink-3">n = {nb.n} <HelpTip id="analogs_colour_scale" label="What are neutral years?" /></div></td>
              {(['ne_monsoon_rain_pct', 'dry_season_rain_pct', 'feb_apr_rain_pct', 'max_feels_like', 'heat_days', 'longest_dry_spell_days'] as const).map((k) => {
                const m = bm[k]
                const unit = k.endsWith('pct') ? '%' : k === 'max_feels_like' ? ' °C' : k === 'longest_dry_spell_days' ? ' d' : ''
                return <td key={k} className={td}><Cell v={m?.median} unit={unit} digits={k === 'max_feels_like' ? 1 : 0} loading={nb.n === 0} sub={m && m.min !== null && m.max !== null ? `${fmtNum(m.min, 0)} to ${fmtNum(m.max, 0)}` : undefined} /></td>
              })}
            </tr>
            <tr className="border-t border-line" style={{ background: 'color-mix(in srgb, var(--s2) 10%, transparent)' }}>
              <td className={td}><EventChip id={cur.id} /><div className="text-[10px] font-normal text-ink-2">so far{sf?.last_day ? `, ERA5 through ${fmtDate(sf.last_day)}` : ''}</div></td>
              <td className={td}>{sf?.ne_monsoon ? <Cell v={sf.ne_monsoon.pct} unit="%" tone={rainTone(sf.ne_monsoon.pct)} sub={`${fmtNum(sf.ne_monsoon.rain_mm, 0)} mm, ${sf.ne_monsoon.months.map((m) => MON[Number(m.slice(5)) - 1]).join('-')}`} /> : <span className="text-[12px] text-ink-3">not started</span>}</td>
              <td className={td} colSpan={2}>
                {sf?.sw_monsoon ? (
                  <span className="text-[12px] text-ink-2">Jun-Sep so far ({sf.sw_monsoon.months.map((m) => MON[Number(m.slice(5)) - 1]).join('-')}): <Cell v={sf.sw_monsoon.pct} unit="%" tone={rainTone(sf.sw_monsoon.pct)} sub={`${fmtNum(sf.sw_monsoon.rain_mm, 0)} mm`} /> · the dry season is in 2027</span>
                ) : <span className="text-[12px] text-ink-3">{sf ? 'no complete month yet' : '-- loading'}</span>}
              </td>
              <td className={td} colSpan={3}><span className="text-[12px] text-ink-3">Jan-May 2027: ahead</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  )
}

// --------------------------------------------------------------------------- monthly charts

type Row = Record<string, string | number | null | [number, number]>

function useWaterYearRows(d: Analogs | null | undefined, h: AnalogsHistory | null | undefined, field: 'rain_mm' | 'app_max') {
  return useMemo(() => {
    if (!d || !h?.months) return { rows: [] as Row[], series: [] as string[] }
    const fi = h.fields.indexOf(field)
    const ni = h.fields.indexOf('n_days')
    const ids = [...d.events.map((e) => e.id), d.current_event.id]
    const y1 = (id: string) => (id === d.current_event.id ? d.current_event.years[0] : d.events.find((e) => e.id === id)!.years[0])
    const rows: Row[] = WY_MONTHS.map((mo) => {
      const label = `${MON[mo - 1]} ${mo >= 6 ? 'Y' : 'Y+1'}`
      const mm = String(mo).padStart(2, '0')
      const norm = h.normals?.[mm]
      const nv = norm ? (field === 'rain_mm' ? norm.rain_mm : norm.app_max) : null
      const r: Row = { x: label, normal: nv, band: nv !== null && field === 'rain_mm' ? [Math.round(nv * 0.75), Math.round(nv * 1.25)] : null }
      for (const id of ids) {
        const y = y1(id) + (mo >= 6 ? 0 : 1)
        const row = h.months[`${y}-${mm}`]
        const ok = !!row && fi >= 0 && ni >= 0 && (row[ni] ?? 0) >= COMPLETE_MONTH_DAYS
        r[id] = ok ? row[fi] : null
      }
      return r
    })
    return { rows, series: ids }
  }, [d, h, field])
}

function TipBox({ label, rows }: { label: string; rows: { name: string; color: string; value: string }[] }) {
  return (
    <div className="rounded-md border border-line-strong bg-surface px-2.5 py-1.5 text-[12px] shadow-lg">
      <div className="mb-0.5 font-semibold text-ink">{label}</div>
      {rows.map((r) => (
        <div key={r.name} className="flex items-center gap-2 text-ink-2">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: r.color }} /><span className="flex-1">{r.name}</span><span className="tnum font-semibold text-ink">{r.value}</span>
        </div>
      ))}
    </div>
  )
}

function WaterYearChart({ d, h, field, unit, title, help, refLine }: {
  d: Analogs; h: AnalogsHistory; field: 'rain_mm' | 'app_max'; unit: string; title: string; help: ReactNode; refLine?: number
}) {
  const { rows, series } = useWaterYearRows(d, h, field)
  const [hidden, setHidden] = useState<Set<string>>(() => new Set())
  const toggle = (id: string) => setHidden((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n })
  const fmt = (v: number | null | undefined) => (v === null || v === undefined ? '--' : `${fmtNum(v, field === 'rain_mm' ? 0 : 1)} ${unit}`)
  return (
    <Card title={title} help={help} className="min-h-[420px]" bodyClass="flex flex-col"
      right={<KindBadge kind="reanalysis" compact help={false} />}
      footer={<AsOf ts={h.last_day} label="ERA5 through" source={`${h.source ?? 'Open-Meteo archive (ECMWF ERA5)'}, monthly ${field === 'rain_mm' ? 'totals' : 'maxima'} vs the ${d.normal.period} normal`} href={safeUrl(h.url) ?? 'https://open-meteo.com/en/docs/historical-weather-api'} />}>
      <ul className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px]" aria-label="Events shown (click to hide or show)">
        {series.map((id) => (
          <li key={id}>
            <button type="button" aria-pressed={!hidden.has(id)} onClick={() => toggle(id)}
              className={`inline-flex min-h-6 items-center gap-1.5 rounded px-1 text-ink-2 hover:text-ink ${hidden.has(id) ? 'line-through opacity-60' : ''}`} title={hidden.has(id) ? `Show ${id}` : `Hide ${id}`}>
              <svg width="18" height="8" aria-hidden><line x1="0" y1="4" x2="18" y2="4" stroke={EVENT_COLOR[id]} strokeWidth={id === CURRENT ? 4 : 2.5} /></svg>{id}{id === CURRENT ? ' (so far)' : ''}
            </button>
          </li>
        ))}
        <li className="flex items-center gap-1.5 text-ink-3"><span className="inline-block h-3 w-4 rounded-sm" style={{ background: 'var(--band)', border: '1px dashed var(--ink-3)' }} aria-hidden />{field === 'rain_mm' ? `normal ± 25% (${d.normal.period})` : `normal monthly maximum (${d.normal.period})`}</li>
        {refLine !== undefined && <li className="text-ink-3">· line at {refLine} °C = heat "watch" threshold</li>}
      </ul>
      <ChartFrame table={() => (
        <table className="w-full text-[12px] tnum">
          <thead className="sticky top-0 bg-surface text-left text-ink-3"><tr><th className="py-1 pr-3 font-medium">Month</th><th className="py-1 pr-3 text-right font-medium">Normal</th>{series.map((s) => <th key={s} className="py-1 pr-3 text-right font-medium">{s}</th>)}</tr></thead>
          <tbody>{rows.map((r) => <tr key={String(r.x)} className="border-t border-line"><td className="py-0.5 pr-3 text-ink-2">{String(r.x)}</td><td className="py-0.5 pr-3 text-right">{fmt(r.normal as number | null)}</td>{series.map((s) => <td key={s} className="py-0.5 pr-3 text-right">{fmt(r[s] as number | null)}</td>)}</tr>)}</tbody>
        </table>
      )}>
        <div className="h-[300px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="x" tickLine={false} interval="preserveStartEnd" minTickGap={14} tick={{ fontSize: 10 }} tickFormatter={(v: string) => v.split(' ')[0]} />
              <YAxis width={40} tickLine={false} axisLine={false} domain={field === 'rain_mm' ? [0, 'auto'] : ['auto', 'auto']} tickFormatter={(v: number) => fmtNum(v, 0)} />
              {field === 'rain_mm' && <Area dataKey="band" fill="var(--band)" stroke="none" isAnimationActive={false} connectNulls legendType="none" activeDot={false} />}
              <Line dataKey="normal" stroke="var(--ink-3)" strokeDasharray="4 3" strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />
              {refLine !== undefined && <ReferenceLine y={refLine} stroke="var(--serious)" strokeOpacity={0.6} strokeWidth={1} />}
              {series.map((id) => (
                <Line key={id} dataKey={id} stroke={EVENT_COLOR[id]} strokeWidth={id === CURRENT ? 3.5 : 2} dot={false} hide={hidden.has(id)}
                  activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }} isAnimationActive={false} connectNulls={false} />
              ))}
              <Tooltip content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null
                const r = payload[0].payload as Row
                return <TipBox label={String(label)} rows={[{ name: 'normal', color: 'var(--ink-3)', value: fmt(r.normal as number | null) },
                  ...series.filter((s) => !hidden.has(s)).map((s) => ({ name: s, color: EVENT_COLOR[s], value: fmt(r[s] as number | null) }))]} />
              }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </ChartFrame>
      <p className="mt-1 text-[11px] text-ink-3">Y = the year the event started, Y+1 = the next. A month needs at least {COMPLETE_MONTH_DAYS} valid days to be drawn; {CURRENT} stops at its last complete month.</p>
    </Card>
  )
}

function ChartsSection({ d }: { d: Analogs }) {
  const hq = useAnalogsHistory()
  const h = hq.data
  return (
    <section data-tour="history-charts" className="grid gap-4 xl:grid-cols-2" aria-labelledby="history-charts-h">
      <h2 id="history-charts-h" className="sr-only">Monthly charts</h2>
      {hq.isLoading ? <><Skeleton h={420} /><Skeleton h={420} /></> : hq.isError ? <ErrorBox error={hq.error} what="monthly history" /> : !h || !Object.keys(h.months ?? {}).length ? (
        <Card title="Monthly rain per event" help={<HelpTip id="analogs_charts" />} className="min-h-[420px]"><Empty what="No monthly ERA5 history stored yet" source="samui_era5_history (Open-Meteo archive)" /></Card>
      ) : (
        <>
          <WaterYearChart d={d} h={h} field="rain_mm" unit="mm" title="Monthly rain, event by event (Jun Y to May Y+1)" help={<><HelpTip id="analogs_charts" /><HelpTip id="climatology_baseline" label="What is the normal band?" /></>} />
          <WaterYearChart d={d} h={h} field="app_max" unit="°C" title="Hottest feels-like day of each month" help={<><HelpTip id="analogs_charts" /><HelpTip id="heat_index" label="What is feels-like?" /></>} refLine={HEAT_WATCH_C} />
        </>
      )}
    </section>
  )
}

// --------------------------------------------------------------------------- impacts timeline

interface ImpactRow extends AnalogImpact { eventId: string }

function Impacts({ d }: { d: Analogs }) {
  const f = useUrlFilters({ type: 'list', ev: 'list' }, 'im_')
  const all = useMemo<ImpactRow[]>(() => {
    const out: ImpactRow[] = []
    for (const e of d.events) for (const i of e.impacts) out.push({ ...i, eventId: e.id })
    for (const i of d.current_event.impacts) out.push({ ...i, eventId: d.current_event.id })
    for (const i of d.other_impacts) out.push({ ...i, eventId: 'other' })
    // newest first; a date with only a year sorts by that year
    return out.sort((a, b) => (b.date > a.date ? 1 : b.date < a.date ? -1 : 0))
  }, [d])
  const types = useMemo(() => { const m = new Map<string, number>(); for (const i of all) m.set(i.type, (m.get(i.type) ?? 0) + 1); return [...m.entries()].sort((a, b) => b[1] - a[1]) }, [all])
  const evIds = [...d.events.map((e) => e.id), d.current_event.id, 'other']
  const evCount = (id: string) => all.filter((i) => i.eventId === id).length
  const rows = all.filter((i) => (!f.values.type.length || f.values.type.includes(i.type)) && (!f.values.ev.length || f.values.ev.includes(i.eventId)))
  const human = [...f.values.type.map((t) => `type: ${typeMeta(t).label}`), ...f.values.ev.map((e) => `event: ${e === 'other' ? 'not an El Nino year' : e}`)]
  const checked = all.map((i) => i.checked_at).sort().at(-1) ?? null
  return (
    <Card title={`What actually happened: ${all.length} documented impacts`} help={<HelpTip id="analogs_impacts" />} tour="history-impacts" id="history-impacts" className="min-h-[480px]"
      right={<><KindBadge kind="documented" compact /><span className="text-[11px] text-ink-3">verbatim quotes, links checked live</span></>}
      footer={<AsOf ts={checked} label="links checked" source="press, agencies and peer-reviewed papers (each linked)" />}>
      <div className="flex flex-wrap gap-x-4 gap-y-2" aria-label="Impact filters">
        <FilterGroup label="Type" help={<HelpTip id="analogs_impacts" label="What do the types mean?" />}>
          <ChipSelect selected={f.values.type} onToggle={(v) => f.toggle('type', v)} limit={8}
            options={types.map(([t, n]) => ({ value: t, label: typeMeta(t).label, text: typeMeta(t).label, count: n, color: typeMeta(t).color, help: <HelpFor id={typeMeta(t).topic} appId={t} kind="impact_type" /> }))} />
        </FilterGroup>
        <FilterGroup label="Event" help={<HelpTip id="analogs_events_table" label="Which events are listed?" />}>
          <ChipSelect selected={f.values.ev} onToggle={(v) => f.toggle('ev', v)} limit={9}
            options={evIds.map((id) => ({ value: id, label: id === 'other' ? 'not an El Nino year' : id, text: id === 'other' ? 'not an El Nino year' : id, count: evCount(id), color: EVENT_COLOR[id] }))} />
        </FilterGroup>
        {f.active > 0 && <button type="button" className="btn self-end !min-h-8 !px-2 !py-0.5 !text-[12px]" onClick={f.reset}>Reset filters</button>}
      </div>
      <div className="mt-3">
        {!rows.length ? (
          <FilteredEmpty what="impacts" filters={human} onReset={f.reset} total={all.length} />
        ) : (
          <ol className="relative divide-y divide-line border-l border-line-strong pl-4" aria-label="Documented impacts, newest first">
            {rows.map((i, k) => {
              const t = typeMeta(i.type)
              const u = safeUrl(i.url)
              return (
                <li key={`${i.date}-${i.url}-${k}`} className="relative py-3">
                  <span className="absolute top-4 -left-[21px] inline-block h-2.5 w-2.5 rounded-full border-2 border-surface" style={{ background: t.color }} aria-hidden />
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-ink-3">
                    <b className="text-[13px] text-ink tnum">{i.date.length <= 4 ? i.date : fmtDate(i.date)}</b>
                    <span className="chip" style={{ color: toneText(t.color), borderColor: t.color }}>{t.label}</span>
                    <HelpFor id={t.topic} appId={i.type} kind="impact_type" />
                    <span>· {i.area}</span>
                    <span className="chip" title={i.enso}>{i.eventId === 'other' ? 'not an El Nino year' : i.eventId}</span>
                    <KindBadge kind="documented" compact help={false} />
                    {i.note && <span title={i.note}>· {i.note}</span>}
                  </div>
                  <p className="mt-1 text-[13px] leading-snug text-ink">{i.text}</p>
                  {i.quote && <blockquote className="mt-1 border-l-2 border-line-strong pl-2 text-[12px] leading-snug text-ink-2 italic">"{i.quote}"</blockquote>}
                  <div className="mt-1 flex flex-wrap items-center gap-x-2 text-[11px] text-ink-3">
                    {u ? <a className="link" href={u} target="_blank" rel="noreferrer">{i.source_title} ↗</a> : <span>{i.source_title}</span>}
                    <span>· {i.publisher}{i.published ? `, ${i.published.length <= 4 ? i.published : fmtDate(i.published)}` : ''}</span>
                    <span>· checked {fmtDate(i.checked_at)}</span>
                  </div>
                </li>
              )
            })}
          </ol>
        )}
      </div>
      {d.impacts_not_found?.length > 0 && (
        <div className="mt-4 rounded-lg border border-dashed border-line-strong p-3 text-[12px]">
          <div className="flex items-center gap-1 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">Looked for, not found <HelpTip id="analogs_impacts" label="Why list what was not found?" /></div>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-ink-2">
            {d.impacts_not_found.map((x, i) => <li key={i}>{x}</li>)}
          </ul>
          <p className="mt-1 text-ink-3">A gap in the timeline is not evidence that nothing happened; these searches came back empty and the page says so instead of filling them.</p>
        </div>
      )}
    </Card>
  )
}

// --------------------------------------------------------------------------- method + limits

function Method({ d }: { d: Analogs }) {
  const kinds = Object.entries(d.kinds ?? {})
  const main = d.sources.filter((s) => !s.id.startsWith('impact_'))
  const nImpactSources = d.sources.length - main.length
  const complete = d.events.filter((e) => e.samui.complete).length
  return (
    <Card title="Method and limits" help={<><HelpTip id="analogs_reading" /><HelpTip id="analogs_limits" label="Why ranges, not forecasts?" /></>} tour="history-method" className="min-h-[300px]"
      footer={<AsOf ts={d.generated_at} label="computed" tz="UTC" source="analogs engine (/api/local/analogs)" href="/api/local/analogs" />}>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h3 className="text-[11px] font-semibold tracking-wide text-ink-3 uppercase">How the numbers are made</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{d.method}</p>
          <h3 className="mt-3 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">Kinds of information on this page</h3>
          <ul className="mt-1 space-y-1 text-[13px] text-ink-2">
            {kinds.map(([k, v]) => <li key={k} className="flex flex-wrap items-center gap-1.5"><KindBadge kind={k} compact /><span>{v}</span></li>)}
          </ul>
        </div>
        <div>
          <h3 className="text-[11px] font-semibold tracking-wide text-ink-3 uppercase">Limits (read before concluding)</h3>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-[13px] leading-snug text-ink-2">
            <li><b>Small sample:</b> {complete} of {d.events.length} events reconstructed and {d.neutral_baseline.n} neutral years. A median of seven numbers moves a lot with one more event, so every event's number is shown, not only the summary.</li>
            <li><b>One grid cell:</b> ERA5 is a ~30 km reanalysis at sea level; it under-reads the island's hills and gives cooler maxima than a thermometer in Chaweng. Percentages compare ERA5 with ERA5, so the bias mostly cancels; millimetres and degrees are cell values. <Term id="era5">More on ERA5</Term>.</li>
            <li><b>Warming climate:</b> 2026 is about 1 °C warmer globally than 1982, so an old analog understates today's heat; the recent events (2016, 2024) are the better guide for heat.</li>
            <li><b>Each El Nino differs:</b> the Gulf coast's rain also depends on the Indian Ocean Dipole, the MJO and winter cold surges. Hence "N of M events", never "El Nino means".</li>
            <li><b>Reports depend on reporting:</b> a 1998 shortage on a less developed island may never have been written up online; the "not found" list says what was searched.</li>
            <li><b>The water system has changed:</b> demand, the undersea pipeline and desalination did not exist for the early events, so a 1998-type deficit would bite differently today (see <Term id="samui_water_supply">the island's water supply</Term>).</li>
          </ul>
          <h3 className="mt-3 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">Sources</h3>
          <ul className="mt-1 space-y-0.5 text-[12px]">
            {main.map((s) => { const u = safeUrl(s.url); return <li key={s.id}>{u ? <a className="link" href={u} target="_blank" rel="noreferrer">{s.title} ↗</a> : s.title}</li> })}
            {nImpactSources > 0 && <li className="text-ink-3">+ {nImpactSources} report and paper links, each on its entry in the timeline above.</li>}
          </ul>
        </div>
      </div>
    </Card>
  )
}

// --------------------------------------------------------------------------- page

export default function History() {
  const q = useAnalogs()
  const d = q.data
  const cur = d?.current_event
  return (
    <div className="space-y-4">
      <PageHeader title="Past El Ninos and Koh Samui" help={<HelpTip id="analogs" size="md" />}
        sub={<>The strong El Ninos since 1982 replayed for the island from the same ERA5 grid cell and NOAA indices the live pages use, next to 2026-27 so far. Nothing here is a forecast: it is what happened, with its sources.{cur?.strength ? <> Now: <b className="text-ink">{cur.strength}</b>{cur.oni?.value !== null && cur.oni?.value !== undefined ? ` (ONI ${fmtSigned(cur.oni.value, 2)} °C, ${cur.oni.season ?? ''})` : ''}.</> : null}</>}
        right={<Link className="btn" to="/samui">Koh Samui watch (live) ›</Link>} />
      <PageGuide page="history" />
      {q.isLoading ? (
        <div className="grid gap-4"><Skeleton h={96} /><Skeleton h={200} /><Skeleton h={300} /><Skeleton h={360} /></div>
      ) : q.isError ? <ErrorBox error={q.error} what="past El Ninos" /> : !d ? (
        <Empty what="The analogs endpoint is not available on this server" source="GET /api/local/analogs (app.analogs_api)" />
      ) : (
        <>
          <StatusCard d={d} />
          <Takeaways d={d} />
          <EventsTable d={d} />
          <MetricsTable d={d} />
          <ChartsSection d={d} />
          <Impacts d={d} />
          <Method d={d} />
        </>
      )}
      <p className="text-center text-[11px] text-ink-3">Every value shows its months, kind and source. Missing history is shown as missing, never estimated.</p>
    </div>
  )
}

export type { AnalogEvent }
