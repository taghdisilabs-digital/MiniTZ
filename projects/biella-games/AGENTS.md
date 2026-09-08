# Biella Games Project Execution Authority

Status: `OWNER_DIRECTED_ACCEPTED_REQUIREMENT`
Authority: Mahdi Taghdisi
Scope: `projects/biella-games/` inside canonical `patrickminitz-web/biella-engine`; a deeper path may contain an explicitly accepted narrower `AGENTS.md`

## 1. Authority and truth

Mahdi Taghdisi is the final authority for Biella Games product direction, priorities, architecture choices, infrastructure use, acceptance, and work policy.

Resolve implementation questions using this order:

1. Mahdi's latest explicit instruction.
2. Current accepted Biella Games Project source and authority records.
3. Current repository implementation and observed runtime/build/package evidence for implementation facts.
4. Current canonical Biella Games Drive records not yet mirrored into the repository.
5. Accepted project artifacts and runtime-contract evidence.
6. Generated drafts and experiments.
7. Historical/reference material.
8. Inference.

Do not synthesize incompatible claims. If an implementation choice is required but unresolved, record it as `UNKNOWN` rather than guessing.

Current source/runtime evidence outranks stale planning text about what has already been implemented. Product direction remains controlled by the latest accepted owner/project authority rather than by incidental implementation drift.

## 2. Product implementation direction

Biella Games is to be implemented as a real-time interactive 3D game.

The accepted playable direction is:

- third-person player presentation for normal shooter gameplay;
- realistic, physically coherent, highly detailed AAA-quality real-time 3D presentation;
- a genuinely playable world rather than a rendered backdrop;
- runtime gameplay, simulation, collision/physics, AI/world reactions, state changes, rendering, audio and VFX where the corresponding feature is implemented;
- measured runtime quality rather than screenshot fidelity alone.

The detailed runtime requirements are defined by the canonical files under `docs/runtime-contracts/` and their index once present.

Do not treat the contract numbers as implementation order. Use `docs/IMPLEMENTATION_SEQUENCE.md` for execution order.

## 3. Playable-runtime acceptance rule

No static image, generated picture, screenshot sequence, prerendered video, cinematic-only scene, HTML hotspot experience, clickable background, fake gameplay HUD, non-interactive 3D viewer, benchmark-only scene, offline render, or prerecorded animation sequence constitutes gameplay implementation.

A gameplay feature is real only when the editable game/project source contains the implementation and the behavior executes through the actual runtime or valid editor play/runtime mode.

Where applicable, gameplay proof follows this shape:

`INPUT -> PLAYER/CAMERA RESPONSE -> SIMULATION -> COLLISION/PHYSICS -> AI/WORLD REACTION -> GAMEPLAY STATE CHANGE -> REAL-TIME RENDERED/AUDIO/VFX RESULT`

Supporting captures, logs, screenshots and videos are evidence of the running implementation; they are never substitutes for it.

Environment completion requires navigable runtime geometry and collision/traversal evidence. Character completion requires the runtime character asset, rig/animation/collision and gameplay integration required by its contract. Weapon completion requires gameplay integration. AI/infected completion requires autonomous runtime behavior. Mission completion requires executable mission state. Vehicle completion requires runtime control/physics where vehicles are implemented.

## 4. Biella Games / Biella Engine separation

This subtree is Biella Games Project scope inside the one canonical Biella repository.

Biella Games owns its game-specific:

- product direction and requirements;
- game source and project files;
- mechanics and gameplay systems;
- characters, infected, rivals, vehicles and missions;
- environments and world content;
- art direction, brand, visual/content canon and assets;
- UI, audio, VFX and narrative/content data;
- project-specific acceptance and shipping outputs.

Reusable Biella Engine mechanisms live outside `projects/biella-games/` in the same canonical repository. Repository unification does not collapse semantic ownership: game requirements, Unreal source/assets, visual/content canon and Project acceptance remain under this subtree; reusable controller, routing, memory, provider, browser, storage, validation and learning mechanisms remain Engine scope.

Do not create a second universal scheduler, memory system, routing plane, model layer, browser layer, object store, validation framework or learning system inside Biella Games. Do not promote game-specific implementation into Engine capability merely because both now share one Git repository.

Do not import MiniTZ or BoosTZ project-specific assumptions, prompts, architecture, branding, lore, workflows, agent hierarchies or source ancestry into active Biella Games implementation.

## 5. Technical decisions

`docs/TECHNICAL_DECISIONS.md` is the Project record for implementation choices such as:

- game engine/runtime and exact version;
- implementation language/scripting model;
- platform targets;
- rendering path;
- build/package system;
- asset/runtime formats;
- target hardware tiers;
- resolution/frame-rate/performance targets.

An `UNKNOWN` value is not permission for an agent to select a value automatically. Do not choose a game engine, version, language, platform, renderer, middleware, vendor stack or shipping target merely because a tool is available.

The actual editable game project/source is created only after the required engine/runtime decision is accepted. Do not fabricate a project scaffold that silently makes that decision.

Do not block independent documentation, asset preparation or source-authority work on unrelated `UNKNOWN` decisions.

## 6. Codex / agent execution rules

Before changing implementation:

1. Read this file.
2. Inspect the current canonical repository/Project subtree state once: branch, HEAD, relevant paths and dirty/newer work when a worktree is available.
3. Read only the smallest current source set needed for the task, including relevant runtime contract(s), `docs/TECHNICAL_DECISIONS.md`, and `docs/IMPLEMENTATION_SEQUENCE.md` when the task depends on them.
4. Preserve valid newer work. Do not restart settled work because the chat, Codex session, machine, provider or agent changed.
5. Execute the user's current task directly and make the smallest complete task-scoped change.
6. Do not replace implementation with planning, concept art, mockups, audits or generic recommendations.
7. Do not invent permanent manager/critic/validator/repair agents, approval chains, readiness ceremonies or fixed repair counts.
8. Independent work may proceed concurrently when dependencies, side effects and real resources permit.
9. Diagnose actual failures from observed output before changing architecture, providers or configuration.
10. Stop at the requested boundary unless the user explicitly authorizes the next one.

Do not claim a system, feature, build, render, package, upload, deployment, test or runtime result exists unless it was actually observed.

## 7. Validation and evidence

Validation derives from the feature/output contract.

Typical evidence requirements include:

- software/game source: exact editable source plus relevant deterministic tests/build/runtime evidence;
- gameplay: real input/simulation/state transition evidence;
- world/environment: actual geometry, collision/navigation/traversal and runtime rendering evidence;
- 3D assets: editable source plus structural and runtime integration validation;
- rendering/performance: decoded real-time frames plus measured frame time/resource evidence;
- package/release: exact package identity plus clean launch and real play evidence;
- persistence: state creation, process/session teardown, reconstruction and integrity evidence;
- publication: remote identity plus remote readback.

Exit code, HTTP success, screenshot, config file, mock, generated media, benchmark overlay or agent report alone is not sufficient unless the exact task contract explicitly says it is.

## 8. Git durability

For accepted Project source changes:

`inspect current main -> edit -> task-derived validation -> commit -> push/update main -> remote readback`

Remote readback must verify, as applicable:

- exact result commit;
- exact result tree;
- required paths and file contents on the remote branch.

A local commit with matching task proof can close implementation; it is not a claim of remote publication. Required GitHub/Drive replication is independently retried by the controller. Actual release/delivery contracts still require their own external evidence.

Do not rewrite or discard newer valid concurrent work. If `main` changes during the task, re-read the smallest affected boundary and preserve compatible newer work.

## 9. Google Drive durability

Project authority/continuity records that are maintained in canonical Google Drive must be updated in the matching Biella Games project path when the task changes them.

For Drive publication:

`create/update -> place in canonical project folder -> fetch/list/read back -> verify identity and required content`

When revising an existing canonical Drive record, preserve its Drive file identity when practical instead of creating a second active copy.

Do not claim Drive publication from an upload/write attempt alone. Record the actual Drive file ID/path and readback result when publication is part of the task.

Do not perform broad destructive synchronization.

Generated visual/media artifacts remain `GENERATED_DRAFT` or equivalent candidate status until Mahdi explicitly accepts them. Publication does not equal acceptance.

## 10. Current Project boundary

Until `docs/TECHNICAL_DECISIONS.md` records an accepted game engine/runtime decision or Mahdi explicitly supplies one, do not create an engine-specific game project or claim gameplay implementation has begun.

Once that decision is accepted, create or continue the real editable game project/source in this Project subtree and follow `docs/IMPLEMENTATION_SEQUENCE.md` rather than implementing runtime contracts in numeric order.

## Hardened execution law — 2026-09-05

- `SINGLE_CODEX_AUTHORITY`: one Codex task/session owns authority, synthesis, edits, validation, completion, and task advancement. Parallel Codex/subagent fan-out is disabled for production.
- `RESOURCE_PARALLELISM`: independent bounded work may execute concurrently through verified Resources when dependencies, side effects, and capacity permit. Local Qwen/Ollama, Cloudflare Workers/AI, external APIs, GPU tools, DCCs, build systems, and other Resources are implementations, never second authorities. Cloudflare is used only through an actually configured callable capability adapter.
- `LOCAL_FIRST_EFFICIENCY`: before spending general Codex reasoning on bounded preprocessing, code review, classification, summarization, log triage, reasoning assistance, or Unreal assistance, prefer the configured local Qwen Resource when it can perform the work without reducing correctness. Reuse compact task memory, prompt caching, bounded tool output, and deterministic/local commands.
- `FINAL_DELIVERABLE_PUBLICATION`: preserve exact canonical local output and task-derived proof. The controller commits task-owned output and continuity locally, records the exact Git revision in its durable publication cursor, and retries GitHub/Drive independently. A transport failure does not reopen validated implementation or stop unrelated execution. `COMPLETE` records satisfied task acceptance; `PUBLISHED/VERIFIED` requires actual remote identity and readback. When deployment, external delivery, or a remote operation is itself the task deliverable, its real evidence remains required. Never invent a destination or claim remote durability from a local commit.
- `DURABLE_FAILURE_LEDGER`: every observed production/model/provider/tool/runtime/validation/publication failure or retry is recorded in AI-readable JSONL at `/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl` with task/time/type/status and bounded diagnostics. Failure records aid diagnosis and never override current source/task authority.
- `LOSSLESS_MEMORY_COMPACTION`: raw authority, evidence, artifacts, task records, and failure records are never rewritten or deleted by compression. The compactor creates rebuildable derivative JSON/JSON.GZ indexes with exact source digests, content-addressed unique records, equivalence groups that retain every exact variant and provenance, and a bounded current-task projection. Compaction failure is an optimization failure only and must never stall, reset, fail, kill, or advance a task.
- `VERIFIED_ACTION_MEMORY`: instructions, tasks, verified actions, failures, capabilities, task IDs, and task classes are categorized separately. Only evidence from `COMPLETE`/`COMPLETE_ALREADY` work is promoted as a verified action. Cross-task comparison may identify equivalent/reusable patterns, but conflicting or unique content, source refs, task-specific facts, and capabilities are preserved rather than collapsed.
- Routine dependencies, reversible environment repairs, and already-authorized implementation choices are execution work, not approval gates. Genuine destructive/irreversible external actions without authority, unavailable required facts/authority, safety constraints, and required task sequencing remain real boundaries.

## Next-100 production execution

`docs/task-program/D_NEXT_100_TASKS.json` contains the next 100 existing task identities, normalized source sections/digests, dependencies, output contracts, and execution roots. It is not another queue. The runner injects only the active entry; `PRODUCTION.md` owns order/status and `D_TASK_LEDGER.json` is its derived projection. Reuse matching proof; no new gate, permanent agent, timer, or whole-program prompt load. Read `07_BIELLA_PRODUCTION_SYSTEM.md` for the implemented local-persistence/remote-publication split and inline source repair.

## Owner production priority — GAME_FIRST
Game delivery is priority NUMBER 1. Follow the physical order in docs/PRODUCTION.md and the current active task. Reuse accepted implementations and evidence; perform only missing game outputs and task-derived validation. No unrelated website, Engine business, pilot or investor completion prerequisite. Shared Engine dependencies stay project-neutral; prioritize only what the game actually consumes. Do not weaken gameplay, AAA-quality, packaging or genuine external-player evidence requirements.
