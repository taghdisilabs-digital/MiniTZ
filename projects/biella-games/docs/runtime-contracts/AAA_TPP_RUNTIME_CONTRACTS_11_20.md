# BIELLA GAMES — AAA TPP RUNTIME CONTRACTS 11–20

Status: `OWNER_DIRECTED_ACCEPTED_REQUIREMENT`
Authority: Mahdi Taghdisi, explicit current project direction, 2026-09-01
Project: Biella Games
Scope: playable AAA realistic third-person shooter/survival implementation
Repository: `patrickminitz-web/biella-engine`  
Project path: `projects/biella-games`
Depends on: `docs/runtime-contracts/AAA_TPP_RUNTIME_CONTRACTS_01_10.md`

These ten contracts extend the accepted 01–10 runtime requirements. They do not select a game engine, engine version, platform, exact world dimensions, vehicle catalog, mission count, destruction scope, audio middleware, or final performance targets unless separately approved.

Global rule: every subject below must exist as editable game/project source and execute in the real-time runtime. A screenshot, concept render, offline sequence, fake UI, cinematic-only demonstration, or clickable presentation cannot satisfy implementation completion.

## 11 — VEHICLE RUNTIME

Vehicles are real runtime gameplay entities, not static props or cinematic objects.

Required where a vehicle is implemented:
- player entry/exit and control are runtime state transitions;
- steering, acceleration, braking and reverse are input-driven;
- chassis/wheel contact, collision and movement use the selected runtime physics/vehicle model;
- suspension/wheel behavior, body motion and surface contact remain visually and physically coherent;
- collision produces real gameplay/physics response rather than a prerecorded animation;
- vehicle state can interact with player, rivals, infected and world geometry where the current design permits;
- camera, animation, audio, VFX, lights and damage state remain synchronized with runtime vehicle state;
- LOD, material, interior/exterior detail and streaming behavior support open-world use;
- AI-driven or ambient traffic, if implemented, uses actual navigation/traffic logic rather than spline-only decoration unless explicitly scoped as background traffic;
- exact makes/models, handling values, traffic density and damage depth remain separately defined.

Acceptance requires a running sequence proving entry -> control -> traversal -> collision/response -> exit or another real vehicle state transition.

## 12 — MISSION RUNTIME

A mission is an executable gameplay-state system, not mission text, storyboards, key art or a cinematic sequence.

Required:
- mission identity/version is data- or source-defined and reproducible;
- objectives are bound to real runtime conditions/events;
- objective state changes only from valid gameplay/system events;
- success/failure states are explicit and observable;
- checkpoints/restart/resume behavior preserves valid mission state where the approved design requires it;
- mission logic reacts correctly to player, rival, infected and world-state changes when relevant;
- mission scripting cannot silently bypass collision, AI, combat, inventory/resource or world rules solely to make a demo succeed;
- mission flow supports interruption/failure/retry without corrupting persistent or run-local state;
- exact mission catalog, narrative content, objective counts and progression ordering remain Project-specific.

Acceptance requires a playable mission path showing at least objective activation -> runtime progress -> state transition -> success/failure/recovery from actual gameplay events.

## 13 — PHYSICS + DESTRUCTION

Physics is runtime simulation evidence, not visual implication.

Required where applicable:
- player, vehicles, projectiles/traces, rigid bodies and interactable objects use collision layers/channels appropriate to their gameplay role;
- contact, blocking, overlap and trigger behavior are deterministic enough for debugging and test reproduction;
- dynamic objects maintain plausible mass, inertia, gravity, friction and constraint behavior for the chosen gameplay style;
- breakable/destructible objects, if approved, transition from intact to damaged/destroyed runtime states with cause-and-effect evidence;
- destruction debris derives from the affected object/structure and must not create impossible floating or unsupported geometry;
- destruction cannot remove required collision while leaving invisible blockers or preserve collision where the visible structure no longer exists unless intentionally designed;
- physics state across streaming, checkpoints and mission transitions remains valid;
- visual damage and runtime collision/damage state remain synchronized;
- expensive simulation may use bounded approximations/LOD, but distant or reduced simulation cannot falsify local gameplay state.

Acceptance requires reproducible runtime evidence of collision/physics or destruction causing real object/world/gameplay state change.

## 14 — ANIMATION SYSTEM

Animation is a runtime control layer connected to gameplay state, not a collection of rendered clips.

Required for playable characters and active actors:
- locomotion supports direction/speed/state changes without persistent foot sliding or broken root motion;
- idle/move/run/turn/aim/action transitions blend without unacceptable popping;
- upper/lower-body coordination supports shooter aiming and locomotion where the chosen implementation requires it;
- IK/contact correction is used where needed for feet, hands, weapons, interaction points or uneven surfaces;
- hit, damage, death, traversal, interaction and vehicle states synchronize with actual gameplay events where implemented;
- animation cannot continue a state that gameplay has already cancelled or invalidated;
- animation state, collision, navigation and weapon/combat state remain aligned;
- LOD/reduced animation evaluation may optimize distant actors without breaking authoritative gameplay state;
- runtime retargeting or shared rigs may be used when technically appropriate, but deformation quality must remain production-grade.

Acceptance requires interactive runtime transitions driven by gameplay/input, including locomotion plus at least one non-locomotion gameplay state.

## 15 — WORLD SIMULATION

The open city must behave as a living runtime system rather than a static environment shell.

Required as each subsystem is implemented:
- player, rivals, infected, missions and arena-pressure/world events share the same authoritative world state;
- actor spawning/despawning is bounded by valid world/streaming rules;
- ambient population/traffic/environmental simulation may scale with distance/resource pressure but cannot corrupt nearby gameplay truth;
- doors, elevators, lights, hazards, interactables or other world systems expose real runtime state when present in approved gameplay;
- world events can change navigation, risk, resources or encounter conditions when the design requires it;
- actors entering/leaving streamed regions preserve valid identity/state or are deterministically reconstructed according to the chosen architecture;
- simulation updates cannot depend on the rendering camera being pointed at the object unless explicitly optimized with equivalent authoritative state;
- systemic interaction remains centered on `PLAYER + RIVAL CONTESTANTS + INFECTED + ARENA PRESSURE`.

Acceptance requires a running scenario showing at least two independent systems reacting to a shared world-state change.

## 16 — AAA REAL-TIME RENDERING PIPELINE

The shipping visual target is realistic, physically coherent, high-detail real-time rendering during gameplay.

Required pipeline capabilities, implemented according to the selected engine/runtime:
- physically based shading/material workflow;
- coherent direct and indirect lighting appropriate to the selected rendering path;
- stable shadowing with distance/quality scaling that does not visibly break gameplay presentation;
- reflections appropriate to material/world requirements using supported real-time techniques;
- atmospheric depth, fog/volumetrics and exposure that preserve navigation and gameplay readability;
- high-quality anti-aliasing/upscaling strategy with temporal stability under motion;
- post-processing that enhances realism without hiding geometry/material defects;
- runtime particles/VFX integrate with depth, lighting and motion rather than appearing as detached overlays;
- transparent, emissive, wet, glass, skin, hair, fabric and hard-surface materials use appropriate physically plausible treatment where present;
- generated/display frames, if used, are reported separately from native rendered frames and simulation rate;
- image reconstruction/frame-generation/ray-tracing features from NVIDIA or equivalent vendors are replaceable performance/quality implementations, not proof of correctness.

Reject persistent shimmer, ghosting, texture swimming, reflection instability, broken disocclusion, obvious LOD flashes, lighting discontinuity or frame-generation artifacts that materially damage gameplay readability.

Acceptance requires decoded runtime capture plus measured native frame-time/performance evidence from the same build/source identity.

## 17 — PERFORMANCE + FRAME PACING CONTRACT

AAA visual quality must remain an actual real-time game result.

Until platform/quality-tier targets are explicitly approved, performance limits are measured and reported rather than invented.

Every significant runtime qualification must record, where applicable:
- native rendered FPS and frame time;
- simulation/update rate;
- CPU frame time and major-thread cost when observable;
- GPU frame time/utilization;
- VRAM and system RAM residency;
- streaming/upload stalls;
- shader/PSO or asset compilation stalls;
- input/system latency when measurable;
- generated/display-frame rate separately from native rendered rate;
- frame-time percentiles or equivalent evidence sufficient to expose stutter rather than only average FPS.

Required behavior:
- no performance claim may rely solely on an uncapped empty scene, still camera or offline render;
- representative gameplay must include world geometry plus active gameplay actors/systems appropriate to the tested milestone;
- performance regression must be attributable to exact source/build/configuration where practical;
- quality reduction is explicit and versioned rather than silently changing visual requirements to obtain a pass;
- hardware-specific optimization may improve a route but cannot redefine game correctness.

Acceptance requires measured runtime evidence from representative playable scenes; exact target FPS/resolution tiers remain `UNKNOWN` until approved.

## 18 — LOD + STREAMING + MEMORY RESIDENCY

High-detail production assets must scale across an open-world runtime without collapsing memory or frame stability.

Required:
- geometry uses engine-appropriate LOD/HLOD/virtualized-geometry or equivalent distance/importance scaling;
- textures use mip/residency/streaming policy appropriate to visual importance and available memory;
- animation/simulation/AI detail may scale with distance while authoritative gameplay state remains correct;
- near-field player/character/weapon/vehicle/environment assets maintain close-range quality required by gameplay/cinematics;
- asset streaming is asynchronous or otherwise bounded so world traversal does not require long blocking loads under normal operation;
- streaming prioritizes upcoming/visible/gameplay-critical content rather than arbitrary file order;
- memory pressure is measured rather than guessed;
- stale/unneeded resources may be evicted only if authoritative project/run/game state is preserved elsewhere;
- asset replacement/LOD transitions must avoid visible scale shifts, silhouette collapse, severe texture pop or collision mismatch;
- collision/navigation data cannot unload before dependent gameplay state is safely transitioned.

Acceptance requires traversal through streamed content while recording memory/residency and demonstrating valid rendering/collision/gameplay across transitions.

## 19 — WEBSITE / GAME COMPLETION BOUNDARY

`biellagames.dev`, promotional media and interactive marketing surfaces are consumers of game/project artifacts. They are not substitutes for game implementation.

Rules:
- a website image, WebGL viewer, video, interactive hero, hotspot scene, embedded render or simulated gameplay presentation cannot mark a game feature complete;
- website content may use real runtime screenshots/captures, approved renders, 3D assets and derived media from the game production pipeline;
- any interactive website demonstration that is not the actual game runtime must be labeled and scoped as website/product presentation;
- marketing derivatives must reference their source game/artifact identity when production provenance is required;
- website optimization may reduce resolution, geometry, bitrate or interaction depth without redefining the quality of the underlying game master assets;
- accepted game requirements remain in Biella Games Project source; website UX cannot silently become gameplay canon.

Game completion proof remains editable source + build/play/runtime evidence. Website completion follows its own source/build/browser/deployment evidence.

## 20 — AAA GAME AUDIO RUNTIME

Audio is a real-time gameplay and world-system layer, not a soundtrack pasted over rendered footage.

Required where applicable:
- player, weapon, vehicle, infected, rival, impact, interaction and world sounds originate from runtime events/state;
- 3D positional/spatial audio follows source/listener transforms for world sounds;
- distance attenuation, obstruction/occlusion, interior/exterior treatment and reverb/environment response are used where supported and materially useful;
- repeated high-frequency gameplay sounds use variation/layering sufficient to avoid obvious robotic repetition;
- weapon/impact/vehicle/infected sounds remain synchronized to their actual runtime event;
- priority/voice management prevents critical gameplay cues from being unpredictably dropped under load;
- music and ambience respond to approved gameplay/world state where adaptive behavior is implemented;
- audio assets remain editable/source-traceable and final encoded runtime derivatives are validated for decode/playback;
- exact soundtrack, voice cast, language, middleware and final loudness specifications remain separately approved.

Acceptance requires a running gameplay capture/log showing runtime events producing correctly positioned/synchronized audio, plus decode/runtime validation of the used assets.

## COMMON COMPLETION RULE

For Contracts 11–20, `COMPLETE` requires editable source + actual game/runtime integration + task-derived validation. Images, offline renders, prerecorded videos, website interactions and agent statements may support evidence but cannot substitute for runtime proof.
