# D03-01 — Native engine-preload presentation

Task status: **CONTINUE**. This increment adds a native, editable Biella startup screen to the existing packaged game. It validates engine-preload presentation and preserves the known first-scene gap; it does not qualify continuous startup readiness or close D03-01.

`BiellaLoadingScreen` loads at `PreLoadingScreen`. Slate draws a title, preparation text and a geometry-only activity segment without game assets, a fabricated percentage or game-thread animation. Completion latches after engine initialization and currently active native pipeline precompiles finish. It cannot promise that subsequent gameplay will never create another pipeline. Optional render telemetry is serialized after the native manager joins its loading renderer.

The first marquee implementation produced a static bar in the captured display despite successful native callbacks. Its rejection and original capture remain in `loading-static-marquee-rejection-01.json` and `loading-runtime-cold-04/`. The replacement visibly moves in decoded cold and warm frames. Actual display capture is separate from callback telemetry.

Native build `loading-build-03` passed from the exact current source. `loading-stage-05` reuses the previously qualified SM5/SM6 cook after byte verification. Only the executable and the descriptor inside the existing base pak change; the paired IoStore content is preserved. Native pak extraction verifies all 1,732 members, with only `BiellaGames/BiellaGames.uproject` changed. Archive extraction verifies all 33 members. This is a new executable/descriptor candidate over an unchanged qualified cook, not a fresh full cook.

Canonical candidate: `/root/biella/artifacts/games/D03-01/BiellaGames-Linux-Development-D03-01-loading-candidate-05.tar.zst`, 481,488,626 bytes, SHA-256 `a42cc2924442fa4e1b528581c3308bc17cc1b92f5e247a07143f7f26f1f437f6`.

`loading-series-01.json` passes 4,107 exact file-identity checks and five isolated native launches, with 6,531 scenario frames and 594 display-capture frames. Cold runs use empty task-specific user caches; warm reuses the exact cold state. The host page cache is not flushed. Capture is instrumented, lossy 1280×720 at 10 Hz; these intervals are observations, not a startup latency improvement or a native frame-time benchmark.

| Run | Native result | Captured frames | Last loading → scene candidate | Trailing unchanged indicator samples |
| --- | --- | ---: | ---: | ---: |
| SM6 TSR cold | PASS | 122 | 1.0 s | 2.0 s |
| SM6 TSR warm | PASS | 107 | 0.1 s | 0.3 s |
| Disabled control | PASS; no loader | 125 | N/A | N/A |
| SM5 TAA fallback | PASS | 110 | 1.5 s | 0.9 s |
| Environment regression | PASS | 130 | 1.0 s | 2.4 s |

All enabled runs stop once with engine-finished/ready true, no exit request, and zero active precompile tasks. Existing surface, movement, shader-platform and architecture checks pass where requested; the affected environment scenario also passes. Disabling the loader removes its native lifecycle, telemetry and captured screen while preserving the scenario. Package and runtime inputs remain byte-identical throughout each launch.

Direct inspection rejected cold frame 48: it shows HUD over an unrendered dark scene. The tighter v2 display classifier excludes HUD regions, identifies the later scene candidate at frame 57, and has a real-frame negative control against frame 48 plus positive frame 60. Original v1 observations remain intact; `loading-cold05-display-revalidation-01.json` records the correction. This fixture-specific classifier supplements direct visual review; it is not a general image-quality or readiness oracle.

The initial native `LoadMap` occurs before the loading screen stops. Adding another map-load callback is therefore not a demonstrated repair for the later scene gap. The next startup investigation must correlate first world draws/presents and pipeline readiness after engine initialization with the preserved display capture. A later implementation must retain the functioning engine preloader and demonstrate an uninterrupted visible handoff on cold and fallback launches.

`loading-visual-review-01.json` preserves decoded frame identities and review findings. The current world remains prototype art with mannequin characters, sparse architecture and black world edges. Final world/character art, broader VFX/audio, fine temporal/native performance qualification and first-frame startup readiness remain D03-01 work. Captures and the candidate remain `GENERATED_DRAFT`; no owner acceptance, Shipping, cross-hardware, generated-frame or audible-mix claim is made.

Implementation and all failed/passed evidence are preserved locally. Auto Feeder owns GitHub/Drive publication and canonical task transition; this increment makes no remote-publication claim and changes no 03/04 identity, Project task order/status, predecessor evidence or Engine P4-06 deferral.
