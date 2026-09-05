# BIELLA GAMES — AAA TPP RUNTIME CONTRACTS 31–39

Status: `OWNER_DIRECTED_ACCEPTED_REQUIREMENT`
Authority: Mahdi Taghdisi, explicit current project direction, 2026-09-01
Project: Biella Games
Scope: playable AAA realistic third-person shooter/survival implementation
Repository: `patrickminitz-web/biella-engine`  
Project path: `projects/biella-games`
Depends on:
- `docs/runtime-contracts/AAA_TPP_RUNTIME_CONTRACTS_01_10.md`
- `docs/runtime-contracts/AAA_TPP_RUNTIME_CONTRACTS_11_20.md`
- `docs/runtime-contracts/AAA_TPP_RUNTIME_CONTRACTS_21_23.md`
- `docs/runtime-contracts/AAA_TPP_RUNTIME_CONTRACTS_24_30.md`
Continuation note: Contract 40 already exists in `docs/runtime-contracts/AAA_TPP_RUNTIME_CONTRACTS_40_49.md`; this file defines only Contracts 31–39 and does not duplicate Contract 40.

These contracts extend the accepted real-time third-person AAA realistic open-world direction. They do not select a game engine, platform, exact navigation technology, population counts, encounter director implementation, arena-pressure mechanic, city dimensions, cinematic system, haptics hardware, accessibility catalog, asset toolchain, or final quality settings unless separately approved.

Global rule: every runtime subject below must exist in editable project/game source and execute through the real game runtime. Static media, prerendered sequences, fake HUDs, offline demonstrations, website interactions and agent statements cannot satisfy implementation completion.

## 31 — NAVIGATION + PATHFINDING + TRAVERSABLE-WORLD RUNTIME

Navigation must represent the actual traversable runtime world rather than a disconnected AI-only approximation that ignores collision, streaming or current world state.

Required where AI navigation is used:
- navigation data is derived from or explicitly synchronized with authoritative world geometry and collision;
- rivals and infected can select valid paths through the currently loaded/traversable world rather than following cinematic splines as gameplay behavior;
- blocked, destroyed, opened, closed or otherwise state-changed routes update or invalidate navigation according to the selected runtime architecture;
- streamed regions cannot leave actors targeting unloaded or invalid navigation data without a bounded recovery/replanning path;
- path queries respect actor dimensions, movement capabilities and approved traversal constraints;
- moving obstacles, doors, vehicles, crowds, hazards and dynamic world changes are handled according to their real gameplay significance;
- path failure is observable and cannot silently teleport actors into valid positions merely to make a demonstration succeed;
- local avoidance may reduce collisions between actors without overriding authoritative path goals or forcing impossible geometry penetration;
- distant/reduced AI may use cheaper navigation representations when the actor is not gameplay-critical, provided state remains reconstructable and nearby gameplay truth is preserved;
- navigation debugging can expose current path, failed query or blocked-route evidence when needed for runtime qualification.

Acceptance requires a running scenario in which at least one rival or infected actor selects, follows, invalidates/replans and completes a path through real world geometry under a changing obstruction or route condition.

## 32 — ENCOUNTER + SPAWN + POPULATION ORCHESTRATION

Actors and encounters must enter the world through explicit runtime rules. Spawning cannot be arbitrary visual placement that ignores world validity, simulation state or player readability.

Required for implemented encounter/population systems:
- spawn requests identify actor/content type, world region and valid runtime conditions;
- spawn positions validate collision, navigation/traversability and any approved visibility/readability constraints;
- rivals, infected, vehicles and other population entities cannot duplicate authoritative identity through unload/reload or retry paths;
- despawn/suspension rules distinguish temporary resource optimization from permanent gameplay removal;
- encounter state reacts to actual player/world/mission/arena-pressure conditions where relevant;
- population density may scale with resource pressure, but nearby authoritative encounters cannot disappear solely to conceal performance problems;
- spawning cannot occur inside invalid geometry, unreachable voids, occupied collision or otherwise impossible world positions unless explicitly designed;
- encounter composition should be data-driven/composable where practical so new content reuses stable orchestration mechanisms;
- random/procedural encounter selection uses bounded rules and reproducible seeds/inputs where practical for debugging;
- the system records enough state to explain why an encounter or actor appeared, failed to appear, suspended or ended.

Exact population counts, encounter frequencies, safe-distance rules and spawn budgets remain separately approved.

Acceptance requires a runtime encounter proving valid spawn -> active simulation -> condition-driven transition -> despawn/suspension/encounter completion without duplicate actors or invalid placement.

## 33 — ARENA PRESSURE RUNTIME

`ARENA PRESSURE` is an authoritative gameplay/world system that changes player decisions inside the survival simulation. It cannot be represented only by UI warnings, cinematic effects or decorative environmental change.

Required when an arena-pressure mechanic is implemented:
- pressure state has explicit runtime identity/state and reproducible transition conditions;
- pressure affects gameplay only through approved mechanics and cannot invent damage, barriers, hazards, timers or shrinking geometry not defined by Project source;
- player, rivals and infected can perceive or react to pressure when their approved behavior requires it;
- mission/objective, navigation, world-state, VFX, audio and UI responses derive from the same authoritative pressure state rather than independent fake representations;
- streamed regions reconstruct the current pressure state correctly;
- pressure transitions cannot leave actors permanently trapped in invalid navigation or unloaded collision without explicit failure/recovery behavior;
- any spatial boundary, hazard field, timing phase or environmental transformation must remain physically/readably coherent in the real world;
- reduced distant simulation may simplify presentation but cannot change the authoritative pressure state;
- pressure events remain Project-specific and do not become universal Biella Engine policy;
- exact arena-pressure mechanic, timing, geometry, damage model and escalation pattern remain `UNKNOWN` until separately approved.

Acceptance requires a running scenario where an approved arena-pressure state transition causes real world/gameplay consequences and at least two relevant systems respond to that same state.

## 34 — MULTI-ACTOR COMBAT + HORDE / CROWD SCALABILITY

The accepted `PLAYER + RIVAL CONTESTANTS + INFECTED + ARENA PRESSURE` interaction must remain functional when multiple autonomous actors share the same combat space.

Required as supported by the current milestone:
- multiple rivals/infected can navigate, perceive, choose targets and react without collapsing into a single scripted sequence;
- target selection and threat response allow actor-versus-actor interaction where approved, not only every AI actor targeting the player;
- local avoidance, collision and attack positioning reduce persistent actor interpenetration and impossible stacking;
- combat state, animation, navigation and damage remain synchronized under multi-actor load;
- horde/crowd behavior may use group-level, reduced-frequency or approximate simulation at distance, but nearby actors preserve authoritative individual gameplay state where required;
- actor simulation frequency/LOD may scale with distance and importance without causing obvious teleporting, frozen combatants or invalid damage;
- spawn/population systems respect measured CPU/GPU/memory constraints rather than silently exceeding stable runtime capacity;
- encounter density may scale through explicit quality/content rules without changing the semantic game outcome solely to hide performance defects;
- repeated actor variants preserve enough visual/behavioral variation to remain readable without requiring unique one-off logic per actor;
- stress scenarios expose counts, frame time and failure state sufficient to diagnose scalability limits.

Exact horde sizes, rival counts and simultaneous-combat targets remain performance- and design-dependent rather than invented here.

Acceptance requires representative live combat with multiple autonomous actors producing observable cross-system reactions while remaining navigable, performant enough for the tested milestone and free of persistent state desynchronization.

## 35 — INTERIOR / EXTERIOR + VERTICAL WORLD CONTINUITY

The realistic open-world city must preserve coherent gameplay when moving between streets, buildings, rooftops, interiors, underground/covered spaces or other approved vertical layers. These spaces cannot exist only as separate render sets disconnected from the playable world.

Required where such spaces are implemented:
- entrances/exits connect to real spatially coherent world geometry;
- player/camera collision, navigation, lighting, audio and streaming transition without teleportation or hidden scene replacement unless an explicit designed transition requires it;
- indoor/outdoor materials, exposure, reflections, shadowing, ambience and occlusion transition coherently;
- rivals/infected can enter, leave or reason about connected spaces when their approved behavior requires it;
- vertical routes such as stairs, ramps, ladders, elevators, vaults or other traversal mechanisms are real gameplay paths only when implemented and approved;
- world partition/streaming does not unload required adjacent geometry, collision or navigation during transition;
- interior shells cannot visibly contradict exterior dimensions in ways that break realistic spatial plausibility unless a separate Project rule explicitly permits non-Euclidean design;
- doors, access states and mission blockers remain synchronized across connected spaces;
- rooftop/elevated edges, drops and barriers use valid collision and readable scale;
- exact accessible-building percentage, underground scope and vertical-traversal catalog remain separately approved.

Acceptance requires uninterrupted runtime traversal through at least one implemented exterior -> interior or lower -> upper world transition with valid camera, collision, navigation, lighting and gameplay state.

## 36 — RUNTIME CINEMATIC / SEQUENCE + GAMEPLAY HANDOFF

Cinematics and authored sequences may present the game, but they must remain connected to the real runtime world and cannot substitute for gameplay implementation.

Required when cinematics/sequences are implemented:
- sequence source is editable and traceable to the actual game project/build;
- sequence actors, world state and assets derive from the real game source rather than a disconnected fake-game scene when the sequence is presented as in-game;
- entering a sequence explicitly transfers or constrains player control according to the approved design;
- exiting restores a valid controllable player/camera/gameplay state without stale input locks, duplicate actors, missing equipment or mission-state divergence;
- mission/world changes caused by a cinematic occur through explicit runtime events/state transitions rather than visual implication alone;
- camera cuts, animation, audio and VFX may be authored for presentation but cannot claim combat, AI, physics or interaction occurred unless those systems actually executed;
- skipped/interrupted sequences produce the same required authoritative state transitions as watched sequences where skipping is supported;
- streamed world/asset requirements for the sequence are prepared without corrupting surrounding gameplay state;
- offline/high-quality promotional renders remain separate derivative artifacts and cannot be called runtime cinematic evidence unless produced from the runtime path claimed;
- exact cinematic count, dialogue, narrative beats and camera language remain separately approved.

Acceptance requires an in-game sequence transition proving gameplay -> cinematic/sequence state -> authoritative state changes where applicable -> clean return to live gameplay.

## 37 — GAME FEEL + FEEDBACK + HAPTICS INTEGRATION

Responsive game feel is produced by synchronized runtime feedback around real gameplay events, not by post-produced editing added to captured footage.

Required where supported by the selected platform/runtime:
- camera impulses/shake, hit feedback, recoil presentation, controller vibration/haptics, animation response, VFX, audio and UI feedback originate from real gameplay events;
- feedback intensity/duration is tunable and cannot alter authoritative hit/damage/physics results merely through presentation;
- layered feedback remains readable and bounded during dense combat rather than creating continuous uncontrolled camera, audio or haptic noise;
- camera feedback cannot make third-person aiming persistently unreadable or cause unacceptable clipping/obstruction behavior;
- hit/impact feedback distinguishes confirmed gameplay results from missed/blocked/invalid actions where relevant;
- haptic/controller features use replaceable platform implementations and degrade explicitly when unsupported;
- accessibility or comfort settings can reduce approved camera/haptic effects without changing underlying gameplay semantics unless separately designed;
- frame-rate variation cannot materially desynchronize feedback from the runtime event;
- feedback data may be content-/weapon-/actor-specific while using reusable underlying mechanisms;
- marketing post-processing cannot be used as evidence that runtime feedback exists.

Exact recoil curves, camera-shake style, rumble patterns and comfort defaults remain separately approved.

Acceptance requires live input/gameplay producing synchronized visual/audio/animation and, where hardware is available, haptic feedback from the same authoritative event.

## 38 — INPUT MAPPING + SETTINGS + ACCESSIBILITY RUNTIME

Player-facing settings must change actual runtime behavior and remain durable according to the approved game configuration model. Placeholder toggles or UI-only options do not count as implementation.

Required where supported:
- input actions/axes are mapped through an explicit runtime configuration rather than scattered hard-coded keys/buttons;
- keyboard/mouse and controller support are added only for approved target platforms but can coexist through device-aware prompts and state;
- remapping, sensitivity, inversion, dead-zone and other control settings affect live input where implemented;
- graphics, audio and gameplay-presentation settings apply to the relevant runtime systems and report unsupported combinations explicitly;
- accessibility features, when approved, alter real presentation/input/readability behavior rather than existing only as menu labels;
- settings validation rejects invalid values/ranges and falls back explicitly rather than silently corrupting configuration;
- settings persistence is separated from mission/world/save data ownership;
- changing settings at runtime cannot leave stale render/input/audio state that requires an undocumented restart unless the option explicitly declares restart requirements;
- quality settings preserve gameplay correctness and cannot disable required collision, AI, mission state or authoritative simulation solely for performance;
- exact target devices, accessibility feature catalog and default settings remain separately approved.

Acceptance requires a runtime settings sequence proving at least one input setting and one presentation/system setting change the actual game behavior and persist/reconstruct according to their approved scope.

## 39 — PRODUCTION ASSET INTEGRATION + RUNTIME VALIDATION

A production asset is complete only when its editable source, runtime derivative and integration behavior are traceable and validated for the game. A generated render or isolated DCC file is insufficient when the asset is claimed as game-ready.

Required for integrated production assets as applicable:
- source/editable asset identity is preserved for meshes, rigs, animations, textures/materials, audio, VFX and other content where the production pipeline requires it;
- imported runtime derivatives are attributable to source/revision and can be rebuilt or reimported through the selected toolchain;
- scale, orientation, pivots, transforms, skeleton/rig binding, materials, texture channels, collision and LOD data are validated according to asset type;
- character, weapon, vehicle and environment assets reject fused geometry, invalid normals/tangents, broken skinning, missing materials, impossible collision or other defects that materially affect runtime use;
- texture/material compression and geometry reduction preserve required realistic quality at gameplay distance;
- naming/path organization is Project-scoped and stable enough that mission/content/save/build references do not silently break on ordinary revisions;
- generated/procedural assets remain `GENERATED_DRAFT` or equivalent candidate state until Project acceptance and must not be mistaken for approved canon from filename or publication alone;
- runtime integration verifies actual lighting, animation, collision, streaming and gameplay behavior relevant to the asset rather than only successful import;
- source-control/build packaging includes the exact required runtime dependencies/derivatives or reproducible generation route;
- rejected/obsolete candidates do not remain active alongside accepted assets in a way that creates ambiguous runtime authority.

Acceptance requires at least one representative integrated asset to be traced from editable source -> runtime import/derivative -> live game use -> asset-type validation, with exact source/build identity recorded.

## 31–40 RANGE COMPLETION

Contracts 31–39 are defined by this file. Contract 40 remains defined by `docs/runtime-contracts/AAA_TPP_RUNTIME_CONTRACTS_40_49.md` and is intentionally not duplicated here.

Therefore the 31–40 contract range is source-contract complete only when both files are present in the same accepted repository revision lineage. Runtime implementation completion for any individual contract still requires editable game source + actual runtime integration + task-derived validation appropriate to that contract.
