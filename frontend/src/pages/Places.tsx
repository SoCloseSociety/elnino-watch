import { useMemo, useState } from 'react'
import { ErrorBox, PageHeader, Skeleton, Empty } from '../components/ui'
import { loadPersonal, savePersonal, useCompare, usePlaceDetails, usePlacesList, type GeoResult, type PlaceDetail } from '../components/places/api'
import { PlaceCard } from '../components/places/PlaceCard'
import { ComparisonMatrix } from '../components/places/ComparisonMatrix'
import { RankingPanel } from '../components/places/RankingPanel'
import { ClimateCharts, ProjectionChart, SeasonalTable } from '../components/places/PlaceCharts'
import { EnsoPanel } from '../components/places/EnsoPanel'
import { PlacesMap } from '../components/places/PlacesMap'
import { AddPlace, PersonalList } from '../components/places/AddPlace'
import { PlaceTip } from '../components/places/common'
import { PageGuide } from '../help'

/** /places: compare places side by side (the default set from backend places/config.py + added ones). */
export default function Places() {
  const list = usePlacesList()
  const compare = useCompare()
  const ids = useMemo(() => (list.data?.places ?? []).map((p) => p.id), [list.data])
  const details = usePlaceDetails(ids)
  const [personal, setPersonalState] = useState<GeoResult[]>(loadPersonal)
  const setPersonal = (a: GeoResult[]) => { setPersonalState(a); savePersonal(a) }

  const loaded = details.map((d) => d.data).filter(Boolean) as PlaceDetail[]
  const context = Object.fromEntries(loaded.map((p) => [p.id, p.context ?? []]))
  const detailError = details.find((d) => d.error)?.error

  return (
    <div className="w-full">
      <PageHeader title="Places" help={<PlaceTip id="places_page" />}
        sub="Where could we live? The same data and rules for every place: conditions now, climate, hazards, 2050 trend, El Nino sensitivity, official advice." />
      <PageGuide page="places" />

      {list.error ? <ErrorBox error={list.error} what="Places list" /> : null}
      {list.isLoading && <Skeleton h={220} />}
      {list.data === null && <Empty what="The Places API is not available yet" source="app.places (backend)" />}

      {list.data && (
        <>
          <section aria-label="Place cards" data-tour="places-cards" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {ids.map((id, i) => {
              const d = details[i]
              if (d?.data) return <PlaceCard key={id} p={d.data} />
              if (d?.error) return <ErrorBox key={id} error={d.error} what={id} />
              return <Skeleton key={id} h={420} />
            })}
          </section>

          <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <PlacesMap places={list.data.places} personal={personal} />
            <AddPlace list={list.data} personal={personal} setPersonal={setPersonal} />
          </div>

          {compare.error ? <div className="mt-4"><ErrorBox error={compare.error} what="Comparison" /></div> : null}
          {compare.isLoading && <Skeleton className="mt-4" h={320} />}
          {compare.data && (
            <div className="mt-4 space-y-4">
              <ComparisonMatrix data={compare.data} context={context} />
              <RankingPanel data={compare.data} />
            </div>
          )}

          {detailError ? <div className="mt-4"><ErrorBox error={detailError} what="Place details" /></div> : null}
          {loaded.length > 0 && (
            <div className="mt-4 space-y-4">
              <div className="grid gap-4 xl:grid-cols-2">
                <ClimateCharts places={loaded} />
                <ProjectionChart places={loaded} />
              </div>
              <SeasonalTable places={loaded} />
              <EnsoPanel places={loaded} now={compare.data?.enso_now ?? loaded[0]?.enso.now ?? null} />
            </div>
          )}

          <div className="mt-4">
            <PersonalList personal={personal} setPersonal={setPersonal} />
          </div>
        </>
      )}
    </div>
  )
}
