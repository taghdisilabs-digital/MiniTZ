# D02-04 — Interaction, destruction, and environment state

The editable open world now contains a playable electrical service bay. E changes
its power state through the same distance, facing, visibility, input, and match
gates used by its HUD prompt. Normal weapon input damages individual barrier
panels and detaches their actual geometry into Chaos. Destruction opens movement
and navigation; a live floor applies shared damage to player, rival, and infected.
Power, damage, and debris survive match-local streaming suspension and return.
The existing R restart restores one intact, unpowered site.

This is the single D02-04 boundary in implementation sequence 2.4 and runtime
contracts 13, 27, and 28. It preserves the current vehicle, combat, streaming,
objective, and feedback paths. No successor or canonical status is advanced.

## Editable implementation and operation

`Source/BiellaGames/Public/BiellaEnvironmentSite.h` and
`Source/BiellaGames/Private/BiellaEnvironmentSite.cpp` own the named match-local
actor, panels, switch, power presentation, localized hazard, and debris support.
Five existing character/controller/HUD/game-mode integration files connect the
new actor to normal input. `docs/ENVIRONMENT_RUNTIME.md` gives controls, source
locations, state rules, and reproduction commands.

The bay starts safe at (6500, 700, 0), beside the streamed road. Each panel has
68 health. Two ordinary 34-damage rounds produce intact, damaged, and detached
states; unaffected panels retain their health. The center panel is 240 cm wide,
providing navigation clearance for the configured 48 cm agent radius. Detached
lightweight panels retain static-world physics collision and ignore pawns.
The switch, frame, and markings remain solid or decorative as appropriate.

The floor integrates 12 HP per exposure-second in pulses no faster than four per
second. Leaving, deactivating, or suspending the field discards fractional pulse
exposure, so no deferred damage accumulates. Short measured intervals can differ
by one pulse, approximately 3 HP plus frame overshoot. Geometry shields exposure;
other pawn capsules do not. Distance and support checks suspend debris before
the underlying street unloads, without adding a streaming source.

## Native runtime evidence

`D02-04-build-07.log` records the successful final C++ Editor build. The exact
tested module, source, content, configuration, and tool identities are retained
in the run reports and `D02-04-final-input-identities.json`.

Both `D02-04-acceptance-30/validation.json` and
`D02-04-acceptance-120/validation.json` report PASS with clean process exit and
closed logs. They use Unreal 5.8.2, Linux Vulkan, 1280×720, native variable
timestep, VSync off, and no benchmark mode. Requested caps are workload controls,
not attained or qualified shipping rates.

| Requested cap | Recorded frames | Median frame ms | Hazard sample seconds | Player / rival / infected HP loss |
| --- | ---: | ---: | ---: | --- |
| 30 | 730 | 33.337 | 1.466704 | 19.201 / 16.000 / 16.000 |
| 120 | 2,018 | 12.319 | 1.489415 | 15.315 / 15.361 / 15.361 |

Each independently replayed hazard sample stays within the specified pulse
tolerance of integrated exposure. The 120 cap ran around 81 FPS at the median;
all hitches remain in the original per-frame evidence.

Both runs verify:

- Invalid, input-disabled, terminal-match, distant, wrong-facing, and occluded
  switch actions are rejected, with matching prompt availability.
- Real E and left-mouse input change power and spend exactly two rounds;
  unlocalized generic damage cannot invent a fracture.
- The center mesh physically moves more than 50 cm. Its blocking capsule sweep
  becomes clear, and the dynamic navigation route changes from 1428.346 cm to
  520.000 cm. Real W input traverses the opening.
- The shared floor damages all three pawn types with bounded hurt feedback.
  Cutting power stops damage, including any pending fractional exposure.
- Actual supporting terrain unloads. Detached geometry stops simulating and
  remains stationary, then returns with the same revision, power, health, and
  position. Powered damage resumes after return.
- R creates exactly one fresh site, with all panels intact and power off.

The fixture temporarily suppresses population admission and holds non-player
behavior to isolate causality. It uses the existing supported on-foot relocation
for approach, departure, and return; it never assigns panel health, power, or
debris transforms. Temporary geometry checks switch occlusion. Brief restored
input/match-state fixtures check invalid actions. Those fixtures do not describe
normal gameplay or prove unscripted AI use of the site.

Five original 30-cap PNGs were directly inspected: safe switch, damaged panel,
destroyed panel, active hazard, and streaming return. Capture holds keep fixture
relocations out of the rendered evidence. `D02-04-final-visual-review.json`
records exact identities and observations. The HUD partially overlaps the far
sign from the switch approach; the prompt and field state remain readable.
All captures remain `GENERATED_DRAFT` development geometry and effects.

## Regression, review, and evidence integrity

`D02-04-final-replay.json` replays both environment runs and the unchanged
predecessor verifiers against the same final gameplay module:

- Vehicle: PASS over 2,253 recorded frames. Physical driving, steering, braking,
  collision damage, entry/exit, NPC contact, streaming, audio, and restart remain
  functional. The car travels 64.882 m and reaches 48.305 km/h.
- Shared combat: PASS for ten phases, twenty damage events, all six directions
  between player/rival/infected, and four defeats.

`tests/test_verify_d02_04.py` accepts the native baseline and rejects fourteen
corrupted copies: missing or nonfinite frames, fixed timestep, missing damage
stage, absent physics, falling dormant debris, absent traversal, unequal hazard,
damage on a safe floor, lost revision, absent resumed damage, missing restart,
missing weapon input, and blank capture. The clean final run is retained in
`D02-04-verifier-controls-final.log`.

Those controls exposed an unclosed CSV-reader warning. The final verifier uses a
context manager; every acceptance predicate is unchanged. The exact pre-fix
tool is retained as `D02-04-verifier-before-file-close.txt`. The final identity
audit proves that this is the sole post-run input-file delta, checks its exact
text replacement, and replays both original runs with the final verifier. All
gameplay/source/content/module bytes still match the native runs. The audit
checks 785 recorded identities across all four runs.

The configured local Qwen resource supplied a bounded design-risk review.
Streaming continuity, action gating, shared damage, and restart concerns were
validated against current code and native evidence; its speculative network and
serialization suggestions did not expand scope. Two later bounded review
requests timed out and were rerouted to direct source and runtime review.
Resource responses are retained as non-authoritative inputs.

Earlier failures remain intact: the red presence test, a runtime file-permission
repair, one C++ type-deduction fix, nav clearance probes, shared hazard occlusion,
and blurred capture fixtures. The failed-automation Vulkan teardown assertion
followed the already-failed test result; final runs exit cleanly. No renderer
failure was suppressed to produce acceptance. The environment wrapper retains
the predecessor's exact known-startup Dataflow diagnostic classification;
unknown errors and runtime/test failures still fail. Task-filtered records are
retained in `D02-04-observed-failures.jsonl` beside original attempts.

## Preservation and handoff

`D02-04-preservation.json` checks all 1,128 baseline files: 1,123 unchanged and
exactly five intended integration modifications. Predecessor maps, assets,
evidence, and 03/04/PRODUCTION authority retain their bytes. Engine P4-06 remains
`INCOMPLETE_DEFERRED`. Upstream controller commits during this session affect
only controller tooling; the gameplay and protected-source audit is unchanged.

`D02-04-manifest.json` identifies the exact canonical local implementation,
documentation, raw attempts, and final evidence by path, byte count, and SHA-256.
Its entries exclude only the manifest itself. Files remain at these project
paths; no publication destination is invented.

This evidence qualifies bounded interaction and environment mechanics in the
current playable blockout. It does not claim final AAA art, disk persistence,
network play, weather, Win64/shipping qualification, or a new standalone package.
The existing non-editor package limitation is unchanged.

The task's implementation and evidence are committed locally. The Auto Feeder
owns canonical GitHub/Drive publication, remote readback, and state transition
under the current task instruction. No remote publication or successor
advancement is claimed by this boundary.
