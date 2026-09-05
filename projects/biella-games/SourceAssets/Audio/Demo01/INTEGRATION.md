# Demo 01 feedback integration

The `UBiellaGameplayFeedback` world subsystem owns finite Audio Mixer voices and Niagara components. Gameplay callers resolve the event first; feedback never resolves damage, spends ammunition, changes phase, or consumes gameplay RNG.

| Confirmed production event | Presentation |
| --- | --- |
| Player `FireWeaponAt` accepted collision/damage | One muzzle sound/flash at the weapon tip; one impact sound/burst at `FHitResult.ImpactPoint`, oriented to its normal |
| Rival `FireAtTarget` accepted collision/damage | Same spatial shot/impact path |
| Infected `TryMeleeTarget` accepted collision/damage | Impact at the actual contact, without a firearm cue |
| Accepted player damage | Listener hurt cue plus the predecessor's material hit flash |
| Arena pressure changes named state | One listener warning; unchanged values and revisions within the same state are silent |
| Actual phase changes to Success/Failure | Distinct listener result cue; repeated same-phase updates are silent |

The existing Demo 01 weapon rejects blocked/invalid/cooldown actions before spending ammunition. Those rejected actions remain silent and do not manufacture shot or confirmed-hit effects. Existing targeting, damage, ammunition, AI, objective, and restart behavior is preserved.

The player's noncolliding weapon presentation sits 45 cm beside the torso. Its actual tip and flash now clear the torso from the existing over-shoulder camera; the camera-driven shot trace is unchanged. Rival collision and barrel-clearance traces are unchanged.

Shot audio and event telemetry retain the true weapon tip. The finite muzzle gas system starts 30 cm along the resolved shot direction, so depth testing does not bury the burst inside the barrel. This cosmetic offset is explicit editable C++ and never changes a shot's collision query. Surface effects remain anchored to the collision result and extend outward along its normal.

Shot masters rotate through three source variations. Small pitch variation is a local presentation sequence, independent of the gameplay random stream. Spatial shot/impact voices use native distance attenuation (250 cm inner radius, 4500 cm falloff), spatialization, and visibility-channel occlusion. Hurt/result cues stay intelligible at the listener. Audio parameters and budgets are editable C++; audio masters, their generator, import helper, and native PCM SoundWaves are retained.

Twelve combat voices and two separately reserved critical voices bound concurrency. A terminal cue replaces outstanding critical cues. Above three concurrent combat voices, aggregate gain is reduced to retain headroom for critical cues; every accepted event still resolves gameplay normally. The oldest cosmetic voice/effect is retired when its budget is full. Twenty-four finite Niagara components cap simultaneous effects. All effects obey depth and have no gameplay collision or navigation influence. Native finite completion, watchdog expiry, explicit state reset, and world subsystem teardown release transient components. There are no looping sound/effect actors or persistent cross-restart components.

Niagara source and provenance are in `Content/Python/build_demo_feedback_vfx.py` and `Build/Demo01/D01-042-vfx-README.md`. These original authored assets and runtime captures remain `GENERATED_DRAFT`; implementation qualification does not designate final visual/audio canon.
