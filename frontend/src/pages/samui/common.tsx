/** Shared helpers for the Koh Samui page (watch + exit views). */
import type { LocalRisk, RiskFactor } from '../../api/types'
import { fmtUnit, HOME, inferKind, VALUE_KIND, type ValueKind } from '../../lib/format'

/** Kept as an alias: every /api/local field is now declared on the shared LocalRisk type. */
export type LocalRiskX = LocalRisk

/** Koh Samui values are shown in ICT (Asia/Bangkok). */
export const TZ = 'ICT' as const
export const HOME_NEAR = `${HOME.lat},${HOME.lon}`

/**
 * Kind of a factor / signal value. Order: the backend's `kind`; else a value dated in the future is a
 * forecast; else the backend unit says "(forecast)". Anything else stays unknown (never guessed).
 */
export function valueKind(v: { kind?: string | null; valid_for?: string | null; observed_at?: string | null; unit?: string | null; unit_label?: string | null }): ValueKind | null {
  const k = inferKind(v.kind, v.valid_for ?? v.observed_at)
  if (k) return k
  if (/\bforecast\b/i.test(`${v.unit_label ?? ''} ${v.unit ?? ''}`)) return 'forecast'
  return null
}

/** Human unit: the backend `unit_label` when present, else the raw unit. */
export const unitOf = (v: { unit?: string | null; unit_label?: string | null }) => fmtUnit(v.unit_label ?? v.unit ?? '')

export const KIND_ORDER: (ValueKind | 'unknown')[] = ['observed', 'forecast', 'model_analysis', 'reanalysis', 'bulletin', 'unknown']
export const kindLabel = (k: string) => (k === 'unknown' ? 'Kind not stated' : VALUE_KIND[k as ValueKind]?.label ?? k)

export const factorKindKey = (f: RiskFactor) => valueKind(f) ?? 'unknown'

/** "Kind not stated" chip, shown when neither the backend nor the date tells what kind of value it is. */
export function UnknownKind() {
  return (
    <span className="chip" style={{ color: 'var(--ink-3)', borderColor: 'var(--line-strong)', borderStyle: 'dashed' }}
      title="The source does not say whether this value is measured, modelled or forecast, and its date is not in the future.">
      kind not stated
    </span>
  )
}

/** Display precision per machine unit (docs/reports/PRECISION_AUDIT_2026-09-24.md section 4): a weekly
 *  Nino 3.4 of 3.0 must read "3.0", not "3" (QA 24 Sep 2026); waves 0.1 m, PM2.5 0.1, DHW 0.1. */
const UNIT_DECIMALS: Record<string, number> = { degC: 1, '°C': 1, 'degC-weeks': 1, '°C-weeks': 1, m: 1, 'ug/m3': 1, 'µg/m³': 1, mm: 0, 'km/h': 0, km: 0, '%': 0, count: 0 }

export function fmtVal(v: number | string | null | undefined, unit?: string | null): string {
  if (v === null || v === undefined || v === '') return '--'
  if (typeof v !== 'number') return fmtUnit(String(v))
  const a = Math.abs(v)
  const fixed = unit ? UNIT_DECIMALS[unit] : undefined
  const d = fixed !== undefined ? fixed : a >= 100 ? 0 : a < 10 && v % 1 ? 2 : v % 1 ? 1 : 0
  return v.toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d })
}
