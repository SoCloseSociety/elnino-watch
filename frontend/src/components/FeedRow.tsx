import { useMemo } from 'react'
import { useSources } from '../api/client'
import type { FeedItem } from '../api/types'
import { FEED_KIND_TOPIC, HelpFor, HelpTip, sourceTopic } from '../help'
import { fmtDateTz, relTime, tagsOf, toneText } from '../lib/format'
import { safeUrl } from '../lib/geo'

export const KIND_LABEL: Record<string, string> = { official: 'Official', news: 'Press', social: 'Social', research: 'Research' }
export const KIND_COLOR: Record<string, string> = { official: 'var(--s1)', news: 'var(--s3)', social: 'var(--s7)', research: 'var(--s4)' }
/** What each feed kind is, in one line (badge tooltip; the "?" opens the full topic). */
export const KIND_HINT: Record<string, string> = {
  official: 'Official: a bulletin, warning or statement issued by an agency (NOAA, WMO, TMD, ASMC...). The closest thing to a primary source.',
  news: 'Press: a news article. Context and reporting, not a measurement.',
  social: 'Social: a public post (Bluesky, X, Mastodon, Reddit, Telegram...). Unverified; useful for early signals only.',
  research: 'Research: a scientific publication or newsletter.',
}
const LOCAL_TAGS = new Set(['samui', 'thailand'])

/** Source names -> {title, description} from /api/sources (cached, one request for all rows). */
function useSourceMeta() {
  const s = useSources()
  return useMemo(() => new Map((s.data ?? []).map((x) => [x.name, x])), [s.data])
}

export default function FeedRow({ item, compact = false, onTag, activeTags }: {
  item: FeedItem
  compact?: boolean
  /** clicking a tag chip filters by it (News page) */
  onTag?: (tag: string) => void
  activeTags?: string[]
}) {
  const meta = useSourceMeta().get(item.source)
  const url = safeUrl(item.url)
  const ts = item.published_at ?? item.fetched_at
  const tags = tagsOf(item.tags)
  const local = tags.some((t) => /samui|thailand|thailande/i.test(t))
  const Title = url ? 'a' : 'span'
  // social posts often repeat the title as the summary: only show the summary when it adds something
  const norm = (x: string | null) => (x ?? '').replace(/\s+/g, ' ').replace(/(\.\.\.|…)$/, '').trim().toLowerCase()
  const t = norm(item.title)
  const sm = norm(item.summary)
  const showSummary = !!sm && !(t && (sm.startsWith(t.slice(0, 60)) || t.startsWith(sm.slice(0, 60))))
  const kindTopic = FEED_KIND_TOPIC[item.kind]
  const when = `${item.published_at ? 'Published' : 'Collected (no publication date given)'} ${fmtDateTz(ts, 'UTC')} (${fmtDateTz(ts, 'ICT')})`
  // local tags first, then the rest
  const shownTags = [...tags.filter((x) => LOCAL_TAGS.has(x)), ...tags.filter((x) => !LOCAL_TAGS.has(x))].slice(0, compact ? 0 : 8)
  return (
    <article className={`flex gap-3 ${compact ? 'py-2' : 'py-3'}`}>
      {!compact && item.image && safeUrl(item.image) && (
        <img src={item.image} alt="" loading="lazy" referrerPolicy="no-referrer"
          className="hidden h-16 w-24 shrink-0 rounded-md object-cover sm:block"
          onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')} />
      )}
      <div className="min-w-0 flex-1">
        <div className="mb-0.5 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] text-ink-3">
          <span className="inline-flex items-center gap-0.5">
            <span className="chip" title={KIND_HINT[item.kind] ?? item.kind}
              style={{ color: KIND_COLOR[item.kind] ? toneText(KIND_COLOR[item.kind]) : 'var(--ink-2)', borderColor: 'currentColor' }}>
              {item.kind === 'official' && <span aria-hidden>■</span>}{KIND_LABEL[item.kind] ?? item.kind}
            </span>
            {!compact && kindTopic && <HelpTip id={kindTopic} label={`What is a "${KIND_LABEL[item.kind] ?? item.kind}" item?`} />}
          </span>
          <span className="inline-flex min-w-0 items-center gap-0.5">
            <span className="max-w-[240px] truncate font-semibold text-ink-2" title={meta ? `${meta.title} (${meta.provider}) -- collector "${item.source}"` : item.source}>
              {shortTitle(meta?.title) ?? item.source}
            </span>
            {!compact && (
              <HelpFor appId={item.source} id={sourceTopic(item.source)} kind="source" title={meta?.title ?? item.source}
                text={meta?.description} href={safeUrl(meta?.homepage) ? meta?.homepage : undefined} />
            )}
          </span>
          {item.author && <span className="max-w-[45%] truncate" title={item.author}>· {item.author}</span>}
          {item.lang && <span className="uppercase" title={`Language: ${langName(item.lang)}`}>· {item.lang}</span>}
          {local && compact && <span className="chip" style={{ color: 'var(--warning)', borderColor: 'currentColor' }}>Thailand / Samui</span>}
          <time dateTime={ts} title={when} className="ml-auto whitespace-nowrap tnum">
            {relTime(ts)}{!compact && <span className="hidden sm:inline"> · {fmtDateTz(ts, 'UTC')}</span>}
          </time>
        </div>
        <Title {...(url ? { href: url, target: '_blank', rel: 'noreferrer' } : {})}
          className={`block font-medium leading-snug text-ink ${url ? 'hover:underline' : ''} ${compact ? 'line-clamp-2 text-[13px]' : 'line-clamp-3 text-[14px]'}`}>
          {item.title || '(untitled)'}
        </Title>
        {!compact && showSummary && <p className="mt-1 line-clamp-3 text-[13px] text-ink-2">{item.summary}</p>}
        {shownTags.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1" aria-label="Tags">
            {shownTags.map((tg) => {
              const isLocal = LOCAL_TAGS.has(tg)
              const on = activeTags?.includes(tg)
              const style = isLocal ? { color: 'var(--warning)', borderColor: 'currentColor' } : undefined
              return onTag ? (
                <button key={tg} type="button" className={`chip max-sm:min-h-9 hover:bg-surface-2 ${on ? 'font-semibold' : ''}`} style={style}
                  aria-pressed={!!on} title={on ? `Remove the "${tg}" tag filter` : `Show only items tagged "${tg}"`} onClick={() => onTag(tg)}>
                  #{tg}
                </button>
              ) : <span key={tg} className="chip" style={style}>#{tg}</span>
            })}
          </div>
        )}
      </div>
    </article>
  )
}

/** "X (Twitter) -- verified accounts + ..." -> "X (Twitter)"; the full title stays in the tooltip. */
export function shortTitle(t: string | null | undefined): string | undefined {
  if (!t) return undefined
  return t.split(' -- ')[0]
}

let names: Intl.DisplayNames | null = null
/** "th" -> "Thai" (English names; falls back to the code). */
export function langName(code: string | null | undefined): string {
  if (!code) return 'unknown'
  try {
    names ??= new Intl.DisplayNames(['en'], { type: 'language' })
    return names.of(code) ?? code
  } catch {
    return code
  }
}
