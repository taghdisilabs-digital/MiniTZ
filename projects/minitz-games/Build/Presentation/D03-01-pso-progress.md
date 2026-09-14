# D03-01 PSO capture/replay checkpoint

Task status: **CONTINUE**. This increment qualifies an editable capture/replay harness and preserves a portable PSO description candidate. It does not enable a production cache or close D03-01.

The existing Linux Development SM6 package remains byte-identical. Its default Vulkan SM6/ProductionTSR path runs in the established isolated namespace, with source, editor, home and cook data hidden and network limited to loopback. Every experiment starts with an empty user/driver state; seeded launches add exactly one recorded PSO description file. OS page cache was not flushed. No driver cache is distributed.

## Implementation and diagnosis

`tests/run_d03_01_pso_capture.py` reuses the qualified surface and environment launch commands and verifies package, input, isolation, native gameplay, rendering and recording evidence. Each run preserves its exact runner snapshot. The native Vulkan file-cache compatibility gate defaults off when runtime precaching is active, so `-psocache` alone produced no recording. Enabling `r.Vulkan.EnablePSOFileCacheWhenPrecachingActive=1` with startup `-DPCVars` resolved that boundary. The first seed replay then failed because `-logpso` deletes the writable user cache. Explicit logging CVars preserve it; subsequent native logs confirm it opened. Both failed attempts and their passing gameplay observations remain intact.

`tests/verify_d03_01_pso_capture.py` replays all eight observations, the three matched command pairs, package/native-build identities, isolation checks, seven exact recording copies and the native commandlet dump. It separates the engine Runtime PSO counter from lower-level Vulkan creation timing. Recorded/precache initializers are excluded from the former. Graphics inner timings are excluded to avoid counting the outer timing twice.

## Observed results

| Run | Capture/replay result | Engine init seconds | Runtime counter >20 ms | Vulkan creations >20 ms ending after test start | Native frames / PNGs |
|---|---|---:|---:|---:|---:|
| `pso-capture-cold-01` | FAIL | 5.08 | 326 | 1899 | 1101 / 43 |
| `pso-capture-cold-02` | PASS | 5.39 | 333 | 1868 | 1109 / 43 |
| `pso-capture-cold-03` | PASS | 5.50 | 326 | 1835 | 1070 / 43 |
| `pso-seeded-cold-01` | FAIL | 5.28 | 324 | 1857 | 1098 / 43 |
| `pso-seeded-cold-02` | PASS | 26.48 | 0 | 0 | 1247 / 43 |
| `pso-seeded-cold-03` | PASS | 26.17 | 0 | 0 | 1188 / 43 |
| `pso-seeded-environment-01` | PASS | 26.14 | 0 | 1 | 1460 / 5 |
| `pso-empty-environment-01` | PASS | 5.27 | 331 | 1866 | 1459 / 5 |

All eight native gameplay scenarios succeeded: 9,732 frames and 268 runtime PNGs. Six capture/replay runs passed; two earlier attempts failed for the diagnosed configuration boundaries. The matched empty/seeded surface runs use identical commands after evidence/state path normalization, as do the environment pair. All seed comparisons use the same 27,941-byte recording, SHA-256 `c27735aaee29b1e257a6f5a7db5c29cc607ffc858fc52536ccc8c5b448e67900`.

Seeded launches reduced the Runtime counter to zero, while initialization rose from about 5.3–5.5 seconds to 26.1–26.5 seconds. A lower-level graphics creation lasting 186.892 ms ended after the seeded environment test began despite that zero Runtime counter. The experiment therefore does not establish complete PSO coverage or smooth cold launch. These logged creation durations can overlap and include worker/lock waits; they are not summed frame stalls.

The seeded surface repeat recorded screenshot-free wall-time p50/p95 of 14.34/16.00 ms while stationary and 14.00/15.44 ms during the camera pan; GPU medians were 6.147/6.234 ms. The matched empty run measured 15.65/20.72 ms and 14.54/18.17 ms, with GPU medians 6.173/6.258 ms. These short windows exclude startup and do not establish a general performance gain. Generated frames were not used.

The native `ShaderPipelineCacheTools Dump` read 66 descriptions: 63 graphics and three compute, with 43 Missed and 23 Precached classifications from capture time. The 66-job task-duration log precedes the Vulkan completion callback and excludes its long save/merge interval. Exact causal wait/driver costs need further instrumentation. No engine patch is justified by the current logs alone.

## Evidence and preservation

- `pso-capture-series-precommit-01.json`: full eight-run replay and 516 checked identities.
- `pso-recording-01/preservation.json`: seven canonical raw recording copies and exact original source identities. These are `GENERATED_DRAFT`, not production cache acceptance.
- `pso-recording-dump-01/`: native commandlet result and raw logs. A child trace server appended 770 bytes after the parent receipt; `final-log-readback.json` proves the original byte prefix and additive tail without rewriting the original result.
- `pso-source-notes-01.json`: exact installed UE 5.8.2 source hashes and line references supporting the counter/configuration/timing interpretation.
- `pso-visual-review-01.json`: two directly inspected original frames; readable gameplay, unfinished art.
- `D03-01-pso-increment.json` and `D03-01-pso-file-manifest.json`: bounded editable implementation and evidence identities.

The qualified native build, source, content, configuration, archive and predecessor evidence are preserved. These test-only changes do not require a new native build or cook. The previous SM5 fallback package results remain applicable; this seed is SM6-specific and has not been qualified for SM5, Shipping or another host. Audio used the existing dummy backend and is not an audible mix acceptance.

## Remaining work within D03-01

Integrate and measure a supported production PSO/loading path with startup responsiveness and sufficient coverage; do not ship this experimental seed or compatibility setting merely because its Runtime counter is zero. Investigate the completion/save/merge interval using the exact current engine before changing cache scheduling. Continue the already recorded final-world/art, fine temporal stability and broader VFX/audio gaps. Reuse completed contact, character action, vehicle, facade and package evidence unless materially invalidated.

Canonical local files are retained in the project and the archive remains at its existing games artifact path. The Auto Feeder owns GitHub/Drive publication and canonical state transitions. This checkpoint claims local commit/readback only; no remote publication or D03 completion is inferred.
