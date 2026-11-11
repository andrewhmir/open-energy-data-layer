# Philippine Energy Data Landscape — Evidence Pack for "One Open Energy Data Layer"

**Prepared for:** BetterGov PH Fellowship, Energy challenge (DOE + Mura, Malinis, at Maaasahang Kuryente Coalition)
**Prepared by:** data-researcher (research task-1)
**Research date / access date for every URL below:** 2026-11-10 (Asia/Manila)
**Method:** live HTTP fetches from this environment (curl and a fetch tool). No browser automation, no login, no interpretation of paywalled content.
**Verification labels used throughout:** `[V]` = verified live (HTTP 200 + content inspected); `[P]` = partially verified (reachable but content behind JS/Cloudflare, or only a static asset reachable); `[L]` = likely / inferred from a verified artefact but not directly confirmed; `[U]` = unknown / could not be verified; `[X]` = verified as failing (4xx/blocked/dead).

> Ground rule applied: where the live web disagrees with the fellowship challenge page or the Energy pitch deck, the live source wins and the discrepancy is flagged in §12. This file deliberately does **not** invent endpoint paths, dataset IDs, or figures.

---

## 0. TL;DR for the proposal (read this if you read nothing else)

1. **The single biggest finding: the "one price table" already exists, machine-readable, in the open.** DOE's *Electricity Rates & Power Market Monitor* page embeds a public Google Sheet with **monthly residential, commercial and industrial rates plus blended generation charge for 141 DU/EC rows, January 2018 → December 2026**. A plain CSV export works without login. This is not an API and DOE does not advertise it, but a 3-month fellowship can stand on it on day 1.
2. **The 142-utility claim checks out.** The sheet has 141 rows per tab (21 PIOU + 120 EC) and 142 unique entity names across tabs (the difference is `DANECO` vs `DANECO/NORDECO`) — exactly the "no common ID" problem the deck describes. 21 rows are flagged `OFFGRID`.
3. **Deck figures are reproducible from that sheet**: Meralco June 2026 = 14.48, SOLECO (Southern Leyte) = 16.57 and **+32.2% vs May**, BISELCO (Busuanga, off-grid) = 24.92. The headline **₱12.43 does not reproduce as a simple mean of the June 2026 column (simple mean = 12.29, median 12.10)** — see §12.3.
4. **The hard blockers are regulatory-agency WAFs, not the data's existence.** ERC, NEA, PSA (incl. PSGC/OpenSTAT), FOI portal and NGCP HTML are all behind Cloudflare 403s for automated clients. NGCP's **static PDFs are downloadable** even though its site is blocked. These sources must be partnership/FOI routes, not scrapers.
5. **DOE's portal is a 2026 Next.js rebuild**: content is real but there is no API, no robots policy, and removed legacy paths return **HTTP 200 with a "Page Not Found" shell** — status codes cannot be trusted. `legacy.doe.gov.ph` is dead.
6. **Presyo PH (ICSC) is the closest existing competitor**: `presyo.icsc.ngo`, launched 2026-04-28, >150 DUs/ECs, and it serves a public JSON API. The fellowship should integrate/attribute rather than rebuild blind.

---

## 1. Executive summary — what exists vs. what must be built

### 1.1 What already exists publicly (verified)

| Layer | What exists | Where | Readiness |
|---|---|---|---|
| DU/EC master list (name, grid, region, island, type) | Implicit in DOE's rate sheet (141 rows/tab, 142 unique) | DOE embedded Google Sheet | Machine-readable, no stable IDs, no franchise/PSGC fields |
| Residential/commercial/industrial rates, monthly | 2018–2026 monthly, per DU/EC | Same DOE Google Sheet | Machine-readable, NDA gaps |
| Blended generation charge per DU | 2018–2026 monthly | Same Google Sheet (4th tab) | Machine-readable |
| Plant-level capacity (grid-connected) | LoEPP PDFs as of Aug 2026 (Luzon/Visayas/Mindanao/summary) | doe.gov.ph CloudFront PDFs | Text PDFs, fixed layout, no API |
| RE contracts / pipeline artefacts | HSC applications, RE plants with COE-to-ERC for FIT eligibility, FIT Monitoring Board summary, COA hydro, geothermal applications, wind applications — as of 30 Jun 2026 | doe.gov.ph RE page → CloudFront PDFs | PDFs only, no dashboard feed |
| Microgrid / PVM / proponent databases | 3 interactive dashboards + data-collection programme | doe.gov.ph/data/microgrid-mapping | UI only, no download/API found |
| Fuel prices | Weekly "Oil Monitor" PDFs, LPG monitor, discount stations, retail outlets, fuel-subsidy station lists | doe.gov.ph Data & Price Watch | PDFs + pages, mixed |
| Meralco monthly rates | 2026-01 → 2026-10 panels + monthly PDFs + rates archive | meralco.com.ph | Web tables + PDFs |
| EC billing rates | Per-coop PDFs (sample: SURNECO June 2026, fully text-extractable) | individual coop sites | Highly variable |
| WESM market data | 40+ dataset pages (prices, reserves, schedules), monthly "WESM DU Rates" reports | iemop.ph | JS apps, no documented API |
| Transmission plans | TDP 2025–2050 report, TDP 2020–2040 volumes (PDFs reachable directly) | ngcp.ph `/Attachment-Uploads/` | PDFs |
| Geography codes | PSGC (region/province/city/municipality/barangay) | psa.gov.ph | Exists, bot-blocked |
| Regional comparability layer | ASEAN Energy Statistics Leaflet/Yearbook + AEDS | aseanenergy.org | PDF/DB, "All rights reserved" |
| Consolidated consumer platform (peer) | Presyo PH: >150 DUs, national/local views, public JSON API | presyo.icsc.ngo | App + API, license unclear |

### 1.2 What is missing / must be built (gap analysis)

1. **A canonical entity registry.** No holder publishes a stable utility ID. DOE uses names only (`DANECO` vs `DANECO/NORDECO` in the same workbook); ERC, NEA and DOE each keep separate lists (per deck) and none is public as data. **Build:** `utility_id` namespace + crosswalk (DOE name, ERC case name, NEA coop name, PSGC areas served, franchise type, grid, island, off-grid flag) — the API's spine.
2. **One normalized retail price table with documented schema and provenance.** DOE's sheet is wide-format (one column per month), NDA-coded, unversioned, license-unstated, and embedded in a page rather than published as a dataset. **Build:** tidy long-format table (`utility_id, month, customer_class, component, value, unit, source_doc, retrieved_at`) with lineage back to DOE sheet tabs and utility PDFs.
3. **Bill-component granularity.** DOE publishes only totals + blended generation charge; the utility PDFs carry ~20 line items (generation, transmission, system loss, distribution/supply/metering, subsidies, universal charges, VAT). **Build:** component schema, then parse where available (starts with Meralco + a few ECs), and request DOE/ERC disclosure.
4. **Machine-readable DOE dashboard feeds.** DOE's RE/plant/microgrid content is PDF/UI only; there is no public API in evidence. **Build:** XLSX/PDF→JSON services + a stable feed behind the existing dashboards, co-signed by DOE.
5. **Grid reliability / supply-time series.** No public, verified bulk source was found for daily supply-demand or reliability. **Build/partner:** request from NGCP/DOE; otherwise omit from v1 (do not fabricate).
6. **Geography join.** PSA PSGC exists but is bot-blocked; no public utility→PSGC crosswalk exists. **Build:** seeded crosswalk, crowd-verified, published with confidence fields.
7. **Publishing discipline.** No release calendar, no vintage IDs, no checksums, no deprecation policy on any source above. **Build:** provenance/versioning convention + "retrieved_at/sha256" on every ingestion, published on COMPASS.

---

## 2. DOE — data assets (the core of the challenge)

### 2.1 Portal facts

- Main portal: <https://doe.gov.ph/> `[V]` — rebuilt in 2026 as a Next.js app. Footer states: "All content is in the public domain unless otherwise stated." No public API, no `/robots.txt` (path returns the app shell), no documented data license per dataset.
- **Access quirk (important for scrapers):** removed or never-migrated paths return **HTTP 200** with a client-rendered "Page Not Found". HTTP status is therefore useless for validation; check page title/body. `[V]` verified on `/data`, `/electric-power`, `/energy-statistics`, `/philippine-energy-plan`.
- Old portal `legacy.doe.gov.ph` (which hosted the historical "List of Existing Power Plants", DU lists, etc.) is **dead** — DNS/connection failure `[X]`. Search engines still surface those dead URLs; do not reuse them.
- `doe.gov.ph/sitemap.xml` does not exist as XML (returns the app) `[V]`. Use the `/sitemap` page or the footer nav (verified links: Data & Price Watch, Programs & Projects, Bureaus, Transparency).

### 2.2 Electricity rates / price monitor — the key asset

- Page: <https://doe.gov.ph/data-and-prices/electricity> `[V]` — title "Electricity Rates & Power Market Monitor | DOE"; page metadata shows **content updated 2026-07-27**; description: "Monthly DU electricity rates by customer class, including generation charges, with comparative domestic and international rates."
- Under the hood the page **embeds Google Sheets/Google Slides**, i.e. the real dataset is:
  `https://docs.google.com/spreadsheets/d/1oGc1iGpacELS6tkHjesvAeKZo8v2iv4UkYFY04e0p-I/edit` `[V]`
  Four tabs (verified by exporting each `gid` as CSV, all HTTP 200):
  - Residential rates — gid `0`
  - Commercial rates — gid `441532959`
  - Industrial rates — gid `1244383053`
  - **Blended generation charge per DU** — gid `714337242`
  CSV export pattern that works without login: `…/export?format=csv&gid=<gid>` `[V]` (Content-Disposition filename e.g. `RatesperCostumerClassPerDUPerRegion-ResidentialRatesperDUPerRegion.csv`).
- **Schema (verified from CSV):** columns `DU Name | GRID (ONGRID/OFFGRID) | Region | Island | DU Type (PIOU/EC) | Jan-18 … Dec-26 | SOURCES`. 114 columns = 5 metadata + **108 monthly columns (Jan-18 → Dec-26)** + `SOURCES`.
- **Coverage (verified counts):** 141 DU rows per tab (21 PIOU, 120 EC); region labels include `Region 1–13`, `NCR`, `BARMM`, `CAR`, `Region 4A/4B`; island field `Luzon/Visayas/Mindanao`; 21 rows flagged `OFFGRID`. Union across tabs = **142 unique names** (only inconsistency: `DANECO/NORDECO` vs `DANECO`).
- **Data quality:** missing values coded `NDA` (No Data Available), not blank. June 2026 column: 127 numeric out of 141 rows. Metrics computed from the sheet: **Meralco 14.48; SOLECO 16.57 (May-26 12.53, +32.2%); BISELCO 24.92; min 5.43; max 24.92; mean 12.29; median 12.10** `[V]`.
- **Cadence:** monthly in intent; the sheet covers through Dec 2026 with future months pre-labelled (i.e. a fixed annual template, values filled monthly). The page-level "updated 2026-07-27" is the only machine-visible date; the sheet itself exposes no version. Treat updates as ad hoc.
- **Risk:** embedded Google Sheet is an undocumented dependency (could be swapped, made private, or replaced by a CMS). Snapshot every retrieval (CSV bytes + sha256 + date).

### 2.3 Other DOE assets verified

| Asset | URL / location | Format | Cadence | Machine-readable? | Quirks |
|---|---|---|---|---|---|
| List of Existing Power Plants (Grid Connected) | <https://doe.gov.ph/electric-power-industry-projects/list-of-existing-power-plants-grid-connected> `[V]` | Page + 5 CloudFront PDFs ("DOE-EPIMB LoEPP as of August 2026" Luzon/Visayas/Mindanao/Summary per Region/Summary; tested one = 467 KB `application/pdf` `[V]`) | Ad hoc, "as of" month in filename | PDF only; layout tables | PDFs hosted on `d24qbtp4vooyzi.cloudfront.net/api/media/file/…?prefix=dev%2Fmedia` (note the **dev prefix** in a production URL) |
| Renewable Energy (contracts/pipeline lists) | <https://doe.gov.ph/renewable-energy-projects> `[V]` | Page + CloudFront PDFs: HSC applications summary; RE plants with COE to ERC for FIT eligibility; FIT Monitoring Board summary; COA hydro; geothermal GSC applications; wind applications (as of 30 Jun 2026 / 31 May 2026) `[V]` (tested one = 429 KB PDF) | "as of" dates, irregular | PDF only | Not the "RE dashboard" the deck implies — it is a document list, no filters/API |
| Microgrid & PVM Database Mapping | <https://doe.gov.ph/data/microgrid-mapping> `[V]`; sub-pages `/mgsp`, `/pvm`, `/proponent` `[V]` (titles verified: "MGSP Dashboard", "PVM Dashboard", "Proponent Dashboard") | Interactive dashboards (JS) | Programme updates | No download/API found; contact `mgsp@doe.gov.ph` (from page) | Note: deck says "microgrid map live on doe.gov.ph/data" — **`/data` 404s**; correct path is `/data/microgrid-mapping` (§12.1) |
| Oil price monitoring | <https://doe.gov.ph/data-and-prices/liquid-fuels> `[V]`, Oil Monitor sub-page `/data-and-prices/liquid-fuels/oil-monitor` `[V]` | Weekly PDFs ("Oil Monitor 03 November.pdf", "Oil Monitor As of 08 September 2026.pdf" …), download via `/api/media/download?url=<encoded CloudFront URL>` | Weekly + as-of posts | PDF only | Filenames inconsistent ("As of", dates, typos, `-1` suffixes); CloudFront `dev` prefix |
| LPG / auto-LPG monitoring | <https://doe.gov.ph/data-and-prices/lpg-monitor> `[V]`; discount stations `/data-and-prices/discount-stations` `[V nav]`; retail outlets `/data-and-prices/retail-outlets` `[V nav]` | Page + docs | Periodic | Mixed | Same CMS/CloudFront pattern |
| Fuel subsidy participating stations | e.g. `/fuel-subsidy-program-participating-stations-as-of-17-august-2026` `[V nav]` (also Jun 15, Jul 20 versions on ticker) | Pages per snapshot | Per snapshot | Not verified as data | Versioned only via URL slug |
| Transparency page | <https://doe.gov.ph/transparency> `[V]` | Page (agency mandate, financial, DBM-approved budgets) | Annual-ish | No | No Philippine Energy Plan / energy statistics links found here (§12.2) |
| Philippine Energy Plan, energy statistics, DU master list page | `/philippine-energy-plan`, `/energy-statistics`, `/electric-power/list-distribution-utilities` etc. | — | — | — | **404 on the new portal** `[V]`; legacy site dead `[X]`. Treat as "not publicly available in data form right now" and ask DOE via focal person / FOI |

### 2.4 DOE data-access summary

- Strengths: rates + generation charge are genuinely open and machine-readable (best single find); plant and RE lists are downloadable PDFs; DOE has moved first on publishing.
- Gaps: no API, no dataset metadata/licence, no stable document URLs, no release calendar; old portal removed with no redirect discipline; "dashboards" are UI shells over unpublished data.
- Ask for DOE focal person on day 1: (a) official Excel/CSV exports of LoEPP and RE lists; (b) microgrid dataset export; (c) written confirmation of licence and update cadence; (d) the shape of the "~45 internal systems" consolidation and whether read-only APIs exist.

---

## 3. ERC rate monitoring and the 142 DU/ECs — how rates actually reach the public

### 3.1 ERC website access (verified blocked)

All automated requests to ERC fail with a Cloudflare challenge (`HTTP 403`, body "Just a moment..."): root `https://www.erc.gov.ph/` `[X]`, `http://www.erc.gov.ph/` `[X]`, press pages `https://www.erc.gov.ph/Press-Singular/83107` and `/83102` `[X]`, document renderer `https://www.erc.gov.ph/Files/Render/issuance/45157` `[X]`, and legacy `/pdf/ub_BOHECO%202%20.pdf` `[X]` (all 403 on 2026-11-10). Search indexes show ERC issuance/render URLs but I could not retrieve a single ERC document. **Conclusion: ERC content is readable by humans in a browser but effectively closed to automated collection; any ERC-dependent pipeline must go through ERC/FOI, not scraping.**

### 3.2 Where rate numbers are actually published (verified samples)

| Publisher | Sample (verified) | Format | Extraction difficulty |
|---|---|---|---|
| Meralco | <https://www.meralco.com.ph/residential/rates-and-charges> `[V]` — server HTML with monthly panels `data-rate-month="2026-10"` … `"2026-01"`, each with a month PDF and "Typical Consumption Level" link; archive at <https://www.meralco.com.ph/governance/regulatory/rates-archive> `[V]` (1.2 MB page) | Web tables + monthly PDFs | Medium — static HTML panels + PDFs; no JSON found; JS only toggles panels |
| Electric cooperative (sample) | <https://www.surneco.com.ph/pdf/billingrates_jun2026.pdf> `[V]` — SURNECO "BILLING RATES", June 2026, 3 pages, 241 KB, **fully text-extractable** | PDF (text) | Easy–Medium per coop; layout varies by coop |
| Consolidated (DOE) | DOE Google Sheet, 142 entities, monthly | CSV via Google export `[V]` | Easy — already tabular |
| NEA-hosted EC filings | EC Power Supply Procurement Plans and Annual Reports under `nea.gov.ph/ao39/…` and `nea.gov.ph/wp-content/uploads/…` — indexed publicly but **403 to automated fetch** `[X]` | PDFs | Hard/blocked |
| EC Facebook posts | Widely used by coops (rate advisories). Not verified here: Facebook blocks logged-out automated access; no post was retrievable `[U]` | Social post images/text | Hard — no API, unstable, image-only often; treat as last-resort evidence |
| ERC per-case documents | `erc.gov.ph/Files/Render/issuance/{id}` pattern (indexed) | PDF/HTML | Blocked `[X]` |

### 3.3 Typical rate-table structure and units (verified from SURNECO June 2026 PDF)

SURNECO's table is a good representative of the EC format. Line items observed `[V]`:

- **GENERATION & TRANSMISSION:** Generation – System Charge (Php/kWh), OU Recovery / Generation MAGPP (Php/kWh), PARR (Php/kWh, can be negative), Transmission – System Charge (Php/kWh), Transmission – Demand Charge (Php/kW), System Loss Charge (Php/kWh).
- **DISTRIBUTION (coop):** Distribution – System Charge (Php/kWh), Distribution – Demand Charge (Php/kW), Supply – System Charge (Php/kWh), Supply – Ret. Cust. Charge (Cust/mo), Metering – System Charge (Php/kWh), Metering – Ret. Cust. Charge (meter/mo), plus a fixed Php/kWh line (Reinvestment Fund for Sustainable CAPEX).
- **SUBSIDIES:** Lifeline Subsidy Rate (Php/kWh), Senior Citizen Subsidy Rate (Php/kWh).
- **GOVERNMENT / UNIVERSAL CHARGES:** ME NPC-SPUG, ME RED, Environmental Charges, NPC Stranded Contract Cost / Stranded Debts, FIT-ALL (Renewable), GEA-ALL (Renewable), REC Recovery — all Php/kWh.
- **VAT:** broken out per component (Generation, System Loss, Distribution, Sale for Resale) with Php/kWh + fixed Php/month lines; totals in Php/kWh and Php/month.
- Customer classes differ by coop/site: Residential / Low Voltage / Higher Voltage (SURNECO), plus special sheets for "SALE FOR RESALE" in island systems (e.g. Nonoc Islands) with a different generation source (NPC-SPUG & DIELCO).

Implication: a national price table cannot assume a fixed column set. Design a **component dictionary** (code, label variants, unit type, customer-class scope, taxable flag) and parse into long format; keep the utility's own total as a cross-check.

### 3.4 The "142 utilities" number — corroboration and caveats

- DOE sheet: 141 entity rows per tab (21 PIOU + 120 EC), 142 unique names across tabs (DANECO vs DANECO/NORDECO) `[V]`. This is strong corroboration of the challenge's "142 utilities".
- Caveats to carry into the proposal: the sheet mixes grid-connected and off-grid ECs (21 `OFFGRID`), includes PIOUs that are subsidiaries within one corporate group, and has at least one known naming split. ERC's own count may differ (e.g., by counting subsidiaries/LGU-owned utilities); ERC count cannot be verified because ERC is blocked `[X]`. **Do not claim "exactly 142" as an ERC fact; claim "142 distinct DU/EC names in DOE's own public rate workbook."**

### 3.5 The deck's "stretch" ERC generation-charge parse is partly redundant

Deck slide 40 proposes as a stretch "parse ERC monthly generation-charge PDFs". DOE already publishes a **Blended Generation Charge per DU per Region** monthly tab (2018–2026) `[V]`. Recommendation: v1 should ingest DOE's blended generation charge first (cheap, complete), use EC PDFs to validate component detail, and treat ERC-only parsing as an optional ERC-partnership workstream (blocked for scraping anyway).

---

## 4. NEA — electric cooperatives

- Site `https://www.nea.gov.ph/` `[X]` and `https://nea.gov.ph/` → **403 Cloudflare** for HTML; direct PDF fetches also 403: NEA 2024 Annual Report PDF (`/wp-content/uploads/2025/09/NEA-2024-Annual-Report_compressed-3.pdf`) `[X]`, NEA 2023 Annual Report (`/ao39/phocadownload/Annual_Reports/…`) `[X]`, 1st Quarter 2025 EC Compliance Report (`/ao39/phocadownload/ECs%20Classification/2025/…`) `[X]`.
- What exists (from search-index evidence, not retrievable here `[P]`): NEA Annual Reports with EC-level tables; EC classification/compliance reports with **SAIFI/SAIDI/feeder-loss** and status columns; EC Power Supply Procurement Plans (PSPP) per coop per year (`/ao39/…/CSP_PSPP/{year}/{COOP} PSPP {year}.pdf`); a region→province→city/municipality→barangay table linking ECs to areas (appears in NEA 2024 Annual Report, p.68 per index).
- **Assessment:** NEA is the authoritative source for EC identity, franchise area and performance (reliability) data, but it is **not openly accessible to machines**. Options: (a) NEA letter/FOI; (b) ask DOE focal person to broker; (c) retire risk by seeding the EC list from DOE's sheet + coop websites, and sourcing reliability data from coalition/crowd later.
- Note for the master list: NEA's EC→municipality mapping is exactly the missing geography crosswalk; requesting that table by FOI is a high-value, low-effort ask.

---

## 5. WESM / IEMOP — market data

- Portal `https://www.iemop.ph/` `[V]`. Market data hub `https://www.iemop.ph/the-market/market-data/` `[V]` lists **40+ per-dataset pages**, e.g.:
  - `https://www.iemop.ph/market-data/load-weighted-average-prices-final/` `[V]`
  - `https://www.iemop.ph/market-data/prices-used-in-settlement/` `[V nav]`
  - `https://www.iemop.ph/market-data/registered-capacity-generation/` `[V nav]`
  - `https://www.iemop.ph/market-data/rtd-market-clearing-price/` `[V nav]`
  - plus DAP/HAP/RTD prices and schedules, reserve prices, congestion, outage schedules, MOT files, must-run lists, generator weighted average price, etc.
- Monthly **WESM DU Rates** reports: page `https://www.iemop.ph/market-reports/2026-wesm-du-rates/` `[V]` ("MONTHLY WESM DU RATES"); "WESM Rates" section `https://www.iemop.ph/the-market-3/wesm-rates/` `[V]`.
- **Access reality:** dataset pages are client-side JS apps; the underlying file endpoints were not discoverable from the HTML (no direct PDF/xlsx links in page source `[V]`). The site's "Classic Site" link points to a bare-IP legacy host `http://180.232.125.111/` that is **dead** `[X]`. WordPress REST exists but only `post`/`page` types — no media/file API `[V]`. No public documented API found `[U]`.
- `robots.txt`: `User-agent: * ; Disallow: /wp-content/plugins/ ; Disallow: /wp-admin/` `[V]` — crawling otherwise permitted.
- **Recommendation:** IEMOP data is *market* data (clearing prices, trading amounts), useful for a "why did the generation charge move" narrative but not a substitute for retail rates. Get bulk via IEMOP cooperation (they already publish monthly DU rates reports — ask for the data behind them and for API/bulk access); otherwise skip from v1 scope. Cost will rise if attempted by scraping.

---

## 6. NGCP / transmission and grid data

- `https://www.ngcp.ph/` → **403 Cloudflare** `[X]` for HTML pages.
- **However, static PDFs under `/Attachment-Uploads/` are directly fetchable** `[V]`: e.g. TDP 2025–2050 report (`https://www.ngcp.ph/Attachment-Uploads/TDP%202025-2050%20REPORT-2025-03-11-10-38-56.pdf`, 5.4 MB `application/pdf`) and TDP 2020–2040 consultation draft volume 1 (9.1 MB, also 200 via `ngcp.ph` and `www.ngcp.ph`) `[V]`.
- Verified content: Transmission Development Plan (TDP) documents with transmission projects and capacity tables; they are the closest thing to public "priority projects" data for the grid.
- Not verified: a public daily supply-demand/reliability dataset or API. The deck's claim that NGCP publishes "daily supply & demand" could not be confirmed from this environment (`[U]`). Treat as partner ask: request machine-readable daily operations data, or cite NGCP advisories by URL once a public page is identified (HTML is bot-blocked).
- Scraping posture: site deliberately blocks bots (Cloudflare) but assets are open; use document URLs (stable-ish, dated filenames) and never hammer the HTML.

---

## 7. PSA, data.gov.ph, FOI and PSGC geography

### 7.1 PSA

- `https://psa.gov.ph/` and `https://psa.gov.ph/classification/psgc` both return **403 Cloudflare "Just a moment…"** `[X]`. `https://openstat.psa.gov.ph/` also 403 `[X]` (OpenSTAT is the main PSA statistics warehouse and the source of many datasets that data.gov.ph points to).
- `psa.gov.ph/robots.txt` is a **Cloudflare content-signals** block (not a classic robots file), including opt-out signals for AI/collection use `[V]`. Treat PSA content as restricted-by-policy and bot-blocked.
- **PSGC (PSGC = Philippine Standard Geographic Code; region/province/city/municipality/barangay codes and names):** the canonical dataset exists and is the right join key for COMPASS/geography, but there is **no verified public machine-readable download reachable from this environment**. Options: FOI request to PSA, PSA data-sharing via fellowship partner, or a licensed copy from an existing partner (DBM/PSA). Community mirrors exist but are not authoritative — label any mirror as such and flag code vintage (PSGC is revised; codes for newly created cities/barangays change).
- **Join strategy for utilities:** PSGC codes are not in any public utility list. Build the crosswalk from: NEA EC→municipality table (FOI), ERC franchise descriptions (FOI), coalition knowledge, and PIOU service areas from corporate sites. Publish `utility_id → PSGC[]` with `confidence` and `source`, and mark unverified cities as `pending`.

### 7.2 data.gov.ph

- `https://data.gov.ph/` `[V]` — Angular SPA ("Open Data Philippines"). It is now a **catalogue/meta-portal** linking to other systems found in its JS bundle: `openstat.psa.gov.ph`, `econdb.pids.gov.ph`, `fdpp.dilg.gov.ph`, `pheiti.dof.gov.ph/edge/`, `bsp.gov.ph/PXWeb2007/…`, `philgeps.gov.ph` open data, `foi.gov.ph` `[V from bundle strings]`.
- Backend API host exists: `https://api.data.gov.ph/` returns an Express landing page `[V]`; guessed endpoints (`/api/`, `/datasets`, `/health`) return Express 404 `[X]` — **the catalogue API is undocumented**. The Angular bundle embeds an API key and environment name (do not reproduce the value here; noted as a security/coordination point for DICT/DBM). No legacy CKAN API: `/api/3/action/package_search` returns the SPA HTML `[X]`.
- Energy datasets on data.gov.ph: **could not enumerate** without browser execution (`[U]`). Ask DICT/DBM COMPASS team for the catalogue API or an export; do not assume energy datasets exist there.

### 7.3 FOI (eFOI)

- `https://www.foi.gov.ph/` and `https://www.foi.gov.ph/agencies/doe/` → **403 Cloudflare** `[X]`. DOE's footer links to that DOE agency page, so the route is official; it just cannot be automated.
- Practical implication: FOI is a **manual, time-boxed channel** (request → agency response). For a 3-month fellowship, file FOI/partner requests in week 1 for: NEA EC list+performance, ERC per-DU approved rates, PSA PSGC file, DOE non-published statistics, NGCP operational data.

---

## 8. ASEAN Energy Statistics / ACE — comparability requirements

### 8.1 What ACE publishes (verified)

- Portal `https://www.aseanenergy.org/` `[V]` (robots: allow all `[V]`).
- **ASEAN Energy Database System (AEDS)** project page: `https://www.aseanenergy.org/projects/aeds` `[V]`. The leaflet footer points to `aseanenergy.org/aeds`, which **404s** `[X]` — no public AEDS web query UI was verified.
- **ASEAN Energy Statistics Leaflet (AESL) 2025** publication page + PDF: <https://www.aseanenergy.org/publications/asean-energy-statistics-leaflet-2025/> `[V]`; PDF `https://storage.googleapis.com/aceweb-bucket-261225/files/publication/1766846350_ASEAN-Energy-Statistics-Leaflet-AESL-2025_Report.pdf` `[V]` (55 MB, 36 pages, **text-extractable**). Footer on every page: "The latest historical data is 2023, data updated as of July 2025 | aseanenergy.org/aeds. ACE. All rights reserved." `[V]`
- AESL 2026 and ASEAN Energy Statistical Yearbook (AESY) 2026 launch/consultation article: <https://aseanenergy.org/index.php/articles/3rd-consultation-workshop-of-the-asean-energy-database-system-aeds-and-the-launching-of-asean-energy-statistical-leaflet-aesl-2026-and-asean-energy-statistical-yearbook-aesy-2026> `[V]` (title verified; body truncated by fetch).
- Latest regional outlook: 9th ASEAN Energy Outlook, Oct 2026 `[V nav]`.

### 8.2 AESL 2025 structure (verified by text extraction from the PDF)

Sections and indicators observed `[V]`:

1. **Socio-Economic:** population, GDP (2005 PPP), GDP per capita, energy intensity / electricity intensity ratios, electrification rate (% population), clean-cooking access.
2. **Demand and Supply:** **TFEC (Total Final Energy Consumption)** by fuel (fossil, bioenergy, electricity), by sector (industry, transport, residential, commercial), in **Mtoe**; TPES (Total Primary Energy Supply) by fuel, fossil share (~83.5%), renewables share.
3. **Electricity:** installed capacity by fuel (**GW**, coal 113.1 GW, gas 98.6 GW in 2023), capacity additions (GW), generation, electricity consumption, electricity demand per capita **kWh/person**.
4. **Fossil Fuels:** reserves/production/trade; **Gender on Energy**; **Energy Investment**. Time series 2005–2023, annual, AMS + ASEAN totals.

### 8.3 What "aligned with ASEAN Energy Statistics" should mean for the fellowship

- **Do:** publish national annual aggregates (TPES, TFEC, capacity, generation, consumption per capita, RE share) using **AES indicator definitions, units (ktoe/Mtoe, MW/GW, GWh, kWh/person, %) and 2005→2023 back-series** where available; include a machine-readable **mapping table** (PH source field → AES indicator code → unit conversion factor → vintage). This is cheap and defensible: DOE is the Philippine AES/AEDS focal-point contributor, so alignment is a schema exercise, not new data collection.
- **Don't:** pretend retail DU tariffs are an AES indicator. AESL/AES cover **national aggregate energy statistics**, not utility retail prices. The 142-utility price table is a PH-specific layer; keep it in its own schema with its own units (PHP/kWh, PHP/kW, PHP/month) and map the national aggregates separately. State this explicitly in the proposal — it shows comparability discipline.
- **Licence watch:** AESL PDF says "ACE. All rights reserved." `[V]`. Aligning schemas is fine; **redistributing AES tables requires permission**. Data sourced from DOE/PSA can be republished under their terms; AES-derived series should be linked/attributed, not bulk-copied.

---

## 9. Cross-cutting: licensing, scraping, extraction risk, provenance

### 9.1 Licence / terms status (verified statements only)

| Source | Statement found | Implication |
|---|---|---|
| DOE portal | Footer: "All content is in the public domain unless otherwise stated." `[V]` | Usable; but no dataset-level licence/citation requirement — ask DOE to confirm in writing |
| ACE / AESL | "ACE. All rights reserved." on every PDF page `[V]` | Do not republish AES tables; align to schema only |
| IEMOP | Legal & privacy notice page exists `[V nav]`; terms not inspected | Ask before bulk reuse |
| NGCP | No terms page verified (HTML blocked) `[U]` | Ask; keep PDF citations |
| Meralco | No explicit reuse licence found on rates page `[V]` | Cite + link; prefer DOE consolidated figure for republication |
| PSA | Cloudflare content-signals / collection restrictions `[V]` | FOI/partner route only |
| Presyo PH (ICSC) | No licence found in app/JS `[U]` | Collaborate with ICSC; credit; do not clone silently |
| data.gov.ph | Terms not verified (SPA) `[U]` | Ask DICT |

### 9.2 robots.txt / scraping legality (as verified 2026-11-10)

- `iemop.ph`: classic robots, only plugins/admin disallowed `[V]`.
- `aseanenergy.org`: allow all `[V]`.
- `psa.gov.ph`: Cloudflare content-signal policy block (not a normal robots file) `[V]`.
- `doe.gov.ph`, `data.gov.ph`, `presyo.icsc.ngo`: `/robots.txt` returns the SPA shell (no robots policy exists) `[V]` — absence of a prohibition is **not** permission.
- Legal frame to state in the proposal: RA 10173 (Data Privacy Act — avoid personal data; utility rate tables are not personal data, but staff names/emails and consumer complaint posts can be), RA 8293 (IP Code; government works generally not protected, but agency terms/agency logos are), EPIRA/ERC confidentiality rules for market data, and website ToS. Practical policy: prefer official data/share agreements; use FOI for locked sources; scrape only public, non-personal, published-for-consumers content; identify the bot with a contact UA; cache politely; obey 429/403; publish retrieval metadata.

### 9.3 PDF extraction risks (observed)

- **Text vs scan split:** SURNECO billing PDF is text `[V]`; AESL 2025 is 55 MB and image-heavy (rendered charts) `[V]`; DOE LoEPP/RE PDFs may be text-based but were not extraction-tested — assume a mixed corpus and build an OCR fallback (flag OCR'd rows with lower confidence).
- **Layout variance:** each coop and each month can shift columns/wording (`NPC Stranded Debts` vs `NPC Stranded Contract Cost`); units mix PHP/kWh with PHP/kW and fixed PHP/month; some lines are negative (PARR).
- **Naming chaos:** "Oil Monitor 03 November.pdf", "Oil Monitor As of 08 September 2026.pdf", "…-1.pdf"; LoEPP has `DOE-EPIMB LoEPP as of August 2026 …`; URLs contain spaces/percent-encoding, ampersands, uppercase. Build a link registry + date parser + human review queue; never hardcode a single filename.
- **Embedded "dev" media prefix** (`?prefix=dev%2Fmedia`) in production CloudFront URLs is fragile; store both page URL and resolved asset URL.

### 9.4 Provenance / versioning requirements (must-have for COMPASS integration)

For every ingested row/asset store: `source_url`, `source_page`, `retrieved_at` (UTC + Asia/Manila), `http_status`, `content_type`, `sha256`, `parser_version`, `source_doc_date` (from filename if no date inside), `vintage` (sheet snapshot date), `confidence` (`verified`/`parsed`/`ocr`/`inferred`), `notes` (e.g. NDA replaced with null, rename applied). Publish the same metadata as an API response envelope and in a `datasets.json` manifest with a release calendar. This is what makes the output usable by DBM COMPASS rather than another dashboard.

---

## 10. Source-by-source feasibility (for a 3-month build)

Rating = effort for a 3-month fellowship: **E** easy, **M** medium, **H** hard. Approach: **B** build/ingest, **C** collaborate/partner, **F** FOI/formal request, **A** avoid for v1.

| # | Source | What you get | Rating | Approach | Notes |
|---|---|---|---|---|---|
| 1 | DOE price sheet (Google Sheet, 4 tabs) | 142 DU/EC × 108 months × 4 measures | **E** | B | CSV export; snapshot + normalize; the v1 core |
| 2 | DOE LoEPP PDFs (Aug 2026) | plant-level list by grid + region summaries | M | B + C | table PDF extraction; ask DOE for Excel |
| 3 | DOE RE lists PDFs (Jun 2026) | HSC, FIT-eligible plants, FIT board summary, COA hydro, geothermal/wind applications | M | B + C | same pipeline; no dashboard/API |
| 4 | DOE microgrid/PVM/proponent dashboards | MGSP/PVM/CSP records | H | C (request export) | UI only; email contact on page |
| 5 | DOE Oil Monitor PDFs | weekly fuel prices | M | B | filename/date chaos; link registry needed |
| 6 | Meralco rates page + archive | monthly residential rates, components, PDFs | M | B | static HTML panels; good validation source |
| 7 | EC rate PDFs (SURNECO etc.) | component-level EC rates | M→H | B + crowd | per-utility adapters; start with ~10 largest/visible coops |
| 8 | EC Facebook advisories | rates when no PDF/site | H | A/C | login wall, image OCR, unstable; use only as last resort, with screenshot provenance |
| 9 | ERC (rates/issuances) | regulatory rate detail/generation charge | H | F/C | site 403; do not plan scraping |
| 10 | NEA (EC list, SAIFI/SAIDI, PSPP) | EC identity, reliability, procurement | H | F/C | site 403; high-value FOI (EC→municipality table) |
| 11 | IEMOP market data / monthly DU rates | WESM prices, DU rate reports | M-H | C (bulk/API) | JS apps, no public API; ask IEMOP |
| 12 | NGCP TDP PDFs | transmission projects/plans | M | B (PDF) + C | PDFs fetchable; HTML blocked |
| 13 | PSA PSGC | geography codes | H | F/C | 403; request file; partner copy |
| 14 | data.gov.ph | catalogue/cross-agency datasets | U | C | API undocumented; ask DICT/COMPASS |
| 15 | Presyo PH (ICSC) | >150 DUs consolidated + JSON API | E-M | C | collaborate/attribute; do not duplicate blindly |
| 16 | AESL/AEDS | regional comparability schema | E | B (schema only) | licence: all rights reserved → mapping not copying |

---

## 11. Recommended v1 ingest plan (Dec 2026 – Mar 2027)

### Sprint 0 (weeks 1–2): lock access + registry
1. Day 1 asks: DOE focal person (sheet confirmation + licence + export asks), coalition data analyst (validation), ICSC/Presyo PH (collaboration), DBM COMPASS (target schema/endpoint), PSA/DICT (PSGC + catalogue API), NEA/ERC FOI filings (EC list, reliability, approved rates).
2. Freeze v0 **entity registry**: scrape names/GRID/Region/Island/Type from the DOE sheet, then apply curated aliases (start with `DANECO`/`DANECO/NORDECO`), assign `utility_id` (slug + code), record source and confidence; publish CSV + minimal API.
3. Stand up ingestion scaffolding with provenance metadata and a `datasets.json` manifest (the deliverable that outlives the fellowship).

### Sprint 1 (weeks 3–6): price table v1 (the demo)
1. Ingest DOE sheet (4 tabs) → tidy long table; validate NDA→null; compute simple QC (min/max/mean per month; count reporting DUs).
2. Add Meralco page parse (monthly panels + PDFs) as an independent cross-check; log mismatches vs DOE sheet.
3. Parse 5–10 EC PDFs (start with coops with public PDFs; SURNECO is a verified example) into the component schema.
4. Ship a **price API v1**: `/utilities`, `/utilities/{id}/rates?from=&to=`, `/rates?month=&class=`, plus CSV/JSON downloads; every response carries source + retrieved_at + confidence. (The "one price table" is the API, not a new dashboard.)

### Sprint 2 (weeks 7–10): DOE dashboard feeds
1. Convert LoEPP + RE lists (PDF→JSON/CSV) with plant-level fields (name, grid, region, type/fuel, capacity MW, status, commercial operation date where present in source) and human-verified QA sample.
2. Request/land microgrid dataset export; if unavailable by week 8, publish a documented "pending/partnership" status rather than partial scrapes.
3. Build a downloadable feed + simple API for these datasets and hand the ingestion scripts to DOE for operational ownership (this is the "feeds and an API behind DOE's dashboards" deliverable, scoped honestly).

### Sprint 3 (weeks 11–13): comparability, governance, handoff
1. Publish the AES alignment mapping (PH aggregate → AES indicator/unit/vintage) and a national-aggregates JSON built from DOE/PSA figures (with citations; no AES bulk copy).
2. Publish data dictionary, provenance spec, release calendar, deprecation policy; run the coalition's "every number checked" QA loop; Demo Day package + COMPASS integration notes.

### What to hand off to DOE (sustainability)
- The registry + schema + parsers as maintained pipelines (not one-off notebooks); the release calendar/disclosure order (coalition's rule-reform ask) mapped to actual datasets; dataset-level licence and citation lines; ownership of the Google-Sheet dependency (ideally replaced by a documented DOE dataset endpoint or git-backed export).

### What to crowd-source
- EC rate PDFs/posts via coalition members and student volunteers (with a submission form + provenance fields); geography crosswalk verification (province/city served); alias/discrepancy reports; monthly "reporting DUs" count watch (who went NDA).

---

## 12. Discrepancies found between live sources and the challenge page / deck

1. **`doe.gov.ph/data` does not exist** — it returns a client-side "Page Not Found" (HTTP 200). The microgrid map is at `https://doe.gov.ph/data/microgrid-mapping` (with `/mgsp`, `/pvm`, `/proponent` sub-dashboards) `[V]`. Deck slide 39's "microgrid map live on doe.gov.ph/data" should be re-worded.
2. **"Public dashboards on RE pipeline, grid supply and reliability, priority projects"** — only partially verified. RE pipeline exists as **PDF lists** (`/renewable-energy-projects`); grid/plant data as **PDF lists** (`/electric-power-industry-projects/list-of-existing-power-plants-grid-connected`); microgrid as UI dashboards. No verified dashboard/feed was found for "grid supply and reliability" or "priority projects" on doe.gov.ph `[U]`. The proposal should ask DOE what those dashboards are (URL/owner/data) or scope them out.
3. **₱12.43/kWh June 2026 national average** — from DOE's own public June 2026 residential column, the simple mean of 127 reporting DUs is **12.29**, median **12.10** (min 5.43, max 24.92) `[V]`. Individual deck figures do reproduce exactly: Meralco **14.48**, SOLECO **16.57** (+32.2% vs May-26 12.53), BISELCO/Busuanga **24.92** `[V]`. So 12.43 is plausibly a weighted or differently-scoped average — **needs DOE/coalition confirmation before being cited as reproducible**; footnote the methodology if used.
4. **Presyo PH URL**: the live app is `https://presyo.icsc.ngo/` `[V]`; `presyo.ph` does not resolve `[X]`. Also, the ">150 DUs/ECs" claim is from the launch article (2026-04-28) `[V]`, not from the app UI (which I could not fully exercise).
5. **"142 utilities publish rates as PDFs, web tables, and posts"** — the count is corroborated by DOE's workbook (142 unique names) `[V]`, but the *publication formats* are dominated in practice by (a) DOE's consolidated sheet, (b) PIOU websites (Meralco verified), (c) EC PDFs (sample verified) and (d) Facebook posts (unverified). The proposal should say "DOE consolidates 142; formats vary" rather than implying all 142 maintain web pages.
6. **ERC monthly generation-charge PDFs** (deck stretch goal) are largely redundant with DOE's public "Blended Generation Charge per DU per Region" tab (2018–2026) `[V]`; and ERC is bot-blocked `[X]`, so re-plan this as an ERC partnership item.
7. **AEDS public access**: the leaflet advertises `aseanenergy.org/aeds`, which 404s; no public AEDS query interface verified. Use AESL PDFs + AESY when available, plus DOE as the PH focal point.
8. **Legacy DOE URLs** still rank in search results (`legacy.doe.gov.ph/...`, old plant-list paths) but the host is dead `[X]` — any proposal citing them will look stale.
9. **The workbook now extends to October 2026** (re-fetched 2026-11-10 for the build): 107 header month columns (Jan-18 → Nov-26), 106 with published data. June 2026 remains the pitch's anchor month, but coverage moves: 127 residential DUs reported in June 2026 vs **113 in October 2026** (27 NDA, 1 invalid cell — the residential tab has the text `Jan-16` in one Oct-26 cell). Any dashboard must show the reporting count alongside the month.
10. **The four tabs disagree in five places.** ILECO II and ILECO III are `ONGRID` in the residential/generation tabs and `OFFGRID` in the commercial/industrial tabs (2–2 → published as `CONFLICT`, not guessed); CLPC is BARMM in three tabs and Region 12 in the industrial tab (majority BARMM); that industrial row also has the island field set to `BARMM`; and `DANECO/NORDECO` is labelled `DANECO` in the generation tab (hence 142 distinct names across the four tabs — the pitch's "142 utilities" checks out). These are logged in `data/seed/validation.json` and surfaced on the page.

---

## 13. Verification log (all accessed 2026-11-10)

**Verified live (HTTP 200, content inspected):** `https://fellowship.bettergov.ph/`; `https://doe.gov.ph/`; `https://doe.gov.ph/data-and-prices/electricity`; Google Sheet `1oGc1iGpacELS6tkHjesvAeKZo8v2iv4UkYFY04e0p-I` + CSV exports gid 0/441532959/1244383053/714337242; `https://doe.gov.ph/electric-power-industry-projects/list-of-existing-power-plants-grid-connected` (+ 1 CloudFront LoEPP PDF); `https://doe.gov.ph/renewable-energy-projects` (+ 1 CloudFront RE PDF); `https://doe.gov.ph/data/microgrid-mapping`, `/mgsp`, `/pvm`, `/proponent`; `/data-and-prices/liquid-fuels`, `/liquid-fuels/oil-monitor`, `/data-and-prices/lpg-monitor`, `/data-and-prices/retail-outlets`, `/data-and-prices/discount-stations`; `https://doe.gov.ph/transparency`; `https://www.iemop.ph/`, `/the-market/market-data/`, `/market-data/load-weighted-average-prices-final/`, `/market-reports/2026-wesm-du-rates/`, `/the-market-3/wesm-rates/`, `/wp-json/wp/v2/types`; `https://www.meralco.com.ph/residential/rates-and-charges`, `https://www.meralco.com.ph/governance/regulatory/rates-archive`; `https://www.surneco.com.ph/pdf/billingrates_jun2026.pdf`; `https://presyo.icsc.ngo/` and `https://presyo.icsc.ngo/api/national_trend_normalized?normalization=percent`; `https://powerphilippines.com/icsc-launches-presyo-ph-web-app-to-help-consumers-understand-power-costs/`; NGCP TDP 2025–2050 PDF and TDP 2020–2040 PDF (`ngcp.ph/Attachment-Uploads/…`); `https://www.aseanenergy.org/`, `/projects/aeds`, `/knowledge-hub`, `/publications/asean-energy-statistics-leaflet-2025/`, AESL 2025 PDF, AESL/AESY 2026 article; `https://compass.dbm.gov.ph/`; `https://data.gov.ph/`; `https://api.data.gov.ph/`; robots.txt for `iemop.ph`, `aseanenergy.org`; source PDF text extraction for SURNECO and AESL; counts/metrics computed from the DOE CSV.

**Blocked / failed (all HTTP 403 Cloudflare unless noted):** `https://www.erc.gov.ph/`, `http://www.erc.gov.ph/`, `https://www.erc.gov.ph/Press-Singular/83107`, `/83102`, `/Files/Render/issuance/45157`, `http://www.erc.gov.ph/pdf/ub_BOHECO%202%20.pdf`; `https://www.nea.gov.ph/`, NEA 2024 Annual Report PDF, NEA 2023 Annual Report PDF, NEA Q1-2025 EC Compliance Report PDF; `https://www.ngcp.ph/` (HTML); `https://psa.gov.ph/`, `https://psa.gov.ph/classification/psgc`, `https://openstat.psa.gov.ph/`; `https://www.foi.gov.ph/`, `https://www.foi.gov.ph/agencies/doe/`; `legacy.doe.gov.ph` (dead); `http://180.232.125.111/` IEMOP classic host (dead); `https://doe.gov.ph/sitemap.xml` (not XML); `https://doe.gov.ph/data` and legacy DOE paths (client-side 404); `https://presyo.ph/` (does not resolve); `https://www.aseanenergy.org/aeds` (404); `https://data.gov.ph/api/3/action/package_search…` (SPA, not CKAN); `https://api.data.gov.ph/api|/datasets|/health` (Express 404).

**Not verified / open (do not cite as fact):** ERC rate-monitoring page existence and its publication format; NEA contents beyond indexed titles; NGCP daily supply/demand data; PSA OpenSTAT/PSGC download mechanics; data.gov.ph energy dataset inventory and its API schema; Presyo PH licence and full endpoint set; IEMOP downloadable file URLs/API; DOE's "~45 internal systems" and DOE–ERC data-sharing arrangement (deck claim only); whether DOE's Google Sheet has a named owner/refresh SLA.

---

## 13a. Implementation re-verification (2026-11-10, build)

The draft page is now generated from the workbook rather than from sample data. What was asserted on every build (`tools/ingest-doe-rates.py`, all 17 checks passing):

- 141 DU/EC rows in each of the four tabs, 107 month columns, first month Jan-2018, latest month with published data **Oct-2026**.
- **142 distinct DU/EC names** across the four tabs (the pitch's 142).
- 21 off-grid DUs (unanimous across tabs); 2 grid-status conflicts (ILECO II/III); 1 region conflict (CLPC); 1 island-label conflict; 1 name variant (`DANECO`).
- June 2026 anchors: Meralco **14.48**, SOLECO **16.57** (+32.2% vs May-26 12.53), BISELCO **24.92**; 127 reporting DUs; simple mean **12.29**; median **12.10**; max 24.92.
- Raw snapshots `data/raw/doe-rates/2026-11-10/{gid}.csv`; SHA-256 `17c746168e77…` (residential), `55c8ccc0f2b7…` (commercial), `96e8f42e28e9…` (industrial), `66002d90c2b3…` (generation); full hashes in `data/seed/validation.json`.
- Latest-month residential stats (Oct 2026): 113 reporting, 27 NDA, 1 invalid; median ₱12.72/kWh, mean ₱13.23, range ₱5.33–₱19.36.

The page was rendered in headless Chromium at 1440 px and 390 px: 18 map regions, 141 table rows, expandable monthly charts, region filtering and API preview all exercised, 0 console errors, no external requests. June 2026 anchors still reproduce, so the earlier discrepancy analysis is unchanged; the workbook's newer months are additive evidence, not a contradiction.

---

## 14. Questions to put to DOE / partners (week 1)

1. Is the public Google Sheet (`Electricity Rates & Power Market Monitor`) the canonical rate dataset, who maintains it, on what schedule, and under what licence/citation? Will DOE publish it as a documented dataset/API?
2. Which RE/grid/reliability/priority-project dashboards exist in production today (URLs, owners, data sources), and can fellows get read access/export? Are the LoEPP/RE PDFs generated from an internal table we can consume directly?
3. What is the official/authoritative DU/EC registry (system of record), and does it carry an ID we should adopt (or must we mint one)? Can DOE share the ERC/NEA crosswalk?
4. Can ERC provide per-DU approved rates/generation-charge files as data (not PDFs), or nominate a data focal person for the fellowship?
5. Can NEA provide the EC list with franchise areas (PSGC), reliability metrics, and PSPPs as a bulk file?
6. Will DBM COMPASS accept our entity/price schema, and what identifiers/geography codes must the API use (PSGC vintage)?
7. For ASE alignment: which AES indicator set/vintage does DOE report to ACE, and is there a mapping table the fellowship can reuse?
