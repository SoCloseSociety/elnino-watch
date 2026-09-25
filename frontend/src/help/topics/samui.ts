import type { TopicDef } from '../types'
import { SRC } from './enso'

/*
 * Thresholds and rules below mirror backend/app/local/risk.py and exit.py as read on
 * 2026-09-24. If the backend changes, update these tables (see help/README.md).
 */

const LEVEL_ROWS: string[][] = [
  ['0', 'Normal', 'Nothing abnormal expected on the island.', 'Keep a basic 3-day stock; review the Preparedness page once a month.'],
  ['1', 'Watch', 'Something is building up somewhere (El Nino, a rain deficit, a distant storm).', 'Check the page daily, follow TMD warnings, build 7 days of drinking water, note ferry and airport contacts.'],
  ['2', 'Prepare', 'A real hazard is likely in the coming days or season.', 'Build 14 days of self-sufficiency, fill the cistern, charge batteries, copy documents, decide your departure threshold.'],
  ['3', 'Act', 'A hazard is here or imminent, or two hazards combine.', 'Apply the matching scenario, stock water and fuel, pack the go-bag, check ferries and flights every morning.'],
  ['4', 'Leave', 'Safety or basic supplies are directly threatened.', 'Leave while ferries and flights run, or follow the authorities (DDPM 1784).'],
]

export const SAMUI_TOPICS = {
  risk_levels: {
    title: 'Koh Samui risk levels (0-4)',
    category: 'samui',
    aliases: ['risk level', 'Normal', 'Watch', 'Prepare', 'Act', 'Leave', 'vigilance', 'level'],
    short: 'One overall level for the island, from 0 Normal to 4 Leave, computed from 9 factors with documented rules. Each factor shows its value, threshold and source.',
    body: `The Samui page turns many numbers into one answer: how worried should you be, and what should you do now?

How it works, in short:

- 9 **factors** are scored from 0 to 4 each: El Nino, water, heat, flood, cyclone/wind, sea state, air quality, marine heat and news. See [[risk_factors]].
- 4 **rules** combine them into one overall level. See [[risk_rules]].
- If a critical factor has no current data, the level becomes **Unknown**, never "Normal". See [[data_coverage]].

Every factor shows its value, the threshold that applies, the explanation, the source and the time of the data. Nothing is hidden in a black-box score.`,
    thresholds: {
      columns: ['Level', 'Name', 'Means', 'What to do (summary)'],
      rows: LEVEL_ROWS,
      note: 'Full action lists are on the Learn page ("What to do at each level") and on the Samui page. The engine calls level 1 "vigilance" internally; it is shown as Watch.',
    },
    whyItMatters: 'The level is a planning aid, not an official warning. When Thai authorities (TMD, DDPM, the province) issue orders, follow them first.',
    related: ['risk_factors', 'risk_rules', 'data_coverage', 'unknown_level', 'limitations'],
    sources: [SRC.tmd, SRC.ddpm],
  },
  risk_factors: {
    title: 'The 9 risk factors',
    category: 'samui',
    aliases: ['factors', 'factor'],
    short: 'El Nino, water, heat, flood, cyclone/wind, sea state, air quality, marine heat and news. Each has its own thresholds and a cap on how far it can raise the overall level.',
    body: `Each factor is scored 0-4 from real data. Some factors are "context" and can only raise the overall level a little (the cap).`,
    thresholds: {
      columns: ['Factor', 'Main data', 'Cap in overall level', 'Critical?'],
      rows: [
        ['El Nino (enso)', 'NOAA ONI + weekly Nino 3.4, CPC status, IRI', '2 Prepare', 'yes'],
        ['Water (water)', 'ERA5 rain vs 1991-2020 normal, ECMWF seasonal, PWA notices, dam', '3 Act (4 only via rule R4b or confirmed shortage)', 'yes'],
        ['Heat (heat)', 'Open-Meteo feels-like forecast 7 days, ERA5 30-day Tmax anomaly', '3 Act', 'yes'],
        ['Flood (flood)', 'Open-Meteo 3-day rain, island rain gauges, TMD warnings, past 7 days of rain', '3 Act', 'yes'],
        ['Cyclone / wind (cyclone_wind)', 'GDACS cyclones, forecast gusts, TMD storm warnings', '3 Act (4 via rule R4a)', 'yes'],
        ['Sea state (sea_state)', 'Open-Meteo marine waves 72 h, TMD Gulf wave warnings', '3 Act', 'yes'],
        ['Air (air)', 'CAMS PM2.5 (Open-Meteo)', '3 Act', 'no'],
        ['Marine heat (marine_heat)', 'Coral Reef Watch DHW', '1 Watch', 'no'],
        ['News (news)', 'Keyword counts in news and social feeds', '1 Watch, and only with another factor >= 1', 'no'],
      ],
      note: '"Critical" factors: if one has no data or stale data, the overall level is Unknown.',
    },
    related: ['factor_enso', 'factor_water', 'factor_heat', 'factor_flood', 'factor_cyclone_wind', 'factor_sea_state', 'factor_air', 'factor_marine_heat', 'factor_news', 'risk_rules'],
    sources: [SRC.tmd],
  },
  risk_rules: {
    title: 'How the overall level is decided (rules R1-R4)',
    category: 'samui',
    aliases: ['R1', 'R2', 'R3', 'R4', 'rules', 'combination', 'compound risk'],
    short: 'R1: the highest factor wins (after caps). R2: news never triggers alone. R3: two physical hazards at Prepare = Act. R4: Leave only for a close orange/red cyclone or extreme heat plus a water crisis.',
    body: `The engine combines the factors with four documented rules:

- **R1, the highest factor wins.** Overall level = the highest factor level, after applying each factor's cap. Caps: El Nino 2; water, heat, flood, cyclone/wind, sea state and air 3; marine heat 1; news 1.
- **R2, news never decides alone.** The news factor only counts if another factor is at 1 or more.
- **R3, combined hazards.** If two physical hazards (among water, heat, flood, cyclone/wind, sea state, air) are both at 2 Prepare or more, the overall level is at least 3 Act. Example: heavy rain while 2 m seas stop the ferries.
- **R4, Leave (4) only when safety or basic supplies are directly threatened:**
  - **R4a**: an orange or red GDACS tropical cyclone within 300 km of Samui (cyclone/wind factor = 4).
  - **R4b**: extreme heat (heat >= 3) together with a water supply crisis (water >= 3).

The Samui page lists which rules fired, and "what would raise the level" (the next trigger for each factor).`,
    example: 'ONI at +1.8 °C gives the El Nino factor 2 (Prepare). All other factors at 0 or 1. Overall = 2 Prepare by R1, even if the weather today is fine.',
    related: ['risk_levels', 'risk_factors', 'data_coverage', 'factor_news'],
    sources: [SRC.gdacs],
  },
  factor_enso: {
    title: 'Factor: El Nino (event strength)',
    category: 'samui',
    aliases: ['enso factor'],
    short: 'Scores how strong El Nino is, from the latest ONI and weekly Nino 3.4. It can raise the overall level to Prepare but never higher: it is a warning sign, not a direct threat.',
    body: `The factor takes the higher of two levels: one from the latest ONI and one from the latest weekly Nino 3.4 anomaly. The explanation also shows the NOAA alert status and the highest El Nino probability in the IRI forecast (for context; they do not change the level).

It is marked stale if the newest ONI is more than 120 days old.`,
    thresholds: {
      columns: ['Value (ONI or weekly Nino 3.4)', 'Factor level'],
      rows: [
        ['below +0.5 °C', '0 Normal'],
        ['+0.5 to +1.49 °C (weak or moderate El Nino)', '1 Watch'],
        ['+1.5 °C or more (strong, and very strong)', '2 Prepare'],
      ],
      note: 'Cap in the overall level: 2. Critical factor.',
    },
    whyItMatters: 'A strong El Nino usually means below-normal rain and a hotter, longer dry season in Thailand. For Samui, the water risk window is February-April 2027.',
    related: ['oni', 'nino34', 'strength_categories', 'el_nino_thailand', 'risk_rules'],
    sources: [SRC.cpcOni, SRC.cpcDisc, SRC.iri],
  },
  factor_water: {
    title: 'Factor: rain deficit / water shortage',
    category: 'samui',
    aliases: ['water factor', 'drought', 'rain deficit'],
    short: 'Compares rain over the last 90 days (180 days in the dry season) with the 1991-2020 normal, and adds PWA notices, the seasonal forecast, the regional dam and the El Nino season.',
    body: `Main measure: rain observed (ERA5) over the last 90 days as a % of the 1991-2020 normal for the same days. In the dry season (January-May) the 180-day window drives the level when it is worse, because it holds the last monsoon refill.

Then, raise the level (never lower it) when:

- 60-day rain is below 50% of normal, or 180-day rain below 75%: at least 1.
- October-December (refill season) + strong El Nino (ENSO factor 2) + 90-day rain below 75%: at least 2.
- January-May + strong El Nino: at least 1, or 2 if rain is below 75% of normal.
- ECMWF seasonal forecast below 80% of normal for the next 3 months: at least 1.
- Ratchaprapa dam (mainland, a regional indicator only) below 40%: at least 1; below 25%: at least 2.
- A PWA Samui water-supply notice in force: at least 1; a notice lasting more than 48 h, or "no supply": at least 2.

Safeguards:

- A rain-only level 3 needs at least 100 mm missing in absolute terms; otherwise it stays at 2 (40% of a tiny dry-season normal is not an emergency by itself).
- Level 4 only when a shortage is confirmed: level 3 AND (at least 2 news reports of water shortage on Samui in 14 days, or a long PWA notice).

Not tracked automatically (no machine-readable source): the island reservoir levels and the PWA rotation schedule.`,
    thresholds: {
      columns: ['Rain, % of 1991-2020 normal (90 d; 180 d in the dry season)', 'Factor level'],
      rows: [
        ['75% or more', '0 Normal'],
        ['60 to 75%', '1 Watch'],
        ['40 to 60%', '2 Prepare'],
        ['below 40% and at least 100 mm short', '3 Act'],
        ['level 3 + shortage confirmed on the island', '4 (counts as 3 in the overall level, 4 only through rule R4b)'],
      ],
      note: 'Cap in the overall level: 3. Critical factor. Stale if ERA5 has not updated for 3 days or the last ERA5 day is more than 10 days old.',
    },
    whyItMatters: 'October-December is when Samui\'s reservoirs refill (about half of the year\'s rain). A deficit now is the strongest warning for the 2027 dry season.',
    related: ['rain_vs_normal', 'samui_water_supply', 'samui_seasons', 'era5', 'seasonal_outlook'],
    sources: [SRC.omEra5, SRC.samuiWater, SRC.thaiwater],
  },
  factor_heat: {
    title: 'Factor: extreme heat',
    category: 'samui',
    aliases: ['heat factor'],
    short: 'Uses the highest forecast feels-like temperature over the next 7 days, and how many days reach 41 °C, plus how much warmer than normal the last 30 days were.',
    body: `Main measure: the maximum daily feels-like ([[heat_index|apparent]]) temperature forecast for the next 7 days (Open-Meteo), and the number of days at 41 °C or more.

It can also be raised by a persistent warm spell: if the daily maximum temperature over the last 30 days (ERA5) averaged 1.5 °C above normal, at least 1; 2.5 °C above normal, at least 2.

Why start at 39 °C: on Samui a feels-like of 32-38 °C is an ordinary day, so the thresholds are set higher than the "caution" bands.`,
    thresholds: {
      columns: ['Max feels-like (7-day forecast)', 'Factor level'],
      rows: [
        ['below 39 °C', '0 Normal'],
        ['39 to 41 °C', '1 Watch'],
        ['41 °C or more on 1-2 days', '2 Prepare'],
        ['41 °C or more on 3+ days', '3 Act'],
        ['54 °C or more', '4 (counts as 3 in the overall level)'],
      ],
      note: 'Cap in the overall level: 3. Critical factor. Stale after 36 h without a forecast update. Heat >= 3 together with water >= 3 sets the overall level to 4 (rule R4b).',
    },
    whyItMatters: 'Above 41 °C feels-like, heatstroke is possible, especially for children, older people and during exertion. Power cuts (no air conditioning) make it worse. El Nino makes March-May 2027 likely hotter than normal.',
    related: ['heat_index', 'prep_heat', 'risk_rules'],
    sources: [SRC.omForecast, SRC.nwsHeat, SRC.tmdHeat],
  },
  factor_flood: {
    title: 'Factor: heavy rain / flooding',
    category: 'samui',
    aliases: ['flood factor', 'heavy rain'],
    short: 'Uses the 3-day rain forecast (biggest day and 72-hour total), island rain gauges, TMD heavy-rain warnings and how wet the ground already is.',
    body: `Main measure: the largest 24-hour rain and the 72-hour total in the Open-Meteo forecast for the next 3 days. A fresh island rain gauge reading (less than 6 hours old) is also scored with the 24-hour column.

Raised when:

- A TMD heavy-rain warning for the area is in force: at least 1.
- The past 7 days already brought 150 mm or more and the level is 1 or 2: +1 level (the same rain on saturated ground floods and slides more).
- The past 7 days brought 250 mm or more: at least 1, even without more rain forecast (landslides, slow drainage).`,
    thresholds: {
      columns: ['Max 24 h rain', 'or 72 h total', 'Factor level'],
      rows: [
        ['35 mm or less', 'below 100 mm', '0 Normal'],
        ['more than 35 mm (heavy)', '100 mm or more', '1 Watch'],
        ['more than 90 mm (very heavy)', '150 mm or more', '2 Prepare'],
        ['150 mm or more', '250 mm or more', '3 Act'],
      ],
      note: 'Rain classes from the TMD (see Rain amount classes). Cap: 3. Critical factor.',
    },
    whyItMatters: 'October-December (northeast monsoon) brings Samui\'s heaviest rain and floods, even in an El Nino year. Coastal roads and the Lamai/Chaweng area can flood; landslides are possible on slopes.',
    related: ['rain_classes', 'tmd_warnings', 'samui_seasons', 'layer_radar', 'prep_flood'],
    sources: [SRC.omForecast, SRC.tmdCriteria, SRC.thaiwater],
  },
  factor_cyclone_wind: {
    title: 'Factor: tropical cyclone / wind',
    category: 'samui',
    aliases: ['cyclone factor', 'wind factor', 'gusts'],
    short: 'Looks for GDACS tropical cyclones by distance to Samui and by alert colour, plus forecast wind gusts for 72 h and TMD storm warnings.',
    body: `The factor takes the highest of:

- The cyclone level (table below), from GDACS cyclone positions and colours.
- The gust level, from the strongest forecast gust in the next 72 hours (Beaufort scale; Samui often sees 55-70 km/h gusts in the monsoons, so it starts at strong gale).
- A TMD storm warning in force: at least 2.

If neither GDACS nor the TMD has answered recently, the factor is unknown: a cyclone cannot be ruled out.`,
    thresholds: {
      columns: ['Condition', 'Factor level'],
      rows: [
        ['Any GDACS cyclone within 800 km', '1 Watch'],
        ['Orange/red cyclone within 800 km', '2 Prepare'],
        ['Any cyclone within 300 km', '3 Act'],
        ['Orange/red cyclone within 300 km', '4 Leave (rule R4a)'],
        ['Gusts 75-88 km/h (Beaufort 9)', '1 Watch'],
        ['Gusts 89-117 km/h (Beaufort 10-11)', '2 Prepare'],
        ['Gusts 118 km/h or more (Beaufort 12)', '3 Act'],
      ],
      note: 'Cap: 3, except the orange/red cyclone within 300 km, which sets the overall level to 4. Critical factor.',
    },
    whyItMatters: 'Cyclones are rare on Samui but destructive (Harriet 1962, Gay 1989, Pabuk January 2019). They mostly arrive from October to January.',
    related: ['gdacs', 'tropical_cyclone', 'tmd_warnings', 'risk_rules'],
    sources: [SRC.gdacsTc, SRC.omForecast, SRC.tmd],
  },
  factor_sea_state: {
    title: 'Factor: sea state (ferries, isolation)',
    category: 'samui',
    aliases: ['sea state factor', 'waves factor'],
    short: 'The highest forecast wave height near Samui over 72 hours, plus TMD Gulf wave warnings. High seas stop ferries and cut the island off.',
    body: `Main measure: the maximum significant wave height forecast for the next 72 hours (Open-Meteo Marine). A TMD high-wave warning for the Gulf raises it to at least 1. Andaman-only warnings are ignored: they do not concern Samui.

If the wave forecast is missing but a TMD rough-sea warning is in force, the factor shows 1 Watch.`,
    thresholds: {
      columns: ['Max wave height (72 h)', 'Factor level'],
      rows: [
        ['below 1.5 m', '0 Normal'],
        ['1.5 to 2 m', '1 Watch'],
        ['2 to 3 m (small boats stay in port)', '2 Prepare'],
        ['3 m or more', '3 Act'],
      ],
      note: 'Cap: 3. Critical factor. Stale after 24 h without a marine forecast update.',
    },
    whyItMatters: 'Above 2 m, small boats stay in port and ferries may be cancelled: the island is then cut off (supplies, evacuation, water by barge). Only the airport remains, with limited capacity.',
    related: ['wave_height', 'departure_windows', 'exit_plan'],
    sources: [SRC.omMarine, SRC.tmd],
  },
  factor_air: {
    title: 'Factor: air quality (PM2.5, haze)',
    category: 'samui',
    aliases: ['air factor', 'haze factor'],
    short: 'The worse of the last 24-hour average of PM2.5 and the worst 24-hour average forecast for the next 72 hours, scored with the Thai PCD bands.',
    body: `Data: modelled PM2.5 from the Copernicus Atmosphere Monitoring Service (CAMS), through Open-Meteo. It is a model, not a monitoring station: compare with Air4Thai (the Thai Pollution Control Department network) when in doubt.`,
    thresholds: {
      columns: ['PM2.5, 24 h average', 'Thai PCD band', 'Factor level'],
      rows: [
        ['37.5 µg/m³ or less', 'very good to moderate', '0 Normal'],
        ['37.6 to 75', 'starting to affect health', '1 Watch'],
        ['75.1 to 125', 'affects health', '2 Prepare'],
        ['above 125', 'affects health (above 125.4 = US EPA "very unhealthy")', '3 Act'],
      ],
      note: 'Cap: 3. Not a critical factor. Stale after 12 h without an update.',
    },
    whyItMatters: 'Samui is usually clean, but El Nino years bring haze from fires in Indonesia and Malaysia (2015, 2019).',
    related: ['pm25', 'aqi', 'asmc_haze', 'cams', 'prep_haze'],
    sources: [SRC.omAir, SRC.air4thai, SRC.thaiAqi],
  },
  factor_marine_heat: {
    title: 'Factor: marine heat / coral bleaching',
    category: 'samui',
    aliases: ['marine heat factor'],
    short: 'NOAA Coral Reef Watch Degree Heating Weeks for the Gulf of Thailand stations. Context only: it can raise the overall level to Watch at most.',
    body: `Uses the latest DHW of the Coral Reef Watch stations, preferring those around Samui and the Gulf of Thailand. Stale if the newest value is more than 10 days old.`,
    thresholds: {
      columns: ['DHW', 'NOAA meaning', 'Factor level'],
      rows: [
        ['below 4 °C-weeks', 'below Alert Level 1', '0 Normal'],
        ['4 to 8', 'Alert Level 1 (reef-wide bleaching risk)', '1 Watch'],
        ['8 or more', 'Alert Level 2 or higher (mortality likely)', '2 (counts as 1 in the overall level)'],
      ],
      note: 'Cap: 1. Not a critical factor.',
    },
    related: ['dhw', 'coral_reef_watch', 'marine_heatwave'],
    sources: [SRC.crwDhw, SRC.crwBaa],
  },
  factor_news: {
    title: 'Factor: media and social signal',
    category: 'samui',
    aliases: ['news factor', 'social signal'],
    short: 'Counts news and social posts from the last 14 days that mention water shortage or flooding on Samui or in Thailand. Low weight, never a trigger on its own.',
    body: `A simple keyword count (English, French and Thai words for water shortage, drought, flood, landslide) over the app's news and social feeds.

It is deliberately weak: keyword counts can be fooled by old stories, rumours or articles about somewhere else. So it can only add Watch, and only when another factor is already at 1 or more (rule R2). Its main job: point you to local reports worth reading.`,
    thresholds: {
      columns: ['Mentions in 14 days', 'Factor level'],
      rows: [
        ['fewer than 3 about Samui and fewer than 10 about Thailand', '0 Normal'],
        ['3 or more about Samui, or 10 or more about Thailand', '1 Watch (only counts if another factor >= 1)'],
      ],
      note: 'Cap: 1. Also: 2 or more reports of water shortage on Samui can confirm a water level 4 when rain is already at level 3.',
    },
    related: ['news_signals', 'risk_rules', 'factor_water'],
    sources: [SRC.tmd],
  },
  heat_index: {
    title: 'Feels-like temperature and heat index',
    category: 'samui',
    aliases: ['apparent temperature', 'feels like', 'heat index'],
    short: 'How hot it feels to the body, combining air temperature with humidity (and in some formulas wind and sun). In humid Samui it is often several degrees above the air temperature.',
    body: `Sweat cools you by evaporating. In humid air it evaporates slowly, so you feel hotter than the thermometer says. The "heat index" (US National Weather Service) and the "apparent temperature" (the Open-Meteo value used here, which also accounts for wind and solar radiation) both try to express this.

Heat index values assume shade. Full sunshine can add up to 8 °C (15 °F) according to the NWS.

Thai health and weather agencies use four heat index bands adapted from the NWS (table). The current NWS chart uses slightly lower upper bands (danger from 39.4 °C / 103 °F, extreme danger from 51.7 °C / 125 °F). This app's heat factor uses its own thresholds of 39, 41 and 54 °C (see [[factor_heat]]).`,
    thresholds: {
      columns: ['Heat index (feels-like)', 'Band (TMD / Thai Department of Health)', 'Possible effects'],
      rows: [
        ['27 to 32 °C', 'Caution', 'Fatigue with prolonged exposure or activity'],
        ['32 to 41 °C', 'Extreme caution', 'Heat cramps, heat exhaustion or heat stroke possible with prolonged exposure or activity'],
        ['41 to 54 °C', 'Danger', 'Heat cramps or exhaustion likely; heat stroke possible'],
        ['above 54 °C', 'Extreme danger', 'Heat stroke highly likely'],
      ],
    },
    whyItMatters: 'Heat is the most common El Nino hazard for people in Thailand. The risk is highest in March-May, during exertion, for older people and children, and during power cuts.',
    related: ['factor_heat', 'prep_heat', 'layer_land_temp'],
    sources: [SRC.nwsHeat, SRC.tmdHeat, SRC.omForecast],
  },
  pm25: {
    title: 'PM2.5 and the Thai bands',
    category: 'samui',
    aliases: ['PM2.5', 'fine particles', 'particulate matter', 'PCD'],
    short: 'Tiny particles smaller than 2.5 micrometres (about 1/30 of a hair) that go deep into the lungs. Thailand\'s 24-hour standard is 37.5 µg/m³ since June 2023.',
    body: `PM2.5 comes from smoke (forest fires, crop burning), traffic and industry. Because the particles are so small, they reach deep into the lungs and the blood. It is measured in micrograms per cubic metre of air (µg/m³), usually as a 24-hour average.

Thailand tightened its standard on 1 June 2023: the 24-hour limit went from 50 to 37.5 µg/m³, and the red band now starts at 75.1 µg/m³.`,
    thresholds: {
      columns: ['PM2.5, 24 h (µg/m³)', 'Thai PCD band'],
      rows: [
        ['0 to 15.0', 'Very good'],
        ['15.1 to 25.0', 'Good'],
        ['25.1 to 37.5', 'Moderate'],
        ['37.6 to 75.0', 'Starting to affect health'],
        ['75.1 or more', 'Affects health'],
      ],
      note: 'Bands as used by the risk engine (Thai PCD, revised 2023).',
    },
    related: ['aqi', 'factor_air', 'asmc_haze', 'cams', 'layer_aerosol'],
    sources: [SRC.air4thai, SRC.thaiAqi],
  },
  aqi: {
    title: 'AQI (air quality index): Thai vs US',
    category: 'samui',
    aliases: ['AQI', 'US AQI', 'Thai AQI', 'air quality index'],
    short: 'An AQI turns pollutant levels into one score. The Thai AQI and the US AQI use different scales: the same air can read 100 on one and 105 on the other, so compare like with like.',
    body: `Thai AQI (Pollution Control Department, Air4Thai): 0-25 very good, 26-50 good, 51-100 moderate, 101-200 starting to affect health, 201 or more affects health. A 24-hour PM2.5 of 37.5 µg/m³ corresponds to Thai AQI 100.

US AQI (used by many apps, and by Open-Meteo in this dashboard): 0-50 good up to 301-500 hazardous, with different breakpoints.

That is why IQAir, AQICN and Air4Thai can show different numbers for the same place and hour. The app's risk level uses the PM2.5 concentration itself (µg/m³), not an index.`,
    related: ['pm25', 'factor_air', 'sources_disagree'],
    sources: [SRC.thaiAqi, SRC.air4thai, SRC.omAir],
  },
  rain_vs_normal: {
    title: 'Rain as % of normal',
    category: 'samui',
    aliases: ['percent of normal', '% of normal', 'rain deficit', 'rainfall totals'],
    short: 'Rain over the last 30, 60, 90 or 180 days divided by the 1991-2020 average for the same calendar days. 60% means 40% less rain than usual.',
    body: `The app adds up the rain observed on Samui (ERA5 reanalysis, about 5 days behind) over several windows, and compares each with the 1991-2020 ERA5 normal for exactly the same days of the year.

- 100% = a normal amount.
- Below 75% = drier than normal (the water factor starts at Watch).
- Above 100% = wetter than normal.

Short windows (30 days) react fast but a single storm can swing them. Long windows (180 days) show the slow deficit that empties reservoirs.`,
    howToRead: 'Look at both the % and the millimetres: 40% of a dry-season normal of 60 mm is only 36 mm missing, while 60% of a November normal can be over 100 mm missing.',
    related: ['factor_water', 'era5', 'climatology_baseline', 'samui_seasons'],
    sources: [SRC.omEra5],
  },
  samui_seasons: {
    title: 'Koh Samui\'s seasons',
    category: 'samui',
    aliases: ['seasons', 'northeast monsoon', 'southwest monsoon', 'dry season', 'rainy season', 'NE monsoon', 'SW monsoon'],
    short: 'Samui (Gulf side) gets its main rain from the northeast monsoon, October to January, wettest around November. The dry, hot season runs February to May. The southwest monsoon (June-September) is mild on Samui.',
    body: `Samui's calendar is the reverse of Phuket's and most of Thailand's, because it sits on the Gulf of Thailand side, sheltered from the southwest monsoon:

- **October to January, northeast monsoon**: the real rainy season. The ERA5 1991-2020 normal at Samui gives about 282 mm in October, 284 mm in November and 148 mm in December: close to half of the roughly 1,530 mm year falls in October-December. Floods, rough seas in the Gulf and the rare cyclones come in this period. It is also when reservoirs refill.
- **February to May, dry and hot season**: February is the driest month (about 39 mm). March to May is the heat peak. Water stored during the monsoon is used up.
- **June to September, southwest monsoon**: Samui is relatively sheltered; rain is moderate. Andaman-side storms and wave warnings mostly do not apply.

The TMD monthly summaries describe the same pattern: heavy to very heavy rain on the east coast of the South in November-December under the northeast monsoon.`,
    whyItMatters: 'With El Nino, the danger window for water is February-April 2027, and for heat March-May. The flood and sea risk is highest now, October-January, El Nino or not.',
    related: ['el_nino_thailand', 'samui_water_supply', 'factor_water', 'factor_flood', 'wave_height'],
    sources: [SRC.omEra5, SRC.tmd],
  },
  samui_water_supply: {
    title: 'Samui\'s water supply',
    category: 'samui',
    aliases: ['water supply', 'PWA', 'rationing', 'pipeline', 'reservoirs', 'tap water'],
    short: 'Samui relies on small reservoirs, desalination and an undersea pipeline from the mainland. In 2026 a long dry spell led the PWA to rotate supply by zone from 3 August.',
    body: `What is known (sources linked below):

- Tap water on Samui is run by the PWA (Provincial Waterworks Authority), Ko Samui branch.
- Supply comes from the island's small reservoirs, desalination plants and a pipeline from the Surat Thani mainland.
- According to the PWA as reported in July 2026, the mainland pipeline supplies about 16,000 m³ per day, against an average island demand of about 34,000 m³ per day.
- In late July 2026 a prolonged dry spell, worsened by El Nino, cut clean-water production to about 40% of normal, and the PWA announced supply rotating by zone from 3 August 2026 (Bangkok Post, 29 July 2026). Hotels and businesses bought trucked water.

What the app tracks: PWA Samui interruption notices (from the PWA notice service) and rain vs normal. What it does not track (no machine-readable source): reservoir levels and the rotation schedule. Check PWA Samui announcements directly.`,
    whyItMatters: 'A system already short in August 2026 enters the 2027 dry season with a very strong El Nino peaking. If the October-December monsoon is weak, shortages in February-April 2027 are likely. This is the single biggest risk for residents who stay.',
    related: ['factor_water', 'samui_seasons', 'prep_water', 'rain_vs_normal'],
    sources: [SRC.samuiWater],
  },
  exit_plan: {
    title: 'Exit plan (leaving the island)',
    category: 'samui',
    aliases: ['exit', 'departure', 'leaving', 'evacuation', 'routes'],
    short: 'The "Leave the island" view: can you leave, when, how, and what to do first. It checks waves, wind, TMD sea warnings, cyclones and heavy rain, and lists the routes.',
    body: `Samui can only be left by sea (car ferries, passenger boats, catamarans) or by air. The exit plan gathers:

- **Signals** now: waves, TMD Gulf sea warnings, wind gusts, tropical cyclones, heavy rain. Each is ok, caution, blocked or unknown.
- **Departure windows** for the next 7 days (see [[departure_windows]]).
- **Routes**: Seatran and Raja car ferries to Donsak, Lomprayah boats to Donsak or Chumphon, flights from Samui (USM) or Surat Thani (URT), trains from Surat Thani. Only official operator sites are linked; no schedules or prices (they change).
- **Checklist** before leaving: documents, cash, medicine, confirming the crossing, telling someone, charged phone, go-bag, and securing the house.

Missing or stale data shows as unknown, never ok.`,
    thresholds: {
      columns: ['Signal', 'Caution', 'Blocked'],
      rows: [
        ['Waves (daily max)', '2 m or more', '3 m or more'],
        ['TMD Gulf sea bulletin', 'wave warning in force', '"small boats should stay ashore"'],
        ['Wind gusts (daily max)', '50 km/h or more (Beaufort 7)', '75 km/h or more (Beaufort 9)'],
        ['Tropical cyclone', 'any within 800 km', 'within 300 km, or orange/red within 800 km'],
        ['Heavy rain', 'TMD heavy-rain bulletin or 90 mm/24 h forecast', '150 mm/24 h forecast'],
      ],
    },
    whyItMatters: 'Leave early, while ferries and flights still run. When the sea closes, everyone tries to fly out at once and seats run out.',
    related: ['departure_windows', 'wave_height', 'prep_exit', 'risk_levels'],
    sources: [SRC.omMarine, SRC.tmd, SRC.ddpm],
  },
  departure_windows: {
    title: 'Departure windows',
    category: 'samui',
    aliases: ['windows', 'ferry windows', 'when to leave'],
    short: 'For each of the next 7 days: whether conditions look normal for a ferry crossing (ok), possible with delays (caution), ferries likely suspended (blocked), or unknown.',
    body: `Each day is graded from that day's forecast maximum wave height and gusts, TMD Gulf wave bulletins still in force, and, for the first 3 days, any nearby cyclone. The worst signal wins.

- **ok**: crossing conditions look normal.
- **caution**: possible, but expect delays or cancellations.
- **blocked**: ferries likely suspended.
- **unknown**: no wave forecast for that day; cannot be assessed.

Forecasts beyond 3 days are less reliable. Always confirm with the operator or at the pier on the day.`,
    related: ['exit_plan', 'wave_height', 'factor_sea_state'],
    sources: [SRC.omMarine, SRC.tmd],
  },
  data_coverage: {
    title: 'Data coverage',
    category: 'samui',
    aliases: ['coverage', 'critical factors', 'missing data'],
    short: 'How many of the 9 factors have current data. If a critical factor (El Nino, water, heat, flood, cyclone/wind, sea state) is missing or stale, the overall level is Unknown.',
    body: `Missing data is never read as "safe". The engine checks each factor:

- **No data** (the source did not answer, or nothing was collected): the factor level is unknown.
- **Stale data** that would read 0: also unknown (old calm data cannot prove it is calm now).

The six **critical** factors are enso, water, heat, flood, cyclone_wind and sea_state: each can on its own move the level to Act or Leave, or (El Nino) sets the background of the season. If any is missing or stale, the overall level is **Unknown**, and the page shows "at least ..." computed from the factors that do have data.

Air, marine heat and news are secondary: if they are missing, the level is still computed, and the headline says which ones lack data.`,
    related: ['unknown_level', 'stale_data', 'freshness', 'sources_page'],
    sources: [SRC.tmd],
  },
  unknown_level: {
    title: 'Unknown level ("at least ...")',
    category: 'samui',
    aliases: ['unknown', 'level unknown', 'at least'],
    short: 'The overall level cannot be assessed because a critical factor has no current data. "At least X" is the minimum the known factors justify; the real level may be higher.',
    body: `"Unknown" is an honest answer, not an error to ignore. Example: if the wave forecast is down, the app cannot tell whether ferries will run, so it will not claim "Normal".

What to do while it is unknown:

- Act on the "at least" level shown.
- Check the missing information yourself: TMD (tmd.go.th, hotline 1182) for warnings, the ferry operators for crossings.
- Look at the Sources page to see which source is failing and since when.`,
    related: ['data_coverage', 'stale_data', 'sources_page'],
    sources: [SRC.tmd],
  },
  stale_data: {
    title: 'Stale data',
    category: 'samui',
    aliases: ['stale', 'old data', 'out of date'],
    short: 'Data older than it should be for that source. Stale values are marked with a clock sign; a stale "all calm" is treated as unknown.',
    body: `Each source has a maximum age that matches how often it really updates: a few hours for weather forecasts, a day or two for satellite products, about two months for a monthly index.

When the newest data is older than that, it is **stale**. The value is still shown (with its date and a warning), because it can still be useful context. But for the Samui risk level, a stale factor that would read 0 becomes unknown, and a stale critical factor makes the overall level Unknown.`,
    howToRead: 'Look for the "stale" chip and the "as of" date next to every value.',
    related: ['freshness', 'data_coverage', 'sources_page'],
    sources: [SRC.tmd],
  },
} satisfies Record<string, TopicDef>
