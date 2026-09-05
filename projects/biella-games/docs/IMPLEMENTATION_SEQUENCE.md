# Biella Games Implementation Sequence

Status: `OWNER_DIRECTED_EXECUTION_ORDER`
Authority: Mahdi Taghdisi
Project: Biella Games
Repository: `patrickminitz-web/biella-engine`  
Project path: `projects/biella-games`

## Purpose

The runtime contracts under `docs/runtime-contracts/` define requirements and acceptance conditions. They are **not** implementation order.

This file converts the accepted requirements into a dependency-oriented build sequence for the real playable game.

Do not implement Contracts 01–59 numerically. Execute the smallest playable dependency chain first, then expand breadth, scale, quality and release qualification.

## Entry state

Current repository authority defines a real-time third-person realistic AAA-quality game target and now accepts **Unreal Engine 5.8.2** as the primary runtime in `docs/TECHNICAL_DECISIONS.md`. The actual engine-native editable game project has not yet been created in this repository.

Therefore the first implementation boundary is no longer runtime selection or additional concept work. It is creation of the real Unreal Engine 5.8.2 C++ project, proof that the editor/runtime opens it, and then the first playable Stage 1.1 chain.

## Stage 0 — Runtime selection + real project bootstrap

### 0.1 Accepted runtime decision

The required bootstrap decisions are now accepted in `docs/TECHNICAL_DECISIONS.md`:

- **Game engine / primary runtime:** Unreal Engine 5;
- **Exact engine version:** Unreal Engine 5.8.2;
- **Primary gameplay implementation language:** C++;
- **Scripting model:** C++ primary + bounded Unreal Blueprint orchestration;
- **First platform/runtime baseline:** Windows PC x64, DirectX 12 + Shader Model 6;
- **Build/package path:** UnrealBuildTool + Unreal AutomationTool, Win64 packaged builds.

Do not silently switch the project to another engine, Unreal version, NvRTX preview branch, language/runtime baseline, or platform. Future accepted changes belong in `docs/TECHNICAL_DECISIONS.md`.

Do not block project creation on unrelated future decisions such as final platform certification, exact hardware tiers, final frame-rate targets or complete content catalogs unless the active bootstrap genuinely requires them.

### 0.2 Create the real editable project

Create the actual Unreal Engine 5.8.2 C++ game project/source inside `patrickminitz-web/biella-engine` under `projects/biella-games/`.

Minimum bootstrap result:

- real engine-native `BiellaGames.uproject` and editable source tree;
- runtime/editor opens the project successfully;
- one executable/editor-play entry map/scene/world;
- deterministic project/build configuration under source control where applicable;
- initial `Source/`, `Content/`, `Config/`, and `Plugins/` boundaries appropriate to the selected engine;
- test/qualification/evidence directories or tooling required by the selected runtime;
- package/build path sufficient to prove the project is a game project rather than documentation only.

Do not create the game implementation in `patrickminitz-web/biella-engine`.

**Bootstrap acceptance:** exact source revision + real Unreal Engine 5.8.2 editor/runtime open/launch evidence from the created project.

## Stage 1 — First playable vertical slice

This stage establishes one end-to-end real gameplay chain before large-world breadth or asset volume.

### 1.1 Player + camera + input

Implement first:

`runtime bootstrap -> player spawn -> third-person player -> camera -> continuous input -> collision-safe control`

Primary contracts:
- 01 Playable Runtime Acceptance
- 02 Third-Person Player + Camera + Control
- 38 Input Mapping + Settings + Accessibility Runtime, only the minimum control mapping needed now
- 50 Player Lifecycle + Spawn / Death / Restart, initial spawn lifecycle
- 51 Game Session + Pause + Mode State Ownership, minimum gameplay-mode ownership

**Acceptance:** interactive runtime session with real player locomotion, camera control, input response and valid collision/obstruction behavior.

### 1.2 Real world geometry + collision

Implement:

`playable level/world geometry -> real scale -> collision -> traversal surfaces -> runtime lighting/materials`

Primary contracts:
- 03 Real-Time 3D World
- 05 Open-World City Runtime Architecture, only architecture needed by the initial slice
- 13 Physics + Destruction, collision/physics foundation first
- 27 Interaction + Traversal Runtime, minimum traversal needed by the slice
- 35 Interior / Exterior + Vertical World Continuity only if the initial slice crosses those boundaries

**Acceptance:** player moves through actual runtime geometry with valid collision/traversal and no rendered-backdrop substitution.

### 1.3 Playable character runtime integration

Implement:

`runtime character asset -> skeleton/rig -> locomotion -> aim/orientation -> collision/hit representation`

Primary contracts:
- 07 Playable Character Production
- 14 Animation System
- 39 Production Asset Integration + Runtime Validation

Use the minimum production-quality character needed to prove the pipeline. Do not block the entire vertical slice on a final cosmetic catalog.

**Acceptance:** possessed/controlled runtime character animates, collides, orients and renders correctly during gameplay.

### 1.4 Weapon + combat + damage consequence

Implement:

`equip -> aim -> fire/action -> hit/collision resolution -> damage -> target reaction -> gameplay state change`

Primary contracts:
- 08 Combat + Game-Weapon Runtime
- 26 Health + Damage + Status + Actor Reaction
- 21 VFX + Runtime Effects, minimum event-driven combat effects
- 20 AAA Game Audio Runtime, minimum event-driven combat audio
- 37 Game Feel + Feedback + Haptics Integration, only supported feedback needed by the slice

Do not substitute a weapon model, muzzle-flash render or canned animation for actual combat state.

**Acceptance:** reproducible real input -> combat action -> hit/collision -> damage/state -> reaction chain.

### 1.5 One rival contestant

Implement one real autonomous rival before population scaling.

Primary contracts:
- 09 Rival Contestant AI Runtime
- 31 Navigation + Pathfinding + Traversable-World Runtime
- 32 Encounter + Spawn + Population Orchestration, minimum valid spawn/activation

Required minimum behavior:
- spawn in valid world state;
- navigate real geometry;
- perceive relevant gameplay state;
- make multiple observable state/decision transitions;
- participate in combat/survival response rather than following a cinematic spline.

**Acceptance:** one live rival reacts to changing conditions and produces real gameplay state changes.

### 1.6 Infected runtime actor

Implement one or a small bounded infected set before horde scaling.

Primary contracts:
- 10 Infected / Zombie Runtime
- 31 Navigation + Pathfinding
- 32 Encounter + Spawn
- 34 Multi-Actor Combat + Horde / Crowd Scalability only at the minimum cross-actor level needed now

Required minimum:
- runtime navigation;
- perception/target response;
- attack/reaction/damage/death state;
- interaction with player and rival where the slice permits it.

**Acceptance:** infected independently create gameplay consequences rather than serving as background animation.

### 1.7 Arena pressure

Add the first actual arena-pressure state only after player, rival, infected and world systems exist to react to it.

Primary contracts:
- 15 World Simulation
- 28 Environmental Runtime States + Weather / Lighting / Hazards where pressure changes environment state
- 33 Arena Pressure Runtime

Do not invent the exact pressure mechanic if it remains unapproved. Implement only the owner-approved mechanic/state.

**Acceptance:** one pressure transition changes actual world/gameplay state and causes at least two relevant systems to respond to the same authoritative state.

### 1.8 First executable mission

Implement a small mission around the existing playable systems rather than building mission logic before gameplay exists.

Primary contracts:
- 12 Mission Runtime
- 24 Runtime UI + HUD + Gameplay Readability, minimum objective/status UI
- 25 Inventory + Loot + Equipment Runtime only if the mission requires item state

Required chain:

`objective activation -> real gameplay condition -> progress/state transition -> success/failure -> valid recovery/retry`

**Acceptance:** mission state changes only from real gameplay/system events.

### 1.9 Save + reconstruction

Add persistence after the vertical slice has meaningful state worth persisting.

Primary contracts:
- 22 Save + Persistence + Recovery
- 54 World State Persistence + Reconstruction
- 55 Content Dependency + Version Compatibility, minimum save/content identity support

**Acceptance:** create state -> save -> terminate/tear down -> relaunch -> load -> reconstruct required player/mission/world/settings state without duplication or corruption.

### 1.10 Package + real play evidence

Close the first vertical slice with an actual runnable game build/package when the selected runtime supports packaging at this milestone.

Primary contracts:
- 06 Runtime Evidence + Feature Acceptance
- 23 Build + Package + Launch + Play Qualification
- 40 Runtime Telemetry + Measured Evidence
- 41 Frame Pacing + Stutter + Hitch Control
- 42 Input Latency + Control Responsiveness
- 43 CPU + GPU + VRAM + RAM Resource Accounting
- 47 Crash / Hang / Assert / Diagnostic Evidence
- 48 Reproducible Runtime Scenarios + Regression Automation

**Vertical-slice acceptance:** exact source/build identity -> clean runtime/package launch -> live player control -> combat -> rival -> infected -> approved arena pressure -> mission state -> save/reconstruction where included -> runtime rendering/audio/VFX -> measured logs/performance -> clean exit/relaunch evidence where required.

## Stage 2 — Open-world and systemic expansion

Only after the first vertical slice works end to end, expand the world and simulation.

### 2.1 World streaming and continuity

Primary contracts:
- 05 Open-World City Runtime Architecture
- 18 LOD + Streaming + Memory Residency
- 35 Interior / Exterior + Vertical World Continuity
- 44 Streaming Stress + World-Traversal Continuity
- 45 LOD / HLOD / Culling / Occlusion Correctness

Build additional streamed regions, connected routes, vertical/interior transitions and world-state reconstruction without breaking the proven slice.

### 2.2 Population and encounter scaling

Primary contracts:
- 15 World Simulation
- 31 Navigation
- 32 Encounter/Spawn/Population
- 34 Multi-Actor Combat + Horde/Crowd Scalability

Increase rival/infected/population density from measured evidence. Do not choose target counts from ambition alone.

### 2.3 Vehicles

Primary contract:
- 11 Vehicle Runtime

Integrate vehicles only when approved and when the world, collision, streaming, camera and animation foundations can support them.

### 2.4 Deeper interaction, destruction and environment state

Primary contracts:
- 13 Physics + Destruction
- 27 Interaction + Traversal
- 28 Environmental Runtime States

Add only approved gameplay-relevant destruction, hazards, weather/power/environment transitions and world interactions.

## Stage 3 — Production rendering, animation, VFX and audio quality

Raise production quality on top of functioning gameplay rather than building isolated showcase scenes.

Primary contracts:
- 04 AAA Realistic Art + Rendering Direction
- 14 Animation System
- 16 AAA Real-Time Rendering Pipeline
- 20 AAA Game Audio Runtime
- 21 VFX + Runtime Effects
- 37 Game Feel + Feedback + Haptics
- 39 Production Asset Integration + Runtime Validation
- 46 Shader / PSO / Material Pipeline Stability
- 49 Quality Scalability + Vendor-Neutral Advanced Rendering

Requirements:
- gameplay and cinematics use the same underlying production assets/world where claimed;
- accepted baseline rendering follows `docs/TECHNICAL_DECISIONS.md`;
- optional ray tracing, DLSS, frame generation and Reflex remain replaceable extensions unless later made explicit requirements;
- static fidelity, motion quality, temporal stability and measured runtime cost all matter.

## Stage 4 — Content system multiplication

Once core systems are stable, multiply content through reusable definitions instead of isolated logic.

Primary contracts:
- 25 Inventory + Loot + Equipment
- 29 Data-Driven Content + Variant Multiplication
- 32 Encounter + Spawn + Population
- 52 Difficulty + Tuning + Balance Data
- 53 Progression + Unlock + Meta-State Runtime, only if progression is approved
- 55 Content Dependency + Version Compatibility

Add missions, items, weapons, actor variants, infected/rival variants, encounters, environment states and tuning through shared systems where practical.

## Stage 5 — UI, settings, localization and accessibility

Expand player-facing product surfaces after the runtime systems they control exist.

Primary contracts:
- 24 Runtime UI + HUD + Gameplay Readability
- 38 Input Mapping + Settings + Accessibility Runtime
- 51 Game Session + Pause + Mode State Ownership
- 56 Localization + Subtitles + Text Runtime
- 57 Accessibility + Comfort Implementation Evidence

Do not ship placeholder settings. Every exposed option must change the real runtime subsystem it claims to control.

## Stage 6 — Cinematic and presentation integration

Primary contract:
- 36 Runtime Cinematic / Sequence + Gameplay Handoff

Build in-game cinematics/sequences only after the real gameplay/world actors and state exist. A cinematic may present gameplay state but cannot substitute for implementing it.

## Stage 7 — Performance, stability and scalability qualification

Continuously measure performance from Stage 1 onward; perform full production qualification after representative world/content scale exists.

Primary contracts:
- 17 Performance + Frame Pacing Contract
- 18 LOD + Streaming + Memory Residency
- 40 Runtime Telemetry + Measured Evidence
- 41 Frame Pacing + Stutter + Hitch Control
- 42 Input Latency + Control Responsiveness
- 43 Resource Accounting
- 44 Streaming Stress
- 45 LOD/Culling/Occlusion
- 46 Shader/PSO/Material Stability
- 47 Crash/Hang/Diagnostic Evidence
- 48 Reproducible Runtime Scenarios
- 49 Advanced Rendering/Scalability

Exact target hardware, FPS, resolution, RAM/VRAM and latency thresholds come from accepted values in `docs/TECHNICAL_DECISIONS.md`, not from this sequence.

## Stage 8 — Delivery, update and release-candidate qualification

Primary contracts:
- 23 Build + Package + Launch + Play Qualification
- 55 Content Dependency + Version Compatibility
- 58 Patch / Update / Save-Compatibility Delivery
- 59 Release-Candidate Playable Qualification

Before release-candidate status, require the exact packaged build to launch and play outside the editor where applicable, with measured runtime evidence tied to exact source/build identity.

## Cross-cutting rules

At every stage:

- preserve real editable source and exact source identity;
- do not use screenshots, renders, trailers, HTML demos or fake HUDs as implementation proof;
- keep Biella Games project systems inside this repository;
- keep Biella Engine universal mechanisms separate;
- do not infer remaining `UNKNOWN` technical decisions;
- preserve newer valid work and recover the smallest failed boundary;
- use task-derived validation rather than a permanent reviewer pipeline;
- commit/publish source changes durably and remotely read them back;
- update matching canonical Drive authority/continuity records when their content changes;
- generated assets remain candidates until explicitly accepted.

## Current next implementation boundary

The runtime selection gate is closed. The next game-source implementation boundary is:

`CREATE REAL EDITABLE UNREAL ENGINE 5.8.2 C++ PROJECT IN THIS REPOSITORY -> OPEN/LAUNCH IT -> RECORD SOURCE/RUNTIME EVIDENCE -> BEGIN STAGE 1.1 PLAYER + CAMERA + INPUT`

Do not continue adding numbered runtime contracts merely to avoid crossing this real implementation boundary.
