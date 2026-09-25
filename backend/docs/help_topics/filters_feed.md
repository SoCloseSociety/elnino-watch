# News and posts filters

id: filters_feed
short: Narrow the feed by type, source, language, tag, date, location or text; chips show how many items each choice has.

## What it is
Server-side filters on the news / social / official feed: kind (official, news,
social, research), source, language, tag (enso, drought, flood, storm, heat, haze,
bleaching, thailand, samui, ...), a text search, a date range, and "has a map
location". Several values can be picked in each filter.

## How to read it
- Within one filter, items matching ANY chosen value are shown (e.g. tags samui OR flood).
- Different filters combine with AND (e.g. kind = news AND language = th).
- The number on each chip is how many items you would get by adding that value,
  given your other filters.
- Dates are the publication date, or the date we fetched the item when the source
  gives none.

## Why it matters for Koh Samui
The feed mixes agencies, press and social media in many languages. Filtering to
"official" or to the "samui" tag separates what agencies say from noise.

## Limits
Tags come from keyword matching on titles and summaries, so an article can be missed
or mis-tagged. Map positions of news are approximate (place named in the text, else
the publisher's country). News and social items older than 180 days are removed.

## Sources
- GDELT news search (one of the feed sources): https://www.gdeltproject.org/
