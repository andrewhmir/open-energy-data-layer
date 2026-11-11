# Open Energy Data Layer — Draft Data Model (v0.9)

**Data-platform specification — Open Energy Data Layer**
Project: **Open Energy Data Layer** — the product page is titled *Philippine electricity rates*. One brand only: the retired working title is not used anywhere in the published artefacts. ICSC's Presyo PH is complementary, not a competitor.

Status: **draft for review** · Date: 2026-11-10 · Scope: one open dataset on *who sells power, at what price, and how reliably*, published as an API, a map, and a table, aligned with ASEAN Energy Statistics and consumable by DBM COMPASS.

> **Evidence base:** revised after a source-verification review on 2026-11-10. Key facts that shape the model: (1) DOE already publishes a machine-readable rate workbook (141 DU/EC rows × 107 month columns Jan-18→Nov-26, 4 tabs incl. blended generation charge; latest published month Oct-26); (2) ERC, NEA, PSA/PSGC, FOI and NGCP HTML are bot-blocked for automated collection — partnership/FOI routes only; (3) the local API pattern is BetterGovPH's Budget API (`{meta,data,next_cursor}`, error slugs, `/mcp`); (4) AES/AESL covers national aggregates, not retail tariffs, and is "All rights reserved". Full ledger: `research/data-landscape.md`, `research/api-landscape.md`.

---

## 1. Design goals

1. **One canonical ID per entity.** Suppliers, distribution utilities (DUs), and electric cooperatives (ECs) currently live across ERC, DOE, and NEA with no common identifier. We mint a stable code, publish a crosswalk to every agency ID, and never re-use codes.
2. **Facts, with receipts.** Every published number points to a `source_document` (URL, publisher, date, document hash, extraction method, confidence, reviewer). No number is publishable without provenance.
3. **Monthly, comparable, versioned.** Rates are observations keyed by `(utility, month, rate_class)`. Corrections create new versions — nothing is silently overwritten.
4. **Geography by PSGC.** All locations use PSA Philippine Standard Geographic Code (10-digit) keys, so the map/table/API can join to budgets, census, and COMPASS data without fuzzy matching.
5. **ASEAN-comparable.** Indicator tables map to ASEAN Energy Statistics definitions so DOE can submit/compare without a second data model.
6. **Boring, portable, cheap.** Postgres + CSV/JSON snapshots + one REST API. Everything open source and reproducible from public sources.
7. **Build on what DOE already publishes.** The DOE rate workbook is the v1 spine; this project adds identity, schema, provenance, API, and component enrichment — not 142 scrapers. Unverifiable sources (reliability, priority projects) are scoped as partner asks, not fabricated.

---

## 2. Entity–relationship overview

```
region ─┬─< province ──< city_municipality
        │
        └─< utility >──< rate_observation >── source_document
              │   │                            ▲
              │   └──< utility_identifier       │
              │                                │
              ├──< asset (plant / RE project) ──┘
              └──< service_area >── service_area_source (v1.1)

source_document ──< ingest_run
region/province ──< indicator_value >── indicator (ASEAN crosswalk)
rate_observation ──< change_event
submission (crowd) ──> rate_observation (after review)
```

Conventions: `snake_case`; UTC ISO-8601 timestamps; months as `YYYY-MM`; money as PHP decimals (`NUMERIC(12,4)`); rates in **₱/kWh**; capacity in **MW**; coordinates WGS84 (`lat`, `lng`).

---

## 3. Reference geography (`region`, `province`, `city_municipality`)

Source of truth: **PSA PSGC** (as of 30 September 2023 / current 2026 release; includes the re-established Negros Island Region, PSGC `1800000000`). Keep a frozen copy plus a sync script; never hard-code names in application logic.

| field | type | notes |
|---|---|---|
| `psgc_code` | char(10) | PK. e.g. `1300000000` (NCR), `0100000000` (Region I), `1800000000` (NIR) |
| `name` | text | official name |
| `short_name` | text | e.g. "NCR", "IV-A", "BARMM" |
| `level` | enum | `region` / `province` / `city_municipality` |
| `parent_psgc` | char(10) | null for regions |
| `region_psgc` | char(10) | denormalized for fast join |
| `island_group` | enum | `luzon` / `visayas` / `mindanao` |
| `valid_from`, `valid_to` | date | PSGC codes are not immutable; keep history |
| `geometry_ref` | text | key to GeoJSON layer (map only; not served in v1 API rows) |

**Map geometry** is a separate, versioned artifact: region + province GeoJSON derived from PSA/PSGC boundaries. Version it (`ph-regions-2026.geojson`) and store its SHA-256 in `meta` so the map is reproducible.

**Region-label caveat.** DOE's workbook uses 17 region labels (Regions I–XIII with Region IV split into 4A/4B, plus NCR, CAR, BARMM) and carries no Negros Island Region label. Persist a `doe_region_label` on utility rows and an auditable mapping to PSGC; never infer NIR membership from the workbook alone.

**PSGC vintage pin.** Use the current release (PSGC 3Q 2026 in this package): **NIR = `1800000000`**, **BARMM = `1900000000`** (the older `1500000000` is the retired ARMM code). PSGC codes are versioned keys: store the vintage used in `meta` and in every crosswalk row, and never silently rebase historical rows.

---

## 4. `utility` — the master list (deliverable 1)

| field | type | notes |
|---|---|---|
| `utility_code` | text | **PK**. Stable slug, e.g. `meralco`, `cepalco`, `nordeco`. Human-readable, never re-used |
| `utility_uid` | uuid | internal immutable ID (for crosswalks) |
| `name` | text | legal name at the time of the record |
| `short_name` | text | display name |
| `type` | enum | `private_iou`, `electric_cooperative`, `lgu_owned`, `other` (e.g. economic zone, PEZA, microgrid operator) |
| `ownership` | text | e.g. "Aboitiz Power", "NEA-supervised coop", "LGU" |
| `parent_utility_code` | text | FK to `utility` (subsidiary/parent groups) |
| `region_psgc` | char(10) | FK; service-area primary region |
| `province_psgc` | char(10) | FK; nullable for multi-province utilities |
| `city_municipality_psgc` | char(10) | FK; nullable |
| `name_variants` | text[] | name variants seen in sources, e.g. `DANECO` vs `DANECO/NORDECO` |
| `doe_region_label` | text | raw DOE workbook label (`Region 4A`, `BARMM`, …) for audit |
| `service_area_text` | text | human-readable coverage, from franchise/DU profile |
| `franchise_ref` | text | e.g. "RA 9209", "ERC Case No. ..."; nullable |
| `grid` | enum | `luzon`, `visayas`, `mindanao`, `off_grid`, `hybrid` |
| `connection_type` | enum | `grid_connected`, `off_grid`, `hybrid` |
| `hq_lat`, `hq_lng` | numeric | HQ / service point for map pin (nullable) |
| `website` | text | nullable |
| `status` | enum | `active`, `merged`, `renamed`, `inactive` |
| `notes` | text | merge/rename history, e.g. "CENECO → NEPC/CEPALCO..." |
| `source_ids` | text[] | FK array → `source_document` |
| `doe_region_psgc` | char(10) | the single DOE workbook region (alias of `region_psgc`; kept for audit) |
| `coverage_source_ids` | text[] | FK array → `service_area_source`; which sources back the published service area |
| `coverage_detail` | enum | `lgu` / `barangay` / `region` — strongest published service-area level |
| `coverage_lgu_count` | int | number of LGU-level published coverage rows |
| `coverage_regions` | char(10)[] | PSGC regions the published service-area rows touch (may be more than the one DOE region) |
| `version` | int | row version, monotonic |
| `created_at`, `updated_at` | timestamptz | audit |

### 4.1 `utility_identifier` — the crosswalk (the actual hard part)

| field | type | notes |
|---|---|---|
| `id` | bigint | PK |
| `utility_code` | text | FK |
| `scheme` | enum | `erc_du`, `doe_du`, `nea_ec`, `psgc`, `ngcp`, `seal_of_good`, `internal_legacy`, `other` |
| `identifier` | text | the value in that agency's system |
| `is_primary` | bool | one primary per scheme per utility |
| `source_id` | text | where the mapping was observed |
| `confidence` | enum | `verified`, `probable`, `unverified` |
| `valid_from`, `valid_to` | date | merges/renames kept as history |

Publish this crosswalk openly — it is reusable by ERC, DOE, NEA, COMPASS, and other civic tech projects, and it is the interoperability artifact the challenge asks for.

---

## 5. `source_document` + `ingest_run` — provenance backbone

### `source_document` (published as `sources/<source_id>.json`)

The source record is part of the public contract: the static API publishes it verbatim at
`api/v1/sources/SRC-DOE-RATES.json` and lists it at `api/v1/sources.json`. Every response's `meta`
carries the compact `source` reference plus `attribution`, `licence` and the `disclaimers` array.

| field | type | notes |
|---|---|---|
| `id` | text | **PK**. Stable slug, e.g. `SRC-DOE-RATES` (not a hash: the id must stay stable across re-retrievals). |
| `publisher` | text | e.g. `Department of Energy (DOE)` |
| `title` | text | Published dataset title, e.g. *Electricity Rates & Power Market Monitor* |
| `canonical_url` | text | The page that embeds/canonicalises the source (DOE `data-and-prices/electricity`). |
| `workbook_url`, `sheet_id` | text | Public Google Sheet URL + id for an embedded workbook (DOE rates). |
| `retrieved_at` | timestamptz | Exact retrieval instant, ISO-8601 with offset. |
| `extraction_method` | enum | `csv_export`, `pdf_download`, `html_parse`, `ocr`, `manual_entry`, `api` |
| `licence` | object | `{name, note, url}`; `name` is **"Not stated by publisher"** and `url` is `null` while the DOE workbook has no explicit reuse licence. No open licence is asserted over the upstream data. |
| `tabs` | array | Per-tab provenance: `{gid, customer_class, sha256, bytes, rows}` — exact bytes of each exported tab. |
| `raw_snapshots` | array | Archived raw CSVs (repository path + gid + bytes + sha256) that the `tabs` hashes are verified against. |
| `coverage` | object | `{months, month_columns, utility_rows, latest_published_month, latest_available_month}` |
| `notes` | array | Provenance caveats, e.g. no documented refresh calendar, licence unstated. |
| `archive_url` | text | Optional Wayback/self-hosted snapshot for volatile pages and social posts (v2 sources). |
| `published_date` | date | As stated by the publisher (null when the source carries no date). |
| `sheet_row` | int | Cell-level traceability: every utility/rate record points back to its workbook row (e.g. `source_row: 18`). |
| `vintage` | date | Snapshot date for sources with no intrinsic version — here the `dataset_version`. |

**Attribution convention.** Every response (and the index catalog) carries an `attribution`
string: *"Source: Department of Energy (DOE) — Electricity Rates & Power Market Monitor, retrieved
… When republishing, credit DOE as the source and the Open Energy Data Layer for the
compilation."* The index also carries a `citation` string for
academic/bibliographic use. Attribution is required when republishing; the five `disclaimers`
(`disclaimer-unofficial`, `disclaimer-licence`, `disclaimer-nda`, `disclaimer-rates`) must travel
with any figure.

### `ingest_run`

| field | type | notes |
|---|---|---|
| `run_id` | uuid | PK |
| `source_id` | text | FK |
| `parser` | text | e.g. `meralco_rates_pdf@1.2.0` |
| `started_at`, `finished_at` | timestamptz | |
| `rows_found`, `rows_valid`, `rows_error` | int | pipeline observability |
| `error_log` | jsonb | bounded, no PII |
| `review_status` | enum | `pending`, `in_review`, `approved`, `rejected` |

Rule: **a rate row cannot be published without `source_id` + `extraction.method` + `reviewer`.**

**Implemented record (v1.0, 2026-11-10):** the DOE rate workbook is one logical source (`SRC-DOE-RATES`) with four tab-level provenance entries (one per customer class). This is the real published shape (abridged: two of four tabs):

```json
{
  "id": "SRC-DOE-RATES",
  "publisher": "Department of Energy (DOE)",
  "title": "Electricity Rates & Power Market Monitor",
  "canonical_url": "https://doe.gov.ph/data-and-prices/electricity",
  "workbook_url": "https://docs.google.com/spreadsheets/d/1oGc1iGpacELS6tkHjesvAeKZo8v2iv4UkYFY04e0p-I",
  "sheet_id": "1oGc1iGpacELS6tkHjesvAeKZo8v2iv4UkYFY04e0p-I",
  "retrieved_at": "2026-11-10T17:00:34+08:00",
  "extraction_method": "csv_export",
  "licence": { "name": "Not stated by publisher", "note": "…", "url": null },
  "tabs": [
    { "gid": 0, "customer_class": "residential", "sha256": "17c74616…", "bytes": 106827, "rows": 141 },
    { "gid": 441532959, "customer_class": "commercial", "sha256": "55c8ccc0…", "bytes": 102822, "rows": 141 }
  ],
  "raw_snapshots": [
    { "path": "data/raw/doe-rates/2026-11-10/0.csv", "gid": 0, "customer_class": "residential",
      "bytes": 106827, "sha256": "17c74616…" }
  ],
  "coverage": { "months": "2018-01 to 2026-11", "month_columns": 107, "utility_rows": 141,
                "latest_published_month": "2026-10", "latest_available_month": "2026-11" },
  "notes": [ "The DOE page embeds a public Google Sheet (four tabs). Every tab was exported as CSV; the per-tab SHA-256 above is the exact bytes retrieved and kept under data/raw/doe-rates/." ]
}
```

Cell-level traceability: every utility record carries `source_row` and every response points at
`SRC-DOE-RATES`, so a reader can open the workbook tab at the exact row. `data/seed/sources.csv`
holds the four tab records with full hashes; `data/seed/validation.json` holds the 17 ingest checks
and the five cross-tab conflicts are published at `api/v1/conflicts.json`. The build
(`tools/build-api.py`) re-verifies the raw snapshots against the tab SHA-256 on every run.

---

## 6. `rate_observation` — the price table (deliverable 2)

One row = one utility × month × rate class. The challenge's v1 asks for *utility, month, price per kWh, generation charge*; the model carries the full bill decomposition because that is what makes the price comparable and the generation charge visible.

| field | type | notes |
|---|---|---|
| `rate_id` | uuid | PK |
| `utility_code` | text | FK (`utility`) |
| `month` | char(7) | billing month `YYYY-MM` |
| `rate_class` | enum | `residential`, `commercial`, `industrial`, `other` |
| `total_rate_php_kwh` | numeric(12,4) | effective rate, ₱/kWh |
| `generation_php_kwh` | numeric(12,4) | nullable |
| `transmission_php_kwh` | numeric(12,4) | nullable |
| `system_loss_php_kwh` | numeric(12,4) | nullable |
| `distribution_php_kwh` | numeric(12,4) | nullable |
| `subsidies_php_kwh` | numeric(12,4) | nullable (senior citizen, lifeline, etc.) |
| `universal_charges_php_kwh` | numeric(12,4) | nullable |
| `fit_all_php_kwh` | numeric(12,4) | nullable (FIT-All) |
| `government_taxes_php_kwh` | numeric(12,4) | nullable (VAT, local taxes) |
| `other_php_kwh` | numeric(12,4) | nullable; itemize in `components_json` |
| `components_json` | jsonb | raw line items exactly as published, for audit |
| `currency` | char(3) | `PHP` (keep column for future) |
| `billing_basis` | enum | `residential_typical_200kwh`, `per_kwh`, `other` — DUs publish different bases; record it |
| `generation_basis` | enum | `blended_doe`, `utility_published`, `derived` — DOE publishes a blended generation charge, not the utility's full generation line items |
| `reporting_status` | enum | `reported`, `no_data_available`, `not_published` — maps DOE `NDA` to a null value, never 0 |
| `data_status` | enum | `official` (as published), `derived` (computed/normalized), `editorial` (author-entered) — shown in the UI |
| `source_id` | text | FK `source_document` |
| `extraction_method` | enum | `manual`, `pdf_text`, `pdf_ocr`, `web_table`, `social_post`, `api` |
| `confidence` | enum | `verified` (analyst checked against source), `extracted` (automated, not yet checked), `unverified` (crowd/legacy) |
| `reviewer` | text | nullable; analyst initials/handle |
| `reviewed_at` | timestamptz | |
| `status` | enum | `draft`, `published`, `superseded`, `rejected` |
| `supersedes_rate_id` | uuid | correction chain |
| `notes` | text | e.g. "rate excludes VAT; see source p.2" |
| `created_at`, `updated_at` | timestamptz | |

Constraints:
- unique `(utility_code, month, rate_class)` among rows with `status = 'published'`;
- `total_rate_php_kwh` within `[3.0000, 40.0000]` (₱/kWh; widen only with reviewer override + note);
- if components are present, `abs(sum(components) - total) <= 0.05` unless `components_json.basis` says otherwise;
- `month` not in the future relative to `retrieved_at`;
- `reporting_status = no_data_available` implies `total_rate_php_kwh IS NULL`; the count of reporting utilities per month/region is published in metadata and must never be hidden;
- a parsed row must reconcile with the DOE total for the same utility/month within 0.05 ₱/kWh, or be quarantined with a note.

> **Why full decomposition?** The core insight is that "the part of the bill that moves the most, the generation charge, is the part a consumer cannot see or compare." A price table with only the total would reproduce that gap.

---

## 7. `asset` — plants, RE projects, priority projects (deliverable 3)

One table for existing power plants and pipeline projects; distinguishes operational vs committed vs indicative.

| field | type | notes |
|---|---|---|
| `asset_id` | text | **PK**. `doe:<ref>` when DOE ID exists, else deterministic slug |
| `name` | text | |
| `asset_type` | enum | `plant`, `re_project`, `priority_project`, `microgrid` |
| `technology` | enum | `coal`, `natural_gas`, `lng`, `oil`, `diesel`, `hydro`, `geothermal`, `solar`, `wind`, `biomass`, `waste_to_energy`, `storage`, `other` |
| `capacity_mw` | numeric(10,3) | nullable for projects without firm capacity |
| `status` | enum | `operational`, `under_construction`, `committed`, `indicative`, `planned`, `retired`, `unknown` |
| `region_psgc`, `province_psgc`, `city_municipality_psgc` | char(10) | FK; nullable when only region-known |
| `lat`, `lng` | numeric | nullable; approximate flags below |
| `geo_precision` | enum | `exact`, `municipality_centroid`, `province_centroid`, `none` — honest map dots |
| `grid` | enum | `luzon`, `visayas`, `mindanao`, `off_grid` |
| `owner`, `operator` | text | |
| `cod` | date | commercial operation date (nullable / expected) |
| `doe_project_ref` | text | DOE project registry reference |
| `re_contract_no` | text | RE contract number if published |
| `source_id` | text | FK |
| `updated_at` | timestamptz | |

Map rule: **never render a centroid as if it were an exact site.** `geo_precision` drives dot style (solid = exact, hollow = approximate, region fill = none).

**v1 sources:** DOE's List of Existing Power Plants (LoEPP, PDF, as of Aug 2026) and DOE's RE-project PDF lists (as of Jun 2026), converted by parsers with human QA. Priority-project and grid-reliability records are **out of v1** until a public or partner source is confirmed — the schema supports them, the sprint does not invent them.

---

## 8. `indicator` / `indicator_value` — ASEAN Energy Statistics alignment

This layer aligns with ASEAN Energy Statistics. **Important correction from the evidence review:** AES/AESL covers *national aggregate energy statistics* (TPES/TFEC in Mtoe, installed capacity in GW, generation, consumption, electrification; 2005–2023), **not retail utility tariffs**, and the AESL PDFs state "ACE. All rights reserved." So the retail price table stays a PH-specific layer, and this indicator layer exists solely for national aggregates that DOE reports to ACE.

Model the indicator layer so DOE-comparable values are first-class (not derived ad hoc in the UI).

| field | type | notes |
|---|---|---|
| `indicator_code` | text | PK, e.g. `residential_electricity_price_php_kwh` (internal code; AES mapping in `indicator_crosswalk`) |
| `name`, `description` | text | |
| `unit` | text | `PHP/kWh`, `MW`, `GWh`, `%`, `SAIDI_minutes`, … |
| `frequency` | enum | `monthly`, `annual`, `quarterly` |
| `definition` | text | method notes (e.g. "simple mean of reporting DUs' published residential rates; unweighted; NDA excluded — see `coverage` metadata") |

`indicator_value`: `(indicator_code, geography_psgc, period, value, unit, source_ids[], status, published_at)`. `status`: `provisional` / `final`; `geography_psgc = 0000000000` for national totals.

`indicator_crosswalk`: maps internal indicator → **ASEAN Energy Statistics** concept (PH source field → AES indicator → unit conversion → vintage). Definitions/units come from the AESL 2025 leaflet (ASEAN Centre for Energy) during implementation — **do not guess codes**. Schema alignment only: AES tables are not bulk-copied or rehosted (© ACE, all rights reserved); values are sourced from DOE/PSA and attributed.

Suggested v1 indicators (national, annual): installed capacity by technology (MW), generation by technology (GWh), electricity consumption (GWh), electrification rate (%), RE share (%), energy intensity where available. **Retail rates are not AES indicators** — they live in `rate_observation` with PHP/kWh units and PH-specific definitions.

---

## 9. `service_area` coverage — v1.1 (implemented as data, not polygons)

The provider filter needs to know which LGUs a utility serves, not only the single region the DOE
workbook assigns. v1.1 publishes a **sourced, row-level service area** — not polygons: one row per
(utility, covered LGU) where an LGU-level source exists, barangay-level rows where a franchise is
barangay-only, and one `region` fallback row for utilities with no LGU-level source. It is served at
`api/v1/service-areas.json` and `api/v1/service-areas/<CODE>.json`, and summarised in utilities and
`meta`.

Precedence (implemented by `tools/build-service-areas.py`):
1. `research/service-areas.json` — RA 12146 Section 1 for **MERALCO** (108 cities/municipalities
   plus 17 Pampanga barangays). The franchise law wins over OSM rows for MERALCO.
2. `research/coverage/osm-service-areas.csv` — LGU-level franchise areas from the OpenStreetMap
   Wiki operator table (CC BY-SA 2.0) for the other utilities.
3. `data/seed/utilities.csv` — the DOE workbook region, published as a single `region` fallback row
   when no LGU-level row joins. In the 2026-11-10 snapshot every utility has LGU-level coverage
   (1,648 LGU rows + 17 Pampanga barangay rows; **zero** region fallback rows), so the fallback
   path is implemented but not exercised by the current data.

### `service_areas.csv` (published seed — one row per covered area)

| column | type | notes |
|---|---|---|
| `utility_code` | text | FK → `utility` (joins `data/seed/utilities.csv`) |
| `source_id` | text | FK → `service_area_source`; the source backing this row |
| `area_level` | enum | `lgu` (a covered city/municipality), `barangay` (a covered barangay), `region` (fallback row) |
| `region_psgc` | char(10) | PSA PSGC region code |
| `province_psgc`, `province_name` | char(10), text | province (or NCR district) layer; null on `region` rows |
| `adm3_psgc`, `lgu_name` | char(10), text | canonical 10-digit city/municipality PSGC + name; null on `region` rows |
| `adm4_psgc`, `barangay_name` | char(10), text | barangay PSGC + name on `barangay` rows only; null otherwise |
| `coverage_note` | text | the source's own qualification: "province coverage: partial", "barangay-level franchise area", "region-level fallback", law-override notes |

### `service_area_sources.csv` (published seed — one row per coverage source)

| column | type | notes |
|---|---|---|
| `source_id` | text | **PK**. `SRC-RA-12146`, `SRC-OSM-OPERATORS`, `SRC-WIKI-DUS` (supplementary), `SRC-DOE-RATES` (fallback) |
| `publisher` | text | e.g. Congress of the Philippines / Supreme Court e-Library, OpenStreetMap Wiki contributors |
| `dataset_title` | text | e.g. *Republic Act No. 12146: renewal of the Meralco franchise* |
| `page_url` | text | official text / wiki page URL |
| `revision_id` | text | law id + approval date, or wiki page revision (oldid) |
| `retrieved_at` | timestamptz | retrieval instant of the snapshot used |
| `license` | text | `Public document (Philippine law)`, `CC BY-SA 2.0`, `CC BY-SA 4.0`, or DOE "no explicit dataset licence" |
| `attribution` | text | the exact attribution line to carry with the data |
| `notes` | text | usage notes (which utilities, which levels, raw snapshot path) |

### Relationship to `utility` — one DOE region vs a sourced service area

- `utility.region_psgc` is the **DOE workbook assignment** (exactly one region). It stays the basis
  for region rate aggregates and is kept as an audit reference.
- `utility.coverage` is the **sourced service area**: `{detail, source_ids, regions, provinces[],
  lgus[], lgu_count, barangays[], barangay_count, barangay_provinces, note}`.
- `detail` is the strongest published level; `regions` can contain more than one region even though
  the DOE workbook lists one. In the 2026-11-10 snapshot 10 utilities are multi-region: MERALCO
  (the franchise-law case — NCR + Region III + Region IV-A plus 17 Pampanga barangays) and nine
  cross-region / PSGC-reassignment franchises (AURELCO, BASELCO, CAGELCO-II, FIBECO, LASURECO,
  PPALMA, QUEZELCO-I, SUKELCO, ZAMSURECO-I). Treat the flag as sourced coverage, not a legal finding.
- Three utilities — PROSIELCO, SIASELCO, SULECO — publish coverage in a different region than their
  DOE workbook row because PSGC 3Q 2026 reassigned Sulu to Region IX and Siquijor to NIR; their
  `coverage.note` documents this. It is not an error: use the published coverage for the provider
  filter and the DOE row for rate aggregation.
- A `region`-level fallback row is honest: it says "no LGU-level source", not "one LGU". LGU-level
  rows are franchise/service areas, not verified household-level billing territory.
- Utility codes join LGU boundaries through `adm3_psgc` / `adm4_psgc` (canonical 10-digit PSGC), so
  the coverage layer joins the same geometry as the map.

### Coverage API object (v1.1)

- `meta.service_area` (every response): `{detail_counts: {total, lgu, barangay, region},
  sources: [{source_id, licence: {name, url}}], note}`.
- `utilities.json` rows: compact `coverage` = `{detail, source_ids, regions, lgu_count,
  province_count, barangay_count}`; `utilities/<CODE>.json` adds full `service_area` =
  compact + `provinces[]`, `lgus[]`, `barangays[]`, `barangay_provinces[]`, `note`.
- `GET /v1/service-areas.json`: `{coverage stats, detail_counts, rows_by_area_level, sources[]
  (full source records + used_for), utilities[] (141 compact coverage summaries)}`.
- `GET /v1/service-areas/<CODE>.json`: `{utility, service_area (full), rows[] (published
  coverage rows), sources[], notes}`; `meta.count` is the number of published rows for the utility.

### Validation rules (enforced by `tools/build-service-areas.py` and `tools/build-api.py`)

- Every utility has at least one coverage row; a `region` fallback is exactly one row equal to the
  utility's DOE region; `lgu` rows carry a canonical 10-digit `adm3_psgc`; `barangay` rows carry
  `adm4_psgc`.
- `coverage.detail` matches the row mix (`lgu` ⇒ LGU rows, `barangay` ⇒ barangay rows only,
  `region` ⇒ one fallback row and no LGU/barangay rows).
- Each utility's `regions`, `source_ids`, `lgu_count`, `barangay_count` and `provinces` match its
  rows; the coverage stats (per-level row counts, `distinct_lgus`, `multi_region_utilities`,
  `sources`) match the published files; both seed files' rows/bytes/SHA-256 are pinned in
  `page-data.json` and re-verified by the API build.
- 7 recorded coverage checks (rows present, every utility covered, LGU spot counts, valid PSGC,
  DOE region inside service area) feed `health.json`; any failure marks the snapshot `degraded`.

### Licensing (coverage layer)

| source | licence / terms | what to carry |
|---|---|---|
| `SRC-RA-12146` | Public document (Philippine law); works of the Government are not subject to copyright (IP Code, Sec. 176) | cite the law (official text, Supreme Court e-Library) |
| `SRC-OSM-OPERATORS` | **CC BY-SA 2.0** — attribution required; share-alike applies to coverage derived from it | keep the OSM Wiki attribution and licence note with any republished coverage |
| `SRC-WIKI-DUS` (when used) | **CC BY-SA 4.0** | attribution + share-alike |
| `SRC-DOE-RATES` | no explicit licence; terms to be confirmed with DOE | fallback rows only; do not present as an official service-area dataset |

The coverage layer is **separate from the rate data**: do not apply the DOE rate licence (or any
CC licence claimed for other BetterGov data) to the rates, and keep the CC BY-SA obligations on the
coverage rows sourced from OSM Wiki / Wikipedia. Because the layer merges CC BY-SA 2.0 and 4.0 rows
with the public-law MERALCO area, **the combined coverage layer is a CC BY-SA derivative**:
redistributions must attribute the sources and keep the share-alike terms. The five API disclaimers,
including `disclaimer-coverage`, must travel with republished coverage.

---

## 10. `change_event` — audit + change feed

`change_id`, `entity` (`utility`|`rate`|`asset`|`source`), `entity_id`, `change_type` (`create`|`update`|`correct`|`supersede`|`retire`), `diff` jsonb (before/after, bounded), `actor` (system or analyst), `reason`, `created_at`. Powers `GET /v1/changes` and the "what changed this month" widget.

## 11. `submission` — citizen/crowd intake (v1.1, gated)

`submission_id`, `submitted_by` (hashed handle / contact optional), `utility_code`, `month`, `claimed_rate`, `bill_photo_url`, `source_url`, `status` (`pending`, `accepted`, `rejected`, `needs_info`), `moderator`, `linked_rate_id`. Citizens can flag discrepancies; only analyst-approved rows publish, preserving the "analyst checks every number" covenant.

---

## 12. Publication states and versioning

```
draft ──> in_review ──> published ──> superseded
             │               │
             └──> rejected   └──> withdrawn ──> change_event
```

DOE/coalition can withdraw a live row instantly (`status = withdrawn`, reason logged). `data_status` distinguishes official publisher values from derived/editorial values in the same table.

- `api_version` = JSON contract version (`1.0`), stable across snapshots; `dataset_version` = ISO date of the retrieval/snapshot (`2026-11-10`), exposed in every API `meta` block, the catalog (`index.json`) and the static tree path convention.
- Snapshots are immutable once published (`draft/api/v1/` for `2026-11-10`); a new retrieval is a new `dataset_version`, never a silent rewrite. The changelog lives in `openapi.yaml` as `x-changelog`.
- Corrections create a new observation + `supersedes_rate_id` (v2 dynamic API); the static v1 tree only ever carries the current snapshot.
- Every source record carries `licence`, `publisher`, `retrieved_at`, `extraction_method` and per-tab checksums — the fields needed for `data.gov.ph`/DCAT registration.
- Every response carries `attribution`, the five `disclaimers` (including `disclaimer-coverage`) and a compact `meta.service_area` context; the catalog adds a `citation` string. Keep them with republished figures.
- The v1.1 coverage layer is an additive change to API contract `1.0`: no rate endpoint or envelope
  field changed; `api_version` stays `1.0` and `dataset_version` identifies the snapshot.

## 13. Licensing & provenance policy

| artifact | licence status |
|---|---|
| **Upstream rate data (DOE workbook) — v1 published data** | **Unconfirmed: licence "Not stated by publisher".** The workbook carries no explicit reuse licence, so the API asserts **no licence over the upstream data** and `meta.licence.url` is null. The DOE site footer says content is in the public domain unless otherwise stated; dataset-level terms must be confirmed with DOE **in writing** before any open licence is claimed. Do **not** publish these figures under CC BY or any other licence at this stage. |
| Static API tree, OpenAPI spec, docs, build tooling | Project deliverable, shared for review; the repository does not yet declare a code licence. Do not represent it as MIT/CC0 until a `LICENSE` file is added by the project owners. |
| Coverage layer — RA 12146 (MERALCO) | Public document (Philippine law); works of the Government are not subject to copyright (IP Code, Sec. 176); cite the law. |
| Coverage layer — OSM Wiki operator table | **CC BY-SA 2.0**: attribution required; share-alike applies to derived coverage data. Keep the attribution and licence note on any republication. |
| Coverage layer — Wikipedia DU list (supplementary, when used) | **CC BY-SA 4.0**: attribution + share-alike. |
| Coverage layer — DOE region fallback | Same as the DOE workbook: no explicit licence, terms to be confirmed with DOE. Fallback rows only; not an official service-area dataset. |
| Map geometry derived from PSA | PSA terms; keep attribution + snapshot hash |
| Source PDFs/posts | not redistributed; facts extracted with link + hash; publisher retains copyright |
| API metadata | DCAT-3-shaped records internally; the published contract is OpenAPI 3.1 + `index.json` (no verified national "DCAT-PH" profile exists) |
| AES/AESL reference | © ASEAN Centre for Energy, "All rights reserved" — cite and align schema only; never rehost AES tables |
| Attribution (all artefacts) | Credit **Department of Energy (DOE)** as the source and the **Open Energy Data Layer** for the compilation; carry the disclaimers. |

## 14. Open questions to settle with DOE/ERC/coalition in December

1. Is the public DOE rate workbook canonical — owner, refresh cadence, license/citation, and will DOE publish it as a documented dataset/API? Can the embedded Google Sheet be replaced by (or mirrored as) a documented CSV/API endpoint?
2. Can DOE expose (or grant) the internal endpoint behind the client-side electricity data pages and RE dashboards, or do we scrape/observe-network with permission?
3. Does ERC have a canonical DU register with IDs we can adopt (instead of minting our own codes)?
4. Is NEA able to share the EC register (including coops with no published digital rate) and its EC→municipality (PSGC) table?
5. Which rate basis is comparable across the 142 utilities (typical 200 kWh residential? effective rate?) — analyst decision, documented.
6. Can social-post sources (Facebook) be archived with permission, or do we rely on DO/ERC official copies only?
7. Who signs off on publication during the build — the coalition data analyst — and who inherits it after March 2027?
8. Which PSGC vintage does DBM COMPASS use, and can the project obtain the PSGC file through DBM/PSA rather than a blocked public download?

---

## 15. Addendum — v1 source-of-truth map (after evidence review)

| Dataset | v1 primary source | Access | Enrichment / validation | Notes |
|---|---|---|---|---|
| DU/EC registry | DOE rate workbook (141 utility codes from 142 distinct names across tabs) + curated aliases | Google Sheet CSV export | PIOU/EC sites, coalition knowledge; NEA EC list via FOI | Mint `utility_code`; publish crosswalk with confidence |
| Monthly retail rates | DOE workbook: four tabs — residential / commercial / industrial / blended generation (107 months, 2018-01→2026-11; latest published 2026-10) | CSV export, snapshot + sha256 | Meralco panels/PDFs as independent cross-check | `NDA` → null + `no_data_available`; aggregate methodology published |
| Generation charge | DOE workbook blended generation charge tab | CSV export | EC/PIOU PDFs for component detail | `generation_basis = blended_doe` |
| Bill components | PIOU/EC published documents (Meralco verified; SURNECO sample verified) | PDF/HTML parse + OCR fallback | Component dictionary; total must reconcile with DOE | Start with top utilities by customer volume |
| Geography | PSA PSGC (partner/FOI route; DBM/COMPASS may share) | Partner/FOI; community mirror only for prototyping | DOE region-label → PSGC mapping; utility→province crosswalk | 18 regions incl. NIR; DOE workbook has 17 labels |
| Existing plants | DOE LoEPP PDFs (Aug 2026) | PDF download/parse | Human QA sample | `geo_precision` flags; feed + API |
| RE projects | DOE RE-project PDF lists (Jun 2026) | PDF download/parse | Human QA sample | No verified dashboard/API behind them |
| Microgrids | DOE microgrid dashboards (UI only) | Partner request (`mgsp@doe.gov.ph`) | — | Do not scrape UI; request export |
| Market prices | IEMOP monthly WESM DU rate reports | Partner request | — | v2/partner; not v1 |
| Transmission projects | NGCP TDP PDFs | Static PDF download | — | v2 reference layer |
| Reliability (SAIDI/SAIFI) | NEA EC compliance reports (bot-blocked) | FOI/partner | — | v2; not promised in v1 |
| National aggregates (AES) | DOE/PSA published statistics | Partner/FOI + public PDFs | AESL 2025 definitions for schema mapping | Do not rehost AES tables |
| Provider service area (v1.1) | RA 12146 Section 1 (MERALCO) + OSM Wiki operator table + DOE workbook region fallback | Legislative text + wiki CSV (CC BY-SA 2.0) + `utilities.csv`; assembled by `tools/build-service-areas.py` | 7 coverage checks + API build consistency checks + geometry join validation | LGU-level rows where sourced; barangay rows where barangay-only; one honest `region` fallback otherwise. Franchise ≠ billing territory; multi-region franchises stay visible. |
| Source documents | All of the above | Source registry + archive (URL + sha256) | Review workflow | Every published value resolves here |
| API snapshot (v1.0) | Generated deterministically from `data/seed/` by `tools/build-api.py` | Static files under `draft/api/v1/` (17 routes, 176 JSON files, 2.91 MiB) | Schema validation, determinism check, 17 ingest checks | Envelope `{meta, data, next_cursor}`; explicit NDA/missing/invalid states; `draft/openapi.yaml` OpenAPI 3.1; licence "Not stated by publisher" |
