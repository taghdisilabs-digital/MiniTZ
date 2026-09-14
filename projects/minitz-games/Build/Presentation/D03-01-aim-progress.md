# D03-01 upper-body aim increment

Increment: **implemented and validated**. Full D03-01: **CONTINUE**.

The existing player now aims the evaluated skeletal weapon toward the authoritative on-foot camera direction. The game thread copies the real look pitch and attachment axis into the animation sample. A bounded quaternion correction is distributed across Manny's five spine joints after foot placement, preserving the locomotion pose below the spine. Pitch follows the existing -55 to +12 degree gameplay limits, interpolates at 120 degrees per second, and acquires weight at six per second. The total correction is limited to 75 degrees. Each evaluation starts from the fresh authored pose; no previous correction accumulates. Missing required bones retain that pose.

Native measurement also exposed a reversed weapon attachment. The prop now points out of Manny's hand-local -X grip while its own +X remains the barrel axis. The gameplay camera, collision, input, ammunition and shot resolution stay authoritative. Jump, dormancy, vehicle seating and defeat clear the cosmetic aim layer; landing, waking and dismounting reacquire it. `biella.Animation.UpperBodyAim=0` retains the authored pose.

## Evidence

- `aim-build-03/result.json`: native UE 5.8.2 editor target build passed from the tested source.
- `aim-runtime-03/validation.json`: positive native scenario passed with 1,032 evaluated pose frames, seven alignment checks and six captures. It exercises level/down/up aim, an actor turn, forward movement, jump/landing, dormancy/wake, vehicle entry/exit and defeat. Standing aim preserves the capsule and evaluated foot heights; movement preserves gait and actual displacement. Qualified pitch and full 3D barrel-to-camera angle errors both peak at 0.000002 degrees.
- `aim-disabled-01/validation.json`: disabled control passed as an expected negative control, with zero aim weights and a maximum pitch error of 56.952484 degrees. Three native captures and 327 pose frames are retained.
- `aim-contact-regression-01/validation.json`: terrain contact regression passed with 1,469 pose frames and eight captures.
- `aim-animation-regression-01/validation.json`: locomotion, NPC gait, jump and lifecycle regression passed with 1,048 pose frames and nine captures.
- `aim-environment-regression-01/validation.json`: both environment scenarios passed, including native mouse shots, ammunition use, damaged/destroyed panels, Chaos debris, navigation change, traversal, hazards, power and stream return/restart.
- `D03-01-aim-final-readback.json`: the five final scenarios share 274 exact input identities. Current source, module, editor, content, logs and capture bytes were read back; every engine process exited zero with a closed log. Across 158 settled samples in four aim windows, pitch error and consecutive barrel-pitch change round to zero at the CSV's six-decimal precision. This is a settled-fixture measurement, not a claim of mathematical zero or general temporal/frame-time qualification.

The directly inspected captures and their exact identities are recorded in `aim-visual-review-01.json`. They remain `GENERATED_DRAFT`. The existing Manny integration rig, box weapon and world blockout are not accepted final art. The aim fixture covers forward movement; wider directional aiming, crowd/LOD and platform coverage remain to be qualified.

## Repairs and preservation

Build 01 exposed an ambiguous double-to-input-value constructor in the fixture; an explicit float resolved it in build 02. Runtime 01 exposed the wrong weapon-axis assumption, followed by an engine Vulkan shutdown failure; all raw logs remain. A disabled baseline then measured the original attachment nearly backward. Build 03 includes the corrected mount and a solver based on the actual barrel axis. Runtime 02 passed all native checks but its wrapper incorrectly required a setup pose before the animation instance was acquired. The wrapper now requires the actual sampled phases 2 through 15; fresh positive and disabled runs passed. Failed attempts and their exact inputs remain intact.

The optional configured local-Qwen resource supplied bounded design advice under `aim-design-01`. Local engine APIs, actual gameplay limits and native measurements determined the implementation. The final receipt supersedes the historical design review's pending validation field.

`D03-01-aim-preservation.json` verifies all four predecessor D03 manifests: 1,003 entries, including 996 unchanged entries and seven authorized source-entry changes across those manifests. Original source bytes remain in their predecessor commits. The environment runner still records 03/04 observations but protects the unchanged Project production authority independently, since 03/04 are volatile controller continuity state.

## Remaining scope and durability

Action/hit/defeat animation layers, skeletal vehicle presentation, production world/lighting/character/weapon art, broader VFX/audio, crowd/LOD/platform costs, native frame times, clean shader/material/PSO launch, supported fallback and packaged play remain unfinished D03 work. This increment does not change task identity, Project production status, task order or Engine P4-06.

Canonical editable source and raw evidence remain in this Project subtree. `D03-01-aim-file-manifest.json` records the exact files for the local increment commit. The Auto Feeder owns GitHub/Drive publication and canonical state transition; no remote publication or full-task completion is claimed here.
