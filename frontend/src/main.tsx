import { Component, StrictMode, Suspense, lazy, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import Layout from './components/Layout'
import { Skeleton } from './components/ui'

const Overview = lazy(() => import('./pages/Overview'))
const MapPage = lazy(() => import('./pages/MapPage'))
const Indices = lazy(() => import('./pages/Indices'))
const News = lazy(() => import('./pages/News'))
const Samui = lazy(() => import('./pages/Samui'))
const Prep = lazy(() => import('./pages/Prep'))
const Sources = lazy(() => import('./pages/Sources'))
const Learn = lazy(() => import('./pages/Learn'))
const Places = lazy(() => import('./pages/Places'))
const Cams = lazy(() => import('./pages/Cams'))
const History = lazy(() => import('./pages/History'))

const qc = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 60_000,
      refetchOnWindowFocus: true,
      staleTime: 30_000,
      retry: 1,
      placeholderData: (prev: unknown) => prev,
    },
  },
})

function Fallback() {
  return (
    <div className="grid gap-3">
      <Skeleton h={120} />
      <Skeleton h={240} />
    </div>
  )
}

/** One broken page must not blank the whole dashboard. */
class PageBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) { return { error } }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <div role="alert" className="card mx-auto max-w-xl p-4 text-[13px]" style={{ borderColor: 'var(--critical)' }}>
        <p className="font-semibold" style={{ color: 'var(--critical)' }}>■ This page failed to render</p>
        <p className="mt-1 text-ink-2">{this.state.error.message}</p>
        <p className="mt-1 text-ink-2">The other pages still work. Reloading usually fixes a transient problem.</p>
        <button type="button" className="btn mt-3" onClick={() => window.location.reload()}>Reload</button>
      </div>
    )
  }
}

function NotFound() {
  return <p className="text-ink-2">Page not found.</p>
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            {([
              ['/', Overview], ['/map', MapPage], ['/indices', Indices], ['/news', News],
              ['/samui', Samui], ['/prep', Prep], ['/sources', Sources], ['/learn', Learn], ['/learn/:topic', Learn],
              ['/places', Places], ['/cams', Cams], ['/history', History],
            ] as const).map(([path, C]) => (
              <Route key={path} path={path} element={<PageBoundary key={path}><Suspense fallback={<Fallback />}><C /></Suspense></PageBoundary>} />
            ))}
            {/* Legacy French paths */}
            <Route path="/carte" element={<Navigate to="/map" replace />} />
            <Route path="/actualites" element={<Navigate to="/news" replace />} />
            <Route path="/preparation" element={<Navigate to="/prep" replace />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
