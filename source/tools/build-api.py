#!/usr/bin/env python3
"""Build a deterministic, static, read-only JSON API for the energy data layer.

Inputs (read-only):
  data/seed/page-data.json      canonical page payload (build/source/stats/regions/utilities/conflicts)
  data/seed/rates_monthly.csv   tidy long table: utility x customer class x month
  data/seed/utilities.csv       registry crosswalk CSV
  data/seed/regions.csv         region aggregate CSV
  data/seed/sources.csv         source registry CSV
  data/seed/validation.json     the 17 data-quality checks
  data/raw/doe-rates/<date>/    raw per-tab CSV snapshots (SHA-256 verified here)
  draft/openapi.yaml            OpenAPI 3.1 source of truth, mirrored to openapi.json

Outputs (draft/api/v1/):
  meta.json, health.json, months.json, validation.json, conflicts.json
  rates/latest.json + rates/latest/{residential,commercial,industrial,generation}.json
  utilities.json + utilities/<CODE>.json           (141 files)
  regions.json + regions/<psgc>.json               (18 files)
  changes/latest.json
  sources.json + sources/SRC-DOE-RATES.json
  openapi.json                                     (mirror of draft/openapi.yaml)
  index.json                                       (flat catalog consumed by the page builder)

Every response except index.json/openapi.json uses the BetterGov-style envelope
``{"meta": {...}, "data": ..., "next_cursor": null}``.  No value is imputed:
NDA / missing / invalid months are preserved as explicit states, never as zeros
or estimates.

Determinism: no wall-clock timestamps and no randomness are introduced here.  The
only timestamps come from the seed payload (``build.generated_at`` and
``source.retrieved_at``).  Collections are explicitly sorted, dicts are emitted
in insertion order, JSON is UTF-8 with ``indent=2`` and a trailing newline.
Running the builder twice must produce byte-identical files.

Exit codes:
  0  API written and draft/openapi.yaml is consistent with the emitted tree
  1  API written but the OpenAPI contract drifted (details printed)
  2  seed data failed an internal consistency check (nothing written)

Usage:
  python3 tools/build-api.py                  # write the API tree, verify the contract
  python3 tools/build-api.py --sync-openapi   # also refresh the two volatile spec blocks
                                             # (x-data-files, x-coverage-sources) from the seed
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import statistics
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "seed"
RAW = ROOT / "data" / "raw" / "doe-rates"
DRAFT = ROOT / "draft"
OUT = DRAFT / "api" / "v1"
OPENAPI_YAML = DRAFT / "openapi.yaml"

API_NAME = "Open Energy Data Layer — Philippine Electricity Rates Data API"
API_VERSION = "1.0"          # the JSON API major version, mirrored in OpenAPI info.version 1.0.0
DATASET_ID = "doe-electricity-rates"
RATE_CLASSES = ("residential", "commercial", "industrial", "generation")
CLASS_LABELS = {
    "residential": "Residential",
    "commercial": "Commercial",
    "industrial": "Industrial",
    "generation": "Blended generation charge",
}
DISCLAIMER_URL = "#disclaimers"

# Service-area coverage layer (v1.1). The seed can grow: rows, counts and sources
# are all derived, never hardcoded.
AREA_LEVELS = ("lgu", "barangay", "region")
AREA_LEVEL_RANK = {name: index for index, name in enumerate(AREA_LEVELS)}
RATE_DATA_FILE_NAMES = ("utilities.csv", "regions.csv", "rates_monthly.csv", "sources.csv")
SERVICE_AREA_DATA_FILE_NAMES = ("service_areas.csv", "service_area_sources.csv")
REQUIRED_SERVICE_AREA_COLUMNS = (
    "utility_code",
    "source_id",
    "area_level",
    "region_psgc",
    "coverage_note",
)

DISCLAIMERS = [
    {
        "id": "disclaimer-unofficial",
        "title": "Unofficial compilation.",
        "text": (
            "This is an independent compilation of a public DOE workbook, not an official DOE "
            "publication. Verify every figure against the source before citing or acting on it."
        ),
        "url": DISCLAIMER_URL,
    },
    {
        "id": "disclaimer-licence",
        "title": "Upstream reuse terms unconfirmed.",
        "text": (
            "The DOE workbook publishes no explicit reuse licence; terms are to be confirmed with "
            "DOE. No licence is asserted over the upstream data by this API."
        ),
        "url": DISCLAIMER_URL,
    },
    {
        "id": "disclaimer-nda",
        "title": "NDA, missing and invalid are preserved, never imputed.",
        "text": (
            "NDA is the source's \"No Data Available\"; missing is a month not yet published; "
            "invalid is a cell that failed validation. null never means zero and is never an estimate."
        ),
        "url": DISCLAIMER_URL,
    },
    {
        "id": "disclaimer-rates",
        "title": "Rates are monthly averages as published.",
        "text": (
            "Actual bills vary by consumption, charges, subsidies and timing. Figures are "
            "informational only and not financial advice."
        ),
        "url": DISCLAIMER_URL,
    },
    {
        "id": "disclaimer-coverage",
        "title": "Coverage is derived data, not a DOE rate publication.",
        "text": (
            "Service-area coverage is derived from franchise law (RA 12146 for MERALCO), the "
            "DOE workbook region column as a fallback, and, where present, the OpenStreetMap "
            "Wiki operator table (CC BY-SA 2.0) and the Wikipedia distribution-utility list "
            "(CC BY-SA 4.0). Because the layer combines CC BY-SA rows, the combined coverage "
            "layer is a CC BY-SA derivative: attribution is required and share-alike applies to "
            "redistributed coverage data. A franchise area is not verified household-level "
            "billing territory; region-level rows are a fallback, not LGU-level confirmation. "
            "Keep each source's attribution and licence."
        ),
        "url": DISCLAIMER_URL,
    },
]

LICENCE = {
    "name": "Not stated by publisher",
    "note": (
        "The DOE workbook publishes no explicit reuse licence; terms are to be confirmed with DOE. "
        "No licence is asserted over the upstream data by this API."
    ),
    "url": None,
}

STATUS_VOCABULARY = {
    "published": "The source workbook has a numeric rate for this utility, class and month.",
    "nda": "\"No Data Available\" as published by the source (an explicit NDA cell), never zero.",
    "missing": "The month column exists in the source but this cell is blank / not yet published.",
    "invalid": "A cell that failed extraction validation; no value is published for it.",
}

TAGS = [
    ("meta", "API discovery, dataset metadata, months and build health."),
    ("quality", "The source conflicts and validation checks behind the snapshot."),
    ("rates", "Monthly average rates by customer class, latest published month."),
    ("utilities", "The 141-entity utility / electric-cooperative registry and monthly series."),
    (
        "service-areas",
        "Provider service-area coverage: the LGUs/barangays each utility serves, with provenance.",
    ),
    ("regions", "PSGC regions with latest-month aggregates and member utilities."),
    ("changes", "What moved between the two most recent months."),
    ("sources", "The DOE workbook behind every published value, with per-tab checksums."),
]
TAG_ORDER = {name: i for i, (name, _) in enumerate(TAGS)}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def die(message: str) -> None:
    """Abort before writing anything: the seed data is inconsistent."""
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(2)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def round2(value: float) -> float:
    return round(value + 0.0, 2)


def round1(value: float) -> float:
    return round(value + 0.0, 1)


def row_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as fh:
        return max(0, sum(1 for _ in fh) - 1)


# Collected as files are written: "api/v1/<rel>" -> {"size_bytes", "sha256"}
FILES: dict[str, dict] = {}


def write_json(rel: str, obj) -> None:
    """Serialise deterministic JSON under draft/api/v1/ and record its checksum."""
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    path.write_bytes(raw)
    key = f"api/v1/{rel}"
    if key in FILES:
        die(f"internal error: {key} written twice")
    FILES[key] = {"size_bytes": len(raw), "sha256": sha256_bytes(raw)}


# ---------------------------------------------------------------------------
# Load the seed data
# ---------------------------------------------------------------------------

page = read_json(SEED / "page-data.json")
validation_doc = read_json(SEED / "validation.json")
rate_rows = read_csv(SEED / "rates_monthly.csv")
service_area_rows_in = read_csv(SEED / "service_areas.csv")
service_area_sources_in = read_csv(SEED / "service_area_sources.csv")
coverage_seed = page["coverage"]

build = page["build"]
source = page["source"]
utilities_in = page["utilities"]
regions_in = page["regions"]
conflicts_in = page["conflicts"]
latest_stats = page["stats"]["latest"]
anchor_stats = page["stats"]["anchor"]

GENERATED_AT = build["generated_at"]
DATASET_VERSION = build["dataset_version"]
LATEST_MONTH = build["latest_month"]
PREV_MONTH = build["prev_month"]
ANCHOR_MONTH = build["anchor_month"]
MONTHS = list(build["months"])

MONTH_INDEX = {month: i for i, month in enumerate(MONTHS)}
CSV_MONTHS = sorted({r["month"] for r in rate_rows})

SOURCE_REF = {
    "id": source["id"],
    "publisher": source["publisher"],
    "title": source["dataset_title"],
    "canonical_url": source["page_url"],
    "retrieved_at": source["retrieved_at"],
    "extraction_method": source["extraction_method"],
}

def _clean(value) -> str | None:
    """Trim a CSV cell to a string, or None when the cell is blank/absent."""
    if value is None:
        return None
    value = str(value).strip()
    return value or None


# Licence normalisation for coverage sources. Known ids get a precise licence object;
# anything else falls back to the licence string published in the seed, so a new
# source arriving in `service_area_sources.csv` needs no code change.
COVERAGE_SOURCE_LICENCES = {
    "SRC-RA-12146": {
        "short_title": "Republic Act No. 12146 (Meralco franchise)",
        "licence": {
            "name": "Public document (Philippine law)",
            "url": None,
            "note": "Works of the Government are not subject to copyright (IP Code, Sec. 176); cite the law.",
        },
    },
    "SRC-OSM-OPERATORS": {
        "short_title": "OpenStreetMap Wiki operator table",
        "licence": {
            "name": "CC BY-SA 2.0",
            "url": "https://creativecommons.org/licenses/by-sa/2.0/",
            "note": "Attribution required; share-alike applies to service-area coverage derived from this source.",
        },
    },
    "SRC-WIKI-DUS": {
        "short_title": "Wikipedia distribution-utility list",
        "licence": {
            "name": "CC BY-SA 4.0",
            "url": "https://creativecommons.org/licenses/by-sa/4.0/",
            "note": "Attribution required; share-alike applies to service-area coverage derived from this source.",
        },
    },
    "SRC-DOE-RATES": {
        "short_title": "DOE workbook region column",
        "licence": {
            "name": "Not stated by publisher",
            "url": None,
            "note": (
                "The DOE workbook states no explicit reuse licence; terms are to be confirmed "
                "with DOE. Used only as a region-level fallback for coverage."
            ),
        },
    },
}


def _coverage_licence(src: dict) -> dict:
    """A normalised licence object for one coverage source, generic over new sources."""
    known = (COVERAGE_SOURCE_LICENCES.get(src.get("source_id", "")) or {}).get("licence")
    if known:
        return dict(known)
    text = _clean(src.get("license")) or ""
    if "CC BY-SA 2.0" in text:
        return {
            "name": "CC BY-SA 2.0",
            "url": "https://creativecommons.org/licenses/by-sa/2.0/",
            "note": "Attribution required; share-alike applies to coverage derived from this source.",
        }
    if "CC BY-SA 4.0" in text:
        return {
            "name": "CC BY-SA 4.0",
            "url": "https://creativecommons.org/licenses/by-sa/4.0/",
            "note": "Attribution required; share-alike applies to coverage derived from this source.",
        }
    return {
        "name": text or "Not stated by publisher",
        "url": None,
        "note": "See the source record for the publisher's terms.",
    }


def _coverage_short_title(src: dict) -> str:
    known = COVERAGE_SOURCE_LICENCES.get(src.get("source_id", ""))
    if known:
        return known["short_title"]
    return _clean(src.get("dataset_title")) or src.get("source_id", "")


COVERAGE_SOURCES_BASE = [
    {
        "source_id": src["source_id"],
        "short_title": _coverage_short_title(src),
        "publisher": _clean(src.get("publisher")),
        "dataset_title": _clean(src.get("dataset_title")),
        "page_url": _clean(src.get("page_url")),
        "revision_id": _clean(src.get("revision_id")),
        "retrieved_at": _clean(src.get("retrieved_at")),
        "licence": _coverage_licence(src),
        "attribution": _clean(src.get("attribution")),
        "notes": _clean(src.get("notes")),
    }
    for src in coverage_seed["sources"]
]


def _coverage_credit(source: dict) -> str:
    return f"{source['short_title']} — {source['licence']['name']}"


CITATION = (
    "Open Energy Data Layer (2026). Open Energy Data Layer: Philippine electricity rates "
    "[Data set, v1.0]. Source: Department of Energy (DOE), Electricity Rates & Power Market "
    "Monitor, retrieved 2026-11-10. "
    "Service-area coverage: "
    + "; ".join(_coverage_credit(src) for src in COVERAGE_SOURCES_BASE)
    + ". No upstream licence is asserted for the DOE rate data; normalise and verify against "
    "the DOE workbook before citing."
)

ATTRIBUTION = (
    f"Source: {source['publisher']} — {source['dataset_title']}, retrieved "
    f"{source['retrieved_at']}. "
    "When republishing, credit DOE as the source and the Open Energy Data Layer for the "
    "compilation. "
    "Service-area coverage (derived data, not a DOE rate publication): "
    + "; ".join(_coverage_credit(src) for src in COVERAGE_SOURCES_BASE)
    + "."
)


def make_meta(count: int) -> dict:
    """The compact metadata block repeated in every envelope."""
    return {
        "api_version": API_VERSION,
        "dataset": DATASET_ID,
        "dataset_version": DATASET_VERSION,
        "latest_month": LATEST_MONTH,
        "generated_at": GENERATED_AT,
        "currency": "PHP",
        "unit": "PHP per kWh",
        "source": dict(SOURCE_REF),
        "attribution": ATTRIBUTION,
        "licence": dict(LICENCE),
        "disclaimers": [dict(d) for d in DISCLAIMERS],
        "service_area": {
            "detail_counts": dict(SERVICE_AREA_META["detail_counts"]),
            "sources": [
                {"source_id": src["source_id"], "licence": dict(src["licence"])}
                for src in SERVICE_AREA_META["sources"]
            ],
            "note": SERVICE_AREA_META["note"],
        },
        "count": count,
    }


def envelope(count: int, data) -> dict:
    return {"meta": make_meta(count), "data": data, "next_cursor": None}


# Data files shipped alongside the API (paths are relative to draft/).
def _data_file_record(name: str) -> dict:
    path = SEED / name
    return {
        "name": name,
        "path": f"../data/seed/{name}",
        "rows": row_count(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


DATA_FILES = [_data_file_record(name) for name in RATE_DATA_FILE_NAMES]
DATA_FILES += [_data_file_record(name) for name in SERVICE_AREA_DATA_FILE_NAMES]

# Archived raw workbook snapshots referenced by the source record.
RAW_SNAPSHOTS = [
    {
        "path": f"data/raw/doe-rates/{DATASET_VERSION}/{tab['gid']}.csv",
        "gid": tab["gid"],
        "customer_class": tab["class"],
        "bytes": tab["bytes"],
        "sha256": tab["sha256"],
    }
    for tab in source["tabs"]
]


# ---------------------------------------------------------------------------
# Derived lookups (from the tidy long table, which is the numeric source of truth)
# ---------------------------------------------------------------------------

RATE: dict[tuple[str, str, str], dict] = {}
for row in rate_rows:
    key = (row["utility_code"], row["customer_class"], row["month"])
    if key in RATE:
        die(f"duplicate rates_monthly row for {key}")
    RATE[key] = row

UTILITIES = sorted(utilities_in, key=lambda u: u["code"])
CODES = [u["code"] for u in UTILITIES]
REGIONS = sorted(regions_in, key=lambda r: r["psgc"])
UTILITY_BY_CODE = {u["code"]: u for u in UTILITIES}
REGION_BY_PSGC = {r["psgc"]: r for r in REGIONS}

REGION_CODES: dict[str, list[str]] = {r["psgc"]: [] for r in REGIONS}
for u in UTILITIES:
    REGION_CODES.setdefault(u["psgc"], []).append(u["code"])
for codes in REGION_CODES.values():
    codes.sort()


# ---------------------------------------------------------------------------
# Provider service-area coverage (v1.1) — derived from the published coverage seed
# ---------------------------------------------------------------------------

COVERAGE_STATS_IN = coverage_seed["stats"]
COVERAGE_CHECKS = list(coverage_seed["checks"])
COVERAGE_FILES_IN = coverage_seed["files"]
SERVICE_AREA_COLUMNS = list(service_area_rows_in[0].keys()) if service_area_rows_in else []


def _row_sort_key(raw: dict) -> tuple:
    return (
        AREA_LEVEL_RANK.get(raw.get("area_level") or "", len(AREA_LEVELS)),
        raw.get("region_psgc") or "",
        raw.get("province_psgc") or "",
        raw.get("adm3_psgc") or "",
        raw.get("adm4_psgc") or "",
    )


SERVICE_ROWS_BY_CODE: dict[str, list[dict]] = {code: [] for code in CODES}
for _raw in service_area_rows_in:
    _code = _raw.get("utility_code") or ""
    if _code not in SERVICE_ROWS_BY_CODE:
        SERVICE_ROWS_BY_CODE[_code] = []
    SERVICE_ROWS_BY_CODE[_code].append(_raw)
for _code in CODES:
    SERVICE_ROWS_BY_CODE[_code].sort(key=_row_sort_key)


def service_area_row(raw: dict) -> dict:
    """One published coverage row, enriched with region names; absent levels are null."""
    region = REGION_BY_PSGC.get(raw.get("region_psgc") or "")
    return {
        "utility_code": raw["utility_code"],
        "area_level": raw["area_level"],
        "source_id": raw["source_id"],
        "region_psgc": _clean(raw.get("region_psgc")),
        "region_short": region["short"] if region else None,
        "region_name": region["name"] if region else None,
        "province_psgc": _clean(raw.get("province_psgc")),
        "province_name": _clean(raw.get("province_name")),
        "adm3_psgc": _clean(raw.get("adm3_psgc")),
        "lgu_name": _clean(raw.get("lgu_name")),
        "adm4_psgc": _clean(raw.get("adm4_psgc")),
        "barangay_name": _clean(raw.get("barangay_name")),
        "coverage_note": _clean(raw.get("coverage_note")),
    }


def coverage_summary(ucov: dict) -> dict:
    """Compact coverage block used in registry rows and list endpoints."""
    return {
        "detail": ucov.get("detail"),
        "source_ids": list(ucov.get("source_ids") or []),
        "regions": list(ucov.get("regions") or []),
        "lgu_count": ucov.get("lgu_count", 0),
        "province_count": len(ucov.get("provinces") or []),
        "barangay_count": ucov.get("barangay_count", 0),
    }


def coverage_full(ucov: dict) -> dict:
    """Full coverage block published for one utility."""
    return {
        **coverage_summary(ucov),
        "provinces": [dict(province) for province in (ucov.get("provinces") or [])],
        "lgus": list(ucov.get("lgus") or []),
        "barangays": [dict(barangay) for barangay in (ucov.get("barangays") or [])],
        "barangay_provinces": list(ucov.get("barangay_provinces") or []),
        "note": _clean(ucov.get("note")),
    }


COVERAGE_DETAIL_COUNTS = {"total": len(UTILITIES), "lgu": 0, "barangay": 0, "region": 0}
for _u in UTILITIES:
    _detail = (_u.get("coverage") or {}).get("detail")
    if _detail in COVERAGE_DETAIL_COUNTS:
        COVERAGE_DETAIL_COUNTS[_detail] += 1
    else:
        COVERAGE_DETAIL_COUNTS[_detail] = 1  # surfaced by the consistency checks below

ROWS_BY_LEVEL = {
    level: sum(1 for row in service_area_rows_in if (row.get("area_level") or "") == level)
    for level in AREA_LEVELS
}
DISTINCT_LGUS = sorted(
    {
        _clean(row.get("adm3_psgc"))
        for row in service_area_rows_in
        if row.get("area_level") == "lgu" and _clean(row.get("adm3_psgc"))
    }
)


def _coverage_usage(source_id: str) -> dict:
    rows = [row for row in service_area_rows_in if row.get("source_id") == source_id]
    by_level = {
        level: sum(1 for row in rows if (row.get("area_level") or "") == level)
        for level in AREA_LEVELS
    }
    return {
        "rows": len(rows),
        "utilities": len({row.get("utility_code") for row in rows}),
        "rows_by_area_level": {level: count for level, count in by_level.items() if count},
    }


COVERAGE_SOURCES = [
    {**src, "used_for": _coverage_usage(src["source_id"])} for src in COVERAGE_SOURCES_BASE
]

X_COVERAGE_SOURCES = [
    {
        "source_id": src["source_id"],
        "publisher": src["publisher"],
        "short_title": src["short_title"],
        "dataset_title": src["dataset_title"],
        "page_url": src["page_url"],
        "revision_id": src["revision_id"],
        "retrieved_at": src["retrieved_at"],
        "licence": dict(src["licence"]),
        "attribution": src["attribution"],
    }
    for src in COVERAGE_SOURCES
]

COVERAGE_STATS = dict(COVERAGE_STATS_IN)
COVERAGE_STATS["multi_region_utilities"] = sorted(
    {
        _u["code"]
        for _u in UTILITIES
        if len({region for region in ((_u.get("coverage") or {}).get("regions") or [])}) > 1
    }
)

SERVICE_AREA_META = {
    "detail_counts": dict(COVERAGE_DETAIL_COUNTS),
    "sources": [
        {
            "source_id": src["source_id"],
            "licence": {"name": src["licence"]["name"], "url": src["licence"]["url"]},
        }
        for src in COVERAGE_SOURCES
    ],
    "note": (
        "Service-area coverage is derived data, not a DOE rate publication; the combined layer "
        "is a CC BY-SA derivative (attribution + share-alike). See /v1/service-areas.json for "
        "rows, provenance and licences."
    ),
}


def status_at(code: str, cls: str, month: str) -> str:
    return RATE[(code, cls, month)]["data_status"]


def has_value(code: str, cls: str, month: str) -> bool:
    return status_at(code, cls, month) == "published"


def series_for(code: str, cls: str) -> dict:
    """One customer-class series, grouped by explicit source state."""
    published: dict[str, float] = {}
    lists = {"nda": [], "missing": [], "invalid": []}
    for month in MONTHS:
        row = RATE[(code, cls, month)]
        status = row["data_status"]
        if status == "published":
            published[month] = round2(float(row["rate_php_kwh"]))
        elif status in lists:
            lists[status].append(month)
        else:
            die(f"unknown data_status {status!r} for {code}/{cls}/{month}")
    total = sum(1 for _ in MONTHS)
    counts = {
        "published": len(published),
        "nda": len(lists["nda"]),
        "missing": len(lists["missing"]),
        "invalid": len(lists["invalid"]),
        "total": total,
    }
    if sum(counts[k] for k in ("published", "nda", "missing", "invalid")) != total:
        die(f"series states do not cover all months for {code}/{cls}")
    published_months = sorted(published)
    return {
        "unit": "PHP per kWh",
        "counts": counts,
        "first_published_month": published_months[0] if published_months else None,
        "last_published_month": published_months[-1] if published_months else None,
        "published": published,
        "nda": lists["nda"],
        "missing": lists["missing"],
        "invalid": lists["invalid"],
    }


SERIES = {(code, cls): series_for(code, cls) for code in CODES for cls in RATE_CLASSES}


def latest_status_map(code: str) -> dict:
    return {cls: status_at(code, cls, LATEST_MONTH) for cls in RATE_CLASSES}


def registry_row(u: dict) -> dict:
    """The compact registry row used by utilities.json, regions/<psgc>.json and utility detail."""
    return {
        "code": u["code"],
        "name": u["name"],
        "name_variants": u["name_variants"],
        "type": u["type"],
        "grid": u["grid"],
        "grid_conflict": u["grid_conflict"],
        "psgc": u["psgc"],
        "region_short": u["region_short"],
        "region_name": u["region_name"],
        "island": u["island"],
        "on_grid": u["on_grid"],
        "data_status": u["data_status"],
        "latest": dict(u["latest"]),
        "prev": dict(u["prev"]),
        "latest_status": latest_status_map(u["code"]),
        "res_delta_pct": u["res_delta_pct"],
        "source_row": u["source_row"],
        "coverage": coverage_summary(u.get("coverage") or {}),
    }


REGISTRY_ROWS = [registry_row(u) for u in UTILITIES]

REGION_ROW_KEYS = (
    "psgc",
    "name",
    "short",
    "island",
    "sheet_label",
    "utility_count",
    "reporting",
    "res_median",
    "res_mean",
    "res_min",
    "res_max",
    "com_median",
    "ind_median",
    "gen_median",
)
REGION_ROWS = [{key: region[key] for key in REGION_ROW_KEYS} for region in REGIONS]


# Monthly availability: per class, four arrays aligned to MONTHS.
AVAILABILITY: dict[str, dict] = {}
for cls in RATE_CLASSES:
    AVAILABILITY[cls] = {
        "published": [0] * len(MONTHS),
        "nda": [0] * len(MONTHS),
        "missing": [0] * len(MONTHS),
        "invalid": [0] * len(MONTHS),
    }
for row in rate_rows:
    slot = AVAILABILITY[row["customer_class"]][row["data_status"]]
    slot[MONTH_INDEX[row["month"]]] += 1


# Month-over-month movements between PREV_MONTH and LATEST_MONTH.
MOVEMENTS = []
AVAILABILITY_CHANGES = []
for cls in RATE_CLASSES:
    for code in CODES:
        prev_status = status_at(code, cls, PREV_MONTH)
        latest_status = status_at(code, cls, LATEST_MONTH)
        if prev_status != latest_status:
            AVAILABILITY_CHANGES.append(
                {
                    "code": code,
                    "name": UTILITY_BY_CODE[code]["name"],
                    "customer_class": cls,
                    "from": prev_status,
                    "to": latest_status,
                }
            )
        if prev_status == "published" and latest_status == "published":
            prev_value = round2(float(RATE[(code, cls, PREV_MONTH)]["rate_php_kwh"]))
            latest_value = round2(float(RATE[(code, cls, LATEST_MONTH)]["rate_php_kwh"]))
            delta = round2(latest_value - prev_value)
            MOVEMENTS.append(
                {
                    "code": code,
                    "name": UTILITY_BY_CODE[code]["name"],
                    "region_short": UTILITY_BY_CODE[code]["region_short"],
                    "customer_class": cls,
                    "from_value": prev_value,
                    "to_value": latest_value,
                    "delta_php_kwh": delta,
                    "delta_pct": round1(delta / prev_value * 100) if prev_value else None,
                }
            )

CLASS_RANK = {cls: i for i, cls in enumerate(RATE_CLASSES)}
MOVEMENTS.sort(key=lambda m: (CLASS_RANK[m["customer_class"]], -abs(m["delta_php_kwh"]), m["code"]))
AVAILABILITY_CHANGES.sort(
    key=lambda c: (CLASS_RANK[c["customer_class"]], c["code"], c["from"], c["to"])
)


# ---------------------------------------------------------------------------
# Seed consistency checks — fail loudly before writing anything if the inputs drift
# ---------------------------------------------------------------------------

checks_run = 0


def check(condition: bool, label: str) -> None:
    global checks_run
    checks_run += 1
    if not condition:
        die(f"seed consistency check failed: {label}")


check(len(rate_rows) == len(CODES) * len(RATE_CLASSES) * len(MONTHS), "long-table row count")
check(CSV_MONTHS == MONTHS, "month columns match build.months")
check(MONTHS[0] == "2018-01" and MONTHS[-1] == "2026-11", "month coverage")
check(LATEST_MONTH == "2026-10" and PREV_MONTH == "2026-09", "latest/previous month")
check(len(set(CODES)) == len(CODES) == 141, "141 unique utility codes")
check(len(REGIONS) == 18, "18 PSGC regions")
check(set(u["psgc"] for u in UTILITIES) <= set(REGION_BY_PSGC), "every utility PSGC is a known region")
check(sum(r["utility_count"] for r in REGIONS) == 141, "region utility counts sum to 141")

for code in CODES:
    check(bool(re.fullmatch(r"[A-Za-z0-9._-]+", code)), f"safe utility code {code!r}")
for region in REGIONS:
    check(bool(re.fullmatch(r"[0-9]{10}", region["psgc"])), f"PSGC shape {region['psgc']!r}")

# The payload's per-month stats for the latest and anchor months must be exactly
# reproducible from the tidy table; this is what lets the API publish both.
for month, stats in ((LATEST_MONTH, latest_stats), (ANCHOR_MONTH, anchor_stats)):
    for cls in RATE_CLASSES:
        values = [
            round2(float(RATE[(code, cls, month)]["rate_php_kwh"]))
            for code in CODES
            if has_value(code, cls, month)
        ]
        expected = stats[cls]
        check(len(values) == expected["reporting"], f"{month} {cls} reporting count")
        check(round2(statistics.mean(values)) == expected["mean"], f"{month} {cls} mean")
        check(round2(statistics.median(values)) == expected["median"], f"{month} {cls} median")
        check(min(values) == expected["min"] and max(values) == expected["max"], f"{month} {cls} range")
        check(
            [len(AVAILABILITY[cls]["published"])][0] == len(MONTHS)
            and AVAILABILITY[cls]["published"][MONTH_INDEX[month]]
            + AVAILABILITY[cls]["nda"][MONTH_INDEX[month]]
            + AVAILABILITY[cls]["missing"][MONTH_INDEX[month]]
            + AVAILABILITY[cls]["invalid"][MONTH_INDEX[month]]
            == 141,
            f"{month} {cls} availability counts sum to 141",
        )

# Payload `latest` / `prev` are the fixed LATEST_MONTH / PREV_MONTH cells.
for u in UTILITIES:
    for cls in RATE_CLASSES:
        expected_latest = (
            round2(float(RATE[(u["code"], cls, LATEST_MONTH)]["rate_php_kwh"]))
            if has_value(u["code"], cls, LATEST_MONTH)
            else None
        )
        expected_prev = (
            round2(float(RATE[(u["code"], cls, PREV_MONTH)]["rate_php_kwh"]))
            if has_value(u["code"], cls, PREV_MONTH)
            else None
        )
        check(u["latest"][cls] == expected_latest, f"{u['code']} {cls} latest value at {LATEST_MONTH}")
        check(u["prev"][cls] == expected_prev, f"{u['code']} {cls} prev value at {PREV_MONTH}")

# res_delta_pct is the percent change between the two fixed month cells.
for u in UTILITIES:
    if u["latest"]["residential"] is not None and u["prev"]["residential"] is not None:
        expected = round1(
            (u["latest"]["residential"] - u["prev"]["residential"]) / u["prev"]["residential"] * 100
        )
        check(u["res_delta_pct"] == expected, f"{u['code']} res_delta_pct")

# Region aggregates must be reproducible from the tidy table for the latest month.
for region in REGIONS:
    region_codes = REGION_CODES[region["psgc"]]
    published = {
        cls: [
            round2(float(RATE[(code, cls, LATEST_MONTH)]["rate_php_kwh"]))
            for code in region_codes
            if has_value(code, cls, LATEST_MONTH)
        ]
        for cls in RATE_CLASSES
    }
    check(len(region_codes) == region["utility_count"], f"{region['psgc']} utility_count")
    check(len(published["residential"]) == region["reporting"], f"{region['psgc']} reporting")
    check(round2(statistics.median(published["residential"])) == region["res_median"], f"{region['psgc']} res_median")  # noqa: E501
    check(round2(statistics.mean(published["residential"])) == region["res_mean"], f"{region['psgc']} res_mean")
    check(min(published["residential"]) == region["res_min"], f"{region['psgc']} res_min")
    check(max(published["residential"]) == region["res_max"], f"{region['psgc']} res_max")
    for cls, key in (("commercial", "com_median"), ("industrial", "ind_median"), ("generation", "gen_median")):
        expected = round2(statistics.median(published[cls])) if published[cls] else None
        check(expected == region[key], f"{region['psgc']} {key}")

# Source tabs: raw snapshots must hash to the tab checksums in the payload.
for tab in source["tabs"]:
    raw_path = RAW / DATASET_VERSION / f"{tab['gid']}.csv"
    if raw_path.is_file():
        check(raw_path.stat().st_size == tab["bytes"], f"raw snapshot size gid {tab['gid']}")
        check(sha256_file(raw_path) == tab["sha256"], f"raw snapshot sha256 gid {tab['gid']}")
    tab_rows = sum(1 for row in rate_rows if row["customer_class"] == tab["class"])
    check(tab_rows == tab["rows"] * len(MONTHS), f"tab row coverage {tab['class']}")

check(len(conflicts_in) == 5, "5 source conflicts recorded")
check(len(validation_doc["checks"]) == 17, "17 validation checks")

# --- service-area coverage consistency --------------------------------------
check(bool(service_area_rows_in), "service_areas.csv has rows")
check(
    set(SERVICE_AREA_COLUMNS) >= set(REQUIRED_SERVICE_AREA_COLUMNS),
    "service_areas.csv has the required columns",
)
check(
    len(COVERAGE_SOURCES_BASE) == len({src["source_id"] for src in COVERAGE_SOURCES_BASE}),
    "unique coverage source ids",
)
check(
    sum(COVERAGE_DETAIL_COUNTS[level] for level in AREA_LEVELS) == len(UTILITIES),
    "coverage detail counts cover every utility",
)
check(
    COVERAGE_DETAIL_COUNTS["lgu"] + COVERAGE_DETAIL_COUNTS["barangay"]
    == COVERAGE_STATS_IN.get("utilities_with_lgu_coverage"),
    "coverage utilities_with_lgu_coverage",
)
check(
    COVERAGE_DETAIL_COUNTS["region"] == COVERAGE_STATS_IN.get("utilities_region_only"),
    "coverage utilities_region_only",
)
for _level in AREA_LEVELS:
    check(ROWS_BY_LEVEL[_level] == COVERAGE_STATS_IN.get(f"{_level}_rows"), f"coverage {_level}_rows")
check(len(DISTINCT_LGUS) == COVERAGE_STATS_IN.get("distinct_lgus"), "coverage distinct_lgus")
check(
    COVERAGE_STATS["multi_region_utilities"]
    == sorted(COVERAGE_STATS_IN.get("multi_region_utilities") or []),
    "coverage multi_region_utilities",
)
check(
    set(COVERAGE_STATS_IN.get("sources") or [])
    == {src["source_id"] for src in COVERAGE_SOURCES_BASE},
    "coverage stats sources match source registry",
)
_ROW_SOURCE_IDS = {src["source_id"] for src in COVERAGE_SOURCES_BASE}
check(
    {row["source_id"] for row in service_area_rows_in} <= _ROW_SOURCE_IDS,
    "coverage rows reference known sources",
)

for _name in SERVICE_AREA_DATA_FILE_NAMES:
    _entry = COVERAGE_FILES_IN.get(_name)
    check(bool(_entry), f"coverage files manifest lists {_name}")
    if _entry:
        _raw_bytes = (SEED / _name).read_bytes()
        check(len(_raw_bytes) == _entry.get("bytes"), f"{_name} bytes")
        check(sha256_bytes(_raw_bytes) == _entry.get("sha256"), f"{_name} sha256")
        check(row_count(SEED / _name) == _entry.get("rows"), f"{_name} rows")

for _u in UTILITIES:
    _code = _u["code"]
    _ucov = _u.get("coverage") or {}
    _rows = SERVICE_ROWS_BY_CODE.get(_code, [])
    check(bool(_ucov), f"{_code} has a coverage block")
    check(bool(_rows), f"{_code} has service-area rows")
    _per_level = {level: 0 for level in AREA_LEVELS}
    for _raw in _rows:
        _level = _raw.get("area_level") or ""
        check(_level in _per_level, f"{_code} valid area_level {_level!r}")
        if _level in _per_level:
            _per_level[_level] += 1
        check(bool(_clean(_raw.get("region_psgc"))), f"{_code} row has region_psgc")
        check(_clean(_raw.get("source_id")) in _ROW_SOURCE_IDS, f"{_code} row source known")
        if _level in ("lgu", "barangay"):
            check(bool(_clean(_raw.get("adm3_psgc"))), f"{_code} {_level} row has adm3_psgc")
        if _level == "barangay":
            check(bool(_clean(_raw.get("adm4_psgc"))), f"{_code} barangay row has adm4_psgc")
        if _level == "region":
            check(_clean(_raw.get("region_psgc")) == _u["psgc"], f"{_code} region fallback is the DOE region")
            check(not _clean(_raw.get("adm3_psgc")), f"{_code} region row has no adm3_psgc")
    check(_per_level["lgu"] == _ucov.get("lgu_count", 0), f"{_code} lgu_count matches rows")
    check(_per_level["barangay"] == _ucov.get("barangay_count", 0), f"{_code} barangay_count matches rows")
    _detail = _ucov.get("detail")
    if _detail == "region":
        check(
            _per_level["region"] == 1 and _per_level["lgu"] == 0 and _per_level["barangay"] == 0,
            f"{_code} region fallback rows",
        )
    elif _detail == "lgu":
        check(_per_level["lgu"] >= 1 and _per_level["region"] == 0, f"{_code} LGU rows")
    elif _detail == "barangay":
        check(
            _per_level["barangay"] >= 1 and _per_level["lgu"] == 0 and _per_level["region"] == 0,
            f"{_code} barangay rows",
        )
    else:
        die(f"{_code} unknown coverage detail {_detail!r}")
    check(
        {row["region_psgc"] for row in _rows} == set(_ucov.get("regions") or []),
        f"{_code} coverage regions match rows",
    )
    check(
        {row["source_id"] for row in _rows} == set(_ucov.get("source_ids") or []),
        f"{_code} coverage sources match rows",
    )
    _lgu_rows = [row for row in _rows if row.get("area_level") == "lgu"]
    check(
        sorted(_ucov.get("lgus") or []) == sorted({_clean(row.get("adm3_psgc")) for row in _lgu_rows}),
        f"{_code} lgus match rows",
    )
    _province_codes = {
        _clean(row.get("province_psgc"))
        for row in _lgu_rows
        if _clean(row.get("province_psgc"))
    }
    check(len(_ucov.get("provinces") or []) == len(_province_codes), f"{_code} provinces match rows")
    _barangay_rows = [row for row in _rows if row.get("area_level") == "barangay"]
    check(len(_ucov.get("barangays") or []) == len(_barangay_rows), f"{_code} barangays match rows")

COVERAGE_PASSED = sum(1 for entry in COVERAGE_CHECKS if entry.get("ok"))
COVERAGE_FAILED = len(COVERAGE_CHECKS) - COVERAGE_PASSED
VALIDATION_PASSED = sum(1 for c in validation_doc["checks"] if c["ok"])
VALIDATION_FAILED = len(validation_doc["checks"]) - VALIDATION_PASSED
HEALTH_STATUS = "ok" if (VALIDATION_FAILED == 0 and COVERAGE_FAILED == 0) else "degraded"

# The full source record shared by sources.json, sources/<id>.json and meta.json.
SOURCE_RECORD = {
    "id": source["id"],
    "publisher": source["publisher"],
    "title": source["dataset_title"],
    "canonical_url": source["page_url"],
    "workbook_url": source["sheet_url"],
    "sheet_id": source["sheet_id"],
    "retrieved_at": source["retrieved_at"],
    "extraction_method": source["extraction_method"],
    "licence": dict(LICENCE),
    "tabs": [
        {
            "gid": tab["gid"],
            "customer_class": tab["class"],
            "sha256": tab["sha256"],
            "bytes": tab["bytes"],
            "rows": tab["rows"],
        }
        for tab in source["tabs"]
    ],
    "raw_snapshots": RAW_SNAPSHOTS,
    "coverage": {
        "months": f"{MONTHS[0]} to {MONTHS[-1]}",
        "month_columns": len(MONTHS),
        "utility_rows": len(CODES),
        "latest_published_month": LATEST_MONTH,
        "latest_available_month": MONTHS[-1],
    },
    "notes": [
        "The DOE page embeds a public Google Sheet (four tabs: residential, commercial, industrial, "
        "generation). Every tab was exported as CSV; the per-tab SHA-256 above is the exact bytes "
        "retrieved and kept under data/raw/doe-rates/.",
        "The source workbook has no stable dataset identifier or documented refresh calendar; this "
        "snapshot is one dated retrieval, not a live feed.",
        "The source workbook contains no explicit licence. The DOE site footer says content is in the "
        "public domain unless otherwise stated; reuse terms are to be confirmed with DOE in writing.",
    ],
}

# Re-verify the source record against the page payload (defensive against ordering bugs).
check(SOURCE_RECORD["tabs"][0]["gid"] == 0, "source tab order")
check(SOURCE_RECORD["tabs"][1]["gid"] == 441532959, "source tab order 2")


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------


def build_meta_response() -> dict:
    data = {
        "name": API_NAME,
        "description": (
            "Static, read-only JSON API over the DOE Electricity Rates & Power Market Monitor "
            "workbook: monthly average rates for residential, commercial, industrial and blended "
            "generation-charge customers across 141 distribution utilities and electric "
            "cooperatives in 18 PSGC regions, 2018-01 to 2026-10 (latest published month). It "
            "also publishes the provider service-area coverage layer (which LGUs/barangays each "
            "utility serves, with per-row source provenance). Every response states its source, "
            "licence status and disclaimers; NDA, missing and invalid source cells are preserved "
            "as explicit states and never imputed."
        ),
        "api_version": API_VERSION,
        "dataset": DATASET_ID,
        "dataset_version": DATASET_VERSION,
        "generated_at": GENERATED_AT,
        "source": SOURCE_RECORD,
        "attribution": ATTRIBUTION,
        "licence": dict(LICENCE),
        "disclaimers": [dict(d) for d in DISCLAIMERS],
        "coverage": {
            "months_total": len(MONTHS),
            "first_month": MONTHS[0],
            "last_month": MONTHS[-1],
            "latest_month": LATEST_MONTH,
            "prev_month": PREV_MONTH,
            "anchor_month": ANCHOR_MONTH,
            "utilities": len(CODES),
            "regions": len(REGIONS),
            "rate_classes": list(RATE_CLASSES),
            "rate_rows": len(rate_rows),
        },
        "units": {
            "currency": "PHP",
            "rate_unit": "PHP per kWh",
            "scale": "pesos per kilowatt-hour",
        },
        "identifiers": {
            "utility": "utility_code — the stable slug used by this dataset (e.g. MERALCO), not an official DOE/ERC id.",
            "region": "region_psgc — 10-digit PSA PSGC region code (e.g. 1300000000 for NCR).",
            "month": "YYYY-MM billing month, as labelled in the source workbook.",
        },
        "status_vocabulary": STATUS_VOCABULARY,
        "data_files": DATA_FILES,
        "raw_snapshots": RAW_SNAPSHOTS,
        "service_area": {
            "description": (
                "Provider service-area coverage for the map's provider filter: one row per "
                "utility x covered LGU; barangay-level rows where the franchise is barangay-only; "
                "and one region-level fallback row where no LGU-level service area is sourced."
            ),
            "coverage": COVERAGE_STATS,
            "detail_counts": dict(COVERAGE_DETAIL_COUNTS),
            "rows_by_area_level": ROWS_BY_LEVEL,
            "sources": COVERAGE_SOURCES,
            "checks": COVERAGE_CHECKS,
            "files": COVERAGE_FILES_IN,
            "disclaimer_id": "disclaimer-coverage",
            "notes": [
                "Coverage rows are published verbatim in data/seed/service_areas.csv: "
                "utility_code, source_id, area_level, the PSGC hierarchy and a coverage_note. "
                "Every utility has at least one row.",
                "A row is a published franchise/service area, not verified household-level "
                "billing territory. Region-level rows are an explicit fallback, not LGU-level "
                "confirmation.",
                "Multi-region utilities in this snapshot: "
                + ", ".join(COVERAGE_STATS["multi_region_utilities"])
                + ". MERALCO is the documented franchise-law case: RA 12146 Section 1 "
                "enumerates its LGUs in NCR, Region III and Region IV-A plus 17 Pampanga "
                "barangays, while the DOE workbook lists MERALCO under NCR only.",
                "Coverage sources carry their own licences (public law, CC BY-SA where the "
                "OpenStreetMap Wiki / Wikipedia tables are used, DOE terms unconfirmed for the "
                "region fallback); see service_area.sources and /v1/sources.json.",
            ],
        },
        "machine_access": {
            "catalog": "api/v1/index.json",
            "openapi_json": "api/v1/openapi.json",
            "openapi_yaml": "openapi.yaml",
            "docs": "api-docs.md",
            "data_model": "data-model.md",
        },
        "not_included": [
            "Power-plant points: data/seed/plants.csv is illustrative sample data and is not part of this API.",
            "Bill-component breakdown (generation, transmission, system loss, distribution, subsidies, "
            "FIT-All, taxes): not in the DOE workbook and not published here.",
            "No imputed, interpolated or modelled values are published; an absent value stays absent.",
            "Service-area coverage is derived data, not part of the DOE rates publication: a "
            "franchise area is not verified billing territory, and region-level rows are a "
            "fallback. See service_area and /v1/service-areas.json for provenance and licences.",
        ],
        "notes": [
            "This is a static snapshot: files are JSON documents and there is no query layer, so "
            "next_cursor is always null and there are no filter parameters.",
            "api_version is the JSON contract version; dataset_version changes with each new retrieval "
            "of the source workbook.",
            "Coverage counts (utilities_with_lgu_coverage, rows per area level) are derived from "
            "the coverage seed and re-checked at build time; the API never hardcodes them.",
        ],
    }
    return envelope(1, data)


def build_health_response() -> dict:
    data = {
        "status": HEALTH_STATUS,
        "snapshot": True,
        "dataset_version": DATASET_VERSION,
        "generated_at": GENERATED_AT,
        "source_retrieved_at": source["retrieved_at"],
        "latest_month": LATEST_MONTH,
        "prev_month": PREV_MONTH,
        "checks": {
            "validation": len(validation_doc["checks"]),
            "validation_passed": VALIDATION_PASSED,
            "validation_failed": VALIDATION_FAILED,
            "utilities": len(CODES),
            "regions": len(REGIONS),
            "months": len(MONTHS),
            "rate_rows": len(rate_rows),
            "coverage_checks": len(COVERAGE_CHECKS),
            "coverage_checks_passed": COVERAGE_PASSED,
            "coverage_checks_failed": COVERAGE_FAILED,
            "service_area_rows": len(service_area_rows_in),
            "service_area_sources": len(COVERAGE_SOURCES_BASE),
        },
        "service_area": {
            "detail_counts": dict(COVERAGE_DETAIL_COUNTS),
            "rows_by_area_level": ROWS_BY_LEVEL,
            "sources": [src["source_id"] for src in COVERAGE_SOURCES_BASE],
        },
        "notes": [
            "\"ok\" means the published snapshot is internally consistent and every recorded "
            "data-quality check (rates and coverage) passes. It is not an uptime or live-service "
            "signal.",
            "Because this is a static snapshot, health is asserted at build time: re-run "
            "tools/build-api.py to re-check, or read validation.json for the checks themselves.",
            "Coverage is derived data, not a DOE rate publication; health covers the coverage "
            "checks as well as the rate checks.",
        ],
    }
    return envelope(1, data)


def build_months_response() -> dict:
    data = {
        "months": MONTHS,
        "first_month": MONTHS[0],
        "last_month": MONTHS[-1],
        "latest_month": LATEST_MONTH,
        "prev_month": PREV_MONTH,
        "anchor_month": ANCHOR_MONTH,
        "classes": list(RATE_CLASSES),
        "availability": AVAILABILITY,
        "notes": [
            "availability.<class>.<state> are arrays of counts aligned to the months array: "
            "availability.residential.published[i] counts utilities whose residential cell for "
            "months[i] has that state.",
            "The source workbook's 2026-11 column exists but is not published yet (all cells are "
            "blank in the retrieval), so the latest published month is 2026-10.",
        ],
    }
    return envelope(len(MONTHS), data)


def build_validation_response() -> dict:
    data = {
        "dataset": validation_doc["dataset"],
        "retrieved_at": validation_doc["retrieved_at"],
        "latest_month": validation_doc["latest_month"],
        "prev_month": validation_doc["prev_month"],
        "anchor_month": validation_doc["anchor_month"],
        "summary": {
            "checks": len(validation_doc["checks"]),
            "passed": VALIDATION_PASSED,
            "failed": VALIDATION_FAILED,
        },
        "checks": validation_doc["checks"],
        "coverage_checks": validation_doc.get("coverage_checks", []),
        "coverage_summary": {
            "checks": len(COVERAGE_CHECKS),
            "passed": COVERAGE_PASSED,
            "failed": COVERAGE_FAILED,
        },
        "coverage": validation_doc.get("coverage"),
        "notes": [
            "These are the checks run at retrieval time against the source workbook (row counts, "
            "month coverage, known spot values, derived aggregates). Any failure would change "
            "health.json status to \"degraded\".",
            "coverage_checks validate the service-area layer (rows present, every utility "
            "covered, PSGC validity, LGU spot counts, DOE region inside the service area); they "
            "are separate from the rate checks.",
        ],
    }
    return envelope(len(validation_doc["checks"]), data)


def build_conflicts_response() -> dict:
    data = {
        "count": len(conflicts_in),
        "conflicts": conflicts_in,
        "notes": [
            "Every conflict is a disagreement between the source workbook's four tabs for the same "
            "utility. \"resolved by majority\" follows the tab consensus; a 2-2 split is published "
            "as grid CONFLICT rather than guessed.",
        ],
    }
    return envelope(len(conflicts_in), data)


def build_latest_rates_index() -> dict:
    data = {
        "month": LATEST_MONTH,
        "previous_month": PREV_MONTH,
        "unit": "PHP per kWh",
        "classes": {
            cls: {
                "label": CLASS_LABELS[cls],
                "file": f"api/v1/rates/latest/{cls}.json",
                "count": len(CODES),
                "size_bytes": FILES[f"api/v1/rates/latest/{cls}.json"]["size_bytes"],
                "sha256": FILES[f"api/v1/rates/latest/{cls}.json"]["sha256"],
                "stats": latest_stats[cls],
            }
            for cls in RATE_CLASSES
        },
        "notes": [
            "Each class file carries the 2026-10 cell for all 141 utilities, with the non-published "
            "states (nda, missing, invalid) explicit. For full history per utility use "
            "utilities/<CODE>.json.",
        ],
    }
    return envelope(len(RATE_CLASSES), data)


def build_latest_rate_class(cls: str) -> dict:
    rows = []
    for u in UTILITIES:
        code = u["code"]
        status = status_at(code, cls, LATEST_MONTH)
        prev_status = status_at(code, cls, PREV_MONTH)
        value = (
            round2(float(RATE[(code, cls, LATEST_MONTH)]["rate_php_kwh"])) if status == "published" else None
        )
        previous_value = (
            round2(float(RATE[(code, cls, PREV_MONTH)]["rate_php_kwh"]))
            if prev_status == "published"
            else None
        )
        change_pct = (
            round1((value - previous_value) / previous_value * 100)
            if value is not None and previous_value
            else None
        )
        rows.append(
            {
                "code": code,
                "name": u["name"],
                "region_short": u["region_short"],
                "type": u["type"],
                "grid": u["grid"],
                "value": value,
                "status": status,
                "previous_value": previous_value,
                "change_pct": change_pct,
            }
        )
    data = {
        "month": LATEST_MONTH,
        "previous_month": PREV_MONTH,
        "customer_class": cls,
        "label": CLASS_LABELS[cls],
        "unit": "PHP per kWh",
        "stats": latest_stats[cls],
        "rows": rows,
        "notes": [
            "Rows are sorted by utility_code. value is the 2026-10 cell when the source publishes "
            "one and null otherwise; null never means zero. status says why a value is absent. "
            "previous_value is the 2026-09 cell when published; change_pct is month over month "
            "on the two published cells only.",
        ],
    }
    return envelope(len(rows), data)


def build_utilities_response() -> dict:
    by_type: dict[str, int] = {}
    by_grid: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for u in UTILITIES:
        by_type[u["type"]] = by_type.get(u["type"], 0) + 1
        by_grid[u["grid"]] = by_grid.get(u["grid"], 0) + 1
        by_status[u["data_status"]] = by_status.get(u["data_status"], 0) + 1
    data = {
        "latest_month": LATEST_MONTH,
        "previous_month": PREV_MONTH,
        "counts": {
            "total": len(UTILITIES),
            "by_type": dict(sorted(by_type.items())),
            "by_grid": dict(sorted(by_grid.items())),
            "by_data_status": dict(sorted(by_status.items())),
        },
        "rows": REGISTRY_ROWS,
        "service_area": {
            "detail_counts": dict(COVERAGE_DETAIL_COUNTS),
            "rows_by_area_level": ROWS_BY_LEVEL,
            "sources": [src["source_id"] for src in COVERAGE_SOURCES_BASE],
            "note": (
                "Every row's coverage object is a compact service-area summary (detail, "
                "source_ids, regions, lgu_count, province_count, barangay_count). Full rows and "
                "provenance: /v1/service-areas/<CODE>.json."
            ),
        },
        "notes": [
            "latest / prev are the 2026-10 and 2026-09 cells. A null means the cell is not "
            "published; latest_status says whether it is nda, missing or invalid.",
            "coverage is derived data, not a DOE rate publication; see /v1/service-areas.json.",
            "data_status restates the utility's latest-month outcome: published (a residential "
            "value exists), partial (some classes published), nda (no latest-month values).",
            "Codes are this dataset's stable slugs, not official DOE/ERC/NEA identifiers; "
            "name_variants records tab labels that differ.",
        ],
    }
    return envelope(len(REGISTRY_ROWS), data)


def build_utility_response(code: str) -> dict:
    u = UTILITY_BY_CODE[code]
    data = {
        "utility": registry_row(u),
        "coverage": {
            "months_total": len(MONTHS),
            "first_month": MONTHS[0],
            "last_month": MONTHS[-1],
            "latest_month": LATEST_MONTH,
            "previous_month": PREV_MONTH,
        },
        "series": {cls: SERIES[(code, cls)] for cls in RATE_CLASSES},
        "service_area": coverage_full(u.get("coverage") or {}),
        "source": {
            "source_id": source["id"],
            "source_row": u["source_row"],
            "source_url": source["page_url"],
            "retrieved_at": source["retrieved_at"],
            "extraction_method": source["extraction_method"],
        },
        "notes": [
            "The series is grouped by explicit source state. published is month -> PHP/kWh for "
            "cells the source publishes; nda/missing/invalid list the months with those states. "
            "All four states together cover every month in coverage.months_total exactly once.",
            "NDA is the source's own \"No Data Available\" marker. No value is imputed.",
            "service_area is the full coverage block (provinces, LGUs, barangays) with its "
            "source ids; the published rows are at /v1/service-areas/<CODE>.json. Coverage is "
            "derived data, not a DOE rate publication.",
        ],
    }
    return envelope(1, data)


def build_service_areas_response() -> dict:
    data = {
        "coverage": COVERAGE_STATS,
        "detail_counts": dict(COVERAGE_DETAIL_COUNTS),
        "rows_by_area_level": ROWS_BY_LEVEL,
        "sources": COVERAGE_SOURCES,
        "utilities": [
            {
                "code": u["code"],
                "name": u["name"],
                "type": u["type"],
                "region_short": u["region_short"],
                "region_name": u["region_name"],
                "coverage": coverage_summary(u.get("coverage") or {}),
            }
            for u in UTILITIES
        ],
        "notes": [
            "One item per utility. coverage.detail says the strongest published level: lgu "
            "(LGU-level rows), barangay (barangay-level rows only) or region (region-level "
            "fallback). coverage.regions lists every PSGC region the published rows touch, so a "
            "multi-region franchise is visible even when the DOE workbook lists one region.",
            "Rows and per-row provenance: /v1/service-areas/<CODE>.json. Coverage is derived "
            "data, not a DOE rate publication; keep the per-source attribution and licence.",
        ],
    }
    return envelope(len(UTILITIES), data)


def build_service_area_response(code: str) -> dict:
    u = UTILITY_BY_CODE[code]
    ucov = u.get("coverage") or {}
    rows = [service_area_row(raw) for raw in SERVICE_ROWS_BY_CODE.get(code, [])]
    used_source_ids = set(ucov.get("source_ids") or []) | {row["source_id"] for row in rows}
    sources = [src for src in COVERAGE_SOURCES if src["source_id"] in used_source_ids]
    data = {
        "utility": {
            "code": u["code"],
            "name": u["name"],
            "type": u["type"],
            "grid": u["grid"],
            "psgc": u["psgc"],
            "region_short": u["region_short"],
            "region_name": u["region_name"],
            "data_status": u["data_status"],
        },
        "service_area": coverage_full(ucov),
        "rows": rows,
        "sources": sources,
        "notes": [
            "rows are published verbatim from data/seed/service_areas.csv (sorted LGU, then "
            "barangay, then region fallback) with the region name joined from data/seed/regions.csv. "
            "A null field means that level does not apply (e.g. adm3_psgc on a region row).",
            "A franchise/service area is not verified household-level billing territory; "
            "region-level rows are an explicit fallback. Coverage is derived data, not a DOE "
            "rate publication.",
        ],
    }
    return envelope(len(rows), data)


def build_regions_response() -> dict:
    data = {
        "latest_month": LATEST_MONTH,
        "counts": {
            "regions": len(REGIONS),
            "utilities": len(UTILITIES),
        },
        "rows": REGION_ROWS,
        "notes": [
            "reporting is the number of utilities with a published residential value in "
            f"{LATEST_MONTH}; the medians/means/ranges use published values only and exclude "
            "nda, missing and invalid cells.",
            "sheet_label is the region label as it appears in the DOE workbook; short is the "
            "public shorthand and psgc is the PSA PSGC region code.",
        ],
    }
    return envelope(len(REGION_ROWS), data)


def build_region_response(psgc: str) -> dict:
    region = REGION_BY_PSGC[psgc]
    members = []
    for code in REGION_CODES[psgc]:
        u = UTILITY_BY_CODE[code]
        members.append(
            {
                "code": code,
                "name": u["name"],
                "type": u["type"],
                "grid": u["grid"],
                "latest": dict(u["latest"]),
                "latest_status": latest_status_map(code),
                "res_delta_pct": u["res_delta_pct"],
            }
        )
    data = {
        "region": {key: region[key] for key in REGION_ROW_KEYS},
        "latest_month": LATEST_MONTH,
        "utilities": members,
        "notes": [
            "Region aggregates cover published cells only. Member utilities resolve to full "
            "monthly series at utilities/<CODE>.json.",
        ],
    }
    return envelope(len(members), data)


def build_changes_response() -> dict:
    data = {
        "from_month": PREV_MONTH,
        "to_month": LATEST_MONTH,
        "unit": "PHP per kWh",
        "counts": {
            "movements": len(MOVEMENTS),
            "availability_changes": len(AVAILABILITY_CHANGES),
        },
        "movements": MOVEMENTS,
        "availability_changes": AVAILABILITY_CHANGES,
        "notes": [
            "This is a month-over-month movement feed, not a dataset revision history: the API "
            "publishes one dated snapshot, and a new snapshot is a new dataset_version.",
            "movements lists utility/class pairs published in both months, sorted by customer "
            "class then absolute change (largest first). delta_pct is null when the previous "
            "value is zero.",
            "availability_changes records cells whose explicit state changed between the two "
            "months (e.g. published -> nda).",
        ],
    }
    return envelope(len(MOVEMENTS), data)


def build_sources_response() -> dict:
    data = {
        "count": 1,
        "sources": [SOURCE_RECORD],
        "coverage_sources": COVERAGE_SOURCES,
        "counts": {
            "rate_sources": 1,
            "coverage_sources": len(COVERAGE_SOURCES_BASE),
        },
        "notes": [
            "sources is the rate-data registry: one record, the DOE Electricity Rates & Power "
            "Market Monitor workbook. Every rate value in this API resolves to this record and "
            "to a tab SHA-256.",
            "coverage_sources is the service-area registry: the franchise law (RA 12146), the "
            "DOE workbook region column used as fallback, and any OpenStreetMap Wiki / Wikipedia "
            "tables that supplied LGU-level coverage. Each carries its own licence, attribution "
            "and used_for counts.",
            "Coverage is derived data, not a DOE rate publication; see disclaimer-coverage.",
        ],
    }
    return envelope(1, data)


def build_source_response(source_id: str) -> dict:
    data = SOURCE_RECORD
    return envelope(1, data)


# ---------------------------------------------------------------------------
# Route catalog (drives index.json and is cross-checked against OpenAPI)
# ---------------------------------------------------------------------------

ROUTES: list[dict] = []


def add_route(
    tag: str,
    path: str,
    spec_path: str,
    static_file: str,
    catalog_file: str,
    summary: str,
    description: str,
    count: int,
    file_count: int | None = None,
) -> None:
    if tag not in TAG_ORDER:
        die(f"unknown tag {tag!r}")
    ROUTES.append(
        {
            "tag": tag,
            "path": path,
            "spec_path": spec_path,
            "static_file": static_file,
            "catalog_file": catalog_file,
            "summary": summary,
            "description": description,
            "count": count,
            "file_count": file_count,
        }
    )


add_route(
    "meta",
    "/v1/meta.json",
    "/meta.json",
    "api/v1/meta.json",
    "api/v1/meta.json",
    "Dataset metadata: source, licence, coverage, status vocabulary, checksums",
    "One document with the full dataset metadata: coverage, units, identifier schemes, the "
    "status vocabulary, the source record, licence status, disclaimers, SHA-256 checksums of "
    "the four seed CSVs and links to every machine-readable artefact.",
    1,
)
add_route(
    "meta",
    "/v1/health.json",
    "/health.json",
    "api/v1/health.json",
    "api/v1/health.json",
    "Snapshot health: build identity and data-quality check results",
    "Build identity plus the result of the 17 recorded data-quality checks. \"ok\" means the "
    "snapshot is internally consistent, not that a live service is up.",
    1,
)
add_route(
    "meta",
    "/v1/months.json",
    "/months.json",
    "api/v1/months.json",
    "api/v1/months.json",
    "Month coverage 2018-01 to 2026-11 with per-class state counts",
    "The 107 source month columns, the latest published month (2026-10), and for every customer "
    "class the count of published / NDA / missing / invalid cells in each month.",
    len(MONTHS),
)
add_route(
    "quality",
    "/v1/validation.json",
    "/validation.json",
    "api/v1/validation.json",
    "api/v1/validation.json",
    "The 17 data-quality checks run against the retrieved workbook",
    "Row counts, month coverage, spot values, derived aggregates and checksum checks, as run at "
    "retrieval time. Published verbatim; any failure would set health status to degraded.",
    len(validation_doc["checks"]),
)
add_route(
    "quality",
    "/v1/conflicts.json",
    "/conflicts.json",
    "api/v1/conflicts.json",
    "api/v1/conflicts.json",
    "Source disagreements, with the resolution rule and unresolved splits",
    "Rows where the workbook's four tabs disagree: region, island-group and grid-connection "
    "conflicts, plus name variants. Resolved by majority; a 2-2 grid split is published as "
    "CONFLICT rather than guessed.",
    len(conflicts_in),
)
add_route(
    "rates",
    "/v1/rates/latest.json",
    "/rates/latest.json",
    "api/v1/rates/latest.json",
    "api/v1/rates/latest.json",
    "Index of the latest published month per customer class",
    "Points at the four per-class files for 2026-10 with their stats, sizes and checksums. Start "
    "here for a single class; use utilities/<CODE>.json for one utility's history.",
    len(RATE_CLASSES),
)
for _cls in RATE_CLASSES:
    add_route(
        "rates",
        f"/v1/rates/latest/{_cls}.json",
        f"/rates/latest/{_cls}.json",
        f"api/v1/rates/latest/{_cls}.json",
        f"api/v1/rates/latest/{_cls}.json",
        f"Latest published {_cls} rate per utility ({LATEST_MONTH})",
        f"The {LATEST_MONTH} {_cls} cell for all 141 utilities, with explicit non-published "
        "states, the previous month's value and the month-over-month change where both cells "
        "are published.",
        len(CODES),
    )
add_route(
    "utilities",
    "/v1/utilities.json",
    "/utilities.json",
    "api/v1/utilities.json",
    "api/v1/utilities.json",
    "Utility / electric-cooperative registry (141 entities)",
    "Identity, type, grid connection, PSGC region, data status and latest/previous month values "
    "for all 141 utilities. Codes discovered here resolve to utilities/<CODE>.json.",
    len(REGISTRY_ROWS),
)
add_route(
    "utilities",
    "/v1/utilities/{code}.json",
    "/utilities/{code}.json",
    "api/v1/utilities/{code}.json",
    "api/v1/utilities/MERALCO.json",
    "One utility with its full monthly series per customer class",
    "Registry record plus all four customer-class series, grouped by explicit source state "
    "(published / nda / missing / invalid) for 2018-01 to 2026-11.",
    141,
    file_count=141,
)
_SERVICE_AREA_EXAMPLE = "MERALCO" if "MERALCO" in UTILITY_BY_CODE else CODES[0]
add_route(
    "service-areas",
    "/v1/service-areas.json",
    "/service-areas.json",
    "api/v1/service-areas.json",
    "api/v1/service-areas.json",
    "Provider service-area coverage registry with source provenance",
    "One item per utility with a compact coverage summary, plus the coverage-source registry "
    "(franchise law, DOE fallback, OSM Wiki / Wikipedia tables) and the aggregate counts. This "
    "is derived data, not a DOE rate publication.",
    len(UTILITIES),
)
add_route(
    "service-areas",
    f"/v1/service-areas/{_SERVICE_AREA_EXAMPLE}.json",
    "/service-areas/{code}.json",
    "api/v1/service-areas/{code}.json",
    f"api/v1/service-areas/{_SERVICE_AREA_EXAMPLE}.json",
    "One utility's full service-area coverage rows",
    "The published coverage rows for one utility (LGU / barangay / region-fallback rows) with "
    "the PSGC hierarchy, a per-row source_id and the source records. One file per utility "
    "(api/v1/service-areas/<CODE>.json).",
    len(UTILITIES),
    file_count=len(UTILITIES),
)
add_route(
    "regions",
    "/v1/regions.json",
    "/regions.json",
    "api/v1/regions.json",
    "api/v1/regions.json",
    "18 PSGC regions with latest-month aggregates",
    "Latest-month medians, means and ranges per customer class, reporting counts, island group "
    "and the DOE workbook's region label for all 18 regions.",
    len(REGION_ROWS),
)
add_route(
    "regions",
    "/v1/regions/{psgc}.json",
    "/regions/{psgc}.json",
    "api/v1/regions/{psgc}.json",
    "api/v1/regions/1300000000.json",
    "One region plus its member utilities",
    "One region's aggregates plus every member utility with its latest-month values and states.",
    18,
    file_count=18,
)
add_route(
    "changes",
    "/v1/changes/latest.json",
    "/changes/latest.json",
    "api/v1/changes/latest.json",
    "api/v1/changes/latest.json",
    "What moved between 2026-09 and 2026-10",
    "Month-over-month movements for utility/class pairs published in both months (largest "
    "absolute change first), plus cells whose explicit state changed between the two months.",
    len(MOVEMENTS),
)
add_route(
    "sources",
    "/v1/sources.json",
    "/sources.json",
    "api/v1/sources.json",
    "api/v1/sources.json",
    "Source registry: the DOE workbook and its checksums",
    "The single upstream source record: canonical DOE URL, workbook URL and sheet id, retrieval "
    "timestamp and extraction method, per-tab SHA-256 and byte counts, archived raw snapshots, "
    "licence status and provenance notes.",
    1,
)
add_route(
    "sources",
    "/v1/sources/{source_id}.json",
    "/sources/{source_id}.json",
    "api/v1/sources/{source_id}.json",
    "api/v1/sources/SRC-DOE-RATES.json",
    "One source record",
    "The full source record for one source_id (currently SRC-DOE-RATES). Unknown ids are not "
    "served by this static snapshot. One file per source (api/v1/sources/<source_id>.json).",
    1,
    file_count=1,
)


# ---------------------------------------------------------------------------
# Write the API tree
# ---------------------------------------------------------------------------

if OUT.exists():
    resolved = OUT.resolve()
    if resolved == ROOT or ROOT not in resolved.parents:
        die(f"refusing to clear unexpected output directory: {resolved}")
    shutil.rmtree(OUT)
OUT.mkdir(parents=True, exist_ok=True)

# meta / discovery
write_json("meta.json", build_meta_response())
write_json("health.json", build_health_response())
write_json("months.json", build_months_response())
write_json("validation.json", build_validation_response())
write_json("conflicts.json", build_conflicts_response())

# rates
for cls in RATE_CLASSES:
    write_json(f"rates/latest/{cls}.json", build_latest_rate_class(cls))
write_json("rates/latest.json", build_latest_rates_index())

# utilities
for u in UTILITIES:
    write_json(f"utilities/{u['code']}.json", build_utility_response(u["code"]))
write_json("utilities.json", build_utilities_response())

# service areas (provider coverage layer)
for u in UTILITIES:
    write_json(f"service-areas/{u['code']}.json", build_service_area_response(u["code"]))
write_json("service-areas.json", build_service_areas_response())

# regions
for region in REGIONS:
    write_json(f"regions/{region['psgc']}.json", build_region_response(region["psgc"]))
write_json("regions.json", build_regions_response())

# changes and sources
write_json("changes/latest.json", build_changes_response())
write_json(f"sources/{source['id']}.json", build_source_response(source["id"]))
write_json("sources.json", build_sources_response())

# OpenAPI mirror — the YAML file stays the human-editable source of truth.
if not OPENAPI_YAML.is_file():
    die(f"missing OpenAPI source: {OPENAPI_YAML}")


def _yaml_block(key: str, value) -> str:
    dumped = yaml.safe_dump(
        {key: value},
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    )
    return dumped if dumped.endswith("\n") else dumped + "\n"


def _replace_top_level_yaml_block(text: str, key: str, replacement: str) -> str:
    lines = text.splitlines(keepends=True)
    start = None
    for index, line in enumerate(lines):
        if line.startswith(key + ":"):
            if start is not None:
                die(f"{key} appears twice in {OPENAPI_YAML}")
            start = index
    if start is None:
        die(f"{key} not found in {OPENAPI_YAML}")
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() == "":
            end += 1
            break
        if re.match(r"^[A-Za-z]", line):
            break
        end += 1
    return "".join(lines[:start]) + replacement + "".join(lines[end:])


if "--sync-openapi" in sys.argv[1:]:
    spec_text = OPENAPI_YAML.read_text(encoding="utf-8")
    spec_text = _replace_top_level_yaml_block(
        spec_text, "x-data-files", _yaml_block("x-data-files", DATA_FILES)
    )
    spec_text = _replace_top_level_yaml_block(
        spec_text, "x-coverage-sources", _yaml_block("x-coverage-sources", X_COVERAGE_SOURCES)
    )
    OPENAPI_YAML.write_text(spec_text, encoding="utf-8")
    print("synced draft/openapi.yaml: x-data-files + x-coverage-sources")

with OPENAPI_YAML.open(encoding="utf-8") as fh:
    spec = yaml.safe_load(fh)


def assert_json_types(node, where="openapi") -> None:
    """YAML dates/timestamps would not survive a JSON round-trip faithfully."""
    if isinstance(node, dict):
        for key, value in node.items():
            if not isinstance(key, str):
                die(f"{where}: non-string mapping key {key!r}")
            assert_json_types(value, f"{where}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            assert_json_types(value, f"{where}[{i}]")
    elif node is None or isinstance(node, (str, int, float, bool)):
        return
    else:
        die(f"{where}: YAML value {node!r} is not JSON-serialisable (quote dates/timestamps)")


assert_json_types(spec)
write_json("openapi.json", spec)


# ---------------------------------------------------------------------------
# index.json — flat catalog consumed by the page builder
# ---------------------------------------------------------------------------

index_endpoints = []
for route in sorted(ROUTES, key=lambda r: (TAG_ORDER[r["tag"]], r["path"])):
    record = FILES[route["catalog_file"]]
    # Templated routes (per-entity files) advertise their concrete example file in the
    # served-URL style; the path template is in file_pattern.
    display_path = (
        "/v1/" + route["catalog_file"][len("api/v1/"):]
        if route["file_count"] is not None
        else route["path"]
    )
    entry = {
        "tag": route["tag"],
        "method": "GET",
        "path": display_path,
        "file": route["catalog_file"],
        "summary": route["summary"],
        "description": route["description"],
        "count": route["count"],
        "size_bytes": record["size_bytes"],
        "sha256": record["sha256"],
    }
    if route["file_count"] is not None:
        entry["file_pattern"] = route["static_file"]
        entry["file_count"] = route["file_count"]
    index_endpoints.append(entry)

index_doc = {
    "name": API_NAME,
    "description": (
        "Machine-readable catalog of the static energy-data API: endpoints, files and checksums, "
        "source data files and disclaimers. Consumed by the page builder and by anyone who wants "
        "to discover the API without parsing the OpenAPI document."
    ),
    "api_version": API_VERSION,
    "dataset_version": DATASET_VERSION,
    "generated_at": GENERATED_AT,
    "base_url_hint": "api/v1/",
    "openapi": {"yaml": "openapi.yaml", "json": "api/v1/openapi.json"},
    "docs": {"api": "api-docs.md", "data_model": "data-model.md"},
    "source": dict(SOURCE_REF),
    "attribution": ATTRIBUTION,
    "citation": CITATION,
    "data_files": DATA_FILES,
    "disclaimers": [dict(d) for d in DISCLAIMERS],
    "counts": {
        "endpoints": len(index_endpoints),
        "data_files": len(DATA_FILES),
        "utilities": len(UTILITIES),
        "regions": len(REGIONS),
    },
    "service_area": {
        "coverage": COVERAGE_STATS,
        "detail_counts": dict(COVERAGE_DETAIL_COUNTS),
        "rows_by_area_level": ROWS_BY_LEVEL,
        "sources": [
            {
                "source_id": src["source_id"],
                "publisher": src["publisher"],
                "short_title": src["short_title"],
                "licence": dict(src["licence"]),
            }
            for src in COVERAGE_SOURCES_BASE
        ],
        "checks": {
            "checks": len(COVERAGE_CHECKS),
            "passed": COVERAGE_PASSED,
            "failed": COVERAGE_FAILED,
        },
        "files": COVERAGE_FILES_IN,
        "note": SERVICE_AREA_META["note"],
    },
    "endpoints": index_endpoints,
}
write_json("index.json", index_doc)


# ---------------------------------------------------------------------------
# Verify the OpenAPI contract against the emitted tree
# ---------------------------------------------------------------------------

problems: list[str] = []
warnings: list[str] = []


def verify_contract(spec_doc: dict) -> list[str]:
    """Hard failures for structural drift; stale volatile metadata is a warning.

    Coverage files and their SHA-256 change with every seed refresh (including the OSM
    merge), so a spec that predates a seed refresh should warn, not block the build.
    """
    found: list[str] = []
    if spec_doc.get("openapi") != "3.1.0":
        found.append(f"openapi must be '3.1.0', got {spec_doc.get('openapi')!r}")
    info = spec_doc.get("info") or {}
    if info.get("version") != "1.0.0":
        found.append(f"info.version must be '1.0.0', got {info.get('version')!r}")
    servers = spec_doc.get("servers") or []
    if [s.get("url") for s in servers] != ["api/v1"]:
        found.append(
            "servers must be exactly [{url: 'api/v1'}] (relative, no leading slash), "
            f"got {servers!r}"
        )
    tags = [t.get("name") for t in spec_doc.get("tags") or []]
    if tags != [name for name, _ in TAGS]:
        found.append(f"tags must be {[name for name, _ in TAGS]!r}, got {tags!r}")

    paths = spec_doc.get("paths") or {}
    expected_paths = {route["spec_path"] for route in ROUTES}
    missing = sorted(expected_paths - set(paths))
    extra = sorted(set(paths) - expected_paths)
    if missing:
        found.append(f"OpenAPI is missing paths for emitted files: {missing}")
    if extra:
        found.append(f"OpenAPI declares endpoints that are not emitted (no invented endpoints): {extra}")

    for route in ROUTES:
        operation = (paths.get(route["spec_path"]) or {}).get("get")
        if not operation:
            found.append(f"{route['spec_path']}: missing GET operation")
            continue
        expected_static = (
            route["catalog_file"] if route["file_count"] is not None else route["static_file"]
        )
        if operation.get("x-static-file") != expected_static:
            found.append(
                f"{route['spec_path']}: x-static-file must be {expected_static!r}, "
                f"got {operation.get('x-static-file')!r}"
            )
        if (operation.get("tags") or [None])[0] != route["tag"]:
            found.append(f"{route['spec_path']}: first tag must be {route['tag']!r}")
        if not operation.get("operationId"):
            found.append(f"{route['spec_path']}: missing operationId")
        responses = operation.get("responses") or {}
        if "200" not in responses:
            found.append(f"{route['spec_path']}: missing 200 response")

    declared_files = spec_doc.get("x-data-files")
    if not isinstance(declared_files, list):
        found.append("x-data-files must list the six seed data files")
    elif [entry.get("name") for entry in declared_files] != [entry["name"] for entry in DATA_FILES]:
        found.append("x-data-files must list the six seed data files in manifest order")
    else:
        for declared_entry, actual in zip(declared_files, DATA_FILES):
            if declared_entry.get("path") != actual["path"]:
                found.append(f"x-data-files[{actual['name']}].path must be {actual['path']!r}")
            for key in ("rows", "bytes", "sha256"):
                if declared_entry.get(key) != actual[key]:
                    warnings.append(
                        f"x-data-files[{actual['name']}].{key} is stale in draft/openapi.yaml "
                        f"(spec {declared_entry.get(key)!r} != seed {actual[key]!r}); "
                        "refresh the spec after a seed refresh"
                    )
    if spec_doc.get("x-source") != X_SOURCE:
        found.append("x-source must equal the emitted source record (id/workbook/gids/hashes/retrieved_at)")

    declared_sources = spec_doc.get("x-coverage-sources")
    if not isinstance(declared_sources, list):
        found.append("x-coverage-sources must list the coverage-source registry")
    elif [entry.get("source_id") for entry in declared_sources] != [
        entry["source_id"] for entry in X_COVERAGE_SOURCES
    ]:
        found.append(
            "x-coverage-sources must list the coverage sources in registry order "
            f"({[entry['source_id'] for entry in X_COVERAGE_SOURCES]!r})"
        )
    else:
        for declared_entry, actual in zip(declared_sources, X_COVERAGE_SOURCES):
            if declared_entry.get("licence") != actual["licence"]:
                found.append(
                    f"x-coverage-sources[{actual['source_id']}].licence must be "
                    f"{actual['licence']!r}"
                )
            for key in ("publisher", "short_title", "dataset_title", "page_url", "revision_id",
                        "retrieved_at", "attribution"):
                if declared_entry.get(key) != actual[key]:
                    warnings.append(
                        f"x-coverage-sources[{actual['source_id']}].{key} is stale in "
                        "draft/openapi.yaml; refresh the spec after a seed refresh"
                    )
    if spec_doc.get("x-static-api") != {
        "api_version": API_VERSION,
        "dataset_version": DATASET_VERSION,
        "catalog": "api/v1/index.json",
        "base_url": "api/v1",
        "note": "Static read-only snapshot: every path is a JSON file; no query parameters, no auth; next_cursor is always null.",
    }:
        found.append("x-static-api block missing or stale")

    rendered = json.dumps(spec_doc).lower()
    # The rate data must never be relicensed in the spec. Coverage sources carry their own
    # licences (public law, CC BY-SA), so only the rate-data licence statements are pinned.
    info_licence = (info.get("license") or {}).get("name", "")
    if info_licence != "Upstream data: licence not stated by publisher (no licence asserted)":
        found.append(f"info.license must keep the rate-data licence statement, got {info_licence!r}")
    if ((spec_doc.get("x-source") or {}).get("licence") or {}).get("name") != LICENCE["name"]:
        found.append("x-source.licence must keep the DOE rate-data licence status")
    for forbidden in ("openkuryente.ph", "api.openkuryente"):
        if forbidden in rendered:
            found.append(f"OpenAPI must not invent a domain; found {forbidden!r}")
    schemas = (spec_doc.get("components") or {}).get("schemas") or {}
    for schema_name in (
        "ServiceAreaMeta",
        "ServiceAreaStats",
        "CoverageSummary",
        "CoverageFull",
        "CoverageSource",
        "CoverageSourceRegistry",
        "ServiceAreaRow",
        "ServiceAreasData",
        "ServiceAreaData",
    ):
        if schema_name not in schemas:
            found.append(f"OpenAPI is missing the coverage schema {schema_name!r}")
    description = (info.get("description") or "").lower()
    for required in (
        "department of energy",
        "no authentication",
        "cors",
        "cache-control",
        "next_cursor",
        "not stated",
        "disclaimer",
        "php per kwh",
        "service area",
        "coverage",
        "cc by-sa 2.0",
        "region-level fallback",
    ):
        if required not in description:
            found.append(f"info.description must cover {required!r}")
    return found


X_SOURCE = {
    "id": source["id"],
    "publisher": source["publisher"],
    "title": source["dataset_title"],
    "canonical_url": source["page_url"],
    "workbook_url": source["sheet_url"],
    "sheet_id": source["sheet_id"],
    "retrieved_at": source["retrieved_at"],
    "extraction_method": source["extraction_method"],
    "licence": dict(LICENCE),
    "tabs": SOURCE_RECORD["tabs"],
}

problems.extend(verify_contract(spec))


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

file_count = len(FILES)
total_bytes = sum(record["size_bytes"] for record in FILES.values())
largest = sorted(FILES.items(), key=lambda item: (-item[1]["size_bytes"], item[0]))[:5]

print(f"wrote {file_count} JSON files, {total_bytes:,} bytes ({total_bytes / 1024 / 1024:.2f} MiB) "
      f"under {OUT.relative_to(ROOT)}/")
print(f"  seed consistency checks passed: {checks_run}")
print(f"  source: {source['id']} — {source['dataset_title']} (retrieved {source['retrieved_at']})")
print(f"  dataset_version {DATASET_VERSION} · latest published month {LATEST_MONTH} · "
      f"{len(CODES)} utilities · {len(REGIONS)} regions · {len(MONTHS)} months")
print(f"  data files: " + ", ".join(f"{f['name']} ({f['rows']:,} rows)" for f in DATA_FILES))
print(
    "  service areas: "
    + ", ".join(f"{level} {count:,} rows" for level, count in ROWS_BY_LEVEL.items())
    + f" · {len(COVERAGE_SOURCES_BASE)} sources"
    + " · details "
    + ", ".join(f"{level} {count}" for level, count in COVERAGE_DETAIL_COUNTS.items() if level != "total")
)
print("  largest generated files:")
for name, record in largest:
    print(f"    {name:38s} {record['size_bytes']:>9,} bytes")

if warnings:
    print(f"\nOPENAPI DRIFT WARNINGS ({len(warnings)}) — spec metadata predates a seed refresh:",
          file=sys.stderr)
    for warning in warnings:
        print(f"  - {warning}", file=sys.stderr)

if problems:
    print(f"\nOPENAPI CONTRACT DRIFT ({len(problems)} problem(s)) — draft/openapi.yaml needs updating:",
          file=sys.stderr)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    sys.exit(1)

print(f"\nOpenAPI contract consistent: {len(ROUTES)} operations, {len(spec.get('paths') or {})} paths, "
      f"{len((spec.get('components') or {}).get('schemas') or {})} schemas"
      + (f" ({len(warnings)} drift warning(s))" if warnings else ""))
print("Deterministic build: re-run to confirm byte-identical output.")
