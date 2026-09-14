# D02-04 environment runtime

The bounded continuation adds one match-local electrical service bay beside the open-world road at (6500, 700, 0). It uses the existing C++ runtime, streamed street collision, dynamic navigation, damage/feedback services, and restart path. It is development gameplay geometry; no new shipping platform, persistence service, weather system, or multiplayer contract is implied.

Three independently damageable steel panels form a barrier. The center panel is 240 cm wide so its opening admits the configured 48 cm-radius navigation agent with voxel clearance. Each panel progresses from intact through damaged to detached, using the same mesh as a Chaos rigid body. Intact panels obstruct movement and navigation; detached lightweight panels ignore pawns and stop carving navigation. They retain world collision and bounded physics. Two normal 34-damage shots detach a panel. The switch, frame, and floor markings are not destructible.

The service switch uses E and one shared availability predicate for HUD and action: live on-foot player, active match, ready traversal, within 220 cm, facing the switch, and unobstructed sight. Power drives a warning lamp, ground marking, and localized electrical damage together. All combat-capable pawn teams use the same spatial and damage rules: 12 HP per exposure-second, delivered in pulses no faster than four per second. Fractional exposure is discarded on exit, limiting edge error to one pulse (about 3 HP) and preventing deferred damage. Geometry blocks the hazard trace; other pawn capsules do not provide electrical shielding. Deactivation immediately removes damage; no delayed pulse accumulates while off or dormant.

The site retains power, individual panel health, debris transforms, and motion within the current match. Before streamed ground can disappear, distant or unsupported debris is frozen. The whole site sleeps when distant or unsupported, disabling interaction and hazard work. Return restores the same state after support is available. Restart creates one fresh site with intact panels and power off. This is match continuity, not disk saving.

Validation exercises real E/fire/movement input in Linux Vulkan, rejected range/facing/occluded interactions, partial and full destruction, physical debris displacement, blocked then open traversal, shared hazard damage and power-off safety, actual terrain streaming unload/return, and R restart. Test-only AI holds and on-foot relocation isolate causal behavior; tests never set panel health, power, or debris transforms. Native variable timestep and raw per-frame evidence remain visible. Existing vehicle/shared regressions protect touched controller and weapon behavior.

Open `/Game/Maps/BiellaOpenWorldMap` and approach the cabinet on the west side of the bay at world coordinates (6500, 700, 0). Face the switch until the E prompt appears. The floor starts safe; E restores power and changes the switch, floor, lamp, sign, and prompt together. Aim the shoulder-camera crosshair at a panel and use the normal fire input twice to open it. E cuts power before crossing safely; entering a live floor causes damage. R uses the existing match restart.

`Source/BiellaGames/Public/BiellaEnvironmentSite.h` and `Private/BiellaEnvironmentSite.cpp` own the state and geometry. The open-world game mode creates the named site; character, controller, and HUD integration reuse the current input and feedback paths. `Private/Tests/BiellaEnvironmentTest.cpp` supplies the native causal scenario.

Reproduce from the project root after building `BiellaGamesEditor Linux Development` with the installed Unreal 5.8.2 `Build.sh`. Use fresh output directories:

```bash
python3 tests/run_d02_04.py --output /tmp/d02-04-environment-30 --fps 30
python3 tests/run_d02_04.py --output /tmp/d02-04-environment-120 --fps 120
python3 tests/run_d02_03.py --output /tmp/d02-04-vehicle --fps 60
python3 tests/run_d02_01_shared_regression.py --output /tmp/d02-04-shared
python3 tests/verify_d02_04.py Build/Environment/D02-04-acceptance-30
python3 -m unittest discover -s tests -p test_verify_d02_04.py -v
```

The native runners use the configured `unreal` runtime account and Xvfb. `Build/Environment/D02-04-acceptance.md` records the completed evidence, exact local identities, fixture limits, and Auto Feeder publication handoff. The negative controls copy the retained native 30-cap baseline into temporary directories and never rewrite it.
