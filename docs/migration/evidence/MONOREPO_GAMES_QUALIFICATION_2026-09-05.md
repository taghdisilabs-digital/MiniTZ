# Monorepo Games Qualification — 2026-09-05

Status: `VERIFIED`
Project source: `projects/biella-games/`
Frozen source commit: `2193b769e61b43ebfc4f910f6380c68e6b828cd5`
Frozen source tree: `b80f2fcee95b3180d0a5a7b6664819876962ce6e`
Execution boundary: migration qualification only; D01-027 remained pending.

## Source preservation
- Final import comparison before path-specific edits: `88/88 Git blobs matched`.
- Runtime validation copy comparison: `89 regular Project files matched` after current migration metadata/verifier edits.
- Compiled module/receipt comparison: `5/5 Binaries files matched` between nested canonical build output and non-root runtime validation copy.

## Structure
- `projects/biella-games/tests/verify_demo01.py`: `DEMO01_STRUCTURE_PASS completed=26/50 current=D01-027`.

## Unreal build
- Engine: `/opt/unreal/UE_5.8.2`
- Target: `BiellaGamesEditor Linux Development`
- Result: `Succeeded`
- Build log SHA256: `ae489889d29bfe332f47e72314d965b8f0b3519cfb139ad661c0bb74bf9cff55`

## Headless runtime
- Unreal runs as existing non-root `unreal` user because Linux UE 5.8.2 explicitly refuses UID 0.
- Runtime source is an exact-byte validation copy of the canonical Project plus exact compiled module/receipt bytes.
- Exit: `124` from the bounded 45-second qualification timeout, accepted by the existing runtime qualification pattern.
- Loaded `/Game/Maps/BiellaGameplayMap` with `BiellaGamesGameModeBase`.
- Observed `D01_SIGNAL` evidence for game instance, arena, navigation, world, infected spawn/group, controller, player pawn, camera, aim, input, locomotion, weapon, infected aggro and chase.
- No `Fatal error`, `Assertion failed`, `Unhandled Exception`, `Segmentation fault`, or `SIGSEGV` observed.
- Runtime log SHA256: `b9dc78dc044b02d0739d27182b25d2366d38d9a8ece7abe47a6686e760f765a1`

This record proves migration/runtime continuity. It does not mark D01-027 complete or advance Games production.
