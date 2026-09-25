import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ageMs, fmtDate, fmtDateTz, inferKind, levelMeta, relTime, toneText, VALUE_KIND, type DisplayTz } from '../lib/format'
import { HelpTip } from '../help/HelpTip'
import { VALUE_KIND_TOPIC } from '../help/content'

export function Card({ title, help, right, children, footer, className = '', bodyClass = '', pad = true, id, tour }: {
  title?: ReactNode
  /** HelpTip (or HelpFor) shown right after the title */
  help?: ReactNode
  right?: ReactNode
  children: ReactNode
  /** pinned to the bottom of the card (as-of / source line), so side-by-side cards line up */
  footer?: ReactNode
  className?: string
  bodyClass?: string
  pad?: boolean
  id?: string
  /** data-tour target */
  tour?: string
}) {
  return (
    <section id={id} data-tour={tour} className={`card flex min-w-0 flex-col ${className}`}>
      {(title || right) && (
        <header className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1 border-b border-line px-4 py-2.5">
          {title && <h2 className="flex min-w-0 items-center gap-1.5 text-[13px] font-semibold tracking-wide text-ink-2 uppercase">{title}{help}</h2>}
          {right && <div className="flex flex-wrap items-center gap-2">{right}</div>}
        </header>
      )}
      <div className={`min-h-0 flex-1 ${pad ? 'p-4' : ''} ${bodyClass}`}>{children}</div>
      {footer && <div className="border-t border-line px-4 py-2">{footer}</div>}
    </section>
  )
}

/**
 * Badge telling what kind of value this is: Observed / Forecast / Model / Reanalysis / Bulletin,
 * with the date it is valid for and its time zone when known.
 */
export function KindBadge({ kind, ts, validFor, tz = 'UTC', compact = false, help = true }: {
  kind?: string | null
  /** timestamp of the value (used to infer "forecast" when no kind is sent) */
  ts?: string | null
  validFor?: string | null
  tz?: DisplayTz
  compact?: boolean
  help?: boolean
}) {
  const k = inferKind(kind, validFor ?? ts)
  if (!k) return null
  const m = VALUE_KIND[k]
  const when = validFor ?? (k === 'forecast' ? ts : null)
  return (
    <span className="inline-flex items-center gap-1">
      <span className="chip" title={`${m.hint}${when ? `. Valid for ${fmtDateTz(when, tz)}` : ''}`} style={{ color: toneText(m.color), borderColor: m.color }}>
        <span aria-hidden>{m.icon}</span> {m.label}
        {when && !compact ? <span className="font-normal text-ink-2"> · for {fmtDateTz(when, tz)}</span> : null}
      </span>
      {help && <HelpTip id={VALUE_KIND_TOPIC[k]} label={`What does "${m.label}" mean?`} />}
    </span>
  )
}

/** "as of <date> -- Source" line; marks stale values. */
export function AsOf({ ts, source, href, staleMs, label = 'as of', className = '', tz, kind, validFor, stale: staleIn }: {
  ts?: string | null; source?: string | null; href?: string | null; staleMs?: number; label?: string; className?: string
  /** show the time in this zone (ICT for Samui, UTC for global); default: browser time */
  tz?: DisplayTz
  /** value kind (observed | forecast | model_analysis | reanalysis | bulletin), badge shown first */
  kind?: string | null
  validFor?: string | null
  /** force the stale mark (e.g. backend `stale: true`) */
  stale?: boolean
}) {
  const age = ageMs(ts)
  const future = age !== null && age < 0
  const stale = staleIn === true || (!future && staleMs !== undefined && age !== null && age > staleMs)
  return (
    <div className={`flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] text-ink-3 ${className}`}>
      {(kind || validFor || future) && <KindBadge kind={kind} ts={ts} validFor={validFor} tz={tz} compact />}
      {ts ? (
        <span title={ts}>
          {label} {tz ? fmtDateTz(ts, tz) : fmtDate(ts)}
        </span>
      ) : (
        <span>date not reported</span>
      )}
      {stale && <span className="inline-flex items-center gap-1"><span className="chip" style={{ color: 'var(--warning)', borderColor: 'var(--warning)' }}>▲ stale ({relTime(ts)})</span><HelpTip id="stale_data" label="What does stale mean?" /></span>}
      {source && (
        <>
          <span aria-hidden>·</span>
          {href ? (
            <a className="link" href={href} target="_blank" rel="noreferrer">
              {source} ↗
            </a>
          ) : (
            <span>{source}</span>
          )}
        </>
      )}
    </div>
  )
}

export function Empty({ what, source, children }: { what: string; source?: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line-strong p-4 text-[13px] text-ink-2">
      <p className="font-medium text-ink">{what}</p>
      <p className="mt-1">
        {source ? <>Fed by <b>{source}</b>. </> : null}
        No data received yet. Collection status is on the{' '}
        <Link className="link" to="/sources">
          Sources
        </Link>
        {' '}page.
      </p>
      {children}
    </div>
  )
}

export function ErrorBox({ error, what }: { error: unknown; what: string }) {
  const msg = error instanceof Error ? error.message : String(error)
  return (
    <div className="rounded-lg border p-3 text-[13px]" style={{ borderColor: 'var(--critical)', color: 'var(--ink)' }}>
      <b style={{ color: 'var(--critical)' }}>■ Error</b> {what}: <span className="text-ink-2">{msg}</span>
    </div>
  )
}

export function Skeleton({ h = 80, className = '' }: { h?: number; className?: string }) {
  return <div className={`skeleton ${className}`} style={{ height: h }} />
}

export function LevelBadge({ level, levelKey, size = 'sm', floor }: {
  level: number | null | undefined; levelKey?: string | null; size?: 'sm' | 'lg'
  /** when the level is unknown: the minimum level the known factors justify */
  floor?: { level: number | null | undefined; key?: string | null } | null
}) {
  const m = levelMeta(level, levelKey)
  if (!m) {
    const f = floor ? levelMeta(floor.level, floor.key) : null
    return (
      <span className={`chip ${size === 'lg' ? 'text-sm !px-3 !py-1' : ''}`}
        style={{ color: 'var(--ink-2)', borderColor: 'var(--line-strong)', borderStyle: 'dashed' }}
        title="Level unknown: critical factors have no data">
        <span aria-hidden>?</span> Unknown{f ? <> · at least <span style={{ color: f.color }}>{f.label}</span></> : null}
      </span>
    )
  }
  return (
    <span
      className={`chip ${size === 'lg' ? 'text-sm !px-3 !py-1' : ''}`}
      style={{ color: m.color, borderColor: m.color, background: 'color-mix(in srgb, currentColor 12%, transparent)' }}
    >
      <span aria-hidden>{m.icon}</span> {m.n} · {m.label}
    </span>
  )
}

export function Ext({ href, children, className = '' }: { href?: string | null; children: ReactNode; className?: string }) {
  if (!href) return <span className={className}>{children}</span>
  return (
    <a className={`link ${className}`} href={href} target="_blank" rel="noreferrer">
      {children}
    </a>
  )
}

export function PageHeader({ title, sub, right, help }: { title: string; sub?: ReactNode; right?: ReactNode; help?: ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">{title}{help}</h1>
        {sub && <p className="mt-0.5 text-[13px] text-ink-2">{sub}</p>}
      </div>
      {right && <div className="flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  )
}

export function Seg<T extends string>({ value, options, onChange, label }: {
  value: T; options: { v: T; l: string }[]; onChange: (v: T) => void; label?: string
}) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.v} type="button" aria-pressed={o.v === value} onClick={() => onChange(o.v)}>
          {o.l}
        </button>
      ))}
    </div>
  )
}
