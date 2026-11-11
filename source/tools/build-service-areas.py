#!/usr/bin/env python3
"""Assemble the published service-area dataset for the provider filter.

Why this tool exists
--------------------
The DOE workbook publishes each distribution utility once, under a single
region. That is enough to filter by region, but it is not the utility's service
area: an electric cooperative usually covers a handful of municipalities, and a
few franchises (Meralco is the clear case) span several regions. The page's
provider filter needs the real coverage footprint, mapped to the same PSGC
codes as the geometry.

Inputs (in precedence order)
----------------------------
1. ``research/coverage/osm-service-areas.csv`` - LGU-level franchise areas
   extracted from the OpenStreetMap Wiki operator table (CC BY-SA 2.0, compiled
   from DOE franchise records; see research/coverage/README.md). Optional: if
   it does not exist yet, every utility without a curated override falls back
   to region level.
2. ``research/service-areas.json`` - the authoritative RA 12146 service area
   for MERALCO (108 cities/municipalities plus 17 Pampanga barangays), encoded
   by tools-side research. MERALCO's OSM rows are ignored: the franchise law
   wins.
3. ``data/seed/utilities.csv`` - the utility registry (one DOE region each).
   Utilities with no LGU-level rows get a single ``area_level=region`` row so
   the provider filter still has something honest to show.

Outputs
-------
* ``data/seed/service_areas.csv`` - tidy published dataset:
  one row per (utility, covered LGU) / (utility, covered barangay) / fallback
  region row.
* ``data/seed/service_area_sources.csv`` - source registry with the licence and
  attribution for every source_id used above.

Both files are deterministic (sorted by utilities.csv order, then code order),
so re-running the tool twice produces byte-identical output. The tool refuses
to write when a code does not join to the pinned geometry, when a utility has
no coverage at all, or when a row is duplicated.
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "data", "seed")
GE0 = os.path.join(ROOT, "draft", "assets", "coverage-geo.json")
UTILITIES = os.path.join(SEED, "utilities.csv")
REGIONS_CSV = os.path.join(SEED, "regions.csv")
LAW = os.path.join(ROOT, "research", "service-areas.json")
OSM_ROWS = os.path.join(ROOT, "research", "coverage", "osm-service-areas.csv")
OSM_RAW = os.path.join(ROOT, "research", "coverage", "osm-operators.json")
OUT_AREAS = os.path.join(SEED, "service_areas.csv")
OUT_SOURCES = os.path.join(SEED, "service_area_sources.csv")

AREA_HEADER = [
    "utility_code", "source_id", "area_level", "region_psgc", "province_psgc",
    "province_name", "adm3_psgc", "lgu_name", "adm4_psgc", "barangay_name",
    "coverage_note",
]
SOURCE_HEADER = [
    "source_id", "publisher", "dataset_title", "page_url", "revision_id",
    "retrieved_at", "license", "attribution", "notes",
]

SOURCE_DOE = "SRC-DOE-RATES"
SOURCE_LAW = "SRC-RA-12146"
SOURCE_OSM = "SRC-OSM-OPERATORS"
SOURCE_WIKI = "SRC-WIKI-DUS"
SOURCE_REGISTRY = os.path.join(SEED, "service_area_sources.csv")


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def require(condition, message, problems):
    if not condition:
        problems.append(message)


def canonical_code(value):
    """Zero-pad a PSGC code to its canonical 10-digit form."""
    value = str(value or "").strip()
    if not value:
        return ""
    if value.isdigit() and len(value) < 10:
        return value.zfill(10)
    return value


def build_source_registry(law, fallback_count, used_sources):
    """Return the source registry rows, preserving upstream extraction metadata.

    The extraction report supplies the OSM/Wikipedia records (revisions, URLs,
    licences, attribution). This tool updates the two records it owns: the
    RA 12146 record notes that the law is the operative Meralco service area,
    and the DOE record records how many region-level fallback rows were needed.
    """
    base = []
    if os.path.isfile(SOURCE_REGISTRY):
        with open(SOURCE_REGISTRY, encoding="utf-8", newline="") as fh:
            base = list(csv.DictReader(fh))
    rows = {row["source_id"]: list(row.values()) for row in base}
    law_meta = law["law"]
    rows[SOURCE_LAW] = [
        SOURCE_LAW, "Congress of the Philippines / Supreme Court e-Library",
        "Republic Act No. 12146 - renewal of the Meralco franchise, Section 1",
        law_meta["url"], law_meta["id"] + " (" + law_meta["approved"] + ")",
        law_meta["retrieved_at"],
        "Public document (Philippine law); works of the Government are not subject "
        "to copyright (IP Code, Sec. 176).",
        "Republic Act No. 12146, official text via the Supreme Court e-Library.",
        "Operative service area for MERALCO: %d cities/municipalities in NCR, Region III "
        "and Region IV-A plus %d Pampanga barangays; overrides the DOE single-region row."
        % (law["counts"]["covered_adm3_total"],
           law["counts"]["pampanga_barangays"]),
    ]
    rows[SOURCE_DOE] = [
        SOURCE_DOE, "Department of Energy (DOE)",
        "Electricity Rates & Power Market Monitor - distribution utility region column",
        "https://doe.gov.ph/data-and-prices/electricity",
        "workbook snapshot 2026-11-10", "2026-11-10T17:00:34+08:00",
        "No explicit dataset licence found on the DOE page; figures are public records. "
        "Reuse terms to be confirmed with DOE.",
        "Department of Energy (Philippines), Electricity Rates & Power Market Monitor.",
        "Used for the DOE region assignment in utilities.csv and as an area_level=region "
        "fallback. Fallback rows in this build: %d utilities." % fallback_count,
    ]
    order = [SOURCE_OSM, SOURCE_WIKI, SOURCE_LAW, SOURCE_DOE]
    result = []
    for source_id in order:
        if source_id == SOURCE_OSM and source_id not in rows:
            rows[source_id] = [
                SOURCE_OSM, "OpenStreetMap Wiki contributors",
                "Power networks/Philippines/Operators - franchise areas per distribution utility",
                "https://wiki.openstreetmap.org/wiki/Power_networks/Philippines/Operators",
                "2836797", "2026-11-10", "CC BY-SA 2.0",
                "OpenStreetMap Wiki contributors, CC BY-SA 2.0.",
                "LGU-level service areas for utilities other than MERALCO.",
            ]
        if source_id == SOURCE_WIKI and source_id not in rows and SOURCE_WIKI in used_sources:
            rows[source_id] = [
                SOURCE_WIKI, "Wikipedia contributors",
                "List of electric distribution utilities in the Philippines",
                "https://en.wikipedia.org/wiki/List_of_electric_distribution_utilities_in_the_Philippines",
                "", "2026-11-10", "CC BY-SA 4.0",
                "Wikipedia contributors, CC BY-SA 4.0.",
                "Supplementary LGU service areas where the OSM table has no franchise list.",
            ]
        if source_id in rows and (source_id in used_sources or source_id == SOURCE_DOE):
            result.append(rows[source_id])
    return result


def main():
    problems = []
    warnings = []

    utilities = read_csv(UTILITIES)
    utility_order = {row["utility_code"]: i for i, row in enumerate(utilities)}
    utility_region = {row["utility_code"]: row["region_psgc"] for row in utilities}
    region_rows = {row["region_psgc"]: row for row in read_csv(REGIONS_CSV)}
    region_order = {psgc: i for i, psgc in enumerate(region_rows)}

    geo = read_json(GE0)
    lgus = geo["lgus"]
    provinces = geo["provinces"]
    name_index = {}
    for psgc, lgu in lgus.items():
        name_index.setdefault((lgu["province_psgc"], lgu["name"].lower()), psgc)

    def resolve_lgu(adm3, province_psgc, lgu_name):
        """Return the canonical adm3_psgc in the geometry, or ''."""
        candidates = []
        code = canonical_code(adm3)
        if code:
            candidates.append(code)
        if province_psgc and lgu_name:
            key = (canonical_code(province_psgc), str(lgu_name).strip().lower())
            if key in name_index:
                candidates.append(name_index[key])
        for candidate in candidates:
            if candidate in lgus:
                return candidate
        return ""

    rows = []
    used_sources = set()

    # ---- 1. OSM LGU-level coverage (all utilities except MERALCO) ----------
    osm_meta = {}
    if os.path.isfile(OSM_RAW):
        try:
            raw = read_json(OSM_RAW)
            if isinstance(raw, dict):
                osm_meta = raw.get("source", raw)
        except (ValueError, OSError):
            osm_meta = {}
    if os.path.isfile(OSM_ROWS):
        seen = {}
        for row in read_csv(OSM_ROWS):
            code = (row.get("utility_code") or "").strip()
            if code == "MERALCO":
                continue  # RA 12146 override below
            if code not in utility_order:
                problems.append("OSM row for unknown utility %r" % code)
                continue
            source_id = (row.get("source_id") or SOURCE_OSM).strip()
            if source_id not in (SOURCE_OSM, SOURCE_WIKI):
                problems.append("unsupported LGU-level source %r for %s" % (source_id, code))
                continue
            adm3 = resolve_lgu(row.get("adm3_psgc"), row.get("province_psgc"),
                               row.get("lgu_name"))
            if not adm3:
                problems.append("OSM row for %s: LGU %r (%r) does not join the pinned geometry"
                                % (code, row.get("lgu_name"), row.get("adm3_psgc")))
                continue
            key = (code, adm3)
            if key in seen:
                previous_source, previous_index = seen[key]
                if previous_source == SOURCE_WIKI and source_id == SOURCE_OSM:
                    rows[previous_index] = rows[previous_index][:1] + [SOURCE_OSM] + \
                        rows[previous_index][2:]
                    seen[key] = (SOURCE_OSM, previous_index)
                else:
                    warnings.append("%s / %s appears in both sources; kept %s"
                                    % (code, adm3, previous_source))
                continue
            lgu = lgus[adm3]
            province = provinces[lgu["province_psgc"]]
            note = (row.get("coverage_note") or "").strip()
            seen[key] = (source_id, len(rows))
            rows.append([
                code, source_id, "lgu", province["region_psgc"],
                lgu["province_psgc"], province["name"],
                adm3, lgu["name"], "", "", note,
            ])
            used_sources.add(source_id)
        print("LGU-level extraction rows read: %d" % len(rows))
    else:
        warnings.append("research/coverage/osm-service-areas.csv not found - "
                        "LGU-level OSM coverage skipped")

    # ---- 2. MERALCO: RA 12146 service area --------------------------------
    law = read_json(LAW)
    law_meta = law["law"]
    meralco_notes = {}
    for item in law["provinces"]:
        region_psgc = canonical_code(item["region_psgc"])
        province_psgc = canonical_code(item["province_psgc"])
        covered = item["lgu_count_covered"]
        total = item["lgu_count_total"]
        if item["coverage"] == "full":
            note = "province coverage: full (%d of %d LGUs)" % (covered, total)
        else:
            note = "province coverage: partial (%d of %d LGUs)" % (covered, total)
        for lgu in item["lgus"]:
            adm3 = resolve_lgu(lgu["adm3_psgc_canonical"], province_psgc,
                               lgu["adm3_en"])
            require(adm3 != "", "RA 12146 LGU %r (%r) does not join the pinned geometry"
                    % (lgu["adm3_en"], lgu["adm3_psgc_canonical"]), problems)
            if not adm3:
                continue
            record = lgus[adm3]
            province = provinces[record["province_psgc"]]
            rows.append([
                "MERALCO", SOURCE_LAW, "lgu", region_psgc,
                record["province_psgc"], province["name"], adm3, record["name"],
                "", "", "",
            ])
            meralco_notes[adm3] = note
    for district in law["ncr"]["districts"]:
        district_psgc = canonical_code(district["district_psgc"])
        province = provinces.get(district_psgc, {})
        note = "province coverage: full (%d of %d LGUs)" % (
            district["lgu_count"], district["lgu_count"])
        for lgu in district["lgus"]:
            adm3 = resolve_lgu(lgu["adm3_psgc_canonical"], district_psgc, lgu["adm3_en"])
            require(adm3 != "", "RA 12146 NCR LGU %r does not join the pinned geometry"
                    % lgu["adm3_en"], problems)
            if not adm3:
                continue
            record = lgus[adm3]
            rows.append([
                "MERALCO", SOURCE_LAW, "lgu", "1300000000",
                record["province_psgc"], province.get("name", "Metro Manila"),
                adm3, record["name"], "", "", "",
            ])
    for municipality in law["pampanga_barangays"]["municipalities"]:
        adm3 = canonical_code(municipality["adm3_psgc"])
        for barangay in municipality["barangays"]:
            adm4 = canonical_code(barangay["adm4_psgc_canonical"])
            record = lgus.get(adm3, {})
            rows.append([
                "MERALCO", SOURCE_LAW, "barangay", "0300000000", "0305400000",
                "Pampanga", adm3, record.get("name", municipality["adm3_en"]),
                adm4, barangay["adm4_en"],
                "barangay-level franchise area (Pampanga): 17 of 22 LGUs have no "
                "whole-LGU coverage",
            ])
    used_sources.add(SOURCE_LAW)
    print("RA 12146 rows: %d LGU, %d barangay"
          % (len(meralco_notes),
             sum(1 for r in rows if r[1] == SOURCE_LAW and r[2] == "barangay")))

    # ---- 3. Region fallback for utilities with no LGU-level coverage ------
    covered = {row[0] for row in rows}
    fallback = 0
    for utility in utilities:
        code = utility["utility_code"]
        if code in covered:
            continue
        region_psgc = utility["region_psgc"]
        region = region_rows.get(region_psgc, {})
        rows.append([
            code, SOURCE_DOE, "region", region_psgc, "", "", "", "", "", "",
            "region-level fallback: LGU-level service area not sourced; DOE workbook "
            "region used as a single coverage area",
        ])
        fallback += 1
        used_sources.add(SOURCE_DOE)
    print("region-level fallback rows: %d (utilities: %d)"
          % (fallback, fallback))

    # ---- 4. Validate ------------------------------------------------------
    valid_regions = set(region_rows)
    seen_rows = set()
    for row in rows:
        utility_code, source_id, level = row[0], row[1], row[2]
        require(utility_code in utility_order, "unknown utility %r" % utility_code, problems)
        require(source_id in (SOURCE_OSM, SOURCE_WIKI, SOURCE_LAW, SOURCE_DOE),
                "unknown source %r" % source_id, problems)
        require(level in ("lgu", "barangay", "region"),
                "bad area_level %r for %s" % (level, utility_code), problems)
        require(row[3] in valid_regions, "bad region_psgc %r for %s" % (row[3], utility_code),
                problems)
        if level in ("lgu", "barangay"):
            require(row[6] in lgus, "LGU %r for %s is not in the geometry" % (row[6], utility_code),
                    problems)
            require(row[4] == lgus.get(row[6], {}).get("province_psgc"),
                    "province mismatch for %s / %s" % (utility_code, row[6]), problems)
        else:
            require(not row[6] and not row[8], "region row for %s carries an LGU code"
                    % utility_code, problems)
        key = (utility_code, level, row[6], row[8])
        require(key not in seen_rows, "duplicate coverage row %r" % (key,), problems)
        seen_rows.add(key)
    coverage_regions_by_utility = {}
    for row in rows:
        if row[2] != "region":
            coverage_regions_by_utility.setdefault(row[0], set()).add(row[3])
    for utility in utilities:
        code = utility["utility_code"]
        if code not in {row[0] for row in rows}:
            problems.append("utility %s has no coverage row" % code)
            continue
        regions = coverage_regions_by_utility.get(code, set())
        if regions and utility["region_psgc"] not in regions:
            warnings.append("%s: LGU coverage does not include its DOE region %s (covers %s)"
                            % (code, utility["region_psgc"], ", ".join(sorted(regions))))
    multi_region = sorted(code for code, regions in coverage_regions_by_utility.items()
                          if len(regions) > 1)

    if problems:
        print("\nCOVERAGE ASSEMBLY FAILED - nothing written:", file=sys.stderr)
        for problem in problems[:30]:
            print("  - %s" % problem, file=sys.stderr)
        if len(problems) > 30:
            print("  ... %d more" % (len(problems) - 30), file=sys.stderr)
        return 2

    # ---- 5. Document PSGC 3Q 2026 region reassignments --------------------
    # Three utilities' DOE workbook region code predates the PSGC 3Q 2026
    # reassignment (Sulu moved to Region IX, Siquijor to NIR). Their LGU rows
    # are correct; record the legacy assignment on every row instead of
    # inventing a fallback region.
    reassigned = []
    for utility in utilities:
        code = utility["utility_code"]
        regions = coverage_regions_by_utility.get(code, set())
        if regions and utility["region_psgc"] not in regions:
            legacy = region_rows.get(utility["region_psgc"], {})
            note = ("cross-region: PSGC 3Q 2026 reassignment; the DOE workbook lists %s "
                    "(legacy region code)" % legacy.get("short_name", utility["region_psgc"]))
            for row in rows:
                if row[0] == code:
                    row[10] = (row[10] + "; " if row[10] else "") + note
            reassigned.append("%s (%s -> %s)" % (code, legacy.get("short_name", "?"),
                                                 ", ".join(sorted(regions))))
    if reassigned:
        print("  documented PSGC region reassignments: %s" % ", ".join(reassigned))

    # ---- 6. Sort + write --------------------------------------------------
    rows.sort(key=lambda row: (utility_order[row[0]], row[2] != "lgu",
                               row[3], row[6] or row[8]))
    with open(OUT_AREAS, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(AREA_HEADER)
        writer.writerows(rows)

    sources = build_source_registry(law, fallback, used_sources)
    with open(OUT_SOURCES, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(SOURCE_HEADER)
        writer.writerows(sources)

    lgu_rows = sum(1 for row in rows if row[2] == "lgu")
    barangay_rows = sum(1 for row in rows if row[2] == "barangay")
    region_rows_count = sum(1 for row in rows if row[2] == "region")
    detailed = {row[0] for row in rows if row[2] in ("lgu", "barangay")}
    region_name = {psgc: row["region_name"] for psgc, row in region_rows.items()}
    print("")
    print("wrote %s" % os.path.relpath(OUT_AREAS, ROOT))
    print("  %d rows: %d LGU, %d barangay, %d region fallback"
          % (len(rows), lgu_rows, barangay_rows, region_rows_count))
    print("  %d of %d utilities have LGU-level coverage (%.0f%%); %d LGU coverage cells"
          % (len(detailed), len(utilities), 100.0 * len(detailed) / max(1, len(utilities)),
             len({(row[0], row[6]) for row in rows if row[2] == "lgu"})))
    if multi_region:
        print("  multi-region service areas: %s" % ", ".join(multi_region))
    coverage_regions = sorted({row[3] for row in rows if row[2] != "region"},
                              key=lambda psgc: region_order.get(psgc, 99))
    print("  regions touched: %d (%s)"
          % (len(coverage_regions),
             ", ".join(region_name.get(psgc, psgc) for psgc in coverage_regions)))
    print("wrote %s (%d source records)"
          % (os.path.relpath(OUT_SOURCES, ROOT), len(sources)))
    for warning in warnings[:5]:
        print("  warning: %s" % warning)
    if len(warnings) > 5:
        print("  ... %d more warnings" % (len(warnings) - 5))
    return 0


if __name__ == "__main__":
    sys.exit(main())
