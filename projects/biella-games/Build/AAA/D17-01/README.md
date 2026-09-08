# D17-01 — service circuit candidate

**INCOMPLETE.** The existing open-world entry, Street01 combat, service bay,
interior, terrace and Street03 return remain the candidate in `scenario.json`.
The 600–1200-second continuous route, complete evolving encounter and zero-major-
defect visual requirement have not been met.

The editable service bay now carries a lobed tissue sheath on the visible front
column, a header mat and vascular branches. Organic pigment/normal response and
lower vein emission distinguish tissue from the existing coated metal. The
cabinet, ribbed panels, mounted warm lamps and accepted mechanics are preserved.
`SourceAssets/Environment/ServiceBay.blend` retains editable meshes/modifiers;
its recipe and FBX exports are beside it. `SourceAssets/Materials/ServiceSurface.hlsl`
and `Content/Python/author_service_bay.py` produce the saved Unreal materials.
This remains candidate art, not final visual acceptance.

`environment/mesh-author-04` records Blender execution and evaluated geometry
readback. Column tissue lies beyond the moving panel's Y envelope; the header mat
clears the lamp edge and panel top. The first readback script used an incorrect
parent path; its failed log and script remain beside the corrected verified run.
`environment/assets-04` independently verifies fresh saved Unreal assets.

Native game/editor builds `game-02` and `editor-02` are unchanged. `build/cook-06`
freshly cooks the changed art using verified derived data; `build/stage-06` and
`build/package-05` verify archive and installed members. The known temporary
Android configuration append was repaired in the isolated cook workspace;
`build/cook-config-recovery-04.json` verifies 423 inputs. Canonical configuration
was preserved.

Current Linux Development package:
`cfd920b323ed65faf205b81783a2474b15930fef76a3ab99f1a1a7341a941048`.
Its exact manifest is `build/package-05/package-manifest.json`; the 482,834,812-byte
archive remains at
`/root/biella/artifacts/games/D17-01/BiellaGames-Linux-Development-service-bay-05.tar.zst`.
Archive SHA-256:
`f5ce5ff65fa17f52e203424c2cfb8bb62dcecaaff241b37fab243ae9595db391`.

`environment/runtime-05` passes installed-package switch, panel damage/physics,
hazard and streaming checks. It uses fixtures, so it is not ordinary slice proof.
`raw/sheath-hazard-720-01` exposes the new column/header from the normal camera,
but the timed approach misses the switch and panel; no electrical-floor damage
is recorded. Native Success occurs at 21.109894568973687 active seconds.
`raw/sheath-hazard-1080-01` shows player/rival/infected at entry and reaches
Success at 9.20354756055167 seconds, before the bay.

`tests/d17_01_raw_input.py` now optionally synchronizes ordinary input to the
first existing nonzero-frame world-residency log signal after Active. The raw
video retains startup; no simulation/world state is changed.
`service-hazard-tick-input.json` uses that clock in `raw/sheath-hazard-720-02`.
The recorded first-world-tick origin is 2.09688 capture seconds. All nine actions
follow it, but native Success at 12.70496472431114 active seconds ends this probe
before the switch. Synchronization alone does not establish the route.

All three videos are unedited H.264 in Matroska with input logs, native telemetry,
and exposed-package byte verification. Terminal footage does not count as active
play. Audio is not captured; recording frame rate is not native performance.

The exact previous package-04 proof remains bound to commit
`c24863b0c3c6b555f7871c6c6cb99579a0a0115e`. Its 720p ordinary run powers the bay,
breaks panel 2 into physical debris, crosses the opening and records nine
native electrical-floor pulses totaling 27.249 player damage. The new material
inputs differ only in ten service-bay assets and their authoring script; native
mechanics remain identical. That historical outcome is not attributed to the
new raw runs. Earlier package/HUD/coordinate evidence retains its own identity;
pre-synchronization captures bind the driver bytes in the preceding commit.

`visual-assessment.json` directly rejects five major groups: placeholder focal
actors/weapons, sparse industrial composition, insufficient wet surface detail,
rubbery/repetitive tissue and insufficient arena coverage, and missing cold-storm
lighting. The new front-facing growth is visible; visibility alone does not
close organic-form quality. `environment/scope-findings.json` retains native
objective and pressure facts. No pressure timer, objective rewrite, fixture
substitution, restart stitching or idle padding has been introduced.

Run `python3 tests/qualify_d17_01.py` to reconcile exact source, package and raw
proof and regenerate the incomplete qualification index. Next visual action:
replace the dry service-bay approach and crude hazard-floor visual treatment
with coherent wet worn surfaces, preserving tested collision and hazard state,
then validate the affected layer in the package and ordinary camera. The longer
route must still come from accepted executable content.

The task commit preserves exact local source/proof. The Auto Feeder owns
configured GitHub/Drive publication and production-state transition. No remote
publication, Win64 Shipping qualification, task completion or advancement is claimed.
