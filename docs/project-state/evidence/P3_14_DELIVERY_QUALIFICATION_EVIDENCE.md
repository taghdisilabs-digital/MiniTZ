# P3-14 Delivery Qualification Evidence

Status: QUALIFIED_REFERENCE_CI
Recorded: 2026-09-04
Project: Biella Engine
Boundary: P3-14 packaging, publishing, release, and durable delivery

## Result

The corrected P3-14 qualification completed successfully in GitHub Actions.

- Workflow: `.github/workflows/p3-14-delivery-qualification.yml`
- Source commit: `ae5d69a0686968af96283260d1c8073f84a833d2`
- Source tree: `39d8f9e338365a28437b44eebde601c80f49508a`
- Workflow run: `33883262378`
- Job: `101056787223`
- Artifact: `p3-14-delivery-qualification`
- Artifact ID: `9940829453`
- Artifact ZIP digest: `sha256:570fb404db6b06526ce3cd0066eb86442861e3fdbba4bf48187d9d80617fff9b`
- Artifact size: `896397` bytes
- Artifact expiry observed: `2026-12-03T14:21:32Z`

Run URL: https://github.com/patrickminitz-web/biella-engine/actions/runs/33883262378

## Verification performed

- Focused P3-14 tests: PASS — `16 passed, 1 skipped` in `64.20s`
- Strict mypy: PASS
- Python compileall: PASS
- Wheel build: PASS
- Wheel: `dist/biella_engine-0.1.0-py3-none-any.whl`
- Wheel size: `898769` bytes
- Wheel SHA-256: `f299003409190d3d06b4cf1bb9c3273fa7ffcc74eaf71b55ce4429a7f2aa3233`
- Evidence JSON SHA-256: `561d758b00dec158c03ccfe6b51526de44394fe8d6dd074e9fdaeef4c2040a1f`
- Pytest output SHA-256: `e19e30b0fc961aca99b5b0bc002fa4a520dcab61a71d3d886ee6c19abe8e9501`

## Qualification classifications

- Focused CI tests: `REFERENCE_CI`
- L40S execution: `NOT_RUN`
- Live Cloudflare publish: `NOT_RUN`
- Drive publication: `NOT_RUN`

The result proves the checked-in P3-14 source and packaging path under the stated CI environment. It does not claim that an L40S runtime, live Cloudflare account, or Drive side effect was exercised.

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

The first qualification attempt (`33883082555`) failed because the GitHub runner did not provide the non-executed `/usr/bin/blender` and `/usr/bin/bwrap` fixtures expected by the existing P3-14 local tests. The workflow was corrected to install the same exit-97 non-executed fixtures already used by the successful P3-12/P3-13 CI workflows. The next run (`33883262378`) passed.

This correction changes CI setup only; it does not alter production delivery behavior.

## Durable boundary

P3-14 is qualified in reference CI. The next project frontier remains P4-06. No P4-06 implementation or consumer activation is claimed by this record.

No historical payload, secret, or unverified runtime claim is promoted by this evidence.
