# D06-01 — Cinematic and presentation integration

Status: `COMPLETE`

Validated: `2026-09-08T06:11:17Z`

Project: `Biella Games`

Engine: Unreal Engine `5.8.2`

Map: `BiellaGameplayMap`

## Delivered

- `ABiellaCinematicDirector` owns one bounded runtime sequence, uses the live
  player/world, transfers camera and input ownership, and restores gameplay on
  watched or skipped completion.
- `ABiellaGamesPlayerController` exposes the existing session-mode handoff as
  `Gameplay -> Cinematic -> Gameplay`, including transient-input reset and the
  existing skip input path.
- `Content/Cinematics/LS_Demo01_RuntimeHandoff.uasset` is an editable technical
  Level Sequence. It contains one `CameraActor` binding and one camera-cut
  section; the transient camera is bound to the sequence at runtime in the
  actual gameplay world.
- `BiellaCinematicTest.cpp` is the native watched/skipped runtime acceptance
  fixture. `tests/run_d06_01_cinematic.py` builds, authors, reads back, runs,
  and validates the task boundary.

## Editable sequence identity

Authoring and separate readback both returned `PASS` for:

```text
asset: /Game/Cinematics/LS_Demo01_RuntimeHandoff
class: LevelSequence
binding_class: CameraActor
binding_count: 1
camera_cut_track_count: 1
camera_cut_section_count: 1
playback: 0..72
authoring_source_sha256: bb9da5187f607ea25cb91cab38d0ef7898ed248f5bbfea0f81a862f683621fdd
```

The checked-in package is a real Unreal package, not an extension rename:

```text
path: Content/Cinematics/LS_Demo01_RuntimeHandoff.uasset
format: UnrealPackage
magic: c1832a9e
bytes: 9856
sha256: f79a65ae337d1476b7b7f6ad5aa3bd82221479f1fe5ceb5822d7a7f07570e3cf
```

## Build and runtime evidence

The fresh editor build used `Build.sh BiellaGamesEditor Linux Development`
against `BiellaGames.uproject` and returned `0`:

```text
build_log: /root/biella/artifacts/games/D06-01/20260908T061117.897522Z-vulkan-eb4ffad8/build.log
build_log_sha256: 21d3bce60d398cd1161c2822151e93c1ab2583591d7aea751f8cf42558614c0a
```

The fresh Vulkan runtime returned `0` and passed `BiellaGames.D06.Cinematic`.
The authoritative runtime log recorded:

```text
D06_SIGNAL CINEMATIC_ENTER ... player=BiellaGamesCharacter_0 camera=CameraActor_0 ... same_world=true input=constrained state_preserved=true
D06_SIGNAL CINEMATIC_HANDOFF path=watched revision=1 player_restored=true input_restored=true camera_restored=true state_unchanged=true same_world=true
D06_SIGNAL CINEMATIC_ENTER ... player=BiellaGamesCharacter_0 camera=CameraActor_1 ... same_world=true input=constrained state_preserved=true
D06_SIGNAL CINEMATIC_HANDOFF path=skipped revision=2 player_restored=true input_restored=true camera_restored=true state_unchanged=true same_world=true
D06_01_TEST COMPLETE watched_state=1 skipped_state=1 same_player=true same_world=true input_restored=true no_duplicate_player=true mission_state_preserved=true
Test Completed. Result={Success} Name={Cinematic} Path={BiellaGames.D06.Cinematic}
```

This proves both paths used the same `BiellaGamesCharacter_0` and live
`BiellaGameplayMap`, restored gameplay camera/input ownership, preserved the
authoritative gameplay snapshot, and did not create a duplicate player or
diverge mission/world state. The D06-only validation hold was released before
the fixture began; it only prevents autonomous encounter resolution before the
runtime assertions observe the real world.

Runtime evidence:

```text
output: /root/biella/artifacts/games/D06-01/20260908T061117.897522Z-vulkan-eb4ffad8
validation_sha256: see validation.json
runtime_log_sha256: 63ad49c8ee7d2b13c7995471b75ba5ba6b75aaeac7879d22c82b59aadbafa252
telemetry_sha256: c0b807e7d72de2641ebd9d12387dd6311938a7f7474de9f7c55f1b75f6b509b7
```

The telemetry contains exactly two `cinematic_enter` events and two handoffs,
with paths `watched` and `skipped`, and both handoffs report restored player,
input, camera, and same-world state.

## Scope and publication

The protected continuity files `docs/project-state/03_BIELLA_CURRENT_STATE.md`,
`docs/project-state/04_BIELLA_ACTIVE_TASK.md`, and
`docs/PRODUCTION.md` were byte-identical before and after validation. No task
metadata or next-task state was edited.

The implementation and this acceptance record are task-owned local output and
are committed together. Remote GitHub/Drive publication is left to the
configured Auto Feeder publication cursor. The captured presentation remains
`GENERATED_DRAFT`; this technical runtime acceptance does not constitute Mahdi
acceptance of generated media.
