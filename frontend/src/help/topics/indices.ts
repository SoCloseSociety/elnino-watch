import type { TopicDef } from '../types'
import { SRC } from './enso'

export const INDEX_TOPICS = {
  anomaly: {
    title: 'Anomaly',
    category: 'indices',
    aliases: ['departure from normal', 'deviation'],
    short: 'The difference between a measured value and the normal value for that place and time of year. +1.5 °C means 1.5 °C warmer than normal.',
    body: `Almost every climate number in this app is an anomaly, not a raw value.

Why: the ocean near the equator is always warm, and the dry season is always dry. What matters is whether it is warmer, wetter or drier **than usual for that time of year**. So scientists subtract the normal value (the [[climatology_baseline|climatology]]) from the measured value.

- A positive anomaly (+) = above normal.
- A negative anomaly (-) = below normal.
- Zero = exactly normal.`,
    example: 'The Nino 3.4 region is normally about 27 to 28 °C at this time of year. If the measured 3-month mean is 29.09 °C and the normal for those months is 27.29 °C, the anomaly is +1.80 °C.',
    related: ['climatology_baseline', 'sst_anomaly', 'oni', 'rain_vs_normal'],
    sources: [SRC.cpcOni, SRC.ucarNino],
  },
  climatology_baseline: {
    title: 'Climatology and the 1991-2020 baseline',
    category: 'indices',
    aliases: ['climatology', 'normal', 'baseline', 'base period', '1991-2020'],
    short: 'The "normal" used to compute anomalies: the average over a 30-year reference period, usually 1991-2020, for each place and each day or month.',
    body: `A climatology is the long-term average of a variable for each calendar day or month. The World Meteorological Organization's current standard period is 1991-2020, and many products in this app use it:

- NOAA's weekly Nino SST values (OISST, 1991-2020 base).
- The Koh Samui rain and temperature normals (ERA5, 1991-2020), used for "% of normal".
- Climate Reanalyzer's daily SST charts.

Some indices use other references: NOAA's [[oni|ONI]] uses centred 30-year base periods updated every 5 years; [[mei_v2|MEI.v2]] uses 1980-2018; the BoM [[bom_soi|SOI]] uses 1933-1992.

Why it matters: the ocean has warmed since 1991-2020, so a fixed old baseline makes everything look "above normal". That is one reason NOAA now uses [[roni|RONI]].`,
    related: ['anomaly', 'roni', 'rain_vs_normal', 'era5'],
    sources: [SRC.cpcOni, SRC.cpcRoniNews, SRC.omEra5],
  },
  sst: {
    title: 'Sea surface temperature (SST)',
    category: 'indices',
    aliases: ['SST', 'ocean temperature'],
    short: 'The temperature of the top layer of the ocean, measured by satellites, ships and buoys, in °C.',
    body: `SST is the temperature of the ocean surface (roughly the top metre). It is measured by satellites (infrared and microwave sensors), ships, drifting buoys and moored buoys such as the [[tao_buoys|TAO array]]. Products such as NOAA OISST and ERSST blend these into maps.

ENSO is measured mainly with SST in the equatorial Pacific. SST also matters locally: warm water around Samui feeds heavier showers and stresses corals.`,
    related: ['sst_anomaly', 'nino34', 'world_sst', 'layer_sst'],
    sources: [SRC.ucarNino, SRC.climateReanalyzer],
  },
  sst_anomaly: {
    title: 'SST anomaly',
    category: 'indices',
    aliases: ['sea surface temperature anomaly'],
    short: 'How much warmer (+) or cooler (-) the sea surface is than its 1991-2020 normal for that date, in °C.',
    body: `An SST anomaly is the sea surface temperature minus its normal for that place and date (see [[anomaly]]). Maps of SST anomaly make El Nino easy to see: a long red tongue of warm anomalies along the equator in the eastern Pacific.`,
    howToRead: 'Red/orange = warmer than normal, blue = cooler, white or pale = near normal. On the Indices page, values above +0.5 in the Nino regions indicate El Nino-like warmth.',
    related: ['anomaly', 'sst', 'nino34', 'layer_sst_anomaly'],
    sources: [SRC.ucarNino],
  },
  nino_regions: {
    title: 'The Nino regions (1+2, 3, 3.4, 4)',
    category: 'indices',
    aliases: ['Nino boxes', 'Niño regions'],
    short: 'Four boxes along the equatorial Pacific where sea temperature is averaged to track ENSO. Nino 3.4 is the main one.',
    body: `Scientists average the sea surface temperature over fixed boxes of ocean:

- **[[nino12|Nino 1+2]]**: off the coast of Peru and Ecuador.
- **[[nino3|Nino 3]]**: the eastern equatorial Pacific.
- **[[nino34|Nino 3.4]]**: the east-central equatorial Pacific. The reference for El Nino.
- **[[nino4|Nino 4]]**: the central and western equatorial Pacific.

The boxes are drawn on the Map page.`,
    thresholds: {
      columns: ['Region', 'Latitude', 'Longitude'],
      rows: [
        ['Nino 1+2', '0 to 10° S', '90° W to 80° W'],
        ['Nino 3', '5° N to 5° S', '150° W to 90° W'],
        ['Nino 3.4', '5° N to 5° S', '170° W to 120° W'],
        ['Nino 4', '5° N to 5° S', '160° E to 150° W'],
      ],
    },
    howToRead: 'When the eastern boxes (1+2, 3) are much warmer than Nino 4, the event is "eastern Pacific" type, like 1997-98 and 2026. When Nino 4 is warmest, it is a "central Pacific" event.',
    related: ['nino34', 'nino12', 'nino3', 'nino4', 'sst_anomaly'],
    sources: [SRC.ucarNino],
  },
  nino34: {
    title: 'Nino 3.4',
    category: 'indices',
    aliases: ['Niño 3.4', 'nino34_weekly_anom'],
    short: 'The average sea temperature anomaly of the box 5° N-5° S, 170° W-120° W. It is the main number used to define El Nino.',
    body: `The Nino 3.4 index is the sea surface temperature anomaly averaged over the Nino 3.4 box. It sits where changes in ocean temperature move the tropical rain the most, so it tracks ENSO impacts well.

NOAA builds its official indices ([[oni|ONI]], [[roni|RONI]]) from it. The app also shows faster versions: weekly (NOAA OISST) and daily (Climate Reanalyzer). See [[time_resolution]].`,
    howToRead: '+0.5 °C or more = El Nino-like; +1.5 °C or more = strong. One warm week is not an El Nino: the official indices use 3-month averages.',
    whyItMatters: 'The app\'s ENSO factor for Samui uses the highest of the latest ONI and the latest weekly Nino 3.4 anomaly.',
    related: ['oni', 'roni', 'nino_regions', 'time_resolution', 'factor_enso'],
    sources: [SRC.ucarNino, SRC.cpcIndices],
  },
  nino12: {
    title: 'Nino 1+2',
    category: 'indices',
    aliases: ['Niño 1+2', 'coastal El Nino'],
    short: 'The box off Peru and Ecuador (0-10° S, 90-80° W). It warms first and most in eastern Pacific El Ninos, and swings a lot from week to week.',
    body: `Nino 1+2 is the smallest and most eastern box, right along the South American coast. It reacts fast, so it is noisy. A warm Nino 1+2 alone (a "coastal El Nino") brings heavy rain to Peru and Ecuador but may have little effect on Asia.

In September 2026 the CPC reported Nino 1+2 at +3.4 °C.`,
    related: ['nino_regions', 'nino3', 'nino34'],
    sources: [SRC.ucarNino, SRC.cpcDisc],
  },
  nino3: {
    title: 'Nino 3',
    category: 'indices',
    aliases: ['Niño 3', 'NINO.3'],
    short: 'The eastern equatorial Pacific box (5° N-5° S, 150-90° W). The Japan Meteorological Agency defines El Nino with it.',
    body: `Nino 3 covers the eastern half of the equatorial Pacific. It was the main El Nino index before Nino 3.4 took over at NOAA. The Japan Meteorological Agency (JMA) still uses it: see [[jma_outlook]].

In September 2026 the CPC reported Nino 3 at +2.5 °C.`,
    related: ['nino_regions', 'jma_outlook', 'nino34'],
    sources: [SRC.ucarNino, SRC.jmaDef],
  },
  nino4: {
    title: 'Nino 4',
    category: 'indices',
    aliases: ['Niño 4'],
    short: 'The central and western equatorial Pacific box (5° N-5° S, 160° E-150° W). It warms most in "central Pacific" El Ninos.',
    body: `Nino 4 sits near the date line, on the edge of the warm pool. Its temperature changes less than the eastern boxes.

In September 2026 the CPC reported Nino 4 at only +0.1 °C: the 2026 event is concentrated in the east.`,
    related: ['nino_regions', 'nino34', 'warm_pool'],
    sources: [SRC.ucarNino, SRC.cpcDisc],
  },
  oni: {
    title: 'ONI (Oceanic Nino Index)',
    category: 'indices',
    aliases: ['Oceanic Nino Index', 'Oceanic Niño Index'],
    short: 'The 3-month running average of the Nino 3.4 sea temperature anomaly, published monthly by NOAA. +0.5 °C or more = El Nino threshold.',
    body: `The ONI is NOAA's long-standing El Nino index. Each value is the average anomaly over three consecutive months, labelled by their initials: JJA = June-July-August (see [[season_codes]]).

- It uses the ERSST ocean dataset (version 6 since 2026) and centred 30-year base periods updated every 5 years.
- Historically, an El Nino "episode" is counted when the ONI is at or above +0.5 °C for at least 5 consecutive overlapping seasons.
- Recent values can be revised for up to two months after they are first posted.

Since 1 February 2026, NOAA uses the relative version, [[roni|RONI]], for official monitoring. The ONI is still published and still shown here, because it is the index most people and older articles refer to.`,
    howToRead: 'One point per month on the chart, dated at the centre month (JJA 2026 is plotted at mid-July 2026). The band from -0.5 to +0.5 is neutral.',
    whyItMatters: 'The app\'s ENSO factor for Samui is based on the ONI (plus the weekly Nino 3.4 value): >= +0.5 gives Watch, >= +1.5 gives Prepare.',
    example: 'CPC values for 2026: AMJ +0.95, MJJ +1.39, JJA +1.80 °C.',
    related: ['roni', 'nino34', 'season_codes', 'strength_categories', 'factor_enso'],
    sources: [SRC.cpcOni, SRC.cpcIndices],
  },
  roni: {
    title: 'RONI (Relative Oceanic Nino Index)',
    category: 'indices',
    aliases: ['Relative ONI', 'relative Nino 3.4'],
    short: 'NOAA\'s official ENSO index since 1 February 2026: the Nino 3.4 anomaly minus the average anomaly of the whole tropical ocean (20° S-20° N), as a 3-month mean.',
    body: `Why it exists: the whole tropical ocean has been warming. With the classic ONI, part of that general warming shows up as "El Nino-like" warmth, and the 30-year baseline struggles to keep up in real time.

What matters for the weather is whether the Nino 3.4 region is warmer **than the rest of the tropics**, because that contrast is what moves the rain and the winds. RONI measures exactly that:

- Take the Nino 3.4 SST anomaly.
- Subtract the average SST anomaly of the global tropics (20° S to 20° N).
- Rescale so that its variability matches the ONI.
- Average over 3 months.

The thresholds are unchanged: +0.5 °C for El Nino, -0.5 °C for La Nina, 5 consecutive overlapping seasons for a historical episode. NOAA made RONI official through NWS Public Information Statement 26-05, effective 1 February 2026.`,
    howToRead: 'Read it like the ONI. RONI is usually a bit lower than ONI when the whole tropics are unusually warm (2023-24: ONI peak +2.0, RONI peak +1.4).',
    whyItMatters: 'NOAA now states El Nino strength and forecasts in RONI (for example, the 75% chance of a RONI of +2.5 °C or more in October-December 2026). Note: the app\'s ENSO factor still uses ONI and the weekly Nino 3.4 value, which run higher than RONI this year (JJA 2026: ONI +1.80, RONI +1.36).',
    related: ['oni', 'climatology_baseline', 'past_events', 'event_2026'],
    sources: [SRC.cpcRoni, SRC.cpcRoniNews, SRC.nwsRoni],
  },
  season_codes: {
    title: 'Season codes (DJF, JJA, SON...)',
    category: 'indices',
    aliases: ['DJF', 'JFM', 'JJA', 'SON', 'OND', 'NDJ', 'MAM', 'AMJ', 'MJJ', 'JAS', 'ASO', 'FMA', '3-month season'],
    short: 'Three letters = three consecutive months, by their initials. DJF = December-January-February; JJA = June-July-August.',
    body: `ENSO indices and forecasts use overlapping 3-month seasons, named by the first letter of each month:

DJF, JFM, FMA, MAM, AMJ, MJJ, JJA, JAS, ASO, SON, OND, NDJ.

"Overlapping" means each season shares two months with the next one. So a value for JJA and a value for JAS are not independent: they share July and August.

Watch out: DJF starts in December of one year and ends in February of the next. "DJF 2027" in forecasts means December 2026 to February 2027.`,
    related: ['oni', 'iri_plume', 'running_mean'],
    sources: [SRC.cpcOni, SRC.iri],
  },
  running_mean: {
    title: 'Running mean (moving average)',
    category: 'indices',
    aliases: ['moving average', '3-month mean', 'smoothing'],
    short: 'An average over a window that slides forward in time. It removes short-lived ups and downs so the trend is easier to see.',
    body: `A 3-month running mean averages months 1-2-3, then 2-3-4, then 3-4-5, and so on. It smooths out week-to-week noise (a passing storm can cool the ocean for a few days).

The price: it lags. A 3-month mean centred on July is only complete at the end of August and is published in early September. That is why the app also shows weekly and daily Nino 3.4 values, which are faster but noisier.`,
    related: ['time_resolution', 'oni', 'season_codes'],
    sources: [SRC.cpcOni],
  },
  time_resolution: {
    title: 'Daily, weekly and monthly values',
    category: 'indices',
    aliases: ['weekly vs daily vs monthly', 'resolution', 'weekly', 'daily', 'monthly'],
    short: 'The same ocean can be summarised every day, every week or every 3 months. Faster values react sooner but jump around; slower ones are steadier and are the official ones.',
    body: `The app shows Nino 3.4 at three speeds:

- **Daily** (Climate Reanalyzer, NOAA OISST v2.1): the newest picture, but noisy.
- **Weekly** (NOAA CPC, OISST, 1991-2020 base): updated every Monday or so; the best "current" value.
- **Monthly 3-month means** ([[oni|ONI]], [[roni|RONI]]): the official record; about one month behind.

They will not match exactly: different datasets (OISST vs ERSST), different baselines, and different averaging windows. A difference of a few tenths of a degree is normal.`,
    howToRead: 'Use the weekly value to see where things are heading, and the 3-month index to judge the official strength.',
    related: ['running_mean', 'nino34', 'oni', 'sources_disagree'],
    sources: [SRC.cpcIndices, SRC.climateReanalyzer],
  },
  soi: {
    title: 'SOI (Southern Oscillation Index, NOAA CPC)',
    category: 'indices',
    aliases: ['Southern Oscillation Index', 'Tahiti minus Darwin'],
    short: 'The standardised air pressure difference between Tahiti and Darwin. Negative values go with El Nino; positive with La Nina.',
    body: `The SOI measures the atmosphere half of ENSO. It compares sea-level air pressure at Tahiti (central Pacific) with Darwin (northern Australia).

- During El Nino, pressure rises at Darwin and falls at Tahiti, so Tahiti minus Darwin becomes **negative**.
- During La Nina, the opposite: **positive** SOI.

The sign convention is the opposite of the ocean indices: a warm Pacific (positive ONI) goes with a negative SOI. One month of SOI is noisy (a single storm near Darwin or Tahiti can swing it). Look for values that stay negative for several months.

The NOAA CPC version is standardised (in units of standard deviations), so typical values are between about -3 and +3. The Australian version uses a different scale: see [[bom_soi]].`,
    howToRead: 'Below zero for months = consistent with El Nino. In September 2026 the CPC reported both the traditional and equatorial SOI as negative.',
    related: ['bom_soi', 'walker_circulation', 'enso', 'mei_v2'],
    sources: [SRC.cpcFaq, SRC.cpcIndices, SRC.cpcDisc],
  },
  bom_soi: {
    title: 'SOI (Australian Bureau of Meteorology, Troup)',
    category: 'indices',
    aliases: ['BoM SOI', 'Troup SOI'],
    short: 'Australia\'s version of the SOI, on a different scale from NOAA\'s: about 10 times larger. Sustained values below -7 often mean El Nino, above +7 La Nina.',
    body: `The Bureau of Meteorology (BoM) computes the SOI with the Troup method: the standardised anomaly of the Tahiti minus Darwin pressure difference, multiplied by 10, with a 1933-1992 base period.

So a BoM SOI of -12 is roughly comparable to a NOAA CPC SOI of about -1.2. **Do not compare the two numbers directly.**

BoM's rule of thumb: sustained values below -7 often indicate El Nino; sustained values above +7 are typical of La Nina.`,
    howToRead: 'Negative = El Nino-like. Look at several months: single months are noisy.',
    related: ['soi', 'sources_disagree'],
    sources: [SRC.bomSoi],
  },
  mei_v2: {
    title: 'MEI.v2 (Multivariate ENSO Index)',
    category: 'indices',
    aliases: ['MEI', 'Multivariate ENSO Index'],
    short: 'A combined ENSO index from NOAA PSL that blends 5 ocean and atmosphere variables over the tropical Pacific. Positive = El Nino-like.',
    body: `MEI.v2 looks at the whole coupled system at once, not just ocean temperature. It combines 5 variables over the tropical Pacific (30° S-30° N, 100° E-70° W): sea-level pressure, sea surface temperature, east-west surface wind, north-south surface wind, and outgoing longwave radiation (a satellite measure of cloudiness).

It is computed for 12 overlapping 2-month "seasons" (DJ, JF, FM...) against a 1980-2018 reference period. The result is in standard deviations, like the NOAA SOI but with the opposite sign: positive = El Nino-like.`,
    howToRead: 'A high MEI together with a high ONI means ocean and atmosphere agree: the El Nino is well "coupled", which usually means stronger impacts.',
    related: ['oni', 'soi', 'enso'],
    sources: [SRC.psl],
  },
  world_sst: {
    title: 'World sea surface temperature',
    category: 'indices',
    aliases: ['global SST', 'world_sst_daily', '60S-60N'],
    short: 'The average sea surface temperature of the world ocean between 60° S and 60° N, updated daily (Climate Reanalyzer, NOAA OISST v2.1).',
    body: `This is the average temperature of almost the whole ocean surface. It has risen over the decades with climate change, and El Nino adds a temporary boost on top, because the Pacific releases heat.

The chart compares the current year with past years and with the 1991-2020 average for each day.`,
    howToRead: 'A line far above all past years means record ocean warmth. It is global context: it does not tell you about Samui directly.',
    whyItMatters: 'A warmer ocean overall is part of why NOAA moved to [[roni|RONI]]. It also raises the background odds of marine heatwaves and coral bleaching in the Gulf of Thailand.',
    related: ['sst', 'roni', 'marine_heatwave'],
    sources: [SRC.climateReanalyzer],
  },
} satisfies Record<string, TopicDef>
