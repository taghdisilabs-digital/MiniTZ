# D02-02 — Population and encounter scaling

This task adds an editable, match-local population director to the existing Unreal
open world. It admits and retains rival/infected encounters on real collision and
Recast navigation, shares existing autonomous combat and pressure behavior, and
measures increasing candidate populations in the actual Vulkan game runtime.

Scope is implementation sequence 2.2 and runtime contracts 15, 31, 32 and 34.
The starting revision is `7c9e29b23b2cb0053ebb7c53dd5f92001c929fd2`.
This document and its evidence belong only to D02-02.

## Editable result

- `Source/BiellaGames/Public/BiellaPopulation.h` and
  `Source/BiellaGames/Private/BiellaPopulation.cpp` implement the director and the
  infected Recast path follower. The existing open-world game mode creates the
  director; its support loop leaves managed actor suspension to that director.
- `Config/DefaultGame.ini` defines three street regions with twelve finite slots
  each. Every four slots contain one rival and three infected. Stable names encode
  region and slot; failed admission retries do not create extra identities.
- The normal development configuration admits at most four active managed actors,
  with at most two spawn attempts each 0.25 seconds. New admission requires a
  supporting floor, full capsule clearance, a complete path to the player and a
  1,000 cm player exclusion distance. It pauses above a 25 ms smoothed wall-frame
  guard and resumes below 20 ms. These values are editable development controls;
  they do not establish shipping density or frame-rate requirements.
- Actors activate within 5,000 cm and may suspend beyond 6,500 cm when combat
  relevance permits. Suspension retains the same UObject, damaged health and
  transform. Defeated/destroyed slots remain tombstones for that world. Missing
  supporting geometry suspends simulation; resume requires valid placement.
- A supported live actor stays visible and collidable during temporary capsule
  obstruction or navigation unavailability. Recast replanning and swept movement
  handle obstruction without hiding the combatant or teleporting it.

`docs/POPULATION_SCALING.md` explains implementation choices and reproduction.
The actor budget applies to director-managed population in addition to legacy
mission actors. Retained dormant objects are bounded by the authored slot count.
There is no new Engine controller, scheduler or disk-persistence system.

## Runtime proof and measurement

The final Editor build is recorded in `D02-02-regression-editor-build.log`.
Each runtime runner checks exact source, content and module identities before and
after execution. Final runs use the same module, ordinary variable simulation
time, Vulkan at 1280×720, no VSync and no fixed timestep or benchmark mode.
The host is Ubuntu 24.04.4, AMD EPYC 9124 and NVIDIA L40S, driver 580.178.04,
with Unreal Engine 5.8.2. These are development-host measurements.

Final accepted development evidence is `runtime-{4,8,12}-final-build/validation.json`.
All three candidates passed; all natural damage sources and targets covered every admitted identity.

| Initial actors (rival/infected) | Combat wall s | Frames | p95 / p99 ms | Max ms | Peak RSS MiB | ≥75% active s | Natural damage events | Survivors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 (1/3) | 20.005748 | 1729 | 13.688 / 14.586 | 626.367 | 2837.18 | 8.386510 | 22 | 1 |
| 8 (2/6) | 20.005330 | 1738 | 13.683 / 14.730 | 732.086 | 2846.66 | 8.488415 | 44 | 2 |
| 12 (3/9) | 20.011031 | 1697 | 13.827 / 14.649 | 673.204 | 2857.80 | 8.436210 | 66 | 3 |

All recorded managed-capsule overlap counts were zero. Full scenario and dense-interval
p50/p95/p99/max/RSS statistics remain in each validation report. These percentile
measurements do not hide the 626–732 ms maximum hitches and do not qualify a shipping FPS target.

The common tested project module SHA-256 is
`e33ed53237ac8198ee1f5bd429ccf082bb257ba8e0f5e983bfb6f5c89557efe6`.
`D02-02-final-input-identities.json` verifies 188 current file identities across
all five runtime reports, including unchanged maps/assets and protected authority.
The final build completed successfully in 29.04 seconds.

Frame data includes every engine frame in the recorded scenario, with monotonic
wall intervals, active/spawned/team counts, health, path revisions, capsule
overlaps and process resident memory. Percentiles and maximum hitches are retained
without filtering capture or streaming stalls. Autonomous defeats reduce the
surviving population during the combat interval; an initial twelve-actor run is
not evidence of twelve actors surviving for the full twenty seconds.

`Source/BiellaGames/Private/Tests/BiellaPopulationTest.cpp` drives these live checks:

1. Reject unsupported, occupied and too-close spawn placements; admit the requested
   stable identities and rival/infected mix with bounded admission bursts.
2. Force the frame admission guard while retaining all existing actors. Insert a
   real obstruction at a live actor and confirm it remains active and collidable.
3. Run twenty wall seconds of ordinary autonomous movement and rival/infected
   damage under the existing pressure response. Require multiple moving and
   damaged actors, both damage directions, Recast activity and zero measured
   managed-capsule overlaps.
4. Preserve a damaged survivor, suspend away from the region and return to the
   same UObject, transform and health. Require unique original IDs, unchanged
   spawn count and defeat tombstones.
5. Add and remove a real navigation obstruction during an infected pursuit.
   Require a path revision while the obstruction exists and actual swept arrival
   within 180 cm of its target.

The fixture freezes legacy mission actors, holds managed actors during isolated
admission/continuity checks and raises player health to 10,000 for survival.
The real HUD clamps that test value to its normal display range. Managed actors
run their ordinary logic throughout the measured combat interval. Explicit
`d02_continuity_fixture_defeat` damage is applied only after that interval to
isolate the survivor; it is excluded from natural-combat proof. A separate frozen
opponent is used for the final navigation probe. Population runs disable sound.

## Regression and evidence integrity

The predecessor streaming fixture now holds new director admission in its
existing pre-tick isolation callback. This development-test-only integration
prevents a newly admitted actor from fighting after the callback has frozen
existing actors. Its original health, traversal, reconstruction and defeat
assertions are retained. Normal gameplay configuration is unchanged by this rule.

- `streaming-regression-final/validation.json`: PASS over 13,903 frames and
  165.755510 wall seconds, with 51 visible cell loads and 39 unloads. The original
  street, interior, elevated route, distant suspension, injured return and defeat
  reconstruction checks passed. Wall-frame p95 was 13.992 ms and p99 was 14.968 ms.
- `shared-regression-final/validation.json`: PASS across ten phases, twenty damage
  events, all six player/rival/infected damage directions and four defeats over
  13.495 seconds. The existing shared-combat verifier and assertions are unchanged.
- `D02-02-final-population-replay.json` and `D02-02-final-regression-replay.json`:
  independent replay of all five canonical local raw evidence copies passed.
- `D02-02-verifier-negative-final.json`: the passing final four-actor baseline was
  accepted and all eleven corrupted controls were rejected.
- `D02-02-final-population-archive.json` and `D02-02-final-regression-archive.json`:
  exact final evidence copies verified byte-for-byte against artifact originals.
- `D02-02-final-visual-review.json`: all nine final population captures decoded;
  the three initial-density captures and both twelve-actor outcome captures were
  visually inspected in their original form. The earlier qualified capture set
  remains separately reviewed and preserved.

The existing regression tools retain their original D02-01 task label inside
reports; these final reports are D02-02 regression evidence from the final module.

The independent population verifier replays raw events, frame CSVs and runtime
logs. It requires real Vulkan presentation, complete ordered lifecycle evidence,
exact identity, measured time, natural bidirectional damage, obstruction
replanning and decoded nonblank captures. Negative controls corrupt eleven
independent parts of actual passing evidence; all must be rejected.

Raw runs remain at `/root/biella/artifacts/games/D02-02/`. Exact copies of the final
runs live beside this document for the local commit and Auto Feeder publication.
Archive manifests preserve source and canonical local identities, byte counts and
SHA-256 digests; original reports retain their original absolute paths.

Earlier red tests, passing candidates and the failed first streaming regression
remain preserved. The red obstruction test exposed a real live-actor suspension
bug that was repaired. The first streaming regression exposed the fixture
isolation gap described above. Error teardown also reported a Vulkan assertion;
final successful runs exited cleanly. The configured local Qwen review was tried
twice and timed out; no provider review verdict is claimed. Local source review
and independent raw-evidence replay supplied validation. Task-filtered failure
records are retained in `D02-02-observed-failures.jsonl`; the original global
failure ledger is not rewritten.

Captures are real, decoded runtime evidence and remain `GENERATED_DRAFT`.
The environment and actors retain current blockout presentation. This task does
not claim AAA art acceptance, shipping performance, a newly qualified standalone
package, audio acceptance or persistence across process teardown. D02-01's known
non-editor package limitation is unchanged and was not reopened.

## Preservation and handoff

`D02-02-preservation.json` verifies unchanged 03/04 and Project `PRODUCTION.md`
bytes. Existing map/assets and all other predecessor Games tracked bytes remain intact
except the four bounded integration files identified in that report. Engine
P4-06 remains `INCOMPLETE_DEFERRED`. No later task is executed.

The implementation, supporting documentation and exact evidence are committed
locally. Per the current task instruction, the Auto Feeder owns GitHub/Drive
publication, remote readback and canonical state transition. This local evidence
does not claim remote publication or modify production status/next-task metadata.
No new publication destination or duplicate authority record is introduced.

A concurrent website-only revision, `3a03951a0c86a34b68bcd7f6d384169a40aaec3c`,
was admitted before this task commit. Its website/workflow changes and ongoing
website edits are preserved; all 188 final runtime input identities still match.
Raw Unreal logs retain their original CRLF/trailing whitespace so their digests
remain exact. Whitespace validation is applied to authored source and documents.
