# P3-14 Delivery Qualification Evidence

Status: QUALIFIED_REFERENCE_CI
Recorded: 2026-09-04
Project: Biella Engine
Boundary: P3-14 packaging, publishing, release, and durable delivery

## Result

The bounded P3-14 qualification completed successfully on the durable `main` state in GitHub Actions.

- Workflow: `.github/workflows/p3-14-delivery-qualification.yml`
- Source commit: `cb451cc221993efd5963727866873c2256c1090e`
- Source tree: `cfcf31f27db642aad1539a5a040f0b5059e828dd`
- Workflow run: `33884528731`
- Job: `101060955843`
- Artifact: `p3-14-delivery-qualification`
- Artifact ID: `9941313281`
- Artifact ZIP digest: `sha256:9399ed9d797de916553a0db298f9e72b46d5150b557e6db742ba10424add59bb`
- Artifact size: `896380` bytes
- Artifact expiry observed: `2026-12-03T14:34:35Z`

Run URL: https://github.com/patrickminitz-web/biella-engine/actions/runs/33884528731

## Verification performed

- Focused P3-14 tests: PASS — `16 passed, 1 skipped` in `50.43s`
- Strict mypy: PASS
- Python compileall: PASS
- Wheel build: PASS
- Wheel: `dist/biella_engine-0.1.0-py3-none-any.whl`
- Wheel size: `898769` bytes
- Wheel SHA-256: `fac6cc513b400b0668038fcb9959260b51a4c1401016a1f1e03252341bbb516a`
- Evidence JSON SHA-256: `a46d93fe124aed54390540c6da26ef09aa9e70bd1aa1d200a3fa2f7cdf7d4870`
- Pytest output SHA-256: `b93e684d200bb4d0f0bb14ff629f6f74115627ea0eec013c081e80fbb7b0880a`

## Qualification classifications

- Focused CI tests: `REFERENCE_CI`
- L40S execution: `NOT_RUN`
- Live Cloudflare publish: `NOT_RUN`
- Drive publication: `NOT_RUN`

`Drive publication: NOT_RUN` is the P3-14 delivery-side-effect classification emitted by the qualification workflow. It is distinct from publication of canonical project-state and qualification evidence to Google Drive, which is recorded separately as verified.

The result proves the checked-in P3-14 source and packaging path under the stated CI environment. It does not claim that an L40S runtime, live Cloudflare account, or P3-14 Drive delivery side effect was exercised.

## Source identity

The generated evidence recorded these SHA-256 values:

| Path | SHA-256 |
|---|---|
| `.github/workflows/p3-14-delivery-qualification.yml` | `822ab14c2db3ba8a541d39978db562a9e24399476628b26a92440d3f8fa22d8a` |
| `src/biella/cloudflare_kv_publish.py` | `e04ef1339e15e85ce72ec4438874128246fa821d3a6e74caa58aed71c823a287` |
| `src/biella/delivery_pack.py` | `aba45023d6465f0f2da49c476761f6c2406e7f625aa41b441cccc2df292e4c34` |
| `src/biella/delivery_tool.py` | `fdd0c30f9b5b0e39dd013e1a3e4b4151911b3a69a8ff5a453ba0cf4171c37285` |
| `src/biella/production_integration.py` | `272b7f31538dd75a8818f4b35021b57602e3c344fb53e6d5892d1a168ce7d43d` |
| `tests/test_p3_14_cross_domain.py` | `6feb36f03e32e42488c38c6dfe53b8c069b5c248a48b3bafaa29d35eeca88b48` |
| `tests/test_p3_14_delivery_local.py` | `755ccd785657f4c646f8d354f071e900205a4063efacd381334e316df59b0a8e` |
| `tests/test_p3_14_delivery_pack.py` | `9a6320468d639de95ba707274f3b9858678aa0abb87018f378665184f3e5a981` |
| `tests/test_p3_14_delivery_publish.py` | `d28d1bb306b16179da048701a9302a5adb422881e4f98c4e4a6ad1a431d2fea7` |

## Bounded CI correction

The first qualification attempt (`33883082555`) failed because the GitHub runner did not provide the non-executed `/usr/bin/blender` and `/usr/bin/bwrap` fixtures expected by the existing P3-14 local tests. The workflow was corrected to install the same exit-97 non-executed fixtures already used by the successful P3-12/P3-13 CI workflows. Run `33883262378` then passed on the corrected workflow.

A subsequent qualification on the durable `main` state, run `33884528731`, also passed and is the current qualification referenced by the canonical project state.

This correction changes CI setup only; it does not alter production delivery behavior.

## Durable publication and readback

Canonical project-state/evidence publication is recorded as `VERIFIED` with these stable Drive file IDs:

- Current state: `1wiWcdWt4hmTf3narsLw4OqGu_ueKOSa4`
- Active task: `1liutA8evH6rPjk-U4tgR13l_kqBrx-DF`
- P3-14 evidence: `1qm2gmf2RWwGelwUa9KUfyUFxrd5GW-Ug`
- Qualification artifact: `1Pp2P3-n0pP25PtiMB5Ba46fLfcb22iJf`

The Drive qualification artifact is the `33884528731` ZIP and has recorded size `896380` bytes, matching the GitHub Actions artifact size.

## Durable boundary

P3-14 is `COMPLETE_DURABLE` under the bounded reference-CI qualification described above. The active project frontier is P4-06. No P4-06 completion or consumer activation is claimed by this record.

L40S execution and live Cloudflare publishing remain `NOT_RUN`. Historical data is not promoted by this evidence.
