# D01-032 — authoritative arena-pressure state

Observed 2026-09-05 in the canonical `patrickminitz-web/biella-engine`
repository, Project `projects/biella-games`, from base commit
`f0521d0df75db5352fb6e9cd12ee67cdf309e7de`. The implementation is intentionally
state-only: D01-033 owns pressure-driven lights, spawning and movement
consequences.

## Implementation

`ABiellaGamesGameState` now owns the project-specific `Demo01ArenaPressure`
identity, a replicated normalized pressure level, an explicit
`EDemo01ArenaPressureState` (`Inactive`, `Rising`, `Elevated`, `Critical`), a
monotonic revision, and the last accepted transition reason. The authority-only
`SetArenaPressure` API rejects non-finite input, clamps the valid domain to
`0..100`, resolves state bands deterministically (`0`, `<35`, `<70`, `>=70`),
and leaves the revision unchanged for an identical value. The GameState emits
authoritative transition signals and replicates the state to runtime clients.
No world consequence or gameplay damage is attached at this boundary.

## Live runtime acceptance

`Source/BiellaGames/Private/Tests/BiellaArenaPressureTest.cpp` runs
`BiellaGames.Demo01.ArenaPressure` in the canonical `BiellaGameplayMap` using
the real Unreal runtime. It verifies the server authority, canonical identity,
initial inactive state, negative-domain clamping, non-finite rejection, four
deterministic transitions, retained reasons, monotonic revisions, and the
no-op revision rule. The runtime log records:

| Phase | Level | State | Revision |
|---|---:|---|---:|
| rising | 20.0 | Rising | 1 |
| elevated | 50.0 | Elevated | 2 |
| critical | 85.0 | Critical | 3 |
| reset | 0.0 | Inactive | 4 |

`tests/verify_d01_032.py` passed against the live log and confirmed the single
`Demo01ArenaPressure` identity, server authority, all four transitions, the
invalid-input guard, Unreal automation success and clean exit.

The UE 5.8.2 `BiellaGamesEditor` build succeeded. Existing predecessor source,
runtime evidence and authority records were preserved; D01-033 and later tasks
were not executed.

## Reproduction

```bash
/opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/Linux/Build.sh BiellaGamesEditor Linux Development -Project=/root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject -WaitMutex -NoUBA -NoHotReloadFromIDE -NoUBTMakefiles
runuser -u unreal -- /opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor /root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject /Game/Maps/BiellaGameplayMap -game -nullrhi -unattended -nosound -nosplash -stdout -FullStdOutLogOutput -NoAsyncLoadingThread '-ExecCmds=Automation RunTests BiellaGames.Demo01.ArenaPressure; SoftQuit' -seconds=40
python3 tests/verify_d01_032.py Build/Demo01/D01-032-arena-pressure.log
python3 tests/verify_demo01.py
```

This qualifies authoritative state-source and live headless runtime behavior;
it makes no claim about pressure world consequences, rendered quality, native
FPS, package delivery or the unapproved exact pressure mechanic.
