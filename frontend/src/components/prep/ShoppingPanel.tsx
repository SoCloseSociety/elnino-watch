/**
 * Per-item "Buy" panel for the Preparedness checklist: where to buy (online search links,
 * physical stores on Samui with a map search), prices seen on real listings with their
 * date and link, and the recommended spec. Renders nothing for items that are not bought
 * (plans, documents, habits) or when the shopping API is not available.
 *
 *   <ShoppingPanel itemId={it.id} needed={qtyNumber} />
 */
import { useShopping, fmtBaht, fmtRange, ShopHelp, STATUS_META, type ShopItem, type ShopListing } from './ShoppingShared'

function packCost(listings: ShopListing[], needed: number): [number, number] | null {
  const costs = listings.filter((l) => l.units && l.price_thb > 0).map((l) => Math.ceil(+(needed / (l.units as number)).toFixed(9)) * l.price_thb)
  return costs.length ? [Math.min(...costs), Math.max(...costs)] : null
}

function estimate(it: ShopItem, needed: number | undefined): [number, number] | null {
  if (it.components?.length) {
    let lo = 0, hi = 0
    for (const c of it.components) {
      const r = packCost(c.listings, c.count)
      if (!r) return null
      lo += r[0]; hi += r[1]
    }
    return [lo, hi]
  }
  if (needed === undefined || !it.listings?.length) return null
  return packCost(it.listings, needed)
}

function ListingRow({ l }: { l: ShopListing }) {
  return (
    <li className="flex flex-wrap items-baseline gap-x-2 py-1 text-[12px]">
      <a className="link min-w-0 flex-1" href={l.url} target="_blank" rel="noreferrer">{l.title} ↗</a>
      <span className="font-semibold tnum">{fmtBaht(l.price_thb)} THB</span>
      <span className="w-full text-[11px] text-ink-3">
        {l.source === 'marketplace' ? `Marketplace seller seen on ${l.retailer_name}` : l.retailer_name}
        {l.unit_price_thb !== null && l.units !== 1 ? ` · ${fmtBaht(l.unit_price_thb)} THB per unit` : ''}
        {' · checked '}{l.checked_at}
        {l.recheck && <span style={{ color: 'var(--serious)' }}> · ▲ re-check</span>}
      </span>
    </li>
  )
}

export function ShoppingPanel({ itemId, needed, defaultOpen = false }: {
  itemId: string
  /** household quantity in the item's unit (as shown on the checklist), for the cost estimate */
  needed?: number
  defaultOpen?: boolean
}) {
  const q = useShopping()
  const it = q.data?.items[itemId]
  if (!it || !it.buyable) return null
  const st = STATUS_META[it.price_status]
  const est = estimate(it, needed)
  const unit = it.unit_price
  const summary = est ? fmtRange(est[0], est[1]) : unit ? `${fmtRange(unit.min, unit.max)}${unit.unit ? ` per ${unit.unit}` : ''}` : 'check link'
  const online = (it.search_links ?? []).filter((l) => l.kind !== 'comparison')
  const compare = (it.search_links ?? []).filter((l) => l.kind === 'comparison')

  return (
    <details className="group mt-1 rounded-md border border-line bg-surface-2/40 text-[12px]" open={defaultOpen}>
      <summary className="flex min-h-9 cursor-pointer list-none flex-wrap items-center gap-x-2 gap-y-1 px-2 py-1 sm:min-h-0">
        <span aria-hidden className="text-ink-3 transition-transform group-open:rotate-90">▸</span>
        <span className="font-semibold">Buy</span>
        <span className="tnum text-ink-2">{summary}</span>
        {it.budget_mode && it.budget_mode !== 'default' && (
          <span className="text-[11px] text-ink-3">({it.budget_mode === 'optional' ? 'only if you have none' : 'only if needed'})</span>
        )}
        <span className="chip ml-auto" title={st.hint} style={{ color: st.color, borderColor: st.color }}>{st.icon} {st.label}</span>
        <ShopHelp id="shopping_panel" title="Where to buy"
          text="Shop links, prices seen on real listings (with the date and link) and the spec to look for. Prices are indicative: confirm on the shop page." />
      </summary>

      <div className="space-y-3 border-t border-line px-3 py-2">
        {(it.spec || it.why) && (
          <section>
            <h4 className="flex items-center gap-1 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">
              What to buy <ShopHelp id="shopping_specs" title="Why the spec matters" text="For safety items (masks, filters, batteries, repellent) the certification or strength decides whether it protects you. The line under the spec says why." />
            </h4>
            {it.spec && <p className="mt-0.5">{it.spec}</p>}
            {it.why && <p className="mt-0.5 text-ink-2">Why: {it.why}</p>}
          </section>
        )}

        <section>
          <h4 className="flex items-center gap-1 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">
            Prices seen <ShopHelp id="shopping_price_range" title="What the price range means" text="Cheapest to dearest listing seen on the date shown, for the quantity on your checklist rounded up to whole packs. Delivery is not included." />
          </h4>
          {est && needed !== undefined && !it.components?.length && (
            <p className="mt-0.5 text-ink-2">For your household ({+needed.toFixed(2)} {it.unit ?? ''}): <b className="tnum">{fmtRange(est[0], est[1])}</b>, rounded up to whole packs.</p>
          )}
          {it.assumption && <p className="mt-0.5 text-[11px] text-ink-3">Assumption: {it.assumption}</p>}
          {it.components?.length ? it.components.map((c) => (
            <div key={c.id} className="mt-1">
              <div className="text-[11px] font-semibold text-ink-2">{c.label}{c.count > 1 ? ` x ${c.count}` : ''}</div>
              <ul className="divide-y divide-line">{c.listings.map((l) => <ListingRow key={l.url + l.title} l={l} />)}</ul>
            </div>
          )) : it.listings?.length ? (
            <ul className="divide-y divide-line">{it.listings.map((l) => <ListingRow key={l.url + l.title} l={l} />)}</ul>
          ) : (
            <p className="mt-0.5 text-ink-2">No verified price: check the links below.</p>
          )}
          {it.price_note && <p className="mt-1 text-[11px] text-ink-2">Note: {it.price_note}</p>}
        </section>

        {(online.length > 0 || compare.length > 0) && (
          <section>
            <h4 className="flex items-center gap-1 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">
              Search online <ShopHelp id="shopping_counterfeits" title="Fakes and official stores" text="Masks, filters and power banks are often faked. On Lazada pick LazMall, on Shopee pick Shopee Mall (official brand stores)." />
            </h4>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {[...online, ...compare].map((l) => (
                <a key={l.url} className="btn !px-2 !py-0.5 text-[12px]" href={l.url} target="_blank" rel="noreferrer" title={l.hint ?? l.query ?? l.name}>
                  {l.name}{l.lang ? ` (${l.lang})` : ''} ↗
                </a>
              ))}
            </div>
            {online.some((l) => l.hint) && <p className="mt-1 text-[11px] text-ink-3">Prefer LazMall / Shopee Mall (official brand stores).</p>}
          </section>
        )}

        {it.local_stores && it.local_stores.length > 0 && (
          <section>
            <h4 className="flex items-center gap-1 text-[11px] font-semibold tracking-wide text-ink-3 uppercase">
              On Samui <ShopHelp id="shopping_samui_vs_online" title="Buying on Samui vs online" text="Island stores let you buy today. Online orders take longer to reach Samui and stop when ferries stop: buy before a storm, not during it." />
            </h4>
            <ul className="mt-0.5 space-y-0.5">
              {it.local_stores.map((s) => (
                <li key={s.id}>
                  <a className="link" href={s.maps_url} target="_blank" rel="noreferrer">{s.name} ↗</a>
                  {s.area && <span className="text-ink-3"> · {s.area}</span>}
                  {s.source && <> · <a className="link text-[11px]" href={s.source} target="_blank" rel="noreferrer">source</a></>}
                </li>
              ))}
            </ul>
            <p className="mt-0.5 text-[11px] text-ink-3">Stock is not checked: call or visit before a special trip.</p>
          </section>
        )}
      </div>
    </details>
  )
}

export default ShoppingPanel
