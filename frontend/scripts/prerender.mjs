#!/usr/bin/env node
/**
 * SEO export: turns the TypeScript help content (src/help/content.ts: 110+ Learn topics,
 * the FAQ and the myths) into JSON the backend can read WITHOUT a JS runtime, so that
 * app/seo.py can server-render one indexable page per topic (/learn/<id>), the FAQPage
 * JSON-LD and the sitemap entries for crawlers that do not run JavaScript.
 *
 *   npm run seo:build          (also runs before every `npm run build`)
 *
 * Output (committed, copied into dist/ by Vite):
 *   public/seo/topics.json  {generated_at, count, categories, topics: [{id, title, category,
 *                            category_label, short, body, how_to_read, why_it_matters, example,
 *                            thresholds, related, sources, aliases}]}  (text fields = plain text)
 *   public/seo/faq.json     {generated_at, items: [{id, question, answer, answer_text, topics}]}
 *   public/seo/myths.json   {generated_at, items: [{myth, fact, topics}]}
 *
 * Bundles content.ts with esbuild (a Vite dependency, nothing new to install) and imports
 * the result: no duplicated content, the TS source stays the single source of truth.
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { build } from 'esbuild'

const here = dirname(fileURLToPath(import.meta.url))
const ENTRY = join(here, '..', 'src', 'help', 'content.ts')
const OUT_DIR = join(here, '..', 'public', 'seo')

const result = await build({
  entryPoints: [ENTRY],
  bundle: true,
  format: 'esm',
  platform: 'node',
  target: 'node20',
  write: false,
  logLevel: 'silent',
})
const code = result.outputFiles[0].text
const mod = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
const { TOPICS, FAQ, MYTHS, validateTopics } = mod

const bad = validateTopics()
if (bad.length) {
  console.error(`seo:build: help content has ${bad.length} problem(s):\n  ${bad.join('\n  ')}`)
  process.exit(1)
}

const CATEGORY_LABELS = {
  enso: 'El Nino basics', indices: 'Indices', forecasts: 'Forecasts and bulletins', ocean: 'Ocean',
  hazards: 'Hazards', layers: 'Map layers', samui: 'Koh Samui watch', data: 'Data and trust',
  prep: 'Preparedness',
}

const titleOf = (id) => TOPICS[id]?.title ?? id

/** markdown-lite -> plain text (bullets kept as "- ", paragraphs kept as blank lines). */
function plain(text) {
  if (!text) return ''
  return text
    .replace(/\[\[([a-z0-9_]+)\|([^\]]*)\]\]/g, (_, id, label) => label || titleOf(id))
    .replace(/\[\[([a-z0-9_]+)\]\]/g, (_, id) => titleOf(id))
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\u2014/g, '--')
    .replace(/[ \t]+\n/g, '\n')
    .trim()
}

const generated_at = new Date().toISOString().replace(/\.\d{3}Z$/, '+00:00')

const topics = Object.keys(TOPICS)
  .sort((a, b) => TOPICS[a].title.localeCompare(TOPICS[b].title, 'en', { sensitivity: 'base' }))
  .map((id) => {
    const t = TOPICS[id]
    return {
      id,
      title: t.title,
      category: t.category,
      category_label: CATEGORY_LABELS[t.category] ?? t.category,
      short: plain(t.short),
      body: plain(t.body),
      how_to_read: plain(t.howToRead),
      why_it_matters: plain(t.whyItMatters),
      example: plain(t.example),
      thresholds: t.thresholds ?? null,
      related: t.related.map((r) => ({ id: r, title: titleOf(r) })),
      sources: t.sources,
      aliases: t.aliases ?? [],
    }
  })

const faq = FAQ.map((f) => ({
  id: f.id,
  question: f.q,
  answer: f.a, // markdown-lite, for the SPA
  answer_text: plain(f.a), // plain text, for JSON-LD / crawlers
  topics: f.topics.map((r) => ({ id: r, title: titleOf(r) })),
}))

const myths = MYTHS.map((m) => ({
  myth: plain(m.myth), fact: plain(m.fact), topics: m.topics.map((r) => ({ id: r, title: titleOf(r) })),
}))

const counts = {}
for (const t of topics) counts[t.category] = (counts[t.category] ?? 0) + 1

mkdirSync(OUT_DIR, { recursive: true })
const dump = (name, data) => writeFileSync(join(OUT_DIR, name), JSON.stringify(data, null, 1) + '\n')
dump('topics.json', {
  generated_at, count: topics.length,
  categories: Object.entries(CATEGORY_LABELS).map(([id, label]) => ({ id, label, count: counts[id] ?? 0 })),
  topics,
})
dump('faq.json', { generated_at, items: faq })
dump('myths.json', { generated_at, items: myths })
console.log(`seo:build: ${topics.length} topics, ${faq.length} FAQ, ${myths.length} myths -> public/seo/`)
