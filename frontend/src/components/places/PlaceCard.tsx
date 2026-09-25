import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AsOf, Card, KindBadge, LevelBadge } from '../ui'
import { fmtDate, fmtUnit, levelMeta, relTime } from '../../lib/format'
import { FACTOR_TOPIC_PLACES, type PlaceDetail, type PlaceFactor } from './api'
import { LevelDot, PlaceTip, fmt } from './common'

function localTime(tz: string | undefined): string {
  try {
    return new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: tz }).format(new Date())
  } catch { return '--' }
}

function Factor({ f }: { f: PlaceFactor }) {
  const [open, setOpen] = useState(false)
  const m = levelMeta(f.level, f.level_key)
  const value = typeof f.value === 'number' ? fmt(f.value, Number.isInteger(f.value) ? 0 : 1) : (f.value ?? '--')
  return (
    <li className="border-t border-line py-1.5 first:border-t-0">
      <div className="flex items-center gap-2">
        <button type="button" className="flex min-w-0 flex-1 items-center gap-2 text-left" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          <LevelDot level={f.level} levelKey={f.level_key} />
          <span className="min-w-0 flex-1 truncate text-[12.5px] text-ink">{f.label}</span>
          <span className="tnum text-[12px] text-ink-2">{f.level === null && !f.value ? 'no data' : `${value}${(f.unit_label ?? f.unit) ? ` ${fmtUnit(f.unit_label ?? f.unit)}` : ''}`}</span>
          <span className="w-16 text-right text-[11px] font-semibold" style={{ color: m?.color ?? 'var(--ink-3)' }}>{m ? m.label : 'Unknown'}</span>
        </button>
        <PlaceTip id={FACTOR_TOPIC_PLACES[f.id] ?? 'place_levels'} />
      </div>
      {open && (
        <div className="mt-1.5 space-y-1 pl-4.5 text-[12px] text-ink-2">
          <p>{fmtUnit(f.explanation)}</p>
          {f.threshold && <p className="text-ink-3">Thresholds: {fmtUnit(f.threshold)}</p>}
          <AsOf ts={f.as_of ?? f.observed_at ?? f.retrieved_at} validFor={f.valid_for} source={f.source} href={f.url} kind={f.kind} stale={f.stale}
            label={f.observed_at ? 'as of' : f.kind === 'forecast' ? 'fetched' : 'as of'} />
        </div>
      )}
    </li>
  )
}

export function PlaceCard({ p }: { p: PlaceDetail }) {
  const c = p.current
  const floor = p.level === null ? { level: p.level_floor, key: p.level_floor_key } : null
  return (
    <Card
      title={<span className="normal-case tracking-normal text-ink">{p.name}{p.role === 'home' && <span className="chip ml-2 !text-[10px]">home</span>}</span>}
      help={<PlaceTip id="place_levels" />}
      footer={<AsOf ts={p.evaluated_at} source="Places engine" label="evaluated" />}
    >
      <p className="-mt-1 mb-2 text-[11.5px] text-ink-3">
        {p.admin} · {p.lat.toFixed(4)}, {p.lon.toFixed(4)} · {fmt(p.elevation_m ?? null, 0)} m · local time {localTime(p.timezone)}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <LevelBadge level={p.level} levelKey={p.level_key} size="lg" floor={floor} />
      </div>
      <p className="mt-1.5 text-[13px] text-ink-2">{p.headline}</p>
      {p.samui_watch && (
        <p className="mt-1 text-[12px] text-ink-2">
          Detailed <Link className="link" to="/samui">Koh Samui watch</Link>: <LevelBadge level={p.samui_watch.level} levelKey={p.samui_watch.level_key} />{' '}
          <span className="text-ink-3">({relTime(p.samui_watch.evaluated_at)})</span>
        </p>
      )}

      <div className="mt-3 rounded-lg border border-line bg-surface-2 p-3">
        <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">Now <PlaceTip id="place_current" /></span>
          {c && <KindBadge kind={c.kind} compact help={false} />}
        </div>
        {c ? (
          <>
            <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
              <span className="tnum text-2xl font-semibold">{fmt(c.temperature_2m, 1)} °C</span>
              <span className="text-[13px] text-ink-2">feels like <b className="tnum text-ink">{fmt(c.apparent_temperature, 1)} °C</b></span>
              <span className="text-[13px] text-ink-2">{c.weather ?? ''}</span>
            </div>
            <dl className="mt-1.5 grid grid-cols-3 gap-2 text-[12px]">
              <div><dt className="text-ink-3">Humidity</dt><dd className="tnum">{fmt(c.relative_humidity_2m, 0)} %</dd></div>
              <div><dt className="text-ink-3">Wind / gusts</dt><dd className="tnum">{fmt(c.wind_speed_10m, 0)} / {fmt(c.wind_gusts_10m, 0)} km/h</dd></div>
              <div><dt className="text-ink-3">Rain (1 h)</dt><dd className="tnum">{fmt(c.precipitation, 1)} mm</dd></div>
            </dl>
            <AsOf className="mt-1.5" ts={c.time} source={c.source} href={c.url} staleMs={6 * 3600_000} />
          </>
        ) : <p className="text-[12px] text-ink-3">No current data yet (collector places_forecast).</p>}
      </div>

      <div className="mt-3">
        <div className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">Factors (tap for details) <PlaceTip id="place_levels" /></div>
        <ul>{(p.factors ?? []).map((f) => <Factor key={f.id} f={f} />)}</ul>
        {p.missing_critical.length > 0 && (
          <p className="mt-1 text-[11.5px]" style={{ color: 'var(--warning)' }}>
            Missing critical data: {p.missing_critical.join(', ')}. The level stays Unknown until it arrives.
          </p>
        )}
        {p.rules.length > 0 && <p className="mt-1 text-[11px] text-ink-3">{p.rules.join(' · ')}</p>}
      </div>

      {p.geocode && (
        <p className="mt-2 text-[11px] text-ink-3">
          Geocode: {p.geocode.url ? <a className="link" href={p.geocode.url} target="_blank" rel="noreferrer">{p.geocode.source} ↗</a> : p.geocode.source}, checked {fmtDate(p.geocode.checked)}.{p.geocode.note ? ` ${p.geocode.note}` : ''}
        </p>
      )}
    </Card>
  )
}
