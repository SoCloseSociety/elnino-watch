# Data retention (what is kept, what is deleted)

id: retention
short: Official bulletins and measurements are kept; news and posts are deleted after 180 days, closed map events after 30 days.

## What it is
A daily housekeeping job. It deletes news, social and research items older than 180
days (official bulletins are kept forever), map events no source has listed for 30
days, and keeps the last 200 run records per source. Hourly buoy temperatures
(the TAO/TRITON series) older than one year are folded into one daily mean per day;
every daily and monthly series (indices, ERA5, gauges) is kept as it is. Once a week
it compacts the database file (SQLite VACUUM).

## How to read it
The status entry `maintenance` shows when it last ran, how many rows it removed and
when the file was last compacted.

## Why it matters for Koh Samui
It keeps the tracker fast and the disk small on a laptop, without losing the history
that matters: all index and measurement series and every official bulletin stay.

## Limits
Deleted news cannot be recovered from the tracker (the original article usually
still exists at its link). Daily and monthly measurement series are never pruned;
for buoy data older than a year only the hour-by-hour detail is gone (the daily mean
and the count of hours it came from stay).

## Sources
- SQLite VACUUM: https://www.sqlite.org/lang_vacuum.html
