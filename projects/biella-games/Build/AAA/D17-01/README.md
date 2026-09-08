# D17-01 — service circuit candidate

**INCOMPLETE.** `scenario.json` binds the owner direction to the existing
open-world entry, Street01 population, service bay, interior, raised terrace and
Street03 return. A continuous 10–20 minute route, player-reachable arena-pressure
consequence and zero-major-defect visuals are still unqualified.

The current authored layer replaces the service bay's plain panels with ribbed,
beveled metalwork, cabinet louvers, hardware and mounted warm lamps. Editable
Blender source, FBX exports, Unreal authoring code and saved runtime assets remain
at `SourceAssets/Environment/`, `Content/Python/author_service_bay.py` and
`Content/Environment/ServiceBay/`. Panel collision envelopes, damage, physics,
switch interaction, hazards and streaming behavior are preserved. These assets
remain a generated candidate, not owner-accepted final art.

Native game/editor builds and fresh saved-asset readback pass. The isolated cook,
archive extraction, exact installed-member verification and packaged environment
regression also pass. The environment fixture exercises actual damage, debris,
traversal, switching, shared hazard and unload/reconstruction; its camera and
actor placement are automated, so it is separate from raw slice evidence.

The new Linux Development package is
`1c539e9274baf5ba24ab603d2238dd0cef2069e5030dc8cc1e966622d50892a1`.
`build/package-02/package-manifest.json` identifies all 34 installed members and
the exact 481,750,430-byte archive at the canonical Games artifact path. Archive
SHA-256 is `2fd394366130ae69770c6f7f9a3ab53e48ff5e322fc834012c25ef75cc9c04ad`.
Both new raw runs expose this package without a native overlay. The stage-02
failure remains recorded: an Unreal Android editor plugin appended first-run
settings to the temporary cook config. `build/cook-config-recovery.json` records
the scoped restoration to original input bytes and verification of all 421
recorded inputs/binaries/cooked files. Stage-03 then passed using the same cook.
Canonical configuration was unchanged.

`raw/service-720-01` and `raw/service-1080-01` contain unedited H.264/Matroska
gameplay, X11 input logs, native telemetry and package verification. They use
fresh processes/user state, normal third-person controls and real-time simulation,
with no fixture, time dilation, actor reset or restart stitching. Success occurs
at 32.21 and 8.70 active simulation seconds; the terminal tail is excluded. The
720p frame at video time 13 seconds shows the new service bay during ordinary
street traversal. It does not prove the switch/destruction or later route beats.
The 1080p capture shows the real player/rival/infected encounter. Neither run
records an arena-pressure transition. Raw videos have no audio; recording at
30 fps is not evidence of native game frame rate.

The compact HUD improvement and its two live regression tests remain preserved
from commit `57190a294440c4dfa6deb9a9a50d23442c66fbc8`. Historical raw runs bind
their original D08 package or exact native overlay, not the new visual assets.
The first raw run predates namespace verification and retains its original
driver-hash recovery limitation. No predecessor evidence is relabeled as current.

`raw/route-rival-01` is an additional ordinary-input feasibility probe against
the unchanged D08 package. Early sprint/fire input still produced success at
14.01 simulation seconds. Telemetry shows population infected joining the
objective, followed by rivals clearing the target set. This attempt does not
prove that every possible route fails. `environment/scope-findings.json` preserves
the causal source and telemetry: the inherited objective ends input at success;
some streaming actors are excluded, while population infected can be registered.
Contract 33 leaves pressure timing/escalation unspecified. No invented timer or
switch-to-pressure connection has been added.

Inspection against the hard visual requirements still finds five major groups:
placeholder focal characters/weapons, sparse industrial density, insufficient wet
material detail, absent organic invasion and absent cold storm lighting. The
service bay also retains coarse mottling, whole-panel orange damage feedback and
an unsupported switch cube. Fresh Blender/Unreal coordinate readback confirms
that FBX import reflects the fixed metalwork across Y: the cabinet appears on the
opposite side from its preserved collision and switch. The editable Blender file
reopens with 88 separate mesh parts and 88 bevel modifiers.
`environment/coordinate-readback-01/validation.json` records both facts. Existing
gameplay proof does not waive the placement or other visual defects.

Run `python3 tests/qualify_d17_01.py` from the Project root to verify exact current
inputs and regenerate `qualification.json`. It indexes the real source, build,
package and raw evidence and records incomplete acceptance. Resume visual work
by correcting the FBX handedness and asymmetric cabinet placement, then the
service-bay approach's wet surface, switch mounting and organic growth,
preserving the validated collision/interaction envelopes. Establish any longer
route or pressure trigger from accepted executable content; do not pad footage
or alter mechanics to manufacture the required sequence.

The task commit preserves local source/proof. The Auto Feeder owns configured
GitHub/Drive publication and production-state transition. No remote publication,
Win64 Shipping qualification, D17-01 completion or next-task advancement is claimed.
