import type { StyleSpecification } from 'maplibre-gl'
import { HOME } from './format'

/** Two free keyless raster bases; visibility is toggled instead of swapping the style. */
export const BASE_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
      maxzoom: 19,
    },
    // Esri Dark Gray Canvas: free, keyless (CARTO raster now demands an API key)
    dark: {
      type: 'raster',
      tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}'],
      tileSize: 256,
      attribution: 'Basemap © Esri, HERE, Garmin, © OpenStreetMap contributors',
      maxzoom: 16,
    },
    darkref: {
      type: 'raster',
      tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}'],
      tileSize: 256,
      maxzoom: 16,
    },
  },
  layers: [
    { id: 'bg', type: 'background', paint: { 'background-color': '#0a1422' } },
    { id: 'base-osm', type: 'raster', source: 'osm', layout: { visibility: 'none' } },
    { id: 'base-dark', type: 'raster', source: 'dark' },
    { id: 'base-dark-ref', type: 'raster', source: 'darkref' },
  ],
}

type Ring = [number, number][]
const box = (w: number, s: number, e: number, n: number): Ring => [[w, s], [e, s], [e, n], [w, n], [w, s]]

/** Nino regions. Nino 4 crosses the antimeridian: written as 160..210 so it stays one continuous box. */
export const NINO_BOXES = [
  { id: 'nino12', name: 'Nino 1+2', ring: box(-90, -10, -80, 0), label: [-85, -5] as [number, number] },
  { id: 'nino3', name: 'Nino 3', ring: box(-150, -5, -90, 5), label: [-105, 0] as [number, number] },
  { id: 'nino34', name: 'Nino 3.4', ring: box(-170, -5, -120, 5), label: [-145, 0] as [number, number] },
  { id: 'nino4', name: 'Nino 4', ring: box(160, -5, 210, 5), label: [180, 0] as [number, number] },
]

export function ninoGeoJSON(): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: NINO_BOXES.map((b) => ({
      type: 'Feature', properties: { id: b.id, name: b.name, main: b.id === 'nino34' },
      geometry: { type: 'Polygon', coordinates: [b.ring] },
    })),
  }
}

/** Approximate, indicative El Nino teleconnection zones (NOAA Climate.gov / WMO schematics). */
export const IMPACT_ZONES: { name: string; effect: 'dry' | 'wet'; season?: string; ring: Ring; label: [number, number] }[] = [
  { name: 'Indonesia', effect: 'dry', ring: [[95, 6], [120, 7], [141, 1], [141, -9], [118, -11], [105, -8], [95, 0], [95, 6]], label: [117, -2] },
  { name: 'Northern and eastern Australia', effect: 'dry', ring: [[129, -11], [143, -10], [146, -15], [153, -25], [151, -34], [146, -38], [140, -36], [138, -25], [130, -18], [129, -11]], label: [143, -24] },
  { name: 'Thailand / Southeast Asia (dry season)', effect: 'dry', ring: [[97, 21], [106, 22], [109, 16], [108, 10], [104, 8], [100, 1], [98, 5], [97, 14], [97, 21]], label: [102, 15] },
  { name: 'Southern Africa', effect: 'dry', ring: [[14, -14], [40, -12], [36, -24], [32, -29], [26, -34], [18, -34], [13, -24], [14, -14]], label: [26, -23] },
  { name: 'Indian monsoon (below normal)', effect: 'dry', ring: [[68, 24], [74, 32], [88, 27], [88, 21], [80, 9], [76, 9], [72, 18], [68, 24]], label: [79, 21] },
  { name: 'Central America', effect: 'dry', ring: [[-92, 17], [-86, 16], [-80, 9], [-77, 8], [-83, 8], [-88, 12], [-92, 14], [-92, 17]], label: [-86, 13] },
  { name: 'Northern South America', effect: 'dry', ring: [[-77, 11], [-62, 11], [-50, 4], [-44, -3], [-55, -8], [-70, -6], [-75, 0], [-77, 11]], label: [-62, 2] },
  { name: 'Coastal Peru and Ecuador', effect: 'wet', ring: [[-81.5, 2], [-78, 2], [-77, -5], [-77, -11], [-79, -11], [-81.5, -5], [-81.5, 2]], label: [-79, -5] },
  { name: 'Southern Brazil / Uruguay', effect: 'wet', ring: [[-58, -21], [-47, -23], [-49, -30], [-53, -35], [-58, -34], [-58, -21]], label: [-53, -28] },
  { name: 'Horn of Africa (short rains)', effect: 'wet', ring: [[36, 11], [44, 12], [51, 11], [48, 4], [41, -4], [37, -4], [34, 3], [36, 11]], label: [42, 4] },
  { name: 'Southern United States (winter)', effect: 'wet', ring: [[-121, 36], [-100, 37], [-80, 35], [-80, 26], [-97, 26], [-106, 31], [-117, 32], [-121, 36]], label: [-98, 31] },
]

export function impactGeoJSON(): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: IMPACT_ZONES.map((z) => ({
      type: 'Feature', properties: { name: z.name, effect: z.effect },
      geometry: { type: 'Polygon', coordinates: [z.ring] },
    })),
  }
}

/** Geodesic circle as a polygon ring. */
export function circleRing(lat: number, lon: number, km: number, steps = 96): Ring {
  const R = 6371
  const d = km / R
  const la = (lat * Math.PI) / 180
  const lo = (lon * Math.PI) / 180
  const ring: Ring = []
  for (let i = 0; i <= steps; i++) {
    const b = (i / steps) * 2 * Math.PI
    const la2 = Math.asin(Math.sin(la) * Math.cos(d) + Math.cos(la) * Math.sin(d) * Math.cos(b))
    const lo2 = lo + Math.atan2(Math.sin(b) * Math.sin(d) * Math.cos(la), Math.cos(d) - Math.sin(la) * Math.sin(la2))
    ring.push([(lo2 * 180) / Math.PI, (la2 * 180) / Math.PI])
  }
  return ring
}

export function homeGeoJSON(radiusKm = HOME.radiusKm, lat = HOME.lat, lon = HOME.lon): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', properties: { kind: 'radius' }, geometry: { type: 'Polygon', coordinates: [circleRing(lat, lon, radiusKm)] } },
      { type: 'Feature', properties: { kind: 'home' }, geometry: { type: 'Point', coordinates: [lon, lat] } },
    ],
  }
}

export const SEVERITY_COLOR: Record<string, string> = {
  red: '#d03b3b', orange: '#ec835a', green: '#0ca30c', info: '#3987e5',
}
export const SEVERITY_LABEL: Record<string, string> = { red: 'Red', orange: 'Orange', green: 'Green', info: 'Info' }

export const CATEGORY_LABEL: Record<string, string> = {
  cyclone: 'Cyclone', flood: 'Flood', drought: 'Drought', wildfire: 'Wildfire', heat: 'Heat',
  storm: 'Storm', volcano: 'Volcano', earthquake: 'Earthquake', bleaching: 'Coral bleaching',
  haze: 'Haze', other: 'Other',
}

/** Small white glyphs (24x24 path) drawn inside the severity disc. */
export const CATEGORY_GLYPH: Record<string, string> = {
  cyclone: 'M12 4a8 8 0 1 0 8 8M12 20a8 8 0 0 1-8-8m8-2a2 2 0 1 1 0 4 2 2 0 0 1 0-4z',
  flood: 'M3 15c2-2 4-2 6 0s4 2 6 0 4-2 6 0M3 19c2-2 4-2 6 0s4 2 6 0 4-2 6 0M12 3l4 7H8z',
  drought: 'M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2 2M16.4 16.4l2 2M5.6 18.4l2-2M16.4 7.6l2-2M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8z',
  wildfire: 'M12 21c-4 0-6-3-6-6 0-4 4-6 4-10 3 2 3 5 3 5s1-2 3-3c1 3 2 5 2 8 0 3-2 6-6 6z',
  heat: 'M10 14V5a2 2 0 1 1 4 0v9a4 4 0 1 1-4 0z',
  storm: 'M7 15a4 4 0 0 1 0-8 6 6 0 0 1 11 2 3 3 0 0 1 0 6M12 13l-2 4h3l-2 4',
  volcano: 'M3 20l6-10h6l6 10zM10 6l-1-3M14 6l1-3M12 6V2',
  earthquake: 'M2 12h4l2-6 3 12 3-9 2 3h6',
  bleaching: 'M12 21V11M12 11c-3 0-5-2-5-5M12 11c3 0 5-2 5-5M12 15c-2 0-4-1-4-3M12 15c2 0 4-1 4-3',
  haze: 'M3 9h18M5 13h14M3 17h18',
  other: 'M12 7v6M12 16v1',
}

export function categoryIconSvg(category: string, color: string): string {
  const g = CATEGORY_GLYPH[category] ?? CATEGORY_GLYPH.other
  return `<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" viewBox="0 0 44 44"><circle cx="22" cy="22" r="19" fill="${color}" stroke="#0b1626" stroke-width="3"/><g transform="translate(10 10)" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="${g}"/></g></svg>`
}

export function esc(s: unknown): string {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)
}

export function safeUrl(u: unknown): string | null {
  if (typeof u !== 'string') return null
  return /^https?:\/\//i.test(u) ? u : null
}

/** What kind of picture a raster layer is (satellite observation vs gap-filled analysis), by layer id. */
export const LAYER_KIND: Record<string, { kind: 'observed' | 'model_analysis'; note: string }> = {
  sst_anomaly: { kind: 'model_analysis', note: 'Satellite analysis (MUR L4): several satellites and buoys blended and gap-filled into one daily map. Not a raw image.' },
  sst: { kind: 'model_analysis', note: 'Satellite analysis (MUR L4): several satellites and buoys blended and gap-filled into one daily map. Not a raw image.' },
  precip_imerg: { kind: 'model_analysis', note: 'Satellite estimate (GPM IMERG): rain rate derived from microwave and infrared satellites, calibrated with gauges. Not a rain-gauge measurement.' },
  ir_himawari: { kind: 'observed', note: 'Satellite observation: infrared image from Himawari-9, refreshed about every 10 minutes.' },
  truecolor_viirs: { kind: 'observed', note: 'Satellite observation: one day of polar-orbit passes stitched together (visible light, daytime only).' },
  truecolor_modis: { kind: 'observed', note: 'Satellite observation: one day of polar-orbit passes stitched together (visible light, daytime only).' },
  aerosol: { kind: 'observed', note: 'Satellite retrieval: aerosol optical depth measured from space (smoke, haze, dust). Gaps under clouds.' },
  chlorophyll: { kind: 'observed', note: 'Satellite retrieval (PACE OCI): ocean colour converted to chlorophyll. Gaps under clouds.' },
  soil_moisture: { kind: 'model_analysis', note: 'Model analysis (SMAP L4): satellite soil moisture assimilated into a land model. Usually 2-3 days behind.' },
  land_temp_day: { kind: 'observed', note: 'Satellite retrieval (MODIS): daytime land surface temperature, not air temperature. Gaps under clouds.' },
  radar_rainviewer: { kind: 'observed', note: 'Ground radar observation: the latest frame shared by national radar networks (10 min).' },
}

/** Page to open a raster layer at its provider (Worldview for NASA GIBS layers). */
export function layerSourceUrl(l: { source?: string | null; gibs_layer?: string | null }, date?: string | null): { title: string; href: string } | null {
  if (l.source === 'nasa_gibs' && l.gibs_layer) {
    return { title: 'NASA Worldview', href: `https://worldview.earthdata.nasa.gov/?l=${encodeURIComponent(l.gibs_layer)}${date ? `&t=${date}` : ''}` }
  }
  if (l.source === 'nasa_gibs') return { title: 'NASA GIBS', href: 'https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/gibs-api' }
  if (l.source === 'rainviewer') return { title: 'RainViewer', href: 'https://www.rainviewer.com/map.html' }
  return null
}

/** Plain-English meaning of each event severity colour. */
export const SEVERITY_TEXT: Record<string, string> = {
  red: 'Red: severe, likely high impact on people',
  orange: 'Orange: moderate, possible impact',
  green: 'Green: minor or low impact',
  info: 'Info: no impact level given by the source',
}
