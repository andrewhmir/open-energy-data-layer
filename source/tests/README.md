# Testing and validation

Three complementary layers guard the open energy data layer:

| Tool | What it proves | Speed | Network |
| --- | --- | --- | --- |
| `tools/validate.py` | The repository contracts are internally consistent: seed payload, CSVs, geometry, built page, OpenAPI, static JSON API, packaging — and (with `--check-page`) that the committed page is byte-for-byte reproducible from the committed data/assets. | ~0.3 s (+ ~2 s rebuild) | none |
| `tests/qa.mjs` | The built page actually works in a real browser: data renders, interactions, accessibility hooks, zero console errors, zero external requests, no horizontal overflow. | ~25 s | none at runtime |
| `tests/qa-docs.mjs` | The generated documentation site (`draft/docs/`) works: every page loads, navigation/TOC/code copy/pager/full-text search behave, all internal links and fragments resolve, no third-party requests, no overflow at desktop or mobile. | ~15 s | none at runtime |

All three run fully offline against files in the checkout (the docs suite starts its own local HTTP server); CI runs them on every push and pull request to `main`.

## 1. Static validation

```bash
python3 -m pip install -r requirements.txt
python3 tools/validate.py              # fast static pass
python3 tools/validate.py --check-page # + rebuild the page twice in a temp copy and compare
python3 tools/validate.py --strict     # warnings become failures
```

Exit code `0` only when every hard check passes; failures are printed with the
exact file/contract that broke and a suggested fix. Checks are contract-based
(JSON schema-ish invariants, row counts, required columns, embedded-payload
equality, anchors, PSGC coverage), never file hashes, so a data refresh or a
copy edit does not need test changes unless the contract itself changes.

What `tools/validate.py` checks:

- **Repository files** — page, seed JSON/CSVs, geometry, fonts, OpenAPI, API
  docs, README, licence, requirements, package manifest, CI workflow, the three
  architecture guides (`draft/frontend.md`, `draft/backend.md`,
  `draft/component-map.md`) and the `AGENTS.md` map hierarchy — root plus
  `tools/`, `data/`, `draft/` and `tests/`, with the root map required to
  reference the four area maps and the component map.
- **Payload contract** — 4 source tabs, 141 utilities, 18 regions, 107 months,
  60,348 cells, 17 validation checks all `ok`, reproducible residential
  median/mean/min/max, stage counts summing to 141, conflict records.
- **CSV contracts** — row counts and required columns; every value cross-checked
  against the payload (`utilities.csv` latest values, `rates_monthly.csv` all
  60,348 cells, `regions.csv` counts, `sources.csv` tab checksums).
- **Geometry** — 18 PSGC regions with paths, bbox, labels, island metadata;
  geometry codes equal the payload codes.
- **Service areas & provider lens** — coverage CSV contracts (1,648 LGU + 17
  barangay rows, 4 registered sources with licences, valid PSGC joins, no
  duplicates), coverage geometry (1,642 LGU polygons, path data, province
  registry), Meralco RA 12146 counts (108 LGUs, 17 barangays, 3 regions),
  payload↔CSV consistency, the page's embedded coverage blocks (every LGU
  polygon, every utility record) and the provider-lens affordances.
- **Docs site** — manifest/page-count consistency pinned at 21 pages (20
  documents + index), every docs page present (including the architecture guides
  `frontend.html`, `backend.html`, `component-map.html` and their required
  Architecture group), shared assets, all page→docs links resolving, sidebar/main
  landmark and zero third-party asset tags on sampled pages; the component map
  must reference the agent map hierarchy and link the frontend/backend guides;
  the submission pack's proposal, application answers and challenge notes are
  absent from `draft/docs/` and from `docs-manifest.json` — the docs site
  documents the data platform only.
- **Built page (static)** — doctype/lang/title/description/viewport, one `h1`,
  section ids and anchors, 18 inline map paths, embedded `DATA` payload equal to
  `data/seed/page-data.json` (catches stale builds), expected counts in visible
  copy, no drafting leftovers, **no submission surfaces** (no `.build-strip`
  element or CSS, no submission-site link, no submission markers anywhere in the
  page source, no submission copy in visible text), **no external http(s)
  runtime asset references**, inlined fonts/favicon/images, resolvable in-page
  anchors and local links, element ids referenced by the inline JS, SVG sprite
  `<use>` targets, accessible names, and a Content-Security-Policy.
- **OpenAPI** — parses, OpenAPI 3.1, operations have unique
  `operationId`/summary/responses, internal `$ref`s resolve, declared data files
  exist; plus full `openapi-spec-validator` validation when installed.
- **Static JSON API** — every file parses as a `{meta, data}` envelope,
  `meta.dataset_version` matches the page payload, `index.json` references
  existing files, size and placeholder checks.
- **Packaging & hygiene** — README commands, README cross-references to the
  architecture guides, the agent map hierarchy and the current docs page count
  (derived from the manifest, not hard-coded), licence, gitignore coverage,
  generated files untracked, built page tracked, no private keys.
- **Deterministic build (`--check-page`)** — copies the tree to a temp dir,
  builds twice, asserts identical output, then asserts the committed page is
  identical to the fresh build.

## 2. Browser QA

Prerequisites:

- Node.js 20+ (`npm ci` installs Playwright; or use an existing
  `playwright-core` install via `PLAYWRIGHT_MODULE`).
- A Chromium build. CI installs it with
  `npx playwright install --with-deps chromium`. Locally, the suite finds the
  Playwright browser cache automatically, or an explicit binary:

```bash
# install once (optional if playwright-core + its chromium are already present)
npm ci
npx playwright install chromium

# run the suite against the committed page
node tests/qa.mjs

# options
node tests/qa.mjs --page draft/map-table-prototype.html
node tests/qa.mjs --base http://localhost:8000/draft/map-table-prototype.html
node tests/qa.mjs --out /tmp/qa-final --strict --json
node tests/qa.mjs --headed --no-screens
```

Environment variables:

| Variable | Purpose |
| --- | --- |
| `PLAYWRIGHT_MODULE` | path or package name of `playwright` / `playwright-core` (default: repo `node_modules`, then `/tmp/qa/node_modules`) |
| `CHROMIUM_PATH` | explicit Chromium executable (default: Playwright browser cache) |

The suite exits `1` with a readable failure list if any hard check fails,
`2` when the page/browser/module cannot be found.

With `--base` the suite also checks the served preview site end to end: every
same-origin link on the rendered page (the preview copy rewrites local paths to
`files/draft/api/v1/*`, `files/draft/openapi.yaml`, `files/draft/data-model.md`,
`files/LICENSE`, `files/NOTICE.md`, ...) is fetched and must return HTTP 200,
and each API file link is resolved against the page URL and its JSON envelope
parsed. For a `file://` page the same link is resolved against the page
directory on disk instead.

What `tests/qa.mjs` checks (desktop 1440x900 **and** mobile 390x844):

- **Zero noise** — no console errors, no page errors, no failed requests, and
  **no external network requests** (only `file:`, `data:`, `blob:`; an
  HTTP-served `--base` only requests its own origin).
- **Layout** — no horizontal overflow (`scrollWidth <= innerWidth + 1`),
  including after interactions and with a filter dropdown open on mobile.
- **Page** — title/lang/description/viewport, a single `h1`, `#main` + `#map`,
  `#table`, `#api`, `#method`, nav anchors.
- **Separation** — the data page is the standalone production product: zero
  `.build-strip` elements or markers, no submission-site link (or any other
  submission marker in the rendered markup), and no submission word in the
  visible text. The section nav anchors must work on their own, since the
  removed strip is gone; submission material lives in the separate
  review/submission pack.
- **Map** — 18 region paths, each with real geometry and a fill colour, PSGC
  codes matching the embedded payload, and a five-swatch legend **above** the
  map frame; zoom-in/zoom-out controls change the viewBox and the whole-country
  reset restores it; exactly one region is tabbable at a time (roving
  tabindex), arrow keys move focus between regions, Enter selects and filters
  the table, Escape clears the selection.
- **National overview aside** — all 18 region medians rendered as proportional
  ranking bars, the month's six biggest movers, a rank-row click filtering the
  price table to that region, and a mover click expanding that utility's row.
- **Price table** — 141 data rows, 9 sortable headers with `aria-sort` and
  full-cell focus-visible targets, row expansion (detail row, monthly chart,
  source-row link, compare action), search filter + clear, a no-results empty
  state with a clear-filters action, sort by utility and by residential rate
  (checked against the payload's min/max), and clicking a region filters the
  table and updates the aside (count + highlight + summary).
- **Comparison** — an expanded row's compare action fills a fixed tray (ARIA
  pressed state, disabled until two selections); the dialog overlays two
  residential histories (`path.line` count), renders the latest-rate matrix,
  moves focus to Close, closes on Escape with focus restored, keeps at most
  three providers (oldest replaced, toast shown), clears tray and URL, and deep
  links (`?compare=`) auto-open it; on mobile the matrix becomes stacked cards
  with no horizontal overflow.
- **Shareable view state** — the nav copy-link action reports a toast and the
  URL carries provider/region/compare/search/type/grid/NDA/sort/expanded-row;
  `?compare=`, `?region=`, and `?q&type&nda` deep links restore the matching
  UI state.
- **Custom dropdowns** — the ARIA combobox contract: `aria-haspopup=listbox`,
  `role=listbox`, `role=option`, `aria-expanded`, `aria-controls`; keyboard
  `Enter` opens, `ArrowDown` moves, `Enter` selects and closes, `Escape` closes
  without selecting. Native `<select>` fallback is exercised if the page still
  uses one.
- **Provider coverage lens** — the searchable 141-provider dropdown filters to
  one option; selecting Meralco draws exactly the 108 RA 12146 LGU paths on a
  zoomed map and syncs the hint banner, aside (province counts incl. partial
  "20 / 23"), table filter (1 row), table summary and `?provider=` URL; hovering
  a coverage polygon shows the LGU, province, provider rate and region-median
  comparison; the whole-country reset restores the viewBox; selecting a region
  exits the lens; clearing restores 141 rows and the full map; the keyboard path
  (Enter → type → ArrowDown → Enter) works. Mobile exercises the same selection,
  asserts no overflow and clears cleanly. Where a utility still uses the
  region-level fallback, the suite checks that the region is outlined and
  labelled as region-level (skipped when all utilities are LGU-level).
- **NDA switch** — hiding NDA rows leaves exactly the utilities with a published
  residential rate; restoring returns 141 rows.
- **CSV export** — triggers a real download, correct filename, header row, 142
  lines (header + 141 rows), and the expected utility names; filtered exports
  are labelled `_filtered` and an empty result is refused instead of writing a
  header-only file.
- **API docs + explorer** — API docs sections exist (getting started, datasets,
  endpoints, conventions, explorer, sources, disclaimers) with endpoint
  reference rows and an OpenAPI link; 6 response tabs each render a distinct,
  parseable `{meta, data}` envelope, update `#api-path`, and link to the local
  JSON file (verified to exist on disk); "Copy JSON" calls the clipboard API
  with the rendered JSON and shows feedback.
- **Navigation** — sticky nav pinned at the top while scrolling,
  scrollspy marks exactly the current section (`aria-current`/active), reading
  progress advances, every in-page anchor scrolls its section under the sticky
  nav, and the back-to-top control appears and returns to the top.
- **Mobile menu** — `aria-expanded` opens/closes the section menu, `Escape`
  closes it, and choosing a link scrolls the target into view and closes the
  menu (polled, robust to the longer page).
- **Screenshots** — 1x screenshots in `/tmp/qa-final/`: `page-top.png`,
  `map.png`, `provider-map.png`, `table.png`, `api.png`, `method.png`,
  `mobile.png`, `mobile-provider.png`, plus `mobile-menu.png`,
  `mobile-table.png`, `export.csv` and `results.json`.

## 3. Docs-site QA

`tools/build-docs.py` renders every markdown/text document into the static docs site
at `draft/docs/` (one page per document plus `index.html`, shared assets, and a
`docs-manifest.json` page/source registry). Every page also ships a full-text search
overlay: the builder indexes each page's title, headings and section snippets into
`assets/docs.js` (deterministic, no runtime fetch, no third-party requests), so the
same experience works from a static host or straight from `file://`. Rebuild and QA
it with:

```bash
python3 tools/build-docs.py     # -> draft/docs/ (deterministic)
node tests/qa-docs.mjs          # serve the repo locally and crawl the docs site

# options
node tests/qa-docs.mjs --docs preview/docs        # test the preview-hub integration
node tests/qa-docs.mjs --root . --out /tmp/qa-docs --strict --json
node tests/qa-docs.mjs --headed --no-screens --max-pages 60
```

The suite starts a throwaway static server on `127.0.0.1` (no network access
needed), crawls from `draft/docs/index.html` and for **every page** checks:

- HTTP 200, one `h1`, non-empty title/description, `lang=en`, skip link and
  header/nav/main/footer landmarks;
- a labelled full-text search modal (`#docs-search-dialog`, `aria-modal`,
  `aria-labelledby`) is wired from a visible trigger on every page, and element
  ids are unique (no sidebar/masthead/dialog collisions);
- the grouped sidebar lists every document and marks the current page with
  `aria-current="page"`; the "On this page" TOC links resolve to real heading ids;
- code blocks and tables are wrapped, and code blocks expose a working copy button;
- the raw-source download link is present and marked `download` (no in-prose
  links to raw `.md` files — docs are browsed as HTML);
- zero console/page errors, zero failed requests and **zero third-party
  requests**; stylesheets/scripts/images are same-origin or inline;
- no horizontal overflow at 1280x900;
- **separation**: the docs chrome (masthead, subnav, sidebar, footer) carries no
  submission link or copy, and no page links to one of the excluded submission
  documents (the proposal, application answers and challenge notes).

It then crawls every internal link collected across the site (pages, heading
fragments and repository files such as CSVs, JSON and the OpenAPI YAML), asserts
all targets resolve, and verifies every external citation link is
`target="_blank" rel="noopener"`. A desktop pass exercises the sidebar filter,
copy feedback, TOC anchor scrolling and the prev/next pager; a 390x844 pass
checks no overflow and the mobile sidebar toggle (opens, `Escape` closes, links
navigate). The sidebar is also checked to expose the **Architecture** group with
`frontend.html`, `backend.html` and `component-map.html`, so the three
architecture guides stay one click from every page.

A dedicated **search suite** then drives the overlay end to end on desktop and
at 390x844: the trigger opens it with focus in the input and an empty-query
state with suggestions; `Ctrl/Cmd+K` and `/` open it when focus is not in a
text field; a query renders doc-labelled results with section headings and
`<mark>`-highlighted snippets; `↑`/`↓` move the active option while
`aria-activedescendant`/`aria-selected` follow, `Enter` and result clicks
navigate to the page or heading fragment; `Escape` and the close control dismiss
it and restore focus to the trigger; queries with no matches render the
no-results state. The suite also asserts the index is inlined in
`assets/docs.js` and that the **runtime script** is network-free: the inlined
`SEARCH_INDEX` payload is stripped before the fetch/XHR scan (page prose may
legitimately mention `fetch()` or XHR without shipping network code), the asset
stays under 250 KB and the manifest `search_index` stats are consistent; the same
search works from `file://` with zero network requests, and the open overlay
causes no horizontal overflow on mobile. The deterministic index is visible in `docs-manifest.json` under
`search_index` (pages, sections, bytes) so a stale build is easy to spot.
Screenshots and `results.json` go to `/tmp/qa-docs/` (including
`search-desktop.png` and `search-mobile.png`).

`docs-manifest.json` is also inspected: page count (21 = 20 documents + index),
every HTML page and source file existing, the three architecture guides being
registered in their Architecture group, and the auto-discovered `research/*.md`
pages being registered
(new research documents appear on rebuild without touching the builder). One
research source is a documented exclusion — submission material published in
the submission pack instead — and the suite asserts it is not registered or
written to the docs directory. A manifest-level separation check also confirms
that none of the three excluded submission documents appear in the manifest or
on disk.

## CI

`.github/workflows/ci.yml` runs two jobs on push/PR to `main`:

1. **Static validation and deterministic build** — Python 3.12,
   `pip install -r requirements.txt` + `openapi-spec-validator`, then
   `python3 tools/validate.py`, `python3 tools/validate.py --check-page`, and
   deterministic `tools/build-api.py` and `tools/build-docs.py` runs
   (`git diff`/`git status` clean under `draft/api` and `draft/docs`).
2. **Browser QA** — builds the page and the docs site from source, `npm ci`,
   `npx playwright install --with-deps chromium`, then `node tests/qa.mjs` and
   `node tests/qa-docs.mjs`; screenshots and `results.json` for both suites are
   uploaded as an artifact (even on failure).

Both jobs are hermetic: no network access is needed by the page, the docs site,
the validator or the browser suites (the docs suite serves the checkout itself).
