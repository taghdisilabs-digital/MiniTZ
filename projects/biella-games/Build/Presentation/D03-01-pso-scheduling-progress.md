# D03-01 PSO scheduling checkpoint

Task status: **CONTINUE**. The alternate native scheduler is not accepted as a production startup optimization. No game source, content, configuration or package changed. This checkpoint extends the native PSO capture/replay evidence in `D03-01-pso-progress.md`; it does not close D03-01.

## Change and controlled comparison

`tests/run_d03_01_pso_capture.py` now accepts an optional `--precache-thread-pool 0|1` startup override and requires its native log readback. Omitting it preserves existing launch behavior. `tests/verify_d03_01_pso_scheduling.py` verifies the two recorded runs against the preceding seeded baseline, including exact command equivalence except for that one setting, isolated state, native assertions, package/build identities, runner snapshots, captures and preserved recordings.

The runs use the same qualified Linux Development SM6 archive and the same 66-description PSO seed. The archive SHA-256 is `057eff4cec157e002d9ea3b735bb9e41c9a7bc66853ad4a338e86d498cc58d8e`; seed SHA-256 is `c27735aaee29b1e257a6f5a7db5c29cc607ffc858fc52536ccc8c5b448e67900`. Each run starts with fresh isolated writable state containing only the supplied seed. The package is read-only; network and hidden host state are excluded by the existing namespace harness. OS page cache was not flushed. Runs were sequential with no concurrent heavy local work.

## Native evidence

| Observation | Alternate pool=0 | Native pool=1 |
| --- | ---: | ---: |
| Engine initialization | 25.60 s | 26.46 s |
| Native frames / captures | 1,093 / 43 | 1,192 / 43 |
| Completion callback to saved log | 1.764 s | 3.297 s |
| Saved log to no-jobs-remaining log | 19.391 s | 20.328 s |
| Runtime PSO creation over 20 ms, count / maximum | 196 / 373.11 ms | 2 / 20.53 ms |
| Vulkan creation over 20 ms ending after initialization, count / maximum | 3 / 383.230 ms | 3 / 373.139 ms |
| Vulkan creation over 20 ms ending after test start | 0 | 0 |
| Stationary screenshot-free frames / wall p50 / p95 | 235 / 14.914 / 16.648 ms | 253 / 14.137 / 15.637 ms |
| Camera-pan screenshot-free frames / wall p50 / p95 | 231 / 15.167 / 17.314 ms | 242 / 14.420 / 15.996 ms |

Both native surface scenarios passed the existing material, architecture, view and gameplay assertions. The series verifier passed with **255 checked identities**, **2,285 native frames** and **86 captures**. These frame windows exclude startup and screenshot requests. No generated frames were used. SDL dummy audio means this experiment provides no audible-mix acceptance.

The Runtime counter excludes classes of precache work; it is not interchangeable with the lower Vulkan creation log. Creation durations can overlap and include waits, and end timestamps only classify observations. Do not sum them as frame stalls. Callback intervals do not isolate driver execution, locking or merge costs.

This single matched pair does not establish a significant startup gain. The long saved-to-finished interval remains in both runs. The alternate setting is therefore not promoted; no affected environment replay or new game build/cook is warranted for a rejected harness-only experiment. Native engine source identities and the exact relevant boundaries are recorded in `pso-scheduling-source-notes-01.json`.

## Preservation and remaining work

- Raw runtime evidence: `pso-scheduling-legacy-cold-01/` and `pso-scheduling-pool-cold-01/`.
- Exact recording copies: `pso-scheduling-recordings-01/preservation.json`.
- Machine verification: `pso-scheduling-series-01.json`.
- Direct native screenshot inspection: `pso-scheduling-visual-review-01.json`.
- Scope and file identities: `D03-01-pso-scheduling-increment.json` and `D03-01-pso-scheduling-file-manifest.json`.

The inspected frame retains readable player/HUD and PBR surface detail, while sparse repeated architecture, exposed black world edges and prototype art remain unfinished. Media and recordings remain `GENERATED_DRAFT`. This is not Shipping, cross-hardware, fine temporal quality or final art acceptance.

The next startup boundary is a supported preparation/loading path with measured responsiveness during expensive native work. Native preload Slate submits render-thread work, so adding a spinner alone does not prove responsiveness. Preserve this scheduling result rather than repeating it. D03-01 also retains the production art, finer temporal presentation and broader VFX/audio qualification gaps from prior progress reports.

Canonical local files are retained here and in the existing canonical artifact directory. Auto Feeder owns GitHub/Drive publication and canonical task transitions. This checkpoint claims local commit/readback only and does not claim remote publication or edit Project status/order metadata.
