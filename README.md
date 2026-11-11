# Open Energy Data Layer — public data page

The public, read-only deployment of the **Open Energy Data Layer** data page:
Philippine electricity rates by distribution utility and service area, 2018 to
October 2026, built from the Department of Energy's *Electricity Rates & Power
Market Monitor* workbook.

**Live site:** <https://andrewhmir.github.io/open-energy-data-layer/>

This repository is the **deployment output**, not the project source. Every file
here is produced by the deterministic Python builders in the Open Energy Data
Layer project (`tools/build-map-page.py`, `tools/build-api.py`,
`tools/build-docs.py`); it is published here so the page, the static JSON API and
the documentation can be read without a build step. Nothing here is hand-edited
except the deployment link rewrites.

## What is served

| Path | What it is |
| --- | --- |
| `/` | The product page: national map, 141-utility price table, provider/coverage lens, comparison view and API explorer. Single self-contained HTML file — all data, fonts, brand marks and geometry inlined; no third-party runtime requests. |
| `/api/v1/` | Static, read-only JSON API (dataset metadata, health, months, latest rates, regions, utilities, service areas, sources, conflicts, validation) with `/openapi.yaml` and `/api/v1/openapi.json` as the machine contract. |
| `/docs/` | The platform documentation site (21 pages) with build-time full-text search and no runtime fetches. |
| `/data/seed/` | The published seed dataset (CSVs, validation report, page payload) — the same bytes the page and API are built from. |
| `/data/raw/doe-rates/2026-11-10/` | The immutable raw workbook snapshots (four tabs) the dataset was extracted from. |
| `/source/` | The raw source files the documentation links to (markdown sources, builder scripts, CI config) so its "download raw" actions return the actual bytes. |

## Data and provenance

- Source: Department of Energy (Philippines), *Electricity Rates & Power Market
  Monitor* workbook, retrieved **10 November 2026**; per-tab SHA-256 hashes are
  recorded in `data/seed/validation.json`.
- 141 distribution utilities and electric cooperatives, 18 PSGC regions, 106
  months with published data (January 2018 – October 2026).
- Cell states `published`, `nda`, `missing` and `invalid` are preserved exactly;
  aggregates use published values only and report the reporting count. Source
  conflicts are disclosed, never guessed.
- **No licence is asserted over the DOE workbook or the figures extracted from
  it** — reuse terms with DOE are to be confirmed. See `NOTICE.md`.
- This is an independent open-data project. It is **not** an official Department
  of Energy or BetterGov.ph publication, and nothing here is financial or
  regulatory advice.

## Licence

The project's own code, the generated page and its design layer are MIT licensed
(`LICENSE`). Third-party assets (fonts, icons, geometry, brand marks) and the DOE
data carry their own terms, documented in `NOTICE.md`; the MIT licence does not
override them. The page's design language is adapted from BetterGovPH's
MIT-licensed `transparency-portal`.

## Rebuilding

This repository is generated. To reproduce it, build the upstream project
(`tools/ingest-doe-rates.py` → `tools/build-api.py` → `tools/build-docs.py` →
`tools/build-map-page.py`) and copy `draft/map-table-prototype.html` to
`index.html` plus `draft/api/`, `draft/docs/`, `draft/openapi.yaml`, `data/seed/`
and the latest `data/raw/doe-rates/<date>/`, rewriting the page's repo-relative
links (`href="../data/` → `href="data/`) and the documentation's
`../../<repo path>` links to their deployed locations.
