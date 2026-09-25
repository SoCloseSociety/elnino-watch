/**
 * "How to read this page" guides and guided-tour steps, per page.
 * Tour steps point at elements by their `data-tour` attribute; the integrator adds
 * those attributes to the pages (full list in README.md). A step whose element is
 * not on the page is shown centred, so a missing attribute never breaks a tour.
 */
import type { TopicId } from './content'
import type { PageGuideDef, PageId, TourStep } from './types'

export const PAGE_IDS: PageId[] = ['overview', 'map', 'indices', 'news', 'samui', 'history', 'prep', 'sources', 'places', 'cams']

/** Route path -> page id (paths from main.tsx). */
export function pageFromPath(pathname: string): PageId | null {
  const p = pathname.replace(/\/+$/, '') || '/'
  const map: Record<string, PageId> = {
    '/': 'overview', '/map': 'map', '/indices': 'indices', '/news': 'news',
    '/samui': 'samui', '/history': 'history', '/prep': 'prep', '/sources': 'sources', '/places': 'places', '/cams': 'cams',
  }
  return map[p] ?? null
}

type Guide = Omit<PageGuideDef, 'topics'> & { topics: TopicId[] }

export const PAGE_GUIDES: Record<PageId, Guide> = {
  overview: {
    page: 'overview',
    title: 'How to read this page',
    intro: 'The one-screen summary: what El Nino is doing, what the forecasts say, and what it means for Koh Samui today.',
    steps: [
      'Start with the Koh Samui watch card: its level (0 Normal to 4 Leave) already combines all local risks.',
      'Read the briefing: a short text rebuilt every few hours from the latest data, with its sources.',
      'Check the weekly Nino 3.4 change: is El Nino still growing or starting to fade?',
      'Look at the IRI probabilities: how likely El Nino is for each coming 3-month season (DJF = Dec-Jan-Feb).',
      'Compare the current ONI line with past strong El Ninos (1982-83, 1997-98, 2015-16, 2023-24).',
      'Every value shows its date and source. A "stale" chip means the data is older than it should be.',
    ],
    topics: ['el_nino', 'nino34', 'oni', 'roni', 'iri_plume', 'risk_levels', 'anomaly'],
  },
  map: {
    page: 'map',
    title: 'How to read the map',
    intro: 'A world map of El Nino signals and hazards, with one satellite layer at a time.',
    steps: [
      'The red boxes along the equator are the Nino regions; Nino 3.4 (highlighted) is the one that defines El Nino.',
      'Orange zones usually get drier during El Nino, blue zones wetter. They are typical patterns, not this year\'s forecast.',
      'The dashed blue circle is 800 km around Koh Samui: events inside it are "near".',
      'Pick a satellite layer (sea temperature anomaly, rain, clouds, smoke...) and use the legend to read its colours.',
      'The date slider starts at the newest day the provider really has; some layers are 1-3 days behind.',
      'Click an event or buoy for details and the link to its source.',
    ],
    topics: ['map_overlays', 'layer_sst_anomaly', 'layer_himawari_ir', 'layer_aerosol', 'gdacs', 'firms_fires', 'tao_buoys'],
  },
  indices: {
    page: 'indices',
    title: 'How to read the indices',
    intro: 'Every El Nino measurement the app collects, grouped by indicator, each with its date and source.',
    steps: [
      'The shaded band from -0.5 to +0.5 is "neutral". Above it = El Nino-like, below = La Nina-like.',
      'Values are anomalies: the difference from normal, not the temperature itself.',
      'ONI and RONI are the official 3-month indices; weekly and daily Nino values are faster but noisier.',
      'The SOI works the other way round: negative = El Nino. BoM\'s SOI uses a scale about 10 times larger than NOAA\'s.',
      'Use the period selector to zoom out and compare with past events.',
    ],
    topics: ['anomaly', 'oni', 'roni', 'nino_regions', 'time_resolution', 'soi', 'bom_soi', 'mei_v2'],
  },
  news: {
    page: 'news',
    title: 'How to read the news page',
    intro: 'Official bulletins, press and public social posts about El Nino, Thailand and Samui.',
    steps: [
      'Official bulletins (NOAA, WMO, TMD...) come first in importance; press and social posts come after.',
      'Titles stay in their original language (Thai, French, Spanish...).',
      'Use the filters to focus on Samui or Thailand.',
      'News is context: the risk level gives it little weight, and never uses it alone.',
      'Check any alarming post against an official source before acting.',
    ],
    topics: ['news_signals', 'factor_news', 'cpc_alert_system', 'limitations'],
  },
  samui: {
    page: 'samui',
    title: 'How to read the Samui watch',
    intro: 'One overall level for the island, the factors behind it, and what to do now.',
    steps: [
      'The big level is the answer: 0 Normal, 1 Watch, 2 Prepare, 3 Act, 4 Leave (or Unknown if critical data is missing).',
      '"What to do now" lists the actions for this level, plus one per factor that is raised.',
      '"What would raise the level" shows the next trigger for each factor, so you know what to watch.',
      'Each factor card shows its value, threshold, explanation, source and data time. Open it to see why.',
      'The water chart compares recent rain with the 1991-2020 normal: below 75% is a warning sign.',
      'The "Leave the island" view shows departure windows by ferry for the next 7 days, routes and a checklist.',
    ],
    topics: ['risk_levels', 'risk_rules', 'risk_factors', 'data_coverage', 'factor_water', 'rain_vs_normal', 'exit_plan'],
  },
  history: {
    page: 'history',
    title: 'How to read the past El Ninos',
    intro: 'The seven strong El Ninos since 1982 replayed for Koh Samui, from the same ERA5 grid cell and the same NOAA indices the live pages use, next to the 2026-27 event so far. Numbers, not opinions: every value has its months, its source and its limits.',
    steps: [
      'Start with the takeaways: how many of the 7 events had a Feb-Apr rain below 60% of normal, how hot the dry season got, how long the dry spells were.',
      'The events table compares each El Nino (peak ONI / RONI, strength) with 2026-27 so far. The highlighted row is the current event; its Samui numbers only appear as its months complete.',
      'The Samui metrics table colours rain as % of the 1991-2020 normal (orange under 75%, red under 60%) and heat by feels-like degrees; the neutral-years median is the yardstick.',
      'The monthly charts align every event on the same water year (June of the developing year to May of the next) with the normal band; 2026 is the thick line and stops at the last complete month.',
      'The impacts timeline lists what actually happened (rationing, floods, bleaching, haze) with a verbatim quote and a checked link. "Documented" means a report says so; nothing is inferred from the numbers.',
      'Read "Method and limits" before drawing conclusions: 7 events, one 30 km cell, a warming climate, and no two El Ninos alike. While the ERA5 history is still loading, missing numbers say so instead of being estimated.',
    ],
    topics: ['analogs', 'analogs_reading', 'analogs_limits', 'analogs_impacts', 'analogs_colour_scale', 'rain_vs_normal', 'era5'],
  },
  prep: {
    page: 'prep',
    title: 'How to use the preparedness page',
    intro: 'A checklist sized for your household, for staying safely on the island through the El Nino dry season and the monsoon.',
    steps: [
      'Enter your household (adults, children, days): quantities adjust automatically.',
      'Tick what you already have; your progress is saved.',
      'Start with the "must" items in Water, Health and Documents.',
      'Open "Buy" under an item for what to look for, prices seen on real shop pages (with their date) and where to buy on Samui or online. The budget card adds it all up for your household.',
      'Scenarios describe what to do for drought, heatwave, storm/flood, haze and "island cut off".',
      'Keep the emergency contacts somewhere you can reach without the internet.',
    ],
    topics: ['preparedness', 'prep_water', 'prep_exit', 'samui_water_supply', 'shopping_panel', 'shopping_budget'],
  },
  sources: {
    page: 'sources',
    title: 'How to read the sources page',
    intro: 'Every data source, whether it works, and how fresh its data is.',
    steps: [
      'State: ok, stale, empty, error, needs config or pending (open the help for each).',
      '"Fetch ok" is not "data fresh": a source can answer while serving old data. That shows as stale.',
      'Freshness shows the age of the newest data compared with the maximum age for that source.',
      'A failing critical source can make the Samui level Unknown.',
      '"Verify all" runs every source now (it takes a while). On the public site this is reserved for the owner.',
    ],
    topics: ['sources_page', 'freshness', 'stale_data', 'sources_disagree', 'model_vs_observation', 'sources_col_interval', 'sources_col_success'],
  },
  places: {
    page: 'places',
    title: 'How to read the Places page',
    intro: 'Maenam (Koh Samui, home), Saint-Gatien-des-Bois (Normandy) and Gorokhovets (Vladimir Oblast) compared with the same data and the same rules. Every number shows its date and source.',
    steps: [
      'The cards show each place now: its level (0 Normal to 4 Leave, same scale as the Samui watch), current conditions and the factors behind the level.',
      'The comparison matrix scores long-term exposure per hazard, 0 very low to 4 very high. Tap a cell for its value, rule and source.',
      'The ranking uses weights you choose with the sliders. It is a decision aid only: it leaves out cost of living, visas, healthcare and family.',
      'The charts overlay the places month by month (temperature, rain, sunshine) and show the change expected by 2050.',
      'The El Nino panel says how much each place feels El Nino, and in which direction.',
      'Add a town to your personal list (kept in this browser). The shared list is edited by the owner only.',
    ],
    topics: ['places_page', 'place_levels', 'place_exposure_scale', 'place_ranking', 'place_enso', 'place_water', 'place_advisories'],
  },
  cams: {
    page: 'cams',
    title: 'How to read the Cams page',
    intro: 'Public cameras to check conditions with your own eyes: Samui beaches and piers, the ferry route, Thailand, the El Nino front line (Peru, Ecuador, Australia, Indonesia), Pacific buoys and satellites.',
    steps: [
      'Filter by area and kind, or keep only cams within a radius of home (Maenam).',
      'The status chip says whether the cam works now: live (fresh image), online (provider says so), reachable (published, the player will tell), stale or offline.',
      'Players load only when you press "Load player", to save data. Still images show their capture time. Some cams can only be opened on their official page.',
      'Each card says why the camera is useful (sea state before a ferry, street flooding, haze) and when it was last checked.',
      'A camera is a spot check, not a forecast: official TMD and Marine Department warnings always win.',
    ],
    topics: ['cams_page', 'webcams', 'webcams_modes', 'webcams_sea_state', 'webcams_buoycams', 'webcams_space_cams'],
  },
}

/**
 * Tour steps per page. `target` = the element's data-tour attribute value.
 * Keep this list in sync with README.md.
 */
export const TOURS: Record<PageId, (TourStep & { topic?: TopicId })[]> = {
  overview: [
    { target: 'overview-samui', title: 'Your island, in one level', body: 'This card is the Koh Samui watch: one level from 0 Normal to 4 Leave, computed from 9 local factors. Start here every time.', topic: 'risk_levels' },
    { target: 'overview-briefing', title: 'The briefing', body: 'A short summary of what changed, rebuilt from the latest data every few hours. Each section lists its sources.' },
    { target: 'overview-weekly', title: 'Is El Nino growing?', body: 'The weekly Nino 3.4 anomaly and its change from the previous week. +0.5 °C or more is El Nino-like; +1.5 °C or more is strong.', topic: 'nino34' },
    { target: 'overview-iri', title: 'What the forecasts say', body: 'The chance of El Nino, neutral or La Nina for each coming 3-month season (DJF = December-January-February).', topic: 'iri_plume' },
    { target: 'overview-oni-compare', title: 'Compared with history', body: 'The current event against the strongest El Ninos since 1982. Values are 3-month averages of the sea temperature anomaly.', topic: 'past_events' },
    { target: 'overview-analogs', title: 'What past El Ninos did', body: 'Seven strong El Ninos since 1982 replayed for Samui from ERA5: how often the Feb-Apr rain failed, the hottest dry-season day, the longest dry spell, and 2026 so far. The full page has the tables, charts and the documented impacts.', topic: 'analogs' },
    { target: 'overview-alerts', title: 'Koh Samui alerts', body: 'Alerts raised by the Koh Samui watch itself: when the island level goes up, when one factor reaches Act or Leave, or when critical data is missing for more than 6 hours. Colours are the island levels (Watch, Prepare, Act, Leave). Empty means none of that happened.', topic: 'risk_rules' },
    { target: 'help-learn', title: 'Learn more anytime', body: 'Every "?" button explains a number. The Learn page has El Nino in 5 minutes, a glossary and a FAQ.' },
  ],
  map: [
    { target: 'map-canvas', title: 'The map', body: 'Nino boxes, typical El Nino impact zones, the 800 km circle around Samui, hazards and buoys.', topic: 'map_overlays' },
    { target: 'map-layer-picker', title: 'Satellite layers', body: 'Show one satellite layer at a time: sea temperature anomaly, rain, clouds, smoke, soil moisture and more.', topic: 'layer_sst_anomaly' },
    { target: 'map-date', title: 'Date', body: 'The newest day the provider really has. Some layers are one to three days behind.' },
    { target: 'map-legend', title: 'Reading the colours', body: 'The legend gives the colour scale of the selected layer. Each layer has its own "?" with a guide.' },
    { target: 'map-vector', title: 'Vector data', body: 'Turn hazards, fires, buoys and news markers on or off. Click a marker for details and its source.', topic: 'gdacs' },
  ],
  indices: [
    { target: 'indices-range', title: 'Period', body: 'Zoom out to compare this event with past years.' },
    { target: 'indices-groups', title: 'Groups', body: 'Jump to an indicator group: ONI/RONI, weekly Nino regions, SOI, MEI, world SST, buoys.', topic: 'nino_regions' },
    { target: 'indices-chart', title: 'Reading a chart', body: 'The shaded band from -0.5 to +0.5 is neutral. Hover or tap for exact values and dates.', topic: 'anomaly' },
  ],
  news: [
    { target: 'news-filters', title: 'Filters', body: 'Filter by kind (official, news, social), source, language or keyword such as "samui".' },
    { target: 'news-list', title: 'The feed', body: 'Newest first. Titles stay in their original language. News is context, not measurement.', topic: 'news_signals' },
  ],
  samui: [
    { target: 'samui-level', title: 'The overall level', body: '0 Normal, 1 Watch, 2 Prepare, 3 Act, 4 Leave. "Unknown" means a critical data source is missing: act on the "at least" level shown.', topic: 'risk_levels' },
    { target: 'samui-actions', title: 'What to do now', body: 'The actions for the current level, plus one per raised factor.' },
    { target: 'samui-triggers', title: 'What would raise the level', body: 'The next threshold for each factor: what to keep an eye on.', topic: 'risk_rules' },
    { target: 'samui-factors', title: 'The factors', body: 'Each factor shows its value, threshold, explanation, source and data time. Nothing is hidden.', topic: 'risk_factors' },
    { target: 'samui-water', title: 'Water', body: 'Rain over 30-180 days against the 1991-2020 normal. In October-December this is the key signal for the 2027 dry season.', topic: 'rain_vs_normal' },
    { target: 'samui-analogs', title: 'Past El Ninos', body: 'What the strong El Ninos of 1982-2024 did to the island (rain deficits, heat, dry spells, documented shortages), the precedent for the 2027 dry season.', topic: 'analogs' },
    { target: 'samui-exit-tab', title: 'Leaving the island', body: 'Departure windows by ferry for the next 7 days, routes and a checklist.', topic: 'exit_plan' },
  ],
  history: [
    { target: 'history-takeaways', title: 'The takeaways', body: 'Numbered statements built from the numbers below and nothing else: counts of events under a threshold, medians, the record and its year.', topic: 'analogs' },
    { target: 'history-events', title: 'Seven El Ninos vs 2026-27', body: 'Peak ONI and RONI of each event from the NOAA CPC series, its strength, and the current event so far (highlighted).', topic: 'analogs_events_table' },
    { target: 'history-metrics', title: 'What Samui got', body: 'Rain of the refill (Oct-Dec), the dry season (Jan-May) and the danger window (Feb-Apr) as % of normal, the hottest feels-like day, heat days and the longest dry spell, per event, with the neutral-years median as the yardstick.', topic: 'analogs_colour_scale' },
    { target: 'history-charts', title: 'Month by month', body: 'Every event aligned on the same water year, with the 1991-2020 normal as a band and 2026 as the thick line, so you can see when each event turned dry or hot.', topic: 'analogs_charts' },
    { target: 'history-impacts', title: 'What actually happened', body: 'Dated reports (rationing, floods, bleaching, haze) with a verbatim quote and a link checked on the date shown. Filter by type or event. What was looked for and not found is listed too.', topic: 'analogs_impacts' },
    { target: 'history-method', title: 'Method and limits', body: 'How each number is computed and why the page shows ranges, not forecasts.', topic: 'analogs_limits' },
  ],
  prep: [
    { target: 'prep-household', title: 'Your household', body: 'Adults, children and days of self-sufficiency: quantities follow.' },
    { target: 'prep-progress', title: 'Progress', body: 'How much of the list you already have. Start with the "must" items.' },
    { target: 'prep-budget', title: 'Shopping budget', body: 'The indicative cost of the whole checklist for your household, from prices seen on real listings (with their date). Delivery and fuel not included.', topic: 'shopping_budget' },
    { target: 'prep-categories', title: 'Categories', body: 'Water, food, power, health, heat, haze, flood, communication, money, departure, documents, home and pets.', topic: 'preparedness' },
    { target: 'prep-scenarios', title: 'Scenarios', body: 'What to do step by step for drought, heatwave, storm/flood, haze and "island cut off".' },
    { target: 'prep-contacts', title: 'Emergency contacts', body: 'Write them down: phones and networks can fail in a storm.', topic: 'prep_comms' },
  ],
  sources: [
    { target: 'sources-summary', title: 'Summary', body: 'How many sources are ok, stale, failing or waiting for configuration.', topic: 'sources_page' },
    { target: 'sources-table', title: 'Each source', body: 'State, last success, success rate and data freshness, with a link to the provider.', topic: 'freshness' },
    { target: 'sources-verify', title: 'Verify', body: 'Run every source now to check that it still works. On the public site this button is reserved for the owner.' },
  ],
  places: [
    { target: 'places-cards', title: 'Each place, now', body: 'Level, current conditions and the factors behind the level, with the same rules for every place.', topic: 'place_levels' },
    { target: 'places-matrix', title: 'Long-term exposure', body: 'Hazard by hazard, 0 very low to 4 very high. Tap a cell for its value, rule and source.', topic: 'place_exposure_scale' },
    { target: 'places-ranking', title: 'Your ranking', body: 'Weight what matters to you; the ranking updates. Missing data is never counted as good.', topic: 'place_ranking' },
    { target: 'places-map', title: 'Map', body: 'The places on the shared list and your personal ones.', topic: 'place_map' },
    { target: 'places-add', title: 'Add a place', body: 'Search a town; add it to your personal list (this browser), or to the shared list if you are the owner.', topic: 'place_add' },
    { target: 'places-enso', title: 'El Nino sensitivity', body: 'How strongly each place usually feels El Nino, and in which direction (drier, wetter, warmer).', topic: 'place_enso' },
  ],
  cams: [
    { target: 'cams-filters', title: 'Filters', body: 'Area, kind, working only, and a radius around home.', topic: 'cams_page' },
    { target: 'cams-grid', title: 'The cameras', body: 'Each card shows the status, last check and why the camera is useful. Press "Load player" to start a stream.', topic: 'webcams' },
  ],
}

/** Every data-tour id used by the tours (for the README and checks). */
export function allTourTargets(): { page: PageId; target: string }[] {
  return PAGE_IDS.flatMap((page) => TOURS[page].map((s) => ({ page, target: s.target })))
}
