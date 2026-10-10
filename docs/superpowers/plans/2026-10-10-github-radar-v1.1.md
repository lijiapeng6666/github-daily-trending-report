# GitHub Radar V1.1

## Scope

Preserve the approved V1 interface. Add daily generation at 08:17 Asia/Shanghai,
persistent JSON/source history on `report-data`, and GitHub Pages deployment.
Do not add AI summaries or substitute Search API results for Trending.

## Steps

- [x] Test history bootstrap, restoration, repeated runs, invalid data, and push conflicts.
- [x] Implement history synchronization with validation and non-force pushes.
- [x] Add read-only pull-request CI and daily/manual Pages publishing workflows.
- [x] Run Python, JavaScript, formatting, and workflow checks.
- [x] Document setup, permissions, schedule limitations, and failure recovery.
- [ ] Enable and verify remote publishing only after the target repository is confirmed.

## Failure Contract

An unavailable remote is an error, not an empty history. Invalid history stops the
run before generating or deploying. A failed generation does not update remote
history or the live site. A failed history push stops deployment. A failed Pages
deployment leaves the saved history available for a manual retry.
