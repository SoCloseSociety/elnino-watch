/**
 * Budget summary card for the Preparedness page: indicative cost (THB, cheapest to
 * dearest listing seen) of the whole checklist for the household, by priority and by
 * category, with the date the prices were checked and what is not counted.
 *
 *   <ShoppingBudgetCard household={h} />
 */
import { useState } from 'react'
import { Card, ErrorBox, Skeleton } from '../ui'
import { fmtRange, PRIORITY_LABEL, ShopHelp, useShoppingBudget } from './ShoppingShared'

const PRIO_COLOR: Record<string, string> = { must: 'var(--critical)', should: 'var(--serious)', nice: 'var(--ink-3)' }

export function ShoppingBudgetCard({ household, className = '' }: {
  household: { adults: number; children: number; days: number }
  className?: string
}) {
  const [extra, setExtra] = useState<string[]>([])
  const b = useShoppingBudget(household, extra)
  const toggle = (m: string) => setExtra((xs) => (xs.includes(m) ? xs.filter((x) => x !== m) : [...xs, m]))
  const d = b.data

  return (
    <Card title="Shopping budget" className={className} tour="prep-budget"
      help={<ShopHelp id="shopping_budget" title="Shopping budget"
        text="Indicative cost of the checklist for your household: quantity x prices seen on real listings, rounded up to whole packs. Range = cheapest to dearest listing. Delivery and fuel not included." />}
      footer={d ? (
        <p className="text-[11px] text-ink-3">
          {d.label}{d.recheck ? <span style={{ color: 'var(--serious)' }}> · ▲ over 60 days old: re-check before relying on it</span> : null}. Delivery, installation and fuel not included.
        </p>
      ) : undefined}>
      {b.isLoading ? <Skeleton h={140} /> : b.isError ? <ErrorBox error={b.error} what="shopping budget (/api/shopping/budget)" /> : !d ? null : (
        <div className="space-y-3 text-[13px]">
          <div>
            <div className="text-[12px] text-ink-2">
              {d.household.adults} adult(s){d.household.children ? `, ${d.household.children} child(ren)` : ''}, {d.household.days} days
            </div>
            <div className="text-2xl font-semibold tnum">{fmtRange(d.total.min, d.total.max)}</div>
          </div>

          <table className="w-full text-[12px]">
            <tbody className="divide-y divide-line">
              {(['must', 'should', 'nice'] as const).map((p) => {
                const v = d.by_priority[p]
                return (
                  <tr key={p}>
                    <td className="py-1"><span className="chip" style={{ color: PRIO_COLOR[p], borderColor: PRIO_COLOR[p] }}>{PRIORITY_LABEL[p]}</span></td>
                    <td className="py-1 text-right font-medium tnum">{fmtRange(v.min, v.max)}</td>
                    <td className="py-1 pl-2 text-right text-[11px] text-ink-3">{v.priced} priced{v.unpriced.length ? ` · ${v.unpriced.length} to check` : ''}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          <details>
            <summary className="cursor-pointer text-[12px] text-ink-2">By category</summary>
            <ul className="mt-1 divide-y divide-line text-[12px]">
              {d.by_category.map((c) => (
                <li key={c.id} className="flex justify-between gap-2 py-1">
                  <span>{c.title}</span>
                  <span className="tnum">{fmtRange(c.min, c.max)}{c.unpriced.length ? <span className="text-ink-3"> +{c.unpriced.length} unpriced</span> : null}</span>
                </li>
              ))}
            </ul>
          </details>

          <fieldset className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-2">
            <legend className="sr-only">Also count</legend>
            <label className="flex items-center gap-1.5">
              <input type="checkbox" checked={extra.includes('optional')} onChange={() => toggle('optional')} /> Add a water tank (if you have none)
            </label>
            <label className="flex items-center gap-1.5">
              <input type="checkbox" checked={extra.includes('conditional')} onChange={() => toggle('conditional')} /> Add baby / pet items
            </label>
          </fieldset>

          {(() => {
            const unpriced = d.items.filter((r) => r.cost_min === null)
            return unpriced.length > 0 && (
              <p className="text-[11px] text-ink-3">
                Not counted (no verified price, check the item's links): {unpriced.map((r) => r.label).join('; ')}.
              </p>
            )
          })()}
        </div>
      )}
    </Card>
  )
}

export default ShoppingBudgetCard
