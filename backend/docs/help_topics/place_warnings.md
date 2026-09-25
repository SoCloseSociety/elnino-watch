# Official weather warnings per place
id: place_warnings
short: France: Meteo-France vigilance via Meteoalarm (yellow, orange, red). Russia: the Hydrometcenter daily bulletin of dangerous weather. Thailand: TMD bulletins.
category: hazards
related: tmd_warnings, place_levels
aliases: warnings, vigilance, Meteoalarm, Roshydromet, TMD

## What it is

- **France (Calvados)**: Meteo-France publishes its vigilance to Meteoalarm (EUMETNET), read here without a key. An empty feed means no yellow, orange or red warning (green). The Meteo-France API itself needs a key, so it is not used.
- **Russia (Vladimir Oblast)**: the Hydrometcenter of Russia bulletin lists dangerous and adverse weather by federal district. The page shows the sentences that name the region (in Russian, as published). Keyword rule: named = Watch; named with wording such as "very heavy", "hurricane", "severe frost" = Prepare.
- **Thailand (Maenam)**: TMD bulletins for the Gulf side / Surat Thani, collected by the Koh Samui watch.

Always follow the national service when it issues a warning.

## How to read it

Columns: Warning | Factor level

- green / none / region not named | 0 Normal
- yellow / region named | 1 Watch
- orange / severe wording / TMD heavy rain, waves, storm | 2 Prepare
- red | 3 Act

## Why it matters for Koh Samui

Official warnings are the reference for immediate danger; this page only relays them.

## Sources

- [Meteoalarm (EUMETNET) -- European weather warnings](https://meteoalarm.org/)
- [Meteo-France -- Vigilance, Calvados](https://vigilance.meteofrance.fr/fr/calvados)
- [Hydrometcenter of Russia -- bulletin of dangerous weather (in Russian)](https://meteoinfo.ru/hazardsbull)
