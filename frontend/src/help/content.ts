/**
 * Help content registry: every topic, keyed by id, plus the FAQ, myths and the
 * lookup tables that map app ids (risk factors, map layers, prep categories,
 * source states) to topic ids. Plain data, no React.
 */
import type { Topic, TopicCategory, TopicDef } from './types'
import { ENSO_TOPICS, SRC } from './topics/enso'
import { INDEX_TOPICS } from './topics/indices'
import { FORECAST_TOPICS } from './topics/forecasts'
import { HAZARD_TOPICS, LAYER_TOPICS, OCEAN_TOPICS } from './topics/ocean_hazards'
import { SAMUI_TOPICS } from './topics/samui'
import { DATA_TOPICS, PREP_TOPICS } from './topics/data_prep'
import { BACKEND_TOPICS } from './topics/backend'
import { PLACES_TOPICS } from './topics/places'
import { SHOPPING_TOPICS } from './topics/shopping'
import { EXTRA_TOPICS } from './topics/extra'
import { ANALOG_TOPICS } from './topics/analogs'

export { BACKEND_SKIPPED } from './topics/backend'

export { SRC }

const ALL = {
  // backend-written topics first: a frontend topic with the same id wins
  ...BACKEND_TOPICS,
  ...ENSO_TOPICS,
  ...INDEX_TOPICS,
  ...FORECAST_TOPICS,
  ...OCEAN_TOPICS,
  ...HAZARD_TOPICS,
  ...LAYER_TOPICS,
  ...SAMUI_TOPICS,
  ...DATA_TOPICS,
  ...PREP_TOPICS,
  ...PLACES_TOPICS,
  ...SHOPPING_TOPICS,
  ...EXTRA_TOPICS,
  ...ANALOG_TOPICS,
} satisfies Record<string, TopicDef>

/** Every valid topic id (use it to type props: `<HelpTip id="oni" />`). */
export type TopicId = keyof typeof ALL

export const TOPICS: Record<TopicId, TopicDef> = ALL

export function isTopicId(id: string | null | undefined): id is TopicId {
  return !!id && Object.prototype.hasOwnProperty.call(TOPICS, id)
}

export function getTopic(id: string | null | undefined): Topic | null {
  return isTopicId(id) ? { id, ...TOPICS[id] } : null
}

/** All topics sorted A-Z by title (glossary order). */
export function allTopics(): Topic[] {
  return (Object.keys(TOPICS) as TopicId[])
    .map((id) => ({ id, ...TOPICS[id] }))
    .sort((a, b) => a.title.localeCompare(b.title, 'en', { sensitivity: 'base' }))
}

export function topicsByCategory(cat: TopicCategory): Topic[] {
  return allTopics().filter((t) => t.category === cat)
}

/** Case-insensitive search over title, short text, aliases and id. */
export function searchTopics(q: string): Topic[] {
  const s = q.trim().toLowerCase()
  if (!s) return allTopics()
  const words = s.split(/\s+/)
  const scored = allTopics().map((t) => {
    const title = t.title.toLowerCase()
    const hay = [t.id, title, t.short, ...(t.aliases ?? []), t.body].join(' ').toLowerCase()
    let score = 0
    for (const w of words) {
      if (!hay.includes(w)) return { t, score: -1 }
      if (title.includes(w)) score += 3
      if ((t.aliases ?? []).some((a) => a.toLowerCase().includes(w))) score += 2
      if (t.short.toLowerCase().includes(w)) score += 1
    }
    return { t, score }
  })
  return scored.filter((x) => x.score >= 0).sort((a, b) => b.score - a.score).map((x) => x.t)
}

/** Dev check: related ids and [[links]] that point to no topic. Returns [] when clean. */
export function validateTopics(): string[] {
  const bad: string[] = []
  for (const id of Object.keys(TOPICS) as TopicId[]) {
    const t = TOPICS[id]
    for (const r of t.related) if (!isTopicId(r)) bad.push(`${id}: related "${r}"`)
    const text = [t.body, t.howToRead, t.whyItMatters, t.example].join('\n')
    for (const m of text.matchAll(/\[\[([a-z0-9_]+)(\|[^\]]*)?\]\]/g)) {
      if (!isTopicId(m[1])) bad.push(`${id}: link [[${m[1]}]]`)
    }
    if (/\u2014/.test(JSON.stringify(t))) bad.push(`${id}: em dash`)
  }
  return bad
}

// --------------------------------------------------------------------------- lookups

/** Samui risk factor id (from /api/local factors[].id) -> topic id. */
export const FACTOR_TOPIC: Record<string, TopicId> = {
  enso: 'factor_enso',
  water: 'factor_water',
  heat: 'factor_heat',
  flood: 'factor_flood',
  cyclone_wind: 'factor_cyclone_wind',
  sea_state: 'factor_sea_state',
  air: 'factor_air',
  marine_heat: 'factor_marine_heat',
  news: 'factor_news',
}

/** Map raster layer id (from /api/layers, backend/app/layers.py) -> topic id. */
export const LAYER_TOPIC: Record<string, TopicId> = {
  sst_anomaly: 'layer_sst_anomaly',
  sst: 'layer_sst',
  precip_imerg: 'layer_imerg',
  ir_himawari: 'layer_himawari_ir',
  truecolor_viirs: 'layer_truecolor',
  truecolor_modis: 'layer_truecolor',
  aerosol: 'layer_aerosol',
  chlorophyll: 'layer_chlorophyll',
  soil_moisture: 'layer_soil_moisture',
  land_temp_day: 'layer_land_temp',
  radar_rainviewer: 'layer_radar',
}

/** Preparedness category id (from /api/preparedness categories[].id) -> topic id. */
export const PREP_TOPIC: Record<string, TopicId> = {
  water: 'prep_water',
  food: 'prep_food',
  power: 'prep_power',
  health: 'prep_health',
  heat: 'prep_heat',
  haze: 'prep_haze',
  flood: 'prep_flood',
  comms: 'prep_comms',
  money: 'prep_money',
  exit: 'prep_exit',
  documents: 'prep_documents',
  home_pets: 'prep_home_pets',
}

/** Observation series name (from /api/latest, /api/series) -> topic id. */
export const SERIES_TOPIC: Record<string, TopicId> = {
  oni: 'oni',
  roni: 'roni',
  nino34_weekly_anom: 'nino34',
  nino34_weekly_sst: 'nino34',
  nino12_weekly_anom: 'nino12',
  nino3_weekly_anom: 'nino3',
  nino4_weekly_anom: 'nino4',
  soi: 'soi',
  bom_soi: 'bom_soi',
  mei_v2: 'mei_v2',
  world_sst_daily: 'world_sst',
}

/** Status key (from /api/status) -> topic id. */
export const STATUS_TOPIC: Record<string, TopicId> = {
  cpc_alert: 'cpc_alert_system',
  iri_plume: 'iri_plume',
  local_risk: 'risk_levels',
  asmc_haze_alert: 'asmc_haze',
  samui_seasonal: 'seasonal_outlook',
  samui_climatology: 'climatology_baseline',
  samui_marine: 'wave_height',
  tmd_warnings: 'tmd_warnings',
  tao_buoys: 'tao_buoys',
  crw_bleaching: 'coral_reef_watch',
  briefing: 'briefing',
  jma_outlook: 'jma_outlook',
  cpc_enso_probs: 'source_cpc_enso_probs',
  ecmwf_nino_plume: 'status_ecmwf_nino_plume',
  maintenance: 'retention',
  pwa_samui_notices: 'source_pwa_samui_notices',
  air4thai_samui: 'source_air4thai',
  asmc_seasonal_outlook: 'source_asmc_seasonal_outlook',
  thai_dams: 'samui_water_supply',
  samui_era5_history: 'analogs_reading',
}

/** Collector name (from /api/sources, feed/event `source`) -> topic id. `source_<name>` topics are found automatically. */
export const SOURCE_TOPIC: Record<string, TopicId> = {
  cpc_oni: 'oni',
  cpc_roni: 'roni',
  cpc_weekly_sst: 'nino_regions',
  cpc_soi: 'soi',
  psl_mei: 'mei_v2',
  bom_soi: 'bom_soi',
  cr_world_sst: 'world_sst',
  cr_nino34_daily: 'nino34',
  cpc_discussion: 'cpc_alert_system',
  iri_plume: 'iri_plume',
  jma_outlook: 'jma_outlook',
  climategov_enso_blog: 'news_signals',
  wmo_enso: 'wmo_update',
  tao_buoys: 'tao_buoys',
  crw_vs: 'coral_reef_watch',
  openmeteo_marine: 'wave_height',
  gdacs: 'gdacs',
  eonet: 'eonet',
  firms_fires: 'firms_fires',
  tmd_warnings: 'tmd_warnings',
  tmd_warnings_en: 'tmd_warnings',
  asmc_haze_alerts: 'asmc_haze',
  asmc_hotspots: 'hotspots',
  thaiwater_dams_national: 'samui_water_supply',
  thaiwater_dams: 'samui_water_supply',
  thaiwater_samui_rain: 'rain_vs_normal',
  gdelt_news: 'news_signals',
  google_news: 'news_signals',
  news_science_rss: 'news_signals',
  news_thailand_rss: 'news_signals',
  bluesky_accounts: 'news_signals',
  bluesky_search: 'news_signals',
  mastodon_tags: 'news_signals',
  reddit_search: 'news_signals',
  x_posts: 'news_signals',
  telegram_channels: 'news_signals',
  cpc_heat_content: 'series_heat_content',
  pmel_wwv: 'series_wwv',
  jma_sst_indices: 'series_nino_west',
  ecmwf_nino_plume: 'status_ecmwf_nino_plume',
  cpc_atmos_indices: 'series_trade_winds_olr',
  psl_mjo_romi: 'series_mjo',
  air4thai_south: 'source_air4thai',
  openmeteo_samui: 'open_meteo',
  openmeteo_samui_era5: 'era5',
  samui_era5_history: 'analogs_reading',
  openmeteo_samui_air: 'cams',
  openmeteo_samui_seasonal: 'seasonal_outlook',
  webcams_images: 'webcams',
  webcams_streams: 'webcams',
  webcams_windy: 'webcams',
  ecmwf_seas5: 'source_ecmwf_seas5_asia',
  nasa_gibs: 'source_nasa_gibs',
  gibs: 'source_nasa_gibs',
  rainviewer: 'source_rainviewer',
  places_forecast: 'place_current',
  places_climate: 'place_climate_charts',
  places_air: 'place_air',
  places_marine: 'place_marine',
  places_seasonal: 'place_seasonal',
  places_projection: 'place_projection',
  places_flood: 'place_river',
  places_quakes: 'place_earthquakes',
  places_fires: 'place_wildfire',
  places_warnings: 'place_warnings',
  places_advisories: 'place_advisories',
}

/** Source state (from /api/sources `state`, incl. the split-out "stale") -> topic id. */
export const SOURCE_STATE_TOPIC: Record<string, TopicId> = {
  ok: 'sources_page',
  stale: 'stale_data',
  empty: 'sources_page',
  error: 'sources_page',
  needs_config: 'sources_page',
  pending: 'sources_page',
}

/** Event category (from /api/events `category`) -> topic id. */
export const EVENT_CATEGORY_TOPIC: Record<string, TopicId> = {
  cyclone: 'tropical_cyclone',
  cyclone_track: 'event_category_cyclone_track',
  wildfire: 'firms_fires',
  haze: 'asmc_haze',
  bleaching: 'coral_reef_watch',
  flood: 'gdacs',
  drought: 'gdacs',
  storm: 'tropical_cyclone',
  volcano: 'eonet',
  earthquake: 'source_usgs_quakes_region',
  heat: 'eonet',
  other: 'eonet',
}

/** Exit-plan signal id (from /api/local/exit signals[].id) -> topic id. */
export const EXIT_SIGNAL_TOPIC: Record<string, TopicId> = {
  waves: 'exit_signal_waves',
  gusts: 'exit_signal_gusts',
  cyclone: 'exit_signal_cyclone',
  rain: 'exit_signal_rain',
  tmd_sea: 'exit_signal_tmd_sea',
}

/** Exit route mode -> topic id. */
export const ROUTE_TOPIC: Record<string, TopicId> = {
  ferry: 'exit_route_ferry',
  air: 'exit_route_air',
  rail: 'exit_route_rail',
  road: 'exit_route_ferry',
}

/** Feed item kind -> topic id. */
export const FEED_KIND_TOPIC: Record<string, TopicId> = {
  official: 'cpc_alert_system',
  news: 'news_signals',
  social: 'news_signals',
  research: 'news_signals',
}

/** Value kind (factor/series `kind`) -> topic id. */
export const VALUE_KIND_TOPIC: Record<string, TopicId> = {
  observed: 'model_vs_observation',
  forecast: 'forecast_uncertainty',
  model_analysis: 'model_vs_observation',
  reanalysis: 'era5',
  bulletin: 'cpc_alert_system',
  documented: 'analogs_impacts',
}

/** Series name -> topic id, by exact name first, then by pattern (families of series). */
export function seriesTopic(series: string | null | undefined): TopicId | null {
  if (!series) return null
  const s = series.toLowerCase()
  if (SERIES_TOPIC[s]) return SERIES_TOPIC[s]
  const rules: [RegExp, string][] = [
    [/^oni/, 'oni'],
    [/^nino34_/, 'nino34'],
    [/^nino12_/, 'nino12'],
    [/^nino3_/, 'nino3'],
    [/^nino4_/, 'nino4'],
    [/^nino_west/, 'series_nino_west'],
    [/^(dmi|iod)_/, 'series_iod_dmi'],
    [/^(heat_content|t300)/, 'series_heat_content'],
    [/^wwv/, 'series_wwv'],
    [/^mjo/, 'series_mjo'],
    [/^(trade_wind|olr|zonal_wind)/, 'series_trade_winds_olr'],
    [/^sla_pacific_east_minus_west/, 'series_sla_pacific_east_minus_west'],
    [/^sla_/, 'series_sea_level_anomaly'],
    [/^world_sst/, 'world_sst'],
    [/^era5_global_t2m/, 'series_era5_global_t2m'],
    [/^era5_sst_6060/, 'series_era5_sst_6060'],
    [/^(hadcrut5|hadsst4)_/, 'series_hadcrut5_hadsst4'],
    [/^gistemp_/, 'series_gistemp'],
    [/^ncei_/, 'series_ncei_anomalies'],
    [/^samui_power_/, 'series_samui_power'],
    [/^tao_/, 'tao_buoys'],
    [/^crw_.*dhw/, 'dhw'],
    [/^crw_/, 'coral_reef_watch'],
    [/^air4thai_.*aqi/, 'aqi'],
    [/^air4thai_/, 'source_air4thai'],
    [/^asmc_hotspots/, 'hotspots'],
    [/^(dam_|thai_large_dams|surat_)/, 'samui_water_supply'],
    [/^samui_era5_month/, 'analogs_reading'],
    [/^samui_era5/, 'era5'],
    [/^samui_(pm2|pm10)/, 'pm25'],
    [/^samui_us_aqi/, 'aqi'],
    [/^samui_apparent/, 'heat_index'],
    [/^samui_(wave|swell)/, 'wave_height'],
    [/^samui_sst/, 'sst'],
    [/^samui_gauge/, 'rain_vs_normal'],
    [/^samui_/, 'open_meteo'],
    [/^soi/, 'soi'],
    [/^mei/, 'mei_v2'],
  ]
  for (const [re, id] of rules) if (re.test(s) && isTopicId(id)) return id
  return null
}

/** Find the topic for any app id (factor, layer, prep category, series, status key, source, signal or topic id). */
export function topicFor(appId: string | null | undefined): TopicId | null {
  if (!appId) return null
  if (isTopicId(appId)) return appId
  const direct = FACTOR_TOPIC[appId] ?? LAYER_TOPIC[appId] ?? PREP_TOPIC[appId] ?? SERIES_TOPIC[appId] ?? STATUS_TOPIC[appId]
    ?? SOURCE_TOPIC[appId] ?? EXIT_SIGNAL_TOPIC[appId] ?? EVENT_CATEGORY_TOPIC[appId]
  if (direct) return direct
  for (const prefix of ['source_', 'status_', 'series_', 'layer_', 'exit_signal_', 'event_category_']) {
    if (isTopicId(prefix + appId)) return (prefix + appId) as TopicId
  }
  return seriesTopic(appId)
}

/** Topic for a collector: its own `source_<name>` topic when the backend wrote one, else the mapped domain topic. */
export function sourceTopic(name: string | null | undefined): TopicId | null {
  if (!name) return null
  const own = `source_${name}`
  if (isTopicId(own)) return own
  return SOURCE_TOPIC[name] ?? topicFor(name)
}

// --------------------------------------------------------------------------- level actions

/**
 * The risk engine's action lists per level, copied verbatim from
 * backend/app/local/risk.py LEVEL_ACTIONS (2026-09-24). The live page gets them from /api/local.
 */
export const LEVEL_ACTIONS: { n: number; key: string; label: string; meaning: string; actions: string[] }[] = [
  {
    n: 0, key: 'normal', label: 'Normal', meaning: 'Nothing abnormal expected on the island.',
    actions: [
      'Nothing urgent. Keep a basic stock: 3 days of water and food.',
      'Once a month, check the Preparedness page and tick off what is missing.',
    ],
  },
  {
    n: 1, key: 'vigilance', label: 'Watch', meaning: 'Something is building up (El Nino, a rain deficit, a distant storm). Stay informed.',
    actions: [
      'Check this page daily and follow TMD warnings.',
      'Build the stock up to 7 days of drinking water (4-5 L/person/day in the heat).',
      'Check the house cistern / tank and look for leaks.',
      'Note ferry (Seatran, Raja, Lomprayah) and airport schedules and contacts, without booking.',
    ],
  },
  {
    n: 2, key: 'prepare', label: 'Prepare', meaning: 'A real hazard is likely in the coming days or season. Get ready while it is calm.',
    actions: [
      'Build 14 days of self-sufficiency: water, no-cook food, medication (30 days).',
      'Fill and clean the cistern; fit a filter and keep purification tablets.',
      'Charge power banks, headlamps, batteries; test the generator/solar panel.',
      'Mosquito nets and repellent: dengue rises with heat and rain.',
      'Copies of documents (passport, visa, insurance) in a waterproof bag + online.',
      'Decide your departure threshold in advance (e.g. water cut for more than 3 days).',
    ],
  },
  {
    n: 3, key: 'act', label: 'Act', meaning: 'A hazard is here or imminent, or two hazards combine. Do it now.',
    actions: [
      'Apply the matching scenario (Preparedness page) now.',
      'Stock up on water and fuel before the crowds; withdraw cash (THB).',
      'Pack the go-bag and keep it by the door.',
      'Check ferries and flights every morning; have a flexible ticket in mind.',
      'Tell someone off the island about your plan and your contact points.',
    ],
  },
  {
    n: 4, key: 'leave', label: 'Leave', meaning: 'Safety or basic supplies are directly threatened.',
    actions: [
      "Leave the island while ferries and flights are running, or follow the authorities' instructions (DDPM 1784).",
      'Take the go-bag, documents, medication and cash.',
      'Shut off water/power/gas, move valuables up high, lock the house.',
      'If you cannot leave: shelter on high ground, away from the shore, radio on.',
    ],
  },
]

/** Extra action per factor at level >= 1 (backend FACTOR_ACTIONS, verbatim). */
export const FACTOR_ACTIONS: Record<string, string> = {
  water: 'Cut water use, fill jerrycans, watch PWA Samui announcements; line up a water-truck supplier.',
  heat: 'Avoid exertion between 11:00 and 16:00, drink regularly, oral rehydration salts (ORS), battery fan; check on vulnerable people.',
  flood: 'Keep documents and electronics high and dry, avoid flooded roads and slopes (landslides), never cross moving water.',
  cyclone_wind: 'Bring in or tie down anything that can fly, ready tarps and rope, follow the TMD and the DDPM (1784).',
  sea_state: 'Shop and refuel before ferry cancellations; do not go out in a small boat.',
  air: 'N95/KN95 masks outdoors, windows closed, a HEPA purifier in one room.',
  marine_heat: 'Diving/snorkelling: avoid touching stressed corals.',
  news: 'Check local information (Samui groups, PWA, municipality) before acting.',
  enso: 'Strong El Nino: prepare for the 2027 dry season now (cistern, water stock, a plan if ferries stop).',
}

// --------------------------------------------------------------------------- FAQ and myths

export interface FaqItem {
  id: string
  q: string
  /** markdown-lite */
  a: string
  topics: TopicId[]
}

export const FAQ: FaqItem[] = [
  {
    id: 'no-rain',
    q: 'Does El Nino mean no rain on Samui?',
    a: `No. El Nino tilts the odds towards less rain, it does not switch rain off. The TMD found that in El Nino years rain in Thailand is usually below normal, mostly in the hot season and early rainy season, while the effect in the middle and late rainy season is unclear.

Samui's main rain comes from the northeast monsoon (October-January). It still comes in El Nino years, and it can still flood. The worry is a weaker monsoon that leaves the reservoirs short before the February-April dry season.`,
    topics: ['el_nino_thailand', 'samui_seasons'],
  },
  {
    id: 'prepare-fine-weather',
    q: 'Why is the risk level "Prepare" when the weather is fine?',
    a: `Because the El Nino factor looks at the season ahead, not at today. A strong El Nino (ONI of +1.5 °C or more) gives that factor level 2 (Prepare), and by rule R1 the overall level takes the highest factor.

"Prepare" here means: use the calm weeks to get ready for a likely hard dry season (water stock, tank, a plan if ferries stop). It does not mean danger today. The El Nino factor can never push the level above Prepare on its own.`,
    topics: ['factor_enso', 'risk_rules'],
  },
  {
    id: 'weekly-number',
    q: 'Which number should I watch every week?',
    a: `Three things, in this order:

- **The Samui level and its headline** (Samui page): it already combines everything.
- **The water factor**: rain over the last 90 days as % of normal. During October-December, this is the key signal for the 2027 dry season.
- **The weekly Nino 3.4 anomaly** (Overview): whether El Nino is still growing or starting to fade.

Once a month, when NOAA publishes its update (second Thursday), look at the CPC status and the IRI probabilities.`,
    topics: ['risk_levels', 'factor_water', 'nino34', 'cpc_alert_system'],
  },
  {
    id: 'reliable-6-months',
    q: 'How reliable are forecasts 6 months ahead?',
    a: `For El Nino itself, forecasts made now (September) for the winter peak are fairly reliable: after the northern spring, models capture about three-quarters of the winter ups and downs. Forecasts that reach through next spring (for when El Nino ends) are much less reliable: that is the "spring predictability barrier".

For local weather on Samui 6 months ahead, forecasts only give tendencies (drier or wetter than normal), not events. Weather forecasts for specific days are useful for about a week, best for 2-3 days.`,
    topics: ['forecast_uncertainty', 'iri_plume', 'seasonal_outlook'],
  },
  {
    id: 'water-danger-period',
    q: 'When is the dangerous period for water?',
    a: `February to April 2027. That is the dry season right after the expected El Nino peak, when the water stored during the northeast monsoon is used up and heat raises demand.

The warning sign comes earlier: if October-December 2026 rain is well below normal, the reservoirs will not refill, and the dry season starts with a deficit. The water system was already rationed from 3 August 2026.`,
    topics: ['samui_water_supply', 'factor_water', 'samui_seasons'],
  },
  {
    id: 'what-is-anomaly',
    q: 'What does "+1.8 °C" mean? Is the sea 1.8 °C?',
    a: `No. It is an anomaly: the difference from normal. "+1.8 °C" means the Nino 3.4 region of the Pacific is 1.8 °C warmer than its usual temperature for that time of year (which is around 27-28 °C), averaged over three months.`,
    topics: ['anomaly', 'oni'],
  },
  {
    id: 'oni-vs-roni',
    q: 'Why do ONI and RONI show different numbers? Which is right?',
    a: `Both are correct measurements of different things. ONI compares the Nino 3.4 region with its own 30-year normal. RONI compares it with the rest of the tropical ocean, which has been warming. Since 1 February 2026 NOAA uses RONI officially, because the contrast with the rest of the tropics is what moves the rain.

This year RONI is lower (June-August 2026: ONI +1.80, RONI +1.36). The app's El Nino factor still uses ONI and the weekly Nino 3.4 value.`,
    topics: ['roni', 'oni'],
  },
  {
    id: 'soi-negative',
    q: 'The SOI is negative. Is that bad?',
    a: `A negative SOI means the air pressure is higher than usual at Darwin and lower at Tahiti, which is the atmosphere's El Nino signature. Several negative months in a row confirm that ocean and atmosphere are both in El Nino mode. It is a confirmation, not an extra danger. Careful: the Australian (BoM) SOI uses a scale about 10 times larger than NOAA's.`,
    topics: ['soi', 'bom_soi'],
  },
  {
    id: 'super-el-nino',
    q: 'Is this a "super El Nino"?',
    a: `"Super" is a media word, not an official category. NOAA said in September 2026 that there is a greater than 90% chance of a very strong event in late 2026 and early 2027, and a 75% chance of a historic one (RONI +2.5 °C or more in October-December). Stronger events make the usual impacts more likely, not certain.`,
    topics: ['strength_categories', 'event_2026'],
  },
  {
    id: 'floods-el-nino',
    q: 'Can Samui flood during an El Nino?',
    a: `Yes. El Nino shifts the seasonal odds, but single storms and monsoon surges still happen. The northeast monsoon brings Samui's heaviest rain in October-December every year. That is why the flood factor and the sea state factor are watched closely even now.`,
    topics: ['factor_flood', 'samui_seasons'],
  },
  {
    id: 'unknown',
    q: 'The level says "Unknown". Is something broken?',
    a: `One of the critical data sources (El Nino, water, heat, flood, cyclone/wind, sea state) has no current data. The app refuses to say "Normal" without it. Act on the "at least ..." level shown, check the TMD and the ferry operators yourself, and look at the Sources page to see what is failing.`,
    topics: ['unknown_level', 'data_coverage', 'sources_page'],
  },
  {
    id: 'official',
    q: 'Is this an official warning?',
    a: `No. It is a personal monitoring tool that gathers public data and explains it. Official warnings come from the Thai Meteorological Department (TMD, 1182), and evacuation orders from the DDPM (1784) and the province. If they say something different, follow them.`,
    topics: ['limitations', 'tmd_warnings'],
  },
  {
    id: 'ferries',
    q: 'How do I know if the ferries will run?',
    a: `The exit plan's departure windows grade each of the next 7 days from forecast waves, gusts, TMD Gulf wave bulletins and nearby cyclones. Around 2 m waves, small boats are told to stay ashore and fast boats are cancelled first; at 3 m the car ferries are likely suspended. Always confirm on the day with the operator or at the pier.`,
    topics: ['departure_windows', 'wave_height', 'exit_plan'],
  },
  {
    id: 'haze',
    q: 'Will there be haze on Samui?',
    a: `Samui usually has clean air. In strong El Nino years, fires in Sumatra and Borneo (and crop burning on the mainland in the dry season) can send haze over the region, as in 2015 and 2019. Watch the air factor (PM2.5), the ASMC haze alert for southern ASEAN and the aerosol map layer.`,
    topics: ['factor_air', 'asmc_haze', 'layer_aerosol'],
  },
  {
    id: 'numbers-differ',
    q: 'Why does this app show a different number from another website?',
    a: `Usually a different dataset, baseline, averaging window or update time. For air quality, many apps use the US AQI while Thai authorities use the Thai AQI. For El Nino, weekly, monthly and 3-month values differ by a few tenths of a degree. Look for the common direction.`,
    topics: ['sources_disagree', 'aqi', 'time_resolution'],
  },
  {
    id: 'how-long',
    q: 'How long will this El Nino last?',
    a: `A typical El Nino lasts 9 to 12 months and fades in the following northern spring or early summer. The IRI forecast in September 2026 kept El Nino at 90% or more until April-June 2027, then 61% for May-July 2027. The end date is the least certain part of the forecast (spring barrier).`,
    topics: ['enso_lifecycle', 'iri_plume', 'forecast_uncertainty'],
  },
  {
    id: 'why-stale',
    q: 'What does the "stale" chip mean?',
    a: `The newest data from that source is older than it should be for how often the source updates. The value is still shown with its date, but a stale "all calm" is never trusted: for the Samui level it becomes unknown.`,
    topics: ['stale_data', 'freshness'],
  },
  {
    id: 'la-nina-next',
    q: 'Will La Nina follow?',
    a: `Sometimes a strong El Nino is followed by La Nina, but not always. It is too early to say: forecasts through next spring are the least reliable. Watch the IRI probabilities in the first months of 2027.`,
    topics: ['la_nina', 'forecast_uncertainty'],
  },
]

export const MYTHS: { myth: string; fact: string; topics: TopicId[] }[] = [
  {
    myth: 'El Nino means drought everywhere.',
    fact: 'El Nino shifts rain: some regions get drier (Indonesia, Thailand, Australia), others wetter (Peru, Ecuador, southern Brazil). And even in the dry regions, it is a tilt of the odds.',
    topics: ['teleconnections'],
  },
  {
    myth: 'El Nino means no floods this year.',
    fact: 'Samui\'s northeast monsoon still arrives in October-January, and single heavy-rain events and storms still happen. El Nino does not prevent floods.',
    topics: ['factor_flood', 'samui_seasons'],
  },
  {
    myth: 'El Nino is caused by climate change.',
    fact: 'ENSO is a natural cycle that existed long before modern warming. How climate change alters ENSO is still an open research question. The warmer background ocean is, however, why NOAA now uses RONI.',
    topics: ['enso', 'roni'],
  },
  {
    myth: 'A strong El Nino guarantees a disaster.',
    fact: 'Stronger events make the usual impacts more likely, not certain. NOAA\'s own words for 2026: impacts are more likely "though not guaranteed".',
    topics: ['strength_categories', 'probability'],
  },
  {
    myth: 'If the sea anomaly is +1.8 °C, the sea near Samui is 1.8 °C warmer.',
    fact: 'The ONI measures a box of the central-eastern Pacific, thousands of kilometres away. Local sea temperature around Samui is a separate measurement (see the SST layers and Coral Reef Watch).',
    topics: ['nino34', 'anomaly', 'layer_sst_anomaly'],
  },
  {
    myth: 'No data means no problem.',
    fact: 'This app treats missing or stale data as unknown, never as safe. An "Unknown" level asks you to check official sources directly.',
    topics: ['data_coverage', 'unknown_level'],
  },
  {
    myth: 'El Nino peaks at Christmas, so by January it is over.',
    fact: 'The ocean peak is around November-January, but the effects on land often come later. For Thailand, the dry season after the peak (February-April) is usually when drought and heat hurt most.',
    topics: ['enso_lifecycle'],
  },
  {
    myth: 'Lots of news about drought means the water is running out on Samui.',
    fact: 'Keyword counts mix old stories, other places and repeats. The app gives news little weight and confirms a water crisis only with rain data plus local reports or PWA notices.',
    topics: ['news_signals', 'factor_news'],
  },
]
