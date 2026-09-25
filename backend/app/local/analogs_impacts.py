"""Documented real-world impacts on Koh Samui / Surat Thani / southern Thailand / the Gulf
of Thailand around past El Nino events (kind "documented" on the analogs page).

Rule 1 of CLAUDE.md: nothing here is inferred. Every entry was fetched live on `checked_at`
(HTTP 200, or a DOI resolving through Crossref), `quote` is verbatim from that page, and
`text` only repeats what the page says (numbers included). `events` lists the El Nino
event(s) of app.local.analogs.EVENTS the impact belongs to; impacts that happened in
La Nina / neutral years (the March 2011 Samui floods, the Dec 2016 - Jan 2017 floods, the
Dec 2022 ferry halt, the Nov-Dec 2024 floods) or in the weak 2018-19 El Nino (Pabuk) carry
an empty `events` list and an honest `enso` note: they show what the NE monsoon does to the
island whatever ENSO says. Looked for and NOT found (say so, never fill in): a Samui water
shortage report for the 2019-20 dry season, for 1998 and for 1992-93; Samui-specific
bleaching percentages for 2016; DDPM tallies for Pabuk; a Nov 2011 Samui flood.
"""

from __future__ import annotations

CHECKED = "2026-09-24"


def _i(date: str, type_: str, area: str, events: list[str], enso: str, text: str, title: str,
       url: str, publisher: str, published: str, quote: str, note: str | None = None) -> dict:
    return {"date": date, "type": type_, "area": area, "events": events, "enso": enso,
            "text": text, "source_title": title, "url": url, "publisher": publisher,
            "published": published, "quote": quote, "checked_at": CHECKED, "note": note}


IMPACTS: list[dict] = [
    # ------------------------------------------------------------------ 1997-98
    _i("1998", "bleaching", "Koh Tao / western Gulf of Thailand", ["1997-98"],
       "very strong El Nino 1997-98",
       "Koh Tao's first major coral bleaching event occurred in 1998 (Hoeksema, Matthews & "
       "Yeemin 2012, Phuket Marine Biological Center Research Bulletin 71: 71-81).",
       "PMBC Research Bulletin 71 -- The 2010 coral bleaching event and its impact on the "
       "mushroom coral fauna of Koh Tao, western Gulf of Thailand",
       "https://www.dmcr.go.th/dmcr/fckupload/upload/44/image/FullpaperPMBC/"
       "2012%20Vol.71%20Hoeksema%2071%2081.pdf",
       "DMCR / Phuket Marine Biological Center", "2012",
       "Koh Tao's first major coral bleaching event occurred in 1998 (Wilkinson 1998, "
       "Yeemin et al. 2006, 2009)", "peer-reviewed PDF"),
    _i("1998", "bleaching", "Koh Tao", ["1997-98"], "very strong El Nino 1997-98",
       "A Koh Tao reef-monitoring NGO page (secondary) states the 1998 mass bleaching was "
       "devastating to the island; for 2010 it gives 98.1% of surveyed corals bleached and "
       "island coral cover falling from 41.2% to 27.1%.",
       "New Heaven Reef Conservation -- Koh Tao Reef Status",
       "https://newheavenreefconservation.org/learning-resources/explore-topics/"
       "koh-tao-reef-status",
       "New Heaven Reef Conservation Program", "undated",
       "the mass coral bleaching event of 1998 was devastating to the island",
       "NGO page, secondary source"),
    _i("2013", "paper", "Western Gulf of Thailand (1998 and 2010 bleaching)",
       ["1997-98", "2009-10"], "El Nino 1997-98 and 2009-10",
       "Sutthacheep M. et al. (2013), Impacts of the 1998 and 2010 mass coral bleaching "
       "events on the Western Gulf of Thailand, Deep Sea Research Part II 96: 25-31.",
       "Deep Sea Research II -- Impacts of the 1998 and 2010 mass coral bleaching events on "
       "the Western Gulf of Thailand", "https://doi.org/10.1016/j.dsr2.2013.04.018",
       "Elsevier", "2013-11",
       "Impacts of the 1998 and 2010 mass coral bleaching events on the Western Gulf of "
       "Thailand", "DOI resolved through Crossref; the abstract itself is behind a 403"),
    # ------------------------------------------------------------------ 2009-10
    _i("2010-06", "bleaching", "Gulf of Thailand and Andaman Sea", ["2009-10"],
       "El Nino 2009-10",
       "Yeemin et al. (2012): sea surface temperatures of 30-34 °C in March-June 2010, "
       "bleaching over 80% at several sites; mortality about 50-60% in the Andaman Sea and "
       "30-40% in the Gulf of Thailand; 2010 judged similar in extent to 1998 but more "
       "severe in the Gulf.",
       "Yeemin et al. 2012 -- Impacts of coral bleaching, recovery and management in Thailand "
       "(12th International Coral Reef Symposium)",
       "https://reefresilience.org/wp-content/uploads/Yeemin-et-al.-2012-Impacts-of-coral-"
       "bleaching-recovery-and-management-in-Thailand.pdf",
       "Reef Resilience Network (ICRS proceedings paper)", "2012-07",
       "Coral mortality following the bleaching event is estimated at about 50 - 60% within "
       "the Andaman Sea, and about 30 - 40% within the Gulf of Thailand.",
       "peer-reviewed PDF"),
    _i("2010-06", "bleaching", "Koh Tao", ["2009-10"], "El Nino 2009-10",
       "In 2010 many reef areas around Koh Tao experienced 95% coral bleaching with 78% "
       "mortality on parts of some reefs such as Chalok Baan Kao; by the February 2011 survey "
       "the mushroom corals had recovered.",
       "PMBC Research Bulletin 71 -- Hoeksema, Matthews & Yeemin 2012",
       "https://www.dmcr.go.th/dmcr/fckupload/upload/44/image/FullpaperPMBC/"
       "2012%20Vol.71%20Hoeksema%2071%2081.pdf",
       "DMCR / Phuket Marine Biological Center", "2012",
       "many reef areas around Koh Tao experienced 95% coral bleaching, with a 78% mortality "
       "on parts of some reefs, such as Chalok Baan Kao", "peer-reviewed PDF"),
    _i("2010-12", "bleaching", "Thailand national parks (both coasts)", ["2009-10"],
       "El Nino 2009-10",
       "After a DMCR recommendation the DNP closed 18 popular dive sites in 7 of 26 marine "
       "national parks on both sides of the peninsula for 6-18 months; the Gulf of Thailand "
       "was less impacted than the Andaman coast.",
       "Reef Resilience Network -- Malaysia & Thailand: Disturbance Response (case study)",
       "https://reefresilience.org/case-studies/malaysia-thailand-disturbance-response/",
       "Reef Resilience Network", "undated",
       "Eighteen popular dive sites within seven of 26 national parks on both sides of the "
       "peninsula were closed for 6-18 months."),
    _i("2011-01-20", "bleaching", "Thailand", ["2009-10"], "El Nino 2009-10",
       "January 2011: more than half of Thailand's 38,000 acres of reef were bleached and "
       "sites where bleaching reached 80% were closed indefinitely; the Andaman Sea reached "
       "34 °C in April-May 2010.",
       "Yale Environment 360 -- Reef dive sites in Thailand closed after damage from coral "
       "bleaching",
       "https://e360.yale.edu/digest/reef-dive-sites-in-thailand-closed-after-damage-from-"
       "coral-bleaching", "Yale E360", "2011-01-20",
       "More than half of Thailand's 38,000 acres of coral reefs are suffering from bleaching"),
    _i("2011-02-08", "bleaching", "Thailand (18 dive sites)", ["2009-10"], "El Nino 2009-10",
       "Thailand's DNP shut 18 popular dive sites for up to 14 months after the 2010 "
       "bleaching, in the second-hottest year on record; tourism was affected.",
       "Inside Climate News -- Coral bleaching outbreak in Thailand shutting dive sites and "
       "slowing tourism",
       "https://insideclimatenews.org/news/08022011/coral-bleaching-outbreak-thailand-"
       "shutting-dive-sites-and-slowing-tourism/", "Inside Climate News", "2011-02-08",
       "The bleached reefs will stay closed for up to 14 months to let the coral recover."),
    # ------------------------------------------------------------------ 2015-16
    _i("2015-10-09", "haze", "Phuket / Samui / southern Thailand", ["2015-16"],
       "very strong El Nino 2015-16 (Indonesian fire season)",
       "Haze from Indonesian fires blanketed the southern Thai islands in October 2015: five "
       "flights bound for Phuket and Samui turned back to Bangkok on 8 October and two "
       "Singapore-Phuket flights circled for up to an hour; the fires were worsened by "
       "El Nino-driven dry conditions.",
       "ABC News (Australia) -- Smog from Indonesian forest fires blankets Thailand's southern "
       "islands, including Phuket and Samui",
       "https://www.abc.net.au/news/2015-10-09/thai-tourist-islands-hit-by-haze-from-"
       "indonesia-fires/6839490", "ABC News (Australia)", "2015-10-09",
       "Five flights bound for the resort islands of Phuket and Samui turned back to Bangkok "
       "on Thursday"),
    _i("2016-01-25", "flood", "Koh Samui / Koh Phangan", ["2015-16"],
       "very strong El Nino 2015-16 (its NE-monsoon winter)",
       "Storms hit the southern islands including Koh Samui and Koh Phangan in late January "
       "2016, causing floods and the suspension of ferry services between Surat Thani and "
       "Koh Samui: the NE monsoon still floods the island in an El Nino winter.",
       "Bangkok Post -- Samui, Phangan swamped by floods, ferry service halted",
       "https://www.bangkokpost.com/thailand/general/838560/samui-phangan-swamped-by-floods-"
       "ferry-service-halted", "Bangkok Post", "2016-01-25",
       "causing floods and suspension of ferry services between Surat Thani and Koh Samui"),
    _i("2016-03-30", "drought", "Thailand (national; the South is not named)", ["2015-16"],
       "very strong El Nino 2015-16",
       "On 30 March 2016 Thailand was reported to be in its worst drought in decades, with "
       "22 of 76 provinces affected and some major dams below 10% of capacity; the report "
       "attributes it to El Nino and does not mention southern Thailand or Samui.",
       "Al Jazeera -- Thailand hit by its worst drought in decades",
       "https://www.aljazeera.com/news/2016/3/30/thailand-hit-by-its-worst-drought-in-decades",
       "Al Jazeera", "2016-03-30",
       "El Nino-induced water shortage reduces reservoirs to critical levels"),
    _i("2016-05-27", "bleaching", "Thailand (Rayong to Satun, both coasts)", ["2015-16"],
       "very strong El Nino 2015-16",
       "On 26-27 May 2016 Thailand's national parks department indefinitely closed at least "
       "ten dive sites after surveys found bleaching on up to 80% of some reefs; the closures "
       "were to be reviewed before the November high season.",
       "ABC News (Australia) -- Thailand closes ten popular dive sites in bid to slow down "
       "coral bleaching crisis",
       "https://www.abc.net.au/news/2016-05-27/thailand-closes-dive-sites-over-coral-"
       "bleaching-crisis/7450274", "ABC News (Australia) / AFP", "2016-05-27",
       "indefinitely closed at least ten diving spots after a survey found bleaching on up to "
       "80 per cent of some reefs"),
    _i("2016-09-30", "water_shortage", "Koh Samui", ["2015-16"],
       "very strong El Nino 2015-16 (the dry spell that followed it)",
       "Water zoning was introduced on Koh Samui on 30 September 2016, with rationing of tap "
       "water to households and businesses.",
       "Bangkok Post -- Water rationing on Koh Samui as reservoirs dry up",
       "https://www.bangkokpost.com/thailand/general/1099148/water-rationing-on-koh-samui-as-"
       "reservoirs-dry-up", "Bangkok Post", "2016-09-30",
       "Water zoning is being introduced on the holiday island of Koh Samui, with rationing "
       "of tap water to households and businesses."),
    _i("2016-09-30", "water_shortage", "Koh Samui", ["2015-16"],
       "very strong El Nino 2015-16 (the dry spell that followed it)",
       "By late September 2016, after a long rainless spell, Koh Samui was on alternating-zone "
       "tap water supply; the Mared subdistrict reservoir was dry and large hotels were "
       "buying trucked water at more than 100,000 baht a month.",
       "ThaiResidents -- Serious water shortage on Koh Samui",
       "https://thairesidents.com/local/serious-water-shortage-koh-samui/", "ThaiResidents.com",
       "2016-09-30", "zones have been divided to supply water alternatively"),
    _i("2016-10-10", "water_shortage", "Koh Samui", ["2015-16"],
       "very strong El Nino 2015-16 (the dry spell that followed it)",
       "October 2016: Samui's two Pru Krajude reservoirs (800,000 m³ combined) were drying up "
       "after a long rainless spell; the desalination plant at full output could not meet the "
       "island's demand of 30,000 m³ a day, rationing was in force, trucks carted water to "
       "villages and the remaining reservoir water was expected to be unusable within a week.",
       "Bangkok Post -- Severe water shortage on Koh Samui",
       "https://www.bangkokpost.com/thailand/general/1107052/severe-water-shortage-on-koh-samui",
       "Bangkok Post", "2016-10-10",
       "that is still not enough to meet the daily demand of 30,000 cu m from houses and "
       "resorts on the island"),
    # ------------------------------------------------------------------ 2023-24
    _i("2023-07-02", "water_shortage", "Koh Samui", ["2023-24"],
       "strong El Nino 2023-24 (developing year)",
       "In July 2023 Koh Samui's freshwater reserves were said to cover only about 30 days of "
       "demand; water plants produced 15,000 m³ a day and residents paid 250-300 baht for "
       "about 2,000 litres when taps ran dry; the report ties the shortage to El Nino.",
       "The Thaiger -- Water crisis grapples Koh Samui as rising tourist demands amplify "
       "freshwater shortage",
       "https://thethaiger.com/news/national/koh-samui-grapples-with-freshwater-shortage-"
       "amid-rising-tourist-demands", "The Thaiger", "2023-07-02",
       "exacerbated by the El Nino phenomenon resulting in further rainfall shortages"),
    _i("2023-07-02", "water_shortage", "Koh Samui", ["2023-24"],
       "strong El Nino 2023-24 (developing year)",
       "Koh Samui was facing a shortage of freshwater in July 2023 due to a lack of rainfall "
       "and increased water demand.",
       "Bangkok Post -- Freshwater shortage hits Samui",
       "https://www.bangkokpost.com/thailand/general/2603476/freshwater-shortage-hits-samui",
       "Bangkok Post", "2023-07-02",
       "Koh Samui is facing a shortage of freshwater due to a lack of rainfall and increased "
       "water demand."),
    _i("2024-04-04", "water_shortage", "Koh Phangan / Koh Samui", ["2023-24"],
       "strong El Nino 2023-24 (its dry season)",
       "Tap water on Koh Phangan was rationed on a rotating basis from late March 2024, with "
       "only 3,500-4,000 m³ a day supplied; Samui's three reservoirs held 3.2 million m³ and "
       "the island drew 22,000 m³ a day (plus 5,000 in the dry season) through the undersea "
       "pipeline from Surat Thani. El Nino is not named in this article.",
       "The Thaiger -- Water crisis hits Koh Pha-ngan and Koh Samui, tap water rationed",
       "https://thethaiger.com/news/national/water-crisis-hits-koh-pha-ngan-and-koh-samui-"
       "tap-water-rationed", "The Thaiger", "2024-04-04",
       "3,500m3 to 4,000m3 of water trickles through the pipes daily"),
    _i("2024-04-04", "water_shortage", "Koh Samui / Koh Phangan", ["2023-24"],
       "strong El Nino 2023-24 (its dry season)",
       "Thai PBS World confirmed rationing on Pha-ngan since late March 2024 (reservoir "
       "capacity 740,000 m³, desalination 600 m³ a day) and said the drought on both islands "
       "was worse than in previous years.",
       "Thai PBS World -- Water shortages on Samui and Pha-ngan islands ahead of Songkran",
       "https://www.thaipbsworld.com/around-thailand/water-shortages-on-samui-and-pha-ngan-"
       "islands-ahead-of-songkran", "Thai PBS World", "2024-04-04",
       "tap water rationing has been in place on Pha-ngan Island since late March"),
    _i("2024-04", "heat", "Thailand (southern east coast rain at 82% of normal)", ["2023-24"],
       "strong El Nino 2023-24 (its dry season)",
       "TMD's April 2024 summary: several places set new all-time highs and the monthly mean "
       "temperature was 2.6 °C above normal; the southern east coast (Gulf side) received "
       "65.4 mm, 82% of normal.",
       "Thai Meteorological Department -- Monthly summary, April 2024",
       "https://www.tmd.go.th/en/climate/summarymonthly/042024", "TMD", "2024-05",
       "the monthly mean temperature in Thailand was 2.6°C above normal",
       "the TMD site omits its intermediate certificate: fetched with the app's TMD trust "
       "chain (see app/local/collectors.py)"),
    _i("2024-04", "heat", "Thailand", ["2023-24"], "strong El Nino 2023-24 (its dry season)",
       "More than three dozen districts across Thailand's 77 provinces set April records in "
       "2024; Lampang reached 44.2 °C, Bangkok's heat index passed 52 °C and power demand hit "
       "a record 36,699 MW on 29 April. No southern-province figure is given.",
       "The Pattaya News -- Record-breaking heatwave continues across Thailand",
       "https://thepattayanews.com/2024/05/01/record-breaking-heatwave-continues-across-"
       "thailand/", "The Pattaya News", "2024-05-01",
       "more than three dozen districts across the country's 77 provinces recorded their "
       "highest temperatures ever for April"),
    _i("2024-05-10", "bleaching", "Gulf of Thailand incl. Koh Tao (Surat Thani)", ["2023-24"],
       "strong El Nino 2023-24 (sea warming after the peak)",
       "Thailand closed 12 national marine parks on 10 May 2024 (including Mu Koh Chumphon and "
       "Hat Khanom-Mu Koh Thalay Tai, near Samui); 50% of Gulf of Thailand reefs were "
       "bleached including at Koh Tao, 20% in the Andaman; the bleaching began in April and "
       "was expected to last to July, attributed to El Nino-linked sea warming.",
       "The Nation -- Thailand shuts 12 national marine parks amid coral bleaching crisis",
       "https://www.nationthailand.com/news/general/40037914", "The Nation (Thailand)",
       "2024-05-10",
       "50% of coral reefs in the Gulf of Thailand were bleached, including at tourism islands "
       "like Koh Tao in Surat Thani and Koh Kram in Chumphon"),
    _i("2024-05-25", "bleaching", "Thailand (21 marine national parks, 9 in the Gulf)",
       ["2023-24"], "strong El Nino 2023-24 (sea warming after the peak)",
       "By late May 2024 the DNP had detected coral bleaching at 152 locations in 21 marine "
       "national parks, nine of them in the Gulf of Thailand: 54 sites with extremely severe "
       "bleaching (over 50%), 56 severe (11-50%), 39 medium (1-10%); dive sites in five parks "
       "were closed from 2 April.",
       "Bangkok Post -- Bleaching forces diving site closures",
       "https://www.bangkokpost.com/thailand/general/2799027/bleaching-forces-diving-site-"
       "closures", "Bangkok Post", "2024-05-25",
       "coral bleaching has been detected at 152 locations in 21 marine national parks, nine "
       "in the Gulf of Thailand and 12 in the Andaman Sea"),
    _i("2024-05", "bleaching", "Gulf of Thailand", ["2023-24"],
       "strong El Nino 2023-24 (sea warming after the peak)",
       "DMCR retrospective (April 2025): the Gulf of Thailand's worst bleaching was in May "
       "2024, affecting about 90% of corals; overall 60-80% of corals bleached, about 40% "
       "died and over 60% of the affected corals later recovered.",
       "The Nation -- Thailand's coral reefs stage impressive comeback after bleaching event",
       "https://www.nationthailand.com/life/travel/40049128", "The Nation (Thailand)",
       "2025-04-23",
       "The Gulf of Thailand saw its worst bleaching in May 2024, affecting some 90% of "
       "corals."),
    _i("2024-05-13", "bleaching", "Thai marine parks (6 Gulf, 6 Andaman)", ["2023-24"],
       "strong El Nino 2023-24 (sea warming after the peak)",
       "Twelve marine parks were under watch from early April 2024; three showed 50-80% "
       "bleaching in water under 2 m, described as part of the fourth global bleaching event.",
       "Bangkok Tribune -- 12 national marine parks under watch for coral bleaching",
       "https://bkktribune.com/12-national-marine-parks-under-watch-for-coral-bleaching/",
       "Bangkok Tribune", "2024-05-13",
       "corals in three of these marine parks have faced bleaching up to 50-80%"),
    # ------------------------------------------------------------------ not El Nino years
    _i("2010-11-03", "flood", "Koh Samui", [], "La Nina 2010-11 (not an El Nino year)",
       "Koh Samui airport suspended services amid torrential rain and flooding in early "
       "November 2010; the Surat Thani mainland and Don Sak were also flooded, with power "
       "outages and businesses shut.",
       "C9 Hotelworks -- Koh Samui airport closes amid torrential flooding",
       "https://c9hotelworks.com/news/koh-samui-airport-closes-amid-torrential-flooding",
       "C9 Hotelworks", "2010-11-03",
       "Currently the airport has suspended services and Bangkok Airways is not sure when "
       "regular service will resume."),
    _i("2011-03-30", "flood", "Koh Samui / southern Thailand", [],
       "La Nina 2010-11 (not an El Nino year)",
       "Late-March 2011 floods and mudslides killed at least 21 people in the South (7 in "
       "Nakhon Si Thammarat, 3 in Surat Thani); 80 districts of eight provinces were declared "
       "disaster areas, over 50 flights were grounded and about 2,000 people were stranded on "
       "Samui.",
       "Al Jazeera -- Deaths as heavy rain hits Thailand",
       "https://www.aljazeera.com/news/2011/3/30/deaths-as-heavy-rain-hits-thailand",
       "Al Jazeera", "2011-03-30",
       "Bangkok Airways said there were 2,000 people, mostly tourists, stranded on Samui island "
       "either at the airport or in hotels"),
    _i("2011-03-30", "flood", "Koh Samui", [], "La Nina 2010-11 (not an El Nino year)",
       "On 29 March 2011 all 53 Bangkok Airways flights in and out of Koh Samui were "
       "cancelled, Firefly suspended flights because the airport was flooded, and 3 m waves "
       "suspended the ferries between Samui and Surat Thani.",
       "TTG Asia -- Tourists still stranded on Koh Samui",
       "https://www.ttgasia.com/2011/03/30/tourists-still-stranded-on-koh-samui/", "TTG Asia",
       "2011-03-30",
       "All 53 of Bangkok Airways' flights in and out of Koh Samui were cancelled yesterday."),
    _i("2011-03-31", "flood", "southern Thailand incl. Samui, Koh Tao, Koh Phangan", [],
       "La Nina 2010-11 (not an El Nino year)",
       "By 31 March 2011 at least 21 were dead and about a million people affected; the navy "
       "carrier Chakri Naruebet evacuated 734 holidaymakers from Koh Tao and Koh Phangan, and "
       "Samui flights had resumed.",
       "Al Jazeera -- Thai military searches for mudslide victims",
       "https://www.aljazeera.com/news/2011/3/31/thai-military-searches-for-mudslide-victims",
       "Al Jazeera", "2011-03-31",
       "At least 21 people have died after unseasonably wet weather deluged the homes and "
       "businesses of around a million people"),
    _i("2016-12-05", "flood", "southern Thailand incl. Koh Samui", [],
       "weak La Nina 2016-17, the winter after the 2015-16 El Nino",
       "A tropical depression on 1-2 December 2016 plus the northeast monsoon dropped over "
       "500 mm on the southern coast between 1 and 7 December 2016; the retrospective says "
       "the flooding killed 91 and affected 360,000 and shows flooded Koh Samui streets "
       "(figures differ between tallies).",
       "The Weather Network -- Remembering the Thailand floods that lasted more than a month",
       "https://www.theweathernetwork.com/en/news/weather/severe/this-day-in-weather-history-"
       "december-5-2016-thailand-flooding", "The Weather Network", "2020-12-05",
       "Over 500 mm of rain fell between Dec.1-7 along the southern coast of the country",
       "retrospective article"),
    _i("2016-12-03", "flood", "Koh Samui", [],
       "weak La Nina 2016-17, the winter after the 2015-16 El Nino",
       "A local blog (secondary) documents the 3-5 December 2016 flooding in Bang Rak, "
       "Chaweng, Choengmon and Maenam: roads closed, dive and snorkel boats stopped, some "
       "Samui flights delayed, and the island declared a disaster zone on 5 December.",
       "Camille's Samui Info blog -- Flooding on Koh Samui",
       "https://samui-weather.blogspot.com/2016/12/flooding-on-koh-samui.html",
       "samui-weather.blogspot.com (local blog)", "2016-12-03",
       "the island has today been declared a disaster zone", "local blog, secondary source"),
    _i("2017-01-05", "flood", "Koh Samui / southern Thailand", [],
       "weak La Nina 2016-17, the winter after the 2015-16 El Nino",
       "AP, 5 January 2017: eight southern provinces flooded since 1 January, at least 3-5 "
       "dead, rail and six long-distance bus routes cut, and flooding on Samui snarled "
       "traffic and delayed flights.",
       "Fox News (AP) -- Flooding disrupts transit, spoils holidays in south Thailand",
       "https://www.foxnews.com/world/flooding-disrupts-transit-spoils-holidays-in-south-"
       "thailand.amp", "Associated Press via Fox News", "2017-01-05",
       "Flooding on the resort island of Samui in the Gulf of Thailand snarled traffic and "
       "delayed flights to and from the popular tourist destination."),
    _i("2017-01-09", "flood", "southern Thailand (12 provinces incl. Surat Thani, Nakhon Si "
       "Thammarat)", [], "weak La Nina 2016-17, the winter after the 2015-16 El Nino",
       "DDPM figures on 9 January 2017: 21 dead, 2 missing, 958,602 residents affected in 12 "
       "southern provinces since 1 January; 1 billion m³ of floodwater in the Pak Phanang "
       "basin; 218 road sections, 59 bridges and 2,253 schools damaged.",
       "The Nation -- No let-up as flood toll hits 21",
       "https://www.nationthailand.com/detail/news/30303792", "The Nation (Thailand)",
       "2017-01-09",
       "Since January 1 the Southern floods had already affected 958,602 residents in the 12 "
       "provinces."),
    _i("2019-01-04", "storm", "Nakhon Si Thammarat / Koh Samui / Surat Thani", [],
       "weak El Nino 2018-19 (not one of the strong events)",
       "Tropical Storm Pabuk made landfall at Pak Phanang just after midday on 4 January 2019 "
       "(45 mph winds), the first January tropical cyclone in Thai records since 1951; 30,000 "
       "were evacuated in Nakhon Si Thammarat, Gulf ferries were suspended, Nakhon Si "
       "Thammarat and Surat Thani airports closed and red flags flew on Samui beaches.",
       "The Weather Channel -- Tropical Storm Pabuk makes first on record southern Thailand "
       "January landfall; two killed, thousands evacuated",
       "https://weather.com/news/news/2019-01-03-thailand-tropical-storm-pabuk", "weather.com",
       "2019-01-05",
       "no previous tropical cyclone had struck Thailand in January, February or March in "
       "records dating to 1951"),
    _i("2019-01-05", "storm", "Koh Samui", [], "weak El Nino 2018-19 (not one of the strong "
       "events)",
       "During Pabuk about 20,000 tourists were on Koh Samui; all transport to the mainland "
       "was suspended, beaches closed, one person died and one was missing from a capsized "
       "fishing boat, and over 6,100 people were evacuated in four provinces.",
       "ABC News (Australia) -- At least one dead on capsized boat as Tropical Storm Pabuk "
       "batters Thailand",
       "https://www.abc.net.au/news/2019-01-05/one-dead-as-tropical-storm-pabuk-batters-"
       "thailand/10686700", "ABC News (Australia)", "2019-01-05",
       "The island is now totally cut off from the mainland, all kinds of transportation (to "
       "mainland) have been suspended since yesterday."),
    _i("2019-09-23", "haze", "Phuket / southern Thailand", [],
       "weak El Nino 2018-19 (Indonesian fire season)",
       "On 23 September 2019 smoke from Indonesian plantation fires cut Phuket's visibility "
       "below 1 km with particulate readings three times the 50 µg/m³ upper limit; "
       "Narathiwat exceeded 150.",
       "The Thaiger -- Smoke-laced smog envelops Phuket",
       "https://thethaiger.com/news/phuket/smoke-laced-smog-envelops-phuket", "The Thaiger",
       "2019-09-23",
       "air pollution is three times the world upper-limit standard of 50 micrograms per cubic "
       "metre of air"),
    _i("2022-12-18", "storm", "Koh Samui / Koh Phangan / Koh Tao ferries", [],
       "La Nina 2022-23 (not an El Nino year)",
       "All ferry services between the mainland and Samui, Phangan and Tao were suspended on "
       "18-19 December 2022 as a strong northeast-monsoon surge brought 2-4 m waves; Seatran "
       "and Raja Ferry offered refunds or rebooking.",
       "The Thaiger -- Heavy rains close Gulf ferries, Surin Islands for 2 days",
       "https://thethaiger.com/hot-news/weather/heavy-rains-close-gulf-ferries-surin-islands-"
       "for-2-days", "The Thaiger", "2022-12-18",
       "all ferry services between the mainland and Koh Samui, Koh Phangan, and Koh Tao have "
       "been suspended for two days"),
    _i("2024-11-30", "flood", "southern Thailand (8 provinces; Surat Thani among relief "
       "recipients)", [], "ENSO-neutral, the winter after the 2023-24 El Nino",
       "By 30 November 2024 the southern floods had killed 9 (Phatthalung 1, Songkhla 3, "
       "Pattani 3, Yala 1, Narathiwat 1) and affected over 550,000 people in 78 districts; 200 "
       "shelters held more than 13,000 evacuees; Surat Thani was among six provinces allotted "
       "70 million baht each in relief.",
       "Khaosod English -- Southern Thailand flooding crisis worsens: 9 dead, over 550,000 "
       "affected",
       "https://www.khaosodenglish.com/news/2024/11/30/southern-thailand-flooding-crisis-"
       "worsens-9-dead-over-550000-affected/", "Khaosod English", "2024-11-30",
       "The death toll currently stands at nine, with casualties reported in Phatthalung (1), "
       "Songkhla (3), Pattani (3), Yala (1), and Narathiwat (1)."),
    _i("2024-11-30", "flood", "southern Thailand (Nakhon Si Thammarat to Satun)", [],
       "ENSO-neutral, the winter after the 2023-24 El Nino",
       "At least 4 dead and more than 240,000 households affected by 30 November 2024; 24-hour "
       "rainfall reached 205 mm at Chian Yai (Nakhon Si Thammarat) and 128.2 mm at Khao Chong "
       "(Trang). Surat Thani is not listed in this report.",
       "The Watchers -- Severe floods hit southern Thailand, affecting over 240 000 "
       "households",
       "https://watchers.news/2024/11/30/severe-floods-hit-southern-thailand-affecting-over-"
       "240-000-households/", "The Watchers", "2024-11-30", "205 mm (8.07 inches)"),
    _i("2024-12-04", "flood", "southern Thailand (Pattani, Narathiwat, Songkhla, Nakhon Si "
       "Thammarat, Phatthalung)", [], "ENSO-neutral, the winter after the 2023-24 El Nino",
       "The death toll reached 29 by 4 December 2024, with more than 155,000 households "
       "affected and over 33,000 people displaced; the cabinet approved relief payments.",
       "VOA -- Death toll rises to 29 in southern Thailand floods",
       "https://www.voanews.com/a/death-toll-rises-to-29-in-southern-thailand-floods/"
       "7886658.html", "Voice of America", "2024-12-04",
       "The death toll now stands at 29, up from 25 reported on Tuesday."),
    _i("2024-12-14", "flood", "Koh Tao (Surat Thani)", [],
       "ENSO-neutral, the winter after the 2023-24 El Nino",
       "Flash floods up to 60 cm deep hit Koh Tao on 14 December 2024 after continuous heavy "
       "rain since 13 December, damaging homes, shops, motorcycles and cars.",
       "Thai FYI -- Flash floods hit Koh Tao following heavy rainfall",
       "https://www.thai.fyi/2024/12/14/565/surat-thani-koh-tao-floods", "thai.fyi",
       "2024-12-14", "continuous heavy rainfall since December 13"),
    _i("2024-12-28", "flood", "Koh Phangan (Surat Thani)", [],
       "ENSO-neutral, the winter after the 2023-24 El Nino",
       "All-night rain to the morning of 28 December 2024 flooded residential areas and roads "
       "on Koh Phangan; a pickup truck was swept into the sea near Ban Tai.",
       "Thai Newsroom -- Koh Phangan flooded after heavy all-night rain",
       "https://thainewsroom.com/2024/12/28/koh-phangan-flooded-after-heavy-all-night-rain/",
       "Thai Newsroom", "2024-12-28",
       "the heavy all-night downpour caused large amounts of runoffs to gush down the hills to "
       "flow to the sea"),
    # ------------------------------------------------------------------ current event
    _i("2026-07-29", "water_shortage", "Koh Samui", ["2026-27"],
       "strong El Nino 2026-27 (the current event, developing year)",
       "Dry weather worsened by El Nino depleted Samui's reservoirs in July 2026: the undersea "
       "pipeline from the mainland supplies about 16,000 m³ a day against an average demand "
       "of about 34,000 m³, so the PWA rotated tap water supply across zones of the island "
       "from 3 August 2026; hotels bought trucked water and the Interior Ministry ordered "
       "urgent measures.",
       "Bangkok Post -- Koh Samui faces water rationing",
       "https://www.bangkokpost.com/thailand/general/3293479/koh-samui-faces-water-rationing",
       "Bangkok Post", "2026-07-29",
       "The underwater pipeline from the mainland supplies about 16,000 cubic metres of water "
       "per day but average demand is about 34,000 cubic metres."),
    # ------------------------------------------------------------------ science (context)
    _i("2005", "paper", "Thailand (summer monsoon rainfall)", [], "context",
       "Singhrattna N., Rajagopalan B., Krishna Kumar K., Clark M. (2005), Interannual and "
       "interdecadal variability of Thailand summer monsoon season, Journal of Climate 18(11): "
       "1697-1708.",
       "Journal of Climate -- Interannual and interdecadal variability of Thailand summer "
       "monsoon season", "https://doi.org/10.1175/JCLI3364.1",
       "American Meteorological Society", "2005",
       "Interannual and Interdecadal Variability of Thailand Summer Monsoon Season",
       "DOI resolved through Crossref; the abstract page answers 403 to scripts"),
    _i("2005", "paper", "Southeast Asia incl. the peninsula", [], "context",
       "Juneng L., Tangang F.T. (2005), Evolution of ENSO-related rainfall anomalies in "
       "Southeast Asia region and its relationship with atmosphere-ocean variations in the "
       "Indo-Pacific sector, Climate Dynamics 25: 337-350.",
       "Climate Dynamics -- Evolution of ENSO-related rainfall anomalies in Southeast Asia "
       "region", "https://doi.org/10.1007/s00382-005-0031-6", "Springer", "2005",
       "Evolution of ENSO-related rainfall anomalies in Southeast Asia region and its "
       "relationship with atmosphere-ocean variations in Indo-Pacific sector",
       "DOI resolved through Crossref"),
    _i("2016", "paper", "Thailand (total and extreme precipitation)", [], "context",
       "Limsakul A., Singhruck P. (2016), Long-term trends and variability of total and "
       "extreme precipitation in Thailand, Atmospheric Research 169: 301-317.",
       "Atmospheric Research -- Long-term trends and variability of total and extreme "
       "precipitation in Thailand", "https://doi.org/10.1016/j.atmosres.2015.10.015",
       "Elsevier", "2016",
       "Long-term trends and variability of total and extreme precipitation in Thailand",
       "DOI resolved through Crossref"),
    _i("2025", "paper", "Thailand (rainfall vs ENSO and IOD)", [], "context",
       "Madolli M.J. et al. (2025), A systematic review on rainfall patterns of Thailand: "
       "insights into variability and its relationship with ENSO and IOD, Earth-Science "
       "Reviews.",
       "Earth-Science Reviews -- A systematic review on rainfall patterns of Thailand",
       "https://doi.org/10.1016/j.earscirev.2025.105102", "Elsevier", "2025",
       "A systematic review on rainfall patterns of Thailand: Insights into variability and "
       "its relationship with ENSO and IOD", "DOI resolved through Crossref"),
]

NOT_FOUND = [
    ("Koh Samui water shortage or rationing in the 2019-20 dry season (searched The Thaiger, "
     "Samui Times, Khaosod English, Thai PBS: only 2016, 2023, 2024 and 2026 reports surfaced)"),
    "Koh Samui water shortage in 1998 (El Nino 1997-98) and in 1992-93",
    "Samui / Koh Tao-specific bleaching percentages for 2016",
    "DDPM casualty and affected-population tallies for Tropical Storm Pabuk (January 2019)",
    "a November 2011 flood on Koh Samui",
]
