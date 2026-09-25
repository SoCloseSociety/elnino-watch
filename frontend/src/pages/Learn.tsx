import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useSeo } from '../seo'
import {
  allTopics, FAQ, FACTOR_ACTIONS, getTopic, isTopicId, LEVEL_ACTIONS, MYTHS, searchTopics,
} from '../help/content'
import { EnsoDiagram } from '../help/EnsoDiagram'
import { PAGE_GUIDES, PAGE_IDS } from '../help/guides'
import { Markdown } from '../help/Markdown'
import { startTour } from '../help/store'
import { Thresholds, TopicView } from '../help/TopicView'
import { CATEGORY_LABELS, type PageId, type Topic } from '../help/types'

const SECTIONS = [
  { id: 'el-nino-in-5-minutes', label: 'El Nino in 5 minutes' },
  { id: 'reading-this-dashboard', label: 'Reading this dashboard' },
  { id: 'risk-levels', label: 'Koh Samui risk levels' },
  { id: 'what-to-do', label: 'What to do at each level' },
  { id: 'glossary', label: 'Glossary' },
  { id: 'faq', label: 'FAQ' },
  { id: 'myths', label: 'Myths vs facts' },
  { id: 'limitations', label: 'Limitations' },
  { id: 'sources', label: 'Sources' },
] as const

const PAGE_PATH: Record<PageId, string> = {
  overview: '/', map: '/map', indices: '/indices', news: '/news', samui: '/samui', history: '/history', prep: '/prep', sources: '/sources', places: '/places', cams: '/cams',
}
const PAGE_NAME: Record<PageId, string> = {
  overview: 'Overview', map: 'Map', indices: 'Indices', news: 'News & social', samui: 'Koh Samui', history: 'Past El Ninos', prep: 'Preparedness', sources: 'Sources', places: 'Places', cams: 'Cams',
}
/** Level colours: the app's status tokens (same order as lib/format LEVELS). */
const LEVEL_COLOR = ['var(--good)', 'var(--warning)', 'var(--serious)', 'var(--critical)', 'var(--extreme)']

function scrollToId(id: string) {
  const el = document.getElementById(id)
  if (!el) return
  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  // scroll only the page's own scroll area (#main): scrollIntoView would also shift the fixed app shell
  const main = document.getElementById('main')
  if (main && main.contains(el)) {
    const top = el.getBoundingClientRect().top - main.getBoundingClientRect().top + main.scrollTop - 12
    main.scrollTo({ top, behavior: reduced ? 'auto' : 'smooth' })
  } else {
    el.scrollIntoView({ block: 'start', behavior: reduced ? 'auto' : 'smooth' })
  }
}

export default function Learn() {
  const loc = useLocation()
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState<Set<string>>(() => new Set())

  // /learn/<topic> is its own indexable URL (server-rendered by backend/app/seo.py)
  const { topic: topicParam } = useParams()
  const seoTopic = topicParam ? getTopic(topicParam) : undefined
  useSeo(seoTopic ? {
    title: `${seoTopic.title}: El Nino explained`.slice(0, 60),
    description: seoTopic.short.slice(0, 160),
    path: `/learn/${seoTopic.id}`,
  } : undefined)

  // #hash (or /learn/<topic>): a topic id opens its glossary entry; a section id scrolls to it
  useEffect(() => {
    const id = topicParam ?? decodeURIComponent(loc.hash.replace(/^#/, ''))
    if (!id) return
    if (isTopicId(id)) {
      setQ('')
      setOpen((s) => new Set(s).add(id))
    }
    // after the layout's own scroll-to-top on navigation, and after the entry renders
    const t = window.setTimeout(() => scrollToId(id), 80)
    return () => window.clearTimeout(t)
  }, [loc.hash, topicParam])

  const goTopic = (id: string) => nav({ hash: `#${id}` })

  // highlight the section being read in the side table of contents (wide screens)
  const [active, setActive] = useState<string>(SECTIONS[0].id)
  useEffect(() => {
    const main = document.getElementById('main')
    if (!main) return
    const onScroll = () => {
      const top = main.getBoundingClientRect().top + 120
      let cur: string = SECTIONS[0].id
      for (const sec of SECTIONS) {
        const el = document.getElementById(sec.id)
        if (el && el.getBoundingClientRect().top <= top) cur = sec.id
      }
      setActive(cur)
    }
    onScroll()
    main.addEventListener('scroll', onScroll, { passive: true })
    return () => main.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className="mx-auto max-w-[1100px] pb-16 xl:grid xl:max-w-[1480px] xl:grid-cols-[210px_minmax(0,1fr)] xl:gap-8 min-[112.5rem]:max-w-[1680px] min-[112.5rem]:grid-cols-[240px_minmax(0,1fr)]">
      <nav aria-label="On this page" className="mb-6 flex flex-wrap gap-1.5 text-[12px] xl:sticky xl:top-0 xl:order-first xl:mb-0 xl:max-h-[calc(100dvh-4rem)] xl:flex-col xl:flex-nowrap xl:gap-0.5 xl:self-start xl:overflow-y-auto xl:border-r xl:border-line xl:pt-1 xl:pr-3 xl:text-[13px]">
        <span className="hidden px-2 pb-1 text-[11px] font-semibold tracking-wide text-ink-3 uppercase xl:block">On this page</span>
        {SECTIONS.map((s) => (
          <a key={s.id} href={`#${s.id}`} aria-current={active === s.id ? 'location' : undefined}
            className={`chip hover:bg-surface-2 xl:!rounded-md xl:!border-transparent xl:!px-2 xl:!py-1.5 xl:!text-[13px] ${active === s.id ? 'xl:!bg-surface-2 xl:font-semibold xl:text-ink' : ''}`}
            onClick={(e) => { e.preventDefault(); nav({ hash: `#${s.id}` }) }}>
            {s.label}
          </a>
        ))}
      </nav>
      <div className="min-w-0">
      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">Learn</h1>
        <p className="mt-0.5 max-w-[70ch] text-[13px] text-ink-2">
          Everything on this dashboard, explained in plain English: what El Nino is, how to read each number and map,
          how the Koh Samui risk level is decided, and what to do.
        </p>
      </div>

      <div className="space-y-10">
        <FiveMinutes goTopic={goTopic} />
        <ReadingDashboard goTopic={goTopic} />
        <RiskLevels goTopic={goTopic} />
        <WhatToDo />
        <Glossary q={q} setQ={setQ} open={open} setOpen={setOpen} goTopic={goTopic} />
        <Faq goTopic={goTopic} />
        <Myths goTopic={goTopic} />
        <Limitations goTopic={goTopic} />
        <Sources />
      </div>
      </div>
    </div>
  )
}

function Section({ id, title, intro, children }: { id: string; title: string; intro?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="scroll-mt-4">
      <h2 id={`${id}-h`} className="text-[18px] font-semibold tracking-tight text-ink">{title}</h2>
      {intro && <div className="mt-1 max-w-[75ch] text-[13.5px] leading-relaxed text-ink-2">{intro}</div>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

function TopicChip({ id, goTopic }: { id: string; goTopic: (id: string) => void }) {
  const t = getTopic(id)
  if (!t) return null
  return (
    <a href={`#${id}`} className="chip max-w-full whitespace-normal hover:bg-surface-2" title={t.short}
      onClick={(e) => { e.preventDefault(); goTopic(id) }}>
      {t.title}
    </a>
  )
}

// --------------------------------------------------------------------------- 1. El Nino in 5 minutes

function FiveMinutes({ goTopic }: { goTopic: (id: string) => void }) {
  return (
    <Section id="el-nino-in-5-minutes" title="El Nino in 5 minutes">
      <div className="grid gap-5">
        <div className="card space-y-3 p-4 text-[14px] leading-relaxed text-ink-2">
          <Markdown onTopic={goTopic} text={`**1. The Pacific normally leans one way.** Along the equator, the [[trade_winds|trade winds]] blow from east to west. They push the warm surface water towards Indonesia, where it piles up as the [[warm_pool|warm pool]]. Near South America, cold deep water rises to replace it. Warm water heats the air, which rises and makes rain clouds over the west; the air sinks, dry, over the cool east. That loop is the [[walker_circulation|Walker circulation]].

**2. El Nino is when that balance tips.** The trade winds weaken. The warm water slides back east (often helped by [[westerly_wind_burst|westerly wind bursts]] and [[kelvin_wave|Kelvin waves]] under the surface). The [[thermocline]], the boundary with the cold deep water, gets deeper in the east, so the cold water can no longer come up. The central and eastern Pacific warm up by 1 to 3 °C or more.

**3. The rain moves with the warm water.** The big rain clouds shift towards the central Pacific. Over Indonesia and Southeast Asia, air tends to sink instead, and sinking air means fewer clouds. That is why El Nino years are usually drier and hotter in Thailand, especially in the hot season and early rainy season.

**4. It is measured with one box of ocean.** Scientists watch the sea temperature [[anomaly]] in the [[nino34|Nino 3.4]] region. A 3-month average of +0.5 °C or more ([[oni|ONI]], and since 2026 the official [[roni|RONI]]) plus a response of the winds = El Nino. Around +1.5 °C = strong; +2.0 °C and above = very strong ("super" in the media).

**5. It follows a calendar.** An El Nino typically forms in March-June, peaks around November-January and fades the next spring. For Samui, the season that matters most is the dry, hot season right after the peak: February-April 2027.

**6. It shifts the odds, it does not decide the weather.** El Nino does not stop the northeast monsoon: Samui can still flood in November. It makes a weak monsoon and a long, hot dry season more likely. This dashboard turns those odds into a concrete level for the island, with every rule written down.`} />
        </div>
        <EnsoDiagram />
        <p className="text-[12px] text-ink-3">
          Schematic cross-section along the equator (not to scale), based on NOAA's descriptions of ENSO (CPC FAQ, Climate.gov).
        </p>
        <div className="flex flex-wrap gap-1.5">
          {['enso', 'el_nino', 'la_nina', 'el_nino_thailand', 'enso_lifecycle', 'strength_categories', 'past_events', 'event_2026'].map((id) => (
            <TopicChip key={id} id={id} goTopic={goTopic} />
          ))}
        </div>
      </div>
    </Section>
  )
}

// --------------------------------------------------------------------------- 2. Reading this dashboard

function ReadingDashboard({ goTopic }: { goTopic: (id: string) => void }) {
  const nav = useNavigate()
  const tour = (p: PageId) => {
    nav(PAGE_PATH[p])
    window.setTimeout(() => startTour(p), 400)
  }
  return (
    <Section id="reading-this-dashboard" title="Reading this dashboard" intro="Page by page: what each one is for and how to read it. Every page also has a small guide at the top and a guided tour.">
      <div className="grid grid-cols-[minmax(0,1fr)] gap-4 md:grid-cols-2">
        {PAGE_IDS.map((p) => {
          const g = PAGE_GUIDES[p]
          return (
            <article key={p} className="card flex min-w-0 flex-col p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="text-[15px] font-semibold text-ink">
                  <Link className="link" to={PAGE_PATH[p]}>{PAGE_NAME[p]}</Link>
                </h3>
                <button type="button" className="btn !px-2.5 !py-1 !text-[12px]" onClick={() => tour(p)}>Take the tour</button>
              </div>
              <p className="mt-1 text-[13px] text-ink-2">{g.intro}</p>
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-[13px] leading-relaxed text-ink-2 marker:text-ink-3">
                {g.steps.map((s, i) => <li key={i}>{s}</li>)}
              </ol>
              <div className="mt-auto flex flex-wrap gap-1.5 pt-3">
                {g.topics.map((id) => <TopicChip key={id} id={id} goTopic={goTopic} />)}
              </div>
            </article>
          )
        })}
      </div>
    </Section>
  )
}

// --------------------------------------------------------------------------- 3. Risk levels

const FACTOR_IDS = ['factor_enso', 'factor_water', 'factor_heat', 'factor_flood', 'factor_cyclone_wind', 'factor_sea_state', 'factor_air', 'factor_marine_heat', 'factor_news']

function RiskLevels({ goTopic }: { goTopic: (id: string) => void }) {
  const levels = getTopic('risk_levels')
  const factors = getTopic('risk_factors')
  const rules = getTopic('risk_rules')
  const coverage = getTopic('data_coverage')
  return (
    <Section id="risk-levels" title="Koh Samui risk levels explained"
      intro="One level for the island, from 0 Normal to 4 Leave. It is computed from 9 factors with 4 written rules, and every factor shows its value, threshold and source.">
      <div className="space-y-5">
        <div className="grid gap-2 sm:grid-cols-5">
          {LEVEL_ACTIONS.map((l) => (
            <div key={l.key} className="card p-3" style={{ borderTop: `3px solid ${LEVEL_COLOR[l.n]}` }}>
              <div className="text-[12px] font-semibold tnum" style={{ color: LEVEL_COLOR[l.n] }}>{l.n} · {l.label}</div>
              <p className="mt-1 text-[12.5px] leading-snug text-ink-2">{l.meaning}</p>
            </div>
          ))}
          <div className="card p-3 sm:col-span-5" style={{ borderTop: '3px dashed var(--line-strong)' }}>
            <div className="text-[12px] font-semibold text-ink-2">? · Unknown</div>
            <p className="mt-1 text-[12.5px] leading-snug text-ink-2">
              A critical factor has no current data. The page shows "at least ..." from the factors that do have data. Never read it as "all clear".
            </p>
          </div>
        </div>

        {factors?.thresholds && (
          <div>
            <h3 className="mb-2 text-[14px] font-semibold text-ink">The 9 factors</h3>
            <Thresholds table={factors.thresholds} caption="Risk factors" />
          </div>
        )}

        {rules && (
          <div className="card p-4">
            <h3 className="mb-2 text-[14px] font-semibold text-ink">How the factors combine</h3>
            <div className="text-[13.5px] leading-relaxed text-ink-2">
              <Markdown text={rules.body} onTopic={goTopic} />
              {rules.example && <p className="mt-2 text-[13px]"><b className="text-ink">Example:</b> {rules.example}</p>}
            </div>
          </div>
        )}

        {coverage && (
          <div className="card p-4 text-[13.5px] leading-relaxed text-ink-2">
            <h3 className="mb-2 text-[14px] font-semibold text-ink">Missing and old data</h3>
            <Markdown text={coverage.body} onTopic={goTopic} />
          </div>
        )}

        <div>
          <h3 className="mb-2 text-[14px] font-semibold text-ink">Each factor's thresholds</h3>
          <div className="space-y-2">
            {FACTOR_IDS.map((id) => {
              const t = getTopic(id)
              if (!t) return null
              return (
                <details key={id} className="card group">
                  <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-2.5 text-[13.5px] font-medium text-ink">
                    <span aria-hidden className="text-ink-3 transition-transform group-open:rotate-90">›</span>
                    {t.title.replace(/^Factor: /, '')}
                    <span className="ml-auto hidden text-[12px] font-normal text-ink-3 md:inline">{t.thresholds?.note?.split('.')[0]}</span>
                  </summary>
                  <div className="border-t border-line px-4 py-3">
                    <TopicView topic={t} onTopic={goTopic} headingLevel={4} />
                  </div>
                </details>
              )
            })}
          </div>
        </div>
        {levels && <p className="text-[12.5px] text-ink-3">{levels.whyItMatters}</p>}
      </div>
    </Section>
  )
}

// --------------------------------------------------------------------------- 4. What to do

function WhatToDo() {
  const factorNames: Record<string, string> = {
    enso: 'El Nino', water: 'Water', heat: 'Heat', flood: 'Flood', cyclone_wind: 'Cyclone / wind',
    sea_state: 'Sea state', air: 'Air quality', marine_heat: 'Marine heat', news: 'News',
  }
  return (
    <Section id="what-to-do" title="What to do at each level"
      intro="These are the action lists the risk engine shows on the Samui page. When a factor is raised, its own action is added. Official instructions (TMD, DDPM 1784, the province) always come first.">
      <div className="grid gap-3 md:grid-cols-2">
        {LEVEL_ACTIONS.map((l) => (
          <div key={l.key} className="card p-4" style={{ borderLeft: `4px solid ${LEVEL_COLOR[l.n]}` }}>
            <h3 className="text-[14px] font-semibold" style={{ color: LEVEL_COLOR[l.n] }}>{l.n} · {l.label}</h3>
            <p className="mt-0.5 text-[12.5px] text-ink-3">{l.meaning}</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px] leading-relaxed text-ink-2">
              {l.actions.map((a) => <li key={a}>{a}</li>)}
            </ul>
          </div>
        ))}
        <div className="card p-4">
          <h3 className="text-[14px] font-semibold text-ink">Extra action when a factor is raised</h3>
          <ul className="mt-2 space-y-1.5 text-[13px] leading-relaxed text-ink-2">
            {Object.entries(FACTOR_ACTIONS).map(([k, v]) => (
              <li key={k}><b className="text-ink">{factorNames[k] ?? k}:</b> {v}</li>
            ))}
          </ul>
        </div>
      </div>
      <p className="mt-3 text-[13px] text-ink-2">
        Emergency numbers in Thailand: police 191, ambulance 1669, fire 199, tourist police 1155, DDPM disaster hotline 1784, TMD weather hotline 1182.
        The full checklist is on the <Link className="link" to="/prep">Preparedness</Link> page.
      </p>
    </Section>
  )
}

// --------------------------------------------------------------------------- 5. Glossary

function Glossary({ q, setQ, open, setOpen, goTopic }: {
  q: string; setQ: (s: string) => void
  open: Set<string>; setOpen: (f: (s: Set<string>) => Set<string>) => void
  goTopic: (id: string) => void
}) {
  const list = useMemo(() => (q.trim() ? searchTopics(q) : allTopics()), [q])
  const letters = useMemo(() => {
    const m = new Map<string, Topic[]>()
    for (const t of list) {
      const L = /[a-z]/i.test(t.title[0]) ? t.title[0].toUpperCase() : '#'
      if (!m.has(L)) m.set(L, [])
      m.get(L)!.push(t)
    }
    return [...m.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [list])
  const searching = q.trim().length > 0
  const toggle = (id: string, isOpen: boolean) =>
    setOpen((s) => {
      const n = new Set(s)
      if (isOpen) n.add(id)
      else n.delete(id)
      return n
    })

  return (
    <Section id="glossary" title="Glossary"
      intro={<>Every term used in the dashboard, A to Z. Each entry has its own link: <code>/learn#oni</code>, <code>/learn#factor_water</code>...</>}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label htmlFor="glossary-q" className="sr-only">Search the glossary</label>
        <input id="glossary-q" type="search" className="input w-full max-w-[360px]" placeholder="Search: ONI, haze, ferry, DJF..."
          value={q} onChange={(e) => setQ(e.target.value)} />
        <span className="text-[12px] text-ink-3" aria-live="polite">{list.length} term{list.length === 1 ? '' : 's'}</span>
      </div>
      {!searching && (
        <nav aria-label="Glossary letters" className="mb-3 flex flex-wrap gap-1 text-[12px]">
          {letters.map(([L]) => (
            <a key={L} href={`#glossary-${L}`} className="chip hover:bg-surface-2"
              onClick={(e) => { e.preventDefault(); scrollToId(`glossary-${L}`) }}>{L}</a>
          ))}
        </nav>
      )}
      {list.length === 0 && <p className="text-[13px] text-ink-2">No term matches "{q}".</p>}
      <div className="space-y-5">
        {letters.map(([L, ts]) => (
          <div key={L}>
            {!searching && <h3 id={`glossary-${L}`} className="mb-1.5 scroll-mt-4 text-[13px] font-semibold text-ink-3">{L}</h3>}
            <div className="space-y-1.5">
              {ts.map((t) => (
                <details key={t.id} id={t.id} className="card scroll-mt-4" open={open.has(t.id)}
                  onToggle={(e) => toggle(t.id, (e.currentTarget as HTMLDetailsElement).open)}>
                  <summary className="cursor-pointer list-none px-4 py-2.5">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <span className="text-[14px] font-semibold text-ink">{t.title}</span>
                      <span className="text-[11px] text-ink-3">{CATEGORY_LABELS[t.category]}</span>
                    </div>
                    <p className="mt-0.5 text-[13px] text-ink-2">{t.short}</p>
                  </summary>
                  {open.has(t.id) && (
                    <div className="border-t border-line px-4 py-3">
                      <TopicView topic={t} onTopic={goTopic} headingLevel={4} />
                    </div>
                  )}
                </details>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Section>
  )
}

// --------------------------------------------------------------------------- 6. FAQ

function Faq({ goTopic }: { goTopic: (id: string) => void }) {
  return (
    <Section id="faq" title="Frequently asked questions">
      <div className="space-y-1.5">
        {FAQ.map((f) => (
          <details key={f.id} id={`faq-${f.id}`} className="card group scroll-mt-4">
            <summary className="flex cursor-pointer list-none items-start gap-2 px-4 py-2.5 text-[14px] font-medium text-ink">
              <span aria-hidden className="mt-0.5 text-ink-3 transition-transform group-open:rotate-90">›</span>
              {f.q}
            </summary>
            <div className="border-t border-line px-4 py-3 text-[13.5px] leading-relaxed text-ink-2">
              <Markdown text={f.a} onTopic={goTopic} />
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {f.topics.map((id) => <TopicChip key={id} id={id} goTopic={goTopic} />)}
              </div>
            </div>
          </details>
        ))}
      </div>
    </Section>
  )
}

// --------------------------------------------------------------------------- 7. Myths

function Myths({ goTopic }: { goTopic: (id: string) => void }) {
  return (
    <Section id="myths" title="Myths vs facts">
      <div className="grid gap-3 md:grid-cols-2">
        {MYTHS.map((m) => (
          <div key={m.myth} className="card p-4 text-[13.5px] leading-relaxed">
            <p className="text-ink-2"><span className="mr-1 font-semibold" style={{ color: 'var(--critical)' }}>Myth:</span>{m.myth}</p>
            <p className="mt-1.5 text-ink-2"><span className="mr-1 font-semibold" style={{ color: 'var(--good-ink)' }}>Fact:</span>{m.fact}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {m.topics.map((id) => <TopicChip key={id} id={id} goTopic={goTopic} />)}
            </div>
          </div>
        ))}
      </div>
    </Section>
  )
}

// --------------------------------------------------------------------------- 8. Limitations

function Limitations({ goTopic }: { goTopic: (id: string) => void }) {
  const t = getTopic('limitations')
  return (
    <Section id="limitations" title="Limitations and disclaimer">
      <div className="card p-4 text-[13.5px] leading-relaxed text-ink-2" style={{ borderLeft: '4px solid var(--warning)' }}>
        {t && <Markdown text={t.body} onTopic={goTopic} />}
        <p className="mt-3">
          Official sources: <a className="link" href="https://www.tmd.go.th/en/" target="_blank" rel="noreferrer">Thai Meteorological Department ↗</a>{' · '}
          <a className="link" href="https://www.disaster.go.th/" target="_blank" rel="noreferrer">DDPM ↗</a>
        </p>
      </div>
    </Section>
  )
}

// --------------------------------------------------------------------------- 9. Sources

function Sources() {
  const groups = useMemo(() => {
    const seen = new Map<string, { title: string; url: string; topics: number }>()
    for (const t of allTopics()) {
      for (const s of t.sources) {
        const cur = seen.get(s.url)
        if (cur) cur.topics++
        else seen.set(s.url, { ...s, topics: 1 })
      }
    }
    const byHost = new Map<string, { title: string; url: string; topics: number }[]>()
    for (const s of seen.values()) {
      let host = s.url
      try {
        host = new URL(s.url).hostname.replace(/^www\d?\./, '')
      } catch {
        /* keep the raw url */
      }
      if (!byHost.has(host)) byHost.set(host, [])
      byHost.get(host)!.push(s)
    }
    return [...byHost.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [])
  return (
    <Section id="sources" title="Sources"
      intro="Every explanation on this page cites where it comes from. These are all the references used, grouped by website (links checked on 2026-09-24). The data sources of the dashboard itself are listed on the Sources page.">
      <div className="grid gap-3 md:grid-cols-2">
        {groups.map(([host, list]) => (
          <div key={host} className="card p-3">
            <h3 className="text-[12px] font-semibold tracking-wide text-ink-3">{host}</h3>
            <ul className="mt-1.5 space-y-1 text-[12.5px]">
              {list.map((s) => (
                <li key={s.url}>
                  <a className="link break-words" href={s.url} target="_blank" rel="noreferrer">{s.title} <span aria-hidden>↗</span></a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Section>
  )
}
