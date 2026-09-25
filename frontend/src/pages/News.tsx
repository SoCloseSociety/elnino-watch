import { useEffect, useMemo, useRef, useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, facet, qs, useFeedFacets, useSources } from '../api/client'
import type { FeedItem } from '../api/types'
import FeedRow, { KIND_COLOR, KIND_HINT, KIND_LABEL, langName } from '../components/FeedRow'
import { ChipSelect, DateRange, FilterBar, FilteredEmpty, FilterGroup, MultiSelect, SearchFilter, type Opt } from '../components/filters'
import { Card, ErrorBox, PageHeader, Skeleton } from '../components/ui'
import { FEED_KIND_TOPIC, HelpFor, HelpTip, PageGuide, sourceTopic } from '../help'
import { fmtDateTz, relTime } from '../lib/format'
import { safeUrl } from '../lib/geo'
import { sinceFromPreset, useUrlFilters } from '../lib/urlFilters'

const PAGE = 40
const KINDS = ['official', 'news', 'social', 'research']
const LOCAL_TAGS = ['samui', 'thailand']
const tsOf = (i: FeedItem) => i.published_at ?? i.fetched_at
const PRESET_LABEL: Record<string, string> = { '24h': 'last 24 h', '7d': 'last 7 days', '30d': 'last 30 days', '90d': 'last 90 days' }

/** "YYYY-MM-DD" (custom "to" date) -> end of that day, so the day itself is included. */
const untilParam = (u: string) => (/^\d{4}-\d{2}-\d{2}$/.test(u) ? `${u}T23:59:59Z` : u || undefined)

export default function News() {
  const f = useUrlFilters({ kind: 'list', source: 'list', lang: 'list', tag: 'list', since: 'str', until: 'str', geo: 'bool', q: 'str' })
  const v = f.values
  const wide = useMedia('(min-width: 768px)')
  const [more, setMore] = useState(false)
  const params = useMemo(() => ({
    kind: f.api.kind, source: f.api.source, lang: f.api.lang, tag: f.api.tag, q: f.api.q,
    since: sinceFromPreset(v.since), until: untilParam(v.until), has_geo: v.geo ? 'true' : undefined,
  }), [f.api, v.since, v.until, v.geo])

  const facets = useFeedFacets(params)
  const all = useFeedFacets({})
  const geoCount = useFeedFacets({ ...params, has_geo: 'true' })
  const sources = useSources()
  const srcMeta = useMemo(() => new Map((sources.data ?? []).map((s) => [s.name, s])), [sources.data])

  const inf = useInfiniteQuery({
    queryKey: ['feed-inf', params],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => api<FeedItem[]>(`/feed${qs({ ...params, limit: PAGE, offset: pageParam || undefined })}`),
    getNextPageParam: (last, pages) => (last.length < PAGE ? undefined : pages.length * PAGE),
    refetchInterval: false,
  })
  const items = useMemo(() => {
    const seen = new Set<string>()
    const out: FeedItem[] = []
    for (const p of inf.data?.pages ?? []) for (const i of p) {
      const k = `${i.source}:${i.ext_id}`
      if (!seen.has(k)) { seen.add(k); out.push(i) }
    }
    return out
  }, [inf.data])

  // "N new" pill: items newer than the top of the loaded list
  const newest = inf.data?.pages[0]?.[0] ? tsOf(inf.data.pages[0][0]) : null
  const head = useQuery({
    queryKey: ['feed-head', params],
    queryFn: () => api<FeedItem[]>(`/feed${qs({ ...params, limit: 50 })}`),
    enabled: !!inf.data,
  })
  const fresh = newest ? (head.data ?? []).filter((i) => tsOf(i) > newest).length : 0

  // infinite scroll
  const sentinel = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = sentinel.current
    if (!el) return
    const io = new IntersectionObserver((es) => {
      if (es[0].isIntersecting && inf.hasNextPage && !inf.isFetchingNextPage) inf.fetchNextPage()
    }, { rootMargin: '600px' })
    io.observe(el)
    return () => io.disconnect()
  }, [inf])

  // ------------------------------------------------------------------ filter options (counts from /api/feed/facets)
  const fk = facet(facets.data, 'kind')
  const kindOpts: Opt[] = KINDS.filter((k) => fk.some((x) => x.value === k) || v.kind.includes(k)).map((k) => ({
    value: k, text: KIND_LABEL[k], count: fk.find((x) => x.value === k)?.count ?? 0, color: KIND_COLOR[k], title: KIND_HINT[k],
    help: FEED_KIND_TOPIC[k] ? <HelpTip id={FEED_KIND_TOPIC[k]} label={`What is a "${KIND_LABEL[k]}" item?`} /> : undefined,
  }))
  const srcOpts: Opt[] = withSelected(facet(facets.data, 'source'), v.source).map((x) => {
    const m = srcMeta.get(x.value)
    return { value: x.value, text: m?.title ?? x.value, count: x.count, title: m ? `${m.title} (${m.provider}) -- ${x.value}` : x.value }
  })
  const langOpts: Opt[] = withSelected(facet(facets.data, 'lang'), v.lang).map((x) => ({
    value: x.value, text: `${x.value} -- ${langName(x.value)}`, count: x.count, title: langName(x.value),
  }))
  const tagFacet = withSelected(facet(facets.data, 'tag'), v.tag)
  // samui / thailand first (prominent), then by count
  const tagOpts: Opt[] = [
    ...LOCAL_TAGS.map((t) => ({ value: t, count: tagFacet.find((x) => x.value === t)?.count ?? 0 })),
    ...tagFacet.filter((x) => !LOCAL_TAGS.includes(x.value)),
  ].map((x) => ({
    value: x.value, text: `#${x.value}`, count: x.count,
    color: LOCAL_TAGS.includes(x.value) ? 'var(--warning)' : undefined,
    title: LOCAL_TAGS.includes(x.value) ? `Items that mention ${x.value === 'samui' ? 'Koh Samui' : 'Thailand'}` : undefined,
  }))

  const total = facets.data?.total ?? null
  const grand = all.data?.total ?? null
  const human: string[] = [
    ...(v.kind.length ? [`kind: ${v.kind.map((k) => KIND_LABEL[k] ?? k).join(' or ')}`] : []),
    ...(v.source.length ? [`source: ${v.source.map((s) => srcMeta.get(s)?.title ?? s).join(' or ')}`] : []),
    ...(v.lang.length ? [`language: ${v.lang.map(langName).join(' or ')}`] : []),
    ...(v.tag.length ? [`tag: ${v.tag.map((t) => `#${t}`).join(' or ')}`] : []),
    ...(v.since ? [`date: ${PRESET_LABEL[v.since] ?? `from ${v.since}`}${v.until ? ` to ${v.until}` : ''}`] : v.until ? [`date: until ${v.until}`] : []),
    ...(v.geo ? ['has a map location'] : []),
    ...(v.q ? [`text: "${v.q}"`] : []),
  ]
  const summary = total === null ? (facets.isLoading ? 'Counting...' : '') : (
    <><b className="text-ink">{total.toLocaleString('en-GB')}</b>{grand !== null && f.active ? <> of {grand.toLocaleString('en-GB')}</> : null} items{items.length && items.length < total ? <> · {items.length.toLocaleString('en-GB')} loaded</> : null}</>
  )
  const secondary = more ? '' : 'hidden xl:flex'

  return (
    <div className="space-y-3">
      <PageHeader title="News & social" help={<HelpTip id="news_signals" size="md" />}
        sub="Official bulletins, press and social media about El Nino and Koh Samui / Thailand, collected continuously. Titles stay in their original language; links open in a new tab." />
      <PageGuide page="news" />

      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-3 xl:grid-cols-[300px_minmax(0,1fr)] 2xl:grid-cols-[330px_minmax(0,1fr)] xl:gap-4">
        <FilterBar tour="news-filters" sticky={wide} active={f.active} onReset={f.reset} summary={summary}
          className="xl:max-h-[calc(100dvh-5rem)] xl:overflow-y-auto">
          <FilterGroup label="Search" className="w-full sm:w-[300px] xl:w-full" help={<HelpTip id="filters_feed" label="How do the news filters work?" />}>
            <SearchFilter value={v.q} onChange={(s) => f.set('q', s)} placeholder="Title, summary or author" label="Search the feed" className="w-full" />
          </FilterGroup>
          <FilterGroup label="Kind" className="xl:w-full" help={<HelpTip id="news_signals" label="What are the kinds of items?" />}>
            <ChipSelect options={kindOpts} selected={v.kind} onToggle={(x) => f.toggle('kind', x)} />
          </FilterGroup>
          <FilterGroup label="Place tags" className="xl:w-full" help={<HelpTip id="filters_feed" label="What are tags?" />}>
            <ChipSelect options={tagOpts.slice(0, LOCAL_TAGS.length)} selected={v.tag} onToggle={(x) => f.toggle('tag', x)} />
          </FilterGroup>
          <span className="self-end xl:hidden">
            <button type="button" className="fchip" aria-expanded={more} onClick={() => setMore((m) => !m)}>
              {more ? 'Fewer filters' : `More filters${f.active ? ` (${f.active} active)` : ''}`} <span aria-hidden>{more ? '▴' : '▾'}</span>
            </button>
          </span>
          <FilterGroup label="Date" className={`${secondary} xl:w-full`} help={<HelpTip id="freshness" label="Which date is used?" />}>
            <DateRange since={v.since} until={v.until} onSince={(s) => f.set('since', s)} onUntil={(u) => f.set('until', u)} />
          </FilterGroup>
          <FilterGroup label="Source" className={`${secondary} xl:w-full`} help={<HelpTip id="sources_page" label="What is a source?" />}>
            <MultiSelect label="Source" options={srcOpts} selected={v.source} onToggle={(x) => f.toggle('source', x)} onClear={() => f.set('source', [])} placeholder="Search sources" />
            {v.source.map((s) => (
              <span key={s} className="inline-flex items-center gap-0.5">
                <button type="button" className="fchip" aria-pressed onClick={() => f.toggle('source', s)} title="Remove this source filter">
                  {srcMeta.get(s)?.title ?? s} <span aria-hidden>×</span>
                </button>
                <HelpFor appId={s} id={sourceTopic(s)} kind="source" title={srcMeta.get(s)?.title ?? s} text={srcMeta.get(s)?.description}
                  href={safeUrl(srcMeta.get(s)?.homepage) ? srcMeta.get(s)?.homepage : undefined} />
              </span>
            ))}
          </FilterGroup>
          <FilterGroup label="Language" className={`${secondary} xl:w-full`} help={<HelpTip id="filters_feed" label="How does the language filter work?" />}>
            {langOpts.length ? <ChipSelect options={langOpts} selected={v.lang} onToggle={(x) => f.toggle('lang', x)} limit={6} /> : <span className="text-[12px] text-ink-3">No language for these filters</span>}
          </FilterGroup>
          <FilterGroup label="Topic tags" className={`${secondary} xl:w-full`} help={<HelpTip id="filters_feed" label="What are topic tags?" />}>
            <ChipSelect options={tagOpts.slice(LOCAL_TAGS.length)} selected={v.tag} onToggle={(x) => f.toggle('tag', x)} limit={10} />
          </FilterGroup>
          <FilterGroup label="Location" className={`${secondary} xl:w-full`} help={<HelpTip id="map_overlays" label="What does 'has a map location' mean?" />}>
            <ChipSelect options={[{ value: 'geo', text: 'Has a map location', count: geoCount.data?.total ?? null, title: 'Only items the source geolocated (they also appear on the Map page)' }]}
              selected={v.geo ? ['geo'] : []} onToggle={() => f.set('geo', !v.geo)} />
          </FilterGroup>
        </FilterBar>

        <Card pad={false} tour="news-list" title="Feed" help={<HelpTip id="news_signals" />}
          right={<span className="text-[11px] text-ink-3">newest first · times in UTC</span>}
          footer={
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-ink-3">
              {newest ? <span>Newest item {fmtDateTz(newest, 'UTC')} ({relTime(newest)})</span> : <span>No item yet</span>}
              <span aria-hidden>·</span>
              <span>Collector state on the <Link className="link" to="/sources?category=news,social,official">Sources</Link> page</span>
              <HelpTip id="retention" label="How long are items kept?" />
            </div>
          }>
          <div className="relative px-4">
            {fresh > 0 && (
              <div className="sticky top-2 z-10 flex justify-center">
                <button type="button" className="btn btn-primary mt-2 !rounded-full shadow-lg" onClick={() => { inf.refetch(); document.querySelector('main')?.scrollTo({ top: 0, behavior: 'smooth' }) }}>
                  ▲ {fresh} new
                </button>
              </div>
            )}
            {inf.isLoading ? <div className="space-y-3 py-4"><Skeleton h={60} /><Skeleton h={60} /><Skeleton h={60} /></div> : inf.isError ? (
              <div className="py-4"><ErrorBox error={inf.error} what="feed" /></div>
            ) : !items.length ? (
              <div className="py-4">
                {f.active ? (
                  <FilteredEmpty what="items" filters={human} onReset={f.reset} total={grand}>
                    {v.kind.includes('social') && (
                      <p className="mt-1 text-[12px] text-ink-3">Some social networks (X, Telegram) need credentials: they show as <code>needs_config</code> on the <Link className="link" to="/sources">Sources</Link> page until configured.</p>
                    )}
                  </FilteredEmpty>
                ) : (
                  <p className="py-4 text-center text-[13px] text-ink-2">No items collected yet. Status of the news / social / official collectors: <Link className="link" to="/sources">Sources</Link>.</p>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-[minmax(0,1fr)] min-[112.5rem]:grid-cols-2 min-[112.5rem]:gap-x-8">
                {items.map((i) => (
                  <div key={`${i.source}:${i.ext_id}`} className="border-b border-line">
                    <FeedRow item={i} onTag={(t) => f.toggle('tag', t)} activeTags={v.tag} />
                  </div>
                ))}
              </div>
            )}
            <div ref={sentinel} className="py-4 text-center text-[12px] text-ink-3">
              {inf.isFetchingNextPage ? 'Loading...' : inf.hasNextPage ? (
                <button type="button" className="btn" onClick={() => inf.fetchNextPage()}>Load more</button>
              ) : items.length ? `End of the feed (${items.length.toLocaleString('en-GB')} items)` : ''}
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}

/** Keep selected values in the option list even when the facet no longer returns them (count 0). */
function withSelected(list: { value: string; count: number }[], selected: string[]) {
  const out = [...list]
  for (const s of selected) if (!out.some((x) => x.value === s)) out.push({ value: s, count: 0 })
  return out
}

/** true when the media query matches (sticky filter bars only where they do not eat the phone screen). */
function useMedia(q: string) {
  const [m, setM] = useState(() => typeof window !== 'undefined' && !!window.matchMedia?.(q).matches)
  useEffect(() => {
    const mq = window.matchMedia?.(q)
    if (!mq) return
    const on = () => setM(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [q])
  return m
}
