/**
 * Shared pieces of the Cams page and the "Cams near home" strip: status chip, labels and the
 * camera card. Rule 11: only owner-published public feeds. How a cam is shown follows its `mode`:
 * embed = the owner's player (click to load), proxy = still image through our server, link = official page.
 */
import { useState } from 'react'
import type { Webcam } from '../../api/types'
import { HelpFor, HelpTip, isTopicId, type TopicId } from '../../help'
import { fmtDateTz, fmtNum, haversineKm, HOME, relTime, toneText } from '../../lib/format'
import { safeUrl } from '../../lib/geo'

export const CAM_STATUS: Record<string, { label: string; color: string; icon: string; hint: string }> = {
  live: { label: 'live', color: 'var(--good)', icon: '●', hint: 'A still image newer than this camera\'s limit' },
  online: { label: 'online', color: 'var(--good)', icon: '●', hint: 'The provider\'s own page says the stream is up' },
  reachable: { label: 'reachable', color: 'var(--accent)', icon: '◐', hint: 'Still published and embeddable; the player shows whether it is broadcasting now' },
  stale: { label: 'stale', color: 'var(--stale)', icon: '◷', hint: 'The newest image is older than this camera\'s limit: a photo of the past' },
  offline: { label: 'offline', color: 'var(--ink-3)', icon: '■', hint: 'Removed, marked offline by the provider, or the last check failed' },
  error: { label: 'error', color: 'var(--critical)', icon: '■', hint: 'The last check failed' },
}
export const camStatus = (s: string) => CAM_STATUS[s] ?? CAM_STATUS.offline

export const AREA_LABEL: Record<string, string> = {
  samui: 'Koh Samui', ferry_route: 'Ferry route (Phangan, Tao, pier)', thailand: 'Thailand', indonesia: 'Indonesia',
  australia: 'Australia', peru_ecuador: 'Peru and Ecuador', pacific: 'Pacific buoys (NOAA)', space: 'Satellites (full disk)',
}
export const AREA_ORDER = ['samui', 'ferry_route', 'thailand', 'indonesia', 'australia', 'peru_ecuador', 'pacific', 'space']
export const areaLabel = (a: string) => AREA_LABEL[a] ?? a.replace(/_/g, ' ')

export const KIND_LABEL: Record<string, string> = {
  beach: 'Beach', pier: 'Pier / port', city: 'Street / city', traffic: 'Traffic', airport: 'Airport', buoy: 'Buoy', satellite: 'Satellite',
}
export const kindLabel = (k: string) => KIND_LABEL[k] ?? k

export const MODE_LABEL: Record<string, string> = { embed: 'Player', proxy: 'Still image', link: 'Official page' }

export const WORKING = new Set(['live', 'online', 'reachable'])

/** Distance from home (Maenam) in km, or null for satellites / cams without a position. */
export function camDistance(c: Webcam): number | null {
  if (c.distance_km !== undefined && c.distance_km !== null) return c.distance_km
  if (c.kind === 'satellite' || c.lat === null || c.lon === null) return null
  return haversineKm(HOME.lat, HOME.lon, c.lat, c.lon)
}

export function camTopic(c: Webcam): TopicId {
  return c.help_id && isTopicId(c.help_id) ? c.help_id : 'webcams'
}

export function StatusChip({ s }: { s: string }) {
  const m = camStatus(s)
  return (
    <span className="chip shrink-0 whitespace-nowrap" title={m.hint} style={{ color: toneText(m.color), borderColor: m.color }}>
      <span aria-hidden>{m.icon}</span> {m.label}
    </span>
  )
}

function embedSrc(u: string): string {
  const url = new URL(u)
  if (/youtube(-nocookie)?\.com$/.test(url.hostname)) {
    url.searchParams.set('autoplay', '1')
    url.searchParams.set('mute', '1')
    url.searchParams.set('playsinline', '1')
    url.searchParams.set('rel', '0')
  }
  return url.toString()
}

/** The picture area: owner's player on click, proxied still image, or a link panel. */
export function CamMedia({ c, compact = false }: { c: Webcam; compact?: boolean }) {
  const [load, setLoad] = useState(false)
  const [imgErr, setImgErr] = useState(false)
  const page = safeUrl(c.page_url)
  const embed = safeUrl(c.embed_url)
  const box = 'relative aspect-video w-full overflow-hidden rounded-md border border-line bg-surface-2'
  if (c.mode === 'embed' && embed) {
    return (
      <div className={box}>
        {load ? (
          <iframe className="absolute inset-0 h-full w-full" src={embedSrc(embed)} title={`${c.title} (${c.provider ?? 'player'})`}
            allow="autoplay; encrypted-media; picture-in-picture; fullscreen" referrerPolicy="strict-origin-when-cross-origin" loading="lazy" />
        ) : (
          <button type="button" onClick={() => setLoad(true)} className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 p-2 text-center hover:bg-surface-3"
            aria-label={`Load player: ${c.title}${c.provider ? ` (${c.provider})` : ''}`}>
            <span aria-hidden className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-current text-ink-2">▶</span>
            <span className="text-[12.5px] font-semibold text-ink">Load player</span>
            {!compact && <span className="text-[11px] text-ink-3">{c.provider}'s official player. Loads only on click, to save data.</span>}
          </button>
        )}
      </div>
    )
  }
  if (c.mode === 'proxy' && c.snapshot_proxy && !imgErr) {
    return (
      <div className={box}>
        <a href={page ?? c.snapshot_proxy} target="_blank" rel="noreferrer" title="Open the source page">
          <img src={c.snapshot_proxy} alt={`Latest image: ${c.title}`} loading="lazy" decoding="async" onError={() => setImgErr(true)}
            className={`absolute inset-0 h-full w-full ${c.kind === 'satellite' ? 'object-contain' : 'object-cover'}`} />
        </a>
        {c.image_updated_at && (
          <span className="absolute bottom-1 left-1 rounded bg-black/70 px-1.5 py-0.5 text-[10.5px] text-white tnum">
            image {fmtDateTz(c.image_updated_at, 'UTC')}
          </span>
        )}
      </div>
    )
  }
  return (
    <div className={`${box} flex flex-col items-center justify-center gap-1.5 p-3 text-center`}>
      {c.mode === 'proxy' ? (
        <span className="text-[12px] text-ink-2">{imgErr ? 'The image could not be loaded right now.' : 'No image available right now.'}</span>
      ) : (
        <span className="text-[12px] text-ink-2">{compact ? 'Opens on the provider\'s site' : `${c.provider ?? 'The provider'} only allows viewing on its own page.`}</span>
      )}
      {page && <a className="btn !py-1 !text-[12px]" href={page} target="_blank" rel="noreferrer">Open official page ↗</a>}
    </div>
  )
}

export function CamCard({ c, highlight = false }: { c: Webcam; highlight?: boolean }) {
  const page = safeUrl(c.page_url)
  const d = camDistance(c)
  return (
    <article id={`cam-${c.id}`} className={`card flex h-full min-w-0 flex-col gap-2 p-3 ${highlight ? 'ring-2 ring-[var(--accent)]' : ''}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="flex items-center gap-1.5 text-[13px] font-semibold">
            <span className="min-w-0 truncate" title={c.title}>{c.title}</span>
            <HelpFor id={camTopic(c)} appId={c.help_id ?? 'webcams'} kind="webcam" title={c.title} text={c.why} />
          </h3>
          <div className="line-clamp-2 text-[11.5px] text-ink-3" title={c.place ?? ''}>
            {c.place}{d !== null ? ` · ${fmtNum(d, d < 10 ? 1 : 0)} km from home` : ''}{c.coord_precision && c.coord_precision !== 'exact' ? ' (approx.)' : ''}
          </div>
        </div>
        <span className="inline-flex items-center gap-0.5"><StatusChip s={c.status} /><HelpTip id="webcams" label="What does the camera status mean?" /></span>
      </div>
      <CamMedia c={c} />
      {c.why && <p className="text-[12px] leading-snug text-ink-2"><span className="font-semibold text-ink">Useful for: </span>{c.why}</p>}
      <div className="mt-auto space-y-0.5 border-t border-line pt-1.5 text-[11px] text-ink-3">
        <div className="flex flex-wrap items-center gap-x-1.5">
          <span>{kindLabel(c.kind)}</span><span aria-hidden>·</span>
          <span className="inline-flex items-center gap-1">{MODE_LABEL[c.mode] ?? c.mode} <HelpTip id="webcams_modes" label="Player, still image or link?" /></span>
          <span aria-hidden>·</span>
          <span title={c.last_checked ?? ''}>checked {c.last_checked ? relTime(c.last_checked) : 'never'}</span>
          {c.status !== 'live' && c.status !== 'online' && c.status !== 'reachable' && c.last_ok && <><span aria-hidden>·</span><span>last ok {relTime(c.last_ok)}</span></>}
        </div>
        {c.detail && <div className="line-clamp-2" title={c.detail}>{c.detail}</div>}
        <div className="flex flex-wrap items-center gap-x-1.5">
          <span>{c.publisher && c.publisher !== c.provider ? `${c.publisher} via ${c.provider}` : c.provider}</span>
          {page && <><span aria-hidden>·</span><a className="link" href={page} target="_blank" rel="noreferrer">official page ↗</a></>}
        </div>
        {c.license_note && <div className="line-clamp-2 italic" title={c.license_note}>{c.license_note}</div>}
      </div>
    </article>
  )
}
