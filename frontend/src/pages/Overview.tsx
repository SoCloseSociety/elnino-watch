import { Suspense, lazy, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useAlertsQ, useBriefing, useEventFacets, useEventsQ, useFeed, useLatest, useLocal, useSources, useStatus } from '../api/client'
import type { CpcAlert, EventItem, IriPlume, LatestPoint, TaoBuoy } from '../api/types'
import { AnalogsCard } from '../components/AnalogsCard'
import { CategoryLines, Sparkline } from '../components/charts'
import FeedRow from '../components/FeedRow'
import { ChipSelect, FilterGroup, FilteredEmpty, PresetSelect } from '../components/filters'
import { AsOf, Card, Empty, ErrorBox, Ext, KindBadge, LevelBadge, Skeleton } from '../components/ui'
import { HelpFor, HelpTip, InfoTip, PageGuide, Term, type TopicId } from '../help'
import { ageMs, fmtDate, fmtNum, fmtSigned, fmtUnit, HOME, isoDaysAgo, levelMeta, relTime, riskFloor, strength, toneText } from '../lib/format'
import { safeUrl } from '../lib/geo'
import { seasonLabel, useNamedSeries } from '../lib/hooks'
import { buoysFrom } from '../lib/normalize'
import { findLatest, sourceLink, staleAfterMs, unitLabel } from '../lib/series'
import { sinceFromPreset, useUrlFilters } from '../lib/urlFilters'

// maplibre (~1 MB) is only fetched when the mini map scrolls into view
const WorldMap = lazy(() => import('../components/WorldMap'))

const MONTHLY_STALE = 75 * 86400000

function useInView<T extends Element>(margin = '0px 0px 80px 0px') {
  const ref = useRef<T>(null)
  const [seen, setSeen] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || seen) return
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) setSeen(true) }, { rootMargin: margin })
    io.observe(el)
    return () => io.disconnect()
  }, [seen, margin])
  return [ref, seen] as const
}

/**
 * True once the browser is idle after load AND the person has interacted with the page
 * (scroll, pointer, key, touch). Heavy optional chunks (the maplibre mini map) then stay
 * off the initial load; a "Show the map" button in the placeholder is the explicit way in.
 */
function useIdleAfterInteraction() {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    if (ready) return
    let idle = false
    let interacted = false
    const w = window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number }
    const check = () => { if (idle && interacted) setReady(true) }
    const onAct = () => { interacted = true; check() }
    const onIdle = () => { idle = true; check() }
    const start = () => (w.requestIdleCallback ? w.requestIdleCallback(onIdle, { timeout: 4000 }) : window.setTimeout(onIdle, 1500))
    if (document.readyState === 'complete') start()
    else window.addEventListener('load', start, { once: true })
    const evs: (keyof WindowEventMap)[] = ['scroll', 'pointermove', 'pointerdown', 'keydown', 'touchstart', 'wheel']
    for (const e of evs) window.addEventListener(e, onAct, { passive: true, capture: true })
    return () => { for (const e of evs) window.removeEventListener(e, onAct, { capture: true }) }
  }, [ready])
  return [ready, () => setReady(true)] as const
}

function useMedia(q: string) {
  const [m, setM] = useState(() => typeof window !== 'undefined' && !!window.matchMedia?.(q).matches)
  useEffect(() => {
    const mq = window.matchMedia?.(q)
    if (!mq) return
    const on = () => setM(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [q])
  return m
}

/** Briefing section id -> the topic that explains what that section summarises. */
const BRIEF_SECTION_TOPIC: Record<string, TopicId> = {
  enso: 'enso',
  forecast: 'forecast_uncertainty',
  local: 'risk_levels',
  hazards: 'gdacs',
  official: 'cpc_alert_system',
  gaps: 'data_coverage',
}

/** Collapsed height of the briefing card (skeleton = card, so loading it never shifts the page). */
const BRIEF_H = 'h-[300px] sm:h-[260px]'

function BriefingCard() {
  const q = useBriefing()
  const b = q.data
  const sections = (b?.sections ?? []).filter((x) => x && (x.bullets?.length || x.title))
  const llm = b?.method === 'llm'
  const age = ageMs(b?.generated_at)
  const stale = age !== null && age > 12 * 3600000 // regenerated every 6 h
  const [open, setOpen] = useState(false)
  if (q.isLoading) return <div className={`skeleton ${BRIEF_H}`} aria-hidden />
  if (q.isError) return <ErrorBox error={q.error} what="briefing" />
  if (!b) {
    return (
      <section data-tour="overview-briefing" className={`card flex flex-wrap items-center gap-2 px-4 py-2.5 text-[13px] text-ink-2 ${BRIEF_H}`} aria-label="Briefing">
        <span className="flex items-center gap-1 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">Briefing <HelpTip id="briefing" /></span>
        <span>Not generated yet (the API does not serve <code>/api/briefing</code> yet). The figures below are all live.</span>
      </section>
    )
  }
  const text = b.text?.trim()
  return (
    <section data-tour="overview-briefing" className={`card relative flex flex-col overflow-hidden ${open ? '' : BRIEF_H}`} aria-labelledby="briefing-h">
      <header className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2.5">
        <h2 id="briefing-h" className="flex items-center gap-1.5 text-[13px] font-semibold tracking-wide text-ink-2 uppercase">Briefing <HelpTip id="briefing" /></h2>
        <span className="inline-flex items-center gap-1">
          <span className="chip" title={llm ? `Rules-based briefing rewritten by ${b.model ?? 'an LLM'}. Facts and links come from the rules engine.` : 'Generated by deterministic rules from the collected data'}
            style={{ color: llm ? 'var(--s7)' : 'var(--ink-2)', borderColor: 'currentColor' }}>
            {llm ? '✦ AI-polished' : '≡ Rules'}
          </span>
          <InfoTip title={llm ? 'AI-polished briefing' : 'Rules-based briefing'}
            text={llm
              ? `A fixed set of rules wrote this briefing from the stored data, then a language model (${b.model ?? 'LLM'}) rewrote it in plainer words. Any rewritten text containing a number that is not in the rules version is rejected, so the figures are the same as the rules text.`
              : 'Written by fixed rules from the stored data: every figure, date and link comes straight from the collected sources, nothing is estimated. An optional AI rewrite (needs a ComputeForge key) only rephrases it.'} />
        </span>
        {llm && b.model && <span className="hidden text-[11px] text-ink-3 sm:inline">{b.model}</span>}
        <span className="ml-auto flex items-center gap-1.5 text-[11px] text-ink-3" title={b.generated_at ?? ''}>
          generated {fmtDate(b.generated_at)} ({relTime(b.generated_at)}) · rebuilt every 6 h
          {stale && <><span className="chip" style={{ color: 'var(--stale)', borderColor: 'var(--stale)' }}>◷ stale</span><HelpTip id="stale_data" /></>}
        </span>
        <button type="button" className="btn !min-h-8 !px-2 !py-0.5 !text-[12px]" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {open ? 'Collapse' : `Show all ${sections.length} sections`}
        </button>
      </header>
      <div className={`px-4 py-3 ${open ? '' : 'min-h-0 flex-1 overflow-hidden'}`}>
        {b.headline && <p className="text-[17px] leading-snug font-semibold text-ink sm:text-[19px]">{fmtUnit(b.headline)}</p>}
        {sections.length > 0 ? (
          <div className="mt-3 grid gap-x-6 gap-y-4 md:grid-cols-2 xl:grid-cols-3 min-[137.5rem]:grid-cols-6">
            {sections.map((sec) => (
              <div key={sec.id} className="min-w-0">
                <h3 className="flex items-center gap-1 text-[12px] font-semibold tracking-wide text-ink-3 uppercase">
                  {sec.title}
                  {BRIEF_SECTION_TOPIC[sec.id] && <HelpTip id={BRIEF_SECTION_TOPIC[sec.id]} />}
                </h3>
                {sec.bullets?.length ? (
                  <ul className="mt-1 space-y-1 text-[13px] leading-snug text-ink-2">
                    {sec.bullets.map((t, i) => <li key={i} className="flex gap-2"><span className="text-ink-3" aria-hidden>▸</span><span className="min-w-0">{fmtUnit(t)}</span></li>)}
                  </ul>
                ) : null}
                {sec.sources?.length ? (
                  <div className="mt-1.5 flex flex-wrap gap-x-2 gap-y-0.5 text-[11px]">
                    <span className="text-ink-3">Sources:</span>
                    {sec.sources.map((x, i) => {
                      const u = safeUrl(x.url)
                      return u ? <a key={i} className="link" href={u} target="_blank" rel="noreferrer">{x.title} ↗</a> : <span key={i} className="text-ink-3">{x.title}</span>
                    })}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : text ? (
          <div className="mt-2 space-y-2 text-[13px] leading-relaxed whitespace-pre-line text-ink-2">{fmtUnit(text)}</div>
        ) : null}
      </div>
      {!open && (
        <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-14" style={{ background: 'linear-gradient(to bottom, transparent, var(--surface))' }} />
      )}
    </section>
  )
}

function toneColor(t: 'warm' | 'cold' | 'neutral') {
  return t === 'warm' ? 'var(--warm)' : t === 'cold' ? 'var(--cold)' : 'var(--ink-2)'
}

function HeroStat({ label, help, value, sub, children, tour }: {
  label: ReactNode; help?: ReactNode; value: string; sub?: ReactNode; children?: ReactNode; tour?: string
}) {
  return (
    <div data-tour={tour} className="min-w-0 border-t border-line px-4 py-3 sm:border-t-0 sm:border-l first:sm:border-l-0">
      <div className="flex items-center gap-1 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">{label}{help}</div>
      <div className="mt-0.5 flex flex-wrap items-baseline gap-x-2">
        <span className="text-[34px] leading-none font-semibold tracking-tight tnum">{value}</span>
        {sub}
      </div>
      {children}
    </div>
  )
}

function Hero() {
  const cpc = useStatus<CpcAlert>('cpc_alert')
  const latest = useLatest()
  const sources = useSources()
  const oni = findLatest(latest.data, 'oni')
  const wk = findLatest(latest.data, 'nino34_weekly_anom')
  const oniS = strength(oni?.value)
  const wkS = strength(wk?.value)
  const delta = wk && wk.value !== null && wk.prev_value !== null ? wk.value - wk.prev_value : null
  const a = cpc.data?.value
  const status = a?.status ?? null
  const isEl = status ? /el ?ni/i.test(status) : false
  const statusColor = !status ? 'var(--ink-3)' : /advisory|avis/i.test(status) ? 'var(--warm)' : /watch|veille/i.test(status) ? 'var(--warning)' : 'var(--ink-2)'
  const link = (l?: LatestPoint) => (l ? sourceLink(sources.data, l.source) : null)

  return (
    <section className="card overflow-hidden">
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-[1.4fr_1fr_1fr]">
        {/* CPC */}
        <div className="px-4 py-3 sm:col-span-2 xl:col-span-1" style={{ background: 'linear-gradient(90deg, color-mix(in srgb, var(--warm) 14%, transparent), transparent)' }}>
          <div className="flex items-center gap-1 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">Official NOAA CPC status <HelpTip id="cpc_alert_system" /></div>
          {cpc.isLoading ? <Skeleton h={48} className="mt-2" /> : a ? (
            <>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className="chip !text-[13px]" style={{ color: statusColor, borderColor: statusColor }}>
                  {isEl ? '▲ ' : ''}{status ?? 'unknown status'}
                </span>
                <KindBadge kind="bulletin" />
              </div>
              {a.synopsis && <p className="mt-2 line-clamp-3 text-[13px] leading-snug text-ink-2">{a.synopsis}</p>}
              <AsOf className="mt-1.5" label="issued" ts={a.issued ?? cpc.data?.updated_at} tz="UTC" source="NOAA CPC ENSO Diagnostic Discussion" href={safeUrl(a.url)} staleMs={40 * 86400000} />
            </>
          ) : (
            <p className="mt-2 text-[13px] text-ink-2">
              CPC status not collected yet (key <code>cpc_alert</code>). <Link className="link" to="/sources">See Sources</Link>
            </p>
          )}
        </div>
        {/* ONI */}
        <HeroStat
          label={<>ONI {oni ? <Term id="season_codes">{seasonLabel(oni.ts)}</Term> : ''}</>}
          help={<HelpTip id="oni" />}
          value={oni ? fmtSigned(oni.value, 2) : '--'}
          sub={oni && <span className="text-sm text-ink-3">°C</span>}>
          {oni ? (
            <>
              <div className="mt-1 text-[13px] font-semibold" style={{ color: toneColor(oniS.tone) }}>{oniS.label}</div>
              <p className="text-[11px] text-ink-3">official 3-month mean of the Nino 3.4 <Term id="anomaly">anomaly</Term></p>
              <AsOf ts={oni.ts} label="season centred on" tz="UTC" kind={oni.kind} validFor={oni.valid_for} source={link(oni)?.title} href={link(oni)?.href} staleMs={staleAfterMs('oni')} />
            </>
          ) : latest.isLoading ? <Skeleton h={30} className="mt-1" /> : <p className="mt-1 text-[12px] text-ink-3">Series <code>oni</code> unavailable. <Link className="link" to="/sources">Sources</Link></p>}
        </HeroStat>
        {/* weekly */}
        <HeroStat tour="overview-weekly" label="Weekly Nino 3.4"
          help={<><HelpTip id="nino34" /><HelpTip id="time_resolution" label="Weekly vs monthly values" /></>}
          value={wk ? fmtSigned(wk.value, 1) : '--'}
          sub={wk && (
            <>
              <span className="text-sm text-ink-3">°C</span>
              <span className="text-[13px] font-semibold tnum" style={{ color: delta === null ? 'var(--ink-3)' : delta > 0 ? 'var(--warm)' : delta < 0 ? 'var(--cold)' : 'var(--ink-3)' }}
                title="Change from the previous week">
                {delta === null ? '' : `${delta > 0 ? '▲' : delta < 0 ? '▼' : '='} ${fmtSigned(delta, 1)} over 1 wk`}
              </span>
            </>
          )}>
          {wk ? (
            <>
              <div className="mt-1 text-[13px] font-semibold" style={{ color: toneColor(wkS.tone) }}>{wkS.label}</div>
              <p className="text-[11px] text-ink-3">1-week mean, faster but noisier than the ONI</p>
              <AsOf ts={wk.ts} label="week of" tz="UTC" kind={wk.kind} validFor={wk.valid_for} source={link(wk)?.title} href={link(wk)?.href} staleMs={staleAfterMs('nino34_weekly_anom')} />
            </>
          ) : latest.isLoading ? <Skeleton h={30} className="mt-1" /> : <p className="mt-1 text-[12px] text-ink-3">Series <code>nino34_weekly_anom</code> unavailable. <Link className="link" to="/sources">Sources</Link></p>}
        </HeroStat>
      </div>
      <div className="flex flex-wrap items-center gap-1 border-t border-line px-4 py-1.5 text-[11px] text-ink-3">
        Strength thresholds (Nino 3.4 anomaly): weak 0.5 to 1.0 · moderate 1.0 to 1.5 · strong 1.5 to 2.0 · very strong &gt;= 2.0 °C.
        <HelpTip id="strength_categories" />
      </div>
    </section>
  )
}

function pct(v: number | null | undefined, scale: number) {
  return v === null || v === undefined ? null : Math.round(v * scale)
}

function IriCard() {
  const q = useStatus<IriPlume>('iri_plume')
  const v = q.data?.value
  const probs = v?.probabilities ?? []
  const sum = probs[0] ? (probs[0].la_nina ?? 0) + (probs[0].neutral ?? 0) + (probs[0].el_nino ?? 0) : 100
  const scale = sum <= 1.5 ? 100 : 1
  return (
    <Card title="ENSO probabilities (IRI)" help={<HelpTip id="iri_plume" />} tour="overview-iri" className="h-full"
      right={<KindBadge kind="forecast" />}
      footer={probs.length ? <AsOf label="issued" ts={v?.issued ?? q.data?.updated_at} tz="UTC" source="IRI ENSO Forecast" href={safeUrl(v?.url) ?? 'https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/'} staleMs={40 * 86400000} /> : undefined}>
      {q.isLoading ? <Skeleton h={160} /> : q.isError ? <ErrorBox error={q.error} what="IRI" /> : !probs.length ? (
        <Empty what="IRI probabilistic forecasts unavailable" source="IRI Columbia (iri_plume)" />
      ) : (
        <>
          <ul className="mb-2 flex flex-wrap items-center gap-3 text-[11px] text-ink-2" aria-label="Legend">
            <li className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: 'var(--cold)' }} /><Term id="la_nina">La Nina</Term></li>
            <li className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: 'var(--neutral)' }} /><Term id="neutral">Neutral</Term></li>
            <li className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: 'var(--warm)' }} /><Term id="el_nino">El Nino</Term></li>
            <li className="ml-auto flex items-center gap-1 text-ink-3">season codes <HelpTip id="season_codes" /></li>
          </ul>
          <div className="space-y-1.5">
            {probs.map((p) => {
              const parts = [
                { k: 'La Nina', v: pct(p.la_nina, scale), c: 'var(--cold)' },
                { k: 'Neutral', v: pct(p.neutral, scale), c: 'var(--neutral)' },
                { k: 'El Nino', v: pct(p.el_nino, scale), c: 'var(--warm)' },
              ]
              return (
                <div key={p.season} className="grid grid-cols-[44px_1fr_40px] items-center gap-2 text-[12px]">
                  <span className="font-semibold text-ink-2 tnum">{p.season}</span>
                  <div className="flex h-4 gap-[2px] overflow-hidden rounded" role="img"
                    aria-label={`${p.season}: ${parts.map((x) => `${x.k} ${x.v ?? '?'} %`).join(', ')}`}>
                    {parts.map((x) => (x.v ? (
                      <div key={x.k} title={`${x.k}: ${x.v} %`} style={{ width: `${x.v}%`, background: x.c }} className="h-full first:rounded-l last:rounded-r" />
                    ) : null))}
                  </div>
                  <span className="text-right font-semibold tnum">{parts[2].v ?? '--'} %</span>
                </div>
              )
            })}
          </div>
          <p className="mt-1 flex items-center justify-end gap-1 text-right text-[10px] text-ink-3">% = El Nino <Term id="probability">probability</Term> for that 3-month season</p>
        </>
      )}
    </Card>
  )
}

function SamuiCard() {
  const q = useLocal()
  const r = q.data
  const unknown = !!r && (r.level === null || r.level === undefined || r.level_key === 'unknown')
  const m = r && !unknown ? levelMeta(r.level, r.level_key) : null
  const floor = riskFloor(r)
  const cov = r?.coverage
  return (
    <Card title="Koh Samui watch" help={<HelpTip id="risk_levels" />} tour="overview-samui" className="h-full"
      right={<Link className="link text-[12px]" to="/samui">Details ›</Link>}
      footer={r ? <AsOf label="evaluated" ts={r.evaluated_at} tz="ICT" staleMs={6 * 3600000} source={`Koh Samui risk engine, ${r.factors?.length ?? 0} factors`} /> : undefined}>
      {q.isLoading ? <Skeleton h={120} /> : q.isError ? <ErrorBox error={q.error} what="local risk" /> : !r ? (
        <Empty what="Local risk assessment not produced yet" source="Koh Samui risk engine (/api/local)" />
      ) : (
        <div className="flex h-full flex-col">
          <div className="flex items-center gap-3">
            <div className="grid h-14 w-14 shrink-0 place-items-center rounded-full text-2xl font-bold tnum"
              style={{ background: m ? `color-mix(in srgb, ${m.color} 20%, transparent)` : 'var(--surface-2)', color: m?.color ?? 'var(--ink-2)', border: `2px ${m ? 'solid' : 'dashed'} ${m?.color ?? 'var(--line-strong)'}` }}
              aria-hidden>
              {m ? r.level : '?'}
            </div>
            <div className="min-w-0">
              <span className="inline-flex items-center gap-1">
                <LevelBadge level={unknown ? null : r.level} levelKey={unknown ? null : r.level_key} floor={unknown ? floor : null} />
                {unknown && <HelpTip id="unknown_level" />}
                {unknown && floor && <HelpTip id="local_level_floor" label="What does 'at least' mean?" />}
              </span>
              <p className="mt-1 text-[14px] leading-snug font-medium">{r.headline ?? 'No summary.'}</p>
            </div>
          </div>
          {unknown && (
            <p className="mt-2 text-[12px]" style={{ color: 'var(--warning)' }}>
              ▲ Level unknown: critical factors lack data. Not an all-clear.
            </p>
          )}
          {cov && (
            <p className="mt-2 flex flex-wrap items-center gap-1 text-[12px] text-ink-2 tnum">
              Data coverage: {cov.with_data} / {cov.total} factors with data
              {cov.critical_missing?.length ? <span style={{ color: 'var(--warning)' }}> · critical missing: {cov.critical_missing.join(', ')}</span> : <span className="text-ink-3"> · all critical factors present</span>}
              <HelpTip id="local_coverage" />
              <HelpTip id="data_coverage" label="What is data coverage?" />
            </p>
          )}
          {r.actions?.length ? (
            <>
              <div className="mt-3 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">What to do now</div>
              <ul className="mt-0.5 list-disc space-y-0.5 pl-5 text-[13px] text-ink-2">
                {r.actions.slice(0, 3).map((a, i) => <li key={i}>{a.text}</li>)}
              </ul>
            </>
          ) : null}
          <div className="mt-auto grid grid-cols-2 gap-2 pt-3">
            <Link to="/samui" className="btn justify-center">Koh Samui watch</Link>
            <Link to="/samui?view=exit" className="btn justify-center">Exit plan</Link>
          </div>
        </div>
      )}
    </Card>
  )
}

const ALERT_LEVELS = ['vigilance', 'prepare', 'act', 'leave', 'unknown']
const ALERT_SINCE = [
  { v: '', l: 'Any time' }, { v: '24h', l: '24 h' }, { v: '7d', l: '7 days' }, { v: '30d', l: '30 days' },
]
const SEV_COLOR: Record<string, string> = { green: 'var(--good)', orange: 'var(--serious)', red: 'var(--critical)', info: 'var(--ink-3)' }

function alertKindLabel(k: string, factors: Map<string, string>): string {
  if (k === 'local_level') return 'Island level'
  if (k === 'data_gap') return 'Data gap'
  if (k.startsWith('factor_')) return factors.get(k.slice(7)) ?? k.slice(7).replace(/_/g, ' ')
  return k.replace(/_/g, ' ')
}

function NearbyEvents() {
  const q = useEventsQ({ near: `${HOME.lat},${HOME.lon}`, limit: 50 })
  const rows = useMemo(() => [...(q.data ?? [])].sort((a, b) => (a.distance_km ?? 1e9) - (b.distance_km ?? 1e9)), [q.data])
  const newest = rows.reduce<string>((m, e) => { const t = e.updated_at ?? e.started_at ?? ''; return t > m ? t : m }, '')
  return (
    <div className="mt-3 border-t border-line pt-3">
      <div className="flex flex-wrap items-center gap-1 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">
        Hazard events within {HOME.radiusKm} km <HelpTip id="gdacs" />
        <Link className="link ml-auto text-[11px] font-normal normal-case" to="/map">on the map ›</Link>
      </div>
      {q.isLoading ? <Skeleton h={60} className="mt-2" /> : q.isError ? <ErrorBox error={q.error} what="nearby events" /> : !rows.length ? (
        <p className="mt-1 text-[12px] text-ink-2">No GDACS, EONET, FIRMS or Coral Reef Watch event within {HOME.radiusKm} km of Koh Samui right now.</p>
      ) : (
        <>
          <ul className="mt-1 divide-y divide-line">
            {rows.slice(0, 5).map((e: EventItem) => {
              const c = SEV_COLOR[e.severity ?? ''] ?? 'var(--ink-3)'
              const u = safeUrl(e.url)
              return (
                <li key={`${e.source}:${e.ext_id}`} className="flex items-start gap-2 py-1.5 text-[12px]">
                  <span className="mt-1 inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: c }} title={`severity: ${e.severity ?? 'unknown'}`} aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-x-1.5 text-[11px] text-ink-3">
                      <span className="font-semibold capitalize" style={{ color: toneText(c) }}>{e.category}</span>
                      <HelpFor appId={e.category} kind="category" />
                      <span>· {e.source}</span>
                      {e.distance_km != null && <span className="tnum">· {fmtNum(e.distance_km, 0)} km</span>}
                      <span className="ml-auto" title={fmtDate(e.updated_at ?? e.started_at)}>{relTime(e.updated_at ?? e.started_at)}</span>
                    </span>
                    {u ? <a className="line-clamp-1 hover:underline" href={u} target="_blank" rel="noreferrer">{e.title ?? '(untitled)'}</a> : <span className="line-clamp-1">{e.title ?? '(untitled)'}</span>}
                  </span>
                </li>
              )
            })}
          </ul>
          <p className="text-[11px] text-ink-3">{rows.length} event{rows.length > 1 ? 's' : ''} · newest update {relTime(newest)} · these feed the island level, they are not alerts by themselves</p>
        </>
      )}
    </div>
  )
}

function AlertsCard() {
  const f = useUrlFilters({ level: 'list', kind: 'list', since: 'str' }, 'al_')
  const local = useLocal()
  const all = useAlertsQ({ limit: 1000 })
  const q = useAlertsQ({ level: f.api.level, kind: f.api.kind, since: sinceFromPreset(f.values.since), limit: 20 })
  const allRows = all.data ?? []
  const rows = q.data ?? []
  const factors = useMemo(() => new Map((local.data?.factors ?? []).map((x) => [x.id, x.label])), [local.data])
  const count = (key: 'level' | 'kind', v: string) => allRows.filter((a) => a[key] === v).length
  const levelOpts = ALERT_LEVELS.map((k) => {
    const m = levelMeta(null, k)
    return { value: k, text: m?.label ?? 'Unknown', label: m?.label ?? 'Unknown', color: m?.color ?? 'var(--ink-3)', count: all.data ? count('level', k) : null }
  })
  const kinds = ['local_level', 'data_gap', ...[...factors.keys()].map((id) => `factor_${id}`)]
  for (const a of allRows) if (!kinds.includes(a.kind)) kinds.push(a.kind)
  const kindOpts = kinds.map((k) => ({
    value: k, text: alertKindLabel(k, factors), label: alertKindLabel(k, factors), count: all.data ? count('kind', k) : null,
    help: k === 'data_gap' ? <HelpTip id="alert_data_gap" /> : k === 'local_level' ? <HelpTip id="risk_levels" label="What is the island level?" /> : undefined,
  }))
  const human = [
    ...f.values.level.map((v) => `level: ${levelMeta(null, v)?.label ?? v}`),
    ...f.values.kind.map((v) => `kind: ${alertKindLabel(v, factors)}`),
    ...(f.values.since ? [`since: ${ALERT_SINCE.find((s) => s.v === f.values.since)?.l ?? f.values.since}`] : []),
  ]
  const newest = allRows[0]?.created_at
  return (
    <Card title="Latest alerts" help={<HelpTip id="risk_rules" label="What raises an alert?" />} tour="overview-alerts" className="h-full"
      right={f.active > 0 ? <button type="button" className="btn !min-h-8 !px-2 !py-0.5 !text-[12px]" onClick={f.reset}>Reset filters</button> : undefined}
      footer={<AsOf label={newest ? 'newest alert' : 'checked'} ts={newest ?? (all.dataUpdatedAt ? new Date(all.dataUpdatedAt).toISOString() : null)} tz="ICT" source="Koh Samui alert engine (/api/alerts)" />}>
      <div className="flex flex-wrap gap-x-4 gap-y-2" aria-label="Alert filters">
        <FilterGroup label="Level" help={<HelpTip id="risk_levels" />}>
          <ChipSelect options={levelOpts} selected={f.values.level} onToggle={(v) => f.toggle('level', v)} limit={5} />
        </FilterGroup>
        <FilterGroup label="Kind" help={<HelpTip id="filters_sources_alerts" />}>
          <ChipSelect options={kindOpts} selected={f.values.kind} onToggle={(v) => f.toggle('kind', v)} limit={2} />
        </FilterGroup>
        <FilterGroup label="Since">
          <PresetSelect label="Alerts since" value={f.values.since} options={ALERT_SINCE} onChange={(v) => f.set('since', v)} />
        </FilterGroup>
      </div>
      <div className="mt-3">
        {q.isLoading || all.isLoading ? <Skeleton h={80} /> : q.isError ? <ErrorBox error={q.error} what="alerts" /> : !rows.length ? (
          f.active > 0 && allRows.length > 0 ? (
            <FilteredEmpty what="alerts" filters={human} onReset={f.reset} total={allRows.length} />
          ) : (
            <div className="rounded-lg border border-dashed border-line-strong p-3 text-[13px] text-ink-2" role="status">
              <p className="font-medium text-ink">{f.active > 0 ? 'No alerts match these filters, and none have been issued at all yet.' : 'No alerts issued yet.'}</p>
              <p className="mt-1">
                The Koh Samui watch raises an alert only when the island level goes up (to Watch or higher),
                when one factor reaches Act or Leave, or when critical data has been missing for more than 6 hours
                (a data gap alert <HelpTip id="alert_data_gap" />). An empty list means none of that has happened, not that the data is missing.
              </p>
              {f.active > 0 && <button type="button" className="btn mt-2" onClick={f.reset}>Reset filters</button>}
            </div>
          )
        ) : (
          <ul className="divide-y divide-line">
            {rows.slice(0, 6).map((a) => {
              const lv = Number.isFinite(Number(a.level)) ? Number(a.level) : null
              return (
                <li key={a.id} className="py-2">
                  <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-3">
                    <LevelBadge level={lv} levelKey={lv === null ? a.level : null} />
                    <span>{alertKindLabel(a.kind, factors)}</span>
                    <span className="ml-auto" title={fmtDate(a.created_at)}>{relTime(a.created_at)}</span>
                  </div>
                  <div className="mt-0.5 text-[13px] font-medium">{a.title}</div>
                  {a.body && <p className="line-clamp-2 text-[12px] text-ink-2">{a.body}</p>}
                </li>
              )
            })}
          </ul>
        )}
      </div>
      <NearbyEvents />
    </Card>
  )
}

function LatestFeed() {
  const off = useFeed({ kind: 'official', limit: 60 })
  const news = useFeed({ kind: 'news', limit: 30 })
  const wide = useMedia('(min-width: 2200px)')
  const items = useMemo(() => {
    const all = [...(off.data ?? []), ...(news.data ?? [])]
    all.sort((a, b) => ((b.published_at ?? b.fetched_at) > (a.published_at ?? a.fetched_at) ? 1 : -1))
    // at most 3 items per source so one prolific feed does not hide the others
    const per = new Map<string, number>()
    return all.filter((i) => { const n = (per.get(i.source) ?? 0) + 1; per.set(i.source, n); return n <= 3 }).slice(0, wide ? 12 : 10)
  }, [off.data, news.data, wide])
  const newest = items[0] ? (items[0].published_at ?? items[0].fetched_at) : null
  return (
    <Card title="Official bulletins and press" help={<HelpTip id="news_signals" />}
      right={<><span className="hidden items-center gap-1 text-[11px] text-ink-3 sm:inline-flex">Official <HelpTip id="cpc_alert_system" label="What are official bulletins?" /></span><Link className="link text-[12px]" to="/news">See all ›</Link></>}
      footer={items.length ? <AsOf label="newest item" ts={newest} source="official agencies and press collectors (see Sources)" /> : undefined}>
      {off.isLoading && news.isLoading ? <Skeleton h={200} /> : !items.length ? (
        <Empty what="No bulletins or articles" source="official and news collectors" />
      ) : (
        <div className="grid gap-x-6 md:grid-cols-2 min-[137.5rem]:grid-cols-3">
          {items.map((i) => <div key={`${i.source}:${i.ext_id}`} className="min-w-0 border-b border-line last:border-b-0">
            <FeedRow item={i} compact />
          </div>)}
        </div>
      )}
    </Card>
  )
}

function Kpi({ series, title, help, since, unit, digits = 2, note, zero = true, staleMs, color }: {
  series: string; title: string; help: TopicId; since: string; unit?: string; digits?: number; note?: string; zero?: boolean
  staleMs?: number; color?: string
}) {
  const latest = useLatest()
  const s = useNamedSeries(series, since)
  const l = findLatest(latest.data, series)
  const d = l && l.value !== null && l.prev_value !== null ? l.value - l.prev_value : null
  const u = l?.unit_label || unit || unitLabel(l?.unit)
  return (
    <div className="card flex min-w-0 flex-col p-3">
      <div className="flex items-start justify-between gap-2">
        <span className="flex min-w-0 items-center gap-1 text-[12px] font-semibold text-ink-2">{title}<HelpTip id={help} /></span>
        {note && <span className="hidden text-right text-[10px] leading-tight text-ink-3 sm:inline">{note}</span>}
      </div>
      {l ? (
        <>
          <div className="mt-1 flex flex-wrap items-baseline gap-x-2">
            <span className="text-2xl font-semibold tnum">{fmtSigned(l.value, digits)}</span>
            {u && <span className="text-[12px] text-ink-3">{u}</span>}
            {d !== null && <span className="text-[12px] text-ink-3 tnum" title="Change from the previous value">{d > 0 ? '▲' : d < 0 ? '▼' : '='} {fmtSigned(d, digits)}</span>}
          </div>
          <div className="mt-auto">
            <Sparkline points={s.points} zero={zero} color={color} />
            <AsOf ts={l.ts} tz="UTC" kind={l.kind} validFor={l.valid_for} source={s.link?.title} href={s.link?.href} staleMs={staleMs ?? staleAfterMs(series)} />
          </div>
        </>
      ) : latest.isLoading ? <Skeleton h={70} className="mt-2" /> : (
        <p className="mt-2 text-[12px] text-ink-3">
          No data yet (<code>{series}</code>). <Link className="link" to="/sources">Sources</Link>
        </p>
      )}
    </div>
  )
}

function WorldSstKpi() {
  // absolute temperature; delta vs climatology if the collector also stores it
  const latest = useLatest()
  const s = useNamedSeries('world_sst_daily', isoDaysAgo(120))
  const l = findLatest(latest.data, 'world_sst_daily')
  const clim = latest.data?.find((x) => /^world_sst.*(clim|normal|mean)/.test(x.series))
  const anom = latest.data?.find((x) => /^world_sst.*anom/.test(x.series))
  const diff = anom?.value ?? (l && clim && l.value !== null && clim.value !== null ? l.value - clim.value : null)
  return (
    <div className="card flex min-w-0 flex-col p-3">
      <span className="flex items-center gap-1 text-[12px] font-semibold text-ink-2">Global SST (daily) <HelpTip id="world_sst" /></span>
      {l ? (
        <>
          <div className="mt-1 flex flex-wrap items-baseline gap-x-2">
            <span className="text-2xl font-semibold tnum">{fmtNum(l.value, 2)}</span>
            <span className="text-[12px] text-ink-3">°C</span>
            {diff !== null && <span className="inline-flex items-center gap-1 text-[12px] tnum text-ink-3" title="Departure from climatology">{fmtSigned(diff, 2)} vs normal<HelpTip id="climatology_baseline" label="What is 'normal'?" /></span>}
          </div>
          <div className="mt-auto">
            <Sparkline points={s.points} color="var(--s2)" />
            <AsOf ts={l.ts} tz="UTC" kind={l.kind} validFor={l.valid_for} source={s.link?.title} href={s.link?.href} staleMs={staleAfterMs('world_sst_daily')} />
          </div>
        </>
      ) : latest.isLoading ? <Skeleton h={70} className="mt-2" /> : (
        <p className="mt-2 text-[12px] text-ink-3">No data yet (<code>world_sst_daily</code>). <Link className="link" to="/sources">Sources</Link></p>
      )}
    </div>
  )
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const EVENTS = [
  { y: 1997, label: '1997-98', color: 'var(--s1)' },
  { y: 2015, label: '2015-16', color: 'var(--s3)' },
  { y: 2023, label: '2023-24', color: 'var(--s7)' },
  { y: 2026, label: '2026-27 (ongoing)', color: 'var(--s2)', width: 3.5 },
]

function OniCompare() {
  const s = useNamedSeries('oni', '1996-01-01')
  const box = useRef<HTMLDivElement>(null)
  const [boxH, setBoxH] = useState(0)
  useEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver(() => setBoxH(el.clientHeight))
    ro.observe(el)
    return () => ro.disconnect()
  })
  const rows = useMemo(() => {
    const by = new Map<string, number | null>()
    for (const p of s.points) by.set(p.ts.slice(0, 7), p.value)
    return Array.from({ length: 24 }, (_, i) => {
      const m = i % 12
      const r: Record<string, string | number | null> = { x: `${MONTHS[m]}${i >= 12 ? ' Y+1' : ''}` }
      for (const e of EVENTS) {
        const key = `${e.y + (i >= 12 ? 1 : 0)}-${String(m + 1).padStart(2, '0')}`
        r[`y${e.y}`] = by.has(key) ? (by.get(key) ?? null) : null
      }
      return r
    })
  }, [s.points])
  const has = s.points.length > 0
  return (
    <Card title="ONI: current event vs major El Ninos" tour="overview-oni-compare" className="h-full" bodyClass="flex flex-col"
      help={<><HelpTip id="past_events" /><HelpTip id="oni" label="What is the ONI?" /></>}
      right={<span className="text-[11px] text-ink-3">centre month of the <Term id="season_codes">season</Term>, onset year = Y</span>}
      footer={has ? <AsOf ts={s.entry?.last} tz="UTC" label="latest value" source={s.link?.title ?? 'NOAA CPC ONI'} href={s.link?.href} staleMs={staleAfterMs('oni')} /> : undefined}>
      {s.isLoading ? <Skeleton h={260} /> : !has ? (
        <Empty what="ONI history unavailable" source="NOAA CPC (oni series)" />
      ) : (
        <>
          {/* the chart fills whatever height the row gives it (the alerts card next to it sets the row height) */}
          <div ref={box} className="relative min-h-[300px] flex-1">
            <div className="absolute inset-0 overflow-auto">
              <CategoryLines rows={rows} xKey="x" unit="C" height={Math.max(260, boxH - 44)}
                series={EVENTS.map((e) => ({ key: `y${e.y}`, label: e.label, color: e.color, width: e.width }))} />
            </div>
          </div>
          <p className="mt-1 text-[11px] text-ink-3">
            Shaded band: <Term id="neutral">neutral</Term> (-0.5 to +0.5 °C). Each line starts in January of the year the event began; the thick line is the current event.
          </p>
        </>
      )}
    </Card>
  )
}

const MINI_MAP_EVENTS = 2000 // newest events drawn on the mini map (the count comes from the facets)

function MiniMap() {
  const [ref, inView] = useInView<HTMLDivElement>()
  const [idle, forceMount] = useIdleAfterInteraction()
  const mount = inView && idle
  // the 1 MB event list and the maplibre chunk are only fetched once the map is about to mount
  const ev = useEventsQ({ limit: MINI_MAP_EVENTS }, { enabled: mount })
  const facets = useEventFacets({})
  const total = typeof facets.data?.total === 'number' ? facets.data.total : null
  const tao = useStatus<unknown>('tao_buoys')
  const buoys: TaoBuoy[] = useMemo(() => buoysFrom(tao.data?.value), [tao.data])
  const newest = useMemo(() => (ev.data ?? []).reduce<string>((m, e) => { const t = e.updated_at ?? e.started_at ?? ''; return t > m ? t : m }, ''), [ev.data])
  return (
    <Card title="Map" help={<HelpTip id="map_overlays" />} right={<Link className="link text-[12px]" to="/map">Live map ›</Link>} pad={false}
      className="h-full" bodyClass="relative min-h-[260px] lg:min-h-[300px]"
      footer={
        <div className="flex min-h-[38px] flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] text-ink-3">
          <span>{total !== null ? `${total.toLocaleString('en-GB')} geolocated events` : 'Events: loading'}</span><HelpTip id="gdacs" label="What are these events?" />
          <span>· {buoys.length} TAO buoys</span><HelpTip id="tao_buoys" />
          <span>· Nino regions</span><HelpTip id="nino_regions" />
          <span>· Koh Samui ({HOME.radiusKm} km)</span>
          {newest && <span>· newest event update {relTime(newest)}</span>}
          {tao.data?.updated_at && <span>· buoys {relTime(tao.data.updated_at)}</span>}
          <span>· GDACS, NASA EONET / FIRMS, NOAA PMEL</span>
        </div>
      }>
      <div ref={ref} className="absolute inset-0 overflow-hidden">
        {mount ? (
          <Suspense fallback={<div className="skeleton h-full w-full !rounded-none" />}>
            <WorldMap mini pacific base="dark" events={ev.data} buoys={buoys} center={[-170, 2]} zoom={0.55}
              visible={{ events: true, buoys: true, news: false, nino: true, home: true, impacts: false, cams: false }} />
          </Suspense>
        ) : (
          <div className="skeleton flex h-full w-full items-center justify-center !rounded-none">
            <button type="button" className="btn" onClick={forceMount} title="The map (about 1 MB) loads once you scroll or move the mouse; this button loads it now">Show the map</button>
          </div>
        )}
      </div>
    </Card>
  )
}

export default function Overview() {
  const y3 = isoDaysAgo(365 * 3)
  return (
    <div className="grid gap-4">
      <PageGuide page="overview" />
      {/* min-heights reserve the loaded size of each async block so the page does not jump (CLS) */}
      <BriefingCard />
      <div className="min-h-[560px] sm:min-h-[260px]"><Hero /></div>
      <div className="grid grid-cols-2 gap-2 sm:gap-3 xl:grid-cols-5 min-[137.5rem]:grid-cols-10 [&>*]:min-h-[224px]">
        <Kpi series="nino34_daily_anom" title="Nino 3.4 (daily)" help="nino34" since={isoDaysAgo(180)} digits={2} note="preliminary, 1 day" color="var(--warm)" />
        <Kpi series="soi" title="SOI (NOAA)" help="soi" since={y3} note="negative = El Nino" digits={1} />
        <Kpi series="bom_soi" title="SOI (BoM)" help="bom_soi" since={y3} note="El Nino below -7" digits={1} staleMs={MONTHLY_STALE} />
        <Kpi series="mei_v2" title="MEI.v2" help="mei_v2" since={y3} />
        <Kpi series="roni" title="RONI" help="roni" since={y3} unit="C" />
        <WorldSstKpi />
        <Kpi series="wwv_anom" title="Warm water volume" help="series_wwv" since={y3} unit="x10^14 m3" note="fuel for El Nino" staleMs={MONTHLY_STALE} color="var(--s3)" />
        <Kpi series="heat_content_180w_100w_anom" title="Heat content 180-100W" help="series_heat_content" since={y3} unit="C" note="upper 300 m" staleMs={MONTHLY_STALE} color="var(--s3)" />
        <Kpi series="trade_wind_850_cpac_anom" title="Trade winds (C. Pacific)" help="series_trade_winds_olr" since={y3} unit="m/s" digits={1} note="negative = weaker" staleMs={MONTHLY_STALE} color="var(--s4)" />
        <Kpi series="dmi_jma_anom" title="Indian Ocean Dipole" help="series_iod_dmi" since={y3} unit="C" note="DMI (JMA)" staleMs={MONTHLY_STALE} color="var(--s7)" />
      </div>
      <div className="min-h-[355px] lg:min-h-[207px]"><AnalogsCard compact tour="overview-analogs" /></div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-12 min-h-[2770px] md:min-h-[1550px]">
        <div className="min-w-0 xl:col-span-4 min-[137.5rem]:col-span-3"><SamuiCard /></div>
        <div className="min-w-0 xl:col-span-4 min-[137.5rem]:col-span-3"><IriCard /></div>
        <div className="min-w-0 md:col-span-2 xl:col-span-4 min-[137.5rem]:col-span-6"><MiniMap /></div>
        <div className="min-w-0 md:col-span-2 xl:col-span-8"><OniCompare /></div>
        <div className="min-w-0 md:col-span-2 xl:col-span-4"><AlertsCard /></div>
      </div>
      <div className="min-h-[990px] md:min-h-[460px]"><LatestFeed /></div>
      <p className="text-center text-[11px] text-ink-3">
        Every value shows its date and source. No data is estimated or made up.{' '}
        <Ext href="https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/">NOAA CPC ENSO Discussion ↗</Ext>
      </p>
    </div>
  )
}
