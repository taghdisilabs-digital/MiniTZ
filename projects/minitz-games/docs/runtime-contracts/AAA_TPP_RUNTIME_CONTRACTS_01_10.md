# BIELLA GAMES — AAA TPP RUNTIME CONTRACTS 01–10

Status: `OWNER_DIRECTED_ACCEPTED_REQUIREMENT`
Authority: Mahdi Taghdisi, explicit current project direction, 2026-09-01
Project: Biella Games
Scope: playable game implementation and runtime production
Repository: `patrickminitz-web/biella-engine`  
Project path: `projects/minitz-games`

This contract captures only the first ten approved runtime subjects. It does not select a game engine, engine version, platform, programming language, exact map size, exact character identity, exact weapon catalog, or release target unless separately approved.

Global target: a real-time, third-person, AAA-quality realistic shooter/survival game with highly detailed production assets and a genuinely playable world. `AAA`, `realistic`, `high-detail`, and `shipping-quality` are quality targets, not substitutes for measured runtime evidence.

## 01 — PLAYABLE RUNTIME ACCEPTANCE

The product is a real-time interactive 3D game.

A static image, generated picture, screenshot sequence, prerendered video, cinematic-only scene, HTML hotspot experience, clickable background, fake gameplay HUD, non-interactive 3D viewer, or pre-authored animation sequence cannot satisfy gameplay implementation or feature completion.

A gameplay feature is `REAL` only when:
- editable project/game source contains the implementation;
- the feature executes in the actual game runtime or editor play/runtime mode;
- live input or simulation drives state changes;
- required collision, physics, AI, gameplay state, and rendering execute rather than being visually implied;
- the result can be reproduced from exact source identity.

Required proof shape when applicable:
`INPUT -> PLAYER/CAMERA RESPONSE -> SIMULATION -> COLLISION/PHYSICS -> AI/WORLD REACTION -> GAMEPLAY STATE CHANGE -> REAL-TIME RENDERED RESULT`.

Website media, key art, screenshots, trailers, and renders are derivative Project artifacts. They never substitute for playable runtime evidence.

## 02 — THIRD-PERSON PLAYER + CAMERA + CONTROL

The playable game uses a third-person player presentation for normal shooter gameplay.

Required runtime behavior:
- a real controllable player entity exists in the 3D world;
- the player body is rendered and spatially grounded during normal third-person gameplay except explicit approved transitions;
- movement and view/camera input are continuous runtime controls, not pre-authored path playback;
- camera follows/orbits the player with tunable offset, distance, pitch/yaw limits, smoothing, and sensitivity;
- camera collision/obstruction handling prevents persistent wall penetration and unacceptable geometry clipping;
- aiming/shooter presentation preserves readable target direction and player orientation;
- movement, aiming, animation, collision, and camera state remain synchronized;
- input is responsive and frame-to-frame behavior is stable.

Exact shoulder side, FOV, camera distance, traversal action set, controller layout, and sensitivity defaults remain tunable until separately approved.

Acceptance requires an interactive runtime session showing continuous player locomotion, camera control, aiming orientation, collision response, and recovery from camera obstruction.

## 03 — REAL-TIME 3D WORLD

The playable world must be actual runtime 3D geometry and simulation, not a rendered backdrop.

Required:
- playable surfaces have real geometry, scale, collision, and navigation/traversal meaning;
- buildings, streets, terrain, props, barriers, doors, structures, and environmental objects use physically coherent placement and dimensions;
- materials and lighting are evaluated in the runtime rendering pipeline;
- traversable routes remain spatially valid from multiple camera angles;
- interaction objects expose real runtime state where interaction is part of the approved design;
- distant impostors/LOD proxies may optimize non-playable distance but may not masquerade as playable geometry;
- world composition preserves clear foreground/midground/background depth and navigation readability;
- generated/environment assets with floating, fused, melted, unsupported, or perspective-invalid geometry are rejected before runtime integration.

Environment completion requires actual navigable runtime geometry plus collision/traversal evidence. A concept render alone is never environment completion.

## 04 — AAA REALISTIC ART + RENDERING DIRECTION

Final playable implementation targets realistic, physically coherent, highly detailed AAA-quality 3D presentation.

Supersession: for final playable game implementation, this realistic target supersedes earlier `stylized-3D` rendering language. Existing Environment Quality Lock requirements for structural coherence, scale, modularity, material logic, lighting logic, navigation readability, damage causality, and rejection of generative artifacts remain valid. Existing environment-family identities may remain Project visual references where they do not conflict with the current realistic direction.

Required quality characteristics:
- physically based material response with credible roughness, reflectance, surface depth, wear, moisture/dirt and damage logic;
- realistic character skin, eyes, hair/fabric/hard-surface response where applicable;
- coherent direct/indirect lighting, shadows, reflections, exposure and atmospheric depth;
- high-frequency detail that survives gameplay motion without texture swimming, shimmer, ghosting, unstable reflections or temporal breakup;
- high-resolution source assets with runtime-scalable LOD/mip behavior rather than screenshot-only detail;
- gameplay and cinematic views must share the same underlying world/assets; cinematics may enhance framing but cannot conceal lower runtime asset quality.

NVIDIA-class rendering features may be used as replaceable implementations where supported: ray/path-traced effects, DLSS Super Resolution/Ray Reconstruction/Frame Generation, Reflex latency instrumentation, or equivalent technologies. They are optimizations, not correctness authority. Generated frames do not count as simulation ticks and cannot alone satisfy native runtime performance evidence.

## 05 — OPEN-WORLD CITY RUNTIME ARCHITECTURE

The game direction includes a realistic, real-life-plausible open-world city. Exact real-world city identity, dimensions, district count, and geographic reproduction remain `UNKNOWN` until separately approved.

The city must be runtime world content rather than background scenery.

Required architecture:
- spatially coherent road/street/building/block structure;
- district/zone partitioning suitable for incremental loading and unloading;
- world-streaming/partition equivalent chosen by the eventual runtime;
- collision, navigation data, spawn/runtime entity placement, lighting and gameplay state remain valid across streaming boundaries;
- near-field gameplay geometry and interiors selected for play are real, traversable geometry;
- distant city geometry may use LOD/HLOD/impostor techniques without breaking silhouette, scale or continuity;
- world-origin/large-coordinate precision must remain stable for the chosen scale;
- streaming failure must not expose voids, unloaded collision, duplicate entities, stale mission state or visible asset replacement errors;
- city content must support player, rival, infected and arena-pressure interactions rather than functioning as static decoration.

Acceptance requires traversal across multiple streamed world regions with stable collision, navigation, rendering and gameplay state.

## 06 — RUNTIME EVIDENCE + FEATURE ACCEPTANCE

Feature acceptance is evidence-based.

Required evidence for a runtime feature, as applicable:
- exact repository commit/tree or source snapshot identity;
- exact editable project/source paths;
- build/editor-runtime launch evidence;
- interactive input or deterministic simulation evidence;
- runtime state-transition evidence;
- decoded rendered-frame/video evidence only as supporting proof of the actual runtime;
- validation of collision/physics/AI/gameplay behavior relevant to that feature;
- observed failures and limitations rather than hidden defects;
- performance/resource measurements when the feature materially affects runtime cost.

A screenshot, offline render, successful export, HTTP response, process exit code, generated video, or agent statement is insufficient by itself.

For visual-performance evidence, distinguish native rendered FPS, simulation rate, generated/display frames, frame time, system/input latency, VRAM/RAM residency, streaming stalls and shader/asset compilation stalls. Upscaling or frame generation must not be reported as proof that native simulation/render work meets its own target.

## 07 — PLAYABLE CHARACTER PRODUCTION

A finished playable character is a runtime character asset, not a character render.

Required production layers:
- coherent high-detail body/head/clothing/equipment geometry suitable for the selected runtime;
- production topology/deformation quality appropriate to animated regions;
- physically plausible materials for skin, eyes, hair, fabric, leather, metal, plastics and other present surfaces;
- skeleton/rig compatible with gameplay animation requirements;
- runtime animation integration for locomotion, orientation, aiming and required gameplay actions;
- collision/hit representation appropriate to gameplay;
- LOD/geometry and texture scaling suitable for open-world runtime distance;
- no fused anatomy, broken joints, floating clothing/equipment, impossible proportions, texture projection errors or generative mesh artifacts;
- character remains readable at gameplay distance while retaining close-range quality.

Exact identity, face, clothing set, body proportions, cosmetic catalog and narrative details remain Project-specific and require their own approved source.

Acceptance requires the character to be possessed/controlled in the real runtime and to animate, collide, orient and render correctly during gameplay.

## 08 — COMBAT + GAME-WEAPON RUNTIME

Weapons are gameplay systems and runtime assets, not decorative props.

For each implemented game weapon, the runtime must integrate the mechanics approved for that weapon, potentially including equip/unequip, aim, fire, reload, ammunition/state, recoil/dispersion, projectile or trace resolution, impact response, damage state, animation, VFX, audio and AI reaction.

Required:
- player input causes a runtime combat action;
- weapon state and player animation remain synchronized;
- hits/impacts resolve against runtime collision/gameplay targets;
- damage/reaction flows into actual target state;
- effects originate from the runtime event and do not merely play a pre-authored demonstration;
- weapon assets maintain realistic material/scale/animation quality appropriate to the game;
- exact weapon catalog, balance numbers and ballistic model remain separately defined.

This contract concerns fictional/gameplay implementation only and does not require real-world weapon construction, modification or operational instructions.

Acceptance requires an interactive runtime combat sequence with reproducible input -> weapon action -> collision/hit resolution -> target/world reaction -> state change.

## 09 — RIVAL CONTESTANT AI RUNTIME

Rival contestants are autonomous runtime actors and must participate in the accepted `PLAYER + RIVAL CONTESTANTS + INFECTED + ARENA PRESSURE` simulation.

Required capabilities at the level supported by the current gameplay design:
- runtime navigation/path selection;
- perception/sensing of relevant player, infected, world and arena-pressure information;
- state/goal selection rather than fixed animation playback;
- ability to fight, evade, reposition, pursue, disengage or otherwise respond according to approved behavior;
- reaction to infected pressure and environmental events where applicable;
- interruption/replanning when relevant world state changes;
- animation/combat/navigation state synchronization;
- bounded reproducible test scenarios or seeds where practical;
- no permanent assumption that one scripted behavior pattern is universally correct.

A rival standing in a scene, following a cinematic spline, or looping a canned combat animation is not implemented rival AI.

Acceptance requires a runtime encounter demonstrating at least multiple observable decision/state transitions caused by changing world conditions.

## 10 — INFECTED / ZOMBIE RUNTIME

Infected/zombies are runtime simulation actors, not background decoration.

Required capabilities at the level supported by the current gameplay design:
- runtime locomotion/navigation;
- perception/target selection using relevant stimuli/state;
- attack/threat behavior and interruption/reaction states;
- collision and damage/death/state transitions appropriate to gameplay;
- interaction with player and rival contestants rather than player-only scripting;
- response to world/environment/arena conditions where applicable;
- crowd/group/horde behavior may be used where supported but must remain stable and performant;
- animation, navigation, collision and combat state must remain synchronized;
- variants must remain data-/asset-driven where practical so new content multiplies interactions rather than creating isolated one-off logic;
- close and gameplay-distance visual quality must avoid broken anatomy, sliding, foot penetration, floating contact and visibly repeated generative defects.

An infected model, still render, cinematic swarm, or non-interactive animation does not satisfy infected gameplay implementation.

Acceptance requires a running encounter where infected independently navigate, select/respond to targets, interact with player/rivals/world and produce real gameplay state changes.

## COMMON COMPLETION RULE

For Contracts 01–10, `COMPLETE` requires editable source + actual runtime execution + task-derived validation. Promotional media may prove appearance but never substitutes for interactive implementation. Any unavailable engine-specific implementation detail remains `UNKNOWN` until the runtime/toolchain is explicitly selected or current source makes it factual.
