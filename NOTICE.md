# Third-party notices, attribution and data provenance

This repository reuses third-party assets and builds on public data. This file
records what those are, their terms, and what this project does **not** claim.
The MIT licence in [LICENSE](LICENSE) covers this project's own code, generated
page and design layer; it does not override or relicense anything below.

| Component | Where it lives | Terms | Attribution / note |
| --- | --- | --- | --- |
| BetterGovPH design language | page + review hub | MIT (© 2026 BetterGov.ph) | Design tokens, type roles, masthead/subnav/rule-table/footer patterns adapted from BetterGovPH's `transparency-portal` (MIT); the page is our implementation, not a BetterGov.ph code import. |
| Fonts — Figtree, Inter, JetBrains Mono | `draft/assets/fonts/*.woff2` | SIL Open Font License 1.1 | Latin variable subsets, unmodified. © 2022 The Figtree Project Authors, © 2020 The Inter Project Authors, © 2020 The JetBrains Mono Project Authors. |
| Icons — Lucide | `draft/assets/brand/` icon sprite | ISC License; Feather-derived icons MIT | © Lucide Icons and Contributors (ISC). Icons derived from Feather: © 2013-present Cole Bemis (MIT). Exact pinned versions and vendored notices: `draft/assets/brand/README.md`. |
| Philippine region geometry | `draft/assets/geo.json` | MIT (repository scripts/maps, © James Faeldon); boundaries **CC BY 3.0 IGO** | Derived from `faeldon/philippines-json-maps` v1.1.1; boundary attribution: © NAMRIA and the Philippine Statistics Authority, via OCHA's Philippines COD-AB (CC BY 3.0 IGO). Full provenance in `draft/assets/geo-sources.json`. |
| BetterGovPH brand assets | `draft/assets/bettergov-logo.png`, `draft/assets/favicon.svg`, `draft/assets/brand/` | BetterGovPH brand property — **not** MIT | Used with attribution for this BetterGovPH open-data project. See the brand note below. |
| DOE workbook data | `data/raw/`, `data/seed/` | **No licence confirmed** — none asserted here | Published public records from the Department of Energy. See the data note below. |
| Python build dependencies | `requirements.txt` | PyYAML: MIT; markdown-it-py: MIT | Build tooling only; not served. |
| Browser QA dependency | `package.json`, `tests/` | Playwright: Apache-2.0 | Test/CI tooling only; not served or shipped in the page. |

## BetterGovPH design language

The visual language of the generated page — typography roles (Figtree for
display, Inter for text, JetBrains Mono for metadata), BetterGov blue, white
paper, rule-based tables, masthead/subnav/footer structure — is adapted from
BetterGovPH's `transparency-portal` repository, which is MIT-licensed
(© 2026 BetterGov.ph) and mirrors `budget.bettergov.ph`. That MIT licence
permits reuse and adaptation; the adaptation in this repository is itself
released under the MIT licence in [LICENSE](LICENSE).

## Brand assets (BetterGovPH)

The BetterGov logo, emblem and favicon are the brand property of BetterGovPH
and are **not** covered by this project's MIT licence. They are used here,
unmodified and with attribution, to identify this work as part of the
BetterGovPH open-data design family. Nothing in this repository implies that
this project is an official BetterGov.ph product or that BetterGovPH endorses
it. Before any independent deployment, the deploying party should obtain the
brand owner's approval for the mark's use, or replace it with their own mark.
If the brand owner asks for a change, the assets will be updated or removed.

## Fonts

Three `woff2` files under `draft/assets/fonts/` are the *latin variable*
subsets of Figtree, Inter and JetBrains Mono, taken from Google Fonts and
inlined into the page as data URIs at build time (they are unmodified font
software). Each is licensed under the **SIL Open Font License, Version 1.1**
(OFL 1.1), which permits embedding and redistribution in this form; the
fonts are not sold separately, no Reserved Font Name is used, and the
required copyright notices are the ones listed in the table above. The OFL
text for each family is available from the Google Fonts repository
(`google/fonts`, `ofl/<family>/OFL.txt`) and from the font projects themselves.

## Icons

Interface icons come from the open-source **Lucide** icon set. The Lucide
project's licence is the **ISC License** (© Lucide Icons and Contributors);
Lucide also states that a listed subset of its icons derives from the Feather
project and remains under the **MIT License** (© 2013-present Cole Bemis). Both
are permissive and compatible with this repository's MIT licence. The icon
sprite is vendored (not loaded from a CDN), so the page makes no external
requests; the pinned version and the vendored notice live in
`draft/assets/brand/`.

## Philippine region geometry

`draft/assets/geo.json` is a simplified, projected Philippine region boundary file (18
PSGC 3Q 2026 regions, including NIR and BARMM) built by `tools/build-geo.py` from
`faeldon/philippines-json-maps` release **v1.1.1** (TopoJSON, level `regions`, resolution
`hires`).

- That repository's **scripts and map files are MIT-licensed** (© James Faeldon).
- The **boundaries are licensed CC BY 3.0 IGO**: they are derived from NAMRIA and the
  Philippine Statistics Authority data, via OCHA's Philippines Common Operational Dataset
  for Administrative Boundaries (COD-AB). Required attribution:
  *"Province boundaries: © NAMRIA and the Philippine Statistics Authority, via OCHA's
  Philippines COD-AB, licensed CC BY 3.0 IGO."*
- This repository inlines a simplified derivative of that data for a schema-level
  choropleth (18 PSGC regions) and for the provider service-area overlay (1,642 city /
  municipality polygons in `draft/assets/coverage-geo.json`, built from the same release's
  province/district TopoJSON files); it is not an authoritative boundary dataset. Full
  provenance — source release, archive and per-file SHA-256 hashes, the pinned checksums
  file, projection, simplification parameters and evaluated alternatives — is recorded in
  `draft/assets/geo-sources.json`. Reusers of the geometry should preserve the CC BY 3.0
  IGO attribution above.

## Department of Energy (DOE) workbook data

The rates, utility list and aggregates in `data/seed/` are derived from the
DOE **"Electricity Rates & Power Market Monitor"** workbook — a public Google
Sheet embedded on `doe.gov.ph/data-and-prices/electricity` — retrieved through
its public CSV export on **2026-11-10** (dataset version `2026-11-10`).

- **No dataset-specific licence has been confirmed with DOE.** The DOE website
  footer states that its content is in the public domain "unless otherwise
  stated", but this project does not treat that general statement as a
  confirmed licence for the workbook, and **this repository does not assert a
  licence over the workbook or over the figures extracted from it.**
- What this repository publishes is a derived factual extract (utility
  registry, monthly rate observations, region aggregates) together with
  provenance: the DOE page and sheet URLs, the retrieval timestamp, the row
  and tab each value came from, and a SHA-256 hash of the raw tab bytes. The
  raw byte snapshots in `data/raw/doe-rates/` exist so that a published number
  can be reproduced from exactly the publisher bytes we saw; they are not a
  republication of the workbook as a dataset.
- **No endorsement by DOE is implied.** DOE is the publisher of the source
  workbook; it has not reviewed, approved or licensed this extract.
- Reusers should cite the DOE workbook and this retrieval date, and should
  satisfy themselves about DOE's terms. Confirming the workbook's ownership,
  refresh cadence and licence/citation terms with DOE is a **week-1
  partnership ask** recorded in `research/data-landscape.md`.
- If DOE asks for changes to how the source data is
  presented or redistributed, the project will comply and update this notice.

Generated files — `data/seed/*.csv`, `data/seed/page-data.json`,
`data/seed/validation.json` (built by `tools/ingest-doe-rates.py`), the service-area
dataset (`tools/build-service-areas.py`), the static JSON API under `draft/api/v1/` (built
by `tools/build-api.py`), the docs site under `draft/docs/` (built by
`tools/build-docs.py`) and the page `draft/map-table-prototype.html` (built by
`tools/build-map-page.py`) — are produced by this project's build tooling. The MIT licence applies to the generator code and to the
project's own markup/design; it does not relicense the underlying DOE figures, whose terms
remain as described above.

## Service-area coverage data (`data/seed/service_areas.csv`)

The provider filter draws each distribution utility's service area. That layer is derived
data, **not** part of the DOE rate workbook, and it carries its own licences:

- **Meralco** — Republic Act No. 12146 (approved 11 April 2025), Section 1, which renews the
  Meralco distribution franchise and enumerates its territory. The text was retrieved from
  the Supreme Court E-Library (<https://elibrary.judiciary.gov.ph/thebookshelf/showdocsfriendly/2/98850>,
  2026-11-10). Philippine laws are public documents; the official text is not subject to
  copyright. The franchise area is encoded LGU-by-LGU against PSGC 3Q 2026; the law wins
  over the secondary sources below.
- **Other distribution utilities** — LGU-level franchise areas from the OpenStreetMap Wiki
  page *"Power networks/Philippines/Operators"*, revision 2836797 (2025-04-14), which
  tabulates franchise areas "per Department of Energy". That page is licensed
  **CC BY-SA 2.0**; required attribution:
  *"Service areas: © OpenStreetMap Wiki contributors, 'Power networks/Philippines/Operators',
  revision 2836797 (2025-04-14), CC BY-SA 2.0."*
- **Supplementary LGU areas** for 22 utilities the OSM page lists without a franchise-area
  table come from Wikipedia, *"List of electric distribution utilities in the Philippines"*,
  revision 1374171231 (2026-09-10), licensed **CC BY-SA 4.0**; required attribution:
  *"Additional service areas: © Wikipedia contributors, 'List of electric distribution
  utilities in the Philippines', revision 1374171231 (2026-09-10), CC BY-SA 4.0."*
- **Fallback** — where no LGU-level area is sourced, the DOE workbook's region assignment
  is published as a labelled region-level area. The 2026 edition of the dataset needed zero
  fallbacks; the mechanism and its label remain in the contract.
- The **combined coverage dataset** (`data/seed/service_areas.csv`,
  `data/seed/service_area_sources.csv` and the derived LGU overlay) is a **CC BY-SA
  derivative** of the sources above: attribution to the OpenStreetMap Wiki and Wikipedia
  contributors (and share-alike for the derived coverage database) is required. The
  project's MIT licence applies to the assembler code and to the page's own markup, not to
  this derived dataset. Per-row source ids and revision/retrieval metadata are published in
  `service_area_sources.csv`; the extraction method, pinned wikitext snapshots and known
  gaps are documented in `research/coverage/README.md`.
- The coverage data is **not an official DOE publication** and implies no endorsement. It
  records partial-coverage notes where an LGU is split between utilities, and documents
  PSGC 3Q 2026 region reassignments instead of forcing legacy DOE region labels.

## Names and trademarks

"Department of Energy", "DOE", "BetterGov.ph", "BetterGovPH", utility and
electric-cooperative names, and any other third-party names are used
nominatively to identify the sources and the entities being described.
Trademarks and brand rights remain with their respective owners. This project
is not affiliated with, or endorsed by, any of the named utilities or
agencies.
