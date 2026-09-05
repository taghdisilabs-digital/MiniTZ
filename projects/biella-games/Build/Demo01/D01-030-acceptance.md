# D01-030 rival weapon use and damage response evidence

Observed 2026-09-05 against canonical `patrickminitz-web/biella-engine`,
`projects/biella-games`, from base commit
`62d5315748b41b6655590ae7a5365f1ccec5ebd2`.
Completion authority remains `docs/PRODUCTION.md`. Exact source, map, module,
and evidence SHA-256 identities are in `D01-030-validation.json`.

## Implementation

The preserved rival already selected targets, fired on a cooldown, and inherited
health, hit flash and defeat. Its trace accepted a miss as permission to damage,
while the shared Pawn collision profile ignored Visibility. Public firing also
lacked its own range and friendly/self-target checks. That implementation did
not satisfy current weapon collision acceptance.

The rival now carries an editable equipped mesh using the existing Demo cube
asset baseline. It aims the weapon at the selected target and resolves actual
capsule hits from its muzzle. Shared pawn capsules block Visibility, so targets
and intervening pawns participate in the shot query. Barrel clearance prevents
firing through nearby cover; a target intersecting the barrel segment receives
that first impact, including point-blank shots. Missing collision, obstructions,
invalid/self/friendly/defeated targets, targets outside 950 cm, active cooldown,
and invalid weapon parameters reject firing without damage.

The existing 14 damage and 0.9-second cooldown remain. Successful shots drive a
short weapon-material flash and report owner, target, muzzle, impact, damage and
simulation time. Incoming player and engine damage reuse the shared authoritative
health and hit-reaction path. Defeat dispatch is virtual so the rival immediately
clears its target/path, stops movement, enters Idle and hides its weapon alongside
the existing body/collision cleanup. Existing navigation and target selection
remain in place.

## Observed validation

`Source/BiellaGames/Private/Tests/BiellaRivalCombatTest.cpp` defines live Unreal
automation `BiellaGames.Demo01.RivalCombat`. It starts in the canonical map,
uses real collision, materials, player weapon calls, engine damage and actor/world
ticks, and isolates only fixture creation and scenario changes. Initial firing
gates use disabled rival ticks; cadence, recovery and navigation/death use normal
ticks. It never substitutes a simulated damage implementation or edits the map.

| Runtime assertion | Result at both 30 and 120 FPS caps |
|---|---|
| Target and parameter gates | Null, self, same-team, defeated/destroyed targets and non-positive/non-finite weapon settings rejected. |
| Real hit collision | Cover, intervening pawn, missing target collision and cover behind the muzzle prevented damage. |
| Range and close contact | 951 cm rejected; 950 cm and 100 cm each produced a real 14-damage hit. |
| Autonomous cadence | Target health 100 -> 86 -> 72 -> 58; both successive intervals measured 0.900 seconds; same-frame duplicate fire rejected. |
| Event feedback | Equipped weapon material and victim hit color changed on shots, then returned to their resting colors between shots. |
| Incoming player weapon | Real player `FireWeaponAt` consumed one round and changed rival health 100 -> 66 with hit flash. |
| Engine damage and recovery | Zero/negative damage ignored; 27 damage changed 66 -> 39; rival team color restored. |
| Defeat consequence | Fatal damage while navigating applied only the remaining 39 health, hid body/weapon, disabled collision, cleared target/path and stopped motion immediately. |
| After defeat | Repeated damage applied zero; live in-range target remained unharmed during direct fire attempts after cooldown; no movement or target reacquisition for over 1.2 seconds. |

Both accepted combat logs also show the normal canonical encounter before fixture
setup: the rival defeated the first infected through `rival_fire` and selected
the second. This is supporting task-level encounter evidence; it does not close
D01-031's separate shared-interaction acceptance.

`D01-030-navigation-regression.log` passes all nine existing D01-029 phases:
detour, hold, retreat, dynamic obstruction, occluded combat position, bounded
failure, reopening, target loss and defeat stop. Its continuous collision,
floor support and speed checks also passed. This regression used the final
gameplay source before the new combat-test instrumentation was added; its
separate module identity is retained in the validation JSON.

The three accepted runtime processes exited 0 and report Unreal automation
Success, `GIsCriticalError=0`, and `TEST COMPLETE. EXIT CODE: 0`, without fatal,
assertion, ensure or automation errors. `D01-030-editor.log` records the gameplay
source build; `D01-030-editor-acceptance.log` records the final build including
the combat test. Both succeeded. Earlier build/test logs are retained as
diagnostics: the new test initially needed read permission for the non-root
`unreal` build account, and its post-defeat assertion was strengthened after an
initial passing run. Final source and accepted log identities are explicit in
the JSON.

## Reproduction

From the Project directory, provide the `unreal` account read access to source
and write access to generated `Binaries`, `Intermediate`, `Saved` and
`DerivedDataCache`. The new test source uses normal 0644 permissions.

```bash
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/Linux/Build.sh BiellaGamesEditor Linux Development -Project=/root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject -WaitMutex -NoUBA -NoHotReloadFromIDE -NoUBTMakefiles -gather
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor-Cmd /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -nullrhi -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread '-ExecCmds=t.MaxFPS 30,Automation RunTests BiellaGames.Demo01.RivalCombat; SoftQuit' -seconds=130
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor-Cmd /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -nullrhi -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread '-ExecCmds=t.MaxFPS 120,Automation RunTests BiellaGames.Demo01.RivalCombat; SoftQuit' -seconds=130
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor-Cmd /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -nullrhi -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread '-ExecCmds=Automation RunTests BiellaGames.Demo01.RivalNavigation; SoftQuit' -seconds=190
python3 tests/verify_demo01.py
```

Resource routing was consulted for `game-code` and `coding`; neither returned a
configured provider. Local Unreal and deterministic validation were sufficient.

This evidence qualifies real headless gameplay simulation, hit collision and
runtime material/visibility state. It does not claim rendered visual quality,
native rendered FPS, animation/audio polish or Win64 package qualification.
D01-001..029 stay complete. D01-031 and all later tasks remain pending, and the
owner-stopped feeder is unchanged.
