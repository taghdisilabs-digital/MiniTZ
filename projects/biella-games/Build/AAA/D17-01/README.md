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
Unreal materials. This remains candidate art. The close packaged floor view has
obvious blotchy, grid-shaped wetness and an abrupt transition to the dry road;
those defects are recorded in `visual-assessment.json` and are not accepted.

`environment/mesh-author-05` records Blender execution and evaluated geometry
readback, including ground height and retained panel/tissue clearance.
`environment/assets-05` independently reads fresh saved Unreal assets and verifies
the exact ground shader. Native game/editor builds `game-03` and `editor-03` pass.
`build/cook-07`, `build/stage-07` and `build/package-06` verify the fresh cook,
archive and installed members. The known temporary Android configuration append
was repaired in the isolated cook workspace; `build/cook-config-recovery-05.json`
verifies 425 inputs. Canonical configuration was preserved.

Current Linux Development package:
`e4020d739f936bf18059147b3e91e0dabc54769fad206db3fa775f34c850a429`.
Its exact manifest is `build/package-06/package-manifest.json`; the 483,543,613-byte
archive remains at
`/root/biella/artifacts/games/D17-01/BiellaGames-Linux-Development-service-bay-06.tar.zst`.
Archive SHA-256:
`f52825560b4e5fab242cf88b43afb12fd4453ba6cb4be6f54b96f59bfe2d7d5f`.

`environment/runtime-06` passes installed-package switch, panel damage/physics,
hazard and streaming checks. It uses fixtures, so it is not ordinary slice proof.
`raw/wet-floor-720-01` records ordinary input and the approach from the normal
camera, but native Success occurs at 12.202572849520948 active seconds before
the switch. `raw/wet-floor-1080-01` shows player/rival/infected at entry and reaches
Success at 8.713285327830818 seconds. Neither run records a power transition,
panel event, electrical-floor damage or natural arena-pressure event.

Both videos are unedited H.264 in Matroska with input logs, native telemetry,
and exposed-package byte verification. Terminal footage does not count as active
play. Audio is not captured; recording frame rate is not native performance.

Package-05 art and raw captures remain bound to commit
`02174657d6e83409c441a928c5b1a029024cec8b`. Its input synchronization probe retains
the exact first-world-tick signal and short terminal outcome. Package-04 proof
remains bound to commit `c24863b0c3c6b555f7871c6c6cb99579a0a0115e`: its ordinary
720p run powers the bay, breaks panel 2 into physical debris and records nine
native electrical-floor pulses totaling 27.249 player damage. Those historical
outcomes are not attributed to the current raw runs. Earlier package/HUD/coordinate
evidence retains its own identity and exact committed inputs.

`visual-assessment.json` rejects five major groups: placeholder focal actors and
weapons, sparse industrial composition, incoherent wet surface treatment,
rubbery/repetitive tissue with insufficient arena coverage, and missing cold-storm
lighting. `environment/scope-findings.json` retains native objective and pressure
facts. No pressure timer, objective rewrite, fixture substitution, restart
stitching or idle padding has been introduced.

Run `python3 tests/qualify_d17_01.py` to reconcile exact source, package and raw
proof and regenerate the incomplete qualification index. Next visual action:
correct the ground shader's wetness mask to remove visible grid-shaped blotches,
then rebuild the affected assets and qualify packaged and normal-camera output.
The longer route must still come from accepted executable content.

The task commit preserves exact local source/proof. The Auto Feeder owns
configured GitHub/Drive publication and production-state transition. No remote
publication, Win64 Shipping qualification, task completion or advancement is claimed.
