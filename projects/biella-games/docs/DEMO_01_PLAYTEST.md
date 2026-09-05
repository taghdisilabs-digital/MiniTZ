# Demo 01 deterministic playtest

D01-39 provides a development automation scenario, `BiellaGames.Demo01.DeterministicPlaytest`, and opt-in local JSONL telemetry from the actual gameplay implementation. The fixture uses the canonical arena, possessed player, Enhanced Input, weapon collision/damage, objective manager, autonomous infected melee, HUD terminal states, and the bound `R` restart input.

Build the current `BiellaGamesEditor` target before running from the Project directory:

```sh
python3 tests/run_d01_039.py
python3 tests/run_d01_039.py --renderer vulkan
```

The default host executable is `/opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor`. Root launches it as the existing `unreal` account. `--editor`, `--runtime-user`, `--output`, and `--timeout` override the host execution details. Each invocation creates a unique directory under `Build/Demo01/D01-039-runs`, runs at least two separate processes, and saves commands, logs, captures, validation, source/configuration/map hashes, and build identities. This qualifies the existing Linux development runtime; it does not qualify a Windows package.

The scenario runs a fixed 60 Hz simulation step and defaults to seed `1337`. `--seed` selects a nonnegative 32-bit seed for the controlled arena lane and rising pressure level. This seed describes fixture choices, not a promise of deterministic Unreal physics, rendering, or all autonomous encounters. Loading and process startup remain outside the semantic comparison interval.

The seven ordered checkpoints are:

1. A clean Active match with health 100, ammo 60, two full-health infected, objective progress zero, and pressure zero.
2. Movement through Enhanced Input, with observed displacement bounded by runtime assertions.
3. The first infected defeated by three real weapon inputs, ammo 57, objective progress one.
4. Success after six weapon inputs, ammo 54, no infected remaining, and a visible terminal overlay.
5. A clean Active match after the bound success restart input and real map reconstruction.
6. Failure caused by live infected AI selecting, attacking, and defeating the player through melee collision and damage.
7. A clean Active match after the bound failure restart input and another map reconstruction.

Success targets and the rival are held stationary as controlled fixture conditions. A pre-actor-tick callback freezes each fresh fixture before incidental AI fire can damage its baseline. The failure encounter enables an infected's normal AI tick. The harness never assigns health, ammo, objective progress, cooldowns, or terminal outcomes. It restores AI ticking and removes its callback when the scenario ends. Each stage and the entire run have bounded deadlines; a failure emits diagnostics instead of a completion record.

Telemetry can also be enabled for an ordinary development session with `-BiellaTelemetry=<new-writable-file.jsonl>`. Capture is disabled by default and uses no external service. The game-instance subsystem survives map reloads, gives each capture a unique session, and flushes each event as UTF-8 JSON. Existing files are refused so retries cannot replace failed evidence. A capture error fails harness acceptance.

Every record uses schema `biella.demo01.telemetry/v1` with `session`, contiguous `seq`, `restart_count`, world-relative `sim_seconds`, session-relative `wall_seconds`, `map`, `event`, and a `fields` dictionary of strings. Runtime hooks record phase, pressure, objective activation/progress/success, damage, defeat, weapon hits/blocked traces, and restart requests. Harness events identify the scenario, seed, fixture, input schedule, and state checkpoints. Explicit fixture actor IDs distinguish the player, rival, and each infected.

`restart_requested` is recorded in the departing world after the restart count increments. The next world's simulation clock can therefore reset without another increment. Lifecycle records can lack a world. Wall time and sequence retain session continuity.

The verifier compares every ordered event and field between `scenario_begin` and `scenario_complete`, with restart counts relative to the scenario baseline. Session IDs, absolute sequence offsets, and timestamps are validated but excluded from trace equality. Thus a changed damage amount, missing event, reordered transition, or corrupted reset fails comparison. Actual clocks remain in the original captures. Both processes must also report Unreal automation success, and source/configuration/map/build bytes must stay unchanged during the attempt.

```sh
python3 tests/verify_d01_039.py --self-test
python3 tests/verify_d01_039.py /path/to/run-01.telemetry.jsonl /path/to/run-02.telemetry.jsonl
```

The verifier's adversarial fixtures test rejection behavior; they are separate from real runtime acceptance evidence. These captures support gameplay regression work. Native performance, soak qualification, visual/readability judgment, and manual playable acceptance remain their separate production tasks.
