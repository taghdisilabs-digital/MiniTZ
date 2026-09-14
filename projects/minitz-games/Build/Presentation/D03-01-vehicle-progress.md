# D03-01 skeletal vehicle exterior increment

Increment: **implemented and validated**. Full D03-01: **CONTINUE**.

The existing Chaos ray-suspension vehicle now drives an editable skeletal exterior: suspension links, a rigid body and four detailed tires. The render-only `UBiellaVehiclePresentation` receives the vehicle's existing contact centers, steering and accumulated wheel spin. It evaluates the actual installed rig hierarchy, maintains linkage endpoints, and scales each tire to the authoritative 38 cm radius. Rigid tire attachments cancel each wheel's authored orientation, including the different rear-left basis. The body attaches to the unrotated `OffroadCar` root.

The vehicle still owns its chassis, four suspension rays, forces, controls, health, entry/exit, streaming and restart lifecycle. New presentation components have no collision or navigation influence. Damage updates both suspension and body paint immediately, including collisions after the pre-physics tick. Shared brake and head lamps follow the body; the original primitive representation remains available through `biella.Vehicle.SkeletalPresentation=0`. Parked dormancy hides both representations and stops rig evaluation.

## Native evidence

- `vehicle-build-05/result.json`: UE 5.8.2 editor target compiled successfully in 8.790 seconds. Final readback verifies all 81 build source files against the runtime source and records the exact tested native module.
- `vehicle-runtime-03/validation.json`: the existing 28-event input/Chaos driving scenario passed on the streamed playable map. Its 2,257 pose frames include 1,895 visible rig frames, 66 live fallback frames and 296 dormant frames. Travel reached 6,488.905 cm and 48.305 km/h. Real wall collision reduced health to 60; exit, walking, reentry, NPC contact, vehicle disable, driver defeat and world restart all passed.
- Native assertions and CSV replay check evaluated wheel centers, steering axes, spin, three suspension-link endpoints per wheel, body and tire attachment, rendered mesh transforms, 38 cm tire radius, root isolation, paint, exclusive visibility, dormancy and restart cleanup. Position, radius, root and paint errors round to zero at six decimals. The largest angular error is 0.000006 degrees. The test observes actual rigid mesh components as well as bones, preventing the missing-body/tire blind spot found in the first attempt.
- `vehicle-disabled-01/validation.json`: expected negative control passed through the same gameplay scenario. All 2,255 pose frames have zero rig evaluations and zero visible skeletal/rigid exterior parts; 1,959 fallback frames and 296 dormant frames are observed.
- Both scenarios decode an audible, unclipped six-channel 48 kHz native mixer recording. The positive recording lasts 18.688 seconds. This preserves the existing vehicle engine and impact feedback coverage.
- `D03-01-vehicle-final-readback-01.json`: both reports share 323 identical current runtime input identities, including the native module, source, configuration and assets. Closed logs, CSV replay, all ten decoded 1280x720 captures, build source and exact installed/local asset bytes pass readback.

The positive driving interval contains 561 native frames with p50 16.731 ms, p95 20.273 ms and p99 21.275 ms. This scenario is capped at 60 fps and includes streaming, capture and telemetry work. The complete sample includes a 767.556 ms maximum frame. These numbers are integration measurements, **not** clean frame-time, shader/PSO or package qualification; no generated frames are used.

## Traceability and observed repairs

`SourceAssets/Vehicles/UE58Offroad.provenance.json` preserves the installed Epic UE 5.8.2 rig's 20-package closure. `UE58OffroadParts.provenance.json` preserves the body/tire 24-package closure; together they contain 28 unique exact local assets. `Content/Python/inspect_vehicle_rig.py` reads the 49-bone hierarchy, material parameters and rigid mesh bounds in native Unreal. `vehicle-assets-05` passes both closures. These assets are `INTEGRATION_RESOURCE_NOT_FINAL_VEHICLE_ART`; no template vehicle pawn or second physics controller was imported.

The routed local Qwen assistance is retained under `vehicle-design-01`; its invented bone names and API claims were rejected against installed source and native metadata. Build 01 exposed the actual poseable-mesh API and `TObjectPtr` handling; build 03 exposed another pointer deduction error. Both were repaired without changing gameplay. Runtime 01 exposed a one-frame damage-tint delay. Visual review then established that the installed skeletal asset contains suspension only: body and tires are separate static meshes. Their exact import and render-component checks closed that gap. FBX commandlet exports in asset probes 03/04 failed an engine `MeshObject` assertion; native bounds and the installed rigid assets supplied the needed facts without export. Runtime 02 passed after these repairs; runtime 03 additionally corrects the old oversized, outboard lamp blocks and their capture timing. All raw failed attempts and subsequent evidence remain preserved.

`vehicle-visual-review-01.json` records inspection of approach, driving and impact captures. The exterior renders with its materials and tires, and brake markers sit on the rear frame. The seated driver still visibly uses the earlier floating blockout; this is an explicit remaining defect. The surrounding world also remains visibly blockout. Captures are `GENERATED_DRAFT`, not final art acceptance.

`D03-01-vehicle-preservation.json` verifies all 1,406 predecessor manifest entries against their original Git blobs: 1,392 remain byte-identical locally and 14 are already authorized D03 source/test extensions. The initial check's overly narrow source-only allowance was corrected using the exact prior preservation record and current committed test bytes.

## Durability and remaining work

The immediate next presentation boundary is the seated driver: `BiellaGamesCharacter::MountVehicle`, `BiellaDemoPawn::RefreshCharacterPresentation` and the shared character animation instance. Preserve authoritative entry/exit, collision, controls and death behavior while replacing the visual blockout and fitting the driver to the real seat. Do not repeat the qualified contact, aim, action, defeat or exterior increments without material invalidation.

Other directional/interaction animation, final production world/lighting/character/weapon/vehicle art, broader VFX/audio coverage, crowd/LOD costs, native frame-time qualification, clean shader/material/PSO launch, supported rendering fallback and packaged play remain D03 work. No full D03 completion or shipping performance claim is made.

Canonical editable source and raw evidence remain in this Project subtree. `D03-01-vehicle-file-manifest.json` defines this local commit scope. The Auto Feeder owns GitHub/Drive publication and canonical state transition. Task identity, Project production status/order and Engine P4-06 remain unchanged.
