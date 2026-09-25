/** "Leave the island" view: recommendation, departure windows, signals, routes and a checklist. */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useLocalExit } from '../../api/client'
import type { ExitRoute, ExitSignal } from '../../api/types'
import { AsOf, Card, ErrorBox, KindBadge, Skeleton } from '../../components/ui'
import { EXIT_SIGNAL_TOPIC, HelpFor, HelpTip, ROUTE_TOPIC } from '../../help'
import { fmtDateTz, fmtUnit, LOCALE } from '../../lib/format'
import { safeUrl } from '../../lib/geo'
import { fmtVal, TZ, unitOf, UnknownKind, valueKind } from './common'

const SIGNAL: Record<string, { label: string; color: string; icon: string }> = {
  ok: { label: 'OK', color: 'var(--good)', icon: '●' },
  caution: { label: 'Caution', color: 'var(--warning)', icon: '▲' },
  blocked: { label: 'Blocked', color: 'var(--critical)', icon: '■' },
  unknown: { label: 'Unknown', color: 'var(--ink-3)', icon: '?' },
}

function SignalCard({ s }: { s: ExitSignal }) {
  const m = SIGNAL[s.status] ?? SIGNAL.unknown
  const kind = valueKind(s)
  const unit = unitOf(s)
  // round 3: forecasts have observed_at null; as_of = observed_at or issued_at or retrieved_at
  const when = s.as_of ?? s.observed_at ?? s.retrieved_at ?? null
  const asOfLabel = s.observed_at ? 'data time' : s.issued_at ? 'issued' : 'fetched'
  const hasVal = !(s.value === null || s.value === undefined || s.value === '')
  return (
    <article className="card flex h-full min-w-0 flex-col p-3" style={{ borderLeft: `4px solid ${m.color}` }}>
      <div className="flex items-start justify-between gap-2">
        <h4 className="flex min-w-0 items-center gap-1.5 text-[13px] font-semibold">
          <span className="min-w-0">{s.label}</span>
          <HelpFor id={EXIT_SIGNAL_TOPIC[s.id] ?? null} appId={s.id} title={s.label} text={s.reason ?? s.threshold} href={s.url} kind="signal" />
        </h4>
        <span className="chip shrink-0" style={{ color: m.color, borderColor: m.color, borderStyle: s.status === 'unknown' ? 'dashed' : undefined }}>{m.icon} {m.label}</span>
      </div>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-1.5">
        {hasVal ? (
          <>
            <span className="text-[18px] font-semibold tnum break-words">{fmtVal(s.value)}</span>
            {unit && <span className="text-[12px] text-ink-3">{unit}</span>}
          </>
        ) : !s.reason ? <span className="text-[13px] text-ink-3">no value</span> : null}
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-1.5">
        {kind ? <KindBadge kind={kind} ts={when} validFor={s.valid_for ?? (kind === 'forecast' ? when : null)} tz={TZ} /> : <UnknownKind />}
      </div>
      {s.reason && <p className="mt-1 text-[12px] leading-snug text-ink-2">{fmtUnit(s.reason)}</p>}
      {s.threshold && <p className="mt-0.5 text-[11px] text-ink-3">Thresholds: {fmtUnit(s.threshold)}</p>}
      <div className="mt-auto border-t border-line pt-1.5">
        <AsOf className="mt-1.5" ts={when} label={asOfLabel} tz={TZ} source={s.source} href={safeUrl(s.url)} staleMs={kind === 'forecast' || !s.observed_at ? undefined : 24 * 3600000} />
      </div>
    </article>
  )
}

function ModeIcon({ mode }: { mode: string }) {
  const d = mode === 'air' ? 'M2 16l20-6-3-2-7 2-5-6H5l3 7-4 1-2-2H1l1 6z'
    : mode === 'rail' ? 'M7 3h10a2 2 0 0 1 2 2v9a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3V5a2 2 0 0 1 2-2zM5 10h14M9 14h.01M15 14h.01M8 17l-2 4M16 17l2 4'
    : mode === 'ferry' ? 'M3 17l2 3h14l2-3M5 17V11h14v6M8 11V7h8v4M12 3v4M2 21c2 0 2-1 4-1s2 1 4 1 2-1 4-1 2 1 4 1 2-1 4-1'
    : 'M5 16V11l2-5h10l2 5v5M5 16h14M5 16v2M19 16v2M7 13h1M16 13h1'
  const label = MODE_LABEL[mode] ?? mode
  return (
    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-surface-2 text-ink-2" title={label}>
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" role="img" aria-label={label}><path d={d} /></svg>
    </span>
  )
}
const MODE_LABEL: Record<string, string> = { air: 'Flight', ferry: 'Ferry', road: 'Road', rail: 'Train' }

function RouteRow({ r }: { r: ExitRoute }) {
  const u = safeUrl(r.url)
  return (
    <li className="flex gap-3 py-2.5">
      <ModeIcon mode={r.mode} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2">
          <span className="text-[13px] font-semibold">{r.operator ?? 'Operator unknown'}</span>
          <span className="text-[11px] tracking-wide text-ink-3 uppercase">{MODE_LABEL[r.mode] ?? r.mode}</span>
          <HelpFor id={ROUTE_TOPIC[r.mode] ?? null} appId={r.mode} title={MODE_LABEL[r.mode] ?? r.mode} text={r.notes} kind="route" />
        </div>
        <div className="text-[13px] text-ink-2">{r.from ?? '?'} <span aria-label="to">→</span> {r.to ?? '?'}</div>
        {r.notes && <p className="mt-0.5 text-[12px] text-ink-3">{r.notes}</p>}
      </div>
      {u && <a className="link inline-flex min-h-10 shrink-0 items-start text-[12px] sm:min-h-0" href={u} target="_blank" rel="noreferrer">Website ↗</a>}
    </li>
  )
}

const PRIO_EXIT: Record<string, { label: string; color: string }> = {
  must: { label: 'Essential', color: 'var(--critical)' },
  high: { label: 'Essential', color: 'var(--critical)' },
  should: { label: 'Recommended', color: 'var(--serious)' },
  medium: { label: 'Recommended', color: 'var(--serious)' },
  nice: { label: 'Useful', color: 'var(--ink-3)' },
  low: { label: 'Useful', color: 'var(--ink-3)' },
}
const LS_EXIT = 'exit-checklist'

function useStoredChecks(key: string) {
  const [v, setV] = useState<Record<string, boolean>>(() => {
    try { return JSON.parse(localStorage.getItem(key) ?? '{}') ?? {} } catch { return {} }
  })
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(v)) } catch { /* storage blocked */ } }, [key, v])
  return [v, setV] as const
}

const WIN: Record<string, { label: string; color: string }> = {
  ok: { label: '● Go', color: 'var(--good)' },
  caution: { label: '▲ Caution', color: 'var(--warning)' },
  blocked: { label: '■ No-go', color: 'var(--critical)' },
  unknown: { label: '? Unknown', color: 'var(--ink-3)' },
}

const WD = new Intl.DateTimeFormat(LOCALE, { weekday: 'short', timeZone: 'UTC' })
const DM = new Intl.DateTimeFormat(LOCALE, { day: 'numeric', month: 'short', timeZone: 'UTC' })

export function ExitPlanView() {
  const q = useLocalExit()
  const [checks, setChecks] = useStoredChecks(LS_EXIT)
  const e = q.data
  if (q.isLoading) return <div className="space-y-3"><Skeleton h={90} /><Skeleton h={160} /></div>
  if (q.isError) return <ErrorBox error={q.error} what="exit plan" />
  if (!e) {
    return (
      <div className="rounded-lg border border-dashed border-line-strong p-4 text-[13px] text-ink-2">
        <p className="font-medium text-ink">Exit plan not available yet</p>
        <p className="mt-1">The API does not serve <code>/api/local/exit</code> yet. Meanwhile, the departure items are in the <Link className="link" to="/prep">Preparedness</Link> checklist.</p>
      </div>
    )
  }
  const signals = e.signals ?? []
  const windows = (e.windows ?? []).slice(0, 7)
  const routes = e.routes ?? []
  const list = e.checklist ?? []
  const done = list.filter((c) => checks[c.id]).length
  const blocked = signals.filter((x) => x.status === 'blocked').length
  const caution = signals.filter((x) => x.status === 'caution').length
  const ts = e.generated_at ?? e.evaluated_at ?? null
  return (
    <div className="space-y-4">
      <section className="card p-4" style={{ borderLeft: `4px solid ${blocked ? 'var(--critical)' : caution ? 'var(--warning)' : 'var(--good)'}` }} aria-labelledby="exit-rec">
        <h2 id="exit-rec" className="flex items-center gap-1.5 text-[12px] font-semibold tracking-wide text-ink-3 uppercase">Recommendation <HelpTip id="exit_plan" /></h2>
        <p className="mt-1 text-[16px] leading-snug font-semibold sm:text-[18px]">{e.recommendation ? fmtUnit(e.recommendation) : 'No recommendation returned.'}</p>
        <p className="mt-1.5 text-[12px] text-ink-3">
          {signals.length} signals: {(['ok', 'caution', 'blocked', 'unknown'] as const).map((k) => `${signals.filter((x) => (SIGNAL[x.status] ? x.status : 'unknown') === k).length} ${SIGNAL[k].label.toLowerCase()}`).join(' · ')}
        </p>
        <AsOf className="mt-1" ts={ts} label="evaluated" tz={TZ} source="Koh Samui exit plan engine" href="/api/local/exit" staleMs={6 * 3600000} />
        {e.notes?.length ? (
          <ul className="mt-2 space-y-0.5 text-[12px] text-ink-2">
            {e.notes.map((n, i) => <li key={i} className="flex gap-1.5"><span className="text-ink-3" aria-hidden>i</span><span>{n}</span></li>)}
          </ul>
        ) : null}
      </section>

      <Card title="Departure windows by ferry, next 7 days" help={<><HelpTip id="departure_windows" /><HelpTip id="exit_windows" label="How are the windows computed?" /></>}
        right={<KindBadge kind="forecast" compact />}
        footer={<AsOf ts={ts} label="computed" tz={TZ} source="Open-Meteo Marine + Open-Meteo forecast" href="https://open-meteo.com/en/docs/marine-weather-api" />}>
        {!windows.length ? <p className="text-[13px] text-ink-3">No sea / wind forecast windows returned.</p> : (
          <ol className="grid gap-2 sm:grid-cols-[repeat(auto-fit,minmax(120px,1fr))]">
            {windows.map((w) => {
              const st = w.status && WIN[w.status] ? w.status : w.ok ? 'ok' : 'blocked'
              const c = WIN[st].color
              const d = new Date(`${w.date.slice(0, 10)}T00:00:00Z`)
              return (
                <li key={w.date} title={w.reason ?? undefined} className="flex items-center gap-3 rounded-lg border border-line p-2.5 sm:flex-col sm:items-stretch sm:gap-1 sm:text-center"
                  style={{ borderTop: `3px solid ${c}` }}>
                  <div className="w-16 shrink-0 sm:w-auto">
                    <div className="text-[11px] font-semibold text-ink-3 uppercase">{Number.isNaN(d.getTime()) ? '' : WD.format(d)}</div>
                    <div className="text-[13px] font-semibold tnum">{Number.isNaN(d.getTime()) ? (w.label ?? w.date) : DM.format(d)}</div>
                  </div>
                  <div className="w-20 shrink-0 text-[13px] font-semibold sm:w-auto" style={{ color: c }}>{WIN[st].label}</div>
                  <div className="min-w-0 flex-1 text-[11px] leading-snug text-ink-2">
                    {(w.wave_max_m !== undefined && w.wave_max_m !== null) || (w.gust_max_kmh !== undefined && w.gust_max_kmh !== null) ? (
                      <div className="tnum">{w.wave_max_m != null ? `waves ${fmtVal(w.wave_max_m)} m` : ''}{w.wave_max_m != null && w.gust_max_kmh != null ? ' · ' : ''}{w.gust_max_kmh != null ? `gusts ${fmtVal(Math.round(w.gust_max_kmh))} km/h` : ''}</div>
                    ) : null}
                    {w.reason && (st !== 'ok' || w.wave_max_m == null) ? <div title={w.reason}>{fmtUnit(w.reason)}</div> : null}
                  </div>
                </li>
              )
            })}
          </ol>
        )}
        <p className="mt-2 text-[11px] text-ink-3">Go = forecast waves and gusts within normal ferry limits; Caution = possible, expect delays or cancellations; No-go = crossings likely suspended. Dates in ICT. Always confirm with the operator the same day.</p>
      </Card>

      <section aria-labelledby="exit-sig">
        <h3 id="exit-sig" className="mb-2 flex items-center gap-1.5 text-[15px] font-semibold">Signals ({signals.length}) <HelpTip id="exit_plan" label="How do the signals feed the recommendation?" /></h3>
        {!signals.length ? <p className="text-[13px] text-ink-3">No signals returned.</p> : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,280px),1fr))] gap-3">{signals.map((x) => <SignalCard key={x.id} s={x} />)}</div>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Routes off the island" help={<HelpTip id="exit_route_ferry" label="How to leave Samui" />} className="h-full"
          right={<span className="text-[11px] text-ink-3">{routes.length} routes</span>}
          footer={<AsOf ts={e.verified_at ?? null} label="links checked" source="operator websites" />}>
          {!routes.length ? <p className="text-[13px] text-ink-3">No routes returned.</p> : (
            <ul className="-my-2.5 divide-y divide-line">{routes.map((r, i) => <RouteRow key={`${r.id}-${i}`} r={r} />)}</ul>
          )}
        </Card>
        <Card title="Departure checklist" help={<HelpTip id="prep_exit" />} className="h-full"
          right={<span className="text-[12px] text-ink-3 tnum">{done} / {list.length}</span>}
          footer={<span className="text-[11px] text-ink-3">Ticks are kept in this browser only. Full list on the <Link className="link" to="/prep">Preparedness</Link> page.</span>}>
          {!list.length ? <p className="text-[13px] text-ink-3">No checklist returned.</p> : (
            <>
              <div className="mb-2 h-1.5 overflow-hidden rounded-full bg-surface-3" aria-hidden>
                <div className="h-full rounded-full" style={{ width: `${(done / list.length) * 100}%`, background: 'var(--s1)' }} />
              </div>
              <ul className="divide-y divide-line">
                {list.map((c) => {
                  const pr = PRIO_EXIT[c.priority] ?? PRIO_EXIT.nice
                  return (
                    <li key={c.id}>
                      <label className="flex min-h-10 cursor-pointer items-center gap-2.5 py-1.5">
                        <input type="checkbox" className="h-4 w-4 shrink-0 accent-[var(--accent)]" checked={!!checks[c.id]}
                          onChange={(ev) => setChecks((m) => ({ ...m, [c.id]: ev.target.checked }))} />
                        <span className={`min-w-0 flex-1 text-[13px] ${checks[c.id] ? 'text-ink-3 line-through' : ''}`}>{c.label}</span>
                        <span className="chip shrink-0" style={{ color: pr.color, borderColor: pr.color }}>{pr.label}</span>
                      </label>
                    </li>
                  )
                })}
              </ul>
            </>
          )}
        </Card>
      </div>
      <p className="text-[11px] text-ink-3">Times in ICT (Asia/Bangkok). Today: {fmtDateTz(new Date().toISOString(), TZ)}.</p>
    </div>
  )
}
