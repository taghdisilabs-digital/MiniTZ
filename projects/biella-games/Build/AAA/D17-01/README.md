# D17-01 — service circuit candidate

**INCOMPLETE.** The existing open-world entry, Street01 combat, service bay,
interior, terrace and Street03 return remain the candidate in `scenario.json`.
The 600–1200-second continuous route, complete evolving encounter and zero-major-
defect visual requirement have not been met.

The editable bay now includes 200 service-ground parts: bevelled concrete slabs,
steel floor plates, side aprons, a sill and grated drains. A dedicated PBR ground
shader provides damp aggregate, wet reflections and worn perimeter markings. The
existing native power state controls small amber perimeter lenses. Ground art is
non-colliding and stays within two centimeters of the accepted walking plane;
the existing collision and hazard volumes remain authoritative. Exact comparison
in `environment/ground-mechanics-preservation.json` confirms eleven gameplay
methods are unchanged. The prior cabinet, panels, tissue sheath and lamps remain.

`SourceAssets/Environment/ServiceBay.blend` retains editable meshes/modifiers;
its recipe and FBX exports are beside it. `SourceAssets/Materials/ServiceGround.hlsl`,
`ServiceSurface.hlsl` and `Content/Python/author_service_bay.py` produce the saved
Unreal materials. Package-08 replaces the ground's floating-point sine hash with
an integer lattice hash. Controlled G-buffer captures isolate the angular breaks
to Roughness/BaseColor while WorldNormal remains flat across slab interiors.
Post-change Roughness and Lit views, the installed fixture and ordinary approach
show continuous wetness. `environment/floor-diagnosis.json` binds the comparison,
source intervention and causal limits. No specific generated GPU instruction or
compiler precision behavior is claimed. The initial rejected view-mode command
and corrected rerun remain preserved. A ground-only authoring mode verifies that
only `M_ServiceGround.uasset` changes. The abrupt dry-road edge and other major
visual deficiencies remain; `visual-assessment.json` records the rejection.

`environment/mesh-author-05` records Blender execution and evaluated geometry
readback, including ground height and retained panel/tissue clearance.
`environment/assets-07` independently reads fresh saved Unreal assets and verifies
the exact corrected ground shader and unchanged other assets. Native game/editor
builds `game-03` and `editor-03` are reused with matching inputs.
`build/cook-09`, `build/stage-09` and `build/package-08` verify the fresh cook,
archive and installed members. The known temporary Android configuration append
was repaired in the isolated cook workspace; `build/cook-config-recovery-07.json`
verifies 425 inputs. Canonical configuration was preserved.

Current Linux Development package:
`2b327215c81c8cb7186be4490daac1f9362799abfc34219f6730d809d0384949`.
Its exact manifest is `build/package-08/package-manifest.json`; the 483,686,863-byte
archive remains at
`/root/biella/artifacts/games/D17-01/BiellaGames-Linux-Development-service-bay-08.tar.zst`.
Archive SHA-256:
`1a7df8cc72ba9b70d7b99b22f3f4e1dfe059eb65dbca5c81263083f5e3945108`.

`environment/runtime-08` passes installed-package switch, panel damage/physics,
hazard and streaming checks. It uses fixtures, so it is not ordinary slice proof.
`raw/integer-floor-720-01` records 21 ordinary inputs, approaches the bay from the
normal camera and ends at native Success after 15.935191704833414 active seconds.
It includes an interaction attempt and three shots, without a native environment
event. `raw/integer-floor-1080-01` shows player/rival/infected at entry and reaches
Success at 8.907017945253756 seconds. Neither run records a power transition,
panel event, electrical-floor damage or natural arena-pressure event.

Both videos are unedited H.264 in Matroska with input logs, native telemetry,
and exposed-package byte verification. Terminal footage does not count as active
play. Audio is not captured; recording frame rate is not native performance.

Package-07 art and raw captures remain bound to commit
`fdad60240ebd296e95a593789cc0fb8ed7716124`. The new package changes only its saved
ground material; the editable shader is separately bound to fresh asset readback.
Package-06 ground art and raw captures remain bound to commit
`51811365a77cde9f45a8733a663a649c57766df9`. The current package preserves its
geometry and native gameplay methods. Package-05 art and raw captures bind commit
`02174657d6e83409c441a928c5b1a029024cec8b`. Its input synchronization probe retains
the exact first-world-tick signal and short terminal outcome. Package-04 proof
remains bound to commit `c24863b0c3c6b555f7871c6c6cb99579a0a0115e`: its ordinary
720p run powers the bay, breaks panel 2 into physical debris and records nine
native electrical-floor pulses totaling 27.249 player damage. Those historical
outcomes are not attributed to the current raw runs. Earlier package/HUD/coordinate
evidence retains its own identity and exact committed inputs.

`visual-assessment.json` rejects five major groups: placeholder focal actors and
weapons, sparse industrial composition, incoherent surrounding material treatment,
rubbery/repetitive tissue with insufficient arena coverage, and missing cold-storm
lighting. `environment/scope-findings.json` retains native objective and pressure
facts. No pressure timer, objective rewrite, fixture substitution, restart
stitching or idle padding has been introduced.

Run `python3 tests/qualify_d17_01.py` to reconcile exact source, package and raw
proof and regenerate the incomplete qualification index. Next visual action:
replace the flat green service-switch surface with an editable weathered control
face driven by the existing BaseColor/Emission power parameters. Preserve the
Switch component, transform, collision and interaction trace; validate saved-
material readback, packaged power interaction and the normal approach camera.
The longer route must still come from accepted executable content.

The task commit preserves exact local source/proof. The Auto Feeder owns
configured GitHub/Drive publication and production-state transition. No remote
publication, Win64 Shipping qualification, task completion or advancement is claimed.
