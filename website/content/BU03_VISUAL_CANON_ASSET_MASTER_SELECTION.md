# BU-03 — Visual Canon and Asset Master Selection

Task: `WEB-BU-03`
Selection date: `2026-09-01`
Scope: Website visual slots `01`–`50` only.

## Current authority and source identity

- Website branch before BU-03: commit `a7def2978423ed83b8c79b989202df5535ea9f4d`, tree `57dedc64b81a9e4a91c3a053ad04eb8b9088b8f3`.
- Engine `main` observed during BU-03: commit `7a4feb3b1ff32300be67be0c36f1fd923a288e6b`, tree `5ce486ac3cc846c4dc2693861981e4bdb45a095c`.
- Canonical Website asset manifest: Drive `11skZ-wCs4fX2dG2Q-OzXAjcFufFX33-8`; GitHub blob `4704e5b0792835dd867782afe2e6ebbb1c7cdac8`.
- BU-02 classification: GitHub blob `9c97031a4cff1dfa3a474a7c47b37e2f6f31f711`; Drive `1nDAKjiQNnxtxqEQ4aO0Cn_7m9p0CYPEAivQebFWczIw`.
- Existing visual-resolution record: Drive `1tZs8oWUfXB9BOyYQe_-DaTk8tGcQpHLGTrwBVg4rq0k`; GitHub `website/content/asset-resolution.json` blob `eee8a2fb386d22ec465b94546b74967bf092ca38`.

## Visual canon

BU-03 preserves the canonical `BIELLA VISUAL LOCK` from the asset manifest without modification: transparent background; no surrounding scenery; no giant mechanical frame; no blue/orange arcade-HUD treatment; deep graphite/navy surfaces; Biella violet dominant accent; electric cyan secondary accent; semantic green/amber/red only; thin precision borders; subtle glass/emissive edges; restrained bloom; compact typography; dense professional workstation UI; production-grade game-engine/editor aesthetic; modular implementation-ready components; consistent album identity.

## Fresh source-resolution evidence

A fresh exact-name Drive query covered all 50 canonical visual filenames and returned `0` exact matches. The canonical `30_VISUAL_MASTERS` Drive folder currently contains only `WEBSITE_VISUAL_MASTER_RESOLUTION_01_50`, not image master bytes.

The verified BU-01/BU-02 boundary remains valid: UUID/generated-image, generic image, historical, and Biella Games visual material cannot be promoted by filename similarity or guess. Exact source bytes plus slot provenance are required before dimensions or SHA-256 can be asserted.

## Selection determination

- Visual slots evaluated: `50 / 50`.
- Byte-qualified canonical visual masters selected: `0 / 50`.
- Genuine source-byte gaps: `50 / 50` — slots `01` through `50`.
- Dimensions available for selected masters: `0`; all unresolved values remain `UNKNOWN`.
- SHA-256 available for selected masters: `0`; all unresolved values remain `UNKNOWN`.
- Unqualified generated/UUID candidates promoted: `0`.
- Superseded assets promoted: `0`.

For every registered visual slot `01`–`50`, the canonical filename and manifest visual status remain the registration/control identity, while the BU-03 master-selection state is exactly:

`GAP_SOURCE_BYTES_UNRESOLVED`

with:

- `Exact_Source_Identity = UNKNOWN`
- `Dimensions = UNKNOWN`
- `SHA256 = UNKNOWN`

The full per-slot canonical filenames and manifest statuses remain in `docs/biellawebsite/MINITZ_WEBSITE_ASSET_MANIFEST.md`; this result does not rewrite or fabricate them.

## Validation

The completion criterion is satisfied as a selection determination against the current verified corpus: every visual slot has been evaluated, every available byte-qualified master would have been selected with exact identity/dimensions/digest, and every unavailable master is recorded as a real gap rather than guessed. Current verified availability is zero, so the correct selected-master set is empty and the gap set is exactly slots `01`–`50`.

## Boundary

BU-03 does not generate missing art, migrate assets, build Website UI, alter Engine/Game mechanisms, or start BU-04/BU-11. Later tasks must not treat a registered filename, `APPROVED_REFERENCE`, or `VISUAL_LOCK_FINAL` label as proof that source bytes exist.