import { useEffect, useRef, useState } from 'react'
import maplibregl, { type GeoJSONSource, type LngLatLike } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { EventItem, FeedItem, TaoBuoy, Webcam } from '../api/types'
import { fmtDate, fmtNum, HOME, relTime, toneText } from '../lib/format'
import {
  BASE_STYLE, CATEGORY_LABEL, IMPACT_ZONES, NINO_BOXES, SEVERITY_COLOR, SEVERITY_LABEL, categoryIconSvg, esc,
  homeGeoJSON, impactGeoJSON, ninoGeoJSON, safeUrl,
} from '../lib/geo'

export type LayerKey = 'events' | 'buoys' | 'news' | 'nino' | 'home' | 'impacts' | 'cams'

export interface Overlay {
  id: string
  tiles: string
  maxzoom: number
  attribution?: string | null
  opacity: number
}

export interface WorldMapProps {
  events?: EventItem[]
  buoys?: TaoBuoy[]
  news?: FeedItem[]
  /** public webcams (GET /api/webcams); satellites (no real position) are skipped */
  cams?: Webcam[]
  visible: Record<LayerKey, boolean>
  base: 'dark' | 'osm'
  pacific?: boolean
  overlay?: Overlay | null
  mini?: boolean
  center?: LngLatLike
  zoom?: number
  homeRadiusKm?: number
  /**
   * Called after every move (and once when loaded) with the visible box
   * [minLon, minLat, maxLon, maxLat] in -180..180 / -90..90. minLon > maxLon when the view
   * crosses the antimeridian; null when the whole world width is visible.
   */
  onBounds?: (b: [number, number, number, number] | null) => void
  /** gives the MapLibre instance once loaded (for imperative moves such as fitBounds) */
  onMap?: (m: maplibregl.Map) => void
  /** px of the map hidden behind floating panels: the centre is shifted so the content stays in view */
  padding?: { left?: number; bottom?: number }
}

const wrapLon = (x: number) => ((((x + 180) % 360) + 360) % 360) - 180
const r2 = (x: number) => Math.round(x * 100) / 100

/**
 * Visible bounds for the API `bbox` filter (antimeridian-aware, see WorldMapProps.onBounds).
 * `pad` = px hidden behind floating panels (left side panel / bottom sheet), excluded from the box.
 */
export function mapBounds(map: maplibregl.Map, pad: { left?: number; bottom?: number } = {}): [number, number, number, number] | null {
  const c = map.getCanvas()
  const w = c.clientWidth, h = c.clientHeight
  const l = Math.min(pad.left ?? 0, w - 40), btm = Math.min(pad.bottom ?? 0, h - 40)
  const nw = map.unproject([l, 0]), se = map.unproject([w, h - btm])
  if (se.lng - nw.lng >= 359.9) return null
  const s = Math.max(-90, se.lat), n = Math.min(90, nw.lat)
  return [r2(wrapLon(nw.lng)), r2(s), r2(wrapLon(se.lng)), r2(n)]
}

const EMPTY: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] }

function eventsFC(ev: EventItem[] = []): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: ev
      .filter((e) => Number.isFinite(e.lat) && Number.isFinite(e.lon))
      .map((e) => {
        const sev = (e.severity ?? 'info') in SEVERITY_COLOR ? (e.severity ?? 'info') : 'info'
        const cat = (e.category ?? 'other') in CATEGORY_LABEL ? e.category : 'other'
        return {
          type: 'Feature',
          properties: {
            kind: 'event', title: e.title ?? '', source: e.source, url: e.url ?? '', severity: sev, category: cat,
            icon: `ev-${cat}-${sev}`, time: e.updated_at ?? e.started_at ?? '', dist: e.distance_km ?? null, rank: sev === 'red' ? 3 : sev === 'orange' ? 2 : sev === 'green' ? 1 : 0,
          },
          geometry: { type: 'Point', coordinates: [e.lon, e.lat] },
        }
      }),
  }
}

function buoysFC(b: TaoBuoy[] = []): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: b
      .filter((x) => Number.isFinite(x.lat) && Number.isFinite(x.lon))
      .map((x) => ({
        type: 'Feature',
        properties: {
          kind: 'buoy', name: x.name ?? x.station ?? x.id ?? '', sst: x.sst ?? null, anom: x.sst_anom ?? null,
          time: x.observed_at ?? x.ts ?? '', url: x.url ?? '',
        },
        geometry: { type: 'Point', coordinates: [x.lon, x.lat] },
      })),
  }
}

function newsFC(n: FeedItem[] = []): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: n
      .filter((x) => x.lat !== null && x.lon !== null && Number.isFinite(x.lat) && Number.isFinite(x.lon))
      .map((x) => ({
        type: 'Feature',
        properties: { kind: 'news', title: x.title ?? '', source: x.source, url: x.url ?? '', time: x.published_at ?? x.fetched_at, feedKind: x.kind },
        geometry: { type: 'Point', coordinates: [x.lon as number, x.lat as number] },
      })),
  }
}

/** Camera status -> marker colour (same meaning as on the Cams page). */
export const CAM_COLOR: Record<string, string> = {
  live: '#2fb36d', online: '#2fb36d', reachable: '#4ea1ff', stale: '#c98500', offline: '#8a93a3', error: '#8a93a3',
}

function camsFC(c: Webcam[] = []): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: c
      .filter((x) => x.kind !== 'satellite' && x.lat !== null && x.lon !== null && Number.isFinite(x.lat) && Number.isFinite(x.lon))
      .map((x) => ({
        type: 'Feature',
        properties: {
          kind: 'cam', id: x.id, title: x.title, place: x.place ?? '', status: x.status, why: x.why ?? '', provider: x.provider ?? '',
          url: x.page_url ?? '', time: x.last_checked ?? '', color: CAM_COLOR[x.status] ?? '#8a93a3', approx: x.coord_precision !== 'exact',
        },
        geometry: { type: 'Point', coordinates: [x.lon as number, x.lat as number] },
      })),
  }
}

function popupHtml(p: Record<string, unknown>): string {
  const url = safeUrl(p.url)
  const link = url ? `<a class="link" href="${esc(url)}" target="_blank" rel="noreferrer">Open source ↗</a>` : ''
  const t = p.time ? `<div style="color:var(--ink-3);font-size:11px">${esc(fmtDate(String(p.time)))} · ${esc(relTime(String(p.time)))}</div>` : ''
  if (p.kind === 'event') {
    const sev = String(p.severity)
    return `<div style="display:flex;gap:6px;align-items:center;margin-bottom:4px"><span class="chip" style="color:${toneText(SEVERITY_COLOR[sev])};border-color:${SEVERITY_COLOR[sev]}">${esc(SEVERITY_LABEL[sev] ?? sev)}</span><span style="color:var(--ink-2)">${esc(CATEGORY_LABEL[String(p.category)] ?? p.category)}</span></div><div style="font-weight:600;margin-bottom:2px">${esc(p.title) || '(untitled)'}</div><div style="color:var(--ink-2)">Source: ${esc(p.source)}</div>${p.dist !== null && p.dist !== undefined && p.dist !== '' ? `<div style="color:var(--ink-2)">${esc(fmtNum(Number(p.dist), 0))} km from ${esc(HOME.name)}</div>` : ''}${t}${link}`
  }
  if (p.kind === 'buoy') {
    const sst = p.sst === null || p.sst === undefined ? '--' : `${fmtNum(Number(p.sst), 2)} °C`
    const an = p.anom === null || p.anom === undefined ? '' : ` (anomaly ${fmtNum(Number(p.anom), 2)} °C)`
    return `<div style="font-weight:600">TAO/TRITON buoy ${esc(p.name)}</div><div>SST: <b>${sst}</b>${an}</div><div style="color:var(--ink-2)">Source: NOAA PMEL</div>${t}${link}`
  }
  if (p.kind === 'news') {
    return `<div style="color:var(--ink-3);font-size:11px;text-transform:uppercase">${esc(p.feedKind)} · ${esc(p.source)}</div><div style="font-weight:600;margin:2px 0">${esc(p.title)}</div>${t}${link}`
  }
  if (p.kind === 'cam') {
    const st = String(p.status)
    return `<div style="display:flex;gap:6px;align-items:center;margin-bottom:4px"><span class="chip" style="color:${toneText(String(p.color))};border-color:${esc(p.color)}">${esc(st)}</span><span style="color:var(--ink-2)">Public webcam</span></div><div style="font-weight:600">${esc(p.title)}</div><div style="color:var(--ink-2)">${esc(p.place)}${p.approx ? ' (approximate position)' : ''}</div>${p.why ? `<div style="margin-top:3px">${esc(p.why)}</div>` : ''}<div style="color:var(--ink-3);font-size:11px;margin-top:3px">Checked ${esc(relTime(String(p.time)))} · ${esc(p.provider)}</div><div style="margin-top:4px;display:flex;gap:10px"><a class="link" href="/cams?cam=${encodeURIComponent(String(p.id))}">Open on the Cams page</a>${link ? link.replace('Open source', 'Official page') : ''}</div>`
  }
  if (p.kind === 'nino') return `<div style="font-weight:600">${esc(p.name)} region</div><div style="color:var(--ink-2)">SST anomaly monitoring zone (NOAA CPC).</div>`
  if (p.kind === 'impact') {
    return `<div style="font-weight:600">${esc(p.name)}</div><div>${p.effect === 'dry' ? 'Drier' : 'Wetter'} than normal during El Nino</div><div style="color:var(--ink-3);font-size:11px;margin-top:3px">Indicative schematic (NOAA Climate.gov / WMO). Impacts vary by event and season.</div>`
  }
  return ''
}

async function loadIcons(map: maplibregl.Map) {
  const jobs: Promise<void>[] = []
  for (const cat of Object.keys(CATEGORY_LABEL)) for (const [sev, col] of Object.entries(SEVERITY_COLOR)) {
    const name = `ev-${cat}-${sev}`
    if (map.hasImage(name)) continue
    jobs.push(new Promise((res) => {
      const img = new Image(44, 44)
      img.onload = () => {
        if (!map.hasImage(name)) map.addImage(name, img, { pixelRatio: 2 })
        res()
      }
      img.onerror = () => res()
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(categoryIconSvg(cat, col))
    }))
  }
  await Promise.all(jobs)
}

const VIS: Record<LayerKey, string[]> = {
  events: ['events-sym', 'events-cluster'],
  buoys: ['buoys-c'],
  news: ['news-c'],
  nino: ['nino-fill', 'nino-line'],
  home: ['home-fill', 'home-line', 'home-pt'],
  impacts: ['impacts-fill', 'impacts-line'],
  cams: ['cams-c'],
}

export default function WorldMap(props: WorldMapProps) {
  const { events, buoys, news, cams, visible, base, pacific, overlay, mini, center, zoom, homeRadiusKm } = props
  const cbRef = useRef({ onBounds: props.onBounds, onMap: props.onMap })
  cbRef.current = { onBounds: props.onBounds, onMap: props.onMap }
  const padRef = useRef(props.padding ?? {})
  padRef.current = props.padding ?? {}
  const radiusRef = useRef(homeRadiusKm)
  radiusRef.current = homeRadiusKm
  const el = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markers = useRef<{ layer: LayerKey; m: maplibregl.Marker }[]>([])
  const [ready, setReady] = useState(false)

  // init once
  useEffect(() => {
    if (!el.current) return
    const map = new maplibregl.Map({
      container: el.current,
      style: BASE_STYLE,
      center: center ?? (pacific ? [175, 5] : [30, 10]),
      zoom: zoom ?? (mini ? 0.6 : el.current.clientWidth < 700 ? 0.3 : 1.4),
      minZoom: 0,
      renderWorldCopies: true,
      attributionControl: { compact: true },
      dragRotate: false,
      cooperativeGestures: !!mini,
    })
    mapRef.current = map
    if (!mini) map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left')
    map.touchZoomRotate.disableRotation()

    map.on('load', async () => {
      await loadIcons(map)
      map.addSource('impacts', { type: 'geojson', data: impactGeoJSON() })
      map.addLayer({
        id: 'impacts-fill', type: 'fill', source: 'impacts',
        paint: { 'fill-color': ['match', ['get', 'effect'], 'dry', '#c98500', '#3987e5'], 'fill-opacity': 0.22 },
      })
      map.addLayer({
        id: 'impacts-line', type: 'line', source: 'impacts',
        paint: { 'line-color': ['match', ['get', 'effect'], 'dry', '#e0a030', '#6da7ec'], 'line-width': 1.2, 'line-dasharray': [3, 2] },
      })
      map.addSource('nino', { type: 'geojson', data: ninoGeoJSON() })
      map.addLayer({ id: 'nino-fill', type: 'fill', source: 'nino', paint: { 'fill-color': '#e66767', 'fill-opacity': ['case', ['get', 'main'], 0.16, 0.07] } })
      map.addLayer({ id: 'nino-line', type: 'line', source: 'nino', paint: { 'line-color': '#f0a0a0', 'line-width': ['case', ['get', 'main'], 2, 1] } })
      map.addSource('home', { type: 'geojson', data: homeGeoJSON(homeRadiusKm) })
      map.addLayer({ id: 'home-fill', type: 'fill', source: 'home', filter: ['==', ['get', 'kind'], 'radius'], paint: { 'fill-color': '#4ea1ff', 'fill-opacity': 0.06 } })
      map.addLayer({ id: 'home-line', type: 'line', source: 'home', filter: ['==', ['get', 'kind'], 'radius'], paint: { 'line-color': '#4ea1ff', 'line-width': 1.5, 'line-dasharray': [2, 2] } })
      map.addLayer({ id: 'home-pt', type: 'circle', source: 'home', filter: ['==', ['get', 'kind'], 'home'], paint: { 'circle-radius': 7, 'circle-color': '#4ea1ff', 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 2.5 } })
      map.addSource('news', { type: 'geojson', data: EMPTY })
      map.addLayer({ id: 'news-c', type: 'circle', source: 'news', paint: { 'circle-radius': 5, 'circle-color': '#9085e9', 'circle-stroke-color': '#0b1626', 'circle-stroke-width': 1.5 } })
      map.addSource('cams', { type: 'geojson', data: EMPTY })
      map.addLayer({ id: 'cams-c', type: 'circle', source: 'cams', paint: { 'circle-radius': 4.5, 'circle-color': ['get', 'color'], 'circle-stroke-color': '#0b1626', 'circle-stroke-width': 2 } })
      map.addSource('buoys', { type: 'geojson', data: EMPTY })
      map.addLayer({ id: 'buoys-c', type: 'circle', source: 'buoys', paint: { 'circle-radius': 5, 'circle-color': '#199e70', 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.5 } })
      // ~2000 events: one clustered GeoJSON source rendered by WebGL layers (no DOM markers).
      map.addSource('events', {
        type: 'geojson', data: EMPTY, cluster: true, clusterMaxZoom: 4, clusterRadius: mini ? 28 : 36,
        clusterProperties: { maxRank: ['max', ['get', 'rank']] },
      })
      map.addLayer({
        id: 'events-cluster', type: 'circle', source: 'events', filter: ['has', 'point_count'],
        paint: {
          'circle-color': ['match', ['get', 'maxRank'], 3, SEVERITY_COLOR.red, 2, SEVERITY_COLOR.orange, 1, SEVERITY_COLOR.green, SEVERITY_COLOR.info],
          'circle-radius': ['step', ['get', 'point_count'], 8, 5, 10, 20, 13, 60, 16, 200, 20],
          'circle-opacity': 0.85,
          'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.5, 'circle-stroke-opacity': 0.9,
        },
      })
      map.addLayer({
        id: 'events-sym', type: 'symbol', source: 'events', filter: ['!', ['has', 'point_count']],
        layout: {
          'icon-image': ['get', 'icon'], 'icon-size': ['interpolate', ['linear'], ['zoom'], 0, 0.7, 5, 1],
          'icon-allow-overlap': true, 'symbol-sort-key': ['get', 'rank'],
        },
      })

      const clickable = ['events-cluster', 'events-sym', 'buoys-c', 'news-c', 'cams-c', 'home-pt', 'nino-fill', 'impacts-fill']
      map.on('click', (e) => {
        const layers = clickable.filter((l) => map.getLayer(l) && map.getLayoutProperty(l, 'visibility') !== 'none')
        const f = map.queryRenderedFeatures(e.point, { layers })[0]
        if (!f) return
        if (f.layer.id === 'events-cluster') {
          const src = map.getSource('events') as GeoJSONSource
          const id = Number(f.properties?.cluster_id)
          const n = Number(f.properties?.point_count)
          src.getClusterExpansionZoom(id).then((z) => {
            map.easeTo({ center: (f.geometry as GeoJSON.Point).coordinates as [number, number], zoom: Math.min(z, 8), duration: 500 })
          }).catch(() => undefined)
          src.getClusterLeaves(id, 12, 0).then((leaves) => {
            const items = leaves.map((l) => {
              const p = l.properties as Record<string, unknown>
              const u = safeUrl(p.url)
              const sev = String(p.severity)
              const t = esc(p.title) || '(untitled)'
              return `<li style="padding:3px 0;border-top:1px solid var(--line)"><span style="color:${toneText(SEVERITY_COLOR[sev] ?? '#888')};font-weight:600">${esc(SEVERITY_LABEL[sev] ?? sev)}</span> · ${u ? `<a class="link" href="${esc(u)}" target="_blank" rel="noreferrer">${t}</a>` : t}<div style="color:var(--ink-3);font-size:11px">${esc(p.source)} · ${esc(relTime(String(p.time)))}</div></li>`
            }).join('')
            new maplibregl.Popup({ maxWidth: '300px' }).setLngLat(e.lngLat)
              .setHTML(`<div style="font-weight:600;margin-bottom:4px">${n} events here</div><ul class="popup-list">${items}</ul>${n > 12 ? `<div style="color:var(--ink-3);font-size:11px;margin-top:4px">Showing 12 of ${n}. Zoom in for the rest.</div>` : ''}`)
              .addTo(map)
          }).catch(() => undefined)
          return
        }
        const props = { ...f.properties } as Record<string, unknown>
        if (f.layer.id === 'nino-fill') props.kind = 'nino'
        if (f.layer.id === 'impacts-fill') props.kind = 'impact'
        if (f.layer.id === 'home-pt') {
          new maplibregl.Popup({ maxWidth: '280px' }).setLngLat(e.lngLat)
            .setHTML(`<div style="font-weight:600">${esc(HOME.name)} (home)</div><div style="color:var(--ink-2)">Circle radius: ${radiusRef.current ?? HOME.radiusKm} km</div>`).addTo(map)
          return
        }
        const html = popupHtml(props)
        if (html) new maplibregl.Popup({ maxWidth: '300px' }).setLngLat(e.lngLat).setHTML(html).addTo(map)
      })
      for (const l of ['events-cluster', 'events-sym', 'buoys-c', 'news-c', 'cams-c', 'home-pt']) {
        map.on('mouseenter', l, () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', l, () => { map.getCanvas().style.cursor = '' })
      }

      // DOM labels (no glyph server needed)
      const mk = (layer: LayerKey, lngLat: [number, number], html: string, cls: string) => {
        const d = document.createElement('div')
        d.className = cls
        d.innerHTML = html
        markers.current.push({ layer, m: new maplibregl.Marker({ element: d, offset: layer === 'home' ? [0, -18] : [0, 0] }).setLngLat(lngLat).addTo(map) })
        // MapLibre labels every marker "Map marker": the accessible name must be the visible text
        const text = d.textContent?.trim()
        if (text) d.setAttribute('aria-label', text)
        else d.setAttribute('aria-hidden', 'true')
      }
      if (!mini) {
        for (const b of NINO_BOXES) mk('nino', b.label, esc(b.name), 'map-label map-label-nino')
        for (const z of IMPACT_ZONES) mk('impacts', z.label, `${z.effect === 'dry' ? '☀' : '☂'} ${esc(z.name)}`, `map-label map-label-${z.effect}`)
      }
      mk('home', [HOME.lon, HOME.lat], mini ? '' : esc(HOME.name), 'map-label map-label-home')
      setReady(true)
      cbRef.current.onMap?.(map)
      cbRef.current.onBounds?.(mapBounds(map, padRef.current))
    })
    map.on('moveend', () => cbRef.current.onBounds?.(mapBounds(map, padRef.current)))

    const ro = new ResizeObserver(() => map.resize())
    ro.observe(el.current)
    return () => {
      ro.disconnect()
      markers.current = []
      map.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // data
  useEffect(() => {
    const m = mapRef.current
    if (!ready || !m) return
    ;(m.getSource('events') as GeoJSONSource | undefined)?.setData(eventsFC(events))
    ;(m.getSource('buoys') as GeoJSONSource | undefined)?.setData(buoysFC(buoys))
    ;(m.getSource('news') as GeoJSONSource | undefined)?.setData(newsFC(news))
    ;(m.getSource('cams') as GeoJSONSource | undefined)?.setData(camsFC(cams))
  }, [ready, events, buoys, news, cams])

  // floating panels: keep the visual centre in the free part of the map
  const padL = props.padding?.left ?? 0
  const padB = props.padding?.bottom ?? 0
  useEffect(() => {
    const m = mapRef.current
    if (!ready || !m) return
    m.easeTo({ padding: { left: padL, bottom: padB, top: 0, right: 0 }, duration: 350 })
  }, [ready, padL, padB])

  // home circle radius (e.g. the "near Koh Samui" filter radius)
  useEffect(() => {
    const m = mapRef.current
    if (!ready || !m) return
    ;(m.getSource('home') as GeoJSONSource | undefined)?.setData(homeGeoJSON(homeRadiusKm))
  }, [ready, homeRadiusKm])

  // visibility
  useEffect(() => {
    const m = mapRef.current
    if (!ready || !m) return
    for (const [k, ids] of Object.entries(VIS) as [LayerKey, string[]][]) {
      for (const id of ids) if (m.getLayer(id)) m.setLayoutProperty(id, 'visibility', visible[k] ? 'visible' : 'none')
    }
    for (const { layer, m: mk } of markers.current) mk.getElement().style.display = visible[layer] ? '' : 'none'
  }, [ready, visible])

  // base
  useEffect(() => {
    const m = mapRef.current
    if (!ready || !m) return
    m.setLayoutProperty('base-dark', 'visibility', base === 'dark' ? 'visible' : 'none')
    m.setLayoutProperty('base-dark-ref', 'visibility', base === 'dark' ? 'visible' : 'none')
    m.setLayoutProperty('base-osm', 'visibility', base === 'osm' ? 'visible' : 'none')
  }, [ready, base])

  // pacific / atlantic centring (skip the initial render: the map was created centred already)
  const firstCentre = useRef(true)
  useEffect(() => {
    const m = mapRef.current
    if (!ready || !m || mini || center) return
    if (firstCentre.current) { firstCentre.current = false; return }
    m.easeTo({ center: pacific ? [175, 5] : [30, 10], duration: 600 })
  }, [ready, pacific, mini, center])

  // raster overlay
  useEffect(() => {
    const m = mapRef.current
    if (!ready || !m) return
    if (m.getLayer('overlay')) m.removeLayer('overlay')
    if (m.getSource('overlay')) m.removeSource('overlay')
    if (!overlay) return
    m.addSource('overlay', {
      type: 'raster', tiles: [overlay.tiles], tileSize: 256, maxzoom: overlay.maxzoom,
      attribution: overlay.attribution ?? undefined,
    })
    m.addLayer({ id: 'overlay', type: 'raster', source: 'overlay', paint: { 'raster-opacity': overlay.opacity } }, 'base-dark-ref')
  }, [ready, overlay?.tiles, overlay?.maxzoom, overlay?.attribution]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const m = mapRef.current
    if (ready && m?.getLayer('overlay') && overlay) m.setPaintProperty('overlay', 'raster-opacity', overlay.opacity)
  }, [ready, overlay?.opacity]) // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={el} className="h-full w-full" role="region" aria-label="Map" />
}
