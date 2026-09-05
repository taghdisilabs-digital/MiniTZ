# D01-037 — gameplay HUD core

## Implementation

- Added `UBiellaGameplayHUD`, a native UMG widget built from editable C++ source.
- Added objective/progress, player health bar and value, ammunition, threat countdown, phase status, and crosshair presentation.
- Bound every displayed value to the live player pawn, replicated `ABiellaGamesGameState`, or replicated `ABiellaDemoObjectiveManager`; no hand-authored gameplay values are used after construction.
- The local player controller owns the widget and refreshes it from the controller game tick as well as the widget tick, so headless and rendered runtime paths observe the same state updates.
- Added `BiellaGames.Demo01.GameplayHUD` automation coverage for baseline binding and live damage/fire/defeat-driven UI changes.
- Renamed three pre-existing unity-test helper functions to remove a clean-build symbol collision exposed when the new HUD source invalidated the module unity translation unit. Their test behavior is unchanged.

The countdown is the authoritative remaining infected-target count (`InfectedRemaining`), which is the approved Demo 01 mission count state; no unapproved time limit was invented.

## Validation

| Check | Result |
| --- | --- |
| UE 5.8.2 Editor build | PASS — canonical unity build completed and linked `libUnrealEditor-BiellaGames.so` |
| Headless live HUD automation | PASS — `BiellaGames.Demo01.GameplayHUD`, exit code `0` |
| Rendered Vulkan HUD automation | PASS — `BiellaGames.Demo01.GameplayHUD`, exit code `0`, 1280×720 offscreen runtime |
| State transition evidence | PASS — baseline `100/100`, ammo `60`, countdown `2`, objective `0/2`; after real damage/fire/defeat: `75/100`, ammo `59`, countdown `1`, objective `1/2` |
| D01-036 restart regression | PASS — Failure → restart → clean Active match, `0/2`, two infected, player health `100` |
| Demo structure verifier | PASS — `completed=36/50`, current task remains `D01-037` |

## Commands

```text
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/Linux/Build.sh BiellaGamesEditor Linux Development -Project=/root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject -WaitMutex -NoUBA -NoHotReloadFromIDE -NoUBTMakefiles -gather
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor-Cmd /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -nullrhi -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread '-ExecCmds=Automation RunTests BiellaGames.Demo01.GameplayHUD; SoftQuit' -seconds=75
xvfb-run -a runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -RenderOffscreen -vulkan -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread -windowed -ResX=1280 -ResY=720 '-ExecCmds=Automation RunTests BiellaGames.Demo01.GameplayHUD; SoftQuit' -seconds=90
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor-Cmd /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -nullrhi -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread '-ExecCmds=Automation RunTests BiellaGames.Demo01.RestartReset; SoftQuit' -seconds=75
python3 tests/verify_demo01.py
```

Evidence logs and hashes are recorded in `D01-037-validation.json`.
