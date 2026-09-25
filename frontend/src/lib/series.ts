import type { CatalogEntry, LatestPoint, SourceInfo } from '../api/types'
import type { TopicId } from '../help/content'

export interface SeriesMeta {
  label: string
  short: string
  group: string
  /** anomaly-like: zero line + +/-0.5 bands make sense */
  anomaly: boolean
  /** ENSO threshold bands (+/-0.5) only for Nino/ONI-like indices */
  ensoBands: boolean
  /** sign convention note (SOI is negative during El Nino) */
  note?: string
  monthly?: boolean
  refLines?: { y: number; label: string }[]
  /** series sharing a family (and unit) are drawn on one chart; default = one chart per unit in the group */
  family?: string
  /** chart title for the family */
  familyTitle?: string
}

export const GROUPS: { id: string; title: string; blurb: string; topic?: TopicId; layout?: 'charts' | 'tao' | 'multiples' | 'snapshot' }[] = [
  { id: 'oni', title: 'ONI / RONI', topic: 'oni', blurb: 'Official NOAA index: 3-month running mean of the Nino 3.4 anomaly. El Nino when >= +0.5 °C for 5 consecutive seasons.' },
  { id: 'daily', title: 'Daily Nino 3.4', topic: 'nino34', blurb: 'Daily Nino 3.4 anomaly (OISST via Climate Reanalyzer), more responsive than the monthly indices.' },
  { id: 'weekly', title: 'Nino regions (weekly)', topic: 'nino_regions', blurb: 'Sea surface temperature anomalies (OISST) by region, updated weekly.' },
  { id: 'jma', title: 'Nino indices (JMA)', topic: 'series_nino_west', blurb: 'Japan Meteorological Agency monthly SST anomalies: Nino 3 and Nino West (the warm pool north of New Guinea). A second agency to cross-check NOAA.' },
  { id: 'subsurface', title: 'Subsurface heat and warm water volume', topic: 'series_heat_content', blurb: 'Heat stored in the top 300 m of the equatorial Pacific. It leads the surface by a few months: when it drains, El Nino usually ends 3-6 months later.' },
  { id: 'atmosphere', title: 'Atmosphere: trade winds and clouds', topic: 'series_trade_winds_olr', blurb: 'The atmosphere\'s side of El Nino. Negative trade-wind anomalies = weaker trades; negative OLR = more rain clouds near the dateline. Both are El Nino-like.' },
  { id: 'soi', title: 'SOI', topic: 'soi', blurb: 'Southern Oscillation Index (Tahiti minus Darwin air pressure). Negative during El Nino.' },
  { id: 'mjo', title: 'Madden-Julian Oscillation (MJO)', topic: 'series_mjo', blurb: 'A pulse of clouds and rain that travels east around the tropics in 30-60 days. It can trigger westerly wind bursts that feed El Nino, and wet or dry spells over Thailand.' },
  { id: 'mei', title: 'MEI.v2', topic: 'mei_v2', blurb: 'Multivariate ENSO Index (NOAA PSL), bi-monthly: combines ocean and atmosphere variables in one number.' },
  { id: 'iod', title: 'Indian Ocean Dipole (IOD)', topic: 'series_iod_dmi', blurb: 'West minus east Indian Ocean SST anomaly (DMI, JMA). A positive IOD often comes with El Nino and adds to dryness over Southeast Asia and Australia.' },
  { id: 'world', title: 'Global SST vs climatology', topic: 'world_sst', blurb: 'Daily global mean sea surface temperature (OISST).' },
  { id: 'climate', title: 'Global temperature (climate context)', topic: 'climate_context', blurb: 'Global air and sea temperature from ERA5 (Copernicus Climate Pulse, daily) and the monthly records of NOAA NCEI, NASA GISTEMP and the Met Office (HadCRUT5, HadSST4). El Nino adds roughly 0.1-0.2 °C to the global mean a few months after its peak. Each agency uses its own baseline period, so their anomalies are not directly comparable.' },
  { id: 'tao', title: 'TAO/TRITON buoys', topic: 'tao_buoys', layout: 'tao', blurb: 'Temperatures measured by the equatorial Pacific buoy array.' },
  { id: 'coral', title: 'Coral reef heat stress (Gulf of Thailand)', topic: 'coral_reef_watch', blurb: 'NOAA Coral Reef Watch virtual stations around Koh Samui: sea temperature, anomaly, accumulated heat stress (Degree Heating Weeks) and the bleaching alert level.' },
  { id: 'local', title: 'Koh Samui (local)', topic: 'open_meteo', blurb: 'Local weather, sea and air series used by the Koh Samui watch: recent days plus forecasts (marked Forecast).' },
  { id: 'air', title: 'Air quality stations (Air4Thai, southern Thailand)', topic: 'source_air4thai', layout: 'snapshot', blurb: 'Latest readings of the Thai Pollution Control Department stations nearest to Samui: Thai AQI, PM2.5 and PM10.' },
  { id: 'fire', title: 'Fire hotspots (ASMC)', topic: 'hotspots', layout: 'multiples', blurb: 'Daily satellite fire hotspot counts per country / region from the ASEAN Specialised Meteorological Centre. A surge in dry weather warns of haze.' },
  { id: 'water', title: 'Water: Thai dam storage', topic: 'samui_water_supply', layout: 'snapshot', blurb: 'Reservoir storage in % of capacity (ThaiWater). Ratchaprapa (Surat Thani) is the one closest to Samui. Low storage before the dry season means water stress.' },
  { id: 'other', title: 'Other series', blurb: 'Series without a dedicated group yet.' },
]

/** Group heading for a series (by id). */
export function groupOf(id: string) {
  return GROUPS.find((g) => g.id === id)
}

const REGION: Record<string, string> = { nino12: 'Nino 1+2', nino3: 'Nino 3', nino34: 'Nino 3.4', nino4: 'Nino 4' }

export function seriesMeta(series: string): SeriesMeta {
  const s = series.toLowerCase()
  if (s === 'oni') return { label: 'ONI (Nino 3.4, 3-month mean)', short: 'ONI', group: 'oni', anomaly: true, ensoBands: true, monthly: true }
  if (s === 'oni_total') return { label: 'Nino 3.4 absolute (3-month mean)', short: 'ONI total', group: 'oni', anomaly: false, ensoBands: false, monthly: true }
  if (s.startsWith('nino34_daily')) {
    const kind = s.endsWith('anom') ? 'anom' : s.endsWith('clim') ? 'clim' : 'sst'
    return kind === 'anom'
      ? { label: 'Daily Nino 3.4 anomaly', short: 'Anomaly', group: 'daily', anomaly: true, ensoBands: true }
      : { label: kind === 'clim' ? 'Nino 3.4 climatology' : 'Daily Nino 3.4 SST', short: kind === 'clim' ? 'Climatology' : 'Nino 3.4 SST', group: 'daily', anomaly: false, ensoBands: false }
  }
  if (s === 'bom_soi') return { label: 'SOI (BoM, Troup scale)', short: 'SOI BoM', group: 'soi', anomaly: true, ensoBands: false, note: 'El Nino if sustained < -7', monthly: true, refLines: [{ y: -7, label: 'El Nino threshold -7' }, { y: 7, label: '+7 La Nina' }] }
  if (s === 'roni') return { label: 'RONI (relative ONI)', short: 'RONI', group: 'oni', anomaly: true, ensoBands: true, monthly: true }
  const m = s.match(/^(nino\d+)_weekly_(anom|sst)$/)
  if (m) {
    const r = REGION[m[1]] ?? m[1]
    return m[2] === 'anom'
      ? { label: `${r} anomaly (weekly)`, short: r, group: 'weekly', anomaly: true, ensoBands: true }
      : { label: `${r} SST (weekly, absolute)`, short: `${r} SST`, group: 'weekly', anomaly: false, ensoBands: false }
  }
  if (s.startsWith('soi')) return { label: 'SOI (NOAA CPC, standardized)', short: 'SOI', group: 'soi', anomaly: true, ensoBands: false, note: 'negative = El Nino', monthly: true }
  if (s.startsWith('mei')) return { label: 'MEI.v2', short: 'MEI', group: 'mei', anomaly: true, ensoBands: true, monthly: true }
  if (s.startsWith('world_sst')) {
    const clim = /clim|normal|mean/.test(s)
    const anom = /anom/.test(s)
    return {
      label: anom ? 'Global SST (anomaly)' : clim ? 'Global SST (climatology)' : 'Daily global SST',
      short: anom ? 'Anomaly' : clim ? 'Climatology' : 'Global SST',
      group: 'world', anomaly: anom, ensoBands: false,
    }
  }
  const jma = s.match(/^(nino3|nino_west)_jma_anom$/)
  if (jma) {
    const r = jma[1] === 'nino3' ? 'Nino 3' : 'Nino West'
    return { label: `${r} anomaly (JMA, monthly)`, short: r, group: 'jma', anomaly: true, ensoBands: jma[1] === 'nino3', monthly: true, family: 'jma', familyTitle: 'JMA SST anomalies' }
  }
  if (s === 'dmi_jma_anom') return { label: 'Dipole Mode Index (IOD, JMA)', short: 'DMI', group: 'iod', anomaly: true, ensoBands: false, monthly: true, family: 'dmi', familyTitle: 'Dipole Mode Index (west minus east)', refLines: [{ y: 0.4, label: '+0.4 positive IOD' }, { y: -0.4, label: '-0.4 negative IOD' }] }
  if (/^iod_(east|west)_jma_anom$/.test(s)) {
    const w = s.includes('west')
    return { label: `IOD ${w ? 'west' : 'east'} pole SST anomaly (JMA)`, short: w ? 'West pole' : 'East pole', group: 'iod', anomaly: true, ensoBands: false, monthly: true, family: 'iod_poles', familyTitle: 'IOD poles: SST anomalies' }
  }
  const hc = s.match(/^heat_content_(\w+?)_anom$/)
  if (hc) {
    const z = hc[1].toUpperCase().replace(/_/g, '-')
    return { label: `Upper-ocean heat content anomaly ${z}`, short: z, group: 'subsurface', anomaly: true, ensoBands: false, monthly: true, family: 'hc', familyTitle: 'Upper-ocean heat content anomaly (0-300 m, CPC)' }
  }
  const t3 = s.match(/^t300(?:_(east|west))?_(anom|total)$/)
  if (t3) {
    const part = t3[1] === 'east' ? 'east' : t3[1] === 'west' ? 'west' : 'whole basin'
    return t3[2] === 'total'
      ? { label: 'Mean temperature 0-300 m (whole basin)', short: 'T300', group: 'subsurface', anomaly: false, ensoBands: false, monthly: true, family: 't300_total', familyTitle: 'Mean temperature of the top 300 m (PMEL)' }
      : { label: `0-300 m temperature anomaly (${part})`, short: part[0].toUpperCase() + part.slice(1), group: 'subsurface', anomaly: true, ensoBands: false, monthly: true, family: 't300', familyTitle: 'Top 300 m temperature anomaly (PMEL)' }
  }
  const wv = s.match(/^wwv(?:_(east|west))?_(anom|total)$/)
  if (wv) {
    const part = wv[1] === 'east' ? 'east' : wv[1] === 'west' ? 'west' : 'whole basin'
    return wv[2] === 'total'
      ? { label: 'Warm water volume (whole basin)', short: 'WWV', group: 'subsurface', anomaly: false, ensoBands: false, monthly: true, family: 'wwv_total', familyTitle: 'Warm water volume (above 20 °C, PMEL)' }
      : { label: `Warm water volume anomaly (${part})`, short: part[0].toUpperCase() + part.slice(1), group: 'subsurface', anomaly: true, ensoBands: false, monthly: true, family: 'wwv', familyTitle: 'Warm water volume anomaly (PMEL)' }
  }
  const tw = s.match(/^trade_wind_850_(wpac|cpac|epac)_anom$/)
  if (tw) {
    const r = { wpac: 'West Pacific', cpac: 'Central Pacific', epac: 'East Pacific' }[tw[1]]!
    return { label: `Trade winds 850 hPa anomaly, ${r}`, short: r, group: 'atmosphere', anomaly: true, ensoBands: false, monthly: true, family: 'trade', familyTitle: 'Trade winds at 850 hPa (anomaly)', note: 'negative = weaker trades (El Nino-like)' }
  }
  if (s === 'olr_dateline_anom') return { label: 'Outgoing long-wave radiation anomaly at the dateline', short: 'OLR', group: 'atmosphere', anomaly: true, ensoBands: false, monthly: true, family: 'olr', note: 'negative = more rain clouds (El Nino-like)' }
  if (s === 'zonal_wind_200_anom') return { label: 'Upper-level zonal wind anomaly (200 hPa)', short: '200 hPa wind', group: 'atmosphere', anomaly: true, ensoBands: false, monthly: true, family: 'u200' }
  if (s === 'mjo_romi_amplitude') return { label: 'MJO strength (ROMI amplitude)', short: 'Amplitude', group: 'mjo', anomaly: false, ensoBands: false, family: 'mjo_amp', refLines: [{ y: 1, label: 'active MJO above 1' }] }
  if (/^mjo_romi_pc[12]$/.test(s)) return { label: `MJO ROMI ${s.endsWith('1') ? 'PC1' : 'PC2'}`, short: s.endsWith('1') ? 'PC1' : 'PC2', group: 'mjo', anomaly: true, ensoBands: false, family: 'mjo_pc', familyTitle: 'MJO phase components (ROMI PC1 / PC2)' }
  const crw = s.match(/^crw_(.+)_(alert|dhw|sst|ssta)$/)
  if (crw) {
    const place = crw[1].replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())
    const v = crw[2]
    const t = { alert: 'Bleaching alert level (0-5)', dhw: 'Degree Heating Weeks', sst: 'Sea surface temperature', ssta: 'Sea surface temperature anomaly' }[v]!
    return { label: `${t}: ${place}`, short: place, group: 'coral', anomaly: v === 'ssta', ensoBands: false, family: `crw_${v}`, familyTitle: t,
      refLines: v === 'dhw' ? [{ y: 4, label: '4: bleaching likely' }, { y: 8, label: '8: mortality likely' }] : undefined }
  }
  if (s.startsWith('air4thai_')) {
    const m2 = s.match(/^air4thai_(\w+?)_(aqi|pm25|pm10)$/)
    const v = m2?.[2] === 'aqi' ? 'Thai AQI' : m2?.[2] === 'pm25' ? 'PM2.5' : m2?.[2] === 'pm10' ? 'PM10' : series
    return { label: `${v} station ${m2?.[1]?.toUpperCase() ?? ''}`, short: v, group: 'air', anomaly: false, ensoBands: false, family: 'air' }
  }
  const hs = s.match(/^asmc_hotspots_(.+)$/)
  if (hs) {
    const names: Record<string, string> = { p_malaysia: 'Peninsular Malaysia', sabahsarawak: 'Sabah and Sarawak', lao_pdr: 'Lao PDR' }
    const n = names[hs[1]] ?? hs[1].replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    return { label: `Fire hotspots: ${n}`, short: n, group: 'fire', anomaly: false, ensoBands: false, family: 'fire' }
  }
  if (/^(dam_|thai_large_dams|surat_)/.test(s)) {
    const n = s === 'thai_large_dams_storage_pct' ? 'All large dams (national)' : s === 'surat_ratchaprapa_storage_pct' ? 'Ratchaprapa (Surat Thani)'
      : s.replace(/^dam_/, '').replace(/_storage_pct$/, '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    return { label: `${n} storage`, short: n, group: 'water', anomaly: false, ensoBands: false, family: 'water' }
  }
  const CLIMATE: Record<string, [string, string, boolean]> = {
    era5_global_t2m: ['Global air temperature at 2 m (ERA5, daily)', 'ERA5 air', false],
    era5_global_t2m_anom: ['Global air temperature anomaly (ERA5, daily, vs 1991-2020)', 'ERA5 air anomaly', false],
    era5_sst_6060: ['Global SST 60S-60N (ERA5, daily)', 'ERA5 SST', false],
    era5_sst_6060_anom: ['Global SST anomaly 60S-60N (ERA5, daily, vs 1991-2020)', 'ERA5 SST anomaly', false],
    hadcrut5_global_anom: ['Global temperature anomaly (HadCRUT5, monthly, vs 1961-1990)', 'HadCRUT5', true],
    hadsst4_global_anom: ['Global SST anomaly (HadSST4, monthly, vs 1961-1990)', 'HadSST4 global', true],
    hadsst4_tropics_anom: ['Tropical SST anomaly (HadSST4, monthly, vs 1961-1990)', 'HadSST4 tropics', true],
    gistemp_global_anom: ['Global temperature anomaly (NASA GISTEMP, monthly, vs 1951-1980)', 'GISTEMP', true],
    gistemp_tropics_annual_anom: ['Tropics temperature anomaly (NASA GISTEMP, annual, vs 1951-1980)', 'GISTEMP tropics', true],
    ncei_global_anom: ['Global temperature anomaly (NOAA NCEI, monthly, vs 20th century)', 'NCEI global', true],
    ncei_asia_land_anom: ['Asia land temperature anomaly (NOAA NCEI, monthly, vs 20th century)', 'NCEI Asia land', true],
  }
  if (CLIMATE[s]) {
    const [label, short, monthly] = CLIMATE[s]
    return { label, short, group: 'climate', anomaly: s.endsWith('_anom'), ensoBands: false, monthly, family: s }
  }
  if (s.startsWith('tao_')) {
    const st = s.replace(/^tao_/, '').replace(/_(sst|anom)$/, '').toUpperCase()
    const anom = s.endsWith('_anom')
    return { label: `TAO buoy ${st}${anom ? ' (anomaly)' : ''}`, short: st, group: 'tao', anomaly: anom, ensoBands: false }
  }
  if (s.startsWith('samui_')) {
    return { label: localLabel(s), short: localLabel(s), group: 'local', anomaly: /anom/.test(s), ensoBands: false }
  }
  return { label: series, short: series, group: 'other', anomaly: /anom/.test(s), ensoBands: false }
}

function localLabel(s: string): string {
  const map: Record<string, string> = {
    samui_temp_max: 'Koh Samui max temp.',
    samui_temp_min: 'Koh Samui min temp.',
    samui_rain: 'Koh Samui rain',
    samui_precip: 'Koh Samui rain (Open-Meteo)',
    samui_precip_prob: 'Rain probability',
    samui_pm25: 'PM2.5 Koh Samui',
    samui_pm2_5: 'PM2.5 Koh Samui',
    samui_pm10: 'PM10 Koh Samui',
    samui_us_aqi: 'Air quality index (US AQI)',
    samui_uv_max: 'UV max',
    samui_wind_gust_max: 'Max wind gusts',
    samui_apparent_temp_max: 'Max feels-like temp.',
    samui_era5_precip: 'Rain (ERA5)',
    samui_era5_temp_max: 'Max temp. (ERA5)',
    samui_era5_temp_min: 'Min temp. (ERA5)',
    samui_era5_apparent_temp_max: 'Max feels-like temp. (ERA5)',
    samui_gauge_rain_24h: 'Samui rain gauge 24 h',
    samui_sst: 'Sea temperature off Samui',
    samui_power_precip: 'Rain (NASA POWER)',
    samui_power_rh: 'Relative humidity (NASA POWER)',
    samui_power_solar: 'Solar radiation (NASA POWER)',
    samui_power_t2m: 'Mean air temp. (NASA POWER)',
    samui_power_t2m_anom: 'Air temp. anomaly (NASA POWER)',
    samui_power_t2m_max: 'Max air temp. (NASA POWER)',
    samui_power_t2m_min: 'Min air temp. (NASA POWER)',
    samui_power_wind10m: 'Wind at 10 m (NASA POWER)',
    samui_wave_height: 'Wave height off Samui',
    samui_swell_height: 'Swell height off Samui',
  }
  if (s === 'surat_ratchaprapa_storage_pct') return 'Ratchaprapa dam (storage)'
  return map[s] ?? s.replace(/^samui_/, 'Samui ').replace(/_/g, ' ')
}

export function unitLabel(u: string | null | undefined): string {
  if (!u) return ''
  const m: Record<string, string> = {
    degC: '°C', C: '°C', celsius: '°C', '°C': '°C', 'degC-weeks': '°C-weeks', mm: 'mm', 'ug/m3': 'µg/m³', 'µg/m³': 'µg/m³',
    'km/h': 'km/h', m: 'm', '%': '%', index: '', std: '', soi: '', level: '', 'W/m2': 'W/m²', 'm/s': 'm/s', '1e14 m3': 'x10^14 m3', hotspots: 'hotspots', 'Thai AQI': 'Thai AQI', 'US AQI': 'US AQI',
  }
  return m[u] ?? u
}

export function sourceLink(sources: SourceInfo[] | undefined, name: string): { title: string; href: string | null; provider: string } {
  const s = sources?.find((x) => x.name === name)
  return { title: s?.title ?? name, href: s?.homepage ?? s?.endpoint ?? null, provider: s?.provider ?? name }
}

export function findLatest(latest: LatestPoint[] | undefined, series: string, source?: string): LatestPoint | undefined {
  if (!latest) return undefined
  const all = latest.filter((l) => l.series === series && (!source || l.source === source))
  // prefer the most recent if several sources publish the same series name
  return all.sort((a, b) => (a.ts < b.ts ? 1 : -1))[0]
}

export function findCatalog(cat: CatalogEntry[] | undefined, pred: (c: CatalogEntry) => boolean): CatalogEntry | undefined {
  return cat?.filter(pred).sort((a, b) => (a.last < b.last ? 1 : -1))[0]
}

/** Max age before a series is flagged stale, by cadence. */
export function staleAfterMs(series: string): number {
  const m = seriesMeta(series)
  // annual values (mid-year timestamp) are published once a year
  if (/_annual/.test(series)) return 550 * 86400000
  // ERA5 reanalysis and NASA POWER run about 3-7 days behind real time by design
  if (/era5|_power_/.test(series)) return 12 * 86400000
  if (m.monthly) return 75 * 86400000
  if (m.group === 'weekly') return 16 * 86400000
  return 4 * 86400000
}

/** Stale = the source answered, but its newest data is older than its max age (round-2 `freshness`). */
export function isStale(s: SourceInfo): boolean {
  return s.freshness?.stale === true
}
