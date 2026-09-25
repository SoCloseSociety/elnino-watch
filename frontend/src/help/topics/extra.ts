import type { TopicDef } from '../types'

/*
 * Help for the map tile providers, the climate-context series group, the Sources table columns,
 * the Cams page and the public site. Links checked on 2026-09-24 (HTTP 200).
 */

const L = {
  gibsDocs: { title: 'NASA GIBS -- API documentation', url: 'https://nasa-gibs.github.io/gibs-api-docs/' },
  gibsPortal: { title: 'NASA Earthdata -- Global Imagery Browse Services (GIBS)', url: 'https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/gibs-api' },
  worldview: { title: 'NASA Worldview (the same imagery, interactive)', url: 'https://worldview.earthdata.nasa.gov/' },
  rainviewer: { title: 'RainViewer -- Weather Maps API', url: 'https://www.rainviewer.com/api/weather-maps-api.html' },
  pulse: { title: 'Copernicus Climate Pulse (ERA5, daily)', url: 'https://pulse.climate.copernicus.eu/' },
  hadcrut5: { title: 'Met Office Hadley Centre -- HadCRUT5', url: 'https://www.metoffice.gov.uk/hadobs/hadcrut5/' },
  gistemp: { title: 'NASA GISS -- GISTEMP', url: 'https://data.giss.nasa.gov/gistemp/' },
  cag: { title: 'NOAA NCEI -- Climate at a Glance', url: 'https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/' },
  ytPlayer: { title: 'YouTube -- embedded player parameters', url: 'https://developers.google.com/youtube/player_parameters' },
  windyCams: { title: 'Windy Webcams API', url: 'https://api.windy.com/webcams' },
  buoycams: { title: 'NOAA NDBC BuoyCAMs', url: 'https://www.ndbc.noaa.gov/buoycams.shtml' },
  omMarine: { title: 'Open-Meteo -- marine weather API', url: 'https://open-meteo.com/en/docs/marine-weather-api' },
  http403: { title: 'MDN -- HTTP 403 Forbidden', url: 'https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403' },
}

export const EXTRA_TOPICS = {
  source_nasa_gibs: {
    title: 'NASA GIBS (satellite map tiles)',
    category: 'layers',
    aliases: ['gibs', 'nasa_gibs', 'worldview', 'satellite tiles', 'wmts'],
    short: 'NASA\'s Global Imagery Browse Services: ready-made satellite map tiles (sea temperature, rain, clouds, smoke...) that the Live map draws, one layer at a time.',
    body: `GIBS is NASA's free tile service for satellite imagery. It serves hundreds of products (MODIS, VIIRS, GPM IMERG, Himawari, SMAP, GHRSST...) as map tiles, one image per day (or per 10 minutes for geostationary satellites). The Live map asks GIBS directly for the tiles of the chosen layer and date; the server only checks the layer list and the newest date GIBS really has.

It is the same imagery you see in [NASA Worldview](https://worldview.earthdata.nasa.gov/).`,
    howToRead: `- Each layer has its own colour scale: read the legend under the layer picker.
- **Date**: most layers are daily and lag 1-3 days (the satellite must pass, then NASA processes the data). "latest" layers (Himawari infrared) are near real time.
- Grey or empty areas mean no data for that day (clouds for surface products, gaps between satellite passes, night for true colour).`,
    whyItMatters: 'The map layers show the whole picture around Koh Samui (warm sea, rain bands, fire smoke from Sumatra or Borneo) that no single number captures.',
    related: ['map_overlays', 'layer_sst_anomaly', 'layer_himawari_ir', 'layer_aerosol', 'source_rainviewer'],
    sources: [L.gibsPortal, L.gibsDocs, L.worldview],
  },
  source_rainviewer: {
    title: 'RainViewer (rain radar mosaic)',
    category: 'layers',
    aliases: ['rainviewer', 'radar', 'rain radar'],
    short: 'A worldwide mosaic of national weather radars, updated every 10 minutes. The map shows the newest frame and its time.',
    body: `RainViewer collects the images of public weather radars (the Thai Meteorological Department's among them) and joins them into one map. The app asks RainViewer which frames exist and shows the newest past frame; its time is printed with the layer.`,
    howToRead: `- Colours = rain intensity (light blue light rain, yellow/red heavy rain, purple very heavy or hail).
- Only where a radar reaches (about 200-250 km from each radar). Outside, the map is empty, which does **not** mean dry.
- Frames are past radar images, not a forecast.`,
    whyItMatters: 'Radar shows a rain band approaching the Gulf of Thailand in the next hour or two, useful before a ferry crossing or a drive in a monsoon surge.',
    related: ['layer_radar', 'source_nasa_gibs', 'map_overlays'],
    sources: [L.rainviewer],
  },
  climate_context: {
    title: 'Global temperature (climate context)',
    category: 'indices',
    aliases: ['global warming', 'era5', 'hadcrut5', 'hadsst4', 'gistemp', 'ncei', 'climate pulse', 'global temperature'],
    short: 'How warm the whole planet and its oceans are compared with normal, from four agencies. It is background: El Nino adds to it for a few months.',
    body: `This group gathers the global temperature records:

- **ERA5 (Copernicus Climate Pulse)**: daily global air temperature at 2 m and daily sea surface temperature between 60 S and 60 N, with anomalies from 1991-2020 ([[series_era5_global_t2m]], [[series_era5_sst_6060]]).
- **Met Office HadCRUT5 / HadSST4**: monthly global land + sea, global sea and tropical sea anomalies, from 1961-1990 ([[series_hadcrut5_hadsst4]]).
- **NASA GISTEMP**: monthly global and yearly tropical anomalies, from 1951-1980 ([[series_gistemp]]).
- **NOAA NCEI**: monthly global and Asian land anomalies, from 1901-2000 ([[series_ncei_anomalies]]).`,
    howToRead: `- Values are **anomalies** in °C: the difference from each agency's own baseline period. An older baseline gives a bigger number for the same year, so compare the shapes of the lines, not the values across agencies.
- Daily ERA5 values arrive 2-3 days late; the monthly records about 1-6 weeks after the month ends.`,
    whyItMatters: 'A strong El Nino usually lifts the global mean by roughly 0.1-0.2 °C a few months after its peak, on top of the long warming trend. It explains why records can fall in 2027 and why the sea around Samui runs warm (coral bleaching risk).',
    related: ['anomaly', 'climatology_baseline', 'world_sst', 'series_era5_global_t2m', 'series_gistemp', 'roni'],
    sources: [L.pulse, L.hadcrut5, L.gistemp],
  },
  sources_col_interval: {
    title: 'Sources: interval',
    category: 'data',
    aliases: ['interval', 'polling', 'update frequency'],
    short: 'How often the app asks this source for new data. It follows how often the provider really updates, so it does not hammer it for nothing.',
    body: `Each collector has its own interval: a monthly index is checked every 6-12 hours, disaster alerts every 10-15 minutes, news every 15-60 minutes. A run is also capped at 5 minutes.

The interval is not the age of the data: a source checked every 10 minutes can still serve data that is days old. That is the "Data age" column ([[source_freshness]]).`,
    howToRead: '"every 6 h" = one request every 6 hours. Shorter is not better: most sources update daily or monthly.',
    related: ['sources_page', 'source_freshness', 'sources_col_last_run'],
    sources: [],
  },
  sources_col_last_run: {
    title: 'Sources: last run',
    category: 'data',
    aliases: ['last run', 'http status', 'latency'],
    short: 'When the app last contacted the source, the HTTP answer code and how long it took. "Last ok" is the last run that worked.',
    body: `Every run is logged (the last 200 per source are kept), whether it worked or not, so a silent failure is impossible.

- **HTTP 200** = the server answered normally. 4xx = refused or missing (the address changed, or a key is needed); 5xx = the provider's server failed.
- **ms** = how long the answer took.
- **last ok** appears when the newest run failed: the data shown comes from that earlier run.`,
    howToRead: 'A recent run with HTTP 200 is healthy. A run "2 d ago" on a 1 h interval means the scheduler or the server was stopped.',
    related: ['sources_page', 'sources_col_success', 'sources_col_items'],
    sources: [L.http403],
  },
  sources_col_items: {
    title: 'Sources: items',
    category: 'data',
    aliases: ['items', 'records'],
    short: 'How many records the last run received: observations, articles, events or status documents.',
    body: 'The count of what the last run stored or updated. 0 with the state "empty" means the source answered but had nothing (for example no active cyclone warning, which is good news). A sudden drop to 0 on a source that usually returns many items can mean its format changed; the state then becomes "error" with the reason.',
    howToRead: 'Compare with the usual number for that source, not between sources: an index adds one value a month, a news feed dozens a day.',
    related: ['sources_page', 'sources_col_last_run'],
    sources: [],
  },
  sources_col_success: {
    title: 'Sources: success rate',
    category: 'data',
    aliases: ['success', 'reliability'],
    short: 'Share of the recent runs (up to the last 200) that worked.',
    body: 'Below 100 % means the source sometimes fails or times out. The newest good data is still shown with its date. A low rate on a critical Koh Samui source (weather, sea, rain) is worth watching: when it fails for too long, the Samui level turns "Unknown" rather than pretending all is calm.',
    howToRead: '95-100 %: reliable. 70-95 %: occasional failures, usually a slow provider. Below 70 %: check the error column and the provider\'s site.',
    related: ['sources_page', 'unknown_level', 'sources_col_last_run'],
    sources: [],
  },
  cams_page: {
    title: 'Cams page',
    category: 'ocean',
    aliases: ['cams', 'webcam', 'live camera', 'see it yourself'],
    short: 'Public cameras to see the sea, the sky and the streets yourself: Samui beaches and piers, the ferry route, Pacific buoys and satellites.',
    body: `Forecasts say what is expected; a camera shows what is happening. Every camera here is published by its owner for public viewing (a venue's YouTube channel, a webcam portal, NOAA, JMA). Nothing is taken from private or unsecured cameras.

How each camera is shown depends on what its owner allows ([[webcams_modes]]): the owner's own player (loaded only when you click, to save data), a still image we may display (NOAA buoys, JMA satellites), or a link to the official page.`,
    howToRead: `- **Status**: live / online / reachable / stale / offline ([[webcams]]). "Last checked" is when the app last tested it.
- **Why** says what the camera is useful for (sea state before a ferry, flooding in the streets, haze).
- **Filters**: area, kind, "working only" and a radius around home (Maenam).`,
    whyItMatters: 'Before a ferry, a look at the north-coast and pier cams shows whether the strait is white with breaking waves; in a monsoon surge the street cams show standing water. Official warnings (TMD, Marine Department) always win.',
    related: ['webcams', 'webcams_sea_state', 'webcams_buoycams', 'webcams_space_cams', 'webcams_modes', 'exit_plan'],
    sources: [L.buoycams, L.windyCams],
  },
  webcams_modes: {
    title: 'Cameras: player, still image or link',
    category: 'ocean',
    aliases: ['embed', 'snapshot', 'click to load', 'link only'],
    short: 'How a camera is shown depends on what its owner allows: their own player, a still image we may display, or only a link.',
    body: `- **Player (embed)**: YouTube and Windy streams play in the owner's official player. It loads only when you press "Load player", so the page stays light on a phone connection. YouTube uses its privacy-enhanced (no-cookie) player.
- **Still image (snapshot)**: NOAA buoy cameras and JMA / NOAA satellite images are public and may be redisplayed; the app fetches the newest image through its server and shows its time.
- **Link only**: some portals (SkylineWebcams) forbid copying frames or re-streaming. The card opens their official page in a new tab.`,
    howToRead: 'A still image shows its capture time: compare it with the clock. A player may show a "not live" placeholder when the venue stopped streaming.',
    related: ['cams_page', 'webcams', 'webcams_privacy'],
    sources: [L.ytPlayer, L.buoycams],
  },
  place_marine: {
    title: 'Places: sea state near the coast',
    category: 'ocean',
    aliases: ['waves', 'sea temperature', 'marine', 'inland'],
    short: 'Wave height and sea surface temperature at the sea cell nearest to each place (Open-Meteo marine model). Inland places have none.',
    body: `For each place on the Places page the app asks the Open-Meteo marine model for the nearest sea grid cell and keeps its wave height (m) and sea surface temperature (°C), recent days and forecast. Places far from the sea (Gorokhovets, for example) get no sea cell and are shown as "inland".

The distance to the chosen cell is a rough indication: the model grid is coarse (about 5-25 km), so a sheltered bay can be calmer than its cell.`,
    howToRead: 'Waves below 1.25 m are moderate; 2 m and more stop small boats and fast ferries in the Gulf of Thailand; 3 m and more usually stop the car ferries. Values after today are forecasts.',
    whyItMatters: 'For an island (Maenam) the sea decides whether ferries and supplies run; on the mainland it matters for coastal flooding and fishing only.',
    related: ['wave_height', 'place_flood', 'departure_windows'],
    sources: [L.omMarine],
  },
  public_mode: {
    title: 'Public site (read-only)',
    category: 'data',
    aliases: ['public', 'admin', 'read only', 'owner sign-in'],
    short: 'On the public address anyone can read everything, but actions that change the server (running sources, re-evaluating, editing the shared places) are reserved for the owner.',
    body: `The public site shows the same live data as the owners' own copy. To keep it safe and fair to the data providers, visitors cannot:

- run or verify sources on demand (that would hammer the providers),
- force a re-evaluation of the Koh Samui level,
- add or remove places on the shared Places list,
- save the Preparedness checklist on the server.

Your Preparedness ticks and your personal Places list are kept **in this browser** instead (they stay after a reload, but not on another device). The owner can sign in with an admin token to get the buttons back.`,
    howToRead: 'A note "reserved for the site owner" replaces each hidden button. Everything else works normally.',
    related: ['sources_page', 'preparedness', 'place_add'],
    sources: [L.http403],
  },
} satisfies Record<string, TopicDef>
