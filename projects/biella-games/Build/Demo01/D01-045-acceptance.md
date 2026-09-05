# D01-45 — Lifecycle, GC and spawn cleanup

Result: `PASS`

## Scope

The Demo 01 runtime now keeps its authored encounter spawn idempotent, owns one
authoritative objective manager per match, retires defeated pressure
reinforcements, and clears GameMode/pawn/rival references during `EndPlay`.
Pressure slots remain consumed after retirement, so cleanup cannot turn into an
unbounded refill loop.

## Live validation

The real UE 5.8.2 Development Editor target was built successfully, then the
headless Vulkan-independent game runtime ran:

```text
Automation RunTests BiellaGames.Demo01.LifecycleCleanup; SoftQuit
```

The automation completed with `Result={Success}` and process exit code `0`.
It observed:

- two repeated `SpawnDemoActors()` calls preserved exactly two encounter
  infected and one objective manager;
- a pressure reinforcement was tagged, defeated, emitted
  `D01_SIGNAL INFECTED_RETIRE`, and was removed from the live world without
  refilling its reserved slot;
- a fresh map world reconstructed with two encounter infected, zero pressure
  infected, one objective manager, and inactive pressure state.

Evidence: [engine log](D01-045-lifecycle.engine.log),
[stdout log](D01-045-lifecycle.stdout.log), and
[validation record](D01-045-validation.json).

## Changed editable source

- `Source/BiellaGames/Private/BiellaGamesGameModeBase.cpp`
- `Source/BiellaGames/Private/BiellaDemoPawn.cpp`
- `Source/BiellaGames/Private/BiellaInfected.cpp`
- `Source/BiellaGames/Private/BiellaRival.cpp`
- matching public headers;
- `Source/BiellaGames/Private/Tests/BiellaLifecycleCleanupTest.cpp`.

Known Unreal navigation-registration/shutdown warnings remain the same
predecessor signatures; no fatal error, assertion, ensure, device loss, or
`D01_045_TEST FAIL` was observed. This is bounded Demo 01 lifecycle evidence,
not a full-content or shipping-platform memory qualification.
