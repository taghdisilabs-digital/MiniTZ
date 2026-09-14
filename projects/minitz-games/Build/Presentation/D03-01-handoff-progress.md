# D03-01 — First-world startup handoff

Task status: **CONTINUE**. The packaged game now keeps the Biella preparation screen over the first world draws until its startup readiness checks and two RHI submissions complete. The four enabled runtime scenarios show no uncovered samples between the preparation screen and the first scene candidate. This closes the demonstrated startup coverage defect in these fixtures; production art, uninterrupted indicator motion and wider D03 qualification remain open.

The existing engine preloader and a new startup-only viewport overlay share the exact editable Slate artwork. The overlay is cosmetic and hit-test invisible. It changes neither simulation, possession nor input. It checks the active game world, begun play, a possessed pawn, rendered view locations, visible asset-bearing mesh proxies and currently active pipeline precompiles. An asynchronous RHI submission fence prevents an enqueue callback alone from releasing the overlay. Two qualifying submissions are required. World/proxy/precompile changes reset the count; exit, viewport loss or a 30-second game-frame-polled timeout release with an explicit non-ready diagnostic. This is not a GPU-completion, temporal-convergence or future-PSO guarantee, and does not cover later map travel.

`handoff-design-01.json` records the installed UE 5.8.2 source basis. Initial map loading precedes the engine preloader wait; world rendering follows it. The new overlay covers that observed boundary. Historical receipts remain unchanged.

Native `handoff-build-01` passed from exact source in 113.08 seconds. `handoff-stage-01` reuses the previously qualified unchanged SM5/SM6 cook. Only the native executable and project descriptor inside the base pak change. All 1,732 extracted pak members and all 33 archive members were read back; paired IoStore content remains unchanged. This is not a fresh full cook.

Canonical candidate: `/root/biella/artifacts/games/D03-01/BiellaGames-Linux-Development-D03-01-handoff-candidate-01.tar.zst`, 481,443,287 bytes, SHA-256 `655c314d2d552749f7ece123e4183c5467d655e00c6faebacf3b425046272859`.

`handoff-series-01.json` passes 4,123 exact file-identity checks. Five completed isolated packaged runs preserve package and test-input bytes throughout, with 6,211 native scenario frames and 596 captured display frames.

| Run | Native scenario | Last loader / first scene frame | Uncovered handoff samples | Overlay duration |
| --- | --- | --- | ---: | ---: |
| Cold SM6 / TSR | PASS | 63 / 64 | 0 | 3.416 s |
| Warm SM6 / TSR | PASS | 33 / 34 | 0 | 0.409 s |
| Same-binary overlay disabled | PASS; handoff correctly rejected | 49 / 60 | 10 | Disabled |
| Cold SM5 / TAA fallback | PASS | 52 / 53 | 0 | 2.616 s |
| Cold environment regression | PASS | 64 / 65 | 0 | 3.332 s |

All enabled overlays release once with `reason=ready`, two submissions, 91 qualifying meshes, no missing proxies and zero currently active precompiles. The original cold baseline is rejected for frames 48–56. Disabling only the overlay on the new binary reproduces uncovered frames 50–59 while gameplay still passes. These real captured negative controls validate the missing-scene check.

The initial warm attempt exited 143 before native scenario completion. Its partial output remains in `handoff-runtime-warm-01/`; no source fault or interruption cause is inferred. `handoff-warm-recovery-01.json` records process absence and the cache snapshot. The successful warm retry follows the exact chain cold-after → interrupted-warm-before → preserved recovery state → warm-retry-before. Cache state was not cleared. Cold launches use fresh task user caches; host OS page cache is not flushed.

`handoff-visual-review-01.json` records exact decoded frames and direct review. Cold, warm, fallback and environment transitions show the preparation screen followed by the existing playable world. The disabled control visibly exposes HUD and sky over an unrendered dark world. The classifier is specific to this fixture and sampled at 10 Hz; it does not establish visibility between samples or later in play.

The cold capture still contains a roughly 2.1-second internal run of unchanged indicator samples. Covering the world gap does not establish continuously animated startup. The world also retains prototype mannequin characters, sparse architectural detail and black outer edges. Final art, broader VFX/audio and fine temporal/native performance qualification remain open. Lossy, instrumented 1280×720 display capture is not a native frame-time benchmark or a startup speed claim. Dummy audio provides no audible-mix qualification. All media and the package remain `GENERATED_DRAFT`.

Implementation, passed evidence, negative controls and interrupted evidence are preserved locally. Auto Feeder owns GitHub/Drive publication and canonical task transition. No remote publication or D03 completion is claimed; 03/04 identity, Project status/order, predecessor evidence and Engine P4-06 deferral remain unchanged.
