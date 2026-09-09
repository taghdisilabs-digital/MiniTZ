# D17-02 traversal and camera evidence

D17-02 remains in progress. This record distinguishes real route measurements
from the required final visual acceptance. D17-01 selection and accepted
movement, combat, AI, objective and streaming rules are preserved.

| Observed gap | Task-scoped repair | Evidence / disposition |
| --- | --- | --- |
| Bare ramp edges and an unsupported-looking terrace | Authored fitted nonslip steel decking, raised edge strips, parapet cassettes, six ground-bearing columns and bracing. Preserved original ramp/deck/parapet transforms and collision profiles. | Editable Blender/FBX/native assets; fresh-process readback in `environment/terrace-assets-04`; game/editor build, affected cook, stage/archive and installed membership readback pass. Actual new geometry appears in `raw/terrace-720-04` and `raw/terrace-1080-02`. |
| Route lacked instrumented full traversal proof | Opt-in native end-frame camera, capsule, near-plane, projection, movement and readiness measurements; X11 route driven by live observations. | `terrace-720-04` completes 35 stages without camera/collision faults. `terrace-1080-02` also completes all stages, but exposes the panel-corner camera issue below. These runs use game-02; later camera/HUD changes require fresh evidence. |
| Upper-body sightline crosses the service-panel corner one frame before the normal arm retracts | Before calculating the actual player view, sweep the camera sphere from upper body to the regular arm socket. Rebase each frame; the camera component remains the real view and weapon-trace origin. | `terrace-1080-02`: native frame 961, D02Environment01, 0.0243739 s; normal arm retracts on frame 962. `game-03` compiles the repair. `framing-720-05` completes the full route with zero upper-body occlusion, camera overlap or near-plane intersections; current partial 1080p attempts also measure zero such faults. Full current 1080p route proof remains to be recorded. |
| Large status/countdown panels obscure route framing and the player's feet | Compact objective/remaining-threat hierarchy at top-left; health/ammo at bottom-right; lower centre reserved for contextual interaction text. Preserve actual HUD state binding and accessibility scaling. | `game-03` builds. Opaque card area shrinks from 13.74% to 6.04% at default 720p scale. Actual `framing-720-05` panel, hall, ramp and overlook frames show readable text and unobstructed player/feet; native measurements report zero head/feet/centre frame loss. Source area is supporting evidence, not a visual verdict. |
| Ordinary-input automation could fire the final infected shot before completing the return circuit | Read the same objective progress as the HUD and withhold that optional shot. When the final infected blocks an optional rival engagement, explicitly record the engagement as deferred and resume movement. | `framing-720-01/02` ended in native Success; `framing-720-03` waited within melee range and ended in native Failure. `framing-720-04` exposed a distant-rival shot gate that withheld immediate melee defence; repairing that input choice produced `framing-720-05`, 35/35 stages, 4,450 ready active frames and no measured faults. Each failed run is retained with native telemetry and measurement faults. Victory, health, AI, collision and objectives are never disabled or rewritten. |
| Off-route rival pursuit and delayed population admission caused earlier route failures | Bound retreat to the street corridor; select live admitted rivals and skip unavailable optional engagements; preserve resolution-specific successful input snapshots. | `framing-1080-01/02` finished the native objective before completing the circuit. `framing-1080-03` died while waiting for delayed admission. A bounded ordinary-input street patrol replaces stationary waiting; `framing-1080-04` additionally exposed a stale nearest-target crossover, prompting a 200 cm shot-selection margin and diagonal opening approach. No native objective/AI changes were made. Earlier `route-*` and `terrace-*` observations remain exact historical/debug evidence, not current visual acceptance. No failed or partial run is promoted. |
| Sparse exterior, mannequin player and underdeveloped route lighting/material composition remain visible | Keep these major defects explicit and continue only task-scoped route/framing creation. | Current unmodified panel/hall/ramp/overlook frames in `framing-720-05`; exact observations and remaining creation boundary are recorded in `visual-assessment.json`. Functional measurements do not satisfy `VISUAL_DEFECT_BUDGET_ZERO_MAJOR` or `NO_PASS_ON_CURRENT_D08_BASELINE`. |

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

Current full 720p evidence: `raw/framing-720-05/measurements.json`, 35/35 stages, 76.165 active simulated seconds, 290.588 m measured path, 520 cm target arm and 90-degree FOV. Camera retraction reaches 272.081 cm; capsule centre reaches 490.238 cm at the terrace. Native frame times: p50 16.668 ms, p95 18.647 ms, p99 22.527 ms; the maximum 400 ms includes startup. Readiness holds remain 2 to 2, with no new active unready frame. No collision, camera, projection or unexplained position-step fault is observed.
The latest current-build 1080p run, `raw/framing-1080-06`, completes 7/35
stages and 1,920 ready active frames with zero measured camera/collision/projection
faults. Rival fire defeats the last infected at simulated second 44.607884;
the native objective enters Success at 44.707890 and stops ordinary input.
The player remains alive with 52 health. This is an incomplete route, despite
zero faults in the observed portion. The strongest current 1080p route remains
`framing-1080-01`, 28/35 stages through the terrace overlook; descent/return
with the camera repair still requires proof.

`framing-1080-05` also exposed early player/rival concurrent kills before
population admission. The current driver withholds optional infected fire when
two targets remain, adds a 200 cm nearest-target margin and uses a bounded
street patrol while waiting for admitted rivals. Attempt 06 demonstrates that
these input safeguards cannot prevent autonomous rival kills. The current
1080p plan is an unsuccessful experiment, not an accepted repeatable recipe.
Every executed run retains its exact input source; the successful 720p proof
binds that run's captured driver and plan, not later input experiments.

The exact unmodified 1080p panel, hall and overlook extractions corroborate the
remaining exterior composition/material/player defects in
`visual-assessment.json`. Continue with the recorded approach/terrace creation
boundary rather than replaying this unchanged input plan. All earlier raw
attempts are indexed in `raw-attempts.json` and retained for diagnosis.
