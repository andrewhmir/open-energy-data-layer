#!/usr/bin/env python3
"""Ingest the DOE public electricity-rate workbook into reliable, traceable data.

Source: DOE "Electricity Rates & Power Market Monitor" page, which embeds a public
Google Sheet. Each customer-class tab is pulled through Google's unauthenticated
CSV export (the same bytes a browser gets), snapshotted, hashed, parsed, and
published as tidy CSVs plus a compact JSON payload for the draft page.

Reliability rules:
  * never impute: every cell is one of published / "NDA" (publisher says no data)
    / blank (tab has nothing) / invalid (unparseable), preserved downstream;
  * the four tabs disagree in three places. We resolve by majority, keep the
    losing claims verbatim, and mark unresolved ties as CONFLICT instead of
    guessing;
  * every row keeps its source tab (gid), source row, retrieval timestamp, hash;
  * June-2026 reference anchors are asserted; a mismatch fails the build.

Usage:  python3 tools/ingest-doe-rates.py [--refresh]
Output: data/raw/doe-rates/<retrieval-date>/<gid>.csv
        data/seed/{utilities,rates_monthly,regions,sources}.csv
        data/seed/validation.json
        data/seed/page-data.json
"""
import csv
import hashlib
import io
import json
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET_ID = "1oGc1iGpacELS6tkHjesvAeKZo8v2iv4UkYFY04e0p-I"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
PAGE_URL = "https://doe.gov.ph/data-and-prices/electricity"
SOURCE_ID = "SRC-DOE-RATES"
# Rebuilds must be reproducible: set OPEN_ENERGY_RETRIEVED_AT to the snapshot
# timestamp recorded in the existing seed data instead of stamping "now".
RETRIEVED_AT = (os.environ.get("OPEN_ENERGY_RETRIEVED_AT")
                or datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"))
RETRIEVAL_DATE = RETRIEVED_AT[:10]
RAW_DIR = os.path.join(ROOT, "data", "raw", "doe-rates", RETRIEVAL_DATE)
SEED_DIR = os.path.join(ROOT, "data", "seed")
SERVICE_AREAS_CSV = os.path.join(SEED_DIR, "service_areas.csv")
SERVICE_AREA_SOURCES_CSV = os.path.join(SEED_DIR, "service_area_sources.csv")

TABS = [
    (0, "residential", "Residential electricity rate"),
    (441532959, "commercial", "Commercial electricity rate"),
    (1244383053, "industrial", "Industrial electricity rate"),
    (714337242, "generation", "Blended generation charge"),
]
CLASSES = [t[1] for t in TABS]

MONTH_NUM = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

REGION_PSGC = {
    "Region 1": ("0100000000", "Region I", "Ilocos Region", "Luzon"),
    "Region 2": ("0200000000", "Region II", "Cagayan Valley", "Luzon"),
    "Region 3": ("0300000000", "Region III", "Central Luzon", "Luzon"),
    "Region 4A": ("0400000000", "Region IV-A", "CALABARZON", "Luzon"),
    "Region 4B": ("1700000000", "Region IV-B", "MIMAROPA", "Luzon"),
    "Region 5": ("0500000000", "Region V", "Bicol Region", "Luzon"),
    "Region 6": ("0600000000", "Region VI", "Western Visayas", "Visayas"),
    "Region 7": ("0700000000", "Region VII", "Central Visayas", "Visayas"),
    "Region 8": ("0800000000", "Region VIII", "Eastern Visayas", "Visayas"),
    "Region 9": ("0900000000", "Region IX", "Zamboanga Peninsula", "Mindanao"),
    "Region 10": ("1000000000", "Region X", "Northern Mindanao", "Mindanao"),
    "Region 11": ("1100000000", "Region XI", "Davao Region", "Mindanao"),
    "Region 12": ("1200000000", "Region XII", "SOCCSKSARGEN", "Mindanao"),
    "NCR": ("1300000000", "NCR", "National Capital Region", "Luzon"),
    "CAR": ("1400000000", "CAR", "Cordillera Administrative Region", "Luzon"),
    "CARAGA": ("1600000000", "Region XIII", "Caraga", "Mindanao"),
    "NIR": ("1800000000", "NIR", "Negros Island Region", "Visayas"),
    "BARMM": ("1900000000", "BARMM", "Bangsamoro Autonomous Region in Muslim Mindanao", "Mindanao"),
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_seed_csv(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_coverage(utilities):
    """Attach service areas (provider filter) to the utility registry.

    Input is the assembled data/seed/service_areas.csv (see
    tools/build-service-areas.py): LGU/barangay rows for utilities with a sourced
    franchise footprint, and one region row for utilities that still have
    region-level coverage only. Returns (coverage_by_code, sources, stats, checks).
    """
    for path in (SERVICE_AREAS_CSV, SERVICE_AREA_SOURCES_CSV):
        if not os.path.isfile(path):
            raise SystemExit(
                "missing %s - run python3 tools/build-service-areas.py first"
                % os.path.relpath(path, ROOT))
    area_rows = read_seed_csv(SERVICE_AREAS_CSV)
    sources = read_seed_csv(SERVICE_AREA_SOURCES_CSV)
    source_ids = {row["source_id"] for row in sources}
    codes = [u["code"] for u in utilities]
    code_set = set(codes)
    valid_region_psgc = [value[0] for value in REGION_PSGC.values()]
    region_index = {psgc: i for i, psgc in enumerate(valid_region_psgc)}
    grouped = {}
    problems = []
    for row in area_rows:
        code = row.get("utility_code", "").strip()
        if code not in code_set:
            problems.append("service area row for unknown utility %r" % code)
            continue
        source_id = row.get("source_id", "").strip()
        if source_id not in source_ids:
            problems.append("service area row for %s uses unregistered source %r"
                            % (code, source_id))
        level = row.get("area_level", "").strip()
        if level not in ("lgu", "barangay", "region"):
            problems.append("bad area_level %r for %s" % (level, code))
        region_psgc = row.get("region_psgc", "").strip()
        if region_psgc not in region_index:
            problems.append("bad region_psgc %r for %s" % (region_psgc, code))
        adm3 = row.get("adm3_psgc", "").strip()
        if level in ("lgu", "barangay") and not (adm3.isdigit() and len(adm3) == 10):
            problems.append("bad adm3_psgc %r for %s" % (adm3, code))
        if level == "barangay":
            adm4 = row.get("adm4_psgc", "").strip()
            if not (adm4.isdigit() and len(adm4) == 10):
                problems.append("bad adm4_psgc %r for %s" % (adm4, code))
        grouped.setdefault(code, []).append(row)
    if problems:
        raise SystemExit("service area validation failed: " + "; ".join(problems[:20]))

    coverage = {}
    for utility in utilities:
        rows = grouped.get(utility["code"], [])
        if not rows:
            raise SystemExit("utility %s has no service area row" % utility["code"])
        lgu_rows = [row for row in rows if row["area_level"] == "lgu"]
        barangay_rows = [row for row in rows if row["area_level"] == "barangay"]
        lgus = sorted({row["adm3_psgc"] for row in lgu_rows})
        regions = sorted({row["region_psgc"] for row in rows}, key=region_index.get)
        provinces = {}
        for row in lgu_rows:
            key = row["province_psgc"]
            item = provinces.setdefault(key, {
                "psgc": key,
                "name": row["province_name"],
                "region_psgc": row["region_psgc"],
                "lgu_count": 0,
            })
            item["lgu_count"] += 1
        province_list = [provinces[key] for key in sorted(
            provinces, key=lambda key: (region_index[provinces[key]["region_psgc"]], key))]
        barangays = [{
            "adm4": row["adm4_psgc"],
            "name": row["barangay_name"],
            "lgu": row["adm3_psgc"],
            "lgu_name": row["lgu_name"],
        } for row in barangay_rows]
        barangay_provinces = sorted({row["province_name"] for row in barangay_rows})
        u_sources = sorted({row["source_id"] for row in rows})
        if lgu_rows:
            detail = "lgu"
        elif barangay_rows:
            detail = "barangay"
        else:
            detail = "region"
        notes = [row["coverage_note"] for row in rows if row.get("coverage_note")]
        coverage[utility["code"]] = {
            "detail": detail,
            "source_ids": u_sources,
            "regions": regions,
            "provinces": province_list,
            "lgus": lgus,
            "lgu_count": len(lgus),
            "barangays": barangays,
            "barangay_count": len(barangays),
            "barangay_provinces": barangay_provinces,
            "note": " · ".join(sorted(set(notes)))[:400] if notes else "",
        }

    def check(label, ok, detail=""):
        result = {"check": label, "ok": bool(ok)}
        if detail:
            result["detail"] = detail
        checks.append(result)

    checks = []
    detailed = [code for code, item in coverage.items() if item["detail"] != "region"]
    multi = sorted(code for code, item in coverage.items() if len(item["regions"]) > 1)
    meralco = coverage.get("MERALCO", {})
    check("service area rows present", len(area_rows) > 0, "%d rows" % len(area_rows))
    check("every utility has a coverage block", len(coverage) == len(utilities),
          "%d of %d" % (len(coverage), len(utilities)))
    check("utilities with LGU-level coverage", len(detailed) >= 1,
          "%d of %d" % (len(detailed), len(utilities)))
    check("MERALCO service-area LGUs (RA 12146)",
          len(meralco.get("lgus", [])) == 108, str(len(meralco.get("lgus", []))))
    check("MERALCO Pampanga barangays", meralco.get("barangay_count") == 17,
          str(meralco.get("barangay_count")))
    check("coverage regions are valid PSGC regions",
          all(set(item["regions"]) <= set(valid_region_psgc) for item in coverage.values()))
    region_mismatch = [utility for utility in utilities
                       if utility["psgc"] not in coverage[utility["code"]]["regions"]]
    undocumented = [utility["code"] for utility in region_mismatch
                    if "PSGC 3Q 2026 reassignment" not in coverage[utility["code"]]["note"]]
    check("each utility's DOE region is inside its service area, or the "
          "PSGC 3Q 2026 reassignment is documented",
          not undocumented,
          "%d documented reassignment(s)" % len(region_mismatch)
          if not undocumented else ", ".join(undocumented[:3]))
    stats = {
        "utilities_total": len(utilities),
        "utilities_with_lgu_coverage": len(detailed),
        "utilities_region_only": len(utilities) - len(detailed),
        "lgu_rows": sum(1 for row in area_rows if row["area_level"] == "lgu"),
        "barangay_rows": sum(1 for row in area_rows if row["area_level"] == "barangay"),
        "region_rows": sum(1 for row in area_rows if row["area_level"] == "region"),
        "distinct_lgus": len({row["adm3_psgc"] for row in area_rows
                              if row["area_level"] == "lgu"}),
        "multi_region_utilities": multi,
        "sources": [row["source_id"] for row in sources],
    }
    return coverage, sources, stats, checks


def fetch(gid, refresh=False):
    os.makedirs(RAW_DIR, exist_ok=True)
    dst = os.path.join(RAW_DIR, f"{gid}.csv")
    if refresh or not os.path.exists(dst):
        url = f"{SHEET_URL}/export?format=csv&gid={gid}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (open-energy-data-research)"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        if len(data) < 10_000:
            raise SystemExit(f"tab {gid}: suspiciously small response ({len(data)} bytes)")
        open(dst, "wb").write(data)
    return dst


def parse_tab(path):
    rows = list(csv.reader(io.StringIO(open(path, encoding="utf-8-sig").read())))
    header = next((r for r in rows if r and r[0].strip() == "DU Name"), None)
    if header is None:
        raise SystemExit(f"{path}: no header row")
    months = []
    for i, cell in enumerate(header):
        m = re.fullmatch(r"([A-Z][a-z]{2})-(\d{2})", cell.strip())
        if m and m.group(1) in MONTH_NUM:
            months.append((i, f"20{m.group(2)}-{MONTH_NUM[m.group(1)]:02d}"))
    if not months:
        raise SystemExit(f"{path}: no month columns")
    records, invalid = [], []
    for ri, row in enumerate(rows):
        if len(row) < 5:
            continue
        grid = row[1].strip()
        if grid not in ("ONGRID", "OFFGRID"):
            continue
        values = {}
        for ci, month in months:
            raw = row[ci].strip() if ci < len(row) else ""
            if raw == "NDA":
                values[month] = (None, "nda")
            elif raw == "":
                values[month] = (None, "missing")
            else:
                try:
                    number = float(raw.replace(",", ""))
                except ValueError:
                    invalid.append({"source_row": ri + 1, "month": month, "raw": raw})
                    values[month] = (None, "invalid")
                    continue
                values[month] = (number, "published")
        records.append({
            "name": row[0].strip(), "grid": grid, "region_label": row[2].strip(),
            "island": row[3].strip(), "du_type": row[4].strip(),
            "source_row": ri + 1, "values": values,
        })
    return months, records, invalid


def slug(name):
    s = re.sub(r"[^A-Za-z0-9]+", "-", name.upper()).strip("-")
    return re.sub(r"-+", "-", s) or "UNKNOWN"


def median(vals):
    vals = sorted(vals)
    n = len(vals)
    if not n:
        return None
    mid = n // 2
    return round(vals[mid], 2) if n % 2 else round((vals[mid - 1] + vals[mid]) / 2, 2)


def mean(vals):
    return round(sum(vals) / len(vals), 2) if vals else None


def pct_change(new, old):
    if new is None or old in (None, 0):
        return None
    return round((new - old) / old * 100, 1)


def vote(values):
    """Majority value. Returns (winner, counts, tie). winner is None on a tie."""
    counts = Counter(values)
    top, n = counts.most_common(1)[0]
    tied = len(counts) > 1 and list(counts.values()).count(n) > 1
    return (None if tied else top), counts, tied


def members_by_value(per_class):
    """per_class: list of (class, value). Returns {value: [classes]}."""
    out = {}
    for cls, value in per_class:
        out.setdefault(value, []).append(cls)
    return out


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def main():
    refresh = "--refresh" in sys.argv
    os.makedirs(SEED_DIR, exist_ok=True)

    tabs = {}
    for gid, cls, label in TABS:
        path = fetch(gid, refresh=refresh)
        months, records, invalid = parse_tab(path)
        tabs[cls] = {"gid": gid, "label": label, "path": path, "sha256": sha256(path),
                     "bytes": os.path.getsize(path), "months": months,
                     "records": records, "invalid": invalid}
        print(f"{cls:12s} gid {gid:>10}: {len(records)} DUs, {len(months)} months, "
              f"{len(invalid)} unparseable cells, sha256 {tabs[cls]['sha256'][:12]}…")

    month_names = [m for _, m in tabs["residential"]["months"]]
    for cls in CLASSES:
        if [m for _, m in tabs[cls]["months"]] != month_names:
            raise SystemExit("month columns differ between tabs")
    n_rows = len(tabs["residential"]["records"])
    if any(len(tabs[c]["records"]) != n_rows for c in CLASSES):
        raise SystemExit("DU row count differs between tabs")

    # ---- resolve the four tabs into one canonical utility row ----
    dataset_conflicts = []
    utilities_meta = []
    for i in range(n_rows):
        res = tabs["residential"]["records"][i]
        names = [(c, tabs[c]["records"][i]["name"]) for c in CLASSES]
        grids = [(c, tabs[c]["records"][i]["grid"]) for c in CLASSES]
        regions = [(c, tabs[c]["records"][i]["region_label"]) for c in CLASSES]
        types = [(c, tabs[c]["records"][i]["du_type"]) for c in CLASSES]

        canon_name = res["name"]
        variants = {c: n for c, n in names if n != canon_name}
        if variants:
            dataset_conflicts.append({
                "type": "name_variant", "source_row": res["source_row"],
                "canonical": canon_name, "variants": variants,
                "note": "same workbook row is labelled differently in another tab",
            })

        region_label, region_counts, region_tie = vote([v for _, v in regions])
        if region_tie:
            region_label = res["region_label"]
        if len(region_counts) > 1:
            dataset_conflicts.append({
                "type": "region_conflict", "source_row": res["source_row"],
                "canonical": region_label, "claims": members_by_value(regions),
                "note": "resolved by majority" if not region_tie else "unresolved tie — residential tab used",
            })
        psgc, short, region_name, island_group = REGION_PSGC[region_label]

        grid, grid_counts, grid_tie = vote([v for _, v in grids])
        if grid_tie:
            grid_value = "CONFLICT"
            grid_conflict = {"claims": members_by_value(grids)}
            dataset_conflicts.append({
                "type": "grid_conflict", "source_row": res["source_row"],
                "canonical": "CONFLICT", "claims": members_by_value(grids),
                "note": "2–2 split between ONGRID and OFFGRID — published as CONFLICT, not guessed",
            })
        else:
            grid_value = grid or res["grid"]
            grid_conflict = None
            if len(grid_counts) > 1:
                dataset_conflicts.append({
                    "type": "grid_conflict_resolved", "source_row": res["source_row"],
                    "canonical": grid_value, "claims": members_by_value(grids),
                    "note": "majority of tabs used; minority claim kept",
                })

        du_type, type_counts, _ = vote([v for _, v in types])
        du_type = du_type or res["du_type"]
        sheet_island_conflict = None
        if any(island != island_group for _, island in [(c, tabs[c]["records"][i]["island"]) for c in CLASSES]):
            sheet_island_conflict = {c: tabs[c]["records"][i]["island"] for c in CLASSES}
            dataset_conflicts.append({
                "type": "island_conflict", "source_row": res["source_row"],
                "canonical": island_group, "claims": sheet_island_conflict,
                "note": "island label contradicts the region's island group; region mapping used",
            })

        utilities_meta.append({
            "name": canon_name, "name_variants": variants, "grid": grid_value,
            "grid_conflict": grid_conflict, "region_label": region_label,
            "psgc": psgc, "region_short": short, "region_name": region_name,
            "island": island_group, "du_type": du_type, "source_row": res["source_row"],
        })

    region_counts = Counter(u["region_label"] for u in utilities_meta)
    unique_names = {u["name"] for u in utilities_meta} | {
        n for u in utilities_meta for n in u["name_variants"].values()}
    all_names = [u["name"] for u in utilities_meta]

    # ---- months, aggregates ----
    def month_total(month):
        return sum(sum(1 for r in tabs[c]["records"]
                       if r["values"].get(month, (None, None))[1] == "published")
                   for c in CLASSES)

    last_data_month = max((m for m in month_names if month_total(m)), key=month_names.index)
    idx = month_names.index(last_data_month)
    prev_month = month_names[idx - 1] if idx else None
    anchor_month = "2026-06" if "2026-06" in month_names else None

    codes, seen = [], {}
    for meta in utilities_meta:
        code = slug(meta["name"])
        if code in seen:
            raise SystemExit(f"duplicate utility slug {code}: {seen[code]} vs {meta['name']}")
        seen[code] = meta["name"]
        codes.append(code)

    utilities = []
    for i, meta in enumerate(utilities_meta):
        latest, prev, statuses = {}, {}, []
        for cls in CLASSES:
            val, status = tabs[cls]["records"][i]["values"][last_data_month]
            pval, _ = tabs[cls]["records"][i]["values"].get(prev_month, (None, "missing"))
            latest[cls] = val
            prev[cls] = pval
            statuses.append(status)
        series = [tabs["residential"]["records"][i]["values"][m][0] for m in month_names]
        res_status = tabs["residential"]["records"][i]["values"][last_data_month][1]
        if res_status == "published":
            data_status = "published"
        elif any(s == "published" for s in statuses):
            data_status = "partial"
        else:
            data_status = "nda"
        utilities.append({
            "code": codes[i], "name": meta["name"], "name_variants": meta["name_variants"],
            "type": meta["du_type"], "grid": meta["grid"], "grid_conflict": meta["grid_conflict"],
            "psgc": meta["psgc"], "region_short": meta["region_short"],
            "region_name": meta["region_name"], "island": meta["island"],
            "on_grid": (True if meta["grid"] == "ONGRID" else False if meta["grid"] == "OFFGRID" else None),
            "latest": latest, "prev": prev,
            "res_delta_pct": pct_change(latest["residential"], prev["residential"]),
            "data_status": data_status, "series": series, "source_row": meta["source_row"],
        })

    regions = []
    for label, (psgc, short, rname, island) in REGION_PSGC.items():
        members = [u for u in utilities if u["psgc"] == psgc]
        res = [u["latest"]["residential"] for u in members if u["latest"]["residential"] is not None]
        com = [u["latest"]["commercial"] for u in members if u["latest"]["commercial"] is not None]
        ind = [u["latest"]["industrial"] for u in members if u["latest"]["industrial"] is not None]
        gen = [u["latest"]["generation"] for u in members if u["latest"]["generation"] is not None]
        regions.append({
            "psgc": psgc, "name": rname, "short": short, "island": island,
            "sheet_label": label, "utility_count": len(members), "reporting": len(res),
            "res_median": median(res), "res_mean": mean(res),
            "res_min": round(min(res), 2) if res else None,
            "res_max": round(max(res), 2) if res else None,
            "com_median": median(com), "ind_median": median(ind), "gen_median": median(gen),
        })
    regions.sort(key=lambda r: r["psgc"])

    # ---- service areas (provider filter) ---------------------------------
    coverage, coverage_sources, coverage_stats, coverage_checks = load_coverage(utilities)
    for utility in utilities:
        utility["coverage"] = coverage[utility["code"]]
    print(f"\nService areas: {coverage_stats['utilities_with_lgu_coverage']} of "
          f"{coverage_stats['utilities_total']} utilities have LGU-level coverage "
          f"({coverage_stats['lgu_rows']} LGU rows, {coverage_stats['barangay_rows']} "
          f"barangay rows, {coverage_stats['region_rows']} region fallbacks)")

    def stats_for(month, cls="residential"):
        vals = [r["values"][month][0] for r in tabs[cls]["records"]
                if r["values"][month][1] == "published"]
        return {
            "month": month, "reporting": len(vals),
            "nda": sum(1 for r in tabs[cls]["records"] if r["values"][month][1] == "nda"),
            "missing": sum(1 for r in tabs[cls]["records"] if r["values"][month][1] == "missing"),
            "invalid": sum(1 for r in tabs[cls]["records"] if r["values"][month][1] == "invalid"),
            "total": len(tabs[cls]["records"]),
            "mean": mean(vals), "median": median(vals),
            "min": round(min(vals), 2) if vals else None,
            "max": round(max(vals), 2) if vals else None,
        }

    stats_last = {cls: stats_for(last_data_month, cls) for cls in CLASSES}
    stats_june = {cls: stats_for(anchor_month, cls) for cls in CLASSES} if anchor_month else {}

    def value_of(name, cls, month):
        for i, u in enumerate(utilities):
            if u["name"] == name:
                return tabs[cls]["records"][i]["values"][month][0]
        raise SystemExit(f"utility not found: {name}")

    checks = []
    def check(label, got, want):
        ok = (got == want) if not isinstance(want, float) else (
            got is not None and abs(float(got) - want) < 0.011)
        checks.append({"check": label, "ok": bool(ok), "got": got, "expected": want})
        print(f"  {'OK  ' if ok else 'FAIL'} {label}: got {got!r} expected {want!r}")

    print("\nValidation")
    check("DU row count per tab", n_rows, 141)
    check("month columns (Jan-18 → Nov-26)", len(month_names), 107)
    check("first month", month_names[0], "2018-01")
    check("latest month with published data", last_data_month, "2026-10")
    check("reference anchor month present", anchor_month, "2026-06")
    check("distinct DU/EC names across tabs (reference count 142)", len(unique_names), 142)
    check("off-grid DUs (unanimous)", sum(1 for u in utilities if u["grid"] == "OFFGRID"), 21)
    check("grid-status conflicts", sum(1 for u in utilities if u["grid"] == "CONFLICT"), 2)
    check("region utility counts sum", sum(r["utility_count"] for r in regions), 141)
    if anchor_month:
        check("Jun-2026 Meralco residential", value_of("MERALCO", "residential", anchor_month), 14.48)
        check("Jun-2026 SOLECO residential", value_of("SOLECO", "residential", anchor_month), 16.57)
        check("Jun-2026 BISELCO residential", value_of("BISELCO", "residential", anchor_month), 24.92)
        check("Jun-2026 reporting DUs", stats_june["residential"]["reporting"], 127)
        check("Jun-2026 simple mean", stats_june["residential"]["mean"], 12.29)
        check("Jun-2026 median", stats_june["residential"]["median"], 12.10)
        check("Jun-2026 max = BISELCO 24.92", stats_june["residential"]["max"], 24.92)
        may = month_names[month_names.index(anchor_month) - 1]
        change = pct_change(value_of("SOLECO", "residential", anchor_month),
                            value_of("SOLECO", "residential", may))
        checks.append({"check": "SOLECO May→Jun 2026 change ~ +32.2%", "ok": change is not None and abs(change - 32.2) <= 0.2,
                       "got": change, "expected": 32.2})
        print(f"  {'OK  ' if checks[-1]['ok'] else 'FAIL'} SOLECO May→Jun 2026 change: got {change!r} expected ~32.2")
    failed = [c for c in checks if not c["ok"]]

    # ---- write tidy CSVs -------------------------------------------------
    util_rows = []
    for u in utilities:
        def val(v):
            return "" if v is None else f"{v:.2f}"
        util_rows.append([
            u["code"], u["name"], "; ".join(f"{c}:{n}" for c, n in sorted(u["name_variants"].items())),
            u["type"], u["grid"], u["psgc"], u["region_short"], u["region_name"], u["island"],
            last_data_month, val(u["latest"]["residential"]), val(u["latest"]["commercial"]),
            val(u["latest"]["industrial"]), val(u["latest"]["generation"]),
            "" if u["res_delta_pct"] is None else f"{u['res_delta_pct']:.1f}",
            u["data_status"], SOURCE_ID, "csv_export", "verified", RETRIEVED_AT, u["source_row"],
            ";".join(u["coverage"]["source_ids"]), u["coverage"]["detail"],
            str(u["coverage"]["lgu_count"]), ";".join(u["coverage"]["regions"]),
        ])
    n = write_csv(os.path.join(SEED_DIR, "utilities.csv"),
                  ["utility_code", "utility_name", "name_variants", "du_type", "grid_connection",
                   "region_psgc", "region_short", "region_name", "island_group", "latest_month",
                   "res_latest", "com_latest", "ind_latest", "gen_latest", "res_delta_mom_pct",
                   "data_status", "source_id", "extraction_method", "confidence", "retrieved_at",
                   "source_row", "coverage_source_ids", "coverage_detail", "coverage_lgu_count",
                   "coverage_regions"], util_rows)
    print(f"\nwrote utilities.csv ({n} rows)")

    monthly_rows = []
    for cls in CLASSES:
        for i, rec in enumerate(tabs[cls]["records"]):
            for month in month_names:
                value, status = rec["values"][month]
                monthly_rows.append([codes[i], rec["name"], cls, month,
                                     "" if value is None else f"{value:.2f}", status,
                                     SOURCE_ID, "csv_export", "verified", RETRIEVED_AT])
    n = write_csv(os.path.join(SEED_DIR, "rates_monthly.csv"),
                  ["utility_code", "utility_name", "customer_class", "month", "rate_php_kwh",
                   "data_status", "source_id", "extraction_method", "confidence", "retrieved_at"],
                  monthly_rows)
    print(f"wrote rates_monthly.csv ({n} rows)")

    region_rows = [
        [r["psgc"], r["name"], r["short"], r["island"], last_data_month,
         r["utility_count"], r["reporting"],
         "" if r["res_median"] is None else f"{r['res_median']:.2f}",
         "" if r["res_mean"] is None else f"{r['res_mean']:.2f}",
         "" if r["com_median"] is None else f"{r['com_median']:.2f}",
         "" if r["ind_median"] is None else f"{r['ind_median']:.2f}",
         "" if r["gen_median"] is None else f"{r['gen_median']:.2f}",
         "" if r["res_min"] is None else f"{r['res_min']:.2f}",
         "" if r["res_max"] is None else f"{r['res_max']:.2f}",
         SOURCE_ID, RETRIEVED_AT] for r in regions]
    n = write_csv(os.path.join(SEED_DIR, "regions.csv"),
                  ["region_psgc", "region_name", "short_name", "island_group", "latest_month",
                   "utility_count", "reporting_dus", "res_median_latest", "res_mean_latest",
                   "com_median_latest", "ind_median_latest", "gen_median_latest",
                   "res_min_latest", "res_max_latest", "source_id", "retrieved_at"], region_rows)
    print(f"wrote regions.csv ({n} rows)")

    src_rows = []
    for cls in CLASSES:
        t = tabs[cls]
        src_rows.append([
            SOURCE_ID, "Department of Energy (DOE)",
            "Electricity Rates & Power Market Monitor — public Google Sheet tab",
            PAGE_URL, SHEET_URL, SHEET_ID, t["gid"], cls,
            f"{month_names[0]} to {last_data_month}", len(t["records"]) * len(t["months"]),
            RETRIEVED_AT, "csv_export", t["sha256"],
            "No explicit dataset license found on the DOE page; figures are public records. "
            "Reuse terms to be confirmed with DOE (week-1 ask).",
            f"{len(t['records'])} DU rows x {len(t['months'])} months; raw snapshot kept at "
            f"data/raw/doe-rates/{RETRIEVAL_DATE}/{t['gid']}.csv",
        ])
    n = write_csv(os.path.join(SEED_DIR, "sources.csv"),
                  ["source_id", "publisher", "dataset_title", "page_url", "sheet_url", "sheet_id",
                   "tab_gid", "customer_class", "months_covered", "cell_count", "retrieved_at",
                   "extraction_method", "sha256", "license_note", "notes"], src_rows)
    print(f"wrote sources.csv ({n} rows)")

    # ---- payload for the page -------------------------------------------
    payload = {
        "build": {"generated_at": RETRIEVED_AT, "dataset_version": RETRIEVAL_DATE,
                  "latest_month": last_data_month, "prev_month": prev_month,
                  "anchor_month": anchor_month, "months": month_names},
        "source": {"id": SOURCE_ID, "publisher": "Department of Energy (DOE)",
                   "dataset_title": "Electricity Rates & Power Market Monitor",
                   "page_url": PAGE_URL, "sheet_url": SHEET_URL, "sheet_id": SHEET_ID,
                   "retrieved_at": RETRIEVED_AT, "extraction_method": "csv_export",
                   "license": "to_confirm",
                   "tabs": [{"gid": tabs[c]["gid"], "class": c, "sha256": tabs[c]["sha256"],
                             "bytes": tabs[c]["bytes"], "rows": len(tabs[c]["records"])}
                            for c in CLASSES]},
        "stats": {"latest": stats_last, "anchor": stats_june, "coverage": coverage_stats},
        "coverage": {"stats": coverage_stats, "sources": coverage_sources,
                     "checks": coverage_checks,
                     "files": {
                         "service_areas.csv": {
                             "rows": len(read_seed_csv(SERVICE_AREAS_CSV)),
                             "bytes": os.path.getsize(SERVICE_AREAS_CSV),
                             "sha256": sha256(SERVICE_AREAS_CSV),
                         },
                         "service_area_sources.csv": {
                             "rows": len(coverage_sources),
                             "bytes": os.path.getsize(SERVICE_AREA_SOURCES_CSV),
                             "sha256": sha256(SERVICE_AREA_SOURCES_CSV),
                         },
                     }},
        "regions": regions,
        "utilities": utilities,
        "conflicts": dataset_conflicts,
        "validation": checks,
    }
    payload_path = os.path.join(SEED_DIR, "page-data.json")
    with open(payload_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"), ensure_ascii=False)
    print(f"wrote page-data.json ({os.path.getsize(payload_path) / 1024:.0f} KB)")

    validation = {
        "dataset": SOURCE_ID, "retrieved_at": RETRIEVED_AT,
        "latest_month": last_data_month, "prev_month": prev_month, "anchor_month": anchor_month,
        "checks": checks, "passed": not failed,
        "coverage_checks": coverage_checks, "coverage": coverage_stats,
        "conflicts": dataset_conflicts,
        "tabs": [{"gid": tabs[c]["gid"], "class": c, "sha256": tabs[c]["sha256"],
                  "bytes": tabs[c]["bytes"], "rows": len(tabs[c]["records"]),
                  "months": len(tabs[c]["months"]),
                  "unparseable_cells": tabs[c]["invalid"]} for c in CLASSES],
        "statistics": {"latest": stats_last, "anchor": stats_june},
        "raw_snapshots": f"data/raw/doe-rates/{RETRIEVAL_DATE}/",
    }
    with open(os.path.join(SEED_DIR, "validation.json"), "w", encoding="utf-8") as fh:
        json.dump(validation, fh, indent=1, ensure_ascii=False)
    print(f"wrote validation.json · {'ALL CHECKS PASSED' if not failed else str(len(failed)) + ' FAILURES'}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
