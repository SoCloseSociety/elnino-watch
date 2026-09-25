#!/usr/bin/env node
/**
 * Converts the backend-written help topics (backend/docs/help_topics/*.md) into
 * src/help/topics/backend.ts so they join the help registry (HelpTip, drawer, Learn).
 *
 *   npm run help:import        (also runs before every `npm run build`)
 *
 * Markdown format (one file per topic):
 *   # Title
 *   id: some_id
 *   short: One or two sentences.
 *   category: samui            (optional; otherwise inferred from the id)
 *   related: a, b              (optional)
 *   ## What it is / ## How to read it / ## Why it matters for Koh Samui / ## Limits / ## Sources
 * Ids that already exist in the frontend topics are skipped (the frontend text wins) and
 * listed in BACKEND_SKIPPED.
 */
import { readdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const SRC_DIR = join(here, '..', '..', 'backend', 'docs', 'help_topics')
const OUT = join(here, '..', 'src', 'help', 'topics', 'backend.ts')
const TOPICS_DIR = join(here, '..', 'src', 'help', 'topics')

const CATS = ['enso', 'indices', 'forecasts', 'ocean', 'hazards', 'layers', 'samui', 'data', 'prep']

function inferCategory(id) {
  if (/^(exit_|local_|alert_)/.test(id)) return 'samui'
  if (/^event_category_/.test(id)) return 'hazards'
  if (/^series_/.test(id)) return 'indices'
  if (/^status_/.test(id)) return 'forecasts'
  if (/^webcams/.test(id)) return 'ocean'
  if (/^source_(jma_typhoons|jtwc|ptwc|usgs|reliefweb)/.test(id)) return 'hazards'
  if (/^source_(air4thai|pwa_)/.test(id)) return 'samui'
  if (/^source_(cpc_enso_probs|asmc_seasonal)/.test(id)) return 'forecasts'
  return 'data'
}

/** Frontend topic ids (keys of the other topic files), so backend duplicates are skipped. */
function frontendIds() {
  const ids = new Set()
  for (const f of readdirSync(TOPICS_DIR)) {
    if (!f.endsWith('.ts') || f === 'backend.ts') continue
    const txt = readFileSync(join(TOPICS_DIR, f), 'utf8')
    for (const m of txt.matchAll(/^ {2}([a-z0-9_]+): \{/gm)) ids.add(m[1])
  }
  return ids
}

const clean = (s) => s.replace(/—/g, '--').replace(/–/g, '-').replace(/\r/g, '')

/** Join wrapped lines: keep blank lines (paragraphs) and "- " bullets. */
function reflow(lines) {
  const out = []
  for (const raw of lines) {
    const line = raw.replace(/\s+$/, '')
    if (!line.trim()) { if (out.length && out[out.length - 1] !== '') out.push(''); continue }
    const isBullet = /^\s*[-*] /.test(line)
    const prev = out[out.length - 1]
    if (!isBullet && prev !== undefined && prev !== '') out[out.length - 1] = `${prev} ${line.trim()}`
    else out.push(isBullet ? line.replace(/^(\s*)\* /, '$1- ') : line.trim())
  }
  while (out.length && out[out.length - 1] === '') out.pop()
  return out.join('\n')
}

function parse(file) {
  const txt = clean(readFileSync(join(SRC_DIR, file), 'utf8'))
  const lines = txt.split('\n')
  let title = ''
  const meta = {}
  const sections = {}
  let cur = null
  for (const line of lines) {
    const h1 = line.match(/^# (.+)/)
    const h2 = line.match(/^## (.+)/)
    if (h1 && !title) { title = h1[1].trim(); continue }
    if (h2) { cur = h2[1].trim().toLowerCase(); sections[cur] = []; continue }
    if (!cur) {
      const m = line.match(/^([a-z_]+):\s*(.*)$/)
      if (m) meta[m[1]] = m[2].trim()
      continue
    }
    sections[cur].push(line)
  }
  const id = meta.id || file.replace(/\.md$/, '')
  const pick = (...names) => {
    for (const n of names) for (const k of Object.keys(sections)) if (k.startsWith(n)) return reflow(sections[k])
    return ''
  }
  const what = pick('what it is')
  const how = pick('how to read')
  const why = pick('why it matters')
  const limits = pick('limits', 'limitations')
  const sources = []
  const srcNotes = []
  for (const l of reflow(sections.sources ?? []).split('\n')) {
    const s = l.replace(/^\s*- /, '').trim()
    if (!s) continue
    const md = s.match(/^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/)
    const tu = s.match(/^(.*?):?\s*(https?:\/\/\S+)\s*$/)
    if (md) sources.push({ title: md[1], url: md[2] })
    else if (tu) {
      let t = tu[1].replace(/[:\s]+$/, '').trim()
      if (!t) { try { t = new URL(tu[2]).host.replace(/^www\./, '') } catch { t = tu[2] } }
      sources.push({ title: t, url: tu[2] })
    } else srcNotes.push(s)
  }
  let body = what || meta.short || ''
  if (limits) body += `\n\n**Limits.** ${limits.includes('\n') ? `\n\n${limits}` : limits}`
  if (srcNotes.length) body += `\n\n${srcNotes.map((n) => `- ${n}`).join('\n')}`
  const category = CATS.includes(meta.category) ? meta.category : inferCategory(id)
  const related = (meta.related ?? '').split(/[,\s]+/).filter(Boolean)
  const aliases = (meta.aliases ?? '').split(/,\s*/).filter(Boolean)
  return {
    id,
    def: {
      title: title || id,
      category,
      short: (meta.short || what.split('\n')[0] || title).replace(/\*\*/g, ''),
      body,
      ...(how ? { howToRead: how } : {}),
      ...(why ? { whyItMatters: why } : {}),
      related,
      sources,
      ...(aliases.length ? { aliases } : {}),
    },
  }
}

if (!existsSync(SRC_DIR)) {
  console.error(`help:import: ${SRC_DIR} not found, keeping the existing backend.ts`)
  process.exit(0)
}
const fe = frontendIds()
const files = readdirSync(SRC_DIR).filter((f) => f.endsWith('.md')).sort()
const topics = {}
const skipped = []
for (const f of files) {
  const { id, def } = parse(f)
  if (!/^[a-z0-9_]+$/.test(id)) { skipped.push(`${id} (invalid id, ${f})`); continue }
  if (fe.has(id)) { skipped.push(id); continue }
  topics[id] = def
}

const header = `/**
 * GENERATED by scripts/import-help-topics.mjs from backend/docs/help_topics/*.md
 * (${files.length} files, ${Object.keys(topics).length} imported). Do not edit by hand: edit the .md file
 * and run \`npm run help:import\` (it also runs before \`npm run build\`).
 */
import type { TopicDef } from '../types'

`
const body = `export const BACKEND_TOPICS = ${JSON.stringify(topics, null, 2)} satisfies Record<string, TopicDef>

/** Backend topics not imported because the frontend already defines the same id (frontend text wins). */
export const BACKEND_SKIPPED: string[] = ${JSON.stringify(skipped)}
`
writeFileSync(OUT, header + body)
console.log(`help:import: ${Object.keys(topics).length} topics imported, ${skipped.length} skipped (${skipped.join(', ') || 'none'}) -> src/help/topics/backend.ts`)
