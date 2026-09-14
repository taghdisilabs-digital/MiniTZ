# Biella Games Production Support Packages

Status: `PROJECT_SUPPORT_NON_AUTHORITY`

These packages support the canonical Biella Games production source. They do not create a second scheduler, controller, memory system, packaging implementation, validation authority, or task queue.

## Packages
- `visual-release-helper/` — maps current visual defects to editable asset/evidence lanes and the existing D17→D08 packaging handoff.
- `source-integrity-helper/` — verifies Git/task/runtime/task-memory/service alignment without requiring a clean active-task worktree.
- `progress-continuity-helper/` — uses the canonical runner's own liveness status and compares explicit forward-progress markers across pause/resume.
- `release-readiness-helper/` — classifies D17 visual/evidence readiness and D08 release readiness without creating package bytes.

## Filesystem rule
These helpers stay under `docs/production-support/`, outside the Unreal cook material-input roots (`Source/`, `Content/`, `Config/`, `Plugins/`, and `BiellaGames.uproject`).

## Authority rule
Current execution state, current source, `docs/project-state/03_BIELLA_CURRENT_STATE.md`, `04_BIELLA_ACTIVE_TASK.md`, `docs/PRODUCTION.md`, exact task guides, and task-derived evidence outrank these helpers.

## Operational use
Use source integrity before/after operational changes, progress continuity after resume, visual-release guidance during D17 finishing, and release readiness when deciding whether the existing D08 packaging/release machinery has sufficient accepted inputs.
