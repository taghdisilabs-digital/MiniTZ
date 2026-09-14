# D03-01 default SM6 and explicit SM5 packaged-world qualification

**D03-01 remains CONTINUE.** The authored playable world now passes isolated Linux Development package qualification on the default SM6/Nanite/TSR path and explicit SM5/TAA fallback. All six runs use one exact archive. The prior SM5-only archive and its historical receipts remain preserved.

Canonical archive: `/root/biella/artifacts/games/D03-01/BiellaGames-Linux-Development-D03-01-sm6-package-01.tar.zst` — 481,060,250 bytes; SHA256 `057eff4cec157e002d9ea3b735bb9e41c9a7bc66853ad4a338e86d498cc58d8e`. All 33 archive members match the stage and extracted readback. Captures remain `GENERATED_DRAFT`; this is not final art acceptance.

## Editable implementation and exact lineage

`tests/run_d03_01_package.py` now distinguishes forced feature level from the expected native observation. Default SM6 runs have no forced feature-level argument. Explicit fallback runs use `-sm5`. The harness verifies actual shader platform, renderer capabilities, all six authored facade mesh identities and their platform-specific proxies. It retains isolated cache state, source identities, actual native view/scenario joins and commands. The missing-cache runner supports an exact SM5 or SM6 control. `verify_d03_01_sm6_package.py` replays native views, platform, facade and scenario validation, verifies file identities and rejects six opposite-feature-level assertions.

The game source, Content and Config are unchanged from facade commit `d5d695da5933a417f5c996278d67829dcbfbd14d`. `package-sm6-build-01` records a 109.45-second native game build with 85 unchanged build inputs and exact restored installed-engine marker. Its 298,959,360-byte binary has SHA256 `72cb697cc2d9402c48d68659d3498b8266d8332ad014e5bae162d89cd829e04f`. The same binary appears in the cook snapshot and archive.

`package-sm6-cook-01` records 329 canonical inputs, an initially empty isolated DDC, 21,898 compiled shaders across SM5 and SM6, 679 cooked packages, zero incrementally skipped packages, 35 platform skips, and zero final errors or warnings. The cook took 1,376.21 seconds. The existing exact-match config repair preserves the generated private cook append and restores the canonical snapshot bytes; private credential contents are excluded from public evidence. `package-sm6-stage-01` stages from that preserved Zen store and verifies the archive and every extracted member in 51.76 seconds. Existing qualified engine dependency repairs and notices are reused.

## Native runtime proof

Each process runs with a read-only package, hidden editor/project/cook/home paths, task-local user and driver caches, and a loopback-only network namespace. Cold states start empty; warm states continue from the exact preceding state. OS page cache was not flushed. Tests run at 1280×720 with VSync and motion blur off; surface windows are uncapped, environment scenarios capped at 60. No generated frames are used. SDL dummy audio means these runs add no audible-mix qualification.

| Platform / profile / scenario | Frames | Captures | PSO creations over 20 ms | Largest creation ms |
| --- | ---: | ---: | ---: | ---: |
| Default SM6 / TSR / cold surfaces | 1,096 | 43 | 344 | 927.78 |
| Default SM6 / TSR / warm surfaces | 1,151 | 43 | 13 | 36.54 |
| Default SM6 / TSR / environment | 1,464 | 5 | 4 | 30.75 |
| Explicit SM5 / TAA / cold surfaces | 1,298 | 43 | 217 | 318.07 |
| Explicit SM5 / TAA / warm surfaces | 1,230 | 43 | 6 | 30.40 |
| Explicit SM5 / TAA / environment | 1,457 | 5 | 6 | 28.69 |

All six pass. The native renderer reports all six facade meshes with Nanite proxies on SM6 and zero Nanite proxies on SM5. Packaged Global/game shader libraries contain 8,887/2,009 unique shaders on SM6 and 6,431/1,480 on SM5. Environment checks preserve weapon interaction, panel destruction, hazard damage, safe-switch behavior, stream return and restart. Material fallback/error checks pass.

Screenshot-free native timing windows on the recorded Development host:

| Platform / state / window | Samples | Wall p50 / p95 ms | GPU p50 ms |
| --- | ---: | ---: | ---: |
| SM6 cold stationary | 234 | 14.855 / 19.106 | 6.224 |
| SM6 cold camera pan | 220 | 15.456 / 19.210 | 6.319 |
| SM6 warm stationary | 247 | 14.130 / 15.875 | 6.172 |
| SM6 warm camera pan | 254 | 13.993 / 15.830 | 6.246 |
| SM5 cold stationary | 297 | 11.803 / 15.004 | 3.394 |
| SM5 cold camera pan | 264 | 12.942 / 14.662 | 3.409 |
| SM5 warm stationary | 289 | 12.221 / 13.504 | 3.397 |
| SM5 warm camera pan | 259 | 13.659 / 14.887 | 3.412 |

`package-sm6-series-precommit-01.json` replays 7,696 native frames and 182 captures with 2,551 exact checked identities. Nine directly reviewed PNGs are identified in `package-sm6-visual-review-01.json`: player, facades, HUD, threats, live floor and destruction remain readable in both paths. The sparse surroundings and remaining simple structures are unfinished art. Gross image-delta checks and selected stills do not establish fine ghosting, disocclusion or temporal quality.

## Negative control, durability and remaining quality

`package-sm6-missing-shader-01` removes only `Engine/GlobalShaderCache-VULKAN_SM6.bin` from a separate package copy. Native startup exits 1 in 1.923 seconds and explicitly identifies the missing file. All other 1,731 logical pak files and IoStore containers remain unchanged. The canonical archive/extraction are verified before and after. This demonstrates an actual packaged shader dependency rather than access to hidden editor caches.

The configured local Qwen review adapter timed out; its exact inputs and failure remain in `package-sm6-resource-review-01` and the failure ledger. Direct source review and the actual native/negative/readback checks completed the bounded validation.

Cold PSO creation remains a production gap. The largest SM6 event is a compute shadow-projection PSO; warm cache results do not prove first-launch smoothness. Worker creation durations may overlap and are not additive wall-frame stalls. Current evidence proves shader availability and functional native rendering, not acceptable cold-launch frame pacing. The next bounded work should address this measured gap while preserving this archive and baseline.

Fine temporal and high-speed motion quality, broader transitions/VFX/audio, final world/lighting/character/weapon/vehicle art, and wider hardware/Shipping qualification also remain. This increment does not advance the task or reopen passed animation/contact/vehicle work. Local commit and exact Git-object readback precede handoff; the Auto Feeder owns GitHub/Drive publication and canonical state transition. No remote publication is claimed here.
