# D01-036 — deterministic restart/reset path

## Implementation

- `ABiellaGamesGameModeBase::RequestRestart()` is authoritative, single-flight, records the restart in the persistent game instance, and reloads the active authored map.
- A new map instance reconstructs the run-local player, rival, infected roster, objective manager, arena pressure and replicated match state from their authored starting conditions.
- `BiellaGames.Demo01.RestartReset` forces a real player Failure state, requests restart, and verifies the reconstructed match is Active with objective progress `0/2`, two remaining infected, a live player at full health, a live rival, and zero arena pressure.

## Validation

| Check | Result |
| --- | --- |
| UE 5.8.2 Editor build | PASS — `BiellaGamesEditor` compiled and linked |
| Live runtime automation | PASS — `BiellaGames.Demo01.RestartReset`, exit code `0` |
| Runtime phases | `terminal_failure` → `restart_request` → `clean_match` |
| Final clean match | `restart_count=2`, `phase=Active`, `objective=Demo01ClearArena`, `target=2`, `progress=0`, `infected_remaining=2`, `player_health=100.0`, `pressure=0.0`, server authority |
| Structural regression | PASS — `DEMO01_STRUCTURE_PASS completed=35/50 current=D01-036` |

Commands:

```text
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/Linux/Build.sh BiellaGamesEditor Linux Development -Project=/root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject -WaitMutex -NoUBA -NoHotReloadFromIDE -NoUBTMakefiles -gather
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor-Cmd /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -nullrhi -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread '-ExecCmds=Automation RunTests BiellaGames.Demo01.RestartReset; SoftQuit' -seconds=60
python3 tests/verify_d01_036.py Build/Demo01/D01-036-restart.log
python3 tests/verify_demo01.py
```

Evidence:

- `Build/Demo01/D01-036-restart.log`
- `Build/Demo01/D01-036-validation.json`
