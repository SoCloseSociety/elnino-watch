# Situation briefing (rules vs AI-polished)

id: briefing
short: A plain-English summary of ENSO, the forecast, Koh Samui's level, nearby hazards and data gaps, rebuilt every 6 hours.

## What it is
An automatic briefing assembled from the tracker's own stored data: the official ENSO
status and indices with their dates, the forecast probabilities, the Koh Samui level
and its main factors, hazards within 800 km plus major (GDACS orange/red) events
worldwide, the 5 latest official bulletins, and which sources are failing or stale.
It is rebuilt every 6 hours and immediately when the Koh Samui level changes.

## How to read it
- **method = rules**: every sentence was built by fixed rules from stored values. No AI.
- **method = llm**: the same facts were rewritten by an AI model (ComputeForge) for
  readability. The AI is told not to add anything, and its text is thrown away
  automatically if it contains any number that was not in the rules version.
- `llm_error` explains why the AI version was not used (no key, error, refusal, or a
  rejected invented number). The rules version is then shown.
- Every section lists its sources with links; dates are UTC.

## Why it matters for Koh Samui
It is the fastest way to know "what changed and does it concern us", and it always
states what it does not know (missing factors, stale sources) instead of implying
all is well.

## Limits
It summarizes; it does not forecast on its own. If a source is stale or missing, the
briefing is only as good as what remains; read the "Data gaps" section. The level
"UNKNOWN" means data is insufficient, never "safe".

## Sources
- NOAA CPC ENSO Diagnostic Discussion: https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml
- IRI ENSO forecast: https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/
- GDACS alert levels: https://www.gdacs.org/Knowledge/overview.aspx
