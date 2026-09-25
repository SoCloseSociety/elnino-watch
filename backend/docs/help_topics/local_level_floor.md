# 'At least' level (level floor)

id: local_level_floor
short: The lowest level the island can be at, computed from the factors that do have data.

## What it is
`level_floor` applies the same rules as the full level (maximum of the factors, compound hazards, 'leave' rules) to the factors that are known.

## How to read it
Read 'At least Prepare (El Nino)' as: even without the missing data, you should already be at 'Prepare'. The real level may be higher, never lower. Actions and triggers shown while the level is Unknown are based on this floor.

## Why it matters for Koh Samui
During a strong El Nino some signals (the event itself, a cyclone report) arrive even when a local weather feed is down: the floor keeps them useful.

## Limits
The floor can hide a higher real level if the missing factor is the dangerous one (for example, no wave data during a storm).

## Sources
- https://www.tmd.go.th/en/warning-and-events/warning-storm
