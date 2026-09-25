import { useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useWebcams } from '../api/client'
import type { Webcam } from '../api/types'
import { ChipSelect, FilterBar, FilteredEmpty, FilterGroup, PresetSelect } from '../components/filters'
import { AsOf, Empty, ErrorBox, PageHeader, Skeleton } from '../components/ui'
import { AREA_ORDER, areaLabel, CAM_STATUS, CamCard, camDistance, kindLabel, WORKING } from '../components/cams/common'
import { HelpTip, PageGuide } from '../help'
import { HOME } from '../lib/format'
import { useUrlFilters } from '../lib/urlFilters'

const RADII = ['50', '150', '300', '1000']
const KIND_ORDER = ['beach', 'pier', 'city', 'traffic', 'airport', 'buoy', 'satellite']

/** /cams: public webcams (rule 11), grouped by area, with status, last check and why each is useful. */
export default function Cams() {
  const q = useWebcams()
  const f = useUrlFilters({ area: 'list', kind: 'list', alive: 'bool', near: 'str' })
  const [params] = useSearchParams()
  const focus = params.get('cam')
  const v = f.values
  const radius = RADII.includes(v.near) ? Number(v.near) : null
  const all = useMemo(() => q.data?.webcams ?? [], [q.data])

  const inRadius = (c: Webcam) => radius === null || ((camDistance(c) ?? Infinity) <= radius)
  const mArea = (c: Webcam) => !v.area.length || v.area.includes(c.area)
  const mKind = (c: Webcam) => !v.kind.length || v.kind.includes(c.kind)
  const mAlive = (c: Webcam) => !v.alive || WORKING.has(c.status)
  // facet counts: each group ignores its own filter
  const count = (pred: (c: Webcam) => boolean) => all.filter(pred).length
  const areas = [...new Set(all.map((c) => c.area))].sort((a, b) => (AREA_ORDER.indexOf(a) + 1 || 99) - (AREA_ORDER.indexOf(b) + 1 || 99))
  const kinds = [...new Set(all.map((c) => c.kind))].sort((a, b) => (KIND_ORDER.indexOf(a) + 1 || 99) - (KIND_ORDER.indexOf(b) + 1 || 99))
  const areaOpts = areas.map((a) => ({ value: a, text: areaLabel(a), count: count((c) => c.area === a && mKind(c) && mAlive(c) && inRadius(c)) }))
  const kindOpts = kinds.map((k) => ({ value: k, text: kindLabel(k), count: count((c) => c.kind === k && mArea(c) && mAlive(c) && inRadius(c)) }))
  const shown = all.filter((c) => mArea(c) && mKind(c) && mAlive(c) && inRadius(c))
  const working = all.filter((c) => WORKING.has(c.status)).length

  const groups = useMemo(() => {
    if (radius !== null) return [{ area: 'near', cams: [...shown].sort((a, b) => (camDistance(a) ?? 1e9) - (camDistance(b) ?? 1e9)) }]
    const m = new Map<string, Webcam[]>()
    for (const c of shown) m.set(c.area, [...(m.get(c.area) ?? []), c])
    return [...m.entries()]
      .sort((a, b) => (AREA_ORDER.indexOf(a[0]) + 1 || 99) - (AREA_ORDER.indexOf(b[0]) + 1 || 99))
      .map(([area, cams]) => ({ area, cams: cams.sort((a, b) => Number(WORKING.has(b.status)) - Number(WORKING.has(a.status))) }))
  }, [shown, radius])

  // deep link from the map: /cams?cam=<id> scrolls to that card
  useEffect(() => {
    if (!focus || !all.length) return
    const t = setTimeout(() => document.getElementById(`cam-${focus}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' }), 300)
    return () => clearTimeout(t)
  }, [focus, all.length])

  const human = [
    ...(v.area.length ? [`area: ${v.area.map(areaLabel).join(' or ')}`] : []),
    ...(v.kind.length ? [`kind: ${v.kind.map(kindLabel).join(' or ')}`] : []),
    ...(v.alive ? ['working only'] : []),
    ...(radius !== null ? [`within ${radius} km of home`] : []),
  ]
  const parts = q.data?.parts ?? {}
  const partNote = Object.entries(parts).map(([k, p]) => (p ? `${k.replace('webcams_', '')}: ${p.ok}/${p.count} ok` : `${k.replace('webcams_', '')}: not configured`)).join(' · ')

  return (
    <div className="space-y-3">
      <PageHeader title="Cams" help={<HelpTip id="cams_page" size="md" />}
        sub={<>See it yourself: public cameras on Samui, the ferry route, Thailand, the El Nino front line, Pacific buoys and satellites. Only feeds their owners publish for public viewing <HelpTip id="webcams_privacy" label="Which cameras are allowed?" />.</>} />
      <PageGuide page="cams" />

      {q.isLoading ? <Skeleton h={320} /> : q.isError ? <ErrorBox error={q.error} what="webcams" /> : !q.data ? (
        <Empty what="The webcam list is not available yet" source="webcam collectors (/api/webcams)" />
      ) : !all.length ? (
        <Empty what="No webcam checked yet" source="webcam collectors (webcams_images, webcams_streams)" />
      ) : (
        <>
          <FilterBar tour="cams-filters" active={f.active} onReset={f.reset}
            summary={<><b className="text-ink">{shown.length}</b> of {all.length} cams · {working} working now</>}>
            <FilterGroup label="Area" help={<HelpTip id="cams_page" label="What are the areas?" />}>
              <ChipSelect options={areaOpts} selected={v.area} onToggle={(x) => f.toggle('area', x)} limit={8} />
            </FilterGroup>
            <FilterGroup label="Kind" help={<HelpTip id="webcams_sea_state" label="Which cams show the sea state?" />}>
              <ChipSelect options={kindOpts} selected={v.kind} onToggle={(x) => f.toggle('kind', x)} limit={8} />
            </FilterGroup>
            <FilterGroup label="Status" help={<HelpTip id="webcams" label="What does the status mean?" />}>
              <button type="button" className="fchip" aria-pressed={v.alive} onClick={() => f.set('alive', !v.alive)}
                title={`Only ${Object.keys(CAM_STATUS).filter((s) => WORKING.has(s)).join(', ')}`}>
                Working only <span className="fchip-n tnum">{working}</span>
              </button>
            </FilterGroup>
            <FilterGroup label={`Near home (${HOME.name})`} help={<HelpTip id="map_overlays" label="Where is home?" />}>
              <PresetSelect label="Radius around home" value={radius === null ? '' : String(radius)} onChange={(x) => f.set('near', x)}
                options={[{ v: '', l: 'Anywhere' }, ...RADII.map((r) => ({ v: r, l: `${r} km` }))]} />
            </FilterGroup>
          </FilterBar>

          {!shown.length ? (
            <FilteredEmpty what="cams" filters={human} onReset={f.reset} total={all.length}>
              {radius !== null && <p className="mt-1 text-[12px]">Satellite images have no position, so a radius filter leaves them out.</p>}
            </FilteredEmpty>
          ) : (
            <div data-tour="cams-grid" className="space-y-5">
              {groups.map((g) => (
                <section key={g.area} aria-label={g.area === 'near' ? 'Cams near home' : areaLabel(g.area)}>
                  <h2 className="mb-2 flex items-center gap-1.5 text-[14px] font-semibold">
                    {g.area === 'near' ? `Within ${radius} km of home, nearest first` : areaLabel(g.area)}
                    <span className="text-[12px] font-normal text-ink-3">({g.cams.length})</span>
                    {g.area === 'pacific' && <HelpTip id="webcams_buoycams" />}
                    {g.area === 'space' && <HelpTip id="webcams_space_cams" />}
                    {(g.area === 'samui' || g.area === 'ferry_route') && <HelpTip id="webcams_sea_state" label="Reading sea state on a camera" />}
                  </h2>
                  <div className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,290px),1fr))] gap-3">
                    {g.cams.map((c) => <CamCard key={c.id} c={c} highlight={c.id === focus} />)}
                  </div>
                </section>
              ))}
            </div>
          )}
          <AsOf ts={q.data.updated_at} label="list checked" tz="UTC" source={partNote || 'webcam collectors'} />
        </>
      )}
    </div>
  )
}
