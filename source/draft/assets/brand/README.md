# draft/assets/brand — official BetterGov marks, favicon and interface icon set

Assets for the **Philippine electricity rates** page (a BetterGovPH open-data project).
Everything here is self-containable: the page builder inlines these files and the
built page makes **no external requests**.

Directory map (bytes / sha256 recorded at generation time, 10 Nov 2026):

| file | bytes | sha256 | role |
| --- | ---: | --- | --- |
| `emblem.svg` | 8,248 | `573f22fb7987992e774f64e7ba2747c8bd8c489332caef6ac29809c3d8014383` | official BetterGov.ph emblem (primary), inline-ready |
| `emblem-outline.svg` | 8,628 | `4acd437896f53a64fae4c29c32a7bbb471d00540afde3847e4fdbc531778b7ca` | official inversed/outline variant for navy or dark surfaces |
| `icons.svg` | 6,472 | `fe13937d8258b52cf7badff4347a30059adad930b9d94f57bf3038a6cfaa3bda` | inline `<symbol>` sprite, `id="i-<name>"` |
| `icons.json` | 9,056 | `8af86e1ef9788e7fc70cda44eba0a21d8e67c31ece6e0f17333b4fd705d27391` | icon manifest (name → viewBox + body markup) + provenance |
| `favicon-32.png` | 1,282 | `edd54f0e5a7298bcd34938f5898480a8cff5ab960cf3f32af75db05747ed1429` | opaque 32×32 fallback |
| `favicon-192.png` | 10,044 | `952b93bc321f39ffe846861b3b996e042c17964121cb86b6c2047fe69053c7e6` | opaque 192×192 (PWA) |
| `favicon-512.png` | 28,430 | `2e176c37ac5aa21cc96ae7793076a8eb85e4ff2b75c1c958cf416dcbd8fb8525` | opaque 512×512 (PWA) |
| `apple-touch-icon.png` | 14,371 | `e77263375ad95c4899f9f4f82321ad1c04901c2aaaa1b75c2f426f31be347760` | opaque 180×180, official emblem on white paper |
| `og-card.template.html` | — | — | OG card layout (1200×630), rendered by `render-assets.mjs` |
| `render-assets.mjs` | — | — | deterministic regeneration of `og.png` + the PNG favicon set |

Related files outside this directory:

| file | bytes | sha256 | role |
| --- | ---: | --- | --- |
| `../favicon.svg` | 2,765 | `9a5b1966d01df7ca95a77abe0db3528758208047b6653b63fa9f04883de21430` | production tab favicon (32×32 viewBox); replaced the previous generic 3-bar file in place |
| `../og.png` | 84,672 | `8cb4d43753c910e9cb1094ec708f426e505e2a9daffa0f44d59615d7cf94839f` | 1200×630 social card (RGB, opaque) |

## Sources, versions and licences

### Official BetterGov.ph brand assets

| asset | source URL | note |
| --- | --- | --- |
| emblem (primary) | <https://assets.bettergov.ph/logos/svg/emblem-primary.svg> (fetched 2026-11-10) | 1080×1080, navy `#0032a0` + white |
| emblem (outline, inversed) | <https://data.bettergov.ph/BetterGov_Emblem-Outline-Inversed.svg> (fetched 2026-11-10) | the exact file data.bettergov.ph serves as its favicon |
| official apple-touch-icon (reference) | <https://bettergov.ph/logos/png/apple-touch-icon.png> (fetched 2026-11-10) | 1024×1024 RGB; full emblem on white, emblem at ≈91.7 % of the square — our 180 px icon copies that composition |
| horizontal wordmark | `draft/assets/bettergov-logo.png` (BetterGovPH `transparency-portal`, `public/brand/bettergov-horizontal-primary.png`) | inlined into the OG card only |

**Brand usage.** The BetterGov emblem and wordmark are BetterGov.ph brand assets,
not open-source artwork. This page uses them unmodified, for this BetterGovPH
open-data project — the same brand-usage position already recorded in
`draft/assets/README.md`. Before public deployment,
confirm logo/brand usage with the brand owner. Rules followed here:

- path data and proportions are never redrawn — the files are the official
  drawings with editor cruft (`<defs><style>`, classes, ids) stripped;
- no recolouring: the emblem uses only official navy `#0032a0` and white;
- the emblem is never stretched (always square), never outlined, never given a
  drop shadow; keep clear space around it (≥ ¼ of the disc diameter) and do not
  place it on busy imagery;
- the page presents itself as an open-data product, not as an official DOE or
  BetterGov publication (see the page footer/source notes).

The single derived use is the **favicon mark**: `../favicon.svg` scales the
emblem's own inner sun/Sarimanok mark from the official path data onto the
official navy field. The emblem's circular "BETTER GOV PILIPINAS" ring text is
unreadable below ~40 px, so the derived mark keeps the brand recognisable at
16–32 px. Nothing is redrawn; the mark is only translated/scaled. If the brand
owner prefers the strict official favicon, substitute
`https://data.bettergov.ph/BetterGov_Emblem-Outline-Inversed.svg` (our
`emblem-outline.svg` is that same file, optimised) — the full badge is legible
from ~40 px up (see proof sheet `favicon-before-after.png`).

### Interface icons — Lucide 1.71.0

- Package: **`lucide-static@1.71.0`** (pinned), fetched from
  <https://unpkg.com/lucide-static@1.71.0/icons/<name>.svg> on 2026-11-10.
- **Licence: ISC** — Lucide's own LICENSE file, `Copyright (c) 2026 Lucide Icons
  and Contributors` (`https://unpkg.com/lucide-static@1.71.0/LICENSE`). This is
  not MIT-only: the brief said MIT, but the verified licence is ISC, plus **MIT
  (Copyright (c) 2013-present Cole Bemis) for the icons derived from Feather**.
  Feather-derived icons in this set: `alert-triangle`, `arrow-up`, `check`,
  `chevron-down`, `chevron-right`, `database`, `download`, `external-link`,
  `search`, `table-2`, `x`.
- Icon set (22, exact names used by the page): `map`, `table-2`, `code-2`,
  `book-open-text`, `database`, `download`, `filter`, `search`, `chevron-down`,
  `chevron-right`, `external-link`, `copy`, `check`, `alert-triangle`,
  `rotate-ccw`, `arrow-up`, `x`, `menu`, `layers`, `file-json`, `shield-check`,
  `sun`.
- `code-2` and `alert-triangle` are the *legacy alias filenames* still shipped
  by lucide-static 1.71.0 (`code-2`'s body is identical to the canonical
  `code-xml`). The requested names are used as `id`s; `icons.json` →
  `sources.<name>` keeps the exact download URL and sha256 for every icon.
- No icon has been redrawn. Only the delivery attributes are normalised:
  24×24 viewBox, `fill="none"`, `stroke="currentColor"`, `stroke-width="1.75"`,
  round line caps/joins (the page controls stroke through CSS; the sprite also
  repeats the attributes on each `<symbol>` so it renders correctly on its own).

### Fonts (OG card only)

`draft/assets/fonts/*.woff2` — Figtree, Inter, JetBrains Mono (latin variable
subsets via Google Fonts), **SIL Open Font License 1.1**. They are embedded as
data URIs in the OG card at render time; the final `og.png` contains no font
files or network references.

## Regeneration

The SVGs (`emblem.svg`, `emblem-outline.svg`, `favicon.svg`, `icons.svg`,
`icons.json`) are the sources. The rasters are generated from them:

```bash
# from the repo root
node draft/assets/brand/render-assets.mjs
```

Overrides if playwright-core / Chromium live elsewhere:

```bash
PLAYWRIGHT_CORE=/path/to/node_modules/playwright-core \
CHROME_PATH=/path/to/chrome \
node draft/assets/brand/render-assets.mjs
```

The script (headless Chromium via playwright-core, no downloads, no network):

1. builds the OG HTML from `og-card.template.html` by inlining
   `draft/assets/fonts/*.woff2` (data URIs), `draft/assets/bettergov-logo.png`
   and `emblem.svg`; asserts the page makes zero non-`data:`/`file:` requests;
   screenshots exactly 1200×630 → `draft/assets/og.png`;
2. rasterises `draft/assets/favicon.svg` at 32/192/512 → `favicon-*.png`
   (opaque, white-matted, RGB);
3. rasterises the official emblem on white at the official 91.7 % scale →
   `apple-touch-icon.png` (180×180, opaque).

It prints bytes + sha256 for every output and fails if a PNG is not the expected
size or not opaque RGB. Rendered bytes depend on the Chromium build (a different
Chromium/font build may produce different PNG bytes/checksums); the SVG and JSON
markup is deterministic in any environment.

## How the page builder consumes these

`tools/build-map-page.py` reads them at build time and inlines them:

- **Emblem** — `load_emblem()` reads `emblem.svg` verbatim and prepends
  `class="emblem"`; `emblem()` emits it at the masthead and footer. The file has
  no `<style>`/`<defs>`/classes, only plain `fill` attributes, so no CSS
  collision can repaint it. It has no `width`/`height`: size it in CSS
  (`.emblem`), keep it square. Sizing advice: masthead 40–46 px, footer 32–36 px;
  drop the old `.masthead-mark` blue tile behind it (the emblem is already a navy
  disc) — the decision sheet is `/tmp/brand-proof/masthead-options.png`; use
  `emblem-outline.svg` on navy/dark backgrounds.
- **Icons** — `load_icons()` merges `icons.json.icons` into the builder's `ICONS`;
  `icon(name)` emits `<svg class="i" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="1.75" stroke-linecap="round"
  stroke-linejoin="round">{body}</svg>`. Values are objects with `viewBox` and
  `body`, which the builder already unwraps. Alternatively inline `icons.svg`
  and reference `<svg class="i"><use href="#i-<name>"></use></svg>`.
  Pick an icon by name only — never paste path data into templates.
- **Favicon** — `draft/assets/favicon.svg` is base64-inlined as
  `<link rel="icon" type="image/svg+xml">`; `apple-touch-icon.png` is inlined as
  `<link rel="apple-touch-icon" sizes="180x180">`. The PNG ladder
  (32/192/512) is available for deployments that prefer bitmaps or for a web
  app manifest.
- **OG card** — `draft/assets/og.png` sits beside the built page as
  `assets/og.png`; the builder points `og:image` at it when
  `OPEN_ENERGY_SITE_URL` is set (1200×630, so it also declares
  `og:image:width/height`).

## Verification performed (10 Nov 2026)

- `emblem.svg` is **pixel-identical** to a render of the official source: 0 of
  1,166,400 pixels differ at 1080×1080, and it round-trips through an XML parser
  (`emblem-outline.svg`, `icons.svg`, `favicon.svg` likewise XML-valid).
- All four SVGs contain no `<script>`, `<style>`, `<defs>`, `<image>`, classes or
  external URLs (only the `xmlns` namespace).
- The builder's own `load_emblem()` / `load_icons()` / `icon()` / `emblem()`
  were exercised against these files: 22 icons load and render, the emblem
  inlines and renders.
- `icons.json` bodies are well-formed, contain no `fill`/`stroke`/`class`/`style`
  overrides, and every `viewBox` is `0 0 24 24`.
- All PNGs are opaque RGB at the exact expected dimensions; `og.png` is exactly
  1200×630 and its render made zero external requests.
- Proof sheets (generated during this task, not committed):
  `/tmp/brand-proof/` — `favicon-tab-proof.png` (16 px tab icon, light+dark,
  2× density), `favicon-legibility-16-32-48.png`, `favicon-before-after.png`,
  `icons-legibility-16-20-24.png`, `icons-on-dark-24.png`,
  `icons-sprite-use-proof.png` (sprite `<use>` integration),
  `emblem-official-vs-optimized.png`, `masthead-options.png`,
  `brand-assets-overview.png`, `og-card-1200x630.png`.

## Caveats

- **Brand permission** for the emblem/wordmark is the one non-code dependency:
  this is a pre-release draft; clear public use with the brand owner before
  launch. Fonts and Lucide icons are properly licensed (OFL 1.1; ISC + MIT for
  Feather-derived icons) — keep the notices; `repo-docs` writes the consolidated
  NOTICE.
- **The favicon mark is derived** (scaled official inner mark, explained above).
  If strict brand governance is required, swap `../favicon.svg` for the official
  inversed outline file (`emblem-outline.svg`) and re-run the regeneration
  script — the tab icon gets softer at 16 px, but it is the exact official mark.
- **OG card text is data-dependent.** “141 distribution utilities … 2018–2026” is
  the current dataset headline; if the ingested data changes, update
  `og-card.template.html` and re-run `render-assets.mjs`, otherwise the card and
  the page will disagree. The card is a static render — it is not regenerated by
  `tools/build-map-page.py`.
- **No font is shipped for the page’s own runtime by this directory**; the OG
  card embeds the existing latin subsets only, so non-latin text would fall back
  if someone edits the card with non-latin glyphs.
