# Open Energy Data Layer — Philippine electricity rates

An open, API-first data layer that collates who sells power in the Philippines, at what
price, and with what provenance — starting from what the Department of Energy (DOE) already
publishes, not from a fleet of scrapers.

This repository turns DOE's public **Electricity Rates & Power Market Monitor** workbook (a
public Google Sheet embedded in a page) into a usable open dataset: a canonical utility
registry, tidy monthly rate observations with a receipt behind every number, region
aggregates, **sourced service areas for every distribution utility**, a self-contained
publication page, a read-only static JSON API, a documented OpenAPI 3.1 contract, and a
generated documentation site. It is built as a production open-source project.

The product page is titled **"Philippine electricity rates"** — a national map, a comparable
price table, the API in one place, and the receipts behind every number.

| | |
|---|---|
| **Dataset version** | `2026-11-10` (DOE workbook retrieved 2026-11-10) |
| **Latest published month** | October 2026 |
| **Coverage** | 141 distribution utilities and electric cooperatives, 18 PSGC regions, 106 months with published data (Jan 2018 – Oct 2026) |
| **Status** | Pre-release (`0.x`), not yet deployed — see [Deployment status](#deployment-status) |
| **Licence** | Code, page and design: MIT. Data, brand and third-party assets: see [Licence](#licence) and [NOTICE.md](NOTICE.md) |

## What it does

DOE already consolidates monthly electricity rates for the country's distribution utilities
(DUs) and electric cooperatives (ECs), but as a wide-format Google Sheet with no stable
entity IDs, no licence statement, no provenance and no API. This project adds the missing
layer:

- **A canonical utility registry** — one row per DU/EC, with a stable `utility_code`, PSA
  PSGC geography, type (PIOU/EC), grid status, source row and provenance.
- **A tidy monthly price table** — utility × month × customer class, with `published`,
  `nda`, `missing` and `invalid` states preserved and **nothing imputed**.
- **Region aggregates** — medians/means and reporting counts behind the map, computed only
  from published values.
- **Sourced service areas** — the LGU-level franchise footprint behind every utility, so the
  map can answer "where does this provider operate, and at what price?" instead of assuming
  one utility per region. Meralco's territory comes from RA 12146 (the current franchise
  law); the rest come from franchise tables compiled from DOE records, with the DOE workbook
  region as a labelled fallback. The coverage layer is published as its own CSV with a source
  registry and licence notes.
- **A self-contained publication page** — national map, provider coverage lens, comparable
  price table, expandable histories, API preview and the method/receipts behind every number.
- **A generated documentation site** — every markdown document (README, data model, API
  guide, frontend/backend architecture, the component map, contributing, security,
  changelog, research notes and seed documentation) rendered as a styled static docs UI
  under `draft/docs/`, with a sidebar, table of contents and full-text downloads.
- **Agent maps** — an `AGENTS.md` at the repository root plus per-area maps for `tools/`,
  `data/`, `draft/` and `tests/`, so a human or a coding agent can find the source of
  truth, the build command and the contract for each component.
- **A versioned API contract and a static JSON API** — an OpenAPI 3.1 contract, plus a
  complete read-only JSON mirror generated under `draft/api/v1/` for anyone who wants to
  integrate today from a static host, with a BetterGovPH-compatible envelope and
  provenance fields.
- **A paper trail** — raw publisher bytes, per-tab SHA-256 hashes, a 17-check validation
  report and a disclosed log of where the source tabs disagree.

### Dataset at a glance

| Metric | Value |
| --- | --- |
| Distribution utilities and electric cooperatives | **141** (120 ECs, 21 PIOUs) |
| Regions | **18** PSGC regions |
| Monthly observation rows | **60,348** (141 utilities × 107 header months × 4 customer classes) |
| Months with published data | **106** — Jan 2018 → Oct 2026 (the workbook's Nov 2026 column exists but has no published values) |
| Customer classes | Residential, commercial, industrial, blended generation charge |
| Latest month reporting (residential) | **113 / 141** — 27 NDA, 1 invalid cell, median ₱12.72/kWh |
| Source-tab conflicts disclosed | **5** (grid status, region, island label, name variant) |
| Service areas | **141 / 141** utilities with LGU-level coverage; **1,648 LGU rows + 17 barangay rows**, 1,602 distinct LGUs |
| Service-area sources | RA 12146 (Meralco law), OSM Wiki franchise table (CC BY-SA 2.0), Wikipedia supplement (CC BY-SA 4.0), DOE region fallback |
| Automated ingest checks | **17 / 17 passing**, plus **7 / 7** service-area checks |
| Raw source snapshots | **4** tab CSVs with per-tab SHA-256 |

## Architecture and agent maps

Three generated guides explain how the system is put together and where to change it —
all rendered with the rest of the documentation under `draft/docs/` (21 pages: 20
documents + index):

- **[Frontend architecture](draft/frontend.md)** — the three browser-facing surfaces
  (product page, docs site, review pack), build-time data/asset injection, the runtime JS
  modules and state/deep links, accessibility, and the pinned QA contracts.
- **[Backend & pipeline architecture](draft/backend.md)** — the deterministic
  static-artifact pipeline: raw snapshots and hashes, ingest and validation, service
  areas, geometry, the static JSON API, the page/docs/preview builders, determinism and
  failure modes.
- **[Component map & agent guide](draft/component-map.md)** — where every component lives,
  what to edit versus regenerate, the build-order graph, task routing, and the
  cross-cutting invariants.

For coding agents the repository also ships `AGENTS.md` plus per-area maps —
`tools/AGENTS.md`, `data/AGENTS.md`, `draft/AGENTS.md` and `tests/AGENTS.md` — each
stating its area's source-of-truth files, commands, generated artefacts and pitfalls.

## The page

[`draft/map-table-prototype.html`](draft/map-table-prototype.html) is the product reading:
a single, self-contained HTML file in the BetterGovPH open-data design language. It is
built by `tools/build-map-page.py` and contains no external runtime dependencies — fonts,
logo, favicon, region geometry and data are inlined at build time, and the page makes **no
network requests**. It includes:

- a national map of the 18 regions, coloured by median rate per customer class, with a
  visible colour-scale legend above the map, zoom controls, keyboard-accessible region
  selection (roving tabindex, arrow keys to move, Enter to select, Escape to clear) and
  click-to-filter;
- a **national overview** beside the map: the latest month's median residential rate and
  reporting count, a proportional ranking of all 18 region medians, and the month's biggest
  movers — every row and chip clickable through to the region or utility;
- a **provider lens**: search any of the 141 utilities, see its sourced service area drawn at
  LGU level on a zoomed map, with the utility's latest published rate, its region-median
  comparison for context, and an aside listing the served provinces and LGU counts
  ("Cavite 20/23", "Metro Manila 17"); Meralco's franchise, the only multi-region utility
  whose territory is settled by law, is drawn from RA 12146 and includes its 17 Pampanga
  barangays;
- a sticky, scrollspy navigation bar, custom searchable dropdown filters (provider, region,
  grid, customer class), a copy-link action and a mobile menu — designed to stay usable at
  390 px;
- a sortable, searchable, filterable price table of all 141 utilities, with month-on-month
  deltas, NDA/invalid badges, expandable 106-month histories, a service-area line in each
  expanded row, a compare action, a source-row link behind each rate and a clear no-results
  state;
- a **comparison view**: add up to three utilities from an expanded price-table row or the
  provider panel, then compare their full 2018–2026 residential histories on one chart plus
  a latest-rate matrix; every row links to its DOE workbook source row and its public API
  file, the dialog is keyboard-accessible, becomes stacked cards on mobile, and the selection
  is deep-linkable (`?compare=MERALCO,SOLECO`);
- **shareable views**: the copy-link control in the sticky nav puts the current provider,
  region, comparison, search, type, grid, NDA toggle and sort into the URL, so any filtered
  view can be bookmarked or sent to a colleague;
- a generated **docs site** (`draft/docs/`) linked from the masthead, downloads and footer,
  so the markdown documents are readable as a UI rather than raw files;
- an **API v1.0** section with the static JSON API's conventions, datasets and units, a file
  reference, and an in-page JSON explorer for the generated payloads;
- the method, validation report, source-tab hashes and the five disclosed conflicts, plus a
  downloads-and-licence section.

Open the file directly in a browser (no server needed), or rebuild it from source with the
commands below. Reviewed data and generated payloads are documented in
[`data/seed/README.md`](data/seed/README.md).

## Deployment status

**No public deployment exists yet, and this repository contains no live URL for the project.**
The page is a single static HTML file that can be opened locally or dropped on any static
host or CDN; choosing and documenting that host (and the API's base URL) is pending. The
generated static JSON API under `draft/api/v1/` is the same kind of artefact: it can be
served from any static host, but no host is configured yet, and the proposed hostnames in
the API contract are not live services. The `preview/` review hub is a **local build
artefact** (gitignored, produced by `tools/build-preview.py`), not a deployment. Nothing
here is an official DOE or BetterGovPH publication.

When a deployment exists, this section will record the URL, the host, the deployed dataset
version and the API base URL. Until then, treat any URL that is not a source citation (DOE,
the public Google Sheet, BetterGov.ph) as not ours.

## Quickstart

Requirements: **Python 3.12** with `pip`, and network access for the first workbook fetch.

```bash
# 1. Get the source (a public remote is pending publication; clone or copy as available)
# 2. Install the build dependencies (PyYAML, markdown-it-py)
python3 -m pip install -r requirements.txt

# 3. (Optional) Rebuild the geometries from the pinned boundary release: the region
#    choropleth (geo.json) and the LGU coverage layer (coverage-geo.json)
python3 tools/build-geo.py             # network only on the first cached fetch

# 4. Assemble the service-area dataset: LGU-level franchise areas for all 141
#    utilities (OSM/Wikipedia extraction inputs under research/coverage/), the
#    RA 12146 Meralco override, and region fallbacks where nothing is sourced
python3 tools/build-service-areas.py   # -> data/seed/service_areas.csv + source registry

# 5. Ingest the DOE workbook: fetch -> snapshot raw bytes -> SHA-256 -> parse -> validate -> publish
python3 tools/ingest-doe-rates.py
#    ...or force a fresh download of all four tabs (rewrites today's snapshot):
python3 tools/ingest-doe-rates.py --refresh

# 6. Build the static JSON API mirror (read-only JSON payloads, no server)
python3 tools/build-api.py             # -> draft/api/v1/

# 7. Build the documentation site from the markdown sources
python3 tools/build-docs.py            # -> draft/docs/

# 8. Build the page (uses the ingested payload and the generated API; the provider
#    lens and API explorer degrade gracefully if their inputs are missing)
python3 tools/build-map-page.py        # -> draft/map-table-prototype.html

# 9. Optional: rebuild the local review hub (docs, API reference, downloads; gitignored)
python3 tools/build-preview.py         # -> preview/

# 10. Validate the repository offline (data contracts, service areas, page, docs,
#     OpenAPI, static API, packaging)
python3 tools/validate.py              # add --check-page for the deterministic rebuild check

# 11. Browser QA of the built page and the docs site
#     (Node.js 20+: npm ci, then npx playwright install chromium)
npm ci
node tests/qa.mjs
node tests/qa-docs.mjs
```

The ingest prints per-tab row/month/hash information, then the 17 rate checks and the seven
service-area checks, and finishes with `ALL CHECKS PASSED`; a failed check exits non-zero and
stops publication. The first run of a given day fetches the four CSV exports and snapshots
them under `data/raw/doe-rates/<date>/`; later runs reuse that snapshot, so rebuilds are
reproducible (set `OPEN_ENERGY_RETRIEVED_AT` to the recorded snapshot timestamp to reproduce
an existing build byte-for-byte). The API mirror, docs site, page and review hub are built
from the published files in `data/seed/`. The recommended rebuild order is exactly the order
above: geometry → service areas → ingest → API → docs → page → preview.

Optional extras: `research/coverage/extract.py` re-derives the raw service-area extraction
from pinned wikitext snapshots (offline, deterministic). CI runs static validation, a
deterministic page/docs rebuild check and both browser QA suites on every push/PR to `main`.

## Repository layout

| Path | What it is |
| --- | --- |
| `tools/ingest-doe-rates.py` | **Data pipeline.** Fetch → snapshot raw bytes → SHA-256 → parse → validate → publish. The 17 checks are asserted on every run; reference-anchor mismatches fail the build. |
| `tools/build-map-page.py` | **Page builder.** Inlines design assets, rate data, region geometry and the 1,642-polygon LGU coverage layer from `data/seed/` + `draft/assets/` into the single-file page. |
| `tools/build-api.py` | **Static API builder.** Generates the read-only JSON API mirror under `draft/api/v1/` from the published data; every response uses the documented envelope. |
| `tools/build-preview.py` | **Review-hub builder.** Renders the markdown docs, the API contract, a copy of the page and the data downloads into `preview/` (gitignored). |
| `tools/build-geo.py` | **Geometry builder.** Regenerates the region choropleth (`draft/assets/geo.json`) and the LGU coverage layer (`draft/assets/coverage-geo.json`) from the pinned, SHA-256-verified boundary release; deterministic and offline after the first cached fetch. |
| `tools/build-service-areas.py` | **Service-area assembler.** Merges the LGU-level franchise extraction with the RA 12146 Meralco override and DOE region fallbacks, validates every PSGC join, and publishes `data/seed/service_areas.csv` + `data/seed/service_area_sources.csv`. |
| `tools/build-docs.py` | **Docs builder.** Renders every markdown source into the styled static docs site under `draft/docs/` (sidebar, TOC, code copy, prev/next, mobile drawer); deterministic. |
| `tools/validate.py` | **Offline repository validation.** Checks data contracts, the built page, the OpenAPI document, the static API and packaging; exits non-zero on failure and can prove a deterministic page rebuild (`--check-page`). |
| `draft/map-table-prototype.html` | **Generated page.** Single self-contained file — do not edit by hand. |
| `draft/openapi.yaml` | **API contract**, OpenAPI 3.1 (API version 1.0.0); a JSON mirror is generated at `draft/api/v1/openapi.json`. |
| `draft/api-docs.md` | **API guide** (human-readable): access, datasets and units, conventions, endpoint reference, attribution, disclaimers and versioning. |
| `draft/api/v1/` | **Generated static JSON API.** Dataset metadata, health, months, latest rates, utilities (one file per utility), regions (one file per region), service areas (one file per utility), sources, changes, conflicts and the validation report — read-only JSON, no server required. |
| `draft/docs/` | **Generated documentation site** (21 pages + shared assets, deterministic): project README, data model, API guide, frontend/backend architecture, component map & agent guide, seed/asset/brand/testing docs, contributing, security, changelog and research notes — a styled UI with sidebar, TOC and raw-markdown downloads. |
| `draft/data-model.md` | Canonical entities, IDs, provenance, versioning and licensing policy. |
| `draft/frontend.md`, `draft/backend.md`, `draft/component-map.md` | **Architecture docs**: the frontend surfaces and UI contracts, the backend/pipeline design and failure modes, and the component map & agent guide. Hand-maintained; rendered as `frontend.html`, `backend.html`, `component-map.html` in the docs site. |
| `AGENTS.md`, `tools/AGENTS.md`, `data/AGENTS.md`, `draft/AGENTS.md`, `tests/AGENTS.md` | **Agent maps** for coding assistants: repository orientation/component map at the root plus per-area source-of-truth files, commands, generated artefacts, contracts and pitfalls. |
| `data/raw/doe-rates/2026-11-10/` | **Raw byte snapshots** of the four source tabs — the source of truth for every published number. Tracked; never edited. |
| `data/seed/` | **Published data**: `utilities.csv` (141), `rates_monthly.csv` (60,348), `regions.csv` (18), `sources.csv` (4), `service_areas.csv` (1,648 LGU rows + 17 barangay rows), `service_area_sources.csv` (4 source records), `validation.json` (17 rate checks + 7 coverage checks), `page-data.json` (page payload), plus a data dictionary. Generated — do not hand-edit. |
| `data/seed/plants.csv` | **Illustrative** sample plants (13 rows) for a future asset layer; not displayed and not generated by the current pipeline. |
| `draft/assets/` | Design assets: OFL fonts, BetterGov brand assets, favicon set and social card, vendored Lucide icon sprite, the region geometry and the LGU coverage geometry, with provenance (`geo-sources.json`) and contract (`README.md`). |
| `tests/qa.mjs` | **Browser QA suite.** Playwright/Chromium checks of the built page at desktop and mobile widths (map, provider coverage lens, table, filters, API explorer, CSV export, sticky nav, zero console errors/external requests). |
| `tests/qa-docs.mjs` | **Docs-site QA suite.** Crawls every generated docs page over HTTP: loads, zero third-party requests, sidebar/TOC, code copy, internal link + fragment resolution, desktop/mobile overflow, mobile drawer. |
| `research/coverage/` | Service-area extraction: deterministic script, pinned wikitext snapshots, raw operator table, methodology and known-gap report (CC BY-SA sources). |
| `package.json` | Node tooling for the QA suite (Playwright pinned; convenience scripts for QA, validation and builds). |
| `.github/workflows/ci.yml` | **CI.** On push/PR to `main`: static validation + deterministic rebuild check, then Chromium browser QA; QA screenshots are uploaded as artifacts. |
| `plan/` | Internal working notes and plans (not part of the published product). |
| `research/` | Source ledger and evidence: data landscape, API/interop landscape and API documentation conventions. |
| `preview/` | Generated local review hub (gitignored). |
| `LICENSE`, `NOTICE.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`, `requirements.txt` | Project packaging and governance. |

## Data

### Source

| | |
| --- | --- |
| Publisher | Department of Energy (DOE), Philippines |
| Source page | <https://doe.gov.ph/data-and-prices/electricity> (the *Electricity Rates & Power Market Monitor*) |
| Machine-readable source | Public Google Sheet `1oGc1iGpacELS6tkHjesvAeKZo8v2iv4UkYFY04e0p-I`, four tabs: residential, commercial, industrial, blended generation charge |
| Retrieval method | Unauthenticated CSV export of each tab (`/export?format=csv&gid=…`) — the same bytes a browser downloads |
| Retrieval date | 2026-11-10 (Asia/Manila) |
| Snapshot | `data/raw/doe-rates/2026-11-10/{0,441532959,1244383053,714337242}.csv` with SHA-256 recorded in `data/seed/sources.csv` and `data/seed/validation.json` |
| Licence | **Not confirmed** — see [NOTICE.md](NOTICE.md); the project asserts no licence over the DOE workbook or the figures extracted from it |

### Pipeline: fetch → snapshot → hash → parse → validate → publish

1. **Fetch** each customer-class tab through Google's public CSV export, with a timeout and
   a size sanity check.
2. **Snapshot** the raw bytes under a retrieval-dated directory; a same-day run reuses the
   existing snapshot (which is why rebuilds are reproducible), and `--refresh` re-fetches.
3. **Hash** each tab (SHA-256) and record it alongside the source URL, retrieval timestamp
   and licence note in `data/seed/sources.csv` and `data/seed/validation.json`.
4. **Parse** the wide month columns into tidy `utility × month × customer class`
   observations. Each cell is classified as `published`, `nda` (the publisher says no data),
   `missing` (blank) or `invalid` (unparseable text); the four tabs are resolved into one
   canonical utility row.
5. **Validate** 17 structural and anchor checks — row/month counts, naming, off-grid count,
   region totals, conflict counts, and the June-2026 figures pinned as ingest anchors —
   plus 7 service-area checks. A mismatch stops publication.
6. **Assemble service areas** separately (`tools/build-service-areas.py`): LGU-level franchise
   areas are joined to PSGC 3Q 2026, the RA 12146 Meralco territory overrides the secondary
   source, and every utility without an LGU-level area gets a labelled region fallback.
7. **Publish** the tidy CSVs, the coverage dataset, the validation report and the compact page
   payload.

### Data semantics

- **No imputation.** `published`, `nda`, `missing` and `invalid` are preserved as distinct
  states. All aggregates use published values only and are reported together with the
  reporting count.
- **Disagreements are disclosed, not smoothed.** The four source tabs disagree in five
  places: ILECO II/III grid status (2–2 split → published as `CONFLICT`), the CLPC region,
  one island label, and a `DANECO` / `DANECO/NORDECO` name variant. Each is logged in
  `data/seed/validation.json` and surfaced in the page's method section.
- **142 names, 141 rows.** The workbook has 141 DU/EC rows; across the four tabs there are
  142 distinct names because one row is spelled differently in the generation tab. That
  reconciles the headline "142 utilities" figure.
- **Latest month (October 2026).** Residential: 113 of 141 reporting, 27 NDA, 1 invalid
  cell; median ₱12.72/kWh, mean ₱13.23/kWh, range ₱5.33–₱19.36/kWh. Commercial, industrial
  and generation have larger NDA shares, so always read the reporting count with the number.

### Service areas (provider coverage)

The DOE workbook is organised by region and names each utility once, under a single region.
That is enough for a regional median, but it is not the utility's service area — most electric
cooperatives cover a handful of municipalities, and Meralco's franchise spans three regions.
The provider lens therefore uses a separate, LGU-level coverage layer:

| | |
| --- | --- |
| Published files | `data/seed/service_areas.csv` (1,648 LGU rows + 17 barangay rows) and `data/seed/service_area_sources.csv` (source registry) |
| MERALCO | **RA 12146** (approved 11 April 2025), Section 1: 108 cities/municipalities in Metro Manila, Bulacan, Rizal, plus parts of Cavite, Laguna, Quezon, Batangas, and 17 barangays in Pampanga. This law wins over the secondary sources. |
| Other utilities | LGU-level franchise areas from the OpenStreetMap Wiki "Power networks/Philippines/Operators" table (revision 2836797, 2025-04-14, CC BY-SA 2.0), compiled from DOE franchise records; a Wikipedia supplement (CC BY-SA 4.0) fills 22 utilities the OSM table lists without a franchise-area table. |
| Fallback | If no LGU-level area is sourced, the DOE workbook region is published as a single region-level area and labelled as such — the 2026 edition needed zero fallbacks. |
| Geometry | 1,642 municipality/city polygons (`draft/assets/coverage-geo.json`), simplified from the same pinned PSGC 3Q 2026 boundary release as the region map; the page inlines them. |
| Checks | 7 service-area checks on every ingest (every utility covered, MERALCO 108 LGU + 17 barangay rows, valid PSGC joins, every DOE region inside its service area or a documented PSGC reassignment). |

Three utilities (PROSIELCO, SIASELCO, SULECO) are listed under a legacy DOE region because
PSGC 3Q 2026 moved Sulu to Region IX and Siquijor to the Negros Island Region; their coverage
notes record the reassignment rather than forcing the old region. Partial coverage (an LGU
split between two utilities, or a franchise that covers only part of an LGU) is recorded in
the row's `coverage_note`. The coverage dataset is a **CC BY-SA derivative** of the OSM and
Wikipedia sources and is licensed separately from the MIT code — see [NOTICE.md](NOTICE.md).
57 of the 1,642 LGUs have no DU in the current sources; they are listed with reasons in
[`research/coverage/README.md`](research/coverage/README.md).

### Reproducibility

The pipeline is deterministic: with the same raw snapshots, a rebuild reproduces
`data/seed/*.csv` and the generated page byte-for-byte except for the retrieval timestamp
stamped by the ingest. To audit a number, start from its `source_row` in
`data/seed/utilities.csv`, then check the tab hash and raw snapshot in
`data/seed/validation.json`.

## Data model and API

- [`draft/data-model.md`](draft/data-model.md) defines the canonical entities — utility
  registry and name crosswalk, source documents and ingest runs, monthly rate observations,
  assets, indicators, change events and gated citizen submissions — with PSGC geography,
  stable `utility_code` IDs, provenance fields, publication states and versioning.
- [`draft/openapi.yaml`](draft/openapi.yaml) is the OpenAPI 3.1 contract for the public API
  (API version **1.0.0**): keyless public reads, a BetterGovPH-compatible
  `{meta, data, next_cursor}` envelope, provenance on every observation, and metadata.
- [`draft/api-docs.md`](draft/api-docs.md) is the human-readable API guide: overview, base
  URL and access, datasets and units, conventions, endpoint reference with real example
  payloads, sources and attribution, disclaimers, data files and versioning.
- [`draft/api/v1/`](draft/api/v1/) is a generated, read-only **static JSON API** built from
  the same published data by `tools/build-api.py`: dataset metadata, health, months, latest
  rates per customer class, the utility registry plus one JSON file per utility, region
  aggregates plus one file per region, **service areas plus one file per utility**, sources,
  changes, conflicts, the validation report and a JSON mirror of the contract.
- [`draft/docs/`](draft/docs/) is the generated documentation site for all of the above
  (`tools/build-docs.py`): project README, data model, API guide, seed/asset/brand/testing
  docs, contributing, security, changelog and research notes, with a
  sidebar, per-page table of contents, code-block copy buttons and raw-markdown downloads. It needs no server, no key and no database — serve the
  directory from any static host.
- **Nothing is deployed yet.** There is no API host, and any hostnames in the contract are
  proposed values, not live services. The page's API section documents the same envelopes
  and files that the generated mirror contains.

Consumers who want the data today should use the static JSON API in `draft/api/v1/`
(start at `draft/api/v1/index.json`, the machine-readable catalogue), the CSVs in
`data/seed/`, the raw snapshots in `data/raw/`, or the page payload
`data/seed/page-data.json`.

## Quality and validation

- **17 automated ingest checks + 7 service-area checks** run on every publication
  (structure, naming, counts, conflicts, reference anchors, coverage joins); a failure exits
  non-zero and stops publication.
- **Deterministic rebuilds**: same snapshots → same CSVs, page, docs site and static API
  (timestamps aside). `python3 tools/validate.py --check-page` proves the committed page
  rebuilds reproducibly; CI also verifies the generated docs tree.
- **Offline repository validation**: `tools/validate.py` checks the data contracts, the
  service-area dataset and provider-lens markup, the docs site, the built page, the OpenAPI
  document, the static JSON API and packaging, and exits non-zero on failure.
- **Browser QA**: `tests/qa.mjs` drives the built page in headless Chromium at desktop and
  mobile widths — zero console errors, zero external network requests, no horizontal
  overflow, the 18-region map, the 141-row table, the provider service-area lens (search,
  zoom, tooltip, region-level fallback, clearing), filters/sort/search, the custom dropdown
  keyboard UX, the API explorer, CSV export and the sticky scrollspy navigation.
  `tests/qa-docs.mjs` crawls every docs page over HTTP and checks loading, third-party
  requests, sidebar/TOC, internal links and fragments, and mobile overflow.
- **CI**: `.github/workflows/ci.yml` runs the static validation (including the
  deterministic-rebuild check), the docs build check and both browser QA suites on every
  push and pull request to `main`.
- **Provenance per number**: source tab, gid, SHA-256, retrieval time and the workbook row
  behind each utility's values.
- **Self-contained page**: verified to have no external runtime asset references and no
  client-side storage, analytics or fetch calls; outbound traffic is limited to user clicks
  on citation links.
- **Manual review**: the data dictionary, the validation report and the disclosed conflict
  log are part of the published tree, and `CONTRIBUTING.md` defines the review checklist.

Known limits are stated rather than hidden: there is no component-level bill breakdown yet
(v1 covers the blended published rates), the asset/plants layer is illustrative, the
upstream workbook has no documented refresh SLA or licence, and some commercial/industrial
cells are NDA. Service areas are derived from community-maintained franchise tables (OSM
Wiki / Wikipedia, CC BY-SA) rather than a single DOE publication; they carry per-row notes
for partial coverage, 57 LGUs are currently uncovered, and Meralco's law-based territory is
authoritative only for Meralco. The API is a contract, not a running service.

## Contributing

Contributions are welcome — especially data-quality checks, parsing fixes, accessibility
improvements and API/schema feedback. See **[CONTRIBUTING.md](CONTRIBUTING.md)** for the
development setup, the data and page rules, and the pull-request checklist. For security
issues, follow **[SECURITY.md](SECURITY.md)** instead of opening a public issue. Changes are
recorded in **[CHANGELOG.md](CHANGELOG.md)**.

## Licence

| Artefact | Licence |
| --- | --- |
| Source code, generated page, design layer | **MIT** — see [LICENSE](LICENSE) (© 2026 Open Energy Data Layer contributors) |
| Design language derived from BetterGovPH `transparency-portal` | MIT (© 2026 BetterGov.ph) |
| Fonts (Figtree, Inter, JetBrains Mono) | SIL Open Font License 1.1 |
| Icons (Lucide) | ISC License; Feather-derived icons MIT |
| Region + LGU geometry | MIT (repository scripts/maps, © James Faeldon / `faeldon/philippines-json-maps`); boundaries **CC BY 3.0 IGO** (© NAMRIA and PSA, via OCHA COD-AB) |
| Service-area dataset (`service_areas.csv`, derived coverage layer) | **CC BY-SA 2.0 / 4.0 derivative** — © OpenStreetMap Wiki contributors (CC BY-SA 2.0) and © Wikipedia contributors (CC BY-SA 4.0), with RA 12146 (Philippine public law) for Meralco; attribution + share-alike apply to the derived coverage data |
| BetterGov brand assets | BetterGovPH brand property — not MIT; used with attribution for this BetterGovPH open-data project |
| DOE workbook data and derived figures | **No confirmed licence** — the project asserts none; see [NOTICE.md](NOTICE.md) |

Third-party terms, provenance and attribution notes are in **[NOTICE.md](NOTICE.md)**.
