# D02-03 vehicle runtime

The accepted Unreal 5.8.2 open-world development map now contains one drivable,
match-local vehicle, `D02Vehicle01`. This implements the current vehicle boundary
in implementation sequence 2.3 and runtime contract 11. Vehicle catalog, final art,
shipping handling and traffic systems are outside this result.

Open `/Game/Maps/BiellaOpenWorldMap` in the existing editable project and play.
The car starts at `(2800, -450, 110)` cm. Approach it on foot; the HUD displays the
interaction prompt when nearby.

| Control | Behavior |
| --- | --- |
| E | Enter a nearby stopped car; exit when stopped with a clear supported side |
| W / S | Forward throttle / reverse throttle |
| A / D | Steer left / right |
| Space | Brake |
| Mouse | Rotate the third-person follow camera |
| R after a terminal outcome | Existing restart flow recreates the world and car |

`BiellaVehicle.h/.cpp` owns a Chaos rigid-body chassis, four suspension rays and
forces applied at the wheel contacts. Chaos integrates motion and resolves
collisions; driving does not write car transforms or prescribed velocities.
Suspension compression and steering drive the visible wheels. Configurable mass,
acceleration, speed limit and spring controls live in `Config/DefaultGame.ini`.
These are development tunables, not accepted production handling specifications.

The existing possessed character attaches in a seated pose while mounted. Walking,
jumping and firing are gated; the player's health and ammunition remain intact.
Entry checks distance, speed, player state and the approach path. Exit checks both
sides for supporting terrain, capsule clearance and the swept path from the seat.
Moving, overturned or obstructed exits are rejected with HUD feedback. A valid exit
restores the on-foot character, collision, movement, pose and camera. This uses
the current blockout character presentation, not a finished entry/exit animation.

An occupied car supplies a World Partition source with a forward lookahead. If
current or forward wheel support is unavailable, simulation holds until support
returns. The pending streaming target survives the velocity reset used by that
hold. A distant parked car removes its source and suspends rendering/collision
and physics; returning to supported terrain resumes the same UObject, transform
and damaged health. This is match-local retention, not save/load across processes.

Rigid collision impulses damage the car. Contact with infected or rivals uses the
existing shared damage path. Impact cues use existing gameplay audio/VFX; engine
pitch and volume respond to throttle and speed. Headlights, brake lamps and a
health-dependent body tint accompany runtime state. Depletion disables driving;
driver defeat stops throttle/audio. Restart and actor teardown release the
streaming provider, audio and driver relationship.

`SourceAssets/Audio/Vehicle/` contains the original deterministic two-second,
48 kHz mono PCM16 engine loop and editable generator. The Unreal importer at
`Content/Python/import_vehicle_audio.py` produces the native looping PCM SoundWave
at `/Game/Vehicle/Audio/S_VehicleEngine` and verifies an exact PCM export roundtrip.
The source, native sound and runtime captures remain `GENERATED_DRAFT`.

To reproduce the qualified scenario after building `BiellaGamesEditor` with the
accepted engine, run from the Games project root, choosing a fresh output path:

```bash
python3 tests/run_d02_03.py --output /root/biella/artifacts/games/D02-03/vehicle-new-run
python3 -m pytest -q tests/test_d02_03_vehicle_audio.py tests/test_verify_d02_03.py tests/test_run_d02_01.py
```

The runner launches the actual Vulkan game runtime at 1280×720, with a 60 FPS cap,
ordinary variable simulation time and the software audio mixer. It executes
`BiellaGames.D02.Vehicle` from `Private/Tests/BiellaVehicleTest.cpp`, which sends real
controller key events and measures every frame. The independent Python verifier
replays raw frame CSV, ordered events, collision/damage logs, decoded captures and
mixed PCM audio. `Build/Vehicles/D02-03-acceptance.md` records exact evidence,
fixture limits, regression results and preservation checks for this boundary.
