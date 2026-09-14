# D01-033 — pressure world consequences and responses

Task scope: `demo01`, lights/spawns/movement consequence. This continues the
implementation preserved in recovery commit
`6582d4bcbc5a86dc87495a21e9f4f4c6187b8fc7` from canonical main
`4a3aa04`. Project authority remains `docs/PRODUCTION.md` and the current
03/04 records; their status and task metadata are unchanged by this task.

## Runtime implementation

`ABiellaGamesGameState::SetArenaPressure` remains the sole authoritative
transition API. The existing `Demo01ArenaPressure` identity, normalized level,
state bands, revision, validation and no-op behavior from D01-032 are preserved.
Its change delegate supplies the same snapshot to these three consumers:

- `ABasicWorldGeometry` updates the actual movable point light from
  900 to 2600 lumens and green to red over the pressure range. Revision replication
  notifies presentation consumers. BeginPlay reads the current snapshot.
- `ABiellaInfected` derives movement from its unchanged base speed, with a
  default multiplier of 1.0 at zero pressure and 1.5 at 100. The multiplier
  changes actual swept chase displacement and the movement component maximum.
  Repeated changes do not compound speed. Defeated infected retain zero movement.
- `ABiellaGamesGameModeBase` admits one reinforcement at Elevated and a second
  at Critical. Each slot is consumed once per match, including after death or
  removal. Spawn positions must project onto the real Recast navigation and
  pass a full pawn capsule check against solid simple collision, followed by
  Unreal's `DontSpawnIfColliding` safeguard. Transitions attempt placement
  immediately; unavailable positions also retry on a one-second tick interval.
  Lower pressure cancels still-unfilled requests. New infected
  immediately consume the current pressure snapshot and run normal AI/combat.

All three consumers unsubscribe during EndPlay. Arena region teardown destroys
its generated geometry, lights and navigation bounds. The task also fixes the
recovered teardown implementation to clear build flags, tags and stale child
references: a streamed actor instance can rebuild its world pieces and read
the current pressure on a subsequent BeginPlay. Runtime mesh assignment now
temporarily uses movable mobility and restores static mobility afterward.
This avoids Unreal rejecting mesh assignment after the world has begun play;
the live floor/navigation checks exposed that additional reconstruction issue.

The occupied-placement test exposed a second defect in the recovered code:
the omitted collision query parameters defaulted to complex triangle queries.
A capsule fully enclosed by the blocker did not intersect its triangle
surfaces. The task explicitly selects simple collision to match pawn movement.
Live evidence records both queries against the same enclosing blocker and
checks that production spawning now defers with `reason=collision`.

Rendered inspection also found the recovered point light used Unreal's default
legacy unitless intensity, making its numeric range too faint to read against
the arena's existing directional light. Explicit lumens retain the numeric
range and inverse-square falloff while making the actual lighting response
visible. Runtime assertions check the light's unit selection as well as its
intensity, color and shared revision. The earlier `*-unitless.png` captures are
diagnostic evidence, not the final result.

These are the bounded Demo tuning values already present in the recovered
implementation. Pressure itself does not introduce damage, barriers, shrinking
geometry or a time-based escalation. Transition scheduling remains an explicit
caller of the accepted GameState API. Restart still reconstructs a match via
the existing OpenLevel path; this task does not add a restart or mission system.

## Acceptance evidence

Observed 2026-09-05 on Unreal Engine 5.8.2 Linux. Final editor build:
`D01-033-editor-qualified.log` (`Succeeded`, process exit 0).

| Final runtime | Result | Measured movement ratio at pressure 50 | Reinforcements |
|---|---|---:|---:|
| Vulkan, 30 FPS cap, NVIDIA L40S, 960×540 | 11 phases PASS | 1.250 | 2, once each |
| NullRHI, 120 FPS cap | 11 phases PASS | 1.250 | 2, once each |

Final logs use the `*-qualified.log` suffix. Each run observes ten shared
pressure transitions including cleanup. The enclosing-blocker comparison
records `simple_blocked=true default_complex_blocked=false`; rebuilt region
validation records `navigation=true floor_collision=true`.

Final-build predecessor regressions also pass in fresh processes: D01-032's
four authoritative transitions; D01-031's ten phases and all six directed
player/rival/infected damage edges; D01-030's five combat phases; and D01-029's
nine navigation phases. `tests/verify_demo01.py` retains the canonical
`completed=32/50 current=D01-033` metadata pending the Auto Feeder transition.

The decoded final captures [baseline](D01-033-baseline.png) and
[critical](D01-033-critical.png) show the same possessed-player camera with a
green-to-warm-orange lighting response on fixed arena surfaces, plus the live
infected population change. Copies are available to the private Assets
inspector at `/root/biella/artifacts/games/D01-033/` as `GENERATED_DRAFT`
supporting captures, not accepted art.

Validation results and exact source/build/log hashes are recorded in
`D01-033-validation.json`. The editable automation scenario is
`Source/BiellaGames/Private/Tests/BiellaPressureResponsesTest.cpp`; its log
validator is `tests/verify_d01_033.py`.

The scenario runs in the actual `BiellaGameplayMap`, places a possessed player
and autonomous infected in an unobstructed lane, and changes pressure through
the production setter. It checks eleven phases: baseline chase; Rising without
spawns; blocked Elevated placement; downgrade cancellation; unblocked retry;
measured Elevated chase; two Critical slots; late infected and same-instance
arena reconstruction; return to baseline; defeated immobility; and no duplicate
or refilled slots. A collision blocker leaves navigation intact so the capsule
overlap guard itself is exercised. After region lifecycle reconstruction, a
floor trace and Recast query prove that real collision/navigation also return.

Fixture setup removes the unrelated starting encounter and places actors; it
does not assign pressure response values, movement speeds, health or spawn
counts. Movement is measured over world ticks. Defeat uses the production
damage API. The scenario replays the actor's streaming lifecycle callbacks;
it does not claim full World Partition streaming qualification.

## Reproduction

Run from the Biella Games Project directory:

```bash
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/Linux/Build.sh BiellaGamesEditor Linux Development -Project=/root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject -WaitMutex -NoUBA -NoHotReloadFromIDE -NoUBTMakefiles -gather
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor-Cmd /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -nullrhi -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread '-ExecCmds=t.MaxFPS 30,Automation RunTests BiellaGames.Demo01.PressureResponses; SoftQuit' -seconds=100
```

Repeat the scenario with `t.MaxFPS 120` for simulation cadence variation. These
caps do not establish rendered performance targets. Run the predecessor
`BiellaGames.Demo01.ArenaPressure` and `BiellaGames.Demo01.SharedInteraction`
scenarios in separate fresh processes, then validate their logs with the
existing D01-032 and D01-031 scripts.

Rendered validation uses the same scenario and assertions:

```bash
runuser -u unreal -- xvfb-run -a /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -RenderOffscreen -vulkan -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread -windowed -ResX=960 -ResY=540 -D01PressureCaptures '-ExecCmds=t.MaxFPS 30,Automation RunTests BiellaGames.Demo01.PressureResponses; SoftQuit' -seconds=100
python3 tests/verify_d01_033.py Build/Demo01/D01-033-pressure-120fps-qualified.log Build/Demo01/D01-033-pressure-vulkan-qualified.log
python3 tests/verify_d01_032.py Build/Demo01/D01-033-state-regression-qualified.log
python3 tests/verify_d01_031.py Build/Demo01/D01-033-shared-regression-qualified.log
python3 tests/verify_demo01.py
```

The screenshots are supporting captures of editable live runtime behavior,
not accepted game art or a claim of AAA visual completion. This task does not
qualify Win64 packaging, multiplayer replication, native rendered frame-rate
targets or large populations.

Other D01-033 logs preserve development attempts, including build access and
compiler corrections, the original complex-collision failure, and the reload
failure that appeared only when real floor/navigation checks were added.
They are diagnostic history; final acceptance refers to the qualified build,
qualified logs, and final captures listed above.

Local implementation/evidence commitment is this task's durability boundary.
The Auto Feeder owns publication, remote readback, and canonical status
transition. Engine P4-06 remains INCOMPLETE_DEFERRED; D01-034 is not executed.
