# D03-01 — Separate automatic PSO observations

Task status: **CONTINUE**. Startup now reports automatic graphics/compute PSO requests separately from file-cache precompiles. The production wait policy stays at its prior default. Waiting for all currently observed automatic work is retained only as an explicit diagnostic option: it adds about 23 seconds to these cold loaders and still fails the sampled indicator-motion check.

The installed UE 5.8.2 source shows that `GetNumActivePipelinePrecompileTasks()` tracks `bFromPSOFileCache` work; `NumActivePrecacheRequests()` reports a separate, priority-filtered automatic count. These Vulkan runs enable automatic precaching with both priority filters at zero and observe no file-cache tasks. Default cold SM6 release reports file-cache zero but 5,379 automatic requests; world handoff still reports 4,150. The earlier zero-pending value was a statement about the selected wait policy, not an all-PSOs-ready guarantee.

`BiellaStartupPipelines.*` shares the read-only observation and policy between the preloader and existing cosmetic viewport overlay. The final default adds no automatic wait. `-BiellaWaitForAutomaticPSOs` opts in; `-BiellaSkipAutomaticPSOWait` overrides that option. Separate start/stop/handoff log records and an output-enabled, capped CSV expose both counters. Gameplay, input, collision, compilation scheduling and engine source remain unchanged. Separate atomic reads are not a future-request barrier or GPU fence. The existing two-submission handoff check retains its earlier limits.

`automatic-pso-build-02` passed from exact current source in 105.552 seconds. Candidate 02 reuses the unchanged qualified SM5/SM6 cook; the native executable and project descriptor inside the base pak are the only changed archive content. All 1,732 pak members and 33 archive members were read back. This is an incremental package qualification, not a fresh full cook.

Canonical local candidate: `/root/biella/artifacts/games/D03-01/BiellaGames-Linux-Development-D03-01-automatic-pso-candidate-02.tar.zst`, 481,426,583 bytes, SHA-256 `c85bb02bd03c496cb71372816722246ddd952eeb7fe755f7c5aaa785e7b12240`.

`automatic-pso-series-01.json` passes 7,744 exact identity checks. The seven completed packaged scenarios preserve their package and test-input bytes. The final candidate supplies five runs; two preserved candidate-01 runs document the original full-wait trial and its same-binary bypass. The default-to-warm cache chain is byte-exact.

| Run | Candidate | Native scenario / handoff | Loader | Handoff | Longest sampled static interval | >=1s motion gate |
| --- | --- | --- | ---: | ---: | ---: | --- |
| default-01 | 02 | PASS / PASS | 0.750 s | 3.376 s | 2.0 s | FAIL |
| warm-01 | 02 | PASS / PASS | 0.649 s | 0.400 s | 0.3 s | PASS |
| sm5-01 | 02 | PASS / PASS | 0.612 s | 2.418 s | 0.8 s | PASS |
| environment-01 | 02 | PASS / PASS | 0.771 s | 3.431 s | 2.0 s | FAIL |
| optin-01 | 02 | PASS / PASS | 23.104 s | 1.489 s | 1.0 s | FAIL |
| cold-01 | 01 | PASS / PASS | 23.979 s | 1.516 s | 1.3 s | FAIL |
| disabled-01 | 01 | PASS / PASS | 0.743 s | 3.394 s | 3.0 s | FAIL |

Total evidence: 9,336 native scenario frames and 1,279 captured display frames. All seven handoffs release with `reason=ready`, two submissions, no missing proxies and no uncovered samples. The SM5/TAA fallback and environment regression pass. These scenario counts are not native frame-time measurements.

The original full-wait trial increased loader duration from 0.743 to 23.979 seconds while retaining a 1.3-second static indicator interval. The final explicit opt-in independently reports zero in both counters at loader and handoff release, but still has a 23.104-second loader and a 1.0-second static interval. This rejects full automatic waiting as the production solution. The code comment associating the remaining stall with new world PSOs is an inference; causal attribution has not been isolated.

The strict wait-and-motion verifier intentionally remains failed: default/bypass cases reject the full-wait condition, and opted-in cases reject the static indicator. Its failures are preserved separately from telemetry/native-scenario PASS. The historical pre-instrumentation negative control rejects missing counters. The corrected interval calculation uses first-to-last sample time; the old 2.1-second sample-bin receipt remains unchanged and the corrected historical interval is 2.0 seconds.

`automatic-pso-visual-review-01.json` records 18 unchanged decoded PNGs and the 15 directly reviewed frames. They show the preparation screen, repeated static segment positions, and transitions into the existing playable world. The source review records the exact installed-engine basis, independent-counter/future-request limits and the disposition of bounded local-Qwen assistance. Unverified suggested APIs and spin waits were not adopted.

Limitations: 10 Hz lossy 1280×720 X11 capture cannot qualify continuous animation or native frame times; RHI submissions do not establish display completion. Cold fixtures use fresh task user caches; host OS page cache is not flushed. Dummy audio supplies no audible-mix qualification. The world retains prototype mannequin art, sparse architectural detail and black outer edges. Final art, broader VFX/audio, uninterrupted startup motion and finer temporal/native performance evidence remain open.

All media and package candidates remain `GENERATED_DRAFT`. Canonical local bytes are retained. Auto Feeder owns GitHub/Drive publication and canonical task transition; this increment makes no remote-publication or D03-completion claim. 03/04 identity, Project status/order, predecessor evidence and Engine P4-06 deferral are unchanged.
