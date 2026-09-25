/** Context cards of the watch view: rain vs normal, water supply, seasonal outlook, TMD warnings, nearby events, level history. */
import { useMemo, type ReactNode } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { facet, useEventFacets, useEventsQ, useLocalHistory, useLocalWeather, useStatus } from '../../api/client'
import type { RiskFactor } from '../../api/types'
import { ChartFrame } from '../../components/charts'
import { ChipSelect, FilteredEmpty, FilterGroup, PresetSelect } from '../../components/filters'
import { AsOf, Card, Empty, Ext, KindBadge, LevelBadge, Skeleton } from '../../components/ui'
import { EVENT_CATEGORY_TOPIC, HelpFor, HelpTip, Term } from '../../help'
import { fmtDateTz, fmtNum, LEVELS, LOCALE, relTime, toneText } from '../../lib/format'
import { CATEGORY_LABEL, SEVERITY_COLOR, SEVERITY_LABEL, safeUrl } from '../../lib/geo'
import { useUrlFilters } from '../../lib/urlFilters'
import { HOME_NEAR, TZ } from './common'

const ICT_OFFSET = 7 * 3600000
/** Shift a UTC instant to ICT wall-clock, expressed as a UTC timestamp (for UTC-formatted chart axes). */
const ictMs = (ts: string) => new Date(ts).getTime() + ICT_OFFSET

// --------------------------------------------------------------------------- level history

export function HistoryCard() {
  const q = useLocalHistory()
  const data = useMemo(() => (q.data ?? []).filter((p) => p.evaluated_at).map((p) => ({ t: ictMs(p.evaluated_at), level: p.level, ts: p.evaluated_at }))
    .sort((a, b) => a.t - b.t), [q.data])
  const span = data.length ? data[data.length - 1].t - data[0].t : 0
  const tick = (t: number) => new Date(t).toLocaleString(LOCALE, span < 2 * 86400000
    ? { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: 'UTC' }
    : { day: 'numeric', month: 'short', timeZone: 'UTC' })
  return (
    <Card title="Level history" help={<HelpTip id="risk_levels" />} className="h-full"
      right={<span className="text-[11px] text-ink-3">{data.length} evaluations · times ICT</span>}
      footer={<AsOf ts={data.at(-1)?.ts} label="latest evaluation" tz={TZ} source="Koh Samui risk engine" href="/api/local/history" />}>
      {q.isLoading ? <Skeleton h={180} /> : !data.length ? <Empty what="No history yet" source="risk engine (/api/local/history)" /> : (
        <ChartFrame table={() => (
          <table className="w-full text-[12px] tnum"><tbody>
            {[...data].reverse().slice(0, 200).map((d) => <tr key={d.t} className="border-t border-line"><td className="py-0.5 pr-3 text-ink-2">{fmtDateTz(d.ts, TZ)}</td><td>{d.level ?? '--'} {LEVELS[d.level ?? -1]?.label ?? 'Unknown'}</td></tr>)}
          </tbody></table>
        )}>
          <div className="h-[210px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="t" type="number" scale="time" domain={['dataMin', 'dataMax']} tickLine={false} minTickGap={40} tickFormatter={tick} />
                <YAxis domain={[0, 4]} ticks={[0, 1, 2, 3, 4]} width={82} tickLine={false} axisLine={false}
                  tickFormatter={(v: number) => `${v} ${LEVELS[v]?.label ?? ''}`} />
                <Tooltip content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const d = payload[0].payload as { ts: string; level: number | null }
                  return <div className="rounded-md border border-line-strong bg-surface px-2.5 py-1.5 text-[12px]"><div className="font-semibold">{fmtDateTz(d.ts, TZ)}</div><LevelBadge level={d.level} /></div>
                }} />
                <Line dataKey="level" type="stepAfter" stroke="var(--s1)" strokeWidth={2} dot={data.length < 40 ? { r: 3 } : false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          {data.length < 10 && <p className="mt-1 text-[11px] text-ink-3">Short history: the engine stores one point per evaluation, so the line grows as the watch keeps running.</p>}
        </ChartFrame>
      )}
    </Card>
  )
}

// --------------------------------------------------------------------------- water

interface Win { obs_mm?: number; normal_mm?: number; pct?: number }
interface Obs { ts?: string; value?: number | null; unit?: string; source?: string; meta?: Record<string, unknown> }
interface WeatherDoc {
  rain_windows?: Record<string, Win | string> | null
  gauge?: Obs | null
  ratchaprapa?: Obs | null
  sources?: { name: string; provider?: string; url?: string; last_ok_at?: string }[]
}

const pctColor = (pct: number | undefined) => (pct === undefined ? undefined : pct < 60 ? 'var(--critical)' : pct < 75 ? 'var(--serious)' : undefined)

/** Label + value rows shown as a table from md, as stacked cards on phones. */
function ResponsiveTable({ head, rows }: { head: ReactNode[]; rows: { key: string; cells: ReactNode[] }[] }) {
  return (
    <>
      <table className="hidden w-full text-[12px] tnum md:table">
        <thead className="text-left text-ink-3">
          <tr>{head.map((h, i) => <th key={i} className={`py-1 pr-2 font-medium ${i ? 'text-right' : ''}`}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r) => <tr key={r.key} className="border-t border-line">{r.cells.map((c, i) => <td key={i} className={`py-1 pr-2 ${i ? 'text-right' : ''}`}>{c}</td>)}</tr>)}
        </tbody>
      </table>
      <ul className="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-2 md:hidden">
        {rows.map((r) => (
          <li key={r.key} className="rounded-lg bg-surface-2 p-2.5 text-[13px] tnum">
            <div className="mb-1 font-semibold">{r.cells[0]}</div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-[12px]">
              {r.cells.slice(1).map((c, i) => <div key={i} className="contents"><dt className="text-ink-3">{head[i + 1]}</dt><dd className="text-right">{c}</dd></div>)}
            </dl>
          </li>
        ))}
      </ul>
    </>
  )
}

export function WaterCard() {
  const w = useLocalWeather()
  const d = (w.data ?? null) as WeatherDoc | null
  const win = d?.rain_windows
  const rows = win ? (['d30', 'd60', 'd90', 'd180'] as const).map((k) => [k, win[k] as Win | undefined] as const).filter(([, v]) => v) : []
  const end = typeof win?.end === 'string' ? win.end : null
  return (
    <Card title="Water: rainfall totals vs normal" tour="samui-water" className="h-full"
      help={<><HelpTip id="rain_vs_normal" /><HelpTip id="era5" label="What is ERA5?" /></>}
      right={<KindBadge kind="reanalysis" compact />}
      footer={end
        ? <AsOf ts={end} label="through" source="Open-Meteo ERA5 vs 1991-2020 normal" href="https://open-meteo.com/en/docs/historical-weather-api" staleMs={10 * 86400000} />
        : <AsOf ts={null} source="Open-Meteo ERA5" href="https://open-meteo.com/en/docs/historical-weather-api" />}>
      {w.isLoading ? <Skeleton h={120} /> : !rows.length ? (
        <Empty what="Rainfall totals unavailable" source="Open-Meteo ERA5 (openmeteo_samui_era5)" />
      ) : (
        <>
          <ResponsiveTable head={['Window', 'Rain (ERA5)', 'Normal', '% of normal']} rows={rows.map(([k, v]) => ({
            key: k,
            cells: [
              `Last ${k.slice(1)} days`,
              `${fmtNum(v?.obs_mm ?? null, 0)} mm`,
              <span className="text-ink-2">{fmtNum(v?.normal_mm ?? null, 0)} mm</span>,
              <b style={{ color: pctColor(v?.pct) }}>{v?.pct === undefined ? '--' : `${v.pct < 75 ? '▲ ' : ''}${v.pct} %`}</b>,
            ],
          }))} />
          <p className="mt-2 text-[11px] leading-snug text-ink-3">
            Totals from the <Term id="era5">ERA5 reanalysis</Term> (a model blend of observations, about 5 days behind), compared with the
            1991-2020 <Term id="climatology_baseline">normal</Term> of the same dataset. Below 75 % is a warning sign, below 60 % serious.
          </p>
        </>
      )}
    </Card>
  )
}

export function WaterSupplyCard({ water }: { water?: RiskFactor }) {
  const w = useLocalWeather()
  const d = (w.data ?? null) as WeatherDoc | null
  const det = (water?.details ?? {}) as { seasonal_next3_pct?: number; pwa_notices_active?: unknown[]; pwa_fetched_at?: string; not_tracked?: string[]; context_url?: string }
  const dam = d?.ratchaprapa
  const dm = (dam?.meta ?? {}) as { usable_pct?: number; inflow_acc_pct_of_avg?: number; storage_mcm?: number }
  const stations = (d?.gauge?.meta?.stations as unknown[] | undefined)?.length
  const pwa = det.pwa_notices_active
  const tile = 'rounded-lg bg-surface-2 p-2.5'
  return (
    <Card title="Island water supply" help={<HelpTip id="samui_water_supply" />} className="h-full"
      footer={<AsOf ts={water?.as_of ?? water?.observed_at} label="water factor data" tz={TZ} source="PWA, ThaiWater, risk engine" href={safeUrl(det.context_url) ?? 'https://www.thaiwater.net/'} />}>
      {w.isLoading ? <Skeleton h={120} /> : !dam && !d?.gauge && !water ? <Empty what="Water supply data unavailable" source="ThaiWater + PWA notices" /> : (
        <div className="grid grid-cols-2 gap-2.5">
          {dam && (
            <div className={tile}>
              <div className="text-[11px] text-ink-3">Ratchaprapa dam, storage (Surat Thani)</div>
              <div className="text-lg font-semibold tnum">{fmtNum(dam.value ?? null, 1)} %</div>
              {dm.usable_pct !== undefined && <div className="text-[11px] text-ink-2 tnum">usable {fmtNum(dm.usable_pct, 1)} %{dm.inflow_acc_pct_of_avg !== undefined ? ` · inflow ${fmtNum(dm.inflow_acc_pct_of_avg, 0)} % of avg` : ''}</div>}
              <AsOf ts={dam.ts} tz={TZ} source="ThaiWater" href="https://www.thaiwater.net/" staleMs={3 * 86400000} kind="observed" />
            </div>
          )}
          {d?.gauge && (
            <div className={tile}>
              <div className="flex items-center gap-1 text-[11px] text-ink-3">Samui rain gauges, 24 h max <HelpTip id="rain_classes" label="How much rain is heavy?" /></div>
              <div className="text-lg font-semibold tnum">{fmtNum(d.gauge.value ?? null, 1)} mm</div>
              {stations ? <div className="text-[11px] text-ink-2">{stations} stations</div> : null}
              <AsOf ts={d.gauge.ts} tz={TZ} source="ThaiWater" href="https://www.thaiwater.net/" staleMs={6 * 3600000} kind="observed" />
            </div>
          )}
          {water && (
            <div className={tile}>
              <div className="text-[11px] text-ink-3">PWA Samui supply notices</div>
              <div className="text-lg font-semibold tnum">{Array.isArray(pwa) ? `${pwa.length} active` : '--'}</div>
              <AsOf ts={det.pwa_fetched_at} label="checked" tz={TZ} source="PWA" href="https://www.pwa.co.th/" kind="bulletin" />
            </div>
          )}
          {det.seasonal_next3_pct !== undefined && (
            <div className={tile}>
              <div className="text-[11px] text-ink-3">Rain next 3 months, % of model normal</div>
              <div className="text-lg font-semibold tnum">{fmtNum(det.seasonal_next3_pct, 0)} %</div>
              <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-ink-3">
                <KindBadge kind="forecast" compact help={false} /> <a className="link" href="https://open-meteo.com/en/docs/seasonal-forecast-api" target="_blank" rel="noreferrer">ECMWF SEAS5 ↗</a>
              </div>
            </div>
          )}
          {det.not_tracked?.length ? (
            <p className="col-span-2 text-[11px] text-ink-3"><b className="font-semibold text-ink-2">Not tracked</b> (no machine-readable source): {det.not_tracked.join(', ')}.</p>
          ) : null}
        </div>
      )}
    </Card>
  )
}

// --------------------------------------------------------------------------- TMD warnings

interface TmdItem { issue?: string; title?: string; description?: string; until?: string; active?: boolean; affects_samui?: boolean; heavy_rain?: boolean; strong_waves?: boolean; strong_waves_gulf?: boolean; small_boats_ashore?: boolean; storm?: boolean }

export function TmdWarningsCard() {
  const q = useStatus<{ url?: string; items?: TmdItem[]; fetched_at?: string }>('tmd_warnings')
  const items = (q.data?.value?.items ?? []).filter((i) => i.active !== false)
  const samui = items.filter((i) => i.affects_samui).length
  return (
    <Card title="TMD weather warnings" help={<><HelpTip id="tmd_warnings" /><HelpTip id="rain_classes" label="Heavy / very heavy rain: what amounts?" /></>} className="h-full"
      right={<><KindBadge kind="bulletin" compact /><span className="text-[11px] text-ink-3">{items.length} active · {samui} affect Samui</span></>}
      footer={q.data ? <AsOf ts={q.data.value?.fetched_at ?? q.data.updated_at} label="collected" tz={TZ} source="Thai Meteorological Department" href={safeUrl(q.data.value?.url) ?? 'https://www.tmd.go.th/'} staleMs={12 * 3600000} /> : undefined}>
      {q.isLoading ? <Skeleton h={80} /> : !q.data ? <Empty what="TMD warnings not collected" source="Thai Meteorological Department (tmd_warnings)" /> : !items.length ? (
        <p className="text-[13px] text-ink-2">No active warnings.</p>
      ) : (
        <ul className="-my-2 max-h-[320px] divide-y divide-line overflow-y-auto pr-1">
          {items.slice(0, 8).map((i) => (
            <li key={i.issue ?? i.title} className="py-2">
              <div className="mb-0.5 flex flex-wrap items-center gap-1.5 text-[11px]">
                {i.issue && <span className="chip font-mono">{i.issue}</span>}
                {i.affects_samui && <span className="chip" style={{ color: 'var(--warning)', borderColor: 'currentColor' }}>▲ affects Samui</span>}
                {i.heavy_rain && <span className="chip">heavy rain</span>}
                {(i.strong_waves || i.strong_waves_gulf) && <span className="chip">strong waves{i.strong_waves_gulf ? ' (Gulf)' : ''}</span>}
                {i.small_boats_ashore && <span className="chip" style={{ color: 'var(--critical)', borderColor: 'currentColor' }}>small boats ashore</span>}
                {i.storm && <span className="chip">storm</span>}
                {i.until && <span className="text-ink-3">valid until {fmtDateTz(i.until, TZ)}</span>}
              </div>
              <div className="line-clamp-2 text-[13px] font-medium" lang="th">{i.title}</div>
              {i.description && <p className="line-clamp-2 text-[12px] text-ink-2" lang="th">{i.description}</p>}
            </li>
          ))}
          {items.length > 8 && <li className="py-2 text-[12px] text-ink-3">+ {items.length - 8} older active bulletins (same warnings reissued) on the TMD site.</li>}
        </ul>
      )}
    </Card>
  )
}

// --------------------------------------------------------------------------- seasonal outlook

interface SeasonalMonth { month: string; precip_mean_mm?: number; precip_anomaly_mm?: number; precip_pct_of_model_normal?: number; temp_mean_c?: number; temp_anomaly_c?: number }

export function SeasonalCard() {
  const q = useStatus<{ model?: string; url?: string; months?: SeasonalMonth[] }>('samui_seasonal')
  const months = q.data?.value?.months ?? []
  return (
    <Card title="Seasonal outlook (6 months)" help={<HelpTip id="seasonal_outlook" />} className="h-full"
      right={<KindBadge kind="forecast" compact />}
      footer={q.data ? <AsOf ts={q.data.updated_at} label="collected" tz={TZ} source={q.data.value?.model ?? 'ECMWF SEAS5'} href={safeUrl(q.data.value?.url) ?? 'https://open-meteo.com/en/docs/seasonal-forecast-api'} staleMs={40 * 86400000} /> : undefined}>
      {q.isLoading ? <Skeleton h={80} /> : !months.length ? <Empty what="Seasonal forecast unavailable" source="ECMWF SEAS5 via Open-Meteo (openmeteo_samui_seasonal)" /> : (
        <>
          <ResponsiveTable head={['Month', 'Rain', '% of normal', 'Temp. anomaly']} rows={months.map((m) => {
            const pct = m.precip_pct_of_model_normal
            return {
              key: m.month,
              cells: [
                new Date(`${m.month}-15T00:00:00Z`).toLocaleDateString(LOCALE, { month: 'short', year: 'numeric', timeZone: 'UTC' }),
                `${fmtNum(m.precip_mean_mm ?? null, 0)} mm`,
                <b style={{ color: pct === undefined ? undefined : pct < 75 ? 'var(--serious)' : pct > 125 ? toneText('var(--cold)') : undefined }}>{pct === undefined ? '--' : `${fmtNum(pct, 0)} %`}</b>,
                m.temp_anomaly_c === undefined ? '--' : `${m.temp_anomaly_c > 0 ? '+' : ''}${fmtNum(m.temp_anomaly_c, 1)} °C`,
              ],
            }
          })} />
          <p className="mt-2 text-[11px] leading-snug text-ink-3">
            Ensemble-mean forecast of monthly totals; "% of normal" compares with the model's own climate, the
            temperature column is an <Term id="anomaly">anomaly</Term>. Monthly outlooks are uncertain beyond 2-3 months.
          </p>
        </>
      )}
    </Card>
  )
}

// --------------------------------------------------------------------------- events nearby

const RADII = [300, 800, 1500]

export function NearbyCard({ homeName }: { homeName: string }) {
  const f = useUrlFilters({ r: 'str', cat: 'list' }, 'ev_')
  const radius = RADII.includes(Number(f.values.r)) ? Number(f.values.r) : 800
  const base = { near: HOME_NEAR, radius_km: radius }
  const ev = useEventsQ({ ...base, category: f.api.cat, limit: 200 })
  const fac = useEventFacets(base)
  const cats = facet(fac.data, 'category')
  const total = typeof fac.data?.total === 'number' ? fac.data.total : null
  const rows = useMemo(() => [...(ev.data ?? [])].sort((a, b) => (a.distance_km ?? Infinity) - (b.distance_km ?? Infinity)), [ev.data])
  const newest = rows.map((e) => e.updated_at ?? e.started_at ?? '').sort().at(-1)
  return (
    <Card title={`Events within ${radius} km`} help={<HelpTip id="filters_events" label="Where do these events come from?" />} className="h-full"
      right={<span className="text-[11px] text-ink-3 tnum">{rows.length}{total !== null ? ` of ${total}` : ''}</span>}
      footer={<AsOf ts={newest || null} label="latest update" tz={TZ} source="GDACS, NASA EONET, FIRMS, Coral Reef Watch" href="/api/events" />}>
      <div className="mb-2 flex flex-wrap gap-x-4 gap-y-2">
        <FilterGroup label="Radius">
          <PresetSelect label="Radius" value={String(radius)} options={RADII.map((r) => ({ v: String(r), l: `${r} km` }))} onChange={(v) => f.set('r', v === '800' ? '' : v)} />
        </FilterGroup>
        {cats.length > 0 && (
          <FilterGroup label="Category">
            <ChipSelect selected={f.values.cat} onToggle={(v) => f.toggle('cat', v)} limit={6}
              options={cats.map((c) => ({
                value: c.value, label: CATEGORY_LABEL[c.value] ?? c.value, text: CATEGORY_LABEL[c.value] ?? c.value, count: c.count,
                help: <HelpFor id={EVENT_CATEGORY_TOPIC[c.value] ?? null} appId={c.value} title={CATEGORY_LABEL[c.value] ?? c.value} kind="category" />,
              }))} />
          </FilterGroup>
        )}
      </div>
      {ev.isLoading ? <Skeleton h={80} /> : ev.isError ? <p className="text-[13px] text-ink-3">Events unavailable.</p> : !rows.length ? (
        f.values.cat.length ? (
          <FilteredEmpty what="events" filters={f.values.cat.map((c) => `category: ${CATEGORY_LABEL[c] ?? c}`)} onReset={() => f.set('cat', [])} total={total} />
        ) : (
          <p className="text-[13px] text-ink-2">No geolocated event within {radius} km of {homeName} (GDACS, EONET, FIRMS, Coral Reef Watch). Try a wider radius.</p>
        )
      ) : (
        <ul className="-my-1 max-h-[320px] divide-y divide-line overflow-y-auto pr-1">
          {rows.slice(0, 60).map((e) => (
            <li key={`${e.source}:${e.ext_id}`} className="flex items-center gap-3 py-2 text-[13px]">
              <span className="chip shrink-0" style={{ color: toneText(SEVERITY_COLOR[e.severity ?? 'info'] ?? 'var(--ink-2)'), borderColor: 'currentColor' }}>
                {SEVERITY_LABEL[e.severity ?? 'info'] ?? e.severity}
              </span>
              <div className="min-w-0 flex-1">
                <Ext href={safeUrl(e.url)} className="line-clamp-1 font-medium">{e.title ?? '(untitled)'}</Ext>
                <div className="text-[11px] text-ink-3">{CATEGORY_LABEL[e.category] ?? e.category} · {e.source} · updated {relTime(e.updated_at ?? e.started_at)}</div>
              </div>
              <span className="text-[12px] whitespace-nowrap text-ink-2 tnum">{e.distance_km === null || e.distance_km === undefined ? '--' : `${fmtNum(e.distance_km, 0)} km`}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
