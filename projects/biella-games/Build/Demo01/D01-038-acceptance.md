# D01-038 — success/failure overlays and restart input

## Implementation

- `UBiellaGameplayHUD` builds a native UMG terminal overlay from editable C++ source and binds its title, message, and restart prompt to the authoritative runtime phase.
- Success presents `SUCCESS // ARENA CLEARED` / `Arena cleared.`; failure presents `FAILURE // YOU WERE DEFEATED` / `You were defeated.`; both present `PRESS R TO RESTART`.
- `ABiellaGamesPlayerController` binds `R`, disables movement/look while the match is terminal, and routes the restart request to the authoritative game mode.
- `BiellaGames.Demo01.TerminalOverlay` covers both terminal outcomes, verifies the displayed strings and visibility, sends the restart input, and verifies a clean Active match after reload.
- The production implementation was already present in the same-task checkpoint `6a80aa2cfc808071ca848763af818cbaa53556ab`; this boundary adds fresh runtime/build evidence and its durable acceptance record.

## Validation

| Check | Result |
| --- | --- |
| UE 5.8.2 Editor build | PASS — target up to date; `BiellaGamesEditor` build exited `0` with `Result: Succeeded` |
| Headless live automation | PASS — `BiellaGames.Demo01.TerminalOverlay`, exit code `0` |
| Rendered Vulkan automation | PASS — `BiellaGames.Demo01.TerminalOverlay`, exit code `0`, 1280×720 offscreen runtime |
| Success terminal state | PASS — success overlay visible with exact title/message/prompt; `input_accepted=true` for `R` |
| Failure terminal state | PASS — failure overlay visible with exact title/message/prompt; player is dead |
| Restart recovery | PASS — authoritative restart request reloads the map; new Active match has objective progress `0/2`, two infected, and a live full-health player |
| Structural verifier | PASS — `DEMO01_STRUCTURE_PASS completed=37/50 current=D01-38` |

## Evidence

- `Build/Demo01/D01-038-editor-build.log`
- `Build/Demo01/D01-038-overlay-headless.log`
- `Build/Demo01/D01-038-overlay-vulkan-fresh.log`
- `Build/Demo01/D01-038-validation.json`

The runtime emitted existing navigation/crowd warnings during map teardown/reload; the D01-038 automation test completed successfully and reported no task assertion failure.
