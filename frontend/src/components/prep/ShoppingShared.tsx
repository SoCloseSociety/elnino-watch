/**
 * Shared types, data hooks and small helpers for the Preparedness shopping panel
 * (GET /api/shopping, GET /api/shopping/budget). Data is a curated, dated file on the
 * backend: nothing is scraped live.
 */
import { useQuery } from '@tanstack/react-query'
import { api, qs } from '../../api/client'
import { HelpTip, InfoTip, getTopic, isTopicId } from '../../help'

export type PriceStatus = 'ok' | 'recheck' | 'unverified' | 'not_buyable'

export interface ShopListing {
  retailer: string
  retailer_name: string
  title: string
  price_thb: number
  units: number | null
  unit_price_thb: number | null
  url: string
  source: 'retailer' | 'marketplace'
  checked_at: string
  age_days: number
  recheck: boolean
}

export interface ShopLink {
  retailer: string | null
  name: string
  kind: string
  lang: 'EN' | 'TH' | null
  query: string | null
  url: string
  hint: string | null
}

export interface ShopStore {
  id: string
  name: string
  area: string | null
  address: string | null
  sells: string | null
  source: string | null
  maps_url: string
}

export interface ShopItem {
  id: string
  label: string | null
  unit: string | null
  priority: string | null
  category: string | null
  buyable: boolean
  price_status: PriceStatus
  checked_at: string
  reason?: string
  spec?: string | null
  why?: string | null
  assumption?: string | null
  price_note?: string | null
  budget_mode?: 'default' | 'conditional' | 'optional'
  unit_price?: { min: number; max: number; unit: string | null } | null
  listings?: ShopListing[]
  components?: { id: string; label: string; count: number; listings: ShopListing[] }[]
  search_links?: ShopLink[]
  local_stores?: ShopStore[]
}

export interface ShoppingData {
  checked_at: string
  age_days: number
  stale_after_days: number
  recheck: boolean
  note: string
  method: string
  stores: ShopStore[]
  coverage: { prep_items: number; covered: number; missing: string[]; unknown: string[] }
  items: Record<string, ShopItem>
}

export interface BudgetBucket { min: number; max: number; priced: number; unpriced: string[] }

export interface ShoppingBudget {
  household: { adults: number; children: number; days: number }
  currency: 'THB'
  checked_at: string
  age_days: number
  recheck: boolean
  label: string
  included_modes: string[]
  total: { min: number; max: number }
  by_priority: Record<'must' | 'should' | 'nice', BudgetBucket>
  by_category: (BudgetBucket & { id: string; title: string })[]
  items: { id: string; label: string; category: string; priority: string; needed: number; unit: string | null
    cost_min: number | null; cost_max: number | null; price_status: PriceStatus; note: string | null }[]
  excluded: { id: string; label: string; mode: string; reason: string }[]
  not_buyable: string[]
  missing_from_catalog: string[]
  caveats: string[]
}

export const useShopping = () =>
  useQuery({ queryKey: ['shopping'], queryFn: () => api<ShoppingData>('/shopping'), staleTime: 60 * 60_000 })

export const useShoppingBudget = (h: { adults: number; children: number; days: number }, include: string[]) =>
  useQuery({
    queryKey: ['shopping-budget', h.adults, h.children, h.days, include.join(',')],
    queryFn: () => api<ShoppingBudget>(`/shopping/budget${qs({ adults: h.adults, children: h.children, days: h.days })}${include.map((m) => `&include=${m}`).join('')}`),
    placeholderData: (prev) => prev,
  })

const THB = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 })
const THB2 = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 2 })

/** "1,234" (whole baht) or "4.44" for small unit prices. */
export function fmtBaht(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '--'
  return v < 100 && !Number.isInteger(v) ? THB2.format(v) : THB.format(Math.round(v))
}

export function fmtRange(min: number | null | undefined, max: number | null | undefined): string {
  if (min === null || min === undefined) return 'check link'
  if (max === null || max === undefined || Math.round(min) === Math.round(max)) return `${fmtBaht(min)} THB`
  return `${fmtBaht(min)}-${fmtBaht(max)} THB`
}

export const STATUS_META: Record<PriceStatus, { label: string; color: string; icon: string; hint: string }> = {
  ok: { label: 'Price checked', color: 'var(--good-ink)', icon: '✓', hint: 'Prices seen on the shop pages on the date shown (less than 60 days ago).' },
  recheck: { label: 'Re-check price', color: 'var(--serious)', icon: '▲', hint: 'These prices are more than 60 days old: open the links before relying on them.' },
  unverified: { label: 'No verified price', color: 'var(--ink-3)', icon: '?', hint: 'No reliable price was found: check the links.' },
  not_buyable: { label: 'Not bought', color: 'var(--ink-3)', icon: '·', hint: 'A plan, document or habit: nothing to buy.' },
}

export const PRIORITY_LABEL: Record<string, string> = { must: 'Essential', should: 'Recommended', nice: 'Useful' }

/**
 * "?" help for a shopping topic. Uses the registered topic when it exists (see
 * help/topics/shopping.ts), otherwise shows the fallback text so help is never missing.
 */
export function ShopHelp({ id, title, text, label }: { id: string; title: string; text: string; label?: string }) {
  if (isTopicId(id) && getTopic(id)) return <HelpTip id={id} label={label} />
  return <InfoTip title={title} text={text} />
}
