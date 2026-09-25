import { Link } from 'react-router-dom'
import { useWebcams } from '../../api/client'
import type { Webcam } from '../../api/types'
import { HelpTip } from '../../help'
import { fmtNum, relTime } from '../../lib/format'
import { AsOf } from '../ui'
import { CamMedia, camDistance, StatusChip, WORKING } from './common'

const NEAR_KM = 60

/** Small strip of the working cams on and around Koh Samui (Samui page). */
export function CamsStrip() {
  const q = useWebcams()
  const all = q.data?.webcams ?? []
  const near = all
    .filter((c) => c.area === 'samui' || c.area === 'ferry_route' || ((camDistance(c) ?? Infinity) <= NEAR_KM))
    .sort((a, b) => Number(WORKING.has(b.status)) - Number(WORKING.has(a.status)) || (camDistance(a) ?? 1e9) - (camDistance(b) ?? 1e9))
  const shown = near.slice(0, 6)
  if (!q.isLoading && !near.length) return null
  return (
    <section aria-labelledby="cams-strip-h" className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="cams-strip-h" className="flex items-center gap-1.5 text-[15px] font-semibold">
          See it yourself: cams on and around Samui <HelpTip id="webcams_sea_state" label="How to read sea state on a camera" />
        </h2>
        <Link to="/cams?area=samui,ferry_route" className="btn !py-1 !text-[12px]">All {near.length} nearby cams</Link>
      </div>
      {q.isLoading ? <div className="skeleton h-40" /> : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,230px),1fr))] gap-3">
          {shown.map((c) => <StripCard key={c.id} c={c} />)}
        </div>
      )}
      {q.data && <AsOf ts={q.data.updated_at} label="cams checked" tz="UTC" source="Cams page" href="/cams" />}
    </section>
  )
}

function StripCard({ c }: { c: Webcam }) {
  const d = camDistance(c)
  return (
    <div className="card flex min-w-0 flex-col gap-1.5 p-2">
      <div className="flex items-center justify-between gap-1.5">
        <span className="min-w-0 truncate text-[12px] font-semibold" title={c.title}>{c.title}</span>
        <StatusChip s={c.status} />
      </div>
      <CamMedia c={c} compact />
      <div className="text-[11px] text-ink-3">
        {d !== null ? `${fmtNum(d, d < 10 ? 1 : 0)} km from home · ` : ''}checked {c.last_checked ? relTime(c.last_checked) : 'never'}
      </div>
    </div>
  )
}
