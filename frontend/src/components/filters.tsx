/**
 * Shared filter UI: sticky bar, labelled groups with help, multi-select chips with counts,
 * searchable multi-select for long lists, date presets, search box and the
 * "filtered-empty" explanation. State lives in the URL (see lib/urlFilters.ts).
 */
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useDebounced } from '../lib/urlFilters'

export interface Opt {
  value: string
  label?: ReactNode
  /** plain-text label for search / aria */
  text?: string
  count?: number | null
  color?: string
  /** help (HelpTip / HelpFor) shown next to the chip */
  help?: ReactNode
  title?: string
}

/** Sticky filter bar at the top of the page's scroll area. */
export function FilterBar({ children, active, onReset, tour, summary, className = '', sticky = true }: {
  children: ReactNode
  active: number
  onReset: () => void
  tour?: string
  /** e.g. "124 of 1 682 items" */
  summary?: ReactNode
  className?: string
  sticky?: boolean
}) {
  return (
    <section data-tour={tour} aria-label="Filters"
      className={`card no-print z-20 ${sticky ? 'sticky top-0 shadow-[0_6px_16px_-10px_rgba(0,0,0,.5)]' : ''} ${className}`}>
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2.5 px-3 py-2.5">
        {children}
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t border-line px-3 py-1.5 text-[12px] text-ink-3">
        {summary && <span className="tnum" aria-live="polite">{summary}</span>}
        <span className="ml-auto flex items-center gap-2">
          {active > 0 && <span className="tnum">{active} filter{active > 1 ? 's' : ''} active</span>}
          <button type="button" className="btn !min-h-8 !px-2.5 !py-0.5 !text-[12px]" disabled={!active} onClick={onReset}>
            Reset filters
          </button>
        </span>
      </div>
    </section>
  )
}

/** A labelled filter group: "Kind (?)  [chips]". */
export function FilterGroup({ label, help, children, className = '' }: { label: string; help?: ReactNode; children: ReactNode; className?: string }) {
  const id = useId()
  return (
    <div role="group" aria-labelledby={id} className={`flex min-w-0 flex-col gap-1 ${className}`}>
      <span id={id} className="flex items-center gap-1 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">{label}{help}</span>
      <div className="flex min-w-0 flex-wrap items-center gap-1.5">{children}</div>
    </div>
  )
}

/** Toggle chips (multi-select). Counts come from the facets endpoint. */
export function ChipSelect({ options, selected, onToggle, limit = 12, allLabel, onAll }: {
  options: Opt[]
  selected: string[]
  onToggle: (v: string) => void
  /** show at most N, then a "+ N more" toggle */
  limit?: number
  /** optional "All" chip that clears the selection */
  allLabel?: string
  onAll?: () => void
}) {
  const [more, setMore] = useState(false)
  // selected values always stay visible
  const sorted = options
  const visible = more ? sorted : sorted.filter((o, i) => i < limit || selected.includes(o.value))
  const hidden = sorted.length - visible.length
  return (
    <>
      {allLabel && onAll && (
        <button type="button" aria-pressed={!selected.length} onClick={onAll} className="fchip">{allLabel}</button>
      )}
      {visible.map((o) => {
        const on = selected.includes(o.value)
        const zero = o.count === 0 && !on
        return (
          <span key={o.value} className="inline-flex items-center gap-0.5">
            <button type="button" aria-pressed={on} onClick={() => onToggle(o.value)} title={zero ? `${o.title ?? o.text ?? o.value}: no items match right now` : o.title}
              className={`fchip ${zero ? '!border-dashed' : ''}`}
              style={on && o.color ? { borderColor: o.color, boxShadow: `inset 0 0 0 1px ${o.color}` } : undefined}>
              {o.color && <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: o.color }} aria-hidden />}
              <span>{o.label ?? o.text ?? o.value}</span>
              {o.count !== undefined && o.count !== null && <span className="fchip-n tnum">{o.count.toLocaleString('en-GB')}</span>}
            </button>
            {o.help}
          </span>
        )
      })}
      {hidden > 0 && <button type="button" className="fchip !border-dashed" onClick={() => setMore(true)}>+ {hidden} more</button>}
      {more && sorted.length > limit && <button type="button" className="fchip !border-dashed" onClick={() => setMore(false)}>Show less</button>}
    </>
  )
}

/** Dropdown multi-select with a search box, for long lists (sources, languages, tags). */
export function MultiSelect({ label, options, selected, onToggle, onClear, placeholder = 'Search' }: {
  label: string
  options: Opt[]
  selected: string[]
  onToggle: (v: string) => void
  onClear: () => void
  placeholder?: string
}) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const ref = useRef<HTMLDivElement>(null)
  const id = useId()
  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('pointerdown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open])
  const s = q.trim().toLowerCase()
  const shown = options.filter((o) => !s || `${o.value} ${o.text ?? ''}`.toLowerCase().includes(s))
  const selLabel = selected.length === 0 ? 'All' : selected.length === 1 ? (options.find((o) => o.value === selected[0])?.text ?? selected[0]) : `${selected.length} selected`
  return (
    <div ref={ref} className="relative">
      <button type="button" className="fchip !pr-2" aria-expanded={open} aria-controls={id} aria-haspopup="listbox" onClick={() => setOpen((o) => !o)}
        aria-label={`${label}: ${selLabel}`} style={selected.length ? { borderColor: 'var(--accent)', boxShadow: 'inset 0 0 0 1px var(--accent)' } : undefined}>
        <span className="max-w-[180px] truncate">{selLabel}</span>
        <span aria-hidden className="text-ink-3">▾</span>
      </button>
      {open && (
        <div id={id} className="card absolute top-full left-0 z-40 mt-1 w-[min(320px,calc(100vw-24px))] p-2 shadow-2xl">
          <input className="input mb-1.5 w-full" type="search" placeholder={placeholder} value={q} onChange={(e) => setQ(e.target.value)} aria-label={`Search ${label}`} autoFocus />
          <ul role="listbox" aria-multiselectable className="max-h-[300px] overflow-y-auto">
            {shown.map((o) => (
              <li key={o.value} role="option" aria-selected={selected.includes(o.value)}>
                <label className="flex min-h-10 cursor-pointer items-center gap-2 rounded px-1.5 text-[13px] hover:bg-surface-2 sm:min-h-8">
                  <input type="checkbox" className="h-4 w-4 accent-[var(--accent)]" checked={selected.includes(o.value)} onChange={() => onToggle(o.value)} />
                  <span className="min-w-0 flex-1 truncate" title={o.title ?? o.text ?? o.value}>{o.label ?? o.text ?? o.value}</span>
                  {o.count !== undefined && o.count !== null && <span className="text-[11px] text-ink-3 tnum">{o.count.toLocaleString('en-GB')}</span>}
                </label>
              </li>
            ))}
            {!shown.length && <li className="px-1.5 py-2 text-[12px] text-ink-3">No match.</li>}
          </ul>
          <div className="mt-1.5 flex justify-between border-t border-line pt-1.5">
            <button type="button" className="btn !px-2 !py-0.5 !text-[12px]" disabled={!selected.length} onClick={onClear}>Clear</button>
            <button type="button" className="btn !px-2 !py-0.5 !text-[12px]" onClick={() => setOpen(false)}>Done</button>
          </div>
        </div>
      )}
    </div>
  )
}

/** Single-choice presets ("Any", "24 h", "7 d", ...). */
export function PresetSelect({ value, options, onChange, label }: {
  value: string
  options: { v: string; l: string; title?: string }[]
  onChange: (v: string) => void
  label: string
}) {
  return (
    <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button key={o.v || 'any'} type="button" role="radio" aria-checked={value === o.v}
          className="fchip" title={o.title} onClick={() => onChange(o.v)}>
          {o.l}
        </button>
      ))}
    </div>
  )
}

/** Date range: presets plus optional custom from/to dates. */
export function DateRange({ since, until, onSince, onUntil, presets = DEFAULT_PRESETS, custom = true }: {
  since: string
  until?: string
  onSince: (v: string) => void
  onUntil?: (v: string) => void
  presets?: { v: string; l: string }[]
  custom?: boolean
}) {
  const isPreset = presets.some((p) => p.v === since)
  const [showCustom, setShowCustom] = useState(!isPreset || !!until)
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <PresetSelect label="Date range" value={isPreset && !showCustom ? since : showCustom ? '__custom' : since}
        options={[...presets, ...(custom ? [{ v: '__custom', l: 'Custom' }] : [])]}
        onChange={(v) => {
          if (v === '__custom') { setShowCustom(true); return }
          setShowCustom(false)
          onSince(v)
          onUntil?.('')
        }} />
      {showCustom && custom && (
        <span className="flex flex-wrap items-center gap-1.5 text-[12px] text-ink-2">
          <label className="flex items-center gap-1">from
            <input type="date" className="input min-h-10 !py-1 sm:min-h-8" value={/^\d{4}-/.test(since) ? since.slice(0, 10) : ''} max={new Date().toISOString().slice(0, 10)}
              onChange={(e) => onSince(e.target.value)} aria-label="From date" />
          </label>
          {onUntil && (
            <label className="flex items-center gap-1">to
              <input type="date" className="input min-h-10 !py-1 sm:min-h-8" value={until ?? ''} onChange={(e) => onUntil(e.target.value)} aria-label="To date" />
            </label>
          )}
        </span>
      )}
    </div>
  )
}

export const DEFAULT_PRESETS = [
  { v: '', l: 'Any time' }, { v: '24h', l: '24 h' }, { v: '7d', l: '7 days' }, { v: '30d', l: '30 days' }, { v: '90d', l: '90 days' },
]

/** Search box that writes to the URL after a short pause. */
export function SearchFilter({ value, onChange, placeholder = 'Search', label = 'Search', className = '' }: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  label?: string
  className?: string
}) {
  const [text, setText] = useState(value)
  const deb = useDebounced(text, 350)
  // external reset -> input
  useEffect(() => { setText(value) }, [value])
  useEffect(() => { if (deb !== value) onChange(deb.trim()) }, [deb]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <input className={`input min-h-10 min-w-0 sm:min-h-8 ${className}`} type="search" placeholder={placeholder} value={text}
      onChange={(e) => setText(e.target.value)} aria-label={label} />
  )
}

/** Explains an empty filtered result: which filters are on, and how to widen. */
export function FilteredEmpty({ what, filters, onReset, total, children }: {
  what: string
  /** human descriptions of the active filters, e.g. ["kind: social", "language: th"] */
  filters: string[]
  onReset: () => void
  /** how many items exist without any filter, when known */
  total?: number | null
  children?: ReactNode
}) {
  return (
    <div className="rounded-lg border border-dashed border-line-strong p-4 text-[13px] text-ink-2" role="status">
      <p className="font-medium text-ink">No {what} match these filters.</p>
      {filters.length > 0 && (
        <p className="mt-1">
          Active: {filters.map((f, i) => <span key={i} className="chip mr-1 mb-1">{f}</span>)}
        </p>
      )}
      <p className="mt-1">
        Filters combine with AND (each group narrows the result); values inside one group combine with OR.
        {total ? <> There are <b className="tnum">{total.toLocaleString('en-GB')}</b> {what} without filters.</> : null}{' '}
        Remove a filter or widen the date range.
      </p>
      {children}
      <button type="button" className="btn mt-2" onClick={onReset}>Reset filters</button>
    </div>
  )
}
