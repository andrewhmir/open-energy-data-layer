# draft/assets — design assets for the data page and companion site

Small, licensed assets used by `tools/build-map-page.py` to build
`draft/map-table-prototype.html` as a single self-contained file (fonts, emblem,
favicon, interface icons, geometry and the data are inlined at build time), and by
`tools/build-preview.py` for the companion site. Brand provenance, licences and
regeneration commands for the mark/icon set live in `brand/README.md`.

| asset | source | licence / note |
| --- | --- | --- |
| `brand/emblem.svg`, `brand/emblem-outline.svg` | Official BetterGov.ph emblem (`assets.bettergov.ph/logos/svg/emblem-primary.svg`) and the inversed/outline variant (`data.bettergov.ph/BetterGov_Emblem-Outline-Inversed.svg`) | BetterGov.ph brand assets, unmodified except for stripping editor/class cruft; inlined into the page masthead and footer. Brand-owner clearance is required before public launch outside a BetterGov.ph project. |
| `favicon.svg` | Derived from the official emblem's inner sun/Sarimanok mark on the official navy `#0032a0` tile | Documented derived use: the full emblem's ring text is unreadable below ~40px, so the tab icon uses the emblem's own interior mark, scaled only (no redraw). `brand/favicon-32/192/512.png` are the raster versions. |
| `brand/apple-touch-icon.png` | Official bettergov.ph apple-touch composition (full emblem on white, 91.7% of the square) | BetterGov.ph brand asset, unmodified proportions. |
| `brand/icons.svg`, `brand/icons.json` | lucide-static 1.71.0 (pinned) interface icons | ISC licence (Lucide Icons and Contributors); the Feather-derived subset (`alert-triangle`, `arrow-up`, `check`, `chevron-down`, `chevron-right`, `database`, `download`, `external-link`, `search`, `table-2`, `x`) is MIT (Cole Bemis). See `brand/README.md` for the per-icon provenance manifest. |
| `og.png` | Rendered from `brand/og-card.template.html` by `brand/render-assets.mjs` | Contains the BetterGov emblem/wordmark and the page headline; regenerate if the headline numbers change. |
| `bettergov-logo.png` | BetterGovPH `transparency-portal` repo (`public/brand/bettergov-horizontal-primary.png`) | BetterGov.ph brand asset; used for the companion site's wordmark. |
| `fonts/figtree-normal-latin.woff2` | Google Fonts, Figtree (variable, latin subset) | SIL Open Font License 1.1 |
| `fonts/inter-normal-latin.woff2` | Google Fonts, Inter (variable, latin subset) | SIL Open Font License 1.1 |
| `fonts/jetbrains-mono-normal-latin.woff2` | Google Fonts, JetBrains Mono (variable, latin subset) | SIL Open Font License 1.1 |
| `geo.json` | Region geometry from the `faeldon/philippines-json-maps` release v1.1.1 (PSGC 3Q 2026, 18 regions incl. NIR and BARMM), TopoJSON `regions/hires` (10% of the source vertices), projected and simplified offline by `tools/build-geo.py`; `geo-sources.json` records the pinned URL and SHA-256s, parameters and per-region counts | repository code/maps MIT; boundary data CC BY 3.0 IGO (CC BY-IGO), © NAMRIA and PSA via OCHA's Philippines COD-AB |
| `coverage-geo.json` | LGU coverage geometry for the provider lens: 1,642 municipality/city polygons from the same pinned release's province/district TopoJSON (`topojson/provdists/hires`), projected with the same frame as `geo.json`, simplified and stored as compact relative integer path data; provenance and per-file SHA-256s are in `geo-sources.json` | repository code/maps MIT; boundary data CC BY 3.0 IGO, © NAMRIA and PSA via OCHA's Philippines COD-AB |

Design tokens (colour, type roles, spacing) follow the BetterGovPH
`transparency-portal` theme (MIT), which mirrors budget.bettergov.ph:
Figtree speaks, Inter works, JetBrains Mono labels, BetterGov blue `#0b4fd9`,
white paper, ink rules.

The fonts are the *latin* variable subsets only (three files, ~108 KB total) so the
page can be fully self-contained without shipping multi-script font families.

`geo.json` and `coverage-geo.json` are generated, not hand-edited:
`python3 tools/build-geo.py` downloads and
verifies the pinned high-resolution release archive (a release tag, not the mutable
`latest/` branch), extracts the 18 region files, projects them (Mercator, width 1000)
and simplifies them at the TopoJSON-arc level for the map's render size
(Douglas-Peucker 0.6 viewBox units; islets below ~4 km² dropped). The frame and the
level of detail stay stable between runs; the Cordillera region, which read as a
box, went from 36 to 324 points. `geo-sources.json` carries the exact source URL,
licence, per-file SHA-256s, fetch timestamp, simplification parameters and per-region
point counts. The boundaries remain CC BY-IGO: credit NAMRIA and the Philippine
Statistics Authority through OCHA's Philippines COD-AB wherever the map is
republished.

`coverage-geo.json` is the overlay layer for the provider filter: one simplified polygon per
municipality/city, used only when the map is filtered by distribution utility. It is
deliberately lighter than the region layer (Douglas-Peucker 1.4 viewBox units, integer
relative path commands, tiny islets dropped unless they are an LGU's only land) because it is
drawn as a filled overlay; the page inlines all 1,642 polygons. `geo-sources.json` records
the per-file SHA-256s of the 88 province/district source files, the layer's simplification
parameters and its own output hash. The service-area *data* that selects these polygons is
published separately in `data/seed/service_areas.csv` (sources and licences in
`data/seed/service_area_sources.csv`; methodology in `research/coverage/README.md`).
