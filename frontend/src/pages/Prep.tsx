import { useEffect, useMemo, useRef, useState } from 'react'
import { api, useAccess, usePreparedness, usePrepState } from '../api/client'
import { ShoppingPanel } from '../components/prep/ShoppingPanel'
import { ShoppingBudgetCard } from '../components/prep/ShoppingBudget'
import type { Household, PrepContact, PrepItem, PrepScenario, PrepState, Preparedness } from '../api/types'
import { Card, Empty, ErrorBox, Ext, PageHeader, Skeleton } from '../components/ui'
import { HelpFor, HelpTip, InfoTip, PageGuide, PREP_TOPIC, Term } from '../help'
import { fmtNum, levelMeta } from '../lib/format'
import { safeUrl } from '../lib/geo'

const PRIO: Record<string, { label: string; color: string; icon: string; hint: string }> = {
  must: { label: 'Essential', color: 'var(--critical)', icon: '■', hint: 'Get this first: without it, a few days cut off (no water, power or ferry) becomes dangerous.' },
  should: { label: 'Recommended', color: 'var(--serious)', icon: '▲', hint: 'Makes a long disruption much easier to live through; get it once the essentials are done.' },
  nice: { label: 'Useful', color: 'var(--ink-3)', icon: '●', hint: 'Comfort or backup items; nice to have if space and budget allow.' },
}

function multiplier(per: string | null | undefined, h: Household): { n: number; how: string } | null {
  if (!per) return null
  // accepts both the new English values ("person/day", "person", "household") and the legacy French ones
  const p = per.toLowerCase().replace(/\s/g, '')
  const persons = h.adults + h.children
  const perPerson = /person|pers|people|head/.test(p)
  const perDay = /day|jour/.test(p)
  const perAdult = /adult/.test(p)
  const perChild = /child|enfant/.test(p)
  if (perAdult && perDay) return { n: h.adults * h.days, how: `${h.adults} adult(s) x ${h.days} d` }
  if (perChild && perDay) return { n: h.children * h.days, how: `${h.children} child(ren) x ${h.days} d` }
  if (perAdult) return { n: h.adults, how: `${h.adults} adult(s)` }
  if (perChild) return { n: h.children, how: `${h.children} child(ren)` }
  if (perPerson && perDay) return { n: persons * h.days, how: `${persons} person(s) x ${h.days} d` }
  if (perPerson) return { n: persons, how: `${persons} person(s)` }
  if (perDay) return { n: h.days, how: `${h.days} d` }
  return null
}

/** Total quantity needed for the household (same rule as qtyText), for the shopping estimate. */
function qtyNeeded(it: PrepItem, h: Household): number | undefined {
  if (it.qty === null || it.qty === undefined) return undefined
  const m = multiplier(it.per, h)
  return m ? it.qty * m.n : it.qty
}

function qtyText(it: PrepItem, h: Household): string | null {
  if (it.qty === null || it.qty === undefined) return null
  const m = multiplier(it.per, h)
  const unit = it.unit ?? ''
  const household = !it.per || /foyer|household|maison/i.test(it.per)
  if (!m) return `${fmtNum(it.qty, it.qty % 1 ? 1 : 0)} ${unit}${household ? '' : ` / ${it.per}`}`.trim()
  const total = it.qty * m.n
  return `${fmtNum(total, total % 1 ? 1 : 0)} ${unit} (${fmtNum(it.qty, it.qty % 1 ? 1 : 0)} x ${m.how})`.trim()
}

const DEFAULT_H: Household = { adults: 2, children: 0, days: 14 }
const LS = 'prep-state'

function scenarioTitle(s: PrepScenario, i: number) {
  return String(s.title ?? s.name ?? s.id ?? `Scenario ${i + 1}`)
}

function Scenario({ s, i, open = false }: { s: PrepScenario; i: number; open?: boolean }) {
  const lm = s.level_key ? levelMeta(null, s.level_key) : null
  const steps = (s.steps ?? s.actions ?? []) as unknown[]
  const known = new Set(['id', 'title', 'name', 'summary', 'description', 'level_key', 'steps', 'actions'])
  const KEY_LABEL: Record<string, string> = { when: 'When', before: 'Before', during: 'During', after: 'After', triggers: 'Triggers' }
  const extras = Object.entries(s).filter(([k, v]) => !known.has(k) && (typeof v === 'string' || Array.isArray(v)))
  return (
    <details className="group border-t border-line first:border-t-0" open={open || i === 0}>
      <summary className="flex cursor-pointer list-none items-center gap-2 py-2.5 text-[14px] font-medium">
        <span className="text-ink-3 transition group-open:rotate-90">›</span>
        {scenarioTitle(s, i)}
        {lm && <span className="chip" style={{ color: lm.color, borderColor: lm.color }}>{lm.label}</span>}
      </summary>
      <div className="pb-3 pl-5 text-[13px] text-ink-2">
        {(s.summary || s.description) && <p className="mb-2">{String(s.summary ?? s.description)}</p>}
        {steps.length > 0 && <ol className="list-decimal space-y-0.5 pl-5">{steps.map((x, j) => <li key={j}>{typeof x === 'string' ? x : JSON.stringify(x)}</li>)}</ol>}
        {extras.map(([k, v]) => (
          <div key={k} className="mt-2">
            <div className="text-[11px] font-semibold tracking-wide text-ink-3 uppercase">{KEY_LABEL[k] ?? k.replace(/_/g, ' ')}</div>
            {Array.isArray(v) ? <ul className="list-disc pl-5">{v.map((x, j) => <li key={j}>{typeof x === 'string' ? x : JSON.stringify(x)}</li>)}</ul> : <p>{v as string}</p>}
          </div>
        ))}
      </div>
    </details>
  )
}

function Contact({ c }: { c: PrepContact }) {
  const name = String(c.name ?? c.label ?? c.title ?? '')
  const num = (c.number ?? c.phone) as string | undefined
  const url = safeUrl(c.url) ?? safeUrl(c.source)
  return (
    <li className="flex flex-wrap items-baseline gap-x-3 py-1.5 text-[13px]">
      <span className="font-medium">{name}</span>
      {num && <a className="link font-semibold tnum" href={`tel:${num.replace(/[^\d+]/g, '')}`}>{num}</a>}
      {url && <Ext href={url} className="text-[12px]">{c.url ? 'website' : 'source'} ↗</Ext>}
      {c.note && <span className="w-full text-[12px] text-ink-3">{String(c.note)}</span>}
    </li>
  )
}

export default function Prep() {
  const data = usePreparedness()
  const access = useAccess()
  // public site: the checklist is per browser (localStorage); the server state is the owner's
  const local = access.loaded && !access.canWrite
  const remote = usePrepState(access.loaded && access.canWrite)
  const [state, setState] = useState<PrepState | null>(null)
  const [save, setSave] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // initialise once from API (fallback: browser storage)
  useEffect(() => {
    if (state || !access.loaded || (!local && remote.isLoading)) return
    let s: PrepState | null = local ? null : remote.data ?? null
    if (!s) {
      try { s = JSON.parse(localStorage.getItem(LS) ?? 'null') } catch { s = null }
    }
    setState({ checked: s?.checked ?? {}, household: { ...DEFAULT_H, ...(s?.household ?? {}) } })
  }, [remote.isLoading, remote.data, state, access.loaded, local])

  const update = (fn: (s: PrepState) => PrepState) => {
    if (!state) return
    const next = fn(state)
    setState(next)
    try { localStorage.setItem(LS, JSON.stringify(next)) } catch { /* ignore */ }
    if (local) return // public site: kept in this browser only, nothing to send
    if (timer.current) clearTimeout(timer.current)
    setSave('saving')
    timer.current = setTimeout(() => {
      api('/preparedness/state', { method: 'PUT', body: JSON.stringify(next) })
        .then(() => setSave('saved'))
        .catch(() => setSave('error'))
    }, 700)
  }

  const cats = data.data?.categories ?? []
  const h = state?.household ?? DEFAULT_H
  const checked = state?.checked ?? {}
  const totals = useMemo(() => {
    let all = 0, done = 0, must = 0, mustDone = 0
    for (const c of cats) for (const it of c.items) {
      all++; if (checked[it.id]) done++
      if (it.priority === 'must') { must++; if (checked[it.id]) mustDone++ }
    }
    return { all, done, must, mustDone }
  }, [cats, checked])

  const setH = (k: keyof Household, v: number) => update((s) => ({ ...s, household: { ...s.household, [k]: Math.max(k === 'adults' ? 1 : 0, Math.min(k === 'days' ? 120 : 20, Math.round(v) || 0)) } }))
  const sources = data.data?.sources ?? []
  // wide screens: every scenario starts expanded (there is room for them side by side)
  const [wideOpen] = useState(() => typeof window !== 'undefined' && !!window.matchMedia?.('(min-width: 1024px)').matches)
  const verified = (data.data as (Preparedness & { verified_at?: string; location?: string }) | undefined)?.verified_at ?? null
  const pctDone = totals.all ? Math.round((totals.done / totals.all) * 100) : 0
  const asOf = (
    <p className="text-[11px] text-ink-3">
      Checklist data verified {verified ?? 'date not given by the API'} against {sources.length} published guides (WHO, FEMA Ready.gov, Red Cross, Thai DDPM, UK FCDO...) · <a className="link" href="#prep-sources">sources</a>
    </p>
  )

  return (
    <div className="space-y-4">
      <PageHeader title="Preparedness" help={<HelpTip id="preparedness" />}
        sub="Checklist for staying on Koh Samui through the event. Ticks are saved automatically."
        right={
          <>
            <span className="text-[12px] text-ink-3" aria-live="polite">
              {local ? 'Saved in this browser' : save === 'saving' ? 'Saving...' : save === 'saved' ? 'Saved' : save === 'error' ? 'Server save failed (kept in this browser)' : ''}
            </span>
            {local && <HelpTip id="public_mode" label="Why is it saved in this browser only?" />}
            <button type="button" className="btn no-print" onClick={() => window.print()}>Print</button>
          </>
        } />
      <PageGuide page="prep" />

      {data.isLoading ? <Skeleton h={300} /> : data.isError ? <ErrorBox error={data.error} what="preparedness checklist" /> : !data.data || !cats.length ? (
        <Empty what="Preparedness checklist unavailable" source="preparedness module (/api/preparedness)" />
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
            <Card title="Household" tour="prep-household" className="h-full"
              help={<InfoTip title="Household" text="Enter who you are preparing for and how many days you want to last without shops, mains water or power. Items given per person or per day are multiplied for you (for example water: litres x persons x days). Saved with your ticks." />}
              footer={<p className="text-[11px] text-ink-3">{local ? 'Saved in this browser only (public site): it stays after a reload, not on another device.' : 'Saved on this server (and in this browser as a backup).'}</p>}>
              <div className="grid grid-cols-3 gap-3">
                {([['adults', 'Adults'], ['children', 'Children'], ['days', 'Days']] as const).map(([k, l]) => (
                  <label key={k} className="text-[12px] text-ink-2">
                    {l}
                    <input type="number" inputMode="numeric" className="input mt-1 min-h-10 w-full tnum sm:min-h-0" value={h[k]} min={k === 'adults' ? 1 : 0}
                      onChange={(e) => setH(k, Number(e.target.value))} />
                  </label>
                ))}
              </div>
              <p className="mt-2 text-[12px] text-ink-3">Per-person and per-day quantities are multiplied automatically. Guides recommend at least 14 days on an island.</p>
            </Card>
            <Card title="Progress" tour="prep-progress" className="h-full"
              help={<InfoTip title="Progress" text="Share of checklist items you have ticked, overall and for the Essential items only. Start with the Essential ones: they are what keeps you safe if the island is cut off." />}
              footer={<p className="text-[11px] text-ink-3">Counts your own ticks; nothing here is measured automatically.</p>}>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-semibold tnum">{pctDone} %</span>
                <span className="text-[13px] text-ink-2 tnum">{totals.done} / {totals.all} items</span>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-3" role="progressbar" aria-valuenow={pctDone} aria-valuemin={0} aria-valuemax={100} aria-label="Checklist progress">
                <div className="h-full rounded-full" style={{ width: `${pctDone}%`, background: 'var(--s1)' }} />
              </div>
              <p className="mt-2 text-[13px] text-ink-2">
                Essential: <b className="tnum">{totals.mustDone} / {totals.must}</b>
                {totals.must > 0 && totals.mustDone < totals.must && <span style={{ color: 'var(--serious)' }}> · ▲ {totals.must - totals.mustDone} missing</span>}
              </p>
            </Card>
            <ShoppingBudgetCard household={h} className="h-full" />
            <Card title="How to read the list" className="h-full"
              help={<HelpTip id="preparedness" label="Why prepare on an island?" />}
              footer={asOf}>
              <ul className="space-y-1.5 text-[13px]">
                {Object.entries(PRIO).map(([k, p]) => (
                  <li key={k} className="flex items-start gap-2">
                    <span className="chip shrink-0" style={{ color: p.color, borderColor: p.color }}>{p.icon} {p.label}</span>
                    <span className="text-[12px] text-ink-2">{p.hint}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[12px] text-ink-3">
                Each category has a <span className="font-semibold">?</span> explaining why it matters for Koh Samui during an El Nino (drought and <Term id="samui_water_supply">water rationing</Term>, heat, haze, storms).
              </p>
            </Card>
          </div>

          {/* CSS columns: a balanced masonry for cards of very different heights */}
          <div data-tour="prep-categories" className="gap-4 md:columns-2 xl:columns-3 min-[112.5rem]:columns-4">
            {cats.map((c) => {
              const done = c.items.filter((i) => checked[i.id]).length
              return (
                <div key={c.id} className="mb-4 break-inside-avoid">
                  <Card title={c.title}
                    help={<HelpFor appId={c.id} id={PREP_TOPIC[c.id] ?? null} title={c.title} text={c.why} kind="category" />}
                    right={<span className="text-[12px] text-ink-3 tnum">{done} / {c.items.length}</span>}>
                    {c.why && <p className="-mt-1 mb-2 text-[12px] text-ink-2">{c.why}</p>}
                    <div className="mb-2 h-1.5 overflow-hidden rounded-full bg-surface-3">
                      <div className="h-full rounded-full" style={{ width: `${c.items.length ? (done / c.items.length) * 100 : 0}%`, background: 'var(--s1)' }} />
                    </div>
                    <ul className="divide-y divide-line">
                      {c.items.map((it) => {
                        const pr = PRIO[it.priority] ?? PRIO.nice
                        const q = qtyText(it, h)
                        return (
                          <li key={it.id} className="py-1.5">
                            <label className="flex min-h-10 cursor-pointer items-start gap-2.5 sm:min-h-0">
                              <input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--accent)]" checked={!!checked[it.id]}
                                onChange={(e) => update((s) => ({ ...s, checked: { ...s.checked, [it.id]: e.target.checked } }))} />
                              <span className="min-w-0 flex-1">
                                <span className={`text-[13px] ${checked[it.id] ? 'text-ink-3 line-through' : ''}`}>{it.label}</span>
                                {q && <span className="block text-[12px] font-medium text-ink-2 tnum">{q}</span>}
                                {it.note && <span className="block text-[11px] text-ink-3">{it.note}</span>}
                              </span>
                              <span className="chip shrink-0" title={`${pr.label}: ${pr.hint}`} style={{ color: pr.color, borderColor: pr.color }}>{pr.icon} {pr.label}</span>
                            </label>
                            <ShoppingPanel itemId={it.id} needed={qtyNeeded(it, h)} />
                          </li>
                        )
                      })}
                    </ul>
                  </Card>
                </div>
              )
            })}
          </div>

          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            <Card title="Scenarios" tour="prep-scenarios" className="h-full lg:col-span-2"
              help={<InfoTip title="Scenarios" text="Step-by-step plans for the situations a strong El Nino can bring to Koh Samui (drought and water rationing, heatwave, storm and flood, haze, island cut off): when it applies, what to do before, during and after. The island level on the Koh Samui page tells you which one is getting closer." />}
              footer={asOf}>
              {data.data.scenarios?.length ? (
                <div className="gap-x-6 md:columns-2 min-[137.5rem]:columns-3">
                  {data.data.scenarios.map((s, i) => <div key={i} className="break-inside-avoid border-t border-line first:border-t-0"><Scenario s={s} i={i} open={wideOpen} /></div>)}
                </div>
              ) : <p className="text-[13px] text-ink-3">No scenarios provided.</p>}
            </Card>
            <div className="grid content-start gap-4 lg:col-span-2 lg:grid-cols-2 xl:col-span-1 xl:grid-cols-1">
              <Card title="Emergency contacts" tour="prep-contacts" help={<HelpTip id="prep_comms" />}
                footer={<p className="text-[11px] text-ink-3">Numbers checked against the linked official pages ({verified ?? 'date unknown'}). Write them on paper too: phones and networks can fail.</p>}>
                {data.data.contacts?.length ? <ul className="divide-y divide-line">{data.data.contacts.map((c, i) => <Contact key={i} c={c} />)}</ul> : <p className="text-[13px] text-ink-3">No contacts provided.</p>}
              </Card>
              <Card title="Sources" id="prep-sources"
                help={<InfoTip title="Checklist sources" text="Quantities and advice come from these published guides. The line under each link says which figure came from it, so you can check it yourself." />}
                footer={verified ? <p className="text-[11px] text-ink-3">Verified {verified}</p> : undefined}>
                {sources.length ? (
                  <ul className="space-y-1.5 text-[13px]">
                    {sources.map((s, i) => {
                      const url = typeof s === 'string' ? s : s.url
                      const t = typeof s === 'string' ? s : (s.title ?? s.name ?? s.url)
                      return (
                        <li key={i}>
                          <Ext href={safeUrl(url)}>{t} ↗</Ext>
                          {typeof s !== 'string' && s.used_for && <p className="text-[11px] text-ink-3">{s.used_for}</p>}
                        </li>
                      )
                    })}
                  </ul>
                ) : <p className="text-[13px] text-ink-3">Sources not listed by the API.</p>}
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
