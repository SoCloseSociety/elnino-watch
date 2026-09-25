import type { ReactNode } from 'react'
import { getTopic } from './content'

/**
 * Markdown-lite renderer for help text. Supports only:
 *   blank line = paragraph break; "- " bullet (and "  - " one nested level);
 *   **bold**; [text](https://url); [[topic_id]] / [[topic_id|label]] topic links.
 * No HTML is ever injected.
 */
export function Markdown({ text, onTopic, className = '' }: {
  text: string
  /** called when a [[topic]] link is clicked; without it the link goes to /learn#id */
  onTopic?: (id: string) => void
  className?: string
}) {
  const blocks = text.trim().split(/\n\s*\n/)
  return (
    <div className={`space-y-2.5 ${className}`}>
      {blocks.map((b, i) => {
        const lines = b.split('\n')
        if (lines.every((l) => /^\s*- /.test(l))) return <List key={i} lines={lines} onTopic={onTopic} />
        // a paragraph followed by bullets in the same block
        const first = lines.findIndex((l) => /^\s*- /.test(l))
        if (first > 0 && lines.slice(first).every((l) => /^\s*- /.test(l))) {
          return (
            <div key={i} className="space-y-1.5">
              <p>{inline(lines.slice(0, first).join(' '), onTopic)}</p>
              <List lines={lines.slice(first)} onTopic={onTopic} />
            </div>
          )
        }
        return <p key={i}>{inline(lines.join(' '), onTopic)}</p>
      })}
    </div>
  )
}

function List({ lines, onTopic }: { lines: string[]; onTopic?: (id: string) => void }) {
  // group nested "  - " lines under their parent
  const items: { text: string; sub: string[] }[] = []
  for (const l of lines) {
    const nested = /^\s{2,}- /.test(l)
    const t = l.replace(/^\s*- /, '')
    if (nested && items.length) items[items.length - 1].sub.push(t)
    else items.push({ text: t, sub: [] })
  }
  return (
    <ul className="list-disc space-y-1 pl-5 marker:text-ink-3">
      {items.map((it, i) => (
        <li key={i}>
          {inline(it.text, onTopic)}
          {it.sub.length > 0 && (
            <ul className="mt-1 list-[circle] space-y-1 pl-5 marker:text-ink-3">
              {it.sub.map((s, j) => <li key={j}>{inline(s, onTopic)}</li>)}
            </ul>
          )}
        </li>
      ))}
    </ul>
  )
}

const TOKEN = /(\*\*[^*]+\*\*|\[\[[a-z0-9_]+(?:\|[^\]]+)?\]\]|\[[^\]]+\]\(https?:\/\/[^)\s]+\))/g

export function inline(text: string, onTopic?: (id: string) => void): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  let k = 0
  for (const m of text.matchAll(TOKEN)) {
    const idx = m.index ?? 0
    if (idx > last) out.push(text.slice(last, idx))
    const tok = m[0]
    if (tok.startsWith('**')) {
      out.push(<strong key={k++} className="font-semibold text-ink">{inline(tok.slice(2, -2), onTopic)}</strong>)
    } else if (tok.startsWith('[[')) {
      const [id, label] = tok.slice(2, -2).split('|')
      out.push(<TopicLink key={k++} id={id} label={label} onTopic={onTopic} />)
    } else {
      const mm = /^\[([^\]]+)\]\((.+)\)$/.exec(tok)
      if (mm) {
        out.push(
          <a key={k++} className="link" href={mm[2]} target="_blank" rel="noreferrer">
            {mm[1]} <span aria-hidden>↗</span>
          </a>,
        )
      }
    }
    last = idx + tok.length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

export function TopicLink({ id, label, onTopic }: { id: string; label?: string; onTopic?: (id: string) => void }) {
  const t = getTopic(id)
  const text = label ?? t?.title ?? id
  if (!t) return <span>{text}</span>
  if (onTopic) {
    return (
      <button type="button" className="link cursor-pointer text-left underline decoration-dotted underline-offset-2"
        onClick={() => onTopic(id)} title={t.short}>
        {text}
      </button>
    )
  }
  return (
    <a className="link underline decoration-dotted underline-offset-2" href={`/learn#${id}`} title={t.short}>
      {text}
    </a>
  )
}
