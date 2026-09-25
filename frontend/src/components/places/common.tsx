import { useState, type ReactNode } from 'react'
import { HelpTip, InfoTip, isTopicId, openTopic } from '../../help'
import { PLACES_TOPICS, type PlacesTopicId } from '../../help/topics/places'
import { levelMeta, toneText } from '../../lib/format'
import { EXPOSURE_COLORS } from './api'

/**
 * Help button for a Places topic. Uses the shared HelpTip once the topics are registered in
 * help/content.ts; until then it falls back to an InfoTip with the topic's short text, so no
 * element ever ships without its explanation.
 */
export function PlaceTip({ id, label }: { id: string; label?: string }) {
  if (isTopicId(id)) return <HelpTip id={id} label={label} />
  const t = (PLACES_TOPICS as Record<string, (typeof PLACES_TOPICS)[PlacesTopicId]>)[id]
  if (!t) return null
  return <InfoTip title={t.title} text={t.short} href={t.sources[0]?.url} />
}

/** Opens a topic in the drawer when registered; otherwise nothing (PlaceTip covers it). */
export function openPlaceTopic(id: string) {
  if (isTopicId(id)) openTopic(id)
}

export function ExposureChip({ score, label, compact = false }: { score: number | null | undefined; label?: string | null; compact?: boolean }) {
  if (score === null || score === undefined) {
    return (
      <span className="chip" style={{ color: 'var(--ink-3)', borderColor: 'var(--line-strong)', borderStyle: 'dashed' }} title="No data yet">
        -- {compact ? '' : 'no data'}
      </span>
    )
  }
  const c = EXPOSURE_COLORS[score]
  return (
    <span className="chip tnum" style={{ color: toneText(c), borderColor: c, background: `color-mix(in srgb, ${c} 16%, transparent)` }}>
      {score}{compact ? '' : ` · ${label ?? ''}`}
    </span>
  )
}

export function LevelDot({ level, levelKey }: { level: number | null | undefined; levelKey?: string | null }) {
  const m = levelMeta(level, levelKey)
  return (
    <span aria-hidden className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
      style={{ background: m ? m.color : 'transparent', border: m ? undefined : '1.5px dashed var(--ink-3)' }} />
  )
}

/** Collapsible "How to read this page" panel for /places (PageGuide takes only registered page ids). */
export function PlacesGuide() {
  const KEY = 'elnino.help.guide.places.collapsed'
  const [open, setOpen] = useState(() => {
    try { return window.localStorage.getItem(KEY) !== '1' } catch { return true }
  })
  const toggle = () => {
    const next = !open
    setOpen(next)
    try { window.localStorage.setItem(KEY, next ? '0' : '1') } catch { /* ignore */ }
  }
  const steps: ReactNode[] = [
    <>The <b>cards</b> show each place now: its level (0 Normal to 4 Leave, same rules as the Samui watch), the current conditions and the factors behind the level.</>,
    <>The <b>comparison matrix</b> scores long-term exposure per hazard, 0 very low to 4 very high. Tap a cell for its value, rule and source.</>,
    <>The <b>charts</b> overlay the places month by month (temperature, rain, sunshine) and show the change expected by 2050.</>,
    <>The <b>ranking</b> uses weights you choose with the sliders. It is a decision aid only: it leaves out cost of living, visas, healthcare and family.</>,
    <>The <b>official advisories</b> row quotes the UK, US and French governments with the date of their last update.</>,
  ]
  const topics = ['places_page', 'place_levels', 'place_exposure_scale', 'place_ranking', 'place_enso', 'place_advisories']
  return (
    <section className="card no-print mb-4" aria-label="How to read this page">
      <div className="flex flex-wrap items-center gap-2 px-4 py-2.5">
        <button type="button" onClick={toggle} aria-expanded={open} className="flex min-w-0 flex-1 items-center gap-2 text-left">
          <span aria-hidden className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-line-strong text-[11px] font-bold text-ink-2">?</span>
          <span className="text-[13px] font-semibold text-ink">How to read this page</span>
          <span aria-hidden className="text-ink-3 transition-transform" style={{ transform: open ? 'rotate(90deg)' : undefined }}>›</span>
        </button>
      </div>
      {open && (
        <div className="border-t border-line px-4 pt-3 pb-4">
          <p className="text-[13px] text-ink-2">Three places compared with the same data and the same rules: Maenam (Koh Samui, where you live), Saint-Gatien-des-Bois (Normandy) and Gorokhovets (Vladimir Oblast). Every number shows its date and source; missing data is marked, never hidden.</p>
          <ol className="mt-2.5 list-decimal space-y-1.5 pl-5 text-[13px] leading-relaxed text-ink-2 marker:font-semibold marker:text-ink-3">
            {steps.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-semibold tracking-wide text-ink-3 uppercase">Key topics</span>
            {topics.map((id) => {
              const t = (PLACES_TOPICS as Record<string, { title: string; short: string }>)[id]
              return (
                <span key={id} className="chip gap-1" title={t.short}>
                  {t.title} <PlaceTip id={id} />
                </span>
              )
            })}
          </div>
        </div>
      )}
    </section>
  )
}

export function fmt(v: number | null | undefined, d = 1, unit = ''): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '--'
  return `${v.toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d })}${unit ? ` ${unit}` : ''}`
}

export function signed(v: number | null | undefined, d = 1, unit = ''): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '--'
  const s = fmt(Math.abs(v), d)
  return `${v > 0 ? '+' : v < 0 ? '-' : ''}${s}${unit ? ` ${unit}` : ''}`
}
