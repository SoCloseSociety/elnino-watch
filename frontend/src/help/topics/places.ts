import type { TopicDef } from '../types'

/*
 * Help for the Places page (/places). Thresholds mirror backend/app/places/engine.py,
 * collectors.py and enso.py as written on 2026-09-24. If those change, update here.
 * Source links checked on 2026-09-24 (HTTP 200, or DOI resolved through Crossref).
 */

export const PSRC = {
  omForecast: { title: 'Open-Meteo -- weather forecast API', url: 'https://open-meteo.com/en/docs' },
  omEra5: { title: 'Open-Meteo -- historical weather API (ERA5)', url: 'https://open-meteo.com/en/docs/historical-weather-api' },
  omAir: { title: 'Open-Meteo -- air quality API (CAMS)', url: 'https://open-meteo.com/en/docs/air-quality-api' },
  omMarine: { title: 'Open-Meteo -- marine weather API', url: 'https://open-meteo.com/en/docs/marine-weather-api' },
  omSeasonal: { title: 'Open-Meteo -- seasonal forecast API (ECMWF SEAS5)', url: 'https://open-meteo.com/en/docs/seasonal-forecast-api' },
  omClimate: { title: 'Open-Meteo -- climate change API (CMIP6 HighResMIP)', url: 'https://open-meteo.com/en/docs/climate-api' },
  omFlood: { title: 'Open-Meteo -- flood API (GloFAS)', url: 'https://open-meteo.com/en/docs/flood-api' },
  omGeocode: { title: 'Open-Meteo -- geocoding API (GeoNames)', url: 'https://open-meteo.com/en/docs/geocoding-api' },
  nwsHeat: { title: 'US National Weather Service -- Heat index', url: 'https://www.weather.gov/ama/heatindex' },
  nwsCold: { title: 'US National Weather Service -- Wind chill chart', url: 'https://www.weather.gov/safety/cold-wind-chill-chart' },
  whoAir: { title: 'WHO global air quality guidelines (2021)', url: 'https://www.who.int/publications/i/item/9789240034228' },
  pcd: { title: 'Air4Thai (Thai Pollution Control Department)', url: 'https://air4thai.pcd.go.th/' },
  aridity: { title: 'JRC World Atlas of Desertification -- aridity', url: 'https://wad.jrc.ec.europa.eu/patternsaridity' },
  usgs: { title: 'USGS -- earthquake catalogue search', url: 'https://earthquake.usgs.gov/earthquakes/search/' },
  gem: { title: 'GEM -- Global seismic hazard map', url: 'https://www.globalquakemodel.org/product/global-seismic-hazard-map' },
  firms: { title: 'NASA FIRMS -- active fires', url: 'https://firms.modaps.eosdis.nasa.gov/' },
  gdacs: { title: 'GDACS -- Global Disaster Alert and Coordination System', url: 'https://www.gdacs.org/' },
  meteoalarm: { title: 'Meteoalarm (EUMETNET) -- European weather warnings', url: 'https://meteoalarm.org/' },
  vigilance: { title: 'Meteo-France -- Vigilance, Calvados', url: 'https://vigilance.meteofrance.fr/fr/calvados' },
  hydromet: { title: 'Hydrometcenter of Russia -- bulletin of dangerous weather (in Russian)', url: 'https://meteoinfo.ru/hazardsbull' },
  tmd: { title: 'Thai Meteorological Department (TMD)', url: 'https://www.tmd.go.th/' },
  fcdo: { title: 'GOV.UK -- Foreign travel advice (FCDO)', url: 'https://www.gov.uk/foreign-travel-advice' },
  state: { title: 'US Department of State -- Travel advisories (RSS feed)', url: 'https://travel.state.gov/_res/rss/TAsTWs.xml' },
  diplo: { title: 'France Diplomatie -- Conseils aux voyageurs (in French)', url: 'https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/' },
  noaaImpacts: { title: 'NOAA Climate.gov -- Global impacts of El Nino and La Nina', url: 'https://www.climate.gov/news-features/featured-images/global-impacts-el-ni%C3%B1o-and-la-ni%C3%B1a' },
  juneng: { title: 'Juneng & Tangang (2005), ENSO-related rainfall anomalies in Southeast Asia, Climate Dynamics 25', url: 'https://doi.org/10.1007/s00382-005-0031-6' },
  bronnimann: { title: 'Bronnimann (2007), Impact of ENSO on European climate, Reviews of Geophysics 45', url: 'https://doi.org/10.1029/2006RG000199' },
  metoffice: { title: 'Met Office -- El Nino and La Nina', url: 'https://www.metoffice.gov.uk/weather/learn-about/weather/oceans/el-nino' },
  samuiWater: { title: 'Bangkok Post, 29/07/2026 -- Koh Samui faces water rationing', url: 'https://www.bangkokpost.com/thailand/general/3293479/koh-samui-faces-water-rationing' },
  osm: { title: 'OpenStreetMap Nominatim (geocoder)', url: 'https://nominatim.openstreetmap.org/' },
}

const EXPOSURE_NOTE = 'Exposure scale: 0 very low, 1 low, 2 moderate, 3 high, 4 very high. Higher = more exposed. The colour of the matrix cell follows the same scale.'

export const PLACES_TOPICS = {
  places_page: {
    title: 'The Places page: comparing where to live',
    category: 'data',
    aliases: ['places', 'compare places', 'where to live', 'Maenam', 'Saint-Gatien-des-Bois', 'Gorokhovets'],
    short: 'Compares candidate towns side by side: current conditions and warnings, 1991-2020 climate, 2050 projections, natural hazards, El Nino sensitivity and official travel advice. Every number shows its date and source.',
    body: `The page answers "which of these places would suit us best, and for what?" with data, not opinion.

- **Place cards**: the current level (0-4, same names as the Samui watch) with the conditions right now. See [[place_levels]] and [[place_current]].
- **Comparison matrix**: long-term exposure per dimension (heat, cold, water, flood, storms, air, wildfire, earthquakes, El Nino sensitivity, trend to 2050), each cell with its value, rule and source. See [[place_exposure_scale]].
- **Charts**: monthly climate (temperature, rain, sunshine) and the change expected by 2050. See [[place_climate_charts]] and [[place_projection]].
- **Ranking with sliders**: you choose how much each dimension matters. See [[place_ranking]].
- **Official advisories**: what the UK, US and French governments currently say about each country. See [[place_advisories]].

The places were geocoded against OpenStreetMap and GeoNames, and their admin area checked (see [[place_add]]).`,
    whyItMatters: 'A move is a big, slow decision. The page keeps the facts, their dates and their limits in one place, so the discussion is about what matters to you, not about which numbers are right.',
    related: ['place_levels', 'place_exposure_scale', 'place_ranking', 'place_advisories', 'place_add', 'limitations'],
    sources: [PSRC.omForecast, PSRC.omEra5, PSRC.osm],
  },
  place_levels: {
    title: 'Place level (current, 0-4)',
    category: 'hazards',
    aliases: ['place level', 'current level', 'factors'],
    short: 'One level per place for NOW and the next 7 days, from 9 factors (heat, cold, water, flood, storm, air, wildfire, earthquakes, official warnings). Same names as the Samui watch: Normal, Watch, Prepare, Act, Leave.',
    body: `Each factor is scored 0-4 from real data and shows its value, threshold, source and date. The overall level is:

- **R1**: the highest factor, each capped (earthquakes at 2 Prepare; cold, water, flood, air, wildfire and warnings at 3; heat and storm can reach 4).
- **R3**: two physical hazards at 2 Prepare or more at the same time give at least 3 Act.
- If heat, water, flood or storm has no current data, the level is **Unknown**, never Normal.

For Maenam the detailed [[risk_levels|Koh Samui watch]] (with water supply, sea state, ferries...) remains the reference; its level is shown on the Maenam card.`,
    thresholds: {
      columns: ['Factor', 'Watch (1)', 'Prepare (2)', 'Act (3)'],
      rows: [
        ['Heat: highest feels-like, 7 days', '>= 39 °C', '>= 41 °C (1-2 days)', '>= 41 °C on 3+ days (>= 54 °C: Leave)'],
        ['Cold: lowest feels-like, 7 days', '<= -10 °C', '<= -28 °C', '<= -40 °C (<= -48 °C: Leave)'],
        ['Water, tropical profile (Maenam): ERA5 rain, 90 days, % of normal', '< 75%', '< 60%', '< 40% and >= 100 mm short'],
        ['Water, temperate profile (Normandy, Vladimir): 365 d / 180 d / 90 d, % of normal', '< 85% / < 75% / < 60%', '< 75% / < 60% / < 35%', '< 65% / < 50% / never on 90 d alone; >= 100 mm short'],
        ['Flood: forecast rain / river', '> 35 mm in 24 h, or river above its 99th percentile', '> 90 mm/24 h or 150 mm/72 h, or a 2-year river flood', '>= 150 mm/24 h or 250 mm/72 h, or a 10-year river flood'],
        ['Storm: forecast gusts / cyclones', '>= 75 km/h, or a cyclone within 800 km', '>= 89 km/h', '>= 118 km/h, or orange/red cyclone within 500 km (300 km: Leave)'],
        ['Air: PM2.5 24 h mean', '> 37.5', '> 75', '> 125 µg/m³'],
        ['Wildfire: VIIRS detections', '>= 3 within 100 km', '>= 25 within 50 km', '>= 100 within 50 km'],
        ['Earthquakes, 30 days, 300 km', 'M5+ within 150 km', 'M6+ (aftershocks possible)', 'M7+ (capped at 2 overall)'],
        ['Official warnings', 'yellow / region named', 'orange / severe wording', 'red'],
      ],
      note: 'Critical factors: heat, water, flood, storm. A factor whose data is too old cannot say Normal: it becomes unknown.',
    },
    whyItMatters: 'The current level tells you how each place is doing today. It is not a verdict on the place: a Russian winter cold snap or a Thai dry spell are normal parts of those climates. Use the matrix for the long view.',
    related: ['place_current', 'place_warnings', 'risk_levels', 'data_coverage', 'heat_index', 'pm25'],
    sources: [PSRC.nwsHeat, PSRC.nwsCold, PSRC.pcd],
  },
  place_current: {
    title: 'Current conditions (model analysis) and forecast badges',
    category: 'data',
    aliases: ['current conditions', 'observed', 'forecast badge', 'model'],
    short: 'The "now" values are Open-Meteo model analyses for the place (not a weather station). Future days are marked Forecast. Every value shows its time and source.',
    body: `Badges tell you what kind of number you are looking at:

- **Model**: a model analysis for the current hour, the best estimate for the exact point, not a thermometer reading.
- **Forecast**: a value for a future date; it changes with each update (every few hours).
- **Reanalysis**: ERA5, observations blended by a model after the fact, about 5 days behind.
- **Observed**: satellite fire detections, earthquakes.
- **Bulletin**: an official warning text.

Feels-like temperature combines air temperature, humidity and wind (heat index in the tropics, wind chill in the cold).`,
    whyItMatters: 'Comparing a Thai noon with a Russian night is misleading: the card shows each place\'s local time. Look at the 7-day range rather than a single hour.',
    related: ['model_vs_observation', 'open_meteo', 'era5', 'freshness', 'stale_data'],
    sources: [PSRC.omForecast],
  },
  place_exposure_scale: {
    title: 'Comparison matrix: exposure scores (0-4)',
    category: 'hazards',
    aliases: ['matrix', 'exposure', 'comparison matrix', 'very low', 'very high'],
    short: 'Each cell scores how exposed a place is to one hazard over the long term, 0 very low to 4 very high, with the value, the rule used, a note and the source.',
    body: `The matrix uses long-term data only: the 1991-2020 climate normals (ERA5), the 2050 projections (CMIP6), the earthquake record since 1976 (USGS), a year of modelled air quality (CAMS) and the curated El Nino sensitivity. Today's weather does not change it.

Hover or tap a cell for its value, rule and note. Cells without data say so and are left out of the ranking.

Rows: [[place_heat_stress]], [[place_cold]], [[place_water]], [[place_flood]], [[place_storms]], [[place_air]], [[place_wildfire]], [[place_earthquakes]], [[place_enso]], [[place_trend_2050]], [[place_coverage]].`,
    thresholds: {
      columns: ['Score', 'Label', 'Colour'],
      rows: [['0', 'very low', 'green'], ['1', 'low', 'yellow'], ['2', 'moderate', 'orange'], ['3', 'high', 'red'], ['4', 'very high', 'magenta'], ['--', 'no data', 'grey, dashed']],
      note: EXPOSURE_NOTE,
    },
    whyItMatters: 'It shows trade-offs at a glance: one place is hot, another cold, a third far from the sea but on a river.',
    related: ['place_ranking', 'place_coverage', 'climatology_baseline', 'era5'],
    sources: [PSRC.omEra5, PSRC.omClimate],
  },
  place_heat_stress: {
    title: 'Heat stress (days with feels-like above 35 °C)',
    category: 'hazards',
    aliases: ['heat days', 'heat stress', 'hot days'],
    short: 'How many days a year the feels-like maximum exceeds 35 °C (ERA5, 1991-2020 average). Humid tropical places score high even when the air temperature looks moderate.',
    body: 'Counted from ERA5 daily feels-like (apparent) maximum temperature, averaged over 1991-2020. Feels-like uses temperature, humidity and wind, so humid heat counts more than dry heat.',
    thresholds: {
      columns: ['Heat days per year', 'Exposure'],
      rows: [['< 5', '0 very low'], ['5-30', '1 low'], ['30-90', '2 moderate'], ['90-180', '3 high'], ['>= 180', '4 very high']],
      note: EXPOSURE_NOTE,
    },
    whyItMatters: 'Heat stress affects sleep, health (especially for older people and children), work and electricity bills for air conditioning. El Nino years add heat in Southeast Asia.',
    related: ['heat_index', 'place_trend_2050', 'place_exposure_scale'],
    sources: [PSRC.omEra5, PSRC.nwsHeat],
  },
  place_cold: {
    title: 'Cold / winter severity',
    category: 'hazards',
    aliases: ['cold', 'winter', 'frost days', 'snow'],
    short: 'Scored from the mean temperature of the coldest month (ERA5 1991-2020), with frost days and yearly snowfall in the note.',
    body: 'The coldest month mean summarises how hard winter is: heating needs, frozen roads, snow clearing. Frost days = days with a minimum below 0 °C. Snowfall is in cm of fresh snow per year.',
    thresholds: {
      columns: ['Coldest month mean', 'Exposure'],
      rows: [['>= 10 °C', '0 very low'], ['3 to 10 °C', '1 low'], ['-3 to 3 °C', '2 moderate'], ['-10 to -3 °C', '3 high'], ['< -10 °C', '4 very high']],
      note: EXPOSURE_NOTE,
    },
    whyItMatters: 'Cold is a real hazard for health, housing (insulation, heating fuel) and daily life, and a big change for anyone used to the tropics.',
    related: ['place_levels', 'place_trend_2050'],
    sources: [PSRC.omEra5, PSRC.nwsCold],
  },
  place_water: {
    title: 'Water / drought (aridity)',
    category: 'hazards',
    aliases: ['drought', 'aridity', 'water supply', 'P/ET0'],
    short: 'Yearly rain compared with how much water the air could evaporate (P/ET0, the UNEP aridity index), plus a penalty for long dry seasons.',
    body: `ET0 is the reference evapotranspiration: how much water a well-watered grass would lose to the air. Rain divided by ET0 is the aridity index used by UNEP and the JRC World Atlas of Desertification.

A place can be humid over the year and still run dry for months: the score gets +1 if 3 or more consecutive months receive less than half of their evaporation. Local context (for example Samui's small island reservoirs and the 2026 rationing) is added to the note, with its source, but does not change the score.

**The current "Water" factor (place level) uses a climate profile.** It compares recent ERA5 rain with the place's own 1991-2020 normal for the same days, but how long a window counts depends on where the water comes from:

- **Tropical** (coldest month >= 18 °C), e.g. Maenam: supply leans on small surface stores that one dry quarter drains. 90 days: < 75% Watch, < 60% Prepare, < 40% and >= 100 mm short Act (the Koh Samui watch bands).
- **Temperate humid, groundwater-buffered** (coldest month < 18 °C, P/ET0 >= 0.5), e.g. Saint-Gatien-des-Bois and Gorokhovets: soil and aquifers refill every winter and carry supply through a dry summer, so the 180- and 365-day windows count most (bands in the table of [[place_levels]]). A shorter window can sit at most one level above the longest one, 90 days alone can raise at most Watch (Prepare when no longer window exists), and Act also needs >= 100 mm actually missing.
- **Dry** (P/ET0 < 0.5): no dry-climate bands yet; the 90-day bands are used and the explanation says so.

**Limit today:** only the last 120 days of ERA5 are stored, so the 180- and 365-day windows cannot be computed yet. The temperate level then rests on 90 days only and the explanation calls it provisional (longer windows are never estimated). A dry quarter in Normandy (for example 38% of normal over 90 days in 2026) is therefore Watch, not Act.`,
    thresholds: {
      columns: ['Aridity index P/ET0', 'Class', 'Exposure'],
      rows: [['>= 0.65', 'humid', '0'], ['0.5-0.65', 'dry sub-humid', '1'], ['0.2-0.5', 'semi-arid', '2'], ['0.05-0.2', 'arid', '3'], ['< 0.05', 'hyper-arid', '4']],
      note: '+1 (max 4) for 3+ consecutive months with rain below half of ET0. ' + EXPOSURE_NOTE,
    },
    whyItMatters: 'Water security is where El Nino hits Samui hardest. The current rain deficit is the "Water" factor of the place level.',
    related: ['place_levels', 'place_enso', 'era5'],
    sources: [PSRC.aridity, { title: 'WMO -- Standardized Precipitation Index User Guide (WMO-No. 1090)', url: 'https://library.wmo.int/idurl/4/39629' }, PSRC.samuiWater],
  },
  place_flood: {
    title: 'Flood (heavy rain, river, coast)',
    category: 'hazards',
    aliases: ['flood', 'river', 'storm surge', 'heavy rain days'],
    short: 'The worst of three parts: days with 50 mm of rain or more, the height of the place above the nearest large river (GloFAS), and low-lying coast.',
    body: `- **Heavy rain**: ERA5 days per year with >= 50 mm. ERA5 is a ~30 km model and smooths peaks: real local downpours are stronger.
- **River**: the largest river cell (mean flow >= 1 m3/s) within about 15 km, from GloFAS. What matters is how far the place sits above it: a hilltop village above an estuary is not exposed to river floods.
- **Coast**: when a sea cell is within 10 km and the place is low (elevation from the Copernicus DEM).

See [[place_river]] for the river forecast.`,
    thresholds: {
      columns: ['Part', '1', '2', '3', '4'],
      rows: [
        ['Heavy-rain days/yr', '0.5-2', '2-5', '5-10', '>= 10'],
        ['Height above river cell', '< 30 m', '< 10 m', '< 3 m', '--'],
        ['Coastal and elevation', '< 20 m', '< 10 m', '< 5 m', '--'],
      ],
      note: 'Score = the highest part. Elevations are at the place point: individual streets can be lower. ' + EXPOSURE_NOTE,
    },
    whyItMatters: 'Floods damage homes, cut roads and ferries, and contaminate water. Check the exact plot before buying or renting.',
    related: ['place_river', 'place_levels'],
    sources: [PSRC.omEra5, PSRC.omFlood, PSRC.omMarine],
  },
  place_river: {
    title: 'River discharge (GloFAS)',
    category: 'hazards',
    aliases: ['GloFAS', 'river discharge', 'm3/s', '2-year flood'],
    short: 'Daily river flow in m3/s from the Copernicus GloFAS model for the largest river cell near the place, compared with its 2001-2020 flood levels.',
    body: `GloFAS is a global hydrological model on a 5 km grid. For each place we search 7 x 7 cells (about 15 km) and keep the one with the largest flow, then compute from 2001-2020:

- the 99th percentile of daily flow,
- the **2-year flood** (median of the yearly maxima),
- the **10-year flood** (90th percentile of the yearly maxima).

The forecast (30 days, ensemble) is compared with these levels. Model flows can differ from gauges, especially for small or regulated rivers and estuaries.`,
    whyItMatters: 'Spring snowmelt floods (Russia) and long rainy spells (Normandy) show up here days to weeks ahead.',
    related: ['place_flood', 'place_levels'],
    sources: [PSRC.omFlood],
  },
  place_storms: {
    title: 'Storms / cyclones',
    category: 'hazards',
    aliases: ['wind', 'gusts', 'storms', 'typhoon', 'cyclone'],
    short: 'Days per year with gusts of 75 km/h or more (ERA5 1991-2020). Tropical-cyclone history is added to the note with sources.',
    body: 'ERA5 gusts are for a ~30 km cell and underestimate local gusts on exposed coasts and hills. Tropical cyclones are rare events that 30 years of gust statistics do not capture well, so documented landfalls near a place are listed in the note (for Maenam: Typhoon Gay 1989 and Tropical Storm Pabuk 2019). Current cyclones come from GDACS in the place level.',
    thresholds: {
      columns: ['Gust days (>= 75 km/h) per year', 'Exposure'],
      rows: [['< 0.5', '0'], ['0.5-2', '1'], ['2-5', '2'], ['5-15', '3'], ['>= 15', '4']],
      note: EXPOSURE_NOTE,
    },
    whyItMatters: 'Storms cut power, block roads and ferries and damage roofs. On an island they can isolate you for days.',
    related: ['gdacs', 'place_levels'],
    sources: [PSRC.omEra5, PSRC.gdacs],
  },
  place_air: {
    title: 'Air quality (PM2.5, yearly mean)',
    category: 'hazards',
    aliases: ['PM2.5', 'air pollution', 'haze', 'pollen'],
    short: 'Mean PM2.5 over the last 365 days from the global CAMS model (the same model for every place), against the WHO 2021 guideline and interim targets.',
    body: `PM2.5 are fine particles (smoke, traffic, industry, dust) that reach the lungs and blood. The yearly mean comes from the CAMS global model so that all places are compared with the same tool; it is a model, not a monitoring station.

The note gives the number of days above the WHO 24-hour guideline (15 µg/m³) and above 37.5 µg/m³. In Europe the place card also shows CAMS pollen (alder, birch, grass, mugwort, olive, ragweed).`,
    thresholds: {
      columns: ['Yearly mean PM2.5', 'WHO 2021', 'Exposure'],
      rows: [['<= 5', 'guideline', '0'], ['5-10', 'interim target 4', '1'], ['10-15', 'interim target 3', '2'], ['15-25', 'interim target 2', '3'], ['> 25', 'above IT-2', '4']],
      note: EXPOSURE_NOTE,
    },
    whyItMatters: 'Southeast Asia has a smoke season (February-April) that El Nino makes worse; European villages are usually cleaner but can have pollen seasons.',
    related: ['pm25', 'aqi', 'cams', 'place_levels'],
    sources: [PSRC.whoAir, PSRC.omAir],
  },
  place_wildfire: {
    title: 'Wildfire (fire-weather months)',
    category: 'hazards',
    aliases: ['wildfire', 'forest fire', 'fire weather'],
    short: 'A climate proxy: months per year that are both warm (mean max >= 20 °C) and dry (rain below half of evaporation). Current satellite fire detections are in the place level.',
    body: 'A long fire record needs the NASA FIRMS archive, which requires a key, so the long-term score uses the climate normals as a proxy for the length of the fire-weather season. It says nothing about fuel (forests, grass) or ignition. Live detections within 100 km (VIIRS, last 24 h) are shown in the Wildfire factor of each place.',
    thresholds: {
      columns: ['Warm and dry months per year', 'Exposure'],
      rows: [['0', '0'], ['1-2', '1'], ['3-4', '2'], ['5-6', '3'], ['>= 7', '4']],
      note: EXPOSURE_NOTE,
    },
    whyItMatters: 'Wildfire smoke travels hundreds of km (Samui haze comes from fires elsewhere); nearby fires threaten homes and roads.',
    related: ['firms_fires', 'place_air'],
    sources: [PSRC.firms, PSRC.omEra5],
  },
  place_earthquakes: {
    title: 'Earthquakes (USGS record since 1976)',
    category: 'hazards',
    aliases: ['earthquakes', 'seismic', 'USGS'],
    short: 'Number of magnitude 4.5+ earthquakes within 300 km since 1976 (USGS catalogue), with the strongest one. A count, not an official hazard map.',
    body: 'The global catalogue is fairly complete for M4.5+ since the 1970s. Few or no events means low seismic activity nearby, not zero risk. For building standards, check the national seismic zoning or the GEM global hazard map. Recent quakes (30 days, M2.5+) are in the place level.',
    thresholds: {
      columns: ['M4.5+ within 300 km since 1976', 'Exposure'],
      rows: [['0', '0'], ['1-5', '1'], ['6-25', '2'], ['26-100', '3'], ['> 100', '4']],
      note: EXPOSURE_NOTE,
    },
    whyItMatters: 'Earthquakes are not linked to El Nino, but they matter for a long-term home. Coastal places also have tsunami exposure from distant quakes.',
    related: ['place_exposure_scale'],
    sources: [PSRC.usgs, PSRC.gem],
  },
  place_enso: {
    title: 'ENSO sensitivity (how much El Nino reaches a place)',
    category: 'enso',
    aliases: ['ENSO sensitivity', 'teleconnection', 'El Nino effect'],
    short: 'How strongly El Nino and La Nina change the weather of each place, assessed from agency and peer-reviewed sources: strong for Samui, weak for Normandy and central Russia.',
    body: `El Nino warms the tropical Pacific and moves the big rain-making areas. The effect reaches far-away places through the atmosphere ([[teleconnections]]), strongly near the Pacific and weakly elsewhere.

- **Maenam (Southeast Asia): strong (3).** El Nino usually brings less rain and more heat to the region (Juneng & Tangang 2005). On Samui, a weak north-east monsoon (October-January) leaves the reservoirs low for the dry season: PWA rotated water supply from August 2026.
- **Saint-Gatien-des-Bois (Normandy): weak (1).** The North Atlantic dominates; the ENSO signal in Europe is small and mostly in late winter (Bronnimann 2007). The Met Office notes El Nino is one factor that can raise the risk of colder UK winters.
- **Gorokhovets (central Russia): weak (1).** Far inland; winters are driven by the NAO / Arctic Oscillation and the Siberian High. No agency statement specific to the region was found.

For 2026-27 (a strong El Nino): Samui should prepare for a drier end of monsoon and a long, hot 2027 dry season; for Normandy and Gorokhovets, El Nino says little, so use the ECMWF seasonal anomalies on the page.`,
    thresholds: {
      columns: ['Score', 'Meaning'],
      rows: [['0', 'none known'], ['1', 'weak / indirect'], ['2', 'moderate'], ['3', 'strong'], ['4', 'very strong (Indonesia, coastal Peru, eastern Australia)'], ['--', 'not assessed (added places outside the curated regions)']],
      note: 'Curated, not measured: each region lists its evidence. ' + EXPOSURE_NOTE,
    },
    whyItMatters: 'This project exists because of the 2026 El Nino. A place with weak sensitivity is not "safe", it is simply less affected by this particular driver.',
    related: ['teleconnections', 'el_nino_thailand', 'place_seasonal'],
    sources: [PSRC.juneng, PSRC.bronnimann, PSRC.metoffice],
  },
  place_trend_2050: {
    title: 'Climate trend to 2050 (CMIP6)',
    category: 'forecasts',
    aliases: ['2050', 'climate change', 'projection', 'CMIP6', 'warming'],
    short: 'Change between 1991-2020 and 2036-2050 in mean temperature and hot days (> 35 °C), from 6 high-resolution climate models on a high-emission pathway. The model range is shown.',
    body: 'The Open-Meteo climate API gives daily data from 6 CMIP6 HighResMIP models, bias-corrected on ERA5-Land (10 km). Their future forcing is as close to the high-emission RCP8.5 / SSP5-8.5 pathway as CMIP6 allows; before 2050 the scenarios differ little. The daily mean is taken as (max + min) / 2. Hot day = model daily maximum above 35 °C (air temperature, not feels-like).',
    thresholds: {
      columns: ['Warming (ensemble mean)', 'Exposure'],
      rows: [['< 0.75 °C', '0'], ['0.75-1.25 °C', '1'], ['1.25-1.75 °C', '2'], ['1.75-2.5 °C', '3'], ['>= 2.5 °C', '4']],
      note: 'At least 2 if hot days rise by 10 or more per year, at least 3 if by 30 or more. Fewer frost days are shown but not scored. ' + EXPOSURE_NOTE,
    },
    whyItMatters: 'A home is for decades. Warming reduces cold hazards in Russia but adds heat everywhere, most painfully where it is already hot and humid.',
    related: ['place_projection', 'place_heat_stress', 'place_cold'],
    sources: [PSRC.omClimate],
  },
  place_projection: {
    title: 'Chart: change by 2050 per place',
    category: 'forecasts',
    aliases: ['projection chart'],
    short: 'Bars show the ensemble-mean change 2036-2050 vs 1991-2020 for each place; the thin range is the lowest and highest of the 6 models.',
    body: 'Read the bar for the average model answer and the range for the uncertainty. Precipitation changes are in % and often disagree in sign between models: treat them as uncertain.',
    related: ['place_trend_2050'],
    sources: [PSRC.omClimate],
  },
  place_climate_charts: {
    title: 'Monthly climate charts (1991-2020 normals)',
    category: 'forecasts',
    aliases: ['climate chart', 'monthly normals', 'sunshine hours'],
    short: 'Average temperature, rain and sunshine for each month of the year, per place (ERA5, 1991-2020). Lines overlay the places so seasons can be compared.',
    body: 'Temperature: mean of daily means, with the average daily max and min available in the table view. Rain: mean monthly total in mm. Sunshine: hours of sunshine per month, computed by Open-Meteo from modelled solar radiation (not a sunshine recorder), so it can read higher than station records: use it to compare places with each other. ERA5 is a ~30 km reanalysis: it is good for comparing places, less precise for local extremes.',
    whyItMatters: 'The charts show when each place is at its best and worst: the Samui monsoon (October-December), the Normandy winter drizzle, the Russian deep freeze (December-February).',
    related: ['era5', 'climatology_baseline'],
    sources: [PSRC.omEra5],
  },
  place_seasonal: {
    title: 'Seasonal outlook per place (ECMWF SEAS5)',
    category: 'forecasts',
    aliases: ['seasonal outlook', 'SEAS5', 'next months'],
    short: 'Forecast monthly temperature and rain anomalies for the next 6 months, relative to the model\'s own normal.',
    body: 'An anomaly is the difference from normal: +1 °C means one degree warmer than usual for that month. Seasonal forecasts give tendencies, not daily weather; their skill is highest in the tropics and during strong El Nino years, lowest in mid-latitude winters.',
    related: ['seasonal_outlook', 'anomaly', 'place_enso'],
    sources: [PSRC.omSeasonal],
  },
  place_warnings: {
    title: 'Official weather warnings per place',
    category: 'hazards',
    aliases: ['warnings', 'vigilance', 'Meteoalarm', 'Roshydromet', 'TMD'],
    short: 'France: Meteo-France vigilance via Meteoalarm (yellow, orange, red). Russia: the Hydrometcenter daily bulletin of dangerous weather. Thailand: TMD bulletins.',
    body: `- **France (Calvados)**: Meteo-France publishes its vigilance to Meteoalarm (EUMETNET), read here without a key. An empty feed means no yellow, orange or red warning (green). The Meteo-France API itself needs a key, so it is not used.
- **Russia (Vladimir Oblast)**: the Hydrometcenter of Russia bulletin lists dangerous and adverse weather by federal district. The page shows the sentences that name the region (in Russian, as published). Keyword rule: named = Watch; named with wording such as "very heavy", "hurricane", "severe frost" = Prepare.
- **Thailand (Maenam)**: TMD bulletins for the Gulf side / Surat Thani, collected by the Koh Samui watch.

Always follow the national service when it issues a warning.`,
    thresholds: {
      columns: ['Warning', 'Factor level'],
      rows: [['green / none / region not named', '0 Normal'], ['yellow / region named', '1 Watch'], ['orange / severe wording / TMD heavy rain, waves, storm', '2 Prepare'], ['red', '3 Act']],
    },
    whyItMatters: 'Official warnings are the reference for immediate danger; this page only relays them.',
    related: ['tmd_warnings', 'place_levels'],
    sources: [PSRC.meteoalarm, PSRC.vigilance, PSRC.hydromet],
  },
  place_advisories: {
    title: 'Official travel advisories',
    category: 'data',
    aliases: ['travel advice', 'FCDO', 'State Department', 'France Diplomatie', 'sanctions'],
    short: 'What the UK FCDO, the US State Department and France Diplomatie currently say about each country, with the date of their last update and a link. Shown as published, not rated.',
    body: `These are the official, regularly updated government pages. The row quotes their headline (for example "Level 4: Do Not Travel" or "Advises against all travel to the whole country") and the date, and links to the full page. France Diplomatie text stays in French.

They cover security, politics, sanctions, health and entry rules, which the climate data cannot. Other decisive factors (cost of living, visas and residence, healthcare, banking, family) are not in this data: check them separately.`,
    whyItMatters: 'Advisories affect insurance, flights, banking and consular help. A "do not travel" advice usually voids travel insurance.',
    related: ['places_page', 'place_ranking'],
    sources: [PSRC.fcdo, PSRC.state, PSRC.diplo],
  },
  place_ranking: {
    title: 'Ranking and weights (decision aid)',
    category: 'data',
    aliases: ['ranking', 'weights', 'sliders', 'score'],
    short: 'Score = weighted average of (4 - exposure) over the dimensions that have data, shown as 0-100. You set the weights; by default all are equal. A decision aid only.',
    body: `How it is computed, with nothing hidden:

- For each place and dimension, suitability = 4 - exposure score (so 4 = best, 0 = worst).
- Score = sum(weight x suitability) / sum(weight x 4) x 100.
- Dimensions without data for a place are left out for that place and listed; compare coverage before trusting a close ranking.
- Weights go from 0 (ignore) to 5 (very important). They are saved in this browser only.

It leaves out everything that is not in this data: cost of living, visas, healthcare, language, family, politics. The official advisories are shown next to it for that reason.`,
    example: 'If cold matters three times more than heat to you, set Cold to 3 and Heat stress to 1: the ranking changes instantly.',
    whyItMatters: 'Different people weigh the same facts differently. The sliders make that explicit instead of hiding it in a single number.',
    related: ['place_exposure_scale', 'place_coverage', 'place_advisories'],
    sources: [PSRC.omEra5],
  },
  place_coverage: {
    title: 'Data coverage per place',
    category: 'data',
    aliases: ['coverage', 'missing data'],
    short: 'How many of the 10 ranked dimensions have data for a place. Long-term data (normals, projections, river levels) is computed once and filled over a few days.',
    body: 'Heavy one-time downloads (30 years of ERA5, CMIP6 projections, GloFAS history) are spread over several scheduler runs so they never exhaust the shared Open-Meteo quota that the Koh Samui watch also uses. Until then those cells say "no data yet". Coverage is shown in the matrix but not used in the ranking.',
    related: ['data_coverage', 'freshness', 'place_ranking'],
    sources: [PSRC.omEra5],
  },
  place_add: {
    title: 'Adding a place (search, server list, personal list)',
    category: 'data',
    aliases: ['add place', 'geocoding', 'personal list'],
    short: 'Search a town by name (GeoNames via Open-Meteo), check its region and country, then add it. On a public site, only the admin can add to the shared list; anyone can keep a personal list in their own browser.',
    body: `- **Shared list (server)**: the place is collected like the others (forecast, air, warnings, advisories within a minute; climate normals, projections and river levels over the next days).
- **Personal list (this browser)**: stored in localStorage only. It shows the current conditions and 7-day forecast, the El Nino sensitivity and the country advisories, not the long-term matrix.

Always check the region shown in the search results: many towns share a name (there are three Gorokhovets in Russia). The default places were checked against OpenStreetMap as well.`,
    related: ['places_page', 'place_map'],
    sources: [PSRC.omGeocode, PSRC.osm],
  },
  place_map: {
    title: 'Map of the places',
    category: 'data',
    aliases: ['places map'],
    short: 'The compared places on a world map, coloured by their current level. Personal-list places are drawn with a dashed outline.',
    body: 'Click a marker for its name, coordinates, elevation and current level. The home place (Maenam) is marked. Distances between places are great-circle distances.',
    related: ['place_add', 'place_levels'],
    sources: [PSRC.osm],
  },
} satisfies Record<string, TopicDef>

export type PlacesTopicId = keyof typeof PLACES_TOPICS
