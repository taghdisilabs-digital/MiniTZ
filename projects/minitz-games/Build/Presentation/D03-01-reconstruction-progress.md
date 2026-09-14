# D03-01 reconstruction fallback increment

**Task remains CONTINUE.** Version 1 launch profiles now select ProductionTSR or NativeTAA in the existing playable world. NativeTAA runs at 100% resolution with temporal upsampling and dynamic resolution disabled. The accepted Deferred/Nanite/Lumen/VSM baseline remains active. Game-instance initialization applies the profile; gameplay authority is unchanged.

`BiellaRenderProfile.*` uses installed Unreal capability checks, emits selection/fallback diagnostics, and optionally records constructed native game-thread views. Unknown explicit profiles select NativeTAA. Explicit console overrides retain their normal priority and are detectable independently of the selection log. See `docs/RECONSTRUCTION_PROFILES.md` for launch and verification commands.

| Evidence | Result | Observed gameplay frames |
| --- | --- | --- |
| `reconstruction-tsr-02/validation.json` | PASS | 1282 |
| `reconstruction-taa-01/validation.json` | PASS | 1326 |
| `reconstruction-environment-tsr-01/validation.json` | PASS | 1456 |
| `reconstruction-environment-taa-01/validation.json` | PASS | 1454 |
| `reconstruction-invalid-01/validation.json` | PASS | 1437 |
| `reconstruction-override-01/negative-readback.json` | EXPECTED_NEGATIVE_CONTROL: rendered FXAA rejects TSR claim | 1421 |
| `reconstruction-controls-01/result.json` | 13 deliberately corrupted view-evidence cases rejected | Offline replay |

All 6,955 positive scenario frames join to native primary views with the expected AA/resolution state, Lumen GI/reflections, virtual shadows, Nanite, hardware RT disabled and no external temporal upscaler. The environment scenarios cover two real weapon input events, panel destruction and Chaos debris, shared hazard damage, safe-floor control, traversal, stream-out/return, and restart. Both profiles pass on the same exact source/module lineage.

`reconstruction-build-01/result.json` records a successful 16.379893-second native editor build with 85 unchanged source identities. `D03-01-reconstruction-final-readback-01.json` verifies 331 current input identities, all 85 build source files, six closed native runs and 182 decoded 1280×720 captures. The earlier failed `reconstruction-tsr-01` remains intact: its verifier incorrectly required one view family per global frame during loading; the repaired verifier keeps and checks every matching primary view. Fresh `reconstruction-tsr-02` passes.

The following native measurements use screenshot-free stationary and camera-pan windows at 1280×720, uncapped, VSync off, dynamic resolution off, on the recorded NVIDIA L40S / driver 580.178.04 / Linux Vulkan Development environment. Existing development caches and the opt-in view observer are included. Generated frames are not used.

| Profile / window | Samples | Wall p50 / p95 ms | GPU p50 ms |
| --- | ---: | ---: | ---: |
| ProductionTSR / stationary | 288 | 12.682 / 14.116 | 3.680 |
| ProductionTSR / camera_pan | 261 | 13.497 / 15.059 | 3.732 |
| NativeTAA / stationary | 290 | 12.085 / 14.350 | 3.290 |
| NativeTAA / camera_pan | 278 | 13.013 / 14.508 | 3.305 |

The stationary/pan sequences pass gross temporal-stability and non-frozen-motion checks. Six directly inspected captures retain player/NPC silhouettes, road/curb edges, floor hazard cues, destruction visibility and readable HUD. `reconstruction-visual-review-01.json` identifies the exact images and limits. All captures remain `GENERATED_DRAFT`; blockout structures and empty surroundings remain visible. This is bounded fallback integration and measured cost evidence, not final art or broad performance acceptance.

`D03-01-reconstruction-preservation.json` verifies all 1,797 entries across the nine prior D03 manifests: 1,772 still match local bytes; 25 previously extended source entries retain their exact original bytes in the cited commits. No completed evidence or canonical task/production metadata was rewritten. Local commit and exact Git readback precede handoff; the Auto Feeder owns GitHub/Drive publication and canonical transitions. No remote publication is claimed here.

Remaining D03 work includes clean shader/material/PSO launch and packaged qualification, final production world/lighting/character/weapon/vehicle art, broader VFX/audio and remaining animation/LOD/crowd coverage. The unavailable-TSR hardware branch is source-reviewed but untested on this TSR-capable workstation. Fine ghosting/disocclusion, particles/reflections, high-speed camera motion, other hardware and lower-feature renderers remain unqualified. Do not advance beyond D03-01.
