# D02-02 population and encounter scaling

Task scope: implementation sequence 2.2 and runtime contracts 15, 31, 32, 34.
The current instruction authorizes bounded implementation and measured tuning.
No shipping population, hardware or performance target is selected here.

## Design and implementation plan

Extend the existing open-world game mode with a persistent, match-local encounter
director. Config-defined street regions own deterministic rival/infected slots;
actor names and slots stay stable through retries, suspension and movement across
cell boundaries. Existing Demo mission/pressure actors retain their ownership.

Admission requires actual supporting collision, full capsule clearance, a complete
Recast path to the player and a readable minimum spawn distance. Admission has a
small per-update budget. Measured wall frame time can pause new admission; it must
never erase ongoing combat. Distant actors suspend only beyond a hysteresis radius
and without nearby player combat relevance. Their UObjects, health and defeat
state persist; removed actors leave non-respawning tombstones. Unsupported terrain
holds simulation before movement and resumes only after placement is valid again.
Population infected use bounded Recast replanning and swept collision, reusing the
existing authoritative target selection, pressure response and melee damage.

Implementation order (one D02-02 boundary, no separate production ledger):
1. Add a live Unreal acceptance test that fails when the director is absent.
2. Implement director/configuration, infected path follower and game-mode ownership.
3. Exercise valid/invalid spawn, identity, pressure/load admission, suspension,
   defeat, multiple autonomous combatants, obstruction/replanning and frame metrics.
4. Build the current Editor, run real Vulkan candidate densities, inspect captures,
   replay raw evidence and run affected predecessor regressions.
5. Record exact source/evidence hashes and limitations, commit locally. The Auto
   Feeder owns GitHub/Drive publication and protected 03/04/PRODUCTION transitions.

Rejected alternatives: per-cell respawn duplicates migrating actors; deleting
nearby actors to meet a frame budget changes encounter outcomes. Retaining a
bounded authored population in memory uses more dormant memory but preserves
match-local identity without inventing disk persistence or an Engine controller.

Captures remain GENERATED_DRAFT. Current executable evidence will be recorded in
`Build/Population/D02-02-acceptance.md`.

## Implemented development controls

`Config/DefaultGame.ini` configures the open-world director with three street
regions, twelve finite slots per region and a conservative four-active admission
limit. Each group of four slots contains one existing rival and three population
infected variants. Admission uses at most two spawn attempts per 0.25 seconds;
new admission pauses above a 25 ms smoothed wall-frame guard and resumes below
20 ms. These are editable development controls for this measured blockout,
not accepted shipping density or frame-rate requirements.

Activation is within 5,000 cm and distance suspension starts beyond 6,500 cm,
subject to combat relevance. A 1,000 cm player exclusion radius applies to new
spawns. Increasing or decreasing admission limits does not replace, heal or
remove existing combatants. A live actor with supporting floor remains visible
and collidable during capsule obstruction or temporary navigation unavailability;
its path follower waits/replans. An unloaded supporting floor suspends it. Resume
rechecks full placement and preserves its current transform and damaged health.
Destroyed/defeated identities become tombstones for the rest of that world.
This is bounded match-local continuity, not a disk save or population respawn rule.

Reproduction uses the real Editor `-game` Vulkan world with ordinary variable
simulation time:

```
python3 tests/run_d02_02.py --output /root/biella/artifacts/games/D02-02/<fresh-run> --count 4
python3 tests/run_d02_02.py --output /root/biella/artifacts/games/D02-02/<fresh-run> --count 8
python3 tests/run_d02_02.py --output /root/biella/artifacts/games/D02-02/<fresh-run> --count 12
```

The fixture freezes legacy mission actors and holds population only while
checking admission/continuity. During the twenty-second measured combat window,
all managed actors use their ordinary autonomous logic, tuning, collision and
damage. Player health is increased for repeatable survival. A separate explicit
fixture defeat finishes remaining enemies after that window; it never substitutes
for the measured natural combat. The final navigation probe follows real Recast
paths to a stationary opponent while a runtime obstruction is added and removed.
Raw measurements include capture and streaming hitches and disclose the actual
duration at each surviving population density.

The predecessor `BiellaGames.D02.WorldStreaming` fixture also holds new population
admission while it measures its existing authored encounter. This prevents a new
actor spawned after pre-tick isolation from fighting inside that frozen fixture.
Its original health, traversal, reconstruction and defeat assertions remain in
place. The separate population scenario runs the new actors autonomously and
checks their own suspension/return behavior. This fixture rule is compiled only
with development automation and is not a normal gameplay configuration change.
