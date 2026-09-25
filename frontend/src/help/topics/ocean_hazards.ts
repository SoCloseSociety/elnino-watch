import type { TopicDef } from '../types'
import { SRC } from './enso'

export const OCEAN_TOPICS = {
  tao_buoys: {
    title: 'TAO/TRITON buoys',
    category: 'ocean',
    aliases: ['TAO', 'TRITON', 'moored buoys', 'buoy array'],
    short: 'About 50 moored buoys along the equatorial Pacific that measure sea temperature (surface and deep), air temperature and wind in real time.',
    body: `The Tropical Atmosphere Ocean (TAO/TRITON) array is a line of buoys anchored across the equatorial Pacific, run by NOAA and Japan's JAMSTEC. They measure the temperature from the surface down to about 500 m, plus winds and air temperature.

They were built after the 1982-83 El Nino, which was not detected in time. They show [[kelvin_wave|Kelvin waves]] and [[westerly_wind_burst|wind bursts]] as they happen.

The app shows the surface temperature from buoys with a recent reading, on the Map (green dots) and the Indices page.`,
    howToRead: 'Warmer readings in the east than usual = El Nino-like. Buoys go offline for maintenance or damage: a missing buoy is not a signal.',
    related: ['thermocline', 'kelvin_wave', 'sst'],
    sources: [SRC.tao],
  },
  coral_reef_watch: {
    title: 'NOAA Coral Reef Watch',
    category: 'ocean',
    aliases: ['CRW', 'bleaching', 'virtual stations'],
    short: 'NOAA\'s satellite monitoring of heat stress on coral reefs. The app follows the Gulf of Thailand stations (Samui is in the western Gulf station).',
    body: `Coral Reef Watch uses daily 5 km satellite sea temperatures to estimate how much heat stress reefs are under. For each "virtual station" it gives the SST, the anomaly, the [[dhw|Degree Heating Weeks]] and a bleaching alert level.

Coral bleaching: when water stays too warm for too long, corals expel the tiny algae living in them and turn white. They can recover if the heat ends soon; long or intense stress kills them.

The product is daily and one day behind.`,
    related: ['dhw', 'marine_heatwave', 'factor_marine_heat'],
    sources: [SRC.crwVs, SRC.crwDhw],
  },
  dhw: {
    title: 'Degree Heating Weeks (DHW)',
    category: 'ocean',
    aliases: ['DHW', 'bleaching alert', 'Alert Level', 'HotSpot', 'bleaching alert area'],
    short: 'Accumulated heat stress on corals over the last 12 weeks, in °C-weeks. 4 = risk of reef-wide bleaching; 8 = bleaching with deaths of heat-sensitive corals likely.',
    body: `Corals are stressed when the water is more than 1 °C above the warmest monthly average they normally see. NOAA calls that excess a **HotSpot**.

DHW adds up the HotSpots over the last 12 weeks. Example: 2 weeks at +2 °C above the threshold = 4 °C-weeks. So DHW grows with both how hot and how long.

NOAA's alert levels (Bleaching Alert Area, updated with Levels 3-5 in December 2023) are in the table.`,
    thresholds: {
      columns: ['NOAA level', 'Definition', 'Potential impact'],
      rows: [
        ['No Stress', 'HotSpot <= 0', 'No bleaching'],
        ['Bleaching Watch', '0 < HotSpot < 1', 'Bleaching unlikely'],
        ['Bleaching Warning', 'HotSpot >= 1 and 0 < DHW < 4', 'Risk of possible bleaching'],
        ['Alert Level 1', 'HotSpot >= 1 and 4 <= DHW < 8', 'Risk of reef-wide bleaching'],
        ['Alert Level 2', 'HotSpot >= 1 and 8 <= DHW < 12', 'Reef-wide bleaching with mortality of heat-sensitive corals'],
        ['Alert Level 3', 'HotSpot >= 1 and 12 <= DHW < 16', 'Risk of multi-species mortality'],
        ['Alert Level 4', 'HotSpot >= 1 and 16 <= DHW < 20', 'Severe multi-species mortality (> 50% of corals)'],
        ['Alert Level 5', 'HotSpot >= 1 and DHW >= 20', 'Near complete mortality (> 80% of corals)'],
      ],
      note: 'HotSpot and DHW in °C and °C-weeks. In this app, DHW >= 4 gives the marine heat factor level 1 (the factor is capped at 1 in the overall level).',
    },
    whyItMatters: 'Bleaching hurts Samui\'s diving, snorkelling, fishing and tourism. It is not a direct safety threat, so it only counts as context in the risk level.',
    related: ['coral_reef_watch', 'marine_heatwave', 'factor_marine_heat'],
    sources: [SRC.crwBaa, SRC.crwDhw],
  },
  marine_heatwave: {
    title: 'Marine heatwave',
    category: 'ocean',
    aliases: ['ocean heatwave', 'warm sea'],
    short: 'A period of days to months when the sea is unusually warm for the season. El Nino years often bring marine heatwaves to Southeast Asian seas.',
    body: `A marine heatwave is like a heatwave on land, but in the ocean: the sea surface stays much warmer than usual for the season for days to months.

Around Samui, a marine heatwave means coral bleaching risk, stressed fisheries, and warmer, more humid nights on land. Coral Reef Watch's [[dhw|DHW]] is the best single measure of its effect on reefs.`,
    howToRead: 'On the Map, the SST anomaly layer shows it as orange/red around the Gulf of Thailand.',
    related: ['dhw', 'coral_reef_watch', 'layer_sst_anomaly', 'world_sst'],
    sources: [SRC.crwDhw],
  },
  wave_height: {
    title: 'Wave height and ferries',
    category: 'ocean',
    aliases: ['significant wave height', 'sea state', 'rough sea', 'ferry cancellation'],
    short: 'The forecast height of waves off Samui, in metres. Around 2 m, small boats are told to stay ashore and fast ferries start to be cancelled; at 3 m car ferries are likely suspended.',
    body: `Wave forecasts give the **significant wave height**: roughly the average height of the highest third of the waves. Individual waves are often higher than this average, so expect some bigger waves.

The app uses the Open-Meteo marine forecast for open water near Samui, plus TMD wind-wave warnings for the Gulf of Thailand. Only Gulf warnings count: Andaman Sea warnings do not concern Samui.

Why it matters: Samui is an island. The car ferries (Seatran, Raja) and passenger boats (Lomprayah) are how most food, fuel and people arrive. In rough seas the crossings are cut back or cancelled, and the high-speed catamarans are the first to stop.`,
    thresholds: {
      columns: ['Max wave height (72 h)', 'Sea state factor', 'Exit plan (ferry)'],
      rows: [
        ['below 1.5 m', '0 Normal', 'ok'],
        ['1.5 to 2 m', '1 Watch', 'ok'],
        ['2 to 3 m', '2 Prepare (small boats stay in port)', 'caution'],
        ['3 m or more', '3 Act', 'blocked'],
      ],
      note: 'A TMD Gulf rough-sea warning in force raises the sea state factor to at least 1. For departure windows, a TMD bulletin saying small boats should stay ashore counts as blocked.',
    },
    whyItMatters: 'When the ferries stop, the island is cut off: supplies, fuel and evacuation depend on the sea. Only the airport remains, with limited seats. Shop and refuel before the seas rise.',
    related: ['factor_sea_state', 'departure_windows', 'exit_plan', 'samui_seasons'],
    sources: [SRC.omMarine, SRC.tmd],
  },
} satisfies Record<string, TopicDef>

export const HAZARD_TOPICS = {
  gdacs: {
    title: 'GDACS alerts (green, orange, red)',
    category: 'hazards',
    aliases: ['Global Disaster Alert and Coordination System', 'disaster alerts'],
    short: 'A UN / European Commission system that rates each new disaster by its likely humanitarian impact: green (low), orange (medium), red (high, international help likely needed).',
    body: `GDACS (Global Disaster Alert and Coordination System) is run by the European Commission's Joint Research Centre with the UN. It automatically detects cyclones, floods, droughts, earthquakes, volcanoes and wildfires, and estimates their impact.

The colour is about **impact on people**, not only about the strength of the hazard. It combines hazard severity, how many people are exposed, and how vulnerable the country is. For tropical cyclones, for example:

- **Green**: for example a tropical storm affecting fewer than 10 million people, or storm surge up to 1 m.
- **Orange**: for example a Category 1-2 cyclone affecting 100,000+ people in medium-to-high vulnerability areas, or surge of 1-3 m.
- **Red**: for example a Category 3 cyclone affecting 100,000+ people in medium-to-high vulnerability areas, or surge of 3 m or more.

A strong storm over an empty ocean can be green. The alert is automatic and can change as the storm moves.`,
    howToRead: 'Coloured symbols on the Map. Click one for the GDACS report link. Distance to Samui matters as much as the colour.',
    whyItMatters: 'The cyclone part of the Samui risk level uses GDACS: an orange or red tropical cyclone within 300 km of Samui is the only single hazard that sets the level to 4 Leave (rule R4a).',
    related: ['factor_cyclone_wind', 'tropical_cyclone', 'eonet', 'risk_rules'],
    sources: [SRC.gdacsTc, SRC.gdacs],
  },
  eonet: {
    title: 'NASA EONET natural events',
    category: 'hazards',
    aliases: ['EONET', 'Earth Observatory Natural Event Tracker'],
    short: 'NASA\'s list of ongoing natural events (storms with their tracks, wildfires, volcanoes, floods, ice) linked to satellite imagery. No impact rating.',
    body: `EONET (Earth Observatory Natural Event Tracker) is a curated NASA catalogue of natural events that are happening now, each with its location and links to images and sources. Storms come with their track.

Unlike GDACS, EONET does not rate impact. It answers "what is happening where", not "how bad is it for people".`,
    related: ['gdacs', 'firms_fires'],
    sources: [SRC.eonet],
  },
  tropical_cyclone: {
    title: 'Tropical cyclones near Samui',
    category: 'hazards',
    aliases: ['typhoon', 'tropical storm', 'cyclone', 'depression'],
    short: 'Rotating storms that form over warm tropical seas. Rare on Samui but destructive; they mostly reach the Gulf of Thailand from October to January.',
    body: `"Tropical cyclone" covers tropical depressions, tropical storms and typhoons (the name used in the western Pacific). They bring strong winds, very heavy rain, big waves and storm surge.

Samui is hit rarely, but the risk-engine notes past examples: tropical storm Harriet (1962), typhoon Gay (1989) and storm Pabuk (January 2019). They mostly arrive from October to January, through the Gulf of Thailand.

Follow the TMD for official warnings and the DDPM (hotline 1784) for evacuation orders.`,
    related: ['factor_cyclone_wind', 'gdacs', 'layer_himawari_ir', 'tmd_warnings'],
    sources: [SRC.tmd, SRC.gdacs],
  },
  tmd_warnings: {
    title: 'TMD weather warnings',
    category: 'hazards',
    aliases: ['TMD', 'Thai Meteorological Department', 'warning bulletin'],
    short: 'Numbered warning bulletins from the Thai Meteorological Department about heavy rain, strong wind-waves and storms. They are the official source for Thailand.',
    body: `The TMD issues numbered bulletins (for example "No. 12") when heavy rain, strong wind-waves or a storm threaten parts of Thailand. Each has an issue time and an end date, and often names the provinces and whether small boats should stay ashore.

The app reads them and checks which ones concern the Gulf side of the South / Surat Thani. They feed the flood, sea state and cyclone factors and the departure windows.

Official orders come from Thai authorities, not from this app. TMD hotline: 1182.`,
    related: ['factor_flood', 'factor_sea_state', 'rain_classes', 'limitations'],
    sources: [SRC.tmd],
  },
  rain_classes: {
    title: 'TMD rain amount classes',
    category: 'hazards',
    aliases: ['heavy rain', 'very heavy rain', 'rain criteria', 'mm per day'],
    short: 'The Thai Meteorological Department grades 24-hour rain as light (0.1-10 mm), moderate (10.1-35), heavy (35.1-90) and very heavy (more than 90 mm).',
    body: `1 mm of rain = 1 litre of water per square metre. The TMD classes (rain over 24 hours, 07:00 to 07:00) are in the table.

For scale: a very heavy day can bring more rain than Samui normally gets in the whole month of February (about 39 mm in the ERA5 1991-2020 normal).`,
    thresholds: {
      columns: ['Class (TMD)', 'Rain in 24 h'],
      rows: [
        ['Light rain', '0.1 to 10.0 mm'],
        ['Moderate rain', '10.1 to 35.0 mm'],
        ['Heavy rain', '35.1 to 90.0 mm'],
        ['Very heavy rain', '90.1 mm or more'],
      ],
    },
    related: ['factor_flood', 'tmd_warnings'],
    sources: [SRC.tmdCriteria],
  },
  firms_fires: {
    title: 'Fire detections (NASA FIRMS)',
    category: 'hazards',
    aliases: ['FIRMS', 'active fires', 'VIIRS fires', 'thermal anomalies'],
    short: 'Hot spots detected by satellites in the last 24 hours, mostly vegetation fires and burning. Many fires in Sumatra, Borneo or mainland Southeast Asia can mean haze.',
    body: `NASA FIRMS lists places where satellite sensors (VIIRS and MODIS) saw something much hotter than its surroundings during an overpass. Most are fires: forest and peat fires, crop burning.

Limits: a satellite only sees a place a few times a day; clouds and smoke hide fires; small fires can be missed; some hot spots are industrial sites. One dot is not one fire.`,
    howToRead: 'Clusters of dots matter more than single ones. Fires far away only affect Samui if the winds carry the smoke towards the Gulf of Thailand.',
    whyItMatters: 'In El Nino years, peat and forest fires in Indonesia and Malaysia can send haze across the region (2015, 2019). Crop burning on the mainland peaks in the dry season.',
    related: ['hotspots', 'asmc_haze', 'layer_aerosol', 'factor_air'],
    sources: [SRC.firms],
  },
  hotspots: {
    title: 'Hotspot counts (ASMC)',
    category: 'hazards',
    aliases: ['hotspot', 'ASMC hotspots'],
    short: 'The daily number of fire hotspots per country or region counted by the ASEAN haze centre. A sudden rise, with dry weather, is an early haze warning.',
    body: `The ASEAN Specialised Meteorological Centre (ASMC) counts satellite fire hotspots (VIIRS, daytime, high confidence) per region every day. The app charts the last 14 days.

Hotspot counts depend on clouds (fewer seen on cloudy days), so look at the trend over several days, not one day.`,
    related: ['asmc_haze', 'firms_fires', 'factor_air'],
    sources: [SRC.asmc],
  },
  asmc_haze: {
    title: 'ASMC haze alert levels (0-3)',
    category: 'hazards',
    aliases: ['haze', 'transboundary haze', 'ASMC'],
    short: 'The ASEAN haze centre\'s alert level for smoke that crosses borders, for the Mekong sub-region (including Thailand) and southern ASEAN: 0 none, 1 dry season, 2 increasing risk, 3 high risk.',
    body: `"Transboundary haze" is smoke from fires that drifts from one country to another. The ASMC issues alert levels for two sub-regions:

- **Mekong sub-region**: Myanmar, Thailand, Cambodia, Lao PDR, Vietnam.
- **Southern ASEAN**: mainly Sumatra and Kalimantan (Indonesia), which also affects Malaysia, Singapore and southern Thailand.

It weighs forecast rain and winds, smoke haze density, and hotspot counts and locations.`,
    thresholds: {
      columns: ['ASMC level', 'Meaning'],
      rows: [
        ['0', 'No transboundary smoke haze / stand down'],
        ['1', 'Dry season'],
        ['2', 'Increasing risk of transboundary haze (more hotspots, moderate to dense smoke for several days, persistent dry weather, winds towards neighbours)'],
        ['3', 'High risk of severe transboundary haze (significant persistent hotspots, widespread moderate to dense smoke for several days)'],
      ],
    },
    whyItMatters: 'Samui usually has clean air, but in strong El Nino years haze from Indonesia and Malaysia has reached southern Thailand. A southern ASEAN level 2-3 is a reason to check the air quality factor.',
    related: ['factor_air', 'pm25', 'firms_fires', 'hotspots'],
    sources: [SRC.asmcAlerts],
  },
} satisfies Record<string, TopicDef>

export const LAYER_TOPICS = {
  map_overlays: {
    title: 'Map basics (boxes, zones, home circle)',
    category: 'layers',
    aliases: ['map', 'impact zones', 'home radius', 'vector data'],
    short: 'The map combines vector data (Nino boxes, typical El Nino impact zones, the 800 km circle around Samui, events, buoys, news) with one optional satellite layer.',
    body: `What you see on the Map page:

- **Nino boxes** (red outlines): the [[nino_regions|Nino regions]]. Nino 3.4 is highlighted.
- **Impact zones** (orange = usually drier, blue = usually wetter during El Nino): typical patterns, not this year's forecast (see [[teleconnections]]).
- **Home circle** (blue dashed): 800 km around Koh Samui. Events inside it are counted as "near".
- **Events**: GDACS and EONET hazards, FIRMS fires. Clusters show a number; zoom in to split them.
- **Buoys** (green dots): [[tao_buoys|TAO buoys]] with a recent reading.
- **One satellite layer** at a time, with a date slider and an opacity control.

Satellite layers show the latest day the provider actually has. Some products are one or more days behind (soil moisture often 2-3 days).`,
    related: ['nino_regions', 'teleconnections', 'gdacs', 'layer_sst_anomaly'],
    sources: [SRC.gibs],
  },
  layer_sst_anomaly: {
    title: 'Layer: sea surface temperature anomaly',
    category: 'layers',
    aliases: ['SST anomaly map', 'MUR SST anomaly'],
    short: 'Daily map of how much warmer or cooler the sea is than normal (JPL MUR, about 1 km). The red tongue along the equatorial Pacific is El Nino.',
    body: `This layer is the GHRSST Level 4 MUR sea surface temperature anomaly from NASA JPL, shown through NASA GIBS. It blends many satellites into a daily, gap-free map.`,
    howToRead: `- **Red / orange**: warmer than normal. Deep red = several °C above.
- **Blue**: cooler than normal.
- **White / pale**: near normal.

Use the legend image for exact values. Look for: the warm tongue along the equator in the eastern Pacific (El Nino); warm patches in the Gulf of Thailand (marine heatwave, coral stress).`,
    related: ['sst_anomaly', 'layer_sst', 'marine_heatwave'],
    sources: [SRC.gibs],
  },
  layer_sst: {
    title: 'Layer: sea surface temperature',
    category: 'layers',
    aliases: ['SST map'],
    short: 'Daily map of the actual sea surface temperature (JPL MUR, about 1 km), in °C.',
    body: `The raw sea surface temperature, not the anomaly. The tropics are always warm, so this map shows where the water is hot, not where it is unusual. Use the anomaly layer to see El Nino.`,
    howToRead: 'Colour scale from purple/blue (cold) to red/white (hot). Around Samui, water above about 30 °C for weeks stresses corals.',
    related: ['sst', 'layer_sst_anomaly', 'dhw'],
    sources: [SRC.gibs],
  },
  layer_imerg: {
    title: 'Layer: rain (GPM IMERG)',
    category: 'layers',
    aliases: ['IMERG', 'GPM', 'satellite rain', 'precipitation rate'],
    short: 'Satellite estimate of rain intensity (NASA GPM IMERG). Shows where it is raining hard, even over the ocean where there are no rain gauges.',
    body: `IMERG merges microwave and infrared data from a constellation of satellites, calibrated with rain gauges, into a global rain map. It is an estimate: it can miss short, small showers and can be off over mountains and small islands.`,
    howToRead: 'Colours show rain rate (see the legend): light colours = light rain, bright/dark colours = heavy rain. Empty = no rain detected.',
    whyItMatters: 'During El Nino, heavy rain shifts to the central Pacific and Southeast Asia gets less. In the northeast monsoon, look for rain bands over the southern Gulf of Thailand.',
    related: ['layer_radar', 'model_vs_observation', 'factor_flood'],
    sources: [SRC.gibs],
  },
  layer_himawari_ir: {
    title: 'Layer: infrared clouds (Himawari)',
    category: 'layers',
    aliases: ['Himawari', 'infrared', 'IR satellite', 'band 13'],
    short: 'The latest infrared image from Japan\'s Himawari satellite (updated about every 10 minutes). Bright, cold cloud tops = tall storm clouds; day and night.',
    body: `Himawari is a geostationary satellite: it stays above the same point over the equator and photographs Asia and the western Pacific every 10 minutes. The infrared channel (band 13) measures the temperature of whatever it sees: the ground, the sea, or cloud tops.

High clouds are very cold, so they stand out. Tall thunderstorms and cyclones have the coldest tops.`,
    howToRead: 'The coldest (highest) cloud tops appear brightest or in the strongest colours of the legend; warm ground and sea appear dark. A tight, round mass of cold cloud with spiral bands is a tropical cyclone.',
    related: ['tropical_cyclone', 'layer_radar', 'layer_truecolor'],
    sources: [SRC.gibs],
  },
  layer_truecolor: {
    title: 'Layer: true-colour image (VIIRS, MODIS)',
    category: 'layers',
    aliases: ['true colour', 'true color', 'VIIRS', 'MODIS', 'visible'],
    short: 'A daily "photo" from space as the eye would see it (Suomi NPP VIIRS or Terra MODIS). Shows clouds, smoke plumes and haze.',
    body: `These satellites orbit over the poles and image each place about once a day, in strips (swaths). Where strips meet, you can see seams or gaps. MODIS Terra passes in the morning; VIIRS in the early afternoon.

Brown-grey smudges over land or sea are often smoke or haze; bright white is cloud.`,
    howToRead: 'White = clouds. Grey/brown veil = smoke or haze. Blue-green swirls in water = sediment or plankton. Black stripes = no data for that day.',
    related: ['layer_aerosol', 'firms_fires', 'asmc_haze'],
    sources: [SRC.gibs],
  },
  layer_aerosol: {
    title: 'Layer: aerosols / smoke (optical depth)',
    category: 'layers',
    aliases: ['AOD', 'aerosol optical depth', 'MAIAC'],
    short: 'How much sunlight is blocked by particles (smoke, dust, pollution) in the whole air column. Below 0.1 = clear; about 1 = very hazy; above 2-3 = very high concentrations.',
    body: `Aerosol optical depth (AOD) is a number without units that measures how much the particles in the air dim the sunlight. NASA's guide: less than 0.1 is a crystal clear sky; a value of 1 means very hazy; above 2 or 3 means very high concentrations.

AOD is for the whole column of air, from the ground to the top of the atmosphere. A thick smoke layer high up can give a high AOD while the air you breathe is fine, and the reverse. For what you breathe, use PM2.5 (see [[pm25]]).`,
    howToRead: 'Yellow/orange/red-brown patches (see legend) = more particles. Look for plumes spreading from fire areas in Sumatra and Borneo towards the Malay Peninsula.',
    related: ['pm25', 'asmc_haze', 'firms_fires', 'layer_truecolor'],
    sources: [SRC.aodEo, SRC.aod],
  },
  layer_chlorophyll: {
    title: 'Layer: chlorophyll (PACE)',
    category: 'layers',
    aliases: ['chlorophyll-a', 'plankton', 'ocean colour', 'PACE'],
    short: 'Satellite estimate of chlorophyll in the sea surface, a sign of plankton. El Nino cuts the cold, nutrient-rich upwelling off Peru, so chlorophyll drops there.',
    body: `Phytoplankton are microscopic plants that colour the water green. More chlorophyll = more plankton = more food for fish.

Off Peru, cold deep water normally rises to the surface and fertilises the sea. During El Nino the [[thermocline]] deepens, that upwelling weakens, and the plankton (and the fishery) collapses.`,
    howToRead: 'Blue/purple = low chlorophyll (clear, poor water); green/yellow/red = high chlorophyll. Clouds leave gaps.',
    related: ['thermocline', 'el_nino'],
    sources: [SRC.gibs],
  },
  layer_soil_moisture: {
    title: 'Layer: soil moisture (SMAP)',
    category: 'layers',
    aliases: ['SMAP', 'root zone', 'drought map'],
    short: 'How much water is in the soil down to about 1 m (the root zone), from NASA\'s SMAP satellite with a land model. Often 2-3 days behind.',
    body: `SMAP measures the moisture of the top few centimetres of soil from space; the Level 4 product combines it with a land model to estimate water in the root zone (the layer plants draw from).

Dry soils are one of the first signs of an El Nino drought on land, before reservoirs drop.`,
    howToRead: 'Brown/orange = dry, green/blue = wet (see legend). Compare with a few weeks earlier using the date slider.',
    related: ['factor_water', 'layer_imerg'],
    sources: [SRC.gibs],
  },
  layer_land_temp: {
    title: 'Layer: land surface temperature',
    category: 'layers',
    aliases: ['LST', 'land surface temperature', 'MODIS LST'],
    short: 'How hot the ground itself is during the day (Terra MODIS), not the air. On a sunny day the ground is often much hotter than the air.',
    body: `Land surface temperature is the temperature of the ground surface (soil, roofs, roads, leaves) seen by a satellite. It is not the air temperature from a weather forecast, and it is not the feels-like temperature. It is useful to spot heatwaves and very dry areas. Clouds hide the ground, so cloudy areas are empty.`,
    howToRead: 'Warmer colours = hotter ground (see legend). Compare regions and dates rather than reading exact numbers.',
    related: ['heat_index', 'factor_heat'],
    sources: [SRC.gibs],
  },
  layer_radar: {
    title: 'Layer: rain radar (RainViewer)',
    category: 'layers',
    aliases: ['radar', 'RainViewer'],
    short: 'The latest rain radar picture (about every 10 minutes), from national radar networks shared through RainViewer. Shows where it is raining right now.',
    body: `Weather radars send out pulses and measure the echo from raindrops. RainViewer combines the radars that countries share. Coverage depends on which national radars are included: some areas may be empty even when it rains.

Radar shows the present; it is not a forecast.`,
    howToRead: 'Light colours = light rain; yellow/orange/red = heavy rain or thunderstorms. Movement between frames shows where the rain is heading.',
    related: ['layer_imerg', 'factor_flood'],
    sources: [SRC.rainviewer],
  },
} satisfies Record<string, TopicDef>
