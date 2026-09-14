# D01-031 — shared player/rival/infected interaction

Observed 2026-09-05 in canonical `patrickminitz-web/biella-engine`, Project
`projects/biella-games`, from base commit
`e893807d50108ab570163a7aa25417e302852461`.
Exact source, map, module and log hashes are in `D01-031-validation.json`.

## Task boundary and implementation

D01-030's evidence explicitly left shared-interaction acceptance open. D01-031
now supplies editable Unreal automation and live cross-actor state evidence for
Contracts 26 and 34 at the current three-actor Demo milestone.

The player and infected reused the existing shared health, team, hit flash and
defeat implementation, but player fire accepted an empty trace and infected
melee only checked distance. Player fire now requires an actual first collision
hit on a valid opposing actor. Infected melee also requires a real unobstructed
hit, rejects self/friendly/invalid targets and invalid attack parameters, and
uses the same 170 cm range as autonomous attack selection (the old direct-call
allowance was 212.5 cm). Damage values remain player 34, rival 14 and infected 12;
cooldowns remain 0.25, 0.9 and 0.85 seconds respectively.

Player and infected defeat now stop movement and their pending actions;
infected targeting clears immediately and the player's equipped weapon hides.
Shared damage rejects non-finite amounts and records source, source team, target
team and simulation time alongside its existing health/cause fields. Rival
navigation, weapon and damage-response source remains unchanged.

## Live acceptance

`Source/BiellaGames/Private/Tests/BiellaSharedInteractionTest.cpp` runs
`BiellaGames.Demo01.SharedInteraction` in the canonical `BiellaGameplayMap`.
It creates two bounded encounters using actual `ABiellaGamesCharacter`,
`ABiellaRival` and `ABiellaInfected` instances. The player is possessed by the
real local controller; action injection passes through Unreal Enhanced Input
and the pawn's bound movement/fire actions. AI runs on normal world ticks and
selects its own targets. Encounters never assign health, preferred targets,
damage, speed or cooldowns. Only the separate negative collision probes disable
AI ticks/change fixture properties. No map/content changes are needed.

Both final runs passed all ten phases, observed 20 source-attributed damage
events covering all six directed edges, and observed four combat defeats:

| Interaction | Observed state consequence in each run |
|---|---|
| Player → infected | Enhanced Input fire consumes ammo; encounter A infected 56 → 22; later player fire finishes encounter B infected. |
| Rival → infected | Autonomous firing reduces infected health and finishes encounter A infected at zero. |
| Infected → player | Autonomous chase/melee changes player 100 → 88, with further timed hits; retargeted infected repeats this in encounter B. |
| Rival → player | After infected death, rival selects player, damages 64 → 50 and eventually defeats player. |
| Infected → rival | Infected chooses the nearer rival with the player present, damages rival 100 → 88 and changes its runtime hit material. |
| Player → rival | Three input-driven shots change rival 88 → 54 → 20 → 0, immediately clearing its targeting/path and hiding its weapon. |

After the rival dies in encounter B, the infected independently retargets,
moves over 60 cm toward the player and produces a real melee hit and hit flash.
After the player kills that infected, defeated AI stays stationary, cannot
attack and has no target for at least 1.2 seconds. Encounter A also verifies
that a defeated player rejects movement, jump and fire input while the live
rival remains available as a target. Every encounter sample checks finite,
bounded health, defeat/body/collision consistency and absence of intersecting
live pawn capsules. Player movement from Enhanced Input exceeds 20 cm.

Negative probes reject missing player/melee target collision, intervening world
cover, self/same-team attacks, melee beyond 170 cm, non-finite shared damage and
non-finite player damage. A second melee request in the first hit's frame is
rejected. These probes preserve health and player ammunition.

| Final live run | Result | Minimum observed infected / rival / player repeat intervals |
|---|---|---|
| `D01-031-shared-30fps.log` | 10 phases PASS; process 0; Unreal Success | 0.866 / 0.900 / 0.366 seconds |
| `D01-031-shared-120fps.log` | 10 phases PASS; process 0; Unreal Success | 0.850 / 0.900 / 0.350 seconds |

`tests/verify_d01_031.py` excludes startup AI by fixture identities, reconstructs
health and ammunition from the actual events, checks damage arithmetic and
fatal clamping, rejects attacks by/on defeated actors, checks all six edges and
attack cooldowns, and correlates each damage event with the resolved attack,
hit reaction, hit flash and defeat where applicable. It requires all phases,
Unreal automation Success and the successful automation exit marker.

The final UE 5.8.2 Editor build succeeded. The existing rival combat and all nine
navigation phases also passed on the same final module; see
`D01-031-rival-regression.log`. The Project structure check passed with the
runner-owned state still at 30/50 completed and D01-031 current.

## Reproduction and qualification limits

Run from the Project root. Unreal uses the existing `unreal` host user and
its established access to the engine/project and generated build directories.

```bash
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/Linux/Build.sh BiellaGamesEditor Linux Development -Project=/root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject -WaitMutex -NoUBA -NoHotReloadFromIDE -NoUBTMakefiles -gather
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor-Cmd /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -nullrhi -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread '-ExecCmds=t.MaxFPS 30,Automation RunTests BiellaGames.Demo01.SharedInteraction; SoftQuit' -seconds=130
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor-Cmd /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -nullrhi -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread '-ExecCmds=t.MaxFPS 120,Automation RunTests BiellaGames.Demo01.SharedInteraction; SoftQuit' -seconds=130
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor-Cmd /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -nullrhi -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread '-ExecCmds=Automation RunTests BiellaGames.Demo01.Rival; SoftQuit' -seconds=190
python3 tests/verify_d01_031.py Build/Demo01/D01-031-shared-30fps.log Build/Demo01/D01-031-shared-120fps.log
python3 tests/verify_demo01.py
```

Resource routing for `runtime-validation` and `game-code` returned no configured
provider. Local Unreal and deterministic evidence validation supplied the task's
needed capability. No external provider was needed.

This qualifies live headless gameplay simulation, collision and runtime
material/visibility state. The 30/120 values are execution caps, not measured
rendered FPS. It makes no rendered visual-quality, audio/animation, crowd-scale,
arena-pressure or Win64-package claim. The initial successful build/runtime
logs are retained as development evidence; final acceptance uses the final
build and the two final runs above.

D01-001..030 evidence is preserved. The canonical 03/04 records and Project
PRODUCTION status/next-task metadata are untouched for the runner's transition.
Engine P4-06 remains INCOMPLETE_DEFERRED. No successor task was executed.
