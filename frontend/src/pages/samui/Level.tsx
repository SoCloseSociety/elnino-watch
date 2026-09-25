/** Overall level block: gauge, headline, rules fired, season, coverage, actions and triggers. */
import type { Coverage, RiskFactor } from '../../api/types'
import { AsOf, LevelBadge } from '../../components/ui'
import { HelpFor, HelpTip, Term } from '../../help'
import { fmtUnit, LEVELS, levelMeta, riskFloor } from '../../lib/format'
import { TZ, type LocalRiskX } from './common'

function Gauge({ level, floor = null }: { level: number | null; floor?: number | null }) {
  // semicircle, 5 equal segments
  const cx = 110, cy = 105, r = 86, w = 20
  const seg = (i: number) => {
    const a0 = Math.PI - (i / 5) * Math.PI + 0.012
    const a1 = Math.PI - ((i + 1) / 5) * Math.PI - 0.012
    const p = (a: number, rr: number) => `${cx + rr * Math.cos(a)} ${cy - rr * Math.sin(a)}`
    return `M ${p(a0, r)} A ${r} ${r} 0 0 1 ${p(a1, r)} L ${p(a1, r - w)} A ${r - w} ${r - w} 0 0 0 ${p(a0, r - w)} Z`
  }
  const ang = level === null ? null : Math.PI - ((level + 0.5) / 5) * Math.PI
  const m = levelMeta(level)
  const fm = level === null && floor !== null ? levelMeta(floor) : null
  return (
    <svg viewBox="0 0 220 130" className="w-full max-w-[280px]" role="img"
      aria-label={m ? `Level ${level}: ${m.label}` : `Level unknown${fm ? `, at least ${fm.label}` : ''}`}>
      <defs>
        <pattern id="unk-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" fill="var(--surface-2)" />
          <line x1="0" y1="0" x2="0" y2="6" stroke="var(--ink-3)" strokeWidth="2" opacity="0.5" />
        </pattern>
      </defs>
      {LEVELS.map((l, i) => {
        if (level === null) {
          const possible = floor === null || i >= floor
          return <path key={l.key} d={seg(i)} fill={possible ? (i === floor ? l.color : 'url(#unk-hatch)') : l.color} opacity={possible ? (i === floor ? 0.55 : 1) : 0.12} />
        }
        return <path key={l.key} d={seg(i)} fill={l.color} opacity={i === level ? 1 : 0.28} />
      })}
      {ang !== null && (
        <>
          <line x1={cx} y1={cy} x2={cx + (r - w - 8) * Math.cos(ang)} y2={cy - (r - w - 8) * Math.sin(ang)} stroke="var(--ink)" strokeWidth="3" strokeLinecap="round" />
          <circle cx={cx} cy={cy} r="6" fill="var(--ink)" />
        </>
      )}
      <text x={cx} y={cy - 6} textAnchor="middle" fontSize={m ? 0 : 30} fontWeight="700" fill="var(--ink-2)">{m ? '' : '?'}</text>
      <text x={cx} y={cy + 22} textAnchor="middle" fontSize="13" fontWeight="700" fill={m?.color ?? 'var(--ink-2)'}>
        {m ? `${level} · ${m.label}` : fm ? `Unknown · at least ${fm.label}` : 'Unknown: data insufficient'}
      </text>
    </svg>
  )
}

function CoverageBar({ c, factors }: { c: Coverage; factors: RiskFactor[] }) {
  const label = (id: string) => factors.find((f) => f.id === id)?.label ?? id
  const pct = c.total ? (c.with_data / c.total) * 100 : 0
  const crit = c.critical_missing ?? []
  const other = (c.missing ?? []).filter((id) => !crit.includes(id))
  const full = c.with_data >= c.total
  return (
    <div className="rounded-lg border border-line bg-surface-2 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-[12px]">
        <span className="flex items-center gap-1.5 font-semibold text-ink-2">Data coverage <HelpTip id="data_coverage" /><HelpTip id="local_coverage" label="How is coverage computed?" /></span>
        <span className="tnum text-ink-2"><b className="text-ink">{c.with_data} / {c.total}</b> factors with data</span>
      </div>
      <div className="mt-1.5 flex h-2 overflow-hidden rounded-full bg-surface-3" role="meter" aria-valuemin={0} aria-valuemax={c.total} aria-valuenow={c.with_data}
        aria-label={`${c.with_data} of ${c.total} factors with data`}>
        <div className="h-full" style={{ width: `${pct}%`, background: full ? 'var(--good)' : crit.length ? 'var(--critical)' : 'var(--warning)' }} />
      </div>
      {crit.length > 0 && (
        <p className="mt-2 text-[12px]" style={{ color: 'var(--critical)' }}>
          <b>■ Critical, missing:</b> <span className="text-ink">{crit.map(label).join(', ')}</span>
        </p>
      )}
      {other.length > 0 && <p className="mt-1 text-[12px] text-ink-2"><b className="font-semibold">Missing:</b> {other.map(label).join(', ')}</p>}
      {c.stale?.length ? <p className="mt-1 text-[12px]" style={{ color: 'var(--stale)' }}><b>◷ Stale data:</b> <span className="text-ink">{c.stale.map(label).join(', ')}</span></p> : null}
      {full && !c.stale?.length && (
        <p className="mt-1.5 text-[12px] text-ink-2">
          All factors have current data{c.critical?.length ? `. Critical (the level cannot be computed without them): ${c.critical.map(label).join(', ')}` : ''}.
        </p>
      )}
    </div>
  )
}

/** "R1 max of factors (enso)" -> readable text + the factor labels it names. */
function RuleRow({ rule, factors }: { rule: string; factors: RiskFactor[] }) {
  const m = rule.match(/^(R\d+)\s+(.*)$/)
  const code = m?.[1]
  let text = m?.[2] ?? rule
  text = text.replace(/\(([a-z_,\s]+)\)/g, (_all, ids: string) =>
    `(${ids.split(',').map((id) => factors.find((f) => f.id === id.trim())?.label ?? id.trim()).join(', ')})`)
  return (
    <li className="flex items-start gap-2 text-[13px]">
      {code && <span className="chip shrink-0 font-mono">{code}</span>}
      <span className="min-w-0">{fmtUnit(text)}</span>
    </li>
  )
}

export function LevelPanel({ r, onExit }: { r: LocalRiskX; onExit: () => void }) {
  const m = levelMeta(r.level, r.level_key)
  const unknown = r.level === null || r.level === undefined || r.level_key === 'unknown'
  const floor = riskFloor(r)
  const floorN = floor ? (floor.level ?? levelMeta(null, floor.key)?.n ?? null) : null
  const factors = r.factors ?? []
  const actions = r.actions ?? []
  const triggers = r.triggers ?? []
  const rules = r.rules ?? []
  const sc = r.season_context
  const floorMeta = levelMeta(r.level_floor ?? null, r.level_floor_key ?? null)

  return (
    <section className="card grid gap-4 p-4 min-[106.25rem]:grid-cols-[minmax(0,1.5fr)_minmax(0,2fr)]" aria-label="Overall level">
      <div data-tour="samui-level" className="grid min-w-0 gap-4 md:grid-cols-[230px_minmax(0,1fr)]">
        <div className="flex flex-col items-center">
          <div className="mb-1 flex items-center gap-1.5 self-stretch text-[12px] font-semibold tracking-wide text-ink-3 uppercase">
            Overall level <HelpTip id="risk_levels" />
          </div>
          <Gauge level={unknown ? null : r.level} floor={unknown ? floorN : null} />
          <ol className="mt-1 flex flex-wrap justify-center gap-x-2 gap-y-1 text-[11px] text-ink-2">
            {LEVELS.map((l, i) => <li key={l.key} className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full" style={{ background: l.color }} />{i} {l.label}</li>)}
            <li className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full border border-dashed border-ink-3" />? Unknown <HelpTip id="unknown_level" label="What does Unknown mean?" /></li>
          </ol>
        </div>
        <div className="min-w-0 space-y-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <LevelBadge level={unknown ? null : r.level} levelKey={unknown ? null : r.level_key} size="lg" floor={unknown ? floor : null} />
              {floorMeta && (
                <span className="inline-flex items-center gap-1 text-[12px] text-ink-2">
                  floor: <b style={{ color: floorMeta.color }}>{floorMeta.label}</b> <HelpTip id="local_level_floor" />
                </span>
              )}
            </div>
            <p className="mt-2 text-lg leading-snug font-semibold">{r.headline ?? 'No summary.'}</p>
            {unknown && (
              <div role="alert" className="mt-2 rounded-lg border px-3 py-2 text-[13px]" style={{ borderColor: 'var(--warning)', background: 'color-mix(in srgb, var(--warning) 10%, transparent)' }}>
                <b style={{ color: 'var(--warning)' }}>▲ Level unknown: data insufficient.</b>{' '}
                <span className="text-ink">
                  Critical factors have no data, so the watch cannot say how serious things are. This is <b>not</b> an all-clear.
                  {floor && levelMeta(floor.level, floor.key) ? <> The factors that do have data already justify at least <b>{levelMeta(floor.level, floor.key)!.label}</b>.</> : null}
                  {r.unknown_since ? <> Unknown since {r.unknown_since}.</> : null}
                </span>
              </div>
            )}
            <AsOf className="mt-1" ts={r.evaluated_at} label="evaluated" tz={TZ} staleMs={6 * 3600000}
              source={`Koh Samui risk engine, ${factors.length} factors, level = highest of the available factors`} href="/api/local" />
          </div>

          <div>
            <h2 className="mb-1 flex items-center gap-1.5 text-[12px] font-semibold tracking-wide text-ink-3 uppercase">Rules fired <HelpTip id="risk_rules" /></h2>
            {rules.length ? <ul className="space-y-1">{rules.map((x, i) => <RuleRow key={i} rule={x} factors={factors} />)}</ul>
              : <p className="text-[12px] text-ink-3">The engine did not report which rules set the level.</p>}
          </div>

          {(r.season || sc) && (
            <div className="rounded-lg border border-line p-3">
              <h2 className="mb-1 flex flex-wrap items-center gap-1.5 text-[12px] font-semibold tracking-wide text-ink-3 uppercase">
                Season now <HelpTip id="samui_seasons" /><HelpTip id="local_season_logic" label="How does the season change the rules?" />
              </h2>
              {sc?.label && <p className="text-[13px] font-semibold text-ink">{sc.label}</p>}
              {r.season && <p className="text-[13px] text-ink-2">{fmtUnit(r.season)}</p>}
              {sc?.note && <p className="mt-1 text-[12px] text-ink-2">{fmtUnit(sc.note)}</p>}
              {sc?.focus?.length ? (
                <p className="mt-1.5 flex flex-wrap items-center gap-1 text-[12px] text-ink-3">
                  Factors to watch this season:
                  {sc.focus.map((id) => <span key={id} className="chip">{factors.find((f) => f.id === id)?.label ?? id}</span>)}
                </p>
              ) : null}
            </div>
          )}

          {r.coverage && <CoverageBar c={r.coverage} factors={factors} />}
        </div>
      </div>

      <div className="grid min-w-0 gap-4 lg:grid-cols-2">
        <div data-tour="samui-actions" className="min-w-0 rounded-lg border border-line p-3">
          <h2 className="mb-1.5 flex items-center gap-1.5 text-[13px] font-semibold tracking-wide text-ink-2 uppercase">
            What to do now <HelpTip id="risk_levels" label="What does each level ask me to do?" />
          </h2>
          {actions.length ? (
            <ul className="space-y-1.5 text-[14px]">
              {actions.map((a, i) => <li key={i} className="flex gap-2"><span aria-hidden style={{ color: levelMeta(null, a.level_key)?.color ?? m?.color }}>▸</span><span className="min-w-0">{fmtUnit(a.text)}</span></li>)}
            </ul>
          ) : <p className="text-[13px] text-ink-3">No actions provided by the engine.</p>}
        </div>
        <div data-tour="samui-triggers" className="min-w-0 rounded-lg border border-line p-3">
          <h2 className="mb-1.5 flex items-center gap-1.5 text-[13px] font-semibold tracking-wide text-ink-2 uppercase">
            What would raise the level <HelpTip id="risk_rules" label="How do triggers work?" />
          </h2>
          {triggers.length ? (
            <ul className="space-y-1.5 text-[14px]">
              {triggers.map((t, i) => {
                const tm = levelMeta(null, t.level_key)
                const fid = (t as { factor?: string }).factor
                const f = fid ? factors.find((x) => x.id === fid) : undefined
                return (
                  <li key={i} className="flex gap-2">
                    {tm ? <span className="chip shrink-0 self-start" style={{ color: tm.color, borderColor: tm.color }}>{tm.label}</span> : <span aria-hidden>▸</span>}
                    <span className="min-w-0">{fmtUnit(t.text)}</span>
                    {fid && <HelpFor appId={fid} title={f?.label ?? fid} text={f?.explanation} kind="factor" />}
                  </li>
                )
              })}
            </ul>
          ) : <p className="text-[13px] text-ink-3">No triggers provided.</p>}
          <button type="button" className="btn mt-3" onClick={onExit}>Open the exit plan ›</button>
          <p className="mt-1 text-[11px] text-ink-3">The level is the highest of the factor levels, adjusted by the rules above. See <Term id="risk_rules">how the rules work</Term>.</p>
        </div>
      </div>
    </section>
  )
}
