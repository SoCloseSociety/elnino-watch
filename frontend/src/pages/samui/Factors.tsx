/** Factor cards with URL-synced filters by level and by value kind. */
import { useEffect, useMemo, useState } from 'react'
import type { FactorInput, RiskFactor } from '../../api/types'
import { ChipSelect, FilterBar, FilteredEmpty, FilterGroup } from '../../components/filters'
import { AsOf, KindBadge, LevelBadge } from '../../components/ui'
import { FACTOR_TOPIC, HelpFor, HelpTip, VALUE_KIND_TOPIC } from '../../help'
import { ageMs, fmtDateTz, fmtUnit, LEVELS, levelMeta, relTime, tzOf, VALUE_KIND, type ValueKind } from '../../lib/format'
import { safeUrl } from '../../lib/geo'
import { useUrlFilters } from '../../lib/urlFilters'
import { factorKindKey, fmtVal, KIND_ORDER, kindLabel, TZ, unitOf, UnknownKind, valueKind } from './common'

/** "How this was computed": every number the factor used, each with its own kind, date and source (round 3). */
function FactorInputs({ inputs }: { inputs: FactorInput[] }) {
  return (
    <details className="mb-1.5 text-[11px] text-ink-2">
      <summary className="cursor-pointer py-1 text-ink-3">
        How this was computed ({inputs.length} {inputs.length === 1 ? 'input' : 'inputs'}) <HelpTip id="factor_inputs" label="What are the inputs?" />
      </summary>
      <ul className="mt-1 space-y-1.5">
        {inputs.map((x, i) => {
          const tz = tzOf(x.tz, TZ)
          const when = x.valid_for ?? x.as_of ?? x.retrieved_at
          const href = x.url?.startsWith('/') ? x.url : safeUrl(x.url)
          return (
            <li key={i} className="rounded border border-line p-1.5">
              <div className="flex flex-wrap items-baseline gap-x-1.5">
                <span className="text-ink">{x.name}</span>
                <b className="tnum text-ink">{fmtVal(x.value as number | string | null, x.unit as string | null)}{unitOf(x) ? ` ${unitOf(x)}` : ''}</b>
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-ink-3">
                {x.kind ? <KindBadge kind={x.kind} validFor={when} tz={tz} compact help={false} /> : null}
                {when && <span>{x.kind === 'forecast' ? 'for' : 'valid for'} {fmtDateTz(when, tz)}</span>}
                {x.issued_at && <span>· issued {fmtDateTz(x.issued_at, 'UTC')}</span>}
                {x.retrieved_at && <span title={x.retrieved_at}>· fetched {relTime(x.retrieved_at)}</span>}
                {x.source && <span>· {href ? <a className="link" href={href} target="_blank" rel="noreferrer">{x.source} ↗</a> : x.source}</span>}
              </div>
              {x.note && <div className="mt-0.5 text-ink-3">{fmtUnit(x.note)}</div>}
            </li>
          )
        })}
      </ul>
    </details>
  )
}

function FactorCard({ f, critical = false }: { f: RiskFactor; critical?: boolean }) {
  const m = levelMeta(f.level, f.level_key)
  const kind = valueKind(f)
  // round 3: as_of = observed_at or issued_at or retrieved_at (forecasts have no observed_at)
  const when = f.as_of ?? f.observed_at ?? f.retrieved_at ?? null
  const age = ageMs(f.observed_at)
  // the engine knows each factor's expected cadence (a monthly index is weeks old by design): trust its flag
  const stale = f.stale !== undefined && f.stale !== null ? f.stale === true : kind !== 'forecast' && age !== null && age > 48 * 3600000
  const unavailable = f.level === null || f.level === undefined
  const unit = unitOf(f)
  const tz = tzOf(f.tz, TZ)
  const validFor = f.valid_for ?? (kind === 'forecast' ? when : null)
  const asOfLabel = f.observed_at ? 'data time' : f.issued_at ? 'issued' : 'fetched'
  return (
    <article className="card flex h-full min-w-0 flex-col p-3" style={{ borderLeft: `4px solid ${m?.color ?? 'var(--line-strong)'}` }}>
      <div className="flex items-start justify-between gap-2">
        <h3 className="flex min-w-0 items-center gap-1.5 text-[13px] font-semibold">
          <span className="min-w-0">{f.label}</span>
          <HelpFor id={FACTOR_TOPIC[f.id] ?? null} appId={f.id} title={f.label} text={f.explanation} href={f.url} kind="factor" />
        </h3>
        {unavailable
          ? <span className="chip shrink-0" style={{ color: critical ? 'var(--critical)' : 'var(--ink-2)', borderColor: 'currentColor', borderStyle: 'dashed' }}>? no data{critical ? ' · critical' : ''}</span>
          : <span className="shrink-0"><LevelBadge level={f.level} levelKey={f.level_key} /></span>}
      </div>
      {unavailable ? (
        <p className="mt-2 text-[13px] text-ink-2">
          {critical
            ? 'No data from this source. It is a critical factor, so the overall level cannot be computed until it responds.'
            : 'No data from this source. The level is computed without it until it responds.'}
        </p>
      ) : (
        <>
          <div className="mt-1 flex flex-wrap items-baseline gap-x-1.5">
            <span className="text-xl font-semibold tnum">{fmtVal(f.value, f.unit)}</span>
            {unit && <span className="text-[12px] text-ink-3">{unit}</span>}
          </div>
          {(f.value_label ?? f.summary) && <p className="text-[12px] text-ink-2">{fmtUnit(f.value_label ?? f.summary)}</p>}
        </>
      )}
      <div className="mt-1 flex flex-wrap items-center gap-1.5">
        {kind ? <KindBadge kind={kind} ts={when} validFor={validFor} tz={tz} /> : <><UnknownKind /><HelpTip id="model_vs_observation" label="Observed, model or forecast: why it matters" /></>}
        {critical && !unavailable && <span className="chip" title="The overall level cannot be computed without this factor">critical</span>}
      </div>
      {f.threshold !== null && f.threshold !== undefined && f.threshold !== '' && (
        <div className="mt-1.5 text-[12px] text-ink-2">Threshold: <span className="tnum">{fmtUnit(String(f.threshold))}</span></div>
      )}
      {f.explanation && <p className="mt-1.5 text-[12px] leading-snug text-ink-2">{fmtUnit(f.explanation)}</p>}
      <div className="mt-auto pt-2">
        {f.inputs && f.inputs.length > 0 && <FactorInputs inputs={f.inputs} />}
        {f.steps && Object.keys(f.steps).length > 0 && (
          <details className="mb-1.5 text-[11px] text-ink-2">
            <summary className="cursor-pointer py-1 text-ink-3">Thresholds by level</summary>
            <ul className="mt-1 space-y-0.5">
              {Object.entries(f.steps).map(([lv, t]) => {
                const lm = levelMeta(Number(lv))
                return <li key={lv} className="flex gap-1.5"><span style={{ color: lm?.color }}>{lm?.icon}</span><span><span className="font-semibold">{lv} {lm?.label}:</span> {fmtUnit(t)}</span></li>
              })}
            </ul>
          </details>
        )}
        {f.next && <p className="mb-1 text-[11px] text-ink-2"><span className="text-ink-3">Next threshold:</span> {fmtUnit(f.next)}</p>}
        {stale && <div className="mb-1 text-[11px] font-semibold" style={{ color: 'var(--warning)' }}>▲ Stale data ({relTime(f.observed_at ?? when)}{f.stale ? '' : ', over 48 h'}) <HelpTip id="stale_data" /></div>}
        <div className="border-t border-line pt-1.5">
          {when
            ? <AsOf ts={when} label={asOfLabel} tz={tz} source={f.source} href={f.url?.startsWith('/') ? f.url : safeUrl(f.url)} />
            : <AsOf ts={null} source={f.source} href={f.url?.startsWith('/') ? f.url : safeUrl(f.url)} />}
        </div>
      </div>
    </article>
  )
}

/** Columns that fill each row as evenly as possible (9 cards on room for 7 -> 5 + 4, not 7 + 2). */
function useBalancedCols(n: number, min = 300, gap = 12) {
  const [el, ref] = useState<HTMLDivElement | null>(null)
  const [w, setW] = useState(0)
  useEffect(() => {
    if (!el) return
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [el])
  const max = Math.max(1, Math.floor((w + gap) / (min + gap)))
  const cols = n <= 0 ? 1 : Math.ceil(n / Math.ceil(n / max))
  return [ref, w ? cols : null] as const
}

export function FactorsSection({ factors, critical, evaluatedAt }: { factors: RiskFactor[]; critical: Set<string>; evaluatedAt?: string | null }) {
  const f = useUrlFilters({ level: 'list', kind: 'list' }, 'f_')
  const lvlKey = (x: RiskFactor) => (x.level === null || x.level === undefined ? 'nodata' : levelMeta(x.level, x.level_key)?.key ?? 'nodata')
  const levelCounts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const x of factors) c[lvlKey(x)] = (c[lvlKey(x)] ?? 0) + 1
    return c
  }, [factors])
  const kindCounts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const x of factors) c[factorKindKey(x)] = (c[factorKindKey(x)] ?? 0) + 1
    return c
  }, [factors])
  const shown = factors.filter((x) =>
    (!f.values.level.length || f.values.level.includes(lvlKey(x))) && (!f.values.kind.length || f.values.kind.includes(factorKindKey(x))))
  const levelOpts = [
    ...LEVELS.map((l, i) => ({ value: l.key, label: `${i} ${l.label}`, text: l.label, color: l.color, count: levelCounts[l.key] ?? 0 })),
    ...(levelCounts.nodata ? [{ value: 'nodata', label: 'No data', text: 'No data', count: levelCounts.nodata, color: 'var(--ink-3)' }] : []),
  ]
  const kindOpts = KIND_ORDER.map((k) => ({
    value: k, label: kindLabel(k), count: kindCounts[k] ?? 0,
    color: k === 'unknown' ? 'var(--ink-3)' : VALUE_KIND[k as ValueKind].color,
    title: k === 'unknown' ? 'The source does not say whether the value is measured, modelled or forecast' : VALUE_KIND[k as ValueKind].hint,
    help: k !== 'unknown' && k !== 'observed' && k !== 'model_analysis' ? <HelpTip id={VALUE_KIND_TOPIC[k]} label={`What does "${kindLabel(k)}" mean?`} /> : undefined,
  }))
  const [gridRef, cols] = useBalancedCols(shown.length)
  const human = [
    ...f.values.level.map((v) => `level: ${levelOpts.find((o) => o.value === v)?.text ?? v}`),
    ...f.values.kind.map((v) => `kind: ${kindLabel(v)}`),
  ]
  return (
    <section data-tour="samui-factors" aria-labelledby="factors-h" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="factors-h" className="flex items-center gap-1.5 text-[15px] font-semibold">
          Factors ({factors.length}) <HelpTip id="risk_factors" />
        </h2>
        <AsOf ts={evaluatedAt} label="evaluated" tz={TZ} source="Koh Samui risk engine" href="/api/local" />
      </div>
      <FilterBar active={f.active} onReset={f.reset} summary={`${shown.length} of ${factors.length} factors`}>
        <FilterGroup label="Level" help={<HelpTip id="risk_levels" />}>
          <ChipSelect options={levelOpts} selected={f.values.level} onToggle={(v) => f.toggle('level', v)} />
        </FilterGroup>
        <FilterGroup label="Kind of value" help={<HelpTip id="model_vs_observation" label="Observed, model or forecast?" />}>
          <ChipSelect options={kindOpts} selected={f.values.kind} onToggle={(v) => f.toggle('kind', v)} />
        </FilterGroup>
      </FilterBar>
      {!factors.length ? <p className="text-[13px] text-ink-3">No factors returned.</p> : !shown.length ? (
        <FilteredEmpty what="factors" filters={human} onReset={f.reset} total={factors.length}>
          <p className="mt-1 text-[12px]">Counts on each chip show how many factors have that level or kind right now; a chip at 0 cannot match.</p>
        </FilteredEmpty>
      ) : (
        <div ref={gridRef} className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,300px),1fr))] gap-3"
          style={cols ? { gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` } : undefined}>
          {shown.map((x) => <FactorCard key={x.id} f={x} critical={critical.has(x.id)} />)}
        </div>
      )}
    </section>
  )
}
