import { useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { getTopic } from './content'
import { PAGE_GUIDES } from './guides'
import { lsGet, lsSet, openTopic, startTour, useHelp } from './store'
import type { PageId } from './types'

/**
 * Collapsible "How to read this page" panel. Remembers the collapsed state per page
 * (localStorage `elnino.help.guide.<page>.collapsed`).
 *
 *   <PageGuide page="samui" />
 */
export function PageGuide({ page, defaultOpen = true, className = '' }: {
  page: PageId
  /** state on the very first visit (before the user toggles it) */
  defaultOpen?: boolean
  className?: string
}) {
  const g = PAGE_GUIDES[page]
  const key = `guide.${page}.collapsed`
  const [open, setOpen] = useState(() => {
    const v = lsGet(key)
    return v === null ? defaultOpen : v !== '1'
  })
  const { hasDrawer } = useHelp()
  const uid = useId()
  const bodyId = `page-guide-${uid}`

  const toggle = () => {
    const next = !open
    setOpen(next)
    lsSet(key, next ? '0' : '1')
  }

  return (
    <section className={`card no-print mb-4 ${className}`} aria-label={`${g.title}`}>
      <div className="flex flex-wrap items-center gap-2 px-4 py-2.5">
        <button type="button" onClick={toggle} aria-expanded={open} aria-controls={bodyId}
          className="flex min-w-0 flex-1 items-center gap-2 text-left">
          <span aria-hidden className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-line-strong text-[11px] font-bold text-ink-2">?</span>
          <span className="text-[13px] font-semibold text-ink">{g.title}</span>
          <span aria-hidden className="text-ink-3 transition-transform" style={{ transform: open ? 'rotate(90deg)' : undefined }}>›</span>
        </button>
        <button type="button" className="btn !px-2.5 !py-1 !text-[12px]" onClick={() => startTour(page)}>
          Take the tour
        </button>
      </div>
      {open && (
        <div id={bodyId} className="border-t border-line px-4 pt-3 pb-4">
          <p className="text-[13px] text-ink-2">{g.intro}</p>
          <ol className="mt-2.5 list-decimal space-y-1.5 pl-5 text-[13px] leading-relaxed text-ink-2 marker:font-semibold marker:text-ink-3">
            {g.steps.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-semibold tracking-wide text-ink-3 uppercase">Key topics</span>
            {g.topics.map((id) => {
              const t = getTopic(id)
              if (!t) return null
              return hasDrawer ? (
                <button key={id} type="button" className="chip cursor-pointer whitespace-normal hover:bg-surface-2" title={t.short} onClick={() => openTopic(id)}>
                  {t.title}
                </button>
              ) : (
                <Link key={id} className="chip whitespace-normal hover:bg-surface-2" to={`/learn#${id}`} title={t.short}>{t.title}</Link>
              )
            })}
            <Link className="link ml-1 text-[12px]" to="/learn">All explanations →</Link>
          </div>
        </div>
      )}
    </section>
  )
}
