# Contributing

Thanks for helping make Philippine electricity-rate data easier to check. A
correction that can be traced to a publisher source is worth more than a hundred
new features.

## What this repository is

This is the **public deployment** of the
[Open Energy Data Layer](https://andrewhmir.github.io/open-energy-data-layer/)
data platform: a generated static site (the page, the read-only JSON API, the
documentation and the published dataset). It is **not** the project source. Every
html/json/csv file here is emitted by deterministic builders and re-published as
a whole; edits made directly in this repository do not survive the next deploy.

## Good contributions here

- **Data corrections and verification** — point out a rate that looks wrong, a
  mislabelled NDA cell, or a service area that does not match a franchise
  document. Include the utility code, the month, the customer class, and the DOE
  source tab/row where possible. The validation report
  [`data/seed/validation.json`](data/seed/validation.json) records the checks and
  the raw per-tab SHA-256 hashes; the
  [data dictionary](docs/data-seed.html) explains every column and state.
- **Page bugs** — report the browser and viewport and paste the full page URL:
  the page keeps its state (provider, region, search, sort, comparison) in the
  query string, so a shared link reproduces the bug.
- **API and contract issues** — cite the endpoint path (for example
  `/api/v1/rates/latest/residential.json`), the [OpenAPI](openapi.yaml) rule it
  breaks, and the expected envelope field.
- **Documentation fixes** — the pages under [`docs/`](docs/index.html) are
  generated from markdown sources; a report that names the page and the sentence
  is enough, and the fix is made upstream.

## Rules a contribution must respect

- **Provenance, never imputation.** Cell states `published`, `nda`, `missing`
  and `invalid` are preserved exactly. Aggregates use published values only and
  always report the reporting count. A source conflict is disclosed, never
  guessed into a single value.
- **Every number is traceable.** New values need a source id, tab and row, an
  extraction method, and the workbook snapshot hash.
- **No licence claims over third-party data.** No licence is asserted over the
  DOE workbook or the figures extracted from it; see [NOTICE.md](NOTICE.md).
  Keep the attribution for geometry (NAMRIA/PSA via OCHA, CC BY 3.0 IGO) and
  brand assets intact.
- **Data platform only.** Fellowship/application material is deliberately absent
  from this repository and from the page; do not add it.
- **Accessibility and determinism.** The page must keep its keyboard path, focus
  handling, no-horizontal-overflow guarantee and zero external runtime requests;
  the builders must stay byte-identical across runs.

The full contributor workflow (setup, build order, pull-request checklist) lives
on the [contributing page](docs/contributing.html) of the documentation site.

## Licence

By contributing you agree that your contributions are licensed under the
project's MIT licence ([LICENSE](LICENSE)) for code, page and design. Data
contributions remain subject to the source-data terms described in
[NOTICE.md](NOTICE.md).
