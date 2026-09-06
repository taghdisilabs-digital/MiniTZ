# D03-01 — skeletal presentation increment

Status: implementation increment; full D03-01 remains CONTINUE.

Use the installed UE 5.8.2 mannequin rig and animation resources with exact provenance. Add a native animation instance on the existing shared APawn; movement, collision, combat and streaming remain gameplay authorities. Sample actual displacement on the game thread (NPC movement does not populate FloatingPawnMovement velocity). Reject teleport/residency discontinuities. Worker evaluation consumes the copied sample only.

Ground locomotion blends directions and speed using editable native blend spaces. Player/rival use rifle locomotion; infected use unarmed locomotion. Jump sampling follows the existing gameplay jump clock, with short pose transitions. No animation root motion or notify changes gameplay. The existing seated blockout presentation is retained until a fitted skeletal vehicle pose is qualified; defeated and dormant actors cannot keep presenting active animation. Original mannequin resources are integration assets, not accepted final Biella character art.

Validation: first establish a failing native test against the current blockout. Exercise real Enhanced Input for movement in multiple directions and jump; measure actual displacement and changing evaluated foot bones, capture native rendered frames, then verify dormancy/wake and defeat cancellation. Run the existing environment regression after integration. Asset readback must resolve dependencies and skeleton identities in native Unreal. Preserve exact attempts and diagnose any failures.

Sequence: native behavior test → source resource dependency closure and readback → graph/pawn integration → native behavior/visual inspection → affected gameplay regression → evidence and local commit. Remaining D03 world, VFX/audio, final character/IK/action/vehicle polish and launch qualification are separate unfinished work inside this task.
