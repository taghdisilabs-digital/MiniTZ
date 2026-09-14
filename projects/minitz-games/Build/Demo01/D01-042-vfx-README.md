# D01-42 Niagara asset provenance

Status: `GENERATED_DRAFT`. Authored in Epic Unreal Engine 5.8.2 on the Linux qualification host on 2026-09-05. These assets are game-specific feedback candidates, not a change to the accepted platform or visual canon.

`Content/Python/build_demo_feedback_vfx.py` is the editable, reproducible authoring source. It uses Epic's editor-only `CascadeToNiagaraConverter` graph adapter to build ordinary native Niagara systems; no Cascade particle asset is converted. Graph construction requires the full editor/Slate (`-ExecutePythonScript`); a Python commandlet cannot initialize the adapter's Slate property customization. Saved assets load without the converter plugin, as the independent readback proves. Runtime uses Niagara and the project material only; the converter is not added to the project plugins or runtime dependencies.

The saved editable graphs reference Epic Niagara's CompletelyEmpty emitter template, SystemState, EmitterState, SpawnBurst_Instantaneous, InitializeParticle, ParticleState, SolveForcesAndVelocity, RandomRangeVector, Color, MakeLinearColorFromVectorAndFloat, and their standard Niagara enums. The template path contains `CascadeConversion` under `/Niagara/`; it is part of the Niagara plugin, not a converter runtime dependency. Each emitter uses CPU simulation, local coordinates, a single burst at time zero, self lifecycle Once, a 0.01s emitter loop, and finite particle lifetime. Component +X points down the barrel or out of the hit normal. Color/size/velocity/lifetime remain editable in the Niagara graph and authoring dictionary. No exposed user parameters are required.

| System | Emitters | Authored count | Longest authored particle lifetime |
| --- | --- | --- | --- |
| `/Game/Feedback/NS_Muzzle` | WarmCore, MuzzleSparks | 1 + 4 | 0.12s |
| `/Game/Feedback/NS_Impact` | SurfaceSparks, SurfaceDust | 6 + 5 | 0.36s |

`M_FeedbackParticle` is a code-authored material graph with procedural radial softness, particle color, relative-age opacity fade, and 6cm scene-depth intersection fade. It uses translucent unlit emissive sprites with depth testing enabled. The visual intent is a modest warm barrel flash and a small neutral surface burst. No downloaded textures, generated bitmap, or external provider was used.

`D01-042-vfx-author.log` retains actual native compilation and save lines plus the observed Linux teardown failure: after `LogExit: Exiting.`, the process reported `free(): invalid pointer`, Signal 6, then exited 139. This run alone is not claimed as clean process validation. Assets were preserved and independently reloaded in a fresh commandlet without the converter plugin; `D01-042-vfx-readback.log` shows `Success - 0 error(s), 0 warning(s)` and exit 0. Readback verifies native asset types and saved material depth/translucency settings; authoring counts/lifetimes in its JSON are explicitly source specifications. Actual runtime particle counts, rendered output, and completion/cleanup are validated by the D01-42 integrated runtime test, not inferred from these authoring logs.

No 03/04 identity, PRODUCTION status, predecessor evidence, or Engine P4-06 state is changed by this subtask.

Original native asset SHA-256 (superseded by the color correction below):

- `Content/Feedback/M_FeedbackParticle.uasset`: `4e38ecbe6d3c27867e26620cf304f4492dec615ccb2d6b4b9f45bc8c8e771841`
- `Content/Feedback/NS_Muzzle.uasset`: `3bbe1df3b1d6410dc9d60037e54e3bdb9b61fb9bd346343389d27166f54be058`
- `Content/Feedback/NS_Impact.uasset`: `a63f77a1ce8c0a8f75bc152a92f6b6e2eeaa195f3a41712e24d97cf3ee5ae7e5`

Color/visibility correction: native runtime dataset inspection in run `20260905T082921.833085Z` showed the initial direct Color assignment remained white, despite correct size/position/lifetime. The editable source now uses the standard Niagara Update Color module with explicit RGB/alpha dynamic inputs, matching Epic's supported converter pathway. Core size is 20x12cm, both spark sizes 3.5cm, and dust 12cm. Count/lifetime remain unchanged. Run `20260905T083847.402035Z` observed exact intended RGBA values for all four emitter types and correct transformed positions; dense-combat capture shows the warm burst. Root owns final visual/integration acceptance and settled-source qualification.

Reproduce safely from the Project root:

```bash
python3 Content/Python/run_demo_feedback_vfx_authoring.py --rebuild
python3 Content/Python/run_demo_feedback_vfx_authoring.py --verify
```

The helper creates a disposable moduleless `.uproject` with Niagara and PythonScriptPlugin, launches full-editor authoring with CascadeToNiagaraConverter enabled only for that process, and authors exactly three candidates with the same `/Game/Feedback` package names in empty temporary Content. Fresh-process candidate readback must pass before those three files replace canonical assets; the helper then verifies the canonical BiellaGames project. The temporary context has no gameplay module or authority and is removed afterward. This reroute avoids two observed in-place authoring failures: material expressions loaded/rooted through gameplay constructor hard references could not be deleted, and linked-Content force-delete left an existing package name that unattended recreation rejected. Existing canonical candidates are preserved until new candidate readback succeeds. Do not pass the old in-place `-D01RebuildFeedbackVFX` flag to the Unreal script; it now rejects that unsafe path explicitly.

Intermediate color-corrected asset SHA-256 (superseded by final gas extension below):

- `Content/Feedback/M_FeedbackParticle.uasset`: `622c3837eba13d988f1262dba00617d042ad0a98efe51086aade449ce62b15b2`
- `Content/Feedback/NS_Muzzle.uasset`: `be003179177fef77b88a22d836534d66ada81f96b8eacf180913a9a1785f6dfd`
- `Content/Feedback/NS_Impact.uasset`: `763aa88bab17346e860686dc6cc8658e7099708c71d375a3c8efbd8f1fbe5b88`

The initializer-offset experiment was rejected by observed runtime data: run `20260905T084403.419146Z` still reported WarmCore `first=V(0)` and MuzzleSparks only its normal velocity displacement, although the authoring API accepted local PositionOffset inputs. Those ineffective inputs and source specifications were removed, and the native assets rebuilt. The bounded author log retains that evidence. Final source does not claim a Niagara-local initialization offset.

The runtime C++ integration now derives only the shot VFX component position as `true_muzzle + normalized_shot_direction * 30cm`. This models gas beyond the barrel and preserves actual muzzle audio/event telemetry, impact collision location, particle counts/lifetimes, material depth testing, and shooter geometry. It is an explicit, tested component transform rather than an unobserved initializer input. Final settled-source qualification belongs to the integrated runtime test.

The final helper --rebuild completed exit0 at 08:46:59 UTC. Candidate and canonical fresh-process readbacks each reported zero errors/warnings; editor teardown139 remains disclosed in author log. Source/helper/native assets are frozen after this rebuild. Final native asset SHA-256:

- `Content/Feedback/M_FeedbackParticle.uasset`: `656d1f1bac66e98df33158f764028226a6de6cd460089063e94bd64a51b48939`
- `Content/Feedback/NS_Muzzle.uasset`: `472881a1ed4e829fe69a62b429c34a738233b8288bcc8be2b4dbf7dbf84ce354`
- `Content/Feedback/NS_Impact.uasset`: `d07a7b6ffbb1b00adb18bb95dfb3f2cb7c203955eacdcde4ac03cec21cf2ddc6`
