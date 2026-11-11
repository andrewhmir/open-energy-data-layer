# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project intends to adopt [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once it
reaches 1.0.

**Status: pre-release (`0.x`), not yet deployed.** There is no public URL for the page and
no running API host yet; [`draft/openapi.yaml`](draft/openapi.yaml) is an API *contract*, not
a service. The page is a static, self-contained file. The DOE workbook has no confirmed
dataset licence (see [NOTICE.md](NOTICE.md)), so no licence is asserted over the data.

## [Unreleased]

### Added

- **Architecture documentation.** Three new generated docs pages explain how the system
  fits together: *Frontend architecture* (`draft/frontend.md` — the three browser-facing
  surfaces, build-time data/asset injection, the runtime JS modules, state and deep links,
  accessibility and the pinned QA contracts), *Backend & pipeline architecture*
  (`draft/backend.md` — the deterministic static-artifact pipeline, provenance, data
  contracts, hosting, safe-change loop and troubleshooting) and a *Component map & agent
  guide* (`draft/component-map.md` — where every component lives, what to edit versus
  regenerate, the build-order graph and task routing). They render under a new
  "Architecture" group in the docs site (now 21 pages: 20 documents + index), linked from
  the README, CONTRIBUTING and the docs landing page.
- **Agent maps.** The repository now ships an `AGENTS.md` hierarchy: a root orientation
  map (components, task routing, invariants, finish checklist) plus per-area maps for
  `tools/`, `data/`, `draft/` and `tests/`, each stating the area's source-of-truth files,
  build/verify commands, generated artefacts, contract inventory and pitfalls.
- **Provider comparison on the data page.** Any expanded price-table row or provider panel can
  add a utility to a comparison tray (up to three); the comparison dialog overlays each
  utility's full 2018–2026 residential history and a latest-rate matrix for all four customer
  classes, with service-area context, a link to each provider's DOE workbook source row and
  public API file, and an explicit "not a bill estimator, not financial advice" note. Every
  figure shown is available from the public static API. The dialog is a focus-trapped native
  dialog (Escape closes and restores focus), becomes stacked cards on mobile, and the selection
  is deep-linkable (`?compare=MERALCO,SOLECO`).
- **Shareable, fully stateful deep links and a copy-link action.** The sticky nav's copy-link
  button puts the current state into the URL — provider, region, comparison, search, type,
  grid, NDA toggle, colour measure, sort and expanded row (`?provider=`, `?region=`,
  `?compare=`, `?q=`, `?type=`, `?grid=`, `?nda=0`, `?colour=`, `?sort=`, `?utility=`) — so any
  filtered view can be bookmarked or sent on, and the page restores it on load.
- **Richer national map view.** The map legend now sits above the map (visible without
  scrolling), with zoom-in/zoom-out controls in addition to the existing whole-country reset.
  Region paths use a roving tabindex with arrow-key navigation, Home/End and Escape-to-clear;
  the tooltip documents the keyboard contract.
- **National overview beside the map.** The aside now shows the latest month's median
  residential rate, published range, reporting count and median generation charge, a
  proportional ranking of all 18 region medians, and the month's biggest movers — each
  clickable through to the region or utility — instead of a mostly empty panel.
- **Clearer table states.** A no-results state explains when filters exclude every utility and
  offers a single "Clear all filters" reset; the expanded-row detail spans all nine columns;
  the filter summary reports any comparison selection in progress.
- **Provider service-area lens on the data page.** A searchable provider filter (all 141
  utilities) switches the map to a coverage view: the utility's sourced cities and
  municipalities are drawn at LGU level on a zoomed map, with its latest published rate, a
  region-median comparison in the tooltip, an aside listing served provinces with
  full/partial counts, and a region-level fallback for utilities without LGU detail. Every
  selection is reflected in the table filter and the URL (`?provider=MERALCO`).
- **LGU-level service-area dataset** (`tools/build-service-areas.py` →
  `data/seed/service_areas.csv`, `data/seed/service_area_sources.csv`): 108 RA 12146
  Meralco LGUs + 17 Pampanga barangays, 1,540 LGU-level rows for the other 140 utilities
  from the OpenStreetMap Wiki franchise table (CC BY-SA 2.0) and a Wikipedia supplement
  (CC BY-SA 4.0), with per-row source ids, revision/retrieval metadata, partial-coverage
  notes and documented PSGC 3Q 2026 region reassignments. 141/141 utilities now have
  LGU-level coverage.
- **LGU coverage geometry** (`draft/assets/coverage-geo.json`, built by `tools/build-geo.py`
  from the same pinned boundary release): 1,642 municipality/city polygons simplified for
  the coverage overlay, with per-file SHA-256 provenance.
- **Generated documentation site** (`tools/build-docs.py` → `draft/docs/`, 20 pages): every
  markdown document rendered in the BetterGovPH design language with a grouped sidebar,
  per-page table of contents, code copy buttons, prev/next pager, raw-markdown downloads and
  mobile navigation; the data page's masthead, downloads and footer now link to it instead
  of raw `.md` files.
- **Docs QA suite** (`tests/qa-docs.mjs`): HTTP crawl of every docs page checking loads,
  zero third-party requests, sidebar/TOC state, internal link and fragment resolution,
  desktop/mobile overflow and the mobile drawer.
- Provider-filter coverage data is published in the static JSON API (service-area endpoints
  and per-utility coverage in the utility responses) and documented in the OpenAPI contract,
  API guide and data model.
- Service-area review material under `research/coverage/` (deterministic extractor, pinned
  wikitext snapshots, raw operator table, methodology and known-gap report).
- Searchable custom dropdowns, map viewBox zoom/reset, deep-linkable `?provider=` /
  `?region=` state, and a coverage-aware CSV export.

### Changed

- **The fellowship submission is now fully isolated from the data platform.** The production
  page no longer carries any submission surface: the blue Fellowship strip, the masthead and
  footer "Fellowship 2026" links, the "Fellowship proposal" footer link, the review-pack bar
  and the "Compiled for the BetterGovPH Fellowship 2026 Energy Track" attribution are gone.
  Dataset attribution and citation now credit the Department of Energy (DOE) as the source and
  the Open Energy Data Layer for the compilation, and the remaining "challenge pitch" wording
  in the validation labels, README, CONTRIBUTING, NOTICE, SECURITY and brand-asset notes was
  neutralised. The page reads as an independent production data product.
- **The data-platform documentation site is platform-only** (`draft/docs/`, 18 pages): the
  proposal, application answers and challenge-deck notes were removed from the docs registry
  and the research auto-discovery; the docs masthead/footer/index quick-links no longer link
  the fellowship, and the search index and manifest only register the remaining 17 platform
  documents. No rendered docs page links to a submission document.
- **The fellowship submission now lives only in the review pack.** `/` is a dedicated
  "Fellowship submission & review pack" home with the submission status/deadline, proposal,
  application answers, challenge brief, review evidence and downloads, and an explicit
  statement that the data platform is a separate standalone product containing no submission
  material. `/prototype.html` in the pack is byte-identical to the production page after the
  canonical repo-link rewrites (no review bar and no submission chrome), and the pack's
  data-artifact pages (`api`, `data-model`, `readme`, `research-*`) and every docs page use a
  neutral "review copy" bar instead of fellowship chrome.
- `tools/validate.py` and the browser QA suites gained a hard separation contract: the built
  page must have no submission strip/marker/link/visible copy, and the docs site must not
  register or publish any submission document.
- `tools/validate.py` gained service-area and docs-site validation groups (337+ checks):
  coverage joins, source registry, Meralco law/barangay counts, payload↔CSV consistency,
  embedded coverage blocks, provider affordances, docs tree and page→docs link resolution.
- `tests/qa.mjs` gained the provider-lens suite (search, selection, tooltip, zoom reset,
  region fallback, clearing, keyboard) plus provider screenshots at desktop and mobile.
- CI additionally verifies the generated docs tree and runs the docs QA suite.
- The ingest can now reproduce an existing build byte-for-byte by pinning
  `OPEN_ENERGY_RETRIEVED_AT`; `utilities.csv` gained coverage summary columns.
- README, NOTICE, CONTRIBUTING and the page's method/downloads/footer copy document the
  coverage sources, licences and limits (coverage is a CC BY-SA derivative, not a DOE
  publication).

- Production repository packaging: an MIT [LICENSE](LICENSE), a third-party and data
  [NOTICE.md](NOTICE.md), [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md),
  this changelog, `.editorconfig`, `.gitattributes` and `requirements.txt`, together with a
  rewritten production [README.md](README.md).
- BetterGovPH design assets under `draft/assets/brand/`: the official BetterGov emblem
  (primary and outline), an emblem-based favicon set, and a vendored Lucide icon sprite with
  a machine-readable manifest (icon licences: ISC; Feather-derived icons MIT); plus a
  1200×630 social card (`draft/assets/og.png`).
- **High-resolution region geometry** (`tools/build-geo.py` → `draft/assets/geo.json`):
  rebuilt from the pinned `faeldon/philippines-json-maps` v1.1.1 hires release with archive
  and per-file SHA-256 verification and screen-space simplification, fixing the boxy CAR
  outline from the first pass. Provenance and parameters are recorded in
  `draft/assets/geo-sources.json`; licences are MIT (repository scripts/maps) plus
  CC BY 3.0 IGO (boundaries, © NAMRIA/PSA via OCHA COD-AB).
- **Static JSON API** (`tools/build-api.py` → `draft/api/v1/`): a read-only JSON mirror of
  the dataset with the documented `{meta, data, next_cursor}` envelope — metadata, health,
  months, latest rates per class, the utility registry plus one file per utility, region
  aggregates plus one file per region, sources, changes, conflicts, the validation report
  and a JSON mirror of the OpenAPI document. No server, key or database required.
- **Offline repository validation** (`tools/validate.py`): checks the CSV/JSON data
  contracts, the built page, the OpenAPI document, the static JSON API and repository
  packaging, exits non-zero on failure, and can prove a deterministic page rebuild
  (`--check-page`).
- **Production API documentation and contract**: `draft/openapi.yaml` rewritten as
  OpenAPI 3.1 (API version `1.0.0`) documenting the static endpoints (17 at first; 19 once
  the service-area endpoints were added), the provenance
  envelope, datasets and units, sources/attribution, disclaimers and versioning; the
  readable guide is `draft/api-docs.md`, and the generated static JSON API matches both.
- **Browser QA and CI**: `tests/qa.mjs` drives the built page in headless Chromium at
  desktop and mobile widths (console/network assertions, map, table, filters, API explorer,
  CSV export, sticky nav) and `.github/workflows/ci.yml` runs the static validation, the
  deterministic-rebuild check and the QA suite on push/PR to `main`. `package.json` pins the
  Playwright tooling.

### Changed

- The README now documents the project as a production open-source project; challenge
  context is kept to a single short section near the end.
- `.gitattributes` marks the generated page and the largest generated data files as
  generated, and webfonts as binary, without hiding legitimate source diffs.

### Pending

- Public deployment (static host, page URL, API base URL) — not decided in this repository;
  the OpenAPI `servers` entry is a relative base path, and nothing is live.
- A scheduled dataset refresh (new retrieval date → new snapshot) — the pipeline supports
  it, but no schedule is configured in this repository yet.

## [0.1.0] — 2026-11-10 — pre-release

Initial repository: a real-data pipeline, a generated publication page and an evidence
pack, committed as `e05cc1e` ("Open energy data layer: real DOE data pipeline, BetterGovPH
page, proposal and evidence").

### Added

- **Data pipeline** (`tools/ingest-doe-rates.py`): fetches the four tabs of DOE's public
  *Electricity Rates & Power Market Monitor* workbook through Google's unauthenticated CSV
  export, snapshots the raw bytes under `data/raw/doe-rates/<retrieval-date>/`, records a
  per-tab SHA-256, parses the wide month columns into tidy `utility × month × customer
  class` observations, resolves the four tabs into one canonical utility row per workbook
  row, validates 17 structural and anchor checks (a mismatch stops publication), and
  publishes tidy CSVs, a validation report and the page payload.
- **Published dataset** in `data/seed/`: `utilities.csv` (141 rows), `rates_monthly.csv`
  (60,348 rows), `regions.csv` (18 rows), `sources.csv` (4 tab records with hashes, URLs
  and licence notes), `validation.json` (17 checks, conflicts, counts, per-tab hashes) and
  `page-data.json` (compact page payload), plus a data dictionary.
- **Generated page** (`tools/build-map-page.py` → `draft/map-table-prototype.html`): a
  single self-contained HTML file in the BetterGovPH open-data design — 18-region
  choropleth map, sortable/filterable price table of all 141 utilities with expandable
  monthly histories, NDA/invalid states, CSV export, API preview, and method/validation/
  conflict receipts. Fonts, logo, favicon, geometry and data are inlined; no external
  runtime requests.
- **API contract** (`draft/openapi.yaml`): OpenAPI 3.1 draft covering the registry, rates,
  regions, sources, changes and downloads surface with provenance fields and a
  BetterGovPH-compatible response envelope.
- **Data model** (`draft/data-model.md`): canonical entities, PSGC geography and
  `utility_code` identifiers, provenance backbone, publication states, versioning and
  licensing policy.
- **Evidence pack** (`research/`): a source-by-source data landscape with verification
  labels, blocked-source log and discrepancies; an API/interop landscape (DBM COMPASS,
  DCWG/open-data standards, precedent APIs, BetterGovPH reuse); and a verbatim extract of
  the challenge pitch deck's energy-track slides.
- **Submission documents** (`plan/`): the fellowship proposal and draft answers to the
  application form.
- **Local review hub** (`tools/build-preview.py` → `preview/`, gitignored): rendered docs,
  API reference, a copy of the page and data downloads for internal review.
- **Raw source snapshots**: the four tab CSVs for retrieval `2026-11-10`, tracked as the
  auditable source of truth.

### Data

- 141 distribution utilities and electric cooperatives (120 ECs, 21 PIOUs), 18 PSGC
  regions, four customer classes, 107 header months (Jan 2018 – Nov 2026) and 106 months
  with published data (Jan 2018 – Oct 2026).
- Latest month, October 2026: 113/141 residential utilities reporting, 27 NDA, 1 invalid
  cell; median ₱12.72/kWh, mean ₱13.23/kWh, range ₱5.33–₱19.36/kWh.
- Five cross-tab source conflicts disclosed and handled by majority vote, with a 2–2 tie
  published as `CONFLICT` rather than guessed; `published`/`nda`/`missing`/`invalid` states
  preserved with no imputation.
- All 17 automated checks passing, including the challenge pitch's June-2026 anchor figures
  (Meralco ₱14.48, SOLECO ₱16.57 at +32.2% month-on-month, BISELCO ₱24.92; 127 reporting
  DUs, simple mean ₱12.29, median ₱12.10).

### Known limitations

- No public deployment, page URL or API host exists yet.
- No dataset licence has been confirmed with DOE; the project asserts none (see
  [NOTICE.md](NOTICE.md)).
- `data/seed/plants.csv` (13 rows) is illustrative sample data for a future asset layer and
  is not displayed; the current map shows regions, not facilities.
- v1 covers blended published rates; component-level bill breakdowns, DOE plant/RE feeds and
  reliability data are future/partnership work, not claimed here.
- The application's identity/contact placeholders in `plan/application-answers.md` are
  filled in before the 17 November 2026 deadline, not part of the code release.
