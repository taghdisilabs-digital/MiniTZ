# D03-01 — skeletal animation and character readability increment

**Increment validation: PASS. Full D03-01: CONTINUE.**

The shared player, rival and infected pawn now renders an evaluated skeletal
character on foot. Rifle and unarmed locomotion respond to actual movement;
the player's jump pose follows the existing gameplay jump clock. Native
movement, collision, combat, vehicle and streaming authority remain intact.
This is an implementation increment, not final Biella character art or AAA
acceptance. All visual captures remain `GENERATED_DRAFT`.

The prior rendering increment remains at commit
`ffdd4babd2196151ad33a85b2fd2a0db28b5dd90`. Its 457 manifest entries, including
exact symlink targets, are unchanged. No 03/04 task identity, Project PRODUCTION
metadata, predecessor evidence, map or configuration bytes were changed.

## Editable implementation

- `Source/BiellaGames/Private/BiellaCharacterAnimInstance.cpp` and its public
  header implement the native animation proxy. Game-thread displacement
  sampling drives directional/speed blending. Worker evaluation consumes a
  copied sample. Root motion does not move the gameplay capsule.
- `BiellaDemoPawn` owns the cosmetic rig, team-tinted dynamic materials and
  front/back spine-attached role marks. Player/rival/infected retain the one
  band, two bands and cross distinction. Dormancy, defeat and vehicle seating
  cancel on-foot presentation. The existing fitted seated blockout remains;
  exit restores the skeletal character and hand-attached placeholder weapon.
- `SourceAssets/Characters/UE58Mannequin.provenance.json` identifies 63 imported
  assets totaling 101,839,589 bytes. Every local asset matches its installed UE
  5.8.2 source exactly. The dependency closure includes skeleton preview
  resources; this does not add a new playable character. These are integration
  resources, not accepted final character art.
- `Content/Characters/Presentation/BS_RifleLocomotion.uasset` contains 27 saved
  samples using compatible non-additive rifle idle, directional walk and jog
  clips. The original unarmed blend space and clips are unchanged.
- `Content/Characters/Presentation/M_CharacterReadability.uasset` and
  `MI_Character_01/02.uasset` preserve the mannequin's texture inheritance and
  lit surface graph. A 0.10 color-matched fill preserves the shadow silhouette.
  Exact native authoring and read-only verification scripts live in
  `Content/Python/build_production_locomotion.py`,
  `build_production_character_material.py` and `inspect_production_animation.py`.

## Final validation

| Evidence | Result and scope |
| --- | --- |
| `animation-green-build-06/build.log` | Native Linux Development editor build PASS, 9.82 seconds |
| `animation-assets-01/readback.json` | All 63 imported native assets load; project dependencies resolve |
| `animation-assets-03/readback.json` | Fresh-process saved rifle blend-space readback PASS, 27 samples |
| `animation-material-02/readback.json` | Fresh-process material graph, bounded fill, parent and texture readback PASS |
| `animation-runtime-04/validation.json` | Native animation scenario PASS, 971 pose frames and nine captures |
| `animation-environment-regression-02/validation.json` | Environment regression PASS, 1,456 frames and five captures |
| `animation-readability-regression-03/validation.json` | Native readability regression PASS at 1280×720 and 1920×1080, six captures each |
| `animation-material-02/shadow-green.json` | Fixed-camera shadow image check PASS at both resolutions; earlier dark candidates fail the same thresholds |
| `D03-01-animation-final-readback.json` | Final test logs/captures and current input/authority identities rehashed after the processes finished |
| `D03-01-animation-preservation.json` | Prior rendering evidence, imported source identities and protected authority preserved |

The animation scenario uses real Enhanced Input W/D/S and Space. It checks
movement in each requested direction, changing evaluated foot bones, jump
height/pose and return to ground; it also checks actual NPC movement, role
selection, dormancy/wake, defeat, vehicle entry/exit and cosmetic lifecycle.
Population AI is explicitly frozen for this controlled animation fixture.
The environment regression separately exercises live interaction, shooting,
Chaos destruction, navigation, traversal, hazards and stream-out/return state.
Its 16.85 ms median frame time is Development causal evidence; it is not
shipping or frame-rate qualification.

Direct visual review covered final forward movement, jump, NPC role markers
and shadowed player captures at both resolutions. Vehicle seat and dismount
were also reviewed in the preceding candidate; the final lifecycle checks
pass. The lit world still has blockout surfaces, a black horizon and an
unfinished weapon/vehicle presentation.

The shadow check examines a fixed lower-body region that excludes the bright
floor behind the upper torso. The fraction of sufficiently bright blue pixels
rose from 0.18%/0.19% to 30.54%/30.21%. This detects the observed regression;
it does not qualify arbitrary lighting or accessibility.

## Retained diagnostics and limits

All failed/rejected attempts remain in their original evidence directories.
They include missing-rig RED evidence, a Python blend-sample copy issue,
compile/API corrections, an overbroad imported root-motion assertion, two
role-mark fit errors and the first insufficient shadow fill. The 0.035 fill
asset and source are preserved under `animation-material-01/rejected-fill035`.
Two local Qwen requests timed out; controller review and installed Unreal
source inspection are documented in `animation-review-01/controller-review.md`.
No independent provider review approval is claimed. Failures/retries were
recorded in the canonical runtime `failures.jsonl`.

Full D03-01 still requires production world/rendering art and lighting, final
character/weapon art, terrain foot placement/IK, aim/action/hit/defeat layers,
skeletal vehicle presentation, broader transition/LOD/crowd qualification,
production VFX/audio and launch-platform validation. Engine P4-06 remains
`INCOMPLETE_DEFERRED`. No later task has been started.

All files remain at their canonical Project paths. The separate animation
manifest inventories exact bytes. This increment is committed locally for
the Auto Feeder, which owns GitHub/Drive publication and canonical state
transition under the current task instruction. No remote publication or full
task completion is inferred here.
