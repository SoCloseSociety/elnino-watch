import type { ReactNode } from 'react'
import { getTopic } from './content'
import { Markdown } from './Markdown'
import { CATEGORY_LABELS, type ThresholdTable, type Topic } from './types'

/** Full rendering of one topic: body, how to read, why it matters, table, example, related, sources. */
export function TopicView({ topic, onTopic, headingLevel = 3, showTitle = false }: {
  topic: Topic
  /** open a related topic (drawer navigation or in-page jump) */
  onTopic?: (id: string) => void
  headingLevel?: 2 | 3 | 4
  showTitle?: boolean
}) {
  const H = `h${headingLevel}` as 'h2' | 'h3' | 'h4'
  const related = topic.related.map((id) => getTopic(id)).filter((t): t is Topic => !!t)
  return (
    <div className="space-y-4 text-[14px] leading-relaxed text-ink-2">
      {showTitle && <H className="text-[16px] font-semibold text-ink">{topic.title}</H>}
      <p className="text-[14.5px] text-ink">{topic.short}</p>
      <Markdown text={topic.body} onTopic={onTopic} />
      {topic.howToRead && (
        <Section title="How to read it" H={H}>
          <Markdown text={topic.howToRead} onTopic={onTopic} />
        </Section>
      )}
      {topic.thresholds && <Thresholds table={topic.thresholds} />}
      {topic.whyItMatters && (
        <Section title="Why it matters for Koh Samui" H={H} tone="accent">
          <Markdown text={topic.whyItMatters} onTopic={onTopic} />
        </Section>
      )}
      {topic.example && (
        <Section title="Example" H={H}>
          <Markdown text={topic.example} onTopic={onTopic} />
        </Section>
      )}
      {related.length > 0 && (
        <Section title="Related" H={H}>
          <div className="flex flex-wrap gap-1.5">
            {related.map((r) =>
              onTopic ? (
                <button key={r.id} type="button" className="chip cursor-pointer hover:bg-surface-2" onClick={() => onTopic(r.id)} title={r.short}>
                  {r.title}
                </button>
              ) : (
                <a key={r.id} className="chip hover:bg-surface-2" href={`/learn#${r.id}`} title={r.short}>{r.title}</a>
              ),
            )}
          </div>
        </Section>
      )}
      {topic.sources.length > 0 && (
        <Section title="Sources" H={H}>
          <ul className="space-y-1 text-[12.5px]">
            {topic.sources.map((s) => (
              <li key={s.url}>
                <a className="link break-words" href={s.url} target="_blank" rel="noreferrer">{s.title} <span aria-hidden>↗</span></a>
              </li>
            ))}
          </ul>
        </Section>
      )}
      <p className="text-[11px] text-ink-3">{CATEGORY_LABELS[topic.category]} · topic id: <code>{topic.id}</code></p>
    </div>
  )
}

function Section({ title, H, children, tone }: { title: string; H: 'h2' | 'h3' | 'h4'; children: ReactNode; tone?: 'accent' }) {
  return (
    <section
      className={tone === 'accent' ? 'rounded-lg border p-3' : ''}
      style={tone === 'accent' ? { borderColor: 'color-mix(in srgb, var(--accent) 45%, transparent)', background: 'color-mix(in srgb, var(--accent) 7%, transparent)' } : undefined}
    >
      <H className="mb-1.5 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">{title}</H>
      {children}
    </section>
  )
}

export function Thresholds({ table, caption }: { table: ThresholdTable; caption?: string }) {
  return (
    <div>
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[420px] border-collapse text-[12.5px]">
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead className="bg-surface-2 text-left text-ink-2">
            <tr>
              {table.columns.map((c) => (
                <th key={c} scope="col" className="px-2.5 py-1.5 font-semibold">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((r, i) => (
              <tr key={i} className="border-t border-line align-top">
                {r.map((cell, j) => (
                  <td key={j} className={`px-2.5 py-1.5 ${j === 0 ? 'font-medium text-ink tnum' : 'text-ink-2'}`}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {table.note && <p className="mt-1.5 text-[12px] text-ink-3">{table.note}</p>}
    </div>
  )
}
