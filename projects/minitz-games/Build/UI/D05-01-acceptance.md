# D05-01 UI, settings, localization, and accessibility acceptance

Observed 2026-09-08 against the canonical Biella Games project. Completion
authority remains `docs/PRODUCTION.md`; this evidence record does not change
task or Project metadata.

## Editable implementation

The task implementation is native Unreal C++ and an editable runtime text
catalog:

- `UBiellaGameUserSettings` owns bounded X/Y look sensitivity, invert-Y,
  motion-blur comfort, and HUD readability scale in `GameUserSettings` scope.
- `UBiellaSettingsWidget` creates the player-facing pause/settings surface;
  every control is wired to the corresponding setting and the Apply & Resume
  action saves and applies it.
- `ABiellaGamesPlayerController` owns Escape pause/settings transitions,
  cursor and input-mode ownership, idempotent input reset, and stale transient
  input clearing on resume.
- `UBiellaGameplayHUD` refreshes from authoritative player and game-state
  values, including health, ammo, objective progress, threat count, phase and
  terminal state.
- `Content/UI/ST_BiellaRuntime.json` contains the English source dataset and
  an explicitly labeled `pseudo_test` dataset. The latter is validation data,
  not a claimed shipping language; missing keys and datasets return diagnostic
  markers.

## Build and live runtime proof

The affected editor target was rebuilt with Unreal Engine 5.8.2:

```text
/opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/Linux/Build.sh BiellaGamesEditor Linux Development -Project=/root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject -WaitMutex -NoUBA -NoHotReloadFromIDE -NoUBTMakefiles -gather
```

Observed exit code `0`, including `Result: Succeeded` after compiling and
linking `BiellaGamesPlayerController.cpp`.

The acceptance automation was run in the real game world with headless
Unreal/null RHI (the process was non-root only for the host display/runtime
constraint):

```text
env XDG_CONFIG_HOME=/home/unreal/biella-d05-runtime-05/.config XDG_CACHE_HOME=/home/unreal/biella-d05-runtime-05/.cache XDG_DATA_HOME=/home/unreal/biella-d05-runtime-05/.local/share XDG_STATE_HOME=/home/unreal/biella-d05-runtime-05/.local/state DOTNET_CLI_HOME=/home/unreal/biella-d05-runtime-05 UE-LocalDataCachePath=/home/unreal/biella-d05-runtime-05/ddc setpriv --reuid=1001 --regid=0 --groups=0 -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor-Cmd /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -nullrhi -userdir=/home/unreal/biella-d05-runtime-05/ -DDC='(Local)' -unattended -nosound -nosplash -NoAsyncLoadingThread -stdout -FullStdOutLogOutput -AbsLog=/root/biella/repos/biella-engine/projects/biella-games/Build/UI/D05-01-runtime-05/runtime.log -BiellaD05Output=/root/biella/repos/biella-engine/projects/biella-games/Build/UI/D05-01-runtime-05 -ExecCmds="Automation RunTests BiellaGames.D05.UISettingsLocalizationAccessibility; SoftQuit"
```

The process exited `0`; `result.json` is exactly:

```json
{"task_id":"D05-01","success":true,"source":"live_runtime","reason":""}
```

Final evidence files and SHA-256 identities:

```text
fc836d84f8112994162678423e88a2147835367e1aff6bbd2f085cf72380243a  Build/UI/D05-01-runtime-05/result.json
12e239c66f0a83ce2223f54bb3d024c35e193fd301c54972feeebe958ff0aa0c  Build/UI/D05-01-runtime-05/runtime.log
```

## Observed task criteria

The final Unreal log records all required live assertions:

| Criterion | Observed proof |
|---|---|
| Structured localization and negative cases | `D05_D01_TEST PASS phase=localization source_locale=en test_dataset=pseudo_test english_len=62 pseudo_len=77 missing_key=[MISSING:missing_d05_key] missing_dataset=[MISSING_DATASET:missing_dataset]` |
| Authoritative runtime HUD | `D05_D01_TEST PASS phase=hud authoritative=true health=100.0 ammo=60 remaining=2 objective_progress=0/2 mode=1` |
| Sensitivity and invert-Y live effect | `D05_D01_TEST PASS phase=sensitivity yaw_low=0.50 yaw_high=1.50 pitch_normal_delta=0.80 pitch_inverted_delta=-0.80` |
| Actual renderer motion-blur setting | `D05_D01_TEST PASS phase=motion_blur disabled_quality=0 disabled_default=0 enabled_quality=4 enabled_default=1` |
| Live readability/accessibility effect | `D05_D01_TEST PASS phase=readability accessibility=HUDScale baseline=1.00 enabled=1.35 live_gameplay=true` |
| Settings reconstruction and persistence | `D05_D01_TEST PASS phase=persistence scope=GameUserSettings reconstruction=new_object_load sensitivity_x=1.35 sensitivity_y=1.25 invert_y=true motion_blur=true hud_scale=1.25` |
| Pause/settings ownership and resume | `D05_SIGNAL SESSION_TRANSITION from=Gameplay to=PauseSettings paused=true cursor=true input=ui focus=settings`, followed by `D05_SIGNAL SESSION_TRANSITION from=PauseSettings to=Gameplay paused=false cursor=false input=game_only stale_input=cleared` and `D05_D01_TEST PASS phase=pause_settings input=Escape paused=true cursor=true ui=owned resume=gameplay stale_movement_cleared=true repeated_transitions=idempotent` |

The runtime also records `D05_D01_TEST COMPLETE source=live_runtime
criteria=hud_settings_localization_accessibility_pause` and Unreal automation
reports `Result={Success}` with `**** TEST COMPLETE. EXIT CODE: 0 ****`.
