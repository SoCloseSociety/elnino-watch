# Webcams: what was considered, included, excluded (2026-09-24)

Code: `app/collectors/extra_cams.py` (collectors `webcams_images`, `webcams_streams`,
`webcams_windy`), `app/cams_api.py` (`GET /api/webcams`, `/api/webcams/{id}`,
`/api/webcams/{id}/snapshot`). Help topics: `docs/help_topics/webcams*.md`.

## The rule (CLAUDE.md rule 11)
Only cameras their owner publishes for public viewing. Never unsecured-camera
directories (Insecam style), device search engines (Shodan), default-password IP
cams, or anything reached by bypassing access control. Provider terms are followed:
where frames may not be reused, the app links to the official page.

## How liveness is checked (automated, every 30-60 min)
| Feed type | Check | Status it can reach |
|---|---|---|
| NOAA NDBC BuoyCAM | `buoycams.php` JSON (lists newest image per buoy) + HEAD on the image; age from the UTC time in the file name | live / stale / offline (no photo listed) / error |
| JMA Himawari | `sat_img.php?area=` page, first time option (e.g. value 1350 = image 14:00 UTC) + HEAD on the image | live / stale / error |
| NOAA GOES (STAR CDN) | HEAD on `1808x1808.jpg`; age from `Last-Modified` | live / stale / error |
| YouTube venue stream | official oEmbed endpoint: 200 = still published + embeddable; 401/403 = embedding disabled; 404 = removed; channel name must still match the verified publisher | reachable / offline / error |
| SkylineWebcams | GET of the public cam page (robots.txt allows all); their page shows `OFFLINE` when the cam is down | online / offline / error |
| Owner page (link only) | HEAD on the page | reachable / error |
| Windy Webcams API | `status` + `lastUpdatedOn` per webcam (needs key) | live / stale / reachable / offline |

We do NOT scrape YouTube watch pages in the collector (YouTube terms): so a YouTube
cam is "reachable" (published, embeddable), not "live". The player itself shows
whether it is broadcasting. The one-off manual check on 2026-09-24 (below) did look
at each watch page's `isLiveNow` flag to choose the streams.

## Snapshot proxy vs embed vs link
| Mode | Who | Why |
|---|---|---|
| proxy (`/api/webcams/{id}/snapshot`, 120 s cache, 5 MB cap, credit headers) | NOAA NDBC, NOAA NESDIS GOES | US Government work, public domain |
| proxy | JMA Himawari | JMA terms: Public Data License 1.0, CC BY 4.0 compatible, credit "Source: Japan Meteorological Agency" (https://www.jma.go.jp/jma/en/copyright.html) |
| embed | YouTube streams | owner-published, `playableInEmbed` true; only via the official YouTube embed player (youtube-nocookie) |
| embed | Windy webcams | Windy terms: show via their player/URLs, link to the webcam page; image URLs carry 10-min tokens so they are never stored |
| link | SkylineWebcams | terms forbid copying frames or re-streaming without written permission (https://www.skylinewebcams.com/en/terms-of-use.html) |
| link | Phuket 101 (Patong Tower) | owner's ipcamlive player sends `Content-Security-Policy: frame-ancestors` limited to phuket101.net / sawadeecam.com: embedding elsewhere is not allowed |
| link | SSS Phuket (Kata), BMA Traffic | owner / agency page; no reuse licence for frames |

## Included (verified 2026-09-24 ~14:00 UTC)
Evidence: HTTP 200 + (image time | oEmbed author + `isLiveNow` true on the watch page |
Skyline page without OFFLINE). First live collector run: 101 cams, 95 ok
(52 live images, 10 online, 33 reachable), 6 offline (5 NDBC buoys with no photo,
1 publisher-name mismatch, fixed; the re-run gave streams 44/44 ok). Live snapshot proxy test: himawari_se1_b13, goes18_fd_ir, ndbc_51002 served 200 image/jpeg; skyline_mancora answered 409 link_only.

### Koh Samui (area `samui`)
| id | Place / kind | Publisher | Mode | Evidence |
|---|---|---|---|---|
| yt_CSp55hSd_6A | Fisherman's Village beach (El Gaucho), Bophut / beach | The Real Samui Webcam | embed | oEmbed 200, live |
| yt_x73IEW0fOo0 | Floating Lotus, Big Buddha / beach | The Real Samui Webcam | embed | oEmbed 200, live |
| yt_RN2miwo_S-o | Sunset Bar, Bang Rak / beach | STREETS OF THAILAND | embed | oEmbed 200, live |
| yt_J9g4uE0gvm4 | Karma Two Palms, Bang Po (NW) / beach | STREETS OF THAILAND | embed | oEmbed 200, live |
| yt_3N3ZwIB_X4Y | Crystal Bay Yacht Club, Lamai / beach | The Real Samui Webcam | embed | oEmbed 200, live |
| yt_Fw9hgttWzIg | Crystal Bay Beach Resort / beach | The Real Samui Webcam | embed | oEmbed 200, live |
| yt_Szx0K7gZBx8 | Villa Tao sea view, Lamai / beach | The Real Samui Webcam | embed | oEmbed 200, live |
| yt_Tpj0cmMVOd0 | Baobab, Lamai / beach | The Real Samui Webcam | embed | oEmbed 200, live |
| yt_NwnRppDlkX8 | Black Pearl, Lamai / beach | STREETS OF THAILAND | embed | oEmbed 200, live |
| yt_ZAGJyPv4mNU | Teddy Weed beach club, Lamai / beach | STREETS OF THAILAND | embed | oEmbed 200, live |
| yt_wP6hpWgPJ98 | Banyan Tree Samui, Lamai Bay / beach | Banyan Tree Samui (hotel's own channel) | embed | oEmbed 200, live |
| skyline_choengmon_beach | Choeng Mon / beach | SkylineWebcams | link | page 200, not OFFLINE |
| skyline_lamai | Lamai / beach | SkylineWebcams | link | page 200, not OFFLINE |
| yt_DwKCna1mumk, yt_yFgVmioYkys, yt_Ajo0iFkX3EY, yt_OdY-pbgl1Mk | Soi Green Mango, Chaweng / city | The Real Samui Webcam; Jimmywoo's Samui | embed | oEmbed 200, live |
| yt_Jv_2vPCbZUo | Bondi, Chaweng Beach Road / city | The Real Samui Webcam | embed | oEmbed 200, live |
| yt_HdaWcBamcSA | Bondi, Lamai / city | The Real Samui Webcam | embed | oEmbed 200, live |
| yt_bbBGNNPu0rg, yt_FyFAqPHBKiQ | Fisherman's Village street / city | The Real Samui Webcam | embed | oEmbed 200, live |
| himawari_se1_b13, himawari_se1_trm | Himawari-9 Southeast Asia sector (Gulf of Thailand) / satellite | JMA | proxy | image 14:00 UTC, HTTP 200 |

### Ferry route (area `ferry_route`)
| id | Place / kind | Publisher | Mode | Evidence |
|---|---|---|---|---|
| yt_gtSsnmLXJV4 | Koh Tao, Mae Haad Bay / pier | Scuba Birds PADI 5 * IDC Dive Center (also on their own site) | embed | oEmbed 200, live |
| yt_MW3fisTCXRQ | Koh Phangan, Haad Rin (House of Sanskara) / beach | Teleport.camera | embed | oEmbed 200, live |

### Wider Thailand (area `thailand`)
| id | Place / kind | Publisher | Mode | Evidence |
|---|---|---|---|---|
| yt_UemFRPrl1hk, yt_Q71sLS8h9a4 | Bangkok Sukhumvit Soi 11 / 19 / city | The Real Samui Webcam | embed | live |
| yt_a_bUVExv_Cg | Bangkok Petchaburi Road / city | Tahug | embed | live |
| bma_traffic | Bangkok BMA Traffic CCTV portal / traffic | Bangkok Metropolitan Administration (official) | link | http://www.bmatraffic.com/ 200 |
| yt_Qa5LqU9xxtc | Pattaya Beach Road / beach | PattayaBob360IRL | embed | live |
| yt__nvG0c9keWI | Patong, Sainamyen Road / city | Randomly Entertained | embed | live |
| phuket101_patong | Patong Bay from Patong Tower / beach | Phuket 101 | link | page 200 |
| sss_kata | Kata Beach / beach | SSS Phuket Dive & Surf | link | page 200 |
| yt_cD5ZEBOf2Tg | Khao Lak / beach | Khao Lak Land Discovery | embed | live |

### ENSO regions
| id | Place / kind | Publisher | Mode | Evidence |
|---|---|---|---|---|
| skyline_mancora, skyline_pimentel, skyline_playa_huanchaco, skyline_miraflores | Peru coast (Piura, Lambayeque, Trujillo, Lima) / beach, pier, city | SkylineWebcams | link | page 200, not OFFLINE |
| skyline_montanita, skyline_paco_illescas, skyline_galapagos_ecuador | Ecuador coast + Galapagos / beach | SkylineWebcams | link | page 200, not OFFLINE |
| yt_5uZa3-RMFos | Sydney Harbour / city | WebcamSydney | embed | live |
| yt_dypAtzvl24s | Port of Newcastle NSW / pier | Port of Newcastle (official port) | embed | live |
| skyline_mount_cole | Mount Cole forest, Victoria / city (landscape) | SkylineWebcams | link | page 200 |
| yt_L1duJDAqbJY | Bali, Bukit Jimbaran / city | Bali Weather Live Stream | embed | live |
| yt_RsPsUMd7Wu4 | Drini beach, Gunungkidul (Java) / beach | Kominfo Gunungkidul (regional government) | embed | live |
| ndbc_* (50 Pacific buoys, 45 with a current photo: 46xxx, 51xxx) | NOAA BuoyCAMs, Hawaii / US west coast / Alaska / Bering / 175 E / buoy | NOAA NDBC | proxy | JSON + image HEAD 200, images 13:10 UTC |
| himawari_fd_b13, himawari_fd_trm | Himawari full disk / satellite | JMA | proxy | 200, 14:00 UTC |
| goes18_fd_geocolor, goes18_fd_ir | GOES-West full disk / satellite | NOAA NESDIS STAR | proxy | 200, Last-Modified 14:07 / 13:51 UTC |
| goes19_fd_geocolor | GOES-East full disk / satellite | NOAA NESDIS STAR | proxy | 200, Last-Modified 13:47 UTC |

Coordinates of venue cams are approximate (venue / beach, `coord_precision: approx`);
NDBC positions are NOAA's; satellites carry their sector centre.

## Excluded, with reasons
| Candidate | Reason |
|---|---|
| Insecam / opencctv.org ("614 live cameras in Thailand") and similar directories | directories of cameras whose owners did not choose to publish them, or of unclear origin: rule 11 |
| Shodan / default-password IP cams | never, rule 11 |
| NICT Himawari (himawari.asia `latest.json` 200) | works, but redistribution terms not verified; JMA publishes the same satellite under a clear open licence |
| Nathon pier / west coast (EJBV Villa, video unGBfW8m_9U via thai-rest.com / tabi.cam) | YouTube oEmbed 404: stream removed |
| Samui airport runway cam (webcamtaxi, webcam.scs.com.ua) | only on aggregators; webcamtaxi answers 403 to automated checks; no owner page found |
| Windfinder "Koh Samui Airport" | page lists "No nearby webcams available" |
| Koh Phangan Thong Sala, Haad Rin (Skyline), Koh Tao Mae Haad (Skyline) | SkylineWebcams marks them OFFLINE (Mae Haad is covered by the Scuba Birds stream) |
| Haad Rin byhWzqNSsF0 (Teleport.camera) | not live (isLiveNow false); MW3fisTCXRQ is the live one |
| Chaweng Hushbar rroTT7AsqY0, Green Mango gEm6dAETk7E | listed on the channel but not live today; DwKCna1mumk / yFgVmioYkys used instead |
| Skyline "Volcano Merapi" (Yogyakarta) | the embedded stream is afarTV's "Fuego Volcano (Guatemala)": mislabelled, not Indonesia |
| Skyline "Sydney skyline" 8ycZQkBNjcM (channel "Luis Angelo") | publisher's relation to the camera is unclear; WebcamSydney (own cam) used instead |
| Skyline Banyan Food Market, Pattaya Soi Buakhao, Melbourne Platinum Apartments, Brisbane River | live and public, but they add nothing for weather / sea checks beyond the cams already listed (kept the list focused) |
| webcamtaxi.com (Thong Sala, Patong, Haad Rin pages) | 403 for automated checks; the underlying streams are the owners' YouTube streams, used directly where live |
| Donsak / Seatran / Raja ferry pier cams | none published by the operators or the Marine Department was found |
| Thai DOH / DRR highway CCTV | no public portal with stable, documented public images found; BMA Traffic (Bangkok) is the one official Thai CCTV portal included, link-only |
| Surfline / Coastalwatch (Australia) | commercial, subscription terms: not a free public feed |
| Phuket 101 ipcamlive snapshot.php | player is CSP-locked to the owner's domain: snapshot reuse not intended; link to the page instead |

## Needs configuration
- `WINDY_WEBCAMS_KEY` (free key, https://api.windy.com/keys): collector `webcams_windy`
  shows `needs_config` until set (env var or the project `.env`). It queries webcams
  within 30 km of Koh Samui, 40 km of Koh Phangan / Koh Tao and 50 km of Donsak /
  Surat Thani. No real Windy response could be captured without a key, so its parser is
  tested against the example values of Windy's published OpenAPI document; capture a real
  response into `tests/fixtures/cams/` once a key exists.
- Optional follow-up: a `YOUTUBE_API_KEY` (YouTube Data API `videos.list`,
  `liveStreamingDetails`) would let YouTube cams move from "reachable" to a confirmed
  "live"; not implemented (no key to capture a real fixture).

## Maintenance
YouTube stream ids change when a venue restarts its stream: the cam then shows
`offline` ("video removed or made private"). Find the new id on the publisher's
channel (`/streams`), check it is the same owner and live, and update `STREAM_CATALOG`.
A publisher-name change is flagged "re-verify" and never shown as ok.
