# BIELLA GAMES — AAA TPP RUNTIME CONTRACTS 24–30

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

These seven contracts fill the runtime-contract range between the accepted 21–23 supporting contracts and Contracts 31–39. They do not select a game engine, platform, final control scheme, final UI layout, inventory size, damage numbers, traversal catalog, weather system, telemetry backend, or release target unless separately approved.

Global rule: every subject below must exist as editable game/project source and execute in the real-time runtime. Static imagery, offline renders, fake HUD overlays, prerecorded demonstrations, clickable presentations and agent statements cannot satisfy implementation completion.

## 24 — RUNTIME UI + HUD + GAMEPLAY READABILITY

Game UI/HUD must represent real runtime state and support gameplay decisions. It cannot be a composited fake interface used to make screenshots look playable.

Required where the game exposes the corresponding information:
- HUD values are bound to authoritative gameplay state rather than hand-authored display values;
- health, ammunition, equipment, objectives, interaction prompts, threat/readability indicators and other implemented surfaces update from real events;
- UI state cannot indicate an action, item, objective or resource that the gameplay system does not actually own;
- screen-space composition remains readable across supported aspect ratios/resolutions once those targets are selected;
- critical UI does not become unreadable against bright/dark/complex realistic environments;
- scaling, safe areas and text/icon clarity are validated in motion, not only on one screenshot;
- input prompts reflect the active input mapping/device where implemented;
- menus/overlays correctly enter/exit their intended gameplay/input state without leaving stale controls or hidden interaction;
- accessibility settings/features, when approved, modify real presentation/input behavior rather than being placeholder toggles;
- cinematic/marketing overlays must not be confused with runtime HUD evidence.

Acceptance requires a runtime sequence showing authoritative game-state changes producing corresponding UI updates and input/UI transitions.

## 25 — INVENTORY + LOOT + EQUIPMENT RUNTIME

Loot, inventory and equipment are gameplay-state systems, not item icons or decorative pickup models.

Required where implemented:
- every gameplay item has stable runtime/content identity and versioned definition/data where practical;
- world pickup, acquire, remove, drop, equip/unequip, consume/use and transfer actions update authoritative state according to the approved item behavior;
- inventory capacity, stacking, slotting, weight or other constraints exist only when explicitly defined and are enforced consistently;
- equipped items synchronize with character visuals, animation and gameplay capabilities where visible/required;
- world representations cannot remain usable after authoritative pickup/removal unless explicitly designed;
- save/checkpoint/mission transitions do not duplicate or silently destroy authoritative items;
- loot generation/distribution is reproducible enough for debugging where procedural/random behavior is used;
- item definitions are data-driven/composable where practical so new content multiplies interactions instead of requiring isolated duplicate systems;
- UI representation is derived from real item state;
- exact item catalog, rarity system, currencies and capacity values remain separately approved.

Acceptance requires a playable sequence proving world item -> acquisition -> inventory state -> equip/use/drop or another real item transition, with state remaining consistent across related systems.

## 26 — HEALTH + DAMAGE + STATUS + ACTOR REACTION

Combat consequence must be authoritative runtime state, not only animation/VFX.

Required where applicable:
- damage events identify valid source/cause/target and resolve through the actual gameplay damage model;
- health or equivalent survivability state changes only from valid gameplay/system events;
- armor, shields, resistances, hit zones, critical effects or status systems exist only when approved and must resolve through explicit runtime logic;
- actor reaction animation/VFX/audio reflect the resolved gameplay result rather than determining it by appearance alone;
- death/incapacitation/removal state transitions disable or alter gameplay behavior consistently with the design;
- player, rivals and infected use compatible event/state semantics where systems interact, while retaining their Project-specific rules;
- repeated/stacked effects cannot silently bypass bounds or produce invalid negative/duplicate state;
- collision/hit resolution and damage state remain synchronized under variable frame rate and network-independent local timing assumptions;
- save/checkpoint/restart behavior restores the intended survivability/status state only when approved;
- exact damage values, balance curves, hit zones and status catalog remain separately defined.

Acceptance requires a real combat/runtime sequence proving hit/cause -> damage resolution -> authoritative state change -> actor/system reaction -> resulting gameplay consequence.

## 27 — INTERACTION + TRAVERSAL RUNTIME

World interaction and traversal must be real spatial/gameplay operations, not camera cuts or scripted visual transitions.

Required for implemented actions:
- interactable objects expose explicit runtime availability/state;
- interaction validates distance, orientation, obstruction, ownership/state or other constraints required by the chosen design;
- open/use/activate/pickup/enter/exit/climb/vault/jump/drop or other approved actions update actual world/player state;
- traversal respects geometry, collision and physically coherent entry/exit positions;
- animation, IK, camera and gameplay state remain synchronized during traversal/interaction;
- interrupted/cancelled actions recover to a valid controllable state without teleporting, clipping or stale locks;
- moving/streamed/damaged world objects cannot leave orphaned interaction targets;
- navigation for rivals/infected responds correctly when interactions change traversability where applicable;
- interaction prompts/UI derive from the same runtime availability state;
- exact traversal action catalog remains separately approved.

Acceptance requires interactive runtime proof of at least one world interaction and one spatial traversal/state transition where those systems are implemented.

## 28 — ENVIRONMENTAL RUNTIME STATES + WEATHER / LIGHTING / HAZARDS

Environment state must affect the real runtime when the Project uses weather, time, power, fire, flooding, blackout, damage, biological contamination or similar world conditions.

Required for implemented states:
- environment state has explicit runtime data/identity rather than existing only as a color grade or render preset;
- lighting/material/VFX/audio changes remain motivated by the actual state;
- state transitions preserve structural/environment-family identity and physically coherent cause/effect;
- hazards affect gameplay only through explicit approved rules and cannot damage/slow/block actors merely because the visual suggests danger;
- navigation/collision/interaction updates remain synchronized when environment state changes traversal or access;
- player, rivals and infected may perceive/respond to environmental state when their approved AI/gameplay rules require it;
- streamed regions reconstruct the correct current environment state rather than reverting to defaults;
- weather/atmosphere does not destroy gameplay readability or hide geometry defects;
- reduced distant simulation may simplify effects but must preserve authoritative nearby world state;
- exact day/night cycle, weather catalog, hazard values and global frequency remain separately approved.

Acceptance requires a runtime environment-state transition producing synchronized visual/world/gameplay consequences where the chosen state is gameplay-relevant.

## 29 — DATA-DRIVEN CONTENT + VARIANT MULTIPLICATION

Game content should multiply systemic value rather than become isolated one-off logic.

Required where practical:
- missions, items, weapons, vehicles, actors, infected variants, rival variants, encounters, environment states and other repeatable content use stable IDs and versioned structured definitions;
- content definitions reference reusable runtime systems/capabilities rather than duplicating core logic per asset;
- schema/content validation rejects malformed or unresolved definitions before they become accepted runtime content;
- variants may change approved parameters/assets/behavior composition without silently changing unrelated canon;
- generated content remains traceable to source/prompt/config/artifact identity until accepted;
- procedural/random generation uses bounded constraints and reproducible seeds/inputs where practical for debugging;
- content deletion/renaming/version changes preserve or explicitly migrate references used by saves/missions/builds;
- duplicate-feeling variation and combinatorial explosion are controlled by meaningful gameplay/readability constraints;
- content data never overrides universal Engine authority; it remains Biella Games Project scope;
- exact catalogs/counts remain separately approved.

Acceptance requires at least one runtime system consuming multiple structured content definitions/variants without separate duplicated implementation for each case.

## 30 — RUNTIME QA + TELEMETRY + REPRODUCTION

AAA runtime quality requires failures, performance and gameplay regressions to be reproducible and attributable to exact source/build state.

Required as supported by the implementation:
- every qualification session records exact game source/build/config identity;
- deterministic seeds/scenario fixtures are used where practical for repeatable AI, mission, loot or world tests;
- runtime logs preserve crashes, assertions, fatal errors and relevant subsystem failures;
- performance captures can be tied to exact scene/scenario/hardware/configuration;
- gameplay telemetry used for development records real runtime events rather than inferred screenshot state;
- automated or scripted runtime scenarios may exercise movement, combat, AI, streaming, mission and save boundaries where technically useful;
- regression baselines are versioned and do not silently convert old results into current truth;
- crash recovery/reproduction preserves the smallest useful evidence set without requiring full-session replay when unnecessary;
- telemetry/metrics are evidence inputs, not authority over observed game behavior or owner acceptance;
- any user-facing analytics/privacy collection requires separate approved product/policy scope; development telemetry does not imply shipping telemetry.

NVIDIA Nsight, Reflex instrumentation, Aftermath-style GPU diagnostics, or equivalent vendor/platform tooling may be used as replaceable evidence implementations where supported. No NVIDIA tool or GPU feature is required for game correctness, and vendor measurements do not replace whole-game runtime evidence.

Acceptance requires at least one exact-build runtime qualification record with reproducible scenario/evidence sufficient to diagnose a failure or regression without relying on an agent statement alone.

## COMMON COMPLETION RULE

For Contracts 24–30, `COMPLETE` requires editable source + actual game/runtime integration + task-derived validation. Images, renders, prerecorded video, website demonstrations, configuration files, process exit codes and agent claims may support evidence but cannot substitute for runtime proof.
