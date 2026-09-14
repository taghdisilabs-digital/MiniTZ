# D03-01 — Rendering increment, task continues

Status: **CONTINUE**. This is evidence for the surface-rendering increment of D03-01, not acceptance of the full production rendering, animation, VFX and audio task. The canonical task remains D03-01. Generated material assets and captures remain `GENERATED_DRAFT`.

## Implemented behavior

The playable open world now uses an opaque, lit surface master with filtered irregular grain, linked base-color/roughness variation and bounded world-space normal relief. The four existing street, wall, route and interior instances keep their established colors and gain distinct roughness, detail scale and relief parameters. World authoring references this saved master, so subsequent authoring retains the new material path. Existing map geometry, external actors, collision and gameplay are unchanged.

The material is editable in Unreal and reproducible from `SourceAssets/Materials/ProductionSurface.hlsl` and `Content/Python/build_production_surfaces.py`. Three spatial noise octaves fade as their pixel footprint becomes too large; the shader contains no time animation, emissive input or world-position offset. Relief is clamped to 0.20 cm. The saved graph supports instanced static meshes and uses its custom result in base color, roughness and normal. A separate native editor process read back the graph, exact embedded shader text, instance parents and parameters without modifying asset bytes.

The canonical default disables motion blur and selects TSR. The test runner explicitly verifies those settings plus uncapped, variable-timestep rendering with dynamic resolution and VSync disabled. TAA at 100% and TSR at 67% are additional measured test paths; this does not implement a shipping quality-settings UI or qualify all hardware.

## Validation

All of these checks passed on UE 5.8.2, Linux Development, native Vulkan, NVIDIA L40S at a 1280×720 output:

- Native Editor build: `D03-01-build-02.log`.
- Material authoring and fresh-process exact graph/asset readback: `surface-v2-author/validation.json`.
- TSR 100%, TAA 100%, TSR 67% runtime profiles: `clarity-tsr100-01/validation.json`, `clarity-taa100-01/validation.json`, `clarity-tsr67-01/validation.json`.
- Final gameplay regression with these source/config/material bytes: `environment-regression-02/validation.json`. It exercises real input, power interaction, shooting, Chaos destruction, traversal, hazards, navigation, streaming state and restart through the existing D02-04 test.
- Six corrupt-evidence controls were rejected: wrong AA, missing GPU time, reordered frame IDs, frozen camera trajectory, enabled motion blur and fixed timestep. See `negative-verifier-02/result.json`; its relative symlinks point to unchanged baseline evidence.
- Preservation: `D03-01-preservation-after.json` compares 1,262 baseline files. Exactly six intended files changed: renderer config, the four existing material instances, and the world-authoring material reference. The remaining 1,256 files, including maps, predecessor evidence, 03/04 authority and `docs/PRODUCTION.md`, are byte-identical.

The native surface fixture freezes population AI for repeatability, then measures a stationary camera and a camera pan, captures ten stationary and 32 pan frames, and drives actual W movement over resident ground before its final capture. Each profile produced all 43 captures and more than 1,300 native frame records. Cost windows never request screenshots and exclude the first 0.5 seconds after each phase change. The verifier checks native frame order, actual quality cvars, live material coverage, positive wall/GPU timings, traversal, capture identity and gross image instability.

| Profile | Stationary wall p50 / p95 (ms) | Stationary GPU p50 (ms) | Pan wall p50 / p95 (ms) | Pan GPU p50 (ms) |
| --- | ---: | ---: | ---: | ---: |
| TSR 100% | 12.90 / 14.25 | 3.142 | 11.61 / 14.28 | 3.479 |
| TAA 100% | 11.92 / 13.57 | 2.792 | 12.82 / 14.59 | 3.101 |
| TSR 67% | 11.72 / 12.92 | 2.799 | 12.06 / 13.60 | 3.158 |

These are whole-frame development measurements, not isolated material cost, a before/after speedup, or a shipping performance claim. Existing development DDC was used. Screenshot readback perturbs capture-phase pacing, so those frames are excluded from the timing results. The pixel-difference gate screens for gross stationary instability; it does not establish artistic quality or comprehensive temporal reconstruction quality.

## Visual review and retained attempts

The first shader version produced obvious directional bands and was rejected after viewing `tsr100-01/captures/static_005.png`. Its exact source and reports remain in `rejected-surface-v1/`; no evidence was rewritten. The second version uses irregular value noise. Its initial motion captures still showed blur that obscured detail, prompting the default-setting change and all three final clarity runs. The pre-clarity runs (`tsr100-02`, `taa100-01`, `tsr67-01`) remain as historical evidence. `verify_d03_01_surfaces_v1.py` preserves their original verifier schema.

Inspection of final `clarity-tsr100-01/captures/pan_014.png` and `clarity-tsr67-01/captures/pan_014.png` shows sharper world and player contours without the rejected directional grain. The scene still has primitive characters, blockout buildings and undeveloped dark areas beside the route. These captures do **not** satisfy the full AAA art/rendering direction. Individual screenshots also cannot prove a complete absence of shimmer, ghosting or disocclusion problems.

The configured `unreal.assist` route supplied bounded local Qwen advice before implementation. Its exact input/output is retained here. Unsupported suggestions were discarded; the accepted implementation was checked in native Unreal. The animation resource route returned no configured provider, and installed Unreal template assets were located as a possible next resource; no template assets have been imported in this increment. Internal authoring API and permission failures, the rejected pattern and the motion-blur retry are retained in raw logs and the production failure ledger.

## Reproduction

Run from the canonical Project root. Use new output directories; existing evidence is deliberately not overwritten.

```sh
umask 022
/opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/Linux/Build.sh BiellaGamesEditor Linux Development -Project=/root/biella/repos/biella-engine/projects/biella-games/BiellaGames.uproject -WaitMutex
python3 tests/author_d03_01_surfaces.py --output Build/Presentation/surface-readback-next
python3 tests/run_d03_01_surfaces.py --profile tsr100 --output Build/Presentation/clarity-tsr100-next
python3 tests/run_d03_01_surfaces.py --profile taa100 --output Build/Presentation/clarity-taa100-next
python3 tests/run_d03_01_surfaces.py --profile tsr67 --output Build/Presentation/clarity-tsr67-next
python3 tests/run_d02_04.py --output Build/Presentation/environment-regression-next --fps 60
```

`tests/author_d03_01_surfaces.py --rebuild` explicitly regenerates the material assets after a source edit. Without that flag, existing assets are validated and read back. The new scripts require the same local Python/Unreal environment as the existing project runners, with NumPy and Pillow for capture verification. The runner starts Unreal as the `unreal` user; source and libraries must be readable by that user.

## Remaining D03-01 work

Continue the same task under Stage 3 of `docs/IMPLEMENTATION_SEQUENCE.md` and its primary contracts. This report is a checkpoint, not a new queue or status authority.

- Integrate production skeletal characters and gameplay-driven locomotion/action animation, blending and appropriate IK, with collision and lifecycle regression evidence. The current player remains a primitive presentation mesh.
- Raise world asset, lighting and atmosphere quality on the existing playable world and validate static fidelity and motion under representative traversal.
- Develop and validate the production VFX/audio presentation of actual gameplay events, including variation, spatial behavior, bounds, scalability and cleanup. Preserve the existing functioning feedback baseline.
- Qualify material/shader/PSO behavior across clean launch and cold/warm conditions, packaging and supported fallback paths. The current development-cache tests do not provide that proof.

The immediate continuation is skeletal presentation integration using the installed Unreal resources where suitable, driven by existing pawn state rather than replacing movement/gameplay authority. No owner decision or routine permission is needed to continue this authorized work.

## Durable identity

Canonical editable source remains in the Project paths above; exact task evidence remains under `Build/Presentation/`. `D03-01-rendering-increment.json` indexes current results, and `D03-01-file-manifest.json` records exact local bytes, including retained failed attempts. Git commits preserve this increment locally. The Auto Feeder owns GitHub/Drive publication and canonical status transition under the active instruction; this checkpoint makes no remote-publication or full-task-completion claim.
