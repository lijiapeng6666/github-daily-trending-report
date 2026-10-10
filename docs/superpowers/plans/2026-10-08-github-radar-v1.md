# GitHub Radar V1 Implementation Plan

> **For agentic workers:** Use executing-plans to implement this plan task-by-task in the current workspace. This new directory is not a Git checkout; no worktree or commit is part of this delivery.

**Goal:** Generate a real Daily Trending report that opens directly as an HTML file, with JSON snapshots and the approved responsive design.

**Architecture:** Python parses Trending and enriches each repository through its REST endpoint. Validated report models feed Jinja2 templates; CSS and classic JavaScript are embedded so local-file reading needs no server. Reports are saved by Shanghai date, and the site is rebuilt from saved snapshots under a single writer lock.

**Tech Stack:** Python 3.11+, httpx, BeautifulSoup, Pydantic, Jinja2, pytest, Ruff, Node's built-in test runner.

## Task 1: Collection and classification (Completed)

Files: `src/github_radar/{models,trending,network,classify}.py`, `config.toml`, `tests/test_collection.py`, `tests/test_network.py`.

- [x] Define package dependencies in `pyproject.toml`; install with `uv sync --python /opt/homebrew/bin/python3.12`.
- [x] Add fixture tests for commas, absent numbers, invalid links, duplicated repositories, empty pages, and source rank preservation. Run `uv run pytest tests/test_collection.py`; expect failure until the collector exists.
- [x] Implement `parse_trending(html, limit)` using `article.Box-row`, `h2 a`, `itemprop=programmingLanguage`, the stargazers link, and daily-growth text. Return validated `Repository` objects; reject a nonempty page with malformed rows rather than silently calling it a full report.
- [x] Implement boundary-aware classification from names, descriptions and topics, with editable TOML patterns. Store the matched keyword as evidence and preserve rank.
- [x] Implement bounded HTTP retries with an injected httpx client and sleep function. Honor Retry-After; fail rather than ignore a wait beyond the retry budget. Add optional token only to API calls, never to Trending or cross-origin redirects.
- [x] Run collector/network tests; require all to pass.

## Task 2: Reports and safe publication (Completed)

Files: `src/github_radar/{report,publish}.py`, `tests/test_reports.py`.

- [x] Add tests for enrichment failures, zero counts, unsafe source text, same-day replacement, preserved history, and failed render leaving output unchanged. Run `uv run pytest tests/test_reports.py`; expect missing implementation failures.
- [x] Build `Report` with aware timestamps, actual Shanghai date, source URL, warnings and complete/partial status. Keep daily growth from Trending while replacing total Star with API metadata when present. Invalid API data produces a partial report with the original parsed data.
- [x] Stage all output before replacement. Hold a nonblocking data-directory lock across collection and publication; rebuild the full site from existing JSON plus the current report. Roll back renamed output on a replacement failure; write snapshots atomically after staged rendering succeeds.
- [x] Run report and publication tests, including the previous successful result surviving an exception.

## Task 3: Approved page and interactions (Completed)

Files: `src/github_radar/resources/{report.html,archive.html,radar.css,filters.js,radar.js}`, `tests/filters.test.cjs`.

- [x] Write Node tests for combined search/filtering, rank and Star sorting, null-last ordering, AI-first behavior and input immutability. Run `node --test tests/filters.test.cjs`; expect failure until the pure filter module exists.
- [x] Move approved presentation into a template with actual collection timestamps and report status. Render rows on the server so they remain readable when JavaScript is disabled. Embed local assets and JSON with Jinja2 `tojson` and autoescape; build repository URLs from validated identifiers.
- [x] Implement pure `filterRepos(repos, state)` and browser controls that reuse it. Date links navigate to generated report pages, resetting filters; options list only real saved reports. Populate categories and languages from data. Display null as unavailable and zero as zero.
- [x] Run Node tests, then verify generated pages in a browser at desktop and mobile widths, including empty results and outbound links.

## Task 4: CLI, live run and documentation (Completed)

Files: `src/github_radar/{cli,__main__}.py`, `README.md`, `uv.lock`, `data/reports/`, `site/`.

- [x] Provide `uv run github-radar generate` and `uv run github-radar rebuild`. Generation accepts config, data and output paths; `--no-api` produces an explicitly partial report. Rebuild makes no network calls and does not change original timestamps.
- [x] Add CLI failure tests for invalid configuration, empty source and locked writer.
- [x] Run `uv run pytest`, `node --test tests/filters.test.cjs`, `uv run ruff check .`, `uv run ruff format --check .`.
- [x] Run a real generation and compare repository names/ranks/daily growth against the saved response from that same collection. Save the source HTML for audit; never replace real results with demo projects.
- [x] Document installation, commands, token configuration, offline rebuild and V1 boundaries. Mark the design as approved; report actual collection count, API degradation if any, and the resulting HTML path.

## Scope

History is rebuilt locally because snapshots must survive repeated V1 runs. GitHub Actions and Pages configuration, AI summaries, user accounts and subscriptions remain separate versions. No Git commit, push, or public deployment is planned in this task.

## Execution Record

Completed on 2026-10-08. Collection and frontend tests were first run against missing modules, then passed after implementation. Three additional identity-validation tests reproduced unsafe path/selector behavior before the fix. Final verification covers 43 Python tests and 11 JavaScript tests, Ruff checks and formatting, a real 13-repository collection with all API enrichments, source rank/growth comparison, offline rebuild preserving the snapshot hash, and browser filtering/navigation/responsive checks.

The live HTML is `site/index.html`; source and JSON snapshots are under `data/`. The response contained only 13 repositories, so the report has an explicit count warning. No scheduled automation or public site was created.
