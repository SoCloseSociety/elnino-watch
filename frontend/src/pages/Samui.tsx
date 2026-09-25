import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, useAccess, useLocal } from '../api/client'
import { AdminOnlyNote } from '../components/Admin'
import { AnalogsCard } from '../components/AnalogsCard'
import { CamsStrip } from '../components/cams/CamsStrip'
import { Empty, ErrorBox, PageHeader, Skeleton } from '../components/ui'
import { HelpTip, PageGuide } from '../help'
import { HOME } from '../lib/format'
import { HistoryCard, NearbyCard, SeasonalCard, TmdWarningsCard, WaterCard, WaterSupplyCard } from './samui/Cards'
import type { LocalRiskX } from './samui/common'
import { ExitPlanView } from './samui/Exit'
import { FactorsSection } from './samui/Factors'
import { LevelPanel } from './samui/Level'
import { WeatherCharts } from './samui/Weather'

type Tab = 'watch' | 'exit'

export default function Samui() {
  const q = useLocal()
  const qc = useQueryClient()
  const access = useAccess()
  const [params, setParams] = useSearchParams()
  const tab: Tab = params.get('view') === 'exit' ? 'exit' : 'watch'
  // keep the other URL filters when switching views
  const setTab = (t: Tab) => setParams((prev) => {
    const p = new URLSearchParams(prev)
    if (t === 'exit') p.set('view', 'exit')
    else p.delete('view')
    return p
  }, { replace: true })
  const [msg, setMsg] = useState<string | null>(null)
  const evalM = useMutation({
    mutationFn: () => api<unknown>('/local/evaluate', { method: 'POST' }),
    onSuccess: () => { setMsg('Re-evaluation complete.'); qc.invalidateQueries({ queryKey: ['local'] }); qc.invalidateQueries({ queryKey: ['alerts'] }) },
    onError: (e) => setMsg(`Failed: ${e instanceof Error ? e.message : String(e)}`),
  })
  const r = (q.data ?? null) as LocalRiskX | null
  const critical = new Set(r?.coverage?.critical_missing ?? [])
  const home = r?.home?.name ?? HOME.name

  return (
    <div className="space-y-4">
      <PageHeader title={`${home} watch`} help={<HelpTip id="risk_levels" size="md" />}
        sub={`${(r?.home?.lat ?? HOME.lat).toFixed(3)} N, ${(r?.home?.lon ?? HOME.lon).toFixed(3)} E · every factor is explained, dated (ICT) and sourced.`}
        right={
          <>
            {msg && <span className="text-[12px] text-ink-2" role="status">{msg}</span>}
            {access.canWrite ? (
              <button type="button" className="btn btn-primary" disabled={evalM.isPending} onClick={() => { setMsg(null); evalM.mutate() }}
                title="Recompute the level now from the data already collected (it also runs by itself after every data update)">
                {evalM.isPending && <span className="spin" />} Re-evaluate
              </button>
            ) : <AdminOnlyNote what="re-evaluating on demand" signIn={false} />}
          </>
        } />
      <PageGuide page="samui" />

      <div className="flex flex-wrap items-center gap-2">
        <div className="seg" role="group" aria-label="View">
          <button type="button" aria-pressed={tab === 'watch'} onClick={() => setTab('watch')}>Risk watch</button>
          <button type="button" data-tour="samui-exit-tab" aria-pressed={tab === 'exit'} onClick={() => setTab('exit')}>Exit plan</button>
        </div>
        <HelpTip id={tab === 'exit' ? 'exit_plan' : 'risk_levels'} />
      </div>

      {tab === 'exit' ? <ExitPlanView /> : (
        <>
          {/* the level panel + factors are ~1000 px once loaded: reserve the height so the cards below never jump (CLS) */}
          <div className="min-h-[900px] space-y-4">
          {q.isLoading ? <Skeleton h={600} /> : q.isError ? <ErrorBox error={q.error} what="local assessment" /> : !r ? (
            <Empty what="No local risk assessment yet" source="Koh Samui risk engine (/api/local)">
              <p className="mt-2 text-[12px] text-ink-3">{access.canWrite ? 'The Re-evaluate button runs an assessment if the engine is installed.' : 'The assessment runs by itself after each data update.'}</p>
            </Empty>
          ) : (
            <>
              <LevelPanel r={r} onExit={() => setTab('exit')} />
              <FactorsSection factors={r.factors ?? []} critical={critical} evaluatedAt={r.evaluated_at} />
            </>
          )}
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 xl:[&>*]:min-h-[533px]">
            <WaterCard />
            <WaterSupplyCard water={r?.factors?.find((f) => f.id === 'water')} />
            <SeasonalCard />
            <TmdWarningsCard />
            <NearbyCard homeName={home} />
            <HistoryCard />
            <AnalogsCard tour="samui-analogs" />
          </div>

          <CamsStrip />

          <section aria-labelledby="wx-h">
            <h2 id="wx-h" className="mb-2 flex items-center gap-1.5 text-[15px] font-semibold">Local weather <HelpTip id="open_meteo" label="Where does the local weather come from?" /></h2>
            <WeatherCharts />
          </section>
        </>
      )}
    </div>
  )
}
