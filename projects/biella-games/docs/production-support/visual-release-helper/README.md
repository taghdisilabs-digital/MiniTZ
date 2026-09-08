# Biella Games Visual + Release Helper

Status: `PROJECT_SUPPORT_NON_AUTHORITY`
Scope: reusable D17 visual-finishing and release-handoff material for Biella Games.

This package does not replace `docs/PRODUCTION.md`, task guides, D17 qualification, or the D08 package/install implementation.
It exists to make the remaining visual work and later packaging work easier to execute from the current filesystem.

## Read first
- `docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md`
- `docs/task-guides/D17-01.md`
- `docs/task-guides/D17-07.md`
- `docs/task-guides/D17-08.md`
- `Build/AAA/D17-01/visual-assessment.json`
- `Build/AAA/D17-01/qualification.json`
- `Build/Release/D08-01/qualification.json`

## Package contents
- `visual-finish-worklist.json` — current major visual groups mapped to exact source/content/evidence lanes.
- `filesystem-map.json` — where editable art, Unreal content, raw captures, qualification evidence and package records belong.
- `release-handoff.md` — how D17 visual closure should hand off into existing D08 packaging without inventing a second pipeline.

## Use rule
Use current live files as authority. Re-read D17 assessment/qualification before acting because production may advance them.
Reuse accepted assets and evidence; fix only the smallest unmet layer.
Do not add final art under `Build/`, `Saved/`, `Intermediate/`, caches, or runtime-only paths.
Do not treat this helper package as completion evidence.
