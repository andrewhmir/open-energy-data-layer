# API & Interop Landscape — Open Energy Data Layer for the Philippines

**Author:** api-researcher (Team Lead's research task) · **Date:** 2026-11-10 (Asia/Manila)
**Scope:** DBM COMPASS / EO 126 context, PH open-data stack, precedent energy APIs, standards, BetterGovPH assets, and a recommended v1 API + governance shape for the BetterGov PH Fellowship "Energy" challenge (pilot cohort Dec 2026 – Mar 2027).
**Method / legend:** `[V]` = URL or fact fetched and observed on 2026-11-10. `[B]` = URL exists but fetch was blocked (Cloudflare/bot protection) in this environment. `[I]` = inferred/recommended by this researcher, not observed. Access date for every source below: **2026-11-10**. Endpoints described as "proposed" are not live and are not claimed to exist.

---

## 0. TL;DR — decisions this research supports

1. **Build REST-first, then wrap in MCP.** BetterGovPH already ships this exact pattern twice (Budget API, community Open Data Portal): OpenAPI 3.1 + public REST + stateless Streamable-HTTP MCP server + bulk data files. Copy it; don't invent a new pattern.
2. **One master entity list is the product.** A `utility`/`supplier` entity with a stable public ID keyed to PSGC geography is the join key for the price table, DOE RE/priority projects, COMPASS budget records, and Presyo PH. Publish it before the rates pipeline.
3. **Register the dataset where government data is already discovered.** data.gov.ph registration + DICT eGov API catalog listing + DCAT-3 metadata are the three "publish" surfaces; COMPASS itself is consumed read-only via its own API-keyed REST API.
4. **Bulk CSV mirror is non-negotiable.** Every precedent with staying power pairs an API with dated bulk files (OPSD, OEDI, Ember datasets). A GitHub/Cloudflare mirror + `datapackage.json` + SHA-256 makes the project survive API downtime and outlast the 3-month fellowship.
5. **Editorial review must be modeled in the schema, not a side process.** The coalition data analyst who "checks every number before it goes public" needs `data_status`, `reviewed_by`, `reviewed_at`, `source_document_id`, `confidence` fields and `draft → in_review → published → superseded` states.
6. **License: CC-BY-4.0 for data, MIT/CC0 for code, link-don't-rehost for source PDFs.** PH government content is "public domain unless otherwise stated"; CC-BY-4.0 satisfies the fellowship's open-license expectation while preserving attribution to DOE/ERC/NEA.
7. **COMPASS integration is a metadata + join-key problem, not a write-API problem.** No public write API was found; the documented surface is the read-only DBM Transparency Portal API behind `X-API-Key`, plus dataset publication.

---

## 1. DBM COMPASS + EO 126 s. 2026: what it is and why integration matters

**What COMPASS is.**
COMPASS = *Centralized Open Monitoring Platform for Appropriations and Spending Statistics*, DBM's unified public platform for budget execution and spending disclosure. Public portal: https://compass.dbm.gov.ph/ `[V]` (HTTP 200; client-rendered SPA; title verified). Fellowship context page: https://fellowship.bettergov.ph/#challenge-energy `[V]`.

**What EO 126 s. 2026 does** (as described in DBM's own press release of 2026-09-30 `[V]`, https://www.dbm.gov.ph/index.php/management-2/4275-follow-every-peso-pbbm-orders-gov-t-wide-disclosure-of-budget-procurement-project-data-through-dbm-compass):
- Institutionalizes COMPASS as *the* government-wide disclosure platform for budget, procurement, project implementation and completion data.
- Requires covered NGAs, GOCCs/GFIs to submit/disclose/update/publish through COMPASS; each agency owns accuracy, completeness, timeliness; non-compliance may trigger administrative/disciplinary sanctions.
- Directs COMPASS to be **capable of interfacing** with IFMIS, BTMS, PhilGEPS, DIME, and the E-Gov PH App "among other systems identified by DBM".
- Creates a **COMPASS Council**: DBM chair, DICT co-chair, DOF and DILG members; empowered to set disclosure standards, timelines, monitor compliance, recommend action.
- Requires **exception/redaction logs** with legal basis, approving authority and date whenever information is withheld; requires standards on integrity, authenticity, interoperability, accessibility, traceability, auditability, cybersecurity, resilience.
- Encourages LGUs; DILG to push COMPASS use and potentially use disclosure as an SGLG criterion.
- Formal text: https://www.officialgazette.gov.ph/2026/09/28/executive-order-no-126-s-2026/ (linked from the fellowship site; direct fetch returned **403 Cloudflare** in this environment `[B]`). The fellowship page itself frames the mission as linking "government datasets and services to DBM COMPASS and the open data ecosystem through open APIs and shared standards" `[V]`.

**Verified COMPASS integration surface — its public API catalog.**
DICT's eGov developer portal publishes a COMPASS API catalog page: https://platforms.e.gov.ph/api-catalogs/compass `[V]` (HTTP 200; Next.js, catalog content embedded in the RSC payload and read by this researcher). Observed facts:
- Catalog entry describes "REST endpoints to securely consume SAAODB, NCA, SARO, and LGSF records and dashboard summaries".
- Authentication: **`X-API-Key` request header** on every endpoint.
- Endpoints documented in the catalog's embedded API reference (base URL is presented as a `{{baseUrl}}` template, so the concrete host is not honestly publishable from the public page): `GET /api/v1/records/saaodb`, `/api/v1/records/saaodb/dashboard`, `/api/v1/records/saaodb/entities`, `/api/v1/records/nca`, `/api/v1/records/saro`, `/api/v1/records/lgsf`, `/api/v1/records/lgsf/dashboard`. Pagination `page` + `limit` (limit max 1000). A Postman collection ("DBM Transparency Portal API") is embedded on the same page. `[V]`
- This is a **read-only budget-execution API**, not a general-purpose write API. `[I]` conclusion from the documented methods/scope.

**Plausible integration surfaces for the energy layer** (ranked by feasibility):
| # | Surface | What it means concretely | Status |
|---|---|---|---|
| 1 | **Join keys, not writes** | Publish DOE/ERC records carrying PSGC codes and UACS codes where applicable, so COMPASS users/agents can join DOE project spend to budget lines. | `[I]` recommended |
| 2 | **Register API + metadata** | List the energy API as an external/public API in DICT's eGov API catalog (`platforms.e.gov.ph`) and register datasets on data.gov.ph. | `[V]` catalog exists; submission process not documented publicly `[I]` |
| 3 | **COMPASS consumption** | If DBM grants a key, consume COMPASS SAAODB/SARO/LGSF data to show energy-program budget vs. project status; keep the key server-side. | `[V]` API documented; key availability unknown |
| 4 | **MCP for agents** | Wrap the energy API in an MCP server (and, where possible, point at COMPASS-backed helpers) so AI clients can query "who sells power at what price in <PSGC>". | `[V]` pattern proven by BetterGovPH Budget API |
| 5 | **Project feeds behind DOE dashboards** | Replace manual DOE dashboard updates with feeds (CSV+API) for RE contracts and priority projects; DIME-style project IDs help COMPASS linkage. | `[I]` target from pitch deck |

**What the fellowship expects** (verbatim from the site `[V]`): connect datasets "through open APIs, metadata standards, MCP-compatible integrations, or other approved mechanisms"; deliver a "working civic-tech solution, platform enhancement, data tool, dashboard, API service"; provide "technical and data-schema documentation, source-code repositories, deployment instructions"; outputs "encouraged to be released under open licenses". Energy challenge deliverables: (a) one master list of suppliers/DUs/ECs published as an API, (b) one price table from the 142 utilities' published rates, (c) feeds + an API behind DOE's RE and priority-project dashboards, aligned with ASEAN Energy Statistics `[V]`.

---

## 2. Philippine open-data ecosystem and what a new energy dataset must publish

| Asset | URL | Observed status 2026-11-10 |
|---|---|---|
| Open Data Philippines (national portal) | https://data.gov.ph/ | `[V]` HTTP 200; Angular SPA, client-rendered; a third-party directory reports the old CKAN `/api/3/action/*` paths are gone (not independently re-verified here). |
| data.gov.ph public API | https://api.data.gov.ph/api/public/dataset/search | `[V]` Anonymous POST returns **HTTP 401** `{"success":false,"message":"API Key not found."}` — i.e., an API key (likely `X-API-KEY`, registered via portal account) is required. The portal's client bundle shows the public routes it calls: `/api/public/dataset/search`, `/api/public/topic/search`, `/api/public/agency/search`, `/api/public/format/search`, `/api/public/dataset/featured`, `/api/public/dataset/{id}/{slug}` — observed in the client JS, **not documented** by the portal, so treat as unstable. |
| DCAT / "DCAT-PH" | https://www.w3.org/TR/vocab-dcat-3/ | `[V]` DCAT 3 is the stable W3C vocabulary. **No published "DCAT-PH" national profile could be verified** on any official site as of 2026-11-10 `[B/I]` — treat "DCAT-PH" as a working name, not a citable spec; publish a documented DCAT-3 profile instead. |
| PSGC (geography) | https://psa.gov.ph/classification/psgc | `[B]` PSA blocks automated fetches (Cloudflare 403). PSGC is the authoritative code system; community JSON mirror https://psgc.gitlab.io/api/ `[V]` (unofficial, useful for prototyping only). |
| FOI portal | https://www.foi.gov.ph/ · DOE agency page: https://www.foi.gov.ph/agencies/doe/ | `[B]` Portal blocks automated fetches; DOE links its agency FOI page `[V]` (seen on doe.gov.ph footer). Use FOI for bulk data requests and for the redaction/exception-log angle in EO 126. |
| DBM COMPASS open data | https://compass.dbm.gov.ph/ · https://platforms.e.gov.ph/api-catalogs/compass | `[V]` Public portal + documented API-key REST API (see §1). |
| UACS (budget codes) | https://uacs.gov.ph/ | `[V]` linked from DBM footer; scheme needed to join energy projects to COMPASS budget lines. Not fetched here. |
| PSA | https://psa.gov.ph/ | `[B]` Cloudflare-blocked for this researcher; PSGC/statistics needed as geography + denominator reference. |
| DOE electricity rates page | https://doe.gov.ph/data-and-prices/electricity | `[V]` HTTP 200; page title "Electricity Rates & Power Market Monitor"; meta description: "Monthly DU electricity rates by customer class, including generation charges, with comparative domestic and international rates". **Client-rendered Next.js**: no JSON/CSV/PDF links in the initial HTML and **no documented public API found** — the rates table is loaded client-side. Do not invent an endpoint; treat as a scraping/partnership target. |
| DOE energy statistics page | https://doe.gov.ph/data-and-prices/energy-statistics | `[V]` HTTP 200; "Official Energy Statistics & Data Sets". Client-rendered; no documented API. |
| DOE legacy DU profiles / power plants | https://legacy.doe.gov.ph/duprofile ; `legacy.doe.gov.ph/sites/default/files/pdf/electric_power/...` | `[B]` Search-indexed (DU profile pages; LOEPP "existing power plants" PDFs) but **connection failed** on 2026-11-10 — do not design against the legacy host until DOE confirms it is supported. |

**Registration/publication checklist for a new energy dataset** `[I]`:
1. Register the dataset + each distribution on **data.gov.ph** with title, description, topics, agency/publisher ("Department of Energy, with …"), formats, update frequency; obtain/ask DBM-DICT for the publishing API key and document the exact metadata fields in the repo.
2. Publish the **API listing** in DICT's eGov API catalog so COMPASS-adjacent teams can discover it (mirror the COMPASS catalog page structure: auth model, endpoints, query params, examples).
3. Publish **DCAT-3 JSON-LD** at a stable URL (e.g. `/catalog.jsonld`) with `dcat:Dataset` → `dcat:Distribution` (API endpoint + CSV/JSON files), `dcat:contactPoint`, `dct:license`, `dct:spatial` (PSGC codes), `dct:temporal`, `dct:accrualPeriodicity` (`MONTHLY` for rates).
4. Publish a **Frictionless `datapackage.json`** next to every bulk release (`name, title, version, created, licenses, resources[{name,path,format,bytes,hash}]`).
5. State **provenance, units, and methodology** in metadata: PHP/kWh, VAT treatment, customer class, month effective, source document, extraction method, reviewer.
6. Use **PSGC codes** for every geographic reference and publish a crosswalk for legacy DOE/ERC names.
7. Version every release by **effective month + release date**, keep immutable snapshots, and keep old versions addressable.

---

## 3. Precedent APIs worth citing (what to copy, what not to)

| Precedent | Base URL / spec | Auth | Granularity / shape | Bulk | Versioning |
|---|---|---|---|---|---|
| **Ember** | https://api.ember-energy.org/v1 · docs https://ember-energy.org/data/api/ `[V]` | Free API key requested by email; `api_key` query parameter appears in the spec (examples `?api_key=MY_API_KEY`) `[V]` | 10 dataset routes (`/electricity-generation/{yearly,monthly}`, `/electricity-demand/...`, `/power-sector-emissions/...`, `/carbon-intensity/...`, `/installed-capacity/monthly`, `/options/{dataset}/{temporal_resolution}/{filter_name}`); records like `{entity, entity_code, date, series, generation_twh, share_of_generation_pct}`; every response carries a `Stats` block (`timestamp, response_time_in_seconds, rate_limit, number_of_records, query_parameters_used`) `[V]` | Dataset download pages (Yearly/Monthly Electricity Data) — API + files `[V]` | URL `/v1`; OpenAPI `info.version` = 1.2.3 `[V]` |
| **US EIA API v2** | https://api.eia.gov/v2/ · docs https://www.eia.gov/opendata/documentation.php `[V]` | Required `api_key` query param; key registration at `/opendata/register.php` (from 403 JSON `API_KEY_MISSING`) `[V]` | Self-documenting hierarchical routes (`/v2/electricity` → child routes → `/data`), `facets[…]`, `frequency`, `start/end`, chosen `data[]` columns; response echoes the request and the API version; values returned as strings; errors and warnings separated `[V]` | Bulk files offered separately (not verified here) `[I]` | v2 announced in docs; patch-level changelog (v2.1.12, March 2026) with behavioural fixes `[V]` |
| **OEDI (US DOE)** | https://data.openei.org/ · data lake `https://oedi-data-lake.s3.amazonaws.com/` `[V]` | None for public data; content CC-BY-4.0 unless noted `[V]` | Catalog of datasets/submissions + "data lakes" (curated collections); no documented query REST API was found — access is file/dataset-centric `[V/I]` | Yes — S3 bucket list returns XML `ListBucketResult` (public bulk listing, 1000 keys/page, e.g. `ATB/`) `[V]` | Immutable S3 keys/datasets `[I]` |
| **Open Power System Data** | https://data.open-power-system-data.org/ `[V]` | None | 5 core + contributed **data packages**; each package = Frictionless `datapackage.json` listing `resources[{name,title,description,path,format,mediatype,bytes,hash}]` (verified on the `time_series` package) `[V]` | Only bulk: dated ZIPs per release (e.g. `time_series/2020-10-06/…zip`); no API `[V]` | Release date in path (`2020-10-06`), immutable versions, docs per release `[V]` |
| **ENTSO-E Transparency Platform** | Platform https://transparency.entsoe.eu/ · data page https://www.entsoe.eu/data/transparency-platform/ `[V]`; API base `https://web-api.tp.entsoe.eu/api` `[V]` | Security token required: request without token returns **HTTP 401 + XML `Acknowledgement_MarketDocument`** (no JSON error) `[V]`; publication mandated by Regulation (EU) 543/2013 `[V]` | Domain-based XML market documents (load, generation, prices, etc.), IEC 62325-style XML namespaces `[V]` | Not verified `[I]` | Not verified `[I]` |
| **ASEAN Centre for Energy** | https://www.aseanenergy.org/projects/aeds (AEDS) `[V]`; ASEAN Energy Statistics Leaflet 2025 https://aseanenergy.org/publications/asean-energy-statistics-leaflet-2025/ `[V]`; AEDS revamp workshop `[V]` | Not applicable — portal/publications; no documented public API found `[I]` | Country/sector statistics and dashboards; AEDS is being revamped `[V]` (workshop article title) | Publications/leaflets (PDF) `[V]` | Editions (e.g. AESL 2025, data 2005–2023 per publisher description) `[V]` |

**Synthesis — what most influenced the v1 recommendation:**
- **Ember** → single versioned base URL, dataset-oriented routes, stats/rate-limit envelope, API key, `/options` endpoint for enumerations.
- **EIA v2** → self-describing hierarchy (`/v1/datasets` → resources), explicit facets/filters, request echo for debugging, documented changelog.
- **OPSD + OEDI** → dated immutable bulk releases + Frictionless datapackage + hashes; "the mirror is the product" when source sites are fragile.
- **BetterGovPH Budget API** (local precedent, see §5) → the closest cultural/technical model: no-auth public REST, OpenAPI 3.1, cursor pagination, `{meta,data,next_cursor}` envelope, disclaimers/provenance in every response, and an MCP server over the same data.
- **ENTSO-E** → shows why a machine-readable API matters when publication is mandated, but also that government-grade APIs can require registration/tokens — plan for a keyed mode even if v1 is anonymous.

---

## 4. Standards & interoperability decisions

| Decision | Recommendation | Evidence |
|---|---|---|
| API description | **OpenAPI 3.1** (3.2.0 is published and usable; 3.1 has widest tooling today). Serve `/openapi.json`, render docs, commit the spec to the repo and CI-diff it. | https://spec.openapis.org/oas/v3.2.0.html `[V]`; https://spec.openapis.org/oas/v3.1.1.html `[V]`; Budget API publishes 3.1 at `/api/v1/openapi.json` `[V]` |
| Tabular/bulk packaging | **Frictionless Data Package v1** (`datapackage.json`) + CSV files + SHA-256 per resource; also emit Parquet if cheap. | https://specs.frictionlessdata.io/data-package/ `[V]`; OPSD uses exactly this shape `[V]` |
| Catalog metadata | **DCAT 3** JSON-LD (`dcat:Dataset`, `dcat:Distribution`, `dct:spatial`, `dct:temporal`, `dct:license`, `dcat:contactPoint`); document it as a local profile, not as "DCAT-PH". | https://www.w3.org/TR/vocab-dcat-3/ `[V]`; data.gov.ph registration aligns discovery `[V]` |
| MCP-compatible integration | **MCP spec 2026-07-28**, JSON-RPC 2.0; transport **Streamable HTTP** (single endpoint, POST → JSON or request-scoped SSE) or stdio for local use. Expose read-only **tools** (and optionally resources) that return the same envelopes as REST. Keep the server stateless; don't require auth in v1 (rate-limit instead); put disclaimers in server instructions. | https://modelcontextprotocol.io/specification/2026-07-28 `[V]`; transports `[V]`; working local example: Budget API `/mcp` + 25 documented read-only tools `[V]`; data.bettergov.ph `/mcp` with 7 tools `[V]` |
| Caching / ETag | `ETag` + `If-None-Match` on every collection and bulk file; `Cache-Control: public, max-age=300, s-maxage=3600` for data (Budget API does exactly this) and `max-age=86400` for immutable dated files; `Last-Modified` on source documents. | Budget API docs `[V]` |
| Rate limits | Publish committed limits in docs (e.g. anonymous 60 req/min/IP, 10k/day; bulk only via mirror), return `429` + `RateLimit-Limit/Remaining/Reset` (or document headers used); require a descriptive `User-Agent` with contact and crawl politely under each source's robots/terms. Ember exposes `rate_limit` in responses — a good pattern. | Budget API fair-use + UA request `[V]`; Ember `Stats.rate_limit` `[V]` |
| Provenance fields | On every rate row: `source_document_id`, `source_url`, `source_publisher`, `source_document_date`, `fetched_at`, `extraction_method`, `data_status` (`official`/`derived`/`editorial`), `confidence` (`high`/`medium`/`low`), `reviewed_by`, `reviewed_at`, `valid_from`, `valid_to`, `supersedes`. Budget API's `upstream_restrictions_url` + per-figure disclaimers are the local pattern. | Budget API docs `[V]` |
| Licensing | Data **CC-BY-4.0**; code **MIT** (or CC0 for snippets/design); source PDFs **linked, not rehosted**, unless DOE/ERC terms explicitly allow; preserve attribution "Department of Energy / ERC / NEA / utility name" and the coalition. PH gov default: "All content is in the public domain unless otherwise stated" (seen on doe.gov.ph footer) `[V]`; Ember and OEDI both CC-BY-4.0 `[V]`. |

---

## 5. Existing PH civic-tech / BetterGovPH assets — reuse, complement, don't duplicate

**Verified BetterGovPH repos** (GitHub API `api.github.com/orgs/bettergovph/repos`, 2026-11-10 `[V]`). Notable:
- `open-data-portal` (CC0) → live at **https://data.bettergov.ph/** `[V]`: community dataset catalog API (OpenAPI 3.1, paths `/api/v1/datasets`, `/datasets/{id}`, `/publishers`, `/categories`, `/resources`, `/resources/{id}`, `/stats`, `/ping`) **and** MCP at `/mcp` with 7 tools (`get_stats`, `list_categories`, `list_publishers`, `search_datasets`, `get_dataset`, `list_resources`, `get_resource`) `[V]`. Metadata fields already modeled: `name, description, publisher_id, category_id, tags, size_bytes, latest_version_date, attribution[{authors, source_url, attribution_text, license, license_url}], license, license_url`; resources: `mime_type, size_bytes, download_url, source_url` `[V]`. **25 datasets listed, none energy-specific** — a clear, cheap win is to register the energy layer as a publisher+datasets here. Repo's `wrangler.toml` reserves `/api/*`, `/docs*`, `/openapi*`, `/mcp`, `/llms.txt` `[V]`.
- `open-budget-api` / `open-budget-data` (CC0) and the **live Budget API https://budget.bettergov.ph/** `[V]` — the strongest template in the ecosystem: no-auth public REST, OpenAPI 3.1 (34 paths), `{meta,data,next_cursor}` envelope, documented error slugs (`bad_cursor`, `not_found`, `not_loaded`, `query_failed`), keyset cursors (limit 1–500), CORS `*`, edge caching, Terms/Disclaimer pages, "upstream restrictions" carried per figure, and an MCP server (Streamable HTTP, stateless, 25 documented read-only tools) at `/mcp`. `[V]`
- `transparency-portal` (MIT), `transparency-dashboard` (MIT), `flood-watch` (MIT), `kapwa` design system (CC0), `open-congress-api` (CC0), `open-philgeps-data`, `ph-tax-directory` (CC0), `hotlines`. Org-wide: **no energy project/repo exists** `[V]` — the fellowship challenge is greenfield for BetterGovPH.
- BetterGovPH projects page lists 29 live tools incl. `budget.bettergov.ph`, `data.bettergov.ph`, `philgeps.bettergov.ph`, `price-guides.bettergov.ph`, `transparency.bettergov.ph` `[V]`; `philgeps.bettergov.ph` returned a Cloudflare 1016 error on 2026-11-10 (origin DNS error) — don't hard-depend on it `[V]`.

**Existing PH efforts to complement, not duplicate:**
- **PRESYO-PH (ICSC)** — app https://presyo.icsc.ngo/ `[V]` (SPA using MapLibre/Plotly/deck.gl; no documented API found `[V/I]`), project page https://icsc.ngo/power-supply-overview/ `[V]`. Launched 2026-04-28, consolidates rates and supply data for **150+ DUs/ECs**, focuses on generation charge and supply mix, browser-first (Chrome) `[V]` (Power Philippines, 2026-04-28: https://powerphilippines.com/icsc-launches-presyo-ph-web-app-to-help-consumers-understand-power-costs/). **Recommendation:** make PRESYO-PH a link-out/consumer of the open API, not a competing product; the fellowship's edge is the open, citable, versioned data layer behind all such tools.
- **DOE** rate/statistics pages (§2) and **ERC/NEA** source documents: ERC monthly generation-charge postings (pitch-deck stretch goal; ERC site https://www.erc.gov.ph/ blocked 403 here `[B]`), NEA electric-cooperative directory (https://www.nea.gov.ph/ blocked 403 `[B]`), DOE's own monthly DU rates page `[V]`.
- **Market data:** IEMOP (https://www.iemop.ph/ `[V]`; market data at `/market-information/market-data` `[V]`, WESM Rates / Daily Operations Reports) and PEMC/WESM (https://www.wesm.ph/ — not fetched here). Useful for `generation_charge` + WESM reference prices, not as the retail rates source.
- **Procurement/budget:** PhilGEPS (https://philgeps.gov.ph/Indexes/login `[V]` link from DBM), COMPASS `[V]`, and `data.bettergov.ph` dataset "Open PhilGEPS Data" `[V]`.

---

## 6. Recommended v1 API shape

> Proposed only. Deploy under a fellowship-controlled host (e.g. the existing BetterGovPH Cloudflare/Pages setup), publish the OpenAPI spec before the demo, and state clearly when data is derived vs. official.

**Base & versioning.** `https://<host>/v1` with `/v1` frozen after Demo Day. Additive changes only in v1; `/v2` for breaking changes; per-dataset schema version in metadata; `Deprecation` + `Sunset` headers with **≥90 days** notice; CHANGELOG.md + machine-readable `/v1/changelog.json`.

**Resources (proposed):**
| Resource | Keys / fields | Notes |
|---|---|---|
| `GET /v1/utilities` | `id, name, short_name, type (DU/EC/supplier/IPP/cooperative), operator, psgc_province, psgc_city_municipality, region, franchise_area[], licenses[], source_ids[], updated_at` | Master list = deliverable (a). Cursor pagination, filters `type, region, q`. |
| `GET /v1/utilities/{id}` | profile + `latest_rate`, `rate_history_url`, `source_documents[]`, `crosswalks[]` (ERC ID, DOE legacy name, NEA EC ID) | Stable ID is the whole point; document the ID scheme. |
| `GET /v1/rates` | `utility_id, month (YYYY-MM), customer_class, price_php_per_kwh, generation_charge_php_per_kwh, transmission, distribution, subsidies, taxes, currency, unit, source_document_id, data_status, confidence, reviewed_by, reviewed_at` | Deliverable (b). Filter by `month`, `utility_id`, `customer_class`; aggregate endpoints later. |
| `GET /v1/rates/{utility_id}/history` | monthly series for one utility | Small, cacheable, 30-day cache. |
| `GET /v1/projects` | `id, name, type (RE contract / priority project), technology, capacity_mw, status, psgc_location, doe_project_id, dime_id?, amount_php?, source_document_id, updated_at` | Deliverable (c) feed for DOE dashboards. |
| `GET /v1/sources` | `id, publisher, title, url, document_type (PDF/web table/FB post), document_date, fetched_at, sha256, extraction_method, licence_status` | "Source document" provenance registry. |
| `GET /v1/sources/{id}` | metadata + `used_by[]` (rate/project ids) + `archive_url` | Every published number must resolve to one of these. |
| `GET /v1/datasets` | DCAT-3-lite catalog of the API's own datasets/distributions + `datapackage_url`, `openapi_url` | Discoverability + COMPASS/eGov catalog listing. |
| `GET /v1/meta` | service name, version, commit, data vintage, rate limits, licence, disclaimers | Trust surface. |
| Editorial (auth-gated, not public v1) | `POST /v1/admin/records/{id}/review`, `POST /v1/admin/records/{id}/publish`, `POST /v1/admin/records/{id}/correct` | `X-API-Key`/OIDC, reviewer identity, audit log. Model `draft → in_review → published → superseded`; corrections are new versions, never silent overwrites. |

**Response envelope** (copy Budget API `[V]`):
```json
{"meta":{"dataset":"rates","currency":"PHP","unit":"php_per_kwh","source":"ERC/DOE/utility","generated_at":"…","licence":"CC-BY-4.0","matched":142},"data":[…],"next_cursor":"…","disclaimers":["…"]}
```
**Errors** (JSON, machine-readable slug + message + request id): `{"error":{"code":"bad_cursor","message":"…","request_id":"…"}}`; statuses 400 `bad_request`/`bad_cursor`, 404 `not_found`, 405 `read_only`, 409 `stale_version`, 429 `rate_limited`, 503 `upstream_unavailable`. Optionally emit `application/problem+json` (RFC 9457) from the same URLs `[I]`.

**Pagination & filtering.** Opaque keyset `cursor` + `limit` (default 100, max 500) for large collections; `limit/offset` only for small admin lists; every list echoes `meta.matched` / `meta.matched_amount` where meaningful (Budget API pattern) so one call answers "how many/how much".

**ASEAN alignment.** Name indicators and units so they can be mapped 1:1 to ASEAN Energy Statistics concepts (capacity MW, generation GWh/TWh, price PHP/kWh with explicit currency+unit fields), and keep an `asean_concept` crosswalk column in bulk files rather than renaming the agency's original terms `[I]`.

**Bulk mirror.** `GET /v1/bulk/` → `catalog.json` listing dated artifacts: `sources/YYYY-MM-DD/datapackage.json`, `utilities/YYYY-MM-DD.csv`, `rates/YYYY-MM-DD.csv`, `projects/YYYY-MM-DD.csv`, each with `bytes`, `sha256`, `row_count`, `created`. Immutable URLs, 1-day cache; regenerated on every publish; also mirrored to GitHub Releases so availability does not depend on one host.

**MCP wrapper (5 tools, read-only, stateless Streamable HTTP at `/mcp`):**
1. `search_utilities({q?, type?, region?}) → {meta,data[],next_cursor}`
2. `get_utility({utility_id}) → profile + latest rate + sources`
3. `get_rate_history({utility_id, from_month?, to_month?, customer_class?}) → monthly series + provenance per row`
4. `search_projects({type?, region?, status?, technology?}) → RE/priority project feed rows`
5. `get_source_document({source_id}) → URL, fetched_at, sha256, used_by[]`
Each tool returns the same JSON envelope as REST, includes disclaimers in `meta`, and errors return `isError: true` with a fixable message (Budget API MCP convention `[V]`). Tool descriptions must tell agents to cite `source_url` and never present derived rows as official. `[I]`

**COMPASS linkage mechanics** `[I]`: (a) register the API/datasets in the DICT eGov catalog + data.gov.ph; (b) emit `psgc_*` and `uacs_*` join fields in `utilities` and `projects`; (c) publish a quarterly crosswalk CSV `energy_projects ↔ COMPASS SAAODB/SARO/LGSF rows` with match status and unmatched reasons (mirrors how the Budget & Procurement challenge expects unmatched records explained); (d) keep COMPASS API keys server-side; never leak them to MCP clients.

**Governance recommendation:**
- **Who publishes:** DOE (challenge owner) as data authority; coalition (Mura, Malinis, at Maaasahang Kuryente Coalition) as editorial reviewer/"checks every number"; fellowship team as operator; BetterGovPH as host/maintainer during the pilot. Handover plan to DOE/DICT at pilot end.
- **SLA:** rates refreshed **monthly within 5 business days** of ERC/DOE publication; master list re-synced weekly and on notice; source-document fetch failures surfaced in `/v1/meta`; 99% best-effort on static mirror, API best-effort with status page; corrections acknowledged in ≤2 business days.
- **Licence:** data CC-BY-4.0 with attribution string; code MIT; source PDFs linked not rehosted; a `LICENSE` + per-dataset `licence` field and a rights note for utility-published posts (utility terms may be stricter than government terms — link out).
- **Breaking-change policy:** additive-only v1; deprecate with 90-day notice + migration note; never renumber stable IDs; frozen snapshots remain downloadable forever.
- **Review rights:** DOE/coalition can unpublish a row instantly (status `withdrawn`, reason logged); public corrections page.

---

## 7. Risks and mitigations

| # | Risk | Evidence | Mitigation |
|---|---|---|---|
| 1 | **No documented DOE API; SPA-loaded tables** | doe.gov.ph electricity/statistics pages are client-rendered with no API/CSV links `[V]` | Treat as scraping/partnership target; snapshot evidence; agree with DOE focal person on a machine feed (CSV drop or API) — this is exactly deliverable (c). |
| 2 | **Bot protection blocks automated access** | PSA, FOI, ERC, NEA returned Cloudflare 403 in this environment `[B]` | Manual/assisted acquisition; FOI requests for bulk data; keep a human-in-the-loop curator; publish only what can be lawfully and reliably obtained; request allowlisting via DOE invitation. |
| 3 | **142 utilities publish via PDFs, web tables and Facebook posts** | Fellowship challenge page `[V]`; pitch-deck reality (per Lead extraction) | Source-document registry + per-utility `access_method`; parse only where permitted; prioritize utilities with stable pages; mark `confidence` low for OCR'd/FB-sourced rows; weekly coalition review. |
| 4 | **No common utility ID across ERC/DOE/NEA** | Pitch-deck ground truth (Lead, 2026-11-10); DOE legacy DU pages unverified `[B]` | Make the new ID the canonical key and publish crosswalks; never reuse agency IDs as primary keys; version the crosswalk. |
| 5 | **data.gov.ph API requires a key; metadata fields undocumented** | 401 `API Key not found` `[V]`; endpoints only observed in client JS | Ask DBM/DICT for publishing credentials + field documentation early; in the meantime publish DCAT JSON-LD and a raw CSV mirror that need no key. |
| 6 | **COMPASS interface scope unclear; write access unlikely** | COMPASS API catalog is read-only, keyed `[V]` | Frame integration as metadata + join keys + read-side consumption; don't promise write-back; get DBM confirmation in writing before Demo Day. |
| 7 | **Legal/language constraints** | Data Privacy Act concerns for owner/contact fields; EO 126 redaction-log duty; bilingual/Taglish content and regional place names `[I]` | Ship only business/entity data; no personal data; honor redaction logging; support English + Filipino labels; PSGC-based location matching with alias table. |
| 8 | **Vendor lock-in / project death after March 2027** | Single-team pilot, 3 months, no maintenance guarantee `[I]` | Static mirror + GitHub Releases + documented restore; infrastructure-as-code; open licence so anyone can fork; handover runbook as a fellowship deliverable. |
| 9 | **Presyo PH / other trackers perceived as duplicates** | PRESYO-PH live `[V]` | Position as the open data layer + API behind such tools; link out; invite ICSC to consume; avoid cloning their UI. |
| 10 | **Entry-point volatility** | `philgeps.bettergov.ph` Cloudflare 1016; DOE legacy host connection failure; "DCAT-PH" not verifiable `[V/B]` | Prefer durable official sources; monitor links; maintain `sources.archive_url`; don't cite unstable endpoints in public docs without a `[B]`/unstable note. |

---

## 8. Open questions to resolve with DOE / DBM / DICT (first sprint)

1. Does DOE have a machine-readable feed — or will it provide a monthly CSV drop — for DU rates and RE/priority projects? Who owns it?
2. Can DOE provide/confirm the canonical supplier/DU/EC list and names (and the mapping to ERC/NEA identifiers)?
3. Will DBM grant a COMPASS API key to the fellowship team, and is read-only SAAODB/SARO/JOIN acceptable use?
4. Will DICT/DBM accept a DCAT-3 document and eGov API-catalog listing as the submission mechanism for an external API?
5. ERC: may monthly generation-charge PDFs be parsed and republished as derived data with attribution, or must they be linked only?
6. Which customer class(es) does "price per kWh" mean — residential average, per-utility, VAT-inclusive? (The challenge page cites ₱12.43/kWh June 2026 national average `[V]`.)
7. Preferred bilingual presentation (English/Filipino) and any restrictions on utility-published social-media content.

---

## 9. Sources (accessed 2026-11-10; `[B]` = blocked)

**Verified `[V]`:** fellowship.bettergov.ph (challenge + requirements) · dbm.gov.ph press release 2026-09-30 (EO 126) · compass.dbm.gov.ph · platforms.e.gov.ph/api-catalogs/compass (COMPASS API reference, embedded) · data.gov.ph (+ api.data.gov.ph 401) · psgc.gitlab.io/api (unofficial mirror) · doe.gov.ph/data-and-prices/electricity · doe.gov.ph/data-and-prices/energy-statistics · iemop.ph (+ /market-information/market-data) · presyo.icsc.ngo · icsc.ngo/power-supply-overview · powerphilippines.com (Presyo PH launch, 2026-04-28) · ember-energy.org/data/api · api.ember-energy.org/v1/openapi.json · eia.gov/opendata/documentation.php · api.eia.gov/v2 (403 API_KEY_MISSING) · data.openei.org · oedi-data-lake.s3.amazonaws.com (public bucket) · data.open-power-system-data.org (+ datapackage.json) · entsoe.eu/data/transparency-platform · web-api.tp.entsoe.eu/api (401 XML) · aseanenergy.org/projects/aeds · aseanenergy.org/publications/asean-energy-statistics-leaflet-2025 · aseanenergy.org AEDS-revamp article · spec.openapis.org/oas/v3.2.0.html · specs.frictionlessdata.io/data-package · w3.org/TR/vocab-dcat-3 · modelcontextprotocol.io/specification/2026-07-28 (+/basic/transports) · budget.bettergov.ph/docs + /api/v1/openapi.json + /mcp · data.bettergov.ph (+ /openapi.json, /mcp, /api/v1/ping) · github.com/bettergovph (+ GitHub REST API org repos: 37 public repos, none energy-specific) · about.bettergov.ph/projects · pasarapi.xyz/a/data-gov-ph (third-party status note on data.gov.ph).

**Blocked/blocked-by-environment `[B]`:** officialgazette.gov.ph (EO 126 text, Cloudflare 403) · psa.gov.ph/classification/psgc · foi.gov.ph · erc.gov.ph · nea.gov.ph · legacy.doe.gov.ph (connection failure) · businessmirror.com.ph (403) · transparencyplatform.zendesk.com (403) · decorp.com.ph generation-charge page (connection failure). **Unverified / not found:** a published "DCAT-PH" profile; an OEDI query API; an AEDS public API; any BetterGovPH energy repo.

**Ground truth not from web:** Energy pitch-deck details (master-list split across ERC/DOE/NEA, rate schema, ERC stretch goal, sprint/editorial reality) supplied by the Lead from the consolidated fellowship deck on 2026-11-10; this researcher did not independently parse the deck (link on file: https://docs.google.com/presentation/d/1aYTkTqNYfPGnIhzDBXXSsJqjk-NBTYA90yoSDfHgEcA/edit).
