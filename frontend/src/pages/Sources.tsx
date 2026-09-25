import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, useAccess, useSources, useStatus } from '../api/client'
import { AdminOnlyNote } from '../components/Admin'
import type { RunResult, SourceInfo, SourceState } from '../api/types'
import { ChipSelect, FilterBar, FilteredEmpty, FilterGroup, SearchFilter, type Opt } from '../components/filters'
import { AsOf, Card, Empty, ErrorBox, PageHeader, Skeleton } from '../components/ui'
import { HelpFor, HelpTip, PageGuide, SOURCE_STATE_TOPIC, sourceTopic, Term, type TopicId } from '../help'
import { fmtDate, fmtDuration, fmtNum, relTime, toneText } from '../lib/format'
import { safeUrl } from '../lib/geo'
import { isStale } from '../lib/series'
import { useUrlFilters } from '../lib/urlFilters'

/** Display state: the API sends "stale" directly (round 2); older APIs only flag freshness.stale on an "ok" row. */
type View = SourceState

const STATE: Record<View, { label: string; color: string; icon: string; hint: string }> = {
  ok: { label: 'ok', color: 'var(--good)', icon: '●', hint: 'Fetch ok and data within its expected age' },
  stale: { label: 'stale', color: 'var(--stale)', icon: '◷', hint: 'Fetch ok, but the newest data is older than its maximum age' },
  empty: { label: 'empty', color: 'var(--warning)', icon: '▲', hint: 'Source answered with no items' },
  error: { label: 'error', color: 'var(--critical)', icon: '■', hint: 'Last run failed' },
  needs_config: { label: 'needs config', color: 'var(--s7)', icon: '◆', hint: 'Needs a credential or setting' },
  pending: { label: 'pending', color: 'var(--ink-3)', icon: '○', hint: 'Not run yet' },
}
const STATES = Object.keys(STATE) as View[]

const viewOf = (r: SourceInfo): View => (r.state === 'stale' || (r.state === 'ok' && isStale(r)) ? 'stale' : (r.state in STATE ? r.state : 'pending'))

const CATEGORY_LABEL: Record<string, string> = {
  ocean_index: 'Ocean indices', official: 'Official', local: 'Koh Samui (local)', disaster: 'Disasters', news: 'News',
  social: 'Social', maritime: 'Maritime', satellite: 'Satellite', research: 'Research',
}
const catLabel = (c: string) => CATEGORY_LABEL[c] ?? c.replace(/_/g, ' ')


function StateBadge({ s }: { s: View }) {
  const m = STATE[s] ?? STATE.pending
  const topic: TopicId = SOURCE_STATE_TOPIC[s] ?? 'sources_page'
  return (
    <span className="inline-flex items-center gap-0.5 whitespace-nowrap">
      <span className="chip" title={m.hint} style={{ color: s === 'needs_config' ? toneText(m.color) : m.color, borderColor: m.color }}>{m.icon} {m.label}</span>
      <HelpTip id={topic} label={`What does "${m.label}" mean?`} />
    </span>
  )
}

const BASIS: Record<string, string> = {
  observations: 'newest observation', feed: 'newest feed item', events: 'newest event', status: 'status document', run: 'last successful run',
}

function Freshness({ r }: { r: SourceInfo }) {
  const f = r.freshness
  if (f === undefined) return <span className="text-ink-3" title="The API does not report data freshness yet">n/a</span>
  if (!f || !f.newest_data_at) {
    return <span style={{ color: f?.stale ? 'var(--stale)' : undefined }} className={f?.stale ? 'font-semibold' : 'text-ink-3'}>{f?.stale ? '◷ no data yet' : 'no data yet'}{f?.max_age_s ? <span className="font-normal text-ink-3"> / max {fmtDuration(f.max_age_s)}</span> : null}</span>
  }
  const ratio = f.age_s !== null && f.max_age_s ? Math.min(1, f.age_s / f.max_age_s) : null
  const col = f.stale ? 'var(--stale)' : 'var(--good)'
  return (
    <div className="min-w-[130px]" title={`Based on the ${BASIS[f.basis ?? ''] ?? f.basis ?? 'data'}: ${fmtDate(f.newest_data_at)}`}>
      <div className="flex items-baseline gap-1.5">
        <span className="font-semibold tnum" style={{ color: f.stale ? 'var(--stale)' : undefined }}>{f.stale ? '◷ ' : ''}{fmtDuration(f.age_s)} old</span>
        <span className="text-ink-3 tnum">/ max {fmtDuration(f.max_age_s)}</span>
      </div>
      {ratio !== null && (
        <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-surface-3" aria-hidden>
          <div className="h-full rounded-full" style={{ width: `${Math.max(4, ratio * 100)}%`, background: col }} />
        </div>
      )}
      <div className="mt-0.5 text-ink-3">{BASIS[f.basis ?? ''] ?? f.basis}: {fmtDate(f.newest_data_at)}</div>
      {r.expected_stale && f.stale && (
        <div className="mt-0.5 flex items-center gap-1 text-ink-2" title={r.expected_stale}>
          <span className="chip" style={{ color: 'var(--ink-2)', borderColor: 'var(--line-strong)', borderStyle: 'dashed' }}>expected</span>
          <span className="line-clamp-2">{r.expected_stale}</span>
          <HelpTip id="source_freshness" label="What is an expected stale source?" />
        </div>
      )}
    </div>
  )
}

function interval(s: number) {
  if (s >= 86400) return `${fmtNum(s / 86400, s % 86400 ? 1 : 0)} d`
  if (s >= 3600) return `${fmtNum(s / 3600, s % 3600 ? 1 : 0)} h`
  return `${Math.round(s / 60)} min`
}

function host(u: string) {
  try { return new URL(u).host } catch { return u }
}

interface Maintenance {
  last_prune?: string | null
  pruned?: { feed_items?: number; events?: number } | null
  last_vacuum?: string | null
  policy?: { feed_items_days?: number; official?: string; events_closed_days?: number; source_runs?: string; vacuum?: string } | null
}

function MaintenanceCard() {
  const q = useStatus<Maintenance>('maintenance')
  const m = q.data?.value
  return (
    <Card title="Housekeeping" help={<HelpTip id="retention" />} className="h-full" bodyClass="text-[12px]"
      footer={<AsOf ts={q.data?.updated_at} label="updated" source="status: maintenance" />}>
      {q.isLoading ? <Skeleton h={70} /> : q.isError ? <ErrorBox error={q.error} what="maintenance status" /> : !m ? (
        <p className="text-ink-3">The housekeeping job has not reported yet.</p>
      ) : (
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1">
          <dt className="text-ink-3">Last clean-up</dt>
          <dd>{m.last_prune ? <>{relTime(m.last_prune)} · removed {m.pruned?.feed_items ?? 0} feed items, {m.pruned?.events ?? 0} events</> : 'never'}</dd>
          <dt className="text-ink-3">Last compaction</dt>
          <dd>{m.last_vacuum ? relTime(m.last_vacuum) : 'never'}{m.policy?.vacuum ? <span className="text-ink-3"> ({m.policy.vacuum})</span> : null}</dd>
          <dt className="text-ink-3">Kept</dt>
          <dd>
            {m.policy?.feed_items_days ? <>news / posts {m.policy.feed_items_days} d</> : null}
            {m.policy?.official ? <>, official {m.policy.official}</> : null}
            {m.policy?.events_closed_days ? <>, closed events {m.policy.events_closed_days} d</> : null}
            {m.policy?.source_runs ? <>, runs: {m.policy.source_runs}</> : null}
          </dd>
        </dl>
      )}
    </Card>
  )
}

export default function Sources() {
  const q = useSources()
  const qc = useQueryClient()
  const access = useAccess()
  const f = useUrlFilters({ state: 'list', category: 'list', q: 'str' })
  const v = f.values
  const wide = useMedia('(min-width: 768px)')
  const [running, setRunning] = useState<Set<string>>(new Set())
  const [results, setResults] = useState<Record<string, RunResult>>({})
  const [verifyMsg, setVerifyMsg] = useState<string | null>(null)

  const refresh = () => qc.invalidateQueries()

  const verify = useMutation({
    mutationFn: () => api<RunResult[]>('/sources/verify', { method: 'POST' }),
    onMutate: () => setVerifyMsg(null),
    onSuccess: (r) => {
      const ok = r.filter((x) => x.ok).length
      setVerifyMsg(`Verification complete: ${ok} / ${r.length} sources responded correctly.`)
      setResults(Object.fromEntries(r.map((x) => [x.source, x])))
      refresh()
    },
    onError: (e) => setVerifyMsg(`Verification failed: ${e instanceof Error ? e.message : String(e)}`),
  })

  const runOne = async (name: string) => {
    setRunning((s) => new Set(s).add(name))
    try {
      const r = await api<RunResult>(`/sources/${encodeURIComponent(name)}/run`, { method: 'POST' })
      setResults((m) => ({ ...m, [name]: r }))
    } catch (e) {
      setResults((m) => ({ ...m, [name]: { source: name, ok: false, error: e instanceof Error ? e.message : String(e) } }))
    } finally {
      setRunning((s) => { const n = new Set(s); n.delete(name); return n })
      refresh()
    }
  }

  const rows = useMemo(() => q.data ?? [], [q.data])
  const text = v.q.toLowerCase()
  const matchQ = (r: SourceInfo) => !text || `${r.name} ${r.title} ${r.provider} ${r.category} ${r.description}`.toLowerCase().includes(text)
  const matchCat = (r: SourceInfo) => !v.category.length || v.category.includes(r.category)
  const matchState = (r: SourceInfo) => !v.state.length || v.state.includes(viewOf(r))
  // facet-style counts: each group ignores its own filter
  const stateCounts = useMemo(() => {
    const c: Record<string, number> = Object.fromEntries(STATES.map((s) => [s, 0]))
    for (const r of rows) if (matchQ(r) && matchCat(r)) c[viewOf(r)] = (c[viewOf(r)] ?? 0) + 1
    return c
  }, [rows, text, v.category]) // eslint-disable-line react-hooks/exhaustive-deps
  const catCounts = useMemo(() => {
    const c = new Map<string, number>()
    for (const r of rows) if (!c.has(r.category)) c.set(r.category, 0)
    for (const r of rows) if (matchQ(r) && matchState(r)) c.set(r.category, (c.get(r.category) ?? 0) + 1)
    return [...c.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  }, [rows, text, v.state]) // eslint-disable-line react-hooks/exhaustive-deps
  const scopeTotal = rows.filter((r) => matchQ(r) && matchCat(r)).length
  const hasF = rows.some((r) => r.freshness !== undefined)
  const shown = rows.filter((r) => matchQ(r) && matchCat(r) && matchState(r))
    .sort((a, b) => a.category.localeCompare(b.category) || a.title.localeCompare(b.title))

  const catOpts: Opt[] = catCounts.map(([c, n]) => ({ value: c, text: catLabel(c), count: n, title: c }))
  const human = [
    ...(v.state.length ? [`state: ${v.state.map((s) => STATE[s as View]?.label ?? s).join(' or ')}`] : []),
    ...(v.category.length ? [`category: ${v.category.map(catLabel).join(' or ')}`] : []),
    ...(v.q ? [`text: "${v.q}"`] : []),
  ]

  const toggleState = (s: View) => f.toggle('state', s)

  const sourceHelp = (r: SourceInfo) => (
    <HelpFor appId={r.name} id={sourceTopic(r.name)} kind="source" title={r.title} text={r.description} href={safeUrl(r.homepage) ? r.homepage : undefined} />
  )
  const errOf = (r: SourceInfo) => r.last_run?.error ?? (r.missing_config?.length ? `needs_config: ${r.missing_config.join(', ')}` : null)
  const runBtn = (r: SourceInfo, label: string, cls = '') => access.canWrite && (
    <button type="button" className={`btn !px-2 !py-1 !text-[12px] ${cls}`} disabled={running.has(r.name) || verify.isPending} onClick={() => runOne(r.name)}>
      {running.has(r.name) ? <span className="spin" /> : null} {label}
    </button>
  )
  const resLine = (res: RunResult | undefined) => res && (
    <div className="mt-1 text-ink-2">This run: {res.ok ? `ok, ${res.items ?? 0} items${res.ms ? ` in ${res.ms} ms` : ''}` : res.needs_config ? 'needs config' : `failed ${res.error ?? ''}`}</div>
  )

  return (
    <div className="space-y-3">
      <PageHeader title="Sources" help={<HelpTip id="sources_page" size="md" />}
        sub={<>Every collected source, its actual state and its last run. <b className="font-semibold text-ink">Fetch ok</b> and <b className="font-semibold text-ink">data fresh</b> are separate: a source can answer and still serve old data (shown as <span style={{ color: 'var(--stale)' }}>◷ stale</span> <HelpTip id="source_freshness" />). Two sources can also give different numbers for the same thing <HelpTip id="sources_disagree" />.</>}
        right={access.canWrite ? (
          <button type="button" data-tour="sources-verify" className="btn btn-primary" disabled={verify.isPending} onClick={() => verify.mutate()}>
            {verify.isPending && <span className="spin" />}
            {verify.isPending ? 'Verifying (1 to 2 min)...' : 'Verify all sources'}
          </button>
        ) : <span data-tour="sources-verify"><AdminOnlyNote what="running sources on demand" /></span>} />
      <PageGuide page="sources" />
      {verifyMsg && <div className="card px-4 py-2 text-[13px]" role="status">{verifyMsg}</div>}

      <div className="grid gap-3 min-[112.5rem]:grid-cols-[minmax(0,1fr)_400px] min-[137.5rem]:grid-cols-[minmax(0,1fr)_460px]">
        <div data-tour="sources-summary" className="grid grid-cols-2 gap-2 sm:grid-cols-4 sm:gap-3 xl:grid-cols-7" role="group" aria-label="Filter by state">
          <SummaryCard pressed={!v.state.length} onClick={() => f.set('state', [])} className="col-span-2 xl:col-span-1"
            label="All states" value={scopeTotal} title="Every source, whatever its state. Click a state card to list only those sources." help={<HelpTip id="sources_page" label="What are the source states?" />} />
          {STATES.map((s) => (
            <SummaryCard key={s} pressed={v.state.includes(s)} onClick={() => toggleState(s)} title={STATE[s].hint}
              label={<><span style={{ color: STATE[s].color }} aria-hidden>{STATE[s].icon}</span>{STATE[s].label}</>}
              value={s === 'stale' && !hasF ? '--' : stateCounts[s] ?? 0}
              valueColor={(stateCounts[s] ?? 0) > 0 && (s === 'error' || s === 'stale') ? STATE[s].color : undefined}
              help={<HelpTip id={SOURCE_STATE_TOPIC[s] ?? 'sources_page'} label={`What does "${STATE[s].label}" mean?`} />} />
          ))}
        </div>
        <div className="hidden h-full min-[112.5rem]:block"><MaintenanceCard /></div>
      </div>

      <FilterBar active={f.active} sticky={wide} onReset={f.reset}
        summary={q.data ? <><b className="text-ink">{shown.length}</b> of {rows.length} sources{v.state.length ? <> · state {v.state.map((s) => STATE[s as View]?.label ?? s).join(', ')} (use the cards above)</> : null}</> : null}>
        <FilterGroup label="Category" help={<HelpTip id="filters_sources_alerts" label="How do the source filters work?" />}>
          <ChipSelect options={catOpts} selected={v.category} onToggle={(x) => f.toggle('category', x)} limit={12} />
        </FilterGroup>
        <FilterGroup label="Search" className="w-full sm:w-auto sm:min-w-[240px] sm:flex-1">
          <SearchFilter value={v.q} onChange={(s) => f.set('q', s)} placeholder="Name, provider, description" label="Search sources" className="w-full" />
        </FilterGroup>
      </FilterBar>

      <Card pad={false} tour="sources-table" title={`${shown.length} ${shown.length === 1 ? 'source' : 'sources'}`} help={<HelpTip id="sources_page" />}
        right={<span className="text-[11px] text-ink-3">sorted by category, then name</span>}
        footer={<AsOf ts={rows.map((r) => r.last_run?.started_at ?? '').sort().at(-1) || null} label="latest run" source="/api/sources" />}>
        {q.isLoading ? <div className="p-4"><Skeleton h={240} /></div> : q.isError ? <div className="p-4"><ErrorBox error={q.error} what="sources" /></div> : !rows.length ? (
          <div className="p-4"><Empty what="No collectors registered" source="backend (app/collectors)" /></div>
        ) : !shown.length ? (
          <div className="p-4"><FilteredEmpty what="sources" filters={human} onReset={f.reset} total={rows.length} /></div>
        ) : (
          <>
            {/* below xl: one card per source (2 columns from md) */}
            <ul className="grid grid-cols-[minmax(0,1fr)] gap-px bg-line md:grid-cols-2 xl:hidden">
              {shown.map((r) => {
                const lr = r.last_run
                const err = errOf(r)
                return (
                  <li key={r.name} className="min-w-0 bg-surface p-3 text-[12px]">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex items-center gap-1 text-[13px] font-semibold text-ink">{r.title}{sourceHelp(r)}</div>
                        <div className="text-ink-3">{r.provider} · {catLabel(r.category)} · every {interval(r.interval_s)} <HelpTip id="sources_col_interval" label="What is the interval?" /></div>
                      </div>
                      <StateBadge s={viewOf(r)} />
                    </div>
                    {r.description && <p className="mt-1 line-clamp-2 text-ink-3" title={r.description}>{r.description}</p>}
                    <div className="mt-2 grid grid-cols-2 gap-2">
                      <div>
                        <div className="flex items-center gap-1 text-[11px] text-ink-3">Last run <HelpTip id="sources_col_last_run" label="What is the last run?" /></div>
                        {lr ? <div>{relTime(lr.started_at)}{lr.items !== null ? ` · ${lr.items} items` : ''}</div> : <div className="text-ink-3">never</div>}
                        {r.success_rate !== null && r.success_rate !== undefined && <div className="text-ink-3">{Math.round(r.success_rate * 100)} % success</div>}
                        {r.last_ok_at && viewOf(r) !== 'ok' && <div className="text-ink-3">last ok {relTime(r.last_ok_at)}</div>}
                      </div>
                      {hasF && (
                        <div>
                          <div className="flex items-center gap-1 text-[11px] text-ink-3">Data age <HelpTip id="source_freshness" label="What is data age?" /></div>
                          <Freshness r={r} />
                        </div>
                      )}
                    </div>
                    {err && <p className="mt-2 break-words" style={{ color: r.state === 'needs_config' ? 'var(--ink-2)' : 'var(--critical)' }}>{err}</p>}
                    {resLine(results[r.name])}
                    <div className="mt-2 flex flex-wrap items-center gap-3">
                      {safeUrl(r.homepage) && <a className="link" href={r.homepage} target="_blank" rel="noreferrer">website ↗</a>}
                      {safeUrl(r.endpoint) && <a className="link break-all" href={r.endpoint} target="_blank" rel="noreferrer">endpoint ({host(r.endpoint)}) ↗</a>}
                      {runBtn(r, 'Run now', 'ml-auto')}
                    </div>
                  </li>
                )
              })}
            </ul>
            <div className="hidden xl:block">
              <table className="w-full table-fixed text-[12px]">
                <colgroup>
                  <col className="w-[24%]" /><col className="w-[9%]" /><col className="w-[124px]" />{hasF && <col className="w-[14%]" />}
                  <col className="w-[11%]" /><col className="w-[64px]" /><col className="w-[76px]" /><col /><col className="w-[92px]" />
                </colgroup>
                <thead className="bg-surface-2 text-left text-ink-3">
                  <tr>
                    <Th>Source</Th>
                    <Th help={<HelpTip id="sources_col_interval" label="What is the interval?" />}>Category / interval</Th>
                    <Th help={<HelpTip id="sources_page" label="What do the states mean?" />}>State</Th>
                    {hasF && <Th help={<HelpTip id="source_freshness" label="What is data age?" />}>Data age</Th>}
                    <Th help={<HelpTip id="sources_col_last_run" label="What is the last run?" />}>Last run</Th>
                    <Th help={<HelpTip id="sources_col_items" label="What are items?" />}>Items</Th>
                    <Th help={<HelpTip id="sources_col_success" label="What is the success rate?" />}>Success</Th>
                    <Th>Error / detail</Th>
                    <Th>Links</Th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((r: SourceInfo) => {
                    const lr = r.last_run
                    const err = errOf(r)
                    return (
                      <tr key={r.name} className="border-t border-line align-top hover:bg-surface-2">
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-1 font-semibold text-ink">{r.title}{sourceHelp(r)}</div>
                          <div className="truncate text-ink-3">{r.provider} · <code>{r.name}</code></div>
                          {r.description && <div className="mt-0.5 line-clamp-2 text-ink-3" title={r.description}>{r.description}</div>}
                        </td>
                        <td className="px-3 py-2 text-ink-2">{catLabel(r.category)}<div className="text-ink-3">every {interval(r.interval_s)}</div></td>
                        <td className="px-3 py-2"><StateBadge s={viewOf(r)} /></td>
                        {hasF && <td className="px-3 py-2"><Freshness r={r} /></td>}
                        <td className="px-3 py-2">
                          {lr ? <><div>{relTime(lr.started_at)}</div><div className="text-ink-3">{fmtDate(lr.started_at)}</div></> : <span className="text-ink-3">never</span>}
                          {lr && (lr.latency_ms !== null || lr.http_status) ? <div className="text-ink-3 tnum">{lr.http_status ? `HTTP ${lr.http_status}` : ''}{lr.latency_ms !== null && lr.latency_ms !== undefined ? ` · ${fmtNum(lr.latency_ms, 0)} ms` : ''}</div> : null}
                          {r.last_ok_at && viewOf(r) !== 'ok' && <div className="text-ink-3">last ok {relTime(r.last_ok_at)}</div>}
                        </td>
                        <td className="px-3 py-2 tnum">{lr?.items ?? '--'}</td>
                        <td className="px-3 py-2 tnum">{r.success_rate === null || r.success_rate === undefined ? '--' : `${Math.round(r.success_rate * 100)} %`}</td>
                        <td className="px-3 py-2 [overflow-wrap:anywhere]" style={{ color: err ? (r.state === 'needs_config' ? 'var(--ink-2)' : 'var(--critical)') : undefined }}>
                          {err ?? <span className="text-ink-3">--</span>}
                          {resLine(results[r.name])}
                        </td>
                        <td className="px-3 py-2">
                          {safeUrl(r.endpoint) && <div><a className="link" href={r.endpoint} target="_blank" rel="noreferrer" title={r.endpoint}>endpoint ↗</a></div>}
                          {safeUrl(r.homepage) && <div><a className="link" href={r.homepage} target="_blank" rel="noreferrer">website ↗</a></div>}
                          {runBtn(r, 'Run', 'mt-1.5')}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
      <div className="min-[112.5rem]:hidden"><MaintenanceCard /></div>
      <p className="text-[11px] text-ink-3">
        Model-based sources (forecasts, <Term id="era5">reanalysis</Term>, <Term id="cams">air-quality models</Term>) are estimates, not measurements <HelpTip id="model_vs_observation" />.
      </p>
    </div>
  )
}

function Th({ children, help }: { children: ReactNode; help?: ReactNode }) {
  return (
    <th scope="col" className="px-3 py-2 font-medium">
      <span className="inline-flex items-center gap-1">{children}{help}</span>
    </th>
  )
}

function SummaryCard({ pressed, onClick, label, value, help, title, valueColor, className = '' }: {
  pressed: boolean; onClick: () => void; label: ReactNode; value: ReactNode; help: ReactNode; title?: string; valueColor?: string; className?: string
}) {
  // the hint is shown under the number where there is room (it is also the tooltip)
  return (
    <div className={`card relative ${pressed ? 'ring-2 ring-[var(--accent)]' : ''} ${className}`}>
      <button type="button" aria-pressed={pressed} onClick={onClick} title={title} className="flex h-full w-full flex-col justify-start p-2.5 text-left sm:p-3">
        <div className="flex items-center gap-1.5 pr-5 text-[12px] leading-tight text-ink-2">{label}</div>
        <div className="text-xl font-semibold tnum sm:text-2xl" style={{ color: valueColor }}>{value}</div>
        {title && <div className="mt-1 hidden text-[11px] leading-snug text-ink-3 xl:block">{title}</div>}
      </button>
      <span className="absolute top-2 right-2">{help}</span>
    </div>
  )
}

/** true when the media query matches (sticky filter bars only where they do not eat the phone screen). */
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
