# D01-035 — failure/death state

Task scope: an actual player health-zero transition to an authoritative Demo
01 failure state, with terminal objective behavior after death.

## Runtime implementation

`ABiellaGamesCharacter::Defeat` continues to perform the existing pawn death
cleanup, then notifies the authoritative `ABiellaGamesGameModeBase`.
`HandlePlayerDefeat` is idempotent, marks the replicated GameState
`bPlayerAlive` false, and transitions the phase to `Failure` with the
objective text `You were defeated.`. The objective manager refuses to promote
an active clear-arena objective to success once the GameState is in failure or
the player is no longer alive.

## Acceptance evidence

Observed 2026-09-05 on Unreal Engine 5.8.2 Linux Editor `-game` using the
canonical `BiellaGameplayMap` and the compiled `BiellaGamesEditor` target.

| Check | Result |
|---|---|
| Editor build | `Succeeded`, process exit 0 |
| Failure automation | `BiellaGames.Demo01.FailureState`, `Result={Success}`, process exit 0 |
| Failure phases | health zero → failure |
| Terminal state | player health `0.0`, defeated, `bPlayerAlive=false`, phase `Failure` |
| Objective guard | objective did not succeed while infected remained; duplicate post-death damage applied `0.0` |
| D01-034 regression | `BiellaGames.Demo01.ObjectiveManager`, activation → progress → success, process exit 0 |
| Log verifier | `tests/verify_d01_035.py` PASS |
| Structural regression | `tests/verify_demo01.py` PASS, `completed=34/50 current=D01-035` |

The live log records `D01_SIGNAL DEFEAT`,
`D01_SIGNAL PLAYER_FAILURE ... phase=Failure ... authority=server`, and
`D01_035_TEST COMPLETE ... objective_success=false authority=server`.
The test freezes the existing AI encounter after test startup, then drives
the production `ApplyDemoDamage` path; it does not set health, phase or
failure fields directly.

## Reproduction

Run from the Biella Games Project directory:

```bash
/opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/Linux/Build.sh BiellaGamesEditor Linux Development /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject -waitmutex
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -nullrhi -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread '-ExecCmds=Automation RunTests BiellaGames.Demo01.FailureState; SoftQuit' -seconds=40
python3 tests/verify_d01_035.py Build/Demo01/D01-035-failure.log
```

This task does not add deterministic restart/reset, HUD, overlays, package
qualification, multiplayer replication or Engine P4-06 work. The protected
authority records and `docs/PRODUCTION.md` task metadata remain unchanged;
the Auto Feeder owns the canonical status transition and publication.
