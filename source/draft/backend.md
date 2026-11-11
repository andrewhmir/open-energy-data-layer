# Backend & pipeline architecture

There is no API server, database, queue or long-running process in this project. What plays the
"backend" is a **chain of deterministic static generators**: Python scripts that turn one public
spreadsheet into validated seed tables, a self-contained page, a read-only JSON API, a docs site and a
local review pack. Every artefact is a committed file (or a copy) that can be rebuilt byte-for-byte.

This page maps that chain: stages and contracts, build order and CI, hosting, safe changes and failure
diagnosis. Rules: [CONTRIBUTING](../CONTRIBUTING.md) · QA evidence: [tests/README](../tests/README.md)
· whole-repo component map: [component-map.md](component-map.md).

| | |
|---|---|
| **Dataset version** | `2026-11-10` (retrieved `2026-11-10T17:00:34+08:00`; latest published month `2026-10`) |
| **Input coverage** | 141 DU/ECs · 18 PSGC regions · 107 header months (2018-01 → 2026-11) · 60,348 rate observations |
| **Published artefacts** | seed CSVs + page payload · 19-route static JSON API (OpenAPI 3.1, contract `1.0.0`) · single-file page · docs site · local review pack |
| **Status** | Pre-release `0.x`; 17 + 7 ingest checks and two browser QA suites gate it; **no public deployment** — the API is a contract, not a running service |

## What "backend" means here

The system is a build pipeline whose outputs are the product: there is no request path, so its runtime
is a static host (or a browser opening a file) and its state is the checkout — raw publisher bytes,
validated seed tables, generated artefacts and git history.

Concretely: the page is one self-contained HTML file; the API is a directory of JSON files; the docs
site is static HTML; the review pack is a static directory; and the "backend" itself is eight Python
CLI tools (Python 3.12 + `requirements.txt`) with no daemon.

**Why static generation.** No database, API uptime, key management or secrets, and any static host
works; each data change is diffable next to its receipt; same snapshots produce the same bytes (CI
proves it); and everything is reviewable offline.

It is **not** a live feed, a query API (`next_cursor` is always `null`), an official DOE product or a deployed service.

## Source of truth and provenance

Everything derives from DOE's *Electricity Rates & Power Market Monitor* workbook. It publishes no
documented refresh calendar and no dataset-specific licence, so each retrieval is pinned as a dated
snapshot rather than tracked as a feed.

| | |
|---|---|
| **Publisher / source** | Department of Energy (DOE) — <https://doe.gov.ph/data-and-prices/electricity>, embedding public Google Sheet `1oGc1iGpacELS6tkHjesvAeKZo8v2iv4UkYFY04e0p-I` (four tabs) |
| **Retrieval** | unauthenticated CSV export per tab (`/export?format=csv&gid=…`), same bytes a browser downloads; `2026-11-10T17:00:34+08:00` |
| **Raw snapshot** | `data/raw/doe-rates/2026-11-10/<gid>.csv` (tracked, immutable); hashes in [sources.csv](../data/seed/sources.csv) and [validation.json](../data/seed/validation.json) |
| **Licence** | **not confirmed by the publisher**; this project asserts none — see [NOTICE](../NOTICE.md) |

The four tabs are residential (`gid=0`), commercial (`441532959`), industrial (`1244383053`) and
blended generation charge (`714337242`), each exported as `data/raw/doe-rates/2026-11-10/<gid>.csv`
with 141 rows × 107 month columns per tab.

### Snapshots and hashes

- **Snapshot before parsing, hash before publishing.** The ingest writes each tab's exact bytes under
  the retrieval-dated directory and only then parses them; the raw bytes are the source of truth.
- **Per-tab SHA-256**, with URL, `tab_gid`, retrieval timestamp, cell count and snapshot path, is
  recorded in `sources.csv` and `validation.json`. `tools/build-api.py` re-verifies the committed
  snapshot bytes against those hashes on every build, so an edited CSV or stale tree is caught.
- **Immutable history.** A new retrieval date creates a new `data/raw/doe-rates/<date>/` directory;
  old snapshots are never edited. A same-day rerun reuses the snapshot (hence reproducible rebuilds);
  `--refresh` is an explicit re-fetch.
- **`dataset_version`** is the retrieval date (`2026-11-10`), stamped into the page payload, every API
  `meta` and the OpenAPI contract. It changes only with a new retrieval.

### Provenance chain

```text
workbook tab gid ─► data/raw/doe-rates/<date>/<gid>.csv   (immutable bytes, SHA-256)
                         ├─► hash + retrieval time ─► data/seed/sources.csv, validation.json
                         ▼
              data/seed/utilities.csv, rates_monthly.csv   (source_row, retrieved_at, extraction_method)
                         ├─► data/seed/regions.csv, page-data.json ─► page
                         ├─► draft/api/v1/** (meta.dataset_version, meta.source) ─► API consumers
                         └─► draft/docs/** (rendered markdown + data dictionary) ─► docs readers
```

Every row keeps `source_id`, `extraction_method`, `confidence`, `retrieved_at` and `source_row`, so a
published value resolves to a workbook row → tab → SHA-256 → archived publisher bytes.

### Licence status

| Artefact | Status |
|---|---|
| Code, generated page, docs tooling, design layer | **MIT** — see [LICENSE](../LICENSE) |
| DOE workbook and extracted figures | **No confirmed licence; none asserted** — terms to be confirmed with DOE; no endorsement implied |
| Service-area coverage layer | **CC BY-SA derivative** — OSM Wiki (CC BY-SA 2.0) + Wikipedia (CC BY-SA 4.0); RA 12146 public law for MERALCO |
| Region / LGU geometry | Boundaries **CC BY 3.0 IGO** (NAMRIA / PSA via OCHA COD-AB); source maps and scripts MIT |
| Fonts, icons, brand marks | OFL 1.1, ISC/MIT, and BetterGovPH brand property (not MIT) respectively |

Full attribution and obligations are in [NOTICE](../NOTICE.md); the coverage layer must keep its
per-row `source_id` and CC BY-SA attribution when republished.

## Data contracts and publication states

### Cell states: `null` never means zero

| State | Meaning | Published as |
|---|---|---|
| `published` | the workbook has a numeric rate | the value, unchanged |
| `nda` | publisher's "No Data Available" | a state, **never** `0` or an estimate |
| `missing` | month column exists but the cell is blank / not yet published | a state (all of 2026-11) |
| `invalid` | the cell failed extraction (one cell in 2026-10) | a state, no value |

**No imputation.** Cells are never filled, interpolated or averaged over; utility-level `data_status`
is `published`, `partial` or `nda` for the latest month. Aggregates use published values only and are
always published with their reporting count (October 2026 residential: 113 of 141 reporting, 27 NDA,
1 invalid, median ₱12.72/kWh); commercial, industrial and generation have larger NDA shares, so a
number never appears without the count that qualifies it. Pinned June-2026 anchor figures are
asserted on every run, and row counts (141 utilities / 18 regions / 107 months / 60,348 observations)
are hard contracts — a mismatch stops publication and is never silenced by editing the expectation.

### Conflicts: disclosed, not smoothed

When tabs disagree the pipeline resolves by **majority**, keeps the losing claims verbatim, and
publishes `CONFLICT` when there is no majority. All five current disagreements are logged in
`data/seed/validation.json` and surfaced through the API and the page's method section:

| Conflict | Tabs say | Resolution |
|---|---|---|
| CLPC region (row 33) | BARMM (residential/commercial/generation) vs Region 12 (industrial) | majority BARMM; both claims kept |
| Island label (row 33) | industrial says "BARMM"; others Mindanao | region mapping wins; logged |
| ILECO II grid status (row 122) | ONGRID 2 tabs vs OFFGRID 2 tabs | `grid_connection = CONFLICT` — never guessed |
| ILECO III grid status (row 123) | ONGRID 2 tabs vs OFFGRID 2 tabs | `grid_connection = CONFLICT` — never guessed |
| DANECO name | `DANECO` vs `DANECO/NORDECO` | canonical name + `name_variants` kept |

### Versioning and contract stability

- `api_version` (`1.0`) is the JSON contract version, stable across refreshes; `dataset_version`
  (`2026-11-10`) identifies the snapshot and changes with every retrieval. Snapshots are immutable
  once published — a new retrieval is a new version and a new generated tree, never a silent
  rewrite. Contract changes are recorded in the OpenAPI `x-changelog` and [api-docs.md](api-docs.md);
  additive layers keep the major version (service areas were additive v1.1).
- Every response carries `meta.dataset_version`, source/attribution metadata, five disclaimers and a
  coverage context block; `draft/api/v1/index.json` adds a citation string.

### Contracts enforced by the build

Ingest gates publication on the 17 + 7 checks (`ALL CHECKS PASSED`). The API builder checks seed
self-consistency (exit `2`, nothing written) and every emitted file against
[openapi.yaml](openapi.yaml) (exit `1` on drift). `validate.py` covers ten contract groups, and every
docs link and fragment must resolve when the site is built and crawled.

## The pipeline, stage by stage

Each tool is a standalone CLI that derives the repository root from its own path and is run from the
repository root. Read a builder's module docstring before editing it: it declares role, inputs,
outputs, flags, exit codes, network behaviour and determinism rules.

### Build-order graph

```text
[network] pinned geometry release v1.1.1 ─► (1) build-geo.py ─► draft/assets/{geo,coverage-geo,geo-sources}.json
                                                                       │
research/coverage/** ─► (2) build-service-areas.py ◄────────────────────┼── data/seed/utilities.csv, regions.csv
                              └─► data/seed/{service_areas,service_area_sources}.csv
                                                                       │
DOE workbook ─► [network] ─► (3) ingest-doe-rates.py ◄─────────────────┘
                              └─► data/raw/doe-rates/2026-11-10/<gid>.csv (bytes + SHA-256)
                                  data/seed/{utilities,rates_monthly,regions,sources}.csv
                                  data/seed/{validation,page-data}.json
                                                                       │
        ┌──────────────────────────────┬───────────────────────────────┴───────────┐
        ▼                              ▼                                           ▼
(4) build-api.py              build-map-page.py                         build-docs.py
    (+ openapi.yaml)          (+ assets/geo*.json, optional API)        (+ markdown registry)
    └─► draft/api/v1/         └─► draft/map-table-prototype.html        └─► draft/docs/
        └──────────────────────────────┬───────────────────────────────────────────┘
                                       ▼
(5) build-preview.py ──► preview/ (gitignored)   (6) validate.py (+ --check-page) · tests/qa.mjs · tests/qa-docs.mjs
```

### Stage reference

| # | Stage | Tool | Inputs | Outputs | Network | Determinism notes | Command |
|---|---|---|---|---|---|---|---|
| 1 | Geometry | [build-geo.py](../tools/build-geo.py) | pinned `faeldon/philippines-json-maps` v1.1.1 release, per-file SHA-256 | `draft/assets/geo.json` (18 regions), `coverage-geo.json` (1,642 LGUs), `geo-sources.json` | first fetch only; cached in a temp dir | pure function of pinned inputs + constants; only `geo-sources.json` changes between runs | `python3 tools/build-geo.py` |
| 2 | Service areas | [build-service-areas.py](../tools/build-service-areas.py) | `research/coverage/osm-service-areas.csv`, `research/service-areas.json` (RA 12146), `data/seed/utilities.csv`, `draft/assets/coverage-geo.json` | `data/seed/service_areas.csv`, `service_area_sources.csv` | none | sorted output; refuses to write on bad joins, uncovered utilities or duplicate rows (exit `2`) | `python3 tools/build-service-areas.py` |
| 3 | Ingest | [ingest-doe-rates.py](../tools/ingest-doe-rates.py) | four DOE tabs via CSV export; the assembled service-area CSVs | `data/raw/doe-rates/<date>/<gid>.csv`; `data/seed/{utilities,rates_monthly,regions,sources}.csv`; `validation.json`; `page-data.json` | first run per retrieval date or `--refresh`; same-day rerun reuses snapshot | reproducible via `OPEN_ENERGY_RETRIEVED_AT`; 17 + 7 checks gate publication; conflicts logged | `python3 tools/ingest-doe-rates.py [--refresh]` |
| 4 | Static API | [build-api.py](../tools/build-api.py) | `data/seed/**`, raw snapshots (hash-verified), [openapi.yaml](openapi.yaml) | `draft/api/v1/**` incl. `openapi.json` mirror and `index.json` catalogue | none | fixed ordering, no wall clock; only seed timestamps; exit `1` contract drift, `2` seed inconsistency | `python3 tools/build-api.py [--sync-openapi]` |
| 5 | Docs site | [build-docs.py](../tools/build-docs.py) | markdown registry + auto-discovered `research/*.md`, `draft/assets/**`, seed facts | `draft/docs/**` + `docs-manifest.json` + inlined search index | none | two runs byte-identical; unresolved internal links fail the build | `python3 tools/build-docs.py` |
| 6 | Product page | [build-map-page.py](../tools/build-map-page.py) | `data/seed/page-data.json`, `draft/assets/**` (fonts, brand, geometry), optional `draft/api/v1/` | `draft/map-table-prototype.html` (one self-contained file) | none | byte-identical rebuild; everything inlined; API explorer degrades if the API is absent | `python3 tools/build-map-page.py` |
| 7 | Review pack | [build-preview.py](../tools/build-preview.py) | built page, docs, API, OpenAPI, markdown sources, data files | `preview/` (gitignored review hub incl. downloads and a package zip) | none | copies upstream output, never authors it; rebuild upstream first | `python3 tools/build-preview.py` |
| 8 | Validation | [validate.py](../tools/validate.py) | the committed tree; builders only for `--check-page` | console report + exit status | none | contract-based (never file hashes); `--check-page` rebuilds the page twice and compares | `python3 tools/validate.py [--check-page]` |

### Ordering, cost and failure behaviour

- **Geometry → service areas.** The assembler joins every LGU row to canonical PSGC codes in
  `draft/assets/coverage-geo.json`, and reads the previous ingest's `utilities.csv` / `regions.csv`;
  a missing file stops it (the committed seed makes the documented order work).
- **Service areas → ingest.** The ingest refuses to run without `service_areas.csv` /
  `service_area_sources.csv` and folds coverage into the payload and registry.
- **Ingest → API, page, docs.** All three consume `data/seed/`. Build the API **before** the page so
  the API explorer is populated (the page still builds without it, minus the explorer). The review
  pack copies all outputs, and validation/QA run last.

Measured single-run wall time on the dev VM for this snapshot (warm Python, warm geo cache): geometry
≈3.5 s (first run also downloads the release); service areas <0.1 s; ingest ≈0.1–0.2 s from snapshot;
API ≈0.3–0.4 s; docs ≈0.2 s; page <0.1 s; review pack seconds; `validate.py` ≈0.3 s (≈0.4–0.5 s with
`--check-page`); browser QA ≈25 s / ≈15 s per suite.

Failure is loud and non-destructive: failed ingest checks publish nothing; the service-area assembler
prints `COVERAGE ASSEMBLY FAILED - nothing written`; the API exits `1` on contract drift and `2` on
seed inconsistency (nothing written).

## Build order, quickstart and CI

Run the stages in dependency order (the README quickstart order):

```bash
python3 -m pip install -r requirements.txt     # PyYAML + markdown-it-py
python3 tools/build-geo.py                     # optional; network only on first cached fetch
python3 tools/build-service-areas.py           # must run before ingest
python3 tools/ingest-doe-rates.py              # add --refresh to re-fetch the four tabs
python3 tools/build-api.py                     # add --sync-openapi to refresh volatile spec blocks
python3 tools/build-docs.py                    # -> draft/docs/
python3 tools/build-map-page.py                # -> draft/map-table-prototype.html
python3 tools/build-preview.py                 # -> preview/ (gitignored review hub)
python3 tools/validate.py --check-page         # offline contracts + deterministic rebuild proof
npm ci && npx playwright install chromium      # once, for browser QA
node tests/qa.mjs                              # page behaviour
node tests/qa-docs.mjs                         # docs site crawl
```

Flags: `--refresh` (ingest/geo), `--sync-openapi` (API volatile spec blocks), `--check-page` /
`--strict` / `--verbose` / `--timeout` (validation). Environment: `OPEN_ENERGY_RETRIEVED_AT`
(reproduce an ingest timestamp), `OPEN_ENERGY_SITE_URL` (page canonical origin), `GEO_BUILD_CACHE`.

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every push/PR to `main` without
fetching source data — committed snapshots and generated trees are the inputs:

| Job | Steps |
|---|---|
| **Static validation and deterministic build** (Python 3.12) | rebuild the service areas and fail on any `data/seed/` diff; `validate.py`; `validate.py --check-page`; rebuild the API and fail on any diff/untracked file under `draft/api/`; rebuild the docs and fail on any diff/untracked file under `draft/docs/` |
| **Browser QA (Chromium)** (after validation) | build page + docs from source; `npm ci` + Playwright Chromium; `node tests/qa.mjs`; `node tests/qa-docs.mjs`; upload screenshots/results as artifacts even on failure |

CI enforces the determinism rules: tracked generated trees must rebuild byte-identically or the build fails.

## Hosting and deployment model

Everything after the build is served as plain static files. **No public deployment exists**; the page,
docs and API are static artefacts that *can* be served by any host, and the review pack is local.

| Artefact | How it is served | Deployment status |
|---|---|---|
| Page `draft/map-table-prototype.html` | opened directly (`file://`) or on any static host/CDN; self-contained with a strict CSP | not deployed; no public URL recorded |
| Docs site `draft/docs/` | any static host or `file://`; same-origin/inline assets only | not deployed; browsable locally |
| API `draft/api/v1/` | any static file server; GET-only files, no auth, no query layer | **contract + static mirror, not a live service** |
| Review pack `preview/` | local static server (`python3 -m http.server`), tailnet via `tailscale serve` — **not** `funnel` | local review only; gitignored, never public |

The API's `servers` entry is the **relative** URL `api/v1` (no leading slash), so it resolves against
wherever the files are served rather than an invented domain; proposed hostnames in the contract are
not live services. When a host exists, documented conventions apply: CORS
`Access-Control-Allow-Origin: *`, `Cache-Control: public, max-age=300, s-maxage=3600` (files are
immutable within a `dataset_version`), and the host's own 404 for unknown paths. `OPEN_ENERGY_SITE_URL`
sets the canonical/Open Graph origin at page build time; leaving it unset avoids a fabricated URL.
README's *Deployment status* section records the URL, host, dataset version and API base URL once they
exist; review-pack operational notes live in `preview/README.md`.

## How to change the backend safely

### The change loop

1. **Find the owning stage** below; edit the *source* (builder, markdown, OpenAPI, research evidence,
   asset), never the generated bytes.
2. **Rebuild that stage and every downstream stage** in dependency order, then **inspect the generated
   diff** — only bytes your change should affect may move.
3. **Prove the contracts:** `python3 tools/validate.py` (add `--check-page` when the page builder or
   its inputs changed), then `node tests/qa.mjs` and, when page or docs changed, `node tests/qa-docs.mjs`.
4. **Update the human documentation** in the same change (README, CONTRIBUTING, the
   [seed data dictionary](../data/seed/README.md), [data-model.md](data-model.md),
   [api-docs.md](api-docs.md), [NOTICE](../NOTICE.md)) and check scope with `git status --short` —
   only intended files, never `preview/`, `node_modules/`, QA artifacts or generated bytes.

### Where a change lands

| Change | Edit | Rebuild and verify |
|---|---|---|
| New data retrieval | (network) | ingest `--refresh` → API → docs → page → preview → `validate.py` → QA |
| Parsing, states, conflicts, anchors | `tools/ingest-doe-rates.py` + its checks | ingest → API → page → `validate.py` → QA |
| Service-area evidence or fallback rules | `research/coverage/**`, `research/service-areas.json`, assembler | service areas → ingest → API → page → docs → `validate.py` |
| Geometry (pinned inputs only) | `tools/build-geo.py` | geo → service areas → ingest → API → page → `validate.py --check-page` → QA |
| Seed columns/semantics | producing builder + data dictionary + `data-model.md` | rebuild producers, then the whole chain |
| API response shape or routes | [openapi.yaml](openapi.yaml) + [api-docs.md](api-docs.md) + builder | `build-api.py --sync-openapi` → `validate.py` → page API-explorer QA |
| Page copy, layout, interactions | `tools/build-map-page.py` (+ `draft/assets/**`) | page → `qa.mjs` → `validate.py --check-page` |
| Docs prose or a new docs page | the markdown source; register new pages in `tools/build-docs.py` (`KNOWN_DOCS`, integration step) | `build-docs.py` → `qa-docs.mjs` |

### Never hand-edit these

| Generated artefact | Producer |
|---|---|
| `data/raw/doe-rates/**` | ingest — **immutable publisher bytes**; never edited or overwritten |
| `data/seed/*.csv`, `validation.json`, `page-data.json` | ingest (the two service-area CSVs are assembled first) |
| `draft/api/v1/**` (including `openapi.json`) | `tools/build-api.py` |
| `draft/docs/**` + `docs-manifest.json` | `tools/build-docs.py` |
| `draft/map-table-prototype.html` | `tools/build-map-page.py` |
| `draft/assets/{geo,coverage-geo}.json`, `geo-sources.json` | `tools/build-geo.py` |
| `preview/**` | `tools/build-preview.py` (gitignored) |

Inside `data/seed/` only `README.md` (data dictionary) and the illustrative `plants.csv` are
hand-maintained; everything else there is generated.

### Determinism and reproducing a fresh ingest

- Same inputs must produce the same bytes: no wall clock, randomness or unordered iteration; sorted
  collections and explicit ordering; UTF-8 + LF; JSON `indent=2` with a trailing newline; assets
  copied byte-for-byte. The only volatile metadata is provenance: ingest timestamps come from the
  snapshot (`OPEN_ENERGY_RETRIEVED_AT` reproduces them), and `geo-sources.json` records fetch/run
  times. A rebuild that changes any other byte is a signal to investigate, not commit; fix the input
  or parser rather than weakening a contract, run a builder twice and diff, and let CI's API/docs diff
  checks and `--check-page` enforce it mechanically.
- **Fresh ingest:** choose the retrieval date (it becomes `dataset_version`) → run
  `ingest-doe-rates.py --refresh` (or a first run on a new date), committing a new
  `data/raw/doe-rates/<date>/` directory → confirm `ALL CHECKS PASSED` and review the `data/seed/`
  diff → rebuild downstream (service areas if its inputs changed, API → docs → page → preview) →
  `validate.py`, `--check-page`, both QA suites. For a byte-identical rerun set the recorded
  timestamp, e.g. `OPEN_ENERGY_RETRIEVED_AT=2026-11-10T17:00:34+08:00`.
- After a data refresh, refresh the volatile OpenAPI blocks with `build-api.py --sync-openapi` (seed
  file hashes, coverage-source metadata); structural contract changes still require editing
  `openapi.yaml` itself.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `missing data/seed/service_areas.csv — run … first` | ingest ran before coverage assembly | run `build-service-areas.py`, then ingest |
| Fetch error / timeout / "suspiciously small response" | no network, blocked export, or changed workbook export | retry; reuse an existing same-date snapshot offline; investigate the source — never fabricate a snapshot |
| Snapshot SHA-256 mismatch or `seed consistency check failed` | bytes changed / wrong date directory / stale seed data | compare `sha256sum` of `data/raw/doe-rates/<date>/<gid>.csv` with [sources.csv](../data/seed/sources.csv); restore the correct snapshot (a genuine retrieval belongs in a new date directory), rebuild service areas and ingest, then the API |
| `OPENAPI CONTRACT DRIFT` (API exits `1`, payload written) | emitted files no longer match [openapi.yaml](openapi.yaml) | update the contract (and `api-docs.md` / `data-model.md`) for structural changes; `--sync-openapi` only refreshes volatile metadata; never edit `draft/api/v1/` |
| `validate.py` CSV/schema contract failure | a column or field change was not propagated | update the generator, data dictionary, `data-model.md` and the contract checks together |
| Unexpected generated diff after a rebuild, or `--check-page` fails | nondeterminism (wall clock, unordered iteration, newline/locale/format) or a stale committed page | inspect the diff, remove the source, run the builder twice; rebuild the page and commit only intended output |
| Docs build reports unresolved links / docs QA finds raw `.md` links | missing target or unregistered markdown page | fix the path; register new pages in `tools/build-docs.py` |
| Empty API explorer / explorer QA failure | API tree not built before the page | run `build-api.py` before `build-map-page.py` |
| Browser QA reports console errors, external requests or overflow | an asset was linked instead of inlined, a runtime fetch was added, or a layout regressed | inline the asset; keep outputs self-contained; only user-clicked citations leave the page |
| A new retrieval changes anchors or counts | the publisher changed values, or parsing regressed | investigate the source and diff; change checks only when the contract intentionally changes — never to silence a failure |

## Reading order and related documents

1. [README](../README.md) — product, dataset at a glance, quickstart, repository layout.
2. This page — the pipeline mental model and safe-change procedure.
3. [CONTRIBUTING](../CONTRIBUTING.md) — build commands and the non-negotiable data/page/API rules.
4. [data/seed/README](../data/seed/README.md) — the data dictionary and validation report.
5. [data-model.md](data-model.md) — entities, provenance, publication states, licensing.
6. [api-docs.md](api-docs.md) and [openapi.yaml](openapi.yaml) — the HTTP contract and its guide.
7. [tests/README](../tests/README.md) — what static validation and the browser QA suites prove.
8. [component-map.md](component-map.md) — component map with edit/build/verify contracts per artefact.
9. Root `AGENTS.md` — agent/contributor operating guide and task routing (nested maps in each area dir).
10. [NOTICE](../NOTICE.md) — third-party licences, attribution and the DOE data caveats.

Useful while debugging: `data/seed/validation.json` (checks, conflicts, hashes, anchors),
`draft/api/v1/index.json` (API catalogue) and `preview/README.md` (review-pack hosting notes).
