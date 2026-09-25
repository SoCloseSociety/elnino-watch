import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { getTopic } from './content'
import { backTopic, closeTopic, openTopic, registerMount, useHelp } from './store'
import { TopicView } from './TopicView'

/**
 * Global side drawer showing one full help topic. Mount it ONCE (e.g. in Layout);
 * open it from anywhere with `openTopic('oni')` or `useHelp().openTopic('oni')`.
 * While it is mounted, every HelpTip "Learn more" opens it instead of navigating.
 */
export function HelpDrawer() {
  const { topicId, history } = useHelp()
  const topic = getTopic(topicId)
  const panel = useRef<HTMLDivElement>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const returnFocus = useRef<HTMLElement | null>(null)

  useEffect(() => registerMount('drawer'), [])

  // remember what had focus, focus the panel, restore focus on close
  useEffect(() => {
    if (topic) {
      if (!returnFocus.current) returnFocus.current = document.activeElement as HTMLElement | null
      panel.current?.focus()
      scroller.current?.scrollTo(0, 0)
    } else if (returnFocus.current) {
      const el = returnFocus.current
      returnFocus.current = null
      if (el && document.contains(el)) el.focus()
    }
  }, [topic])

  useEffect(() => {
    if (!topic) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        closeTopic()
      } else if (e.key === 'Tab' && panel.current) {
        // keep keyboard focus inside the drawer
        const f = panel.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])')
        if (!f.length) return
        const first = f[0]
        const last = f[f.length - 1]
        if (e.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [topic])

  if (!topic) return null

  return (
    <div className="no-print fixed inset-0 z-[60]">
      <div className="absolute inset-0 bg-black/45" aria-hidden onClick={closeTopic} />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-drawer-title"
        tabIndex={-1}
        className="absolute inset-y-0 right-0 flex w-full max-w-[520px] flex-col border-l border-line-strong bg-surface shadow-2xl outline-none sm:w-[92vw]"
      >
        <header className="flex items-center gap-2 border-b border-line px-4 py-3">
          {history.length > 0 && (
            <button type="button" className="btn !px-2 !py-1 !text-[12px]" onClick={backTopic} aria-label="Back to the previous topic">
              <span aria-hidden>←</span> Back
            </button>
          )}
          <h2 id="help-drawer-title" className="min-w-0 flex-1 truncate text-[15px] font-semibold text-ink">{topic.title}</h2>
          <button type="button" className="rounded-md px-2 py-0.5 text-[22px] leading-none text-ink-3 hover:bg-surface-2 hover:text-ink"
            aria-label="Close help" onClick={closeTopic}>
            ×
          </button>
        </header>
        <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          <TopicView topic={topic} onTopic={openTopic} headingLevel={3} />
        </div>
        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-2.5 text-[12px]">
          <Link className="link" to={`/learn#${topic.id}`} onClick={closeTopic}>Open in the Learn page</Link>
          <Link className="link" to="/learn#glossary" onClick={closeTopic}>Glossary A-Z</Link>
        </footer>
      </div>
    </div>
  )
}
