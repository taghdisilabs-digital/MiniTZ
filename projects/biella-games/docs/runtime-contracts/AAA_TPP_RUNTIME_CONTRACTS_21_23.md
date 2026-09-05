# BIELLA GAMES — AAA TPP RUNTIME CONTRACTS 21–23

Status: `OWNER_DIRECTED_ACCEPTED_REQUIREMENT`
Authority: Mahdi Taghdisi, explicit current project direction, 2026-09-01
Project: Biella Games
Scope: third-part supporting runtime requirements for the playable AAA third-person game
Repository: `patrickminitz-web/biella-engine`  
Project path: `projects/biella-games`
Part: `3`
Depends on: `docs/runtime-contracts/AAA_TPP_RUNTIME_CONTRACTS_01_10.md`, `docs/runtime-contracts/AAA_TPP_RUNTIME_CONTRACTS_11_20.md`

This file captures the requested third supporting-runtime part only: VFX/runtime simulation, Save/Persistence, and Packaging/Play-test. Contract 20 Audio is already owned by `AAA_TPP_RUNTIME_CONTRACTS_11_20.md`; this file does not redefine it. It does not select a game engine, platform, programming language, middleware stack, NVIDIA dependency, release target, exact content catalog, or final quality-tier numbers unless separately approved.

The global playable target established by Contracts 01–20 remains controlling: a real-time, third-person, AAA-quality realistic shooter/survival game with highly detailed production assets and a genuinely playable world. These supporting contracts cannot be satisfied by static media, mockups, prerendered sequences, fake gameplay, or editor-only presentation.

## 21 — RUNTIME VFX + SIMULATION EFFECTS

VFX must be generated or driven by actual runtime state. A beautiful offline effect, composited trailer effect, prerendered explosion, or looping particle demonstration does not prove gameplay VFX implementation.

Runtime VFX may include, where the approved game design requires them:
- weapon muzzle/impact effects, tracers or projectile presentation;
- impact debris, decals, dust and material-response effects;
- infected/blood/biological effects appropriate to the accepted content direction;
- smoke, fire, steam, fog, sparks and volumetric effects;
- weather and atmospheric effects;
- vehicle effects;
- destruction/fracture presentation;
- environmental hazard and arena-pressure effects;
- interaction, traversal and world-state feedback.

Required behavior:
- effects spawn from the real gameplay event, world position, surface/material context and actor state that caused them;
- effect lifetime, attachment, orientation and movement remain spatially coherent under camera/player/world motion;
- VFX that visually represents a hit, hazard, destruction state or gameplay condition must match the authoritative gameplay state rather than inventing a separate visual result;
- purely visual particles must not silently become gameplay authority unless the owning gameplay system explicitly consumes their simulation state;
- collision-aware effects use the selected runtime's actual collision/simulation interfaces where required;
- pooling, reuse, culling, LOD/scalability, simulation bounds and off-screen behavior prevent unbounded entity, particle, draw, memory or compute growth;
- transparent/volumetric overdraw, GPU simulation cost, lighting cost and temporal reconstruction artifacts are measured in representative dense scenes;
- effects remain stable in motion: no unacceptable ghosting, popping, frame-to-frame instability, detached decals, broken depth ordering, camera-space swimming or obvious repetition;
- effects must preserve gameplay readability and cannot routinely hide targets, routes, hazards, reticles or interaction information unless intentional gameplay rules explicitly require obscuration;
- all source effects remain editable/rebuildable from Project-owned source or legally usable dependencies with provenance recorded where required.

NVIDIA-specific technologies are optional replaceable implementations, never game-semantic authority. Where the chosen runtime supports them, current NVIDIA reference capabilities include PhysX/Flow for real-time smoke/fire and related simulation families, PhysX Blast for fracture/destruction, and GPU-accelerated simulation paths. Their use is accepted only when the selected game runtime, project license/provenance requirements, measured quality and measured performance justify them.

When temporal reconstruction, ray reconstruction, upscaling or frame generation is enabled, dense VFX scenes must be validated for motion-vector/depth correctness and temporal stability. Generated/display frames must remain distinguished from native simulation/render work.

Acceptance requires live gameplay-triggered VFX in the real runtime, with representative dense-scene validation covering visual correctness, gameplay-state agreement, temporal stability and measured resource cost relevant to the selected implementation.

## 22 — SAVE + PERSISTENCE + RECOVERY

A playable production game must preserve the Project-defined durable game state across process exit/relaunch without relying on chat context, editor memory, GPU memory, temporary cache or an active development session.

The exact save model depends on the approved game loop, but the persistence system must support the state that the final design declares durable, which may include:
- player progression and unlocked state;
- current run/session checkpoint state where applicable;
- mission/objective state;
- world-state changes that are declared persistent;
- inventory/loadout or equivalent owned gameplay state where implemented;
- settings and accessibility preferences;
- content/schema version identifiers needed to interpret stored state.

Required properties:
- persistence is explicit and versioned rather than an opaque dump of transient runtime memory;
- authoritative save data is written atomically or through an equivalent recoverable transaction pattern so interruption does not silently produce a half-written accepted state;
- corrupt, incomplete or incompatible data is detected and does not masquerade as a valid load;
- the runtime has a defined recoverable outcome for failed writes/reads rather than silently discarding accepted progress;
- save/load boundaries distinguish durable gameplay state from rebuildable cache, streamed assets, transient AI state and renderer state;
- duplicate/retried save operations do not create contradictory authoritative state;
- loading reconstructs required game state through real runtime systems rather than displaying a preauthored approximation;
- migrations or compatibility transforms for changed schemas are explicit when a newer build must consume older supported save data;
- debug/development saves are not silently accepted as production-format compatibility evidence.

Biella Engine Run Memory, Project Memory and execution checkpoints are not substitutes for the shipped game's own Project-scoped persistence. The game may consume Engine production capabilities during development, but its runtime save contract remains a Biella Games Project responsibility.

Acceptance requires creating durable game state in a running build, saving it, terminating the game process, relaunching from the same exact build/source identity, loading the save and verifying the required player/world/mission/settings state from the reconstructed runtime.

## 23 — PACKAGING + LAUNCH + PLAY-TEST EVIDENCE

Editor play is necessary development evidence but is not sufficient release/package evidence. A shippable gameplay revision must be packageable and launchable through the selected target runtime outside the editor once that target is approved.

Required package properties:
- exact source/build identity is recorded for the produced package;
- required game assets, cooked/processed content, shaders/pipelines, native/runtime libraries and configuration are included through the selected build system rather than depending on undeclared editor-local state;
- the package launches through its intended executable/application entry point without requiring the editor to provide gameplay functionality;
- missing/corrupt required files produce a detectable failure rather than a false successful launch;
- enabled optional vendor/runtime features degrade or disable through their supported capability checks rather than making unsupported hardware appear to satisfy the feature;
- development-only placeholders, watermarks, debug-only middleware binaries and test-only assets are excluded from a release-intended build unless explicitly required for an approved diagnostic build;
- packaging preserves legal/provenance requirements for included third-party content and runtime dependencies;
- package size, install layout, startup cost, shader/asset preparation and runtime memory/streaming behavior are measured when they materially affect the approved target;
- crash, assert, fatal log and content-load failures observed during package play are retained as evidence and not hidden by a successful build exit code.

For enabled NVIDIA integrations, package validation must use the production libraries/configuration required by the selected integration and verify feature support at runtime. NVIDIA Streamline capability checks and NVIDIA Reflex/Reflex 2 instrumentation may be used where supported; NVIDIA Nsight Aftermath may provide GPU crash evidence for supported graphics APIs. These tools do not replace broader platform/runtime evidence.

Required play-test proof, as applicable:
`PACKAGE IDENTITY -> CLEAN LAUNCH -> LIVE INPUT -> PLAYER/CAMERA RESPONSE -> GAMEPLAY/SIMULATION -> AI/WORLD REACTION -> SAVE/LOAD OR OTHER REQUIRED STATE -> REAL-TIME RENDER/AUDIO/VFX -> MEASURED LOGS/PERFORMANCE -> PROCESS EXIT/RELAUNCH WHERE REQUIRED`.

A successful package command, installer creation, executable file, screenshot, trailer, benchmark overlay or agent statement is insufficient alone.

Acceptance requires launching the packaged game outside the editor and executing the Task-required playable flow with decoded runtime evidence, relevant logs, state changes and measured performance/resource evidence. Exact platform-specific certification, store submission, installer technology and release-channel requirements remain `UNKNOWN` until separately approved.

## NVIDIA IMPLEMENTATION REFERENCES — NON-AUTHORITATIVE

These references were checked on 2026-09-01 only to keep optional NVIDIA implementation language aligned with current vendor capabilities. They do not turn NVIDIA into a permanent game-engine, renderer, physics or platform dependency.

- NVIDIA PhysX developer reference: `https://developer.nvidia.com/physx-sdk`
- NVIDIA Omniverse Flow documentation: `https://docs.omniverse.nvidia.com/extensions/latest/ext_fluid-dynamics.html`
- NVIDIA DLSS 4.5 developer reference: `https://developer.nvidia.com/rtx/dlss`
- NVIDIA Streamline SDK: `https://developer.nvidia.com/rtx/streamline`
- NVIDIA Reflex developer technology: `https://developer.nvidia.com/performance-rendering-tools/reflex`
- NVIDIA Nsight Aftermath SDK: `https://developer.nvidia.com/nsight-aftermath`

## COMMON COMPLETION RULE

For Contracts 21–23, `COMPLETE` requires editable source + actual packaged/runtime execution where applicable + task-derived validation. VFX media can support appearance evidence, save files can support persistence evidence, and build outputs can support packaging evidence, but none of those artifacts substitutes for live game-runtime proof of the behavior it claims.
