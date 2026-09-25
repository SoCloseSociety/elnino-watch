import { useMemo, useState } from 'react'
import { Card } from '../ui'
import { DIMENSION_TOPIC, PLACE_COLORS, loadWeights, rankPlaces, saveWeights, type Compare } from './api'
import { PlaceTip } from './common'

export function RankingPanel({ data }: { data: Compare }) {
  const ranked = data.dimensions.filter((d) => d.rank)
  const defaults = useMemo(() => Object.fromEntries(ranked.map((d) => [d.id, 1])), [ranked])
  const [weights, setWeights] = useState<Record<string, number>>(() => ({ ...defaults, ...(loadWeights() ?? {}) }))
  const set = (id: string, v: number) => {
    const next = { ...weights, [id]: v }
    setWeights(next)
    saveWeights(next)
  }
  const reset = () => { setWeights(defaults); saveWeights(null) }
  const ids = data.places.map((p) => p.id)
  const rows = rankPlaces(data.matrix, data.dimensions, weights, ids)
  const name = (id: string) => data.places.find((p) => p.id === id)?.short_name ?? id
  const color = (id: string) => PLACE_COLORS[ids.indexOf(id) % PLACE_COLORS.length]
  const label = (id: string) => ranked.find((d) => d.id === id)?.label ?? id
  const allZero = ranked.every((d) => (weights[d.id] ?? 0) <= 0)

  return (
    <Card title="Ranking with your weights" help={<PlaceTip id="place_ranking" />} tour="places-ranking"
      right={<button type="button" className="btn !px-2.5 !py-1 !text-[12px]" onClick={reset}>Equal weights</button>}>
      <p className="mb-3 rounded-lg border p-2.5 text-[12px] text-ink-2" style={{ borderColor: 'var(--warning)' }}>
        <b style={{ color: 'var(--warning)' }}>▲ Decision aid only.</b> {data.disclaimer}
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        <fieldset className="min-w-0">
          <legend className="mb-2 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">How much does each dimension matter? (0 = ignore, 5 = very important)</legend>
          <div className="space-y-2">
            {ranked.map((d) => {
              const v = weights[d.id] ?? 1
              return (
                <label key={d.id} className="grid grid-cols-[minmax(0,9rem)_1fr_2.5rem] items-center gap-2 text-[12.5px]">
                  <span className="flex min-w-0 items-center gap-1 truncate">{d.label}<PlaceTip id={DIMENSION_TOPIC[d.id] ?? 'place_ranking'} /></span>
                  <input type="range" min={0} max={5} step={0.5} value={v} onChange={(e) => set(d.id, Number(e.target.value))}
                    aria-label={`Weight of ${d.label}`} className="w-full accent-[var(--accent)]" />
                  <span className="tnum text-right text-ink-2">{v}</span>
                </label>
              )
            })}
          </div>
          <p className="mt-2 text-[11px] text-ink-3">Weights are saved in this browser only.</p>
        </fieldset>
        <div className="min-w-0">
          <div className="mb-2 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">Result (0-100, higher = less exposed on what you weighted)</div>
          {allZero ? <p className="text-[12.5px] text-ink-3">All weights are 0: nothing to rank.</p> : (
            <ol className="space-y-2.5">
              {rows.map((r, i) => (
                <li key={r.id}>
                  <div className="flex items-center justify-between gap-2 text-[13px]">
                    <span className="font-semibold">{r.score === null ? '--' : `${i + 1}.`} {name(r.id)}</span>
                    <span className="tnum font-semibold">{r.score === null ? 'no data' : r.score.toFixed(1)}</span>
                  </div>
                  <div className="mt-1 h-2 w-full overflow-hidden rounded bg-surface-3" aria-hidden>
                    <div className="h-full rounded" style={{ width: `${r.score ?? 0}%`, background: color(r.id) }} />
                  </div>
                  {r.missing.length > 0 && (
                    <p className="mt-0.5 text-[11px]" style={{ color: 'var(--warning)' }}>
                      Left out (no data yet): {r.missing.map(label).join(', ')}. Compare with care.
                    </p>
                  )}
                </li>
              ))}
            </ol>
          )}
          <p className="mt-3 text-[11px] text-ink-3">
            Score = sum(weight x (4 - exposure)) / sum(weight x 4) x 100, over the dimensions with data. Official advisories and everything not in this data (cost of living, visas, healthcare, family) are not in the score.
          </p>
        </div>
      </div>
    </Card>
  )
}
