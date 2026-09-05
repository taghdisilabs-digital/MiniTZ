# D01-029 rival navigation and combat positioning evidence

Observed 2026-09-05 against canonical `patrickminitz-web/biella-engine`,
`projects/biella-games`. Completion authority remains `docs/PRODUCTION.md`.
Source/config/map and runtime module SHA-256 identities are recorded in
`D01-029-validation.json`; base commit is
`b4bf397d9fa7c8bce1c9b045c9567264fd23cfa5`.

The preserved implementation only swept directly toward the target and held
inside 600 cm. Its old log showed hold without movement. Current work adds
dynamic Unreal Recast paths derived from the arena's real collision, a bounded
search for reachable positions around the selected target, and swept path
following. Advance/retreat use hysteresis around the preferred 600 cm range;
hold faces the target, and lost line of sight causes repositioning. Invalidated
or obstructed paths retry at 0.5 second intervals without teleporting. Target
loss and defeat stop movement. Rival capsule/body navigation relevance is
disabled to prevent self-invalidation; authoritative pawn collision remains on.

The arena now provides runtime navigation bounds and an explicit 48 cm radius /
176 cm height supported agent. The rival spawn is raised 2 cm to clear the
existing floor. Original rival target selection and `FireAtTarget` are
preserved; the weapon function was compared byte-for-byte to the base commit.

## Observed runtime assertions

The editable test is
`Source/BiellaGames/Private/Tests/BiellaRivalNavigationTest.cpp`, automation name
`BiellaGames.Demo01.RivalNavigation`. It runs normal actor/world ticks in a
dedicated canonical-map game process. Only fixture setup and explicit
target/obstruction changes are scripted; the rival moves autonomously through
the production implementation. Fixture weapon damage is zero to keep the
stationary target alive. No map assets are modified by the test.

| Scenario | Observed result |
|---|---|
| Central cover detour | Rival moved from (1000,0,2) to (-456.46,298.19,10), followed a multi-corner path, and held at 620.0 cm. |
| Combat hold | Position remained stable for one second, with target-facing yaw and valid range. |
| Close target | Retreat increased separation from 180 cm to 580.1 cm. |
| New route obstruction | After movement began, a collision block was inserted ahead; path revision increased and the rival bypassed it, reaching 620.0 cm. |
| Occluded firing position | New cover broke sight; rival entered Reposition, moved over 75 cm, restored sight, and held at 580.7 cm. |
| Sealed route | Rival remained outside the arena-spanning wall; failed planning was observable and limited to at most eight retries in three seconds (six observed). |
| Reopened route | Destroying that wall allowed a new complete path and arrival at 620.0 cm. |
| Target loss / defeat | Destroying the target or defeating the moving rival stopped navigation. |
| Continuous physical checks | Every sampled phase checked speed bounds, capsule clearance, and floor support; no teleportation or geometry penetration was observed. |

`D01-029-acceptance-runtime.log` records all nine PASS phases, Unreal
`Result={Success}`, `GIsCriticalError=0`, and `TEST COMPLETE. EXIT CODE: 0`.
The process also exited 0. `D01-029-editor-acceptance.log` records a successful
UE 5.8.2 Editor build including the test source.

`D01-029-smoke.log` records a separate 12-second canonical encounter with normal
weapon damage: the rival retreated from 460.4 cm to 580.1 cm, held, inflicted
14 damage per hit, and selected the second infected after the first was
defeated. This process exited 0. Neither accepted run contains a fatal,
assertion failure, ensure, unhandled exception, or segmentation fault.

## Reproduction

From the Project directory, ensure the non-root `unreal` account can read source
and write generated `Binaries`, `Intermediate`, `Saved`, and `DerivedDataCache`.

```bash
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/Linux/Build.sh BiellaGamesEditor Linux Development -Project=/root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject -WaitMutex -NoUBA -NoHotReloadFromIDE -NoUBTMakefiles -gather
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor-Cmd /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -nullrhi -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread '-ExecCmds=Automation RunTests BiellaGames.Demo01.RivalNavigation; SoftQuit' -seconds=190
python3 tests/verify_demo01.py
```

`SoftQuit` lets automation determine the exit status and shut down cleanly.
UE's generic `-TestExit` phrase hook force-exits on this host and should not be
used as the acceptance exit-status mechanism.

This qualifies navigation and positioning in the current flat Demo arena using
real headless Unreal simulation/collision. It does not qualify visual quality,
Win64 packaging, sloped/streamed-world traversal, or the later weapon task.
The preserved map's old incompatible navmesh emits a startup warning and is
discarded by Unreal; the active dynamically generated mesh was measured at
48/176 and passed the runtime assertions. Existing editor-only startup warnings
do not appear as automation test errors. D01-001..028 remain complete, and
D01-030 remains pending.

Resource routing was consulted with `biella resource route game-ai-navigation`;
no matching configured provider was returned. Local Unreal/Recast and
deterministic acceptance were sufficient; no external generation was needed.
