# D03-01 — seated skeletal driver and steering grip

**Increment validation: PASS. Full D03-01: CONTINUE.**

The existing playable vehicle now seats the shared skeletal player with bent
knees, planted footwell contacts and hands that follow the cosmetic steering
wheel. The final pose uses the same animation proxy and authoritative mount,
drive, exit and defeat state as the existing gameplay. No new showcase scene
or physics controller was added. Captures and the authored wheel remain
`GENERATED_DRAFT`; installed character and vehicle art remain integration
resources rather than accepted final art.

## Editable implementation

`BiellaDriverPose.*` applies a final cosmetic pelvis placement, four two-bone
IK chains without stretching, wrist orientation and reference-based finger
curl. The game-thread sample copies attachment-local seat and wheel transforms
for worker evaluation. Every frame starts from the input pose, so no pose error
accumulates. Missing limb chains keep that input pose; missing finger joints
are skipped individually. This does not qualify every reduced character LOD.

The wheel is project-authored, reproducible Blender geometry with editable
`.blend`, FBX, generator and native importer in `SourceAssets/Vehicles/` and
`Content/Python/`. The canonical saved asset is
`Content/Vehicles/Presentation/SM_DriverSteeringWheel.uasset`. Its source,
import and saved bytes are identified by `DriverSteeringWheel.provenance.json`.
Wheel rotation follows existing steering input; it has no collision or
navigation participation. Native body geometry and reference bones used for
fit remain under `seat-geometry-02/`.

`biella.Animation.DriverPose=0` retains the existing mounted blockout fallback.
Vehicle rig fallback also disables the cockpit and seated skeletal pose.
On-foot pose, weapon visibility, actions and contacts restore after exit.
Mounted streaming characters still tick their shared cosmetic lifecycle;
their existing mounted early return continues to suppress floor snapping.
The character mesh waits for the vehicle tick before copying wheel state.
Gameplay capsule, mount transform, movement authority and Chaos chassis are
unchanged.

## Validation

| Evidence | Result |
| --- | --- |
| `seat-build-06/result.json` | Native Linux Development editor build PASS, 10.58 s; all 83 source identities unchanged |
| `seat-runtime-05/validation.json` | PASS: 2,343 driver frames, 1,456 stable seated frames, 64 fallback frames |
| `seat-disabled-02/validation.json` | EXPECTED_NEGATIVE_CONTROL: zero skeletal seated evaluations with driver pose disabled |
| `seat-animation-01/validation.json` | PASS: 1,002 locomotion/jump/lifecycle pose frames |
| `seat-aim-01/validation.json` | PASS: 954 aim pose frames, including mount cancellation and exit restoration |
| `seat-actions-01/validation.json` | PASS: 943 shot/hit pose frames, including seated cancellation and exit restoration |
| `seat-readback-01/result.json` | Fresh Unreal process loads saved wheel; exact asset bytes unchanged |
| `D03-01-seat-final-readback-01.json` | 325 common and 332 unique current input identities; native source/build lineage, five asset inputs and 35 decoded captures PASS |
| `D03-01-seat-preservation.json` | 1,554 predecessor manifest entries verified; 1,529 unchanged and 25 authorized source extensions retain original bytes in prior commits |

The driving scenario uses actual input and Chaos state through 28 existing
events: approach, mount, both steering directions, support hold, impact,
cosmetic fallback, exit, reentry, vehicle disable, seated defeat and restart.
Final rendered bones are joined to physics telemetry by frame and phase.
Independent bounds on actual middle-finger joints and thumb height verify
that the grip spans the rim instead of merely placing wrists at a target.
The maximum recorded pelvis, feet and wrist target errors round to 0 cm;
maximum limb-length deviation is 0.000076 cm and grip bounds violation is 0.
Both final cockpit views were directly reviewed; hands now grip the wheel.

The positive run drove 6,479.73 cm and reached 48.27 km/h. Its 559 driving
frames measured wall p50/p95/p99 of 16.80/19.39/21.04 ms at the explicit 60 fps
cap. These are native integration frames with streaming, readback and capture
costs, not clean performance or shipping qualification. No generated frames
were used. Existing gameplay audio remained present (18.688 s, 48 kHz,
six channels, RMS 0.01681); this adds no new audio production claim.

## Preserved corrections and limits

Earlier failed build/import/readback attempts and runtime failures remain in
their original `seat-*` directories. They include a mounted tick visibility
bug, the visually rejected hanging-hand pose, and a fixture that checked
wheel fallback before the next actor tick. The final fixture waits for the
representation state to settle and still checks steady-state fallback.
No failed raw evidence was rewritten. The configured Unreal assistance route
and optional local Qwen timeout are retained under `seat-design-01/`; native
Blender and Unreal supplied geometry and runtime evidence. Failure diagnostics
remain in the canonical production `failures.jsonl`.

Remaining D03 work includes other directional/interaction animation,
transition/LOD/crowd costs, final world/lighting/character/weapon/vehicle art,
broader VFX/audio, native frame qualification, and clean shader/material/PSO,
supported fallback and packaged play. The world is still visibly blockout.
Engine P4-06 remains `INCOMPLETE_DEFERRED`; no later task has been started.

All implementation and evidence remain at their canonical Project paths.
The exact file manifest and local commit are supplied for the Auto Feeder,
which owns GitHub/Drive publication and canonical state transition. This
receipt makes no remote publication or full D03 completion claim.

## Reproduction

Use fresh output directories from the Project root and preserve all prior
evidence. Build the current `BiellaGamesEditor Linux Development` target,
then run `tests/run_d03_01_driver.py --output <fresh-path>` and the same command
with `--disabled`. Run the existing animation, aim and actions runners with
fresh output paths. The native importer supports `-D03VerifyDriverWheel` for
read-only saved-asset inspection; its exact command is retained in
`seat-readback-01/command.json`.
