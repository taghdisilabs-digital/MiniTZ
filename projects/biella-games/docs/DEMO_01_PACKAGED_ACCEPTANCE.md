# Demo 01 packaged playable acceptance

D01-48 qualifies the completed D01-46 Linux x64 Development archive through the
actual game executable, cooked map/assets and existing runtime automation. The
runner launches every suite from a separate clean extraction under `/tmp`, as
the Unreal runtime account, with a bounded process deadline. It does not require
the editor or read loose project content during play.

From the Project directory:

```sh
python3 tests/run_d01_048.py
python3 tests/verify_d01_048.py Build/Demo01/D01-048-runs/<attempt>/validation.json
```

The archive SHA-256 must match D01-46/47. The runner also checks that gameplay
source, configuration and content have not changed since the package commit,
hashes the tested source inputs, compares executable/pak/launcher bytes before
and after each session, and preserves the protected production records. A
source change requires a separately qualified package identity; passing an
arbitrary replacement archive cannot silently supersede the accepted package.

| Packaged scenario | Acceptance evidence |
| --- | --- |
| DeterministicPlaytest, separate NullRHI and Vulkan processes | Seven ordered checkpoints: clean Active baseline, Enhanced Input movement, first weapon defeat, objective Success, bound R restart, autonomous infected melee Failure, bound R restart. Exact semantic telemetry comparison between processes. |
| SharedInteraction, Vulkan | Six directed player/rival/infected damage edges, weapon collision, cooldown/damage guards, autonomous targeting, defeat and stopped actors. |
| PressureResponses, Vulkan | Authoritative pressure transitions drive lighting, infected movement and collision-safe reinforcements; reconstruction restores floor collision/navigation. |
| RivalNavigation, Vulkan | Real navigation and swept movement, combat positioning, obstacles, path recovery and stopped defeated actors. |
| VisualReadability, Vulkan | Possessed third-person presentation, moving player, aim geometry, UMG layout and six decoded gameplay/terminal frames. |
| EventFeedback, Vulkan and software audio mixer | Gameplay-driven live Niagara and spatial feedback, five decoded mixer recordings, six frames, restart and effect cleanup. |

The core uses the unchanged D01-39 seed-1337 fixture and a fixed 60 Hz simulation
step. Its success targets and rival are stationary; the failure encounter runs
infected AI. Health, ammunition, cooldowns, objective progress and terminal
outcomes are produced by gameplay. Shared combat, navigation and pressure are
qualified by the complementary suites. Pressure is applied through the
production authoritative API; this does not claim a new time-driven escalation
mechanic. Visual and feedback fixtures deliberately arrange scenarios and are
supporting evidence alongside the core playthrough.

Evidence is retained under `Build/Demo01/D01-048-runs/<attempt>/`, including
commands, source/package identities, logs, JSONL telemetry and verification.
Runtime PNG/WAV artifacts are placed under
`/root/biella/artifacts/games/D01-048/<attempt>/` for inspection and remain
`GENERATED_DRAFT`. Archive extractions are retained for executable/pak readback.
Failed attempts remain distinguishable from successful qualification.

This is automated acceptance of the existing first playable slice on the Linux
development host. It does not change the accepted Windows-first target, claim
Windows/Shipping qualification, owner visual acceptance, a human playtest,
physical speaker output, or final AAA content quality. Fixed simulation steps
are not measured native rendered FPS; the separately measured D01-44 performance
evidence retains its original hardware and runtime scope.

The Auto Feeder owns publication and production-state transitions. This runner
never advances the task or writes `03`, `04`, or `PRODUCTION.md`.
