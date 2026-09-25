import { useEffect, useState, useSyncExternalStore } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useHealth, useSources } from '../api/client'
import { isStale } from '../lib/series'
import { LOCALE, fmtDate, relTime } from '../lib/format'
import { HelpDrawer, HelpTip, Tour, pageFromPath, startTour } from '../help'
import { useSeo } from '../seo'

const NAV: { to: string; label: string; icon: string; tour?: string }[] = [
  { to: '/', label: 'Overview', icon: 'M3 12l9-8 9 8v8a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z' },
  { to: '/map', label: 'Live map', icon: 'M9 4l-6 2v14l6-2 6 2 6-2V4l-6 2-6-2zm0 0v14m6-12v14' },
  { to: '/indices', label: 'Indices', icon: 'M4 19h16M6 16l4-6 4 3 5-8' },
  { to: '/news', label: 'News & social', icon: 'M5 5h11v14H5zM16 9h3v8a2 2 0 0 1-2 2M8 9h5M8 12h5M8 15h3' },
  { to: '/samui', label: 'Koh Samui', icon: 'M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11zm0-8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z' },
  { to: '/history', label: 'Past El Ninos', icon: 'M12 8v4l3 2M3.05 11a9 9 0 1 1 .5 4M3 4v4h4' },
  { to: '/cams', label: 'Cams', icon: 'M3 7h11v10H3zM14 10l7-3v10l-7-3' },
  { to: '/places', label: 'Places', icon: 'M3 21h18M5 21V10l7-5 7 5v11M9 21v-6h6v6' },
  { to: '/prep', label: 'Preparedness', icon: 'M9 11l2 2 4-4M5 4h14v16H5z' },
  { to: '/learn', label: 'Learn', icon: 'M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zm0 0v16M8 7h7M8 11h5', tour: 'help-learn' },
  { to: '/sources', label: 'Sources', icon: 'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zm0 0v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3' },
]

// Page titles / meta come from useSeo() (route map rendered server-side by backend/app/seo.py).

/** Newest successful fetch across all collectors + how many are stale / failing. */
function useDataRefresh() {
  const q = useSources()
  const rows = q.data ?? []
  let last: string | null = null
  for (const r of rows) if (r.last_ok_at && (!last || r.last_ok_at > last)) last = r.last_ok_at
  return {
    last,
    // documented silent feeds (expected_stale) are not a problem to flag in the header
    stale: rows.filter((r) => (r.state === 'stale' || (r.state === 'ok' && isStale(r))) && !r.expected_stale).length,
    failing: rows.filter((r) => r.state === 'error').length,
    hasFreshness: rows.some((r) => r.freshness !== undefined),
    loaded: !!q.data,
  }
}

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={d} />
    </svg>
  )
}

/** Most recent successful data fetch across all queries. */
function useLastUpdate(): number {
  const qc = useQueryClient()
  const cache = qc.getQueryCache()
  return useSyncExternalStore(
    (cb) => cache.subscribe(cb),
    () => cache.getAll().reduce((m, q) => (q.queryKey[0] === 'health' ? m : Math.max(m, q.state.dataUpdatedAt)), 0),
  )
}

function useNow(ms = 15000) {
  const [, set] = useState(0)
  useEffect(() => {
    const t = setInterval(() => set((x) => x + 1), ms)
    return () => clearInterval(t)
  }, [ms])
}

function ThemeToggle() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme ?? 'dark')
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('theme', theme)
    } catch {
      /* storage blocked */
    }
    window.dispatchEvent(new CustomEvent('themechange', { detail: theme }))
  }, [theme])
  return (
    <button type="button" className="btn !px-2 !py-1" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'} aria-label="Toggle theme">
      {theme === 'dark' ? (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
      ) : (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>
      )}
    </button>
  )
}

export default function Layout() {
  const health = useHealth()
  const last = useLastUpdate()
  const loc = useLocation()
  const qc = useQueryClient()
  const refresh = useDataRefresh()
  useSeo()
  useEffect(() => {
    document.getElementById('main')?.scrollTo(0, 0)
    document.querySelector('#mobile-nav a.active')?.scrollIntoView({ block: 'nearest', inline: 'center' })
  }, [loc.pathname])
  useNow()
  const fullBleed = loc.pathname.startsWith('/map')
  const page = pageFromPath(loc.pathname)
  const apiDown = health.isError

  return (
    <div className="flex h-full flex-col md:flex-row">
      <a href="#main" className="skip-link no-print">Skip to content</a>
      {/* Sidebar (desktop) */}
      <aside className="no-print hidden w-56 shrink-0 flex-col border-r border-line bg-surface md:flex">
        <div className="flex items-center gap-2 px-4 py-4">
          <img src="/favicon.svg" width={26} height={26} alt="" />
          <div>
            <div className="text-[15px] leading-tight font-bold">El Nino Watch</div>
            <div className="text-[11px] text-ink-3">ENSO 2026 · Koh Samui</div>
          </div>
        </div>
        <nav className="flex flex-col gap-0.5 px-2" aria-label="Main navigation">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'} data-tour={n.tour}
              className={({ isActive }) => `flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] font-medium ${isActive ? 'bg-surface-3 text-ink' : 'text-ink-2 hover:bg-surface-2 hover:text-ink'}`}>
              <Icon d={n.icon} />
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto px-4 py-3 text-[11px] leading-relaxed text-ink-3">
          Data: NOAA, BoM, IRI, GDACS, NASA and other public sources. See the Sources page.
          <div className="mt-1.5">Every <span className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full border border-line-strong text-[9px] font-bold text-ink-2" aria-hidden>?</span> explains the item next to it.</div>
        </div>
      </aside>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="no-print flex min-w-0 items-center gap-2 border-b sm:gap-3 border-line bg-surface px-3 py-2 md:px-5">
          <div className="flex shrink-0 items-center gap-2 md:hidden">
            <img src="/favicon.svg" width={22} height={22} alt="El Nino Watch" />
            <span className="hidden text-sm font-bold min-[26.25rem]:inline">El Nino Watch</span>
          </div>
          <div className="ml-auto flex min-w-0 items-center gap-2 text-[12px] text-ink-2 sm:gap-3">
            <span className="flex items-center gap-1.5 whitespace-nowrap"
              title={`Last successful source fetch: ${refresh.last ? fmtDate(refresh.last) : 'unknown'}. Page data reloaded ${last ? new Date(last).toLocaleString(LOCALE, { hourCycle: 'h23' }) : '--'} (every 60 s).`}>
              <span className="inline-block h-2 w-2 shrink-0 rounded-full" aria-hidden style={{ background: apiDown ? 'var(--critical)' : 'var(--good)' }} />
              <span className="hidden sm:inline">Last data refresh</span>
              <span className="sm:hidden">Data</span>
              <b className="font-semibold text-ink">{refresh.last ? relTime(refresh.last) : refresh.loaded ? 'never' : '...'}</b>
              <HelpTip id="freshness" label="What does data refresh mean?" />
            </span>
            {refresh.stale > 0 && (
              <Link to="/sources?state=stale" className="chip shrink-0 whitespace-nowrap hover:underline" style={{ color: 'var(--stale)', borderColor: 'var(--stale)' }}
                title="Sources whose newest data is older than their expected update interval">
                <span aria-hidden>▲ </span>{refresh.stale}<span className="hidden min-[26.25rem]:inline"> stale</span><span className="sr-only"> stale sources</span>
              </Link>
            )}
            {refresh.failing > 0 && (
              <Link to="/sources?state=error" title="Sources whose last run failed"
                className="chip shrink-0 whitespace-nowrap hover:underline" style={{ color: 'var(--critical)', borderColor: 'var(--critical)' }}>
                <span aria-hidden>■ </span>{refresh.failing}<span className="hidden min-[26.25rem]:inline"> failing</span><span className="sr-only"> failing sources</span>
              </Link>
            )}
            {page && (
              <button type="button" className="btn !px-2 !py-1 !text-[12px]" onClick={() => startTour(page)} title="Guided tour of this page">
                <span aria-hidden className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-current text-[10px] font-bold">?</span>
                <span className="hidden sm:inline">Tour</span>
              </button>
            )}
            <ThemeToggle />
          </div>
        </header>
        {/* Mobile nav */}
        <nav id="mobile-nav" className="no-print flex gap-1 overflow-x-auto border-b border-line bg-surface px-2 py-1.5 md:hidden" aria-label="Navigation">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'} data-tour={n.tour}
              className={({ isActive }) => `flex min-h-10 shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[12px] font-medium ${isActive ? 'bg-surface-3 text-ink' : 'text-ink-2'}`}>
              <Icon d={n.icon} />
              {n.label}
            </NavLink>
          ))}
        </nav>
        {apiDown && (
          <div role="alert" className="no-print flex flex-wrap items-center gap-2 px-4 py-2 text-[13px] font-medium"
            style={{ background: 'color-mix(in srgb, var(--critical) 18%, var(--surface))', color: 'var(--ink)' }}>
            <b style={{ color: 'var(--critical)' }}>■ API unreachable</b>
            <span className="text-ink-2">
              The server (127.0.0.1:8911) is not responding. Values shown are from the last successful load.
            </span>
            <button type="button" className="btn ml-auto !py-0.5" onClick={() => qc.invalidateQueries()}>Retry</button>
          </div>
        )}
        {/* `relative`: sr-only labels/captions are position:absolute; without a positioned scroll
            container their containing block is the body and they push the DOCUMENT height past the
            viewport (window scrolls into ~1-6k px of blank below the app; QA 24 Sep 2026). */}
        <main id="main" tabIndex={-1} className={`outline-none min-h-0 flex-1 ${fullBleed ? 'relative overflow-hidden' : 'relative overflow-y-auto px-3 pt-3 pb-6 md:px-5 md:pt-4 2xl:px-8'}`}>
          <Outlet />
        </main>
      </div>
      <HelpDrawer />
      <Tour />
    </div>
  )
}
