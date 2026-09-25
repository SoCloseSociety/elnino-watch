import { useState, type FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { AsOf, Card, ErrorBox } from '../ui'
import { useAccess } from '../../api/client'
import { AdminOnlyNote } from '../Admin'
import { fmtDate } from '../../lib/format'
import {
  addPlace, removePlace, searchPlaces, usePreviews,
  type GeoResult, type PlacesList,
} from './api'
import { AdvisoryCell } from './ComparisonMatrix'
import { ExposureChip, PlaceTip, fmt } from './common'

function where(g: GeoResult): string {
  return [g.admin3, g.admin2, g.admin1, g.country].filter(Boolean).join(', ')
}

export function AddPlace({ list, personal, setPersonal }: {
  list: PlacesList | null
  personal: GeoResult[]
  setPersonal: (a: GeoResult[]) => void
}) {
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [results, setResults] = useState<GeoResult[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<unknown>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const access = useAccess()
  const publicMode = access.publicMode || !!list?.public_mode
  // the server decides: private install (can_edit) or a verified admin token on the public site
  const canEditShared = access.loaded && (access.admin || (!!list?.can_edit && !access.publicMode))

  const search = async (e: FormEvent) => {
    e.preventDefault()
    if (q.trim().length < 2) return
    setBusy(true); setErr(null); setMsg(null)
    try { setResults((await searchPlaces(q.trim())).results) } catch (x) { setErr(x) } finally { setBusy(false) }
  }
  const refresh = () => qc.invalidateQueries({ queryKey: ['places'] })
  const addServer = async (g: GeoResult) => {
    setBusy(true); setErr(null)
    try {
      const r = await addPlace(g)
      setMsg(`Added ${r.place.name}. ${r.note}`)
      setResults(null)
      refresh()
    } catch (x) { setErr(x) } finally { setBusy(false) }
  }
  const addLocal = (g: GeoResult) => {
    if (personal.some((p) => Math.abs(p.latitude - g.latitude) < 0.01 && Math.abs(p.longitude - g.longitude) < 0.01)) return
    setPersonal([...personal, g])
    setMsg(`${g.name} added to your personal list (this browser only).`)
    setResults(null)
  }
  const removeServer = async (id: string) => {
    if (!window.confirm(`Remove ${id} from the shared list? Its collected data is deleted.`)) return
    setBusy(true); setErr(null)
    try { await removePlace(id); refresh() } catch (x) { setErr(x) } finally { setBusy(false) }
  }

  return (
    <Card title="Add a place" help={<PlaceTip id="place_add" />} tour="places-add">
      <form onSubmit={search} className="flex flex-wrap gap-2">
        <label className="sr-only" htmlFor="place-q">Town or village name</label>
        <input id="place-q" className="input min-w-0 flex-1" placeholder="Town or village name, e.g. Honfleur" value={q}
          onChange={(e) => setQ(e.target.value)} maxLength={80} />
        <button className="btn btn-primary" disabled={busy || q.trim().length < 2} type="submit">Search</button>
      </form>
      <p className="mt-1.5 text-[11.5px] text-ink-3">
        Search by GeoNames (Open-Meteo geocoding). Check the region: many towns share a name.
        {publicMode && !canEditShared ? ' Anyone can keep a personal list in this browser.' : ''}
      </p>
      <AdminOnlyNote what="editing the shared list" className="mt-1.5" />
      {err ? <div className="mt-2"><ErrorBox error={err} what="Places" /></div> : null}
      {msg && <p className="mt-2 text-[12.5px]" style={{ color: 'var(--good-ink)' }}>{msg}</p>}
      {results && (
        <ul className="mt-3 divide-y divide-line rounded-lg border border-line">
          {results.length === 0 && <li className="p-2.5 text-[12.5px] text-ink-3">No match.</li>}
          {results.map((g) => (
            <li key={`${g.id}-${g.latitude}`} className="flex flex-wrap items-center gap-2 p-2.5 text-[12.5px]">
              <div className="min-w-0 flex-1">
                <b>{g.name}</b> <span className="text-ink-2">{where(g)}</span>
                <div className="text-[11px] text-ink-3">{g.latitude.toFixed(4)}, {g.longitude.toFixed(4)} · {fmt(g.elevation, 0)} m · {g.timezone}{g.population ? ` · pop. ${g.population.toLocaleString('en-GB')}` : ''}</div>
              </div>
              {canEditShared && (
                <button type="button" className="btn !py-1 !text-[12px]" disabled={busy} onClick={() => addServer(g)}>Add to shared list</button>
              )}
              <button type="button" className="btn !py-1 !text-[12px]" onClick={() => addLocal(g)}>Add to my list</button>
            </li>
          ))}
        </ul>
      )}
      {list && canEditShared && (
        <details className="mt-3 text-[12.5px]">
          <summary className="cursor-pointer text-ink-2">Remove a place from the shared list</summary>
          <ul className="mt-2 flex flex-wrap gap-2">
            {list.places.map((p) => (
              <li key={p.id}><button type="button" className="btn !py-1 !text-[12px]" disabled={busy || list.places.length <= 1} onClick={() => removeServer(p.id)}>Remove {p.short_name}</button></li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  )
}

export function PersonalList({ personal, setPersonal }: { personal: GeoResult[]; setPersonal: (a: GeoResult[]) => void }) {
  const qs = usePreviews(personal)
  if (!personal.length) return null
  return (
    <Card title="My personal list (this browser only)" help={<PlaceTip id="place_add" />}>
      <p className="mb-3 text-[12px] text-ink-3">Current conditions, 7-day forecast, El Nino sensitivity and country advisories. The long-term matrix needs the place on the shared list.</p>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {personal.map((g, i) => {
          const r = qs[i]
          const d = r?.data
          return (
            <div key={`${g.latitude},${g.longitude}`} className="rounded-lg border border-dashed border-line-strong p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <b className="text-[13px]">{g.name}</b>
                  <div className="text-[11px] text-ink-3">{where(g)}</div>
                </div>
                <button type="button" className="btn !px-2 !py-0.5 !text-[11px]" onClick={() => setPersonal(personal.filter((x) => x !== g))} aria-label={`Remove ${g.name} from my list`}>Remove</button>
              </div>
              {r?.isLoading && <p className="mt-2 text-[12px] text-ink-3">Loading...</p>}
              {r?.error ? <div className="mt-2"><ErrorBox error={r.error} what={g.name} /></div> : null}
              {d && (
                <>
                  <p className="mt-2 text-[13px]"><b className="tnum">{fmt(d.current.temperature_2m, 1)} °C</b> <span className="text-ink-2">feels {fmt(d.current.apparent_temperature, 1)} °C · {d.current.weather ?? ''}</span></p>
                  <ul className="mt-1 grid grid-cols-7 gap-1 text-center text-[10.5px] tnum">
                    {d.daily.map((x) => (
                      <li key={x.date} className="rounded bg-surface-2 px-0.5 py-1" title={`${fmtDate(x.date)}: ${fmt(x.temperature_2m_min, 0)} to ${fmt(x.temperature_2m_max, 0)} °C, ${fmt(x.precipitation_sum, 1)} mm`}>
                        <div className="text-ink-3">{x.date.slice(8)}</div>
                        <div>{fmt(x.temperature_2m_max, 0)}</div>
                        <div className="text-ink-3">{fmt(x.temperature_2m_min, 0)}</div>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 flex items-center gap-1.5 text-[12px] text-ink-2">El Nino sensitivity: {d.enso.strength_label} <ExposureChip score={d.enso.strength} compact /></p>
                  <div className="mt-2"><AdvisoryCell adv={d.advisories ?? undefined} /></div>
                  <AsOf className="mt-2" ts={d.fetched_at} source={d.source} href={d.url} kind="forecast" label="fetched" />
                </>
              )}
            </div>
          )
        })}
      </div>
    </Card>
  )
}
