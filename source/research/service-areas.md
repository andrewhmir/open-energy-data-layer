# MERALCO service-area coverage — RA 12146 mapped to PSGC 2026-3Q

**Task:** task-9 — structured Meralco franchise coverage for the provider filter on the data page.  
**Repo:** `/home/sysadmin/Test2` (Open Energy Data Layer).  
**Researched / generated:** 2026-11-10 (Asia/Manila).  
**Deliverables:** `research/service-areas.md` (this file), `research/service-areas.json` (canonical, machine-readable), `research/source-snapshots/ra-12146-section1.txt` + `ra-9209-section1.txt` + `.provenance.json` files.  
**Verification labels:** `verified` = fetched live and inspected; `derived` = computed from verified inputs; `unverified` = flagged, not asserted.

---

## 0. TL;DR for the map/provider filter

1. **Meralco is a 3-region DU**: NCR (17/17 LGUs, fully covered), Central Luzon / Region III (Bulacan 24/24 fully + **17 barangays in 3 Pampanga LGUs**), CALABARZON / Region IV-A (67 of 142 LGUs across Batangas, Cavite, Laguna, Quezon, Rizal — Rizal is 14/14 full).
2. **108 LGUs** are enumerated in RA 12146 Section 1 and each is mapped to an exact `adm3_psgc`; **0 unmatched names**. The canonical list is `covered_adm3_psgc` in `service-areas.json`.
3. The DOE workbook assigns MERALCO the single region `1300000000` (NCR). The map must override that with a **multi-region provider record**: regions `[1300000000, 0300000000, 0400000000]` plus the LGU set; a region-only filter would wrongly show Meralco as NCR-only.
4. **Pampanga has no whole LGU in the franchise** — only barangays. If the map renders LGU polygons, render the 3 touched Pampanga LGUs as *partial / barangay-level* (or filter by the 17 `adm4_psgc` values), never as fully covered.
5. No other utility in the 141-row DOE seed dataset spans more than one region; **Meralco is the only multi-region DU franchise identified**. Caveats in §8.

---

## 1. Why the DOE region assignment is wrong for Meralco

The DOE *Electricity Rates & Power Market Monitor* workbook lists each distribution utility exactly once, with one `Region` value (and one `GRID`/`Island` value). MERALCO is listed as `PIOU / ONGRID / NCR / Luzon` and therefore aggregates into NCR-only statistics (e.g. `data/seed/regions.csv` shows NCR with `utility_count=1` and Meralco's rate as the entire NCR median/mean).

But Meralco's legislative franchise has always covered territory in Central Luzon and CALABARZON as well. The current franchise, **RA 12146 (approved 11 April 2025)**, re-enumerates it explicitly. Any provider filter or per-region aggregation that trusts the DOE single-region field will misstate both Meralco's footprint and every region it serves.

---

## 2. Legal source of truth

| field | value |
| --- | --- |
| Law | **RA 12146** — An Act Renewing for Another Twenty-Five (25) Years the Franchise Granted to the Manila Electric Company Under Republic Act No. 9209 |
| Approved | 2025-04-11 |
| Publication | 121 OG No. 17, 3729 (April 28, 2025) |
| Official text URL | <https://elibrary.judiciary.gov.ph/thebookshelf/showdocsfriendly/2/98850> (Supreme Court E-Library, printer-friendly) |
| Retrieved | 2026-11-10T19:13:21+08:00 (HTTP 200; page 32531 bytes) |
| Section used | `Section 1. Nature and Scope` — verbatim snapshot `research/source-snapshots/ra-12146-section1.txt` (2285 bytes UTF-8, 2277 chars) |
| Snapshot SHA-256 | `515341ac88f6fe943636c3ea1d1c6c9862eb80e4f798bf9600198db7cb1e376b` |
| Effective date rule | Sec. 24: effective 15 days after completion of publication (published 2025-04-28); derived date ~2025-05-13, not asserted as authoritative. |

Section 1 is a single sentence of enumeration: the franchise is renewed for the cities/municipalities/barangays of (a) Metro Manila, (b) Bulacan, (c) Cavite, (d) Rizal, (e) Batangas, (f) Laguna, (g) Quezon, and (h) named barangays in Pampanga. The full verbatim text is stored in the snapshot; quoted opening and the Pampanga clause:

> "SECTION 1. Nature and Scope. - Subject to the provisions of the Constitutions and applicable laws, rules, and regulations, the franchise granted to Manila Electric Company (MERALCO) ... to construct, operate, and maintain ... a distribution system for the conveyance of electric power to the end-users in the cities of Caloocan, Las Piñas, Makati, Malabon, Mandaluyong, Manila, Marikina, Muntinlupa, Navotas, Parañaque, Pasay, Pasig, Quezon, San Juan, Taguig, and Valenzuela and in the Municipality of Pateros in Metro Manila; ..."

> "... barangays of Balucuc and Calantipe in Apalit, Pampanga; Barnagay Concepcion in San Simon, Pampanga; and barangays of Bahay Pare, Barangca, Dulong Ilog, Magumbali, Mandili, Mapaniqui, Paliqui, Pangclara, Pulong Gubat, Pulong Palazan, Salapungan, Vizal San Pablo, Vizal Santo Cristo, and Vizal Sto. Niño in Candaba, Pampanga, is hereby renewed."

Ellipses above mark omitted middle clauses only; the snapshot is the unmodified text.


### 2.1 Prior franchise (RA 9209) and the title-vs-text trap

| field | value |
| --- | --- |
| Prior law | **RA 9209** (approved 2003-06-09) |
| URL | <https://lawphil.net/statutes/repacts/ra2003/ra_9209_2003.html> (LawPhil) |
| Retrieved | 2026-11-10T19:13:21+08:00 (HTTP 200) |
| Snapshot SHA-256 | `66f17c83dd64eeef8a973014902ed741084df3f92cb62080a3eabcb48c782a3d` |

**Batangas nuance (verified):** the RA 9209 *title* says "...AND CERTAIN CITIES/MUNICIPALITIES/BARANGAYS IN BATANGAS, LAGUNA, QUEZON AND PAMPANGA", but its **Section 1 enumerates no Batangas LGU at all** — the enumeration proceeds Metro Manila → Bulacan → Cavite → Rizal → Laguna → Quezon → Pampanga. RA 12146 adds the Batangas territory explicitly (Batangas City, Sto. Tomas, San Pascual). Do not infer pre-2025 Batangas coverage from the old title.

### 2.2 RA 9209 vs RA 12146 — what changed (derived from both Section 1 texts)

| Group | RA 9209 (2003) | RA 12146 (2025) | Change |
| --- | --- | --- | --- |
| NCR | 17 | 17 | same set (spellings/city titles updated) |
| Bulacan | 24 | 24 | same set (spellings/city titles updated) |
| Cavite | 23 | 20 | dropped Amadeo, Gen. Alvarez, Gen. E. Aguinaldo |
| Rizal | 14 | 14 | same set (spellings/city titles updated) |
| Laguna | 15 | 19 | added San Pablo, San Pedro, Rizal, Sta. Cruz |
| Quezon | 6 | 11 | added Lucena, Lucban, Mauban, Pagbilao, Sampaloc |
| Pampanga (barangays) | 16 brgys (Balucuc, Concepcion listed under San Simon + Candaba 14) | **17 brgys** (Apalit 2, San Simon 1, Candaba 14) | +Calantipe; corrected Apalit/Simon attribution |
| Batangas | 0 enumerated | **3 LGUs** | added Batangas City, Sto. Tomas, San Pascual |

**Cavite is the one place coverage shrank:** RA 9209 enumerated all 23 Cavite LGUs (including Amadeo, Gen. Emilio Aguinaldo, Gen. Mariano Alvarez); RA 12146 enumerates 20 and omits those three. The law text gives no reason; no other Cavite-based utility appears in the 141-utility DOE workbook (its seven Region IV-A utilities are FBPC, IEEC, BATELEC-I, BATELEC-II, FLECO, QUEZELCO-I, QUEZELCO-II). This is flagged as U1 for DOE/partner verification — the JSON encodes exactly what the law enumerates.

---

## 3. Coverage summary (verified mapping vs PSGC 2026-3Q LGU counts)

LGU totals are the `adm3` feature counts in the pinned map package (`faeldon/philippines-json-maps` v1.1.1, PSGC 2026-3Q) for the same administrative layer that the map uses.

| Region | Province / group | Coverage status | LGUs covered / total | adm3_psgc count | Notes |
| --- | --- | --- | --- | --- | --- |
| NCR (1300000000) | Metro Manila (4 map districts) | **full** | 17 / 17 | 17 | 16 cities + Pateros |
| Region III (0300000000) | Bulacan | **full** | 24 / 24 | 24 | 4 cities + 20 municipalities |
| Region III (0300000000) | Pampanga | **barangay-only** | 0 / 22 | 0 LGUs (17 brgys in 3 LGUs) | No whole LGU; Apalit, San Simon, Candaba only |
| Region IV-A (0400000000) | Rizal | **full** | 14 / 14 | 14 | |
| Region IV-A (0400000000) | Cavite | partial | 20 / 23 | 20 | 3 LGUs not enumerated (U1) |
| Region IV-A (0400000000) | Laguna | partial | 19 / 30 | 19 | |
| Region IV-A (0400000000) | Quezon | partial | 11 / 41 | 11 | incl. Lucena HUC and Tayabas |
| Region IV-A (0400000000) | Batangas | partial | 3 / 34 | 3 | |

**Totals:** 108 distinct LGUs covered (108 fully enumerated LGUs; Pampanga barangays add 17 `adm4_psgc` but no whole LGU). Region totals in the same layer: NCR 17, Region III 130, Region IV-A 142 → Meralco touches 3 of 18 regions and ~37% of the LGUs in those three regions, but no region outside NCR is fully covered.

---

## 4. Enumeration → PSGC mapping (every name mapped; no guesses)

`match` values: `exact` = same string in the law and the PSGC layer; `normalized/alias` = case/abbreviation/alias/rename normalization only (no inference); each alias is listed in §6.

### 4.1 NCR — 17/17 (region_psgc 1300000000)

NCR has no province level in the map package: the 17 LGUs sit in 4 district features (`adm2` codes 1303900000, 1307400000, 1307500000, 1307600000). District composition below is verified from those features.

- **District `1303900000`** (1 LGUs): City of Manila (`1380600000`)
- **District `1307400000`** (5 LGUs): City of Mandaluyong (`1380500000`), City of Marikina (`1380700000`), City of Pasig (`1381200000`), Quezon City (`1381300000`), City of San Juan (`1381400000`)
- **District `1307500000`** (4 LGUs): City of Caloocan (`1380100000`), City of Malabon (`1380400000`), City of Navotas (`1380900000`), City of Valenzuela (`1381600000`)
- **District `1307600000`** (7 LGUs): City of Las Piñas (`1380200000`), City of Makati (`1380300000`), City of Muntinlupa (`1380800000`), City of Parañaque (`1381000000`), Pasay City (`1381100000`), City of Taguig (`1381500000`), Pateros (`1381701000`)

Full table:

| Law name (RA 12146) | adm3_en (PSGC 2026-3Q) | adm3_psgc | match |
| --- | --- | --- | --- |
| Manila | City of Manila | `1380600000` | normalized/alias |
| Mandaluyong | City of Mandaluyong | `1380500000` | normalized/alias |
| Marikina | City of Marikina | `1380700000` | normalized/alias |
| Pasig | City of Pasig | `1381200000` | normalized/alias |
| Quezon | Quezon City | `1381300000` | normalized/alias |
| San Juan | City of San Juan | `1381400000` | normalized/alias |
| Caloocan | City of Caloocan | `1380100000` | normalized/alias |
| Malabon | City of Malabon | `1380400000` | normalized/alias |
| Navotas | City of Navotas | `1380900000` | normalized/alias |
| Valenzuela | City of Valenzuela | `1381600000` | normalized/alias |
| Las Piñas | City of Las Piñas | `1380200000` | normalized/alias |
| Makati | City of Makati | `1380300000` | normalized/alias |
| Muntinlupa | City of Muntinlupa | `1380800000` | normalized/alias |
| Parañaque | City of Parañaque | `1381000000` | normalized/alias |
| Pasay | Pasay City | `1381100000` | normalized/alias |
| Taguig | City of Taguig | `1381500000` | normalized/alias |
| Pateros | Pateros | `1381701000` | exact |

### 4.2 Bulacan — 24/24 (full; province layer code `301400000`, canonical PSGC `0301400000`, region `0300000000`)

| Law name (RA 12146) | adm3_en (PSGC 2026-3Q) | adm3_psgc | match |
| --- | --- | --- | --- |
| Baliwag | City of Baliwag | `301403000` | normalized/alias |
| Malolos | City of Malolos | `301410000` | normalized/alias |
| Meycauayan | City of Meycauayan | `301412000` | normalized/alias |
| San Jose del Monte | City of San Jose Del Monte | `301420000` | normalized/alias |
| Angat | Angat | `301401000` | exact |
| Balagtas | Balagtas | `301402000` | exact |
| Bocaue | Bocaue | `301404000` | exact |
| Bulakan | Bulacan | `301405000` | normalized/alias |
| Bustos | Bustos | `301406000` | exact |
| Calumpit | Calumpit | `301407000` | exact |
| Doña Remedios Trinidad | Doña Remedios Trinidad | `301424000` | exact |
| Guiguinto | Guiguinto | `301408000` | exact |
| Hagonoy | Hagonoy | `301409000` | exact |
| Marilao | Marilao | `301411000` | exact |
| Norzagarayn | Norzagaray | `301413000` | normalized/alias |
| Obando | Obando | `301414000` | exact |
| Pandi | Pandi | `301415000` | exact |
| Paombong | Paombong | `301416000` | exact |
| Plaridel | Plaridel | `301417000` | exact |
| Pulilan | Pulilan | `301418000` | exact |
| San Ildefonso | San Ildefonso | `301419000` | exact |
| San Miguel | San Miguel | `301421000` | exact |
| San Rafael | San Rafael | `301422000` | exact |
| Sta. Maria | Santa Maria | `301423000` | normalized/alias |

### 4.3 Cavite — 20/23 (partial; province layer code `402100000`, canonical PSGC `0402100000`, region `0400000000`)

| Law name (RA 12146) | adm3_en (PSGC 2026-3Q) | adm3_psgc | match |
| --- | --- | --- | --- |
| Bacoor | City of Bacoor | `402103000` | normalized/alias |
| Carmona | City of Carmona | `402104000` | normalized/alias |
| Cavite | City of Cavite | `402105000` | normalized/alias |
| Dasmariñas | City of Dasmariñas | `402106000` | normalized/alias |
| General Trias | City of General Trias | `402108000` | normalized/alias |
| Imus | City of Imus | `402109000` | normalized/alias |
| Tagaytay | City of Tagaytay | `402119000` | normalized/alias |
| Trece Martires | City of Trece Martires | `402122000` | normalized/alias |
| Alfonso | Alfonso | `402101000` | exact |
| Indang | Indang | `402110000` | exact |
| Kawit | Kawit | `402111000` | exact |
| Magallanes | Magallanes | `402112000` | exact |
| Maragondon | Maragondon | `402113000` | exact |
| Mendez | Mendez | `402114000` | exact |
| Naic | Naic | `402115000` | exact |
| Noveleta | Noveleta | `402116000` | exact |
| Rosario | Rosario | `402117000` | exact |
| Silang | Silang | `402118000` | exact |
| Tanza | Tanza | `402120000` | exact |
| Ternate | Ternate | `402121000` | exact |

### 4.4 Rizal — 14/14 (full; province layer code `405800000`, canonical PSGC `0405800000`, region `0400000000`)

| Law name (RA 12146) | adm3_en (PSGC 2026-3Q) | adm3_psgc | match |
| --- | --- | --- | --- |
| Antipolo | City of Antipolo | `405802000` | normalized/alias |
| Angono | Angono | `405801000` | exact |
| Baras | Baras | `405803000` | exact |
| Binangonan | Binangonan | `405804000` | exact |
| Cainta | Cainta | `405805000` | exact |
| Cardona | Cardona | `405806000` | exact |
| Jala-Jala | Jala-Jala | `405807000` | exact |
| Montalban | Rodriguez | `405808000` | normalized/alias |
| Morong | Morong | `405809000` | exact |
| Pililia | Pililla | `405810000` | normalized/alias |
| San Mateo | San Mateo | `405811000` | exact |
| Tanay | Tanay | `405812000` | exact |
| Taytay | Taytay | `405813000` | exact |
| Teresa | Teresa | `405814000` | exact |

### 4.5 Batangas — 3/34 (partial; province layer code `401000000`, canonical PSGC `0401000000`, region `0400000000`)

| Law name (RA 12146) | adm3_en (PSGC 2026-3Q) | adm3_psgc | match |
| --- | --- | --- | --- |
| Batangas | Batangas City | `401005000` | normalized/alias |
| Sto. Tomas | City of Sto. Tomas | `401028000` | normalized/alias |
| San Pascual | San Pascual | `401026000` | exact |

### 4.6 Laguna — 19/30 (partial; province layer code `403400000`, canonical PSGC `0403400000`, region `0400000000`)

| Law name (RA 12146) | adm3_en (PSGC 2026-3Q) | adm3_psgc | match |
| --- | --- | --- | --- |
| Biñan | City of Biñan | `403403000` | normalized/alias |
| Cabuyao | City of Cabuyao | `403404000` | normalized/alias |
| Calamba | City of Calamba | `403405000` | normalized/alias |
| San Pablo | City of San Pablo | `403424000` | normalized/alias |
| San Pedro | City of San Pedro | `403425000` | normalized/alias |
| Sta. Rosa | City of Santa Rosa | `403428000` | normalized/alias |
| Alaminos | Alaminos | `403401000` | exact |
| Bay | Bay | `403402000` | exact |
| Calauan | Calauan | `403406000` | exact |
| Liliw | Liliw | `403410000` | exact |
| Los Baños | Los Baños | `403411000` | exact |
| Luisiana | Luisiana | `403412000` | exact |
| Magdalena | Magdalena | `403415000` | exact |
| Majayjay | Majayjay | `403416000` | exact |
| Nagcarlan | Nagcarlan | `403417000` | exact |
| Pila | Pila | `403422000` | exact |
| Rizal | Rizal | `403423000` | exact |
| Sta. Cruz | Santa Cruz | `403426000` | normalized/alias |
| Victoria | Victoria | `403430000` | exact |

### 4.7 Quezon — 11/41 (partial; province layer code `405600000`, canonical PSGC `0405600000`, region `0400000000`)

| Law name (RA 12146) | adm3_en (PSGC 2026-3Q) | adm3_psgc | match |
| --- | --- | --- | --- |
| Lucena | City of Lucena | `431200000` | normalized/alias |
| Tayabas | City of Tayabas | `405647000` | normalized/alias |
| Candelaria | Candelaria | `405608000` | exact |
| Dolores | Dolores | `405615000` | exact |
| Lucban | Lucban | `405623000` | exact |
| Mauban | Mauban | `405627000` | exact |
| Pagbilao | Pagbilao | `405630000` | exact |
| Sampaloc | Sampaloc | `405639000` | exact |
| San Antonio | San Antonio | `405641000` | exact |
| Sariaya | Sariaya | `405645000` | exact |
| Tiaong | Tiaong | `405648000` | exact |

### 4.8 Pampanga — barangay-level only (province layer code `305400000`, canonical PSGC `0305400000`)

RA 12146 Section 1 names only Pampanga **barangays**, not LGUs. 17 barangays in 3 municipalities are covered; no whole Pampanga LGU is covered. Barangay identities verified against the `bgysubmuns-municity-*` adm4 layer of the same map package.

| Municipality | adm3_psgc | Law barangays | Verified barangays (adm4_en / adm4_psgc) |
| --- | --- | --- | --- |
| Apalit | `305402000` | Balucuc, Calantipe | Balucuc (`305402001`), Calantipe (`305402003`) |
| San Simon | `305418000` | Concepcion | Concepcion (`305418001`) |
| Candaba | `305405000` | Bahay Pare, Barangca, Dulong Ilog, Magumbali, Mandili, Mapaniqui, Paliqui, Pangclara, Pulong Gubat, Pulong Palazan, Salapungan, Vizal San Pablo, Vizal Santo Cristo, Vizal Sto. Niño | Bahay Pare (`305405001`), Barangca (`305405003`), Dulong Ilog (`305405010`), Magumbali (`305405014`), Mandili (`305405016`), Mapaniqui (`305405018`), Paligui (`305405020`) ← law: Paliqui, Pangclara (`305405021`), Pulong Gubat (`305405026`), Pulong Palazan (`305405027`), Salapungan (`305405028`), Vizal San Pablo (`305405035`), Vizal Santo Cristo (`305405036`), Vizal Santo Niño (`305405037`) ← law: Vizal Sto. Niño |

Aliases applied here: `Paliqui` → `Paligui` (`305405020`, Candaba — the same barangay name also exists in Apalit but the law groups it under Candaba), `Vizal Sto. Niño` → `Vizal Santo Niño` (`305405037`). Note RA 12146 typo "Barnagay" in the San Simon clause (preserved in the snapshot).

---

## 5. Name-matching / alias log (all normalized pairs)

The parser first normalizes case, accents (NFKD), punctuation, hyphens, `Sta.`→`Santa`, `Sto.`→`Santo`, `Gen.`→`General`, and strips `City of`/`City`. Anything still different was resolved with an explicit alias (never fuzzy matching). The 45 `normalized/alias` pairs are:

| Province | Law name | PSGC name | adm3_psgc | reason |
| --- | --- | --- | --- | --- |
| Bulacan | Baliwag | City of Baliwag | `301403000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Bulacan | Malolos | City of Malolos | `301410000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Bulacan | Meycauayan | City of Meycauayan | `301412000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Bulacan | San Jose del Monte | City of San Jose Del Monte | `301420000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Bulacan | Bulakan | Bulacan | `301405000` | law spelling "Bulakan"; PSGC layer uses "Bulacan" (municipality, 301405000); name collides with the province |
| Bulacan | Norzagarayn | Norzagaray | `301413000` | law typo (RA 12146 prints "Norzagarayn") |
| Bulacan | Sta. Maria | Santa Maria | `301423000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Batangas | Batangas | Batangas City | `401005000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Batangas | Sto. Tomas | City of Sto. Tomas | `401028000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Cavite | Bacoor | City of Bacoor | `402103000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Cavite | Carmona | City of Carmona | `402104000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Cavite | Cavite | City of Cavite | `402105000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Cavite | Dasmariñas | City of Dasmariñas | `402106000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Cavite | General Trias | City of General Trias | `402108000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Cavite | Imus | City of Imus | `402109000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Cavite | Tagaytay | City of Tagaytay | `402119000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Cavite | Trece Martires | City of Trece Martires | `402122000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Laguna | Biñan | City of Biñan | `403403000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Laguna | Cabuyao | City of Cabuyao | `403404000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Laguna | Calamba | City of Calamba | `403405000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Laguna | San Pablo | City of San Pablo | `403424000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Laguna | San Pedro | City of San Pedro | `403425000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Laguna | Sta. Rosa | City of Santa Rosa | `403428000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Laguna | Sta. Cruz | Santa Cruz | `403426000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Quezon | Lucena | City of Lucena | `431200000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Quezon | Tayabas | City of Tayabas | `405647000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Rizal | Antipolo | City of Antipolo | `405802000` | abbreviation/case/city-title normalization (Sta./Sto., City of, etc.) |
| Rizal | Montalban | Rodriguez | `405808000` | LGU renamed Rodriguez (2009); PSGC 2026-3Q uses Rodriguez |
| Rizal | Pililia | Pililla | `405810000` | law typo; official name Pililla |
| NCR | Manila | City of Manila | `1380600000` | city-title normalization |
| NCR | Mandaluyong | City of Mandaluyong | `1380500000` | city-title normalization |
| NCR | Marikina | City of Marikina | `1380700000` | city-title normalization |
| NCR | Pasig | City of Pasig | `1381200000` | city-title normalization |
| NCR | Quezon | Quezon City | `1381300000` | city-title normalization |
| NCR | San Juan | City of San Juan | `1381400000` | city-title normalization |
| NCR | Caloocan | City of Caloocan | `1380100000` | city-title normalization |
| NCR | Malabon | City of Malabon | `1380400000` | city-title normalization |
| NCR | Navotas | City of Navotas | `1380900000` | city-title normalization |
| NCR | Valenzuela | City of Valenzuela | `1381600000` | city-title normalization |
| NCR | Las Piñas | City of Las Piñas | `1380200000` | city-title normalization |
| NCR | Makati | City of Makati | `1380300000` | city-title normalization |
| NCR | Muntinlupa | City of Muntinlupa | `1380800000` | city-title normalization |
| NCR | Parañaque | City of Parañaque | `1381000000` | city-title normalization |
| NCR | Pasay | Pasay City | `1381100000` | city-title normalization |
| NCR | Taguig | City of Taguig | `1381500000` | city-title normalization |

Unmatched names: **none** (0). Ambiguous matches: **none**. Every RA 12146 Section 1 name has exactly one PSGC adm3 (or adm4, for Pampanga) counterpart.

---

## 6. Multi-region verification against the 141-utility seed dataset

Checked `data/seed/utilities.csv` (the ingested DOE workbook; 141 rows):

- Rows: **141**; distinct `utility_code`: 141 (no duplicates).
- Each row carries exactly **one** `region_psgc`; there is no row with multiple regions, no duplicate utility spanning regions, and no utility duplicated across regions.
- 18 regions are represented. **MERALCO is the only utility in NCR**, at `region_psgc=1300000000`, `region_short=NCR`, `du_type=PIOU`, `grid_connection=ONGRID` — confirming the DOE workbook's single-region assignment.
- **Conclusion:** no other utility in the seed dataset spans more than one DOE region. **Meralco is the only multi-region DU franchise identified** (NCR + Region III + Region IV-A). No other multi-region DU franchise was verified in this research; boundary-crossing cooperative cases (e.g. the BARMM Special Geographic Area barangays formerly part of Cotabato, or the recreated Negros Island Region) were **not** verified and are deliberately not encoded (U8).

---

## 7. Pinned input provenance

- Map/PSGC layer: **faeldon/philippines-json-maps v1.1.1** (released 2026-11-07, PSGC 2026-3Q), archive `e7a00ff5a65c525557ff716658b579dab5c20322bd6b710495bf74e6cf2377d3` retrieved 2026-11-10T10:02:57Z; `topojson/provdists/hires/municities-provdist-<adm2code>.topo.0.1.json (adm3 features); topojson/municities/hires/bgysubmuns-municity-<adm3code>.topo.0.1.json (adm4 features, Pampanga)`; join keys `adm3_psgc`, `adm4_psgc`. Licence: MIT (repository scripts/maps); boundaries CC BY 3.0 IGO (CC BY-IGO), © NAMRIA and PSA via OCHA Philippines COD-AB.
- Law texts: Supreme Court E-Library (RA 12146) and LawPhil (RA 9209); snapshots + SHA-256 + retrieval timestamps in `research/source-snapshots/`.
- Utility/region cross-check: `data/seed/utilities.csv` (DOE workbook ingest, retrieved 2026-11-10; see `data/seed/README.md` and `data/seed/sources.csv`).

---

## 8. Caveats and uncertainties (do not publish past these)

**U1 — Cavite coverage shrank between laws.** RA 9209 Section 1 enumerated all 23 Cavite LGUs; RA 12146 enumerates 20 and omits Amadeo, General Emilio Aguinaldo and Gen. Mariano Alvarez. The reason is not stated in the law text and was not verified. No other Cavite-based utility appears in the 141-utility DOE workbook (its seven Region IV-A utilities are FBPC, IEEC, BATELEC-I, BATELEC-II, FLECO, QUEZELCO-I, QUEZELCO-II). Flag for DOE/coalition verification before publishing any map claim about who serves those three LGUs.

**U2 — RA 9209 title vs Section 1 on Batangas.** The RA 9209 title says "...AND CERTAIN CITIES/MUNICIPALITIES/BARANGAYS IN BATANGAS, LAGUNA, QUEZON AND PAMPANGA" but Section 1 enumerates zero Batangas LGUs. RA 12146 adds Batangas City, Sto. Tomas City and San Pascual. Historical Batangas coverage therefore cannot be inferred from the older title.

**U3 — Pampanga attribution in RA 9209.** RA 9209 wording "barangays of Balucuc and Concepcion in San Simon" mis-attributes Balucuc (which is in Apalit) and omits Calantipe. RA 12146 corrects: Apalit = Balucuc + Calantipe; San Simon = Concepcion; Candaba = 14 barangays. Barangay-level coverage only; no whole Pampanga LGU is in the franchise.

**U4 — Franchise vs actual billing territory.** This dataset encodes the legislative franchise area from RA 12146 Section 1, not verified household-level service territory. Distribution service can differ (unenergized areas, ERC-approved arrangements, contested areas). Use as a coverage/filter layer, not as proof of who bills an address.

**U5 — PSGC code width and NCR districts.** adm3_psgc/adm4_psgc values are copied verbatim from the map package layer. That layer stores PSGC codes as integers, so the leading zero of regions 01-09 is dropped: LGUs outside NCR are 9-digit strings (e.g. 301401000 for Angat; canonical 10-digit PSGC 0301401000), NCR LGUs are 10-digit (e.g. 1380600000), and province-layer adm2 codes are 9-digit (301400000) vs canonical 10-digit (0301400000). Both forms are provided: adm3_psgc/adm4_psgc are the exact map-layer strings (join to the same topojson layer with these), and adm3_psgc_canonical/adm4_psgc_canonical are the zero-padded 10-digit form (cross-dataset joins). Province entries also carry province_psgc_topojson (map layer) and province_psgc (canonical). NCR has no province-level code: the package splits NCR into 4 districts (1303900000/1307400000/1307500000/1307600000), and all 17 NCR LGUs are mapped under ncr.districts[].lgus.

**U6 — Renamed LGU: Montalban -> Rodriguez.** RA 12146 uses "Montalban"; PSGC 2026-3Q and the map package use "Rodriguez" (renamed by law in 2009). Mapped to adm3_psgc 405808000.

**U7 — Name mismatches forced by law typos.** Norzagarayn->Norzagaray (301413000); Pililia->Pililla (405810000); Bulakan->Bulacan municipality (301405000; name collision with the province); Paliqui->Paligui (Candaba, 305405020); Vizal Sto. Niño->Vizal Santo Niño (305405037); Sta./Sto. expanded to Santa/Santo; Mendez Nuñez (RA 9209) -> Mendez (RA 12146 and PSGC).

**U8 — Multi-region DUs other than Meralco.** None found in the 141-row DOE seed dataset and none verified in this research. Meralco is the only known multi-region DU franchise (NCR + Region III + Region IV-A). Possible boundary oddities among electric cooperatives (BARMM Special Geographic Area / Cotabato; recreated NIR) were not verified and are not encoded.

**U9 — Source spelling of Quezon enumeration.** RA 12146 enumerates "cities of Lucena and Tayabas" (Lucena is an independent/Highly Urbanized City, PSGC 431200000, appearing in the Quezon province map layer) plus 9 municipalities; Quezon province has 41 LGUs in the 2026-3Q PSGC layer (39 municipalities + 1 component city + 1 HUC).

---

## 9. Recommended use on the map / API

1. **Canonical filter fields:** `covered_regions_psgc` (3 regions), `covered_adm3_psgc` (108 LGU codes), plus `pampanga_barangays[].municipalities[].barangays[].adm4_psgc` (17 codes). Treat `service-areas.json` as the source of truth; do not re-parse the law in the frontend.
2. **Multi-region override:** MERALCO's provider record should carry `regions = [1300000000, 0300000000, 0400000000]` and `multi_region = true`, while its DOE rate row keeps `region_psgc = 1300000000` (do not rewrite the source row; expose an explicit `service_area_regions` overlay, otherwise region aggregates/medians double-count or misattribute Meralco).
3. **Region-level rendering:** NCR = full; Region III = partial (Bulacan full + Pampanga barangays); Region IV-A = partial (all five provinces touched, only Rizal complete). Use a `partial` hatch/badge rather than a full fill.
4. **LGU-level rendering:** if an LGU layer is added, join on `adm3_psgc`; the 108 codes are exact and all exist in the PSGC 2026-3Q province-level topology. **Code width matters:** map-layer codes for regions 01-09 are 9-digit strings (e.g. `301401000`); `adm3_psgc_canonical` in the JSON is the zero-padded 10-digit PSGC (`0301401000`). Join to the same topojson layer with the map-layer string. For Pampanga, LGU polygons are only partially in-franchise — use the 17 `adm4_psgc` for barangay-level shading, or label "partial" at LGU level.
5. **Pampanga has zero whole-LGU coverage:** never mark the three Pampanga LGUs as fully served.
6. **Convenience join:** `adm2_units` in the JSON lists the 11 map adm2 units (4 NCR district codes + 7 province codes) with `coverage`, `lgu_count_covered` and `lgu_count_total`, so a region/adm2-level filter can consume one array without re-deriving it.

---

## 10. Verification log (all done 2026-11-10)

| Source | URL | Result |
| --- | --- | --- |
| RA 12146, Section 1 | <https://elibrary.judiciary.gov.ph/thebookshelf/showdocsfriendly/2/98850> | HTTP 200, Section 1 extracted verbatim (2278 chars), SHA-256 `515341ac88f6fe94…` |
| RA 9209, Section 1 | <https://lawphil.net/statutes/repacts/ra2003/ra_9209_2003.html> | HTTP 200, Section 1 extracted verbatim, SHA-256 `66f17c83dd64eeef…` |
| Map/PSGC layer | <https://github.com/faeldon/philippines-json-maps/releases/tag/v1.1.1> | release verified via repo provenance + cached archive SHA-256 (the map asset already pinned in `draft/assets/geo-sources.json`) |
| LGU identity check | adm3/adm4 features in the archive | all 108 adm3 codes and 17 adm4 codes exist in the package; 0 unmatched, 0 ambiguous |
| Multi-region check | `data/seed/utilities.csv` | 141 rows, one region each, no duplicates; only MERALCO in NCR |
| Cross-check of law text | DOE hosts a copy of RA 12146 | <https://doe.gov.ph/republic-act-12146> returns 200 and links the RA 12146 PDF; used only as existence cross-check (e-Library text is the source used) |

## 11. Files

| File | Purpose |
| --- | --- |
| `research/service-areas.json` | Canonical structured coverage (machine-readable; schema below) |
| `research/service-areas.md` | This research note (narrative + audit tables) |
| `research/source-snapshots/ra-12146-section1.txt` | Verbatim RA 12146 Section 1 |
| `research/source-snapshots/ra-9209-section1.txt` | Verbatim RA 9209 Section 1 |
| `research/source-snapshots/*.provenance.json` | URL, retrieval time, HTTP status, bytes, SHA-256, extraction notes |

`service-areas.json` top-level shape: `utility_code`, `utility_name`, `multi_region`, `schema_version`, `law`, `prior_law`, `entity_kind`, `coverage_semantics`, `regions[]`, `adm2_units[]` (the 11 map adm2 units: 4 NCR districts + 7 provinces — easiest join for a provider filter), `ncr` (districts → LGUs), `provinces[]` (each with `lgus[]`; each LGU carries `adm3_psgc` + `adm3_psgc_canonical`), `pampanga_barangays` (each barangay carries `adm4_psgc` + `adm4_psgc_canonical`), `covered_adm3_psgc[]`, `covered_adm3_count`, `covered_regions_psgc[]`, `counts`, `cross_checks`, `uncertainties[]`, `topology_source`.

