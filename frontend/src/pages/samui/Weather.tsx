/** Local weather charts: rain, max temperature, feels-like, PM2.5, US AQI, waves. Past vs forecast kept apart. */
import type { ReactNode } from 'react'
import { useLocalWeather, useSeries } from '../../api/client'
import { SLOTS, TimeChart, type ChartSeries } from '../../components/charts'
import { AsOf, Card, Empty, KindBadge, Skeleton } from '../../components/ui'
import { HelpTip } from '../../help'
import { isoDaysAgo } from '../../lib/format'
import { TZ } from './common'

interface Day { date: string; forecast?: boolean; [k: string]: number | string | boolean | undefined | null }
interface WeatherDoc { days?: Day[]; notes?: string[]; today?: string; sources?: { name: string; provider?: string; url?: string; last_ok_at?: string }[] }

type Pt = { ts: string; value: number | null }
const num = (v: unknown) => (typeof v === 'number' ? v : null)

/** One field of `days`, split into past (model analysis) and forecast points. */
function split(days: Day[], field: string): { past: Pt[]; fc: Pt[] } {
  const past: Pt[] = []
  const fc: Pt[] = []
  for (const d of days) {
    const v = num(d[field])
    if (v === null) continue
    ;(d.forecast ? fc : past).push({ ts: d.date, value: v })
  }
  // join the two lines at the boundary so the forecast starts where the past ends
  if (past.length && fc.length) fc.unshift(past[past.length - 1])
  return { past, fc }
}
const col = (days: Day[], field: string): Pt[] => days.filter((d) => num(d[field]) !== null).map((d) => ({ ts: d.date, value: num(d[field]) }))

/** Hourly UTC points -> ICT wall-clock (the chart axis prints UTC, so the shifted instant reads as ICT). */
const toIct = (pts: { ts: string; value: number | null }[]): Pt[] =>
  pts.map((p) => {
    const d = new Date(p.ts)
    if (Number.isNaN(d.getTime()) || p.ts.length <= 10) return p
    return { ts: new Date(d.getTime() + 7 * 3600000).toISOString().slice(0, 16), value: p.value }
  })

function WxCard({ title, help, kinds, children, footer, note }: { title: string; help: ReactNode; kinds: string[]; children: ReactNode; footer: ReactNode; note?: ReactNode }) {
  return (
    <Card title={title} help={help} className="h-full" footer={footer}
      right={<span className="flex flex-wrap gap-1">{kinds.map((k) => <KindBadge key={k} kind={k} compact help={false} />)}</span>}>
      {children}
      {note && <p className="mt-1 text-[11px] leading-snug text-ink-3">{note}</p>}
    </Card>
  )
}

export function WeatherCharts() {
  const w = useLocalWeather()
  const since = isoDaysAgo(7)
  const pm = useSeries('openmeteo_samui_air', 'samui_pm2_5', since)
  const aqi = useSeries('openmeteo_samui_air', 'samui_us_aqi', since)
  const wave = useSeries('openmeteo_marine', 'samui_wave_height', isoDaysAgo(14))
  const doc = (w.data ?? null) as WeatherDoc | null
  const days = doc?.days ?? []
  const src = (name: string) => doc?.sources?.find((s) => s.name === name)
  const fcSrc = src('openmeteo_samui')
  const era = src('openmeteo_samui_era5')
  const lastPast = [...days].reverse().find((d) => !d.forecast)?.date
  const lastFc = days.at(-1)?.date

  const daily = (field: string, era5: string | null, normal: string, labels: { past: string; fc: string }): ChartSeries[] => {
    const s = split(days, field)
    const out: ChartSeries[] = []
    if (era5) { const e = col(days, era5); if (e.length) out.push({ key: 'era5', label: 'ERA5 reanalysis', points: e, color: SLOTS[0] }) }
    if (s.past.length) out.push({ key: 'past', label: labels.past, points: s.past, color: SLOTS[1] })
    if (s.fc.length) out.push({ key: 'fc', label: labels.fc, points: s.fc, color: SLOTS[6], dashed: true })
    const n = col(days, normal)
    if (n.length) out.push({ key: 'normal', label: 'Normal 1991-2020', points: n, color: 'var(--ink-3)', dashed: true, width: 1.5 })
    return out
  }
  const lab = { past: 'Model analysis (past days)', fc: 'Forecast (16 d)' }
  const rain = daily('precip', 'era5_precip', 'normal_precip', lab)
  const tmax = daily('temp_max', 'era5_temp_max', 'normal_temp_max', lab)
  const feels = daily('apparent_temp_max', 'era5_apparent_temp_max', 'normal_apparent_temp_max', lab)

  const fcFooter = <AsOf ts={fcSrc?.last_ok_at} label="fetched" tz={TZ} source={fcSrc?.provider ?? 'Open-Meteo'} href={fcSrc?.url ?? 'https://open-meteo.com/en/docs'} staleMs={12 * 3600000} />
  const dailyNote = <>Solid = ERA5 reanalysis (to {lastPast ? lastPast : '--'}, about 5 days behind) and the model analysis of past days; dashed after the "today" line = forecast to {lastFc ?? '--'}; grey dashed = the 1991-2020 normal. Daily values, dates in ICT.</>

  if (w.isLoading) return <Skeleton h={260} />
  if (!days.length && !pm.data?.points?.length) return <Empty what="Local weather unavailable" source="Open-Meteo (openmeteo_samui, openmeteo_samui_era5, openmeteo_samui_air, openmeteo_marine)" />

  const pmPts = toIct(pm.data?.points ?? [])
  const aqiPts = toIct(aqi.data?.points ?? [])
  const wavePts = (wave.data?.points ?? []).map((p) => ({ ts: p.ts, value: p.value }))
  const nowIso = new Date(Date.now() + 7 * 3600000).toISOString().slice(0, 16)
  const splitNow = (pts: Pt[]) => {
    const past = pts.filter((p) => p.ts <= nowIso)
    const fc = pts.filter((p) => p.ts > nowIso)
    if (past.length && fc.length) fc.unshift(past[past.length - 1])
    return { past, fc }
  }
  const pmS = splitNow(pmPts)
  const aqiS = splitNow(aqiPts)
  const today = isoDaysAgo(0)
  const waveS = { past: wavePts.filter((p) => p.ts.slice(0, 10) <= today), fc: wavePts.filter((p) => p.ts.slice(0, 10) > today) }
  if (waveS.past.length && waveS.fc.length) waveS.fc.unshift(waveS.past[waveS.past.length - 1])
  const two = (s: { past: Pt[]; fc: Pt[] }, lp: string): ChartSeries[] => [
    ...(s.past.length ? [{ key: 'past', label: lp, points: s.past, color: SLOTS[1] }] : []),
    ...(s.fc.length ? [{ key: 'fc', label: 'Forecast', points: s.fc, color: SLOTS[6], dashed: true }] : []),
  ]
  const unavailable = <p className="text-[13px] text-ink-3">Series unavailable.</p>
  const H = 220

  return (
    <div className="space-y-2">
      {doc?.notes?.length ? <ul className="list-disc pl-5 text-[12px] text-ink-3">{doc.notes.map((n, i) => <li key={i}>{n}</li>)}</ul> : null}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <WxCard title="Daily rain vs normal" help={<><HelpTip id="rain_vs_normal" /><HelpTip id="rain_classes" label="What counts as heavy rain?" /></>}
          kinds={['reanalysis', 'model_analysis', 'forecast']} footer={fcFooter} note={dailyNote}>
          {rain.length ? <TimeChart series={rain} unit="mm/day" height={H} curve="linear" nowLine refLines={[{ y: 35.1, label: 'TMD heavy: 35.1' }]} /> : unavailable}
        </WxCard>
        <WxCard title="Max temperature vs normal" help={<><HelpTip id="climatology_baseline" /><HelpTip id="era5" label="What is ERA5?" /></>}
          kinds={['reanalysis', 'model_analysis', 'forecast']} footer={<AsOf ts={era?.last_ok_at ?? fcSrc?.last_ok_at} label="fetched" tz={TZ} source="Open-Meteo + ERA5" href={era?.url ?? 'https://open-meteo.com/en/docs/historical-weather-api'} staleMs={12 * 3600000} />}
          note={dailyNote}>
          {tmax.length ? <TimeChart series={tmax} unit="C" height={H} curve="linear" nowLine /> : unavailable}
        </WxCard>
        <WxCard title="Feels-like max (heat index)" help={<HelpTip id="heat_index" />}
          kinds={['model_analysis', 'forecast']} footer={fcFooter}
          note={<>Feels-like combines temperature and humidity. 39 °C = watch, 41 °C = danger (heatstroke possible) in the risk engine.</>}>
          {feels.length ? <TimeChart series={feels} unit="C" height={H} curve="linear" nowLine refLines={[{ y: 39, label: 'watch 39', color: 'var(--warning)' }, { y: 41, label: 'danger 41', color: 'var(--critical)' }]} /> : unavailable}
        </WxCard>
        <WxCard title="Air quality: PM2.5" help={<><HelpTip id="pm25" /><HelpTip id="cams" label="Where does this come from (CAMS)?" /></>}
          kinds={['model_analysis', 'forecast']}
          footer={<AsOf ts={pm.data?.points?.filter((p) => p.ts <= new Date().toISOString()).at(-1)?.ts} label="latest analysed hour" tz={TZ} source="Copernicus CAMS via Open-Meteo" href="https://open-meteo.com/en/docs/air-quality-api" staleMs={12 * 3600000} />}
          note={<>Hourly, times in ICT. Modelled (CAMS), not a station: compare with Air4Thai. WHO 24 h guideline 15, Thai PCD standard 37.5 µg/m³ (24 h mean).</>}>
          {pm.isLoading ? <Skeleton h={H} /> : pmPts.length ? <TimeChart series={two(pmS, 'Model analysis')} unit="µg/m³" height={H} curve="linear" refLines={[{ y: 15, label: 'WHO 24 h: 15' }, { y: 37.5, label: 'PCD: 37.5', color: 'var(--warning)' }]} /> : unavailable}
        </WxCard>
        <WxCard title="Air quality index (US AQI)" help={<HelpTip id="aqi" />}
          kinds={['model_analysis', 'forecast']}
          footer={<AsOf ts={aqi.data?.points?.filter((p) => p.ts <= new Date().toISOString()).at(-1)?.ts} label="latest analysed hour" tz={TZ} source="Copernicus CAMS via Open-Meteo" href="https://open-meteo.com/en/docs/air-quality-api" staleMs={12 * 3600000} />}
          note={<>Hourly, times in ICT. 0-50 good, 51-100 moderate, above 100 unhealthy for sensitive groups.</>}>
          {aqi.isLoading ? <Skeleton h={H} /> : aqiPts.length ? <TimeChart series={two(aqiS, 'Model analysis')} unit="US AQI" height={H} curve="linear" refLines={[{ y: 50, label: 'good / moderate: 50' }, { y: 100, label: 'unhealthy (sensitive): 100', color: 'var(--warning)' }]} /> : unavailable}
        </WxCard>
        <WxCard title="Wave height off Samui" help={<><HelpTip id="wave_height" /><HelpTip id="departure_windows" label="What wave height stops the ferries?" /></>}
          kinds={['model_analysis', 'forecast']}
          footer={<AsOf ts={wave.data?.points?.at(-1)?.ts} label="forecast to" tz={TZ} source="Open-Meteo Marine" href="https://open-meteo.com/en/docs/marine-weather-api" />}
          note={<>Daily max significant wave height (model, open water east of Samui). 1.5 m = watch, 2 m = small boats stay in port, 3 m = act.</>}>
          {wave.isLoading ? <Skeleton h={H} /> : wavePts.length ? <TimeChart series={two(waveS, 'Model analysis')} unit="m" height={H} curve="linear" nowLine yDomain={[0, 'auto']} refLines={[{ y: 1.5, label: 'watch 1.5 m', color: 'var(--warning)' }, { y: 2, label: 'boats in port 2 m', color: 'var(--critical)' }]} /> : unavailable}
        </WxCard>
      </div>
    </div>
  )
}
