import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type maplibregl from 'maplibre-gl'
import { facet, useEventFacets, useEventsQ, useFeed, useLayers, useStatus, useWebcams } from '../api/client'
import type { MapLayer } from '../api/types'
import WorldMap, { CAM_COLOR, type LayerKey, type Overlay } from '../components/WorldMap'
import { ChipSelect, FilteredEmpty, FilterGroup, PresetSelect, DEFAULT_PRESETS } from '../components/filters'
import { KindBadge } from '../components/ui'
import { fmtDate, fmtDateTz, HOME, isoDaysAgo, relTime } from '../lib/format'
import {
  CATEGORY_LABEL, LAYER_KIND, SEVERITY_COLOR, SEVERITY_LABEL, SEVERITY_TEXT, circleRing, layerSourceUrl, safeUrl,
} from '../lib/geo'
import { buoysFrom } from '../lib/normalize'
import { sinceFromPreset, useDebounced, useUrlFilters } from '../lib/urlFilters'
import { EVENT_CATEGORY_TOPIC, HelpFor, HelpTip, LAYER_TOPIC, PageGuide, sourceTopic, useHelp } from '../help'

/** /api/layers rows carry a few more fields than the shared MapLayer type. */
type LayerRow = MapLayer & {
  time_mode?: string | null
  time?: string | null
  source?: string | null
  gibs_layer?: string | null
  frames?: number | null
}

function useThemeBase(): 'dark' | 'osm' {
  const get = () => (document.documentElement.dataset.theme === 'light' ? 'osm' : 'dark')
  const [b, setB] = useState<'dark' | 'osm'>(get)
  useEffect(() => {
    const h = () => setB(get())
    window.addEventListener('themechange', h)
    return () => window.removeEventListener('themechange', h)
  }, [])
  return b
}

function tilesFor(l: MapLayer, date: string): string {
  return l.url_template.replace(/\{time\}/g, date).replace(/\{date\}/g, date)
}

const dayShift = (iso: string, days: number) => new Date(Date.parse(`${iso}T00:00:00Z`) + days * 86400000).toISOString().slice(0, 10)
const RADII = ['300', '500', '800', '1500']
const SOURCE_LABEL: Record<string, string> = {
  firms_fires: 'NASA FIRMS fires', eonet: 'NASA EONET', gdacs: 'GDACS', usgs_quakes_region: 'USGS earthquakes',
  crw_vs: 'NOAA Coral Reef Watch', jtwc_warnings: 'JTWC warnings', jma_typhoons: 'JMA typhoons',
}
const fmtLon = (x: number) => `${Math.abs(x).toFixed(0)}°${x < 0 ? 'W' : 'E'}`
const fmtLat = (x: number) => `${Math.abs(x).toFixed(0)}°${x < 0 ? 'S' : 'N'}`
const srcLabel = (s: string) => SOURCE_LABEL[s] ?? s.replace(/_/g, ' ')

/** Collapsible panel section (forced open while the map tour runs). */
function Section({ title, help, tour, open, onToggle, children, right, bodyClass = '' }: {
  title: string; help?: ReactNode; tour?: string; open: boolean; onToggle: () => void; children: ReactNode; right?: ReactNode
  /** e.g. a reserved min-height so an async list does not shift the panel (CLS) */
  bodyClass?: string
}) {
  return (
    <section data-tour={tour} className="border-t border-line first:border-t-0">
      <div className="flex items-center gap-1.5 py-1.5">
        <button type="button" onClick={onToggle} aria-expanded={open}
          className="flex min-h-10 flex-1 items-center gap-1.5 text-left text-[11px] font-semibold tracking-wide text-ink-3 uppercase hover:text-ink md:min-h-8">
          <span aria-hidden className={`inline-block transition-transform ${open ? 'rotate-90' : ''}`}>▸</span>{title}
        </button>
        {help}
        {right}
      </div>
      {open && <div className={`pb-3 ${bodyClass}`}>{children}</div>}
    </section>
  )
}

export default function MapPage() {
  const themeBase = useThemeBase()
  const [baseChoice, setBaseChoice] = useState<'auto' | 'dark' | 'osm'>('auto')
  const base = baseChoice === 'auto' ? themeBase : baseChoice
  const [pacific, setPacific] = useState(true)
  const [visible, setVisible] = useState<Record<LayerKey, boolean>>({
    events: true, buoys: true, news: true, nino: true, home: true, impacts: false, cams: false,
  })
  const [panelOpen, setPanelOpen] = useState(() => window.innerWidth >= 1024)
  const help = useHelp()
  const touring = help.tour?.page === 'map'
  const panelShown = panelOpen || touring
  const [sec, setSec] = useState({ layer: true, filters: true, vector: true, base: false })
  const secOpen = (k: keyof typeof sec) => sec[k] || touring
  const flip = (k: keyof typeof sec) => setSec((s) => ({ ...s, [k]: !s[k] }))

  // ---- event filters (URL) ----
  const f = useUrlFilters({ category: 'list', severity: 'list', source: 'list', since: 'str', near: 'bool', radius: 'str', view: 'bool' })
  const lf = useUrlFilters({ layer: 'str', date: 'str' })
  const radius = RADII.includes(f.values.radius) ? f.values.radius : String(HOME.radiusKm)
  const [bounds, setBounds] = useState<[number, number, number, number] | null>(null)
  const dBounds = useDebounced(bounds, 450)
  const bbox = f.values.view && dBounds ? dBounds.join(',') : undefined
  const params = {
    category: f.api.category, severity: f.api.severity, source: f.api.source,
    since: sinceFromPreset(f.values.since),
    near: f.values.near ? `${HOME.lat},${HOME.lon}` : undefined,
    radius_km: f.values.near ? radius : undefined,
    bbox,
    limit: 5000, // explicit: /api/events without a limit returns every stored event
  }
  const ev = useEventsQ(params)
  const facets = useEventFacets(params)
  const allFacets = useEventFacets({})
  const total = allFacets.data?.total ?? null
  const shown = ev.data?.length ?? null

  const camsQ = useWebcams()
  const cams = useMemo(() => (camsQ.data?.webcams ?? []).filter((c) => c.kind !== 'satellite' && c.lat !== null && c.lon !== null), [camsQ.data])
  const tao = useStatus<unknown>('tao_buoys')
  const buoys = useMemo(() => buoysFrom(tao.data?.value), [tao.data])
  const feed = useFeed({ has_geo: 'true', limit: 500 })
  const geoNews = useMemo(() => (feed.data ?? []).filter((x) => x.lat !== null && x.lon !== null), [feed.data])
  const newestNews = useMemo(() => geoNews.reduce<string>((m, x) => { const t = x.published_at ?? x.fetched_at ?? ''; return t > m ? t : m }, ''), [geoNews])
  const layers = useLayers()

  // ---- raster layer (URL: layer + date) ----
  const layer = (layers.data?.find((l) => l.id === lf.values.layer) ?? null) as LayerRow | null
  const dated = !!layer && /\{(time|date)\}/.test(layer.url_template)
  const newest = layer?.default_date ?? isoDaysAgo(layer?.default_date_offset_days ?? 1)
  const date = dated ? (/^\d{4}-\d{2}-\d{2}$/.test(lf.values.date) ? lf.values.date : newest) : ''
  const back = dated ? Math.max(0, Math.round((Date.parse(`${newest}T00:00:00Z`) - Date.parse(`${date}T00:00:00Z`)) / 86400000)) : 0
  const setDate = (d: string) => lf.set('date', d === newest ? '' : d)
  const [opacity, setOpacity] = useState(0.75)
  const overlay: Overlay | null = layer
    ? { id: layer.id, tiles: dated ? tilesFor(layer, date) : (layer.url_template), maxzoom: layer.max_zoom ?? 7, attribution: layer.attribution, opacity }
    : null
  const lk = layer ? LAYER_KIND[layer.id] : undefined
  const lsrc = layer ? layerSourceUrl(layer, dated ? date : null) : null

  // ---- map instance, bounds ----
  const mapRef = useRef<maplibregl.Map | null>(null)
  const [mapReady, setMapReady] = useState(false)
  const onMap = useCallback((m: maplibregl.Map) => { mapRef.current = m; setMapReady(true) }, [])
  const onBounds = useCallback((b: [number, number, number, number] | null) => setBounds(b), [])
  const zoomHome = () => {
    const ring = circleRing(HOME.lat, HOME.lon, Number(radius))
    const lons = ring.map((p) => p[0]), lats = ring.map((p) => p[1])
    mapRef.current?.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], {
      // the map's own padding (side panel / bottom sheet) is added by MapLibre
      padding: 30, duration: 700,
    })
  }
  // turning on "only inside the circle" (or opening a link with it) zooms to the circle
  useEffect(() => {
    if (!mapReady || !f.values.near) return
    const t = setTimeout(zoomHome, 400)
    return () => clearTimeout(t)
  }, [mapReady, f.values.near, radius]) // eslint-disable-line react-hooks/exhaustive-deps

  // keep the map's visual centre out from under the side panel / bottom sheet
  const [vw, setVw] = useState(() => window.innerWidth)
  const [vh, setVh] = useState(() => window.innerHeight)
  useEffect(() => {
    const h = () => { setVw(window.innerWidth); setVh(window.innerHeight) }
    window.addEventListener('resize', h)
    return () => window.removeEventListener('resize', h)
  }, [])
  const pad = !panelShown ? undefined : vw >= 1280 ? { left: 412 } : vw >= 1024 ? { left: 382 } : { bottom: Math.round(vh * (vw >= 768 ? 0.5 : 0.58)) }

  const newestEv = useMemo(() => (ev.data ?? []).reduce<string>((m, e) => { const t = e.updated_at ?? e.started_at ?? ''; return t > m ? t : m }, ''), [ev.data])
  const bySource = useMemo(() => {
    const m = new Map<string, number>()
    for (const e of ev.data ?? []) m.set(e.source, (m.get(e.source) ?? 0) + 1)
    return [...m.entries()].sort((a, b) => b[1] - a[1])
  }, [ev.data])

  const toggle = (k: LayerKey) => setVisible((v) => ({ ...v, [k]: !v[k] }))
  const Row = ({ k, label, swatch, count, help: h, children }: { k: LayerKey; label: string; swatch: ReactNode; count?: number | string; help?: ReactNode; children?: ReactNode }) => (
    <div className="py-1">
      <div className="flex items-center gap-2 text-[13px]">
        <label className="flex min-h-10 flex-1 cursor-pointer items-center gap-2 md:min-h-7">
          <input type="checkbox" checked={visible[k]} onChange={() => toggle(k)} className="h-4 w-4 accent-[var(--accent)]" />
          <span className="flex w-5 justify-center">{swatch}</span>
          <span className="flex-1">{label}</span>
        </label>
        {count !== undefined && <span className="text-[11px] text-ink-3 tnum">{count}</span>}
        {h}
      </div>
      {children && <div className="ml-7 text-[11px] text-ink-3">{children}</div>}
    </div>
  )

  // human descriptions of the active filters (for the empty state)
  const activeDesc = [
    ...f.values.category.map((c) => `category: ${CATEGORY_LABEL[c] ?? c}`),
    ...f.values.severity.map((s) => `severity: ${SEVERITY_LABEL[s] ?? s}`),
    ...f.values.source.map((s) => `source: ${srcLabel(s)}`),
    ...(f.values.since ? [`updated in the last ${DEFAULT_PRESETS.find((p) => p.v === f.values.since)?.l ?? f.values.since}`] : []),
    ...(f.values.near ? [`within ${radius} km of Koh Samui`] : []),
    ...(f.values.view ? ['inside the current map view'] : []),
  ]
  const summary = (
    <span className="tnum" aria-live="polite">
      {shown === null ? 'Loading events...' : <><b className="text-ink">{shown.toLocaleString('en-GB')}</b> of {total?.toLocaleString('en-GB') ?? '..'} events shown</>}
    </span>
  )

  const catOpts = facet(facets.data, 'category').map((c) => ({
    value: c.value, count: c.count, text: CATEGORY_LABEL[c.value] ?? c.value,
    help: <HelpFor id={EVENT_CATEGORY_TOPIC[c.value] ?? null} appId={c.value} kind="category" title={CATEGORY_LABEL[c.value] ?? c.value} />,
  }))
  for (const c of f.values.category) if (!catOpts.some((o) => o.value === c)) catOpts.push({ value: c, count: 0, text: CATEGORY_LABEL[c] ?? c, help: <></> })
  const sevFacet = facet(facets.data, 'severity')
  const sevOpts = ['red', 'orange', 'green', 'info'].map((s) => ({
    value: s, text: SEVERITY_LABEL[s], color: SEVERITY_COLOR[s], title: SEVERITY_TEXT[s],
    count: sevFacet.find((x) => x.value === s)?.count ?? (facets.data ? 0 : null),
  }))
  const srcOpts = facet(facets.data, 'source').map((s) => ({
    value: s.value, count: s.count, text: srcLabel(s.value),
    help: <HelpFor id={sourceTopic(s.value)} appId={s.value} kind="source" title={srcLabel(s.value)} />,
  }))
  for (const s of f.values.source) if (!srcOpts.some((o) => o.value === s)) srcOpts.push({ value: s, count: 0, text: srcLabel(s), help: <></> })

  const filtersEmpty = f.active > 0 && shown === 0 && !ev.isLoading

  return (
    <div className="absolute inset-0">
      <div data-tour="map-canvas" className="absolute inset-0">
        <WorldMap events={ev.data} buoys={buoys} news={geoNews} cams={cams} visible={visible} base={base} pacific={pacific} overlay={overlay}
          homeRadiusKm={Number(radius)} onBounds={onBounds} onMap={onMap} padding={pad} />
      </div>
      {(ev.isLoading || ev.isError || (!panelShown && shown !== null) || filtersEmpty) && (
        <div role="status" className="card absolute top-[60px] left-3 z-10 flex max-w-[calc(100%-70px)] flex-wrap items-center gap-x-2 gap-y-1 px-3 py-1.5 text-[12px] shadow-lg lg:top-3 lg:left-[calc(50%+190px)] lg:max-w-[min(560px,calc(100%-520px))] lg:-translate-x-1/2 lg:justify-center lg:text-center"
          style={ev.isError ? { color: 'var(--critical)', borderColor: 'var(--critical)' } : undefined}>
          {ev.isError ? `Events failed to load: ${ev.error instanceof Error ? ev.error.message : 'error'}`
            : ev.isLoading ? <span className="flex items-center gap-2"><span className="spin" />Loading events...</span>
              : <>
                {summary}
                {filtersEmpty && <span className="text-ink-2">No event matches the filters.</span>}
                {f.active > 0 && <button type="button" className="link text-[12px]" onClick={f.reset}>Reset filters</button>}
              </>}
        </div>
      )}

      {!panelShown && (
        <button type="button" className="btn absolute top-3 left-3 z-10 shadow-lg" onClick={() => setPanelOpen(true)} aria-expanded={false} aria-controls="map-panel">
          Layers, filters and legend{f.active > 0 && <span className="chip !py-0 tnum">{f.active}</span>}
        </button>
      )}

      {panelShown && (
        <aside id="map-panel" aria-label="Map layers, filters and legend"
          className="card absolute inset-x-0 bottom-0 z-10 flex max-h-[58%] flex-col rounded-b-none shadow-2xl md:inset-x-3 md:max-h-[50%] lg:inset-x-auto lg:top-3 lg:bottom-3 lg:left-3 lg:max-h-none lg:w-[370px] lg:rounded-b-[inherit] xl:w-[400px]">
          <header className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-line px-3 py-2">
            <h1 className="flex items-center gap-1.5 text-[14px] font-semibold">Live map <HelpTip id="map_overlays" /></h1>
            <span className="text-[12px] text-ink-3">{summary}</span>
            <span className="ml-auto flex items-center gap-1.5">
              <button type="button" className="btn !min-h-8 !px-2 !py-0.5 !text-[12px]" disabled={!f.active} onClick={f.reset}>Reset filters</button>
              <button type="button" className="btn !min-h-8 !px-2 !py-0.5 !text-[12px]" onClick={() => setPanelOpen(false)} aria-expanded aria-controls="map-panel"
                aria-label="Hide the panel">Hide</button>
            </span>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 pt-2">
            <PageGuide page="map" defaultOpen={false} className="mb-2" />

            {/* ---------------- raster layer ---------------- */}
            <Section title="Satellite layer" tour="map-layer-picker" open={secOpen('layer')} onToggle={() => flip('layer')}
              bodyClass="lg:min-h-[758px]" help={<HelpTip id="map_overlays" label="How do map layers work?" />}>
              {layers.isLoading ? <p className="text-[12px] text-ink-3">Loading...</p> : layers.isError || !layers.data?.length ? (
                <p className="text-[12px] text-ink-3">No raster layer published by the API (<code>/api/layers</code>). <Link className="link" to="/sources">Sources</Link></p>
              ) : (
                <div role="radiogroup" aria-label="Raster layer" className="grid gap-0.5">
                  {[{ id: '', title: 'None (basemap only)' } as Pick<MapLayer, 'id' | 'title' | 'description'>, ...layers.data].map((l) => (
                    <div key={l.id || 'none'} className={`flex items-center gap-1.5 rounded px-1.5 text-[13px] ${lf.values.layer === l.id ? 'bg-surface-2' : 'hover:bg-surface-2'}`}>
                      <label className="flex min-h-10 flex-1 cursor-pointer items-center gap-2 md:min-h-8">
                        <input type="radio" name="raster" className="h-4 w-4 accent-[var(--accent)]" checked={lf.values.layer === l.id}
                          onChange={() => lf.setMany({ layer: l.id, date: '' })} />
                        <span className="flex-1">{l.title}</span>
                      </label>
                      {l.id && <HelpFor id={LAYER_TOPIC[l.id] ?? null} appId={l.id} kind="layer" title={l.title} text={l.description} />}
                    </div>
                  ))}
                </div>
              )}
              {layer && (
                <div className="mt-2 space-y-2 rounded-lg border border-line p-2.5">
                  <div className="flex flex-wrap items-center gap-1.5 text-[12px]">
                    <KindBadge kind={lk?.kind ?? 'observed'} tz="UTC" />
                    <span className="text-ink-3">{dated ? `image of ${fmtDateTz(date, 'UTC')}` : layer.time ? `frame of ${fmtDateTz(layer.time, 'UTC')} (${relTime(layer.time)})` : 'latest image (live)'}</span>
                  </div>
                  {lk && <p className="text-[11px] text-ink-2">{lk.note}</p>}
                  {dated && (
                    <div data-tour="map-date" className="space-y-1.5">
                      <div className="flex flex-wrap items-center gap-1.5 text-[12px]">
                        <button type="button" className="btn !min-h-9 !px-2 !py-0.5" onClick={() => setDate(dayShift(date, -1))} aria-label="Previous day">‹</button>
                        <input type="date" className="input !py-1" value={date} max={newest} aria-label="Layer date"
                          onChange={(e) => { if (/^\d{4}-\d{2}-\d{2}$/.test(e.target.value)) setDate(e.target.value > newest ? newest : e.target.value) }} />
                        <button type="button" className="btn !min-h-9 !px-2 !py-0.5" disabled={back === 0} onClick={() => setDate(dayShift(date, 1))} aria-label="Next day">›</button>
                        {back > 0 && <button type="button" className="link text-[12px]" onClick={() => setDate(newest)}>Newest</button>}
                      </div>
                      <input type="range" min={0} max={60} value={60 - Math.min(60, back)} className="w-full accent-[var(--accent)]"
                        onChange={(e) => setDate(dayShift(newest, -(60 - Number(e.target.value))))} aria-label="Date slider (60 days before the newest image)" />
                      <p className="flex justify-between text-[10px] text-ink-3"><span>{fmtDate(dayShift(newest, -60))}</span><span>newest {fmtDate(newest)} ({relTime(newest)})</span></p>
                    </div>
                  )}
                  <label className="flex items-center gap-2 text-[12px] text-ink-2">
                    Opacity
                    <input type="range" min={0.1} max={1} step={0.05} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} className="flex-1 accent-[var(--accent)]" aria-label="Layer opacity" />
                  </label>
                  <div data-tour="map-legend" className="space-y-1">
                    <p className="flex items-center gap-1 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">
                      Legend <HelpFor id={LAYER_TOPIC[layer.id] ?? null} appId={layer.id} kind="layer" title={layer.title} text={layer.description} />
                    </p>
                    {safeUrl(layer.legend_url) ? <img src={layer.legend_url!} alt={`${layer.title} colour scale`} className="max-w-full rounded bg-white p-1" />
                      : <p className="text-[11px] text-ink-3">The provider publishes no colour scale for this layer: {layer.id === 'radar_rainviewer' ? 'light blue = light rain, yellow/red = heavy rain, purple = very heavy.' : 'see the "?" guide.'}</p>}
                    {layer.description && <p className="text-[11px] text-ink-2">{layer.description}</p>}
                    <p className="flex flex-wrap items-center gap-x-1.5 text-[11px] text-ink-3">
                      {layer.attribution && <span>{layer.attribution}</span>}
                      {lsrc && <><span aria-hidden>·</span><a className="link" href={lsrc.href} target="_blank" rel="noreferrer">{lsrc.title} ↗</a></>}
                      {layer.source && <HelpFor appId={layer.source} kind="source" title={layer.source === 'nasa_gibs' ? 'NASA GIBS' : layer.source === 'rainviewer' ? 'RainViewer' : layer.source}
                        text={layer.source === 'nasa_gibs' ? 'NASA Global Imagery Browse Services: free map tiles made from NASA and partner satellite products, one image per day (or per 10 min for geostationary layers). Dates are UTC days.' : layer.source === 'rainviewer' ? 'RainViewer collects the rain radar images that national weather services share and serves the latest frames as map tiles. Areas without a shared radar stay empty.' : null} />}
                    </p>
                    {dated && <p className="text-[10px] text-ink-3">No image? That date may not be published yet or the pass missed this area: step back one day.</p>}
                  </div>
                </div>
              )}
            </Section>

            {/* ---------------- event filters ---------------- */}
            <Section title="Event filters" open={secOpen('filters')} onToggle={() => flip('filters')}
              help={<HelpTip id="filters_events" label="How do the event filters work?" />}
              right={f.active > 0 ? <span className="chip !py-0 text-[11px] tnum">{f.active} active</span> : undefined}>
              <div className="space-y-3">
                <FilterGroup label="Category" help={<HelpTip id="filters_events" />}>
                  <ChipSelect options={catOpts} selected={f.values.category} onToggle={(v) => f.toggle('category', v)} limit={8} />
                  {!catOpts.length && facets.data && <span className="text-[12px] text-ink-3">No category has events with the other filters.</span>}
                </FilterGroup>
                <FilterGroup label="Severity" help={<HelpTip id="gdacs" label="What do the severity colours mean?" />}>
                  <ChipSelect options={sevOpts} selected={f.values.severity} onToggle={(v) => f.toggle('severity', v)} />
                </FilterGroup>
                <FilterGroup label="Source" help={<HelpTip id="sources_page" label="About the event sources" />}>
                  <ChipSelect options={srcOpts} selected={f.values.source} onToggle={(v) => f.toggle('source', v)} limit={8} />
                  {!srcOpts.length && facets.data && <span className="text-[12px] text-ink-3">No source has events with the other filters.</span>}
                </FilterGroup>
                <FilterGroup label="Updated since" help={<HelpTip id="freshness" label="Which date is used?" />}>
                  <PresetSelect label="Updated since" value={f.values.since} options={DEFAULT_PRESETS} onChange={(v) => f.set('since', v)} />
                </FilterGroup>
                <FilterGroup label="Near Koh Samui" help={<HelpTip id="map_overlays" label="What is the circle around Koh Samui?" />}>
                  <button type="button" className="fchip" aria-pressed={f.values.near} onClick={() => f.set('near', !f.values.near)}>
                    Only inside the circle
                  </button>
                  <PresetSelect label="Radius" value={radius} options={RADII.map((r) => ({ v: r, l: `${r} km` }))} onChange={(v) => f.set('radius', v === String(HOME.radiusKm) ? '' : v)} />
                  <button type="button" className="link min-h-8 text-[12px]" onClick={zoomHome}>Zoom to circle</button>
                </FilterGroup>
                <FilterGroup label="Map view" help={<HelpTip id="filters_events" label="How does 'current view' work?" />}>
                  <button type="button" className="fchip" aria-pressed={f.values.view} onClick={() => f.set('view', !f.values.view)}>
                    Limit to current view
                  </button>
                  {f.values.view && <span className="text-[11px] text-ink-3">{dBounds ? `Longitude ${fmtLon(dBounds[0])} to ${fmtLon(dBounds[2])}${dBounds[0] > dBounds[2] ? ' (across 180)' : ''}, latitude ${fmtLat(dBounds[1])} to ${fmtLat(dBounds[3])}. Updates when you pan or zoom.` : 'The whole world width is visible: zoom in to narrow.'}</span>}
                </FilterGroup>
                {filtersEmpty && (
                  <FilteredEmpty what="events" filters={activeDesc} onReset={f.reset} total={total}>
                    {f.values.view && <p className="mt-1">"Limit to current view" only keeps events inside the visible map area: zoom out or pan.</p>}
                  </FilteredEmpty>
                )}
              </div>
            </Section>

            {/* ---------------- vector data ---------------- */}
            <Section title="Vector data" tour="map-vector" open={secOpen('vector')} onToggle={() => flip('vector')}
              help={<HelpTip id="map_overlays" />}>
              <Row k="events" label="Events (hazards)" count={shown ?? '..'} help={<HelpTip id="gdacs" label="How are events rated?" />}
                swatch={<span className="h-3 w-3 rounded-full" style={{ background: SEVERITY_COLOR.red }} />}>
                <div className="flex flex-wrap gap-x-2 gap-y-0.5">
                  {Object.entries(SEVERITY_COLOR).map(([k, c]) => (
                    <span key={k} className="flex items-center gap-1" title={SEVERITY_TEXT[k]}><span className="h-2 w-2 rounded-full" style={{ background: c }} />{SEVERITY_LABEL[k]}</span>
                  ))}
                </div>
                <div className="mt-0.5">Icon = category, colour = severity. Plain circles = clusters (size = count, colour = worst severity): click to zoom.</div>
                {bySource.length > 0 && (
                  <ul className="mt-1 space-y-0.5">
                    {bySource.map(([s, n]) => (
                      <li key={s} className="flex items-center gap-1.5">
                        <span className="flex-1">{srcLabel(s)}</span><span className="tnum">{n}</span>
                        <HelpFor id={sourceTopic(s)} appId={s} kind="source" title={srcLabel(s)} />
                      </li>
                    ))}
                  </ul>
                )}
                {newestEv && <div className="mt-0.5">Newest update {fmtDateTz(newestEv, 'UTC')} ({relTime(newestEv)})</div>}
                {ev.data && ev.data.length === 0 && !f.active && <div>No events collected. <Link className="link" to="/sources">Sources</Link></div>}
              </Row>
              <Row k="buoys" label="TAO/TRITON buoys" count={buoys.length} help={<HelpTip id="tao_buoys" />}
                swatch={<span className="h-3 w-3 rounded-full border-2 border-white" style={{ background: '#199e70' }} />}>
                {buoys.length === 0 && <>Status <code>tao_buoys</code> missing. <Link className="link" to="/sources">Sources</Link></>}
                {tao.data?.updated_at && <>Sea surface temperature per buoy, updated {fmtDateTz(tao.data.updated_at, 'UTC')} ({relTime(tao.data.updated_at)}) · <a className="link" href="https://www.pmel.noaa.gov/tao/drupal/disdel/" target="_blank" rel="noreferrer">NOAA PMEL ↗</a></>}
              </Row>
              <Row k="news" label="Geolocated news" count={geoNews.length} help={<HelpTip id="news_signals" />}
                swatch={<span className="h-3 w-3 rounded-full" style={{ background: '#9085e9' }} />}>
                News and posts placed where they talk about (newest 500).{newestNews && <> Newest {fmtDateTz(newestNews, 'UTC')}.</>} <Link className="link" to="/news">All news</Link>
              </Row>
              <Row k="cams" label="Public webcams" count={cams.length} help={<HelpTip id="webcams" />}
                swatch={<span className="h-3 w-3 rounded-full border-2" style={{ background: CAM_COLOR.live, borderColor: '#0b1626' }} />}>
                Beach, pier, street and buoy cameras published by their owners. Colour = status:{' '}
                <span style={{ color: CAM_COLOR.live }}>● live/online</span>, <span style={{ color: CAM_COLOR.reachable }}>● reachable</span>, <span style={{ color: CAM_COLOR.stale }}>● stale</span>, <span style={{ color: CAM_COLOR.offline }}>● offline</span>.
                {camsQ.data?.updated_at && <> Checked {fmtDateTz(camsQ.data.updated_at, 'UTC')} ({relTime(camsQ.data.updated_at)}).</>} <Link className="link" to="/cams">All cams</Link>
              </Row>
              <Row k="nino" label="Nino regions" help={<HelpTip id="nino_regions" />}
                swatch={<span className="h-3 w-4 border-2" style={{ borderColor: '#f0a0a0', background: 'rgba(230,103,103,.2)' }} />}>
                1+2: 0-10S 90W-80W · 3: 5N-5S 150W-90W · 3.4: 5N-5S 170W-120W · 4: 5N-5S 160E-150W
              </Row>
              <Row k="home" label={`Home, Maenam (${radius} km radius)`} help={<HelpTip id="map_overlays" />}
                swatch={<span className="h-3 w-3 rounded-full border-2 border-white" style={{ background: '#4ea1ff' }} />} />
              <Row k="impacts" label="Regions typically affected by El Nino" help={<HelpTip id="teleconnections" />}
                swatch={<span className="h-3 w-4" style={{ background: 'linear-gradient(90deg,#c98500 50%,#3987e5 50%)' }} />}>
                <span className="flex gap-3"><span><b style={{ color: '#e0a030' }}>☀</b> drier</span><span><b style={{ color: '#6da7ec' }}>☂</b> wetter</span></span>
                Indicative schematic (NOAA Climate.gov / WMO). Approximate outlines.
              </Row>
            </Section>

            {/* ---------------- basemap ---------------- */}
            <Section title="Basemap and centring" open={secOpen('base')} onToggle={() => flip('base')}>
              <div className="flex flex-wrap items-center gap-2">
                <div className="seg" role="group" aria-label="Centring">
                  <button type="button" aria-pressed={pacific} onClick={() => setPacific(true)}>Pacific</button>
                  <button type="button" aria-pressed={!pacific} onClick={() => setPacific(false)}>World</button>
                </div>
                <div className="seg" role="group" aria-label="Basemap">
                  {(['auto', 'dark', 'osm'] as const).map((b) => (
                    <button key={b} type="button" aria-pressed={baseChoice === b} onClick={() => setBaseChoice(b)}>
                      {b === 'auto' ? 'Auto' : b === 'dark' ? 'Dark' : 'OSM'}
                    </button>
                  ))}
                </div>
              </div>
            </Section>
            <p className="border-t border-line py-2 text-[10px] text-ink-3">Click a feature for its source and timestamp. Times in UTC. Basemaps: © OpenStreetMap, © Esri.</p>
          </div>
        </aside>
      )}
    </div>
  )
}
