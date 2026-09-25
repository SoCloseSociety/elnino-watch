import type { TopicDef } from '../types'

/** Shared source links (checked 2026-09-24). */
export const SRC = {
  cpcFaq: { title: 'NOAA CPC -- ENSO frequently asked questions', url: 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ensofaq.shtml' },
  cpcDisc: { title: 'NOAA CPC -- ENSO Diagnostic Discussion (monthly)', url: 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml' },
  cpcAlert: { title: 'NOAA CPC -- ENSO Alert System definitions', url: 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/enso-alert-readme.shtml' },
  cpcOni: { title: 'NOAA CPC -- Oceanic Nino Index table (ERSSTv6)', url: 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/' },
  cpcRoni: { title: 'NOAA CPC -- Relative Oceanic Nino Index (RONI)', url: 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/' },
  cpcRoniNews: { title: 'NOAA CPC -- CPC adopts RONI (announcement)', url: 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/announcement.php' },
  nwsRoni: { title: 'NWS Public Information Statement 26-05 (RONI official from 1 Feb 2026)', url: 'https://weather.gov/media/notification/pdf_2026/pns26-05_Relative_ONI.pdf' },
  cpcIndices: { title: 'NOAA CPC -- index data files', url: 'https://www.cpc.ncep.noaa.gov/data/indices/' },
  climNutshell: { title: 'NOAA Climate.gov -- What is ENSO, in a nutshell', url: 'https://www.climate.gov/news-features/blogs/enso/what-el-ni%C3%B1o%E2%80%93southern-oscillation-enso-nutshell' },
  climWalker: { title: "NOAA Climate.gov -- The Walker Circulation: ENSO's atmospheric buddy", url: 'https://www.climate.gov/news-features/blogs/enso/walker-circulation-ensos-atmospheric-buddy' },
  climKelvin: { title: 'NOAA Climate.gov -- Oceanic Kelvin waves', url: 'https://www.climate.gov/news-features/blogs/enso/oceanic-kelvin-waves-next-polar-vortex' },
  climFaq: { title: 'NOAA Climate.gov -- El Nino and La Nina: frequently asked questions', url: 'https://www.climate.gov/news-features/understanding-climate/el-ni%C3%B1o-and-la-ni%C3%B1a-frequently-asked-questions' },
  climSpring: { title: 'NOAA Climate.gov -- The spring predictability barrier', url: 'https://www.climate.gov/news-features/blogs/enso/spring-predictability-barrier-we%E2%80%99d-rather-be-spring-break' },
  tmdElNino: { title: 'Thai Meteorological Department -- El Nino phenomenon (in Thai)', url: 'https://www.tmd.go.th/info/%E0%B8%9B%E0%B8%A3%E0%B8%B2%E0%B8%81%E0%B8%8F%E0%B8%81%E0%B8%B2%E0%B8%A3%E0%B8%93%E0%B9%80%E0%B8%AD%E0%B8%A5%E0%B8%99%E0%B9%82%E0%B8%8D' },
  tmdCriteria: { title: 'Thai Meteorological Department -- weather criteria (rain amounts, hot weather, in Thai)', url: 'https://tmd.go.th/info/%E0%B9%80%E0%B8%81%E0%B8%93%E0%B8%91%E0%B8%AD%E0%B8%B2%E0%B8%81%E0%B8%B2%E0%B8%A8%E0%B8%A3%E0%B8%AD%E0%B8%99' },
  tmd: { title: 'Thai Meteorological Department (TMD)', url: 'https://www.tmd.go.th/en/' },
  iri: { title: 'IRI (Columbia University) -- ENSO forecast', url: 'https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/' },
  jma: { title: 'JMA Tokyo Climate Center -- El Nino monitoring and outlook', url: 'https://ds.data.jma.go.jp/tcc/tcc/products/elnino/index.html' },
  jmaDef: { title: 'JMA -- Monitoring and Prediction of El Nino (definition, PDF)', url: 'https://ds.data.jma.go.jp/gmd/tcc/tcc/library/library2012/Monitoring_and_Prediction_of_El_Nino.pdf' },
  wmo: { title: 'WMO -- El Nino/La Nina Updates', url: 'https://wmo.int/wmo-el-ninola-nina-updates' },
  bomSoi: { title: 'Australian Bureau of Meteorology -- About the SOI', url: 'https://www.bom.gov.au/climate/enso/soi/about-soi.html' },
  psl: { title: 'NOAA PSL -- Multivariate ENSO Index version 2 (MEI.v2)', url: 'https://psl.noaa.gov/enso/mei/' },
  ucarNino: { title: 'NCAR Climate Data Guide -- Nino SST indices', url: 'https://climatedataguide.ucar.edu/climate-data/nino-sst-indices-nino-12-3-34-4-oni-and-tni' },
  climateReanalyzer: { title: 'Climate Reanalyzer (University of Maine) -- daily SST', url: 'https://climatereanalyzer.org/clim/sst_daily/' },
  tao: { title: 'NOAA PMEL -- TAO/TRITON buoy array', url: 'https://www.pmel.noaa.gov/gtmba/pmel-theme/pacific-ocean-tao' },
  crwBaa: { title: 'NOAA Coral Reef Watch -- Bleaching Alert Area (alert levels)', url: 'https://coralreefwatch.noaa.gov/product/5km/index_5km_baa-max-7d.php' },
  crwDhw: { title: 'NOAA Coral Reef Watch -- Degree Heating Week', url: 'https://coralreefwatch.noaa.gov/product/5km/index_5km_dhw.php' },
  crwVs: { title: 'NOAA Coral Reef Watch -- Virtual Stations', url: 'https://coralreefwatch.noaa.gov/product/vs/' },
  gdacsTc: { title: 'GDACS -- tropical cyclone impact model and alert levels', url: 'https://www.gdacs.org/Knowledge/models_tc.aspx' },
  gdacs: { title: 'GDACS -- Global Disaster Alert and Coordination System', url: 'https://www.gdacs.org/' },
  eonet: { title: 'NASA EONET -- Earth Observatory Natural Event Tracker', url: 'https://eonet.gsfc.nasa.gov/' },
  firms: { title: 'NASA FIRMS -- Fire Information for Resource Management System', url: 'https://firms.modaps.eosdis.nasa.gov/' },
  asmcAlerts: { title: 'ASMC -- Alert levels for transboundary haze', url: 'https://asmc.asean.org/asmc-alerts/' },
  asmc: { title: 'ASEAN Specialised Meteorological Centre -- regional haze', url: 'https://asmc.asean.org/home/' },
  gibs: { title: 'NASA GIBS / Worldview -- satellite imagery', url: 'https://www.earthdata.nasa.gov/data/tools/worldview' },
  aod: { title: 'NASA Earthdata -- Aerosol optical depth', url: 'https://www.earthdata.nasa.gov/topics/atmosphere/aerosol-optical-depth-thickness' },
  aodEo: { title: 'NASA Earth Observatory -- Aerosol optical depth map guide', url: 'https://science.nasa.gov/earth/earth-observatory/global-maps/aerosol-optical-depth' },
  rainviewer: { title: 'RainViewer -- radar API', url: 'https://www.rainviewer.com/api.html' },
  nwsHeat: { title: 'US National Weather Service -- Heat index', url: 'https://www.weather.gov/ama/heatindex' },
  tmdHeat: { title: 'TMD R&D -- Heat index analysis (Thailand)', url: 'http://www.rnd.tmd.go.th/heatindexanalysis/' },
  air4thai: { title: 'Air4Thai -- Thai Pollution Control Department air quality', url: 'http://air4thai.pcd.go.th/webV3/' },
  thaiAqi: { title: 'Thailand.go.th -- Thailand adjusts AQI criteria for PM2.5 (2023)', url: 'https://thailand.go.th/issue-focus-detail/001_04_073' },
  omForecast: { title: 'Open-Meteo -- weather forecast API documentation', url: 'https://open-meteo.com/en/docs' },
  omEra5: { title: 'Open-Meteo -- historical weather API (ERA5)', url: 'https://open-meteo.com/en/docs/historical-weather-api' },
  omAir: { title: 'Open-Meteo -- air quality API (CAMS)', url: 'https://open-meteo.com/en/docs/air-quality-api' },
  omMarine: { title: 'Open-Meteo -- marine weather API', url: 'https://open-meteo.com/en/docs/marine-weather-api' },
  omSeasonal: { title: 'Open-Meteo -- seasonal forecast API (ECMWF SEAS5)', url: 'https://open-meteo.com/en/docs/seasonal-forecast-api' },
  samuiWater: { title: 'Bangkok Post, 29/07/2026 -- Koh Samui faces water rationing', url: 'https://www.bangkokpost.com/thailand/general/3293479/koh-samui-faces-water-rationing' },
  thaiwater: { title: 'ThaiWater (Hydro-Informatics Institute)', url: 'https://www.thaiwater.net/' },
  ddpm: { title: 'Thai DDPM -- Department of Disaster Prevention and Mitigation (hotline 1784)', url: 'https://www.disaster.go.th/' },
  whoWater: { title: 'WHO Technical Note 9 -- How much water is needed in emergencies', url: 'https://cdn.who.int/media/docs/default-source/wash-documents/who-tn-09-how-much-water-is-needed.pdf' },
  readyWater: { title: 'Ready.gov (FEMA) -- Water', url: 'https://www.ready.gov/water' },
  redcrossKit: { title: 'American Red Cross -- Survival kit supplies', url: 'https://www.redcross.org/get-help/how-to-prepare-for-emergencies/survival-kit-supplies.html' },
  whoDengue: { title: 'WHO fact sheet -- Dengue and severe dengue', url: 'https://www.who.int/news-room/fact-sheets/detail/dengue-and-severe-dengue' },
  readyKit: { title: 'Ready.gov (FEMA) -- Build a kit', url: 'https://www.ready.gov/kit' },
} as const

export const ENSO_TOPICS = {
  enso: {
    title: 'ENSO (El Nino-Southern Oscillation)',
    category: 'enso',
    aliases: ['El Nino Southern Oscillation', 'ENSO cycle'],
    short: 'A natural see-saw of ocean temperature and winds in the tropical Pacific. It has three phases: El Nino (warm), La Nina (cool) and neutral.',
    body: `ENSO is the name scientists use for one big climate pattern with two halves:

- **El Nino / La Nina**: the ocean half. The surface of the central and eastern tropical Pacific becomes warmer (El Nino) or cooler (La Nina) than normal.
- **Southern Oscillation**: the atmosphere half. Air pressure swings between the western Pacific (around Darwin, Australia) and the central Pacific (Tahiti). When the pressure changes, the winds change too.

The two halves push on each other. Warmer water weakens the winds; weaker winds let even more warm water spread east. That feedback is why an El Nino can grow for months and then last most of a year.

ENSO is natural. It existed long before modern climate change. Episodes typically come back every 3 to 5 years, but the gap has varied from 2 to 7 years in the record.`,
    howToRead: 'The phase is read from the sea surface temperature in the [[nino34|Nino 3.4 region]]: +0.5 °C or more above normal for several months = El Nino, -0.5 °C or less = La Nina, in between = neutral. The atmosphere must also respond (winds, pressure, rain) for an official declaration.',
    whyItMatters: 'ENSO is the single biggest reason why one year in Thailand is drier or wetter than the next. It does not decide tomorrow\'s weather on Koh Samui, but it tilts the odds for whole seasons.',
    related: ['el_nino', 'la_nina', 'neutral', 'walker_circulation', 'teleconnections', 'oni'],
    sources: [SRC.cpcFaq, SRC.climNutshell],
  },
  el_nino: {
    title: 'El Nino',
    category: 'enso',
    aliases: ['warm phase', 'El Niño'],
    short: 'The warm phase of ENSO: the central and eastern tropical Pacific is warmer than normal and the trade winds weaken. It shifts rain patterns around the world.',
    body: `During El Nino, the surface of the central and east-central equatorial Pacific (roughly from the date line to the coast of South America) warms up. The easterly trade winds weaken, or even reverse in the far west.

What typically happens:

- The pool of very warm water that normally sits near Indonesia spreads east.
- The big rain clouds follow the warm water east, towards the central Pacific.
- Over Indonesia, northern Australia and much of Southeast Asia, air sinks instead of rising, so it rains less.
- Air pressure rises at Darwin and falls at Tahiti, so the [[soi|SOI]] turns negative.

The name ("the boy" in Spanish, a reference to the Christ child) comes from Peruvian fishermen who noticed warm water off their coast around Christmas.`,
    howToRead: 'NOAA declares El Nino conditions when the one-month relative Nino 3.4 anomaly is +0.5 °C or more, the 3-month [[roni|RONI]] is expected to stay above +0.5 °C, and the atmosphere responds (weaker trade winds, more rain in the central Pacific).',
    whyItMatters: 'For Thailand, El Nino years usually bring less rain and higher temperatures, most clearly in the hot season and early rainy season. On Koh Samui that means a higher risk of a hard dry season (water, heat, haze). See [[el_nino_thailand]].',
    related: ['enso', 'la_nina', 'el_nino_thailand', 'strength_categories', 'enso_lifecycle', 'event_2026'],
    sources: [SRC.cpcFaq, SRC.cpcAlert, SRC.climNutshell],
  },
  la_nina: {
    title: 'La Nina',
    category: 'enso',
    aliases: ['cool phase', 'La Niña'],
    short: 'The cool phase of ENSO: the central and eastern tropical Pacific is cooler than normal and the trade winds are stronger. For Thailand it tends to mean more rain.',
    body: `La Nina is the opposite of El Nino. The central and eastern tropical Pacific is cooler than normal, the trade winds blow harder, and the warm water and rain clouds are pushed even further west, over Indonesia and Southeast Asia.

La Nina often follows a strong El Nino, but not always. It typically lasts 1 to 3 years, longer than a typical El Nino (9 to 12 months).`,
    howToRead: 'La Nina conditions: one-month relative Nino 3.4 anomaly of -0.5 °C or less, with the 3-month [[roni|RONI]] expected to stay below -0.5 °C, plus an atmospheric response.',
    whyItMatters: 'La Nina years tend to be wetter than normal in Thailand. Samui is now in an El Nino, so La Nina matters mostly as the possible next phase in 2027-2028.',
    related: ['enso', 'el_nino', 'neutral', 'enso_lifecycle'],
    sources: [SRC.cpcFaq, SRC.cpcAlert],
  },
  neutral: {
    title: 'ENSO-neutral',
    category: 'enso',
    aliases: ['neutral phase'],
    short: 'Neither El Nino nor La Nina: the Nino 3.4 temperature stays within 0.5 °C of normal. Other climate drivers then have more say.',
    body: `ENSO-neutral means the tropical Pacific is close to its normal state: the Nino 3.4 anomaly is between -0.5 °C and +0.5 °C.

Neutral does not mean "normal weather everywhere". It only means ENSO is not pushing strongly in either direction, so other drivers (the Indian Ocean, the Madden-Julian Oscillation, local weather systems) decide more of what happens.`,
    howToRead: 'On the charts, the shaded band between -0.5 and +0.5 is the neutral zone.',
    related: ['enso', 'el_nino', 'la_nina', 'oni'],
    sources: [SRC.cpcFaq],
  },
  teleconnections: {
    title: 'Teleconnections',
    category: 'enso',
    aliases: ['remote impacts', 'global impacts'],
    short: 'Links between ENSO in the Pacific and the weather far away. They shift the odds of dry or wet, hot or cool seasons; they are not guarantees.',
    body: `A teleconnection is a "connection at a distance". When the rain clouds of the tropical Pacific move, they change the air circulation over half of the planet. So a warm Pacific can mean a dry season in Indonesia and Thailand, extra rain in Peru, or a mild winter in Canada.

These links are about probability, not certainty. NOAA notes that the typical El Nino impacts may happen as often as 80 percent of the time in some places, or as rarely as 40 percent in others. A single storm or flood cannot be labelled "an El Nino event": El Nino changes the background odds.`,
    howToRead: 'On the map, the dry and wet "impact zones" show where El Nino usually tilts the odds. They are typical patterns, not forecasts for this year.',
    whyItMatters: 'Thailand sits in the region that El Nino usually dries out. That is why this app watches water and heat on Samui more closely during an El Nino.',
    related: ['el_nino_thailand', 'walker_circulation', 'el_nino'],
    sources: [SRC.climFaq, SRC.cpcFaq],
  },
  walker_circulation: {
    title: 'Walker circulation',
    category: 'enso',
    aliases: ['Walker cell'],
    short: 'A giant loop of air along the equator: air rises over the warm western Pacific, flows east high up, sinks over the cool eastern Pacific and returns west as the trade winds.',
    body: `Picture a conveyor belt of air over the Pacific:

- Over the very warm water near Indonesia (the [[warm_pool]]), air heats, rises and forms big rain clouds.
- High in the sky, that air flows east.
- Over the cooler eastern Pacific, the air sinks. Sinking air is dry, so skies are clear there.
- Near the surface, the air flows back west. That surface flow is the [[trade_winds|trade winds]].

During El Nino the warm pool moves east, and the rising branch moves with it. The loop weakens. Over Indonesia and nearby, air starts to sink instead of rise, which means fewer rain clouds.`,
    whyItMatters: 'Sinking air over Southeast Asia is the main physical reason El Nino tends to bring drier, sunnier and hotter weather to Thailand.',
    related: ['trade_winds', 'warm_pool', 'el_nino', 'soi', 'teleconnections'],
    sources: [SRC.climWalker, SRC.cpcFaq],
  },
  trade_winds: {
    title: 'Trade winds',
    category: 'enso',
    aliases: ['easterlies', 'easterly winds'],
    short: 'Steady winds that blow from east to west along the equator. They push warm surface water towards Asia. When they weaken, El Nino can grow.',
    body: `Near the equator, surface winds normally blow from the east (they are called "easterlies"). They drag the warm top layer of the ocean west, so the water piles up near Indonesia and the sea level there is higher.

When the trade winds weaken, the warm water sloshes back east. That is the start of El Nino. A burst of wind from the west (a [[westerly_wind_burst]]) can give it an extra push.`,
    related: ['walker_circulation', 'westerly_wind_burst', 'kelvin_wave', 'thermocline'],
    sources: [SRC.climWalker, SRC.climKelvin],
  },
  warm_pool: {
    title: 'Western Pacific warm pool',
    category: 'enso',
    aliases: ['warm pool', 'Indo-Pacific warm pool'],
    short: 'The large area of the warmest ocean water on Earth, normally around Indonesia and the western Pacific. The biggest rain clouds sit above it.',
    body: `The warm pool is a region of ocean, around Indonesia and the western Pacific, where the surface water is usually above about 28 °C. Warm water heats the air above it, the air rises, and huge rain clouds form. That is why Indonesia and the western Pacific are among the rainiest places on Earth.

In an El Nino, the warm pool stretches east, towards and past the date line. The rain clouds follow it.`,
    related: ['walker_circulation', 'thermocline', 'el_nino'],
    sources: [SRC.climWalker, SRC.cpcFaq],
  },
  thermocline: {
    title: 'Thermocline',
    category: 'enso',
    short: 'The boundary in the ocean between the warm surface layer and the cold deep water. Its depth controls how much cold water can reach the surface.',
    body: `The ocean is layered. On top sits a warm, well-mixed layer. Below it, the temperature drops quickly. That zone of fast cooling is the thermocline.

Along the equatorial Pacific, the thermocline is normally tilted:

- **Deep in the west** (around 150 m or more), because the trade winds pile warm water up there.
- **Shallow in the east**, near South America, so cold deep water easily comes up to the surface (this is called "upwelling").

During El Nino the tilt flattens: the thermocline gets deeper in the east (NOAA gives 150 to 175 m as typical during El Nino in the east-central Pacific). The cold water can no longer reach the surface, so the surface warms.`,
    howToRead: 'NOAA\'s subsurface charts show temperature anomalies along the equator from the surface down to about 300 m. Big warm anomalies near the thermocline (the CPC reported more than +10 °C at depth in September 2026) mean more warm water is on its way to the surface.',
    related: ['kelvin_wave', 'warm_pool', 'trade_winds', 'tao_buoys'],
    sources: [SRC.cpcFaq, SRC.climKelvin],
  },
  kelvin_wave: {
    title: 'Oceanic Kelvin wave',
    category: 'enso',
    aliases: ['downwelling Kelvin wave', 'upwelling Kelvin wave'],
    short: 'A slow, huge underwater wave that travels east along the equator in 2-3 months. A "downwelling" one carries warm water east and can start or boost an El Nino.',
    body: `When the trade winds weaken or a westerly wind burst blows, the thick warm layer in the western Pacific starts to slide east along the equator. It moves as a wave that you cannot see at the surface (the sea surface rises only a few centimetres) but that pushes the [[thermocline]] down by tens of metres.

- A **downwelling** Kelvin wave pushes the thermocline down. Cold water cannot come up, so the surface warms. It favours El Nino.
- An **upwelling** Kelvin wave does the opposite: the thermocline rises and the surface cools.

A Kelvin wave takes about 2 to 3 months to cross the Pacific. That delay is useful: forecasters see it coming.`,
    related: ['westerly_wind_burst', 'thermocline', 'tao_buoys', 'forecast_uncertainty'],
    sources: [SRC.climKelvin],
  },
  westerly_wind_burst: {
    title: 'Westerly wind burst (WWB)',
    category: 'enso',
    aliases: ['WWB'],
    short: 'A few days to weeks of winds blowing from the west over the western Pacific, against the usual trade winds. It can launch a warm Kelvin wave.',
    body: `Normally the equatorial winds blow from the east. Sometimes, for a few days to a few weeks, they blow from the west instead over the far western Pacific. That is a westerly wind burst. They are often linked to tropical storm activity or to the Madden-Julian Oscillation (a wave of cloud and rain that travels around the tropics every 30 to 60 days).

A strong burst pushes warm surface water east and triggers a downwelling [[kelvin_wave]]. Several bursts in a row during the build-up of an El Nino often make it stronger.`,
    related: ['kelvin_wave', 'trade_winds', 'el_nino'],
    sources: [SRC.climKelvin, SRC.cpcDisc],
  },
  el_nino_thailand: {
    title: 'Why El Nino affects Thailand',
    category: 'enso',
    aliases: ['El Nino and Thailand', 'impacts on Thailand', 'monsoon interaction'],
    short: 'El Nino moves the Pacific rain clouds east, so air sinks over Southeast Asia. In Thailand, El Nino years are usually drier and hotter than normal, most clearly in the hot season and early rainy season.',
    body: `The Thai Meteorological Department (TMD) studied rain and temperature in El Nino years over 50 years (1951-2000). Its findings, in short:

- Rain in most of Thailand is usually **below normal** in El Nino years, **especially in the hot season and the early rainy season**.
- Moderate to strong El Nino events cut rain more.
- Temperatures are **above normal in every season** of an El Nino year, again most clearly in the hot season and early rainy season, and more so in stronger events.
- In the **middle and late rainy season**, the effect is **unclear**: rain can end up above or below normal.

Why: the rising air and rain clouds move east, towards the central Pacific (see [[walker_circulation]]). Over Southeast Asia, air tends to sink, which suppresses rain clouds.

How this meets the monsoons: Thailand's rain comes mostly from two monsoons. El Nino does not switch them off. It shifts the odds towards a weaker or shorter rainy period and a longer, hotter dry season. Koh Samui, on the Gulf side, gets its main rain from the northeast monsoon (October to January), not from the southwest monsoon. See [[samui_seasons]].`,
    whyItMatters: `For Samui the worry is the chain: less rain -> reservoirs not full -> a long dry season (February to April 2027) with more heat -> water shortage. This is exactly what happened in 2026: the PWA started rotating water supply on Samui from 3 August 2026 after a long dry spell (see [[samui_water_supply]]).

El Nino does NOT prevent floods. The northeast monsoon can still bring heavy rain and floods in November-December, even in an El Nino year.`,
    related: ['samui_seasons', 'samui_water_supply', 'walker_circulation', 'teleconnections', 'factor_enso'],
    sources: [SRC.tmdElNino, SRC.cpcFaq, SRC.climFaq],
  },
  strength_categories: {
    title: 'Weak, moderate, strong and "super" El Nino',
    category: 'enso',
    aliases: ['super El Nino', 'very strong El Nino', 'strong El Nino', 'strength'],
    short: 'El Nino strength is usually graded by the peak 3-month Nino 3.4 anomaly: about +0.5 weak, +1.0 moderate, +1.5 strong, +2.0 and above very strong ("super" is an informal media word).',
    body: `Scientists grade an event by how warm the [[nino34|Nino 3.4]] region gets, averaged over three months ([[oni|ONI]] or, since February 2026, [[roni|RONI]]).

"Super El Nino" is not an official NOAA category. Media use it for the very strongest events, roughly +2.0 °C and above (1982-83, 1997-98, 2015-16).

A stronger El Nino makes the usual impacts more likely, but never certain. The CPC wrote in September 2026 that with an event this strong "the chances of experiencing impacts consistent with El Nino are larger, though not guaranteed".`,
    thresholds: {
      columns: ['3-month index', 'Common label', 'This app (ENSO factor)'],
      rows: [
        ['below +0.5 °C', 'neutral', '0 Normal'],
        ['+0.5 to +0.9 °C', 'weak', '1 Watch'],
        ['+1.0 to +1.4 °C', 'moderate', '1 Watch'],
        ['+1.5 to +1.9 °C', 'strong', '2 Prepare'],
        ['+2.0 °C and above', 'very strong ("super" in the media)', '2 Prepare (the ENSO factor never goes above 2)'],
      ],
      note: 'The weak/moderate/strong/very strong bands are the conventional ones used with NOAA ONI tables. The app\'s ENSO factor uses ONI (and the weekly Nino 3.4 value) with these bands.',
    },
    related: ['oni', 'roni', 'past_events', 'factor_enso', 'event_2026'],
    sources: [SRC.cpcOni, SRC.cpcDisc],
  },
  enso_lifecycle: {
    title: 'Typical El Nino lifecycle',
    category: 'enso',
    aliases: ['lifecycle', 'peak', 'decay', 'when does El Nino peak'],
    short: 'An El Nino usually starts in March-June, peaks in the northern late autumn and winter (about November to February) and fades in the following spring (May-July).',
    body: `NOAA's description of a typical event:

- **Develops** during March to June.
- **Peaks** during the northern late autumn and winter. The CPC says December to April; NOAA Climate.gov says November to February. The warm anomaly is usually largest around November-January.
- **Weakens** during May to July of the following year.
- Lasts typically **9 to 12 months**. Some events have lasted 2 years, or even 3 to 4.

Why the winter peak: the equatorial Pacific is at its warmest then, so a small extra warming moves the tropical rain a lot, which in turn feeds back on the winds.

The effects on land often lag the ocean peak. For Thailand, the dry season right after the peak (February to April) is when El Nino drought and heat usually hurt most.`,
    whyItMatters: 'The 2026 El Nino is expected to peak around late 2026. The dry, hot season that follows (February-April 2027) is the danger window for Samui\'s water.',
    related: ['el_nino', 'forecast_uncertainty', 'samui_seasons', 'event_2026'],
    sources: [SRC.cpcFaq, SRC.climFaq],
  },
  past_events: {
    title: 'Past strong El Nino events',
    category: 'enso',
    aliases: ['1982-83', '1997-98', '2015-16', '2023-24', 'history', 'major El Ninos'],
    short: 'The three strongest El Ninos since 1950 by ONI peaked at about +2.1 °C (1982-83), +2.4 °C (1997-98) and +2.6 °C (2015-16). 2023-24 peaked at about +2.0 °C.',
    body: `The Overview page compares the current event with these past events. Values below are the peak 3-month ONI and RONI from the NOAA CPC data files (downloaded 2026-09-24). ONI and RONI differ because RONI removes the warming of the whole tropics (see [[roni]]).

Notes:

- **1982-83**: one of the strongest on record; it was not predicted in advance.
- **1997-98**: one of the strongest; TMD notes it developed fast and brought drought to Thailand and fires in Indonesia and Malaysia (haze).
- **2015-16**: the highest ONI peak in the record; severe drought in Thailand and haze across the region.
- **2023-24**: strong by ONI (about +2.0) but only moderate by RONI (+1.4), because the whole tropical ocean was unusually warm at the time. This is exactly why NOAA moved to RONI.`,
    thresholds: {
      columns: ['Event', 'Peak ONI (season)', 'Peak RONI (season)'],
      rows: [
        ['1982-83', '+2.14 (DJF 1983)', '+2.40 (DJF 1983)'],
        ['1997-98', '+2.37 (NDJ 1997)', '+2.28 (NDJ 1997)'],
        ['2015-16', '+2.59 (NDJ 2015)', '+2.25 (NDJ 2015)'],
        ['2023-24', '+1.99 (NDJ 2023)', '+1.42 (OND 2023)'],
      ],
      note: 'Source: cpc.ncep.noaa.gov/data/indices/oni.ascii.txt and RONI.ascii.txt. Recent values can be revised for up to two months.',
    },
    related: ['oni', 'roni', 'strength_categories', 'event_2026', 'asmc_haze'],
    sources: [SRC.cpcOni, SRC.cpcRoni, SRC.tmdElNino],
  },
  event_2026: {
    title: 'The 2026 El Nino',
    category: 'enso',
    aliases: ['current event', '2026-27'],
    short: 'NOAA has an El Nino Advisory in force. In September 2026 it gave a greater than 90% chance of a very strong event in late 2026 and early 2027.',
    body: `What NOAA's Climate Prediction Center said in its 10 September 2026 discussion:

- ENSO Alert System status: **El Nino Advisory**.
- El Nino strengthened in August, with surface anomalies above +3.0 °C in the eastern equatorial Pacific. Nino 3.4 reached +1.8 °C, Nino 3 +2.5 °C and Nino 1+2 +3.4 °C (Nino 4 only +0.1 °C).
- Subsurface anomalies exceeded +10 °C at depth; the thermocline is deeper than average.
- Rain is enhanced from the central to the eastern Pacific and suppressed over Indonesia.
- For October-December 2026, a **75% chance** of a historic event, stronger than any since 1950 (3-month RONI of +2.5 °C or more).
- Overall: **more than 90% chance of a very strong event** during the northern fall and winter 2026-27.

The 3-month values published by the CPC for June-August 2026: ONI +1.80 °C, RONI +1.36 °C. The app shows the newest values on the Overview and Indices pages.`,
    whyItMatters: 'A very strong El Nino peaking around the end of 2026 raises the odds of a drier, hotter February-April 2027 on Samui, on top of a water system that was already rationed in August 2026.',
    related: ['cpc_alert_system', 'roni', 'oni', 'enso_lifecycle', 'samui_water_supply'],
    sources: [SRC.cpcDisc, SRC.cpcRoni, SRC.cpcIndices],
  },
} satisfies Record<string, TopicDef>
