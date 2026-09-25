/** Types of the in-app help system (topics, page guides, tours). */

export type TopicCategory =
  | 'enso' // how El Nino works
  | 'indices' // the numbers that measure it
  | 'forecasts' // outlooks and official bulletins
  | 'ocean' // maritime and marine data
  | 'hazards' // disaster and hazard feeds
  | 'layers' // satellite map layers
  | 'samui' // the Koh Samui watch and risk engine
  | 'data' // trust, freshness, sources
  | 'prep' // preparedness

export const CATEGORY_LABELS: Record<TopicCategory, string> = {
  enso: 'El Nino basics',
  indices: 'Indices',
  forecasts: 'Forecasts and bulletins',
  ocean: 'Ocean',
  hazards: 'Hazards',
  layers: 'Map layers',
  samui: 'Koh Samui watch',
  data: 'Data and trust',
  prep: 'Preparedness',
}

export interface HelpSource {
  title: string
  url: string
}

/** A small table (thresholds, levels, categories). Cells are plain text. */
export interface ThresholdTable {
  columns: string[]
  rows: string[][]
  note?: string
}

/**
 * One help topic. Text fields use "markdown-lite" (see Markdown.tsx):
 * blank line = new paragraph, "- " = bullet, "**bold**", "[text](https://...)",
 * "[[topic_id]]" or "[[topic_id|label]]" = link to another topic.
 */
export interface TopicDef {
  title: string
  category: TopicCategory
  /** 1-2 sentences, used in tooltips. Plain text (no markdown). */
  short: string
  /** Plain-English explanation. */
  body: string
  /** How to read the number / chart / map colours. */
  howToRead?: string
  /** Why it matters, for Koh Samui where relevant. */
  whyItMatters?: string
  thresholds?: ThresholdTable
  example?: string
  related: string[]
  sources: HelpSource[]
  /** Extra search words for the glossary (abbreviations, synonyms). */
  aliases?: string[]
}

export interface Topic extends TopicDef {
  id: string
}

export type PageId = 'overview' | 'map' | 'indices' | 'news' | 'samui' | 'history' | 'prep' | 'sources' | 'places' | 'cams'

export interface PageGuideDef {
  page: PageId
  title: string
  intro: string
  steps: string[]
  topics: string[]
}

export interface TourStep {
  /** value of the `data-tour` attribute of the element to spotlight */
  target: string
  title: string
  body: string
  /** optional topic id: the step shows a "Learn more" link */
  topic?: string
}
