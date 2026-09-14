# Visual-to-Release Handoff

Status: `PROJECT_SUPPORT_NON_AUTHORITY`

## Current reusable release foundation
`Build/Release/D08-01/qualification.json` records a verified Linux Development diagnostic lineage with exact package membership, manifests, install/update readback and native runtime evidence. It explicitly does not qualify Win64 Shipping.

D17 already reuses that implementation through `tests/package_d17_01.py`. Keep using the D08 package/manifests/install functions; do not create a second package format or installer lineage for visual work.

## Handoff sequence
1. Finish the active D17 slice against `docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md`.
2. Keep editable art in `SourceAssets/` and canonical Unreal assets in `Content/`.
3. After each material source/content change, run only the affected build/cook/package/runtime evidence required by the current task.
4. Bind raw normal-camera captures to the exact installed package/source identity.
5. D17-07 closes only when the environment/material/lighting/world layer has zero major visual defects under its task contract.
6. D17-08 indexes the truthful raw gameplay, captures, editable-source identities, build/cook/stage/package identities and criterion results; it must not copy predecessor packages just to rename them.
7. Reuse `tests/run_d08_01_release.py` and `tests/verify_d08_01_release.py` for exact-member package/install verification.
8. Reuse `tests/package_d17_01.py` for D17 package binding instead of duplicating release logic.
9. Preserve Linux Development evidence as diagnostic evidence only.
10. Win64 Shipping becomes acceptable only after its own real build/package/native-play evidence on the required Windows resource; never infer it from Linux results.

## Package truth requirements
- source/material input identity
- native build identity
- cook receipt
- stage/archive readback
- exact package member bytes and permissions
- installed manifest readback
- raw gameplay/runtime evidence tied to that package
- task-specific visual acceptance evidence

A successful build, screenshot, archive, or package hash alone is not final release acceptance.
