# Open Energy Data Layer — Philippine Electricity Rates Data API

A small, public, read-only JSON API over the DOE **Electricity Rates & Power Market Monitor**
workbook: monthly average electricity rates for residential, commercial, industrial and blended
generation-charge customers across **141** distribution utilities and electric cooperatives in
**18** PSA PSGC regions, **107** monthly columns from **2018-01** to **2026-11** (latest published
month **2026-10**). Built from the same snapshot as this page by `tools/build-api.py`.

The API is a set of plain JSON files, not a running service: every endpoint below is one file under
`api/v1/`, served read-only with no authentication. The contract is `openapi.yaml` (OpenAPI 3.1);
the machine-readable catalog is `api/v1/index.json`.

---

## Overview

| | |
|---|---|
| **API version** | `1.0` (contract version, stable across dataset snapshots) |
| **Dataset version** | `2026-11-10` (retrieval date; changes with every new snapshot) |
| **Latest published month** | `2026-10` (the source's 2026-11 column is not yet published) |
| **Coverage** | 141 utilities/electric cooperatives · 18 PSGC regions · 4 customer classes · 107 months |
| **Service-area coverage** | 141 utilities — 141 with LGU-level rows, 0 with barangay-only rows, none needing the region fallback |
| **Endpoints** | 19 static GET routes: 17 rate/quality/source + 2 provider service-area |
| **Rate unit** | `PHP per kWh` — the published monthly average, exact to the source's two decimals |
| **Upstream source** | Department of Energy (DOE), *Electricity Rates & Power Market Monitor* |
| **Source retrieved** | `2026-11-10T17:00:34+08:00` (CSV export of the public Google Sheet) |
| **Licence** | **Not stated by publisher** — see [Sources & attribution](#sources--attribution) |
| **Auth** | None. Public read; fair-use conditions apply. |
| **Format** | Static JSON files with a `{meta, data, next_cursor}` envelope |

What it is: a provenance-first view of the DOE workbook with stable utility codes, PSGC geography,
explicit source states and checksums behind every value — plus a sourced **provider service-area
(coverage) layer** for the page's provider filter, with per-row provenance, its own source registry
and its own licences. Coverage is derived data, not a DOE rate publication.

What it is not: an official DOE product; a live feed; a query API (there are no query parameters);
a bill-component breakdown (generation, transmission, system loss, distribution, subsidies,
FIT-All and taxes are not in the source); and it contains **no imputed, interpolated or modelled
values**.

---

## Base URL & access

The API is not hosted as a service yet. The canonical origin is set at deployment; in this
repository the files are served at `api/v1/` (relative to this `draft/` directory), which the page
links to directly. No domain is invented here. The OpenAPI server URL is the relative `api/v1`
(no leading slash), so it resolves against wherever the spec or page is served, not the host
root.

All requests are `GET` (or `HEAD`) on static files:

* **No authentication**, no API key, no request body.
* **CORS**: when served by the deployment host, responses should carry
  `Access-Control-Allow-Origin: *`, following the BetterGov Budget API convention.
* **Caching**: responses should carry `Cache-Control: public, max-age=300, s-maxage=3600`.
  Every file is immutable within a `dataset_version`, so aggressive client-side caching is safe.
* **Fair use**: identify heavy automated use with a descriptive `User-Agent`.
* **Errors**: a path that is not a served file returns the host's normal 404. This snapshot has no
  JSON error envelope; the machine-readable error format (`bad_request`, `not_found`,
  `method_not_allowed`, …) is reserved for a future dynamic deployment.

```bash
# Relative to this draft/ directory; prepend the deployment origin when hosted.
curl -s api/v1/meta.json | jq '.data.coverage'
curl -s api/v1/rates/latest/residential.json | jq '.data.stats'
curl -s api/v1/utilities/MERALCO.json | jq '.data.series.residential.counts'
curl -s api/v1/regions/1300000000.json | jq '.data.region'
curl -s api/v1/changes/latest.json | jq '.data.movements[0]'
curl -s api/v1/sources/SRC-DOE-RATES.json | jq '.data.tabs'
curl -s api/v1/service-areas.json | jq '.data.coverage'
curl -s api/v1/service-areas/MERALCO.json | jq '.data.rows[:2]'
```

---

## Datasets & units

| Dataset | Key | Coverage | What it is |
|---|---|---|---|
| Rates by customer class | `rates/latest/{class}.json` | 2026-10 column, 141 utilities, 4 classes | The newest published monthly average per utility, with explicit non-published states |
| Utility registry | `utilities.json` | 141 entities | Stable `utility_code`, name, type, grid connection, PSGC region, latest/previous month cells |
| Utility series | `utilities/<CODE>.json` | 2018-01 → 2026-11 | Full monthly series per utility and customer class, grouped by source state |
| Service areas / provider coverage | `service-areas.json`, `service-areas/<CODE>.json` | 1,648 LGU rows · 17 barangay rows · 0 region fallbacks | The sourced service area of every utility (LGU / barangay / region fallback), with per-row provenance and per-source licences |
| Region aggregates | `regions.json`, `regions/<psgc>.json` | 18 PSGC regions | Latest-month medians/means/ranges and member utilities |
| Month coverage | `months.json` | 107 months | Published / NDA / missing / invalid counts per class per month |
| Changes | `changes/latest.json` | 2026-09 → 2026-10 | Month-over-month movements and state changes |
| Quality | `validation.json`, `conflicts.json` | snapshot | The 17 rate checks, 7 coverage checks and the 5 recorded source conflicts |
| Source | `sources.json`, `sources/SRC-DOE-RATES.json` | 1 rate source + 4 coverage sources | DOE workbook identity, links, per-tab SHA-256 and retrieval provenance; the coverage-source registry with licences |

**Units.** Every rate is in **PHP per kWh** (`currency: "PHP"`, `unit: "PHP per kWh"` in every
`meta`). No rescaling, no rounding beyond the source's own two decimals. Amounts are averages as
published; they are not bills and not estimates.

**Identifiers.** `utility_code` is this dataset's stable slug (e.g. `MERALCO`, `ABRECO`) — not an
official DOE/ERC/NEA identifier. `region_psgc` is the 10-digit PSA PSGC region code (e.g.
`1300000000` for NCR). Months are `YYYY-MM`. Coverage rows join the same geography through
`region_psgc` / `province_psgc` / `adm3_psgc` / `adm4_psgc` (canonical 10-digit PSGC); the API
publishes coverage areas as codes, not as polygons.

**Explicit source states.** Every utility/class/month cell has exactly one state:

| State | Meaning |
|---|---|
| `published` | The source workbook has a numeric rate; it is published here as-is. |
| `nda` | "No Data Available", as published by the source. Never zero, never estimated. |
| `missing` | The month column exists but the cell is blank / not yet published (all of 2026-11). |
| `invalid` | The cell failed extraction validation; no value is published for it (1 cell in 2026-10). |

`null` never means zero. An aggregate is only computed over `published` values.

---

## Conventions

### Envelope

Every data file returns the same envelope:

```json
{
  "meta": {
    "api_version": "1.0",
    "dataset": "doe-electricity-rates",
    "dataset_version": "2026-11-10",
    "latest_month": "2026-10",
    "generated_at": "2026-11-10T17:00:34+08:00",
    "currency": "PHP",
    "unit": "PHP per kWh",
    "source": {
      "id": "SRC-DOE-RATES",
      "publisher": "Department of Energy (DOE)",
      "title": "Electricity Rates & Power Market Monitor",
      "canonical_url": "https://doe.gov.ph/data-and-prices/electricity",
      "retrieved_at": "2026-11-10T17:00:34+08:00",
      "extraction_method": "csv_export"
    },
    "attribution": "Source: Department of Energy (DOE) — Electricity Rates & Power Market Monitor, retrieved 2026-11-10T17:00:34+08:00. …",
    "licence": { "name": "Not stated by publisher", "note": "…", "url": null },
    "service_area": {
      "detail_counts": { "total": 141, "lgu": 141, "barangay": 0, "region": 0 },
      "sources": [{ "source_id": "SRC-RA-12146", "licence": { "name": "Public document (Philippine law)", "url": null } }, "…"],
      "note": "Service-area coverage is derived data, not a DOE rate publication; see /v1/service-areas.json."
    },
    "disclaimers": [{ "id": "disclaimer-unofficial", "title": "Unofficial compilation.", "text": "…", "url": "#disclaimers" }],
    "count": 141
  },
  "data": { "…": "endpoint-specific payload" },
  "next_cursor": null
}
```

* `meta.count` is the number of primary records in `data` (rows for a list, months for the month
  series, `1` for a single record).
* `next_cursor` is **always `null`** in this static snapshot: there is no pagination and no query
  layer. The field is reserved so a future dynamic deployment can paginate without breaking
  clients.
* `meta.service_area` states the coverage context: how many utilities are covered at LGU,
  barangay or region level, and which sources (with their licences) back the layer. Coverage is
  derived data, not a DOE rate publication — see `disclaimer-coverage`.
* `api/v1/index.json` (the catalog) and `api/v1/openapi.json` (the contract) are documents, not
  envelope responses.

### Errors

Static files do not emit JSON errors; unknown paths are the host's 404. A future dynamic deployment
can adopt the BetterGov Budget API error shape — `{ "error": "not_found", "message": "…" }` with
slugs `bad_request`, `bad_cursor`, `not_found`, `method_not_allowed`, `not_loaded`, `query_failed` —
without changing any success payload.

### Versioning

`api_version` (`1.0`) is the JSON contract version. `dataset_version` (`2026-11-10`) is the retrieval
date; a new snapshot gets a new `dataset_version` and the old files are never silently rewritten.
The changelog is `x-changelog` in `openapi.yaml` (contract 1.0.0 / dataset 2026-11-10; the v1.1
service-area coverage layer is an **additive** change — 19 routes now, but the envelope and every
rate endpoint are unchanged).

---

## Endpoint reference

All paths are GET-only static files and every served path ends in `.json`; prepend the deployment
origin or, in this repository, read them relative to `draft/`. Nineteen routes: 17 discovery,
rate, quality, utility, region, change and source routes, plus 2 provider service-area routes.
Four routes are per-entity file families — the catalog (`api/v1/index.json`) names a concrete
example file for each (`/v1/utilities/MERALCO.json`, `/v1/service-areas/MERALCO.json`,
`/v1/regions/1300000000.json`, `/v1/sources/SRC-DOE-RATES.json`); substitute the entity code to
read any member, e.g. `api/v1/service-areas/<CODE>.json` (141 files).

### Meta & quality

| Endpoint | File | Returns |
|---|---|---|
| `GET /v1/meta.json` | [`api/v1/meta.json`](api/v1/meta.json) | Full dataset metadata: rate source, licence, coverage, identifiers, status vocabulary, service-area block, seed-file checksums |
| `GET /v1/health.json` | [`api/v1/health.json`](api/v1/health.json) | Build identity and the rate + coverage quality check results |
| `GET /v1/months.json` | [`api/v1/months.json`](api/v1/months.json) | 107 month columns and per-class published/nda/missing/invalid counts |
| `GET /v1/validation.json` | [`api/v1/validation.json`](api/v1/validation.json) | The 17 rate checks and the 7 coverage checks run against the snapshot (all pass) |
| `GET /v1/conflicts.json` | [`api/v1/conflicts.json`](api/v1/conflicts.json) | 5 recorded source conflicts and how each was resolved |

```json
// api/v1/health.json → data
{
  "status": "ok",
  "snapshot": true,
  "dataset_version": "2026-11-10",
  "latest_month": "2026-10",
  "prev_month": "2026-09",
  "checks": {
    "validation": 17, "validation_passed": 17, "validation_failed": 0,
    "utilities": 141, "regions": 18, "months": 107, "rate_rows": 60348
  }
}
```

### Rates

| Endpoint | File | Returns |
|---|---|---|
| `GET /v1/rates/latest.json` | [`api/v1/rates/latest.json`](api/v1/rates/latest.json) | Index of the four class files with stats, sizes and SHA-256 |
| `GET /v1/rates/latest/residential.json` | [`api/v1/rates/latest/residential.json`](api/v1/rates/latest/residential.json) | 2026-10 residential cell for all 141 utilities |
| `GET /v1/rates/latest/commercial.json` | [`api/v1/rates/latest/commercial.json`](api/v1/rates/latest/commercial.json) | 2026-10 commercial cell for all 141 utilities |
| `GET /v1/rates/latest/industrial.json` | [`api/v1/rates/latest/industrial.json`](api/v1/rates/latest/industrial.json) | 2026-10 industrial cell for all 141 utilities |
| `GET /v1/rates/latest/generation.json` | [`api/v1/rates/latest/generation.json`](api/v1/rates/latest/generation.json) | 2026-10 blended generation-charge cell for all 141 utilities |

```json
// api/v1/rates/latest/residential.json → data (abridged: 2 of 141 rows)
{
  "month": "2026-10",
  "previous_month": "2026-09",
  "customer_class": "residential",
  "unit": "PHP per kWh",
  "stats": { "reporting": 113, "nda": 27, "missing": 0, "invalid": 1,
             "total": 141, "mean": 13.23, "median": 12.72, "min": 5.33, "max": 19.36 },
  "rows": [
    { "code": "ABRECO", "name": "ABRECO", "region_short": "CAR", "type": "EC", "grid": "ONGRID",
      "value": 12.58, "status": "published", "previous_value": 12.57, "change_pct": 0.1 },
    { "code": "AEC", "name": "AEC", "region_short": "Region III", "type": "PIOU", "grid": "ONGRID",
      "value": 12.31, "status": "published", "previous_value": 11.84, "change_pct": 4.0 }
  ]
}
```

### Utilities

| Endpoint | File | Returns |
|---|---|---|
| `GET /v1/utilities.json` | [`api/v1/utilities.json`](api/v1/utilities.json) | Registry of 141 utilities: identity, PSGC region, type, grid, latest/previous cells, compact coverage summary |
| `GET /v1/utilities/{code}.json` | [`api/v1/utilities/<CODE>.json`](api/v1/utilities/MERALCO.json) | One utility with all four full monthly series and the full `service_area` block (141 files) |

```json
// api/v1/utilities/MERALCO.json → data (abridged series)
{
  "utility": { "code": "MERALCO", "name": "MERALCO", "type": "PIOU", "grid": "ONGRID",
               "psgc": "1300000000", "region_short": "NCR", "region_name": "National Capital Region",
               "data_status": "published",
               "latest": { "residential": 15.06, "commercial": 12.88, "industrial": 11.33, "generation": 10.2 },
               "res_delta_pct": 2.2, "source_row": 18,
               "coverage": { "detail": "lgu", "source_ids": ["SRC-RA-12146"],
                             "regions": ["0300000000", "0400000000", "1300000000"],
                             "lgu_count": 108, "province_count": 10, "barangay_count": 17 } },
  "coverage": { "months_total": 107, "first_month": "2018-01", "last_month": "2026-11",
                "latest_month": "2026-10", "previous_month": "2026-09" },
  "series": {
    "residential": {
      "counts": { "published": 106, "nda": 0, "missing": 1, "invalid": 0, "total": 107 },
      "first_published_month": "2018-01",
      "last_published_month": "2026-10",
      "published": { "2018-01": 9.04, "2018-02": 10.11, "…": "…" },
      "nda": [], "missing": ["2026-11"], "invalid": []
    }
  }
}
```

Utility-level totals in `api/v1/utilities.json`: `EC` 120, `PIOU` 21; `ONGRID` 118, `OFFGRID` 21,
`CONFLICT` 2 (published unresolved, never guessed); data status `published` 113, `partial` 4,
`nda` 24.

### Service areas

| Endpoint | File | Returns |
|---|---|---|
| `GET /v1/service-areas.json` | [`api/v1/service-areas.json`](api/v1/service-areas.json) | Coverage registry: one item per utility with a compact coverage summary, the coverage-source registry (franchise law, DOE fallback, OSM Wiki / Wikipedia) with licences, and aggregate stats |
| `GET /v1/service-areas/{code}.json` | [`api/v1/service-areas/<CODE>.json`](api/v1/service-areas/MERALCO.json) | One utility's published coverage rows (LGU / barangay / region fallback) with the PSGC hierarchy and a per-row `source_id` (141 files) |

```json
// api/v1/service-areas/MERALCO.json → data (abridged: 2 of 125 rows, 1 source)
{
  "utility": { "code": "MERALCO", "name": "MERALCO", "type": "PIOU", "grid": "ONGRID",
               "psgc": "1300000000", "region_short": "NCR", "region_name": "National Capital Region",
               "data_status": "published" },
  "service_area": { "detail": "lgu", "source_ids": ["SRC-RA-12146"],
                    "regions": ["0300000000", "0400000000", "1300000000"],
                    "lgu_count": 108, "province_count": 10, "barangay_count": 17,
                    "provinces": [ { "psgc": "0301400000", "name": "Bulacan",
                                     "region_psgc": "0300000000", "lgu_count": 24 }, "…" ],
                    "lgus": ["0301401000", "0301402000", "…"],
                    "barangays": [ { "adm4": "0305402001", "name": "Balucuc",
                                     "lgu": "0305402000", "lgu_name": "Apalit" }, "…" ],
                    "barangay_provinces": ["Pampanga"],
                    "note": "…" },
  "rows": [
    { "utility_code": "MERALCO", "area_level": "lgu", "source_id": "SRC-RA-12146",
      "region_psgc": "0300000000", "region_short": "Region III", "region_name": "Central Luzon",
      "province_psgc": "0301400000", "province_name": "Bulacan",
      "adm3_psgc": "0301401000", "lgu_name": "Angat",
      "adm4_psgc": null, "barangay_name": null,
      "coverage_note": null },
    { "utility_code": "MERALCO", "area_level": "barangay", "source_id": "SRC-RA-12146",
      "region_psgc": "0300000000", "region_short": "Region III", "region_name": "Central Luzon",
      "province_psgc": "0305400000", "province_name": "Pampanga",
      "adm3_psgc": "0305402000", "lgu_name": "Apalit",
      "adm4_psgc": "0305402001", "barangay_name": "Balucuc",
      "coverage_note": "barangay-level franchise area (Pampanga): 17 of 22 LGUs have no whole-LGU coverage" }
  ],
  "sources": [ { "source_id": "SRC-RA-12146", "short_title": "Republic Act No. 12146 (Meralco franchise)",
                 "licence": { "name": "Public document (Philippine law)", "url": null, "note": "…" },
                 "used_for": { "rows": 125, "utilities": 1, "rows_by_area_level": { "lgu": 108, "barangay": 17 } }, "…": "…" } ],
  "notes": ["…"]
}
```

### Regions

| Endpoint | File | Returns |
|---|---|---|
| `GET /v1/regions.json` | [`api/v1/regions.json`](api/v1/regions.json) | 18 PSGC regions with latest-month medians/means/ranges and reporting counts |
| `GET /v1/regions/{psgc}.json` | [`api/v1/regions/<psgc>.json`](api/v1/regions/1300000000.json) | One region plus its member utilities (18 files) |

```json
// api/v1/regions/1300000000.json → data.region
{ "psgc": "1300000000", "name": "National Capital Region", "short": "NCR", "island": "Luzon",
  "sheet_label": "NCR", "utility_count": 1, "reporting": 1,
  "res_median": 15.06, "res_mean": 15.06, "res_min": 15.06, "res_max": 15.06,
  "com_median": 12.88, "ind_median": 11.33, "gen_median": 10.2 }
```

### Changes

| Endpoint | File | Returns |
|---|---|---|
| `GET /v1/changes/latest.json` | [`api/v1/changes/latest.json`](api/v1/changes/latest.json) | 374 month-over-month movements and 66 state changes between 2026-09 and 2026-10 |

```json
// api/v1/changes/latest.json → data (abridged: 2 of 374 movements)
{
  "from_month": "2026-09", "to_month": "2026-10",
  "counts": { "movements": 374, "availability_changes": 66 },
  "movements": [
    { "code": "LEYECO-II", "name": "LEYECO II", "region_short": "Region VIII",
      "customer_class": "residential", "from_value": 14.05, "to_value": 10.44,
      "delta_php_kwh": -3.61, "delta_pct": -25.7 },
    { "code": "MOELCI-II", "name": "MOELCI II", "region_short": "Region X",
      "customer_class": "residential", "from_value": 12.83, "to_value": 15.32,
      "delta_php_kwh": 2.49, "delta_pct": 19.4 }
  ]
}
```

### Sources

| Endpoint | File | Returns |
|---|---|---|
| `GET /v1/sources.json` | [`api/v1/sources.json`](api/v1/sources.json) | The source registry (1 record): DOE workbook identity, links, per-tab SHA-256, retrieval provenance |
| `GET /v1/sources/{source_id}.json` | [`api/v1/sources/SRC-DOE-RATES.json`](api/v1/sources/SRC-DOE-RATES.json) | One full source record |

```json
// api/v1/sources/SRC-DOE-RATES.json → data (abridged)
{ "id": "SRC-DOE-RATES", "publisher": "Department of Energy (DOE)",
  "title": "Electricity Rates & Power Market Monitor",
  "canonical_url": "https://doe.gov.ph/data-and-prices/electricity",
  "workbook_url": "https://docs.google.com/spreadsheets/d/1oGc1iGpacELS6tkHjesvAeKZo8v2iv4UkYFY04e0p-I",
  "retrieved_at": "2026-11-10T17:00:34+08:00", "extraction_method": "csv_export",
  "tabs": [ { "gid": 0, "customer_class": "residential", "rows": 141,
              "sha256": "17c746168e77f045891d5d3c7ade147b172396de952ae88952ca04b30bb35718" } ] }
```

---

## Service areas & provider coverage

The DOE workbook assigns each utility exactly **one** region. That is enough to filter by region,
but it is not the utility's service area: an electric cooperative usually covers a handful of
municipalities, and Meralco's franchise spans three regions. The coverage layer publishes a
**sourced, row-level service area** so the provider filter can show what a utility actually covers
and every coverage row can be traced to a source. It is derived data, not a DOE rate publication.

| Object | Where | Shape |
|---|---|---|
| Coverage summary | `meta.service_area` in every response; `utilities.json` rows | `{detail, source_ids, regions, lgu_count, province_count, barangay_count}` |
| Full coverage | `utilities/<CODE>.json` → `service_area`; `service-areas/<CODE>.json` → `service_area` | summary + `provinces[]`, `lgus[]`, `barangays[]`, `barangay_provinces[]`, `note` |
| Coverage rows | `service-areas/<CODE>.json` → `rows[]` (published from the seed CSV) | `utility_code`, `area_level`, `source_id`, `region_psgc`/`region_short`/`region_name`, `province_psgc`/`province_name`, `adm3_psgc`/`lgu_name`, `adm4_psgc`/`barangay_name`, `coverage_note` |
| Source registry | `service-areas.json` → `sources[]`; `sources.json` → `coverage_sources[]`; `meta.json` → `service_area.sources[]` | `{source_id, short_title, publisher, dataset_title, page_url, revision_id, retrieved_at, licence {name, url, note}, attribution, notes, used_for {rows, utilities, rows_by_area_level}}` |

`area_level` is one of:

* `lgu` — one covered city/municipality (`adm3_psgc`, canonical 10-digit PSGC).
* `barangay` — one covered barangay (`adm4_psgc`), used where the franchise grants barangays only.
* `region` — a single fallback row that repeats the DOE workbook region when no LGU-level source
  is available. It means "not sourced at LGU level", never "one LGU".

Coverage at this snapshot: 141 of 141 utilities have LGU-level coverage, 0 have barangay-only coverage and 0 publish only the region-level fallback (1,648 LGU rows, 17 barangay rows, 0 fallback rows, 1,602 distinct LGUs, 10 multi-region utilities). The registry (abridged: 1 of 141 utilities,
1 of 4 sources):

```json
// api/v1/service-areas.json → data (abridged)
{
  "coverage": {
    "utilities_total": 141,
    "utilities_with_lgu_coverage": 141,
    "utilities_region_only": 0,
    "lgu_rows": 1648,
    "barangay_rows": 17,
    "region_rows": 0,
    "distinct_lgus": 1602,
    "multi_region_utilities": [
      "AURELCO",
      "BASELCO",
      "CAGELCO-II",
      "FIBECO",
      "LASURECO",
      "MERALCO",
      "PPALMA",
      "QUEZELCO-I",
      "SUKELCO",
      "ZAMSURECO-I"
    ],
    "sources": [
      "SRC-OSM-OPERATORS",
      "SRC-WIKI-DUS",
      "SRC-RA-12146",
      "SRC-DOE-RATES"
    ]
  },
  "detail_counts": {
    "total": 141,
    "lgu": 141,
    "barangay": 0,
    "region": 0
  },
  "rows_by_area_level": {
    "lgu": 1648,
    "barangay": 17,
    "region": 0
  },
  "sources": [
    {
      "source_id": "SRC-OSM-OPERATORS",
      "short_title": "OpenStreetMap Wiki operator table",
      "publisher": "OpenStreetMap Wiki contributors",
      "dataset_title": "Power networks/Philippines/Operators",
      "page_url": "https://wiki.openstreetmap.org/wiki/Power_networks/Philippines/Operators",
      "revision_id": "2836797",
      "retrieved_at": "2026-11-10T19:28:07+08:00",
      "licence": {
        "name": "CC BY-SA 2.0",
        "url": "https://creativecommons.org/licenses/by-sa/2.0/",
        "note": "Attribution required; share-alike applies to service-area coverage derived from this source."
      },
      "attribution": "© OpenStreetMap Wiki contributors, “Power networks/Philippines/Operators”, revision 2836797 (2025-04-14), CC BY-SA 2.0. Franchise areas are tabulated on that page as “per Department of Energy”.",
      "notes": "Primary source. Municipality-level franchise areas grouped by region; repeated operator rows merged. Page revision date 2025-04-14. Raw wikitext snapshot: research/coverage/snapshots/osm-wiki-2836797.wikitext",
      "used_for": {
        "rows": 1343,
        "utilities": 118,
        "rows_by_area_level": {
          "lgu": 1343
        }
      }
    }
  ],
  "utilities": [
    {
      "code": "ABRECO",
      "name": "ABRECO",
      "type": "EC",
      "region_short": "CAR",
      "region_name": "Cordillera Administrative Region",
      "coverage": {
        "detail": "lgu",
        "source_ids": [
          "SRC-OSM-OPERATORS"
        ],
        "regions": [
          "1400000000"
        ],
        "lgu_count": 27,
        "province_count": 1,
        "barangay_count": 0
      }
    }
  ],
  "notes": [
    "One item per utility. coverage.detail says the strongest published level: lgu (LGU-level rows), barangay (barangay-level rows only) or region (region-level fallback). coverage.regions lists every PSGC region the published rows touch, so a multi-region franchise is visible even when the DOE workbook lists one region."
  ]
}
```

### Coverage sources and licences

| source_id | used for | licence / terms | what to carry |
|---|---|---|---|
| `SRC-RA-12146` | MERALCO only: RA 12146 Section 1 — 108 cities/municipalities in NCR, Region III and Region IV-A, plus 17 Pampanga barangays | Public document (Philippine law); works of the Government are not subject to copyright (IP Code, Sec. 176) | cite the law (official text, Supreme Court e-Library) |
| `SRC-OSM-OPERATORS` | LGU-level service areas for the other utilities (OpenStreetMap Wiki operator table, itself compiled "per Department of Energy") | **CC BY-SA 2.0** | attribution required; **share-alike applies to coverage derived from it** |
| `SRC-WIKI-DUS` | supplementary LGU areas where the OSM table has none (Wikipedia DU list) | **CC BY-SA 4.0** | attribution + share-alike |
| `SRC-DOE-RATES` | `region` fallback rows only (DOE workbook region column) | no explicit licence; reuse terms to be confirmed with DOE | keep the DOE caveat; fallback rows only |

These licences apply **only** to the coverage layer, not to the DOE rate data (which has no
confirmed licence of any kind). Keep the per-source attribution and licence with any republished
coverage row.

**The combined coverage layer is a CC BY-SA derivative.** Because it merges OpenStreetMap Wiki
(CC BY-SA 2.0) and Wikipedia (CC BY-SA 4.0) rows with the public-law MERALCO area, any
redistribution of the coverage data must preserve attribution to those sources and keep the
share-alike terms. The DOE rate figures shipped alongside it are not affected by that obligation.

### Caveats — read before using coverage as a filter

* **Multi-region coverage.** 10 utilities have published coverage in more than
  one region: MERALCO (the franchise-law case — RA 12146 Section 1 enumerates its LGUs in NCR,
  Region III and Region IV-A plus 17 Pampanga barangays, while the DOE workbook lists MERALCO under
  NCR only) and 9 other cross-region / PSGC-reassignment franchises whose
  published LGU areas span regional boundaries. `coverage.regions` lists every PSGC region the rows
  touch; a filter built from the DOE single-region field alone understates their footprint.
* **PSGC reassignment is not an error.** Three utilities — PROSIELCO, SIASELCO and SULECO —
  publish coverage in a different region than their DOE workbook row because PSGC 3Q 2026
  reassigned Sulu to Region IX and Siquijor to NIR; their `coverage.note` documents this. Use the
  published coverage for the provider filter and keep the DOE row as the rate-aggregation region.
* **Partial province coverage.** `coverage_note` is the source's own qualification. For example,
  RA 12146 covers 20 of Cavite's 23 LGUs (it omits Amadeo, General Emilio Aguinaldo and Gen.
  Mariano Alvarez relative to the prior franchise; the reason is not stated in the law), and only
  parts of Batangas, Laguna and Quezon. Do not round partial provinces up to full coverage.
* **Barangay-level coverage.** Pampanga has **no** whole-LGU coverage in the MERALCO franchise —
  only 17 barangays in Apalit, San Simon and Candaba. `area_level: barangay` rows count barangays,
  not LGUs; never render the touched LGUs as fully covered.
* **Region fallback.** A utility whose `coverage.detail` is `region` has one fallback row repeating
  its DOE region. That is an explicit "not sourced at LGU level", not a claim that it serves the
  whole region or a single LGU.
* **Franchise ≠ billing territory.** Coverage encodes the legislative franchise / published
  operator area; it is not verified household-level service territory. Distribution service can
  differ (unenergized areas, ERC-approved arrangements, contested areas). Use it as a coverage and
  filter layer, not as proof of who bills an address.
* **Codes, not polygons.** Coverage rows join the map geometry through canonical 10-digit
  `adm3_psgc` / `adm4_psgc`; the API does not publish polygons. NCR has no province layer, so
  `provinces[]` for Meralco lists the map package's NCR districts under the same "Metro Manila"
  name; use `lgus[]` / `adm3_psgc` for LGU-level joins.
* **Validation.** Seven coverage checks are recorded at ingest (`coverage_checks` in
  `api/v1/validation.json`, summarised in `api/v1/health.json`); the API build additionally
  re-verifies that every utility's coverage block matches its published rows and that both seed
  files match their pinned rows/bytes/SHA-256.

---

## Sources & attribution

Source data: **Department of Energy (DOE)**, *Electricity Rates & Power Market Monitor*
(<https://doe.gov.ph/data-and-prices/electricity>), retrieved **2026-11-10T17:00:34+08:00** by CSV
export of the public Google Sheet (`1oGc1iGpacELS6tkHjesvAeKZo8v2iv4UkYFY04e0p-I`).

* The workbook has four tabs — residential (`gid=0`), commercial (`gid=441532959`), industrial
  (`gid=1244383053`) and blended generation (`gid=714337242`). The exact bytes of each retrieved
  tab are archived under `data/raw/doe-rates/2026-11-10/`; their SHA-256 hashes are in
  `api/v1/sources.json` and checked by the build.
* Every published number resolves to a source tab and a row in the workbook; utility records carry
  `source_row` for traceability.
* **Attribution:** if you republish these figures, credit the **Department of Energy (DOE)** as the
  source and the **Open Energy Data Layer** for the compilation, and keep the disclaimers below
  with the figures.
* The DOE workbook is unversioned and has no documented refresh calendar, so each release is a
  dated snapshot (`dataset_version`), not a live feed. Always verify against the DOE workbook or the
  utility's own published tariff before citing in formal work.

**Coverage sources.** The provider service-area layer is a separate, derived layer with its own
source registry (full records, licences, attribution and `used_for` counts in
[`api/v1/service-areas.json`](api/v1/service-areas.json) → `data.sources` and
[`api/v1/sources.json`](api/v1/sources.json) → `data.coverage_sources`):

* **RA 12146** Section 1 for MERALCO — a Philippine statute; the official text is published by the
  Supreme Court e-Library and works of the Government are not subject to copyright (IP Code,
  Sec. 176). Cite the law.
* **OpenStreetMap Wiki** "Power networks/Philippines/Operators" for LGU-level coverage of other
  utilities — **CC BY-SA 2.0**. Attribution is required and the share-alike obligation applies to
  coverage data derived from it.
* **Wikipedia** "List of electric distribution utilities in the Philippines" (supplementary LGU
  areas where the OSM table has none) — **CC BY-SA 4.0**, attribution + share-alike.
* **DOE workbook region column** for `region` fallback rows — same unconfirmed DOE terms as the
  rates; fallback rows only.

When republishing coverage rows, keep the row's `source_id` and the matching source record with its
attribution and licence. The CC BY-SA obligations are on the coverage layer only and do not license
the DOE rate data.

**Licence status.** The DOE workbook publishes **no explicit reuse licence**. The DOE site footer
says content is in the public domain unless otherwise stated, but the dataset-level terms are
**unconfirmed** and reuse terms are to be confirmed with DOE in writing. Accordingly this API
asserts **no licence over the upstream data** — the `meta.licence` object says
`"Not stated by publisher"`, with no licence URL. The rate data is **not** published under CC BY or
any other open licence at this stage; do not represent it as such. The coverage layer has its own
licences (CC BY-SA for OSM Wiki / Wikipedia-derived rows, public-law status for RA 12146; see
above) and must not be relicensed as CC BY either. The API specification and build tooling in this
repository are separate artefacts.

**Citation.** For the whole snapshot (also available as `citation` in `api/v1/index.json`):

> Open Energy Data Layer (2026). *Open Energy Data Layer: Philippine electricity rates* [Data set,
> v1.0]. Source: Department of Energy (DOE), *Electricity Rates & Power Market Monitor*, retrieved
> 2026-11-10. No upstream licence is asserted for the DOE rate data; normalise and verify against
> the DOE workbook before citing.

Every response's attribution string is in `meta.attribution`; keep it with republished figures.

---

## Disclaimers

Every response carries these five disclaimers in `meta.disclaimers` (id / title / text); keep them
with any figure you republish.

1. **`disclaimer-unofficial` — Unofficial compilation.** This is an independent compilation of a
   public DOE workbook, not an official DOE publication. Verify every figure against the source
   before citing or acting on it.
2. **`disclaimer-licence` — Upstream reuse terms unconfirmed.** The DOE workbook publishes no
   explicit reuse licence; terms are to be confirmed with DOE. No licence is asserted over the
   upstream data by this API.
3. **`disclaimer-nda` — NDA, missing and invalid are preserved, never imputed.** NDA is the
   source's "No Data Available"; missing is a month not yet published; invalid is a cell that
   failed validation. `null` never means zero and is never an estimate.
4. **`disclaimer-rates` — Rates are monthly averages as published.** Actual bills vary by
   consumption, charges, subsidies and timing. Figures are informational only and not financial
   advice.
5. **`disclaimer-coverage` — Coverage is derived data, not a DOE rate publication.** Service-area
   coverage is derived from franchise law (RA 12146 for MERALCO), the DOE workbook region column as
   a fallback, and, where present, the OpenStreetMap Wiki operator table (CC BY-SA 2.0) and the
   Wikipedia distribution-utility list (CC BY-SA 4.0). A franchise area is not verified
   household-level billing territory; region-level rows are a fallback, not LGU-level confirmation.
   Keep each source's attribution and licence.

---

## Data files

The tidy seed tables behind the API ship with the repository (six files; paths relative to
`draft/`; rows, bytes and SHA-256 checksums are in [`api/v1/index.json`](api/v1/index.json) under
`data_files` and in `api/v1/meta.json`):

| File | Rows | What it is |
|---|---|---|
| [`../data/seed/rates_monthly.csv`](../data/seed/rates_monthly.csv) | 60,348 | Long table: utility × customer class × month, with explicit `data_status` |
| [`../data/seed/utilities.csv`](../data/seed/utilities.csv) | 141 | Utility registry with provenance columns |
| [`../data/seed/regions.csv`](../data/seed/regions.csv) | 18 | Region aggregates as published in this snapshot |
| [`../data/seed/sources.csv`](../data/seed/sources.csv) | 4 | Rate-source registry, one row per workbook tab, with SHA-256 |
| [`../data/seed/service_areas.csv`](../data/seed/service_areas.csv) | 1,665 | Published coverage rows: one per covered LGU / barangay, or one `region` fallback per utility |
| [`../data/seed/service_area_sources.csv`](../data/seed/service_area_sources.csv) | 4 | Coverage-source registry (law, OSM Wiki, Wikipedia, DOE fallback) with licences and attributions |

`data/seed/plants.csv` is illustrative sample data and is **not** part of this API.

---

## Machine access

| Artefact | Path | Purpose |
|---|---|---|
| OpenAPI 3.1 contract | [`openapi.yaml`](openapi.yaml) · [`api/v1/openapi.json`](api/v1/openapi.json) | Every route, schema, example and provenance block |
| API catalog | [`api/v1/index.json`](api/v1/index.json) | Endpoints, files, sizes, SHA-256, data files and disclaimers |
| Dataset metadata | [`api/v1/meta.json`](api/v1/meta.json) | Same metadata as a response |
| Data model | [`data-model.md`](data-model.md) | Entity/field design behind the dataset |
| Builder | [`../tools/build-api.py`](../tools/build-api.py) | Deterministic generator for the whole tree |

The build is deterministic: re-running `python3 tools/build-api.py` produces byte-identical files.
Validate the contract with
`python3 -c "import yaml; yaml.safe_load(open('draft/openapi.yaml'))"` plus any OpenAPI 3.1
validator.
