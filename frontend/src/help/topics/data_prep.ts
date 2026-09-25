import type { TopicDef } from '../types'
import { SRC } from './enso'

export const DATA_TOPICS = {
  sources_page: {
    title: 'The Sources page and source states',
    category: 'data',
    aliases: ['sources', 'source state', 'ok', 'empty', 'error', 'needs_config', 'needs config', 'pending'],
    short: 'Lists every data source with its state: ok, stale, empty, error, needs config or pending, plus when it last worked and how old its newest data is.',
    body: `Every number in the app comes from a named source (a "collector"). Each run of each collector is recorded, whether it works or not. The Sources page shows the result.

"Fetch ok" and "data fresh" are different things: a website can answer normally while serving data that is weeks old. That is why "stale" is shown separately from "ok".`,
    thresholds: {
      columns: ['State', 'Meaning', 'What to do'],
      rows: [
        ['ok', 'The last run worked and the newest data is within its maximum age.', 'Nothing.'],
        ['stale', 'The fetch works, but the newest data is older than its maximum age.', 'Use the values with care; check the date shown.'],
        ['empty', 'The source answered but returned nothing (for example no event in the area).', 'Often normal for alert feeds; not an error.'],
        ['error', 'The last run failed (site down, network, or the format changed).', 'Values shown are from the last good run; check the date.'],
        ['needs config', 'The source needs a key or setting that is not configured (optional paid sources).', 'Ignore unless you want that source.'],
        ['pending', 'Not run yet since the app started.', 'Wait a few minutes.'],
      ],
    },
    related: ['freshness', 'stale_data', 'data_coverage', 'sources_disagree'],
    sources: [SRC.cpcIndices],
  },
  freshness: {
    title: 'Freshness ("as of" dates)',
    category: 'data',
    aliases: ['as of', 'updated', 'age', 'last update', 'max age'],
    short: 'Every value carries the date of the data itself (not of the download) and a link to its source. Each source has a maximum age matching how often it really updates.',
    body: `Different data arrive at very different speeds:

- Disaster alerts (GDACS): every few minutes.
- Weather forecasts (Open-Meteo): several times a day.
- Weekly Nino SST (NOAA CPC): once a week.
- Satellite images: daily, one or more days behind.
- ERA5 observed rain for Samui: about 5 days behind.
- Monthly indices (ONI, RONI, SOI, MEI): once a month, and a 3-month mean is centred on a month that ended weeks ago.

So "as of 2026-07-15" on the ONI is normal (that is the centre of June-August), while "as of" two weeks ago on a weather forecast is a problem. The app compares each value with its source's maximum age and marks it stale when it is too old.`,
    related: ['stale_data', 'sources_page', 'running_mean'],
    sources: [SRC.cpcIndices, SRC.omEra5],
  },
  sources_disagree: {
    title: 'Why numbers disagree between sources',
    category: 'data',
    aliases: ['different numbers', 'discrepancy', 'disagree'],
    short: 'Different datasets, baselines, averaging windows, regions and update times. A difference of a few tenths of a degree between El Nino indices is normal.',
    body: `Common reasons two numbers for "the same thing" differ:

- **Different datasets**: ERSST (monthly ONI) vs OISST (weekly and daily Nino 3.4) vs MUR (map layer). They use different satellites and methods.
- **Different baselines**: 1991-2020, a sliding 30-year period, 1980-2018... (see [[climatology_baseline]]).
- **Different windows**: a day, a week, a month, 3 months, 5 months (JMA).
- **Different regions**: Nino 3 (JMA) vs Nino 3.4 (NOAA).
- **Different scales**: NOAA SOI vs BoM SOI (about 10 times larger); Thai AQI vs US AQI.
- **Model vs measurement**: a model estimate (CAMS, ERA5, forecasts) vs a station or buoy.
- **Timing**: one source already includes last week, another does not yet.
- **Revisions**: recent ONI and RONI values can change for up to two months.

When sources disagree, look at the direction they share (all warming? all dry?) rather than one exact number.`,
    related: ['time_resolution', 'bom_soi', 'aqi', 'model_vs_observation', 'jma_outlook'],
    sources: [SRC.ucarNino, SRC.cpcOni],
  },
  model_vs_observation: {
    title: 'Model vs observation',
    category: 'data',
    aliases: ['model', 'observation', 'forecast vs measured', 'reanalysis'],
    short: 'Some values are measured (buoys, rain gauges, satellites); many are computed by models (forecasts, CAMS air quality, ERA5). Models cover everywhere but can be wrong locally.',
    body: `Three kinds of data in this app:

- **Observations**: measured by an instrument (TAO buoys, island rain gauges, satellite SST). Real, but only where and when the instrument is.
- **Reanalysis** ([[era5|ERA5]]): past weather rebuilt by combining millions of observations with a weather model. Complete and consistent, but smoothed over about 25 km cells, so it can under-estimate local downpours on a small island.
- **Forecasts and model analyses** (Open-Meteo weather and marine, [[cams|CAMS]] air quality, ECMWF seasonal): computed. Excellent for trends and warnings, less exact for one spot and one hour.

Samui is small compared with most model grid cells, so treat model values as "the area around Samui".`,
    related: ['era5', 'cams', 'open_meteo', 'sources_disagree'],
    sources: [SRC.omEra5, SRC.omForecast, SRC.omAir],
  },
  era5: {
    title: 'ERA5 reanalysis',
    category: 'data',
    aliases: ['ERA5', 'reanalysis', 'ECMWF'],
    short: 'A global reconstruction of past weather by the European centre (ECMWF), about 25 km resolution, available with about 5 days delay. Used for Samui\'s observed rain and its 1991-2020 normals.',
    body: `ERA5 combines weather stations, aircraft, buoys, radar and satellite observations with a weather model to estimate the weather everywhere, every hour, from 1940 to about 5 days ago (served here through Open-Meteo).

The app uses it for the Samui rain totals (30/60/90/180 days) and for the 1991-2020 normals they are compared with. Comparing ERA5 with ERA5 keeps the comparison fair, even if ERA5 misses some local extremes.`,
    related: ['rain_vs_normal', 'model_vs_observation', 'climatology_baseline'],
    sources: [SRC.omEra5],
  },
  cams: {
    title: 'CAMS air quality model',
    category: 'data',
    aliases: ['CAMS', 'Copernicus Atmosphere Monitoring Service'],
    short: 'The European Copernicus model that forecasts air pollution worldwide (about 45 km globally). The app\'s PM2.5 for Samui comes from it, not from a local station.',
    body: `CAMS (Copernicus Atmosphere Monitoring Service) simulates smoke, dust and pollution around the world and forecasts it several days ahead. Globally its grid is about 0.4° (about 45 km).

Good at: seeing a regional haze episode coming. Weak at: local sources (a nearby fire, traffic). Compare with the Thai Pollution Control Department stations on Air4Thai.`,
    related: ['pm25', 'factor_air', 'model_vs_observation'],
    sources: [SRC.omAir, SRC.air4thai],
  },
  open_meteo: {
    title: 'Open-Meteo forecasts',
    category: 'data',
    aliases: ['Open-Meteo', 'forecast', 'weather forecast'],
    short: 'A free service that serves forecasts from national weather models (ECMWF, DWD ICON, NOAA GFS...), choosing the best model for each place. Used for Samui\'s weather, waves, air and seasonal outlook.',
    body: `Open-Meteo gathers model output from national weather services and serves it through one interface. For Samui the app uses:

- the "best match" weather forecast (16 days) for temperature, feels-like, rain, gusts and UV;
- the marine forecast for waves;
- the air quality forecast (CAMS);
- the ERA5 archive for the past;
- the ECMWF SEAS5 seasonal forecast.

These are model values. The first 2-3 days of a forecast are much more reliable than days 7-16.`,
    related: ['model_vs_observation', 'era5', 'cams', 'seasonal_outlook'],
    sources: [SRC.omForecast, SRC.omMarine],
  },
  news_signals: {
    title: 'News and social signals',
    category: 'data',
    aliases: ['news', 'social media', 'posts', 'GDELT', 'Bluesky', 'Mastodon', 'Reddit'],
    short: 'Articles and posts collected from news search, agency feeds and public social networks. Useful for local, early reports; unreliable as measurements, so they carry little weight.',
    body: `The News page gathers official bulletins, press articles and public posts about El Nino and about Samui/Thailand. Titles stay in their original language.

Why low weight in the risk level:

- Articles repeat each other; one event can produce dozens of stories.
- Old stories get re-shared.
- Keyword matching cannot tell "no water shortage expected" from "water shortage".
- Posts can be rumours.

What they are good for: local, human reports (a village without water, a road flooded, ferries stopped) that no dataset captures. Always check them against official sources (TMD, PWA, DDPM, ferry operators).`,
    related: ['factor_news', 'limitations', 'sources_page'],
    sources: [SRC.tmd],
  },
  limitations: {
    title: 'Limitations and disclaimer',
    category: 'data',
    aliases: ['disclaimer', 'not official', 'limits'],
    short: 'This is a personal monitoring tool, not an official warning service. For warnings and evacuation orders, follow the TMD and the DDPM (hotline 1784) and local authorities.',
    body: `What this dashboard is: a place that gathers public data about El Nino and about Koh Samui, and explains it with transparent rules.

What it is not:

- **Not an official warning service.** It does not replace the Thai Meteorological Department (TMD, hotline 1182), the Department of Disaster Prevention and Mitigation (DDPM, hotline 1784), the province, the PWA or the ferry operators.
- **Not a forecast of its own.** It relays forecasts from others, and they can be wrong.
- **Not complete.** Some things are not tracked automatically (island reservoir levels, the PWA rotation schedule, ferry timetables). Sources can fail; when they do, the app says so.
- **Not medical advice.**

The risk thresholds are the app's own choices, based on official scales (TMD rain classes, Thai PCD PM2.5 bands, heat index bands, Beaufort, NOAA Coral Reef Watch) and documented on this page. They are a planning aid.

If official instructions and this app disagree, follow the official instructions.`,
    related: ['risk_levels', 'sources_page', 'news_signals'],
    sources: [SRC.tmd, SRC.ddpm],
  },
} satisfies Record<string, TopicDef>

export const PREP_TOPICS = {
  preparedness: {
    title: 'Why prepare on an island',
    category: 'prep',
    aliases: ['preparedness', 'prepare', 'checklist', 'self-sufficiency'],
    short: 'On an island, a problem on the mainland or at sea can cut supplies for days. A strong El Nino plus the monsoon means drought, heat, haze, floods and rough seas can all happen within a year.',
    body: `Why the Preparedness page matters more on Samui than in a city on the mainland:

- Almost everything arrives by ferry. Rough seas (common in the northeast monsoon) stop the ferries.
- The water system was already rationed in August 2026, before the El Nino peak.
- Power cuts come with storms and with heat waves (air conditioning demand).
- When everyone reacts at once, shops, ATMs, fuel stations and flights run out.

The page sizes a stock for your household (adults, children, days) and tracks what you already have. The categories follow the hazards: water, food, power, health, heat, haze, flood/storm, communication, money, departure plan, documents, home and pets.`,
    related: ['prep_water', 'prep_food', 'prep_power', 'prep_exit', 'risk_levels'],
    sources: [SRC.readyKit, SRC.redcrossKit],
  },
  prep_water: {
    title: 'Preparedness: water',
    category: 'prep',
    aliases: ['water stock', 'drinking water', 'litres per person'],
    short: 'Water is the first El Nino risk on Samui. WHO: 2.5-3 L per person per day just to survive (drinking and food), 7.5-15 L for basic needs. In the heat, drinking needs rise.',
    body: `Why: Samui's reservoirs are small, the mainland pipeline covers under half of demand (see [[samui_water_supply]]), and a strong El Nino raises the odds of a long, hot dry season.

Reference amounts (WHO Technical Note 9): survival needs of 2.5-3 L per person per day (drinking and food); basic hygiene 2-6 L; basic cooking 3-6 L; total basic needs 7.5-15 L. FEMA advises at least 1 gallon (3.8 L) per person per day, and notes that needs can double in hot climates.

Keep a sealed drinking stock, keep the house tank full and clean, and know how to treat water (boiling for 1 minute, or unscented household bleach at the dose on Ready.gov).`,
    related: ['samui_water_supply', 'factor_water', 'preparedness'],
    sources: [SRC.whoWater, SRC.readyWater],
  },
  prep_food: {
    title: 'Preparedness: food',
    category: 'prep',
    aliases: ['food stock'],
    short: 'If ferries stop or the power goes out, island supermarkets empty quickly. Keep food that needs no cooking and little water.',
    body: `A stock of non-perishable food that can be eaten without cooking (canned food, crackers, nuts, dried fruit, ready meals) covers ferry stoppages and power cuts. Choose food that does not need much water to prepare, and rotate it so it does not expire.`,
    related: ['preparedness', 'wave_height'],
    sources: [SRC.readyKit, SRC.redcrossKit],
  },
  prep_power: {
    title: 'Preparedness: power cuts',
    category: 'prep',
    aliases: ['power', 'electricity', 'blackout'],
    short: 'Monsoon storms and heat waves cause outages. Without power: no fan or air conditioning, no pump for the house tank, no phone charging.',
    body: `Keep power banks charged, headlamps and spare batteries, and a battery-powered fan for hot nights. If you have a generator or solar panel, test it. Remember that many houses need electricity to pump water from the tank.`,
    related: ['prep_heat', 'prep_comms', 'preparedness'],
    sources: [SRC.readyKit],
  },
  prep_health: {
    title: 'Preparedness: health (dengue, medicine)',
    category: 'prep',
    aliases: ['health', 'dengue', 'mosquitoes', 'medication'],
    short: 'Heat, doubtful water and dengue (more mosquitoes with heat and rain) are the main health risks. Keep 30 days of prescription medicine.',
    body: `- **Dengue** is spread by Aedes mosquitoes, which breed in standing water (including stored water, so cover tanks and containers). Use repellent and nets. The WHO advises paracetamol for pain and fever, and avoiding ibuprofen and aspirin (bleeding risk).
- **Water**: stored or trucked water can be contaminated; treat it if unsure.
- **Medication**: keep at least 30 days of prescriptions, with the prescriptions themselves.
- **Heat**: see [[prep_heat]].`,
    related: ['prep_heat', 'prep_water'],
    sources: [SRC.whoDengue],
  },
  prep_heat: {
    title: 'Preparedness: heat',
    category: 'prep',
    aliases: ['heat stroke', 'heatstroke', 'ORS'],
    short: 'El Nino likely makes March-May 2027 hotter. Above 41 °C feels-like, heat stroke is possible. Plan cool rest, water, oral rehydration salts, and a fan that works without mains power.',
    body: `Avoid exertion between 11:00 and 16:00, drink regularly, use oral rehydration salts (ORS), and check on older people, children and anyone ill. Signs of heat stroke (confusion, hot and red skin that may be dry or damp, fainting) are an emergency: call 1669.`,
    related: ['heat_index', 'factor_heat', 'prep_power'],
    sources: [SRC.nwsHeat],
  },
  prep_haze: {
    title: 'Preparedness: haze',
    category: 'prep',
    aliases: ['masks', 'N95', 'air purifier'],
    short: 'In El Nino years, fire haze from Indonesia and Malaysia can reach southern Thailand. N95/KN95 masks and one room with a HEPA purifier protect the most.',
    body: `Keep N95 or KN95 masks (not surgical masks) and, if possible, a HEPA air purifier for one room with the windows closed. Check [[pm25|PM2.5]] and [[asmc_haze|ASMC alerts]] when the sky looks hazy.`,
    related: ['factor_air', 'pm25', 'asmc_haze'],
    sources: [SRC.asmcAlerts, SRC.air4thai],
  },
  prep_flood: {
    title: 'Preparedness: flood and storm',
    category: 'prep',
    aliases: ['flood', 'storm', 'landslide'],
    short: 'The northeast monsoon (October-December) brings Samui\'s heaviest rain, El Nino or not. Keep documents and electronics high and dry; never cross moving water.',
    body: `Heavy rain on saturated ground floods low roads and can trigger landslides on slopes. Before a storm: tie down or bring in anything that can fly, prepare tarps and rope, charge everything, and follow the TMD and the DDPM (1784). During: avoid flooded roads and slopes; never walk or drive through moving water.`,
    related: ['factor_flood', 'factor_cyclone_wind', 'samui_seasons'],
    sources: [SRC.tmd, SRC.ddpm],
  },
  prep_comms: {
    title: 'Preparedness: communication',
    category: 'prep',
    aliases: ['phone', 'communication', 'radio'],
    short: 'Cell towers go down when the power is out for long. Write key numbers on paper and agree a plan with someone off the island.',
    body: `Keep emergency numbers written down (police 191, ambulance 1669, fire 199, tourist police 1155, DDPM 1784, TMD 1182), a charged phone and power bank, offline maps, and a contact off the island who knows your plan.`,
    related: ['prep_power', 'prep_exit'],
    sources: [SRC.ddpm],
  },
  prep_money: {
    title: 'Preparedness: money',
    category: 'prep',
    aliases: ['cash', 'money', 'ATM'],
    short: 'Without power or network, cards and ATMs stop working, and ATMs empty fast when everyone leaves. Keep some cash in baht.',
    body: `Keep cash in baht for several days of essentials and for a ticket, plus two cards from different banks.`,
    related: ['prep_exit', 'prep_power'],
    sources: [SRC.readyKit],
  },
  prep_exit: {
    title: 'Preparedness: departure plan',
    category: 'prep',
    aliases: ['go-bag', 'departure plan', 'leave'],
    short: 'The island can only be left by ferry, boat or plane. When seas exceed about 2 m, crossings are cut. Decide in advance what would make you leave, and keep a go-bag ready.',
    body: `Decide your trigger in advance (for example: water cut for more than 3 days, or level Act with the sea about to close). Keep a go-bag with documents, medicine, cash, a day of water and food, a headlamp and rain gear. See the [[exit_plan]] for routes and departure windows.`,
    related: ['exit_plan', 'departure_windows', 'prep_documents'],
    sources: [SRC.ddpm],
  },
  prep_documents: {
    title: 'Preparedness: documents',
    category: 'prep',
    aliases: ['passport', 'visa', 'insurance', 'documents'],
    short: 'A rushed departure or a flood leaves no time to look for papers. Keep passport, visa papers and insurance in a waterproof bag, with copies online.',
    body: `Passport, visa or extension papers, insurance policy with its emergency hotline, and prescriptions: originals in a dry bag in one place, copies stored online.`,
    related: ['prep_exit'],
    sources: [SRC.redcrossKit],
  },
  prep_home_pets: {
    title: 'Preparedness: home and pets',
    category: 'prep',
    aliases: ['home', 'pets', 'house'],
    short: 'Preparing the house limits damage; pets are not always accepted on ferries or planes, so check the rules before you need them.',
    body: `Know how to shut off the water valve, the main breaker and the gas bottle. Keep valuables high in flood-prone houses. For pets: carrier, vaccination record and food, and check ferry and airline rules for animals in advance.`,
    related: ['prep_exit', 'prep_flood'],
    sources: [SRC.readyKit],
  },
} satisfies Record<string, TopicDef>
