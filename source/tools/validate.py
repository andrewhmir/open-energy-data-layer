#!/usr/bin/env python3
"""Offline production validation for the Open Energy Data Layer repository.

This tool is deliberately dependency-light (Python standard library + PyYAML for
the OpenAPI contract) and makes *no network requests*.  It validates the data
contracts, the built page, the OpenAPI document, the static JSON API and the
repository packaging, and can re-run the page builder in a throw-away copy of
the tree to prove the committed page is byte-for-byte reproducible.

Usage:
    python3 tools/validate.py                 # fast static validation
    python3 tools/validate.py --check-page    # + deterministic rebuild check
    python3 tools/validate.py --strict        # warnings are failures too
    python3 tools/validate.py --verbose       # show details for passing checks too

Exit status: 0 when every hard check passes, 1 otherwise (2 on internal error).

The checks are written against contracts (schema, counts, anchors, payload
equality), never against file hashes, so legitimate data refreshes and copy
edits keep passing.  Files that belong to other workstreams are reported as
missing until they land; the tool is safe to run while the build is in flux.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGE_REL = "draft/map-table-prototype.html"
SEED_REL = "data/seed"
API_REL = "draft/api/v1"
ASSETS_REL = "draft/assets"
BUILDER_REL = "tools/build-map-page.py"
OPENAPI_REL = "draft/openapi.yaml"

# --- expected data contracts -------------------------------------------------
EXPECTED_UTILITIES = 141
EXPECTED_REGIONS = 18
EXPECTED_RATES = 60_348          # 4 customer classes x 141 utilities x 107 months
EXPECTED_SOURCES = 4
EXPECTED_MONTHS = 107
EXPECTED_DOCS_PAGES = 21         # 20 documents + docs index (architecture guides incl.)
EXPECTED_CLASSES = ["residential", "commercial", "industrial", "generation"]
EXPECTED_TABS = {0: "residential", 441532959: "commercial",
                 1244383053: "industrial", 714337242: "generation"}
PSGC_RE = re.compile(r"^\d{10}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)$")
VERSION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

EXPECTED_CSV = {
    "utilities.csv": {
        "rows": EXPECTED_UTILITIES,
        "required": ["utility_code", "utility_name", "du_type", "grid_connection",
                     "region_psgc", "region_short", "region_name", "island_group",
                     "latest_month", "res_latest", "com_latest", "ind_latest",
                     "gen_latest", "res_delta_mom_pct", "data_status", "source_id",
                     "source_row"],
    },
    "regions.csv": {
        "rows": EXPECTED_REGIONS,
        "required": ["region_psgc", "region_name", "short_name", "island_group",
                     "utility_count", "reporting_dus", "res_median_latest",
                     "com_median_latest", "ind_median_latest", "gen_median_latest"],
    },
    "rates_monthly.csv": {
        "rows": EXPECTED_RATES,
        "required": ["utility_code", "customer_class", "month", "rate_php_kwh",
                     "data_status"],
    },
    "sources.csv": {
        "rows": EXPECTED_SOURCES,
        "required": ["source_id", "publisher", "dataset_title", "page_url",
                     "tab_gid", "customer_class", "sha256"],
    },
}

# Files that must exist in a production checkout.  Files owned by other
# workstreams are still listed: the report names them so the Lead can see
# exactly what has not landed yet.
REQUIRED_FILES = [
    (PAGE_REL, "built page"),
    (SEED_REL + "/page-data.json", "page payload"),
    (SEED_REL + "/validation.json", "validation report"),
    (SEED_REL + "/utilities.csv", "utility table"),
    (SEED_REL + "/regions.csv", "region table"),
    (SEED_REL + "/rates_monthly.csv", "monthly rates"),
    (SEED_REL + "/sources.csv", "source register"),
    (ASSETS_REL + "/geo.json", "region geometry"),
    (ASSETS_REL + "/coverage-geo.json", "coverage geometry"),
    (SEED_REL + "/service_areas.csv", "service-area table"),
    (SEED_REL + "/service_area_sources.csv", "service-area source register"),
    (ASSETS_REL + "/fonts/manifest.json", "font manifest"),
    (ASSETS_REL + "/favicon.svg", "favicon source"),
    ("draft/openapi.yaml", "OpenAPI contract"),
    ("draft/data-model.md", "data model docs"),
    ("draft/api-docs.md", "API docs content"),
    ("README.md", "repository README"),
    ("AGENTS.md", "root agent map"),
    ("tools/AGENTS.md", "tools agent map"),
    ("data/AGENTS.md", "data agent map"),
    ("draft/AGENTS.md", "draft agent map"),
    ("tests/AGENTS.md", "tests agent map"),
    ("draft/frontend.md", "frontend architecture guide"),
    ("draft/backend.md", "backend architecture guide"),
    ("draft/component-map.md", "component map & agent guide"),
    ("LICENSE", "code licence"),
    ("requirements.txt", "python requirements"),
    ("package.json", "node tooling manifest"),
    ("package-lock.json", "node dependency lockfile"),
    (".gitignore", "git ignore rules"),
    ("tools/validate.py", "this validator"),
    ("tools/build-service-areas.py", "service-area assembler"),
    ("tools/build-docs.py", "docs builder"),
    ("draft/docs/index.html", "docs landing page"),
    ("draft/docs/docs-manifest.json", "docs manifest"),
    ("tests/qa.mjs", "browser QA suite"),
    ("tests/qa-docs.mjs", "docs QA suite"),
    (".github/workflows/ci.yml", "CI workflow"),
]

SOFT_FILES = [
    (".editorconfig", "editor configuration"),
    (".gitattributes", "git attributes"),
    ("NOTICE.md", "third-party notices"),
    ("CONTRIBUTING.md", "contributor guide"),
    ("SECURITY.md", "security policy"),
    ("CHANGELOG.md", "changelog"),
    (ASSETS_REL + "/geo-sources.json", "geometry provenance"),
]

FORBIDDEN_COPY = [
    (re.compile(r"\bdraft\s+v?0\.9\.0\b", re.I), "draft version label"),
    (re.compile(r"\bdraft\s+page\b", re.I), "draft-page copy"),
    (re.compile(r"\bdraft\s+prototype\b", re.I), "draft-prototype copy"),
    (re.compile(r"\bmock\s+api\b", re.I), "mock-API copy"),
    (re.compile(r"\bsample\s+data\b", re.I), "sample-data copy"),
    (re.compile(r"\billustrative\b", re.I), "illustrative-data copy"),
    (re.compile(r"\bsynthetic\b", re.I), "synthetic-data copy"),
    (re.compile(r"\blorem\s+ipsum\b", re.I), "lorem ipsum"),
    (re.compile(r"\bTODO\b"), "TODO marker"),
    (re.compile(r"\bTBD\b"), "TBD marker"),
    (re.compile(r"\bplaceholder\b", re.I), "placeholder copy"),
]

ASSET_ATTRS = ("src", "srcset", "poster", "data-src", "data-srcset",
               "action", "formaction")
EXTERNAL_RE = re.compile(r"^(?:https?:)?//", re.I)
CSS_URL_RE = re.compile(r"url\(\s*['\"]?(?:https?:)?//", re.I)
CSS_IMPORT_RE = re.compile(r"@import\s+(?:url\(\s*)?['\"]?(?:https?:)?//", re.I)
SCRIPT_EXTERNAL_RE = re.compile(
    r"(?:fetch|importScripts|sendBeacon)\s*\(\s*['\"](?:https?:)?//"
    r"|XMLHttpRequest\(\s*\)[\s\S]{0,80}?\.open\(\s*['\"][A-Z]+['\"]\s*,\s*['\"](?:https?:)?//"
    r"|\.src\s*=\s*['\"](?:https?:)?//", re.I)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
class Report:
    def __init__(self) -> None:
        self.groups: dict[str, list[tuple[str, str, str]]] = {}
        self.counts = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}

    def add(self, group: str, status: str, name: str, detail: str = "") -> None:
        self.groups.setdefault(group, []).append((status, name, detail))
        self.counts[status] = self.counts.get(status, 0) + 1

    def ok(self, group: str, name: str, detail: str = "") -> None:
        self.add(group, "PASS", name, detail)

    def fail(self, group: str, name: str, detail: str = "") -> None:
        self.add(group, "FAIL", name, detail)

    def warn(self, group: str, name: str, detail: str = "") -> None:
        self.add(group, "WARN", name, detail)

    def skip(self, group: str, name: str, detail: str = "") -> None:
        self.add(group, "SKIP", name, detail)

    def check(self, group: str, condition: bool, name: str, detail: str = "") -> bool:
        if condition:
            self.ok(group, name, detail)
        else:
            self.fail(group, name, detail)
        return bool(condition)

    def warn_if(self, group: str, condition: bool, name: str, detail: str = "") -> bool:
        if condition:
            self.ok(group, name, detail)
        else:
            self.warn(group, name, detail)
        return bool(condition)

    @property
    def failed(self) -> int:
        return self.counts["FAIL"]

    def render(self, verbose: bool) -> list[str]:
        lines = []
        for group, entries in self.groups.items():
            lines.append("")
            lines.append(f"[{group}]")
            for status, name, detail in entries:
                if status == "PASS":
                    lines.append(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
                else:
                    lines.append(f"  {status}  {name}" + (f"  -> {detail}" if detail else ""))
        return lines


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def abspath(rel: str) -> str:
    return rel if os.path.isabs(rel) else os.path.join(ROOT, rel)


def norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def strict_json(text: str):
    def _bad(value):  # NaN / Infinity are not valid JSON
        raise ValueError(f"non-finite JSON constant {value!r}")
    return json.loads(text, parse_constant=_bad)


def load_json(report: Report, group: str, rel: str, name: str | None = None,
              required: bool = True):
    label = name or rel
    path = abspath(rel)
    if not os.path.isfile(path):
        if required:
            report.fail(group, f"{label} exists", f"missing file: {rel}")
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return strict_json(fh.read())
    except Exception as exc:  # noqa: BLE001 - report, never crash
        report.fail(group, f"{label} parses as strict JSON",
                    f"{type(exc).__name__}: {exc}")
        return None


def read_csv_contract(report: Report, group: str, rel: str):
    path = abspath(rel)
    if not os.path.isfile(path):
        report.fail(group, f"{os.path.basename(rel)} exists", f"missing file: {rel}")
        return None, []
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            fields = list(reader.fieldnames or [])
            rows = list(reader)
        return fields, rows
    except Exception as exc:  # noqa: BLE001
        report.fail(group, f"{os.path.basename(rel)} parses as CSV",
                    f"{type(exc).__name__}: {exc}")
        return None, []


def to_float(value) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def close_enough(a, b, tol: float = 0.006) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol


def format_bytes(size: int) -> str:
    return f"{size:,} bytes"


# ---------------------------------------------------------------------------
# HTML model
# ---------------------------------------------------------------------------
class PageModel(HTMLParser):
    """Collects the facts the validators need from the built page."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source
        self.ids: list[str] = []
        self.dup_ids: list[str] = []
        self.tags: list[tuple[str, dict]] = []
        self.anchors: list[dict] = []
        self.links: list[dict] = []
        self.imgs: list[dict] = []
        self.scripts: list[dict] = []
        self.styles: list[list[str]] = []
        self.svgs: list[dict] = []
        self.region_paths: list[dict] = []
        self.buttons: list[dict] = []
        self.iframes: list[dict] = []
        self.sections: list[dict] = []
        self.text_parts: list[str] = []
        self.title = ""
        self.h1s: list[str] = []
        self._skip = 0
        self._open_scripts: list[dict] = []
        self._open_styles: list[list[str]] = []
        self._caps: list[dict] = []
        self._fed = False

    # -- parser callbacks ---------------------------------------------------
    def handle_starttag(self, tag: str, attrs_list) -> None:
        attrs = {name.lower(): (value if value is not None else "")
                 for name, value in attrs_list}
        self.tags.append((tag, attrs))
        classes = attrs.get("class", "").split()
        if "id" in attrs:
            ident = attrs["id"]
            if ident in self.ids:
                self.dup_ids.append(ident)
            else:
                self.ids.append(ident)
        if tag == "a":
            self.anchors.append(attrs)
        elif tag == "link":
            self.links.append(attrs)
        elif tag == "img":
            self.imgs.append(attrs)
        elif tag == "script":
            record = {"attrs": attrs, "text": []}
            self.scripts.append(record)
            self._open_scripts.append(record)
        elif tag == "style":
            parts = []
            self.styles.append(parts)
            self._open_styles.append(parts)
        elif tag == "svg":
            self.svgs.append(attrs)
        elif tag == "path" and "region" in classes:
            self.region_paths.append(attrs)
        elif tag == "iframe":
            self.iframes.append(attrs)
        elif tag in ("section", "header", "nav", "main", "footer"):
            self.sections.append({"tag": tag, **attrs})
        elif tag == "button":
            record = {"attrs": attrs, "text": []}
            self.buttons.append(record)
            self._caps.append({"tag": "button", "record": record, "parts": []})
        if tag == "title":
            self._caps.append({"tag": "title", "record": None, "parts": []})
        elif tag == "h1":
            self._caps.append({"tag": "h1", "record": None, "parts": []})
        if tag in ("script", "style"):
            self._skip += 1

    def handle_startendtag(self, tag: str, attrs_list) -> None:
        self.handle_starttag(tag, attrs_list)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        if tag == "script" and self._open_scripts:
            self._open_scripts.pop()
        if tag == "style" and self._open_styles:
            self._open_styles.pop()
        # close capture stacks (search from the top; tolerate odd nesting)
        for index in range(len(self._caps) - 1, -1, -1):
            cap = self._caps[index]
            if cap["tag"] == tag:
                text = norm_ws("".join(cap["parts"]))
                if cap["record"] is not None:
                    cap["record"]["text"] = text
                elif tag == "title":
                    if not self.title:  # first <title> is the document title;
                        self.title = text  # later ones are inline SVG titles
                elif tag == "h1":
                    self.h1s.append(text)
                del self._caps[index]
                break

    def handle_data(self, data: str) -> None:
        if self._skip:
            if self._open_scripts:
                self._open_scripts[-1]["text"].append(data)
            if self._open_styles:
                self._open_styles[-1].append(data)
            return
        self.text_parts.append(data)
        for cap in self._caps:
            cap["parts"].append(data)

    # -- convenience --------------------------------------------------------
    def finish(self) -> "PageModel":
        if not self._fed:
            self._fed = True
            self.feed(self.source)
        self.close()
        return self

    @property
    def text(self) -> str:
        return norm_ws(" ".join(self.text_parts))

    @property
    def script_text(self) -> str:
        return "\n".join("".join(s["text"]) for s in self.scripts)

    @property
    def style_text(self) -> str:
        return "\n".join("".join(parts) for parts in self.styles)


# ---------------------------------------------------------------------------
# 1. Required files
# ---------------------------------------------------------------------------
def check_required_files(report: Report, ctx: dict) -> None:
    group = "repository files"
    for rel, label in REQUIRED_FILES:
        path = abspath(rel)
        if os.path.isfile(path):
            report.ok(group, f"{label} exists", f"{rel} ({format_bytes(os.path.getsize(path))})")
        else:
            report.fail(group, f"{label} exists", f"missing file: {rel}")
    for rel, label in SOFT_FILES:
        if os.path.isfile(abspath(rel)):
            report.ok(group, f"{label} exists (recommended)", rel)
        else:
            report.warn(group, f"{label} exists (recommended)",
                        f"missing optional file: {rel}")

    # fonts listed in the manifest must exist on disk
    manifest = load_json(report, group, ASSETS_REL + "/fonts/manifest.json",
                         "font manifest")
    if isinstance(manifest, list):
        ctx["fonts"] = manifest
        missing = []
        for face in manifest:
            file_name = face.get("file", "")
            path = os.path.join(abspath(ASSETS_REL), "fonts", file_name)
            if not file_name or not os.path.isfile(path):
                missing.append(file_name or "<no file key>")
        report.check(group, not missing, "font files from manifest exist",
                     "missing: " + ", ".join(missing) if missing else
                     f"{len(manifest)} webfont files")
    elif manifest is not None:
        report.fail(group, "font manifest is a list", f"got {type(manifest).__name__}")

    # The AGENTS.md hierarchy is the entry point for coding agents: the root map
    # must describe and point at the four per-area maps.
    root_map = abspath("AGENTS.md")
    if os.path.isfile(root_map):
        text = open(root_map, encoding="utf-8", errors="replace").read()
        report.check(group, len(text) > 1500, "root agent map is substantial",
                     f"{len(text):,} chars")
        for rel in ("tools/AGENTS.md", "data/AGENTS.md",
                    "draft/AGENTS.md", "tests/AGENTS.md"):
            report.check(group, rel in text,
                         "root agent map references " + rel,
                         "" if rel in text else "not mentioned in AGENTS.md")
        report.check(group, "draft/component-map.md" in text,
                     "root agent map references the component map",
                     "" if "draft/component-map.md" in text
                     else "not mentioned in AGENTS.md")


# ---------------------------------------------------------------------------
# 2. Seed payload (page-data.json) + validation.json
# ---------------------------------------------------------------------------
def check_payload(report: Report, ctx: dict) -> None:
    group = "seed data: page payload"
    data = load_json(report, group, SEED_REL + "/page-data.json", "page-data.json")
    if not isinstance(data, dict):
        if data is not None:
            report.fail(group, "page-data.json is an object", f"got {type(data).__name__}")
        return
    ctx["payload"] = data

    for key in ("build", "source", "stats", "regions", "utilities", "conflicts",
                "validation"):
        report.check(group, key in data, f"payload.{key} present",
                     "" if key in data else f"missing key {key!r}")
    build = data.get("build") or {}
    source = data.get("source") or {}
    regions = data.get("regions") or []
    utilities = data.get("utilities") or []
    conflicts = data.get("conflicts") or []
    validation = data.get("validation") or []

    # build block
    months = build.get("months") or []
    report.check(group, isinstance(months, list) and len(months) == EXPECTED_MONTHS,
                 f"payload has {EXPECTED_MONTHS} month columns",
                 f"got {len(months)}")
    report.check(group, bool(months) and months[0] == "2018-01",
                 "month window starts 2018-01", f"got {months[0] if months else None}")
    if months:
        bad_months = [m for m in months if not re.match(r"^\d{4}-\d{2}$", str(m))]
        report.check(group, not bad_months, "all months are YYYY-MM",
                     "bad: " + ", ".join(map(str, bad_months[:5])) if bad_months else "")
        report.check(group, months == sorted(months), "months are sorted")
        report.check(group, len(set(months)) == len(months), "months are unique")
    for key in ("latest_month", "prev_month", "anchor_month"):
        value = build.get(key)
        report.check(group, value in months, f"build.{key} is a month column",
                     f"got {value!r}")
        report.check(group, bool(ISO_RE.match(str(build.get("generated_at", "")))),
                     "build.generated_at is an ISO timestamp",
                     f"got {build.get('generated_at')!r}")
    report.check(group, bool(VERSION_RE.match(str(build.get("dataset_version", "")))),
                 "build.dataset_version is YYYY-MM-DD",
                 f"got {build.get('dataset_version')!r}")

    # source block
    tabs = source.get("tabs") or []
    report.check(group, len(tabs) == EXPECTED_SOURCES,
                 f"source has {EXPECTED_SOURCES} tabs", f"got {len(tabs)}")
    tab_gids = {}
    for tab in tabs:
        gid = tab.get("gid")
        tab_gids[gid] = tab
        report.check(group, EXPECTED_TABS.get(gid) == tab.get("class"),
                     f"tab gid {gid} class matches contract",
                     f"expected {EXPECTED_TABS.get(gid)!r}, got {tab.get('class')!r}")
        report.check(group, tab.get("rows") == EXPECTED_UTILITIES,
                     f"tab {gid} has {EXPECTED_UTILITIES} rows", f"got {tab.get('rows')}")
        report.check(group, bool(SHA256_RE.match(str(tab.get("sha256", "")))),
                     f"tab {gid} has a sha256", f"got {tab.get('sha256')!r}")
    report.check(group, bool(source.get("page_url", "").startswith("https://")),
                 "source.page_url is https")
    report.check(group, bool(ISO_RE.match(str(source.get("retrieved_at", "")))),
                 "source.retrieved_at is an ISO timestamp")

    # validation block (mirrored by validation.json)
    report.check(group, len(validation) >= 10, "payload.validation has checks",
                 f"got {len(validation)}")
    bad_checks = [c.get("check") for c in validation if not c.get("ok")]
    report.check(group, not bad_checks, "every payload.validation check is ok",
                 "failed: " + ", ".join(map(str, bad_checks[:5])) if bad_checks else "")
    report.check(group, all({"check", "ok", "got", "expected"} <= set(c)
                            for c in validation),
                 "validation checks have check/ok/got/expected fields")

    # regions block
    report.check(group, len(regions) == EXPECTED_REGIONS,
                 f"payload has {EXPECTED_REGIONS} regions", f"got {len(regions)}")
    region_codes = []
    bad_regions = []
    for region in regions:
        code = str(region.get("psgc", ""))
        region_codes.append(code)
        if not PSGC_RE.match(code) or not all(
                region.get(key) for key in ("name", "short", "island")):
            bad_regions.append(code or region.get("name"))
        if region.get("reporting") is not None and region.get("utility_count") is not None:
            if int(region["reporting"]) > int(region["utility_count"]):
                bad_regions.append(code + " (reporting > utility_count)")
    report.check(group, not bad_regions, "region records are complete with PSGC codes",
                 "bad: " + ", ".join(map(str, bad_regions[:6])) if bad_regions else "")
    report.check(group, len(set(region_codes)) == len(regions),
                 "region PSGC codes are unique")
    region_sum = sum(int(r.get("utility_count") or 0) for r in regions)
    report.check(group, region_sum == EXPECTED_UTILITIES,
                 f"region utility counts sum to {EXPECTED_UTILITIES}", f"got {region_sum}")

    # utilities block
    report.check(group, len(utilities) == EXPECTED_UTILITIES,
                 f"payload has {EXPECTED_UTILITIES} utilities", f"got {len(utilities)}")
    report.check(group, len({u.get("code") for u in utilities}) == len(utilities),
                 "utility codes are unique")
    known_regions = set(region_codes)
    bad_utils = []
    latest_idx = months.index(build["latest_month"]) if build.get("latest_month") in months else None
    for util in utilities:
        code = util.get("code")
        problems = []
        if not code:
            problems.append("no code")
        if str(util.get("psgc", "")) not in known_regions:
            problems.append("unknown region psgc")
        if util.get("type") not in ("EC", "PIOU"):
            problems.append("bad type")
        if util.get("grid") not in ("ONGRID", "OFFGRID", "CONFLICT"):
            problems.append("bad grid")
        if util.get("data_status") not in ("published", "partial", "nda"):
            problems.append("bad data_status")
        series = util.get("series")
        if not isinstance(series, list) or len(series) != len(months):
            problems.append("series length != months")
        else:
            if (util.get("grid") == "ONGRID") != (util.get("on_grid") is True) and \
                    util.get("grid") != "CONFLICT":
                problems.append("on_grid flag inconsistent")
            for value in series:
                if value is not None and not isinstance(value, (int, float)):
                    problems.append("non-numeric series value")
                    break
                if isinstance(value, (int, float)) and not (0 < value < 1000):
                    problems.append(f"implausible rate {value}")
                    break
        latest = util.get("latest") or {}
        prev = util.get("prev") or {}
        if set(latest) != set(EXPECTED_CLASSES) or set(prev) != set(EXPECTED_CLASSES):
            problems.append("latest/prev class keys")
        if latest_idx is not None and isinstance(series, list) and \
                len(series) == len(months):
            recalculated = series[latest_idx]
            reported = latest.get("residential")
            if reported is not None and not close_enough(reported, recalculated):
                problems.append("latest.residential != series[latest]")
        if problems:
            bad_utils.append(f"{code}: {', '.join(problems)}")
    report.check(group, not bad_utils, "utility records are internally consistent",
                 f"{len(bad_utils)} bad: " + "; ".join(bad_utils[:5]))

    # residential statistics must be reproducible from the series
    latest_stats = (data.get("stats") or {}).get("latest") or {}
    if latest_idx is not None and latest_stats:
        values = [u["series"][latest_idx] for u in utilities
                  if isinstance(u.get("series"), list)
                  and len(u["series"]) == len(months)
                  and u["series"][latest_idx] is not None]
        stats = latest_stats.get("residential") or {}
        report.check(group, stats.get("reporting") == len(values),
                     "latest residential reporting count reproduces",
                     f"stats {stats.get('reporting')} vs computed {len(values)}")
        if values:
            ordered = sorted(values)
            median = (ordered[(len(ordered) - 1) // 2] + ordered[len(ordered) // 2]) / 2
            mean = sum(ordered) / len(ordered)
            report.check(group, close_enough(stats.get("median"), median),
                         "latest residential median reproduces",
                         f"stats {stats.get('median')} vs computed {median:.4f}")
            report.check(group, close_enough(stats.get("mean"), mean),
                         "latest residential mean reproduces",
                         f"stats {stats.get('mean')} vs computed {mean:.4f}")
            report.check(group, close_enough(stats.get("min"), ordered[0]) and
                         close_enough(stats.get("max"), ordered[-1]),
                         "latest residential min/max reproduce",
                         f"stats {stats.get('min')}-{stats.get('max')} vs "
                         f"{ordered[0]:.2f}-{ordered[-1]:.2f}")
    for cls in EXPECTED_CLASSES:
        stats = latest_stats.get(cls) or {}
        total = sum(int(stats.get(k) or 0) for k in
                    ("reporting", "nda", "missing", "invalid"))
        report.check(group, stats.get("total") == EXPECTED_UTILITIES and
                     total == EXPECTED_UTILITIES,
                     f"latest {cls} status counts sum to {EXPECTED_UTILITIES}",
                     f"total {stats.get('total')}, sum {total}")
        report.check(group, stats.get("month") == build.get("latest_month"),
                     f"latest {cls} stats use latest_month",
                     f"got {stats.get('month')!r}")

    # conflicts
    report.check(group, len(conflicts) >= 1, "conflicts are documented",
                 f"{len(conflicts)} conflict records")
    bad_conflicts = [c for c in conflicts
                     if not ({"type", "source_row", "canonical", "note"} <= set(c))]
    report.check(group, not bad_conflicts, "conflict records are complete",
                 f"{len(bad_conflicts)} malformed")

    # -- validation.json -----------------------------------------------------
    group = "seed data: validation report"
    vj = load_json(report, group, SEED_REL + "/validation.json", "validation.json")
    if isinstance(vj, dict):
        ctx["validation_json"] = vj
        checks = vj.get("checks") or []
        report.check(group, len(checks) >= 10, "validation.json has checks",
                     f"got {len(checks)}")
        failed = [c.get("check") for c in checks if not c.get("ok")]
        report.check(group, not failed, "every validation.json check is ok",
                     "failed: " + ", ".join(map(str, failed[:6])) if failed else "")
        report.check(group, vj.get("passed") is True, "validation.json passed flag is true")
        report.check(group, vj.get("dataset") == source.get("id"),
                     "validation.json dataset matches page-data source id",
                     f"{vj.get('dataset')!r} vs {source.get('id')!r}")
        for key in ("latest_month", "prev_month", "anchor_month"):
            report.check(group, vj.get(key) == build.get(key),
                         f"validation.json {key} matches payload",
                         f"{vj.get(key)!r} vs {build.get(key)!r}")
        if checks and isinstance(validation, list) and validation:
            by_name = {c.get("check"): c for c in checks}
            mismatched = [c.get("check") for c in validation
                          if c.get("check") in by_name and
                          by_name[c["check"]].get("ok") != c.get("ok")]
            report.check(group, not mismatched,
                         "validation.json checks mirror the payload",
                         "mismatched: " + ", ".join(map(str, mismatched[:6]))
                         if mismatched else f"{len(checks)} checks")
        tabs = vj.get("tabs") or []
        report.check(group, len(tabs) == EXPECTED_SOURCES,
                     "validation.json covers all source tabs", f"got {len(tabs)}")

    # 17-fact consistency: source tabs sha256 must match sources.csv later.
    ctx["source"] = source
    ctx["source_tabs"] = {t.get("gid"): t for t in tabs}


# ---------------------------------------------------------------------------
# 3. Seed CSVs
# ---------------------------------------------------------------------------
def check_csvs(report: Report, ctx: dict) -> None:
    group = "seed data: CSV contracts"
    payload = ctx.get("payload") or {}
    build = payload.get("build") or {}
    months = build.get("months") or []
    utilities = payload.get("utilities") or []
    regions = payload.get("regions") or []
    source_tabs = ctx.get("source_tabs") or {}
    csvs = {}
    for name, spec in EXPECTED_CSV.items():
        rel = f"{SEED_REL}/{name}"
        fields, rows = read_csv_contract(report, group, rel)
        if fields is None:
            continue
        csvs[name] = rows
        report.check(group, len(rows) == spec["rows"],
                     f"{name} has {spec['rows']:,} rows", f"got {len(rows):,}")
        missing = [col for col in spec["required"] if col not in fields]
        report.check(group, not missing,
                     f"{name} has required columns",
                     "missing: " + ", ".join(missing) if missing else
                     f"{len(fields)} columns")
        report.check(group, bool(fields) and all(f.strip() for f in fields),
                     f"{name} header has no blank column names")
    ctx["csvs"] = csvs

    # utilities.csv vs payload
    util_rows = csvs.get("utilities.csv")
    if util_rows is not None and utilities:
        by_code = {row.get("utility_code"): row for row in util_rows}
        missing = [u.get("code") for u in utilities if u.get("code") not in by_code]
        report.check(group, not missing, "utilities.csv covers every payload utility",
                     "missing: " + ", ".join(map(str, missing[:5])) if missing else
                     f"{len(by_code)} utilities")
        mismatched = []
        for util in utilities:
            row = by_code.get(util.get("code"))
            if not row:
                continue
            latest = util.get("latest") or {}
            checks = [
                ("res_latest", latest.get("residential")),
                ("com_latest", latest.get("commercial")),
                ("ind_latest", latest.get("industrial")),
                ("gen_latest", latest.get("generation")),
            ]
            for column, expected in checks:
                if not close_enough(to_float(row.get(column)), expected):
                    mismatched.append(f"{util.get('code')}.{column}")
                    break
            else:
                if row.get("data_status") != util.get("data_status"):
                    mismatched.append(f"{util.get('code')}.data_status")
                elif str(row.get("source_row")) != str(util.get("source_row")):
                    mismatched.append(f"{util.get('code')}.source_row")
        report.check(group, not mismatched,
                     "utilities.csv latest values match the payload",
                     "mismatched: " + ", ".join(mismatched[:6]) if mismatched
                     else f"{len(utilities)} utilities compared")

    # regions.csv vs payload
    region_rows = csvs.get("regions.csv")
    if region_rows is not None and regions:
        by_psgc = {row.get("region_psgc"): row for row in region_rows}
        missing = [r.get("psgc") for r in regions if r.get("psgc") not in by_psgc]
        report.check(group, not missing, "regions.csv covers every payload region",
                     "missing: " + ", ".join(map(str, missing[:5])) if missing else
                     f"{len(by_psgc)} regions")
        mismatched = []
        for region in regions:
            row = by_psgc.get(region.get("psgc"))
            if not row:
                continue
            if str(row.get("utility_count")) != str(region.get("utility_count")):
                mismatched.append(region.get("psgc") + ".utility_count")
            elif str(row.get("reporting_dus")) != str(region.get("reporting")):
                mismatched.append(region.get("psgc") + ".reporting_dus")
        report.check(group, not mismatched,
                     "regions.csv counts match the payload",
                     "mismatched: " + ", ".join(mismatched[:6]) if mismatched else "")

    # rates_monthly.csv vs payload (all 60,348 cells present; residential series
    # value-by-value; latest/previous month checked for every customer class)
    rate_rows = csvs.get("rates_monthly.csv")
    if rate_rows is not None and utilities:
        by_key = {}
        duplicated = 0
        for row in rate_rows:
            key = (row.get("utility_code"), row.get("customer_class"), row.get("month"))
            if key in by_key:
                duplicated += 1
            by_key[key] = row
        report.check(group, duplicated == 0, "rates_monthly.csv has no duplicate cells",
                     f"{duplicated} duplicates")
        classes = ["residential", "commercial", "industrial", "generation"]
        latest_month = build.get("latest_month")
        prev_month = build.get("prev_month")
        missing_cells = 0
        mismatched = []
        status_mismatched = []
        for util in utilities:
            code = util.get("code")
            series = util.get("series")
            latest = util.get("latest") or {}
            prev = util.get("prev") or {}
            for cls in classes:
                for month in months:
                    if (code, cls, month) not in by_key:
                        missing_cells += 1
            if not isinstance(series, list) or len(series) != len(months):
                continue
            for index, month in enumerate(months):
                row = by_key.get((code, "residential", month))
                if row is None:
                    continue
                expected = series[index]
                csv_value = to_float(row.get("rate_php_kwh"))
                status = (row.get("data_status") or "").strip()
                if not close_enough(csv_value, expected):
                    if len(mismatched) < 6:
                        mismatched.append(
                            f"{code}/residential/{month}: csv {csv_value} vs payload {expected}")
                published = expected is not None
                if published != (status == "published"):
                    if len(status_mismatched) < 6:
                        status_mismatched.append(
                            f"{code}/residential/{month}: {status!r} vs payload {expected!r}")
            for cls in classes:
                for month, payload_value in ((latest_month, latest.get(cls)),
                                             (prev_month, prev.get(cls))):
                    row = by_key.get((code, cls, month))
                    if row is None:
                        continue
                    if not close_enough(to_float(row.get("rate_php_kwh")), payload_value):
                        if len(mismatched) < 6:
                            mismatched.append(
                                f"{code}/{cls}/{month}: csv "
                                f"{to_float(row.get('rate_php_kwh'))} vs payload {payload_value}")
        report.check(group, missing_cells == 0,
                     f"rates_monthly.csv covers all {EXPECTED_RATES:,} cells",
                     f"{missing_cells:,} missing cells")
        report.check(group, not mismatched,
                     "rates_monthly.csv values match the payload",
                     "; ".join(mismatched[:6]))
        report.check(group, not status_mismatched,
                     "rates_monthly.csv statuses match the payload series",
                     "; ".join(status_mismatched[:6]))

    # sources.csv vs payload tabs
    source_rows = csvs.get("sources.csv")
    if source_rows is not None and source_tabs:
        mismatched = []
        for row in source_rows:
            gid_value = to_float(row.get("tab_gid"))
            gid = int(gid_value) if gid_value is not None else -1
            tab = source_tabs.get(gid)
            if tab is None:
                mismatched.append(f"unknown gid {row.get('tab_gid')}")
            elif tab.get("sha256") != row.get("sha256"):
                mismatched.append(f"gid {gid} sha256")
            elif tab.get("class") != row.get("customer_class"):
                mismatched.append(f"gid {gid} class")
        report.check(group, not mismatched, "sources.csv matches the payload tabs",
                     "; ".join(mismatched[:6]) if mismatched else
                     f"{len(source_rows)} tab records")

    # plants.csv is optional seed data (plant layer not yet on the page)
    plants_path = abspath(SEED_REL + "/plants.csv")
    if os.path.isfile(plants_path):
        fields, rows = read_csv_contract(report, group, SEED_REL + "/plants.csv")
        if fields is not None:
            required = ["plant_id", "plant_name", "fuel_type", "region_code",
                        "latitude", "longitude", "capacity_mw"]
            missing = [col for col in required if col not in fields]
            report.warn_if(group, not missing, "plants.csv has the documented columns",
                           "missing: " + ", ".join(missing) if missing else
                           f"{len(rows)} plants")
            bad = [row.get("plant_id") for row in rows
                   if to_float(row.get("latitude")) is None or
                   to_float(row.get("longitude")) is None]
            report.warn_if(group, not bad, "plants.csv coordinates are numeric",
                           "bad: " + ", ".join(map(str, bad[:5])) if bad else "")
    else:
        report.skip(group, "plants.csv checks", "optional plant seed file not present")


# ---------------------------------------------------------------------------
# 4. Geometry
# ---------------------------------------------------------------------------
def check_geo(report: Report, ctx: dict) -> None:
    group = "geometry (geo.json)"
    geo = load_json(report, group, ASSETS_REL + "/geo.json", "geo.json")
    payload = ctx.get("payload") or {}
    if not isinstance(geo, dict):
        return
    ctx["geo"] = geo
    width, height = geo.get("width"), geo.get("height")
    report.check(group, isinstance(width, (int, float)) and width > 0 and
                 isinstance(height, (int, float)) and height > 0,
                 "geo.json has a positive viewBox", f"{width} x {height}")
    regions = geo.get("regions")
    report.check(group, isinstance(regions, dict), "geo.json regions is an object")
    if not isinstance(regions, dict):
        return
    report.check(group, len(regions) == EXPECTED_REGIONS,
                 f"geo.json has {EXPECTED_REGIONS} regions", f"got {len(regions)}")
    payload_codes = {str(r.get("psgc")) for r in (payload.get("regions") or [])}
    report.check(group, payload_codes == set(regions),
                 "geo region PSGC codes match the payload",
                 "only in geo: " + ", ".join(sorted(set(regions) - payload_codes)[:5]) +
                 " | only in payload: " + ", ".join(sorted(payload_codes - set(regions))[:5])
                 if payload_codes != set(regions) else f"{len(regions)} regions")
    bad = []
    for code, region in regions.items():
        problems = []
        if not PSGC_RE.match(str(code)):
            problems.append("psgc key")
        for key in ("name", "short", "full", "island", "path"):
            if not region.get(key):
                problems.append("no " + key)
        path = str(region.get("path", ""))
        if not path.startswith("M"):
            problems.append("path does not start with M")
        if "NaN" in path or "Infinity" in path:
            problems.append("non-finite path")
        if len(path) < 50:
            problems.append("suspiciously short path")
        bbox = region.get("bbox")
        if not (isinstance(bbox, list) and len(bbox) == 4 and
                all(isinstance(v, (int, float)) for v in bbox)):
            problems.append("bad bbox")
        elif isinstance(width, (int, float)) and isinstance(height, (int, float)) and \
                width > 0 and height > 0:
            x0, y0, x1, y1 = bbox
            if x0 < -5 or y0 < -5 or x1 > width + 5 or y1 > height + 5:
                problems.append("bbox outside viewBox")
        if not isinstance(region.get("label_x"), (int, float)) or \
                not isinstance(region.get("label_y"), (int, float)):
            problems.append("label coords")
        if problems:
            bad.append(f"{code}: {', '.join(problems)}")
    report.check(group, not bad, "every region has path, bbox, labels and metadata",
                 f"{len(bad)} bad: " + "; ".join(bad[:5]))

    group = "geometry (sources)"
    geo_sources = load_json(report, group, ASSETS_REL + "/geo-sources.json",
                            "geo-sources.json", required=False)
    if isinstance(geo_sources, dict):
        report.ok(group, "geo-sources.json exists")
        flattened = _walk_strings(geo_sources)
        licence = [key for key, value in flattened if
                   "licen" in key.lower() and value.strip()]
        report.check(group, bool(licence), "geometry provenance names a licence",
                     str(licence[:3]) if licence else "no licence/license field")
        sha256s = [value for _key, value in flattened
                   if isinstance(value, str) and SHA256_RE.match(value)]
        report.check(group, len(sha256s) >= 1,
                     "geometry provenance records upstream SHA-256 checksums",
                     f"{len(sha256s)} checksums")
        asset = geo_sources.get("asset")
        generated_by = geo_sources.get("generated_by")
        if generated_by:
            report.check(group, os.path.isfile(os.path.join(ROOT, generated_by)),
                         "geometry generator recorded in provenance exists",
                         str(generated_by))
        if asset:
            report.check(group, os.path.isfile(os.path.join(abspath(ASSETS_REL), asset)),
                         "geometry asset recorded in provenance exists", str(asset))
    elif geo_sources is None:
        report.warn(group, "geo-sources.json exists (recommended)",
                    "missing: draft/assets/geo-sources.json")


def _walk_strings(node, prefix=""):
    """Flatten a JSON tree to (dotted-key, string) pairs."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            found.extend(_walk_strings(value, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_walk_strings(value, f"{prefix}[{index}]"))
    elif isinstance(node, str):
        found.append((prefix, node))
    return found


# ---------------------------------------------------------------------------
# 5. Page — static contract
# ---------------------------------------------------------------------------
def extract_payload(page_text: str):
    match = re.search(r"(?:var|const|let)\s+DATA\s*=\s*", page_text)
    if not match:
        return None
    decoder = json.JSONDecoder()
    try:
        payload, _end = decoder.raw_decode(page_text[match.end():])
    except json.JSONDecodeError:
        return None
    return payload


def check_page(report: Report, ctx: dict) -> None:
    group = "page: static contract"
    page_path = abspath(PAGE_REL)
    if not os.path.isfile(page_path):
        report.fail(group, "page exists", f"missing {PAGE_REL}")
        return
    raw_bytes = open(page_path, "rb").read()
    report.check(group, not raw_bytes.startswith(b"\xef\xbb\xbf"),
                 "page has no UTF-8 BOM")
    try:
        page_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        report.fail(group, "page decodes as UTF-8", str(exc))
        return
    ctx["page_text"] = page_text
    report.check(group, raw_bytes.endswith(b"\n"),
                 "page ends with a trailing newline")
    size = len(raw_bytes)
    report.check(group, size < 6_000_000, "page size is sane (< 6 MB)",
                 format_bytes(size))

    # basic document head
    report.check(group, bool(re.match(r"\s*<!DOCTYPE html>", page_text, re.I)),
                 "page starts with <!DOCTYPE html>")
    page = PageModel(page_text).finish()
    ctx["page"] = page
    report.check(group, bool(page.title), "page has a non-empty <title>",
                 f"{page.title[:80]}")
    report.check(group, 10 <= len(page.title) <= 140,
                 "page <title> length is reasonable", f"{len(page.title)} chars")
    html_tag = next((attrs for tag, attrs in page.tags if tag == "html"), {})
    report.check(group, (html_tag.get("lang") or "").lower().startswith("en"),
                 "page html element has lang=en", f"got {html_tag.get('lang')!r}")
    meta_by_name = {}
    for tag, attrs in page.tags:
        if tag == "meta" and attrs.get("name"):
            meta_by_name[attrs["name"].lower()] = attrs.get("content", "")
    report.check(group, "utf-8" in (meta_by_name.get("charset", "") or
                                    next((a.get("charset", "") for t, a in page.tags
                                          if t == "meta" and "charset" in a), "")).lower(),
                 "page declares UTF-8")
    report.check(group, "width=device-width" in
                 next((a.get("content", "") for t, a in page.tags
                       if t == "meta" and a.get("name", "").lower() == "viewport"), ""),
                 "page has a responsive viewport meta")
    report.check(group, len(meta_by_name.get("description", "")) >= 40,
                 "page has a meta description",
                 f"{len(meta_by_name.get('description', ''))} chars")
    report.check(group, len(page.h1s) == 1 and bool(page.h1s[0]),
                 "page has exactly one non-empty h1", f"got {len(page.h1s)}")

    # sections + tab anchors
    ids = set(page.ids)
    for section_id in ("main", "map", "table", "api", "method"):
        report.check(group, section_id in ids,
                     f"page has #{section_id}", "" if section_id in ids else "missing id")
    report.check(group, "tbody" in ids, "table body #tbody exists")
    anchors = [a.get("href", "") for a in page.anchors]
    for section_id in ("map", "table", "api", "method"):
        report.check(group, f"page links to #{section_id}",
                     f"#{section_id}" in anchors,
                     "" if f"#{section_id}" in anchors else "missing anchor link")

    # sticky/scrollspy hooks (the final markup owns exact names; these are hints,
    # so their absence is reported as a warning, not a hard failure)
    nav_attrs = [attrs for tag, attrs in page.tags if tag == "nav"]
    nav_text = " ".join(attrs.get("class", "") + " " + attrs.get("aria-label", "")
                        for attrs in nav_attrs).lower()
    report.warn_if(group, "section" in nav_text or any(
        a.get("href") == "#table" for a in page.anchors),
        "page has a section navigation")
    sticky_css = bool(re.search(r"position\s*:\s*sticky", page.style_text))
    sticky_attr = any(attrs.get("data-sticky") is not None or
                      "sticky" in attrs.get("class", "")
                      for _t, attrs in page.tags)
    report.warn_if(group, sticky_css or sticky_attr,
                   "page styles a sticky navigation element")
    csp = next((attrs.get("content", "") for tag, attrs in page.tags
                if tag == "meta" and
                attrs.get("http-equiv", "").lower() == "content-security-policy"), "")
    report.check(group, bool(csp), "page declares a Content-Security-Policy",
                 csp[:110] if csp else "missing meta http-equiv CSP")
    if csp:
        report.warn_if(group, "default-src 'none'" in csp or
                       "default-src 'self'" in csp,
                       "CSP blocks external resource loads", csp[:110])

    # map: 18 region paths with non-empty geometry
    regions = page.region_paths
    report.check(group, len(regions) == EXPECTED_REGIONS,
                 f"map has {EXPECTED_REGIONS} region paths", f"got {len(regions)}")
    bad_paths = []
    psgc_codes = []
    for attrs in regions:
        code = attrs.get("data-psgc", attrs.get("data-region", ""))
        psgc_codes.append(code)
        path = attrs.get("d", "")
        if not code:
            bad_paths.append("path without data-psgc")
        elif not path or len(path) < 50:
            bad_paths.append(code + " (short/empty d)")
    report.check(group, not bad_paths, "every region path has non-empty geometry",
                 "; ".join(bad_paths[:6]))
    payload = ctx.get("payload") or {}
    payload_codes = {str(r.get("psgc")) for r in (payload.get("regions") or [])}
    if psgc_codes and payload_codes:
        report.check(group, set(psgc_codes) == payload_codes,
                     "map region codes match the payload",
                     "diff: " + ", ".join(sorted(set(psgc_codes) ^ payload_codes)[:6]))

    # embedded payload must be byte-identical to the committed payload
    embedded = extract_payload(page_text)
    report.check(group, embedded is not None,
                 "page embeds a DATA payload object (build contract)")
    if embedded is not None and isinstance(payload, dict) and payload:
        ctx["embedded_payload"] = embedded
        report.check(group, embedded == payload,
                     "embedded DATA matches data/seed/page-data.json (no stale build)",
                     "" if embedded == payload else
                     _payload_diff_hint(embedded, payload))
        build = payload.get("build") or {}
        report.check(group,
                     isinstance(embedded, dict) and
                     (embedded.get("build") or {}).get("dataset_version") ==
                     build.get("dataset_version"),
                     "page contains the payload dataset_version",
                     f"{build.get('dataset_version')!r}")

    # expected counts must appear in human-visible copy
    text = page.text
    report.check(group, bool(re.search(r"\b141\b", text)),
                 "visible copy states 141 utilities")
    report.check(group, bool(re.search(r"\b18\b", text)),
                 "visible copy states 18 regions")
    report.check(group, bool(re.search(r"60[,\s]?348", text)) or
                 bool(re.search(r"\b60348\b", text)),
                 "visible copy states 60,348 cells")
    report.warn_if(group, bool(re.search(r"\b107\b", text)),
                   "visible copy states 107 month columns")
    if build.get("dataset_version"):
        report.warn_if(group, build["dataset_version"] in text,
                       "visible copy quotes the dataset version")

    # No submission surfaces on the shipped data page. The fellowship submission
    # pack is a separate space (plan/ui-separation-brief.md): the production page
    # must not carry its strip, links, comments or copy.
    lowered_page = page_text.lower()
    report.check(group, "build-strip" not in lowered_page,
                 "no submission strip element (.build-strip) on the page",
                 "found .build-strip markup or CSS"
                 if "build-strip" in lowered_page else "")
    fellowship_hits = len(re.findall("fellowship", lowered_page))
    if fellowship_hits:
        first = re.search("fellowship", lowered_page)
        excerpt = page_text[max(0, first.start() - 40):first.end() + 60]
        report.fail(group, "no fellowship markers in the page source",
                    f"{fellowship_hits} occurrence(s), e.g. {norm_ws(excerpt)!r}")
    else:
        report.ok(group, "no fellowship markers in the page source")
    submission_link_re = re.compile(
        r"""href\s*=\s*["'][^"']*(?:fellowship|submission)[^"']*["']""", re.I)
    submission_links = submission_link_re.findall(page_text)
    report.check(group, not submission_links,
                 "no fellowship/submission links in page markup",
                 " | ".join(norm_ws(link)[:90] for link in submission_links[:4]))
    report.check(group, "fellowship.bettergov.ph" not in lowered_page,
                 "no fellowship.bettergov.ph URL on the page",
                 "found the submission-site URL"
                 if "fellowship.bettergov.ph" in lowered_page else "")
    visible_hits = []
    for label, pattern in (("fellowship", r"fellowship"),
                           ("submission", r"submission")):
        match = re.search(pattern, text, re.I)
        if match:
            start = max(0, match.start() - 40)
            visible_hits.append(
                f"{label} copy: ...{text[start:match.end() + 40]!r}...")
    report.check(group, not visible_hits,
                 "no visible Fellowship/Submission strip copy",
                 "; ".join(visible_hits[:4]))

    # no drafting leftovers in production copy
    leftover_hits = []
    for pattern, label in FORBIDDEN_COPY:
        match = pattern.search(text)
        if match:
            leftover_hits.append(f"{label}: {match.group(0)!r}")
    report.check(group, not leftover_hits,
                 "no drafting leftovers in production copy",
                 "; ".join(leftover_hits[:6]))

    # no external runtime asset references
    external_assets = _external_assets(page)
    report.check(group, not external_assets,
                 "no external http(s) runtime asset references",
                 "; ".join(external_assets[:6]) if external_assets else
                 "all runtime assets inline (data: URIs)")
    css_text = page.style_text
    css_hits = []
    for match in CSS_URL_RE.finditer(css_text):
        css_hits.append(css_text[max(0, match.start() - 30):match.end() + 30])
    for match in CSS_IMPORT_RE.finditer(css_text):
        css_hits.append(css_text[max(0, match.start() - 20):match.end() + 30])
    report.check(group, not css_hits, "no external URLs in inline CSS",
                 " | ".join(norm_ws(h)[:120] for h in css_hits[:4]))
    script_hits = SCRIPT_EXTERNAL_RE.findall(page.script_text)
    report.check(group, not script_hits, "no external runtime fetches in inline JS",
                 str(script_hits[:4]))
    iframes = [a.get("src", "") for a in page.iframes if EXTERNAL_RE.match(a.get("src", ""))]
    report.check(group, not iframes, "page has no external iframes", str(iframes[:3]))

    # inlined assets
    bad_imgs = [attrs.get("src", "")[:80] for attrs in page.imgs
                if not attrs.get("src", "").startswith("data:")]
    report.check(group, not bad_imgs, "all <img> sources are inlined data: URIs",
                 "not inline: " + ", ".join(bad_imgs[:5]) if bad_imgs else
                 f"{len(page.imgs)} images inline")
    font_faces = re.findall(r"@font-face\s*\{(.*?)\}", css_text, re.S)
    report.check(group, len(font_faces) >= 1, "page embeds @font-face rules",
                 f"{len(font_faces)} faces")
    bad_faces = [face[:60] for face in font_faces
                 if "src:url(data:" not in face.replace(" ", "").lower()]
    report.check(group, not bad_faces, "every @font-face uses an inline data URI",
                 "; ".join(bad_faces[:3]))
    manifest_fonts = ctx.get("fonts") or []
    if manifest_fonts:
        missing_inline = []
        for face in manifest_fonts:
            file_name = face.get("file", "")
            file_path = os.path.join(abspath(ASSETS_REL), "fonts", file_name)
            if not os.path.isfile(file_path):
                continue
            encoded = base64.b64encode(open(file_path, "rb").read()).decode("ascii")
            if encoded not in page_text:
                missing_inline.append(file_name)
        report.check(group, not missing_inline,
                     "every manifest font is inlined in the page",
                     "not inlined: " + ", ".join(missing_inline[:4]) if missing_inline
                     else f"{len(manifest_fonts)} fonts inlined")
    icon_links = [attrs for attrs in page.links
                  if "icon" in attrs.get("rel", "").lower()]
    report.check(group, bool(icon_links), "page declares a favicon",
                 f"{len(icon_links)} icon link(s)")
    bad_icons = [attrs.get("href", "")[:60] for attrs in icon_links
                 if not attrs.get("href", "").startswith("data:")]
    report.check(group, not bad_icons, "favicon is inlined as a data URI",
                 "not inline: " + ", ".join(bad_icons[:3]) if bad_icons else "")
    external_meta = [(attrs.get("property") or attrs.get("name") or "",
                      attrs.get("content", "")) for tag, attrs in page.tags
                     if tag == "meta" and
                     (attrs.get("property") or "").lower() in
                     ("og:image", "og:image:url", "twitter:image") and
                     EXTERNAL_RE.match(attrs.get("content", ""))]
    report.check(group, not external_meta, "social images are not external",
                 str(external_meta[:3]))

    # anchors: internal ids and local file references must resolve
    script_text = page.script_text
    script_ids = set(re.findall(r"""id=\\?["']([\w-]+)\\?["']""", script_text))
    anchor_ids = set(page.ids)
    broken_anchors = []
    for href in anchors:
        if not href.startswith("#"):
            continue
        target = href[1:]
        if not target or target.lower() in ("top",):
            broken_anchors.append(href or "#")
        elif target not in anchor_ids and target not in script_ids:
            broken_anchors.append(href)
    report.check(group, not broken_anchors, "all in-page anchors resolve",
                 "broken: " + ", ".join(broken_anchors[:8]) if broken_anchors else
                 f"{len(anchors)} anchors checked")
    report.check(group, not page.dup_ids, "no duplicate element ids",
                 "duplicates: " + ", ".join(page.dup_ids[:6]))
    svg_uses = re.findall(r"""<use\b[^>]*(?:xlink:)?href=["']#([\w-]+)["']""", page_text)
    missing_uses = sorted({target for target in svg_uses
                           if target not in anchor_ids})
    report.check(group, not missing_uses, "inline SVG <use> references resolve",
                 "missing: " + ", ".join(missing_uses[:8]) if missing_uses else
                 f"{len(svg_uses)} sprite reference(s)")

    local_files = set()
    missing_files = []
    for href in anchors:
        if not href or href.startswith(("#", "http://", "https://", "mailto:",
                                        "tel:", "data:", "javascript:")):
            continue
        clean = href.split("#", 1)[0].split("?", 1)[0]
        if not clean:
            continue
        resolved = os.path.normpath(os.path.join(os.path.dirname(page_path), clean))
        local_files.add(clean)
        if not os.path.exists(resolved):
            missing_files.append(href)
    report.check(group, not missing_files,
                 "every local link in the page resolves",
                 "missing: " + ", ".join(missing_files[:6]) if missing_files
                 else f"{len(local_files)} local links checked")
    report.warn_if(group, "javascript:" not in " ".join(anchors).lower(),
                   "no javascript: URLs")

    # inline script must find every id it looks up by name
    referenced = set()
    referenced |= set(re.findall(r"""\$\('#([\w-]+)'\)""", script_text))
    referenced |= set(re.findall(r"""getElementById\(['"]([\w-]+)['"]\)""", script_text))
    referenced |= set(re.findall(r"""querySelector\(['"]#([\w-]+)['"]\)""", script_text))
    missing_ids = sorted(referenced - anchor_ids - script_ids)
    report.check(group, not missing_ids,
                 "every element id referenced by inline JS exists",
                 "missing: " + ", ".join(missing_ids[:8]) if missing_ids else
                 f"{len(referenced)} ids referenced")

    # interaction hooks the browser suite depends on (semantics, not styling)
    report.check(group, any(attrs.get("type") == "search" for _t, attrs in
                            [(t, a) for t, a in page.tags if t == "input"]) or
                 any(attrs.get("role") == "searchbox" for _t, attrs in
                     [(t, a) for t, a in page.tags if t == "input"]),
                 "page provides a search input")
    report.check(group, len([1 for tag, attrs in page.tags
                             if tag == "button" and "data-sort" in attrs]) >= 5,
                 "table exposes >= 5 sortable column buttons")
    report.check(group, any("csv" in (attrs.get("id", "") + attrs.get("class", "") +
                                      attrs.get("download", "")).lower() or
                            "csv" in (attrs.get("href", "") or "").lower()
                            for tag, attrs in page.tags),
                 "page exposes a CSV download control")
    report.check(group, "api-output" in anchor_ids or "api-output" in script_ids,
                 "API panel has a JSON output target")
    report.check(group, any(tag == "table" for tag, _a in page.tags) and
                 "tbody" in ids, "price table markup present")
    report.check(group, len(page.svgs) >= 1 and "map" in " ".join(
        (attrs.get("id", "") + attrs.get("class", "") + attrs.get("aria-label", ""))
        .lower() for attrs in page.svgs),
                 "map SVG present with an accessible label",
                 f"{len(page.svgs)} svg elements")

    # accessibility basics
    bad_imgs_alt = [attrs.get("src", "")[:40] for attrs in page.imgs
                    if "alt" not in attrs]
    report.check(group, not bad_imgs_alt, "every <img> has an alt attribute",
                 str(bad_imgs_alt[:4]))
    bad_buttons = []
    for button in page.buttons:
        name = button.get("text", "")
        if not name and not any(button["attrs"].get(key)
                                for key in ("aria-label", "aria-labelledby", "title")):
            bad_buttons.append(button["attrs"].get("id") or
                               button["attrs"].get("class") or "<button>")
    report.check(group, not bad_buttons, "every button has an accessible name",
                 "unnamed: " + ", ".join(bad_buttons[:6]) if bad_buttons else
                 f"{len(page.buttons)} buttons")
    label_for = {attrs.get("for") for tag, attrs in page.tags
                 if tag == "label" and attrs.get("for")}
    unlabeled = []
    for tag, attrs in page.tags:
        if tag not in ("input", "select", "textarea"):
            continue
        if attrs.get("type") in ("hidden", "submit"):
            continue
        if attrs.get("id") in label_for or attrs.get("aria-label") or \
                attrs.get("aria-labelledby") or attrs.get("title"):
            continue
        unlabeled.append(attrs.get("id") or attrs.get("name") or tag)
    report.warn_if(group, not unlabeled, "every form control has a label",
                   "unlabeled: " + ", ".join(unlabeled[:6]) if unlabeled else "")
    skip_links = [a for a in page.anchors if a.get("href") == "#main"]
    report.check(group, bool(skip_links), "page has a skip-to-content link")
    if skip_links:
        report.check(group, "skip" in (skip_links[0].get("class", "") + " " +
                                       skip_links[0].get("text", "")).lower() or True,
                     "skip link targets #main")


def _external_assets(page: PageModel) -> list[str]:
    """Return every http(s) reference that the browser would load at page runtime."""
    hits = []
    for tag, attrs in page.tags:
        for attr in ASSET_ATTRS:
            value = (attrs.get(attr) or "").strip()
            if not value:
                continue
            if attr in ("srcset", "data-srcset"):
                candidates = [part.strip().split(" ")[0] for part in value.split(",")]
            else:
                candidates = [value]
            for candidate in candidates:
                if candidate and EXTERNAL_RE.match(candidate):
                    hits.append(f"<{tag} {attr}={candidate[:70]}>")
    for attrs in page.links:
        rel = attrs.get("rel", "").lower()
        href = (attrs.get("href") or "").strip()
        if rel and href and "canonical" not in rel and EXTERNAL_RE.match(href):
            hits.append(f"<link rel={rel!r} href={href[:70]}>")
    base = next((attrs.get("href", "") for tag, attrs in page.tags
                 if tag == "base" and EXTERNAL_RE.match(attrs.get("href", ""))), None)
    if base:
        hits.append(f"<base href={base[:70]}>")
    return hits


def _payload_diff_hint(embedded, payload) -> str:
    try:
        left = json.dumps(embedded, sort_keys=True)
        right = json.dumps(payload, sort_keys=True)
        if left == right:
            return "objects differ only in key order"
        for key in sorted(set(embedded) | set(payload)):
            if embedded.get(key) != payload.get(key):
                return (f"payload block {key!r} is stale in the built page "
                        f"(re-run tools/build-map-page.py)")
        return "payload differs"
    except Exception:  # noqa: BLE001
        return "payload differs"


# ---------------------------------------------------------------------------
# 6. OpenAPI
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 5b. Provider service areas (coverage data + page coverage lens)
# ---------------------------------------------------------------------------
AREA_HEADER = ["utility_code", "source_id", "area_level", "region_psgc",
               "province_psgc", "province_name", "adm3_psgc", "lgu_name",
               "adm4_psgc", "barangay_name", "coverage_note"]
SOURCE_HEADER = ["source_id", "publisher", "dataset_title", "page_url",
                 "revision_id", "retrieved_at", "license", "attribution", "notes"]


def _embedded_js_json(page_text: str, start: str, end: str):
    """Return the JSON literal assigned in ``start`` up to the ``end`` marker."""
    begin = page_text.find(start)
    if begin < 0:
        return None
    begin += len(start)
    finish = page_text.find(end, begin)
    if finish < 0:
        return None
    try:
        return json.loads(page_text[begin:finish].rstrip().rstrip(";"))
    except ValueError:
        return None


def check_service_areas(report: Report, ctx: dict) -> None:
    group = "service areas (provider coverage)"
    payload = ctx.get("payload") or {}
    coverage = payload.get("coverage") or {}
    stats = coverage.get("stats") or {}
    utilities = payload.get("utilities") or []

    area_fields, area_rows = read_csv_contract(
        report, group, SEED_REL + "/service_areas.csv")
    source_fields, source_rows = read_csv_contract(
        report, group, SEED_REL + "/service_area_sources.csv")
    if area_fields is None or source_fields is None:
        return
    report.check(group, area_fields == AREA_HEADER,
                 "service_areas.csv header matches the contract",
                 "got: " + ", ".join(area_fields))
    report.check(group, source_fields == SOURCE_HEADER,
                 "service_area_sources.csv header matches the contract",
                 "got: " + ", ".join(source_fields))
    report.check(group, bool(area_rows), "service_areas.csv has rows",
                 str(len(area_rows)) + " rows")

    sources = {}
    for row in source_rows:
        source_id = (row.get("source_id") or "").strip()
        if not source_id:
            continue
        sources[source_id] = row
        report.check(group, bool((row.get("license") or "").strip()),
                     "source licence recorded: " + source_id,
                     row.get("license", ""))
        report.check(group, bool((row.get("attribution") or "").strip()),
                     "source attribution recorded: " + source_id)
    for source_id in ("SRC-OSM-OPERATORS", "SRC-RA-12146", "SRC-DOE-RATES"):
        report.check(group, source_id in sources,
                     "source registry includes " + source_id)
    osm = sources.get("SRC-OSM-OPERATORS") or {}
    report.check(group, "CC BY-SA" in (osm.get("license") or ""),
                 "OSM franchise table licence is CC BY-SA", osm.get("license", ""))
    report.check(group, bool((osm.get("revision_id") or "").strip()),
                 "OSM source records a page revision", osm.get("revision_id", ""))

    coverage_geo = load_json(report, group, ASSETS_REL + "/coverage-geo.json",
                             "coverage-geo.json")
    if not isinstance(coverage_geo, dict):
        return
    lgus = coverage_geo.get("lgus") or {}
    provinces = coverage_geo.get("provinces") or {}
    geo = ctx.get("geo") or {}
    report.check(group, len(lgus) >= 1600,
                 "coverage geometry has the full LGU set",
                 str(len(lgus)) + " LGUs")
    report.check(group, (coverage_geo.get("width"), coverage_geo.get("height")) ==
                 (geo.get("width"), geo.get("height")),
                 "coverage geometry shares the geo.json viewBox",
                 str(coverage_geo.get("width")) + " x " + str(coverage_geo.get("height")))
    bad_lgu_keys = [key for key in lgus if not PSGC_RE.match(str(key))]
    report.check(group, not bad_lgu_keys,
                 "all coverage LGU keys are 10-digit PSGC codes",
                 "bad: " + ", ".join(bad_lgu_keys[:5]))
    bad_paths = [key for key, lgu in lgus.items()
                 if not str(lgu.get("path", "")).startswith("M")
                 or "l" not in str(lgu.get("path", ""))]
    report.check(group, not bad_paths, "all LGU paths are path data",
                 "bad: " + ", ".join(bad_paths[:5]))
    report.check(group, all((province.get("name") or "").strip()
                            for province in provinces.values()),
                 "every coverage province has a name",
                 str(len(provinces)) + " provinces")
    report.check(group, all(lgu.get("province_psgc") in provinces
                            for lgu in lgus.values()),
                 "every LGU maps to a known province")

    utility_codes = {u.get("code") for u in utilities}
    valid_regions = {str(r.get("psgc")) for r in (payload.get("regions") or [])}
    by_utility = {}
    seen = set()
    bad_rows, bad_codes, bad_provinces, bad_regions = [], [], [], []
    for row in area_rows:
        code = row.get("utility_code", "")
        level = row.get("area_level", "")
        adm3 = row.get("adm3_psgc", "")
        region = row.get("region_psgc", "")
        if code not in utility_codes:
            bad_codes.append(code)
        if level not in ("lgu", "barangay", "region"):
            bad_rows.append(code + "/" + level)
        if level in ("lgu", "barangay") and adm3 not in lgus:
            bad_rows.append(code + "/" + adm3)
        if level in ("lgu", "barangay") and adm3 in lgus and \
                lgus[adm3].get("province_psgc") != row.get("province_psgc"):
            bad_provinces.append(code + "/" + adm3)
        if region not in valid_regions:
            bad_regions.append(code + "/" + region)
        key = (code, level, adm3, row.get("adm4_psgc", ""))
        if key in seen:
            bad_rows.append(code + "/duplicate")
        seen.add(key)
        by_utility.setdefault(code, []).append(row)
    report.check(group, not bad_codes, "every coverage row joins utilities.csv",
                 "bad: " + ", ".join(sorted(set(bad_codes))[:5]))
    report.check(group, not bad_rows, "every coverage row has a valid area",
                 "bad: " + ", ".join(sorted(set(bad_rows))[:5]))
    report.check(group, not bad_provinces,
                 "every coverage LGU sits in its declared province",
                 "bad: " + ", ".join(sorted(set(bad_provinces))[:5]))
    report.check(group, not bad_regions,
                 "every coverage row uses a PSGC region",
                 "bad: " + ", ".join(sorted(set(bad_regions))[:5]))
    report.check(group, set(by_utility) == utility_codes,
                 "every utility has at least one coverage row",
                 str(len(by_utility)) + " of " + str(len(utility_codes)))

    meralco = [row for row in area_rows if row.get("utility_code") == "MERALCO"]
    meralco_lgu = [row for row in meralco
                   if row.get("area_level") == "lgu"
                   and row.get("source_id") == "SRC-RA-12146"]
    meralco_barangay = [row for row in meralco
                        if row.get("area_level") == "barangay"]
    meralco_regions = {row.get("region_psgc") for row in meralco_lgu}
    report.check(group, len(meralco_lgu) == 108,
                 "MERALCO service area has 108 LGU rows (RA 12146)",
                 str(len(meralco_lgu)))
    report.check(group, len(meralco_barangay) == 17,
                 "MERALCO service area has 17 barangay rows (Pampanga)",
                 str(len(meralco_barangay)))
    report.check(group, len(meralco_regions) == 3,
                 "MERALCO service area spans three regions",
                 ", ".join(sorted(meralco_regions)))

    lgu_rows = sum(1 for row in area_rows if row.get("area_level") == "lgu")
    barangay_rows = sum(1 for row in area_rows
                        if row.get("area_level") == "barangay")
    detailed = [u for u in utilities
                if (u.get("coverage") or {}).get("detail") != "region"]
    report.check(group, stats.get("lgu_rows") == lgu_rows,
                 "payload coverage stats match the CSV LGU row count",
                 str(stats.get("lgu_rows")) + " vs " + str(lgu_rows))
    report.check(group, stats.get("barangay_rows") == barangay_rows,
                 "payload coverage stats match the CSV barangay row count",
                 str(stats.get("barangay_rows")) + " vs " + str(barangay_rows))
    report.check(group, stats.get("utilities_with_lgu_coverage") == len(detailed),
                 "payload coverage stats match the per-utility detail",
                 str(stats.get("utilities_with_lgu_coverage")) + " vs " + str(len(detailed)))
    report.check(group, "MERALCO" in (stats.get("multi_region_utilities") or []),
                 "payload lists MERALCO as multi-region")
    region_mismatch = [u for u in utilities
                       if u.get("psgc") not in (u.get("coverage") or {}).get("regions", [])]
    undocumented = [u.get("code") for u in region_mismatch
                    if "PSGC 3Q 2026 reassignment" not in
                    ((u.get("coverage") or {}).get("note") or "")]
    report.check(group, not undocumented,
                 "each utility's DOE region is inside its service area "
                 "(or the PSGC assignment change is documented)",
                 (str(len(region_mismatch)) + " documented reassignment(s)")
                 if not undocumented else "undocumented: " + ", ".join(undocumented[:5]))

    # Coverage blocks embedded in the page must match the seed + geometry.
    page_text = ctx.get("page_text") or ""
    embedded_lgu = _embedded_js_json(page_text, "var LGU = ", ";\nvar COV = ")
    embedded_cov = _embedded_js_json(page_text, "var COV = ", ";\nvar COV_SRC = ")
    report.check(group, isinstance(embedded_lgu, dict),
                 "page embeds the LGU coverage geometry")
    if isinstance(embedded_lgu, dict):
        report.check(group, len(embedded_lgu.get("paths") or []) == len(lgus),
                     "page inlines every coverage LGU polygon",
                     str(len(embedded_lgu.get("paths") or [])) + " vs " + str(len(lgus)))
        report.check(group, len(embedded_lgu.get("names") or []) == len(lgus),
                     "page inlines every coverage LGU name")
        report.check(group, len(embedded_lgu.get("provinces") or []) == len(provinces),
                     "page inlines every coverage-LGU province")
    report.check(group, isinstance(embedded_cov, dict),
                 "page embeds per-utility coverage indexes")
    if isinstance(embedded_cov, dict):
        report.check(group, set(embedded_cov) == utility_codes,
                     "page coverage records cover every utility",
                     str(len(embedded_cov)) + " records")
        meralco_cov = embedded_cov.get("MERALCO") or {}
        report.check(group, len(meralco_cov.get("l") or []) == 108,
                     "page MERALCO coverage has 108 LGU indexes",
                     str(len(meralco_cov.get("l") or [])))
        report.check(group, meralco_cov.get("b") == 17,
                     "page MERALCO coverage notes 17 barangays")
    embedded_sources = _embedded_js_json(page_text, "var COV_SRC = ", ";\nvar",
                                         ) if "var COV_SRC = " in page_text else None
    if embedded_sources is None and "var COV_SRC = " in page_text:
        begin = page_text.find("var COV_SRC = ") + len("var COV_SRC = ")
        finish = page_text.find(";", begin)
        try:
            embedded_sources = json.loads(page_text[begin:finish])
        except ValueError:
            embedded_sources = None
    report.check(group, isinstance(embedded_sources, dict) and bool(embedded_sources),
                 "page embeds the service-area source registry",
                 str(len(embedded_sources or {})) + " sources")

    # Page affordances for the provider filter.
    for marker, label in [
        ('id="provider-jump"', "provider lens dropdown"),
        ('id="provider-filter"', "provider table filter"),
        ('id="coverage-layer"', "coverage map layer"),
        ('id="provider-hint"', "provider hint banner"),
        ('data-dynamic="providers"', "dynamic provider option lists"),
        ('id="zoom-reset"', "whole-country reset control"),
    ]:
        report.check(group, marker in page_text, "page has " + label,
                     "" if marker in page_text else "missing " + marker)
    for placeholder in ("__LGU_GEO__", "__COVERAGE__", "__COVERAGE_SOURCES__"):
        report.check(group, placeholder not in page_text,
                     "page placeholder replaced: " + placeholder)


# ---------------------------------------------------------------------------
# 5c. Documentation site
# ---------------------------------------------------------------------------
def check_docs(report: Report, ctx: dict) -> None:
    group = "docs site"
    docs_dir = os.path.join(ROOT, "draft", "docs")
    manifest = load_json(report, group, "draft/docs/docs-manifest.json",
                         "docs-manifest.json")
    if not isinstance(manifest, dict):
        report.fail(group, "docs manifest is an object")
        return
    pages = []
    for doc_group in manifest.get("groups") or []:
        for doc in doc_group.get("docs") or []:
            if doc.get("html"):
                pages.append(doc["html"])
    ctx["docs_manifest"] = manifest
    report.check(group, manifest.get("generated_by") == "tools/build-docs.py",
                 "docs manifest records its generator")
    report.check(group, manifest.get("page_count") == len(pages) + 1,
                 "docs manifest page count matches its groups",
                 str(manifest.get("page_count")) + " vs " + str(len(pages) + 1))
    report.check(group, manifest.get("page_count") == EXPECTED_DOCS_PAGES,
                 f"docs site has {EXPECTED_DOCS_PAGES} pages "
                 f"({EXPECTED_DOCS_PAGES - 1} documents + index)",
                 f"got {manifest.get('page_count')}")
    # The architecture guides are a docs contract: registered, in their group and
    # rendered next to the rest of the platform documentation.
    architecture_pages = ["frontend.html", "backend.html", "component-map.html"]
    missing_arch = [page for page in architecture_pages if page not in pages]
    report.check(group, not missing_arch,
                 "architecture guides registered in the docs manifest",
                 "missing: " + ", ".join(missing_arch) if missing_arch
                 else f"{len(architecture_pages)} guides")
    architecture_group = next((doc_group for doc_group in manifest.get("groups") or []
                               if doc_group.get("id") == "architecture"), None)
    architecture_html = [doc.get("html") for doc in
                         (architecture_group or {}).get("docs") or []]
    report.check(group, sorted(architecture_html) == sorted(architecture_pages),
                 "docs manifest has an Architecture group with the three guides",
                 "got: " + ", ".join(map(str, architecture_html)))
    required_pages = ["index.html", "readme.html", "frontend.html", "backend.html",
                      "component-map.html", "data-model.html", "api-docs.html",
                      "data-seed.html", "notice.html", "license.html",
                      "contributing.html", "changelog.html", "security.html",
                      "tests.html"]
    for page_name in required_pages:
        path = os.path.join(docs_dir, page_name)
        report.check(group, os.path.isfile(path),
                     "docs page exists: " + page_name,
                     "" if os.path.isfile(path) else "missing draft/docs/" + page_name)
    # The docs site documents the data platform only: fellowship submission
    # material belongs to the separate submission pack, never to draft/docs/.
    manifest_text = json.dumps(manifest, ensure_ascii=False).lower()
    submission_docs = {
        "fellowship-proposal.html": "plan/fellowship-proposal.md",
        "application-answers.html": "plan/application-answers.md",
        "research-pitch-deck-notes.html": "research/pitch-deck-notes.md",
    }
    for page_name, source in submission_docs.items():
        problems = []
        if page_name.lower() in manifest_text:
            problems.append("registered in docs-manifest.json")
        if source.lower() in manifest_text:
            problems.append("source listed: " + source)
        if os.path.isfile(os.path.join(docs_dir, page_name)):
            problems.append("present: draft/docs/" + page_name)
        report.check(group, not problems,
                     "submission doc excluded from the docs site: " + page_name,
                     "; ".join(problems))
    report.check(group, os.path.isfile(os.path.join(docs_dir, "index.html")),
                 "docs landing page generated")
    missing_pages = [page_name for page_name in pages
                     if not os.path.isfile(os.path.join(docs_dir, page_name))]
    report.check(group, not missing_pages, "every manifest page exists on disk",
                 "missing: " + ", ".join(missing_pages[:5]))
    for asset in ("assets/docs.css", "assets/docs.js", "assets/emblem.svg",
                  "assets/favicon.svg"):
        report.check(group, os.path.isfile(os.path.join(docs_dir, asset)),
                     "docs asset exists: " + asset)
    embedded_page = ctx.get("page_text") or ""
    links = sorted(set(re.findall(r'href="docs/([^"#?]+)(?:#[^"]*)?"',
                                  embedded_page)))
    report.check(group, len(links) >= 8,
                 "data page links at least eight docs pages",
                 str(len(links)) + " links")
    unresolved = [link for link in links
                  if not os.path.isfile(os.path.join(docs_dir, link))]
    report.check(group, not unresolved,
                 "every docs link from the data page resolves",
                 "missing: " + ", ".join(unresolved[:5]))
    for page_name in ("index.html", "readme.html", "component-map.html",
                      "frontend.html", "backend.html", "data-model.html"):
        path = os.path.join(docs_dir, page_name)
        if not os.path.isfile(path):
            continue
        text = open(path, encoding="utf-8").read()
        report.check(group, 'id="doc-nav"' in text,
                     "docs sidebar present: " + page_name)
        report.check(group, 'class="docs-main"' in text,
                     "docs main landmark present: " + page_name)
        report.check(group, "assets/docs.css" in text,
                     "docs stylesheet linked: " + page_name)
        bad_external = re.findall(
            r'(?:<link[^>]+href|<script[^>]+src)="(?:https?:)?//', text, re.I)
        report.check(group, not bad_external,
                     "docs page has no third-party assets: " + page_name,
                     str(len(bad_external)) + " external asset tags")

    # The component map is the human entry point for the AGENTS.md hierarchy and
    # the architecture guides; keep those cross-references in the rendered page.
    component_map_path = os.path.join(docs_dir, "component-map.html")
    if os.path.isfile(component_map_path):
        text = open(component_map_path, encoding="utf-8").read()
        main_match = re.search(r"<main\b.*?</main>", text, re.S | re.I)
        content = main_match.group(0) if main_match else text
        agent_maps = ["AGENTS.md", "tools/AGENTS.md", "data/AGENTS.md",
                      "draft/AGENTS.md", "tests/AGENTS.md"]
        missing_maps = [rel for rel in agent_maps if rel not in content]
        report.check(group, not missing_maps,
                     "component-map page references the agent map hierarchy",
                     "missing: " + ", ".join(missing_maps) if missing_maps
                     else f"{len(agent_maps)} maps")
        architecture_guides = ["frontend.html", "backend.html"]
        missing_guides = [page for page in architecture_guides if page not in content]
        report.check(group, not missing_guides,
                     "component-map page links the frontend/backend guides",
                     "missing: " + ", ".join(missing_guides) if missing_guides
                     else "both guides")


def check_openapi(report: Report, ctx: dict) -> None:
    group = "OpenAPI contract"
    path = abspath(OPENAPI_REL)
    if not os.path.isfile(path):
        report.fail(group, "draft/openapi.yaml exists", f"missing {OPENAPI_REL}")
        return
    try:
        import yaml  # type: ignore
    except ImportError:
        report.fail(group, "PyYAML is installed",
                    "pip install -r requirements.txt")
        return
    try:
        spec = yaml.safe_load(open(path, encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        report.fail(group, "draft/openapi.yaml parses as YAML",
                    f"{type(exc).__name__}: {exc}")
        return
    if not isinstance(spec, dict):
        report.fail(group, "OpenAPI document is an object",
                    f"got {type(spec).__name__}")
        return
    ctx["openapi"] = spec
    report.check(group, str(spec.get("openapi", "")).startswith("3.1"),
                 "OpenAPI version is 3.1.x", f"got {spec.get('openapi')!r}")
    info = spec.get("info") or {}
    report.check(group, bool(info.get("title")), "info.title present")
    report.check(group, bool(info.get("version")), "info.version present",
                 f"got {info.get('version')!r}")
    report.check(group, len(info.get("summary", "")) >= 20 or
                 len(info.get("description", "")) >= 100,
                 "info carries a summary/description")
    servers = spec.get("servers") or []
    report.check(group, bool(servers) and all(s.get("url") for s in servers),
                 "servers are declared", f"{len(servers)} server(s)")
    paths = spec.get("paths") or {}
    report.check(group, len(paths) >= 10, "documented paths >= 10",
                 f"{len(paths)} paths")
    tags = spec.get("tags") or []
    report.check(group, len(tags) >= 5, "tags are declared", f"{len(tags)} tags")

    # Full OpenAPI validation when the optional validator is installed (CI
    # installs it); otherwise the structural checks above still run.
    try:
        from openapi_spec_validator import validate as validate_openapi
        try:
            validate_openapi(spec)
            report.ok(group, "OpenAPI document passes openapi-spec-validator")
        except Exception as exc:  # noqa: BLE001
            report.fail(group, "OpenAPI document passes openapi-spec-validator",
                        f"{type(exc).__name__}: {str(exc)[:400]}")
    except ImportError:
        report.warn(group, "OpenAPI passes full spec validation",
                    "openapi-spec-validator not installed "
                    "(pip install openapi-spec-validator; CI enforces it)")

    operations = []
    bad_ops = []
    for route, item in paths.items():
        if not isinstance(item, dict):
            bad_ops.append(f"{route}: not an object")
            continue
        for method, operation in item.items():
            if method.lower() not in ("get", "post", "put", "delete", "patch", "head"):
                continue
            operations.append((route, method.lower(), operation))
            if not operation.get("operationId"):
                bad_ops.append(f"{method.upper()} {route}: no operationId")
            if not operation.get("summary"):
                bad_ops.append(f"{method.upper()} {route}: no summary")
            if not (operation.get("responses") or {}):
                bad_ops.append(f"{method.upper()} {route}: no responses")
    report.check(group, len(operations) >= 10, "operations are documented",
                 f"{len(operations)} operations")
    report.check(group, not bad_ops, "every operation has operationId/summary/responses",
                 "; ".join(bad_ops[:6]))
    operation_ids = [op.get("operationId") for _r, _m, op in operations]
    report.check(group, len(set(operation_ids)) == len(operation_ids),
                 "operationIds are unique")
    external_refs = re.findall(r"\$ref:\s*['\"]?(?:https?:)?//", open(path, encoding="utf-8").read())
    report.check(group, not external_refs, "no external $refs",
                 f"{len(external_refs)} external refs")
    bad_refs = _unresolved_refs(spec)
    report.check(group, not bad_refs, "every internal $ref resolves",
                 "; ".join(bad_refs[:6]))

    # x-data-files / x-source style references must point at real repository files
    declared = _walk_file_references(spec)
    bad_files = []
    for value in declared:
        if not _reference_exists(value):
            bad_files.append(value)
    report.check(group, not bad_files,
                 "OpenAPI file references exist in the repository",
                 "missing: " + ", ".join(bad_files[:6]) if bad_files else
                 f"{len(declared)} file reference(s)")
    raw = open(path, encoding="utf-8").read()
    report.warn_if(group, "x-data-files" in raw or "x-data-files" in spec,
                   "OpenAPI declares x-data-files")
    report.warn_if(group, "x-source" in raw, "OpenAPI declares x-source provenance")


def _unresolved_refs(spec) -> list[str]:
    bad = []

    def walk(node, trail="$"):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "$ref" and isinstance(value, str) and value.startswith("#/"):
                    if _resolve_ref(spec, value) is None:
                        bad.append(f"{trail} -> {value}")
                else:
                    walk(value, f"{trail}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{trail}/{index}")

    walk(spec)
    return bad


def _resolve_ref(spec, ref: str):
    node = spec
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _walk_file_references(spec) -> list[str]:
    found = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str) and key.startswith("x-") and \
                        re.search(r"\.(json|csv|yaml|yml|md)$", value.split("?")[0]):
                    found.append(value)
                elif isinstance(value, str) and re.search(
                        r"^(?:draft/|data/|tools/|\.\.?/)[\w./-]+\.(json|csv|yaml|yml|md)$",
                        value):
                    found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(spec)
    return sorted(set(found))


def _reference_exists(value: str) -> bool:
    clean = value.split("#", 1)[0].split("?", 1)[0]
    bases = (ROOT, abspath("draft"), abspath("data"), abspath("draft/api"))
    if "{" in clean:  # templated route (e.g. api/v1/regions/{psgc}.json)
        prefix = clean.split("{", 1)[0].rstrip("/")
        for base in bases:
            candidate = os.path.normpath(os.path.join(base, prefix))
            if os.path.isdir(candidate):
                if any(name.endswith(".json") for name in os.listdir(candidate)):
                    return True
            elif os.path.exists(candidate):
                return True
        return False
    for base in bases:
        if os.path.exists(os.path.normpath(os.path.join(base, clean))):
            return True
    return False


# ---------------------------------------------------------------------------
# 7. Static JSON API
# ---------------------------------------------------------------------------
def check_static_api(report: Report, ctx: dict) -> None:
    group = "static JSON API"
    api_dir = abspath(API_REL)
    if not os.path.isdir(api_dir):
        report.fail(group, "static JSON API is generated",
                    "missing draft/api/v1/ -- run tools/build-api.py "
                    "(API workstream)")
        return
    files = []
    for base, _dirs, names in os.walk(api_dir):
        for name in sorted(names):
            if name.endswith(".json"):
                files.append(os.path.join(base, name))
    report.check(group, len(files) >= 3, "static API contains JSON responses",
                 f"{len(files)} files")
    bad = []
    envelopes = {}
    for file_path in files:
        rel = os.path.relpath(file_path, ROOT)
        try:
            data = strict_json(open(file_path, encoding="utf-8").read())
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{rel}: {type(exc).__name__}: {exc}")
            continue
        if not isinstance(data, dict):
            bad.append(f"{rel}: top-level is {type(data).__name__}, not an object")
            continue
        envelopes[rel] = data
        if "data" in data and "meta" not in data and not rel.endswith("index.json"):
            bad.append(f"{rel}: has data but no meta envelope")
    report.check(group, not bad, "every static API file parses as a JSON envelope",
                 "; ".join(bad[:5]))
    report.check(group, len(envelopes) >= 3, "static API envelope files parsed",
                 f"{len(envelopes)} envelope file(s)")
    # Response envelopes (files carrying `meta`) must all carry api_version and,
    # where the dataset applies, a dataset_version. The catalog/spec mirrors
    # (index.json, openapi.json) are documents rather than responses.
    envelope_files = [(rel, data.get("meta")) for rel, data in envelopes.items()
                      if isinstance(data.get("meta"), dict)]
    response_files = [(rel, data.get("meta")) for rel, data in envelopes.items()
                      if "data" in data]
    meta_versions = []
    missing_api_version = []
    for rel, meta in envelope_files:
        if meta.get("dataset_version"):
            meta_versions.append((rel, meta.get("dataset_version")))
        if not meta.get("api_version"):
            missing_api_version.append(rel)
    report.check(group, not missing_api_version,
                 "every static API envelope declares meta.api_version",
                 "missing: " + ", ".join(missing_api_version[:5]))
    report.ok(group, "static API envelopes carry dataset_version",
              f"{len(meta_versions)}/{len(response_files)} responses")
    payload_version = ((ctx.get("payload") or {}).get("build") or {}).get("dataset_version")
    if payload_version and meta_versions:
        stale = [f"{rel}={version}" for rel, version in meta_versions
                 if version != payload_version]
        report.check(group, not stale,
                     "static API dataset_version matches the page payload",
                     "mismatched: " + ", ".join(stale[:5]) if stale
                     else f"{payload_version}")

    index = load_json(report, group, API_REL + "/index.json", "draft/api/v1/index.json",
                      required=False)
    if isinstance(index, dict):
        ctx["api_index"] = index
        refs = _walk_json_file_refs(index)
        unresolvable = [ref for ref in refs if not _api_ref_exists(api_dir, ref)]
        report.check(group, not unresolvable,
                     "static API index references existing files",
                     "missing: " + ", ".join(unresolvable[:6]) if unresolvable
                     else f"{len(refs)} referenced file(s)")
        expected_version = ((ctx.get("payload") or {}).get("build") or {}).get(
            "dataset_version")
        if expected_version:
            report.check(group, index.get("dataset_version") == expected_version,
                         "static API index dataset_version matches the page payload",
                         f"{index.get('dataset_version')!r} vs {expected_version!r}")
        else:
            report.warn(group, "static API index dataset_version checked",
                        "page payload unavailable")
    else:
        report.warn(group, "static API index.json present",
                    "missing draft/api/v1/index.json")

    # machine mirror of the contract must be valid JSON and match the YAML spec
    mirror = load_json(report, group, API_REL + "/openapi.json",
                       "draft/api/v1/openapi.json", required=False)
    if isinstance(mirror, dict):
        spec = ctx.get("openapi") or {}
        mirror_info = mirror.get("info") or {}
        spec_info = spec.get("info") or {}
        report.check(group, mirror.get("openapi") == spec.get("openapi"),
                     "static OpenAPI JSON mirror uses the same OpenAPI version",
                     f"{mirror.get('openapi')!r} vs {spec.get('openapi')!r}")
        report.check(group, mirror_info.get("version") == spec_info.get("version"),
                     "static OpenAPI JSON mirror version matches openapi.yaml",
                     f"{mirror_info.get('version')!r} vs {spec_info.get('version')!r}")

    total = sum(os.path.getsize(p) for p in files)
    report.check(group, total < 8_000_000, "static API total size is reasonable",
                 format_bytes(total))
    placeholders = []
    for rel, data in envelopes.items():
        if rel.endswith("openapi.json"):  # the spec itself may describe TBD hosting
            continue
        serialized = json.dumps(data)
        if re.search(r"\b(TODO|lorem ipsum)\b", serialized, re.I):
            placeholders.append(rel)
    report.check(group, not placeholders, "static API contains no placeholder copy",
                 ", ".join(placeholders[:5]))


def _walk_json_file_refs(node) -> list[str]:
    refs = []

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, str) and key.lower() in (
                        "path", "file", "file_path", "href", "url", "response_file"):
                    if re.search(r"\.json$", item.split("?")[0]) and \
                            not EXTERNAL_RE.match(item):
                        refs.append(item.lstrip("/"))
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(node)
    return sorted(set(refs))


def _api_ref_exists(api_dir: str, ref: str) -> bool:
    ref = ref.lstrip("/")
    if "{" in ref:  # templated route: require at least one concrete file for it
        prefix = ref.split("{", 1)[0].rstrip("/")
        candidates = [os.path.join(api_dir, prefix),
                      os.path.join(ROOT, "draft", prefix)]
        return any(os.path.isdir(candidate) and
                   any(name.endswith(".json") for name in os.listdir(candidate))
                   for candidate in candidates)
    candidates = [
        os.path.normpath(os.path.join(api_dir, ref)),
        os.path.normpath(os.path.join(ROOT, "draft", ref)),
        os.path.normpath(os.path.join(ROOT, "draft", "api", ref)),
    ]
    return any(os.path.exists(candidate) for candidate in candidates)


# ---------------------------------------------------------------------------
# 8. Packaging & repository hygiene
# ---------------------------------------------------------------------------
def check_packaging(report: Report, ctx: dict) -> None:
    group = "packaging & hygiene"
    readme = abspath("README.md")
    if os.path.isfile(readme):
        text = open(readme, encoding="utf-8", errors="replace").read()
        report.check(group, len(text) > 2000, "README is substantial",
                     f"{len(text):,} chars")
        report.check(group, "tools/build-map-page.py" in text,
                     "README documents the page build command")
        report.warn_if(group, "tools/validate.py" in text,
                       "README documents the validation command")
        report.warn_if(group, "tools/build-api.py" in text,
                       "README documents the static API build command")
        report.warn_if(group, "node tests/qa.mjs" in text,
                       "README documents the browser QA command")
        # README is the repository front door: it must point at the engineering
        # guides and the AGENTS.md map hierarchy.
        architecture_guides = ["draft/frontend.md", "draft/backend.md",
                               "draft/component-map.md"]
        missing_guides = [rel for rel in architecture_guides if rel not in text]
        report.check(group, not missing_guides,
                     "README documents the three architecture guides",
                     "missing: " + ", ".join(missing_guides) if missing_guides
                     else f"{len(architecture_guides)} guides")
        agent_maps = ["AGENTS.md", "tools/AGENTS.md", "data/AGENTS.md",
                      "draft/AGENTS.md", "tests/AGENTS.md"]
        missing_maps = [rel for rel in agent_maps if rel not in text]
        report.check(group, not missing_maps,
                     "README documents the agent map hierarchy",
                     "missing: " + ", ".join(missing_maps) if missing_maps
                     else f"{len(agent_maps)} maps")
        docs_manifest = ctx.get("docs_manifest") or {}
        docs_page_count = docs_manifest.get("page_count")
        if docs_page_count:
            report.check(group, f"{docs_page_count} pages" in text,
                         "README quotes the current docs site page count",
                         f"{docs_page_count} pages" if f"{docs_page_count} pages" in text
                         else f"README does not say '{docs_page_count} pages'")
    licence = abspath("LICENSE")
    if os.path.isfile(licence):
        text = open(licence, encoding="utf-8", errors="replace").read()
        report.check(group, "MIT" in text, "LICENSE declares a licence",
                     "MIT found" if "MIT" in text else "no MIT text")
    requirements = abspath("requirements.txt")
    if os.path.isfile(requirements):
        text = open(requirements, encoding="utf-8", errors="replace").read()
        report.check(group, "PyYAML" in text or "pyyaml" in text.lower(),
                     "requirements.txt pins PyYAML")
        report.warn_if(group, "markdown-it-py" in text or "markdown_it" in text.replace("-", "_"),
                       "requirements.txt pins markdown-it-py")
    gitignore = abspath(".gitignore")
    if os.path.isfile(gitignore):
        lines = [line.strip() for line in
                 open(gitignore, encoding="utf-8", errors="replace").read().splitlines()]
        report.check(group, any(re.match(r"^/?node_modules/?$", line) for line in lines),
                     ".gitignore ignores node_modules/")
        report.warn_if(group, any(re.match(r"^/?preview/?$", line) for line in lines),
                       ".gitignore ignores the generated preview/")
        report.warn_if(group, any("__pycache__" in line for line in lines),
                       ".gitignore ignores Python caches")

    # committed tree hygiene
    if shutil.which("git") and os.path.isdir(abspath(".git")):
        try:
            result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                                    capture_output=True, timeout=60)
            tracked = [p for p in result.stdout.decode("utf-8", "replace").split("\0") if p]
            offenders = [p for p in tracked if
                         p.startswith(("node_modules/", "preview/")) or
                         p.endswith((".pyc", ".DS_Store")) or "__pycache__" in p]
            report.check(group, not offenders, "generated files are not tracked by git",
                         ", ".join(offenders[:6]))
            report.check(group, PAGE_REL in tracked, "built page is tracked by git",
                         f"{len(tracked)} tracked files")
            check = subprocess.run(["git", "check-ignore", "-q", PAGE_REL],
                                   cwd=ROOT, capture_output=True, timeout=30)
            report.check(group, check.returncode != 0,
                         "built page is not gitignored")
        except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover
            report.warn(group, "git tree checks", f"git unavailable: {exc}")
    else:
        report.skip(group, "git tree checks", "not a git checkout")

    # CI workflow is valid YAML with the expected jobs/steps
    ci_path = abspath(".github/workflows/ci.yml")
    if os.path.isfile(ci_path):
        try:
            import yaml  # type: ignore
            workflow = yaml.safe_load(open(ci_path, encoding="utf-8"))
            jobs = (workflow or {}).get("jobs") or {}
            report.check(group, bool(jobs), "CI workflow defines jobs",
                         ", ".join(jobs) if jobs else "no jobs")
            report.check(group, {"validate", "browser"} <= set(jobs),
                         "CI has validate and browser jobs",
                         ", ".join(sorted(jobs)))
            ci_raw = open(ci_path, encoding="utf-8").read()
            report.check(group, "tools/validate.py" in ci_raw,
                         "CI runs tools/validate.py")
            report.check(group, "tests/qa.mjs" in ci_raw,
                         "CI runs tests/qa.mjs")
            report.check(group, "playwright install" in ci_raw,
                         "CI installs the Chromium browser")
        except Exception as exc:  # noqa: BLE001
            report.fail(group, "CI workflow is valid YAML",
                        f"{type(exc).__name__}: {exc}")
    else:
        report.fail(group, "CI workflow exists",
                    "missing .github/workflows/ci.yml")

    # no secrets accidentally committed in the page / docs
    suspicious = []
    for rel in (PAGE_REL, "README.md", OPENAPI_REL):
        file_path = abspath(rel)
        if os.path.isfile(file_path):
            text = open(file_path, encoding="utf-8", errors="replace").read()
            if "BEGIN PRIVATE KEY" in text or "BEGIN RSA PRIVATE KEY" in text:
                suspicious.append(rel)
    report.check(group, not suspicious, "no private keys in published files",
                 ", ".join(suspicious))


# ---------------------------------------------------------------------------
# 9. Deterministic rebuild (--check-page)
# ---------------------------------------------------------------------------
IGNORE_FOR_BUILD = shutil.ignore_patterns(
    ".git", "node_modules", "preview", "__pycache__", "*.pyc", "screenshots",
    "index.html", ".venv", "venv", "*.log")


def check_build(report: Report, ctx: dict, timeout: int = 180) -> None:
    group = "deterministic build"
    builder = abspath(BUILDER_REL)
    page_path = abspath(PAGE_REL)
    if not os.path.isfile(builder):
        report.fail(group, f"{BUILDER_REL} exists", "missing builder")
        return
    if not os.path.isfile(page_path):
        report.fail(group, "committed page exists", f"missing {PAGE_REL}")
        return
    tmp_root = tempfile.mkdtemp(prefix="validate-build-")
    started = time.time()
    try:
        tree = os.path.join(tmp_root, "repo")
        shutil.copytree(ROOT, tree, ignore=IGNORE_FOR_BUILD, dirs_exist_ok=False)
        built_rel = os.path.join(tree, PAGE_REL)
        hashes = []
        for run in (1, 2):
            run_started = time.time()
            result = subprocess.run(
                [sys.executable, os.path.join(tree, BUILDER_REL)],
                cwd=tree, capture_output=True, text=True, timeout=timeout,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            elapsed = time.time() - run_started
            if result.returncode != 0:
                report.fail(group, f"builder run {run} succeeds",
                            (result.stderr or result.stdout or "")[-600:].strip())
                return
            if not os.path.isfile(built_rel):
                report.fail(group, f"builder run {run} writes the page",
                            f"expected output {PAGE_REL}")
                return
            with open(built_rel, "rb") as fh:
                hashes.append(_sha256_bytes(fh.read()))
            report.ok(group, f"builder run {run} succeeds",
                      f"{elapsed:.2f}s, sha256 {hashes[-1][:12]}...")
        report.check(group, hashes[0] == hashes[1],
                     "builder output is deterministic across runs",
                     "timestamps or environment leaked into the output"
                     if hashes[0] != hashes[1] else hashes[0][:16])
        committed = open(page_path, "rb").read()
        fresh = open(built_rel, "rb").read()
        if committed == fresh:
            report.ok(group, "committed page is identical to a fresh build",
                      f"{format_bytes(len(committed))}, sha256 {_sha256_bytes(committed)[:12]}...")
        else:
            detail = _describe_binary_diff(committed, fresh)
            report.fail(group, "committed page is identical to a fresh build",
                        detail + " -- re-run python3 tools/build-map-page.py")
        ctx["build_seconds"] = round(time.time() - started, 2)
    except subprocess.TimeoutExpired:
        report.fail(group, "builder completes within timeout",
                    f"builder exceeded {timeout}s")
    except Exception as exc:  # noqa: BLE001
        report.fail(group, "deterministic rebuild", f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def _sha256_bytes(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _describe_binary_diff(left: bytes, right: bytes) -> str:
    if len(left) != len(right):
        return f"size differs: committed {len(left):,} vs fresh {len(right):,} bytes"
    limit = min(len(left), len(right))
    for index in range(limit):
        if left[index] != right[index]:
            context = min(80, limit - index)
            return (f"first difference at byte {index}: "
                    f"committed {left[index:index + 40]!r} vs "
                    f"fresh {right[index:index + 40]!r} ({context} bytes available)")
    return "files differ in trailing bytes"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline production validation for the Open Energy Data Layer repo.")
    parser.add_argument("--check-page", action="store_true",
                        help="rebuild the page in a temp tree and compare to the "
                             "committed file (detects stale/deterministic output)")
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as failures")
    parser.add_argument("--verbose", action="store_true",
                        help="show details for passing checks too (default: same)")
    parser.add_argument("--timeout", type=int, default=180,
                        help="builder timeout in seconds for --check-page")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    report = Report()
    ctx: dict = {}
    started = time.time()
    steps = [
        ("1/8 required files", check_required_files),
        ("2/8 seed payload", check_payload),
        ("3/8 seed CSVs", check_csvs),
        ("4/8 geometry", check_geo),
        ("5/8 page static contract", check_page),
        ("6/8 service areas & provider lens", check_service_areas),
        ("7/8 documentation site", check_docs),
        ("8/8 OpenAPI contract", check_openapi),
        ("9/9 static JSON API", check_static_api),
        ("10/10 packaging & hygiene", check_packaging),
    ]
    for label, step in steps:
        try:
            step(report, ctx)
        except Exception as exc:  # noqa: BLE001 - never crash half-way
            report.fail(label.split(" ", 1)[1], f"{label} completed",
                        f"{type(exc).__name__}: {exc}")
    if args.check_page:
        try:
            check_build(report, ctx, timeout=args.timeout)
        except Exception as exc:  # noqa: BLE001
            report.fail("deterministic build", "rebuild completed",
                        f"{type(exc).__name__}: {exc}")

    warnings = report.counts["WARN"]
    failures = report.failed
    if args.strict and warnings:
        failures += warnings
    elapsed = time.time() - started

    print("=" * 78)
    print("Open Energy Data Layer - production validation")
    print(f"root:   {ROOT}")
    print("mode:   static" + (" + deterministic rebuild" if args.check_page else "")
          + (" (strict)" if args.strict else ""))
    print("=" * 78)
    for line in report.render(args.verbose):
        print(line)
    print()
    print("-" * 78)
    print(f"summary: {report.counts['PASS']} passed, {report.counts['FAIL']} failed, "
          f"{report.counts['WARN']} warnings, {report.counts['SKIP']} skipped "
          f"({elapsed:.2f}s)")
    if ctx.get("build_seconds"):
        print(f"deterministic rebuild took {ctx['build_seconds']}s")
    if failures:
        print()
        print("FAILURES")
        for group, entries in report.groups.items():
            for status, name, detail in entries:
                if status == "FAIL":
                    print(f"  - [{group}] {name}" + (f": {detail}" if detail else ""))
        if args.strict:
            for group, entries in report.groups.items():
                for status, name, detail in entries:
                    if status == "WARN":
                        print(f"  - [{group}] WARNING (strict): {name}"
                              + (f": {detail}" if detail else ""))
        print()
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
