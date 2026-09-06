# D02-03 — Vehicle runtime

The editable Unreal open world now supports approach, entry, driving, steering,
braking, reverse, physical collisions, shared NPC damage and safe exit through
actual player input. The car also survives match-local streaming suspension and
return with its damaged state intact, and resets cleanly through the existing
restart flow. This is the single D02-03 boundary, implementation sequence 2.3 and
runtime contract 11. No successor task or canonical status is advanced here.

## Editable implementation

`Source/BiellaGames/Public/BiellaVehicle.h` and `Private/BiellaVehicle.cpp` implement
the Chaos chassis, four raycast springs/tire forces, steering, camera, driver
relationship, collision health, streaming support and presentation. The existing
world game mode spawns one named car. Character/controller/HUD changes integrate
ordinary input, seated/on-foot state, action gates and real speed/health feedback.
`Config/DefaultGame.ini` contains bounded development handling controls.

`docs/VEHICLE_RUNTIME.md` provides controls, source locations and reproduction.
`SourceAssets/Audio/Vehicle/` and `Content/Vehicle/Audio/S_VehicleEngine.uasset`
preserve editable deterministic source and the actual imported sound. Native PCM
export matches the source's format and samples exactly. The engine loop responds
to motion; shared impact effects, lamps, wheel motion and damage tint execute in
the same runtime. Meshes, seating and sound remain development candidates.

## Runtime evidence

`D02-03-build-06-audio-testfix.log` records the final successful Editor compile/link
in 8.68 seconds, following the native-audio implementation build. The tested module
SHA-256 is `da58356b6988929a0e73f9a5178a6768a6174e521856719c8ef40dd1751bbbe8`.
Current source/content/module identities match those recorded during the final
vehicle run. The only later input-file change is the Python streaming runner's
post-process error classification, described below. Its imported runtime helpers
and launch command are unchanged, verified structurally in the final identity audit.

`runtime-05-rootfix/validation.json` is the successful final vehicle run. It uses
Unreal 5.8.2, Linux Vulkan, 1280×720, VSync off, a 60 FPS cap, variable simulation
time and no benchmark mode. These are development-host measurements, not a
shipping hardware or frame-rate qualification.

| Measured interval | Frames | Wall seconds | p95 / p99 ms | Maximum ms | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Complete recorded scenario | 2,256 | 38.685176 | 20.233 / 21.505 | 539.678 | 2,884.90 |
| Forward driving/steering | 561 | 9.354928 | 19.860 / 21.660 | 24.453 | 2,868.23 |

The car traversed 64.959 metres and reached 48.389 km/h. Four-wheel contact,
physical velocity/transform consistency, steering response, forward/reverse
braking and support hold/resume passed. A real wall collision produced a Chaos
impulse and reduced car health from 100 to 60. Both infected and rival contact
produced shared `vehicle_impact` damage and defeat. Health 73 and ammunition 60
remained unchanged through mounted travel, exit, streaming departure and return.
The 18.688-second, 48 kHz, six-channel master-submix WAV is audible and unclipped
(RMS 0.016829). This is rendered mixer output, not physical speaker capture.

The fixture sends E/W/D/A/Space/S/R through the actual player controller. It never
teleports or assigns a driving velocity to the car. It temporarily suppresses
population admission and freezes NPC behavior to isolate vehicle causality. It
uses supported on-foot relocation for approach, distant departure and return;
inserts physical walls for blocked entry/exit and impact; and briefly removes
real road collision to test the missing-support hold. Parked return additionally
requires the actual underlying road cell to unload. NPC impact targets start at
one health to isolate contact damage. Explicit damage is used only for the final
disabled-car and driver-defeat controls. Restart recreates one fresh car with no
driver and restores the original player state. These fixtures are not normal
gameplay behavior or proof of unscripted traffic.

All 22 recorded phases and 28 ordered events passed independent replay. Five
original captures were decoded and visually inspected: approach, driving, impact,
exited and disabled. The terminal overlay obscures part of the final car; raw
state/input evidence supplies lifecycle proof. `D02-03-final-visual-review.json`
records exact image identities and observations. Maximum hitches above remain
included; percentile statistics do not imply a shipping FPS target.

## Regression and integrity

`D02-03-final-replay.json` replays the canonical local raw evidence for all five
scenarios with the same final gameplay module:

- Vehicle: PASS for physical driving, contact, player restoration, streaming,
  damage, audio, defeat and restart.
- Population, four actors: PASS over 20.012 seconds of combat, all four natural
  damage sources/targets, 22 natural damage events and no capsule overlap pairs.
- Shared interaction: PASS for ten phases, twenty damage events, all six
  player/rival/infected damage directions and four defeats.
- World streaming: PASS over 13,586 frames and 165.805 seconds, with 51 cell loads
  and 39 unloads, p95 14.084 ms and p99 15.261 ms.
- D01-42 feedback: PASS for all twelve phases, live rendered particles, six
  decoded captures and five distinct audible, unclipped mixer cues. This older
  feedback fixture uses a fixed simulation delta and supplies functionality proof.

The original streaming wrapper reported FAIL on two copies of the exact Unreal
startup diagnostic about `FDataflowToolNodeSnapshot::Date` initialization. The
engine scenario itself succeeded and exited cleanly. The wrapper now excludes
only that full diagnostic before the first D02 world/scenario marker. Unknown
startup errors, any scenario errors, and fatal/assert/ensure/test failures still
fail. The original FAIL report and earlier replay are preserved unchanged; the
final replay applies the narrower filter to the complete original log.

The older D01-42 runner hashed stdout before its detached UnrealTraceServer
finished writing. The final audit verified its entire 359,642-byte recorded
prefix exactly, inspected the 770 appended shutdown bytes and confirmed there
were no remaining writers. `D02-03-feedback-log-finalization.json` preserves both
identities and the appended text. Full-log replay passed; the original report
was not rewritten.

`D02-03-final-unit-tests.log` records eight passing tests for source audio,
collision transition sampling and error classification. The passing raw vehicle
baseline was also accepted while all twelve independently corrupted copies were
rejected (`D02-03-verifier-negative-controls.json`): missing frames, nonphysical
movement, lost wheel contact, player-state corruption, active parked simulation,
missing support hold, silent sound, blank capture, missing input, missing rival
contact, missing event and fixed-timestep substitution. Originals were untouched.

`D02-03-final-input-identities.json` checks every recorded before/after source,
asset, module, protected-authority and regression-tool identity. All gameplay
bytes still match; its exact recorded/current Python filter delta is disclosed.
`D02-03-final-audio-integrity.json` verifies source/generator hashes, native asset
identity and the retained native PCM export.

Earlier build/runtime/audio failures and their repairs remain preserved. The
configured local Qwen resource was routed and a bounded review attempted; its
saved output includes invented APIs and truncation and is not accepted as an
implementation or validation verdict. Current local source, build and runtime
evidence determine this result. Task-filtered failure records are preserved in
`D02-03-observed-failures.jsonl`; the global ledger is not rewritten.

## Preservation and handoff

`D02-03-preservation.json` checks 1,030 baseline files: 1,021 unchanged and exactly
nine expected integration/filter modifications. Existing maps, predecessor
assets/evidence and all three protected 03/04/PRODUCTION records retain their
bytes. Engine P4-06 remains `INCOMPLETE_DEFERRED`. The two state-file keys in the
baseline resolve at repository root, as recorded in that audit.

`D02-03-final-archive.json` verifies 52 copied raw evidence/media files totalling
32,860,114 bytes against the artifact originals by size and SHA-256. Vehicle and
regression copies live beside this document; the original D01-42 logs/report
remain at `Build/Demo01/D01-042-runs/20260906T004514.998286Z/`. Their exact final
stdout identity is in the finalization report. Original absolute paths inside
reports retain provenance. Captures and audio remain `GENERATED_DRAFT`.

This result qualifies bounded vehicle mechanics in the current playable blockout.
It does not claim AAA vehicle art, finished animation, production handling,
traffic AI, shipping performance, a new standalone package or cross-process
persistence. The existing non-editor package limitation is unchanged.

The task's implementation and evidence are committed locally. The Auto Feeder
owns canonical GitHub/Drive publication, remote readback and state transition
under the current task instruction; no publication or successor advancement is
claimed by this boundary.
