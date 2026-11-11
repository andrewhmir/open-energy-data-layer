#!/usr/bin/env python3
"""Build the static documentation site for the Open Energy Data Layer.

Renders every markdown/text document in the repository into a styled, static HTML
site under draft/docs/, in the same BetterGovPH open-data design language as the
product page (tools/build-map-page.py): Figtree / Inter / JetBrains Mono, BetterGov
blue, white paper, rule tables, masthead + footer, official emblem.

Two runs produce byte-identical output (no build timestamps; sources are read in a
fixed order and assets are copied verbatim). Pages link only same-origin assets, so
the site works from file:// and from any static host, with no third-party requests.

Usage:
    python3 tools/build-docs.py

Output: draft/docs/
  index.html                     landing page (grouped cards)
  <doc>.html                     one page per source document
  assets/docs.css, docs.js       shared styles/behaviour (docs.js carries the
                                 deterministically generated full-text search
                                 index: page titles, headings and section
                                 snippets, inlined so the site stays
                                 self-contained and works from file://)
  assets/fonts/*.woff2           OFL webfont subsets (copied)
  assets/emblem.svg, favicon.svg BetterGov marks (copied)
  docs-manifest.json             machine-readable page/source registry
"""
from __future__ import annotations

import html
import json
import os
import posixpath
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from markdown_it import MarkdownIt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "draft", "docs")
ASSETS = os.path.join(OUT, "assets")
SRC_ASSETS = os.path.join(ROOT, "draft", "assets")
PAGE_DATA = os.path.join(ROOT, "data", "seed", "page-data.json")

MD = MarkdownIt("commonmark", {"html": True}).enable("table")

esc = lambda s: html.escape(str(s), quote=False)
esc_attr = lambda s: html.escape(str(s), quote=True)

# ---------------------------------------------------------------------------
# Design system icons (inline SVG; same set as the product page)
# ---------------------------------------------------------------------------
ICON_FALLBACK = {
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "external-link": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/>'
                     '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    "copy": '<rect width="13" height="13" x="9" y="9" rx="2"/>'
            '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "arrow-up": '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>',
    "chevron-right": '<path d="m9 6 6 6-6 6"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "book-open-text": '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 '
                      '4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/>'
                '<path d="M12 15V3"/>',
    "film": "",
}
ICONS: Dict[str, str] = {}


def load_icons() -> None:
    path = os.path.join(SRC_ASSETS, "brand", "icons.json")
    if not os.path.exists(path):
        return
    try:
        data = json.loads(read_text(path))
        for name, spec in (data.get("icons") or {}).items():
            ICONS[name] = spec.get("body", "") if isinstance(spec, dict) else str(spec)
    except (ValueError, OSError):
        pass


def icon(name: str, cls: str = "i", label: str | None = None) -> str:
    body = ICONS.get(name) or ICON_FALLBACK.get(name) or ""
    if not body:
        return ""
    aria = (f' aria-label="{esc_attr(label)}" role="img"'
            if label else ' aria-hidden="true" focusable="false"')
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"{aria}>{body}</svg>')


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def human_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n} B"


def plain_text(markup: str) -> str:
    text = re.sub(r"<[^>]+>", "", markup)
    return html.unescape(text).replace("\u00a0", " ").strip()


def truncate(text: str, limit: int = 150) -> str:
    text = re.sub(r"\s+", " ", plain_text(text)).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",.;:")
    return cut + "\u2026"


def github_slug(text: str) -> str:
    """Approximate GitHub's heading anchor slug, used for stable in-page ids."""
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).strip().lower()
    out = []
    for ch in text:
        if ch == " ":
            out.append("-")
        elif ch in "-_":
            out.append(ch)
        elif ch.isalnum() or unicodedata.category(ch).startswith("M"):
            out.append(ch)
        # every other character (punctuation, em dashes, ...) is dropped
    return "".join(out)


# ---------------------------------------------------------------------------
# Registry: every document that becomes a page
# ---------------------------------------------------------------------------
@dataclass
class Doc:
    id: str
    path: str                  # repo-relative POSIX path
    group: str
    label: str
    summary: str
    kind: str = "markdown"     # "markdown" | "plain"
    html_name: str = ""
    lines: int = 0
    size: int = 0
    words: int = 0
    title_html: str = ""       # rendered inner HTML of the page h1
    title_text: str = ""
    title_id: str = ""
    order: int = 0
    headings: List[Tuple[str, str, str]] = field(default_factory=list)  # (level, id, label)
    raw_html: str = ""         # rendered, pre-link-processing HTML body
    content: str = ""          # final processed HTML body


GROUP_DEFS = [
    ("overview", "Overview", "What the project is, how it is organised, and how to start."),
    ("architecture", "Architecture",
     "How the frontend, the data pipeline and the generated artefacts fit together, "
     "with a component map for contributors and agents."),
    ("data", "Data", "The schema, the published seed data and the design-asset provenance."),
    ("api", "API", "The read-only JSON API: access, conventions and endpoint reference."),
    ("project", "Project", "Delivery notes, testing, contribution and release history."),
    ("research", "Research", "The evidence base and design research behind the data layer."),
    ("legal", "Legal", "Licensing, third-party notices and the security policy."),
]

KNOWN_DOCS = [
    dict(id="readme", path="README.md", group="overview", label="Project README",
         summary="Project overview: what it does, the dataset at a glance, quickstart, "
                 "repository layout, quality checks and licensing."),
    dict(id="frontend", path="draft/frontend.md", group="architecture",
         label="Frontend architecture",
         summary="The three browser-facing surfaces and how they are built: build-time data "
                 "injection, design tokens, runtime JS modules, state and deep links, docs-site "
                 "search, review-pack separation, and the pinned QA contracts."),
    dict(id="backend", path="draft/backend.md", group="architecture",
         label="Backend & pipeline architecture",
         summary="The deterministic static-artifact pipeline: source snapshots and hashes, "
                 "ingest and validation, service areas, geometry, the static JSON API, the "
                 "page/docs/preview builders, determinism and failure modes."),
    dict(id="component-map", path="draft/component-map.md", group="architecture",
         label="Component map & agent guide",
         summary="Where every component lives, what to edit versus regenerate, the build-order "
                 "graph, task routing, the agent entry points (AGENTS.md) and the cross-cutting "
                 "invariants."),
    dict(id="data-model", path="draft/data-model.md", group="data", label="Data model",
         summary="Canonical entities, PSGC geography and utility IDs, the provenance "
                 "backbone, publication states, versioning and licensing policy."),
    dict(id="data-seed", path="data/seed/README.md", group="data", label="Seed data dictionary",
         summary="Column-by-column documentation for the published dataset and its "
                 "17-check validation report."),
    dict(id="coverage-method", path="research/coverage/README.md", group="data",
         label="Service-area extraction",
         summary="How the LGU-level franchise footprints behind the provider lens were "
                 "extracted, matched to PSGC codes, cross-checked and licensed."),
    dict(id="assets", path="draft/assets/README.md", group="data", label="Design assets",
         summary="Fonts, emblem, icons, favicon, social card and region geometry: sources, "
                 "licences and regeneration commands."),
    dict(id="brand-assets", path="draft/assets/brand/README.md", group="data", label="Brand & UI assets",
         summary="Official BetterGov.ph marks, the derived favicon, and the pinned Lucide "
                 "icon sprite with per-icon provenance."),
    dict(id="api-docs", path="draft/api-docs.md", group="api", label="API guide",
         summary="The static JSON API: base URL and access, datasets and units, conventions, "
                 "endpoint reference, attribution, disclaimers and versioning."),
    dict(id="contributing", path="CONTRIBUTING.md", group="project", label="Contributing",
         summary="Development setup, build commands, the data and page rules, and the "
                 "pull-request checklist."),
    dict(id="changelog", path="CHANGELOG.md", group="project", label="Changelog",
         summary="Notable changes, following Keep a Changelog; pre-release status and "
                 "known limitations."),
    dict(id="tests", path="tests/README.md", group="project", label="Testing & validation",
         summary="Static validation, deterministic rebuilds and browser QA: how to run them, "
                 "what they prove and what CI enforces."),
    dict(id="notice", path="NOTICE.md", group="legal", label="Notices & attribution",
         summary="Third-party components, brand usage, fonts, icons, geometry and the "
                 "licence status of the DOE workbook data."),
    dict(id="license", path="LICENSE", group="legal", label="Licence (MIT)", kind="plain",
         summary="The MIT licence for the project's code, page and design layer, plus the "
                 "scope of third-party terms."),
    dict(id="security", path="SECURITY.md", group="legal", label="Security policy",
         summary="The static-site threat model, data-integrity reporting and the private "
                 "vulnerability-disclosure process."),
]

RESEARCH_LABELS = {
    "data-landscape": "Data landscape",
    "api-landscape": "API landscape",
    "api-docs-conventions": "API docs conventions",
    "service-areas": "Service areas",
}

# Submission material, deliberately excluded from the data-platform docs: the
# pitch-deck notes belong to the fellowship submission pack, not the product
# documentation site (see plan/ui-separation-brief.md).
SUBMISSION_RESEARCH = {"pitch-deck-notes.md"}


def build_registry() -> List[Doc]:
    docs = [Doc(id=d["id"], path=d["path"], group=d["group"], label=d["label"],
                summary=d["summary"], kind=d.get("kind", "markdown"), order=index)
            for index, d in enumerate(KNOWN_DOCS)]
    research_dir = os.path.join(ROOT, "research")
    if os.path.isdir(research_dir):
        for order, name in enumerate(sorted(os.listdir(research_dir))):
            if not name.endswith(".md") or name in SUBMISSION_RESEARCH:
                continue
            rel = "research/" + name
            stem = name[:-3]
            label = RESEARCH_LABELS.get(stem.lower())
            if not label:
                label = stem.replace("-", " ").replace("_", " ").strip().capitalize()
            docs.append(Doc(id="research-" + stem, path=rel, group="research",
                            label="Research: " + label, summary="", order=1000 + order))
    for doc in docs:
        doc.html_name = doc.id + ".html"
    return docs


# Fragment resolution is filled after the first render pass.
FRAGMENT_MAPS: Dict[str, Dict[str, str]] = {}


def map_fragment(doc_path: str, fragment: str) -> str:
    if not fragment:
        return ""
    mapping = FRAGMENT_MAPS.get(doc_path, {})
    key = fragment.lower()
    if key in mapping:
        return mapping[key]
    candidate = github_slug(fragment)
    if candidate in mapping:
        return mapping[candidate]
    return fragment


# ---------------------------------------------------------------------------
# Markdown rendering — pass one (headings, title, stats) then pass two (links)
# ---------------------------------------------------------------------------
HEADING_RE = re.compile(r"<h([1-6])>(.*?)</h\1>", re.S)


def render_first_pass(doc: Doc, text: str) -> None:
    rendered = MD.render(text)
    title_html, title_id = "", ""
    match = re.search(r"<h1>(.*?)</h1>", rendered, re.S)
    if match:
        title_html = match.group(1).strip()
        rendered = rendered[:match.start()] + rendered[match.end():]
        title_id = github_slug(title_html)
    seen: Dict[str, int] = {}
    headings: List[Tuple[str, str, str]] = []
    fragment_map: Dict[str, str] = {}

    def repl(m: re.Match) -> str:
        level, inner = m.group(1), m.group(2)
        base = github_slug(inner) or "section"
        count = seen.get(base, 0)
        seen[base] = count + 1
        slug = base if count == 0 else f"{base}-{count}"
        label = plain_text(inner)
        headings.append((level, slug, label))
        fragment_map[github_slug(label)] = slug
        fragment_map[slug] = slug
        fragment_map.setdefault(label.lower(), slug)
        return f'<h{level} id="{slug}">{inner}</h{level}>'

    rendered = HEADING_RE.sub(repl, rendered)
    if not title_html:
        # Plain-text docs and docs without an h1: use the registry label.
        title_text = doc.label
        title_id = github_slug(title_text)
    else:
        title_text = plain_text(title_html)
    if title_id:
        fragment_map.setdefault(github_slug(title_text), title_id)
        fragment_map.setdefault(title_id, title_id)
    doc.title_html = title_html
    doc.title_text = title_text
    doc.title_id = title_id
    doc.headings = [h for h in headings if h[0] in ("2", "3")]
    doc.raw_html = rendered
    FRAGMENT_MAPS[doc.path] = fragment_map


# ---------------------------------------------------------------------------
# Link resolution
# ---------------------------------------------------------------------------
UNRESOLVED: List[Tuple[str, str]] = []


def resolve_link(href: str, doc: Doc, docs_by_path: Dict[str, Doc]) -> Tuple[str, str]:
    """Return (href, kind) where kind is anchor|external|mailto|data|internal|raw."""
    if not href:
        return href, "internal"
    if href.startswith(("http://", "https://", "//")):
        return href, "external"
    if href.startswith("mailto:"):
        return href, "mailto"
    if href.startswith("data:"):
        return href, "data"
    if href.startswith("#"):
        return "#" + map_fragment(doc.path, href[1:]), "anchor"

    path_part, _, frag = href.partition("#")
    path_part = path_part.strip()
    if not path_part:
        return ("#" + map_fragment(doc.path, frag), "anchor")

    if path_part.startswith("/"):
        target = posixpath.normpath(path_part.lstrip("/"))
    else:
        target = posixpath.normpath(posixpath.join(posixpath.dirname(doc.path), path_part))
    target = target.rstrip("/")
    if target in ("", ".", ".."):
        return "index.html" if path_part in ("..", ".") else ("#" + map_fragment(doc.path, frag)), "internal"

    # 1. A registered document.
    if target in docs_by_path:
        target_doc = docs_by_path[target]
        fragment = map_fragment(target_doc.path, frag) if frag else ""
        return target_doc.html_name + (f"#{fragment}" if fragment else ""), "internal"

    # 2. The product page lives one level up from the docs site.
    if target == "draft/map-table-prototype.html":
        return "../map-table-prototype.html" + (f"#{map_fragment('draft/map-table-prototype.html', frag)}" if frag else ""), "internal"

    # 3. Directories that are best represented by a documentation page.
    DIR_PAGE_MAP = {
        "draft/api": "api-docs.html",
        "draft/api/v1": "api-docs.html",
        "draft/docs": "index.html",
    }
    if target in DIR_PAGE_MAP:
        return DIR_PAGE_MAP[target], "internal"

    # 4. A directory: point at its README page when one is registered.
    if os.path.isdir(os.path.join(ROOT, target)):
        readme = posixpath.join(target, "README.md") if target != "." else "README.md"
        if readme in docs_by_path:
            target_doc = docs_by_path[readme]
            fragment = map_fragment(target_doc.path, frag) if frag else ""
            return target_doc.html_name + (f"#{fragment}" if fragment else ""), "internal"
        if target == "plan":
            return "index.html#group-project", "internal"
        if target == "research":
            return "index.html#group-research", "internal"
        if target.startswith("draft/docs"):
            return "index.html", "internal"
        return "../../" + target + "/", "raw"

    # 5. A file in the repository (download / raw asset).
    if os.path.isfile(os.path.join(ROOT, target)):
        return "../../" + target, "raw"

    UNRESOLVED.append((doc.path, href))
    return href, "unresolved"


def rewrite_links(markup: str, doc: Doc, docs_by_path: Dict[str, Doc]) -> str:
    def href_repl(match: re.Match) -> str:
        new_href, _kind = resolve_link(match.group(2), doc, docs_by_path)
        return f'{match.group(1)}="{esc_attr(new_href)}"'

    markup = re.sub(r'(href|src)="([^"]*)"', href_repl, markup)

    def anchor_repl(match: re.Match) -> str:
        attrs, inner = match.group(1), match.group(2)
        if "href=\"http" in attrs and "target=" not in attrs:
            attrs += ' target="_blank" rel="noopener"'
        icon_html = (f'<span class="ext-icon" aria-hidden="true">{icon("external-link")}</span>'
                     if 'href="http' in attrs else "")
        return f"<a{attrs}>{inner}{icon_html}</a>"

    return re.sub(r"<a([^>]*)>(.*?)</a>", anchor_repl, markup, flags=re.S)


# ---------------------------------------------------------------------------
# Content transforms: code blocks, tables, callouts, task lists, heading links
# ---------------------------------------------------------------------------
CODE_RE = re.compile(r'<pre><code(?: class="language-([^"]*)")?>(.*?)</code></pre>', re.S)
TABLE_RE = re.compile(r"<table>(.*?)</table>", re.S)
QUOTE_RE = re.compile(r"<blockquote>(.*?)</blockquote>", re.S)
TASK_RE = re.compile(r"<li>\[([ xX])\] ")
CALLOUT_KINDS = ("note", "tip", "important", "warning", "caution", "todo", "data note", "summary")


def transform_body(markup: str) -> str:
    def code_repl(m: re.Match) -> str:
        lang = (m.group(1) or "").strip()
        code = m.group(2)
        return (
            '<div class="code-block">'
            '<div class="code-head"><span class="code-lang">' + esc(lang or "text") + "</span>"
            '<button type="button" class="copy-btn" data-copy aria-label="Copy code to clipboard">'
            + icon("copy") + "<span>Copy</span></button></div>"
            '<pre><code class="language-' + esc_attr(lang or "text") + '">' + code + "</code></pre></div>"
        )

    markup = CODE_RE.sub(code_repl, markup)
    markup = TABLE_RE.sub(lambda m: f'<div class="table-scroll"><table>{m.group(1)}</table></div>', markup)

    def quote_repl(m: re.Match) -> str:
        inner = m.group(1).strip()
        first_p = re.search(r"<p>(.*?)</p>", inner, re.S)
        kind = None
        if first_p:
            text = plain_text(first_p.group(1))
            low = text.lower()
            for candidate in CALLOUT_KINDS:
                if low.startswith(candidate):
                    kind = candidate
                    break
        cls = "callout callout-" + kind.replace(" ", "-") if kind else "callout callout-note"
        label = (f'<span class="callout-label">{esc(kind.upper())}</span>'
                 if kind else '<span class="callout-label">NOTE</span>')
        return f'<div class="{cls}">{label}<div class="callout-body">{inner}</div></div>'

    markup = QUOTE_RE.sub(quote_repl, markup)
    markup = TASK_RE.sub(
        lambda m: ('<li class="task-item"><span class="task-box done" aria-hidden="true">'
                   + icon("check") + '</span> ' if m.group(1).lower() == "x"
                   else '<li class="task-item"><span class="task-box" aria-hidden="true"></span> '),
        markup)
    return markup


def heading_anchors(markup: str) -> str:
    """Add a visible-on-hover '#'' anchor link to every rendered heading."""
    def repl(m: re.Match) -> str:
        level, attrs, inner = m.group(1), m.group(2), m.group(3)
        id_m = re.search(r'id="([^"]+)"', attrs or "")
        heading_id = id_m.group(1) if id_m else ""
        anchor = (f'<a class="h-anchor" href="#{esc_attr(heading_id)}" '
                  f'aria-label="Link to this section" tabindex="-1">#</a>') if heading_id else ""
        cls = ' class="has-anchor"' if heading_id else ""
        return f"<h{level}{cls}{attrs or ''}>{inner}{anchor}</h{level}>"

    return re.sub(r"<h([2-6])([^>]*)>(.*?)</h\1>", repl, markup, flags=re.S)


# ---------------------------------------------------------------------------
# Full-text search index (built from the Doc objects, inlined into docs.js)
# ---------------------------------------------------------------------------
SEARCH_TEXT_LIMIT = 340
SEARCH_HEADING_LIMIT = 120
SECTION_SPLIT_RE = re.compile(r'<h([23]) id="([^"]+)">(.*?)</h\1>', re.S)


def clean_index_text(text: str, limit: int = SEARCH_TEXT_LIMIT) -> str:
    """Collapse whitespace and cut to a word boundary without lossy HTML parsing."""
    text = html.unescape(text).replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    if space > limit * 0.6:
        cut = cut[:space]
    return cut.rstrip(" ,.;:-\u2013\u2014") + "\u2026"


def index_text(markup: str, limit: int = SEARCH_TEXT_LIMIT) -> str:
    """Plain text for the search index: drop code blocks and tags, keep prose/table text."""
    text = re.sub(r"<pre\b[^>]*>.*?</pre>", " ", markup, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return clean_index_text(text, limit)


def doc_search_sections(doc: Doc) -> List[List[str]]:
    """Return [[fragment, heading label, snippet], ...] for one document.

    The page summary and any preamble before the first h2 become the opening
    "Overview" entry; every h2/h3 starts a new section. Snippets are capped so
    the whole index stays small enough to inline in the shared script.
    """
    sections: List[List[str]] = []
    if doc.kind == "plain":
        body = clean_index_text(doc.raw_text)
        overview = clean_index_text(" ".join(p for p in (doc.summary, body) if p))
        if overview:
            sections.append(["", "Overview", overview])
        return sections

    markup = doc.raw_html
    matches = list(SECTION_SPLIT_RE.finditer(markup))
    intro_end = matches[0].start() if matches else len(markup)
    overview = clean_index_text(" ".join(
        part for part in (doc.summary.strip(), index_text(markup[:intro_end])) if part))
    if overview:
        sections.append(["", "Overview", overview])
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(markup)
        heading = clean_index_text(plain_text(match.group(3)), SEARCH_HEADING_LIMIT) or "Section"
        body = index_text(markup[match.end():end])
        if body:
            sections.append([match.group(2), heading, body])
    return sections


def build_search_index(docs: List[Doc]) -> Dict[str, object]:
    """Deterministic index: pages in registry order, sections in document order."""
    pages: List[Dict[str, object]] = []
    for doc in docs:
        page: Dict[str, object] = {
            "h": doc.html_name,
            "d": doc.label,
            "g": group_label(doc.group),
            "s": doc_search_sections(doc),
        }
        title = clean_index_text(doc.title_text, SEARCH_HEADING_LIMIT)
        if title and title != doc.label:
            page["t"] = title
        pages.append(page)
    return {"version": 1, "pages": pages}


def serialize_search_index(index: Dict[str, object]) -> str:
    """Compact JSON safe to embed as a JS expression (U+2028/U+2029 escaped)."""
    payload = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    return payload.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def search_index_stats(index: Dict[str, object], payload: str) -> Dict[str, int]:
    pages = index.get("pages") or []
    return {
        "pages": len(pages),
        "sections": sum(len(page.get("s") or []) for page in pages),
        "bytes": len(payload.encode("utf-8")),
    }


# ---------------------------------------------------------------------------
# Site data (dataset facts shown in the shell)
# ---------------------------------------------------------------------------
def load_site_facts() -> Dict[str, object]:
    try:
        payload = json.loads(read_text(PAGE_DATA))
    except (OSError, ValueError):
        return {"dataset_version": "", "latest_month": "", "utilities": 0,
                "regions": 0, "checks": 0, "checks_ok": 0}
    checks = payload.get("validation") or []
    months = (payload.get("build") or {}).get("months") or []
    latest = (payload.get("build") or {}).get("latest_month") or ""
    published = len(months[:months.index(latest) + 1]) if latest in months else len(months)
    api_counts = {}
    try:
        api_index = json.loads(read_text(os.path.join(ROOT, "draft", "api", "v1", "index.json")))
        api_counts = api_index.get("counts") or {}
    except (OSError, ValueError):
        pass
    coverage = (payload.get("coverage") or {}).get("stats") or {}
    return {
        "dataset_version": (payload.get("build") or {}).get("dataset_version", ""),
        "latest_month": latest,
        "utilities": len(payload.get("utilities") or []),
        "regions": len(payload.get("regions") or []),
        "months": published,
        "checks": len(checks),
        "checks_ok": sum(1 for c in checks if c.get("ok")),
        "api_endpoints": api_counts.get("endpoints", 0),
        "coverage_utilities": coverage.get("utilities_with_lgu_coverage", 0),
        "coverage_lgus": coverage.get("distinct_lgus", 0),
    }


SITE = load_site_facts()
SITE_TITLE = "Open Energy Data Layer — documentation"
DATA_PAGE = "../map-table-prototype.html"
API_INDEX = "../../draft/api/v1/index.json"
OPENAPI = "../../draft/openapi.yaml"
BETTERGOV = "https://bettergov.ph"


# ---------------------------------------------------------------------------
# HTML shell
# ---------------------------------------------------------------------------
def group_label(key: str) -> str:
    for gid, label, _blurb in GROUP_DEFS:
        if gid == key:
            return label
    return key.title()


def group_blurb(key: str) -> str:
    for gid, _label, blurb in GROUP_DEFS:
        if gid == key:
            return blurb
    return ""


def sidebar_html(docs: List[Doc], active_id: str) -> str:
    parts = ['<nav id="doc-nav" class="doc-nav" aria-label="Documentation">',
             '<a class="nav-home' + (' current' if active_id == "index" else "") + '"'
             ' href="index.html"' + (' aria-current="page"' if active_id == "index" else "") + ">"
             '<span class="nav-home-title">Documentation home</span>'
             '<span class="nav-home-sub">' + str(len(docs)) + " pages</span></a>"]
    for gid, label, _blurb in GROUP_DEFS:
        group_docs = [d for d in docs if d.group == gid]
        if not group_docs:
            continue
        parts.append(f'<div class="nav-group" data-group="{gid}">')
        parts.append(f'<p class="nav-group-title" id="group-nav-{gid}">{esc(label)}</p>')
        parts.append('<ul role="list">')
        for doc in group_docs:
            current = doc.id == active_id
            meta = f"{doc.lines:,} lines" if doc.kind == "markdown" else "plain text"
            parts.append(
                f'<li><a href="{doc.html_name}"'
                + (' class="current" aria-current="page"' if current else "")
                + f' data-title="{esc_attr(doc.label)}"><span class="nav-doc-title">{esc(doc.label)}</span>'
                + f'<span class="nav-doc-meta">{esc(meta)}</span></a></li>')
        parts.append("</ul></div>")
    parts.append("</nav>")
    return "".join(parts)


def toc_html(doc: Doc) -> str:
    headings = doc.headings
    if len(headings) < 2:
        return ('<aside class="docs-toc" aria-label="On this page">'
                '<div class="toc-card"><p class="label">On this page</p>'
                '<p class="toc-empty">This document has no sub-sections.</p></div></aside>')
    items = "".join(
        f'<a class="toc-link{" l3" if level == "3" else ""}" href="#{esc_attr(slug)}">{esc(label)}</a>'
        for level, slug, label in headings)
    return ('<aside class="docs-toc" aria-label="On this page">'
            '<div class="toc-card"><p class="label">On this page</p>'
            f'<nav class="toc-nav">{items}</nav></div></aside>')


def masthead_html() -> str:
    return f"""
<header class="masthead">
  <div class="masthead-top">
    <div class="page masthead-top-inner">
      <span class="muted">Documentation &middot; dataset {esc(str(SITE["dataset_version"]))}</span>
      <span class="masthead-links">
        <a href="{DATA_PAGE}">Data page</a>
        <a href="{API_INDEX}">API index</a>
        <a href="{BETTERGOV}" target="_blank" rel="noopener">BetterGov.ph
          <span class="ext-icon" aria-hidden="true">{icon("external-link")}</span></a>
      </span>
    </div>
  </div>
  <div class="page masthead-main">
    <a class="masthead-title" href="index.html">
      <img class="masthead-mark" src="assets/emblem.svg" width="44" height="44"
           alt="" aria-hidden="true">
      <span>
        <span class="masthead-kicker">BetterGov.ph &middot; open energy data &middot; docs</span>
        <span class="masthead-name">Philippine electricity rates</span>
      </span>
    </a>
    <div class="masthead-with">
      <span class="label">Documentation</span>
      <a href="index.html">All docs &amp; guides</a>
    </div>
  </div>
</header>
<nav class="subnav" aria-label="Site sections">
  <div class="page subnav-inner">
    <button class="docs-menu-btn" type="button" id="docs-menu-btn"
            aria-expanded="false" aria-controls="docs-sidebar">
      {icon("menu")}<span>Docs menu</span>
    </button>
    <a href="index.html">Docs home</a>
    <a href="readme.html">README</a>
    <a href="api-docs.html">API guide</a>
    <a href="{DATA_PAGE}">Data page</a>
    <a href="{API_INDEX}">JSON API</a>
    <span class="subnav-right">
      <span class="subnav-meta">Dataset {esc(str(SITE["dataset_version"]))}</span>
      <button class="search-open" type="button" id="docs-search-open"
              aria-haspopup="dialog" aria-controls="docs-search-dialog"
              aria-keyshortcuts="Control+K Meta+K">
        {icon("search")}<span class="search-open-label">Search docs</span>
        <kbd class="search-open-kbd">Ctrl K</kbd>
      </button>
    </span>
  </div>
</nav>"""


def footer_html() -> str:
    return f"""
<footer class="footer">
  <div class="page footer-inner">
    <div class="footer-grid">
      <div class="footer-col footer-brand">
        <p class="footer-kicker">Open energy data layer</p>
        <p>Research-grounded documentation for Philippine electricity-rate data:
        a national map, a comparable price table and a public JSON API over the
        Department of Energy's public workbook.</p>
        <p class="footer-cite">Source: Department of Energy &mdash; Electricity Rates &amp;
        Power Market Monitor &middot; dataset {esc(str(SITE["dataset_version"]))} &middot;
        {esc(str(SITE["checks_ok"]))}/{esc(str(SITE["checks"]))} validation checks passing.</p>
      </div>
      <div class="footer-col">
        <h2>Documentation</h2>
        <a href="readme.html">Project README</a>
        <a href="data-model.html">Data model</a>
        <a href="api-docs.html">API guide</a>
        <a href="tests.html">Testing &amp; validation</a>
        <a href="contributing.html">Contributing</a>
      </div>
      <div class="footer-col">
        <h2>The product</h2>
        <a href="{DATA_PAGE}">Data page (map, table, API)</a>
        <a href="api-docs.html">API reference</a>
        <a href="{OPENAPI}">OpenAPI 3.1 contract</a>
        <a href="{API_INDEX}">JSON API index</a>
        <a href="data-seed.html">Seed data dictionary</a>
      </div>
      <div class="footer-col">
        <h2>Project &amp; legal</h2>
        <a href="notice.html">Notices &amp; attribution</a>
        <a href="license.html">Licence (MIT)</a>
        <a href="security.html">Security policy</a>
        <a href="{BETTERGOV}" target="_blank" rel="noopener">BetterGov.ph
          <span class="ext-icon" aria-hidden="true">{icon("external-link")}</span></a>
      </div>
    </div>
    <p class="footer-note">An independent open-source project: not an official DOE or
    BetterGov.ph publication, and not financial advice. Rates are the values published in
    the DOE workbook, with no imputation; the workbook's reuse terms are not yet confirmed.</p>
    <div class="footer-legal">
      <span>&copy; 2026 Open Energy Data Layer contributors</span>
      <span>Design: BetterGov.ph open-data language (MIT)</span>
      <span>Figtree / Inter / JetBrains Mono &middot; OFL 1.1</span>
    </div>
  </div>
</footer>
<button id="to-top" type="button" aria-label="Back to top">{icon("arrow-up")}</button>"""


def search_dialog_html() -> str:
    """The full-text search overlay, present on every page (native modal dialog).

    All ids live in this dialog only; the sidebar's own filter keeps its
    ``doc-search*`` ids so nothing collides. Results are rendered client-side
    from the index inlined in assets/docs.js.
    """
    return f"""
<dialog class="search-dialog" id="docs-search-dialog" aria-modal="true"
        aria-labelledby="docs-search-title">
  <div class="search-dialog-panel">
    <div class="search-dialog-head">
      <h2 class="search-dialog-title" id="docs-search-title">Search the documentation</h2>
      <button class="search-dialog-close" id="docs-search-close" type="button"
              aria-label="Close search" data-search-close>
        <kbd>Esc</kbd>{icon("x")}
      </button>
    </div>
    <div class="search-dialog-field">
      {icon("search")}
      <input class="search-dialog-input" id="docs-search-input" type="search"
             placeholder="Search titles, headings and section text&hellip;"
             autocomplete="off" spellcheck="false" role="combobox" aria-expanded="false"
             aria-controls="docs-search-results" aria-autocomplete="list"
             aria-describedby="docs-search-status">
    </div>
    <p class="search-dialog-status" id="docs-search-status" role="status" aria-live="polite"></p>
    <div class="search-dialog-results" id="docs-search-results" role="listbox"
         aria-label="Documentation search results"></div>
    <div class="search-dialog-foot" aria-hidden="true">
      <span><kbd>&uarr;</kbd><kbd>&darr;</kbd> navigate</span>
      <span><kbd>&crarr;</kbd> open</span>
      <span><kbd>Esc</kbd> close</span>
    </div>
  </div>
</dialog>"""


def page_html(title: str, description: str, body: str,
              sidebar: str, toc: str, active_id: str) -> str:
    hamburger = ('' if active_id == "index" else '')
    del hamburger
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#0b4fd9">
<title>{esc(title)}</title>
<meta name="description" content="{esc_attr(description)}">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="stylesheet" href="assets/docs.css">
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
{masthead_html()}
<div class="docs-shell page">
  <div class="sidebar-backdrop" id="sidebar-backdrop" hidden></div>
  <aside class="docs-sidebar" id="docs-sidebar" aria-label="Documentation navigation">
    <div class="sidebar-inner">
      <div class="sidebar-search">
        <label class="label" for="doc-search">Filter docs</label>
        <div class="search-field">
          {icon("search")}
          <input id="doc-search" type="search" placeholder="Filter documentation&hellip;"
                 autocomplete="off" spellcheck="false">
          <button type="button" class="search-clear" id="doc-search-clear" aria-label="Clear filter">{icon("x")}</button>
        </div>
        <p class="search-hint" id="doc-search-hint" aria-live="polite"></p>
      </div>
      {sidebar}
      <div class="sidebar-foot">
        <p class="label">Dataset</p>
        <p class="sidebar-dataset">{esc(str(SITE["dataset_version"]))} &middot;
          {esc(str(SITE["utilities"]))} utilities &middot; {esc(str(SITE["regions"]))} regions</p>
        <a href="{DATA_PAGE}">Open the data page {icon("chevron-right")}</a>
      </div>
    </div>
  </aside>
  <main class="docs-main" id="main">
    {body}
  </main>
  {toc}
</div>
{footer_html()}
{search_dialog_html()}
<script src="assets/docs.js" defer></script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Page bodies
# ---------------------------------------------------------------------------
def doc_meta_html(doc: Doc) -> str:
    bits = [f"<code>{esc(doc.path)}</code>",
            f"{doc.lines:,} lines",
            human_size(doc.size),
            f"{doc.words:,} words"]
    return " &middot; ".join(bits)


def pager_html(docs: List[Doc], active_id: str) -> str:
    order = [d.id for d in docs]
    if active_id not in order:
        return ""
    index = order.index(active_id)
    prev_doc = docs[index - 1] if index > 0 else None
    next_doc = docs[index + 1] if index < len(docs) - 1 else None
    left = (f'<a class="pager-link pager-prev" href="{prev_doc.html_name}">'
            f'<span class="label">Previous</span><span class="pager-title">&larr; {esc(prev_doc.label)}</span></a>'
            if prev_doc else '<span class="pager-spacer"></span>')
    right = (f'<a class="pager-link pager-next" href="{next_doc.html_name}">'
             f'<span class="label">Next</span><span class="pager-title">{esc(next_doc.label)} &rarr;</span></a>'
             if next_doc else '<span class="pager-spacer"></span>')
    return f'<nav class="pager" aria-label="Documentation pages">{left}{right}</nav>'


def render_doc_page(doc: Doc, docs: List[Doc], docs_by_path: Dict[str, Doc]) -> str:
    if doc.kind == "plain":
        title_html = f'<h1 id="{esc_attr(doc.title_id)}">{esc(doc.title_text)}</h1>'
        content = ('<p class="lede">The project\'s licence, reproduced in full. '
                   'The scope note at the end lists the third-party terms that this licence '
                   'does not override.</p>'
                   '<div class="plaintext-wrap"><pre class="plaintext">'
                   + esc(doc.raw_text) + "</pre></div>")
        doc.title_html = title_html
    else:
        title_html = (f'<h1 id="{esc_attr(doc.title_id)}">{doc.title_html}</h1>'
                      if doc.title_html else f'<h1 id="{esc_attr(doc.title_id)}">{esc(doc.title_text)}</h1>')
        content = doc.content
    crumb = (f'<nav class="crumbs" aria-label="Breadcrumb"><a href="index.html">Docs</a>'
             f'<span class="sep">/</span><a href="index.html#group-{esc_attr(doc.group)}">'
             f'{esc(group_label(doc.group))}</a><span class="sep">/</span>'
             f'<span aria-current="page">{esc(doc.label)}</span></nav>')
    body = f"""
{crumb}
<header class="doc-head">
  <p class="eyebrow">{esc(group_label(doc.group))} <span class="sep">&middot;</span> {esc(doc.kind if doc.kind == "plain" else "documentation")}</p>
  <h1 id="{esc_attr(doc.title_id)}">{doc.title_html if doc.kind != "plain" else esc(doc.title_text)}</h1>
  <div class="doc-meta-row">
    <p class="doc-meta">{doc_meta_html(doc)}</p>
    <div class="doc-actions">
      <a class="button button-quiet" href="../../{esc_attr(doc.path)}" download>Download raw</a>
      <a class="button button-quiet" href="index.html">All docs</a>
    </div>
  </div>
</header>
<article class="prose">
{content}
</article>
{pager_html(docs, doc.id)}"""
    sidebar = sidebar_html(docs, doc.id)
    toc = toc_html(doc)
    description = truncate(doc.summary or doc.title_text, 160)
    return page_html(f"{doc.label} — {SITE_TITLE}", description, body,
                     sidebar, toc, doc.id), sidebar


def render_index_page(docs: List[Doc], facts: Dict[str, object]) -> str:
    cards_by_group = []
    for gid, label, blurb in GROUP_DEFS:
        group_docs = [d for d in docs if d.group == gid]
        if not group_docs:
            continue
        cards = []
        for doc in group_docs:
            cards.append(
                f'<a class="doc-card" href="{doc.html_name}">'
                f'<span class="doc-card-group">{esc(label)}</span>'
                f'<span class="doc-card-title">{esc(doc.label)}</span>'
                f'<span class="doc-card-summary">{esc(truncate(doc.summary, 165))}</span>'
                f'<span class="doc-card-meta">{doc.lines:,} lines &middot; {human_size(doc.size)}</span>'
                f'<span class="doc-card-open">Open doc &rarr;</span></a>')
        cards_by_group.append(
            f'<section class="group-card-section" id="group-{gid}">'
            f'<div class="group-head"><h2>{esc(label)}</h2>'
            f'<p class="group-blurb">{esc(blurb)}</p>'
            f'<span class="group-count">{len(group_docs)} &middot; {"doc" if len(group_docs) == 1 else "docs"}</span></div>'
            f'<div class="doc-grid">{"".join(cards)}</div></section>')
    body = f"""
<section class="docs-hero">
  <p class="eyebrow">Open energy data layer <span class="sep">&middot;</span> bettergov.ph design
    <span class="sep">&middot;</span> dataset {esc(str(facts["dataset_version"]))}</p>
  <h1>Documentation</h1>
  <div class="lede">
    <p>Everything behind the <a href="{DATA_PAGE}">Philippine electricity-rates data page</a>:
    the data model and seed dictionary, the read-only JSON API, how the pipeline earns its
    numbers, the evidence base, and the licensing and security terms.</p>
  </div>
  <div class="hero-actions">
    <a class="button button-primary" href="readme.html">Start with the README {icon("book-open-text")}</a>
    <a class="button" href="api-docs.html">Read the API guide {icon("code-2")}</a>
    <a class="button button-quiet" href="data-model.html">Browse the data model {icon("database")}</a>
    <a class="button button-quiet" href="{DATA_PAGE}">Open the data page {icon("map")}</a>
  </div>
  <dl class="site-facts">
    <div><dt class="label">Documents</dt><dd class="fact">{len(docs)}</dd>
      <dd class="fact-sub">{len(docs) + 1} pages incl. this index &middot; {len(GROUP_DEFS)} groups</dd></div>
    <div><dt class="label">Utilities documented</dt><dd class="fact">{esc(str(facts["utilities"]))}</dd>
      <dd class="fact-sub">distribution utilities &amp; electric cooperatives</dd></div>
    <div><dt class="label">Regions</dt><dd class="fact">{esc(str(facts["regions"]))}</dd>
      <dd class="fact-sub">PSGC regions &middot; {esc(str(facts["months"]))} published months</dd></div>
    <div><dt class="label">Validation checks</dt><dd class="fact">{esc(str(facts["checks_ok"]))}/{esc(str(facts["checks"]))}</dd>
      <dd class="fact-sub">asserted on every ingest; a failure stops publication</dd></div>
  </dl>
</section>
<section class="quick-links" aria-label="Common entry points">
  <a class="quick-link" href="readme.html"><span class="label">Start here</span><strong>Project README</strong><span>What it is, dataset at a glance, quickstart</span></a>
  <a class="quick-link" href="data-seed.html"><span class="label">The data</span><strong>Seed dictionary</strong><span>Columns, states and the validation report</span></a>
  <a class="quick-link" href="api-docs.html"><span class="label">Consume it</span><strong>API guide</strong><span>{esc(str(SITE["api_endpoints"]))} static JSON endpoints, no key needed</span></a>
  <a class="quick-link" href="data-model.html"><span class="label">The model</span><strong>Data model</strong><span>Entities, IDs, provenance and publication states</span></a>
  <a class="quick-link" href="component-map.html"><span class="label">For contributors &amp; agents</span><strong>Component map</strong><span>Where to edit, what to run, and the invariants</span></a>
</section>
{''.join(cards_by_group)}"""
    sidebar = sidebar_html(docs, "index")
    toc = ('<aside class="docs-toc" aria-label="On this page"><div class="toc-card">'
           '<p class="label">This documentation site</p>'
           '<p class="toc-empty">Every page is generated from one markdown source, in the '
           'BetterGov.ph open-data design language. Use the filter to jump to a document, or '
           'press <kbd>Ctrl</kbd>&hairsp;+&hairsp;<kbd>K</kbd> / <kbd>/</kbd> for full-text '
           'search across every page.</p>'
           f'<p class="toc-empty"><a href="{DATA_PAGE}">Open the data page &rarr;</a></p>'
           "</div></aside>")
    description = ("Production documentation for the Open Energy Data Layer: data model, seed data, "
                   "API guide, testing, research and licensing.")
    return page_html(SITE_TITLE, description, body, sidebar, toc, "index")


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------
def docs_css() -> str:
    return r"""/* Open Energy Data Layer — documentation UI.
   Design language: budget.bettergov.ph / BetterGovPH transparency-portal (MIT). */
@font-face{font-family:Figtree;font-style:normal;font-weight:300 900;font-display:swap;
  src:url(fonts/figtree-normal-latin.woff2) format('woff2')}
@font-face{font-family:Inter;font-style:normal;font-weight:100 900;font-display:swap;
  src:url(fonts/inter-normal-latin.woff2) format('woff2')}
@font-face{font-family:'JetBrains Mono';font-style:normal;font-weight:100 800;font-display:swap;
  src:url(fonts/jetbrains-mono-normal-latin.woff2) format('woff2')}
:root{
  --paper:#ffffff;--paper-2:#f4f7fc;--paper-3:#eceef2;
  --rule:#d4d8e0;--rule-soft:#e7eaef;
  --ink:#11151c;--ink-2:#2b3340;--ink-3:#5b6373;--ink-mute:#8a92a1;
  --accent:#0b4fd9;--accent-deep:#0a44bd;--accent-soft:#e8efff;
  --positive:#3a6b3a;--negative:#b8341f;--gold:#8a6d1f;
  --font-hero:Figtree,"Manrope",-apple-system,BlinkMacSystemFont,sans-serif;
  --font-body:Inter,-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif;
  --font-mono:"JetBrains Mono",ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --page:1400px;--gutter:32px;
}
*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 var(--font-body);
  font-feature-settings:"ss01","cv11","tnum";-webkit-font-smoothing:antialiased}
img{max-width:100%}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:3px}
a:hover{color:var(--accent-deep)}
button,input,select{font:inherit;color:inherit}
button{cursor:pointer;background:none;border:0}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
h1,h2,h3,h4{font-family:var(--font-hero);font-weight:700;letter-spacing:-.02em;line-height:1.14;margin:0}
.skip-link{position:absolute;left:12px;top:-60px;z-index:300;background:var(--accent);color:#fff;
  padding:10px 14px;text-decoration:none;font-weight:600}
.skip-link:focus{top:8px}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
  clip:rect(0,0,0,0);white-space:nowrap;border:0}
.page{width:100%;max-width:var(--page);margin:0 auto;padding:0 var(--gutter)}
.label{font-family:var(--font-mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--ink-3);margin:0}
.eyebrow{font-family:var(--font-mono);font-size:11px;font-weight:500;letter-spacing:.16em;
  text-transform:uppercase;color:var(--accent);margin:0 0 10px}
.eyebrow .sep,.masthead .sep{color:var(--ink-mute);padding:0 6px}
.muted{color:var(--ink-3)}
.i{width:16px;height:16px;display:inline-block;vertical-align:text-bottom;flex:none}
.ext-icon{display:inline-flex;align-items:center;margin-left:4px;color:var(--ink-mute)}
.ext-icon .i{width:12px;height:12px}

/* masthead */
.masthead{background:var(--paper)}
.masthead-top{border-bottom:1px solid var(--rule-soft);font-family:var(--font-hero);
  font-size:12px;font-weight:600}
.masthead-top-inner{display:flex;justify-content:space-between;gap:16px;padding-top:8px;padding-bottom:8px}
.masthead-links{display:flex;gap:18px;flex-wrap:wrap;justify-content:flex-end}
.masthead-links a{color:var(--ink-2);text-decoration:none}
.masthead-links a:hover{color:var(--accent)}
.masthead-main{display:flex;align-items:center;justify-content:space-between;gap:24px;
  padding-top:18px;padding-bottom:16px}
.masthead-title{display:flex;align-items:center;gap:14px;color:var(--ink);text-decoration:none;min-width:0}
.masthead-title:hover{color:var(--ink)}
.masthead-mark{width:44px;height:44px;flex:none;display:block}
.masthead-kicker{display:block;font-family:var(--font-mono);font-size:10.5px;font-weight:500;
  letter-spacing:.18em;text-transform:uppercase;color:var(--accent);margin-bottom:5px}
.masthead-name{display:block;font-family:var(--font-hero);font-weight:700;font-size:26px;
  letter-spacing:-.025em;line-height:1.05}
.masthead-with{display:flex;flex-direction:column;align-items:flex-end;gap:3px;flex-shrink:0}
.masthead-with a{font-family:var(--font-hero);font-weight:600;font-size:14px;text-decoration:none}

/* subnav */
.subnav{background:var(--accent-deep);position:sticky;top:0;z-index:80}
.subnav-inner{display:flex;align-items:center;gap:24px;overflow-x:auto;scrollbar-width:none;min-height:46px}
.subnav-inner::-webkit-scrollbar{display:none}
.subnav a{display:inline-flex;align-items:center;min-height:46px;font-family:var(--font-hero);
  font-weight:600;font-size:14.5px;color:rgba(255,255,255,.84);text-decoration:none;
  border-bottom:3px solid transparent;white-space:nowrap}
.subnav a:hover{color:#fff}
.subnav a[aria-current="page"]{color:#fff;border-bottom-color:#fff}
.subnav-right{margin-left:auto;display:inline-flex;align-items:center;gap:12px;flex:none;
  padding-left:14px;background:var(--accent-deep);position:sticky;right:0;z-index:2}
.subnav-right::after{content:"";position:absolute;top:0;bottom:0;right:-20px;width:20px;
  background:var(--accent-deep)}
.subnav-meta{font-family:var(--font-mono);font-size:10.5px;letter-spacing:.1em;
  color:rgba(255,255,255,.66);white-space:nowrap;text-transform:uppercase}
.search-open{display:inline-flex;align-items:center;gap:7px;height:30px;padding:0 9px;
  border:1px solid rgba(255,255,255,.42);background:rgba(255,255,255,.08);color:#fff;
  font-family:var(--font-hero);font-weight:600;font-size:13px;white-space:nowrap}
.search-open:hover{background:rgba(255,255,255,.18);border-color:rgba(255,255,255,.7)}
.search-open:focus-visible{outline-color:#fff;outline-offset:2px}
.search-open .i{width:15px;height:15px}
.search-open kbd{font-family:var(--font-mono);font-size:9.5px;letter-spacing:.04em;
  padding:1px 4px;border:1px solid rgba(255,255,255,.38);color:rgba(255,255,255,.86)}
.docs-menu-btn{display:none;align-items:center;gap:8px;color:#fff;font-family:var(--font-hero);
  font-weight:600;font-size:14px;min-height:46px;padding:0 4px;border-bottom:3px solid transparent;
  white-space:nowrap}
.docs-menu-btn .i{width:18px;height:18px}
.docs-menu-btn[aria-expanded="true"]{border-bottom-color:#fff}

/* layout */
.docs-shell{display:grid;grid-template-columns:264px minmax(0,1fr) 236px;gap:44px;
  align-items:start;padding-top:34px;padding-bottom:80px}
.docs-sidebar{position:sticky;top:66px;max-height:calc(100vh - 86px);overflow:auto;
  border-right:1px solid var(--rule-soft);padding-right:20px;scrollbar-width:thin}
.sidebar-inner{display:flex;flex-direction:column;gap:18px;padding-bottom:22px}
.sidebar-search .label{display:block;margin-bottom:7px}
.search-field{display:flex;align-items:center;gap:8px;border:1px solid var(--rule);
  background:var(--paper);padding:0 9px;height:36px}
.search-field .i{width:15px;height:15px;color:var(--ink-3)}
.search-field input{border:0;background:none;flex:1;min-width:0;height:100%;font-size:13.5px}
.search-field input:focus{outline:none}
.search-field:focus-within{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.search-field input::-webkit-search-cancel-button{display:none}
.search-clear{display:none;color:var(--ink-3);padding:2px}
.search-clear .i{width:14px;height:14px}
.search-field.has-value .search-clear{display:inline-flex}
.search-hint{margin:6px 0 0;font-family:var(--font-mono);font-size:10.5px;color:var(--ink-3);min-height:12px}
.doc-nav{display:flex;flex-direction:column;gap:20px}
.nav-home{display:flex;flex-direction:column;gap:2px;text-decoration:none;padding:10px 12px;
  border:1px solid var(--rule);border-left:3px solid var(--ink);color:var(--ink)}
.nav-home:hover{border-color:var(--accent);color:var(--ink)}
.nav-home.current{background:var(--accent-soft);border-left-color:var(--accent)}
.nav-home-title{font-family:var(--font-hero);font-weight:700;font-size:14.5px}
.nav-home-sub{font-family:var(--font-mono);font-size:10px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--ink-3)}
.nav-group ul{list-style:none;margin:6px 0 0;padding:0;display:flex;flex-direction:column;gap:1px}
.nav-group-title{font-family:var(--font-mono);font-size:10px;font-weight:500;letter-spacing:.16em;
  text-transform:uppercase;color:var(--ink-3);margin:0;padding:0 0 4px;border-bottom:1px solid var(--rule-soft)}
.nav-group a{display:flex;flex-direction:column;gap:1px;padding:7px 10px 7px 12px;text-decoration:none;
  color:var(--ink-2);border-left:2px solid transparent;margin-left:-2px}
.nav-group a:hover{background:var(--paper-2);color:var(--ink)}
.nav-group a.current{background:var(--accent-soft);border-left-color:var(--accent);color:var(--ink)}
.nav-doc-title{font-size:13.5px;font-weight:600;line-height:1.3}
.nav-doc-meta{font-family:var(--font-mono);font-size:9.5px;letter-spacing:.06em;color:var(--ink-3);
  text-transform:uppercase}
.nav-group.is-hidden{display:none}
.nav-group a.is-hidden{display:none}
.sidebar-foot{margin-top:6px;border-top:1px solid var(--rule);padding-top:14px}
.sidebar-foot .label{margin-bottom:5px}
.sidebar-dataset{font-family:var(--font-mono);font-size:10.5px;color:var(--ink-2);margin:0 0 8px;line-height:1.6}
.sidebar-foot a{display:inline-flex;align-items:center;gap:3px;font-family:var(--font-hero);
  font-weight:600;font-size:13px;text-decoration:none}
.sidebar-foot a .i{width:14px;height:14px}

/* main column */
.docs-main{min-width:0}
.crumbs{margin:0 0 16px;font-size:13px;color:var(--ink-3)}
.crumbs a{text-decoration:none}
.crumbs .sep{padding:0 6px;color:var(--ink-mute)}
.doc-head{margin-bottom:26px;padding-bottom:20px;border-bottom:1px solid var(--rule)}
.doc-head h1{font-size:clamp(28px,3.4vw,40px);letter-spacing:-.03em;line-height:1.1}
.doc-meta-row{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;
  flex-wrap:wrap;margin-top:14px}
.doc-meta{margin:0;font-family:var(--font-mono);font-size:11.5px;color:var(--ink-3);line-height:1.7}
.doc-meta code{font-size:11.5px;color:var(--ink-2)}
.doc-actions{display:flex;gap:8px;flex-wrap:wrap}
.button{display:inline-flex;align-items:center;justify-content:center;gap:6px;height:34px;
  padding:0 12px;border:1px solid var(--ink);background:var(--paper);font-family:var(--font-hero);
  font-weight:600;font-size:13px;text-decoration:none;color:var(--ink);white-space:nowrap}
.button:hover{background:var(--paper-2);color:var(--ink)}
.button-quiet{border-color:var(--rule)}
.button-primary{background:var(--accent);border-color:var(--accent);color:#fff}
.button-primary:hover{background:var(--accent-deep);color:#fff}
.button .i{width:15px;height:15px}

/* prose */
.prose{font-size:15.5px;line-height:1.68;color:var(--ink-2);max-width:820px}
.prose>*:first-child{margin-top:0}
.prose h2{font-size:26px;letter-spacing:-.02em;margin:42px 0 12px;padding-top:6px;
  border-top:1px solid var(--rule-soft);color:var(--ink)}
.prose h3{font-size:19px;margin:30px 0 8px;color:var(--ink)}
.prose h4{font-size:16px;margin:24px 0 6px;color:var(--ink)}
.prose h2.has-anchor,.prose h3.has-anchor,.prose h4.has-anchor{position:relative}
.h-anchor{position:absolute;margin-left:10px;color:var(--ink-mute);text-decoration:none;
  font-family:var(--font-mono);font-size:.75em;opacity:0;transition:opacity .12s}
.prose h2:hover .h-anchor,.prose h3:hover .h-anchor,.prose h4:hover .h-anchor,
.h-anchor:focus-visible{opacity:1}
.prose p{margin:0 0 14px}
.prose ul,.prose ol{margin:0 0 16px;padding-left:24px}
.prose li{margin:0 0 6px}
.prose li>ul,.prose li>ol{margin:6px 0 0}
.prose a{font-weight:500}
.prose strong{color:var(--ink);font-weight:700}
.prose code{font-family:var(--font-mono);font-size:.86em;background:var(--paper-2);
  border:1px solid var(--rule-soft);padding:1px 5px;color:var(--ink);overflow-wrap:anywhere}
.prose pre code{background:none;border:0;padding:0;font-size:12.5px}
.prose hr{border:0;border-top:1px solid var(--rule);margin:30px 0}
.prose blockquote{margin:0 0 16px;padding:2px 0 2px 16px;border-left:3px solid var(--rule);
  color:var(--ink-2)}
.table-scroll{max-width:100%;overflow-x:auto;margin:0 0 20px;border:1px solid var(--rule-soft)}
.prose table{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--paper)}
.prose th,.prose td{border-bottom:1px solid var(--rule-soft);padding:8px 11px;text-align:left;
  vertical-align:top}
.prose th{font-family:var(--font-mono);font-size:10px;font-weight:500;letter-spacing:.1em;
  text-transform:uppercase;color:var(--ink-3);background:var(--paper-2);white-space:nowrap}
.prose tbody tr:last-child td{border-bottom:0}
.prose td code{white-space:nowrap;font-size:.82em}
.prose-blockquote,.prose img{max-width:100%}

/* code blocks */
.code-block{margin:0 0 20px;border:1px solid var(--rule);background:var(--paper)}
.code-head{display:flex;justify-content:space-between;align-items:center;gap:12px;
  padding:6px 10px;border-bottom:1px solid var(--rule-soft);background:var(--paper-2)}
.code-lang{font-family:var(--font-mono);font-size:10px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--ink-3)}
.copy-btn{display:inline-flex;align-items:center;gap:5px;font-family:var(--font-hero);
  font-weight:600;font-size:12px;color:var(--ink-2);padding:3px 8px;border:1px solid var(--rule);
  background:var(--paper)}
.copy-btn:hover{border-color:var(--accent);color:var(--accent)}
.copy-btn .i{width:13px;height:13px}
.copy-btn.copied{color:var(--positive);border-color:#bcd6bc}
.code-block pre{margin:0;padding:13px 15px;overflow:auto;max-height:520px}

/* callouts */
.callout{margin:0 0 20px;border:1px solid var(--rule);border-left:4px solid var(--accent);
  background:var(--paper-2);padding:12px 16px}
.callout-label{display:block;font-family:var(--font-mono);font-size:9.5px;font-weight:500;
  letter-spacing:.16em;color:var(--accent);margin-bottom:4px}
.callout-body>*:last-child{margin-bottom:0}
.callout-tip{border-left-color:var(--positive)}.callout-tip .callout-label{color:var(--positive)}
.callout-important{border-left-color:var(--gold)}.callout-important .callout-label{color:var(--gold)}
.callout-warning,.callout-caution{border-left-color:var(--negative)}
.callout-warning .callout-label,.callout-caution .callout-label{color:var(--negative)}
.callout-todo{border-left-color:var(--ink-3)}.callout-todo .callout-label{color:var(--ink-3)}

/* task lists */
.task-item{list-style:none;margin-left:-22px;display:flex;gap:8px;align-items:flex-start}
.task-box{width:15px;height:15px;flex:none;margin-top:4px;border:1px solid var(--ink-3);
  display:inline-flex;align-items:center;justify-content:center;background:var(--paper)}
.task-box.done{background:var(--accent);border-color:var(--accent);color:#fff}
.task-box .i{width:11px;height:11px}

/* plaintext licence page */
.plaintext-wrap{border:1px solid var(--rule);background:var(--paper-2);max-width:820px}
.plaintext{margin:0;padding:18px 20px;overflow:auto;font-family:var(--font-mono);font-size:12.5px;
  line-height:1.65;color:var(--ink-2);white-space:pre-wrap;overflow-wrap:break-word}

/* pager */
.pager{display:flex;justify-content:space-between;gap:16px;margin-top:44px;padding-top:20px;
  border-top:1px solid var(--rule);flex-wrap:wrap}
.pager-link{display:flex;flex-direction:column;gap:3px;text-decoration:none;max-width:48%}
.pager-next{text-align:right;margin-left:auto}
.pager-title{font-family:var(--font-hero);font-weight:600;font-size:15px;color:var(--accent)}
.pager-spacer{flex:1}

/* right TOC */
.docs-toc{position:sticky;top:66px;max-height:calc(100vh - 86px);overflow:auto;scrollbar-width:thin}
.toc-card{border-left:1px solid var(--rule);padding:2px 0 2px 18px}
.toc-card .label{margin-bottom:10px}
.toc-nav{display:flex;flex-direction:column;gap:1px}
.toc-link{font-size:12.5px;line-height:1.4;text-decoration:none;color:var(--ink-3);padding:4px 0;
  border-left:2px solid transparent;margin-left:-20px;padding-left:18px}
.toc-link:hover{color:var(--accent)}
.toc-link.l3{padding-left:30px;font-size:12px}
.toc-link.current{color:var(--ink);border-left-color:var(--accent);font-weight:600}
.toc-empty{font-size:12.5px;color:var(--ink-3);line-height:1.6;margin:0 0 8px}
.toc-empty a{font-size:12.5px}
.toc-empty kbd{font-family:var(--font-mono);font-size:10px;padding:1px 4px;border:1px solid var(--rule);
  background:var(--paper-2);color:var(--ink-2);white-space:nowrap}

/* index / landing */
.docs-hero{max-width:900px;margin-bottom:34px}
.docs-hero h1{font-size:clamp(34px,4.6vw,50px);letter-spacing:-.035em}
.lede{margin-top:14px;font-size:17.5px;line-height:1.6;color:var(--ink-2)}
.lede p{margin:0 0 8px}
.hero-actions{display:flex;flex-wrap:wrap;gap:10px;margin:22px 0 0}
.hero-actions .button{height:40px;padding:0 15px;font-size:14px}
.site-facts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin:30px 0 0;
  border-top:1px solid var(--ink);border-bottom:1px solid var(--rule)}
.site-facts>div{padding:14px 18px 16px;border-right:1px solid var(--rule)}
.site-facts>div:first-child{padding-left:0}
.site-facts>div:last-child{border-right:none}
.site-facts dd{margin:0}
.fact{font-family:var(--font-hero);font-weight:700;font-size:32px;letter-spacing:-.02em;line-height:1.1;margin-top:6px!important}
.fact-sub{font-family:var(--font-mono);font-size:10.5px;color:var(--ink-3);margin-top:5px!important;line-height:1.5}
.quick-links{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:0 0 40px}
.quick-link{border:1px solid var(--rule);border-top:3px solid var(--accent);padding:14px 16px;
  text-decoration:none;color:var(--ink);display:flex;flex-direction:column;gap:4px}
.quick-link:hover{background:var(--paper-2);color:var(--ink)}
.quick-link .label{font-size:9.5px;margin-bottom:2px}
.quick-link strong{font-family:var(--font-hero);font-size:15.5px}
.quick-link span:last-child{color:var(--ink-3);font-size:12.5px;line-height:1.5}
.group-card-section{margin:0 0 46px;scroll-margin-top:70px}
.group-head{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;
  border-bottom:1px solid var(--ink);padding-bottom:8px;margin-bottom:16px}
.group-head h2{font-size:23px;letter-spacing:-.02em}
.group-blurb{margin:0;color:var(--ink-3);font-size:13.5px;flex:1;min-width:220px}
.group-count{font-family:var(--font-mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3)}
.doc-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.doc-card{display:flex;flex-direction:column;gap:5px;border:1px solid var(--rule);padding:16px 18px;
  text-decoration:none;color:var(--ink);background:var(--paper)}
.doc-card:hover{border-color:var(--accent);background:var(--paper-2);color:var(--ink)}
.doc-card-group{font-family:var(--font-mono);font-size:9.5px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--accent)}
.doc-card-title{font-family:var(--font-hero);font-weight:700;font-size:17px;letter-spacing:-.01em}
.doc-card-summary{font-size:13px;line-height:1.55;color:var(--ink-2)}
.doc-card-meta{font-family:var(--font-mono);font-size:10px;color:var(--ink-3);margin-top:2px}
.doc-card-open{font-family:var(--font-hero);font-weight:600;font-size:13px;color:var(--accent);margin-top:4px}

/* footer */
.footer{border-top:1px solid var(--rule);background:var(--paper-2);margin-top:0}
.footer-inner{padding-top:34px;padding-bottom:30px}
.footer-grid{display:grid;grid-template-columns:1.6fr 1fr 1fr 1fr;gap:30px}
.footer-col h2{font-family:var(--font-mono);font-size:10px;font-weight:500;letter-spacing:.16em;
  text-transform:uppercase;color:var(--ink-3);margin:0 0 10px}
.footer-col a{display:block;font-size:13px;line-height:1.9;color:var(--ink-2);text-decoration:none}
.footer-col a:hover{color:var(--accent)}
.footer-brand p{margin:0 0 10px;font-size:13px;line-height:1.6;color:var(--ink-2);max-width:340px}
.footer-kicker{font-family:var(--font-hero);font-weight:700;font-size:16px;color:var(--ink)}
.footer-cite{font-family:var(--font-mono);font-size:10.5px!important;color:var(--ink-3)!important}
.footer-note{margin:26px 0 0;font-size:11.5px;line-height:1.6;color:var(--ink-3);max-width:1000px;
  border-top:1px solid var(--rule);padding-top:14px}
.footer-legal{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;font-size:11px;color:var(--ink-3);
  font-family:var(--font-mono)}
#to-top{position:fixed;right:20px;bottom:20px;z-index:120;width:40px;height:40px;
  border:1px solid var(--ink);background:var(--paper);display:inline-flex;align-items:center;
  justify-content:center;opacity:0;pointer-events:none;transition:opacity .15s}
#to-top.visible{opacity:1;pointer-events:auto}
#to-top:hover{background:var(--ink);color:#fff}
#to-top .i{width:17px;height:17px}

/* full-text search overlay */
body.search-active{overflow:hidden}
.search-dialog{position:fixed;inset:0 0 auto 0;margin:10vh auto auto;
  width:min(680px,calc(100vw - 40px));max-width:680px;max-height:min(78vh,660px);
  padding:0;border:1px solid var(--rule);background:var(--paper);color:var(--ink);
  box-shadow:0 30px 90px rgba(17,21,28,.38)}
.search-dialog::backdrop{background:rgba(17,21,28,.55)}
.search-dialog[open]{display:block}
.search-dialog-panel{display:flex;flex-direction:column;max-height:inherit;overflow:hidden}
.search-dialog-head{display:flex;align-items:center;justify-content:space-between;gap:12px;
  padding:10px 16px;border-bottom:1px solid var(--rule-soft);background:var(--paper-2);flex:none}
.search-dialog-title{font-family:var(--font-mono);font-size:10px;font-weight:500;
  letter-spacing:.16em;text-transform:uppercase;color:var(--ink-3)}
.search-dialog-close{display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 8px;
  border:1px solid var(--rule);background:var(--paper);color:var(--ink-2);
  font-family:var(--font-mono);font-size:10px}
.search-dialog-close:hover{border-color:var(--accent);color:var(--accent)}
.search-dialog-close .i{width:13px;height:13px}
.search-dialog kbd{font-family:var(--font-mono);font-size:9.5px;letter-spacing:.04em;
  padding:1px 4px;border:1px solid var(--rule);background:var(--paper);color:var(--ink-3)}
.search-dialog-field{display:flex;align-items:center;gap:11px;padding:14px 16px;
  border-bottom:1px solid var(--rule-soft);color:var(--ink-3);flex:none}
.search-dialog-field .i{width:19px;height:19px}
.search-dialog-field:focus-within{box-shadow:inset 0 -2px 0 var(--accent)}
.search-dialog-input{flex:1;min-width:0;height:30px;padding:0;border:0;background:none;
  font-family:var(--font-hero);font-weight:600;font-size:17.5px;letter-spacing:-.01em;color:var(--ink)}
.search-dialog-input:focus{outline:none}
.search-dialog-input::placeholder{color:var(--ink-mute);font-weight:500}
.search-dialog-input::-webkit-search-cancel-button{display:none}
.search-dialog-status{margin:0;padding:7px 16px;border-bottom:1px solid var(--rule-soft);
  font-family:var(--font-mono);font-size:10.5px;color:var(--ink-3);min-height:26px;flex:none}
.search-dialog-results{flex:1;min-height:110px;max-height:52vh;overflow-y:auto;
  overscroll-behavior:contain;scrollbar-width:thin}
.search-result{display:block;padding:10px 16px;border-left:3px solid transparent;
  border-bottom:1px solid var(--rule-soft);text-decoration:none;color:var(--ink)}
.search-result:last-child{border-bottom:0}
.search-result:hover,.search-result[aria-selected="true"]{background:var(--accent-soft);
  border-left-color:var(--accent);color:var(--ink)}
.search-result-top{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.search-result-doc{font-family:var(--font-hero);font-weight:600;font-size:12.5px;color:var(--accent)}
.search-result-group{font-family:var(--font-mono);font-size:9px;letter-spacing:.12em;
  text-transform:uppercase;color:var(--ink-3)}
.search-result-head{display:block;font-family:var(--font-hero);font-weight:700;font-size:15px;
  letter-spacing:-.01em;margin:1px 0 2px}
.search-result-snippet{display:block;font-size:12.5px;line-height:1.5;color:var(--ink-2);
  overflow-wrap:anywhere}
.search-result-snippet mark{background:#fbe3a0;color:var(--ink);padding:0 1px}
.search-empty{padding:20px 18px 22px;font-size:13px;line-height:1.6;color:var(--ink-3)}
.search-empty-title{font-family:var(--font-hero);font-weight:700;font-size:15.5px;
  letter-spacing:-.01em;color:var(--ink);margin:0 0 3px}
.search-empty-copy{margin:0 0 12px}
.search-empty-chips{display:flex;flex-wrap:wrap;gap:6px}
.search-chip{height:28px;padding:0 10px;border:1px solid var(--rule);background:var(--paper);
  font-family:var(--font-mono);font-size:10.5px;color:var(--ink-2)}
.search-chip:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-soft)}
.search-dialog-foot{display:flex;gap:16px;flex-wrap:wrap;padding:8px 16px;flex:none;
  border-top:1px solid var(--rule-soft);background:var(--paper-2);
  font-family:var(--font-mono);font-size:10px;color:var(--ink-3)}
.search-dialog-foot span{display:inline-flex;align-items:center;gap:4px}

/* responsive */
@media(max-width:1200px){
  .docs-shell{grid-template-columns:250px minmax(0,1fr);gap:34px}
  .docs-toc{display:none}
}
@media(max-width:900px){
  :root{--gutter:20px}
  .docs-shell{grid-template-columns:minmax(0,1fr);padding-top:22px}
  .docs-menu-btn{display:inline-flex}
  .masthead-name{font-size:22px}
  .masthead-with{display:none}
  .subnav-meta{display:none}
  .subnav-right{padding-left:10px;gap:0}
  .docs-sidebar{position:fixed;left:0;top:0;bottom:0;width:min(330px,86vw);max-height:none;
    background:var(--paper);border-right:1px solid var(--rule);padding:18px 16px 40px;
    transform:translateX(-102%);transition:transform .18s ease;z-index:210;overflow:auto}
  body.sidebar-open .docs-sidebar{transform:none;box-shadow:0 20px 60px rgba(17,21,28,.25)}
  .sidebar-backdrop{position:fixed;inset:0;background:rgba(17,21,28,.38);z-index:200}
  .site-facts{grid-template-columns:repeat(2,minmax(0,1fr))}
  .site-facts>div:nth-child(2n){border-right:none}
  .site-facts>div:nth-child(n+3){border-top:1px solid var(--rule)}
  .quick-links,.doc-grid{grid-template-columns:1fr}
  .footer-grid{grid-template-columns:1fr 1fr}
}
@media(max-width:560px){
  .masthead-top-inner{flex-direction:column;gap:4px}
  .footer-grid{grid-template-columns:1fr}
  .site-facts{grid-template-columns:1fr}
  .site-facts>div{border-right:none;padding-left:0}
  .site-facts>div+div{border-top:1px solid var(--rule)}
  .prose h2{font-size:22px}
  .pager-link{max-width:100%}
  .search-open-kbd{display:none}
  .search-dialog{inset:0;margin:0;width:100vw;max-width:100vw;height:100dvh;
    max-height:100dvh;border:0}
  .search-dialog-results{max-height:none}
  .search-dialog-input{font-size:16px}
  .search-dialog-foot{gap:12px}
}
@media print{
  .skip-link,.subnav,.docs-sidebar,.docs-toc,.docs-menu-btn,#to-top,.pager,.copy-btn,
  .search-dialog{display:none!important}
  .docs-shell{display:block;padding:0}
  body{font-size:11px}
  .prose{max-width:none}
  .prose h2{break-after:avoid}
  .code-block pre{max-height:none}
  .footer{background:none}
}
@media(prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  *,*::before,*::after{transition:none!important}
}
"""


def docs_js(search_index_json: str) -> str:
    script = r"""(function () {
  'use strict';
  var root = document.documentElement;
  var SEARCH_INDEX = __DOCS_SEARCH_INDEX__;

  /* mobile sidebar ------------------------------------------------------- */
  var body = document.body;
  var toggle = document.getElementById('docs-menu-btn');
  var backdrop = document.getElementById('sidebar-backdrop');
  function sidebarOpen() { return body.classList.contains('sidebar-open'); }
  function setSidebar(open) {
    body.classList.toggle('sidebar-open', open);
    if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (backdrop) backdrop.hidden = !open;
  }
  if (toggle) {
    toggle.addEventListener('click', function () { setSidebar(!sidebarOpen()); });
  }
  if (backdrop) backdrop.addEventListener('click', function () { setSidebar(false); });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && sidebarOpen()) {
      setSidebar(false);
      if (toggle) toggle.focus();
    }
  });

  /* sidebar filter ------------------------------------------------------- */
  var search = document.getElementById('doc-search');
  var clear = document.getElementById('doc-search-clear');
  var hint = document.getElementById('doc-search-hint');
  var nav = document.getElementById('doc-nav');
  if (search && nav) {
    var groups = Array.prototype.slice.call(nav.querySelectorAll('.nav-group'));
    function applyFilter() {
      var query = search.value.trim().toLowerCase();
      var shown = 0;
      groups.forEach(function (group) {
        var links = Array.prototype.slice.call(group.querySelectorAll('a'));
        var groupShown = 0;
        links.forEach(function (link) {
          var text = (link.getAttribute('data-title') || link.textContent || '').toLowerCase();
          var visible = query === '' || text.indexOf(query) !== -1;
          link.classList.toggle('is-hidden', !visible);
          if (visible) groupShown += 1;
        });
        group.classList.toggle('is-hidden', groupShown === 0);
        shown += groupShown;
      });
      var field = search.parentNode;
      if (field) field.classList.toggle('has-value', query !== '');
      if (hint) {
        hint.textContent = query === ''
          ? ''
          : shown + (shown === 1 ? ' matching doc' : ' matching docs');
      }
    }
    search.addEventListener('input', applyFilter);
    if (clear) {
      clear.addEventListener('click', function () {
        search.value = '';
        applyFilter();
        search.focus();
      });
    }
  }

  /* full-text search ----------------------------------------------------- */
  var searchDialog = document.getElementById('docs-search-dialog');
  var searchInput = document.getElementById('docs-search-input');
  var searchResults = document.getElementById('docs-search-results');
  var searchStatus = document.getElementById('docs-search-status');
  var searchOpenButton = document.getElementById('docs-search-open');
  var searchCloseButton = document.getElementById('docs-search-close');

  if (searchDialog && searchInput && searchResults && SEARCH_INDEX && SEARCH_INDEX.pages) {
    var searchPages = SEARCH_INDEX.pages;
    var searchHits = [];
    var searchActive = -1;
    var searchLastFocus = null;
    var searchSectionCount = 0;
    searchPages.forEach(function (page) {
      searchSectionCount += (page.s || []).length;
    });

    function searchTokens(query) {
      return query.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim().split(' ').filter(Boolean);
    }

    function searchEscape(text) {
      return String(text).replace(/[&<>"']/g, function (character) {
        if (character === '&') return '&amp;';
        if (character === '<') return '&lt;';
        if (character === '>') return '&gt;';
        if (character === '"') return '&quot;';
        return '&#39;';
      });
    }

    function searchHighlight(text, tokens) {
      var lower = text.toLowerCase();
      var ranges = [];
      tokens.forEach(function (token) {
        var from = 0;
        var at = lower.indexOf(token, from);
        while (at !== -1 && ranges.length < 40) {
          ranges.push([at, at + token.length]);
          from = at + token.length;
          at = lower.indexOf(token, from);
        }
      });
      if (!ranges.length) return searchEscape(text);
      ranges.sort(function (left, right) {
        return left[0] - right[0] || right[1] - left[1];
      });
      var merged = [];
      ranges.forEach(function (range) {
        var last = merged[merged.length - 1];
        if (last && range[0] <= last[1]) {
          if (range[1] > last[1]) last[1] = range[1];
        } else {
          merged.push([range[0], range[1]]);
        }
      });
      var out = '';
      var cursor = 0;
      merged.forEach(function (range) {
        out += searchEscape(text.slice(cursor, range[0]));
        out += '<mark>' + searchEscape(text.slice(range[0], range[1])) + '</mark>';
        cursor = range[1];
      });
      return out + searchEscape(text.slice(cursor));
    }

    function searchSnippet(text, tokens) {
      var lower = text.toLowerCase();
      var first = -1;
      tokens.forEach(function (token) {
        var at = lower.indexOf(token);
        if (at !== -1 && (first === -1 || at < first)) first = at;
      });
      var start = 0;
      var limit = 200;
      if (first > 64) {
        start = first - 54;
        var space = text.lastIndexOf(' ', start);
        if (space > 0) start = space + 1;
      }
      var body = text.slice(start, start + limit);
      if (start > 0) body = '\u2026' + body;
      if (start + limit < text.length) body = body.replace(/\s+\S*$/, '') + '\u2026';
      return searchHighlight(body, tokens);
    }

    function searchRun(query) {
      var tokens = searchTokens(query);
      if (!tokens.length) return [];
      var ranked = [];
      searchPages.forEach(function (page, pageIndex) {
        var label = (page.d || '').toLowerCase();
        var title = (page.t || page.d || '').toLowerCase();
        var sections = page.s || [];
        var pageText = label + ' ' + title;
        sections.forEach(function (section) {
          pageText += ' ' + (section[1] || '').toLowerCase() + ' ' + (section[2] || '').toLowerCase();
        });
        var inPage = tokens.every(function (token) {
          return pageText.indexOf(token) !== -1;
        });
        if (!inPage) return;
        var titleHits = 0;
        tokens.forEach(function (token) {
          if (title.indexOf(token) !== -1 || label.indexOf(token) !== -1) titleHits += 1;
        });
        if (titleHits) {
          var overviewText = titleHits && page.t && page.t !== page.d
            ? page.t + ' \u2014 ' + (sections.length ? (sections[0][2] || '') : '')
            : (sections.length ? (sections[0][2] || '') : '');
          ranked.push({
            pageIndex: pageIndex,
            href: page.h,
            doc: page.d || '',
            group: page.g || '',
            heading: 'Page overview',
            snippet: searchSnippet(overviewText, tokens),
            score: 2 + titleHits * 3 + (titleHits === tokens.length ? 10 : 0)
          });
        }
        sections.forEach(function (section, sectionIndex) {
          var heading = (section[1] || '').toLowerCase();
          var text = (section[2] || '').toLowerCase();
          var headingHits = 0;
          var textHits = 0;
          var matched = 0;
          tokens.forEach(function (token) {
            var inHeading = heading.indexOf(token) !== -1;
            var inText = text.indexOf(token) !== -1;
            if (inHeading) headingHits += 1;
            if (inText) textHits += 1;
            if (inHeading || inText) matched += 1;
          });
          if (!matched) return;
          var score = headingHits * 7 + textHits * 2;
          if (matched === tokens.length) score += 6;
          ranked.push({
            pageIndex: pageIndex,
            href: page.h + (section[0] ? '#' + section[0] : ''),
            doc: page.d || '',
            group: page.g || '',
            heading: section[1] || 'Section',
            snippet: searchSnippet(section[2] || '', tokens),
            score: score
          });
        });
      });
      ranked.sort(function (left, right) {
        return right.score - left.score || left.pageIndex - right.pageIndex;
      });
      var unique = [];
      var seen = {};
      var perPage = {};
      ranked.forEach(function (hit) {
        if (seen[hit.href]) return;
        var used = perPage[hit.pageIndex] || 0;
        if (used >= 4) return;
        seen[hit.href] = true;
        perPage[hit.pageIndex] = used + 1;
        unique.push(hit);
      });
      return unique;
    }

    function searchSetActive(index) {
      var options = Array.prototype.slice.call(
        searchResults.querySelectorAll('[data-search-href]'));
      if (!options.length) {
        searchActive = -1;
        searchInput.removeAttribute('aria-activedescendant');
        searchInput.setAttribute('aria-expanded', 'false');
        return;
      }
      if (typeof index !== 'number' || index !== index) index = 0;
      if (index < 0) index = options.length - 1;
      if (index >= options.length) index = 0;
      searchActive = index;
      options.forEach(function (option, position) {
        option.setAttribute('aria-selected', position === index ? 'true' : 'false');
        if (position === index) option.scrollIntoView({ block: 'nearest' });
      });
      searchInput.setAttribute('aria-activedescendant', options[index].id);
      searchInput.setAttribute('aria-expanded', 'true');
    }

    function searchEmptyState() {
      searchHits = [];
      searchActive = -1;
      searchResults.innerHTML = '<div class="search-empty">'
        + '<p class="search-empty-title">Search ' + searchPages.length + ' documentation pages</p>'
        + '<p class="search-empty-copy">' + searchSectionCount + ' sections are indexed: page titles,'
        + ' headings, prose and table text. Try a term like:</p>'
        + '<div class="search-empty-chips">'
        + ['residential rate', 'PSGC', 'API endpoint', 'validation check'].map(function (term) {
          return '<button type="button" class="search-chip" data-search-query="'
            + searchEscape(term) + '">' + searchEscape(term) + '</button>';
        }).join('')
        + '</div></div>';
      searchStatus.textContent = 'Type to search, or choose a suggestion';
      searchInput.setAttribute('aria-expanded', 'false');
      searchInput.removeAttribute('aria-activedescendant');
    }

    function searchNoResults(query) {
      searchHits = [];
      searchActive = -1;
      searchResults.innerHTML = '<div class="search-empty">'
        + '<p class="search-empty-title">No matches for \u201c' + searchEscape(query) + '\u201d</p>'
        + '<p class="search-empty-copy">Check the spelling, or try a broader term such as'
        + ' \u201cdata model\u201d, \u201cAPI\u201d or \u201cvalidation\u201d.</p></div>';
      searchStatus.textContent = '0 results for \u201c' + query + '\u201d';
      searchInput.setAttribute('aria-expanded', 'false');
      searchInput.removeAttribute('aria-activedescendant');
    }

    function searchRender(query) {
      var trimmed = query.trim();
      if (!trimmed) {
        searchEmptyState();
        return;
      }
      var found = searchRun(trimmed);
      var total = found.length;
      searchHits = found.slice(0, 20);
      if (!searchHits.length) {
        searchNoResults(trimmed);
        return;
      }
      var html = '';
      searchHits.forEach(function (hit, index) {
        html += '<a class="search-result" role="option" tabindex="-1"'
          + ' id="docs-search-option-' + index + '" aria-selected="false"'
          + ' data-search-href="' + searchEscape(hit.href) + '">'
          + '<span class="search-result-top">'
          + '<span class="search-result-doc">' + searchEscape(hit.doc) + '</span>'
          + '<span class="search-result-group">' + searchEscape(hit.group) + '</span>'
          + '</span>'
          + '<span class="search-result-head">' + searchEscape(hit.heading) + '</span>'
          + '<span class="search-result-snippet">' + hit.snippet + '</span></a>';
      });
      searchResults.innerHTML = html;
      searchStatus.textContent = total
        + (total === 1 ? ' result' : ' results')
        + ' for \u201c' + trimmed + '\u201d'
        + (total > searchHits.length ? ' \u2014 top ' + searchHits.length : '');
      searchSetActive(0);
    }

    function searchNavigate(href) {
      searchClose();
      window.location.href = href;
    }

    function searchOpen() {
      searchLastFocus = document.activeElement;
      searchInput.value = '';
      searchRender('');
      if (!searchDialog.open) {
        if (typeof searchDialog.showModal === 'function') {
          searchDialog.showModal();
        } else {
          searchDialog.setAttribute('open', '');
        }
      }
      document.body.classList.add('search-active');
      window.setTimeout(function () {
        searchInput.focus();
        searchInput.select();
      }, 0);
    }

    function searchClose() {
      if (!searchDialog.hasAttribute('open')) return;
      if (typeof searchDialog.close === 'function') {
        searchDialog.close();
      } else {
        searchDialog.removeAttribute('open');
        document.body.classList.remove('search-active');
      }
    }

    if (searchOpenButton) {
      searchOpenButton.addEventListener('click', searchOpen);
      var shortcut = searchOpenButton.querySelector('kbd');
      if (shortcut && /Mac|iPhone|iPad|iPod/.test(navigator.platform || '')) {
        shortcut.textContent = '\u2318K';
      }
    }
    if (searchCloseButton) {
      searchCloseButton.addEventListener('click', searchClose);
    }
    searchDialog.addEventListener('click', function (event) {
      if (event.target === searchDialog) searchClose();
    });
    searchDialog.addEventListener('close', function () {
      document.body.classList.remove('search-active');
      var target = searchLastFocus;
      searchLastFocus = null;
      if (target && document.contains(target) && typeof target.focus === 'function') {
        try {
          target.focus({ preventScroll: true });
        } catch (error) {
          target.focus();
        }
      }
    });
    searchInput.addEventListener('input', function () {
      searchRender(searchInput.value);
    });
    searchDialog.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (searchHits.length) searchSetActive(searchActive + 1);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        if (searchHits.length) searchSetActive(searchActive - 1);
      } else if (event.key === 'Enter' && searchActive >= 0 && searchHits[searchActive]) {
        event.preventDefault();
        searchNavigate(searchHits[searchActive].href);
      } else if (event.key === 'Escape') {
        /* the focused search input would otherwise consume Escape to clear itself */
        event.preventDefault();
        searchClose();
      }
    });
    searchResults.addEventListener('click', function (event) {
      var target = event.target;
      var chip = target.closest ? target.closest('[data-search-query]') : null;
      if (chip) {
        event.preventDefault();
        searchInput.value = chip.getAttribute('data-search-query');
        searchRender(searchInput.value);
        searchInput.focus();
        return;
      }
      var option = target.closest ? target.closest('[data-search-href]') : null;
      if (!option) return;
      event.preventDefault();
      searchNavigate(option.getAttribute('data-search-href'));
    });
    /* Ctrl/Cmd+K and "/" open the overlay; the sidebar filter keeps its input. */
    document.addEventListener('keydown', function (event) {
      var target = event.target || {};
      var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName || '')
        || target.isContentEditable === true;
      var key = event.key;
      if ((event.metaKey || event.ctrlKey) && (key === 'k' || key === 'K')) {
        event.preventDefault();
        if (searchDialog.open) {
          searchInput.focus();
        } else {
          searchOpen();
        }
        return;
      }
      if (key === '/' && !typing && !searchDialog.open) {
        event.preventDefault();
        searchOpen();
      }
    });
  }

  /* code copy buttons ---------------------------------------------------- */
  document.addEventListener('click', function (event) {
    var button = event.target.closest ? event.target.closest('[data-copy]') : null;
    if (!button) return;
    var block = button.closest('.code-block');
    var code = block ? block.querySelector('code') : null;
    if (!code) return;
    var text = code.textContent;
    function done() {
      var label = button.querySelector('span');
      button.classList.add('copied');
      button.setAttribute('aria-live', 'polite');
      if (label) {
        var previous = label.textContent;
        label.textContent = 'Copied';
        window.setTimeout(function () {
          label.textContent = previous;
          button.classList.remove('copied');
        }, 1600);
      }
    }
    function fallback() {
      try {
        var area = document.createElement('textarea');
        area.value = text;
        area.setAttribute('readonly', '');
        area.style.position = 'absolute';
        area.style.left = '-9999px';
        document.body.appendChild(area);
        area.select();
        document.execCommand('copy');
        document.body.removeChild(area);
        done();
      } catch (error) { /* clipboard unavailable */ }
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else {
      fallback();
    }
  });

  /* back to top ---------------------------------------------------------- */
  var toTop = document.getElementById('to-top');
  if (toTop) {
    toTop.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      var main = document.getElementById('main');
      if (main) main.focus({ preventScroll: true });
    });
    window.addEventListener('scroll', function () {
      toTop.classList.toggle('visible', window.scrollY > 600);
    }, { passive: true });
  }

  /* TOC scrollspy -------------------------------------------------------- */
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll('.toc-nav a[href^="#"]'));
  if (tocLinks.length && 'IntersectionObserver' in window) {
    var byId = {};
    tocLinks.forEach(function (link) {
      var id = link.getAttribute('href').slice(1);
      var target = document.getElementById(id);
      if (target) byId[id] = link;
    });
    var current = null;
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var link = byId[entry.target.id];
        if (!link || link === current) return;
        if (current) current.classList.remove('current');
        link.classList.add('current');
        current = link;
      });
    }, { rootMargin: '-20% 0px -70% 0px', threshold: 0 });
    Object.keys(byId).forEach(function (id) {
      observer.observe(document.getElementById(id));
    });
  }
})();
"""
    return script.replace("__DOCS_SEARCH_INDEX__", search_index_json)


def write_assets(search_index_json: str) -> None:
    os.makedirs(ASSETS, exist_ok=True)
    write_text(os.path.join(ASSETS, "docs.css"), docs_css())
    write_text(os.path.join(ASSETS, "docs.js"), docs_js(search_index_json))
    fonts_src = os.path.join(SRC_ASSETS, "fonts")
    os.makedirs(os.path.join(ASSETS, "fonts"), exist_ok=True)
    for name in ("figtree-normal-latin.woff2", "inter-normal-latin.woff2",
                 "jetbrains-mono-normal-latin.woff2"):
        shutil.copyfile(os.path.join(fonts_src, name), os.path.join(ASSETS, "fonts", name))
    for name in ("emblem.svg", "favicon.svg"):
        shutil.copyfile(os.path.join(SRC_ASSETS, "brand" if name == "emblem.svg" else "", name),
                        os.path.join(ASSETS, name))


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------
def collect_docs() -> List[Doc]:
    docs = build_registry()
    missing = [d.path for d in docs if not os.path.isfile(os.path.join(ROOT, d.path))]
    if missing:
        raise SystemExit("build-docs: missing source document(s): " + ", ".join(missing))
    for doc in docs:
        path = os.path.join(ROOT, doc.path)
        text = read_text(path)
        doc.lines = text.count("\n") + (0 if text.endswith("\n") else 1)
        doc.size = os.path.getsize(path)
        doc.words = len(text.split())
        if doc.kind == "plain":
            doc.raw_text = text
            doc.title_text = doc.label
            doc.title_id = github_slug(doc.label)
            FRAGMENT_MAPS[doc.path] = {doc.title_id: doc.title_id}
        else:
            render_first_pass(doc, text)
    # Group ordering: GROUP_DEFS order; within a group, declared order (research alphabetical).
    group_rank = {gid: i for i, (gid, _l, _b) in enumerate(GROUP_DEFS)}
    docs.sort(key=lambda d: (group_rank[d.group], d.order))
    return docs


def build() -> Dict[str, object]:
    load_icons()
    os.makedirs(OUT, exist_ok=True)
    # Clean generated HTML/manifest but keep nothing stale around.
    for name in os.listdir(OUT):
        if name == "assets":
            continue
        full = os.path.join(OUT, name)
        if os.path.isdir(full):
            shutil.rmtree(full)
        else:
            os.remove(full)
    docs = collect_docs()
    docs_by_path = {d.path: d for d in docs}

    # Second pass: resolve links and transform content.
    for doc in docs:
        if doc.kind == "plain":
            continue
        markup = rewrite_links(doc.raw_html, doc, docs_by_path)
        markup = transform_body(markup)
        markup = heading_anchors(markup)
        doc.content = markup

    # Full-text search: deterministic index over the collected Doc objects,
    # inlined into the shared script so every page works offline / from file://.
    search_index = build_search_index(docs)
    search_index_json = serialize_search_index(search_index)
    search_stats = search_index_stats(search_index, search_index_json)
    write_assets(search_index_json)

    total = 0
    for doc in docs:
        html_text, _sidebar = render_doc_page(doc, docs, docs_by_path)
        write_text(os.path.join(OUT, doc.html_name), html_text)
        total += len(html_text.encode("utf-8"))

    index_html = render_index_page(docs, SITE)
    write_text(os.path.join(OUT, "index.html"), index_html)
    total += len(index_html.encode("utf-8"))

    manifest = {
        "generated_by": "tools/build-docs.py",
        "site_title": SITE_TITLE,
        "dataset_version": SITE["dataset_version"],
        "page_count": len(docs) + 1,
        "groups": [
            {
                "id": gid,
                "label": label,
                "blurb": blurb,
                "docs": [
                    {
                        "id": doc.id,
                        "label": doc.label,
                        "html": doc.html_name,
                        "source": doc.path,
                        "lines": doc.lines,
                        "bytes": doc.size,
                        "kind": doc.kind,
                    }
                    for doc in docs if doc.group == gid
                ],
            }
            for gid, label, blurb in GROUP_DEFS
        ],
        "pages": [
            {"id": doc.id, "label": doc.label, "html": doc.html_name, "source": doc.path}
            for doc in docs
        ],
        "html_bytes": total,
        "search_index": {
            "pages": search_stats["pages"],
            "sections": search_stats["sections"],
            "bytes": search_stats["bytes"],
            "asset_bytes": os.path.getsize(os.path.join(ASSETS, "docs.js")),
        },
    }
    write_text(os.path.join(OUT, "docs-manifest.json"),
               json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    if UNRESOLVED:
        print("WARN unresolved internal links (kept as-is):", file=sys.stderr)
        for source, href in UNRESOLVED:
            print(f"  {source}: {href}", file=sys.stderr)

    asset_bytes = 0
    for dirpath, _dirnames, filenames in os.walk(ASSETS):
        for fname in filenames:
            asset_bytes += os.path.getsize(os.path.join(dirpath, fname))
    return {
        "pages": len(docs) + 1,
        "docs": len(docs),
        "html_bytes": total,
        "asset_bytes": asset_bytes,
        "unresolved": len(UNRESOLVED),
    }


def main() -> None:
    result = build()
    print(f"Built documentation site: {result['pages']} pages "
          f"({result['docs']} documents + index) in draft/docs/")
    print(f"  HTML     {human_size(result['html_bytes']):>8}")
    print(f"  assets   {human_size(result['asset_bytes']):>8}")
    print(f"  total    {human_size(result['html_bytes'] + result['asset_bytes']):>8}")
    if result["unresolved"]:
        print(f"  unresolved internal links: {result['unresolved']} (see warnings)")
        sys.exit(1)


if __name__ == "__main__":
    main()
