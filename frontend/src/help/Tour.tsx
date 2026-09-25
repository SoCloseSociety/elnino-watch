import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { getTopic } from './content'
import { pageFromPath, TOURS } from './guides'
import { endTour, isTourDone, lsGet, lsSet, markTourDone, openTopic, registerMount, setTourStep, startTour, useHelp } from './store'
import type { PageId } from './types'

type Rect = { top: number; left: number; width: number; height: number }

const PAD = 6

/**
 * Guided tour overlay. Mount it ONCE inside the router (e.g. in Layout).
 * Start a tour with `startTour('samui')` (from './store' or './index').
 * Auto-starts once on the first visit of the pages in `autoStart` (default: overview).
 * Completion is remembered in localStorage (`elnino.help.tour.<page>.done`).
 */
export function Tour({ autoStart = ['overview'], autoStartDelayMs = 1500 }: {
  autoStart?: PageId[]
  autoStartDelayMs?: number
}) {
  const { tour, topicId } = useHelp()
  const loc = useLocation()
  const page = pageFromPath(loc.pathname)

  useEffect(() => registerMount('tour'), [])

  // auto-start once per page on first visit
  useEffect(() => {
    if (!page || !autoStart.includes(page) || tour) return
    if (isTourDone(page) || lsGet(`tour.${page}.auto`) === '1') return
    const t = window.setTimeout(() => {
      lsSet(`tour.${page}.auto`, '1')
      startTour(page)
    }, autoStartDelayMs)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page])

  // leaving the page ends its tour
  useEffect(() => {
    if (tour && page !== tour.page) endTour()
  }, [page, tour])

  if (!tour || topicId) return null // paused while the help drawer is open
  const steps = TOURS[tour.page]
  if (!steps?.length) return null
  const i = Math.max(0, Math.min(tour.step, steps.length - 1))
  return <TourStepView key={`${tour.page}-${i}`} page={tour.page} index={i} total={steps.length} />
}

function TourStepView({ page, index, total }: { page: PageId; index: number; total: number }) {
  const step = TOURS[page][index]
  const [rect, setRect] = useState<Rect | null>(null)
  const [searching, setSearching] = useState(true)
  const [cardPos, setCardPos] = useState<{ top: number; left: number } | null>(null)
  const card = useRef<HTMLDivElement>(null)
  const el = useRef<HTMLElement | null>(null)
  const topic = step.topic ? getTopic(step.topic) : null
  const narrow = typeof window !== 'undefined' && window.innerWidth < 640
  const reduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  const finish = useCallback(() => {
    markTourDone(page)
    endTour()
  }, [page])
  const next = useCallback(() => (index + 1 >= total ? finish() : setTourStep(index + 1)), [index, total, finish])
  const back = useCallback(() => index > 0 && setTourStep(index - 1), [index])

  const measure = useCallback(() => {
    const e = el.current
    if (!e || !document.contains(e)) return setRect(null)
    const r = e.getBoundingClientRect()
    if (r.width === 0 && r.height === 0) return setRect(null)
    setRect({ top: r.top - PAD, left: r.left - PAD, width: r.width + PAD * 2, height: r.height + PAD * 2 })
  }, [])

  // find the target (it may render late: data loads async), scroll it into view, then track it
  useEffect(() => {
    let tries = 0
    let timer: number | undefined
    const find = () => {
      // first VISIBLE match (the sidebar and the mobile nav can both carry the same target)
      const all = [...document.querySelectorAll<HTMLElement>(`[data-tour="${CSS.escape(step.target)}"]`)]
      const e = all.find((x) => x.getClientRects().length > 0) ?? null
      if (e) {
        el.current = e
        e.scrollIntoView({ block: 'center', inline: 'nearest', behavior: reduced ? 'auto' : 'smooth' })
        timer = window.setTimeout(() => {
          measure()
          setSearching(false)
        }, reduced ? 30 : 350)
      } else if (++tries < 15) {
        timer = window.setTimeout(find, 100)
      } else {
        el.current = null
        setRect(null)
        setSearching(false)
      }
    }
    find()
    let raf = 0
    const onMove = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(measure)
    }
    window.addEventListener('resize', onMove)
    window.addEventListener('scroll', onMove, true)
    return () => {
      window.clearTimeout(timer)
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onMove)
      window.removeEventListener('scroll', onMove, true)
    }
  }, [step.target, measure, reduced])

  // place the card next to the spotlight
  useLayoutEffect(() => {
    const c = card.current
    if (!c || narrow) return
    const w = c.offsetWidth
    const h = c.offsetHeight
    const vw = window.innerWidth
    const vh = window.innerHeight
    const m = 12
    if (!rect) {
      setCardPos({ top: Math.max(m, (vh - h) / 2), left: Math.max(m, (vw - w) / 2) })
      return
    }
    let top = rect.top + rect.height + 10
    if (top + h > vh - m) top = rect.top - h - 10
    if (top < m) top = Math.max(m, Math.min(vh - h - m, rect.top + 10))
    const left = Math.max(m, Math.min(rect.left, vw - w - m))
    setCardPos({ top, left })
  }, [rect, narrow, searching])

  useEffect(() => {
    if (!searching) card.current?.focus()
  }, [searching])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        finish()
      } else if (e.key === 'ArrowRight') next()
      else if (e.key === 'ArrowLeft') back()
      else if (e.key === 'Tab' && card.current) {
        // keep keyboard focus inside the tour card
        const f = card.current.querySelectorAll<HTMLElement>('button:not([disabled])')
        if (!f.length) return
        const first = f[0]
        const last = f[f.length - 1]
        const inside = card.current.contains(document.activeElement)
        if (e.shiftKey && (!inside || document.activeElement === first || document.activeElement === card.current)) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && (!inside || document.activeElement === last)) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [finish, next, back])

  return (
    <div className="no-print fixed inset-0 z-[80]" role="presentation">
      {/* click shield: the page underneath is not interactive during the tour */}
      <div className="absolute inset-0" style={{ background: rect ? 'transparent' : 'rgba(0,0,0,0.55)' }} aria-hidden />
      {rect && (
        <div
          aria-hidden
          className="pointer-events-none absolute top-0 left-0 rounded-[10px]"
          style={{
            // transform (not top/left) so moving the spotlight is never a layout shift
            transform: `translate(${rect.left}px, ${rect.top}px)`, width: rect.width, height: rect.height,
            boxShadow: '0 0 0 9999px rgba(0,0,0,0.55)',
            outline: '2px solid var(--accent)',
            transition: reduced ? undefined : 'transform .2s, width .2s, height .2s',
          }}
        />
      )}
      <div
        ref={card}
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-tour-title"
        aria-describedby="help-tour-body"
        tabIndex={-1}
        className={narrow
          ? 'absolute inset-x-0 bottom-0 rounded-t-2xl border-t border-line-strong bg-surface p-4 pb-5 shadow-2xl outline-none'
          : 'absolute top-0 left-0 w-[min(360px,calc(100vw-24px))] rounded-xl border border-line-strong bg-surface p-4 shadow-2xl outline-none'}
        style={narrow ? undefined : { transform: `translate(${cardPos?.left ?? 0}px, ${cardPos?.top ?? 0}px)`, visibility: cardPos ? 'visible' : 'hidden' }}
      >
        <p className="text-[11px] font-semibold tracking-wide text-ink-3 uppercase">
          Step {index + 1} of {total}
        </p>
        <h2 id="help-tour-title" className="mt-1 text-[15px] font-semibold text-ink">{step.title}</h2>
        <p id="help-tour-body" className="mt-1.5 text-[13px] leading-relaxed text-ink-2">{step.body}</p>
        {!rect && !searching && (
          <p className="mt-1.5 text-[11.5px] text-ink-3">(This part is not on screen right now.)</p>
        )}
        {topic && (
          <button type="button" className="link mt-2 text-[12.5px]" onClick={() => openTopic(topic.id)}>
            Learn more: {topic.title} →
          </button>
        )}
        <div className="mt-3 flex items-center gap-1" aria-hidden>
          {Array.from({ length: total }, (_, k) => (
            <span key={k} className="h-1.5 rounded-full"
              style={{ width: k === index ? 16 : 6, background: k <= index ? 'var(--accent)' : 'var(--line-strong)' }} />
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <button type="button" className="text-[12.5px] text-ink-3 hover:text-ink hover:underline" onClick={finish}>
            Skip tour
          </button>
          <div className="flex gap-2">
            <button type="button" className="btn !py-1" onClick={back} disabled={index === 0}>Back</button>
            <button type="button" className="btn btn-primary !py-1" onClick={next}>
              {index + 1 >= total ? 'Done' : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
