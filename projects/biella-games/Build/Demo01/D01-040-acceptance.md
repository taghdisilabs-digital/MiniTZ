# D01-40 — visual/readability pass

Result: **PASS**, implemented and qualified locally. This record covers only D01-40. The Auto Feeder retains publication and canonical task-transition ownership; 03/04 and `PRODUCTION.md` are unchanged.

## Resulting behavior

- The native HUD now renders its actual runtime values. Its tree is built before Unreal selects the Slate root in `RebuildWidget`; the previous late `NativeConstruct` layout produced bound UObject values without a rendered HUD tree. Positive canvas sizes, anchored positions, padding, wrapping, and a 720p reference DPI curve keep the objective, status, countdown, reticle, and terminal cards readable.
- Team colors now reach a real material parameter. Native readback found the engine material exposes `Color`, while the existing code wrote `BaseColor`. The saved Project `M_DemoReadability` material exposes the expected parameter, roughness, and modest shadow fill. Its editable Python graph source and fresh-process verification are included. The material and new sphere mesh have constructor/UPROPERTY references for native asset discovery.
- Existing pawn primitives receive noncolliding role details: player single band and rounded head, rival double bands and square helmet, infected crossed marks and narrow torso. Details follow live defeat visibility and rebuild without accumulating on a repeated `BeginPlay`. Existing damage flashes now use the working material. Cover has contrasting caps without changing its collision or navigation.
- The camera retains the collision-tested 520 cm third-person arm and moves 90 cm sideways / 55 cm upward at the socket, clearing the player silhouette from the aiming lane. Fixed manual exposure for this fixed-daylight arena preserves color and pressure tint when dark walls enter view.
- Arena reconstruction reuses the authored sun, with explicit ownership for the fallback case. Both maps use movable lights and disable precomputed lighting for their runtime-built geometry. The skylight recaptures after construction; Lumen mesh distance fields are enabled. Native map readback verifies all four original actor identities, transforms, component geometry, and collision remain unchanged.

## Task-derived validation

| Check | Observed result |
| --- | --- |
| UE 5.8.2 `BiellaGamesEditor Linux Development` | PASS, [final build](D01-040-editor-build-final.log) |
| Two fresh Vulkan game processes under Xvfb | PASS, 1280×720 and 1920×1080; real Slate window, possessed camera, rendered world and UI |
| Runtime capture sequence | PASS, six PNGs per viewport: 6/12/20 m, pressure 100 with health 25, objective success, bound `R` restart, player defeat/failure |
| Live HUD geometry | PASS, all 11 active and four terminal text widgets fit; cards inside viewport without overlap; centered reticle and terminal card; DPI 1.0 / 1.5 |
| Gameplay-distance visibility | PASS, exact player-origin distances and unobstructed camera-to-target collision traces; 20 m bodies measure 46.1–46.2 px at 720p and 69.2 px at 1080p |
| Motion and aiming lane | PASS, real Enhanced Input produces 46.2 / 198.7 cm motion over 20 rendered frames; HUD geometry stays valid; camera aiming ray clears the still-collidable player capsule |
| Runtime presentation integrity | PASS, actual material parameter resolution, role meshes, collision/navigation exclusion, and defeat visibility checked |
| D01-33 pressure responses | PASS on final build, including authoritative responses, reconstruction, traversal/collision and cleanup |
| D01-37 HUD / D01-38 terminal overlays | PASS on final build in fresh processes |
| D01-39 deterministic playtest | PASS twice on final build; all 56 semantic events match each other. Comparison with the predecessor isolates only two expected restart map-name corrections after native map saves |
| Protected boundary / structural verifier | PASS, `completed=39/50 current=D01-40`; protected-file hashes unchanged |

The render scenario controls encounter placement and freezes AI for distance measurements. Movement, damage, pressure, objective state, and restart use production APIs/input. Pressure reinforcements still spawn through production; the fixture relocates those additional actors away from the camera sweep before the pressure capture. Normal spring-arm collision remains enabled. The independent D01-39 regression exercises autonomous AI and combat.

Decoded-frame inspection, independently repeated, confirms readable role markings, critical text and state changes at both viewports, a clear aiming corridor, and no diagnostic text over the HUD. Bright surfaces no longer wash out role color; dark opaque cards preserve text against both lit and shadowed geometry. These are tested viewports, not newly selected shipping targets.

## Evidence and reproduction

- [Validation manifest](D01-040-validation.json): exact source/configuration/map/build identities, original and committed PNG hashes, authoring/readback evidence, protected hashes, and retained failed attempts.
- [Rendered runtime results](D01-040-runs/20260905T074436.187564Z/validation.json).
- [Final affected regressions](D01-040-final-affected-regressions/validation.json).
- [Final deterministic playtest](D01-040-qualified-playtest/20260905T074646.072976Z-nullrhi-89d623f8/validation.json) and [predecessor identity review](D01-040-predecessor-identity-review.json). The unmodified [strict predecessor comparison](D01-040-qualified-timeline-comparison.json) correctly rejects the two `restart_requested.fields.map` differences: native map saves resolve the old shared recovered-package identity, so restart now reports `BiellaGameplayMap` rather than `BiellaGameplayMap_Recovered`. All other ordered semantic fields match.
- Representative committed captures: [20 m](D01-040-captures/1280x720/active_20m_1280x720.png), [pressure / low health](D01-040-captures/1280x720/low_health_pressure_100_1280x720.png), [success](D01-040-captures/1280x720/success_1280x720.png), [1080p failure](D01-040-captures/1920x1080/failure_1920x1080.png).

After building the Editor target, reproduce with `python3 tests/run_d01_040.py`. It creates fresh attempt directories, enforces process deadlines, rejects failed automation or missing/invalid PNGs, and compares source/build/metadata hashes before and after execution. The material and map authoring scripts document their native Unreal commandlet invocations and read-only verification flags.

Original candidate frames remain under `/root/biella/artifacts/games/D01-040/20260905T074436.187564Z/`; byte-identical copies of all 12 final PNGs are included in this commit. Captures remain **GENERATED_DRAFT**, without owner visual acceptance. The scene remains a simple primitive blockout with dark unfilled areas; this bounded readability pass does not claim final AAA art, unrestricted-combat visual qualification, Windows packaging, native performance qualification, or completion of D01-41/42.

Earlier attempts are retained: the missing rendered HUD root, an Xvfb authorization mismatch, and a pressure reinforcement correctly retracting the fixture camera all failed closed. Failed Vulkan automation also exposed an engine shutdown assertion; successful final processes exit cleanly. An attempted real-time sky capture was corrected to ordinary scene capture after the renderer identified that these maps have no sky-atmosphere/dome source. No diagnostic warnings were suppressed to obtain the final images.
