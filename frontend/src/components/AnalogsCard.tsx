/**
 * Compact "What past El Ninos did to Samui" card (Overview, Koh Samui page), linking to /history.
 * Every figure is read from GET /api/local/analogs; while the ERA5 history is still loading
 * the card says so instead of showing numbers.
 */
import { Link } from 'react-router-dom'
import { useAnalogs } from '../api/client'
import type { Analogs } from '../api/types'
import { HelpTip } from '../help'
import { fmtDate, fmtNum, toneText } from '../lib/format'
import { AsOf, Card, ErrorBox, KindBadge, Skeleton } from './ui'

function tiles(d: Analogs) {
  const ev = d.events.filter((e) => e.samui.complete)
  const n = ev.length
  const dry = ev.filter((e) => (e.samui.feb_apr_rain_pct ?? 999) < 60)
  const hot = ev.filter((e) => e.samui.max_feels_like !== null).sort((a, b) => (b.samui.max_feels_like ?? 0) - (a.samui.max_feels_like ?? 0))[0]
  const spell = ev.filter((e) => e.samui.longest_dry_spell_days !== null).sort((a, b) => (b.samui.longest_dry_spell_days ?? 0) - (a.samui.longest_dry_spell_days ?? 0))[0]
  const neutral = d.neutral_baseline.metrics?.feb_apr_rain_pct
  const sw = d.current_event.so_far?.sw_monsoon
  const out: { label: string; value: string; sub: string; tone?: string }[] = []
  if (n) {
    out.push({ label: 'Feb-Apr rain under 60% of normal', value: `${dry.length} of ${n} events`, sub: neutral?.median !== null && neutral?.median !== undefined ? `neutral-year median ${fmtNum(neutral.median, 0)}% (n=${neutral.n})` : 'the danger window for water', tone: dry.length >= n / 2 ? 'var(--critical)' : undefined })
  }
  if (hot?.samui.max_feels_like !== null && hot?.samui.max_feels_like !== undefined) {
    out.push({ label: 'Hottest dry-season day (feels-like)', value: `${fmtNum(hot.samui.max_feels_like, 1)} °C`, sub: `${hot.id}${hot.samui.max_feels_like_day ? `, ${fmtDate(hot.samui.max_feels_like_day)}` : ''} (ERA5 cell)`, tone: hot.samui.max_feels_like >= 39 ? 'var(--serious)' : undefined })
  }
  if (spell?.samui.longest_dry_spell_days !== null && spell?.samui.longest_dry_spell_days !== undefined) {
    out.push({ label: 'Longest dry spell, Jan-May', value: `${spell.samui.longest_dry_spell_days} days`, sub: `${spell.id} (days under 1 mm)`, tone: spell.samui.longest_dry_spell_days >= 45 ? 'var(--serious)' : undefined })
  }
  if (sw && sw.pct !== null) {
    const m = sw.months
    const mon = (k: string) => new Date(`${k}-15T00:00:00Z`).toLocaleDateString('en-GB', { month: 'short', timeZone: 'UTC' })
    out.push({ label: `2026 so far (${mon(m[0])}${m.length > 1 ? `-${mon(m[m.length - 1])}` : ''})`, value: `${sw.pct}% of normal`, sub: `${fmtNum(sw.rain_mm, 0)} mm; the refill and the 2027 dry season are ahead`, tone: sw.pct < 75 ? 'var(--serious)' : undefined })
  }
  return out
}

export function AnalogsCard({ compact = false, tour }: { compact?: boolean; tour?: string }) {
  const q = useAnalogs()
  const d = q.data
  const pending = d?.history.windows_pending ?? []
  const loading = !!d && (pending.length > 0 || d.history.months === 0)
  const t = d ? tiles(d) : []
  return (
    <Card title="What past El Ninos did to Samui" help={<HelpTip id="analogs" />} tour={tour} className={`h-full ${compact ? 'min-h-[150px]' : 'min-h-[260px]'}`}
      right={<><KindBadge kind="reanalysis" compact help={false} /><Link className="link text-[12px]" to="/history">All 7 events, charts, timeline ›</Link></>}
      footer={d ? <AsOf ts={d.history.updated_at} label="ERA5 history updated" tz="UTC" source={`${d.events.length} strong El Ninos since 1982, NOAA CPC + ERA5`} href="/history" /> : undefined}>
      {q.isLoading ? <Skeleton h={compact ? 70 : 150} /> : q.isError ? <ErrorBox error={q.error} what="past El Ninos" /> : !d ? (
        <p className="text-[13px] text-ink-2">The analogs endpoint is not available on this server (<code>/api/local/analogs</code>).</p>
      ) : loading ? (
        <p className="text-[13px] text-ink-2" role="status">
          <b style={{ color: 'var(--warning)' }}>▲ History loading, not estimated:</b> {pending.length} decade window{pending.length === 1 ? '' : 's'} of ERA5 data still to fetch ({d.history.months} months stored). The comparison appears once the history is complete.{' '}
          <Link className="link" to="/history">See the page</Link>
        </p>
      ) : !t.length ? (
        <p className="text-[13px] text-ink-2">No reconstructed event yet. <Link className="link" to="/history">See the page</Link></p>
      ) : (
        <div className={`grid gap-2 ${compact ? 'grid-cols-2 lg:grid-cols-4' : 'grid-cols-2'}`}>
          {t.map((x) => (
            <div key={x.label} className="rounded-lg bg-surface-2 p-2.5">
              <div className="text-[11px] leading-tight text-ink-3">{x.label}</div>
              <div className="mt-0.5 text-[17px] leading-tight font-semibold tnum" style={x.tone ? { color: toneText(x.tone) } : undefined}>{x.value}</div>
              <div className="text-[11px] leading-tight text-ink-2">{x.sub}</div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
