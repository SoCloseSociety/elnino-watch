import { Fragment, useState } from 'react'
import { AsOf, Card } from '../ui'
import { fmtDate } from '../../lib/format'
import { DIMENSION_TOPIC, EXPOSURE_COLORS, type Advisories, type Advisory, type Compare, type ContextNote, type ExposureCell } from './api'
import { ExposureChip, PlaceTip } from './common'

function valueText(c: ExposureCell): string {
  if (c.value === null || c.value === undefined) return ''
  const v = typeof c.value === 'number' ? c.value.toLocaleString('en-GB', { maximumFractionDigits: 2 }) : c.value
  return `${v}${c.unit ? ` ${c.unit}` : ''}`
}

function AdvisoryLine({ a }: { a: Advisory }) {
  const provider = a.provider.replace(' (conseils aux voyageurs)', '')
  return (
    <li className="text-[12px] leading-snug">
      <span className="font-semibold text-ink">{provider}</span>:{' '}
      <a className="link" href={a.url} target="_blank" rel="noreferrer" lang={a.lang ?? 'en'}>{a.headline ?? 'see page'} ↗</a>
      <span className="text-ink-3"> · updated {a.updated ? fmtDate(a.updated.slice(0, 10)) : 'unknown'}</span>
    </li>
  )
}

export function AdvisoryCell({ adv }: { adv: Advisories | undefined }) {
  const list = [adv?.fcdo, adv?.state, adv?.fr_diplomatie].filter(Boolean) as Advisory[]
  if (!list.length) return <span className="text-[12px] text-ink-3">No advisory collected yet.</span>
  return <ul className="space-y-1">{list.map((a) => <AdvisoryLine key={a.provider} a={a} />)}</ul>
}

export function ComparisonMatrix({ data, context }: { data: Compare; context: Record<string, ContextNote[]> }) {
  const [open, setOpen] = useState<string | null>(null)
  const places = data.places
  return (
    <Card title="Comparison matrix (long-term exposure)" help={<PlaceTip id="place_exposure_scale" />} pad={false}
      tour="places-matrix"
      footer={<AsOf ts={data.evaluated_at} source="Places engine: ERA5 1991-2020, CMIP6, USGS, CAMS, curated ENSO" label="evaluated" />}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 pt-3 text-[11px] text-ink-3" aria-label="Exposure scale">
        {data.exposure_labels.map((l, i) => (
          <span key={l} className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: EXPOSURE_COLORS[i] }} />{i} {l}
          </span>
        ))}
        <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm border border-dashed border-line-strong" />no data</span>
        <span>· higher = more exposed · tap a cell for the rule and source</span>
      </div>
      <div className="overflow-x-auto p-2 sm:p-4">
        <table className="w-full min-w-[560px] border-separate border-spacing-0 text-[12.5px]">
          <thead>
            <tr className="text-left text-ink-3">
              <th className="sticky left-0 z-10 bg-surface py-1.5 pr-2 font-medium">Dimension</th>
              {places.map((p) => <th key={p.id} className="px-2 py-1.5 font-medium">{p.short_name}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.dimensions.map((d) => (
              <Fragment key={d.id}>
                <tr className="align-top">
                  <th scope="row" className="sticky left-0 z-10 border-t border-line bg-surface py-2 pr-2 text-left font-medium text-ink">
                    <span className="flex items-center gap-1.5">{d.label}<PlaceTip id={DIMENSION_TOPIC[d.id] ?? 'place_exposure_scale'} /></span>
                    {!d.rank && <span className="block text-[10.5px] font-normal text-ink-3">not ranked</span>}
                  </th>
                  {places.map((p) => {
                    const c = data.matrix[d.id]?.[p.id]
                    const key = `${d.id}:${p.id}`
                    return (
                      <td key={p.id} className="border-t border-line px-2 py-2">
                        {c ? (
                          <button type="button" className="flex w-full flex-col items-start gap-0.5 text-left" aria-expanded={open === key}
                            onClick={() => setOpen(open === key ? null : key)} title={c.note}>
                            <ExposureChip score={c.score} label={c.label} />
                            <span className="tnum text-[11.5px] text-ink-2">{valueText(c)}</span>
                          </button>
                        ) : <ExposureChip score={null} />}
                      </td>
                    )
                  })}
                </tr>
                {places.map((p) => {
                  const key = `${d.id}:${p.id}`
                  const c = data.matrix[d.id]?.[p.id]
                  if (open !== key || !c) return null
                  const ctx = (context[p.id] ?? []).filter((x) => x.dimension === d.id)
                  return (
                    <tr key={key}>
                      <td colSpan={places.length + 1} className="bg-surface-2 px-3 py-2 text-[12px] text-ink-2">
                        <p><b className="text-ink">{p.short_name} -- {d.label}:</b> {c.note}</p>
                        {c.rule && <p className="mt-1 text-ink-3">Rule: {c.rule}</p>}
                        {ctx.map((x) => (
                          <p key={x.text} className="mt-1 text-ink-3">Sources for the context note: {x.sources.map((s, i) => (
                            <span key={s.url}>{i ? ', ' : ''}<a className="link" href={s.url} target="_blank" rel="noreferrer">{s.title} ↗</a></span>
                          ))}</p>
                        ))}
                        <AsOf className="mt-1" ts={c.as_of} source={c.source} href={c.url} label="computed" />
                      </td>
                    </tr>
                  )
                })}
              </Fragment>
            ))}
            <tr className="align-top">
              <th scope="row" className="sticky left-0 z-10 border-t-2 border-line-strong bg-surface py-2 pr-2 text-left font-medium text-ink">
                <span className="flex items-center gap-1.5">Official advisories<PlaceTip id="place_advisories" /></span>
                <span className="block text-[10.5px] font-normal text-ink-3">as published, not scored</span>
              </th>
              {places.map((p) => (
                <td key={p.id} className="border-t-2 border-line-strong px-2 py-2"><AdvisoryCell adv={data.advisories[p.id]} /></td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      {data.summary.length > 0 && (
        <div className="border-t border-line px-4 py-3">
          <h3 className="mb-1.5 flex items-center gap-1.5 text-[12px] font-semibold tracking-wide text-ink-3 uppercase">Which is better for what (facts only) <PlaceTip id="place_exposure_scale" /></h3>
          <ul className="space-y-1 text-[12.5px] text-ink-2">
            {data.summary.map((s) => <li key={s.dimension}>{s.text}</li>)}
          </ul>
        </div>
      )}
    </Card>
  )
}
