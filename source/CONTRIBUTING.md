# Contributing

Thanks for helping build an open, verifiable energy data layer for the
Philippines. This repository is a **data pipeline plus a static publication
surface**: correctness and provenance matter more than volume, and a number that
cannot be traced to a publisher source should not be published at all.

Contributions are welcome in these areas:

- **Data quality** — new sources, parsing fixes, cross-checks against publisher
  documents, conflict resolution, verification of NDA/missing states.
- **Pipeline** — extractors, validators, deterministic builds, API generation.
- **Page and design** — accessibility, responsiveness, clarity, and anything that
  makes the numbers harder to misread.
- **API and data model** — the OpenAPI 3.1 contract, envelopes, metadata,
  examples, and downstream interoperability (DBM COMPASS, data.gov.ph, DCAT).
- **Documentation and evidence** — correcting this file or any doc, with sources.

By contributing you agree that your contributions are licensed under the
repository's MIT licence ([LICENSE](LICENSE)) for code, page and design, and
that data contributions remain subject to the source-data terms described in
[NOTICE.md](NOTICE.md).

## Development setup

Requirements:

- **Python 3.12** (the version the pipeline is tested on) with `pip`.
- **Git**.
- Optional, for the browser QA suite: **Node.js 20+** with Playwright/Chromium.

```bash
# from the repository root
python3 --version                 # expect 3.12.x
python3 -m pip install -r requirements.txt

# optional: browser QA tooling (pinned Playwright + Chromium)
npm ci
npx playwright install chromium
```

The ingest pipeline, page builder and geometry builder use only the Python standard
library; `PyYAML` is needed by the API builder and the offline validator, and
`markdown-it-py` by the review-hub builder (both installed above).

## Build from source

Run the steps in order. The first ingest of a given day needs network access;
after that the snapshot is reused from `data/raw/doe-rates/<retrieval-date>/`.

```bash
# 1. (Optional) Rebuild the geometries from the pinned boundary release
python3 tools/build-geo.py               # -> draft/assets/geo.json + coverage-geo.json

# 2. Assemble the service-area dataset (Meralco RA 12146 + OSM/Wikipedia extraction
#    under research/coverage/, with labelled DOE-region fallbacks)
python3 tools/build-service-areas.py     # -> data/seed/service_areas.csv + source registry

# 3. Ingest the DOE workbook: fetch -> snapshot -> SHA-256 -> parse -> validate -> publish
python3 tools/ingest-doe-rates.py
#    re-fetch the four tabs even if today's snapshot exists:
python3 tools/ingest-doe-rates.py --refresh

# 4. Build the read-only static JSON API mirror
python3 tools/build-api.py               # -> draft/api/v1/

# 5. Build the documentation site
python3 tools/build-docs.py              # -> draft/docs/

# 6. Build the self-contained page (uses the ingested payload and, when present,
#    the API mirror and coverage geometry)
python3 tools/build-map-page.py          # -> draft/map-table-prototype.html

# 7. Build the local review hub (gitignored output)
python3 tools/build-preview.py           # -> preview/

# 8. Validate the repository offline (data contracts, service areas, page, docs,
#    OpenAPI, static API, packaging)
python3 tools/validate.py                # add --check-page for the deterministic rebuild check

# 9. Browser QA of the built page and the docs site
#    (Node.js 20+; npm ci + npx playwright install chromium first)
npm ci
node tests/qa.mjs
node tests/qa-docs.mjs

# 10. Open the page (it is a single self-contained file; file:// works)
xdg-open draft/map-table-prototype.html   # macOS: open ...; Windows: start ...
```

Expected results from a clean run (dataset version `2026-11-10`):

- ingest: **141 DUs per tab, 107 month columns, 60,348 cells**, `ALL CHECKS PASSED`
  (17/17 rate checks + 7/7 service-area checks);
- service areas: 141/141 utilities with LGU-level coverage (1,648 LGU rows + 17 barangay
  rows), 4 registered sources, zero undocumented region mismatches;
- page: 18 map regions, 1,642 inlined LGU polygons, 141 table rows, all data assets inlined;
- docs: 20 generated pages under `draft/docs/` with a deterministic tree;
- static API: one JSON file per utility (141), per region (18) and per service area (141),
  plus the dataset, rates, sources, changes and validation payloads, each with the
  documented envelope;
- preview: `preview/index.html` plus rendered docs and the contract;
- validation: `python3 tools/validate.py` exits 0;
- QA: `node tests/qa.mjs` exits 0 with no console errors or external requests.

Rebuilds are **deterministic**: with the same raw snapshots, `data/seed/*.csv`
and the page are reproduced byte-for-byte apart from the retrieval timestamp
stamped by the ingest. A rebuild that changes other bytes is a signal to
investigate — a genuine data change, not noise.

## Repository map

| Path | What it is |
| --- | --- |
| `tools/ingest-doe-rates.py` | **The data pipeline.** Fetches the four public workbook tabs, snapshots and hashes the raw bytes, parses them into one canonical utility row per workbook row, resolves cross-tab disagreements, attaches the service-area coverage, validates, and writes `data/raw/`, `data/seed/` and the page payload. |
| `tools/build-service-areas.py` | **Service-area assembler.** Merges the LGU-level franchise extraction with the RA 12146 Meralco override and region fallbacks; validates PSGC joins; writes `data/seed/service_areas.csv` and `data/seed/service_area_sources.csv`. |
| `tools/build-docs.py` | **Docs builder.** Renders every markdown source into the styled docs site under `draft/docs/` (deterministic; do not hand-edit the output). |
| `draft/frontend.md`, `draft/backend.md`, `draft/component-map.md` | **Architecture docs.** How the frontend surfaces are built and tested, the backend/pipeline design and failure modes, and the component map & agent guide (rendered at `frontend.html`, `backend.html`, `component-map.html`). |
| `AGENTS.md` (+ `tools/`, `data/`, `draft/`, `tests/`) | **Agent maps** for coding assistants: root orientation/component map plus per-area source-of-truth files, commands, generated artefacts, contracts and pitfalls. Read the nearest map before changing a component. |
| `data/raw/doe-rates/<date>/<gid>.csv` | Immutable raw byte snapshots, one per customer-class tab. **Never edit these.** |
| `research/coverage/` | Service-area evidence: deterministic extraction script, pinned wikitext snapshots, raw operator table, methodology and known-gap report. New franchise evidence goes here, not into the generated CSV. |
| `data/seed/` | Published outputs: `utilities.csv`, `rates_monthly.csv`, `regions.csv`, `sources.csv`, `service_areas.csv`, `service_area_sources.csv`, `validation.json`, `page-data.json`, and a README data dictionary. Generated — do not hand-edit. |
| `tools/build-map-page.py` | Builds `draft/map-table-prototype.html` from `data/seed/page-data.json` + `draft/assets/`. Fonts, logo, favicon, map geometry and data are inlined; the page makes no external requests. |
| `tools/build-api.py` | Builds the read-only static JSON API under `draft/api/v1/` from the published data. Generated — do not hand-edit. |
| `tools/build-geo.py` | Regenerates the region geometry (`draft/assets/geo.json`), the LGU coverage geometry (`draft/assets/coverage-geo.json`) and their provenance (`draft/assets/geo-sources.json`) from the pinned, SHA-256-verified boundary source. Deterministic; do not hand-edit the output. |
| `tools/build-preview.py` | Builds the local review hub at `preview/` from the markdown docs, the contract, the page and the data files. Output is gitignored. |
| `tools/validate.py` | Offline repository validation: data contracts, page contract, OpenAPI document, static API and packaging. Exits non-zero on failure; `--check-page` proves the committed page rebuilds deterministically. |
| `tests/qa.mjs` | Playwright browser QA for the built page: desktop and mobile viewports, console/network assertions, provider coverage lens, map/table/filter/API-explorer/CSV/nav behaviour. Screenshots go to `/tmp`, never the repo. |
| `tests/qa-docs.mjs` | Playwright docs-site QA: every page loads, no third-party requests, sidebar/TOC, internal link + fragment crawl, desktop/mobile overflow, mobile drawer. |
| `package.json` | Node tooling for the QA suite (pinned Playwright; `qa`, `validate`, `build:page`, `build:api` scripts). |
| `.github/workflows/ci.yml` | CI on push/PR to `main`: static validation + deterministic rebuild check, then browser QA; uploads QA artifacts. |
| `draft/openapi.yaml` | The OpenAPI 3.1 contract for the public API. |
| `draft/api-docs.md` | The human-readable API guide (access, units, conventions, endpoint reference, attribution, versioning). |
| `draft/api/v1/` | Generated static JSON API (dataset metadata, utilities, regions, rates, sources, changes, validation, OpenAPI JSON mirror). |
| `draft/assets/` | Design assets: fonts (OFL 1.1), BetterGov brand assets, favicon, region geometry. `draft/assets/README.md` records sources and licences. |
| `plan/` | Internal working notes and plans (not part of the published product). |
| `research/`, `draft/data-model.md` | Source ledger/evidence and the canonical data model. |
| `data/seed/plants.csv` | **Illustrative** sample plants for a future asset layer; not displayed on the page, marked `data_status=illustrative`. The current pipeline does not generate it. |

## Data rules (non-negotiable)

1. **Never hand-edit generated files.** `draft/map-table-prototype.html`,
   `draft/api/v1/`, `data/seed/*.csv`, `data/seed/page-data.json` and
   `data/seed/validation.json` are build outputs. Fix the generator and rebuild.
2. **Never impute.** Preserve the publisher's states exactly: `published`,
   `nda` (publisher says no data), `missing` (blank cell) and `invalid`
   (unparseable cell, e.g. the `Jan-16` text in an Oct-2026 cell). Aggregates
   use published values only; report the reporting count next to every
   aggregate. Do not fill, interpolate, average over, or silently drop cells.
3. **Provenance is mandatory.** Every published row keeps `source_id`,
   `extraction_method`, `confidence`, `retrieved_at` and `source_row`. A new
   source needs a `sources.csv` entry with the page/sheet URL, retrieval
   timestamp, SHA-256 of the raw bytes, and a licence note that says what is
   known and what is not.
4. **Snapshot before parsing, hash before publishing.** Raw publisher bytes are
   the source of truth. A retrieval that changes them creates a new dated
   snapshot directory; do not edit an old snapshot in place.
5. **Do not guess conflicts.** When tabs disagree, resolve by majority and keep
   the losing claims; publish `CONFLICT` where there is no majority. Add the
   conflict to the validation report so it stays visible.
6. **Anchor checks are contracts, not conveniences.** The pipeline asserts the
   June-2026 reference figures. If an anchor fails, stop and investigate;
   never change the expected value to make the build pass.
7. **Do not assert licences you cannot verify.** The DOE workbook has no
   confirmed dataset licence; see [NOTICE.md](NOTICE.md). New sources with
   unclear terms must be labelled as such, not assumed open.
8. **No personal data, no secrets, no blocked-source scraping.** Do not commit
   API keys, tokens, `.env` files, private contact details, or data obtained by
   circumventing an access control. Blocked sources are partnership/FOI items,
   not scraping targets.

## Page rules

- The page must stay **self-contained and offline-first**: fonts, brand assets,
  map geometry and data are inlined at build time. Do not add CDN scripts,
  remote stylesheets, web fonts, trackers or analytics, or any runtime
  `fetch`/XHR. The only allowed outbound requests are the user's clicks on
  citation links (`target="_blank" rel="noopener"`).
- Keep it **accessible**: semantic headings, labels for controls, visible focus,
  keyboard-operable filters, colour contrast that does not rely on colour alone,
  and a responsive layout at mobile width.
- **Provenance in the UI**: a published rate must be traceable to its month,
  state (published/NDA/invalid) and source row. If you add a number, give it a
  receipt.
- Design tokens and components follow the BetterGovPH open-data language; adapt
  them rather than inventing a parallel style. Brand assets remain BetterGovPH
  property (see [NOTICE.md](NOTICE.md)).

## API and schema rules

- The contract is `draft/openapi.yaml` (OpenAPI 3.1). Keep it valid and keep
  examples consistent with real generated values — no invented endpoints. Update
  `draft/api-docs.md` in the same change and regenerate the static API.
- The static JSON API under `draft/api/v1/` is generated by `tools/build-api.py` from the
  same published data; change the builder, not the JSON files. Keep it and the contract in
  sync (`draft/api/v1/openapi.json` mirrors the YAML document).
- Responses use the documented `{meta, data, next_cursor}` envelope; every
  response carries dataset version, source and attribution metadata.
- The canonical geography is PSA PSGC (10-digit); the canonical entity ID is
  `utility_code`. Do not introduce a second ID scheme.
- Schema changes must update `draft/data-model.md`, the OpenAPI document and the page's API
  preview together.

## Before you open a pull request

1. `python3 tools/ingest-doe-rates.py` — confirm `validation.json` reports
   `"passed": true` (17/17) and review the diff in `data/seed/`.
2. `python3 tools/build-map-page.py` — rebuild and inspect the page.
3. `python3 tools/build-api.py` — rebuild the static JSON API and confirm only intended
   payload changes appear.
4. `python3 tools/build-preview.py` — rebuild the local review hub.
5. `python3 tools/validate.py` — the offline repository validation must pass (use
   `--check-page` when you change the page builder).
6. `npm ci && node tests/qa.mjs` — the browser QA suite must pass (CI runs the same checks
   on every PR). Paste the result in the PR.
7. Confirm the page makes **no external requests** and has no console errors
   (browser devtools), and that it renders on desktop and mobile widths.
8. Update the docs/files your change affects: `README.md`, `data/seed/README.md`,
   `draft/api-docs.md` (API changes), `NOTICE.md` (third-party assets/data),
   `draft/assets/README.md` (asset provenance), the API docs/spec for contract changes,
   and `draft/frontend.md` / `draft/backend.md` / `draft/component-map.md` when the
   architecture, build commands or component map change. If you add or rename a
   builder, path or command, update the matching `AGENTS.md` map too.
9. Ensure `git status --short` lists only your intended files. `preview/`,
   `node_modules/`, screenshots and the unrelated root `index.html` /
   `screenshots/` are not part of this project — leave them out.

Use clear, imperative commit messages; explain *what changed and why* in the PR
body, and call out any data change with its source receipt. Small, focused PRs
are easier to review and to trace. CI runs `tools/validate.py` (including the
deterministic-rebuild check) and `tests/qa.mjs` on every push and pull request to
`main`, so a green local run is a good predictor of a green PR.

## Reporting data problems and security issues

- **Data errors** (a rate that does not match the source workbook): normal
  issue with utility, month, class, value and the source row if known.
- **Security issues**: follow [SECURITY.md](SECURITY.md); do not open a public
  issue.
- **Licence/attribution concerns**: raise them with the maintainers — NOTICE
  corrections are always in scope.
