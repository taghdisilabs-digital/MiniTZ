# D01-48 — Full end-to-end playable acceptance

Result: **PASS** for the existing Demo 01 Linux x64 Development package.
Executed 2026-09-05; task boundary is D01-48 only.

Seven fresh packaged processes passed. The two complete playthroughs exercised
`clean launch → possessed movement input → collision-resolved weapon hits →
objective success → bound R restart → autonomous AI melee failure → bound R
restart → clean Active match`. Complementary packaged scenarios validated
shared combat, navigation, pressure, rendered presentation and audio/VFX.

## Exact tested implementation

- Source HEAD: `c4c981eca4bc3cc6ee36da2ccee36d58a7ef2bc3`, with 73 gameplay
  source/configuration/content files hashed before and after execution.
- Package source/evidence commit: `00c7243077403d9ebfb812318cd23a3a5b13641f`.
  No gameplay source/configuration/content delta exists between that commit and
  the tested worktree; no gameplay rebuild or replacement package was needed.
- Archive: `/root/biella/artifacts/games/D01-46/BiellaGames-Linux-x64-D01-46.tar.zst`.
  SHA-256: `c1085849f0919865a40191b9a40a5883be662b032766d4ef6620fa4f4b315bc8`.
- Executable SHA-256: `b23aacd3ab55b236ad91830e1ffba125ae51b961a6e989d63637c2c1bc696b59`.
- Cooked pak SHA-256: `061c0df4c76e96e72781202a690a906dbc328ebdcd7f6008d7327b2ed4d40a06`.

Each suite extracted this archive independently, launched its own
`Linux/BiellaGames.sh` as `unreal` from its extraction directory, mounted the
gameplay pak and exited cleanly with process code zero and Unreal automation
success. The launcher, executable and pak remained identical across all seven
extractions and after gameplay. No editor runtime was used.

## Observed acceptance

| Scenario | Result |
| --- | --- |
| Core playthrough, NullRHI | PASS: seven checkpoints, success/failure and two input-driven map reconstructions |
| Core playthrough, Vulkan | PASS: same ordered 56-event semantic timeline as NullRHI |
| SharedInteraction, Vulkan | PASS: all six directed player/rival/infected damage edges and ten ordered phases |
| PressureResponses, Vulkan | PASS: eleven phases, authoritative world lighting/movement/spawn consequences, collision-safe reinforcement and reconstructed navigation/floor |
| RivalNavigation, Vulkan | PASS: nine phases including detour, retreat, dynamic obstruction, reopened route and defeated stop |
| VisualReadability, Vulkan | PASS: live movement, third-person aim/presentation, UMG geometry, six decoded 1280×720 frames and terminal/restart states |
| EventFeedback, Vulkan/audio mixer | PASS: gameplay-driven effects, four positive live particle samples, twelve feedback phases, six decoded frames and five distinct non-silent, unclipped PCM recordings |
| Verifier rejection tests | PASS: 22 package/evidence checks plus 19 reused core telemetry checks |
| Structural check | PASS: `completed=47/50 current=D01-48`; protected metadata unchanged |

Each core process produced six real weapon hits, fifteen damage events, three
defeats, objective success, autonomous infected-caused player failure and two
restart requests. Each reconstructed baseline restored health 100, ammo 60,
two infected, objective progress zero and pressure zero. The current package's
cross-renderer semantic trace SHA-256 is
`438cd2e30b6f67f2fe6319a51451dfd0046264638ef8065e5acbb4b74b49a7af`.
The fixed 60 Hz simulation step is not a native FPS measurement.

## Reproducible evidence

- [Final validation and exact identities](D01-048-validation.json)
- [Original seven-process execution manifest](D01-048-runs/20260905T164050.070724Z/validation.json)
- [Core NullRHI telemetry](D01-048-runs/20260905T164050.070724Z/core-nullrhi/telemetry.jsonl)
- [Core Vulkan telemetry](D01-048-runs/20260905T164050.070724Z/core-vulkan/telemetry.jsonl)
- [Package verifier tests](D01-048-verifier-selftest.log), [core verifier tests](D01-048-core-verifier-selftest.log)
- [Editable runner and fixture documentation](../../docs/DEMO_01_PACKAGED_ACCEPTANCE.md)

Runtime PNG/WAV outputs and their hashes are indexed in the final validation
under `/root/biella/artifacts/games/D01-048/20260905T164050.070724Z/`.
The active-play, combat, success and failure frames were inspected: they show
the actual third-person blockout actors/arena, readable HUD and centered
terminal overlays. All media remains `GENERATED_DRAFT`.

Replay the final qualification with:

```sh
python3 tests/verify_d01_048.py Build/Demo01/D01-048-validation.json
```

The initial package-core capability run is retained in
`D01-048-runs/package-core-initial/`. All gameplay executions passed. The
verifier was strengthened after the seven-process run to validate its own
recorded tooling identities. The original execution manifest is unchanged;
the final validation separately records that manifest's hash, its original
tool identities, the final verifier identities and successful independent
replay. Replaying the original manifest with changed verifier bytes correctly
fails the tooling identity check.

## Scope and retained diagnostics

The core uses the existing controlled D01-39 fixture: stationary success
targets/rival, real Enhanced Input/weapon damage/objective transitions, and
autonomous infected AI for failure. Complementary suites exercise autonomous
shared combat and navigation. Pressure is applied through the authoritative
production API. Visual/feedback scenario arrangements support the gameplay
proof; screenshots do not substitute for the playable loop.

Known authored navigation-registration/crowd warnings and the predecessor
Vulkan shutdown `Found 1 unfreed allocations!` diagnostic remain visible.
Navigation and collision behavior passed in the packaged runtime. No runtime
Error/Fatal, assertion, ensure, crash or failed automation signature was found.

This is automated first-slice acceptance on the existing Linux development
host. Primitive blockout assets and dark background regions remain visible;
this does not claim final realistic AAA content, owner visual acceptance,
human playtesting, Windows/Shipping qualification or physical audio output.
D01-44 performance evidence retains its original scope and is not recast as a
new package performance measurement.

All completed predecessors are preserved. Engine P4-06 remains
`INCOMPLETE_DEFERRED`. `03`, `04` and Project `PRODUCTION.md` were not edited.
Only task-scoped runner/verifier/documentation/evidence are committed locally;
the Auto Feeder owns publication and the canonical state transition.
