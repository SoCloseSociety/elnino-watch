import { AsOf, Card } from '../ui'
import { fmtDate, strength } from '../../lib/format'
import type { EnsoNow, PlaceDetail } from './api'
import { ExposureChip, PlaceTip, signed } from './common'

export function EnsoPanel({ places, now }: { places: PlaceDetail[]; now: EnsoNow | null }) {
  const idx = now?.roni ?? now?.oni ?? null
  const st = strength(idx?.value ?? null)
  const top = now?.iri_probabilities?.[0]
  return (
    <Card title="El Nino sensitivity per place" help={<PlaceTip id="place_enso" />} tour="places-enso"
      footer={idx ? <AsOf ts={idx.ts} source={`NOAA CPC ${now?.roni ? 'RONI' : 'ONI'}`} href="https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/" kind="observed" /> : null}>
      <p className="text-[13px] text-ink-2">
        Now: {idx ? <><b className="text-ink">{st.label}</b> ({now?.roni ? 'RONI' : 'ONI'} {signed(idx.value, 2)} °C, {fmtDate(idx.ts)})</> : 'ENSO index not collected yet'}
        {now?.cpc_status ? <>; NOAA status: <b className="text-ink">{now.cpc_status}</b></> : null}
        {top ? <>; IRI {top.season}: El Nino {Math.round(top.el_nino)}%</> : null}.
        {' '}How much that matters depends on the place:
      </p>
      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {places.map((p) => (
          <div key={p.id} className="rounded-lg border border-line bg-surface-2 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <b className="text-[13px]">{p.short_name}</b>
              <span className="flex items-center gap-1.5 text-[12px] text-ink-2">{p.enso.strength_label}<ExposureChip score={p.enso.strength} compact /></span>
            </div>
            {p.enso.region_label && <p className="mt-0.5 text-[11px] text-ink-3">{p.enso.region_label}</p>}
            <p className="mt-1.5 text-[12.5px] text-ink-2">{p.enso.mechanism}</p>
            {p.enso.el_nino_effect && <p className="mt-1.5 text-[12.5px] text-ink-2"><b className="text-ink">Usual El Nino effect:</b> {p.enso.el_nino_effect}</p>}
            {p.enso.outlook_2026_27 && <p className="mt-1.5 text-[12.5px] text-ink-2"><b className="text-ink">2026-27:</b> {p.enso.outlook_2026_27}</p>}
            <ul className="mt-2 space-y-0.5 text-[11.5px]">
              {p.enso.sources.map((s) => <li key={s.url}><a className="link" href={s.url} target="_blank" rel="noreferrer">{s.title} ↗</a></li>)}
            </ul>
          </div>
        ))}
      </div>
    </Card>
  )
}
