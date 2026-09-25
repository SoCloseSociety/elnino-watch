import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { getTopic, topicFor, type TopicId } from './content'
import { openTopic, useHelp } from './store'

const NARROW = '(max-width: 639px)'

function useNarrow(): boolean {
  const [n, setN] = useState(() => typeof window !== 'undefined' && window.matchMedia?.(NARROW).matches)
  useEffect(() => {
    const mq = window.matchMedia?.(NARROW)
    if (!mq) return
    const on = () => setN(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return !!n
}

interface TriggerProps {
  id: TopicId
  /** "drawer" opens the side drawer, "page" links to /learn#id, "auto" (default) = drawer if mounted */
  learnMore?: 'auto' | 'drawer' | 'page'
  className?: string
}

/**
 * Small "?" button that explains a topic in a popover (bottom sheet on phones).
 *
 *   <HelpTip id="oni" />
 *   <h2>ONI <HelpTip id="oni" label="What is the ONI?" /></h2>
 */
export function HelpTip({ id, label, size = 'sm', ...rest }: TriggerProps & {
  /** accessible name; default "What is <title>?" */
  label?: string
  size?: 'sm' | 'md'
}) {
  const t = getTopic(id)
  const px = size === 'md' ? 20 : 16
  // the button is 24 x 24 (WCAG target size); the visible "?" dot inside stays 16 / 20 px
  return (
    <TopicPopover
      {...rest}
      id={id}
      ariaLabel={label ?? `What is ${t?.title ?? id}?`}
      triggerClass={`help-hit -my-1 inline-flex h-6 w-6 shrink-0 items-center justify-center align-middle font-bold text-ink-2 hover:text-accent ${rest.className ?? ''}`}
      triggerStyle={{ fontSize: size === 'md' ? 12 : 10.5, lineHeight: 1 }}
    >
      <span aria-hidden className="inline-flex items-center justify-center rounded-full border border-line-strong" style={{ width: px, height: px }}>?</span>
    </TopicPopover>
  )
}

/**
 * Inline glossary term: dotted underline, tooltip on hover/focus/tap.
 *
 *   Values are an <Term id="anomaly">anomaly</Term>, not a temperature.
 */
export function Term({ id, children, ...rest }: TriggerProps & { children: ReactNode }) {
  const t = getTopic(id)
  return (
    <TopicPopover
      {...rest}
      id={id}
      hover
      ariaLabel={undefined}
      describe={t?.short}
      triggerClass={`inline cursor-help p-0 text-inherit underline decoration-dotted decoration-1 underline-offset-[3px] hover:text-accent ${rest.className ?? ''}`}
    >
      {children}
    </TopicPopover>
  )
}

function TopicPopover({ id, adhoc, learnMore = 'auto', ariaLabel, describe, triggerClass, triggerStyle, hover = false, children }: Omit<TriggerProps, 'id'> & {
  id?: TopicId
  /** a one-off explanation (backend description) for items that have no help topic */
  adhoc?: { title: string; short: string; href?: string | null }
  ariaLabel?: string
  describe?: string
  triggerClass: string
  triggerStyle?: CSSProperties
  hover?: boolean
  children: ReactNode
}) {
  const topic = (id ? getTopic(id) : null) ?? (adhoc ? { id: '', ...adhoc } : null)
  const { hasDrawer } = useHelp()
  const narrow = useNarrow()
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<{ top: number; left: number; maxH: number } | null>(null)
  const btn = useRef<HTMLButtonElement>(null)
  const pop = useRef<HTMLDivElement>(null)
  const hoverTimer = useRef<number | undefined>(undefined)
  const openedBy = useRef<'click' | 'hover' | null>(null)
  const uid = useId()
  const popId = `help-pop-${uid}`
  const titleId = `help-pop-t-${uid}`

  const close = useCallback((focusBack: boolean) => {
    setOpen(false)
    openedBy.current = null
    if (focusBack) btn.current?.focus()
  }, [])

  // position (desktop): below the trigger if it fits, else above; clamped to the viewport
  const place = useCallback(() => {
    const b = btn.current?.getBoundingClientRect()
    const p = pop.current
    if (!b || !p) return
    const w = p.offsetWidth
    const h = p.offsetHeight
    const vw = window.innerWidth
    const vh = window.innerHeight
    const m = 8
    let left = b.left + b.width / 2 - w / 2
    left = Math.max(m, Math.min(left, vw - w - m))
    const below = vh - b.bottom - m
    const above = b.top - m
    let top: number
    let maxH: number
    if (below >= Math.min(h, 260) || below >= above) {
      top = b.bottom + 6
      maxH = below - 6
    } else {
      maxH = above - 6
      top = Math.max(m, b.top - 6 - Math.min(h, maxH))
    }
    setPos({ top, left, maxH: Math.max(120, maxH) })
  }, [])

  useLayoutEffect(() => {
    if (!open || narrow) return
    place()
  }, [open, narrow, place])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        close(true)
      }
    }
    const onDown = (e: PointerEvent) => {
      const tgt = e.target as Node
      if (pop.current?.contains(tgt) || btn.current?.contains(tgt)) return
      close(false)
    }
    const onMove = () => (narrow ? undefined : place())
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onDown)
    window.addEventListener('resize', onMove)
    window.addEventListener('scroll', onMove, true)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onDown)
      window.removeEventListener('resize', onMove)
      window.removeEventListener('scroll', onMove, true)
    }
  }, [open, narrow, place, close])

  // move focus into the popover when opened by click/keyboard (not on hover)
  useEffect(() => {
    if (open && openedBy.current === 'click') pop.current?.focus()
  }, [open])

  useEffect(() => () => window.clearTimeout(hoverTimer.current), [])

  if (!topic) return <>{children}</>

  const useDrawer = learnMore === 'drawer' || (learnMore === 'auto' && hasDrawer)

  const hoverProps = hover && !narrow ? {
    onMouseEnter: () => {
      window.clearTimeout(hoverTimer.current)
      hoverTimer.current = window.setTimeout(() => {
        if (!open) {
          openedBy.current = 'hover'
          setOpen(true)
        }
      }, 250)
    },
    onMouseLeave: () => {
      window.clearTimeout(hoverTimer.current)
      if (openedBy.current === 'hover') hoverTimer.current = window.setTimeout(() => close(false), 200)
    },
  } : {}

  const panel = open && (
    <>
      {narrow && <div className="fixed inset-0 z-[70] bg-black/40" aria-hidden onClick={() => close(true)} />}
      <div
        ref={pop}
        id={popId}
        role="dialog"
        aria-modal={narrow || undefined}
        aria-labelledby={titleId}
        tabIndex={-1}
        className={narrow
          ? 'fixed inset-x-0 bottom-0 z-[71] max-h-[75vh] overflow-y-auto rounded-t-2xl border-t border-line-strong bg-surface p-4 pb-6 shadow-2xl outline-none'
          : 'fixed z-[71] w-[min(340px,calc(100vw-16px))] overflow-y-auto rounded-xl border border-line-strong bg-surface p-3.5 shadow-2xl outline-none'}
        style={narrow ? undefined : { top: pos?.top ?? -9999, left: pos?.left ?? -9999, maxHeight: pos?.maxH }}
        onMouseEnter={hover ? () => window.clearTimeout(hoverTimer.current) : undefined}
        onMouseLeave={hover && openedBy.current === 'hover' ? () => { hoverTimer.current = window.setTimeout(() => close(false), 200) } : undefined}
      >
        {narrow && <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-line-strong" aria-hidden />}
        <div className="flex items-start justify-between gap-3">
          <h2 id={titleId} className="text-[14px] font-semibold text-ink">{topic.title}</h2>
          <button type="button" className="-mt-1 -mr-1 rounded-md px-2 py-0.5 text-[18px] leading-none text-ink-3 hover:bg-surface-2 hover:text-ink"
            aria-label="Close" onClick={() => close(true)}>
            ×
          </button>
        </div>
        <p className="mt-1.5 text-[13px] leading-relaxed text-ink-2">{topic.short}</p>
        <div className="mt-3">
          {!id ? (
            adhoc?.href ? <a className="btn !px-2.5 !py-1 !text-[12px]" href={adhoc.href} target="_blank" rel="noreferrer">Source <span aria-hidden>↗</span></a> : null
          ) : useDrawer ? (
            <button type="button" className="btn !px-2.5 !py-1 !text-[12px]" onClick={() => { close(false); openTopic(id) }}>
              Learn more <span aria-hidden>→</span>
            </button>
          ) : (
            <Link className="btn !px-2.5 !py-1 !text-[12px]" to={`/learn#${id}`} onClick={() => close(false)}>
              Learn more <span aria-hidden>→</span>
            </Link>
          )}
        </div>
      </div>
    </>
  )

  return (
    <>
      <button
        ref={btn}
        type="button"
        className={triggerClass}
        style={triggerStyle}
        aria-label={ariaLabel}
        title={describe}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? popId : undefined}
        onClick={(e) => {
          e.stopPropagation()
          e.preventDefault()
          if (open && openedBy.current === 'click') close(false)
          else {
            openedBy.current = 'click'
            setOpen(true)
          }
        }}
        {...hoverProps}
      >
        {children}
      </button>
      {panel && createPortal(panel, document.body)}
    </>
  )
}

/** Record of dynamic items that had no help topic (inspect with `window.__helpGaps` in the console). */
const GAPS = new Map<string, string>()
function noteGap(key: string, how: string) {
  if (GAPS.has(key)) return
  GAPS.set(key, how)
  ;(window as unknown as { __helpGaps?: Record<string, string> }).__helpGaps = Object.fromEntries(GAPS)
}

/**
 * "i" button with a one-off explanation, for items without a help topic (uses the backend's
 * own description). Same popover as HelpTip, without "Learn more".
 */
export function InfoTip({ title, text, href, className = '' }: { title: string; text: string; href?: string | null; className?: string }) {
  return (
    <TopicPopover
      adhoc={{ title, short: text, href }}
      ariaLabel={`About ${title}`}
      triggerClass={`help-hit -my-1 inline-flex h-6 w-6 shrink-0 items-center justify-center align-middle font-bold text-ink-2 hover:text-accent ${className}`}
      triggerStyle={{ fontSize: 10.5, lineHeight: 1, fontStyle: 'italic', fontFamily: 'Georgia, serif' }}
    >
      <span aria-hidden className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-dashed border-line-strong">i</span>
    </TopicPopover>
  )
}

/**
 * Help for a dynamic item (factor, layer, source, series, signal, category...):
 * the explicit `id` if given, else `topicFor(appId)`, else an InfoTip with the backend
 * description, else nothing (and the gap is recorded in `window.__helpGaps`).
 */
export function HelpFor({ appId, id, title, text, href, kind = 'item', className }: {
  appId?: string | null
  id?: TopicId | null
  title?: string | null
  text?: string | null
  href?: string | null
  kind?: string
  className?: string
}) {
  const t = id ?? topicFor(appId)
  if (t) return <HelpTip id={t} className={className} />
  noteGap(`${kind}:${appId ?? title ?? '?'}`, text ? 'backend description' : 'none')
  if (text) return <InfoTip title={title ?? appId ?? 'About'} text={text} href={href} className={className} />
  return null
}
