"""'If I stay' -- preparedness data for Koh Samui, El Nino 2026-27 + NE monsoon.

Quantities come from cited guidance (WHO, Ready.gov / FEMA, American Red Cross);
phone numbers were checked on official pages on 2026-09-24 (see CONTACTS[*].source).
No ferry schedules are given on purpose: they change, check the operator the day.

Item shape: {id, label, qty, per ("person/day" | "person" | "household"), unit,
priority (must | should | nice), note}. The frontend multiplies by
household.adults + children and household.days (from /api/preparedness/state).
"""

from __future__ import annotations

SOURCES = [
    {"id": "who_tn9", "title": "WHO Technical Note 9: How much water is needed in emergencies",
     "url": "https://cdn.who.int/media/docs/default-source/wash-documents/"
            "who-tn-09-how-much-water-is-needed.pdf",
     "used_for": "Water: survival 2.5-3 L/person/day (drinking + food), basic hygiene "
                 "2-6 L, cooking 3-6 L, total 7.5-15 L; 20 L = minimum for health."},
    {"id": "ready_water", "title": "Ready.gov (FEMA) -- Water",
     "url": "https://www.ready.gov/water",
     "used_for": "At least 1 gallon (3.8 L)/person/day; in hot climates needs can double; "
                 "boil for 1 minute; 5.25-6% bleach: 1/8 teaspoon per gallon, wait 30 min."},
    {"id": "ready_kit", "title": "Ready.gov (FEMA) -- Build a Kit", "url": "https://www.ready.gov/kit",
     "used_for": "Emergency kit contents (radio, flashlight, batteries, first aid kit, "
                 "whistle...)."},
    {"id": "redcross_kit", "title": "American Red Cross -- Survival kit supplies",
     "url": "https://www.redcross.org/get-help/how-to-prepare-for-emergencies/"
            "survival-kit-supplies.html",
     "used_for": "Kit: 2 weeks of supplies at home, medication, copies of documents."},
    {"id": "who_dengue", "title": "WHO fact sheet -- Dengue and severe dengue",
     "url": "https://www.who.int/news-room/fact-sheets/detail/dengue-and-severe-dengue",
     "used_for": "Dengue: paracetamol for pain; avoid ibuprofen and aspirin "
                 "(bleeding risk); Aedes mosquitoes."},
    {"id": "ddpm", "title": "Thai DDPM (Department of Disaster Prevention and Mitigation)",
     "url": "https://www.disaster.go.th/", "used_for": "Disaster hotline 1784."},
    {"id": "fcdo", "title": "UK FCDO travel advice Thailand -- Getting help",
     "url": "https://www.gov.uk/foreign-travel-advice/thailand/getting-help",
     "used_for": "191 police, 1669 ambulance, 199 fire, 1155 tourist police."},
    {"id": "samui_water_2026", "title": "Bangkok Post, 29/07/2026 -- Koh Samui faces water rationing",
     "url": "https://www.bangkokpost.com/thailand/general/3293479/koh-samui-faces-water-rationing",
     "used_for": "Context: PWA rotating water rationing on Samui from 3 August 2026 (El Nino)."},
]

CONTACTS = [
    {"id": "police", "label": "Police (general emergency)", "number": "191",
     "source": "https://www.gov.uk/foreign-travel-advice/thailand/getting-help"},
    {"id": "medical", "label": "Medical emergency / ambulance (NIEMS)", "number": "1669",
     "source": "https://www.niems.go.th/"},
    {"id": "fire", "label": "Fire brigade", "number": "199",
     "source": "https://www.gov.uk/foreign-travel-advice/thailand/getting-help"},
    {"id": "tourist_police", "label": "Tourist police (English)", "number": "1155",
     "source": "https://www.touristpolice.go.th/"},
    {"id": "ddpm", "label": "DDPM -- disaster prevention", "number": "1784",
     "source": "https://www.disaster.go.th/"},
    {"id": "tmd", "label": "Thai Meteorological Department (TMD) hotline", "number": "1182",
     "source": "https://www.tmd.go.th/"},
    {"id": "pwa", "label": "Tap water (PWA, Provincial Waterworks Authority)",
     "number": "1662", "source": "https://www.pwa.co.th/"},
    {"id": "pea", "label": "Electricity (PEA, Provincial Electricity Authority)",
     "number": "1129", "source": "https://www.pea.co.th/"},
    {"id": "ferry_seatran", "label": "Seatran Ferry (today's schedules and cancellations)",
     "number": None, "url": "https://www.seatranferry.com/"},
    {"id": "ferry_raja", "label": "Raja Ferry (today's schedules and cancellations)",
     "number": None, "url": "https://www.rajaferryport.com/"},
    {"id": "ferry_lomprayah", "label": "Lomprayah (catamarans, today's schedules)",
     "number": None, "url": "https://www.lomprayah.com/"},
    {"id": "airport", "label": "Samui International Airport (USM; most flights by Bangkok "
     "Airways)", "number": None, "url": "https://www.samuiairport.com/"},
    {"id": "embassy", "label": "Your embassy in Bangkok (number on its official website)",
     "number": None, "url": None},
]


def _i(id_, label, qty, per, unit, priority, note=""):
    return {"id": id_, "label": label, "qty": qty, "per": per, "unit": unit,
            "priority": priority, "note": note}


P, PJ, F = "person", "person/day", "household"

CATEGORIES = [
    {"id": "water", "title": "Water",
     "why": "Samui has had shortages before (2016, and PWA rotating rationing from "
            "3 August 2026). With El Nino, February-April 2027 is the riskiest period.",
     "items": [
         _i("water_drink", "Drinking water", 4, PJ, "L", "must",
            "WHO: 2.5-3 L/day to survive; in intense heat needs can double "
            "(Ready.gov). 4 L is a minimum in Samui's climate."),
         _i("water_cook", "Drinking-quality water for cooking", 3, PJ, "L", "must",
            "WHO: 3-6 L/day for basic cooking. Less with no-cook food."),
         _i("water_hygiene", "Water for hygiene (washing, hands, dishes)", 5, PJ, "L",
            "should", "WHO: 2-6 L/day for basic hygiene; 20 L/day = minimum for health."),
         _i("water_tank", "House cistern / tank full and clean", 1, F, "tank",
            "must", "Fill before the dry season; check the lid (mosquitoes) and leaks."),
         _i("water_jerrycans", "20 L food-grade jerrycans", 3, F, "jerrycans", "should",
            "To store water from a water truck or a distribution point."),
         _i("water_filter", "Gravity water filter (ceramic or membrane)", 1, F, "filter",
            "should", "A filter does not remove everything: combine with boiling or chlorine "
            "if the water is doubtful."),
         _i("water_tablets", "Purification tablets (chlorine / NaDCC)", 50, F, "tablets",
            "should", "Follow the instructions (dose and contact time)."),
         _i("water_bleach", "Unscented bleach 5.25-6%", 1, F, "L", "nice",
            "Ready.gov: 1/8 teaspoon (~0.6 mL) per 3.8 L, wait 30 min."),
         _i("water_boil", "A way to boil water (stove + gas)", 1, F, "stove", "should",
            "Ready.gov: a rolling boil for 1 minute is the safest method."),
     ]},
    {"id": "food", "title": "Food (14 days, no cooking needed)",
     "why": "If rough seas stop the ferries or the power goes out, the island's supermarkets "
            "empty fast. The Red Cross recommends 2 weeks of supplies at home.",
     "items": [
         _i("food_nocook", "No-cook meals (canned food, tuna, sardines, beans)", 14, P,
            "days", "must", "Choose what you already eat; check the dates."),
         _i("food_snacks", "Dried fruit, nuts, bars, biscuits", 14, P, "days", "should", ""),
         _i("food_rice", "Rice, instant noodles (if you can cook)", 7, P, "days",
            "nice", "Needs water + gas: do not rely on it alone."),
         _i("food_opener", "Manual can opener", 1, F, "item", "must", ""),
         _i("food_gas", "Gas canisters for the stove", 6, F, "canisters", "should",
            "Never indoors without ventilation."),
         _i("food_baby", "Infant formula / special foods if needed", 14, P, "days",
            "must", "Only if your household needs it."),
     ]},
    {"id": "power", "title": "Power cuts",
     "why": "Monsoon storms and heatwaves (peak air-conditioning use) cause outages; "
            "the island has a limited power supply from the mainland.",
     "items": [
         _i("power_bank", "Power banks (20,000 mAh)", 2, P, "items", "must",
            "Keep them charged; recharge after every outage."),
         _i("power_headlamp", "Headlamp", 1, P, "item", "must", ""),
         _i("power_batteries", "Spare batteries (AA/AAA to match devices)", 12, F, "batteries",
            "must", ""),
         _i("power_solar", "Foldable solar panel (60-100 W) + power station/battery", 1, F,
            "kit", "should", "Long autonomy without fuel."),
         _i("power_generator", "Generator + fuel", 1, F, "generator", "nice",
            "Always outdoors: risk of carbon monoxide poisoning."),
         _i("power_fuel", "Spare fuel (scooter/car/generator)", 20, F, "L", "nice",
            "Approved can, in the shade, away from the house. Fill up before the alert."),
     ]},
    {"id": "health", "title": "Health",
     "why": "Heat, doubtful water and dengue (more mosquitoes with heat and rain). "
            "The island's hospitals can be overwhelmed or cut off from the mainland.",
     "items": [
         _i("health_firstaid", "Complete first aid kit", 1, F, "kit", "must", ""),
         _i("health_rx", "Prescription medication", 30, P, "days", "must",
            "+ copies of prescriptions (generic drug name, not just the brand)."),
         _i("health_ors", "Oral rehydration salts (ORS)", 10, P, "sachets", "must",
            "Heat, diarrhoea: first line against dehydration."),
         _i("health_paracetamol", "Paracetamol", 1, F, "box", "must",
            "WHO: if dengue is suspected, take paracetamol and NOT ibuprofen or "
            "aspirin (bleeding risk)."),
         _i("health_repellent", "Mosquito repellent (DEET or icaridin)", 2, P, "bottles",
            "must", "Dengue mosquitoes bite during the day."),
         _i("health_net", "Mosquito net", 1, P, "item", "should", ""),
         _i("health_thermo", "Thermometer", 1, F, "item", "should", ""),
         _i("health_hygiene", "Hand sanitiser, soap, rubbish bags", 1, F, "set", "should",
            "If the water is cut: hand hygiene and dry toilets."),
     ]},
    {"id": "heat", "title": "Heat",
     "why": "El Nino likely makes the 2027 dry season (March-May) hotter; above 41 °C "
            "feels-like, heatstroke becomes a real risk.",
     "items": [
         _i("heat_fan", "Battery / USB fan", 1, P, "item", "must",
            "Runs on a power bank during outages."),
         _i("heat_towels", "Towels / cloths to wet", 2, P, "items", "should", ""),
         _i("heat_shade", "Shade cloth / blackout curtains", 1, F, "set", "nice", ""),
         _i("heat_thermo", "Indoor thermometer-hygrometer", 1, F, "item", "nice",
            "To know when the house becomes dangerous."),
     ]},
    {"id": "haze", "title": "Haze / pollution",
     "why": "In El Nino years, fires in Indonesia and Malaysia can send haze as far as "
            "southern Thailand (2015, 2019).",
     "items": [
         _i("haze_masks", "N95 / KN95 masks", 20, P, "masks", "should",
            "Cloth or surgical masks do not filter PM2.5."),
         _i("haze_hepa", "HEPA air purifier (for one room)", 1, F, "unit", "nice",
            "Create a clean room, windows closed."),
         _i("haze_filter", "Spare HEPA filter", 1, F, "filter", "nice", ""),
     ]},
    {"id": "flood", "title": "Flood / storm",
     "why": "The northeast monsoon (October-December) brings Samui's heaviest rain, "
            "even during an El Nino. Pabuk (January 2019) hit the island.",
     "items": [
         _i("flood_drybags", "Dry bags", 2, P, "bags", "must",
            "Documents, phone, money."),
         _i("flood_docs", "Copies of documents (laminated paper + offline digital)", 1, P,
            "set", "must", ""),
         _i("flood_gobag", "Go-bag ready (1 day of water, clothes, medication, "
            "flashlight, charger)", 1, P, "bag", "must", "By the door when the level is 'act'."),
         _i("flood_rope", "Strong rope", 20, F, "m", "should", ""),
         _i("flood_tarp", "Heavy-duty tarps", 2, F, "tarps", "should", "Roof, windows."),
         _i("flood_tape", "Duct tape", 1, F, "roll", "should", ""),
         _i("flood_whistle", "Whistle", 1, P, "item", "should", "Ready.gov: to signal "
            "for help."),
         _i("flood_boots", "Boots / closed shoes", 1, P, "pair", "nice",
            "Floodwater = debris and a risk of leptospirosis."),
     ]},
    {"id": "comms", "title": "Communication",
     "why": "Cell towers go down when the power is out for a long time.",
     "items": [
         _i("comms_radio", "Battery or hand-crank radio", 1, F, "radio", "must",
            "Ready.gov: a battery or hand-crank radio in the kit."),
         _i("comms_maps", "Offline maps of the island and Surat Thani", 1, P, "phone",
            "must", "Download beforehand (Google Maps / OSM)."),
         _i("comms_numbers", "Printed emergency numbers (see contacts)", 1, F, "sheet",
            "must", ""),
         _i("comms_sim2", "Second SIM card from another carrier", 1, P, "SIM", "nice",
            "If one network goes down, the other sometimes holds."),
     ]},
    {"id": "money", "title": "Money",
     "why": "Without power or network, cards and ATMs stop working.",
     "items": [
         _i("money_cash", "Cash in baht (small notes)", 14, F, "days of spending",
            "must", "Withdraw before the alert: ATMs run dry."),
         _i("money_cards", "Two bank cards from different banks", 1, P, "set",
            "should", ""),
     ]},
    {"id": "exit", "title": "Departure plan",
     "why": "The island can only be left by ferry, catamaran or plane. When seas exceed 2 m, "
            "boats stop: leave early, not at the last minute.",
     "items": [
         _i("exit_ferry", "Know the operators: Seatran, Raja Ferry (cars), "
            "Lomprayah (catamarans)", 1, F, "plan", "must",
            "Schedules and cancellations: only on their websites/pages on the day."),
         _i("exit_airport", "Samui Airport (Bangkok Airways): check flights and fares", 1,
            F, "plan", "should", "Limited capacity and expensive: not an option for everyone."),
         _i("exit_mainland", "A place to stay on the mainland (Surat Thani, Bangkok) and "
            "the route after Don Sak", 1, F, "plan", "should",
            "Routes, sea/wind windows for the next 7 days: Exit plan (/api/local/exit)."),
         _i("exit_threshold", "Departure threshold decided in advance (e.g. water cut > 3 days, "
            "cyclone < 300 km away)", 1, F, "decision", "must",
            "Deciding calmly avoids staying too long."),
         _i("exit_fuel", "Vehicle tank always at least half full", 1, F,
            "habit", "should", ""),
     ]},
    {"id": "documents", "title": "Documents",
     "why": "A rushed departure or a flood leaves no time to look for them.",
     "items": [
         _i("doc_passport", "Passport (valid > 6 months) + copies", 1, P, "set", "must", ""),
         _i("doc_visa", "Visa / extension / TM30, dates up to date", 1, P, "set", "must",
            "Make sure the deadline does not fall during the crisis."),
         _i("doc_insurance", "Health/repatriation insurance: policy number + hotline", 1, P,
            "set", "must", ""),
         _i("doc_home", "Lease / title deed, contracts, landlord contacts", 1, F, "set",
            "should", ""),
         _i("doc_embassy", "Registration with your embassy (citizens register)",
            1, P, "registration", "should", "So you can be contacted in an evacuation."),
     ]},
    {"id": "home_pets", "title": "Home and pets",
     "why": "Preparing the house reduces damage; pets are not always accepted "
            "on boats or in shelters.",
     "items": [
         _i("home_gutters", "Gutters and drains cleared before October", 1, F, "task",
            "should", ""),
         _i("home_secure", "Outdoor items tied down or brought in (wind)", 1, F, "task",
            "should", ""),
         _i("home_high", "High shelf for electronics and documents (flooding)", 1, F,
            "task", "nice", ""),
         _i("pet_food", "Pet food", 14, F, "days", "must",
            "Only if you have pets."),
         _i("pet_carrier", "Pet carrier + vaccination record", 1, F, "set", "should",
            "Check the ferry/airline rules for animals."),
     ]},
]

SCENARIOS = [
    {"id": "drought", "title": "Drought / water shortage",
     "when": "90-day rain < 60% of normal, PWA rationing announcements, February-April 2027.",
     "before": ["Fill the cistern and jerrycans; fix leaks.",
                "14 days of drinking water (4 L/person/day + cooking).",
                "Find a water-truck supplier and its price.",
                "Set up a filter + tablets; collect rainwater if possible."],
     "during": ["Keep drinking water for drinking and cooking only.",
                "Toilets: grey water; short showers; wash dishes in batches.",
                "Follow PWA supply zones and schedules (hotline 1662).",
                "Watch for heat + dehydration (ORS)."],
     "after": ["Clean and disinfect the cistern before refilling it.",
               "Restock; note what ran short."]},
    {"id": "heatwave", "title": "Heatwave",
     "when": "Feels-like >= 41 °C for several days ('danger' threshold), often March-May.",
     "before": ["Battery fans, ORS, blackout curtains.",
                "Find a cool place (shopping mall, library) in case of a power cut."],
     "during": ["No exertion between 11:00 and 16:00; drink before you feel thirsty.",
                "Check on children, older people and pets.",
                "Warning signs (confusion, hot and dry skin): call 1669."],
     "after": ["Rehydrate, check how much of the water stock was used."]},
    {"id": "storm_flood", "title": "Storm / flood",
     "when": "> 90 mm/24 h or 150 mm/72 h, TMD warning, cyclone < 800 km (October-January).",
     "before": ["Clear gutters; bring in/tie down outdoor furniture.",
                "Documents and electronics up high, in dry bags.",
                "Charge every battery; fill up with fuel; get cash.",
                "Go-bag ready; know where to go if the house can flood."],
     "during": ["Stay indoors, away from windows, radio on (TMD, DDPM 1784).",
                "Never cross a flooded road or moving water.",
                "Avoid slopes and mountain roads (landslides)."],
     "after": ["Tap water: boil it until the PWA confirms it is safe.",
               "Photograph the damage for insurance.",
               ("Boots and gloves in floodwater (leptospirosis); drain standing water "
                "(dengue).")]},
    {"id": "haze", "title": "Pollution haze",
     "when": "PM2.5 > 75 µg/m³ as a 24 h mean (PCD 'affects health' threshold).",
     "before": ["Stock N95/KN95 masks; HEPA purifier and a spare filter."],
     "during": ["Windows closed, one purified room; mask outdoors.",
                "Cut outdoor physical activity; take care of people with asthma.",
                "Compare with Air4Thai (PCD) measurements."],
     "after": ["Air out when the air is good again; change the filter if needed."]},
    {"id": "isolation", "title": "Island cut off",
     "when": "Waves >= 2-3 m, ferries cancelled, or a storm over the Gulf.",
     "before": ["14 days of self-sufficiency (water, food, medication, fuel, cash).",
                "Follow the operators' pages (Seatran, Raja, Lomprayah) and the airport.",
                "If you need to leave, leave BEFORE the sea closes."],
     "during": ["Save fuel and water; limit trips.",
                "Listen to the radio / local announcements for distributions."],
     "after": ["Shelves refill within a few days: do not over-buy.",
               "Restock calmly."]},
    {"id": "leave", "title": "Leaving the island",
     "when": ("Overall level 'leave', a cyclone within 300 km, a water cut with no end "
              "announced, or your own departure threshold reached."),
     "exit_plan": "/api/local/exit",
     "before": [("Check the Exit plan: sea / wind signals and the next days with normal "
                 "crossing conditions."),
                "Leave early: ferries stop around 2-3 m waves, catamarans first.",
                ("Confirm the crossing on the operator's site the same day; book a place to "
                 "stay on the mainland."),
                "Home: water valve closed, breaker off, windows shut, valuables up high."],
     "during": ["Carry documents, medication, cash and the go-bag.",
                "Tell someone off the island your route and times.",
                ("If the sea is closed: check flights (USM), otherwise shelter on high ground "
                 "and follow the DDPM (1784).")],
     "after": ["Come back only when the TMD warnings have ended and ferries run normally.",
               "Before using tap water again, check PWA announcements (1662)."]},
]


def preparedness() -> dict:
    return {"location": "Koh Samui", "categories": CATEGORIES, "scenarios": SCENARIOS,
            "contacts": CONTACTS, "sources": SOURCES, "verified_at": "2026-09-24"}


DEFAULT_STATE = {"checked": {}, "household": {"adults": 1, "children": 0, "days": 14}}
