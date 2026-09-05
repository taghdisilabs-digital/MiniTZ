# D01-034 — objective manager and success condition

Task scope: executable Demo 01 objective state and the clear-arena success
condition. The objective is authoritative on the server and is exposed through
the runtime manager plus the replicated Demo 01 GameState.

## Runtime implementation

`ABiellaDemoObjectiveManager` owns the versioned `Demo01ClearArena` objective.
It registers every spawned `ABiellaInfected`, continuously derives remaining
and defeated counts from real pawn state, mirrors those counts to
`ABiellaGamesGameState`, and transitions the objective from `Active` to
`Succeeded` only when the registered infected set reaches zero remaining.
The GameState phase and objective text transition to `Success` / `Arena
cleared.` at the same authoritative event. Objective identity, version, state,
target count, progress and status are replicated for later runtime UI
consumers.

The manager is spawned by `ABiellaGamesGameModeBase` after the Demo 01 actors
are created, so activation observes the actual encounter rather than a
hard-coded display count. Pressure-spawned infected are registered as they
enter the world while the objective remains active.

## Acceptance evidence

Observed 2026-09-05 on Unreal Engine 5.8.2 Linux Editor `-game` using the
canonical `BiellaGameplayMap` and the compiled `BiellaGamesEditor` target.

| Check | Result |
|---|---|
| Editor build | `Succeeded`, process exit 0 |
| Objective automation | `BiellaGames.Demo01.ObjectiveManager`, `Result={Success}`, process exit 0 |
| Objective phases | activation → progress `1/2` → success `2/2` |
| Success condition | `infected_remaining_zero`, authoritative server transition |
| Log verifier | `tests/verify_d01_034.py` PASS |
| Structural regression | `tests/verify_demo01.py` PASS, `completed=33/50 current=D01-034` |

The live log records `D01_SIGNAL OBJECTIVE_ACTIVATED`, real infected defeat
damage/defeat events, `D01_SIGNAL OBJECTIVE_SUCCESS`, GameState phase `Success`,
and `D01_034_TEST COMPLETE ... authority=server`. The test freezes the live
encounter after observing its real initial state, then exercises progress and
success through the production pawn damage/defeat API; it does not set the
objective counters directly.

## Reproduction

```bash
/opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/Linux/Build.sh BiellaGamesEditor Linux Development /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject -waitmutex
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -nullrhi -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread '-ExecCmds=Automation RunTests BiellaGames.Demo01.ObjectiveManager; SoftQuit' -seconds=40
python3 tests/verify_d01_034.py Build/Demo01/D01-034-objective.log
```

This task does not add failure/death, restart/reset, HUD, overlays, package
qualification, or Engine P4-06 work. The protected authority records and
`docs/PRODUCTION.md` task metadata remain unchanged; the Auto Feeder owns the
canonical status transition and publication.
