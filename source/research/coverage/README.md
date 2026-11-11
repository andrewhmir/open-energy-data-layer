# LGU-level service areas for the 141 distribution utilities

Every distribution utility (DU) in `data/seed/utilities.csv` has a DOE-assigned
region, but real franchise areas are far finer: co-ops cover part of a province,
one province can hold several co-ops, and a few DUs span regions. This folder
produces an auditable, reproducible LGU (municipality / city) coverage table for
all 141 DUs so the page's provider filter can draw each provider's operating
area, not just Meralco's.

## At a glance

| | |
| --- | --- |
| Utilities covered | **141 / 141** (100%) have at least one LGU row; 0 need a region fallback |
| Rows | **1,630** LGU rows (1,433 from the OSM page, 197 from the Wikipedia supplement) |
| LGUs mapped | **1,585** distinct PSGC LGUs out of 1,642 (96.5%); 57 remain uncovered, listed below |
| Primary source | OpenStreetMap Wiki *Power networks/Philippines/Operators*, revision **2836797** (2025-04-14), CC BY-SA 2.0 |
| Supplementary source | Wikipedia *List of electric distribution utilities in the Philippines*, revision **1374171231** (2026-09-10), CC BY-SA 4.0 — used only for the 22 DUs the OSM page lists without a franchise table |
| Codes | All emitted PSGC codes are canonical zero-padded 10-digit strings (e.g. Angat `0301401000`, Bulacan `0301400000`) |
| Deterministic | `python3 research/coverage/extract.py`; pinned revisions + committed wikitext snapshots |

Status: ready for the Lead's merge. `MERALCO` rows are OSM-derived and flagged
`law-override-pending (RA 12146)`; the Lead's merge replaces them with the
law-level list (a colleague encodes RA 12146 Section 1 in
`research/service-areas.json`: 108 LGUs + 17 Pampanga barangays).

## Files

| file | what it is |
| --- | --- |
| `research/coverage/extract.py` | the deterministic extraction/mapping tool (stdlib only) |
| `research/coverage/osm-operators.json` | raw extracted OSM table (132 table rows + 19 bullet-section operators, merged operators, match report, ambiguities, cross-checks) |
| `research/coverage/osm-service-areas.csv` | raw extraction in the service-area schema — the Lead's merge input |
| `data/seed/service_areas.csv` | byte-identical to `research/coverage/osm-service-areas.csv`; the Lead's merge rewrites this with the RA 12146 Meralco override |
| `data/seed/service_area_sources.csv` | source registry: revision ids, retrieved_at, licences, attribution strings |
| `research/coverage/snapshots/osm-wiki-2836797.wikitext` | pinned raw wikitext of the OSM page (sha256 in the `.provenance.json`) |
| `research/coverage/snapshots/wikipedia-du-list-1374171231.wikitext` | pinned raw wikitext of the Wikipedia list |

Output hashes (current build):

    service_areas.csv        5c62adcf693fd0c4309796c81f10393629a7ee26025ceed572727082924f1081
    service_area_sources.csv 0418657eb7818bb1dcf5e5978148886f70772869e5324f0c76f8110e4b6bd7d0

## Merge contract with `tools/build-service-areas.py`

The raw file is the merge tool's first input. Checked against the tool and the
pinned LGU geometry (`draft/assets/coverage-geo.json`): **1,540 / 1,540 visible
rows resolve to a geometry LGU (0 misses)** for all utilities except MERALCO (the
tool deliberately ignores our MERALCO rows and substitutes RA 12146). Two
integration notes for the merge:

1. **Cross-utility LGU overlaps are intentional.** 42 LGUs are claimed by more
   than one utility here because the sources describe partial coverage (e.g.
   San Carlos City is CENPELCO's while barangays Cruz and Bolingit are DECORP's;
   Calanasan is KAELCO's while two barangays are CAGELCO II's; 18 FIBECO/MAGELCO/
   SUKELCO/PPALMA/CLPC/COLIGHT partial overlaps in Mindanao; CEDC's Clark
   Freeport portions inside PELCO II/TARELCO II/AEC areas; MORE-POWER's 2022
   expansion into ILECO areas). The merge should therefore de-duplicate on
   `(utility_code, adm3_psgc)`, not on `adm3_psgc` alone — the current
   `tools/build-service-areas.py` uses a global `seen` set and would report these
   42 legitimate overlaps as duplicates.
2. The published file adds `area_level=barangay` rows (MERALCO Pampanga, from
   RA 12146) and may add `area_level=region` fallbacks; this raw extraction has 0
   of either.

## Output schema

`data/seed/service_areas.csv` — header matches the column contract of the Lead's
merge tool (`tools/build-service-areas.py` `AREA_HEADER`) and `tools/validate.py`:

    utility_code,source_id,area_level,region_psgc,province_psgc,province_name,adm3_psgc,lgu_name,adm4_psgc,barangay_name,coverage_note

`adm4_psgc` and `barangay_name` are always empty in this raw extraction: it is
LGU-level only. They exist for the published dataset, where the Lead's merge adds
MERALCO's 17 RA 12146 Pampanga barangays as `area_level=barangay` rows.

* `utility_code` — one of the 141 DOE workbook codes.
* `source_id` — `SRC-OSM-OPERATORS` or `SRC-WIKI-DUS` for LGU rows; `SRC-DOE-RATES`
  for an `area_level=region` fallback (none are needed in the current build).
* `area_level` — `lgu` (one row per covered LGU) or `region` (fallback only).
* `region_psgc` — the **service area's** PSGC region (not the DU's DOE region), so
  joins to LGU geometry work; cross-region rows therefore differ from the DU's
  DOE region and say so in `coverage_note`.
* `province_psgc` / `province_name` — the LGU's adm2 from the PSGC registry.
  For NCR and the independent City of Isabela the adm2 is a district / city
  ("NCR, Second District", "City of Isabela"); the "(Not a Province)" marker is
  dropped from the name only.
* `adm4_psgc` / `barangay_name` — empty here (LGU-level extraction only); the
  Lead's merge fills them for the RA 12146 barangay rows.
* `coverage_note` — `""` normally; otherwise `cross-region`,
  `partial barangay coverage (listed in source)`, a specific partial-coverage
  explanation, and/or `law-override-pending (RA 12146)`.
* Sorted by `utility_code`, then LGU PSGC; no duplicate `(utility_code, adm3_psgc)`.

`data/seed/service_area_sources.csv` (header exactly as specified) has four rows:
`SRC-OSM-OPERATORS`, `SRC-WIKI-DUS`, `SRC-DOE-RATES` (region fallback) and
`SRC-RA-12146` (placeholder for the Lead's Meralco override).

## Sources, revisions and licences

### SRC-OSM-OPERATORS (primary)

* OpenStreetMap Wiki, *Power networks/Philippines/Operators*,
  <https://wiki.openstreetmap.org/wiki/Power_networks/Philippines/Operators>
* Revision **2836797**, edited 2025-04-14 by Kjon; retrieved 2026-11-10.
* Licence: **CC BY-SA 2.0**. The page tabulates operator franchise areas as
  "per Department of Energy", with a municipality-level table for most operators.
* Snapshots: `snapshots/osm-wiki-2836797.wikitext` (+ provenance json).

Structure used: 15 region sections with wikitable rows
(`Name (abbreviation) | Franchise areas | Notes`), plus bullet-only sections:
Nationwide (NGCP), Metro Manila (Meralco), MIMAROPA and Bicol. Operators repeat
across sections (Meralco 3×, CAGELCO II, AURELCO, BASELCO, FIBECO, LASURECO,
SUKELCO, ZAMSURECO-I, COTELCO-PPALMA, QUEZELCO-I bullet) — rows are merged per
operator and areas unioned.

### SRC-WIKI-DUS (supplementary, 22 utilities only)

* Wikipedia, *List of electric distribution utilities in the Philippines*,
  <https://en.wikipedia.org/wiki/List_of_electric_distribution_utilities_in_the_Philippines>
* Revision **1374171231**, edited 2026-09-10 by FiveGeekabytes; retrieved 2026-11-10.
* Licence: **CC BY-SA 4.0**.
* Used **only** where the OSM page has no usable LGU list for a DU; the OSM page
  leaves the Bicol and MIMAROPA sections as bullet lists without franchise areas
  (and has no row for BANELCO / PROSIELCO / CEDC). 22 utilities are supplemented:
  ALECO, BANELCO, BISELCO, CANORECO, CASURECO1–4, CEDC, FICELCO, LUBELCO,
  MARELCO, MASELCO, OMECO, ORMECO, PALECO, PROSIELCO, ROMELCO, SORECO1, SORECO2,
  TIELCO, TISELCO.
* Every supplemented row is marked `source_id=SRC-WIKI-DUS` so it can be attributed
  and re-checked. It is also cross-checked against the OSM result for the 116
  utilities present in both sources (see "Cross-check" below).

### SRC-DOE-RATES (region fallback only)

The DOE workbook behind `data/seed/utilities.csv` gives each DU one region; it is
the fallback source for `area_level=region` rows. None are needed: all 141 DUs
have LGU-level coverage in this build. Licence: no explicit DOE dataset licence;
see `data/seed/sources.csv` ("public records; reuse terms to be confirmed").

### SRC-RA-12146 (placeholder for the Lead's merge)

RA 12146 (Meralco franchise renewal), official text via the Supreme Court
e-Library; the colleague's law encoding is `research/service-areas.json` (not
edited here). MERALCO rows below are OSM-derived and flagged
`law-override-pending (RA 12146)`; the merge should replace them.

## Method

1. **PSGC LGU registry.** Built from the pinned PSGC 3Q 2026 TopoJSON archive
   (`philippines-json-maps` v1.1.1, the file cached by `tools/build-geo.py`):
   `topojson/provdists/hires/municities-provdist-<adm2>.topo.0.1.json` gives
   1,642 LGUs (149 cities + 1,493 municipalities) with `adm1_psgc`,
   `adm2_psgc`, `adm3_psgc`, `adm3_en`; province names come from
   `topojson/regions/hires/*.json`. Codes are zero-padded to 10 digits.
2. **Extract the OSM table and bullets** from the pinned wikitext
   (`osm-operators.json.raw_rows` keeps every row/section verbatim). Bullet
   sections contribute operators and franchise hints, e.g.
   `Quezon I Electric Cooperative (QUEZELCO-I) (Del Gallego, Camarines Sur)`.
3. **Merge operators** across region sections by display name (the abbreviation
   in parentheses is kept separately) and union their areas.
4. **Parse franchise-area cells into LGU items**:
   * `A, B and C in <Province>` → each item resolved inside that province;
   * `A, B and C in <LGU>, <Province>` → barangay-level coverage: one
     **partial** row for the parent LGU with `coverage_note = "partial barangay
     coverage (listed in source)"` (e.g. DECORP: Cruz and Bolingit in San Carlos
     City; QUIRELCO: 18 barangays in San Agustin; Meralco: Candaba / Apalit);
   * `parts of <LGU>` / `portions of <LGU>` → partial LGU row;
   * a bare province name (alone in its cell) → whole-province expansion
     (this is how "Benguet", "Bulacan", "Cavite", "Zamboanga del Sur", etc. work);
   * `province including LGU` → province expansion plus the extra LGU
     (e.g. "Capiz including Roxas City");
   * notes' whole-LGU exclusions are applied, e.g. LANECO excludes Iligan City,
     Pantao Ragat, Pantar (served by ILPI/LASURECO); LUELCO excludes Bauang,
     San Fernando, San Juan; ANTECO excludes Libertad, Pandan; LASURECO excludes
     Wao; DASURECO excludes Davao City; ZANECO/ZAMSURECO-I exclude the LGUs noted
     as served by ZAMSURECO-II; MAGELCO excludes Cotabato City; SUKELCO excludes
     Lutayan.
5. **Resolve LGU names to PSGC**. Order of evidence: exact name / known alias →
   province context stated in the source text → the operator's DOE region (only
   when that narrows the field to one candidate). **Ambiguous names are never
   guessed**: the build reports 0 unresolved LGU names and 3 unmapped source
   items (below). Name handling covers `City of X` / `X City` forms, `Sto.` =
   `Santo` / `Sta.` = `Santa` expansion, accent folding (`Peñablanca`), hyphen
   folding (`Impasug-ong`, `Miag-ao`, `M'Lang`), and the PSGC 3Q 2026 names that
   differ from the source text (`Sawata` for San Isidro, Davao del Norte;
   `Pagagawan` for Datu Montawal; `Gen. S.K. Pendatun`; `Salvador Benedicto`;
   `Pigkawayan`; `Cabanglasan`; `Enrique B. Magalona`; `Dr. Jose P. Rizal` for
   Rizal, Palawan).
6. **Cross-region check**: every LGU's `adm1_psgc` is compared with the DU's DOE
   region. Mismatches are kept and flagged `cross-region` (not dropped) because
   several are genuine franchises: Meralco (NCR DU serving Regions III/IV-A),
   AURELCO (Region III DU serving Dinapigue, Isabela), QUEZELCO-I (Region IV-A DU
   serving Del Gallego, Camarines Sur), CAGELCO-II (Region II DU serving Apayao),
   FIBECO (Region X DU serving Wao, Lanao del Sur), LASURECO (BARMM DU serving
   Pantao Ragat/Pantar, Lanao del Norte), PPALMA (Region XII DU serving Maguindanao
   LGUs), SUKELCO (Region XII DU serving Maguindanao del Sur), ZAMSURECO-I
   (Region IX DU serving Don Victoriano, Misamis Occidental), BASELCO (BARMM DU
   serving Isabela City, Region IX), SULECO/SIASELCO (BARMM DUs serving Sulu,
   which PSGC 3Q 2026 moved to Region IX) and PROSIELCO (DOE Region VII DU serving
   Siquijor, which PSGC 3Q 2026 moved to NIR).
7. **Meralco**: OSM rows are kept but every row carries
   `law-override-pending (RA 12146)`; the Lead's merge replaces them with the
   RA 12146 list.
8. **Validate**: every one of the 141 codes is present; no duplicate
   `(utility_code, adm3_psgc)`; every `adm3_psgc` exists in the registry; every
   region code is one of the 18 PSGC regions; ≥90% of utilities have LGU rows.
   The script exits non-zero if any check fails.

## Ambiguities and unmapped source items

* Unresolved LGU names: **none** (0 in the current build).
* Unmapped franchise-area items (kept in the report, no LGU invented):
  * `Clark Freeport Zone` (CEDC) — a special economic zone, not an LGU; CEDC's
    LGU rows come from the Wikipedia supplement (Clark portions in Angeles,
    Mabalacat, Porac, Bamban, Capas).
  * `First Philippine Industrial Park` (Meralco) — an industrial estate inside
    Sto. Tomas, Batangas, which is already covered by the Meralco row set.
  * `Tungo` (LEYECO-3) — a barangay listed alongside LGUs in the source; not an
    LGU, so it is not mapped.
* Source operators that are not DUs in the 141-row workbook (extracted for audit,
  not used): NGCP (transmission), APEC (concessionaire inside the ALECO franchise;
  ALECO/APEC are one franchise on the sources, and the DOE workbook has only
  ALECO), SPUG (NAPOCOR missionary electrification), Subic Enerzone and LIMA
  Enerzone (freeports/industrial parks), and SIQUELCO (the OSM page's name for
  Siquijor's DU; the workbook code is PROSIELCO, which is used instead).

## Known gaps

57 of the 1,642 LGUs are not claimed by any of the 141 DUs. Most are explained:

* **NCR 17 LGUs** — the OSM page's Metro Manila section is a bare bullet with no
  LGU list, so no NCR LGU appears here. The Lead's MERALCO RA 12146 override adds
  all 17; that is why Meralco is marked "law-override-pending" rather than skipped.
* **11 Sulu LGUs** — SULECO's row lists only 7 of Sulu's 18 LGUs and SIASELCO
  covers Siasi; the remaining LGUs are unlisted in the source (the Sulu franchise
  table is incomplete).
* **8 Special Geographic Area LGUs** (BARMM, in Cotabato) — new 2024 municipalities
  not covered by any DU row in the sources.
* **Romblon 3** (Banton, Concepcion, Corcuera) and **Turtle Islands, Tawi-Tawi** —
  small island/local systems that are not DUs in the 141-row DOE workbook.
* **Kalayaan, Palawan** — the Spratly municipality has no distribution utility row.
* **OSM-page omissions** in otherwise-covered provinces: Samar 3 (Basey, Paranas,
  Zumarraga — Wikipedia attributes them to SAMELCO-II), Basilan 2 (Maluso,
  Sumisip — Wikipedia attributes them to BASELCO), plus single LGUs in Zambales
  (San Marcelino), Batangas (Balete, Mataasnakahoy), Laguna (Alaminos, Rizal),
  Quezon (Dolores), Cebu (San Remigio), Leyte (Tunga), Misamis Oriental
  (Talisayan), Cagayan (Calayan) and Pangasinan (Sison). These are left as gaps
  rather than mixed in from the secondary source, because for those DUs the
  primary table exists and is authoritative for the franchise list.
* **PALECO** list is 19 LGUs: Palawan's 24 minus the 4 Calamianes LGUs served by
  BISELCO and minus Kalayaan (no DU) — consistent with the source.
* **ALECO** is 18 LGUs (all Albay): the Wikipedia source lists the combined
  ALECO/APEC franchise; APEC is not a separate DOE workbook row (see
  `coverage_note` on those rows).

| province / district | LGUs | names |
| --- | --- | --- |
| Basilan | 2 | Maluso, Sumisip |
| Batangas | 2 | Balete, Mataasnakahoy |
| Cagayan | 1 | Calayan |
| Cebu | 1 | San Remigio |
| Laguna | 2 | Alaminos, Rizal |
| Leyte | 1 | Tunga |
| Misamis Oriental | 1 | Talisayan |
| NCR, City of Manila, First District | 1 | City of Manila |
| NCR, Fourth District | 7 | City of Las Piñas, City of Makati, City of Muntinlupa, City of Parañaque, Pasay City, City of Taguig, Pateros |
| NCR, Second District | 5 | City of Mandaluyong, City of Marikina, City of Pasig, Quezon City, City of San Juan |
| NCR, Third District | 4 | City of Caloocan, City of Malabon, City of Navotas, City of Valenzuela |
| Palawan | 1 | Kalayaan |
| Pangasinan | 1 | Sison |
| Quezon | 1 | Dolores |
| Romblon | 3 | Banton, Concepcion, Corcuera |
| Samar | 3 | Basey, Paranas, Zumarraga |
| Special Geographic Area | 8 | Kapalawan, Old Kaabakan, Kadayangan, Nabalawag, Pahamuddin, Malidegao, Ligawasan, Tugunan |
| Sulu | 11 | Kalingalan Caluang, Hadji Panglima Tahil, Old Panamao, Pangutaran, Pata, Tapul, Tongkil, Panglima Estino, Lugus, Pandami, Omar |
| Tawi-Tawi | 1 | Turtle Islands |
| Zambales | 1 | San Marcelino |

## Cross-region flags (kept, not dropped)

126 LGU rows across 13 utilities are flagged `cross-region` (LGU's PSGC region
differs from the DU's DOE region). All are genuine multi-region/service-vintage
cases, not name-matching errors:

| utility | rows | LGUs |
| --- | --- | --- |
| AURELCO | 1 | Dinapigue |
| BASELCO | 1 | City of Isabela |
| CAGELCO-II | 5 | Calanasan, Flora, Luna, Pudtol, Santa Marcela |
| FIBECO | 1 | Wao |
| LASURECO | 2 | Pantao Ragat, Pantar |
| MERALCO | 90 | Alfonso, Amadeo, Angat, Angono, Apalit, Balagtas, Baras, Batangas City, Bay, Binangonan, Bocaue, Bulacan, Bustos, Cainta, Calauan, Calumpit, Candaba, Candelaria, Cardona, City of Antipolo, City of Bacoor, City of Baliwag, City of Biñan, City of Cabuyao, City of Calamba, City of Carmona, City of Cavite, City of Dasmariñas, City of General Trias, City of Imus, City of Lucena, City of Malolos, City of Meycauayan, City of San Jose Del Monte, City of San Pablo, City of San Pedro, City of Santa Rosa, City of Sto. Tomas, City of Tagaytay, City of Tayabas, City of Trece Martires, Doña Remedios Trinidad, Gen. Mariano Alvarez, General Emilio Aguinaldo, Guiguinto, Hagonoy, Indang, Jala-Jala, Kawit, Liliw, Los Baños, Lucban, Magallanes, Majayjay, Maragondon, Marilao, Mauban, Mendez, Morong, Nagcarlan, Naic, Norzagaray, Noveleta, Obando, Pagbilao, Pandi, Paombong, Pila, Pililla, Plaridel, Pulilan, Rodriguez, Rosario, Sampaloc, San Ildefonso, San Mateo, San Miguel, San Pascual, San Rafael, Santa Cruz, Santa Maria, Sariaya, Silang, Tanay, Tanza, Taytay, Teresa, Ternate, Tiaong, Victoria |
| PPALMA | 4 | Buldon, Northern Kabuntalan, Pagagawan, Pagalungan |
| PROSIELCO | 6 | Enrique Villanueva, Larena, Lazi, Maria, San Juan, Siquijor |
| QUEZELCO-I | 1 | Del Gallego |
| SIASELCO | 1 | Siasi |
| SUKELCO | 6 | Buluan, Datu Paglas, Gen. S.K. Pendatun, Mangudadatu, Paglat, Pandag |
| SULECO | 7 | Indanan, Jolo, Luuk, Maimbung, Parang, Patikul, Talipao |
| ZAMSURECO-I | 1 | Don Victoriano |

## Cross-check against the Wikipedia list

For the 116 utilities present in both sources the LGU sets were compared:
**72 identical, 44 differing** (details in `osm-operators.json.report.
wiki_cross_check`). The differences are mostly errors/incompleteness in the
secondary source and were not used to overwrite the primary data, e.g.:

* Wikipedia's DLPC row includes LGUs from Davao del Norte, Cotabato and Davao del
  Sur (the OSM table gives DLPC Davao City + 4 Davao del Norte LGUs);
* its MORESCO-I row includes Baungon/Cagayan de Oro/Iligan, which belong to other
  DUs; its LUELCO row lists the whole of La Union (24 entries) while the
  cooperative's area is La Union minus Bauang/San Fernando/San Juan;
* it adds a few real OSM omissions (SAMELCO-II's Basey/Paranas/Zumarraga,
  ZAMECO-II's San Marcelino) that are listed under "Known gaps" rather than mixed
  in;
* it disagrees on CEPALCO (Jasaan/Villanueva) and CENECO/NEPC, where the sources
  themselves conflict.

The comparison table is kept in the JSON report; `SRC-WIKI-DUS` rows in the CSV
are only the 22 utilities where the OSM page has no LGU data at all.

| utility | OSM LGUs | Wikipedia LGUs | sample differences |
| --- | --- | --- | --- |
| AEC | 1 | 2 | Wiki only: Mabalacat City |
| AKELCO | 19 | 20 | Wiki only: Sapi-An |
| ANTECO | 16 | 15 | OSM only: San Jose |
| AURELCO | 9 | 10 | Wiki only: Alfonso Castaneda |
| BASELCO | 11 | 12 | OSM only: City of Isabela; Wiki only: Maluso, Sumisip |
| BILECO | 8 | 7 | OSM only: Maripipi |
| CAGELCO-II | 21 | 20 | OSM only: Calanasan |
| CASELCO | 1 | 2 | Wiki only: Turtle Islands |
| CEBECO-II | 12 | 13 | Wiki only: San Remigio |
| CELCOR | 2 | 1 | OSM only: Santa Rosa |
| CEPALCO | 2 | 4 | Wiki only: Jasaan, Villanueva |
| DANECO-NORDECO | 18 | 11 | OSM only: Asuncion, Kapalong, New Corella, Island Garden City of Samal |
| DLPC | 5 | 13 | Wiki only: Kitaotao, Asuncion, Kapalong, New Corella |
| FIBECO | 13 | 14 | Wiki only: Amai Manabilang |
| FLECO | 13 | 11 | OSM only: Luisiana, Magdalena |
| IEEC | 1 | 3 | Wiki only: City of Lipa, San Jose |
| KAELCO | 11 | 9 | OSM only: Calanasan, Kabugao |
| LANECO | 20 | 18 | OSM only: Nunungan, Tagoloan |
| LASURECO | 41 | 39 | OSM only: City of Marawi, Amai Manabilang, Tagoloan II; Wiki only: Baloi |
| LEYECO-III | 8 | 9 | Wiki only: Tunga |
| LUELCO | 17 | 24 | Wiki only: Bauang, City of San Fernando, San Juan, Pozorrubio |
| MAGELCO | 36 | 30 | OSM only: Buluan, Datu Paglas, Gen. S.K. Pendatun, Mangudadatu |
| MERALCO | 90 | 113 | OSM only: City of Baliwag, Bulacan, Doña Remedios Trinidad, Gen. Mariano Alvarez; Wiki only: San Simon, City of Calaca, Laurel, City of Tanauan |
| MOPRECO | 10 | 13 | Wiki only: Cervantes, Quirino, Tinglayan |
| MORE-POWER | 17 | 1 | OSM only: Alimodian, Anilao, Banate, Barotac Nuevo |
| MORESCO-I | 10 | 14 | Wiki only: Baungon, Talakag, City of Cagayan De Oro, City of Iligan |
| MORESCO-II | 13 | 13 | OSM only: Villanueva; Wiki only: Talisayan |
| NORECO-I | 11 | 10 | OSM only: Jimalalud |
| NUVELCO | 15 | 14 | OSM only: Alfonso Castaneda |
| PELCO-I | 3 | 6 | Wiki only: Arayat, Mexico, Santa Ana |
| PELCO-II | 8 | 9 | OSM only: Apalit; Wiki only: Floridablanca, Magalang |
| PELCO-III | 5 | 7 | Wiki only: Apalit, City of San Fernando |
| PENELCO | 12 | 14 | Wiki only: Floridablanca, Subic |
| PPALMA | 10 | 6 | OSM only: Buldon, Northern Kabuntalan, Pagagawan, Pagalungan |
| PRESCO | 3 | 4 | Wiki only: Magalang |
| QUEZELCO-I | 24 | 24 | OSM only: San Antonio; Wiki only: Santa Elena |
| SAJELCO | 1 | 4 | Wiki only: Carranglan, Llanera, Science City of Muñoz |
| SAMELCO-II | 13 | 16 | Wiki only: Basey, Paranas, Zumarraga |
| SFELAPCO | 2 | 3 | Wiki only: Bacolor |
| SUKELCO | 17 | 16 | OSM only: Sen. Ninoy Aquino |
| TARELCO-I | 15 | 17 | Wiki only: Guimba, City of Tarlac |
| ZAMECO-II | 6 | 7 | Wiki only: San Marcelino |
| ZAMSURECO-II | 24 | 23 | OSM only: City of Zamboanga |
| ZANECO | 23 | 20 | OSM only: Pres. Manuel A. Roxas, Sergio Osmeña Sr., Leon T. Postigo |

## Meralco cross-check with RA 12146

Against the colleague's `research/service-areas.json` (108 LGUs from RA 12146
Section 1): OSM-derived Meralco rows = 90 LGUs; 85 in common; 23 only in the law
(NCR 17 + other LGUs); 5 only in OSM (Candaba/Apalit barangay-level rows and some
Bulacan/Quezon LGUs). The law list replaces the OSM rows in the Lead's merge.

## Coverage per utility

| utility_code | source rows | LGUs | notes |
| --- | --- | --- | --- |
| ABRECO | OSM | 27 |  |
| AEC | OSM | 1 |  |
| AKELCO | OSM | 19 |  |
| ALECO | WIKI | 18 | supplemented from Wikipedia list |
| ANECO | OSM | 12 |  |
| ANTECO | OSM | 16 |  |
| ASELCO | OSM | 14 |  |
| AURELCO | OSM | 9 |  |
| BANELCO | WIKI | 3 | supplemented from Wikipedia list |
| BASELCO | OSM | 11 |  |
| BATANELCO | OSM | 6 |  |
| BATELEC-I | OSM | 12 |  |
| BATELEC-II | OSM | 16 |  |
| BENECO | OSM | 14 |  |
| BILECO | OSM | 8 |  |
| BISELCO | WIKI | 4 | supplemented from Wikipedia list |
| BLCI | OSM | 1 |  |
| BOHECO-I | OSM | 26 |  |
| BOHECO-II | OSM | 21 |  |
| BUSECO | OSM | 10 |  |
| CAGELCO-I | OSM | 12 |  |
| CAGELCO-II | OSM | 21 |  |
| CAMELCO | OSM | 5 |  |
| CANORECO | WIKI | 12 | supplemented from Wikipedia list |
| CAPELCO | OSM | 17 |  |
| CASELCO | OSM | 1 |  |
| CASURECO1 | WIKI | 11 | supplemented from Wikipedia list |
| CASURECO2 | WIKI | 10 | supplemented from Wikipedia list |
| CASURECO3 | WIKI | 7 | supplemented from Wikipedia list |
| CASURECO4 | WIKI | 9 | supplemented from Wikipedia list |
| CEBECO-I | OSM | 18 |  |
| CEBECO-II | OSM | 12 |  |
| CEBECO-III | OSM | 5 |  |
| CEDC | WIKI | 5 | supplemented from Wikipedia list |
| CELCO | OSM | 4 |  |
| CELCOR | OSM | 2 |  |
| CENECO-NEPC | OSM | 6 |  |
| CENPELCO | OSM | 15 |  |
| CEPALCO | OSM | 2 |  |
| CLPC | OSM | 3 |  |
| COTELCO | OSM | 12 |  |
| DANECO-NORDECO | OSM | 18 |  |
| DASURECO | OSM | 15 |  |
| DECORP | OSM | 7 |  |
| DIELCO | OSM | 7 |  |
| DLPC | OSM | 5 |  |
| DORECO | OSM | 11 |  |
| ESAMELCO | OSM | 23 |  |
| FBPC | OSM | 1 |  |
| FIBECO | OSM | 13 |  |
| FICELCO | WIKI | 11 | supplemented from Wikipedia list |
| FLECO | OSM | 13 |  |
| GUIMELCO | OSM | 5 |  |
| IEEC | OSM | 1 |  |
| IFELCO | OSM | 11 |  |
| ILECO-I | OSM | 15 |  |
| ILECO-II | OSM | 15 |  |
| ILECO-III | OSM | 13 |  |
| ILPI | OSM | 1 |  |
| INEC | OSM | 23 |  |
| ISECO | OSM | 34 |  |
| ISELCO-I | OSM | 15 |  |
| ISELCO-II | OSM | 21 |  |
| KAELCO | OSM | 11 |  |
| LANECO | OSM | 20 |  |
| LASURECO | OSM | 41 |  |
| LEYECO-1-DORELCO | OSM | 13 |  |
| LEYECO-II | OSM | 3 |  |
| LEYECO-III | OSM | 8 |  |
| LEYECO-IV | OSM | 6 |  |
| LEYECO-V | OSM | 12 |  |
| LUBELCO | WIKI | 2 | supplemented from Wikipedia list |
| LUECO | OSM | 3 |  |
| LUELCO | OSM | 17 |  |
| MAGELCO | OSM | 36 |  |
| MARELCO | WIKI | 6 | supplemented from Wikipedia list |
| MASELCO | WIKI | 17 | supplemented from Wikipedia list |
| MECO | OSM | 2 |  |
| MERALCO | OSM | 90 | law-override-pending (RA 12146 merge) |
| MOELCI-I | OSM | 8 |  |
| MOELCI-II | OSM | 8 |  |
| MOPRECO | OSM | 10 |  |
| MORE-POWER | OSM | 17 |  |
| MORESCO-I | OSM | 10 |  |
| MORESCO-II | OSM | 13 |  |
| NEECO-I | OSM | 5 |  |
| NEECO-II-AREA-I | OSM | 10 |  |
| NEECO-II-AREA-II | OSM | 11 |  |
| NOCECO | OSM | 17 |  |
| NONECO | OSM | 9 |  |
| NORECO-I | OSM | 11 |  |
| NORECO-II | OSM | 14 |  |
| NORSAMELCO | OSM | 24 |  |
| NUVELCO | OSM | 15 |  |
| OEDC | OSM | 1 |  |
| OMECO | WIKI | 9 | supplemented from Wikipedia list |
| ORMECO | WIKI | 15 | supplemented from Wikipedia list |
| PALECO | WIKI | 19 | supplemented from Wikipedia list |
| PAMES | OSM | 1 |  |
| PANELCO-I | OSM | 9 |  |
| PANELCO-III | OSM | 17 |  |
| PELCO-I | OSM | 3 |  |
| PELCO-II | OSM | 8 |  |
| PELCO-III | OSM | 5 |  |
| PENELCO | OSM | 12 |  |
| PPALMA | OSM | 10 |  |
| PRESCO | OSM | 3 |  |
| PROSIELCO | WIKI | 6 | supplemented from Wikipedia list |
| QUEZELCO-I | OSM | 24 |  |
| QUEZELCO-II | OSM | 8 |  |
| QUIRELCO | OSM | 7 |  |
| ROMELCO | WIKI | 4 | supplemented from Wikipedia list |
| SAJELCO | OSM | 4 |  |
| SAMELCO-I | OSM | 10 |  |
| SAMELCO-II | OSM | 13 |  |
| SFELAPCO | OSM | 2 |  |
| SIARELCO | OSM | 9 |  |
| SIASELCO | OSM | 1 |  |
| SOCOTECO-I | OSM | 10 |  |
| SOCOTECO-II | OSM | 10 |  |
| SOLECO | OSM | 19 |  |
| SORECO1 | WIKI | 8 | supplemented from Wikipedia list |
| SORECO2 | WIKI | 7 | supplemented from Wikipedia list |
| SUKELCO | OSM | 17 |  |
| SULECO | OSM | 7 |  |
| SURNECO | OSM | 12 |  |
| SURSECO-I | OSM | 5 |  |
| SURSECO-II | OSM | 14 |  |
| TARELCO-I | OSM | 15 |  |
| TARELCO-II | OSM | 5 |  |
| TAWELCO | OSM | 9 |  |
| TEI | OSM | 1 |  |
| TIELCO | WIKI | 10 | supplemented from Wikipedia list |
| TISELCO | WIKI | 4 | supplemented from Wikipedia list |
| VECO | OSM | 8 |  |
| ZAMCELCO | OSM | 1 |  |
| ZAMECO-I | OSM | 6 |  |
| ZAMECO-II | OSM | 6 |  |
| ZAMSURECO-I | OSM | 25 |  |
| ZAMSURECO-II | OSM | 24 |  |
| ZANECO | OSM | 23 |  |

## Reproduction

    # from the repository root; needs the pinned PSGC TopoJSON archive, which
    # tools/build-geo.py already caches (or pass --topojson PATH)
    python3 research/coverage/extract.py

The script uses the committed wikitext snapshots by default (no network) and
verifies their pinned revision ids. `--refresh` refetches the two pinned
revisions; `--topojson PATH` overrides the archive location. Outputs are written
in one pass; `data/seed/service_areas.csv` is asserted byte-identical to
`research/coverage/osm-service-areas.csv`. The CSVs are deterministic; the JSON
report carries `generated_at`/`retrieved_at` timestamps.

## Licence and attribution

Rows carry `source_id` so the page/API can attribute each area. The combined
service-area dataset is a derivative of CC BY-SA sources: redistributing it
requires attribution and share-alike terms compatible with the source licences.

Attribution lines to use (also recorded in `data/seed/service_area_sources.csv`
and `osm-operators.json.report.licence_attribution`):

> Service areas: © OpenStreetMap Wiki contributors, “Power networks/Philippines/
> Operators”, revision 2836797 (2025-04-14), CC BY-SA 2.0. Franchise areas are
> tabulated on that page as “per Department of Energy”.

> Additional service areas: © Wikipedia contributors, “List of electric
> distribution utilities in the Philippines”, revision 1374171231 (2026-09-10),
> CC BY-SA 4.0.

`SRC-DOE-RATES` regions: Department of Energy (Philippines), Electricity Rates &
Power Market Monitor (public records; reuse terms to be confirmed).
`SRC-RA-12146`: Republic Act No. 12146, official text via the Supreme Court
e-Library (Philippine laws are not subject to copyright, IP Code Sec. 176).
