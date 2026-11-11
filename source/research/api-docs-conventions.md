# BetterGov API conventions — findings and how this project adopts them

**Date:** 2026-11-10 · **Method:** read the live documentation and responses of the two BetterGov
APIs (`curl` on 2026-11-10) plus the saved artefacts in `/tmp` (`budgetdocs.txt`,
`budget_openapi.json`, `bg_openapi.json`, `bg_all.json`, `bg_mcp.txt`). Everything below was
observed directly; no convention is assumed from memory.

## Sources

| Source | URL | What it shows |
|---|---|---|
| Budget Data API docs | <https://budget.bettergov.ph/api> | Base URL, access rules, datasets & units, envelope, pagination, errors, data files, OpenAPI/MCP, What's new changelog, disclaimers, sources & attribution |
| Budget API endpoint index | <https://budget.bettergov.ph/api/v1> | Machine-readable catalog: `name`, `version`, `description`, `documentation`, `openapi`, `mcp`, `source_data`, and an `endpoints` map grouped by dataset |
| Budget API OpenAPI | <https://budget.bettergov.ph/api/v1/openapi.json> | OpenAPI **3.1.0**, `info.summary` + long markdown description, `contact` BetterGov.PH, `license` CC BY 4.0, absolute `servers`, per-dataset `tags`, error/disclaimer schemas |
| Budget API response | <https://budget.bettergov.ph/api/v1/gaa> | Live envelope `{meta, data[, next_cursor]}`; response headers `access-control-allow-origin: *`, `cache-control: public, max-age=300, s-maxage=3600` |
| Open Data Portal API | <https://data.bettergov.ph> | Catalog API: `/api/v1/ping`, `/api/v1/datasets`, `/api/v1/stats`; dataset records with `attribution[]` (`authors`, `source_url`, `attribution_text`, `license`, `license_url`), dataset-level `license`/`license_url` (null when not confirmed), publisher/category, `pagination` envelope, rate-limit headers, 429 |
| Budget API terms / disclaimer | <https://budget.bettergov.ph/terms-of-service>, <https://budget.bettergov.ph/disclaimer> | Terms exist for the site, API and MCP server; API docs changelog says keep the disclaimers each result carries and credit the publisher |
| Open Data Portal ping | <https://data.bettergov.ph/api/v1/ping> | `{"success":true,"data":{"status":"ok","timestamp":…}}`; `x-ratelimit-limit`/`remaining`/`reset` headers |

Two different envelopes exist in the BetterGov estate: the **Budget API** uses
`{meta, data, next_cursor}` (with errors `{error, message}` and a `disclaimers` array), while the
**Open Data Portal** uses `{success, data, pagination, error}`. This project follows the Budget API
because its envelope, error slugs and disclaimers are the documented pattern for a data layer;
the portal's *attribution record shape* is reused for source/licence fields.

## Section-by-section mapping

| BetterGov convention (observed) | How this project adopts it |
|---|---|
| **Envelope** `{meta, data, next_cursor}` on every response | Every file under `draft/api/v1/` returns `{meta, data, next_cursor}`. `index.json` (catalog) and `openapi.json` (contract) are documents, not envelopes, and are documented as such. |
| **Meta restates context** (`dataset`, `currency`, `scale`, filters, counts) | `meta` states `api_version`, `dataset`, `dataset_version`, `latest_month`, `generated_at`, `currency`, `unit`, compact `source`, `attribution`, `licence`, `disclaimers[]`, `count`. |
| **Datasets & units section**, units restated in every `meta` | Docs table of datasets; every amount is `PHP per kWh` with `currency: "PHP"` / `unit: "PHP per kWh"` in every response. |
| **Source data links + "Sources & attribution"** (derive from DBM publications; verify against official documents; attribution appreciated) | Every response links source id/URL/publisher; `sources.json` + `sources/SRC-DOE-RATES.json` carry the DOE page URL, workbook URL and sheet id, retrieval timestamp, extraction method, per-tab SHA-256. Docs have a "Sources & attribution" section asking readers to verify against DOE and credit DOE + BetterGov.PH. |
| **Explicit licence record** (`info.license`, dataset `license`/`license_url`; the portal can publish `null`) | Licence is a first-class object `{name, note, url}` in `meta` and every source record. Because the DOE workbook states no reuse licence, `name = "Not stated by publisher"` and `url = null` — mirroring the portal's ability to publish an unconfirmed `null` licence, **without** claiming CC BY for the data. |
| **Disclaimers array** `{id, title, body, url}` on every affected response; `meta.notice`; keep them when republishing | Every response carries `meta.disclaimers` with four entries: `disclaimer-unofficial`, `disclaimer-licence`, `disclaimer-nda`, `disclaimer-rates` (`id`, `title`, `text`, `url`). Docs repeat them verbatim and the catalog (`index.json`) publishes them for the page builder. |
| **Pagination** via opaque keyset cursor; `next_cursor: null` when exhausted | Static snapshot has no query layer: `next_cursor` is always `null`, documented as reserved for a future dynamic deployment. No fake pagination was invented. |
| **Error format** `{error, message}` with slugs (`bad_request`, `bad_cursor`, `not_found`, `method_not_allowed`, `not_loaded`, `query_failed`) | Static files return the host 404, so no JSON error body is emitted. `components.schemas.ErrorResponse` and the docs reserve the BetterGov slug format for a future dynamic layer; the OpenAPI 404 response says so plainly. |
| **Access block**: no auth, CORS `*`, `Cache-Control: public, max-age=300, s-maxage=3600`, descriptive `User-Agent` fair use | OpenAPI description and docs "Base URL & access" state exactly this: GET-only static files, no auth/key/body, recommended `Access-Control-Allow-Origin: *` and `Cache-Control: public, max-age=300, s-maxage=3600` at the deployment host, fair-use User-Agent. |
| **Machine access**: OpenAPI at `/api/v1/openapi.json`, endpoint index at `/api/v1` | `openapi.json` is emitted beside the data; `index.json` is the catalog (endpoints, files, sizes, SHA-256, data files, disclaimers, attribution, citation). `openapi.yaml` is the human-editable source mirrored to `openapi.json` by the builder. |
| **OpenAPI quality**: 3.1.0, `info.summary` + markdown description, `contact`, per-dataset `tags`, one `operationId` per op, examples | OpenAPI 3.1.0 with summary + long description covering source/units/access/caching/versioning/licence/disclaimers; seven tags; camelCase `operationId` per operation; real examples; `x-static-file`, `x-source`, `x-data-files`, `x-changelog`, `x-static-api` extensions. Validated with `openapi-spec-validator`. |
| **Versioning + "What's new" changelog** (`built_at`, dataset version in meta) | `api_version` = contract version (`1.0`); `dataset_version` = retrieval date (`2026-11-10`, from the seed payload); `x-changelog` in the spec; docs "Versioning" section. Files are immutable within a dataset_version. |
| **Health / discovery** (`/ping` portal; endpoint index; meta) | `health.json` (build identity + 17-check result, explicitly not an uptime signal) and `meta.json` (full metadata + checksums) exist as first-class files. |
| **Data files listed separately from endpoints** (manifest.json with rows/size/SHA-256 + notice) | `index.json.data_files` and `meta.json` list the four seed CSVs with rows, bytes and SHA-256 (paths relative to `draft/`); the docs have a "Data files" section. Raw snapshots are also listed in the source record, and the builder verifies their hashes. |

## Deliberate deviations (and why)

1. **Static files, not a hosted API.** The canonical origin is not live, so the OpenAPI `servers`
   URL is relative (`api/v1`, **no leading slash**, so it resolves against the location the spec
   is served from — `draft/openapi.yaml` -> `draft/api/v1/`) and the docs say the files are
   served at `draft/api/v1/` in this repository. No domain is invented; the catalog path
   convention is the served file style (`/v1/meta.json`).
2. **No MCP server.** The Budget API exposes one; this deliverable does not, so no MCP tools are
   declared rather than inventing them.
3. **Licence.** BetterGov's own budget data is CC BY 4.0. That claim is **not** transferable to the
   DOE workbook, which states no reuse licence, so this project publishes "Not stated by publisher"
   and documents that CC BY (or any open licence) is not claimed for the data.
4. **Disclaimers field name.** Adopted `text` (per the project task contract) where the Budget API
   uses `body`; the shape (id/title/text/url) is otherwise identical.
5. **Examples are real.** The old draft spec used illustrative numbers; the production spec and docs
   carry values copied from the generated files (e.g. MERALCO 15.06 ₱/kWh residential, ABRECO 12.58,
   113 residential reporters in 2026-10), so a reader can verify them in `draft/api/v1/`.

## Open questions / risks captured for the team

- Licence wording must stay "not stated / to be confirmed with DOE"; no CC BY claim until DOE
  confirms in writing.
- Relative URLs mean the page must link relatively (`api/v1/...`) until the deployment origin is
  fixed; OpenAPI clients should resolve `servers[0].url` against the deployment origin.
- A dynamic deployment (if funded) should keep the same `meta`/envelope, add the BetterGov error
  slugs and cursors, and serve `index.json`/`openapi.json` unchanged.
