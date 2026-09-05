# Biella Games Technical Decisions

Status: `ACTIVE_DECISION_REGISTRY`
Authority: Mahdi Taghdisi
Project: Biella Games
Repository: `patrickminitz-web/biella-engine`  
Project path: `projects/biella-games`
Last decision update: `2026-09-01`

## Purpose

This file records implementation decisions that materially determine the real editable game project, runtime, build, target hardware, asset pipeline or shipping configuration.

`UNKNOWN` means the decision has not been accepted yet. It is not permission for an agent, tool, provider or implementation worker to choose a value automatically.

Do not infer a decision from tool availability, an installed SDK, an NVIDIA GPU, a generated asset, an old planning document, a vendor recommendation, an engine-neutral runtime contract, or a temporary development experiment.

## Decision authority

A decision becomes active when Mahdi explicitly selects it or explicitly delegates the selection in a current instruction. The 2026-09-01 instruction to fill the Game technical decisions authorizes the bootstrap/runtime selections recorded below.

When a decision is accepted, use the exact selected value. Preserve superseded values as history only when needed for migration or compatibility; do not keep two active choices.

## Current decisions

| Decision | Status | Active value | Evidence / authority |
|---|---|---|---|
| Game engine / primary runtime | `ACCEPTED` | `Unreal Engine 5` | Owner-delegated selection, 2026-09-01 |
| Game engine exact version | `ACCEPTED` | `Unreal Engine 5.8.2` | Epic 5.8.2 hotfix released 2026-08-25; owner-delegated selection, 2026-09-01 |
| Engine distribution baseline | `ACCEPTED` | `Epic Unreal Engine 5.8.2 release; do not base the project on an NvRTX preview branch` | NVIDIA lists NvRTX 5.8 as Preview; vendor branch remains optional/replaceable |
| Primary gameplay implementation language | `ACCEPTED` | `C++` | Engine-native production baseline for authoritative gameplay/runtime systems |
| Scripting / visual-scripting model | `ACCEPTED` | `C++ primary + Unreal Blueprint for content, animation, UI, level and bounded gameplay orchestration` | Blueprint is permitted; core authoritative systems must remain maintainable in source and must not become Blueprint-only by accident |
| Project file / source layout imposed by runtime | `ACCEPTED` | `Unreal C++ project: BiellaGames.uproject + Source/ + Content/ + Config/ + Plugins/` | Required by selected runtime bootstrap |
| Primary target platform(s) | `ACCEPTED` | `Windows PC x64 first` | First editable/runtime/play qualification target; consoles and other platforms remain later explicit targets |
| Development host operating-system requirements | `ACCEPTED` | `Windows 11 x64 primary Unreal development host` | Epic UE 5.8 recommended development OS is Windows 11 |
| Build system / build orchestration | `ACCEPTED` | `UnrealBuildTool + Unreal AutomationTool; BuildGraph when multi-step build orchestration is required` | Engine-native build/package path |
| Packaging / distributable format | `ACCEPTED` | `Win64 Unreal packaged build; Development for iteration/evidence, Shipping for distributable qualification` | First platform target |
| Rendering path / renderer configuration | `ACCEPTED` | `DirectX 12 + Shader Model 6 + Deferred Renderer + Nanite + Lumen GI/Reflections + Virtual Shadow Maps; TSR baseline reconstruction` | UE 5.8 production rendering baseline for the accepted realistic AAA/open-world direction |
| Ray-tracing / path-tracing shipping requirement | `ACCEPTED` | `Hardware ray tracing is optional and evidence-driven; path tracing is not gameplay-completion evidence or a baseline shipping requirement` | Preserve scalable real-time gameplay; do not substitute offline fidelity |
| Upscaling / reconstruction implementation | `ACCEPTED` | `Unreal TSR is the vendor-neutral baseline; NVIDIA DLSS is an optional RTX extension only after UE 5.8.2 plugin compatibility is verified` | NVIDIA's published DLSS 4.5 Unreal plugin archive currently lists UE 5.7 support; avoid making unverified 5.8 support foundational |
| Frame-generation implementation | `ACCEPTED` | `Optional only; generated/display frames never satisfy native simulation/render FPS acceptance` | Runtime contracts require native performance truth |
| Low-latency implementation / instrumentation | `ACCEPTED` | `Engine-native input/frame telemetry baseline; NVIDIA Reflex may be integrated as an optional RTX path after compatibility validation` | Vendor-neutral baseline + replaceable NVIDIA optimization |
| Physics implementation / middleware | `ACCEPTED` | `Unreal Chaos Physics` | Engine-native physics/destruction baseline |
| World partition / streaming implementation | `ACCEPTED` | `World Partition + One File Per Actor + Data Layers + HLOD` | UE 5.8 large-world baseline; World Partition provides distance-based cell streaming |
| Navigation / pathfinding implementation | `ACCEPTED` | `Unreal Navigation System / RecastNavMesh baseline` | Engine-native deterministic starting point; higher-level AI architecture remains task-scoped |
| Character animation runtime / rig integration path | `ACCEPTED` | `Unreal Skeleton/SkeletalMesh + Animation Blueprints + Control Rig + IK Rig/Retargeter; C++ owns authoritative gameplay state` | Engine-native character production path |
| VFX / simulation implementation | `ACCEPTED` | `Niagara` | Engine-native real-time VFX/simulation baseline |
| Audio runtime / middleware | `ACCEPTED` | `Unreal Audio Mixer + MetaSounds; no external audio middleware dependency at bootstrap` | Keep initial runtime self-contained and replaceable |
| Save/persistence file format and storage location | `ACCEPTED` | `UE SaveGame/custom versioned serialization under the platform per-user save location; cloud/platform provider deferred` | Supports first playable persistence without locking an external service |
| Editable 3D source format(s) | `UNKNOWN` | `UNKNOWN` | Select with the first real asset-production pipeline; do not block runtime bootstrap |
| Runtime mesh / scene format(s) | `ACCEPTED` | `Unreal cooked .uasset/.umap runtime content` | Selected engine/runtime |
| Texture/material source format(s) | `UNKNOWN` | `UNKNOWN` | Select with first production material/texture pipeline |
| Runtime texture/material format(s) | `ACCEPTED` | `Unreal cooked texture/material assets` | Selected engine/runtime |
| Animation source/runtime format(s) | `UNKNOWN` | `UNKNOWN` | Select import interchange format with first character pipeline; runtime representation is Unreal animation assets |
| Audio source/runtime format(s) | `ACCEPTED` | `48 kHz WAV masters -> Unreal cooked audio assets` | Production-source and runtime split |
| Source-control large/binary asset strategy | `ACCEPTED` | `GitHub Git for source/docs + Git LFS for large binary game assets when they enter the repository` | Prevent ordinary Git history from absorbing large mutable binary assets |
| Continuous-integration/build service | `UNKNOWN` | `UNKNOWN` | Select after the UE 5.8.2 project opens/builds on the primary development host |
| Target hardware tier(s) | `UNKNOWN` | `UNKNOWN` | Set from measured representative gameplay, not bootstrap ambition |
| Target GPU tier(s) / vendor requirement | `UNKNOWN` | `UNKNOWN` | NVIDIA RTX features are optional extensions; minimum/recommended GPU comes from measured qualification |
| Target system RAM | `UNKNOWN` | `UNKNOWN` | Measure after representative world/content exists |
| Target VRAM | `UNKNOWN` | `UNKNOWN` | Measure after representative world/content exists |
| Target storage/install footprint | `UNKNOWN` | `UNKNOWN` | Measure after representative cooked content exists |
| Target display resolution tier(s) | `UNKNOWN` | `UNKNOWN` | Lock during performance qualification from measured quality/performance data |
| Target native rendered FPS / frame-time tier(s) | `UNKNOWN` | `UNKNOWN` | Lock during performance qualification; generated frames are excluded from native target |
| Target end-to-end/input latency | `UNKNOWN` | `UNKNOWN` | Measure on accepted hardware after first playable input/render chain exists |
| Frame-time percentile / hitch budgets | `UNKNOWN` | `UNKNOWN` | Establish from captured runtime telemetry on representative traversal/combat scenarios |

## Selection basis for the runtime baseline

As of 2026-09-01:

- Epic's current released Unreal Engine line is UE 5.8, with the 5.8.2 hotfix released on 2026-08-25.
- Epic documents UE 5.8's large-world World Partition workflow and recommends DirectX 12 / Shader Model 6 for Nanite, Lumen and Virtual Shadow Maps class features.
- NVIDIA exposes an NvRTX 5.8 branch as **Preview**, while its stable public UE 5.7 path is further along. Biella Games therefore uses Epic UE 5.8.2 as the foundation and treats NVIDIA DLSS/Reflex/NvRTX features as optional replaceable integrations rather than runtime identity.

This choice keeps the editable project on the current stable Epic release without making an NVIDIA preview branch a permanent dependency.

## Already accepted direction that is not an implementation choice

The following are current Project requirements and must not be reset to `UNKNOWN`:

- real-time interactive 3D gameplay rather than static/prerendered substitution;
- third-person player presentation for normal shooter gameplay;
- realistic, physically coherent, highly detailed AAA-quality real-time visual target;
- real runtime world geometry, collision, traversal and gameplay state;
- editable source plus runtime evidence for feature completion;
- project-specific game source lives under `projects/biella-games/` inside canonical `patrickminitz-web/biella-engine`; repository unification does not make that source reusable Engine scope;
- optional provider/vendor features remain replaceable unless explicitly accepted as a requirement.

## Actual game-project creation gate

The engine/runtime gate is now **satisfied** by the accepted Unreal Engine 5.8.2 decision.

The next implementation action is:

1. create the real `BiellaGames.uproject` Unreal C++ project inside this repository;
2. create the engine-native `Source/`, `Content/`, `Config/`, and `Plugins/` boundaries required by the initial project;
3. open the project successfully in Unreal Engine 5.8.2 on the accepted Windows development host;
4. record exact source revision + editor/runtime open evidence;
5. continue according to `docs/IMPLEMENTATION_SEQUENCE.md`, beginning with the Stage 1.1 player + camera + input chain.

Do not wait for deferred hardware/performance/content-pipeline decisions unless they become required by the active implementation task.

## Decision record format

When replacing a remaining `UNKNOWN`, record enough information to reproduce the choice:

```yaml
decision: <stable decision name>
status: ACCEPTED
value: <exact selected value/version>
accepted_date: YYYY-MM-DD
authority: <owner instruction or accepted source evidence>
source_ref: <commit/file/record when applicable>
supersedes: <prior accepted value|null>
notes: <only material constraints>
```

If a later accepted decision changes a prior one, update the active table to the new value and preserve the old choice only as explicit superseded history where migration/compatibility work needs it.
