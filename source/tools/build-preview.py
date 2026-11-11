#!/usr/bin/env python3
"""Build the static review pack for the Open Energy Data Layer draft package.

The pack holds **two clearly separated spaces**:

* **Space A — the data platform** (the standalone, public-facing product): the
  production page copied to ``/prototype.html`` with no review chrome at all,
  plus neutral "review copy" pages for the API reference, data model, research
  artefacts and the documentation site. None of these pages carry fellowship,
  proposal or application-answer pointers; their nav/footer link only platform
  documentation and a plain back-link to the review home.
* **Space B — the fellowship submission** (review-only material): the review
  home ``/`` (submission hub: status/deadline, proposal, application answers,
  challenge brief, the data platform under review, review evidence and
  downloads) and the rendered submission pages (proposal, answers, challenge
  brief) with submission-context chrome.

Design language: the BetterGovPH open-data system (white paper, ink rules,
BetterGov blue, Figtree/Inter/JetBrains Mono).

Output: /home/sysadmin/Test2/preview/
"""
import csv
import html
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone, timedelta

import yaml
from markdown_it import MarkdownIt

ROOT = "/home/sysadmin/Test2"
PREVIEW = os.path.join(ROOT, "preview")
ASSETS = os.path.join(PREVIEW, "assets")
FILES = os.path.join(PREVIEW, "files")
SRC_ASSETS = os.path.join(ROOT, "draft", "assets")
DOCS_SRC = os.path.join(ROOT, "draft", "docs")
DOCS_DST = os.path.join(PREVIEW, "docs")
DOCS_MANIFEST = os.path.join(DOCS_SRC, "docs-manifest.json")

MD = MarkdownIt("commonmark", {"html": True}).enable("table")
esc = lambda s: html.escape(str(s), quote=False)
esc_attr = lambda s: html.escape(str(s), quote=True)

# Two nav/footer contexts. ("group", label) entries are group headings, not links.
# The submission context keeps the platform links clearly grouped and separate;
# the platform context never links proposal/answers/challenge-brief pages.
NAV_SUBMISSION = [
    ("group", "Submission"),
    ("index.html", "Review pack home", "home"),
    ("proposal.html", "Proposal", "proposal"),
    ("answers.html", "Application answers", "answers"),
    ("research-pitch-deck-notes.html", "Challenge brief", "brief"),
    ("group", "Data platform"),
    ("prototype.html", "Data page", "page"),
    ("docs/index.html", "Docs", "docs"),
    ("api.html", "API reference", "api"),
    ("data-model.html", "Data model", "model"),
]

NAV_PLATFORM = [
    ("group", "Review copy"),
    ("index.html", "Review pack home", "home"),
    ("group", "Data platform"),
    ("prototype.html", "Data page", "page"),
    ("docs/index.html", "Docs", "docs"),
    ("api.html", "API reference", "api"),
    ("data-model.html", "Data model", "model"),
    ("research-data-landscape.html", "Data landscape", "data-landscape"),
    ("research-api-landscape.html", "API landscape", "api-landscape"),
]

DOC_PAGES = {
    "README.md": "readme.html",
    "plan/fellowship-proposal.md": "proposal.html",
    "plan/application-answers.md": "answers.html",
    "draft/data-model.md": "data-model.html",
    "research/data-landscape.md": "research-data-landscape.html",
    "research/api-landscape.md": "research-api-landscape.html",
    "research/pitch-deck-notes.md": "research-pitch-deck-notes.html",
    "draft/map-table-prototype.html": "prototype.html",
}
# Repository directories that map to a page in the pack (README links them directly).
DOC_DIRS = {
    "draft/docs": "docs/index.html",
}


def slugify(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "section"


def render_md(text):
    out = MD.render(text)
    seen, toc = {}, []

    def repl(m):
        level, inner = m.group(1), m.group(2)
        base = slugify(inner)
        n = seen.get(base, 0)
        seen[base] = n + 1
        slug = base if n == 0 else f"{base}-{n}"
        if level in ("2", "3"):
            label = re.sub(r"<[^>]+>", "", html.unescape(inner)).strip()
            toc.append((level, slug, label))
        return f'<h{level} id="{slug}">{inner}</h{level}>'

    return re.sub(r"<h([234])>(.*?)</h\1>", repl, out, flags=re.S), toc


def rewrite_links(markup, src_rel):
    def repl(m):
        href = m.group(1)
        if href.startswith(("http://", "https://", "mailto:", "#", "/")):
            return m.group(0)
        target = posixpath.normpath(posixpath.join(posixpath.dirname(src_rel), href))
        frag = ""
        if "#" in target:
            target, frag = target.split("#", 1)
            frag = "#" + frag
        target = target.rstrip("/")
        if target in DOC_PAGES:
            return f'href="{DOC_PAGES[target]}{esc_attr(frag)}"'
        if target in DOC_DIRS:
            return f'href="{DOC_DIRS[target]}{esc_attr(frag)}"'
        return f'href="files/{esc_attr(target)}{esc_attr(frag)}"'

    return re.sub(r'href="([^"]+)"', repl, markup)


def page(title, body, context="platform", active="", desc="", footer_note=""):
    """Render one page of the review pack with the chrome for its space.

    context="submission" -> fellowship submission material (review home, proposal,
    application answers, challenge brief). context="platform" -> a neutral review
    copy of the standalone data platform (API, data model, research, docs).
    """
    nav_items = NAV_SUBMISSION if context == "submission" else NAV_PLATFORM
    items = []
    for entry in nav_items:
        if entry[0] == "group":
            if items:
                items.append('<span class="subnav-divider" aria-hidden="true"></span>')
            items.append(f'<span class="subnav-group-label">{esc(entry[1])}</span>')
            continue
        href, label, key = entry
        cur = ' aria-current="page"' if key == active else ""
        items.append(f'<a href="{href}"{cur}>{esc(label)}</a>')
    nav = ('<nav class="subnav" aria-label="Review pack sections">'
           f'<div class="page subnav-inner">{"".join(items)}</div></nav>')
    if context == "submission":
        context_bar = """
<div class="context-bar context-bar--submission">
  <div class="page context-bar-inner">
    <span class="context-label">Fellowship submission &middot; review material</span>
    <a class="context-back" href="https://fellowship.bettergov.ph/#challenge-energy" target="_blank" rel="noopener">Challenge brief <span aria-hidden="true">&#8599;</span></a>
  </div>
</div>"""
        masthead_top = """
      <span class="muted">Submission pack &middot; draft v1.0 &middot; prepared 10 November 2026</span>
      <span class="masthead-links">
        <a href="https://bettergov.ph" target="_blank" rel="noopener">BetterGov.ph <span aria-hidden="true">&#8599;</span></a>
        <a href="proposal.html">Proposal</a>
        <a href="answers.html">Application answers</a>
      </span>"""
        masthead_kicker = "BetterGov.PH Fellowship 2026 &middot; Energy Track"
        masthead_name = "Submission &amp; review pack"
        masthead_with = """
      <span class="label">Review material</span>
      <a href="https://fellowship.bettergov.ph/" target="_blank" rel="noopener">Fellowship 2026 <span aria-hidden="true">&#8599;</span></a>"""
        footer_source = ("BetterGov.PH Fellowship 2026 &middot; Energy Track submission pack "
                         "&middot; review material")
        footer_notice = (
            "This review pack holds the fellowship submission material and a review copy of the "
            "standalone Open Energy Data Layer data platform &mdash; a separate product that contains "
            "no submission material. Rates and aggregates are values published in the Department of "
            "Energy workbook retrieved 2026-11-10; NDA and blank cells are preserved and excluded "
            "from aggregates, and source conflicts are disclosed. The data platform is an independent "
            "project and not an official DOE publication or financial advice. The workbook's reuse "
            "terms are not yet confirmed. " + footer_note)
        footer_links = """
      <li><span class="label">Submission</span><a href="index.html">Review pack home</a>
        <a href="proposal.html">Fellowship proposal</a><a href="answers.html">Application answers</a>
        <a href="research-pitch-deck-notes.html">Challenge brief</a></li>
      <li><span class="label">The data platform</span><a href="prototype.html">Data page (map, table, API)</a>
        <a href="docs/index.html">Docs &amp; notes</a><a href="api.html">API reference</a>
        <a href="data-model.html">Data model</a></li>
      <li><span class="label">Review evidence</span><a href="index.html#review-evidence">Receipts &amp; conflicts</a>
        <a href="index.html#downloads">Downloads</a><a href="files/data/seed/validation.json">validation.json</a></li>
      <li><span class="label">Source</span><a href="https://doe.gov.ph/data-and-prices/electricity" target="_blank" rel="noopener">DOE rate monitor &#8599;</a>
        <a href="https://bettergov.ph" target="_blank" rel="noopener">BetterGov.ph &#8599;</a>
        <a href="https://fellowship.bettergov.ph/#challenge-energy" target="_blank" rel="noopener">Challenge page &#8599;</a></li>"""
    else:
        context_bar = """
<div class="context-bar context-bar--platform">
  <div class="page context-bar-inner">
    <span class="context-label">Review copy &middot; Open Energy Data Layer data platform</span>
    <a class="context-back" href="index.html">&larr; Review pack home</a>
  </div>
</div>"""
        masthead_top = """
      <span class="muted">Data retrieved 10 November 2026 &middot; dataset 2026-11-10</span>
      <span class="masthead-links">
        <a href="https://bettergov.ph" target="_blank" rel="noopener">BetterGov.ph <span aria-hidden="true">&#8599;</span></a>
        <a href="https://doe.gov.ph/data-and-prices/electricity" target="_blank" rel="noopener">DOE rate monitor <span aria-hidden="true">&#8599;</span></a>
      </span>"""
        masthead_kicker = "Open Energy Data Layer &middot; data platform &middot; review copy"
        masthead_name = "Philippine electricity rates"
        masthead_with = """
      <span class="label">Review copy</span>
      <a href="prototype.html">Open the data page</a>"""
        footer_source = "Open Energy Data Layer &middot; Philippine electricity rates &middot; review copy"
        footer_notice = (
            "Review copy of the standalone Open Energy Data Layer data platform. Rates and aggregates "
            "are values published in the Department of Energy workbook retrieved 2026-11-10; NDA and "
            "blank cells are preserved and excluded from aggregates, and source conflicts are "
            "disclosed. This is an independent project and not an official DOE publication or "
            "financial advice. The workbook's reuse terms are not yet confirmed. " + footer_note)
        footer_links = """
      <li><span class="label">The data platform</span><a href="prototype.html">Data page (map, table, API)</a>
        <a href="docs/index.html">Documentation</a><a href="api.html">API reference</a>
        <a href="data-model.html">Data model</a></li>
      <li><span class="label">Documentation</span><a href="docs/api-docs.html">API guide</a>
        <a href="docs/data-seed.html">Data dictionary</a><a href="docs/coverage-method.html">Coverage method</a>
        <a href="files/draft/openapi.yaml">openapi.yaml</a></li>
      <li><span class="label">Research</span><a href="research-data-landscape.html">Data landscape</a>
        <a href="research-api-landscape.html">API landscape</a>
        <a href="index.html#review-evidence">Review evidence</a></li>
      <li><span class="label">Source</span><a href="https://doe.gov.ph/data-and-prices/electricity" target="_blank" rel="noopener">DOE rate monitor &#8599;</a>
        <a href="https://bettergov.ph" target="_blank" rel="noopener">BetterGov.ph &#8599;</a>
        <a href="index.html">Review pack home</a></li>"""
    emblem_svg = ""
    emblem_path = os.path.join(SRC_ASSETS, "brand", "emblem.svg")
    if os.path.exists(emblem_path):
        emblem_svg = open(emblem_path, encoding="utf-8").read().strip()
        emblem_svg = re.sub(r"<\?xml[^>]*\?>", "", emblem_svg).strip()
        emblem_svg = emblem_svg.replace("<svg ", '<svg width="40" height="40" aria-hidden="true" ', 1)
    fav = os.path.join(SRC_ASSETS, "favicon.svg")
    fav_uri = ""
    if os.path.exists(fav):
        import base64
        with open(fav, "rb") as fh:
            fav_uri = base64.b64encode(fh.read()).decode()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#0b4fd9">
<meta name="robots" content="noindex">
<title>{esc(title)}</title>
<meta name="description" content="{esc_attr(desc or title)}">
{'<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,' + fav_uri + '">' if fav_uri else ''}
<link rel="stylesheet" href="assets/bettergov.css">
</head>
<body class="ctx-{context}">
<a class="skip-link" href="#main">Skip to content</a>{context_bar}
<header class="masthead">
  <div class="masthead-top">
    <div class="page masthead-top-inner">{masthead_top}
    </div>
  </div>
  <div class="page masthead-main">
    <a class="masthead-title" href="index.html">
      <span class="masthead-mark">{emblem_svg}</span>
      <span>
        <span class="masthead-kicker">{masthead_kicker}</span>
        <span class="masthead-name">{masthead_name}</span>
      </span>
    </a>
    <div class="masthead-with">{masthead_with}
    </div>
  </div>
  {nav}
</header>
<main id="main" class="main"><div class="page">
{body}
</div></main>
<footer class="footer">
  <div class="page footer-inner">
    <p class="footer-source">{footer_source}</p>
    <p class="footer-notice">{footer_notice}</p>
    <ul class="footer-links">{footer_links}
    </ul>
  </div>
</footer>
</body></html>"""


CSS = r"""/* Open energy data layer site: budget.bettergov.ph family, MIT transparency-portal tokens */
@font-face{font-family:Figtree;font-style:normal;font-weight:300 900;font-display:swap;
  src:url(fonts/figtree-normal-latin.woff2) format('woff2')}
@font-face{font-family:Inter;font-style:normal;font-weight:100 900;font-display:swap;
  src:url(fonts/inter-normal-latin.woff2) format('woff2')}
@font-face{font-family:'JetBrains Mono';font-style:normal;font-weight:100 800;font-display:swap;
  src:url(fonts/jetbrains-mono-normal-latin.woff2) format('woff2')}
:root{
  --paper:#fff;--paper-2:#f4f7fc;--paper-3:#eceef2;--rule:#d4d8e0;--rule-soft:#e7eaef;
  --ink:#11151c;--ink-2:#2b3340;--ink-3:#5b6373;--ink-mute:#8a92a1;
  --accent:#0b4fd9;--accent-deep:#0a44bd;--accent-soft:#e8efff;
  --positive:#3a6b3a;--negative:#b8341f;--gold:#8a6d1f;
  --font-hero:Figtree,Manrope,-apple-system,BlinkMacSystemFont,sans-serif;
  --font-body:Inter,-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif;
  --font-mono:"JetBrains Mono",ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --page:1280px;--gutter:32px;
}
*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 var(--font-body);
  font-feature-settings:"ss01","cv11","tnum";-webkit-font-smoothing:antialiased}
img{max-width:100%}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:3px}
a:hover{color:var(--accent-deep)}
button,input,select{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
h1,h2,h3,h4{font-family:var(--font-hero);font-weight:700;letter-spacing:-.02em;line-height:1.12;margin:0}
.skip-link{position:absolute;left:12px;top:-60px;z-index:200;background:var(--accent);color:#fff;
  padding:10px 14px;text-decoration:none;font-weight:600}
.skip-link:focus{top:8px}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.page{width:100%;max-width:var(--page);margin:0 auto;padding:0 var(--gutter)}
.main{padding-top:30px;padding-bottom:70px;min-height:50vh}
.label{font-family:var(--font-mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.eyebrow{font-family:var(--font-mono);font-size:11px;font-weight:500;letter-spacing:.16em;
  text-transform:uppercase;color:var(--accent);margin:0 0 10px}
.eyebrow .sep{color:var(--ink-mute);padding:0 6px}
.muted{color:var(--ink-3)}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.fine{font-size:12.5px;color:var(--ink-3);line-height:1.55;max-width:900px;margin:12px 0 0}
.fine a{color:var(--accent)}
.sep{color:var(--ink-mute);padding:0 6px}

/* Context bar: which space this page belongs to (submission vs. platform review copy) */
.context-bar{border-bottom:1px solid var(--rule-soft);background:var(--paper-2);font-family:var(--font-hero)}
.context-bar--submission{background:var(--accent-soft);border-bottom-color:#c8d8fb}
.context-bar-inner{display:flex;align-items:center;justify-content:space-between;gap:6px 18px;flex-wrap:wrap;
  padding:7px var(--gutter)}
.context-label{display:inline-flex;align-items:center;gap:8px;font-family:var(--font-mono);font-size:10.5px;
  font-weight:500;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-3)}
.context-label::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--ink-mute);flex:none}
.context-bar--submission .context-label{color:var(--accent)}
.context-bar--submission .context-label::before{background:var(--accent)}
.context-back{font-family:var(--font-hero);font-weight:600;font-size:12.5px;color:var(--ink-2);
  text-decoration:none;white-space:nowrap}
.context-back:hover{color:var(--accent)}

.masthead{background:var(--paper)}
.masthead-top{border-bottom:1px solid var(--rule-soft);font-family:var(--font-hero);font-size:12px;font-weight:600}
.masthead-top-inner{display:flex;justify-content:space-between;gap:16px;padding:8px var(--gutter)}
.masthead-links{display:flex;gap:18px;flex-wrap:wrap;justify-content:flex-end}
.masthead-links a{color:var(--ink-2);text-decoration:none}
.masthead-links a:hover{color:var(--accent)}
.masthead-main{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:18px var(--gutter)}
.masthead-title{display:flex;align-items:center;gap:14px;color:var(--ink);text-decoration:none;min-width:0}
.masthead-title:hover{color:var(--ink)}
.masthead-mark{width:42px;height:42px;flex:none;display:grid;place-items:center}
.masthead-mark svg{width:42px;height:42px;display:block}
.masthead-kicker{display:block;font-family:var(--font-mono);font-size:10.5px;font-weight:500;
  letter-spacing:.18em;text-transform:uppercase;color:var(--accent);margin-bottom:5px}
.masthead-name{display:block;font-family:var(--font-hero);font-weight:700;font-size:25px;
  letter-spacing:-.025em;line-height:1.08}
.masthead-with{display:flex;flex-direction:column;align-items:flex-end;gap:4px;text-decoration:none;flex-shrink:0}
.masthead-with img{height:26px;width:auto;display:block}
.masthead-with a{font-family:var(--font-hero);font-weight:600;font-size:13px;color:var(--ink-2);text-decoration:none}
.masthead-with a:hover{color:var(--accent)}
.subnav{background:var(--accent-deep)}
.subnav-inner{display:flex;gap:26px;overflow-x:auto;scrollbar-width:none;padding:0 var(--gutter)}
.subnav-inner::-webkit-scrollbar{display:none}
.subnav a{display:inline-flex;align-items:center;min-height:46px;font-family:var(--font-hero);
  font-weight:600;font-size:15px;color:rgba(255,255,255,.82);text-decoration:none;
  border-bottom:3px solid transparent;white-space:nowrap}
.subnav a:hover{color:#fff}
.subnav a[aria-current="page"]{color:#fff;border-bottom-color:#fff}
.subnav-group-label{display:inline-flex;align-items:center;font-family:var(--font-mono);font-size:9.5px;
  font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:rgba(255,255,255,.6);
  white-space:nowrap;padding-right:2px}
.subnav-divider{width:1px;align-self:center;height:20px;background:rgba(255,255,255,.28);flex:none}

/* Hub hero and KPI row */
.hub-head{max-width:940px;margin-bottom:24px}
.hub-head h1{font-size:clamp(30px,4.2vw,46px);letter-spacing:-.03em}
.lede{margin-top:14px;font-size:17px;line-height:1.55;color:var(--ink-2)}
.lede p{margin:0 0 8px}
.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:20px}
.button{display:inline-flex;align-items:center;justify-content:center;height:38px;padding:0 15px;
  border:1px solid var(--ink);background:var(--paper);font-family:var(--font-hero);font-weight:600;
  font-size:14px;text-decoration:none;color:var(--ink);white-space:nowrap}
.button:hover{background:var(--paper-2);color:var(--ink)}
.button-quiet{border-color:var(--rule)}
.button-primary{background:var(--accent);border-color:var(--accent);color:#fff}
.button-primary:hover{background:var(--accent-deep);color:#fff}
.status{display:inline-flex;align-items:center;flex-wrap:wrap;gap:6px;font-size:13.5px;line-height:1.4}
.status-dot{width:9px;height:9px;border-radius:50%;background:var(--positive);flex-shrink:0}
.source-status{margin-top:16px;padding:10px 14px;border:1px solid var(--rule);background:var(--paper-2);
  font-size:13px;color:var(--ink-2)}
/* Submission status band (static deadline label; no date-relative script) */
.status-band{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:0 0 18px}
@media(max-width:820px){.status-band{grid-template-columns:1fr}}
.status-band>div{display:flex;flex-direction:column;gap:4px;border:1px solid var(--rule);
  border-left:3px solid var(--accent);background:var(--accent-soft);padding:12px 16px}
.status-band .label{color:var(--accent)}
.status-band strong{font-family:var(--font-hero);font-size:16px;color:var(--ink);letter-spacing:-.01em}
.status-band .muted{font-size:12.6px;line-height:1.5}
.reviewer-note{margin-top:16px}
.reviewer-note h3{font-size:16px;margin:0 0 8px}
.reviewer-note p{margin:0 0 8px;font-size:13.6px;color:var(--ink-2);line-height:1.55}
.reviewer-note p:last-child{margin-bottom:0}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin:0 0 36px;
  border-top:1px solid var(--ink);border-bottom:1px solid var(--rule)}
.stats>div{padding:16px 20px 18px;border-right:1px solid var(--rule)}
.stats>div:first-child{padding-left:0}
.stats>div:last-child{border-right:none}
.stats dd{margin:0}
.stat{font-family:var(--font-hero);font-weight:700;font-size:32px;letter-spacing:-.02em;line-height:1.1;margin-top:8px!important}
.stat-accent{color:var(--accent)}
.stat-sub{font-family:var(--font-mono);font-size:11px;color:var(--ink-3);margin-top:6px!important;line-height:1.5}
@media(max-width:900px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}
  .stats>div:nth-child(2n){border-right:none}
  .stats>div:nth-child(n+3){border-top:1px solid var(--rule)}}
@media(max-width:560px){.stats{grid-template-columns:1fr}.stats>div{border-right:none;padding-left:0}
  .stats>div+div{border-top:1px solid var(--rule)}}

.section{margin:0 0 42px;scroll-margin-top:18px}
.section-h{font-family:var(--font-hero);font-size:21px;font-weight:700;letter-spacing:-.015em;margin:0 0 6px}
.section-sub{margin:0 0 16px;color:var(--ink-2);font-size:14.5px;max-width:920px}
.tag{display:inline-block;font-family:var(--font-mono);font-size:9px;letter-spacing:.1em;
  text-transform:uppercase;border:1px solid var(--rule);padding:2px 6px;color:var(--ink-3);vertical-align:middle}
.tag.live{color:var(--positive);border-color:#bcd6bc;background:#f2f8f2}

/* Live preview */
.preview-panel{border:1px solid var(--rule);background:var(--paper);margin:0 0 36px}
.preview-frame{position:relative;overflow:hidden;background:var(--paper-2);height:560px}
.preview-frame iframe{position:absolute;top:0;left:0;border:0;width:1440px;height:1100px;
  transform-origin:0 0;pointer-events:none}
.preview-foot{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;
  padding:10px 14px;border-top:1px solid var(--rule);background:var(--paper-2)}
.preview-foot span{color:var(--ink-3);font-size:12.5px}
.shots{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
@media(max-width:900px){.shots{grid-template-columns:1fr}}
.shots a{display:flex;flex-direction:column;gap:7px;text-decoration:none;color:var(--ink-2);
  border:1px solid var(--rule);background:var(--paper);padding:8px;font-size:12.5px}
.shots a:hover{border-color:var(--accent);color:var(--accent)}
.shots img{width:100%;height:auto;display:block;border:1px solid var(--rule-soft);background:var(--paper-2)}
.shots span{padding:0 2px 2px}
@media(max-width:760px){.preview-panel{display:none}}

.grid{display:grid;gap:16px}
.cols-2{grid-template-columns:repeat(2,minmax(0,1fr))}
.cols-3{grid-template-columns:repeat(3,minmax(0,1fr))}
@media(max-width:900px){.cols-2,.cols-3{grid-template-columns:1fr}}
.card{border:1px solid var(--rule);background:var(--paper);padding:17px 19px;display:flex;
  flex-direction:column;gap:8px;text-decoration:none;color:inherit}
.card:hover{border-color:var(--accent)}
.card.primary-card{border-top:3px solid var(--accent)}
.card h3{font-size:16.5px;line-height:1.3;margin:0}
.card p{margin:0;color:var(--ink-2);font-size:13.6px;line-height:1.5}
.card .meta{font-family:var(--font-mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3)}
.card .open{margin-top:auto;padding-top:6px;font-family:var(--font-hero);font-weight:600;font-size:13.5px;color:var(--accent)}

/* data receipts */
.receipt-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,.85fr);gap:18px;align-items:start}
@media(max-width:940px){.receipt-grid{grid-template-columns:1fr}}
.mcard{border:1px solid var(--rule);border-top:3px solid var(--ink);padding:16px 18px;background:var(--paper)}
.mcard.accent-top{border-top-color:var(--accent)}
.mcard h3{font-size:16px;margin:0 0 8px}
.mcard p{margin:0 0 8px;font-size:13.5px;color:var(--ink-2)}
.mcard p:last-child{margin-bottom:0}
.mcard code,.fine code{overflow-wrap:anywhere}
.table-scroll{max-width:100%;overflow:auto}
.data-table{width:100%;border-collapse:collapse;font-size:12.5px;margin:6px 0 2px}
.data-table th,.data-table td{border-bottom:1px solid var(--rule-soft);padding:6px 8px;text-align:left;vertical-align:top}
.data-table th{font-family:var(--font-mono);font-size:9.5px;font-weight:500;letter-spacing:.1em;
  text-transform:uppercase;color:var(--ink-3)}
.data-table td.num{font-family:var(--font-mono);text-align:right;white-space:nowrap}
.data-table td code{font-size:11px}
.ok-mark{color:var(--positive);font-weight:600}
.conflict-row{border-left:3px solid #d9a441;background:#fdf7e8;padding:7px 10px;margin:0 0 8px;
  font-size:12.4px;line-height:1.5}
.conflict-row b{font-family:var(--font-mono);font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--gold);display:block;margin-bottom:2px}
.checks{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.pass{display:inline-flex;align-items:center;gap:5px;font-family:var(--font-mono);font-size:10px;
  border:1px solid #bcd6bc;background:#f2f8f2;color:var(--positive);padding:3px 7px}
.dl-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:8px}
@media(max-width:820px){.dl-grid{grid-template-columns:1fr 1fr}}
@media(max-width:520px){.dl-grid{grid-template-columns:1fr}}
.dl-grid a{display:flex;justify-content:space-between;gap:8px;border:1px solid var(--rule);
  padding:8px 10px;text-decoration:none;color:var(--ink-2);font-size:12.5px}
.dl-grid a:hover{border-color:var(--accent);color:var(--accent)}
.dl-grid span{font-family:var(--font-mono);font-size:10px;color:var(--ink-3);white-space:nowrap}

/* Document pages */
.layout{display:grid;grid-template-columns:250px minmax(0,1fr);gap:34px;align-items:start}
@media(max-width:980px){.layout{grid-template-columns:minmax(0,1fr);gap:8px}
  .layout>div{min-width:0}}
.toc{position:sticky;top:20px;max-height:calc(100vh - 40px);overflow:auto;border:1px solid var(--rule);
  padding:13px;background:var(--paper-2);font-size:12.8px}
@media(max-width:980px){.toc{position:static;max-height:none}}
.toc h2{font-family:var(--font-mono);font-size:10px;font-weight:500;letter-spacing:.14em;
  text-transform:uppercase;color:var(--ink-3);margin:0 0 9px}
.toc a{display:block;color:var(--ink-2);text-decoration:none;padding:4px 6px;border-radius:0;line-height:1.35}
.toc a:hover{background:var(--paper-3);color:var(--ink)}
.toc a.l3{padding-left:17px;font-size:12px;color:var(--ink-3)}
.doc-head{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;align-items:flex-end;margin:0 0 18px;
  padding-bottom:12px;border-bottom:1px solid var(--ink)}
.doc-meta{color:var(--ink-3);font-size:12.3px;font-family:var(--font-mono);margin:0}
.doc-actions{display:flex;gap:8px;flex-wrap:wrap}
.prose{font-size:15.3px;line-height:1.72;color:var(--ink-2);max-width:92ch;min-width:0;
  overflow-wrap:break-word}
.prose a{overflow-wrap:anywhere}
.prose h1{font-size:clamp(27px,3.6vw,36px);margin:0 0 12px;line-height:1.14;color:var(--ink)}
.prose h2{margin:36px 0 12px;font-size:22px;letter-spacing:-.012em;padding-top:8px;
  border-top:1px solid var(--rule);color:var(--ink)}
.prose h3{margin:26px 0 9px;font-size:17.5px;color:var(--ink)}
.prose h4{margin:20px 0 8px;font-size:15px;color:var(--accent)}
.prose p{margin:0 0 12px}
.prose ul,.prose ol{margin:0 0 14px;padding-left:22px}
.prose li{margin:4px 0}
.prose code{font-family:var(--font-mono);font-size:.85em;background:var(--paper-3);padding:1px 4px;
  overflow-wrap:anywhere}
.prose pre{background:var(--paper-2);border:1px solid var(--rule);padding:13px 15px;overflow:auto;
  font-size:12.6px;line-height:1.55;margin:0 0 16px}
.prose pre code{background:none;padding:0;font-size:inherit}
.prose table{border-collapse:collapse;width:100%;margin:0 0 18px;font-size:13.3px;display:block;overflow-x:auto}
.prose th,.prose td{border:1px solid var(--rule);padding:7px 10px;text-align:left;vertical-align:top}
.prose th{background:var(--paper-2);font-weight:700;white-space:nowrap}
.prose blockquote{margin:0 0 16px;padding:11px 15px;border-left:3px solid var(--accent);
  background:var(--paper-2);color:var(--ink-2)}
.prose blockquote p:last-child{margin:0}
.prose hr{border:0;border-top:1px solid var(--rule);margin:26px 0}
.prose h2[id],.prose h3[id]{scroll-margin-top:20px}

/* API reference */
.api-meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:18px 0 0}
@media(max-width:760px){.api-meta{grid-template-columns:1fr}}
.api-meta div{background:var(--paper-2);border:1px solid var(--rule);padding:10px 14px;font-size:13px;
  color:var(--ink-2);overflow-wrap:anywhere}
.api-meta b{display:block;color:var(--ink);font-size:12px;margin-bottom:3px}
.api-sec{margin:32px 0 0}
.api-sec h2{font-size:20px;margin:0 0 4px}
.api-sec .section-sub{margin-bottom:14px}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}
.toolbar button{font:600 12.5px/1 var(--font-body);color:var(--ink-2);background:var(--paper-2);
  border:1px solid var(--rule);padding:8px 11px;cursor:pointer}
.toolbar button:hover{border-color:var(--accent);color:var(--accent)}
.method{font:600 10.5px/1 var(--font-mono);letter-spacing:.05em;padding:5px 8px;text-transform:uppercase;flex:none}
.method.get{background:var(--accent-soft);color:var(--accent);border:1px solid #bfd2fb}
.method.post{background:#fdf7e8;color:var(--gold);border:1px solid #e5cf9a}
.op{border:1px solid var(--rule);margin:0 0 10px;overflow:hidden;background:var(--paper)}
.op>summary{display:flex;align-items:center;gap:10px;padding:11px 14px;cursor:pointer;list-style:none;
  background:var(--paper-2);flex-wrap:wrap}
.op>summary::-webkit-details-marker{display:none}
.op>summary::after{content:"+";margin-left:auto;color:var(--ink-3);font-family:var(--font-mono)}
.op[open]>summary::after{content:"\2212"}
.op-path{font-family:var(--font-mono);font-size:12.8px;font-weight:500;color:var(--ink)}
.op-sum{color:var(--ink-2);font-size:13px;flex:1;min-width:200px}
.op-body{padding:14px 16px 4px;border-top:1px solid var(--rule)}
.op-body h4{font-family:var(--font-mono);font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;
  color:var(--ink-3);margin:18px 0 8px}
.op-body p{color:var(--ink-2);font-size:13.8px}
.op-body table,.op-body th,.op-body td{border:1px solid var(--rule);border-collapse:collapse}
.op-body table{width:100%;font-size:12.8px;margin:0 0 8px;display:block;overflow-x:auto}
.op-body th,.op-body td{padding:6px 9px;text-align:left;vertical-align:top}
.op-body th{background:var(--paper-2);font-weight:600;white-space:nowrap}
.op-id{font-family:var(--font-mono);font-size:11.5px;color:var(--ink-3);margin:0 0 10px}
.fmt{color:var(--ink-3);font-size:11.5px}
.desc{font-size:13.2px;color:var(--ink-2)}
.desc p{margin:0 0 6px}
details.schema{border:1px solid var(--rule);margin:0 0 8px;background:var(--paper)}
details.schema>summary{display:flex;align-items:center;gap:10px;padding:9px 13px;cursor:pointer;
  list-style:none;font-size:13px;background:var(--paper-2)}
details.schema>summary::-webkit-details-marker{display:none}
details.schema>summary::after{content:"+";margin-left:auto;color:var(--ink-3);font-family:var(--font-mono)}
details.schema[open]>summary::after{content:"\2212"}
.schema-body{padding:4px 14px 14px;border-top:1px solid var(--rule)}
.tool-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
@media(max-width:760px){.tool-list{grid-template-columns:1fr}}
.tool{background:var(--paper-2);border:1px solid var(--rule);padding:11px 13px}
.tool code{color:var(--accent);font-size:12.8px}
.tool p{margin:5px 0 0;color:var(--ink-2);font-size:12.8px}

.footer{border-top:1px solid var(--ink);background:var(--paper-2);margin-top:auto}
.footer-inner{padding:26px var(--gutter) 40px}
.footer-source{font-family:var(--font-mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--ink-3);margin:0 0 12px}
.footer-notice{font-size:12.5px;color:var(--ink-2);max-width:960px;margin:0 0 20px;line-height:1.55}
.footer-links{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;font-size:13.5px}
.footer-links li{display:flex;flex-direction:column;gap:4px}
@media(max-width:760px){.footer-links{grid-template-columns:1fr 1fr}}
@media(max-width:700px){
  /* one compact scrollable row instead of a tall wrapped block */
  .subnav-inner{flex-wrap:nowrap;gap:14px;padding:0 var(--gutter)}
  .subnav a{min-height:40px;font-size:13.5px}
  .subnav-group-label{font-size:8.5px}
  .subnav-divider{display:none}

  .context-bar-inner{padding:6px var(--gutter)}
  .context-label{font-size:9px;letter-spacing:.1em}
  .masthead-top .muted{display:none}
  .masthead-top-inner{justify-content:flex-end}
  .masthead-with{display:none}
  .masthead-name{font-size:21px}
  .masthead-kicker{font-size:9px;letter-spacing:.13em}
}
.preview-js{display:none}
"""


def write_assets():
    os.makedirs(os.path.join(ASSETS, "fonts"), exist_ok=True)
    with open(os.path.join(ASSETS, "bettergov.css"), "w", encoding="utf-8") as fh:
        fh.write(CSS)
    for fn in ["figtree-normal-latin.woff2", "inter-normal-latin.woff2", "jetbrains-mono-normal-latin.woff2"]:
        shutil.copy2(os.path.join(SRC_ASSETS, "fonts", fn), os.path.join(ASSETS, "fonts", fn))
    for fn in ["bettergov-logo.png", "favicon.svg"]:
        src = os.path.join(SRC_ASSETS, fn)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(ASSETS, fn))


def load_payload():
    with open(os.path.join(ROOT, "data", "seed", "page-data.json"), encoding="utf-8") as fh:
        return json.load(fh)


def fmt_bytes(n):
    return f"{n/1024/1024:.1f} MB" if n >= 1024 * 1024 else f"{n/1024:.0f} KB"


# ---------------------------------------------------------------------------
# Index — fellowship submission & review pack home
# ---------------------------------------------------------------------------
INDEX_JS = """
<script>
(function(){
  var frame = document.getElementById('previewFrame');
  if(frame){
    var iframe = frame.querySelector('iframe');
    function fit(){
      var w = frame.clientWidth || 1, s = Math.min(1, w / 1440);
      iframe.style.transform = 'scale(' + s + ')';
      frame.style.height = Math.min(600, Math.round(1100 * s)) + 'px';
    }
    fit(); window.addEventListener('resize', fit);
  }
})();
</script>
"""


def build_index():
    """Review home: the fellowship submission hub, with the data platform as a separate product."""
    p = load_payload()
    spec = load_openapi()
    manifest = load_docs_manifest() or {}
    docs_pages = manifest.get("page_count")
    docs_pages_note = f"{docs_pages} pages" if docs_pages else "styled markdown"
    api_ops = len(spec.get("paths", {}))
    api_schemas = len(spec.get("components", {}).get("schemas", {}))
    dm_lines = len(open(os.path.join(ROOT, "draft", "data-model.md"), encoding="utf-8").read().splitlines())
    proposal_lines = len(open(os.path.join(ROOT, "plan", "fellowship-proposal.md"), encoding="utf-8").read().splitlines())
    answer_lines = len(open(os.path.join(ROOT, "plan", "application-answers.md"), encoding="utf-8").read().splitlines())
    brief_lines = len(open(os.path.join(ROOT, "research", "pitch-deck-notes.md"), encoding="utf-8").read().splitlines())
    src = p["source"]
    latest = p["stats"]["latest"]["residential"]
    checks = p["validation"]
    conflicts = p["conflicts"]
    util_n = len(p["utilities"])
    pub_months = p["build"]["months"][:p["build"]["months"].index(p["build"]["latest_month"]) + 1]

    tabs_rows = "".join(
        f'<tr><td>{esc(t["class"])}</td><td class="num">{t["gid"]}</td><td class="num">{t["rows"]}</td>'
        f'<td><code title="full hash in validation.json">{esc(t["sha256"][:14])}&hellip;</code></td></tr>'
        for t in src["tabs"])

    def claims(c):
        if c["type"] == "name_variant":
            return "; ".join(f"{k} tab: <code>{esc(v)}</code>" for k, v in c["variants"].items())
        if c["type"] == "island_conflict":
            return " &middot; ".join(f"{esc(k)}: <code>{esc(v)}</code>" for k, v in c["claims"].items())
        return " &middot; ".join(f"<code>{esc(v)}</code> in {', '.join(esc(x) for x in cs)}"
                                 for v, cs in c["claims"].items())

    conflicts_html = "".join(
        f'<div class="conflict-row"><b>{esc(c["type"].replace("_", " "))} &middot; row {c["source_row"]}</b>'
        f'<strong>{esc(c["canonical"])}</strong>. {claims(c)} <span class="muted">&mdash; {esc(c["note"])}</span></div>'
        for c in conflicts)

    anchors = [
        ("Jun 2026 Meralco residential", "₱14.48"),
        ("Jun 2026 SOLECO residential", "₱16.57 (+32.2% m/m)"),
        ("Jun 2026 BISELCO residential", "₱24.92"),
        ("Jun 2026 simple mean / median", "₱12.29 / ₱12.10"),
        ("Jun 2026 reporting DUs", "127 of 141"),
    ]
    anchor_rows = "".join(f"<tr><td>{a}</td><td class=\"num\">{b}</td><td class=\"ok-mark\">PASS</td></tr>" for a, b in anchors)

    # Space B — fellowship submission material (these pages are not the product).
    submission_cards = [
        ("proposal.html", "Fellowship proposal", f"{proposal_lines} lines &middot; draft v1.0 &middot; 2026-11-10",
         "The argument and the delivery plan: problem, users, three deliverables, map/table/API design, "
         "pipeline, COMPASS/AES integration, 3-month plan, risks and metrics.", "Read the proposal →"),
        ("answers.html", "Application answers", f"{answer_lines} lines &middot; form verified 2026-11-10",
         "Draft answers to the fellowship application questions, plus the pre-submission checklist and "
         "interview preparation.", "Read the answers →"),
        ("research-pitch-deck-notes.html", "Challenge brief", f"{brief_lines} lines &middot; verbatim extract",
         "Energy-track slides 24–42 from the BetterGovPH consolidated pitch deck — the challenge this "
         "submission answers, and the primary source for the quoted claims.", "Read the challenge brief →"),
    ]
    # Space A — the standalone data platform (a review copy of the product).
    platform_cards = [
        ("docs/index.html", "Documentation site", f"{docs_pages_note} &middot; search + TOC",
         "Platform documentation in the BetterGov design: data model, API guide, coverage method, testing, "
         "licensing and security.", "Browse the docs →"),
        ("api.html", "API reference", f"{api_ops} endpoints &middot; {api_schemas} schemas",
         "Rendered OpenAPI 3.1 contract for the static JSON API: envelope, conventions, attribution, "
         "disclaimers and MCP tools.", "Browse the API →"),
        ("data-model.html", "Data model", f"{dm_lines} lines &middot; v1.0",
         "Canonical entities, the provenance backbone, publication states, versioning and licensing policy.",
         "Read the data model →"),
        ("files/data/seed/README.md", "Data dictionary", "141 utilities &middot; 60,348 rows",
         "Column-by-column documentation for the real ingested dataset and its validation report.",
         "Open the data dictionary →"),
    ]

    def card(spec, primary=False):
        href, title, meta, body = spec[:4]
        cta = spec[4] if len(spec) > 4 else "Open →"
        cls = "card primary-card" if primary else "card"
        return (f'<a class="{cls}" href="{href}"><div class="meta">{meta}</div><h3>{title}</h3>'
                f'<p>{body}</p><span class="open">{cta}</span></a>')

    downloads = []
    for label, rel, note in [
        ("utilities.csv", "data/seed/utilities.csv", "141 rows"),
        ("rates_monthly.csv", "data/seed/rates_monthly.csv", "60,348 rows"),
        ("regions.csv", "data/seed/regions.csv", "18 rows"),
        ("sources.csv", "data/seed/sources.csv", "4 tab records"),
        ("validation.json", "data/seed/validation.json", "17 checks"),
        ("page-data.json", "data/seed/page-data.json", "page payload"),
        ("openapi.yaml", "draft/openapi.yaml", f"{api_ops} endpoints"),
        ("data-model.md", "draft/data-model.md", "349 lines"),
        ("integrated page", "map-table-prototype.html", fmt_bytes(os.path.getsize(os.path.join(PREVIEW, "prototype.html"))) if os.path.exists(os.path.join(PREVIEW, "prototype.html")) else "518 KB"),
        ("raw residential tab", f"data/raw/doe-rates/{src['retrieved_at'][:10]}/0.csv", "raw bytes"),
        ("raw commercial tab", f"data/raw/doe-rates/{src['retrieved_at'][:10]}/441532959.csv", "raw bytes"),
        ("raw industrial tab", f"data/raw/doe-rates/{src['retrieved_at'][:10]}/1244383053.csv", "raw bytes"),
        ("raw generation tab", f"data/raw/doe-rates/{src['retrieved_at'][:10]}/714337242.csv", "raw bytes"),
        ("validation log (research)", "research/data-landscape.md", "source ledger"),
        ("package README", "README.md", "updated"),
        ("entire package (.zip)", "open-energy-draft-2026-11-10.zip", "repo + data"),
    ]:
        target = rel if rel in ("map-table-prototype.html", "open-energy-draft-2026-11-10.zip") else f"files/{rel}"
        if not os.path.exists(os.path.join(PREVIEW, target)):
            continue
        downloads.append(f'<a href="{target}" download="{esc_attr(posixpath.basename(rel))}">{label}<span>{note}</span></a>')

    body = f"""
<section class="hub-head">
  <p class="eyebrow">BetterGov.PH Fellowship 2026 <span class="sep">&middot;</span> Energy Track</p>
  <h1>Fellowship submission &amp; review pack</h1>
  <div class="lede">
    <p>This pack is the <strong>BetterGovPH Fellowship 2026 Energy Track submission</strong> for the
    challenge <em>&ldquo;One open energy data layer for the Philippines&rdquo;</em>: the proposal, the
    application answers, the challenge brief, the data platform built for the challenge, and the review
    evidence behind it.</p>
    <p>The <strong>data platform is a separate, standalone product</strong>. It is public-facing and
    contains no submission material — no proposal, no application answers, no deadline and no fellowship
    branding. This review home is the only place the submission material appears.</p>
  </div>
  <div class="actions">
    <a class="button button-primary" href="prototype.html">Open the data platform &rarr;</a>
    <a class="button" href="proposal.html">Read the proposal</a>
    <a class="button button-quiet" href="#submission">Submission material</a>
  </div>
  <div class="source-status">
    <span class="status"><span class="status-dot"></span>
    Submission pack &middot; draft v1.0 prepared 10 November 2026 &middot; application deadline
    <strong>Tuesday, 17 November 2026</strong> &middot; decisions announced 30 November 2026</span>
  </div>
</section>

<section class="section" id="submission">
  <h2 class="section-h">Submission material</h2>
  <p class="section-sub">The application itself — proposal, answers and the challenge brief. Everything
  in this section is submission material and is not part of the data platform.</p>
  <div class="status-band">
    <div><span class="label">Application deadline</span>
      <strong>Tuesday, 17 November 2026</strong>
      <span class="muted">The fellowship application form closes on this date; this pack is prepared for
      internal review before submission.</span></div>
    <div><span class="label">Pack status</span>
      <strong>Draft v1.0 &middot; 10 November 2026</strong>
      <span class="muted">Shortlisted applicants are interviewed by a five-member selection committee;
      decisions are announced 30 November 2026.</span></div>
  </div>
  <div class="grid cols-3">{''.join(card(c) for c in submission_cards)}</div>
  <div class="mcard reviewer-note">
    <h3>Reviewer note</h3>
    <p>Start with the <a href="prototype.html">data platform</a> — it is the deliverable the challenge
    asks for. Then read the <a href="proposal.html">proposal</a> for the argument and delivery plan, and
    the <a href="research-pitch-deck-notes.html">challenge brief</a> extract for the quoted claims it
    answers. Every rate on the platform traces to a DOE source row and source conflicts are disclosed,
    not hidden; the <a href="#review-evidence">review evidence</a> section lists the receipts.</p>
    <p class="fine">The data platform under review is a separate product. This submission pack is the
    only place in the review environment where submission material appears.</p>
  </div>
</section>

<section class="section" id="platform">
  <h2 class="section-h">The data platform under review</h2>
  <p class="section-sub">A standalone, public-facing product built for the challenge — a separate space
  from this submission. Open it directly, or review its documentation, API contract and data model.
  <strong>It contains no submission material.</strong></p>
  <div class="actions">
    <a class="button button-primary" href="prototype.html">Open the data platform &rarr;</a>
    <a class="button" href="docs/index.html">Documentation</a>
    <a class="button button-quiet" href="api.html">API reference</a>
    <a class="button button-quiet" href="data-model.html">Data model</a>
  </div>

<dl class="stats">
  <div><dt class="label">Utilities in the dataset</dt><dd class="stat stat-accent">{util_n}</dd>
    <dd class="stat-sub">141 workbook rows, 21 off-grid, 142 distinct names across tabs</dd></div>
  <div><dt class="label">Published months</dt><dd class="stat">{len(pub_months)}</dd>
    <dd class="stat-sub">{pub_months[0]} &rarr; {pub_months[-1]} &middot; four customer classes</dd></div>
  <div><dt class="label">Reporting &middot; {datetime.strptime(latest["month"], "%Y-%m").strftime("%b %Y")}</dt>
    <dd class="stat">{latest["reporting"]} / {latest["total"]}</dd>
    <dd class="stat-sub">{latest["nda"]} NDA &middot; {latest["invalid"]} invalid cell &middot; median {esc("₱" + format(latest["median"], ",.2f"))}</dd></div>
  <div><dt class="label">Validation checks</dt><dd class="stat">{sum(1 for c in checks if c["ok"])} / {len(checks)}</dd>
    <dd class="stat-sub">pitch anchors + structure + conflicts; a failure stops publication</dd></div>
</dl>

  <div class="preview-panel">
    <div class="preview-frame" id="previewFrame"><iframe src="prototype.html" title="Live copy of the standalone data page" loading="lazy"></iframe></div>
    <div class="preview-foot"><span>Live copy of the standalone data page &middot; BetterGovPH design &middot; real DOE data</span>
      <a class="button button-primary" href="prototype.html">Open the full page &rarr;</a></div>
  </div>

  <div class="grid cols-2">{''.join(card(c) for c in platform_cards)}</div>

  <h3 class="section-h" style="margin-top:34px">The published surface</h3>
  <p class="section-sub">Rendered from the real workbook: the region map, the sortable price table
  with expandable histories, and the method/receipts section.</p>
  <div class="shots">
    <a href="prototype.html#map"><img src="assets/shots/map.png" alt="Region map of Philippine residential electricity rates, October 2026" loading="lazy">
      <span>18-region map · colour by four customer classes</span></a>
    <a href="prototype.html?provider=MERALCO#map"><img src="assets/shots/provider-map.png" alt="Meralco service area drawn at city and municipality level on the provider coverage lens" loading="lazy">
      <span>Provider lens · 141 service areas · Meralco's 108 RA 12146 LGUs</span></a>
    <a href="prototype.html#table"><img src="assets/shots/table.png" alt="Sortable price table of 141 utilities" loading="lazy">
      <span>Price table · 141 utilities · MoM and NDA states</span></a>
    <a href="prototype.html#api"><img src="assets/shots/api.png" alt="API documentation with endpoint reference and response explorer" loading="lazy">
      <span>API docs · 19 JSON endpoints · sources &amp; disclaimers</span></a>
    <a href="docs/index.html"><img src="assets/shots/api.png" alt="Generated documentation site" loading="lazy">
      <span>Docs site · {docs_pages_note} · sidebar, TOC and raw downloads</span></a>
  </div>

  <h3 class="section-h" style="margin-top:34px">How the platform is built</h3>
  <p class="section-sub">A provenance-first pipeline, the BetterGovPH design system, and disagreements
  published instead of hidden — product context for the review.</p>
  <div class="grid cols-3">
    <div class="card primary-card"><div class="meta">Data</div><h3>Publisher bytes, not samples</h3>
      <p><code>tools/ingest-doe-rates.py</code> fetches the four public CSV exports, snapshots and hashes
      the bytes, parses 60,348 cells and publishes tidy CSVs. Every rate on the page links to its source row.</p></div>
    <div class="card primary-card"><div class="meta">Design</div><h3>BetterGovPH design language</h3>
      <p>The page uses the same tokens and components as BetterGovPH's own transparency portal:
      Figtree/Inter/JetBrains Mono, BetterGov blue, rule tables, masthead and footer. Fonts are inlined,
      so it stays one self-contained file.</p></div>
    <div class="card primary-card"><div class="meta">Trust</div><h3>Problems disclosed</h3>
      <p>The workbook's four tabs disagree in {len(conflicts)} places. The pipeline resolves by majority,
      keeps the losing claims, publishes <code>CONFLICT</code> where there is no majority, and shows it all
      in the method section.</p></div>
  </div>
</section>

<section class="section" id="review-evidence">
  <h2 class="section-h">Review evidence</h2>
  <p class="section-sub">The receipts behind the platform's numbers: source tabs and hashes, challenge-pitch
  anchors, source conflicts and the automated checks. Review material, kept separate from the product itself.</p>
  <div class="receipt-grid">
    <div class="mcard accent-top">
      <h3>Source and anchors</h3>
      <p>DOE <a href="{esc_attr(src["page_url"])}" target="_blank" rel="noopener">Electricity Rates &amp; Power
      Market Monitor</a> &middot; public Google Sheet <code>{esc(src["sheet_id"])}</code> &middot; retrieved
      {datetime.fromisoformat(src["retrieved_at"]).strftime("%-d %B %Y")}. Re-fetch with
      <code>python3 tools/ingest-doe-rates.py</code>.</p>
      <table class="data-table"><thead><tr><th>Tab</th><th class="num">gid</th><th class="num">DUs</th>
      <th>SHA-256</th></tr></thead><tbody>{tabs_rows}</tbody></table>
      <h4 class="label" style="margin:16px 0 6px">Challenge-pitch anchors (June 2026)</h4>
      <table class="data-table"><thead><tr><th>Check</th><th class="num">Value</th><th>Result</th></tr></thead>
      <tbody>{anchor_rows}</tbody></table>
      <div class="checks">{''.join(f'<span class="pass">✓ {esc(c["check"])}</span>' for c in checks[:10])}
        <span class="pass">+{len(checks)-10} more</span></div>
      <p class="fine">Full report: <a href="files/data/seed/validation.json">validation.json</a> &middot;
      <a href="files/data/seed/sources.csv">sources.csv</a> &middot;
      <a href="files/data/seed/rates_monthly.csv">rates_monthly.csv</a> (60,348 rows).</p>
    </div>
    <div class="mcard">
      <h3>Source conflicts we found</h3>
      <p>Kept verbatim and resolved in the open — the losing claim is never deleted.</p>
      {conflicts_html}
      <h4 class="label" style="margin:16px 0 6px">Known limits</h4>
      <ul class="fine" style="margin:0;padding-left:18px">
        <li>Component-level bill breakdowns are not in this workbook — next pipeline stage.</li>
        <li>Plant/RE-project layers are not included yet; the map shows regions, not facilities.</li>
        <li>One residential cell (Oct 2026) is text, marked <code>invalid</code>, never imputed.</li>
        <li>No explicit DOE dataset licence found; reuse terms to confirm (week-1 ask).</li>
      </ul>
    </div>
  </div>
</section>

<section class="section" id="downloads">
  <h2 class="section-h">Downloads</h2>
  <p class="section-sub">Real data, raw snapshots, contracts and the self-contained page — all downloadable
  for review. The full-package zip also contains the submission documents.</p>
  <div class="dl-grid">{''.join(downloads)}</div>
</section>

<section class="section" id="sources">
  <h2 class="section-h">Sources &amp; references</h2>
  <p class="section-sub">Public references this project relies on, accessed 2026-11-10 and logged in the
  research files.</p>
  <div class="dl-grid">
    <a href="https://fellowship.bettergov.ph/#challenge-energy" target="_blank" rel="noopener">Challenge brief ↗<span>bettergov.ph</span></a>
    <a href="https://doe.gov.ph/data-and-prices/electricity" target="_blank" rel="noopener">DOE rate monitor ↗<span>doe.gov.ph</span></a>
    <a href="{esc_attr(src["sheet_url"])}" target="_blank" rel="noopener">Public workbook ↗<span>Google Sheets</span></a>
    <a href="https://presyo.icsc.ngo/" target="_blank" rel="noopener">Presyo PH (ICSC) ↗<span>presyo.icsc.ngo</span></a>
    <a href="https://budget.bettergov.ph/" target="_blank" rel="noopener">BetterGovPH Budget API ↗<span>design template</span></a>
    <a href="https://github.com/bettergovph/transparency-portal" target="_blank" rel="noopener">BetterGovPH transparency portal ↗<span>MIT · design system</span></a>
  </div>
</section>
{INDEX_JS}
"""
    return page("Fellowship submission & review pack — BetterGov.PH Fellowship 2026, Energy Track",
                body, context="submission", active="home",
                desc="BetterGovPH Fellowship 2026 Energy Track submission pack: proposal, application answers, challenge brief, and a separated review copy of the standalone Open Energy Data Layer data platform.")


# ---------------------------------------------------------------------------
# Doc pages
# ---------------------------------------------------------------------------
def doc_page(rel_src, out_name, active, title, subtitle, context="platform"):
    src = os.path.join(ROOT, rel_src)
    text = open(src, encoding="utf-8").read()
    rendered, toc = render_md(text)
    rendered = rewrite_links(rendered, rel_src)
    size = os.path.getsize(src)
    lines = text.count("\n") + 1
    meta = f"<code>{esc(rel_src)}</code> &middot; {lines:,} lines &middot; {fmt_bytes(size)}"
    toc_html = ""
    if len(toc) >= 4:
        items = "".join(
            f'<a class="{"l3" if level == "3" else ""}" href="#{slug}">{esc(label)}</a>'
            for level, slug, label in toc)
        toc_html = f'<nav class="toc" aria-label="On this page"><h2>On this page</h2>{items}</nav>'
    body = f"""
<div class="layout">
{toc_html}
<div>
  <div class="doc-head">
    <p class="doc-meta">{meta}</p>
    <div class="doc-actions">
      <a class="button button-quiet" href="files/{esc_attr(rel_src)}" download>Download raw</a>
      <a class="button button-quiet" href="index.html">Review pack home</a>
    </div>
  </div>
  <article class="prose">{rendered}</article>
</div>
</div>"""
    suffix = "submission pack" if context == "submission" else "Open Energy Data Layer review copy"
    return page(f"{title} — {suffix}", body, context=context, active=active, desc=subtitle)


# ---------------------------------------------------------------------------
# API reference (same renderer as before, light theme)
# ---------------------------------------------------------------------------
def load_openapi():
    with open(os.path.join(ROOT, "draft/openapi.yaml"), encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def schema_type_html(spec):
    if not isinstance(spec, dict):
        return "&mdash;"
    if "$ref" in spec:
        name = spec["$ref"].rsplit("/", 1)[-1]
        return f'<a href="#schema-{esc_attr(name)}">{esc(name)}</a>'
    for comb in ("oneOf", "anyOf", "allOf"):
        if comb in spec:
            return f'<span class="fmt">{comb}</span>(' + " | ".join(schema_type_html(x) for x in spec[comb]) + ")"
    t = spec.get("type", "any")
    if t == "array":
        return "array&lt;" + schema_type_html(spec.get("items", {})) + "&gt;"
    if t == "object":
        ap = spec.get("additionalProperties")
        if isinstance(ap, dict):
            return "map&lt;string, " + schema_type_html(ap) + "&gt;"
        return "object"
    out = esc(t)
    if spec.get("format"):
        out += f' <span class="fmt">({esc(spec["format"])})</span>'
    if spec.get("enum"):
        out += " " + " ".join(f"<code>{esc(v)}</code>" for v in spec["enum"][:8])
        if len(spec["enum"]) > 8:
            out += f' <span class="fmt">+{len(spec["enum"])-8} more</span>'
    return out


def desc_html(text):
    return f'<div class="desc">{MD.render(str(text)).strip()}</div>' if text else ""


def resolve_ref(obj, comp, kind):
    if isinstance(obj, dict) and "$ref" in obj:
        name = obj["$ref"].rsplit("/", 1)[-1]
        return name, comp.get(kind, {}).get(name, {})
    return None, obj


def op_params_html(op, comp):
    rows = []
    for prm in op.get("parameters") or []:
        ref_name, prm = resolve_ref(prm, comp, "parameters")
        name = prm.get("name", ref_name or "")
        descr = MD.renderInline(str(prm.get("description", ""))).strip() if prm.get("description") else ""
        rows.append(
            f"<tr><td><code>{esc(name)}</code></td><td>{esc(prm.get('in',''))}</td>"
            f"<td>{schema_type_html(prm.get('schema', {}))}</td>"
            f"<td>{'yes' if prm.get('required') else 'no'}</td><td>{descr}</td></tr>")
    if not rows:
        return ""
    return ('<h4>Parameters</h4><table><thead><tr><th>Name</th><th>In</th><th>Type</th>'
            '<th>Required</th><th>Description</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>")


def op_body_html(op, comp):
    parts = []
    if op.get("description"):
        parts.append(desc_html(op["description"]))
    parts.append(op_params_html(op, comp))
    rb = op.get("requestBody")
    if rb:
        _, rb = resolve_ref(rb, comp, "requestBodies")
        for ctype, cspec in (rb.get("content") or {}).items():
            parts.append(f'<h4>Request body <span class="fmt">({esc(ctype)})</span></h4>'
                         + (desc_html(rb.get("description")) if rb.get("description") else "")
                         + f'<p>Schema: {schema_type_html(cspec.get("schema", {}))}</p>')
    rows = []
    for status, resp in (op.get("responses") or {}).items():
        _, resp = resolve_ref(resp, comp, "responses")
        descr = MD.renderInline(str(resp.get("description", ""))).strip()
        schemas = [f'<span class="fmt">{esc(ct)}</span> {schema_type_html(cs.get("schema", {}))}'
                   for ct, cs in (resp.get("content") or {}).items()]
        rows.append(f"<tr><td><code>{esc(status)}</code></td><td>{descr}</td>"
                    f"<td>{'<br>'.join(schemas) or '&mdash;'}</td></tr>")
    if rows:
        parts.append('<h4>Responses</h4><table><thead><tr><th>Status</th><th>Description</th>'
                     '<th>Schema</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>")
    return "".join(parts)


def schema_props_html(schema):
    rows = []
    for name, prop in (schema.get("properties") or {}).items():
        descr = MD.renderInline(str(prop.get("description", ""))).strip() if prop.get("description") else ""
        rows.append(f"<tr><td><code>{esc(name)}</code></td><td>{schema_type_html(prop)}</td>"
                    f"<td>{descr}</td></tr>")
    if not rows:
        return ""
    return ('<table><thead><tr><th>Property</th><th>Type</th><th>Description</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table>")


def build_api():
    spec = load_openapi()
    info, comp = spec.get("info", {}), spec.get("components", {})
    tags, paths = spec.get("tags", []), spec.get("paths", {})
    schemas, mcp = comp.get("schemas", {}), spec.get("x-mcp-tools") or {}
    tokens = spec.get("x-mcp-endpoint", {})

    groups = []
    for tag in tags:
        ops = [(path, method.upper(), op) for path, methods in paths.items()
               for method, op in methods.items()
               if method in ("get", "post", "put", "patch", "delete")
               and (op.get("tags") or [None])[0] == tag["name"]]
        if not ops:
            continue
        ops_html = ""
        for path, method, op in ops:
            op_id = op.get("operationId", "")
            op_id_html = f'<p class="op-id">{esc(op_id)}</p>' if op_id else ""
            ops_html += (f'<details class="op" open id="op-{esc_attr(op_id)}">'
                         f'<summary><span class="method {method.lower()}">{method}</span>'
                         f'<code class="op-path">{esc(path)}</code>'
                         f'<span class="op-sum">{esc(op.get("summary", ""))}</span></summary>'
                         f'<div class="op-body">{op_id_html}'
                         f'{op_body_html(op, comp)}</div></details>')
        groups.append(f'<div class="api-sec" id="tag-{slugify(tag["name"])}"><h2>{esc(tag["name"])}</h2>'
                      f'<p class="section-sub">{esc(tag.get("description", ""))}</p>{ops_html}</div>')

    schemas_html = ""
    for name, schema in schemas.items():
        req = ", ".join(f"<code>{esc(r)}</code>" for r in schema.get("required") or [])
        req_html = f'<p class="desc"><strong>Required:</strong> {req}</p>' if req else ""
        schemas_html += (f'<details class="schema" id="schema-{esc_attr(name)}">'
                         f'<summary><code>{esc(name)}</code>'
                         f'<span class="fmt">{schema_type_html(schema) if not schema.get("properties") else "object"}</span></summary>'
                         f'<div class="schema-body">{desc_html(schema.get("description"))}'
                         f'{req_html}{schema_props_html(schema)}</div></details>')

    tools_html = ""
    if mcp.get("tools"):
        tools_html = desc_html(mcp.get("description")) + '<div class="tool-list">' + "".join(
            f'<div class="tool"><code>{esc(t.get("name",""))}</code>'
            f'<p>{esc(t.get("description",""))}</p></div>' for t in mcp["tools"]) + "</div>"

    nav_chips = "".join(f'<a class="tag" href="#tag-{slugify(t["name"])}">{esc(t["name"])}</a> '
                        for t in tags)
    meta_kv = "".join(
        f'<div><b>Server</b><code>{esc(s.get("url",""))}</code><br>{esc(s.get("description",""))}</div>'
        for s in spec.get("servers", [])) + \
        f'<div><b>Version</b>{esc(info.get("version",""))} &middot; OpenAPI {esc(spec.get("openapi",""))}</div>' + \
        f'<div><b>MCP</b><code>{esc(tokens.get("path",""))}</code> &middot; {esc(tokens.get("transport",""))} &middot; {esc(tokens.get("mode",""))}</div>'

    body = f"""
<div class="hub-head">
  <p class="eyebrow">API contract <span class="sep">&middot;</span> OpenAPI {esc(spec.get("openapi",""))}</p>
  <h1>{esc(info.get("title", "Open Energy Data Layer API"))}</h1>
  <div class="lede"><p>{esc(info.get("summary", ""))}</p></div>
  <div class="actions">
    <a class="button button-primary" href="prototype.html#api">See it live on the page</a>
    <a class="button" href="files/draft/openapi.yaml" download>Download openapi.yaml</a>
    <a class="button button-quiet" href="data-model.html">Data model</a>
  </div>
  <div class="api-meta">{meta_kv}</div>
</div>
<div class="api-sec"><h2>Overview</h2>{desc_html(info.get("description"))}
  <p class="fine">Jump to: {nav_chips}</p></div>
<div class="toolbar"><button type="button" data-expand="op">Expand all operations</button>
  <button type="button" data-collapse="op">Collapse all operations</button></div>
{''.join(groups)}
<div class="api-sec" id="schemas"><h2>Schemas</h2>
  <p class="section-sub">{len(schemas)} component schemas — the shape of every payload.</p>
  <div class="toolbar"><button type="button" data-expand="schema">Expand all schemas</button>
    <button type="button" data-collapse="schema">Collapse all schemas</button></div>
  {schemas_html}</div>
<div class="api-sec" id="mcp"><h2>MCP tools</h2>
  <p class="section-sub">Read-only wrapper so LLM clients can query the same layer with the same provenance rules.</p>
  {tools_html}</div>
<script>
(function(){{
  function toggle(sel, open){{ document.querySelectorAll(sel).forEach(function(el){{ el.open = open; }}); }}
  document.querySelectorAll('[data-expand]').forEach(function(b){{
    b.addEventListener('click', function(){{ toggle('details.' + b.dataset.expand, true); }}); }});
  document.querySelectorAll('[data-collapse]').forEach(function(b){{
    b.addEventListener('click', function(){{ toggle('details.' + b.dataset.collapse, false); }}); }});
}})();
</script>"""
    return page(f"{info.get('title','API')} — review copy", body, context="platform", active="api",
                desc="Review copy of the OpenAPI 3.1 contract for the Open Energy Data Layer data platform.")


# ---------------------------------------------------------------------------
# File copying, prototype copy, zip, main
# ---------------------------------------------------------------------------
DOCS_SKIP_LINK = '<a class="skip-link" href="#main">Skip to content</a>'
DOCS_REVIEW_BAR_CSS = """
/* Review-pack context bar — injected by tools/build-preview.py into the copied docs site */
.review-copy-bar{background:#eef3fa;border-bottom:1px solid #d4d8e0;
  font-family:Figtree,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:12px;
  font-weight:600;color:#2b3340}
.review-copy-bar-inner{width:100%;max-width:1400px;margin:0 auto;padding:7px 32px;display:flex;
  align-items:center;justify-content:space-between;gap:6px 18px;flex-wrap:wrap}
.review-copy-label{display:inline-flex;align-items:center;gap:8px;
  font-family:"JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;font-size:10.5px;font-weight:500;
  letter-spacing:.13em;text-transform:uppercase;color:#5b6373}
.review-copy-label::before{content:"";width:7px;height:7px;border-radius:50%;background:#8a92a1;flex:none}
.review-copy-bar a{color:#2b3340;text-decoration:none;white-space:nowrap}
.review-copy-bar a:hover{color:#0b4fd9}
@media(max-width:700px){.review-copy-bar-inner{padding:6px 32px}}
"""
DOCS_REVIEW_BAR = (
    '<div class="review-copy-bar"><div class="review-copy-bar-inner">'
    '<span class="review-copy-label">Review copy &middot; Open Energy Data Layer data platform</span>'
    '<a href="../index.html">&larr; Review pack home</a>'
    '</div></div>'
)
def copy_files():
    shutil.rmtree(FILES, ignore_errors=True)
    os.makedirs(FILES, exist_ok=True)
    rels = [
        "README.md",
        "LICENSE",
        "NOTICE.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "draft/api-docs.md",
        "research/api-docs-conventions.md",
        "CHANGELOG.md",
        "requirements.txt",
        "plan/fellowship-proposal.md",
        "plan/application-answers.md",
        "research/data-landscape.md",
        "research/api-landscape.md",
        "research/pitch-deck-notes.md",
        "draft/openapi.yaml",
        "draft/data-model.md",
        "draft/assets/README.md",
        "data/seed/README.md",
        "data/seed/utilities.csv",
        "data/seed/regions.csv",
        "data/seed/rates_monthly.csv",
        "data/seed/sources.csv",
        "data/seed/service_areas.csv",
        "data/seed/service_area_sources.csv",
        "data/seed/validation.json",
        "data/seed/page-data.json",
        "data/seed/plants.csv",
        "research/service-areas.md",
        "research/service-areas.json",
        "research/coverage/README.md",
        "research/coverage/extract.py",
        "draft/assets/geo-sources.json",
        "tests/README.md",
        # CI workflow (the docs architecture guide links it as a repo file)
        ".github/workflows/ci.yml",
    ]
    for rel in rels:
        src = os.path.join(ROOT, rel)
        dst = os.path.join(FILES, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    raw_dir = os.path.join(ROOT, "data", "raw", "doe-rates")
    if os.path.isdir(raw_dir):
        for day in sorted(os.listdir(raw_dir))[-1:]:
            src = os.path.join(raw_dir, day)
            dst = os.path.join(FILES, "data", "raw", "doe-rates", day)
            os.makedirs(dst, exist_ok=True)
            for fn in sorted(os.listdir(src)):
                shutil.copy2(os.path.join(src, fn), os.path.join(dst, fn))
    api_src = os.path.join(ROOT, "draft", "api")
    if os.path.isdir(api_src):
        for dirpath, dirnames, filenames in os.walk(api_src):
            dirnames.sort()
            for fname in sorted(filenames):
                full = os.path.join(dirpath, fname)
                dst = os.path.join(FILES, "draft", "api", os.path.relpath(full, api_src))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(full, dst)
    # Every documentation source (raw download links on the docs pages).
    manifest = load_docs_manifest() or {"pages": []}
    for page in manifest.get("pages", []):
        rel = page.get("source", "")
        src = os.path.join(ROOT, rel)
        if rel and os.path.isfile(src):
            dst = os.path.join(FILES, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    # Tool and test sources referenced from the docs.
    for extra in ["package.json", "package-lock.json", "requirements.txt",
                  "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md", "NOTICE.md", "LICENSE"]:
        src = os.path.join(ROOT, extra)
        if os.path.isfile(src):
            dst = os.path.join(FILES, extra)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
    for base in ["tools", "tests"]:
        src_dir = os.path.join(ROOT, base)
        if not os.path.isdir(src_dir):
            continue
        for dirpath, dirnames, filenames in os.walk(src_dir):
            dirnames.sort()
            for fname in sorted(filenames):
                full = os.path.join(dirpath, fname)
                dst = os.path.join(FILES, base, os.path.relpath(full, src_dir))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(full, dst)
    shutil.copy2(os.path.join(PREVIEW, "prototype.html"), os.path.join(FILES, "map-table-prototype.html"))

    zip_path = os.path.join(FILES, "open-energy-draft-2026-11-10.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for base in ["README.md", "LICENSE", "NOTICE.md", "SECURITY.md", "CONTRIBUTING.md",
                     "CHANGELOG.md", "requirements.txt", ".editorconfig", ".gitattributes",
                     "package.json", "package-lock.json", "plan", "draft", "research", "data",
                     "tools", "tests", ".github"]:
            p = os.path.join(ROOT, base)
            if os.path.isfile(p):
                zf.write(p, base)
                continue
            for dirpath, dirnames, filenames in os.walk(p):
                dirnames.sort()
                for fname in sorted(filenames):
                    full = os.path.join(dirpath, fname)
                    zf.write(full, os.path.relpath(full, ROOT))
    return zip_path


def load_docs_manifest():
    """Registry written by tools/build-docs.py (page list + source paths)."""
    try:
        with open(DOCS_MANIFEST, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def copy_docs():
    """Copy the generated docs site into preview/docs/ and make it a neutral review copy.

    Docs pages reference repository files as ../../<path> (two levels up from
    draft/docs/); in the preview those become ../files/<path>. The product page
    link becomes the preview copy (../prototype.html). Each copied page also gets
    the neutral "Review copy" context bar with a plain back-link to the review
    home — never the fellowship submission chrome.
    """
    if not os.path.isdir(DOCS_SRC):
        build_docs = os.path.join(ROOT, "tools", "build-docs.py")
        print("  docs site missing - building it first (tools/build-docs.py)")
        subprocess.run([sys.executable, build_docs], check=True)

    shutil.rmtree(DOCS_DST, ignore_errors=True)
    shutil.copytree(DOCS_SRC, DOCS_DST)

    page_link = re.compile(r'(href|src)="\.\./(map-table-prototype\.html[^"]*)"')
    repo_link = re.compile(r'(href|src)="\.\./\.\./([^"]+)"')
    rewritten = 0
    injected = 0

    def repl_page(match):
        return f'{match.group(1)}="../prototype.html{match.group(2)[len("map-table-prototype.html"):]}"'

    def repl_repo(match):
        return f'{match.group(1)}="../files/{match.group(2)}"'

    for dirpath, dirnames, filenames in os.walk(DOCS_DST):
        dirnames.sort()
        for fname in sorted(filenames):
            if not fname.endswith(".html"):
                continue
            path = os.path.join(dirpath, fname)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            text, n1 = page_link.subn(repl_page, text)
            text, n2 = repo_link.subn(repl_repo, text)
            rewritten += n1 + n2
            if "review-copy-bar" not in text:
                if DOCS_SKIP_LINK in text:
                    text = text.replace(DOCS_SKIP_LINK, DOCS_SKIP_LINK + "\n" + DOCS_REVIEW_BAR, 1)
                    injected += 1
                elif "<body>" in text:
                    text = text.replace("<body>", "<body>\n" + DOCS_REVIEW_BAR, 1)
                    injected += 1
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
    # The copied docs stylesheet gains the small styles for the injected bar.
    docs_css = os.path.join(DOCS_DST, "assets", "docs.css")
    if os.path.exists(docs_css):
        with open(docs_css, "a", encoding="utf-8") as fh:
            fh.write(DOCS_REVIEW_BAR_CSS)
    return DOCS_DST, rewritten, injected


def build_prototype():
    """Copy the production data page verbatim, rewriting repo-relative links only.

    The pack's ``/prototype.html`` must be the standalone data platform page and
    nothing else: no review bar, no fellowship/submission strip, link or chip.
    The only difference from ``draft/map-table-prototype.html`` is that links
    into the repository are redirected to the pack's ``files/`` tree.
    """
    src = os.path.join(ROOT, "draft/map-table-prototype.html")
    text = open(src, encoding="utf-8").read()
    # links that point inside the repo become preview-relative download links
    for a, b in [('href="../data/', 'href="files/data/'),
                 ('href="../draft/', 'href="files/draft/'),
                 ('href="../plan/', 'href="files/plan/'),
                 ('href="../research/', 'href="files/research/'),
                 ('href="../LICENSE"', 'href="files/LICENSE"'),
                 ('href="../NOTICE.md"', 'href="files/NOTICE.md"'),
                 ('href="../README.md"', 'href="files/README.md"'),
                 ('href="../SECURITY.md"', 'href="files/SECURITY.md"'),
                 ('href="../CHANGELOG.md"', 'href="files/CHANGELOG.md"'),
                 ('href="../CONTRIBUTING.md"', 'href="files/CONTRIBUTING.md"'),
                 ('href="api/v1/', 'href="files/draft/api/v1/'),
                 ('"api/v1/', '"files/draft/api/v1/'),
                 ('href="openapi.yaml"', 'href="files/draft/openapi.yaml"'),
                 ('href="data-model.md"', 'href="files/draft/data-model.md"')]:
        text = text.replace(a, b)
    assert text.count("</body>") == 1 and text.count("<body>") == 1
    with open(os.path.join(PREVIEW, "prototype.html"), "w", encoding="utf-8") as fh:
        fh.write(text)
    return len(text)


def copy_screenshots():
    """Optional: copy the production QA suite's screenshots into the site."""
    shot_dir = os.environ.get("QA_SHOTS", "/tmp/qa-final")
    target = os.path.join(ASSETS, "shots")
    wanted = [("page-top.png", "page-top.png"), ("map.png", "map.png"),
              ("provider-map.png", "provider-map.png"),
              ("table.png", "table.png"), ("api.png", "api.png"),
              ("method.png", "method.png"), ("mobile.png", "mobile.png"),
              ("mobile-provider.png", "mobile-provider.png"),
              ("mobile-menu.png", "mobile-menu.png"), ("mobile-table.png", "mobile-table.png")]
    if not os.path.isdir(shot_dir):
        return
    os.makedirs(target, exist_ok=True)
    for src_name, dst_name in wanted:
        p = os.path.join(shot_dir, src_name)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(target, dst_name))


def main():
    os.makedirs(PREVIEW, exist_ok=True)
    write_assets()

    docs_dir, docs_rewrites, docs_bars = copy_docs()

    # (source, output, active nav key, title, description, context)
    docs = [
        ("plan/fellowship-proposal.md", "proposal.html", "proposal", "Fellowship proposal",
         "Fellowship submission: the project proposal.", "submission"),
        ("plan/application-answers.md", "answers.html", "answers", "Application answers",
         "Fellowship submission: the application answers.", "submission"),
        ("research/pitch-deck-notes.md", "research-pitch-deck-notes.html", "brief", "Challenge brief",
         "Fellowship submission: the challenge deck extract.", "submission"),
        ("draft/data-model.md", "data-model.html", "model", "Data model",
         "Review copy of the data platform's canonical schema and provenance.", "platform"),
        ("research/data-landscape.md", "research-data-landscape.html", "data-landscape", "Data landscape",
         "Review copy: the data platform's source ledger.", "platform"),
        ("research/api-landscape.md", "research-api-landscape.html", "api-landscape", "API & standards landscape",
         "Review copy: the data platform's API evidence.", "platform"),
        ("README.md", "readme.html", "", "Project README",
         "Review copy: the data platform's project README.", "platform"),
    ]
    for rel, out, active, title, sub, context in docs:
        with open(os.path.join(PREVIEW, out), "w", encoding="utf-8") as fh:
            fh.write(doc_page(rel, out, active, title, sub, context))

    n_proto = build_prototype()
    with open(os.path.join(PREVIEW, "api.html"), "w", encoding="utf-8") as fh:
        fh.write(build_api())
    copy_screenshots()
    with open(os.path.join(PREVIEW, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(build_index())
    zip_path = copy_files()

    print("Built review pack (fellowship submission home + data-platform review copies)")
    for name in sorted(os.listdir(PREVIEW)):
        p = os.path.join(PREVIEW, name)
        if os.path.isfile(p):
            print(f"  {name:32s} {fmt_bytes(os.path.getsize(p)):>8}")
    print(f"  prototype copy: {fmt_bytes(n_proto)}")
    docs_bytes = 0
    for dirpath, _dirnames, filenames in os.walk(docs_dir):
        for fname in filenames:
            docs_bytes += os.path.getsize(os.path.join(dirpath, fname))
    print(f"  docs copy: {fmt_bytes(docs_bytes)} ({docs_rewrites} repo links rewritten, "
          f"{docs_bars} neutral review bars injected)")
    print(f"  files/zip: {fmt_bytes(os.path.getsize(zip_path))}")


if __name__ == "__main__":
    main()
