# Component map & agent guide

This repository is a deterministic static-build pipeline: raw DOE workbook snapshots
become validated seed data, which becomes a single-file product page, a read-only
static JSON API, a generated docs site and a local review pack. Nothing is served by
an application server — every artefact is a file produced by a Python builder.

Use this page to find **where to edit** and **what to run**. It is the human version
of the repository's `AGENTS.md` maps; the same content drives coding agents. The
rendered copy lives at `/docs/component-map.html`; the markdown source is
`draft/component-map.md`, registered in the docs builder's `KNOWN_DOCS` registry
(`tools/build-docs.py`) so it renders with the rest of the docs site.

> **Note.** Every command below is meant to be run from the repository root. Build
> outputs under `data/seed/`, `draft/`, `preview/` and `/tmp/qa-*` are generated —
> edit the source, never the artefact.

## Components at a glance

| Component | Source of truth (edit here) | Build(command) | Generated output | Verification |
|---|---|---|---|---|
| Product page | `tools/build-map-page.py`; `data/seed/page-data.json`; `draft/assets/**` | `python3 tools/build-map-page.py` | `draft/map-table-prototype.html` (tracked, single file) | `node tests/qa.mjs`; `python3 tools/validate.py --check-page` |
| Ingest pipeline | `tools/ingest-doe-rates.py` | `python3 tools/ingest-doe-rates.py [--refresh]` | `data/raw/doe-rates/<date>/`; `data/seed/{utilities,rates_monthly,regions,sources}.csv`; `validation.json`; `page-data.json` | ingest exits 0 (17/17 checks); `python3 tools/validate.py` |
| Service areas | `tools/build-service-areas.py`; `research/coverage/**`; `research/service-areas.json` | `python3 tools/build-service-areas.py` | `data/seed/service_areas.csv`; `service_area_sources.csv` | `python3 tools/validate.py`; ingest coverage checks 7/7 |
| Geometry | `tools/build-geo.py` (pinned, SHA-256-verified release) | `python3 tools/build-geo.py` | `draft/assets/geo.json`; `coverage-geo.json`; `geo-sources.json` | `python3 tools/validate.py` (geometry group) |
| Static JSON API | `tools/build-api.py`; `draft/openapi.yaml` | `python3 tools/build-api.py [--sync-openapi]` | `draft/api/v1/**` (incl. `openapi.json` mirror) | `python3 tools/validate.py` (OpenAPI + static API); builder exit 1 = contract drift |
| Docs site | `tools/build-docs.py`; markdown sources | `python3 tools/build-docs.py` | `draft/docs/**`; `docs-manifest.json` | `node tests/qa-docs.mjs`; `python3 tools/validate.py` |
| Review pack (local, gitignored) | `tools/build-preview.py` | `python3 tools/build-preview.py` | `preview/**` | pack self-checks in `preview/README.md`; QA with `--base` / `--docs preview/docs` |
| Validation & QA | `tools/validate.py`; `tests/qa.mjs`; `tests/qa-docs.mjs` | see [Testing & validation](../tests/README.md) | `/tmp/qa-final`, `/tmp/qa-docs` only | `.github/workflows/ci.yml` |

## Dependency and build order

```text
pinned boundary release ──► build-geo.py ────────────────────────────┐
research/coverage/** + RA 12146 ──► build-service-areas.py ──────────┤
                                                                     ▼
DOE workbook tabs ──► ingest-doe-rates.py ──► data/seed/** ──► build-api.py ──► draft/api/v1/**
                                                  │
                                                  ├─► build-map-page.py ──► draft/map-table-prototype.html
                                                  └─► build-docs.py (+ markdown sources) ──► draft/docs/**
                                                                     │
                                            build-map-page.py + build-docs.py + pack sources
                                                                     ▼
                                                             build-preview.py ──► preview/

 after every change:  python3 tools/validate.py  (+ --check-page)  →  node tests/qa.mjs  →  node tests/qa-docs.mjs
```

Build order matters only where a consumer reads another builder's output: geometry
and service areas before ingest; ingest before API, docs and page; page/docs/API
before the review pack. CI itself rebuilds service areas, the API tree and the docs
tree to prove no committed output is stale.

## Agent entry points

| Map file (repo markdown) | Covers | Start here when… |
|---|---|---|
| `AGENTS.md` (repo root) | orientation, component table, task routing, cross-cutting invariants, finish checklist | you are new to the repository or coordinating across areas |
| `tools/AGENTS.md` | builder-by-builder inputs/outputs/flags/network/determinism, run order, shared conventions, adding a builder | you touch `tools/` or the build chain |
| `data/AGENTS.md` | raw → seed → derived provenance, immutable vs generated files, hashes/licences, regeneration pitfalls | you touch data, snapshots, coverage or provenance |
| `draft/AGENTS.md` | generated page/docs/API/assets vs their sources, edit-vs-regenerate decisions | you touch published artefacts |
| `tests/AGENTS.md` | validation + QA suites, pinned contract inventory, artifacts, how to add a check, CI | you change a contract or a test |
| `draft/component-map.md` | this page — the human rendering of the maps above | you prefer one page with links |

The `AGENTS.md` files are repository markdown read by coding agents; this page is
their rendered, human-facing counterpart.

## Task routing — "I am changing…"

| Change | Read first | Build and verify |
|---|---|---|
| Page UI, layout, interactions, accessibility | [Frontend guide](frontend.md), `draft/AGENTS.md`, [`draft/assets/README.md`](assets/README.md) | `build-map-page.py` → `node tests/qa.mjs` → `validate.py --check-page` |
| Data pipeline, parsing, anchors, conflicts | [`data/seed/README.md`](../data/seed/README.md), `data/AGENTS.md`, "Data rules" in [Contributing](../CONTRIBUTING.md) | `ingest-doe-rates.py` → review `data/seed/` diff → `validate.py` |
| Service areas / provider coverage | `data/AGENTS.md`, `research/coverage/README.md`, coverage section in [Notices](../NOTICE.md) | `build-service-areas.py` → `ingest-doe-rates.py` → `validate.py` |
| API, schema or contract | [Backend guide](backend.md), [`draft/openapi.yaml`](openapi.yaml), [API guide](api-docs.md), [Data model](data-model.md) | `build-api.py` → `validate.py` → page API-explorer QA |
| Docs site content or chrome | `draft/AGENTS.md`, registry + renderer in `tools/build-docs.py` | `build-docs.py` → `node tests/qa-docs.mjs` |
| Review pack / separation chrome | `preview/README.md`, `tools/build-preview.py` | `build-preview.py` → pack self-checks → QA with `--base` |
| Tests or a pinned contract | [`tests/README.md`](../tests/README.md), `tests/AGENTS.md` | `validate.py` → `qa.mjs` → `qa-docs.mjs` |
| Geometry or boundary update | `tools/build-geo.py` (pinned release only), [`draft/assets/README.md`](assets/README.md) | `build-geo.py` → rebuild page → full QA + `validate.py` |

## Cross-cutting invariants

1. **Deterministic, byte-identical builds.** No wall clock, randomness or unordered
   iteration in output; CI diffs `draft/api` and `draft/docs`, and
   `validate.py --check-page` rebuilds the page twice and compares it to the
   committed file.
2. **Generated files are read-only.** `data/raw/**` is immutable publisher bytes;
   `data/seed/**`, `draft/map-table-prototype.html`, `draft/api/v1/**`,
   `draft/docs/**` and `draft/assets/{geo,coverage-geo}.json` are generated. Fix the
   generator and rebuild.
3. **Self-contained output.** The page and docs inline fonts, brand, geometry and
   data; no CDN, web font, analytics or `fetch`/XHR. Outbound traffic exists only
   when a reader clicks a citation link; QA asserts zero external/third-party
   requests.
4. **Provenance, no imputation.** `published` / `nda` / `missing` / `invalid` are
   preserved as distinct states; aggregates use published values only and carry the
   reporting count; every value has a source row and a SHA-256 over the raw bytes.
5. **Hard separation: data platform ≠ fellowship submission.** The data platform
   documented here contains no submission material; submission sources
   (`plan/fellowship-proposal.md`, `plan/application-answers.md`,
   `research/pitch-deck-notes.md`) render only on the review pack's submission
   pages. Both QA suites and `validate.py` enforce the separation.
6. **Accessibility and pinned contracts.** Desktop **and** mobile, semantic
   landmarks/labels, visible focus, full keyboard operation; pinned ids, roles and
   counts are contracts shared by builder, validator, QA and docs.

## Where the contracts are enforced

| Contract | Enforced by |
|---|---|
| Seed payload / CSV / anchor counts; page payload equality | `tools/validate.py` (required files, payload, CSV groups) + `tools/ingest-doe-rates.py` asserts |
| Page markup, ids, no external refs, no submission surfaces | `tools/validate.py` (page group) + `tests/qa.mjs` |
| Service areas / provider lens (1,648 LGU + 17 barangay rows, 1,642 polygons, Meralco 108 LGUs) | `tools/build-service-areas.py` checks + `tools/validate.py` (service areas) + `tests/qa.mjs` |
| Docs manifest, page counts, links/fragments, separation | `tests/qa-docs.mjs` + `tools/validate.py` (docs group) |
| OpenAPI 3.1 validity and mirror consistency | `tools/build-api.py` (exit 1 on drift) + `tools/validate.py` (OpenAPI group) |
| Static API envelopes and dataset version | `tools/validate.py` (static API group) |
| Determinism | CI diff steps + `tools/validate.py --check-page` + `tools/build-api.py`/`build-docs.py` two-run guarantees |
| Data-platform/submission separation | `tools/validate.py` + `[separation]` groups in both QA suites |

## Further reading

- [Project README](../README.md) — product, dataset, quickstart, build order.
- [Frontend guide](frontend.md) — how the product page is built and tested.
- [Backend guide](backend.md) — data pipeline, seed data and API layer.
- [Data model](data-model.md) — canonical entities, IDs, provenance and licensing.
- [API guide](api-docs.md) — the static JSON API: access, units, endpoints.
- [Testing & validation](../tests/README.md) — the three QA layers and what they prove.
- [Seed data dictionary](../data/seed/README.md) — column-by-column published data.
- [Design assets](assets/README.md) — fonts, brand, icons, geometry provenance.
- [Contributing](../CONTRIBUTING.md) — setup, build commands and the review checklist.
- [Notices & attribution](../NOTICE.md) — third-party terms, brand and data licences.

Live review pack (tailnet): <https://devvm1.tailf19a1a.ts.net/> — submission and
review material, clearly separated from the data-platform pages.
