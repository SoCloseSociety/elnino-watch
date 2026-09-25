"""Curated shopping data for the preparedness items (Koh Samui, Thailand).

Built by hand on CHECKED_AT from real listings (no runtime scraping):
- Makro (makro.pro), HomePro (homepro.co.th) and Global House (globalhouse.co.th):
  retailers' own product pages, price as displayed that day (incl. any promotion).
- Priceza (priceza.com): a Thai price-comparison site listing Lazada / Shopee / shop
  offers. Used only where the big retailers had no listing; those prices come from
  marketplace sellers and vary more (see `source` on each listing).
Where no price could be verified, `listings` is empty and the item says "check link".
Never add a price you did not see on a page; record the page URL.

Item entry:
  id              preparedness item id (app/local/preparedness.py)
  buyable         False for plans, documents, habits (then `reason`)
  q_en / q_th     search keywords (English / Thai) used to build the shop links
  shops           online retailers to link (keys of RETAILERS)
  local           physical Samui stores likely to stock it (keys of STORES)
  spec / why      recommended spec and a plain-English reason (safety / quality)
  listings        observed offers: {retailer, title, price (THB), units, url, source}
                  `units` = how many checklist units (the item's `unit`, e.g. L,
                  items, person-days) one listing covers; None = cannot be converted.
  components      for kits: [{id, label, count, listings}] (count packs, fixed)
  assumption      how `units` was derived when it is not obvious (food)
  budget          "default" | "conditional" (only if the household needs it) |
                  "optional" (only if you do not have one yet): only "default" is
                  summed unless the caller asks for the others.
  price_note      why there is no price / what is not included
"""

from __future__ import annotations

CHECKED_AT = "2026-09-24"
STALE_AFTER_DAYS = 60

# Online retailers: search URL templates ({q} = url-encoded keywords).
# Every template was opened on CHECKED_AT and returned a normal search page (HTTP 200).
RETAILERS = {
    "lazada": {"name": "Lazada TH", "kind": "marketplace",
               "search": "https://www.lazada.co.th/catalog/?q={q}",
               "official_hint": "Prefer LazMall (official brand stores)."},
    "shopee": {"name": "Shopee TH", "kind": "marketplace",
               "search": "https://shopee.co.th/search?keyword={q}",
               "official_hint": "Prefer Shopee Mall (official brand stores)."},
    "makro": {"name": "Makro", "kind": "retailer",
              "search": "https://www.makro.pro/en/c/search?q={q}"},
    "homepro": {"name": "HomePro", "kind": "retailer",
                "search": "https://www.homepro.co.th/search?q={q}"},
    "globalhouse": {"name": "Global House", "kind": "retailer",
                    "search": "https://www.globalhouse.co.th/search?keyword={q}"},
    "lotuss": {"name": "Lotus's", "kind": "retailer",
               "search": "https://www.lotuss.com/en/search/{q}"},
    "seven": {"name": "7-Eleven (All Online)", "kind": "retailer",
              "search": "https://www.allonline.7eleven.co.th/search/?q={q}"},
    "priceza": {"name": "Priceza (price comparison)", "kind": "comparison",
                "search": "https://www.priceza.com/s/%E0%B8%A3%E0%B8%B2%E0%B8%84%E0%B8%B2/{q}"},
}

# Physical stores on Koh Samui. Each one was checked to exist (source) on CHECKED_AT.
# maps_q feeds a Google Maps search link (no coordinates are invented here).
STORES = {
    "makro_samui": {
        "name": "Makro Koh Samui", "area": "Bophut",
        "address": "115/52 Moo 6, Bophut, Koh Samui",
        "maps_q": "Makro Koh Samui",
        "sells": "Bulk water, food, gas canisters, batteries, basic medicine, cleaning.",
        "source": "https://www.makro.co.th/en/contact-us/31/Ko-Samui"},
    "globalhouse_samui": {
        "name": "Global House Samui", "area": "Maenam",
        "address": "107/60 Moo 4, Maenam, Koh Samui",
        "maps_q": "Global House Samui Maenam",
        "sells": "Water tanks, jerrycans, tarps, rope, boots, fans, torches, tools.",
        "source": "https://www.kosamuilife.com/post/"
                  "global-house-the-biggest-home-improvement-store-in-samui-is-now-open"},
    "homepro_samui": {
        "name": "HomePro Samui", "area": "Bophut",
        "address": "1/7 Moo 6, Bophut, Koh Samui",
        "maps_q": "HomePro Samui",
        "sells": "Power stations, generators, purifiers, filters, tarps, tools.",
        "source": "https://www.soidb.com/samui/store/homepro-tesco-samui.html"},
    "bigc_samui": {
        "name": "Big C Supercenter Samui", "area": "Bophut",
        "address": "Bophut, Koh Samui",
        "maps_q": "Big C Supercenter Samui",
        "sells": "Groceries, water, household goods; has a Boots inside.",
        "source": "https://samui-map.info/listing/boots-big-c-samui/"},
    "lotuss_samui": {
        "name": "Lotus's (several branches)", "area": "Chaweng, Lamai and others",
        "address": None,
        "maps_q": "Lotus's Koh Samui",
        "sells": "Groceries, water, household goods.",
        "source": "https://www.estate-samui-properties.com/supermarkets-on-koh-samui-guide/"},
    "boots_central": {
        "name": "Boots, Central Samui", "area": "Chaweng",
        "address": "Central Samui, Chaweng",
        "maps_q": "Boots Central Samui Chaweng",
        "sells": "Pharmacy: paracetamol, ORS, repellent, first aid, masks.",
        "source": "https://samui-map.info/listing/boots-central-samui/"},
}

# A search (not a specific store): any local pharmacy (ร้านขายยา) near Maenam.
PHARMACY_SEARCH = {"name": "Pharmacies near Maenam (map search)",
                   "maps_q": "pharmacy Maenam Koh Samui"}

REFERENCES = {
    "epa_repellent": "https://www.epa.gov/insect-repellents/find-repellent-right-you",
    "who_diarrhoea": "https://www.who.int/news-room/fact-sheets/detail/diarrhoeal-disease",
    "epa_air_cleaner": "https://www.epa.gov/indoor-air-quality-iaq/guide-air-cleaners-home",
    "ready_power": "https://www.ready.gov/power-outages",
    "ready_water": "https://www.ready.gov/water",
    "who_dengue": "https://www.who.int/news-room/fact-sheets/detail/dengue-and-severe-dengue",
    "pttor_price": "https://www.pttor.com/en/oil_price",
}

MK, HP, GH, PZ = "makro", "homepro", "globalhouse", "priceza"
MKP = "https://www.makro.pro/en/p/"
HPP = "https://www.homepro.co.th/p/"
GHP = "https://www.globalhouse.co.th/product/"
PZS = "https://www.priceza.com/s/%E0%B8%A3%E0%B8%B2%E0%B8%84%E0%B8%B2/"


def L(retailer, title, price, units, url, source="retailer"):
    """One observed listing. source: "retailer" (shop's own page) or "marketplace"
    (a marketplace seller seen via a price-comparison page)."""
    return {"retailer": retailer, "title": title, "price": price, "units": units,
            "url": url, "source": source}


def _no(id_, reason):
    return {"id": id_, "buyable": False, "reason": reason}


GROCERY = ["makro", "lotuss", "seven", "lazada", "shopee"]
HARDWARE = ["globalhouse", "homepro", "lazada", "shopee"]
PHARMA = ["makro", "lazada", "shopee"]

_BOTTLED = [
    L(MK, "ARO Drinking Water 6 l", 35, 6, MKP + "6-8qknh-7497612230851"),
    L(MK, "NESTLE PURELIFE Drinking Water 6 l", 35, 6, MKP + "5nxkbw-7078738100419"),
    L(MK, "SINGHA Drinking Water 6 l", 38, 6, MKP + "xggshch-7078737576131"),
    L(MK, "NEPTUNE Drinking Water 1.5 l x 6", 40, 9, MKP + "mbfjxsh-6814746116291"),
    L(MK, "CRYSTAL Drinking Water 1.5 l x 6", 49, 9, MKP + "f39w5ot-6814746017987"),
]
_BOTTLED_SPEC = ("Sealed bottles from a known brand; 6 L bottles are cheapest per litre, "
                 "1.5 L bottles are easier to carry and ration.")
_BOTTLED_WHY = ("Factory-sealed water stays safe without power or boiling. Store it out of "
                "the sun: heat makes PET bottles taste of plastic.")

ITEMS: list[dict] = [
    # ------------------------------------------------------------------ water
    {"id": "water_drink", "buyable": True, "q_en": "drinking water 6 L",
     "q_th": "น้ำดื่ม 6 ลิตร", "shops": GROCERY,
     "local": ["makro_samui", "bigc_samui", "lotuss_samui"],
     "spec": _BOTTLED_SPEC, "why": _BOTTLED_WHY, "listings": _BOTTLED},
    {"id": "water_cook", "buyable": True, "q_en": "drinking water 6 L",
     "q_th": "น้ำดื่ม 6 ลิตร", "shops": GROCERY,
     "local": ["makro_samui", "bigc_samui", "lotuss_samui"],
     "spec": _BOTTLED_SPEC, "why": _BOTTLED_WHY, "listings": _BOTTLED},
    _no("water_hygiene", "Comes from the tap, your tank or a water truck, not from shops. "
        "Water-truck prices are local: ask neighbours or your landlord."),
    {"id": "water_tank", "buyable": True, "budget": "optional",
     "q_en": "water tank 1000 L", "q_th": "ถังเก็บน้ำ 1000 ลิตร",
     "shops": HARDWARE, "local": ["globalhouse_samui", "homepro_samui"],
     "spec": "Above-ground PE tank, 1000-2000 L (the common sizes on sale), opaque, "
             "food-grade and UV-stabilised, with a tight lid and a screened overflow.",
     "why": "An opaque tank stops algae; a tight lid keeps out dengue mosquitoes. 1000 L "
            "is about 10 days of basic needs (WHO 7.5-15 L/person/day) for 4-6 people.",
     "listings": [
         L(GH, "WAVE above-ground tank 1000 L, Pailin-1000", 3390, 1,
           GHP + "WAVE-ถังเก็บน้ำบนดิน-1000L-รุ่น-Pailin1000-i.8859332307040"),
         L(GH, "DOS above-ground tank 1000 L, Ice", 3590, 1,
           GHP + "DOS-ถังเก็บน้ำบนดินสีเรียบ-ขนาด-1000L-รุ่น-Ice-สี-Ice-Blue-i.8859738100078"),
         L(HP, "WAVE Orchid Selected tank 1000 L", 16890, 1, HPP + "1202029"),
     ],
     "price_note": "Only if you have no tank: the checklist item is keeping yours full "
                   "and clean. Delivery and plumbing are extra."},
    {"id": "water_jerrycans", "buyable": True, "q_en": "20 litre water container",
     "q_th": "แกลลอนน้ำดื่ม 20 ลิตร", "shops": HARDWARE,
     "local": ["globalhouse_samui", "homepro_samui", "makro_samui"],
     "spec": "Food-grade HDPE (PE) container, 20 L, screw cap, ideally with a tap.",
     "why": "Non-food plastics can leach chemicals into water; 20 L (20 kg) is the most "
            "one adult can carry.",
     "listings": [
         L(GH, "Dragon brand plastic container 20 L, blue", 139, 1,
           GHP + "ตรามังกร-ถังแกลลอนพลาสติก-20-ลิตร-สีฟ้า-i.8859178406327"),
         L(HP, "SPRING water gallon 20 L, blue", 149, 1, HPP + "1132219"),
         L(GH, "Hand brand square drinking-water gallon 20 L, RW.9239", 325, 1,
           GHP + "ตรามือ-แกลลอนน้ำดื่ม-แบบเหลี่ยม-20-ลิตร-ขนาด-21.2x32.5x38cm.-RW.9239"
                 "-สีขาว-i.8850421923905"),
     ]},
    {"id": "water_filter", "buyable": True, "q_en": "Sawyer Squeeze water filter",
     "q_th": "เครื่องกรองน้ำพกพา sawyer", "shops": ["lazada", "shopee", "priceza"],
     "local": [],
     "spec": "Hollow-fibre membrane filter rated 0.1 micron absolute (for example Sawyer "
             "Squeeze or Mini), usable as a gravity filter with a hanging bag.",
     "why": "0.1 micron removes bacteria and protozoa, but NOT viruses or chemicals: boil "
            "or add chlorine as well when the water source is doubtful.",
     "listings": [
         L(PZ, "Sawyer Mini filter (marketplace seller)", 1142, 1,
           PZS + "%E0%B9%80%E0%B8%84%E0%B8%A3%E0%B8%B7%E0%B9%88%E0%B8%AD%E0%B8%87%E0%B8%81"
                 "%E0%B8%A3%E0%B8%AD%E0%B8%87%E0%B8%99%E0%B9%89%E0%B8%B3%20sawyer",
           "marketplace"),
         L(PZ, "Sawyer Squeeze SP129 (marketplace seller)", 2546, 1,
           PZS + "sawyer%20squeeze", "marketplace"),
         L(PZ, "Sawyer Squeeze SP303 with 2 L bag (marketplace seller)", 3295, 1,
           PZS + "sawyer%20squeeze", "marketplace"),
     ],
     "price_note": "Not stocked by the Samui stores checked: order online, allow extra "
                   "delivery days. Prices from marketplace sellers: buy from an official "
                   "store to avoid fakes."},
    {"id": "water_tablets", "buyable": True, "q_en": "Aquatabs water purification tablets",
     "q_th": "เม็ดฟอกน้ำ aquatabs", "shops": ["lazada", "shopee", "priceza"],
     "local": ["boots_central"],
     "spec": "Drinking-water tablets with NaDCC (sodium dichloroisocyanurate), for "
             "example Aquatabs, sized for your container (1 L or 20 L per tablet).",
     "why": "Dose depends on the water volume: a tablet made for 20 L is far too strong "
            "for a 1 L bottle. Pool chlorine tablets are NOT for drinking water.",
     "listings": [],
     "price_note": "No reliable price seen: the listings found mixed pack sizes and "
                   "expiry dates. Check link."},
    {"id": "water_bleach", "buyable": True, "q_en": "Haiter bleach", "q_th": "ไฮเตอร์",
     "shops": GROCERY, "local": ["makro_samui", "bigc_samui", "lotuss_samui"],
     "spec": "Plain liquid chlorine bleach whose label says sodium hypochlorite "
             "(โซเดียมไฮโปคลอไรต์) at 5-6%, no scent or additives.",
     "why": "Ready.gov's dose (1/8 teaspoon per 3.8 L) only works at that strength. "
            "Colour-safe bleaches are not chlorine and do not disinfect water.",
     "listings": [
         L(MK, "HAITER Bleach Pink 2.5 l", 79, 2.5, MKP + "8otxzmp-7078773162179"),
         L(MK, "HAITER Liquid Bleach Blue 5 l", 164, 5, MKP + "aeug4ka-7078771523779"),
     ],
     "price_note": "Read the label before using it for water: check the strength and "
                   "that it is unscented."},
    {"id": "water_boil", "buyable": True, "q_en": "portable gas stove butane",
     "q_th": "เตาแก๊สปิคนิค", "shops": HARDWARE + ["makro"],
     "local": ["homepro_samui", "globalhouse_samui", "makro_samui"],
     "spec": "Butane cassette stove with a pressure-sensing safety shut-off; uses standard "
             "250 g canisters.",
     "why": "The safety shut-off releases the canister if it overheats. Standard 250 g "
            "canisters are sold everywhere on the island.",
     "listings": [
         L(HP, "GAZU portable gas stove GZ-MS155BK", 337, 1, HPP + "1300666"),
         L(HP, "KUCINE portable gas stove SLJ-14", 527, 1, HPP + "1272512"),
         L(MK, "IWATANI gas picnic stove CB-BS-1T", 1590, 1,
           MKP + "I3-Zqv-A-662012282668294"),
     ]},
    # ------------------------------------------------------------------ food
    {"id": "food_nocook", "buyable": True, "q_en": "canned sardines", "q_th": "ปลากระป๋อง",
     "shops": GROCERY, "local": ["makro_samui", "bigc_samui", "lotuss_samui"],
     "spec": "Canned fish, beans and ready meals with ring-pull lids, dates at least 6 "
             "months ahead.",
     "why": "No cooking, no fridge, no water needed. Ring-pull lids work even if the can "
            "opener is lost.",
     "assumption": "Budget assumes 3 cans (about 150-170 g each) per person per day. "
                   "That covers protein, not all calories: add snacks and rice.",
     "listings": [
         L(MK, "U-CHEF Sardines in Tomato Sauce 145 g x 10", 125, 10 / 3,
           MKP + "gf1dub1-7275731583171"),
         L(MK, "SEALECT Sardines in Tomato Sauce 155 g x 10+1", 165, 11 / 3,
           MKP + "dyqqgsn-7248036036803"),
         L(MK, "ARO Tuna Chunk in Brine 165 g x 4", 133, 4 / 3,
           MKP + "Cn5it_35-579094132696992"),
         L(MK, "SEALECT Tuna Steak In Spring Water 165 g x 4", 173, 4 / 3,
           MKP + "ylif2dk-7078801768643"),
     ]},
    {"id": "food_snacks", "buyable": True, "q_en": "mixed nuts", "q_th": "ถั่วรวม",
     "shops": GROCERY, "local": ["makro_samui", "bigc_samui", "lotuss_samui"],
     "spec": "Energy-dense, sealed: nuts, dried fruit, biscuits, cereal bars.",
     "why": "Many calories per gram, keep for months, no preparation.",
     "assumption": "Budget assumes about 150 g per person per day.",
     "listings": [
         L(MK, "ARO Black Raisin 1 kg", 155, 1000 / 150, MKP + "r-cwtwx-6761193930947"),
         L(MK, "ARO Choco Bear Biscuit 450 g", 69, 3, MKP + "8ejcuv9-7416136564931"),
         L(MK, "TONG GARDEN Cocktail Nut 400 g", 255, 400 / 150,
           MKP + "prbm1j2-7497391243459"),
         L(MK, "NUT WALKER Mixed Nuts 454 g", 345, 454 / 150, MKP + "y_0il3k-7497559015619"),
     ]},
    {"id": "food_rice", "buyable": True, "q_en": "jasmine rice 5 kg",
     "q_th": "ข้าวหอมมะลิ 5 กก.", "shops": GROCERY,
     "local": ["makro_samui", "bigc_samui", "lotuss_samui"],
     "spec": "Rice in sealed bags and instant noodles; keep dry and off the floor.",
     "why": "Cheap calories, but needs water and gas: only a complement.",
     "assumption": "Budget assumes 150 g of dry rice, or 2 packs of instant noodles, per "
                   "person per day.",
     "listings": [
         L(MK, "PANOMRUNG Jasmine Rice 100% 5 kg", 150, 5000 / 150,
           MKP + "pdndrjc-6761202712771"),
         L(MK, "ROYAL UMBRELLA Jasmine Rice 100% 5 kg", 243, 5000 / 150,
           MKP + "csqforj-6974763237571"),
         L(MK, "MAMA Instant Noodles Tom Yum Kung 55 g 10 pcs", 65, 5,
           MKP + "8pmxf8z-6974763958467"),
     ]},
    {"id": "food_opener", "buyable": True, "q_en": "can opener", "q_th": "ที่เปิดกระป๋อง",
     "shops": GROCERY[:1] + HARDWARE, "local": ["makro_samui", "bigc_samui"],
     "spec": "Manual stainless steel can opener.",
     "why": "Stainless does not rust in Samui's humidity.",
     "listings": [
         L(MK, "ARO Stainless Can Opener", 169, 1, MKP + "bmnx60n-7497358475459"),
         L(MK, "ANCHOR Can Opener Model 3026", 189, 1, MKP + "a09wfbj-7196417622211"),
     ]},
    {"id": "food_gas", "buyable": True, "q_en": "butane gas canister 250 g",
     "q_th": "แก๊สกระป๋อง", "shops": GROCERY[:1] + HARDWARE,
     "local": ["makro_samui", "bigc_samui", "lotuss_samui", "homepro_samui"],
     "spec": "250 g butane cassette canisters matching the stove; store in the shade.",
     "why": "Canisters left in a hot car or in the sun can burst.",
     "listings": [
         L(MK, "MAX SAFE Gas Can 250 g x 3", 109, 3, MKP + "NLNI3GW-199495038788690"),
         L(MK, "GAZU Butane Gas Cartridge 250 g x 3", 125, 3, MKP + "f7blrmv-6974682366147"),
         L(MK, "IWATANI Gas Can 250 g x 4", 155, 4, MKP + "60TlWYs-842521165686003"),
     ]},
    {"id": "food_baby", "buyable": True, "budget": "conditional",
     "q_en": "infant formula", "q_th": "นมผงเด็ก", "shops": GROCERY,
     "local": ["makro_samui", "bigc_samui", "lotuss_samui", "boots_central"],
     "spec": "The formula your child already takes (same brand and stage).",
     "why": "Changing formula in a crisis can upset a baby's stomach.",
     "listings": [
         L(MK, "S-26 SMA Gold 500 g", 460, None, MKP + "8cAUq5B-533925591427221"),
         L(MK, "ENFALAC A+ Mind Pro Formula 1 500 g", 569, None,
           MKP + "0s2qhrv-7497364537539"),
     ],
     "price_note": "Reference prices only: how many days a tin lasts depends on the "
                   "child's age, so it is not added to the budget."},
    # ------------------------------------------------------------------ power
    {"id": "power_bank", "buyable": True, "q_en": "power bank 20000mAh",
     "q_th": "พาวเวอร์แบงค์ 20000", "shops": HARDWARE + ["makro"],
     "local": ["homepro_samui", "makro_samui", "bigc_samui"],
     "spec": "20,000 mAh from a known brand, with the Thai TIS (มอก.) mark, USB-C PD.",
     "why": "20,000 mAh at 3.7 V is about 74 Wh: roughly 3-4 phone charges, or a 5 W USB "
            "fan for about 12 hours. Cheap fakes often hold far less and can overheat.",
     "listings": [
         L(HP, "ORSEN by ELOOP E34 20000 mAh", 399, 1, HPP + "888208900050"),
         L(HP, "ASAKI AB3201P 20000 mAh", 990, 1, HPP + "1315592"),
         L(MK, "UGREEN Power Bank 20000 mAh PD3.0 PB312", 1190, 1,
           MKP + "7hxqoH--847848573471546"),
         L(HP, "XIAOMI 20000 mAh BHR08O4TH", 1499, 1, HPP + "1324399"),
     ]},
    {"id": "power_headlamp", "buyable": True, "q_en": "LED headlamp", "q_th": "ไฟฉายคาดหัว",
     "shops": HARDWARE, "local": ["homepro_samui", "globalhouse_samui"],
     "spec": "LED headlamp, 100-300 lumens, rain-resistant (IPX4 or better), running on "
             "AA/AAA or USB.",
     "why": "Both hands stay free in the dark and the rain; AA/AAA can be swapped when "
            "there is no power to recharge.",
     "listings": [
         L(HP, "WORTH SENSOR HL2505 100 lumens", 199, 1, HPP + "1299315"),
         L(HP, "WORTH SLIM HL2301 280 lumens", 299, 1, HPP + "1299299"),
         L(HP, "PANASONIC LED headlamp 170 lumens", 379, 1, HPP + "1301716"),
         L(HP, "ENERGIZER HDCU22 headlight 100 lumens", 499, 1, HPP + "1172915"),
     ]},
    {"id": "power_batteries", "buyable": True, "q_en": "alkaline AA battery",
     "q_th": "ถ่านอัลคาไลน์ AA", "shops": GROCERY[:1] + HARDWARE,
     "local": ["makro_samui", "globalhouse_samui", "bigc_samui"],
     "spec": "Alkaline (not zinc-chloride 'heavy duty') AA/AAA from a known brand.",
     "why": "Alkaline cells last several times longer and leak less in storage.",
     "listings": [
         L(GH, "PHILIPS Power Alkaline AA, 2 cells", 57, 2,
           GHP + "PHILIPS-ถ่านไฟฉาย-Power-Alkaline-AA-LR6P2B97-2-ก้อน-1.5V-สีไวน์แดง"
                 "-i.8712581544195"),
         L(MK, "PANASONIC Alkaline AA LR6T, 8 pcs", 183, 8, MKP + "PFtYtR4-29429375233616"),
         L(MK, "PANASONIC Alkaline AA LR6T/10SL, 10 pcs", 210, 10,
           MKP + "UTdo4C8-229210283373444"),
         L(MK, "PANASONIC Alkaline AA LR6T, 30 pcs", 606, 30, MKP + "w1fywza-7275671060675"),
     ]},
    {"id": "power_solar", "buyable": True, "q_en": "portable power station LiFePO4",
     "q_th": "power station lifepo4", "shops": ["homepro", "lazada", "shopee"],
     "local": ["homepro_samui"],
     "spec": "Portable power station with a LiFePO4 battery, about 250-500 Wh, plus a "
             "100-160 W foldable panel from the same brand.",
     "why": "LiFePO4 lasts thousands of cycles and is the safer lithium chemistry. Rough "
            "sizing: a phone charge is about 15-20 Wh, a USB fan 5-10 W (a 250 Wh unit "
            "runs one for about 20 hours); a fridge needs about 1 kWh per day, so it "
            "needs a much larger unit plus sun.",
     "components": [
         {"id": "station", "label": "Power station", "count": 1, "listings": [
             L(HP, "ECOFLOW RIVER 3 300 W", 7990, 1, HPP + "1288202"),
             L(HP, "BLUETTI ELITE 30 V2 600 W", 8990, 1, HPP + "1314850"),
             L(HP, "ELECKTA power box 448 Wh 600 W", 9900, 1, HPP + "1312394"),
             L(HP, "ECOFLOW RIVER 3 PLUS 600 W", 9990, 1, HPP + "1298663"),
         ]},
         {"id": "panel", "label": "Foldable solar panel", "count": 1, "listings": [
             L(HP, "ECOFLOW portable solar panel 110 W", 6290, 1, HPP + "1275611"),
             L(HP, "ECOFLOW portable solar panel 160 W", 8990, 1, HPP + "1275550"),
         ]},
     ],
     "price_note": "Check each model's Wh and battery chemistry on the product page "
                   "before buying: the listing titles give the output in W, not the "
                   "capacity."},
    {"id": "power_generator", "buyable": True, "q_en": "inverter generator",
     "q_th": "เครื่องปั่นไฟ อินเวอร์เตอร์", "shops": ["homepro", "globalhouse", "lazada"],
     "local": ["homepro_samui", "globalhouse_samui"],
     "spec": "Inverter petrol generator, 2-2.5 kW, for fridge, fans and electronics.",
     "why": "An inverter gives clean power that does not harm electronics. Run it "
            "outdoors only, far from windows: carbon monoxide kills.",
     "listings": [
         L(HP, "MATALL PRO THG3500A 2.5 kW (not inverter)", 6090, 1, HPP + "1255323"),
         L(HP, "POLO P2250IS inverter 2.0 kW", 13200, 1, HPP + "1236554"),
         L(HP, "SUMO inverter 2.5 kW", 19900, 1, HPP + "1282054"),
     ]},
    {"id": "power_fuel", "buyable": True, "q_en": "fuel can 20L", "q_th": "ถังน้ำมัน 20 ลิตร",
     "shops": ["homepro", "globalhouse", "lazada"],
     "local": ["homepro_samui", "globalhouse_samui"],
     "spec": "A proper fuel can (metal or fuel-rated plastic) with a sealed cap.",
     "why": "Water bottles and jerrycans are not made for petrol: they leak vapour and "
            "can crack.",
     "components": [
         {"id": "can", "label": "20 L fuel can", "count": 1, "listings": [
             L(HP, "MATALL JC-20L-RED gasoline can 20 L", 449, 1, HPP + "1316603"),
             L(HP, "MATALL GC-20L-RD gasoline can 20 L", 950, 1, HPP + "1151158"),
         ]},
     ],
     "extra_links": [{"label": "PTT fuel prices today",
                      "url": "https://www.pttor.com/en/oil_price"}],
     "price_note": "Fuel itself not included: pump prices change often; see the PTT "
                   "price page for today's price."},
    # ------------------------------------------------------------------ health
    {"id": "health_firstaid", "buyable": True, "q_en": "first aid kit",
     "q_th": "ชุดปฐมพยาบาล", "shops": PHARMA + ["homepro"],
     "local": ["boots_central", "homepro_samui"],
     "spec": "A kit WITH contents: bandages, gauze, tape, antiseptic (povidone-iodine), "
             "gloves, scissors. Some 'first aid bags' are sold empty.",
     "why": "Cuts from flood debris infect quickly in the heat; clean and cover at once.",
     "listings": [
         L(HP, "ABLOOM first aid kit set, shoulder strap bag", 699, 1, HPP + "888125000357"),
         L(HP, "ABLOOM first aid kit set 00040180005013", 1190, 1, HPP + "888125000360"),
     ]},
    _no("health_rx", "Prescription medicine: ask your doctor or hospital for a 30-day "
        "supply and a copy of the prescription (generic names)."),
    {"id": "health_ors", "buyable": True, "q_en": "ORS oral rehydration salts",
     "q_th": "ผงเกลือแร่ ORS", "shops": ["lazada", "shopee"],
     "local": ["boots_central"],
     "spec": "Pharmacy ORS sachets (ผงเกลือแร่ ORS) made to the WHO low-osmolarity "
             "formula; mix exactly with the volume printed on the sachet.",
     "why": "Sports and 'electrolyte' drinks are not ORS: they have more sugar and less "
            "salt, and can worsen diarrhoea.",
     "listings": [],
     "price_note": "No current, dated price found online for pharmacy ORS: check at any "
                   "pharmacy (usually a few baht per sachet) or the links."},
    {"id": "health_paracetamol", "buyable": True, "q_en": "paracetamol 500 mg",
     "q_th": "พาราเซตามอล 500", "shops": PHARMA,
     "local": ["boots_central", "makro_samui", "bigc_samui"],
     "spec": "Paracetamol 500 mg tablets, a box of 100.",
     "why": "WHO: with suspected dengue use paracetamol, not ibuprofen or aspirin "
            "(bleeding risk).",
     "listings": [
         L(MK, "PARACAP Paracetamol 10 tabs x 10", 109, 1, MKP + "nY4VVO9-478298460373338"),
         L(MK, "TYLENOL paracetamol 500 mg 4 tablets x 25 sheets", 150, 1,
           MKP + "tvlTLz6-717973247939295"),
     ]},
    {"id": "health_repellent", "buyable": True, "q_en": "mosquito repellent DEET",
     "q_th": "สเปรย์กันยุง DEET", "shops": PHARMA + ["priceza"],
     "local": ["boots_central", "makro_samui", "bigc_samui", "lotuss_samui"],
     "spec": "A skin repellent whose label gives DEET 20-30% or icaridin (picaridin) "
             "about 20%.",
     "why": "These actives, at these strengths, protect for several hours (US EPA). "
            "Aedes mosquitoes (dengue) bite in daytime: reapply as the label says.",
     "listings": [
         L(PZ, "SKINTER GUARD DEET 28 spray (marketplace seller)", 95, 1,
           PZS + "%E0%B8%AA%E0%B9%80%E0%B8%9B%E0%B8%A3%E0%B8%A2%E0%B9%8C%E0%B8%81%E0%B8%B1"
                 "%E0%B8%99%E0%B8%A2%E0%B8%B8%E0%B8%87%20deet", "marketplace"),
         L(MK, "SOFFELL Lotion Flora 60 ml x 4", 185, 4, MKP + "10wswpy-7325018751171"),
         L(MK, "SOFFELL Mosquito Repellent Spray Flora 80 ml x 4", 258, 4,
           MKP + "q_do5v6-7115378294979"),
     ],
     "price_note": "Check the active ingredient and its % on the label; the listing "
                   "titles do not all state it."},
    {"id": "health_net", "buyable": True, "q_en": "mosquito net bed", "q_th": "มุ้งกันยุง",
     "shops": HARDWARE, "local": ["globalhouse_samui"],
     "spec": "Bed net sized to the bed, fine mesh, no holes; ideally insecticide-treated.",
     "why": "Protects during naps and at night, when windows stay open in a power cut.",
     "listings": [
         L(GH, "TRUFFLE mosquito net MGB2 180x190x190 cm", 349, 1,
           GHP + "TRUFFLE-มุ้งกันยุง-รุ่น-MGB2-180x190x190ซม.-สีขาว-i.2008042027387"),
         L(GH, "TRUFFLE foldable net YM002 160x190x85 cm", 790, 1,
           GHP + "TRUFFLE-มุ้งครอบกันยุงแบบพับได้-รุ่น-YM002-160x190x85ซม.-สีขาว"
                 "-i.2008042026811"),
     ]},
    {"id": "health_thermo", "buyable": True, "q_en": "digital thermometer",
     "q_th": "ปรอทวัดไข้ดิจิตอล", "shops": PHARMA + ["homepro"],
     "local": ["boots_central", "homepro_samui"],
     "spec": "Digital clinical thermometer (not mercury).",
     "why": "Fever is the first sign of dengue: note temperature and date.",
     "listings": [
         L(HP, "Yuwell YT311 electronic thermometer", 165, 1, HPP + "888113500001"),
         L(HP, "JUMPER JPD-FR202 infrared thermometer", 1250, 1, HPP + "888206000006"),
     ]},
    {"id": "health_hygiene", "buyable": True, "q_en": "hand sanitizer", "q_th": "เจลล้างมือ",
     "shops": GROCERY, "local": ["makro_samui", "bigc_samui", "lotuss_samui"],
     "spec": "Alcohol hand sanitiser (about 70% alcohol), bar soap, strong rubbish bags.",
     "why": "With the water cut, hand hygiene prevents diarrhoea; strong bags make an "
            "emergency dry toilet.",
     "components": [
         {"id": "sanitiser", "label": "Hand sanitiser", "count": 1, "listings": [
             L(MK, "ALSOFF Hand Sanitizer Gel 450 ml", 55, 1, MKP + "taz0ect-6974723850435"),
             L(MK, "ALSOFF Alcohol Hand Sanitizer 1 l", 69, 1,
               MKP + "9ZVGHET-337461432548641"),
         ]},
         {"id": "soap", "label": "Bar soap", "count": 1, "listings": [
             L(MK, "PARROT Bar Soap Green 70 g x 4", 39, 1, MKP + "0jl-ras-7078731088067"),
             L(MK, "LUX Bar Soap Soft Rose 70 g x 4", 42, 1, MKP + "6okjbdv-7078731382979"),
         ]},
         {"id": "bags", "label": "Rubbish bags", "count": 1, "listings": [
             L(MK, "CHAMPION Extra Thick Garbage Bag 30x40\" 15 bags", 75, 1,
               MKP + "j3enbf2-6761198485699"),
             L(MK, "HERO Eco Garbage Bag 30x40\" x 25", 89, 1, MKP + "eo2hrn9-7078736822467"),
         ]},
     ]},
    # ------------------------------------------------------------------ heat
    {"id": "heat_fan", "buyable": True, "q_en": "rechargeable fan USB",
     "q_th": "พัดลมชาร์จไฟ", "shops": HARDWARE + ["makro"],
     "local": ["globalhouse_samui", "homepro_samui", "makro_samui"],
     "spec": "Rechargeable fan that can also run from a USB power bank.",
     "why": "USB input means it keeps running from a power bank or power station when "
            "the grid is down.",
     "listings": [
         L(HP, "HOCO HX600 handheld fan 1200 mAh", 180, 1, HPP + "888206800255"),
         L(GH, "BENKA rechargeable desk fan 7 inch KN-L2857", 479, 1,
           GHP + "BENKA-พัดลมตั้งโต๊ะชาร์จไฟแบบพกพา-ขนาด-7-นิ้ว-รุ่น-KNL2857-สีขาว"
                 "-i.4722008340037"),
         L(HP, "SONAR FLYBIRD X05 fan 3000 mAh", 670, 1, HPP + "888132700068"),
         L(GH, "BENKA rechargeable desk fan 9 inch KN-L2829", 990, 1,
           GHP + "BENKA-พัดลมตั้งโต๊ะชาร์จไฟแบบพกพา-ขนาด-9-นิ้ว-รุ่น-KNL2829-สีเทา"
                 "-i.4722008340075"),
     ]},
    {"id": "heat_towels", "buyable": True, "q_en": "cotton towel", "q_th": "ผ้าขนหนู",
     "shops": GROCERY[:1] + HARDWARE, "local": ["makro_samui", "bigc_samui"],
     "spec": "Plain cotton towels or cloths.",
     "why": "A wet cloth on the neck and wrists cools by evaporation, with no power.",
     "listings": [
         L(MK, "MOMENTO Towel 30x60 cm Brown 2 pcs", 59, 2, MKP + "ABs0Bflu-166865387636987"),
         L(MK, "ARO Cooling Towel 11x28\" 10 pcs", 220, 10, MKP + "ae-hsiw-7248026894531"),
         L(MK, "MOMENTO Bath Towel 30x60\" Blue", 159, 1, MKP + "D2UtwKCo-776898507908684"),
     ]},
    {"id": "heat_shade", "buyable": True, "q_en": "blackout curtain UV",
     "q_th": "ผ้าม่าน กัน UV", "shops": HARDWARE, "local": ["homepro_samui",
                                                          "globalhouse_samui"],
     "spec": "Outside shade net (60-90%) on sun-facing windows, or UV blackout curtains.",
     "why": "Shading outside the glass blocks more heat than a curtain inside.",
     "listings": [
         L(HP, "SPRING shading net 60% 2x10 m", 249, 1, HPP + "1170870"),
         L(HP, "SPRING shading net 90% 2x3 m with eyelets", 519, 1, HPP + "1049531"),
         L(HP, "HOME LIVING STYLE UV eyelet curtain 130x220 cm", 599, 1, HPP + "1283224"),
     ],
     "price_note": "Price for one net or one curtain panel: multiply by your windows."},
    {"id": "heat_thermo", "buyable": True, "q_en": "thermo hygrometer",
     "q_th": "เครื่องวัดอุณหภูมิและความชื้น", "shops": HARDWARE,
     "local": ["homepro_samui"],
     "spec": "Indoor digital thermometer-hygrometer (temperature and humidity).",
     "why": "Heat stress depends on temperature AND humidity; this tells you when the "
            "house is getting dangerous.",
     "listings": [
         L(HP, "HOCO HX42 digital thermo-hygrometer clock", 700, 1, HPP + "888206800157"),
         L(HP, "UNI-T UT333BT handheld thermo-hygrometer", 760, 1, HPP + "1318303"),
     ]},
    # ------------------------------------------------------------------ haze
    {"id": "haze_masks", "buyable": True, "q_en": "3M 9501+ KN95", "q_th": "หน้ากาก 3M 9501",
     "shops": ["homepro", "lazada", "shopee", "priceza"],
     "local": ["boots_central", "homepro_samui", "makro_samui"],
     "spec": "Certified respirators: N95 (NIOSH, US), KN95 (GB 2626, China) or P2 "
             "(AS/NZS 1716) printed on the mask; for example 3M 9501+ (KN95/P2).",
     "why": "Only a certified, well-fitting respirator filters PM2.5; cloth and surgical "
            "masks do not. Fakes are common: buy from official stores.",
     "listings": [
         L(PZ, "3M 9501 KN95/P2, box of 50 (marketplace seller)", 749, 50,
           PZS + "3m%209501", "marketplace"),
         L(PZ, "3M 9501 KN95/P2, box of 50 (another marketplace seller)", 987.77, 50,
           PZS + "3m%209501", "marketplace"),
         L(HP, "YAMADA 8242 KN95 respirator, 2 valves (1 pc)", 29, 1, HPP + "1109132"),
     ]},
    {"id": "haze_hepa", "buyable": True, "q_en": "air purifier HEPA", "q_th": "เครื่องฟอกอากาศ",
     "shops": ["homepro", "lazada", "shopee"], "local": ["homepro_samui"],
     "spec": "HEPA purifier whose CADR / rated room size matches (or exceeds) the room "
             "you will seal.",
     "why": "A too-small purifier cannot keep up; the US EPA advises matching CADR to "
            "room size.",
     "listings": [
         L(HP, "XIAOMI Smart Air Purifier 4 Compact (27 m2)", 2240, 1, HPP + "1268027"),
         L(HP, "XIAOMI Air Purifier 4 Lite (42 m2)", 3590, 1, HPP + "1266709"),
         L(HP, "XIAOMI Air Purifier 4 Lite (43 m2)", 4990, 1, HPP + "1198239"),
     ]},
    {"id": "haze_filter", "buyable": True, "q_en": "Xiaomi air purifier filter",
     "q_th": "ไส้กรองเครื่องฟอกอากาศ xiaomi", "shops": ["homepro", "lazada", "shopee"],
     "local": ["homepro_samui"],
     "spec": "The genuine filter for YOUR purifier model.",
     "why": "Filters are model-specific; a clogged or fake filter stops cleaning the air.",
     "listings": [
         L(HP, "XIAOMI HEPA filter (black)", 1049, 1, HPP + "1265043"),
         L(HP, "XIAOMI 4 Lite filter", 1590, 1, HPP + "1198647"),
     ]},
    # ------------------------------------------------------------------ flood
    {"id": "flood_drybags", "buyable": True, "q_en": "dry bag 10L", "q_th": "ถุงกันน้ำ dry bag",
     "shops": ["homepro", "lazada", "shopee", "priceza"], "local": ["homepro_samui"],
     "spec": "Roll-top dry bag, 5-10 L, welded seams (PVC or TPU).",
     "why": "Roll-top closures stay dry when dropped in water; zip bags do not.",
     "listings": [
         L(PZ, "Dry bag 10 L (marketplace seller)", 159, 1, PZS + "dry%20bag%2010L",
           "marketplace"),
         L(HP, "FEELFREE Dry Tube Tropical 1.5 L", 382.5, 1, HPP + "888180900130"),
         L(PZ, "Sealline Blocker Dry Sack 10 L (marketplace seller)", 690, 1,
           PZS + "dry%20bag%2010L", "marketplace"),
     ]},
    _no("flood_docs", "Copies and scans you make yourself (print shop or phone). A "
        "laminator or plastic sleeves are optional."),
    _no("flood_gobag", "Assembled from the other items on this list (water, headlamp, "
        "power bank, medication, documents); any backpack works."),
    {"id": "flood_rope", "buyable": True, "q_en": "nylon rope", "q_th": "เชือกไนลอน",
     "shops": HARDWARE, "local": ["globalhouse_samui", "homepro_samui"],
     "spec": "Nylon or PP rope, 8-10 mm for tying down; 4-5 mm only for light use.",
     "why": "Thin rope snaps in storm gusts. Thick rope at Global House is sold by the kg "
            "(8 mm nylon: 119 THB/kg on the checked date).",
     "listings": [
         L(HP, "BIH nylon rope 5 mm x 10 m", 59, 10, HPP + "1137013"),
         L(HP, "DEXZON nylon rope 4 mm x 20 m", 75, 20, HPP + "1179745"),
         L(HP, "DEXZON PE rope 5 mm x 10 m", 75, 10, HPP + "1179647"),
     ],
     "price_note": "Budget uses thin rope prices; thick rope costs more."},
    {"id": "flood_tarp", "buyable": True, "q_en": "heavy duty tarpaulin", "q_th": "ผ้าใบ",
     "shops": HARDWARE, "local": ["globalhouse_samui", "homepro_samui"],
     "spec": "Heavy PE or PVC tarp, at least 3x4 m, with metal eyelets.",
     "why": "Covers a broken window or roof section until repairs; eyelets let you tie it.",
     "listings": [
         L(HP, "GARTENE thick plastic tarp 3x4 m", 319, 1, HPP + "1122392"),
         L(HP, "SPRING PE tarp 3x4 m", 419, 1, HPP + "1187134"),
         L(GH, "Scorpion (แมงป่อง) medium tarp 3x4 m silver", 660, 1,
           GHP + "แมงป่อง-ผ้าใบอย่างกลาง%203x4M.-สีเงิน-i.6420524009002"),
     ]},
    {"id": "flood_tape", "buyable": True, "q_en": "duct tape", "q_th": "เทปผ้า",
     "shops": HARDWARE, "local": ["globalhouse_samui", "homepro_samui"],
     "spec": "Cloth duct tape, 48 mm wide.", "why": "Quick repairs of tarps, bags, pipes.",
     "listings": [
         L(HP, "3M utility duct tape 48 mm x 8 y", 65, 1, HPP + "1098282"),
         L(HP, "PACK IN duct tape 48 mm x 25 y", 115, 1, HPP + "1041970"),
     ]},
    {"id": "flood_whistle", "buyable": True, "q_en": "Fox 40 whistle", "q_th": "นกหวีด",
     "shops": ["lazada", "shopee", "priceza"], "local": [],
     "spec": "Pea-less safety whistle (for example Fox 40), on a lanyard.",
     "why": "Pea-less whistles work when wet; a whistle carries further than a voice and "
            "saves energy.",
     "listings": [
         L(PZ, "Fox 40 whistle (marketplace seller)", 28.71, 1,
           PZS + "%E0%B8%99%E0%B8%81%E0%B8%AB%E0%B8%A7%E0%B8%B5%E0%B8%94%20"
                 "%E0%B8%89%E0%B8%B8%E0%B8%81%E0%B9%80%E0%B8%89%E0%B8%B4%E0%B8%99",
           "marketplace"),
         L(PZ, "Fox 40 whistle (another marketplace seller)", 31, 1,
           PZS + "%E0%B8%99%E0%B8%81%E0%B8%AB%E0%B8%A7%E0%B8%B5%E0%B8%94%20"
                 "%E0%B8%89%E0%B8%B8%E0%B8%81%E0%B9%80%E0%B8%89%E0%B8%B4%E0%B8%99",
           "marketplace"),
     ]},
    {"id": "flood_boots", "buyable": True, "q_en": "rubber boots", "q_th": "รองเท้าบูทยาง",
     "shops": HARDWARE, "local": ["globalhouse_samui", "homepro_samui"],
     "spec": "Knee-high rubber boots in your size.",
     "why": "Floodwater hides sharp debris and carries leptospirosis through cuts.",
     "listings": [
         L(HP, "PIPES rubber boots 12 in No.10 black", 149, 1, HPP + "1105916"),
         L(GH, "Long rubber boots, white, size 11", 225, 1,
           GHP + "รองเท้าบูทยาว-สีขาว-เบอร์-11-i.8855553003808"),
         L(GH, "Waterproof boots 57 cm, size 10", 330, 1,
           GHP + "รองเท้าบูทกันน้ำ-สูง-57-cm.-เบอร์-10-i.8855553000739"),
     ]},
    # ------------------------------------------------------------------ comms
    {"id": "comms_radio", "buyable": True, "q_en": "hand crank radio AM FM",
     "q_th": "วิทยุมือหมุน", "shops": ["lazada", "shopee", "homepro", "priceza"],
     "local": ["homepro_samui"],
     "spec": "Radio with FM (Thai stations broadcast warnings on FM), powered by hand "
             "crank + solar + batteries, ideally with a USB output.",
     "why": "Keeps you informed when the power and the mobile network are both down.",
     "listings": [
         L(HP, "ACONATIC AN-888 portable radio (batteries)", 359, 1, HPP + "888120300078"),
         L(PZ, "Hand crank solar radio AM/FM, 2000 mAh (marketplace seller)", 624, 1,
           PZS + "hand%20crank%20radio", "marketplace"),
         L(PZ, "Hand crank emergency radio AM/FM/SW with torch (marketplace seller)",
           1194, 1, PZS + "%E0%B8%A7%E0%B8%B4%E0%B8%97%E0%B8%A2%E0%B8%B8%E0%B8%A1%E0%B8%B7"
                         "%E0%B8%AD%E0%B8%AB%E0%B8%A1%E0%B8%B8%E0%B8%99", "marketplace"),
     ]},
    _no("comms_maps", "Free: download offline maps in Google Maps or OSM beforehand."),
    _no("comms_numbers", "Print the emergency contacts from this page."),
    {"id": "comms_sim2", "buyable": True, "q_en": "prepaid SIM", "q_th": "ซิมเติมเงิน",
     "shops": [], "local": [],
     "spec": "A prepaid SIM from a second network (AIS or True-dtac), registered to your "
             "passport.",
     "why": "If one network's towers fail, the other sometimes still works.",
     "extra_links": [{"label": "AIS", "url": "https://www.ais.th/"},
                     {"label": "True-dtac", "url": "https://www.true.th/"}],
     "listings": [],
     "price_note": "Prices and packages change; buy at an operator shop or 7-Eleven with "
                   "your passport."},
    _no("money_cash", "Cash withdrawn beforehand, not bought."),
    _no("money_cards", "A second bank card: ask your bank."),
    _no("exit_ferry", "A plan, not a purchase."), _no("exit_airport", "A plan, not a purchase."),
    _no("exit_mainland", "A plan, not a purchase."),
    _no("exit_threshold", "A decision, not a purchase."),
    _no("exit_fuel", "A habit, not a purchase."),
    _no("doc_passport", "Documents, not bought here."), _no("doc_visa", "Documents."),
    _no("doc_insurance", "Documents."), _no("doc_home", "Documents."),
    _no("doc_embassy", "Registration with your embassy (free, online)."),
    _no("home_gutters", "A task."), _no("home_secure", "A task."), _no("home_high", "A task."),
    # ------------------------------------------------------------------ pets
    {"id": "pet_food", "buyable": True, "budget": "conditional", "q_en": "dog food",
     "q_th": "อาหารสุนัข", "shops": GROCERY, "local": ["makro_samui", "bigc_samui"],
     "spec": "The food your pet already eats, sealed bags.",
     "why": "A sudden change of diet can make pets ill.",
     "listings": [
         L(MK, "SMART HEART Adult Dog Food Beef 10 kg", 709, None,
           MKP + "ccgkxpy-7352933908675"),
         L(MK, "WHISKAS Cat Food Adult Mackerel 3 kg", 309, None,
           MKP + "h_inygf-7352841339075"),
     ],
     "price_note": "Reference prices only: daily amount depends on the animal, so it is "
                   "not added to the budget."},
    {"id": "pet_carrier", "buyable": True, "budget": "conditional", "q_en": "pet carrier",
     "q_th": "กล่องใส่สัตว์เลี้ยง", "shops": ["homepro", "lazada", "shopee"],
     "local": ["homepro_samui"],
     "spec": "Hard-shell carrier with ventilation, sized for the animal to stand and turn.",
     "why": "Ferries and airlines usually require a closed carrier; check their rules.",
     "listings": [
         L(HP, "PETUS 9529 pet carrier, grey", 599, 1, HPP + "1320703"),
         L(HP, "PETUS 2503 pet carrier, white", 743.07, 1, HPP + "1325460"),
         L(HP, "PETSTAR PSRB0059 pet carrier", 1499, 1, HPP + "1313167"),
     ]},
]

ITEM_BY_ID = {it["id"]: it for it in ITEMS}
