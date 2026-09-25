# Data gap alert

id: alert_data_gap
short: An alert sent when the island level has been Unknown for more than 6 hours.

## What it is
After each evaluation, if critical data has been missing for over 6 hours, one 'data gap' alert per day is stored and sent (Telegram / webhook, if configured).

## How to read it
It lists the missing factors. Until it clears, check the TMD warnings and the ferry operators yourself.

## Why it matters for Koh Samui
A silent outage during the monsoon or a cyclone would look like 'nothing to report'. This alert makes the silence visible.

## Limits
Short gaps (under 6 hours) do not alert, to avoid noise from brief source outages.

## Sources
- https://www.tmd.go.th/en/warning-and-events/warning-storm
