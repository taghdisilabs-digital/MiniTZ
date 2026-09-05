# D01-39 — deterministic playtest harness and telemetry

Result: **PASS**, local implementation and evidence for this task boundary. Publication and the canonical task transition remain owned by the Auto Feeder; 03/04 and `PRODUCTION.md` are unchanged.

## Implemented behavior

- `BiellaDeterministicPlaytest.cpp` runs `BiellaGames.Demo01.DeterministicPlaytest` through the actual possessed player, Enhanced Input, weapon traces, shared damage, objective success, autonomous infected melee failure, terminal HUD, and bound `R` restart input. It checks seven ordered checkpoints across two map reloads and a fixed 60 Hz simulation step.
- Controlled fixture choices use an explicit seed. Success targets remain stationary; the failure encounter runs infected AI. A scenario-lifetime pre-actor-tick callback establishes full-health spawn conditions before incidental rival attacks. Health, ammunition, cooldowns, objective progress, and terminal outcomes are never assigned by the harness. Callback cleanup restores AI ticking.
- `UBiellaPlaytestTelemetry` captures local UTF-8 JSONL only when `-BiellaTelemetry=<new path>` is supplied. Real gameplay hooks record damage, defeat, shots, blocked traces, objective changes, phase changes, pressure, and restarts. Session identity and contiguous sequence survive world reloads; raw world/session timestamps remain available. Capture files are flushed per event, and existing paths or write errors fail closed.
- `tests/run_d01_039.py` runs independent processes with deadlines, preserves each attempt, checks Unreal automation results, and records exact source/configuration/map/build hashes. It includes both the canonical entry map and the recovered map resolved by the existing runtime. `tests/verify_d01_039.py` validates capture integrity, expected outcomes, and equality of every ordered semantic event/field. [Usage and schema](../../docs/DEMO_01_PLAYTEST.md) describe the reproducibility boundary.

## Observed validation

| Check | Result |
| --- | --- |
| UE 5.8.2 Editor build | PASS, `BiellaGamesEditor Linux Development`, qualified build log |
| Seed 1337, two fresh headless processes | PASS, seven checkpoints and 56 matching semantic events per process |
| Seed 1337, two fresh Vulkan processes | PASS, 1280×720 offscreen runtime, same 56-event trace as both headless processes |
| Seed 42, two fresh headless processes | PASS, seeded pressure changed from 20 to 9, both alternate-seed traces matched |
| Final verifier across all four seed-1337 captures | PASS, exact semantic equality across renderers |
| Verifier adversarial tests | PASS, 19 tests including missing/changed/reordered events, broken resets, duplicate sequences, failed scenarios, incomplete captures, and clock/lifecycle handling |
| SharedInteraction regression | PASS in a fresh process, all six directed damage edges through runtime input/AI |
| ObjectiveManager regression | PASS in a fresh process |
| TerminalOverlay regression | PASS in a fresh process, both terminal outcomes and bound restart input |
| Telemetry disabled regressions | PASS, no telemetry option, errors, or JSONL output |
| Structural verifier | PASS, `completed=38/50 current=D01-39`, canonical metadata preserved |

Every successful scenario recorded six weapon hits, fifteen damage events (six weapon hits plus nine autonomous melee hits), three defeats, seven checkpoints, and two restart requests. Each reconstructed baseline restored health 100, ammo 60, two infected, objective progress zero, pressure zero, and Active phase.

Seed-1337 semantic trace SHA-256: `bd7cd9423274abb57357d990d94bfda7f2307cc5569fcf36f1445fea49a69756`.

Seed-42 semantic trace SHA-256: `7468934fb85642ac75491daa618e64a8bee945ac5d1ff2f44c2a8fc9842a6638`.

## Evidence and retained failures

[`D01-039-validation.json`](D01-039-validation.json) indexes all successful runs, protected-file hashes, build/validation evidence, and the retained failed attempts. Every run directory includes exact commands, automation logs, JSONL telemetry, and validation. The final seed-42 run records the final editable source and verifier identities; the final verifier also revalidated the earlier seed-1337 captures. All six gameplay runs used the same qualified C++ binary.

- [Qualified build](D01-039-editor-build-qualified.log)
- [Headless seed 1337](D01-039-runs/20260905T071125.206199Z-nullrhi-09c5153b/validation.json)
- [Vulkan seed 1337](D01-039-runs/20260905T071227.716362Z-vulkan-1cdb2330/validation.json)
- [Headless seed 42 and final source identities](D01-039-runs/20260905T071440.953098Z-nullrhi-a142aeec/validation.json)
- [Comparison across renderers](D01-039-cross-renderer-validation.json)
- [Predecessor regressions](D01-039-regressions-20260905T071252Z-0344b0aa/validation.json)
- [Verifier self-tests](D01-039-verifier-selftest.log)

The first build failed because newly created source files were unreadable by the existing Unreal build account; source permissions were repaired. The first runtime capture correctly failed when a rival's first-tick shot damaged a target before fixture setup; the pre-actor-tick boundary fixed that race, and full enemy-health checks now protect the baseline. The first runner attempt failed because a root-created output ancestor was inaccessible to Unreal; output creation and runtime-user access checks were repaired. Their original logs/captures remain alongside the qualified runs.

This result establishes a reproducible gameplay regression scenario and captured event timeline on the existing Linux development host. It does not claim deterministic rendered pixels/general physics, native performance qualification, soak stability, a Windows package, or manual visual/play acceptance.
