import type { TopicDef } from '../types'

/**
 * Help for the Preparedness shopping panel and budget card (components/prep/Shopping*.tsx,
 * backend app/shopping). Links checked on 2026-09-24. Register in content.ts:
 *   import { SHOPPING_TOPICS } from './topics/shopping'   and add ...SHOPPING_TOPICS to ALL.
 */
export const SHOPPING_TOPICS = {
  shopping_panel: {
    title: 'Where to buy (the "Buy" panel)',
    category: 'prep',
    aliases: ['buy', 'shop', 'lazada', 'shopee', 'makro', 'homepro', 'global house', 'price'],
    short: 'Under each item you can buy: what to look for, prices seen on real shop pages (with date and link), search links for Lazada, Shopee and Thai retailers, and the stores on Samui that sell it.',
    body: `Open **Buy** under a checklist item to see:

- **What to buy**: the recommended spec and, in one line, why it matters for safety or quality ([[shopping_specs]]).
- **Prices seen**: real listings (Makro, HomePro, Global House, or marketplace sellers seen via the Priceza price-comparison site), each with its price, the date it was checked and a link. For your household the panel adds up the cost, rounded up to whole packs ([[shopping_price_range]]).
- **Search online**: ready-made searches on Lazada and Shopee (in English and Thai, which often finds more) and on the retailers' own sites.
- **On Samui**: stores on the island that sell this kind of item, with a map search and the page that confirms the store exists.

Items that are plans, documents or habits (departure plan, passport copies, offline maps...) have no Buy panel.`,
    howToRead: `The chip on the right says how much to trust the price:

- **Price checked**: seen on the shop page less than 60 days ago.
- **Re-check price**: the prices are over 60 days old; open the links first.
- **No verified price**: no reliable price was found; use the links.`,
    whyItMatters: 'When a storm is forecast, shelves on the island empty fast and ferries can stop. Knowing in advance what to buy, where, and roughly how much it costs lets you buy calmly and early.',
    thresholds: {
      columns: ['Chip', 'Meaning'],
      rows: [
        ['Price checked', 'Prices seen on the shop pages less than 60 days ago.'],
        ['Re-check price', 'Prices older than 60 days: confirm before relying on them.'],
        ['No verified price', 'No reliable dated price was found: check the links.'],
      ],
    },
    related: ['shopping_price_range', 'shopping_specs', 'shopping_samui_vs_online', 'shopping_counterfeits', 'shopping_budget', 'preparedness'],
    sources: [
      { title: 'Makro online (Thailand)', url: 'https://www.makro.pro/en' },
      { title: 'HomePro online (Thailand)', url: 'https://www.homepro.co.th/' },
      { title: 'Priceza (Thai price comparison)', url: 'https://www.priceza.com/' },
    ],
  },
  shopping_price_range: {
    title: 'What the price range means',
    category: 'prep',
    aliases: ['price range', 'THB', 'baht', 'indicative', 'checked on', 're-check'],
    short: 'The cheapest to the dearest listing seen on the date shown, for the quantity on your checklist rounded up to whole packs. Indicative only: prices change and delivery is not included.',
    body: `Each price was read by hand on a shop page on the "checked" date and saved with its link. Nothing is scraped live (Lazada and Shopee forbid it, and a wrong live price is worse than a dated, sourced one).

For your household, every listing is turned into a cost: packs needed = your quantity divided by what one pack holds, **rounded up**; cost = packs x pack price. The range goes from the cheapest listing to the dearest.

Example: 112 L of drinking water (2 people x 4 L x 14 days). 6 L bottles at 35 THB need 19 bottles = 665 THB; 9 L packs (6 x 1.5 L) at 40 THB need 13 packs = 520 THB.`,
    howToRead: '"4.44-6.33 THB per L" is a unit price (price per litre); "520-722 THB" under "For your household" is what your quantity costs. A price marked "marketplace seller" came from a Lazada or Shopee seller listed on Priceza: it varies more, and fakes are more likely.',
    whyItMatters: 'A range is more honest than one number: the same item can cost several times more from a premium brand or a small seller. Plan with the upper value if you want to be sure.',
    example: 'Food per person-day uses a stated assumption (for example 3 cans of fish per person per day); it is shown under the item.',
    related: ['shopping_budget', 'shopping_panel', 'freshness'],
    sources: [
      { title: 'Makro online (Thailand)', url: 'https://www.makro.pro/en' },
      { title: 'Global House online (Thailand)', url: 'https://www.globalhouse.co.th/' },
    ],
  },
  shopping_specs: {
    title: 'Why the recommended spec matters',
    category: 'prep',
    aliases: ['spec', 'N95', 'KN95', 'LiFePO4', 'Wh', 'DEET', 'icaridin', 'picaridin', 'ORS', '0.1 micron', 'HEPA', 'CADR'],
    short: 'For safety items the certification or strength decides whether the product protects you: a mask without N95/KN95/P2, a repellent without enough DEET or icaridin, or a filter coarser than 0.1 micron does not do the job.',
    body: `Key specs used in the panel, in plain English:

- **Masks**: only certified respirators filter PM2.5: N95 (US NIOSH), KN95 (China GB 2626) or P2 (Australia/NZ), printed on the mask. Cloth and surgical masks do not.
- **Water filter**: a hollow-fibre membrane rated 0.1 micron removes bacteria and protozoa but not viruses or chemicals: still boil or chlorinate doubtful water.
- **Bleach for water**: the label must say sodium hypochlorite 5-6%, unscented; colour-safe bleach is not chlorine.
- **Repellent**: DEET 20-30% or icaridin (picaridin) about 20% on the label (US EPA-registered actives).
- **ORS**: pharmacy oral rehydration salts (WHO formula), not sports drinks.
- **Power station**: LiFePO4 battery (long life, safer); size it in Wh. A phone charge is about 15-20 Wh, a USB fan 5-10 W; a fridge needs about 1 kWh per day.
- **Power bank**: 20,000 mAh is about 74 Wh; buy a known brand with the Thai TIS mark.
- **Air purifier**: HEPA, with a CADR / room size at least as big as the room you seal.
- **Water tank / jerrycans**: food-grade, opaque, tight lid (no algae, no mosquitoes).`,
    whyItMatters: 'In an emergency you rely on the item working the first time. Fakes and under-spec products are common online and look the same in photos.',
    related: ['shopping_counterfeits', 'prep_health', 'prep_haze', 'prep_power', 'prep_water'],
    sources: [
      { title: 'US EPA -- Find the insect repellent that is right for you', url: 'https://www.epa.gov/insect-repellents/find-repellent-right-you' },
      { title: 'US EPA -- Guide to air cleaners in the home', url: 'https://www.epa.gov/indoor-air-quality-iaq/guide-air-cleaners-home' },
      { title: 'WHO -- Diarrhoeal disease fact sheet (ORS)', url: 'https://www.who.int/news-room/fact-sheets/detail/diarrhoeal-disease' },
    ],
  },
  shopping_samui_vs_online: {
    title: 'Buying on Samui vs ordering online',
    category: 'prep',
    aliases: ['delivery', 'Samui stores', 'Makro Samui', 'Global House Maenam', 'HomePro Samui', 'ferry', 'online order'],
    short: 'Island stores let you buy today. Lazada and Shopee do deliver to Samui, but most parcels cross by ferry and take longer than to the mainland; when rough seas stop the ferries, deliveries stop too. Buy before a storm, not during it.',
    body: `**On the island** (checked 2026-09-24): Global House in Maenam (tanks, jerrycans, tarps, rope, boots, fans), Makro and HomePro in Bophut, Big C in Bophut, several Lotus's (Chaweng, Lamai...), and Boots at Central Samui in Chaweng, plus local pharmacies. The panel gives a map search for each; stock is not checked, so call before a special trip.

**Online**: Lazada and Shopee deliver to Koh Samui. Delivery usually takes longer than to Bangkok because parcels cross by ferry; the estimate is shown at checkout. Specialist items (0.1 micron filters, crank radios, purification tablets) are often online only.

**Before a storm**: order online weeks ahead in the calm season; in the days before a forecast storm buy locally; once ferries are cancelled, assume no parcel will arrive.`,
    whyItMatters: 'Rough seas in the northeast monsoon (October-January) stop ferries, and with them shop restocking and parcel deliveries. Stock bought early is the only stock you can count on.',
    related: ['shopping_panel', 'prep_exit', 'preparedness'],
    sources: [
      { title: 'Makro -- Ko Samui branch', url: 'https://www.makro.co.th/en/contact-us/31/Ko-Samui' },
      { title: 'Ko Samui Life -- Global House Samui opens (Maenam)', url: 'https://www.kosamuilife.com/post/global-house-the-biggest-home-improvement-store-in-samui-is-now-open' },
      { title: 'Seatran Ferry (crossings and cancellations)', url: 'https://www.seatranferry.com/' },
    ],
  },
  shopping_counterfeits: {
    title: 'Fakes: how to spot official stores',
    category: 'prep',
    aliases: ['counterfeit', 'fake', 'LazMall', 'Shopee Mall', 'official store', 'genuine'],
    short: 'Masks, water filters, power banks and branded batteries are often faked. On Lazada buy from LazMall stores, on Shopee from Shopee Mall stores (official brand shops), or from a big retailer.',
    body: `Warning signs of a fake or unsafe product:

- A price far below the other listings (for example a famous-brand filter or mask at a fraction of the usual price).
- A seller that is not the brand's official shop, with few ratings.
- Missing certification marks (N95 / KN95 / P2 on masks; the Thai TIS mark on power banks) or blurry printing.
- A power bank that is much lighter than a genuine one of the same capacity.

Safer choices:

- **LazMall** (Lazada) and **Shopee Mall** (Shopee) list official brand stores and authorised sellers.
- Big retailers (Makro, HomePro, Global House, Boots) sell through their own shops.
- Keep the receipt, check the product on arrival, and test power banks and radios before you need them.`,
    whyItMatters: 'A fake mask does not filter haze, a fake filter can let bacteria through and a fake power bank can overheat. In an emergency you only find out when it is too late.',
    related: ['shopping_specs', 'shopping_panel'],
    sources: [
      { title: 'LazMall (Lazada official stores)', url: 'https://www.lazada.co.th/lazmall/' },
      { title: 'Shopee Mall (official stores)', url: 'https://shopee.co.th/mall' },
    ],
  },
  shopping_budget: {
    title: 'The shopping budget card',
    category: 'prep',
    aliases: ['budget', 'total cost', 'how much', 'THB total'],
    short: 'Indicative cost of the whole checklist for your household (adults, children, days), split by priority (Essential / Recommended / Useful) and by category, using the prices seen on the date shown.',
    body: `The card multiplies each item's quantity by your household and days (the same rule as the checklist), prices it from the listings in the Buy panels, and adds everything up.

- **Essential / Recommended / Useful** follow the checklist priorities. Start with Essential.
- Items without a verified price are **listed, not counted as zero** ("to check").
- A water tank (only if you have none) and baby / pet items (only if you need them) are left out unless you tick them.
- Delivery, installation and fuel are not included. Food uses stated per-day assumptions.

The date under the card is when the prices were checked; after 60 days the card asks you to re-check.`,
    howToRead: 'The first number is the cheapest combination, the second the dearest. Big items (power station, generator, purifier) dominate the total: the Essential line is usually much smaller.',
    whyItMatters: 'Seeing the cost by priority helps decide what to buy first, and spreading purchases over the calm months avoids panic buying when a storm is announced.',
    related: ['shopping_price_range', 'shopping_panel', 'preparedness'],
    sources: [
      { title: 'Ready.gov -- Build a Kit', url: 'https://www.ready.gov/kit' },
      { title: 'Makro online (Thailand)', url: 'https://www.makro.pro/en' },
    ],
  },
} satisfies Record<string, TopicDef>
