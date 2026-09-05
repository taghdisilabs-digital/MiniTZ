# D02-01 — Open-world streaming and continuity

Task-derived implementation and runtime validation: **PASS**. This report is
D02-01 evidence, not a canonical task-status transition. No later task was
executed. The starting source was `361adc7e8486d493085372d1d1d22568c2423c9b` on
canonical `main`; the starting worktree was clean. The exact tested working
bytes are identified in the validation reports, independent of concurrent
controller, policy and website commits.

## Editable result

`/Game/Maps/BiellaOpenWorldMap` adds six connected native World Partition street
sections, an indoor route and a ramp/terrace transition. Collision, dynamic
Recast navigation, runtime Data Layer and native HLOD are real Unreal assets.
Fresh saved-asset readback verifies 64 authored external actors, 13 native HLOD
actors and 58 HLOD mesh instances. D02 material instancing and indoor/outdoor
lighting are verified without changing the D01 material.

`BiellaWorldContinuity.h/.cpp` implements player streaming sources, safe
traversal and asynchronous relocation, a match-local stable-identity state
store, streamed actor reconstruction, and support-dependent dormancy for the
persistent mission encounter. Health, transforms, defeat tombstones, pressure,
ammo and mission progress survive distant unload and return. Restoration does
not duplicate actors, resurrect defeated actors or award objectives twice.
The streamed encounter remains bounded to its authored residency area.

The map, external actors/objects, materials and layers remain editable at their
canonical Project paths. `Content/Python/author_open_world.py` preserves actor
identities on rerun and supports fresh read-only verification. Native authoring
mutations are isolated behind editor guards in `BiellaWorldAuthoring.h/.cpp`.
`docs/WORLD_STREAMING.md` documents interactive launch and reconstruction rules.

## Final validation

| Check | Observed result | Evidence below `Build/OpenWorld/` |
| --- | --- | --- |
| UE 5.8.2 Development Editor build | PASS, actual exit 0 | `D02-01-editor-build-r16.log` |
| Non-editor Game module compilation | PASS, actual compiler exit 0 | `D02-01-game-module-compile.json`, `D02-01-game-module-compile.log` |
| Saved map/native HLOD readback | PASS, 64 authored / 13 HLOD actors / 58 instances | `D02-01-map-readback.json`, `D02-01-lighting-readback.log` |
| Live Vulkan streaming and continuity | PASS, actual exit 0, finalized logs | `runtime-07/validation.json` |
| Independent evidence replay | PASS against the canonical repository copy | `D02-01-independent-verification.json` |
| Actual capture inspection | PASS, six decoded 1280×720 PNGs | `D02-01-visual-review.json`, `runtime-07/captures/` |
| Shared D01 combat regression | PASS, 10 phases / 20 damage events / all six directions / four defeats | `D02-01-shared-regression-final/validation.json` |
| Deterministic D01 regression | PASS, two fresh processes with identical semantic traces | `D02-01-demo-regression-final/20260905T222959.460315Z-nullrhi-31272583/validation.json` |
| Negative evidence checks | PASS, eight controls/rejections | `D02-01-final-review-python-checks.json` |

The live scenario used Enhanced Input and ordinary variable wall time with
native asynchronous streaming, collision, navigation and rendering. It
traversed **779.53 m**, including indoor and elevated geometry, over **166.05 s**.
It observed **51 visible-cell loads, 39 unloads, 21 distinct cells and 32
navigation checks**. Three restorations, a native unload snapshot, zero
duplicate identities, defeat reconstruction, unsafe debug relocation recovery,
valid destination relocation, invalid-destination timeout and retry passed.
Previously active actor/movement ticks resumed correctly after dormancy,
including repeated transition calls. Initial capture waited for the actual
shader compiler to settle; that wait remained in the measurement.

The raw frame record has 12,362 rows / 12,361 intervals. Wall frame time was
p50 **13.73 ms**, p95 **15.71 ms**, p99 **16.86 ms**, maximum **676.52 ms**.
Peak process resident memory was **2,995,851,264 bytes**; independent `/proc`
sampling reported 2,925,252 KiB peak RSS. The host was Linux Vulkan at 1280×720,
NVIDIA L40S, driver 580.178.04, AMD EPYC 9124, Ubuntu 24.04.4. No target-FPS
qualification is inferred from these development-host measurements. The
largest hitch is retained, not filtered out.

`runtime-07/` contains the exact logs, event record, raw frame CSV, process-memory
samples, result JSON and six captures copied byte-for-byte from the observable
artifact path `/root/biella/artifacts/games/D02-01/runtime-07/`. The reports
identify the tested source, content, editor binary/module and protected metadata
before and after execution. Combat regression and two deterministic processes
used those same final implementation bytes. The negative checks reject material
fallbacks, missing shader-readiness evidence, falsified frame statistics,
player-state discontinuity and missing reconstruction evidence.

## Reproduction

From the Project root:

```sh
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/Linux/Build.sh BiellaGamesEditor Linux Development "$PWD/BiellaGames.uproject" -WaitMutex -NoUBA -NoHotReloadFromIDE
python3 tests/run_d02_01.py --output /root/biella/artifacts/games/D02-01/runtime-next
python3 tests/verify_d02_01.py Build/OpenWorld/runtime-07
python3 tests/run_d02_01_shared_regression.py --output Build/OpenWorld/shared-regression-next
python3 tests/run_d01_039.py --output Build/OpenWorld/demo-regression-next --renderer nullrhi --runs 2
```

Use fresh output directories for new runtime attempts. Exact native authoring,
HLOD and readback commands remain in their retained logs. The saved map may be
opened directly for normal interactive play without the automation fixture.

## Preserved scope and limitations

`D02-01-preservation.json` verifies byte-identical canonical `03`, `04` and
Project `PRODUCTION.md`, all previously tracked content/configuration and D01
evidence. Engine P4-06 remains `INCOMPLETE_DEFERRED`. Only the bounded shared
source integrations and new D02 implementation/assets/tests/evidence are staged.
Concurrent policy/controller/website work remains preserved.

This is a finite streaming blockout and a match-local state store. It does not
claim final city identity/art, disk saves, population migration, vehicles,
shipping platforms, or a new packaged release. The runtime fixture holds
opponent movement/attacks while retaining their real identities, collision,
health and gameplay integration; interactive play retains ordinary autonomy.
Captures remain `GENERATED_DRAFT` pending owner acceptance.

Earlier failed build, authoring and runtime attempts remain preserved. Native
Recast configuration/registration and an acyclic movement-tick dependency
resolved integration faults. Cosmetic mesh initialization now disables
navigation before assigning a mesh, preventing stale default-origin navigation
geometry; the original origin query and D01 regressions pass. Authoring reruns
preserved saved actor identities. Failed-attempt teardown faults are not counted
as successful evidence; final successful runtime processes exited normally.

An additional full non-editor Game relink was attempted, but is **not
qualified**. The installed engine lacks runtime precompiled manifests. A
reversible installed-marker relocation reached the existing source-build cache
and compiled the current game module, then exposed absent `mimalloc/static.c`,
absent `samplerate.h` and a permission-restricted engine SSEMathFun header. The
optional full-engine rebuild was stopped and the installed marker restored.
Validation was narrowed to the exact UBT-generated non-editor game module,
which compiled independently with exit 0. Compiler inputs and hashes are
retained under `game-module-inputs/`; the failed full-build logs are retained
separately. No old Game executable or D01 package is presented as a D02 build.
The accepted D02 gameplay proof is the successfully built Development Editor
running the real world through `-game`, as permitted by Project runtime
acceptance. New package qualification remains outside this task boundary.

The latest resume requires publication/readback at configured destinations.
The configured source destination is `origin/main` in
`patrickminitz-web/biella-engine`; exact commit/tree/file verification follows
the local task commit. This task changes no Drive-maintained authority record
and defines no new Drive destination. Canonical task advancement remains with
the Auto Feeder.
