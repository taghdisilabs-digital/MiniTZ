# Biella — next 100 canonical tasks

Priority: **GAME_FIRST — game delivery is NUMBER 1.**

This map is not a queue. Physical Project PRODUCTION.md order is authoritative; task IDs and accepted work are preserved.

Only task objectives, deliverables, validation, evidence and canonical dependency edges are extracted. Historical repository/controller paths, FUTURE_BLOCKED flags and raw activation/control instructions are not active.

## Shared execution rules

One authoritative task/session per active task; parked resource-blocked tasks retain their task/session identity. Reuse valid work; execute only missing outputs and required validation. No website/business prerequisite for game delivery. Real external evidence remains required where promised. Local/GitHub per-task; Drive every five completed tasks in <=3.8 GB parts.

## 001. D05-01 — UI, settings, localization, and accessibility

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D04-01

**Objective.** Turn existing runtime state and controls into real player-facing UI/settings. Every exposed option must change the subsystem it names; no placeholder menu entries. Exact shipping language/device/accessibility catalogs remain unapproved and are not invented.

**Deliverable.** - Runtime HUD bound to authoritative health/ammo/objective/mode state.
- Live before/after proof for sensitivity/invert-Y and one presentation setting.
- Settings persistence/reconstruction across process or game-session reload according to `UGameUserSettings` scope.
- Pseudo-localization expansion + missing-key negative case.
- Accessibility/readability enabled/disabled comparison from live gameplay.
- Pause -> settings -> gameplay transition with valid ownership and no stale controls.

**Validation.** - Runtime HUD bound to authoritative health/ammo/objective/mode state.
- Live before/after proof for sensitivity/invert-Y and one presentation setting.
- Settings persistence/reconstruction across process or game-session reload according to `UGameUserSettings` scope.
- Pseudo-localization expansion + missing-key negative case.
- Accessibility/readability enabled/disabled comparison from live gameplay.
- Pause -> settings -> gameplay transition with valid ownership and no stale controls.

**Required evidence.** - Runtime HUD bound to authoritative health/ammo/objective/mode state.
- Live before/after proof for sensitivity/invert-Y and one presentation setting.
- Settings persistence/reconstruction across process or game-session reload according to `UGameUserSettings` scope.
- Pseudo-localization expansion + missing-key negative case.
- Accessibility/readability enabled/disabled comparison from live gameplay.
- Pause -> settings -> gameplay transition with valid ownership and no stale controls.

**Source records.** `docs/task-program/D00_D08_ENGINE_GAMES.md` (SHA-256 `efd80e6b05a4cced5ff47d958c3ceaf1ba324e676033fea1c16e832af2a1d3fb`); `projects/biella-games/docs/task-guides/D05-01.md` (SHA-256 `82d2570d2425f63f183c67c5625756e1ab4688632f0a79921118d7657f1ba9dd`)

## 002. D06-01 — Cinematic and presentation integration

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D04-01

**Objective.** Integrate an in-game editable sequence into the real game world and prove clean gameplay handoff. This is runtime presentation, not a disconnected trailer scene and not new narrative canon.

**Deliverable.** - `ABiellaCinematicDirector` — bounded owner for entering/exiting/skipping one runtime sequence and applying explicit authoritative handoff events.
- `Content/Cinematics/LS_Demo01_RuntimeHandoff.uasset` — technical in-game sequence asset.
- `BiellaCinematicTest.cpp` and `tests/run_d06_01_cinematic.py` — native/runtime acceptance fixture.

Build a short technical sequence using existing world/player/arena-pressure presentation. It may move/cut the camera and use existing animation/VFX/audio, but it must not invent dialogue, lore, mission completion or fake combat.

Required flow:
`GAMEPLAY -> CINEMATIC MODE -> CONTROL CONSTRAINED -> EXISTING RUNTIME STATE/PRESENTATION -> WATCHED OR SKIPPED HANDOFF -> GAMEPLAY CONTROL RESTORED`.

**Validation.** - Editable Level Sequence source and exact build/source identity.
- Same runtime actors/world, no duplicate fake player or disconnected scene.
- Input/camera ownership is transferred and restored.
- Watched and skipped paths produce the same required authoritative state.
- No stale input lock, missing equipment, duplicate actor or mission/world divergence.
- Streamed assets/world remain valid around the sequence.
- Capture supports presentation evidence but runtime state assertions are authoritative.

**Required evidence.** - Editable Level Sequence source and exact build/source identity.
- Same runtime actors/world, no duplicate fake player or disconnected scene.
- Input/camera ownership is transferred and restored.
- Watched and skipped paths produce the same required authoritative state.
- No stale input lock, missing equipment, duplicate actor or mission/world divergence.
- Streamed assets/world remain valid around the sequence.
- Capture supports presentation evidence but runtime state assertions are authoritative.

**Source records.** `docs/task-program/D00_D08_ENGINE_GAMES.md` (SHA-256 `efd80e6b05a4cced5ff47d958c3ceaf1ba324e676033fea1c16e832af2a1d3fb`); `projects/biella-games/docs/task-guides/D06-01.md` (SHA-256 `91acf1055ea19691bcbf5bab7f3c781df022e5dd16c1e31971e42166e6ff5920`)

## 003. D07-01 — Full performance, stability, and scalability qualification

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D03-01, D04-01, D05-01, D06-01

**Objective.** Qualify the representative current game with measured runtime evidence. Do not invent FPS/resolution/RAM/VRAM/latency thresholds: current technical decisions explicitly leave those target tiers `UNKNOWN`. The task still measures and reports current behavior and production risks.

**Deliverable.** - Reproducible scenario manifest and raw machine-readable traces.
- Frame-time distribution and worst/recurring hitches, not average FPS alone.
- CPU/GPU/RAM/VRAM/resource context.
- Streaming/LOD/culling correctness under motion.
- Crash/hang/assert diagnostic pipeline with encountered failures retained.
- Clear list of unresolved production risks tied to exact evidence.

**Validation.** - Reproducible scenario manifest and raw machine-readable traces.
- Frame-time distribution and worst/recurring hitches, not average FPS alone.
- CPU/GPU/RAM/VRAM/resource context.
- Streaming/LOD/culling correctness under motion.
- Crash/hang/assert diagnostic pipeline with encountered failures retained.
- Clear list of unresolved production risks tied to exact evidence.

**Required evidence.** - Reproducible scenario manifest and raw machine-readable traces.
- Frame-time distribution and worst/recurring hitches, not average FPS alone.
- CPU/GPU/RAM/VRAM/resource context.
- Streaming/LOD/culling correctness under motion.
- Crash/hang/assert diagnostic pipeline with encountered failures retained.
- Clear list of unresolved production risks tied to exact evidence.

**Source records.** `docs/task-program/D00_D08_ENGINE_GAMES.md` (SHA-256 `efd80e6b05a4cced5ff47d958c3ceaf1ba324e676033fea1c16e832af2a1d3fb`); `projects/biella-games/docs/task-guides/D07-01.md` (SHA-256 `f79f11e10f01d809a612c8ffb8359d1041f3b1b601c2ea0fadc39535bffdde6f`)

## 004. D17-01 — Select canonical AAA challenger slice

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D07-01

**Objective.** Choose a 10-20 minute representative sequence from implemented, accepted gameplay/content and bind the owner visual direction. Identify only the missing final-layer gaps; do not invent mechanics to make the slice more cinematic.

**Deliverable.** Canonical slice scenario definition with start state, route, combat/system beats, end state, and exact build identity.

**Validation.** Scenario can be executed in the packaged game and demonstrates the project's real player+rival+infected+arena interaction without scripted substitution.

**Required evidence.** Scenario file, package identity, first raw run capture.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D17-01.md` (SHA-256 `e4869f1862eff1d365390ad97dcb9442f66da6323f8de7dc36dc66ffab7ca3b4`); `projects/biella-games/docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md` (SHA-256 `a02f91a4a15192c47274eb15b40a2a989fa0861909e652ce227e67c635ae0b07`)

## 005. D17-02 — Prove traversal and camera quality

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D17-01

**Objective.** Create/fix only traversal, camera, collision, framing and route-readability gaps needed for the selected slice, then prove raw gameplay navigation at production camera distance.

**Deliverable.** Traversal/camera issue record plus accepted run evidence after task-scoped fixes if required.

**Validation.** The canonical route is playable without camera clipping, collision traps, navigation ambiguity that blocks intended play, or noninteractive presentation substitutions.

**Required evidence.** Raw capture, runtime log, exact changed source if repaired.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D17-02.md` (SHA-256 `837d9e95c90165fa1b0fba1293729f1af75ba884eb09c0717ec404c2a10389ef`); `projects/biella-games/docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md` (SHA-256 `a02f91a4a15192c47274eb15b40a2a989fa0861909e652ce227e67c635ae0b07`)

## 006. D17-03 — Prove combat feel and consequence chain

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D17-02

**Objective.** Create/fix only combat-feedback and consequence-chain gaps needed for the slice, then prove real input -> action -> hit -> damage -> reaction -> state change.

**Deliverable.** Combat-quality evidence and bounded repair changes where current behavior fails acceptance.

**Validation.** Combat actions are responsive and legible, consequences are real simulation state, and no visual-only effect is counted as gameplay completion.

**Required evidence.** Raw combat capture, telemetry/log events, source/build identity.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D17-03.md` (SHA-256 `bdea770b1f124d711a9f220b666361b9f07c01e7b818bbc8d92feebc88e74fe1`); `projects/biella-games/docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md` (SHA-256 `a02f91a4a15192c47274eb15b40a2a989fa0861909e652ce227e67c635ae0b07`)

## 007. D17-04 — Prove player, rival, infected, and arena interaction

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D17-03

**Objective.** Create/fix only encounter-composition gaps needed so player, rival contestant, infected and approved arena pressure materially affect the same evolving fight.

**Deliverable.** System-interaction evidence trace and raw gameplay capture.

**Validation.** Actor decisions and world consequences originate from runtime state; the encounter is not a prerecorded or manually staged substitute for implementation.

**Required evidence.** Event timeline, raw video, runtime logs, package digest.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D17-04.md` (SHA-256 `a55ae8cd7d1a4c5a96131fb65f5772794cc52f6c228f2411d0883602bca3861a`); `projects/biella-games/docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md` (SHA-256 `a02f91a4a15192c47274eb15b40a2a989fa0861909e652ce227e67c635ae0b07`)

## 008. D17-05 — Create and qualify final animation and motion layer

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D17-04

**Objective.** FINAL_VISUAL_LAYER: create/fix animation, locomotion, aim, weapon handling, hit/death reactions, transitions, deformation and motion continuity until the selected slice reaches the owner visual direction at gameplay distance; then validate. No review-only loop.

**Deliverable.** Animation-quality defect list reduced to accepted slice quality, with exact repaired assets/source where needed.

**Validation.** No acceptance-blocking snapping, foot sliding, broken deformation, impossible pose transitions, or actor-state mismatch remains in the slice.

**Required evidence.** Raw captures at representative moments, source/asset identities, runtime evidence.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D17-05.md` (SHA-256 `55a7b86480ecc07442208d96050dcba7234ad68ef147cdba803fd052be22a3c4`); `projects/biella-games/docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md` (SHA-256 `a02f91a4a15192c47274eb15b40a2a989fa0861909e652ce227e67c635ae0b07`)

## 009. D17-06 — Create and qualify final audio, VFX, HUD, and readability layer

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D17-05

**Objective.** FINAL_VISUAL_LAYER: create/fix event-driven audio, VFX, HUD hierarchy and gameplay readability until the selected slice communicates threats, routes, hazards and consequences at the owner visual direction quality; then validate. No review-only loop.

**Deliverable.** Readability evidence and task-scoped fixes to existing implemented feedback.

**Validation.** Critical events are perceptible and attributable; UI/VFX/audio do not claim mechanics absent from runtime state and do not block gameplay readability.

**Required evidence.** Raw capture with audio, HUD/state event trace, exact source/asset identities.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D17-06.md` (SHA-256 `67083876bbb5e57076dc327e2d13aaedbb3c1fa5db83c3a66c15dd93937dc1cb`); `projects/biella-games/docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md` (SHA-256 `a02f91a4a15192c47274eb15b40a2a989fa0861909e652ce227e67c635ae0b07`)

## 010. D17-07 — Create and qualify final environment, material, lighting, and world layer

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D17-06

**Objective.** FINAL_VISUAL_LAYER: create/fix environment density, modular composition, materials, wetness/reflection response, motivated lighting, infection integration, props, damage/state coherence and spatial depth until the selected slice reaches the owner visual direction while remaining playable and buildable; then validate. No review-only loop.

**Deliverable.** Environment-quality evidence and bounded corrections within accepted project visual direction.

**Validation.** No acceptance-blocking floating/fused geometry, impossible access, contradictory scale/perspective, unreadable route, material failure, or unexplained world-state artifact remains.

**Required evidence.** Raw traversal/combat captures, map/asset identities, runtime logs.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D17-07.md` (SHA-256 `ff0138cc0d8330553a94f0af106c53273c8ced028ca64630ba72ba78ff5ad733`); `projects/biella-games/docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md` (SHA-256 `a02f91a4a15192c47274eb15b40a2a989fa0861909e652ce227e67c635ae0b07`)

## 011. D17-08 — Close AAA vertical-slice evidence package

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D17-07

**Objective.** Package truthful raw gameplay, captures, source/build identities and criterion results for the polished canonical slice. Do not edit evidence to hide runtime defects.

**Deliverable.** Indexed slice bundle containing exact build, scenario, raw full run, selected excerpts, metrics, known limitations, and source identities.

**Validation.** A reviewer can trace every claimed visual/gameplay quality point to the exact running build and raw evidence; unresolved defects are disclosed.

**Required evidence.** Bundle digest/index, Git commit/tree, Drive readback.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D17-08.md` (SHA-256 `df44da7374bdca8502eab06026cce2e47126e2eb8cf1571b4e7f7c2604a42dd6`); `projects/biella-games/docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md` (SHA-256 `a02f91a4a15192c47274eb15b40a2a989fa0861909e652ce227e67c635ae0b07`)

## 012. D19-01 — Lock representative target hardware tiers from measured evidence

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D17-08

**Objective.** Use packaged-runtime telemetry and accepted product intent to replace only the hardware-tier UNKNOWNs that can now be decided.

**Deliverable.** Updated technical decision entries for measured target hardware tiers or explicit retained UNKNOWNs where evidence is insufficient.

**Validation.** Each accepted value has measured evidence and owner/delegated authority; no GPU/RAM/VRAM target is inferred from installed hardware alone.

**Required evidence.** Decision diff, telemetry source IDs, commit/tree.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-029_LOCK_REPRESENTATIVE_TARGET_HARDWARE_TIERS_FROM_MEASURED_EVIDENCE.md` (SHA-256 `568e555d6ac6422e1abab619389f5b347d1683c832164c4bbecb2bb23832aa5f`)

## 013. D19-02 — Lock native frame-time and responsiveness targets from evidence

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D19-01

**Objective.** Define target native FPS/frame-time/hitch/latency tiers only where representative measurements support a production decision.

**Deliverable.** Updated performance decision entries and repeatable benchmark scenarios.

**Validation.** Targets exclude generated frames as native performance and are tied to accepted hardware/scenario identities.

**Required evidence.** Decision record, benchmark telemetry, source commit.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-030_LOCK_NATIVE_FRAME_TIME_AND_RESPONSIVENESS_TARGETS_FROM_EVIDENCE.md` (SHA-256 `f16d1a77390e1113248445d289eb52770481350662e5292bcb9f4c8ecd0b7fe8`)

## 014. D19-03 — Qualify world traversal streaming and hitch behavior

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D19-02

**Objective.** Run representative high-motion traversal through streamed world boundaries and repair acceptance-blocking stalls or continuity defects.

**Deliverable.** Traversal stress evidence and bounded fixes.

**Validation.** Streaming, HLOD/culling/occlusion, collision, and world-state continuity remain valid through the scenario within accepted performance targets.

**Required evidence.** Frame-time trace, streaming logs, raw capture, build digest.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-031_QUALIFY_WORLD_TRAVERSAL_STREAMING_AND_HITCH_BEHAVIOR.md` (SHA-256 `d42916d4985c3ad2e08295be9a26cb2dba2145f03a26826fbeff8da2daab0996`)

## 015. D19-04 — Qualify combat population stress behavior

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D19-03

**Objective.** Run representative simultaneous player/rival/infected combat at the population level supported by current content and measure degradation.

**Deliverable.** Combat stress profile and bounded optimization changes if required.

**Validation.** Simulation correctness and gameplay readability remain intact at the accepted scenario load; counts are evidence-driven rather than ambition-driven.

**Required evidence.** Actor/event counts, CPU/GPU/frame telemetry, runtime logs.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-032_QUALIFY_COMBAT_POPULATION_STRESS_BEHAVIOR.md` (SHA-256 `dc77c8d83e41cdee63e9ff3e12f5f1f5dbe6f1f7a0bc874aafe0936542a1d29e`)

## 016. D19-05 — Qualify memory, VRAM, residency, and leak behavior

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D19-04

**Objective.** Measure resource residency through traversal, combat, restart, and repeated scenario execution.

**Deliverable.** Resource qualification record and leak/residency fixes where evidenced.

**Validation.** RAM/VRAM/resource use is bounded for accepted scenarios and does not grow materially from lifecycle defects across repeated runs.

**Required evidence.** Resource traces, lifecycle logs, build/source identity.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-033_QUALIFY_MEMORY_VRAM_RESIDENCY_AND_LEAK_BEHAVIOR.md` (SHA-256 `0a5d4587327aee41bed49dfc20d9d9323b530fc1beec2795de790134a99d5eed`)

## 017. D19-06 — Qualify sustained packaged-runtime stability

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D19-05

**Objective.** Run the accepted representative soak/repetition duration chosen from current release risk and capture crashes, hangs, asserts, and state degradation.

**Deliverable.** Stability run evidence plus repaired failures limited to reproduced issues.

**Validation.** The exact packaged build survives the accepted duration/repetition scenario without unresolved release-blocking failure.

**Required evidence.** Runtime logs, duration/scenario record, crash/assert artifacts if any.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-034_QUALIFY_SUSTAINED_PACKAGED_RUNTIME_STABILITY.md` (SHA-256 `774f839e6ebcd5418acee766257e91a3fb15704950246555a72b4855733c4a5d`)

## 018. D19-07 — Requalify clean Shipping package

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D19-06

**Objective.** Produce and validate the accepted Win64 Shipping configuration after performance/stability repairs.

**Deliverable.** Shipping package with exact source/build identity and clean-machine play evidence.

**Validation.** Package launches outside editor, completes the canonical slice, persists required state, and exits/relaunches cleanly on the qualified environment.

**Required evidence.** Shipping package digest, runtime logs, raw play capture.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-035_REQUALIFY_A_CLEAN_SHIPPING_PACKAGE.md` (SHA-256 `178233d0114d383d50f1c38f824d92db9a0118c5b80f5620ba5a9bfacf914597`)

## 019. D19-08 — Close release-operations proof

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D19-07

**Objective.** Assemble current build, performance, stability, persistence, diagnostics, update, and clean-machine results into one release-operations evidence set.

**Deliverable.** Release-operations qualification bundle.

**Validation.** Every accepted release claim points to fresh exact-build evidence; stale predecessor logs are references only.

**Required evidence.** Bundle index/digest, Git source identity, Drive readback.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-036_CLOSE_RELEASE_OPERATIONS_PROOF.md` (SHA-256 `96e8fd50b1068e09cff7af034d68b547a481e8806226cdc934771bab483fe02b`)

## 020. D20-01 — Select second production scenario from current accepted systems

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D19-08

**Objective.** Choose a materially different scenario that reuses existing systems and approved content vocabulary rather than introducing a new project identity.

**Deliverable.** Second-scenario production brief with reuse targets, required variation, and acceptance scenario.

**Validation.** Scenario is distinct enough to test repeatability but remains within accepted mechanics, art direction, and current project scope.

**Required evidence.** Brief, source/asset references, acceptance route.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-037_SELECT_A_SECOND_PRODUCTION_SCENARIO_FROM_APPROVED_SYSTEMS.md` (SHA-256 `f280384878cf6347731a9f6708d3129a21ae6cc9a9da6d07c9be00c2986f4e89`)

## 021. D20-02 — Produce second environment or encounter composition through reusable systems

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D20-01

**Objective.** Build the second scenario using existing modular world/content systems before adding bespoke logic.

**Deliverable.** Editable scenario content integrated in the game.

**Validation.** Scenario is playable, collision/navigation-valid, and reuses production systems; bespoke code is justified by an actual missing universal/project capability.

**Required evidence.** Source/asset diff, runtime traversal evidence.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-038_PRODUCE_THE_SECOND_ENVIRONMENT_OR_ENCOUNTER_COMPOSITION_THROUGH_REUSABLE_SYSTEMS.md` (SHA-256 `44f3441dc3f93049ae25bccb4df5727e7d5e1c1c29848f928447d62abc4128b0`)

## 022. D20-03 — Produce different rival and infected encounter composition

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D20-02

**Objective.** Use existing actor/system definitions to create a meaningfully different interaction pattern without forking core AI behavior per encounter.

**Deliverable.** Second encounter composition and runtime evidence.

**Validation.** Rival/infected behavior remains driven by shared systems and current approved tuning/content data, with real state interaction.

**Required evidence.** Encounter data/source identity, raw gameplay/event trace.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-039_PRODUCE_A_DIFFERENT_RIVAL_AND_INFECTED_ENCOUNTER_COMPOSITION.md` (SHA-256 `de35046995825e33dfd9e2eb20ff29ea9833e63d2763182ca992fb4d12f2d5b7`)

## 023. D20-04 — Produce alternate arena-pressure sequence from current accepted systems

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D20-03

**Objective.** Recombine the already approved arena-pressure mechanism with the second scenario without inventing a new pressure mechanic.

**Deliverable.** Second pressure sequence integrated into scenario data/world state.

**Validation.** The same authoritative pressure system drives different valid consequences; no duplicate pressure controller is created.

**Required evidence.** State/event trace, scenario source, runtime capture.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-040_PRODUCE_AN_ALTERNATE_APPROVED_ARENA_PRESSURE_SEQUENCE.md` (SHA-256 `b48a73566106d613bb84594051aa2222c9cdd22e5262814a7ba9ba90cb8f39db`)

## 024. D20-05 — Measure content-system reuse versus bespoke work

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D20-04

**Objective.** Quantify which second-scenario outputs were achieved through reusable data/assets/systems and which required new implementation.

**Deliverable.** Reuse report tied to source diffs and production task evidence.

**Validation.** Counts/times come from real changed files/tasks/traces; no claim of reuse is based only on architecture intent.

**Required evidence.** Git diff stats, task/run identities, categorized reuse record.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-041_MEASURE_CONTENT_SYSTEM_REUSE_VERSUS_BESPOKE_WORK.md` (SHA-256 `63ee98b55e6a23ca7e59feecd5d31f861b547d4e6fee45b7b1348fc48722be5a`)

## 025. D20-06 — Package and qualify second scenario

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D20-05

**Objective.** Build a package containing the second scenario and execute its representative route outside the editor.

**Deliverable.** Second-scenario packaged proof.

**Validation.** Clean launch and real play succeed with the same release pipeline and evidence standards used for the canonical slice.

**Required evidence.** Package digest, raw gameplay, runtime logs.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-042_PACKAGE_AND_QUALIFY_THE_SECOND_SCENARIO.md` (SHA-256 `7f45071808751b15e1a0a630e846adb8cef56ec1f8ba5d1a7bd05a30ba953e7e`)

## 026. D20-07 — Compare production time, intervention, and quality across scenarios

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D20-06

**Objective.** Compare first- and second-scenario creation using actual task/run timelines and acceptance evidence.

**Deliverable.** Repeatability comparison with elapsed production time, accepted-task count, founder interventions, changed source/assets, and validation outcome where observable.

**Validation.** Metrics are computed from durable traces and comparable task boundaries; missing telemetry is marked unknown rather than estimated.

**Required evidence.** Trace IDs, calculation inputs, comparison report.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-043_COMPARE_PRODUCTION_TIME_INTERVENTION_AND_QUALITY_ACROSS_SCENARIOS.md` (SHA-256 `0f45d0ac5d592e9d4357b9a5e77058e41fe635352333b9f5a0e39cf5484fd96a`)

## 027. D20-08 — Close repeatable-content proof

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D20-07

**Objective.** Demonstrate that the playable quality pipeline can produce more than one strong scenario without rebuilding the game architecture each time.

**Deliverable.** Repeatable-content evidence bundle linking both scenarios and their production traces.

**Validation.** Both scenarios run in qualified packages, share core systems, and have evidence-linked production metrics; one-off bespoke hero work is separated from reusable capability.

**Required evidence.** Bundle index/digest, source identities, Drive readback.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-044_CLOSE_REPEATABLE_CONTENT_PROOF.md` (SHA-256 `b9c21672c50b883da000925a6309f469e07a1e58aff10c6afc2864ea236d223a`)

## 028. D23-01 — Publish truthful playable-proof surface

Lane: **Cross-project** · Priority: **1** · Execution root: `.` · Dependencies: D20-08

**Objective.** Prepare and publish a public-facing proof surface using only accepted build facts and gameplay evidence; no invented title/release date/platform promise or fake gameplay.

**Deliverable.** Public proof page or media package with raw-gameplay provenance and exact build/source references kept internally.

**Validation.** Published material matches the running product and does not present generated concepts or cinematics as implemented gameplay.

**Required evidence.** Published URL/identity, source media digest, internal evidence mapping.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-061_PUBLISH_A_TRUTHFUL_PLAYABLE_PROOF_SURFACE.md` (SHA-256 `9be2c8af52e361d3abc352d5a48c99b7c97cc726b3e65ef4eb70ff60f272d563`)

## 029. D18-01 — Define blind external playtest contract

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D17-08

**Objective.** Define what an external player receives, what founder help is prohibited during the session, what evidence is collected, and what counts as completion/failure.

**Deliverable.** Consent-aware playtest protocol and telemetry/question set limited to product evaluation.

**Validation.** Protocol can be run without exposing internal secrets or requiring founder coaching; success criteria derive from the playable product rather than investor narrative.

**Required evidence.** Protocol file and test package identity.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-021_DEFINE_THE_BLIND_EXTERNAL_PLAYTEST_CONTRACT.md` (SHA-256 `12e80f365312e08d2e4af06ef887b54451d303d1a63641571b5cf1cd445d9eb9`)

## 030. D18-02 — Prepare founder-independent playtest handoff

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D18-01

**Objective.** Create the smallest package, instructions, and issue-report path needed for an outside player to install, launch, play, and report results.

**Deliverable.** External playtest handoff bundle.

**Validation.** A person not using the development workspace can follow the instructions without hidden commands or direct founder intervention.

**Required evidence.** Bundle digest, clean-machine dry run, instructions readback.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-022_PREPARE_THE_FOUNDER_INDEPENDENT_PLAYTEST_HANDOFF.md` (SHA-256 `33b5d2a11f8775d70a0a08499514a61e5d23d77e54f04af6e231b18915f43220`)

## 031. D08-01 — Delivery, update, and release-candidate qualification

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D07-01

**Objective.** Produce and qualify an exact distributable build/update lineage. Release-candidate status belongs to one specific package identity, not a successful compile or screenshot.

**Deliverable.** - `tests/run_d08_01_release.py` — package/install/update/launch qualification orchestrator.
- `Build/Release/D08-01/source-build-manifest.json`.
- `Build/Release/D08-01/package-manifest.json`.
- `Build/Release/D08-01/qualification.json` and `qualification.md`.

**Validation.** 1. Clean dependency/content validation, including a bounded missing/incompatible-content negative case.
2. Produce exact package with source/tree/config/content identity.
3. Launch outside editor through intended entry point.
4. Exercise real input/player/camera/gameplay, rivals/infected/pressure, current world/interactions, rendering/audio/VFX, save/settings reconstruction where implemented.
5. Review fatal/assert/content-load diagnostics and package-specific resource/performance evidence.
6. For update support, prove exact old-build -> update -> launch -> supported settings/save compatibility plus incomplete/incompatible update failure handling.
7. Record known exclusions/limitations; do not invent store, launcher, certification, patch cadence or live-service requirements.

One exact packaged build must pass the current approved gameplay, production, stability and evidence contracts appropriate to its platform. Package command success alone is insufficient.

**Required evidence.** - Primary target platform: Windows PC x64 first.
- Build/package path: UnrealBuildTool + Unreal AutomationTool; BuildGraph when useful.
- Development package for iteration/evidence; Shipping for distributable qualification.
- Runtime content: cooked Unreal assets/maps.
- Save format: UE SaveGame/custom versioned serialization at platform per-user location.

The canonical Linux UE 5.8.2 VPS has previously reported Win64 SDK as unavailable. At D08 start, reobserve current package resources. Do not silently call a Linux package the final accepted Win64 release candidate. If Win64 remains unavailable on the current Resource, classify it `REQUIRES_OTHER_RESOURCE` and continue every platform-neutral preparation/validation that does not require Win64 while routing the final package step to an actually observed compatible Resource.

**Source records.** `docs/task-program/D00_D08_ENGINE_GAMES.md` (SHA-256 `efd80e6b05a4cced5ff47d958c3ceaf1ba324e676033fea1c16e832af2a1d3fb`); `projects/biella-games/docs/task-guides/D08-01.md` (SHA-256 `2084a4ea38c5f7976123c2a5ec02a14c57e9f555c5442698447fa8b063542e11`); `ops/workstation/INSTALLERS.md` (SHA-256 `15b8e7ec478d7dc1c18881bef6e81bf823c4e245ed6e840002e4d025618124bd`); `ops/workstation/provider-registry.json` (SHA-256 `4937d73301d45dd3a12153453aa642d253bc4ede321b649a9e5cc5edfb799806`); `ops/workstation/setup-unreal-win64.ps1` (SHA-256 `90aa672e77eb9918fe211a9f27e4a18a4a91f8bb00056fafa59dcb3557ef56fe`); `ops/workstation/build-unreal-win64.ps1` (SHA-256 `329e783d07e936ee72f1936e05618b574d2419872e31d18bb84ef824d3a6e1f9`); `ops/workstation/UNREAL_WIN64.md` (SHA-256 `94ce7b44ea2f33cb478d451d5574be630cd1af6013fd29937c77f4142c2727d0`); `projects/biella-games/Build/Release/D08-01/windows-setup-observation.json` (SHA-256 `4fa2cf76591bd1b5c22661e5c576de61290cb3131ace8181ff63b7602bf9bebf`)

## 032. D15-01 — Lock authoritative predecessor closure set

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D17-08, D08-01

**Objective.** Bind the accepted D17-08 polished game source/slice proof plus the D08 release mechanism and only Engine/runtime dependencies actually consumed. Do not wait for unrelated Website/business programs.

**Deliverable.** Game predecessor record linking exact accepted source/build/proof identities and naming superseded references as inactive; reuse existing records instead of another sign-off stage.

**Validation.** The required game release and consumed dependencies have task-appropriate retained proof. No unrelated program closure is a prerequisite. Do not reopen valid completed work.

**Required evidence.** D08 source/build/proof digests, actual dependency identities and a game-scoped predecessor record; record remote verification only when observed.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D15-01.md` (SHA-256 `5abf52224792d92a0638d20fb096bd039f037ee04b7624995eb28ef8f35a2f9a`)

## 033. D15-02 — Freeze current source and decision identities

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D15-01

**Objective.** Record exact accepted game source/build and used Engine dependency identities plus relevant accepted decisions. This is identity recording, not a production freeze or all-program restart.

**Deliverable.** Source-lock record containing repository, branch, commit, tree, relevant Drive source IDs/revisions, current technical decisions, and unresolved UNKNOWNs that could affect later tasks.

**Validation.** Recorded local commit/tree and required source/artifact digests match the accepted game release. Preserve UNKNOWN values. GitHub readback and five-task Drive publication use the existing independent publication mechanism.

**Required evidence.** Source-lock record with observed timestamps and remote identities.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D15-02.md` (SHA-256 `54d04b054acfa5deb2b74037f960ea440a85584bf92a10a940796a3ce236e037`)

## 034. D15-03 — Create post-program evidence namespace

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D15-02

**Objective.** Reuse the existing canonical game evidence namespace and index for the priority game proof work; add only missing task-scoped indexing, never a second source root.

**Deliverable.** Current game proof index with exact artifact identities and existing configured publication destinations.

**Validation.** Write and read back a bounded required artifact in the existing namespace and link its digest without changing predecessor proof. Drive publication is independently recorded, not a game-start dependency.

**Required evidence.** Canonical local artifact/index digests, source commit/tree and observed remote receipts when published.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D15-03.md` (SHA-256 `54eca7e7ac022fcc4cc47590fc80d78211f82f7577fbd8b7fc82674da78a5f13`)

## 035. D15-04 — Bind production-ready predecessor build

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D15-03

**Objective.** Bind the exact build/package produced by the predecessor release program as the starting artifact for AAA-SF proof. Do not rebuild merely because this program started.

**Deliverable.** Build identity record with source commit/tree, package path or artifact identity, digest, configuration, platform, and prior release-qualification evidence.

**Validation.** Exact retained package and source identities match the accepted game release. Repair only a missing/corrupt boundary from preserved source; do not replay valid build work or stop for unrelated program completion.

**Required evidence.** Exact package digest, source identity, and predecessor validation references.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D15-04.md` (SHA-256 `3894c98fb04a7647a60eec5f06251ad26c74585b64ae1e9f4404acc43169f00f`)

## 036. D16-01 — Reproduce release from clean checkout

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D15-04

**Objective.** Prove the accepted game can be built from a clean repository checkout using current documented dependencies rather than founder-local hidden state.

**Deliverable.** Clean-checkout build record and resulting package identity.

**Validation.** Fresh checkout at the bound commit produces a valid package through the accepted Unreal build/package path; missing undocumented dependencies are captured as defects.

**Required evidence.** Checkout commit/tree, build commands/logs, package digest.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D16-01.md` (SHA-256 `0276cb85d911b01f6f089f81bc1b9ee2131a45c9a345fb24b2f1e7430ade768d`)

## 037. D16-02 — Make package recipe reproducible

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D16-01

**Objective.** Reduce the successful build/package procedure to the smallest durable documented recipe and source-controlled configuration needed to repeat it.

**Deliverable.** Reproducible package recipe referencing exact Unreal version, target, configuration, required environment inputs, and output identity rules.

**Validation.** A second execution of the recipe from the same source succeeds without undocumented interactive repair; documented nondeterministic bytes are distinguished from reproducible functional output.

**Required evidence.** Two build logs, resulting package identities/digests, and recipe commit.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D16-02.md` (SHA-256 `0b13bea1a960ea841a017b2771423dd119cdea5a10afcd01ec9de32fda556ef2`)

## 038. D16-03 — Qualify clean-machine install and launch

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D16-02

**Objective.** Install or unpack the package on a machine/environment that does not depend on the development editor workspace and prove clean launch.

**Deliverable.** Clean-machine launch record including prerequisite handling and first-run behavior.

**Validation.** Packaged executable launches outside the editor, reaches real playable runtime, accepts player input, and exits cleanly; no developer-only path is required.

**Required evidence.** Target-machine identity, package digest, runtime log, and captured launch/play evidence.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D16-03.md` (SHA-256 `280ff71f0798b2786aab3d1cc097e7da6eec55a85a835485aeaba96643741fdc`)

## 039. D16-04 — Qualify save, settings, restart, and reconstruction

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D16-03

**Objective.** Prove normal player state survives the package lifecycle required by the accepted game behavior.

**Deliverable.** Packaged-runtime persistence scenario covering settings, required save state, exit, relaunch, and reconstruction.

**Validation.** State is created through gameplay, process is terminated normally, package relaunches, and required state reconstructs without duplication/corruption.

**Required evidence.** Before/after state evidence, save/version identity, runtime logs.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D16-04.md` (SHA-256 `6cc2413f5a6212179b709a79d2fefe32f5175036d0f136e64e5186211b00cae3`)

## 040. D16-05 — Qualify crash, assert, and failure diagnostics

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D16-04

**Objective.** Ensure a release candidate failure produces actionable diagnostics without requiring an attached editor session.

**Deliverable.** Diagnostic evidence path and bounded test showing logs/dumps or equivalent accepted diagnostics can be retrieved from packaged runtime.

**Validation.** An induced safe diagnostic scenario or observed real failure produces retrievable evidence tied to the exact build; no destructive or fabricated crash proof.

**Required evidence.** Diagnostic artifact identity, build identity, reproduction steps.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D16-05.md` (SHA-256 `627dde721f0580e3af5de1cff1e0f68329fb14252f080a1047fb4dd7178e66fc`)

## 041. D16-06 — Qualify update and package replacement

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D16-05

**Objective.** Prove the game can move from one exact package identity to another without losing required supported state.

**Deliverable.** Two-version update scenario using accepted package/update mechanics and a compatibility result.

**Validation.** Version B installs or replaces Version A as designed, launches, and preserves or intentionally migrates supported state; incompatibility is explicit rather than silent.

**Required evidence.** Version identities, update steps, save/config compatibility evidence.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D16-06.md` (SHA-256 `d0e85e5fc1d1791f9c512d8e6c7f09aab9e7d68c26c18c4aa7c06d32259dea85`)

## 042. D16-07 — Capture representative packaged-runtime baseline

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D16-06

**Objective.** Capture performance and resource behavior from the packaged game in one representative traversal/combat scenario before further proof polishing.

**Deliverable.** Baseline telemetry bundle for frame time, hitching, CPU/GPU/RAM/VRAM where available, load/stream behavior, and scenario identity.

**Validation.** Telemetry comes from the exact packaged build and repeatable scenario; generated/display frames are not substituted for native simulation/render evidence.

**Required evidence.** Telemetry files, runtime log, machine hardware identity, build digest.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D16-07.md` (SHA-256 `cc59599b86d2cf005bff4463f50a43e207295bec9524560053646cbff685220f`)

## 043. D16-08 — Close reproducible-build proof

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D16-07

**Objective.** Assemble the minimal reproducible chain from exact game source to clean build, package, install and play using existing qualified evidence.

**Deliverable.** Reproducibility evidence bundle and index.

**Validation.** Every link source -> build -> package -> install -> play -> persistence -> diagnostics is backed by exact identities; missing proof remains explicitly unresolved.

**Required evidence.** Evidence index, exact artifact digests and source commit/tree; GitHub/Drive readback only when published, with pending publication recorded separately.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `projects/biella-games/docs/task-guides/D16-08.md` (SHA-256 `842b7fb9969837e8167e96ac43060c9c7b92b9187d4b4d7300d5ca80269ac344`)

## 044. D18-03 — Run first independent external session

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D18-02

**Objective.** Observe one real external player using the packaged build under the blind protocol.

**Deliverable.** Session record with launch outcome, completion path, blockers, comprehension issues, crashes, and opt-in qualitative feedback.

**Validation.** Session evidence comes from the participant's real play; founder assistance is recorded rather than hidden; failures remain failures.

**Required evidence.** Session ID, build digest, telemetry/logs, consented notes/captures.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-023_RUN_THE_FIRST_INDEPENDENT_EXTERNAL_SESSION.md` (SHA-256 `75aa91432f6b02699a538c65255ba023728ac1b191337a7996b583fb132bbc18`)

## 045. D18-04 — Run independent session on a different machine context

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D18-03

**Objective.** Repeat external play on a materially different machine/user context to expose founder-machine assumptions.

**Deliverable.** Second independent session record and environment comparison.

**Validation.** The same package/handoff path is used; machine-specific failures are isolated rather than changing the product story.

**Required evidence.** Machine profile, session result, logs, build identity.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-024_RUN_AN_INDEPENDENT_SESSION_ON_A_DIFFERENT_MACHINE_CONTEXT.md` (SHA-256 `3cf384f621ba3518da4b8a1e4a1cc24f06b77f52ca5f69be8bc1e5b28f20b5ec`)

## 046. D18-05 — Aggregate external comprehension and friction evidence

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D18-04

**Objective.** Convert observed external-session facts into a prioritized defect/clarity set without turning subjective comments into fabricated metrics.

**Deliverable.** Evidence-linked playtest findings ranked by reproducibility and impact on intended play.

**Validation.** Every finding links to an observed session event or explicit participant feedback; no unsupported generalization is presented as player consensus.

**Required evidence.** Finding index with session references.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-025_AGGREGATE_EXTERNAL_COMPREHENSION_AND_FRICTION_EVIDENCE.md` (SHA-256 `db080ab04906ee5f88695beff9ccc9eeb1de40b2159537c4c82b9cebb70818ea`)

## 047. D18-06 — Repair highest-impact reproducible external blockers

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D18-05

**Objective.** Fix only product defects clearly evidenced by external sessions and revalidate their affected boundaries.

**Deliverable.** Task-scoped source/content changes plus focused regression evidence.

**Validation.** Each fixed blocker is reproduced before repair where possible, no longer reproduces after repair, and unaffected verified behavior is preserved.

**Required evidence.** Before/after evidence, commit/tree, new package identity.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-026_REPAIR_THE_HIGHEST_IMPACT_REPRODUCIBLE_EXTERNAL_BLOCKERS.md` (SHA-256 `b10a1ac4bb8751ff0281a3b8fd3597ad1859a138d672782a4d9853d69c6f9b6f`)

## 048. D18-07 — Run post-repair external replay

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D18-06

**Objective.** Give the repaired package to an external player and repeat the affected scenario without founder steering.

**Deliverable.** Post-repair session evidence.

**Validation.** Previously targeted blockers are no longer acceptance-blocking; new failures are recorded without expanding the task into unrelated redesign.

**Required evidence.** Session logs/captures, package digest, comparison to prior findings.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-027_RUN_THE_POST_REPAIR_EXTERNAL_REPLAY.md` (SHA-256 `0abcbdeb5b04b08286fd9a7b66f6f7306031e7127f500f4c18547b782088eca5`)

## 049. D18-08 — Close independent-player proof

Lane: **Games** · Priority: **1** · Execution root: `projects/biella-games` · Dependencies: D18-07

**Objective.** Assemble external-play evidence sufficient to demonstrate the game can be installed, understood, and played beyond the founder environment.

**Deliverable.** Independent-player proof bundle with exact session/build identities and bounded qualitative/quantitative findings.

**Validation.** Bundle distinguishes observed facts, participant statements, and interpretation; no claim of broad market validation is made from a small cohort.

**Required evidence.** Bundle index/digest, session references, Drive readback.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-028_CLOSE_INDEPENDENT_PLAYER_PROOF.md` (SHA-256 `a96bba678d936b9a4ac8528a20882a36fb7adb3a885082f8124e725e176d2c05`)

## 050. D23-02 — Distribute qualified build to bounded external test cohort

Lane: **Cross-project** · Priority: **1** · Execution root: `.` · Dependencies: D23-01

**Objective.** Use an accepted distribution mechanism to deliver the exact qualified build to external testers without requiring development-workspace access.

**Deliverable.** External distribution record and downloadable/installable build identity.

**Validation.** Recipients receive the exact intended package, install/launch succeeds under the qualified instructions, and distribution identity is read back.

**Required evidence.** Distribution artifact ID, package digest, tester delivery records without unnecessary personal data.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-062_DISTRIBUTE_THE_QUALIFIED_BUILD_TO_A_BOUNDED_EXTERNAL_TEST_COHORT.md` (SHA-256 `496c605445dbfa30aea0ef570b4cbf45457249d15e1e4cc2b0e30a0fb6fa53b6`)

## 051. D23-03 — Capture real demand signals from proof surface

Lane: **Cross-project** · Priority: **1** · Execution root: `.` · Dependencies: D23-02

**Objective.** Collect only actual opt-in signals available on the accepted distribution/public surface, such as test requests, followers, wishlists if a store is accepted, or qualified inbound interest.

**Deliverable.** Demand-signal dataset with source, timestamp, and definition for each metric.

**Validation.** Every metric comes from a real platform/source record; platform-specific metrics are not invented when that platform is not active.

**Required evidence.** Export/readback from demand source and dataset digest.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-063_CAPTURE_REAL_DEMAND_SIGNALS_FROM_THE_PROOF_SURFACE.md` (SHA-256 `4ebac8d4a4c187a6c4e691b53148088c9efc1615375efc98afc055204a064193`)

## 052. D23-04 — Publish game demand evidence report

Lane: **Cross-project** · Priority: **1** · Execution root: `.` · Dependencies: D23-03

**Objective.** Summarize external play participation and demand signals without extrapolating unsupported market size or conversion claims.

**Deliverable.** Game demand report with exact source counts, dates, cohort definitions, and limitations.

**Validation.** Reported totals reconcile to source exports/readbacks; duplicates and unverified anecdotes are excluded or clearly separated.

**Required evidence.** Report digest and underlying source identities.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-064_PUBLISH_THE_GAME_DEMAND_EVIDENCE_REPORT.md` (SHA-256 `63ec03fd3d049a543d3508067fc176225a03a1b4e2b6b122949776000b286014`)

## 053. D09-06 — Cloudflare + GitHub Website Delivery Topology

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D09-05

**Objective.** Choose the project-specific Cloudflare/GitHub deployment topology, domains, previews, media placement, cache policy and rollback points.

**Deliverable.** Choose the project-specific Cloudflare/GitHub deployment topology, domains, previews, media placement, cache policy and rollback points.

**Validation.** Read back the existing domain/deployment identity and document the actual preview, media, cache and rollback path; reuse the deployed topology rather than replacing it.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 054. D10-01 — Website Application Scaffold and Preview Deployment

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D09-03, D09-04, D09-05, D09-06

**Objective.** Create the actual biellagames.dev application workspace, build/test scripts and reproducible preview deployment.

**Deliverable.** Create the actual biellagames.dev application workspace, build/test scripts and reproducible preview deployment.

**Validation.** Run the actual build/test scripts and read back a preview of the exact revision; reuse the existing website scaffold.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 055. D10-02 — Biella Website Design System

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D09-03, D10-01

**Objective.** Implement reusable website tokens and components from the Biella Visual Lock.

**Deliverable.** Implement reusable website tokens and components from the Biella Visual Lock.

**Validation.** Render representative reusable components at desktop/mobile sizes against current accepted visual sources; check consistency and interaction states.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 056. D10-03 — Typography, Iconography and Accessibility Foundation

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D10-01, D10-02

**Objective.** Implement the website typography/icon system, semantic structure, keyboard/focus behavior and accessibility baseline.

**Deliverable.** Implement the website typography/icon system, semantic structure, keyboard/focus behavior and accessibility baseline.

**Validation.** Exercise keyboard navigation, focus, semantic structure, text scaling and contrast in rendered pages; verify licensed source identities for icons/fonts.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 057. D10-04 — Motion and Transition Language

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D10-02, D10-03

**Objective.** Implement reusable website motion, transitions, scroll behavior and reduced-motion fallbacks.

**Deliverable.** Implement reusable website motion, transitions, scroll behavior and reduced-motion fallbacks.

**Validation.** Exercise normal and reduced-motion paths and route/scroll transitions without obscuring navigation or causing layout jumps.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 058. D10-05 — Website Asset Migration and Web Derivatives

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D09-03, D10-01

**Objective.** Move selected canonical assets into website-controlled storage and create only the web-specific derivatives required for delivery.

**Deliverable.** Move selected canonical assets into website-controlled storage and create only the web-specific derivatives required for delivery.

**Validation.** Verify original-to-derivative identities, dimensions, formats and delivery; retain editable masters and generate only missing required derivatives.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 059. D10-06 — Website Content Registry

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D09-04, D10-01

**Objective.** Create project-specific typed content records for products, capabilities, projects, games/worlds, media, docs, timeline entries and links.

**Deliverable.** Create project-specific typed content records for products, capabilities, projects, games/worlds, media, docs, timeline entries and links.

**Validation.** Validate typed content records, source links, product ownership and missing/invalid references; keep live facts separate from manually authored copy.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 060. D11-01 — Cinematic Entry and Living Biella Core

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D10-02, D10-04, D10-05, D10-06

**Objective.** Build the cinematic entry/Living Core website experience with fast mobile and reduced-motion fallbacks.

**Deliverable.** Build the cinematic entry/Living Core website experience with fast mobile and reduced-motion fallbacks.

**Validation.** Exercise entry interaction on desktop/mobile and reduced-motion/low-capacity fallbacks using actual page rendering.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 061. D11-02 — Home Journey — Objective to Delivery

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D10-06, D11-01

**Objective.** Create the public interactive story of Research → Intelligence → Planning → Creation → Delivery using truthful representations of Task/Graph/Event/routing concepts.

**Deliverable.** Create the public interactive story of Research → Intelligence → Planning → Creation → Delivery using truthful representations of Task/Graph/Event/routing concepts.

**Validation.** Exercise the complete objective-to-delivery journey; distinguish real runtime evidence from labeled demonstrations.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 062. D11-03 — Biella Engine Product Experience

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D10-06, D11-02

**Objective.** Present Biella Engine architecture, verified current state, capability status, execution concepts and roadmap as a public product experience.

**Deliverable.** Present Biella Engine architecture, verified current state, capability status, execution concepts and roadmap as a public product experience.

**Validation.** Check each Engine capability/current-state claim against current source and render verified/prototype/roadmap distinctions.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 063. D11-04 — Biella Games Product Experience

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D10-05, D10-06, D11-02

**Objective.** Build the Biella Games destination from accepted game/world/media assets, playable material and release information.

**Deliverable.** Build the Biella Games destination from accepted game/world/media assets, playable material and release information.

**Validation.** Verify Games content, media and playable links against accepted project artifacts; do not invent release platforms or dates.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 064. D11-05 — Intelligence Experience

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D10-06, D11-02

**Objective.** Visualize approved research/context/model/tool/knowledge/routing evidence and provide deterministic demo data when live engine evidence is unavailable.

**Deliverable.** Visualize approved research/context/model/tool/knowledge/routing evidence and provide deterministic demo data when live engine evidence is unavailable.

**Validation.** Verify displayed research/context/model evidence and label deterministic demo data explicitly.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 065. D11-06 — Production Pipeline Experience

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D10-06, D11-02

**Objective.** Create an interactive visualization of multi-domain production across software, games, 3D, media, validation and delivery.

**Deliverable.** Create an interactive visualization of multi-domain production across software, games, 3D, media, validation and delivery.

**Validation.** Exercise software/game/media/validation/delivery views; observer interaction must not start, stop or alter production.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 066. D12-01 — Capability Explorer

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D11-03, D11-05, D11-06

**Objective.** Build a public explorer over capability definitions/status/resources with explicit verified/prototype/planned states.

**Deliverable.** Build a public explorer over capability definitions/status/resources with explicit verified/prototype/planned states.

**Validation.** Exercise capability filters, details, source references and verified/prototype/planned labels.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 067. D12-02 — Interactive Orchestration Demonstration

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D12-01

**Objective.** Let visitors safely explore a task-decomposition/orchestration demonstration using actual engine records when available and clearly labeled synthetic scenarios otherwise.

**Deliverable.** Let visitors safely explore a task-decomposition/orchestration demonstration using actual engine records when available and clearly labeled synthetic scenarios otherwise.

**Validation.** Run the orchestration interaction; use actual records or explicitly labeled synthetic scenarios without controlling production.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 068. D12-03 — Project and Showcase System

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D10-06, D11-03, D11-04

**Objective.** Build reusable public case-study/project pages from accepted project-scoped source and media.

**Deliverable.** Build reusable public case-study/project pages from accepted project-scoped source and media.

**Validation.** Validate project-scoped records and reusable showcase routes with correct accepted media and no customer-private data.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 069. D12-04 — Game / World Gallery and Playable Embeds

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D11-04, D12-03

**Objective.** Build the website gallery/player layer for accepted game/world/playable media with lazy loading and fallbacks.

**Deliverable.** Build the website gallery/player layer for accepted game/world/playable media with lazy loading and fallbacks.

**Validation.** Exercise gallery/playable loading, keyboard access, lazy loading and unavailable-media fallbacks.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 070. D12-05 — 3D and Media Gallery

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D10-05, D12-03

**Objective.** Present accepted 3D, character, animation, environment, render, VFX, image, audio and video artifacts through performant website viewers.

**Deliverable.** Present accepted 3D, character, animation, environment, render, VFX, image, audio and video artifacts through performant website viewers.

**Validation.** Decode and interact with required 3D/media viewers; verify lazy loading, controls and fallback behavior against actual artifacts.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 071. D12-06 — Interactive Timeline, News and Releases

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D10-06, D12-03

**Objective.** Build source-backed public timeline/news/release views with explicit released/planned distinctions.

**Deliverable.** Build source-backed public timeline/news/release views with explicit released/planned distinctions.

**Validation.** Verify timeline/news/release ordering, source identity and released-versus-planned distinctions.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 072. D13-01 — Public Documentation Hub

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D10-06, D12-03

**Objective.** Publish approved public documentation as a deep-linkable, version-aware Biella Universe experience.

**Deliverable.** Publish approved public documentation as a deep-linkable, version-aware Biella Universe experience.

**Validation.** Verify documentation deep links, version labels, public-source scope and navigation.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 073. D13-02 — Public Website Search

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D10-06, D13-01

**Objective.** Build the public search UI, approved public index scope and result presentation on top of Biella retrieval semantics when available.

**Deliverable.** Build the public search UI, approved public index scope and result presentation on top of Biella retrieval semantics when available.

**Validation.** Test representative public queries, missing results and forbidden/private source exclusion.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 074. D13-03 — Ask Biella Public Guide

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D13-01, D13-02

**Objective.** Integrate a public, bounded assistant over approved website/public documentation context with truthful uncertainty and cost controls.

**Deliverable.** Integrate a public, bounded assistant over approved website/public documentation context with truthful uncertainty and cost controls.

**Validation.** Run grounded public-guide queries, unavailable-answer cases and bounded request/cost behavior; do not expose private context.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 075. D13-04 — NVIDIA Compute / Model Demonstration

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D11-05, D12-01

**Objective.** Visualize or expose authorized, actually observed NVIDIA/model/resource evidence; use clearly labeled demo data otherwise.

**Deliverable.** Visualize or expose authorized, actually observed NVIDIA/model/resource evidence; use clearly labeled demo data otherwise.

**Validation.** Read actual configured compute/model evidence, or visibly label demo data; do not fabricate live GPU/model use.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 076. D13-05 — Live Research / Tool Demonstration

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D11-05, D12-02

**Objective.** Expose one safe bounded public research/tool scenario using approved external adapters when available; otherwise run a labeled deterministic demonstration.

**Deliverable.** Expose one safe bounded public research/tool scenario using approved external adapters when available; otherwise run a labeled deterministic demonstration.

**Validation.** Run the approved research/tool scenario through its real adapter or a clearly labeled deterministic demo; preserve source attribution.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 077. D13-06 — About, Partner, Investor and Contact Experience

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D10-06, D12-03

**Objective.** Build the public company/partner/investor/contact experience and working project-specific contact delivery.

**Deliverable.** Build the public company/partner/investor/contact experience and working project-specific contact delivery.

**Validation.** Exercise company/investor/contact journeys and verify actual configured contact delivery, not just form submission appearance.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 078. D14-01 — SEO, Social Preview and Discoverability

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D12-03, D13-01

**Objective.** Implement project-specific metadata, semantic pages, sitemap/robots, structured data and social previews.

**Deliverable.** Implement project-specific metadata, semantic pages, sitemap/robots, structured data and social previews.

**Validation.** Validate sitemap/robots, canonical URLs, semantic metadata and rendered social previews against actual routes.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 079. D14-02 — Analytics, Privacy and Product Insight

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D10-01, D10-06

**Objective.** Implement privacy-conscious website analytics and interaction/error/performance events without mixing them with internal engine truth.

**Deliverable.** Implement privacy-conscious website analytics and interaction/error/performance events without mixing them with internal engine truth.

**Validation.** Verify privacy-conscious interaction/error/performance events and keep website analytics separate from Engine execution truth.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 080. D14-03 — Performance, Caching and Core Web Vitals

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D11-01, D12-04, D12-05, D14-01

**Objective.** Optimize the website's bundles/media/rendering/caching and verify real browser performance; optionally consume engine locality/failure evidence when available.

**Deliverable.** Optimize the website's bundles/media/rendering/caching and verify real browser performance; optionally consume engine locality/failure evidence when available.

**Validation.** Measure real browser performance for representative routes/media and compare before/after bundles, rendering and cache behavior.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 081. D14-04 — Responsive, Browser, Device and Accessibility Qualification

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D11-01, D12-04, D12-05, D13-06, D14-01

**Objective.** Qualify critical website journeys across the agreed browser/device/accessibility matrix using real browser evidence.

**Deliverable.** Qualify critical website journeys across the agreed browser/device/accessibility matrix using real browser evidence.

**Validation.** Run critical journeys across the currently agreed browser/device/accessibility matrix; record the tested matrix instead of inventing coverage.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 082. D14-05 — Website Resilience, Error and Cost Boundaries

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D13-03, D13-05, D13-06, D14-02

**Objective.** Implement project-specific website fallback UX, request/time/cost ceilings and failure behavior around dynamic/external features.

**Deliverable.** Implement project-specific website fallback UX, request/time/cost ceilings and failure behavior around dynamic/external features.

**Validation.** Inject scoped API/media/network failures and verify usable fallbacks and request/time/cost ceilings without affecting production.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 083. D14-06 — Cloudflare Production Launch and Final Website Qualification

Lane: **Website** · Priority: **2** · Execution root: `website` · Dependencies: D14-01, D14-02, D14-03, D14-04, D14-05

**Objective.** Deploy the exact accepted website revision to biellagames.dev, verify production behavior, record the deployed commit and prove rollback.

**Deliverable.** Deploy the exact accepted website revision to biellagames.dev, verify production behavior, record the deployed commit and prove rollback.

**Validation.** Read back the exact deployed revision and critical production journeys and demonstrate the defined rollback path.

**Required evidence.** Exact source/revision; consumed Engine interfaces and capability mode; editable website changes; task-derived validation and artifact identities; remote readback for actual deployment outputs.

**Source records.** `docs/task-program/D09_D14_WEBSITE.md` (SHA-256 `c58da04721db0c797f863125ea08c7484b9127ea015725ba350b02c2cd01f05f`); `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` (SHA-256 `278ac7f149be074e3e1d88997bcf5ff4456a46aae1abacf3da1fa2f1496b9022`)

## 084. D21-01 — Define founder-leverage evidence schema

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D20-08

**Objective.** Define the minimal durable measurements needed to quantify AI-native execution leverage without creating a second analytics authority or leaking project-private content.

**Deliverable.** Versioned evidence schema for tasks, runs, accepted outcomes, founder interventions, elapsed time, model/provider/resource use, cost where available, and recovery events.

**Validation.** Schema maps to current Engine Task/Run/Resource/Event concepts or existing semantic equivalents; it does not create project-specific permanent Engine types.

**Required evidence.** Schema/source commit and mapping to current Engine interfaces.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-045_DEFINE_THE_FOUNDER_LEVERAGE_EVIDENCE_SCHEMA.md` (SHA-256 `8787146aa08d6e2d092978bb97222044676a17b48403bc388f48700baffbeca7`)

## 085. D21-02 — Compute accepted-task throughput from real traces

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D21-01

**Objective.** Calculate accepted production-task throughput for bounded periods using durable execution records rather than chat estimates.

**Deliverable.** Throughput dataset/report with task IDs, acceptance state, period boundaries, and source traces.

**Validation.** Every counted task has durable accepted completion evidence; retries and failed attempts are not miscounted as accepted output.

**Required evidence.** Task/run IDs, calculation script/query if needed, resulting dataset digest.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-046_COMPUTE_ACCEPTED_TASK_THROUGHPUT_FROM_REAL_TRACES.md` (SHA-256 `902566fa4ff555089b47ab9aadfd185fec3aa2c265028c6eb69e478ca775ff4c`)

## 086. D21-03 — Measure founder intervention per accepted outcome

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D21-02

**Objective.** Classify real founder interventions needed to redirect, repair, decide, or accept work and measure them against accepted outputs.

**Deliverable.** Intervention dataset with explicit categories and links to source events.

**Validation.** Only observed interventions are counted; authority/acceptance actions are not mislabeled as engineering labor without evidence.

**Required evidence.** Event/task references and aggregate calculation.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-047_MEASURE_FOUNDER_INTERVENTION_PER_ACCEPTED_OUTCOME.md` (SHA-256 `1140a59adb4ca797b5d0333d3d40ec1d42ac1fd17ad3c768017de846cd296fa8`)

## 087. D21-04 — Measure compute, model, tool, and infrastructure cost per outcome

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D21-03

**Objective.** Aggregate available real usage/cost evidence by accepted task or milestone while preserving provider/resource replaceability.

**Deliverable.** Cost/resource dataset and normalized per-outcome view where source data exists.

**Validation.** Costs are from provider/runtime records or exact measured resource use; unavailable prices are UNKNOWN rather than fabricated.

**Required evidence.** Resource/event records, provider invoices/usage references where authorized, calculation output.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-048_MEASURE_COMPUTE_MODEL_TOOL_AND_INFRASTRUCTURE_COST_PER_OUTCOME.md` (SHA-256 `3253f2df876a6fa0ce966ddcd091aee111ced9aabe067ec0e160274afce256e9`)

## 088. D21-05 — Measure objective-to-validated-artifact cycle time

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D21-04

**Objective.** Measure elapsed time from durable objective/task activation through validated output for representative tasks.

**Deliverable.** Cycle-time dataset across selected Games and Engine tasks.

**Validation.** Start/end boundaries are defined from actual persisted Task/Run/Event states; paused or externally blocked time is distinguishable where evidence supports it.

**Required evidence.** Task/run/event IDs and calculation output.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-049_MEASURE_OBJECTIVE_TO_VALIDATED_ARTIFACT_CYCLE_TIME.md` (SHA-256 `2e7c084403eaa23f7e2037103ae30e06d8290739e5e12a17b8839f837c924c66`)

## 089. D21-06 — Benchmark durable recovery after interruption

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D21-05

**Objective.** Interrupt a representative active workload at an accepted safe boundary and verify continuation from durable state without replaying verified completed work.

**Deliverable.** Recovery benchmark record.

**Validation.** A new process/session/resource reconstructs current task state and continues correctly; unaffected verified outputs remain reused.

**Required evidence.** Pre-interruption state identity, restart evidence, post-recovery task/run IDs.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-050_BENCHMARK_DURABLE_RECOVERY_AFTER_INTERRUPTION.md` (SHA-256 `2faeb6d0aa04752164b4211566c2fe7299fb3748529c9982f7efdda882e927db`)

## 090. D21-07 — Benchmark model or provider continuity on the same project

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D21-06

**Objective.** Continue one representative project objective across a model/provider change without changing project truth or task semantics merely to fit the worker.

**Deliverable.** Cross-model/provider continuity benchmark.

**Validation.** The replacement worker receives durable current project/task state, preserves accepted work, and completes the next bounded output with normal task-derived validation.

**Required evidence.** Before/after worker/resource identities, task/run evidence, output validation.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-051_BENCHMARK_MODEL_OR_PROVIDER_CONTINUITY_ON_THE_SAME_PROJECT.md` (SHA-256 `d8ffe4d46135d970dd34239ab9944569ff460785ba0aeb08244e5cb8c9712cc6`)

## 091. D21-08 — Publish solo-founder leverage evidence report

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D21-07

**Objective.** Assemble measured throughput, intervention, cycle time, resource cost, recovery, and continuity evidence into a reproducible report.

**Deliverable.** Founder-leverage report with calculations and exact trace references.

**Validation.** Every number can be recomputed from cited durable evidence; unsupported narrative claims are omitted.

**Required evidence.** Report digest, calculation inputs, Engine source/trace identities, Drive publication readback.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-052_PUBLISH_THE_SOLO_FOUNDER_LEVERAGE_EVIDENCE_REPORT.md` (SHA-256 `6b56cd1f91154ce1287cf2ac937cceadd4cae382a2e1862b012b6a6a34db2985`)

## 092. D22-01 — Select non-Biella-Games external pilot objective

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D21-08

**Objective.** Bind one real outside-user/project objective that tests Biella as a universal execution system rather than a game-specific automation.

**Deliverable.** Pilot brief with owner/user objective, project boundary, allowed resources, expected output contract, and acceptance evidence.

**Validation.** Pilot does not import Biella Games canon into Engine behavior and does not depend on MiniTZ historical instructions.

**Required evidence.** Pilot brief, project identity, accepted output contract.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-053_SELECT_A_NON_BIELLA_GAMES_EXTERNAL_PILOT_OBJECTIVE.md` (SHA-256 `9539f90f436622f96db1fba981d6199e57c5dcf38922c0da656f5e84c9bbebbe`)

## 093. D22-02 — Package repeatable external deployment and onboarding path

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D22-01

**Objective.** Reduce current Engine deployment/onboarding to a reproducible package or documented procedure that does not require reconstructing the founder environment by hand.

**Deliverable.** External deployment/onboarding package tied to an exact Engine commit.

**Validation.** A fresh authorized environment can instantiate the required Engine services/state using the package without undocumented founder-only repair.

**Required evidence.** Engine commit/tree, deployment logs, environment identity.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-054_PACKAGE_THE_REPEATABLE_EXTERNAL_DEPLOYMENT_AND_ONBOARDING_PATH.md` (SHA-256 `478ed93f63318f29535d62664f801a8fd26221ebfa8787bff418fafa4a33f423`)

## 094. D22-03 — Onboard external pilot without founder reconstruction

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D22-02

**Objective.** Have the external pilot user/environment establish its project and first task through the supported interface rather than by editing internal Engine state.

**Deliverable.** Pilot project/task identities and onboarding evidence.

**Validation.** Required project truth and task contract are persisted through supported Engine boundaries; manual database/file surgery is not part of the normal path.

**Required evidence.** Project/task IDs, interface logs, persisted state readback.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-055_ONBOARD_THE_EXTERNAL_PILOT_WITHOUT_FOUNDER_RECONSTRUCTION.md` (SHA-256 `672ae2b190a9dfc279332715fe8fbcdad090b1de484c96478e3060c28c944ef5`)

## 095. D22-04 — Execute first external objective to a validated artifact

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D22-03

**Objective.** Run the pilot objective through real resources and produce the contracted output with task-derived validation.

**Deliverable.** Validated pilot artifact and execution trace.

**Validation.** Artifact matches the pilot output contract and is linked to exact Task/Run/Graph/source/resource identities; agent claim alone is insufficient.

**Required evidence.** Artifact identity/digest, run/events, validation evidence.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-056_EXECUTE_THE_FIRST_EXTERNAL_OBJECTIVE_TO_A_VALIDATED_ARTIFACT.md` (SHA-256 `b38f544c33f0ef51c6fcbfa043fd573628ff729a9c6f7c69a2aa841de04ab93d`)

## 096. D22-05 — Persist and reconstruct external pilot state

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D22-04

**Objective.** End the active process/session and prove the external project can be reconstructed from durable state.

**Deliverable.** External pilot continuation record.

**Validation.** Project/task/run state reappears correctly without relying on chat context, RAM, temporary cache, or founder memory.

**Required evidence.** Shutdown/restart evidence, persisted object identities, reconstructed state readback.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-057_PERSIST_AND_RECONSTRUCT_THE_EXTERNAL_PILOT_STATE.md` (SHA-256 `3bd004bbe818129a2c6bfadd8df08cd4bb58a46e621b747b51053db9423ff0a0`)

## 097. D22-06 — Recover pilot after bounded infrastructure interruption

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D22-05

**Objective.** Introduce or use a real bounded interruption and verify smallest-boundary recovery.

**Deliverable.** External recovery benchmark.

**Validation.** Only invalidated work is retried; verified unaffected artifacts/state are preserved; continuation reaches the same project truth.

**Required evidence.** Failure evidence, recovery actions, resulting task/run/artifact identities.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-058_RECOVER_THE_PILOT_AFTER_A_BOUNDED_INFRASTRUCTURE_INTERRUPTION.md` (SHA-256 `f317b0e52c315b3dc85232a886826051c5bdf0a4fca4683b27e585d9d046093d`)

## 098. D22-07 — Continue external pilot with second objective or worker change

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D22-06

**Objective.** Demonstrate that the pilot is a continuing project rather than a one-shot demo by completing a next bounded objective, optionally using a different worker/provider where appropriate.

**Deliverable.** Second validated pilot output linked to the same durable project.

**Validation.** Project truth and prior accepted artifacts remain stable; new work is a new task/run rather than mutation of historical evidence.

**Required evidence.** Second task/run/artifact identities and validation.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-059_CONTINUE_THE_EXTERNAL_PILOT_WITH_A_SECOND_OBJECTIVE_OR_WORKER_CHANGE.md` (SHA-256 `73fae23bc1b28fb3aa7bc94065928f0411c820d3e5b3327c28f7ee701e2c03bb`)

## 099. D22-08 — Close external replication proof

Lane: **Engine** · Priority: **2** · Execution root: `.` · Dependencies: D22-07

**Objective.** Assemble onboarding, execution, persistence, recovery, and continuation evidence showing the founder's leverage transfers to another project/user environment.

**Deliverable.** External replication evidence bundle.

**Validation.** Bundle is reproducible from exact Engine/source/deployment identities and clearly separates pilot user outcomes from founder-run internal proof.

**Required evidence.** Bundle index/digest, pilot references, Drive readback.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-060_CLOSE_EXTERNAL_REPLICATION_PROOF.md` (SHA-256 `2dbebef7c492184452c492e7e7c358c6652291eb3e51b002f64a68f83c13240c`)

## 100. D23-05 — Package external pilot commercial offer

Lane: **Cross-project** · Priority: **2** · Execution root: `.` · Dependencies: D23-04, D22-08

**Objective.** Turn the proven external Engine pilot capability into a clear bounded paid offer or recurring pricing model without changing Engine architecture to fit a sales document.

**Deliverable.** Commercial pilot/pricing package describing scope, usage basis, support boundary, deliverables, and exclusions.

**Validation.** Offer maps to capabilities actually proven by external replication; unimplemented enterprise features are not promised.

**Required evidence.** Offer document identity, capability/evidence references.

**Source records.** `docs/task-program/D15_D24_AAA_CHALLENGER.md` (SHA-256 `12ea5a8f016da58b5100029a968301a447d179a80777e675e392c5dc9221534e`); `docs/future/aaa-challenger-solo-founder/tasks/AAA-SF-065_PACKAGE_THE_EXTERNAL_PILOT_COMMERCIAL_OFFER.md` (SHA-256 `0e41c66eaa64540c3c63dfab90a102660baf7c3e1a97e41790df083c0de5f5d5`)
