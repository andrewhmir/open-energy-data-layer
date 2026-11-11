# Security policy

This repository publishes a **static, self-contained page** and a set of
**generated data files**. It has no server-side application, no accounts, no
cookies and no write path. The security surface is therefore small, and the
highest-value risk is **data integrity**, not remote code execution.

## Supported versions

The project is pre-release (`0.x`, pre-deployment). Only the `main` branch is
maintained; there are no supported release lines yet. Once a public deployment
exists, this section will list the supported versions and the disclosure
window.

## Threat model

| Asset | Exposure | Mitigation in this repository |
| --- | --- | --- |
| `draft/map-table-prototype.html` | Served as a single static HTML file | All styles, scripts, fonts, the logo, map geometry and data are inlined at build time. The page makes **no external requests**; the only network activity is a user clicking a citation link (`target="_blank" rel="noopener"`). There is no runtime JavaScript that fetches data, sets cookies, uses `localStorage`/`sessionStorage`, or loads third-party analytics. |
| Data files (`data/seed/`, raw snapshots) | Published as plain CSV/JSON | Every published number carries provenance. Raw publisher bytes are snapshotted and SHA-256 hashed before parsing; the hashes are recorded in `data/seed/validation.json` and `data/seed/sources.csv`. A failed validation check stops publication (`tools/ingest-doe-rates.py` exits non-zero). |
| Build tooling (`tools/`) | Run by maintainers/CI | Python 3.12, standard library for the ingest and page builders; `PyYAML` and `markdown-it-py` are the only third-party runtime dependencies (see `requirements.txt`). The pipeline only fetches the public DOE workbook via HTTPS and writes inside the repository. |
| Repository secrets | None present | The pipeline uses no API keys, tokens or credentials, and reads no `.env` files (`.env*` is gitignored). If a future step adds authenticated sources, secrets must go through CI secret storage and must never be committed. |

### Out of scope / acknowledged limits

- **Third-party links.** The page links to `doe.gov.ph`, the public Google Sheet
  and `bettergov.ph`. Those sites have their own security posture; this
  repository cannot vouch for them.
- **Upstream data supply chain.** The DOE workbook is fetched from a public
  Google Sheets CSV export. Its availability and content are outside our
  control; the hash snapshot is how we detect content changes.
- **Client-side rendering.** The page renders embedded JSON with DOM APIs. The
  data is publisher data, not user input, and is inserted as text (no `eval`,
  no dynamic code execution), but a compromised build machine could still
  produce a malicious page — hence the deterministic-build and review rules in
  `CONTRIBUTING.md`.

## Data-integrity reporting

If you find a value on the page or in `data/seed/` that does not match the
source workbook, treat it as a **data-integrity bug**: open a normal issue with
the utility, month, customer class, the page/file you saw, and the workbook row
if you can find it. Do not report data errors as security vulnerabilities.

## Reporting a vulnerability

**Do not open a public issue for a security report.**

The public GitHub repository and its private vulnerability-reporting channel
are **pending** (the project is not yet deployed or published; see the README's
status section). When the repository is published, use GitHub's **Security →
Report a vulnerability** (private security advisories) for this repository and
the maintainers will respond there. Until the repository exists, raise the
report privately with the maintainers through the project's BetterGov.ph
contact channel; a dedicated security contact will be
added to this file at publication.

Please include: affected file/URL, reproduction steps, impact, and whether the
issue affects the static page, the generated data, or the build tooling. We aim
to acknowledge reports within 5 working days and to publish a fix or mitigation
note in `CHANGELOG.md` once the report can be disclosed.
