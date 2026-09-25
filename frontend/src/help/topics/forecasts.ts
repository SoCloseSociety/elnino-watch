import type { TopicDef } from '../types'
import { SRC } from './enso'

export const FORECAST_TOPICS = {
  cpc_alert_system: {
    title: 'NOAA ENSO Alert System (Watch, Advisory)',
    category: 'forecasts',
    aliases: ['El Nino Watch', 'El Nino Advisory', 'Final Advisory', 'CPC status', 'cpc_alert'],
    short: 'NOAA\'s official ENSO status, updated monthly: Watch (El Nino likely within 6 months), Advisory (El Nino is here), Final Advisory (it has ended).',
    body: `NOAA's Climate Prediction Center (CPC) publishes an ENSO Diagnostic Discussion every month (usually the second Thursday) with a status line:

- **El Nino Watch**: conditions are favourable for El Nino to develop within the next six months.
- **El Nino Advisory**: El Nino conditions are observed and expected to continue.
- **Final El Nino Advisory**: El Nino conditions have ended.
- **Not active**: none of the above.

The same words exist for La Nina.

"El Nino conditions" means: a one-month relative Nino 3.4 anomaly of +0.5 °C or more, an expectation that the 3-month [[roni|RONI]] threshold will be met, AND an atmospheric response typical of El Nino over the equatorial Pacific.`,
    howToRead: 'A Watch is a forecast; an Advisory is an observation. The Advisory stays in force until conditions end, then a Final Advisory closes the event.',
    whyItMatters: 'As of 10 September 2026 the status is El Nino Advisory, with a greater than 90% chance of a very strong event in late 2026 and early 2027.',
    related: ['event_2026', 'roni', 'iri_plume', 'wmo_update'],
    sources: [SRC.cpcAlert, SRC.cpcDisc],
  },
  iri_plume: {
    title: 'IRI ENSO forecast (plume and probabilities)',
    category: 'forecasts',
    aliases: ['IRI', 'plume', 'model plume', 'ENSO probabilities'],
    short: 'Columbia University\'s monthly summary of about 20 computer models: for each 3-month season ahead, the chance of El Nino, neutral or La Nina.',
    body: `The International Research Institute for Climate and Society (IRI) collects forecasts of the Nino 3.4 anomaly from many models (22 in the current release: 13 dynamical and 9 statistical).

- The **plume** is a chart with one line per model for the next 9 overlapping 3-month seasons. When the lines are close together, the models agree.
- The **probabilities** turn this into chances for each season: El Nino (+0.5 °C or more), neutral (-0.5 to +0.5 °C), La Nina (-0.5 °C or less). The three add up to 100%.

Seasons are named by their months' initials: SON = September-October-November, DJF = December-January-February, and so on (see [[season_codes]]).`,
    howToRead: 'Read the bar for each season: the red part is the El Nino chance. 90% means "9 chances in 10"; it is not a measure of strength. A forecast for 8 months ahead is much less reliable than one for next season (see [[forecast_uncertainty]]).',
    example: 'IRI September 2026: El Nino probability 100% from SON 2026 through FMA 2027, 99% in MAM 2027, 90% in AMJ 2027, then 61% in MJJ 2027.',
    whyItMatters: 'It tells you how long El Nino conditions are likely to last. If El Nino is still likely through February-April 2027, Samui\'s dry season is likely to be affected.',
    related: ['season_codes', 'forecast_uncertainty', 'probability', 'cpc_alert_system'],
    sources: [SRC.iri],
  },
  probability: {
    title: 'Reading a forecast probability',
    category: 'forecasts',
    aliases: ['chance', 'percent chance', 'odds'],
    short: 'A 70% chance of El Nino means that in 10 similar situations, about 7 would end up in El Nino. It is about likelihood, not intensity.',
    body: `Seasonal forecasts are given as probabilities because the climate has a lot of chaos in it.

- 70% El Nino does not mean "a 70% strong El Nino". It means El Nino is likely, but a 30% chance of something else remains.
- 33% for each of three categories would mean "we have no idea" (all equal).
- Probabilities for impacts (for example "below-normal rain in Thailand") are always less certain than probabilities for El Nino itself, because many other things affect local weather.`,
    related: ['iri_plume', 'forecast_uncertainty', 'teleconnections'],
    sources: [SRC.iri, SRC.climFaq],
  },
  jma_outlook: {
    title: 'JMA El Nino outlook (Japan)',
    category: 'forecasts',
    aliases: ['JMA', 'Japan Meteorological Agency', 'NINO.3'],
    short: 'The Japan Meteorological Agency\'s monthly ENSO assessment and 6-month outlook. JMA defines El Nino with the Nino 3 region, not Nino 3.4.',
    body: `JMA's Tokyo Climate Center publishes a monthly El Nino outlook. Its definition differs from NOAA's:

- Region: [[nino3|NINO.3]] (5° N-5° S, 150° W-90° W).
- Rule: the 5-month running mean of the NINO.3 SST deviation stays at +0.5 °C or more for 6 consecutive months or longer.
- The deviation is measured from a sliding 30-year normal.

So JMA and NOAA can declare the start or end of an event a month or two apart. That is normal: they use different yardsticks.`,
    related: ['nino3', 'cpc_alert_system', 'sources_disagree'],
    sources: [SRC.jma, SRC.jmaDef],
  },
  wmo_update: {
    title: 'WMO El Nino/La Nina Update',
    category: 'forecasts',
    aliases: ['WMO', 'World Meteorological Organization'],
    short: 'A consensus bulletin from the World Meteorological Organization, normally every three months, with the chances of El Nino, neutral and La Nina.',
    body: `The WMO combines forecasts from its Global Producing Centres for seasonal prediction and other major centres, plus expert judgement, into one bulletin. It is issued every three months, with extra updates when things change fast.

It gives probabilities rather than a single number, and it is what many national weather services (including in Southeast Asia) refer to.`,
    related: ['cpc_alert_system', 'iri_plume'],
    sources: [SRC.wmo],
  },
  forecast_uncertainty: {
    title: 'Forecast uncertainty and the spring barrier',
    category: 'forecasts',
    aliases: ['spring predictability barrier', 'reliability', 'forecast skill', 'how reliable'],
    short: 'ENSO forecasts made in the northern spring (March-May) are much less reliable. From mid-year, forecasts for the coming winter peak become quite skilful.',
    body: `ENSO forecasts have a weak spot every year, called the **spring predictability barrier**. Forecasts that cross the northern spring (March to May) are much less accurate.

Why (NOAA Climate.gov):

- Spring is a transition time: events decay after their winter peak, pass through neutral, or start to form.
- The ocean and atmosphere are only weakly coupled then, because the temperature contrasts across the Pacific are smallest.
- In short: the signal is small and the noise is large.

After spring, skill improves. Using July-August data, models predict about three-quarters of the winter ENSO ups and downs.

Rules of thumb:

- A forecast made in September for December is fairly reliable.
- A forecast for next May to July is much less reliable, whoever makes it.
- Forecasts of local impacts (rain on Samui) are less certain than forecasts of Nino 3.4.`,
    whyItMatters: 'Forecasts for how the 2026 El Nino peaks around the end of 2026 are fairly solid now. Forecasts for when it ends in mid-2027 will stay uncertain until spring 2027.',
    related: ['iri_plume', 'enso_lifecycle', 'probability'],
    sources: [SRC.climSpring],
  },
  seasonal_outlook: {
    title: 'Seasonal outlook for Samui (ECMWF SEAS5)',
    category: 'forecasts',
    aliases: ['SEAS5', 'ECMWF', 'seasonal forecast', '6-month outlook'],
    short: 'A 6-month forecast of monthly rain and temperature for Samui from the European centre\'s seasonal model, as a % of the model\'s own normal.',
    body: `The Samui page shows the ECMWF SEAS5 seasonal forecast (through Open-Meteo) for the next months. Each month shows expected rain as a percentage of the model's own normal for that month.

Seasonal models do not predict individual storms or rainy days. They predict whether a whole month is likely to be wetter or drier than usual. Coarse grid cells (tens of km) cannot resolve a small island, so treat it as a regional tendency.`,
    howToRead: 'Below 100% = drier than normal; below 80% for the next 3 months raises the water factor to at least Watch.',
    related: ['factor_water', 'forecast_uncertainty', 'model_vs_observation'],
    sources: [SRC.omSeasonal],
  },
} satisfies Record<string, TopicDef>
