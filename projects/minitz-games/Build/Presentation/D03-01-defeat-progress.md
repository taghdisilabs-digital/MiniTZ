# D03-01 cosmetic defeat presentation increment

Increment: **implemented and validated**. Full D03-01: **CONTINUE**.

On-foot lethal gameplay events now preserve the character's evaluated pose, blend into the installed Manny front-death reaction, and hand the cosmetic skeleton to world-contact physics after 0.18 seconds. The pawn-owned presentation copies the role attachments and team color, ignores root motion, and expires after 3.1 seconds. Health, combat eligibility, the original live mesh and the gameplay capsule still enter their existing defeated state immediately.

The cosmetic bodies collide only with static world geometry through `PhysicsOnly`; they ignore pawns and visibility queries and cannot affect navigation. The separate absolute mesh transform prevents the fall from moving the gameplay capsule. Repeated lethal events do not restart it. Expiry, dormancy, actor destruction and `biella.Animation.Defeat=0` remove it; waking or re-enabling does not replay a past death. Seated defeat retains the existing hide fallback pending vehicle presentation work.

## Native evidence

- `defeat-build-02/result.json`: UE 5.8.2 editor target compiled successfully in 23.977 seconds. `defeat-build-readback-01/validation.json` confirms UBT considers the exact tested source up to date, with identical source/content/module identities before and after the 3.499-second dependency check.
- `defeat-runtime-02/validation.json`: the native 19-phase fixture passed on the existing streamed playable map. A real lethal player shot drives the first fall. The 110 sampled falling frames show head descent of 136.485 cm and pelvis descent of 75.769 cm. Initial bone-position handoff error and gameplay capsule drift both round to zero at six-decimal precision.
- Native static-road contact places head and pelvis at 14.622 and 16.098 cm above the supporting floor. Over the next half-second they move 0.764 and 1.474 cm, below the 3 cm settled-pose bound. The fixture verifies physics-only contact, query/pawn isolation, lifetime cleanup, repeated-event rejection, dormancy, destruction, live disabling, no replay and player defeat.
- `defeat-disabled-01/validation.json`: expected negative control passed. All 251 measured control frames contain no cosmetic mesh; authoritative lethal events and cleanup still pass.
- `defeat-action-regression-01`, `defeat-animation-regression-01`, `defeat-environment-regression-01` and `defeat-feedback-regression-01`: all passed. The feedback regression covers all 12 original phases, six captures and five decoded unclipped native mixer recordings.
- `D03-01-defeat-final-readback-01.json`: passed exact readback of all five modern runtime reports, their logs, pose files and 26 decoded captures. They share 289 identical source/build/content identities. Legacy feedback shares 106, including all current source/config/build identities. Its original stdout prefix and 770-byte late trace-daemon suffix are preserved and verified against the closed log.

`defeat-visual-review-01.json` records inspection and exact identities of the live, falling and settled native images. Captures remain `GENERATED_DRAFT`. They support the runtime measurements and are not final character/world/weapon art acceptance. Screenshots run in separate events from the uninterrupted quantitative fall window.

## Asset traceability and observed repairs

`SourceAssets/Characters/UE58Defeat.provenance.json` identifies the front-death clip's 24-package closure. `UE58DefeatPhysics.provenance.json` verifies the already present matching Manny physics asset and its 23-package closure. Exact installed Epic UE 5.8.2 source bytes and local copies pass readback. Five additional death clips remain preserved diagnostic candidates; only Front 01 drives this increment. Their exact copies and metadata remain under `defeat-candidates-01` and the canonical Content paths.

The configured local Qwen resource supplied bounded design assistance under `defeat-design-01`. Its invented API details were rejected; installed engine declarations and native results determined the implementation. Asset probe 01 encountered a script-permission failure; probe 02 passed after the bounded permission repair. The first animation-only runtime failed real pelvis descent (9.038 cm), despite exact pose handoff and zero capsule drift. Native compressed-pose probes ruled out retarget translation and showed that all six installed death clips are initial reactions. The world-contact physics continuation then passed in runtime 02. Failed attempts, the failed-run Vulkan shutdown assertion and all raw probe evidence are retained.

`D03-01-defeat-preservation.json` verifies 1,271 predecessor manifest entries against their original Git blobs: 1,257 are unchanged in the current worktree and 14 are authorized D03 source extensions across those manifests. An initial preservation check needed normalization of historical `size`/`bytes` fields; the retry passed without altering earlier receipts.

## Durability and remaining work

This increment qualifies representative on-foot defeat integration and static road contact. Other directional and interaction actions, seated/vehicle presentation, final production art/lighting, broader VFX/audio, crowd/LOD and platform costs, native frame-time measurement, clean shader/material/PSO behavior, supported rendering fallback and packaged play remain D03 work. No full D03 completion, final art acceptance or shipping performance claim is made.

Canonical source and raw evidence remain in this Project subtree. `D03-01-defeat-file-manifest.json` defines the exact local commit scope. The Auto Feeder owns GitHub/Drive publication and canonical state transition. Task identity, Project production status/order and Engine P4-06 are unchanged.
