# D17-02 traversal and camera evidence

D17-02 remains in progress. This record distinguishes real route measurements
from the required final visual acceptance. D17-01 selection and accepted
movement, combat, AI, objective and streaming rules are preserved.

| Observed gap | Task-scoped repair | Evidence / disposition |
| --- | --- | --- |
| Bare ramp edges and an unsupported-looking terrace | Authored fitted nonslip steel decking, raised edge strips, parapet cassettes, six ground-bearing columns and bracing. Preserved original ramp/deck/parapet transforms and collision profiles. | Editable Blender/FBX/native assets; fresh-process readback in `environment/terrace-assets-04`; game/editor build, affected cook, stage/archive and installed membership readback pass. Actual new geometry appears in `raw/terrace-720-04` and `raw/terrace-1080-02`. |
| Route lacked instrumented full traversal proof | Opt-in native end-frame camera, capsule, near-plane, projection, movement and readiness measurements; X11 route driven by live observations. | `terrace-720-04` completes 35 stages without camera/collision faults. `terrace-1080-02` also completes all stages, but exposes the panel-corner camera issue below. These runs use game-02; later camera/HUD changes require fresh evidence. |
| Upper-body sightline crosses the service-panel corner one frame before the normal arm retracts | Before calculating the actual player view, sweep the camera sphere from upper body to the regular arm socket. Rebase each frame; the camera component remains the real view and weapon-trace origin. | `terrace-1080-02`: native frame 961, D02Environment01, 0.0243739 s; normal arm retracts on frame 962. `game-03` compiles the repair. `framing-720-05` completes the full route with zero upper-body occlusion, camera overlap or near-plane intersections; subsequent full 1080p runs `approach-full-1080-01` and `nanite-full-1080-02` complete 35/35 stages with zero measured camera/collision/framing faults. Each remains bound to its own content revision. |
| Large status/countdown panels obscure route framing and the player's feet | Compact objective/remaining-threat hierarchy at top-left; health/ammo at bottom-right; lower centre reserved for contextual interaction text. Preserve actual HUD state binding and accessibility scaling. | `game-03` builds. Opaque card area shrinks from 13.74% to 6.04% at default 720p scale. Actual `framing-720-05` panel, hall, ramp and overlook frames show readable text and unobstructed player/feet; native measurements report zero head/feet/centre frame loss. Source area is supporting evidence, not a visual verdict. |
| Ordinary-input automation could fire the final infected shot before completing the return circuit | Read the same objective progress as the HUD and withhold that optional shot. When the final infected blocks an optional rival engagement, explicitly record the engagement as deferred and resume movement. | `framing-720-01/02` ended in native Success; `framing-720-03` waited within melee range and ended in native Failure. `framing-720-04` exposed a distant-rival shot gate that withheld immediate melee defence; repairing that input choice produced `framing-720-05`, 35/35 stages, 4,450 ready active frames and no measured faults. Each failed run is retained with native telemetry and measurement faults. Victory, health, AI, collision and objectives are never disabled or rewritten. |
| Off-route rival pursuit and delayed population admission caused earlier route failures | Bound retreat to the street corridor; select live admitted rivals and skip unavailable optional engagements; preserve resolution-specific successful input snapshots. | `framing-1080-01/02` finished the native objective before completing the circuit. `framing-1080-03` died while waiting for delayed admission. A bounded ordinary-input street patrol replaces stationary waiting; `framing-1080-04` additionally exposed a stale nearest-target crossover, prompting a 200 cm shot-selection margin and diagonal opening approach. No native objective/AI changes were made. Earlier `route-*` and `terrace-*` observations remain exact historical/debug evidence, not current visual acceptance. No failed or partial run is promoted. |
| Sparse exterior, mannequin player and underdeveloped route lighting/material composition remain visible | Keep these major defects explicit and continue only task-scoped route/framing creation. | Historical unmodified panel/hall/ramp/overlook frames in `framing-720-05`; exact observations and remaining creation boundary are recorded in `visual-assessment.json`. Functional measurements do not satisfy `VISUAL_DEFECT_BUDGET_ZERO_MAJOR` or `NO_PASS_ON_CURRENT_D08_BASELINE`. |

The 35-stage route covers entry, streets, ordinary service switching, live weapon
breakage and passage through the panel, the hall threshold and interior camera
turns, the existing four-metre terrace ascent/overlook/descent, east street and
return to the service bay. Optional rival-stage completion is an input-plan
boundary, not a claim that every rival was defeated; deferred/absent engagements
are recorded in the input log. Positions come from native frames, not waypoints
copied into an output report.

The driver emits keyboard/mouse inputs and reads native observations. It does not
teleport, mutate game state, set a cinematic camera or suppress terminal states.
Each capture binds exact input-source snapshots, package membership, native
source/build identity, raw video, native telemetry and engine logs. Native frame
times are reported separately from the 30 fps video recording rate. These are
instrument-assisted navigation runs, not external-player usability evidence,
shipping/Win64 validation, audio qualification or the longer whole-slice proof.

Seven proof-rejection tests exercise a real retained original-geometry route:
forged waypoint observations, missing return stages, native sequence gaps,
near-plane collisions, altered summit height and a nonproduction camera are
rejected; the intact measurement fixture passes. Video is fully decoded by the
measurement CLI, separately from those fault-injection tests. No visual verdict
is inferred from a successful measurement or integrity check.

Earlier camera repair proof is retained at `raw/framing-720-05`: 35/35 stages,
4,450 ready frames, 76.165 active simulated seconds and 290.588 m. That content
predates the terrace and shadow repairs. Failed/partial 1080p attempts exposed
autonomous rival kills ending the objective before traversal completed; they
remain in `raw-attempts.json` with their actual input snapshots and native
terminal states. No partial attempt becomes complete because its observed
camera samples were clear.

Package 04 functional proof is `raw/nanite-full-1080-02`: 35/35 stages, 3,262 ready
frames, 72.124 active simulated seconds and 285.274 m, with zero measured camera,
collision and framing faults. The focused 720p terrace run `raw/nanite-720-01`
completes 18/18 stages. Four close-turn frames briefly crop the feet; the raw
inspection records readable head, upper body and forward scene, without an
observed inside-player or inside-static-geometry view. This is affected-route
proof, not a full current 35-stage 720p qualification.

The full-route input repair restricts optional rival selection near the hall to
650 cm. The previous 6,000 cm choice pursued a rival 43 m away through a wall;
`route-input-repair-02.json` records that diagnosis and the subsequent full-route
result. Native movement, AI, damage and objective rules are unchanged.

The package 04 full capture still logs a VSM queue warning. The bounded native
page diagnostic identifies twelve large non-Nanite casters and five missing
Nanite material usage warnings; those materials fell back at runtime. The
repair duplicates the Engine cube into the Project for the named actors and
enables full-detail Nanite and required material usage. Engine assets remain
unchanged. `shadow-casters-01/source-geometry-comparison.json` verifies exact
editable vertex positions, triangle connectivity, material bindings and
aggregate collision against the preserved pre-repair package. Nanite render
bounds are recorded separately from editable mesh bounds. Native author/readback
and new raw shadow/material verification are pending; the earlier runtime does
not prove the changed assets.

Major composition, material, atmosphere, infection and focal-art deficiencies
remain explicit in `visual-assessment.json`. No final visual acceptance follows
from functional route completion or integrity checks. All exact raw attempts
and their source/input/package identities are retained.
