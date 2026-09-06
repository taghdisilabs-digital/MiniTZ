# D03-01 terrain foot-contact increment

Increment: **implemented and validated**. Full D03-01: **CONTINUE**.

Native animation now corrects cosmetic foot contact on supported terrain. The game thread samples two WorldStatic support planes; the animation worker applies bounded pelvis lowering, two-bone leg IK and ankle tilt to the authored locomotion/jump pose. The gameplay capsule remains authoritative. Contact fades during swing, rejects steep or unreachable support, and clears across jump, teleport, dormancy, seating and defeat. `biella.Animation.FootPlacement=0` retains the authored pose as a fallback.

The implementation reuses the existing Manny integration rig and canonical gameplay map. It adds no generated character asset or disconnected showcase. Final character, weapon, vehicle and world art remain unfinished.

## Evidence

- `contact-build-06/result.json`: native UE 5.8.2 editor target build passed from the tested source.
- `contact-runtime-04/validation.json`: positive contact scenario passed, 1,392 evaluated pose frames and eight native captures. Flat ground, both 25-degree slopes, split heights, missing support, jump/landing, rejected steep/deep support, reacquisition, movement/teleport, dormancy, vehicle entry/exit and defeat were exercised.
- `contact-disabled-01/validation.json`: disabled control exposed 12.682162 cm and 11.282937 cm split-support sole errors, with zero contact weights. Four native captures preserved.
- `contact-animation-regression-02/validation.json`: existing animation/gameplay regression passed, 986 pose frames and nine native captures, on the same native build. It covers locomotion, NPC gait, jump and lifecycle transitions.
- `D03-01-contact-final-readback.json`: closed logs, captures, measurements and exact current source/build/input identities verified. Positive and disabled inputs match; the animation regression shares 271 identical inputs. Qualified sole checks peak at 0.002631 cm error and ankle normal checks at 0.783074 degrees. Across 281 settled samples, maximum sole error is 0.0111 cm and maximum consecutive ankle-height step is 0.0021 cm. The stationary capsule stays at 1088 cm within 0.1 cm.

These are measured contact-fixture results, not shipping frame-time or general-terrain guarantees. Raw capture stalls and all failed attempts are retained. The native captures remain `GENERATED_DRAFT`, without an owner art-acceptance claim.

## Repairs and preservation

The first fixture inserted blocking pads that depenetrated the gameplay capsule; pads now ignore Pawn collision while retaining WorldStatic contact queries. The second attempt entered a newly spawned vehicle before terrain residency released its hold; the fixture now waits for the existing native readiness condition. The third attempt repeated a passed assertion after screenshot readback caused a discontinuity reset; each capture now runs its checks once and finishes before changing terrain. Disabled pads are hidden as well as collision-disabled, keeping visible and queried support consistent.

The first animation regression timed out during a roughly 520-second simultaneous engine/monitor pause. The precise external cause is unknown. The unchanged build passed on retry. `contact-recovery-01.json` and `contact-regression-retry-01.json` preserve the earlier diagnoses; the final readback supersedes their pending validation fields. Build 03's interrupted wrapper remains intact; build 04 verified its completed link incrementally. The optional local-Qwen timeout is preserved under `contact-design-01`; its output is not an acceptance authority.

All 874 entries in the prior rendering, animation and audio manifests were checked. Their manifests and 870 current entries remain byte-identical. Four animation source/runner entries were intentionally extended for this increment; original bytes remain in the predecessor commit. See `D03-01-contact-preservation.json` for exact identities. The animation runner retains 03/04 observations but compares only the unchanged Project production authority because 03/04 are volatile controller state.

## Remaining scope and durability

Two support traces run per active evaluated pawn. General crowd/LOD cost, moving platforms, wider terrain transitions, shipping frame times, clean shader/PSO launch and packaged/fallback/platform qualification remain unproven. D03 also still needs aim/action/hit/defeat animation layers, skeletal vehicle presentation, production world/lighting/art and broader VFX/audio coverage. This receipt does not advance the task or change 03/04, Project production status or Engine P4-06.

Canonical files remain in this Project subtree. `D03-01-contact-file-manifest.json` records this increment's editable source and all associated evidence. The increment is committed locally; the Auto Feeder owns GitHub/Drive publication and canonical state transition. No remote publication or full-task completion is claimed here.
