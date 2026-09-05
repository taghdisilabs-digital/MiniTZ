# D01-43 — stability/soak qualification

Result: **PASS — bounded Linux development-host stability qualification, committed locally with this task.** Only D01-43 is in scope. Publication and canonical task transition belong to the Auto Feeder; 03/04 and Project PRODUCTION metadata are protected.

## Observed qualification

| Check | Result |
| --- | --- |
| UE 5.8.2 BiellaGamesEditor Linux Development | PASS; [build log](D01-043-editor-build.log) |
| Continuous workload | **911.972 seconds** after the first clean baseline; 933.298 seconds including process startup/shutdown |
| Process/session continuity | One Unreal PID `1726883`, start ticks `24600140`, one telemetry session and GameInstance; no surviving test processes |
| Gameplay/restart coverage | **69 complete cycles**, 483 ordered checkpoints, 138 bound terminal restarts, 68 intervening natural-encounter reloads; **206 workload reloads** |
| Deterministic preservation | All 69 ordered 56-event core traces exactly match D01-42’s qualified predecessor; trace SHA-256 `438cd2e30b6f67f2fe6319a51451dfd0046264638ef8065e5acbb4b74b49a7af` |
| Autonomous workload | **68 dwell periods**, 340.404 total wall seconds, real AI movement in each, **505 autonomous damage events** |
| Liveness and integrity | 5,916 contiguous telemetry records; **903 heartbeats**, maximum heartbeat gap **1.093 seconds**; no stalled frame progression |
| Runtime invariants | Four gameplay actors, finite actor/camera state, correct world membership and ready feedback assets; audio/VFX remain inside 14/24 caps |
| Runtime failures and shutdown | Zero error/fatal/assert/ensure/device-loss/write-failure signatures; no watchdog termination; final clean Active baseline; automation and process exit 0 |
| Warning accounting | 1,684 warning lines, **zero new signatures** relative to D01-42; details below |
| False-success gates | [17 tests passed](D01-043-verifier-tests.log), including mutated real smoke telemetry; [19 predecessor verifier tests passed](D01-043-predecessor-verifier-tests.log) |
| Ordinary D01-39 regression | [Two fresh headless processes passed](D01-043-predecessor-regression/20260905T090646.726484Z-nullrhi-ecb0d619/validation.json) on the same C++ build |
| Preservation | [Original core and single-run entrypoint preserved](D01-043-preservation.json); source/content/build and protected 03/04/PRODUCTION hashes unchanged throughout qualification |

[Full qualification manifest](D01-043-runs/20260905T090626.266544Z/validation.json) includes exact commands, tested file hashes, original telemetry, process monitor and both runtime logs. [Task evidence index](D01-043-validation.json) binds the editable outputs, build, retained attempts and checks. The [two-cycle smoke](D01-043-runs/20260905T090359.802435Z/validation.json) passed for 22.191 seconds and is explicitly SMOKE_ONLY; it was then independently rechecked by the stronger final verifier. Both original runtime scenarios passed, and no attempts were discarded. A later evidence-digest check detected delayed stdout finalization; the correction is recorded below.

The renderer log confirms actual Vulkan device creation; the mixer log confirms the NonRealtime platform API and initialized output buffers. The soak uses the same real software mixer as D01-42, without physical-speaker measurement. No gameplay classes, maps or content assets changed. Useful specialized routing was checked with `biella resource route stability-soak-qualification`; no provider matched, so local Unreal supplied the actual qualification.

## Evidence finalization correction

Fresh digest readback found that the full-run stdout grew by 770 bytes after the original runner had hashed it. The original 3,922,041-byte prefix still matches its recorded SHA-256 exactly; telemetry, process monitor and tested gameplay/build/content are unchanged. The appended text is the detached UnrealTraceServer daemon’s setup, missing optional settings-file notice, no-sponsor termination and normal shutdown. The original manifest is retained, and [log finalization evidence](D01-043-log-finalization.json) records the immutable prefix, exact trailer and final file identities. Full-capture semantic validation and final-log classification were repeated successfully.

The runner now waits, after closing its own output handle, for all writable `/proc` descriptors referring to the task log’s exact device/inode to close. This has a 45-second bound and does not terminate the trace service. An actual detached late-writer regression and an unresolved-writer timeout regression both pass, alongside the earlier gates: [19 final tests](D01-043-log-finalization-tests.log). The 15-minute gameplay workload remains valid; [a fresh two-cycle runtime passed with the corrected runner](D01-043-runs/20260905T092755.495920Z/validation.json). It observed the trace daemon’s two inherited writable descriptors, waited 2.794 seconds for closure, and its final stdout digest remained exact on subsequent readback. Original qualified [runner](D01-043-tested-runner.py) and [test](D01-043-tested-verifier-tests.py) bytes are retained as evidence snapshots, and the task index distinguishes them from the final tooling. The original process-group exit check did not establish detached-daemon closure. The corrected runner observes inherited-writer closure before recording the final stdout digest.

## Existing diagnostics and qualification limit

The 1,684 warning lines comprise 21 editor widget-factory warnings, one `r.MotionVectorSimulation` warning, 832 direct Recast/Crowd warnings across 208 map-load contexts, 828 copies of those warnings in Unreal’s automation report, and two shutdown `Found 1 unfreed allocations!` messages. Each signature already exists in D01-42’s qualified log. Map-load warnings scale exactly with reloads: two registration warnings, one removal warning and one crowd-manager warning per load. Their original text and exact counts are retained in the full manifest. This pass establishes sustained runnable behavior with these disclosed diagnostics; it does **not** claim warning-free operation or absence of memory leaks. Native performance/resource measurement and lifecycle/GC/spawn cleanup remain the distinct D01-44 and D01-45 task boundaries.

## Qualification design

The production task requires sustained clean runtime and prescribes no numeric duration. This bounded first-slice qualification selects at least 900 seconds of continuous workload and at least 20 complete gameplay cycles in one Unreal process and one GameInstance. Time starts at the first clean Active baseline, after startup/loading. Completion waits for a final fully reconstructed Active baseline.

The test composes the existing D01-39 deterministic scenario without changing gameplay code: possessed Enhanced Input movement and firing, actual collision/damage, objective Success, bound R restart, autonomous infected melee Failure, and another bound R restart. All seven checkpoints and every normalized semantic event must match D01-42’s qualified predecessor trace. Between cycles the fixture releases its AI tick hooks for at least five wall seconds; actual actor displacement, simulation progression and autonomous combat must occur before the next reload.

The workload uses the existing Linux development host, Vulkan 1280×720, fixed 1/60 simulation, and Unreal’s actual AudioMixer with NonRealtimeAudioRenderer. Frame counters and one-second runtime heartbeats establish liveness; finite pawn/camera transforms, exact game actor membership, ready feedback assets, and bounded active audio/VFX are checked throughout. A separate process-group monitor records the Unreal PID/start identity, telemetry progression and exit. A 30-second telemetry watchdog retains process/wait-channel diagnostics before terminating only its own process group. Runtime errors, assertions, ensures, device loss, incomplete telemetry and new warning signatures fail qualification.

A 15-minute pass is bounded development-host stability evidence. It does not establish native FPS/resource budgets, absence of accumulating leaks, Windows/package qualification, representative production content scale, final art acceptance, or manual play acceptance. Those claims are outside D01-43. Existing Recast/Crowd/editor warnings and two Vulkan shutdown allocation diagnostics are preserved and compared by exact signature, never described as warning-free.

## Editable outputs and reproduction

- `Source/BiellaGames/Private/Tests/BiellaDeterministicPlaytest.cpp`: test-only soak composition and runtime checks; original single-run entrypoint preserved.
- `tests/run_d01_043.py`: unique attempts, exact source/content/build/protected hashes, one-process launch, watchdog and exit evidence.
- `tests/verify_d01_043.py`: validates original session/sequence/clocks before deriving per-cycle slices for the unmodified D01-39 verifier; compares every normalized event to retained predecessor evidence.
- `tests/test_d01_043.py`: adversarial false-success gates.

Build the existing BiellaGamesEditor Linux Development target with UE 5.8.2, then run:

```sh
python3 tests/run_d01_043.py --seconds 900 --cycles 20
```

Short runs are explicitly labeled SMOKE_ONLY and cannot satisfy the qualification floor. All failed attempts remain under `Build/Demo01/D01-043-runs/`.
