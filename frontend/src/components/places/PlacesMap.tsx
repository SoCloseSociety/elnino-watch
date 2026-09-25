import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { Card } from '../ui'
import { BASE_STYLE, esc } from '../../lib/geo'
import { levelMeta } from '../../lib/format'
import { haversineKm } from '../../lib/format'
import type { GeoResult, PlaceSummary } from './api'
import { PlaceTip } from './common'

export function PlacesMap({ places, personal }: { places: PlaceSummary[]; personal: GeoResult[] }) {
  const el = useRef<HTMLDivElement>(null)
  const map = useRef<maplibregl.Map | null>(null)
  const markers = useRef<maplibregl.Marker[]>([])

  useEffect(() => {
    if (!el.current) return
    const m = new maplibregl.Map({ container: el.current, style: BASE_STYLE, center: [50, 35], zoom: 1.2, attributionControl: { compact: true } })
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.current = m
    return () => { m.remove(); map.current = null }
  }, [])

  useEffect(() => {
    const m = map.current
    if (!m) return
    for (const k of markers.current) k.remove()
    markers.current = []
    const pts: [number, number][] = []
    const add = (lat: number, lon: number, color: string, dashed: boolean, html: string, label: string) => {
      const dot = document.createElement('div')
      dot.setAttribute('role', 'img')
      dot.setAttribute('aria-label', label)
      dot.style.cssText = `width:16px;height:16px;border-radius:50%;background:${dashed ? 'transparent' : color};border:2px ${dashed ? 'dashed' : 'solid'} ${dashed ? color : 'var(--surface)'};box-shadow:0 0 0 1px ${color};cursor:pointer`
      const mk = new maplibregl.Marker({ element: dot }).setLngLat([lon, lat]).setPopup(new maplibregl.Popup({ offset: 12 }).setHTML(html)).addTo(m)
      markers.current.push(mk)
      pts.push([lon, lat])
    }
    const home = places.find((p) => p.role === 'home')
    for (const p of places) {
      const lm = levelMeta(p.level, p.level_key)
      const dist = home && home.id !== p.id ? ` · ${Math.round(haversineKm(home.lat, home.lon, p.lat, p.lon)).toLocaleString('en-GB')} km from ${esc(home.short_name)}` : ''
      add(p.lat, p.lon, lm?.color ?? 'var(--ink-3)', false,
        `<div style="font-weight:600">${esc(p.name)}${p.role === 'home' ? ' (home)' : ''}</div><div style="color:var(--ink-2)">${p.lat.toFixed(4)}, ${p.lon.toFixed(4)} · ${p.elevation_m ?? '--'} m${dist}</div><div>Level: <b>${lm ? esc(lm.label) : 'Unknown'}</b></div>`,
        `${p.name}: ${lm ? lm.label : 'level unknown'}`)
    }
    for (const g of personal) {
      add(g.latitude, g.longitude, 'var(--accent)', true,
        `<div style="font-weight:600">${esc(g.name)}</div><div style="color:var(--ink-2)">${esc([g.admin1, g.country].filter(Boolean).join(', '))}</div><div style="color:var(--ink-3);font-size:11px">Personal list (this browser only)</div>`,
        `${g.name} (personal list)`)
    }
    if (pts.length) {
      const b = new maplibregl.LngLatBounds(pts[0], pts[0])
      for (const p of pts) b.extend(p)
      m.fitBounds(b, { padding: 48, maxZoom: 6, duration: 0 })
    }
  }, [places, personal])

  return (
    <Card title="Map" help={<PlaceTip id="place_map" />} pad={false} tour="places-map">
      <div ref={el} className="h-72 w-full md:h-80" role="region" aria-label="Map of the compared places" />
      <p className="px-4 py-2 text-[11px] text-ink-3">Marker colour = current level (grey = unknown). Dashed = personal list. Click a marker for details.</p>
    </Card>
  )
}
