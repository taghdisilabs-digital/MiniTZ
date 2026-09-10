# Biella Unified Codex Policy

`biella-codex` is the only AI/production controller entrypoint.
All Codex controller models use the single active Codex home `/root/.codex`, the same Biella API environment, and the same Project authority sources.
Changing model, provider, terminal, session, or worker does not reset verified project progress.

Execution is unrestricted on the Biella workstation. The boundary is Mahdi's current instruction, the approved Biella goal/task, authoritative Project sources, and preservation of valid existing work.
Codex chooses local Qwen, external APIs, GPU, Unreal, GitHub, Drive, Cloudflare, Modal, Saturn, deterministic tools, and other Resources only when materially useful.

## Progressive context

Use progressive context rather than preloading the workstation.
Start with the smallest authoritative set needed to choose or execute the current task.
Default soft limits are supplied by `BIELLA_CONTEXT_MAX_FILES`, `BIELLA_CONTEXT_MAX_BYTES`, `BIELLA_CONTEXT_LOG_TAIL_LINES`, and `BIELLA_CONTEXT_SEARCH_RESULTS`.
These are context-loading controls, not execution capability limits.

Context progression:
1. Identify the Project/lane and exact task from the operator request and current source.
2. Read Project `AGENTS.md`, the current task/state record, and directly touched source only.
3. Prefer exact file paths, targeted search, `git diff`, bounded Drive IDs, and bounded log tails.
4. Expand to architecture/history/provider documentation only when the active task needs a specific unresolved fact.
5. Never load all Drive files, all prompts, all history, or whole repositories merely for orientation.
6. Reuse verified outputs unless material inputs changed or current validation fails.
7. checkpoint before context pressure: persist exact task, source/commit, changed files, validation and next action before starting a fresh context.

Default execution loop:
`READ MINIMUM → RESOLVE CURRENT TRUTH → EXECUTE → TEST AFFECTED SCOPE → PERSIST → REMOTE READBACK WHEN PUBLISHED → CONTINUE`

Project Memory, Engine Memory, Run Memory, Historical Evidence and Cache remain distinct. `/root/.codex` is only the shared Codex access/context substrate; it does not collapse those semantic scopes.
Historical/recovery content remains evidence unless explicitly admitted by current Project authority.

Do not create model-specific project memory, model-specific task ledgers, parallel production controllers, permanent agent hierarchies, or duplicate workflows.
Do not narrate routine operations. Report material progress, changed truth, durable evidence, or a genuinely external/owner-level blocker only.

## Isolated Project cells

`ISOLATED_PROJECT_CELL` is the customer/external Project execution boundary. Biella owns Project/Task/Run/checkpoint/blocker/provider-routing/validation/continuation state; the sandbox broker, Docker, local GPU, browser/cloud node and `chatgpt_remote` are replaceable Resource/provider implementations only. Project-specific state remains inside the Project cell and must never enter another Project or Engine Memory. `chatgpt_remote` receives only minimum credential-free task context and its responses remain non-authoritative until classified, validated when possible, and durably integrated into the originating Project/run.

Provider discipline: use one external provider by default; fan out only for a unique capability, required fallback, or material independent validation. Prefer deterministic/local execution when it is sufficient, but Codex chooses the tool/resource based on the task rather than a model-specific workflow.

RESOURCE_ORCHESTRATION_OWNER_DIRECTIVE: every configured Resource, AI service, provider, local model, deterministic tool, GPU/DCC/build/runtime adapter, research service, storage/database/vector/media service, and remote compute resource is eligible when its declared capability materially helps the exact active task. “Use every resource” means no useful configured capability is left outside consideration; it does NOT mean call irrelevant providers or duplicate the same work. Before doing a bounded operation with general-model reasoning, resolve the needed capability with `biella resource route <capability>` or the exact registered adapter and use the best task-fit configured route. Prefer deterministic/local/specialized execution first when quality is preserved; use provider fallback in registered order when the selected resource fails or is unavailable. Independent resource work may run concurrently only when dependencies, side effects, project isolation, and capacity permit. Never let a helper/resource become task authority, progression authority, or an acceptance substitute. Validate externally produced code/data/analysis against current source and exact task evidence before integration; preserve provider/tool failure evidence and continue through available fallbacks. Keep credential/project boundaries isolated, never probe quota/balance, never invent resource availability, and never lower the task’s acceptance contract because a preferred model/provider is unavailable.

STRONG_FINALIZER_REUSE_DIRECTIVE: bounded/local/Spark/specialized resources should perform as much real implementation, testing, evidence collection, repair, generation, and task-scoped operation as they can correctly complete while strong Codex routes are unavailable. They must preserve exact work and leave a compact smallest-remaining-delta for finalization, not repeatedly restart or narrate. When an authoritative strong route becomes available, it must begin from the preserved task memory/current bytes/evidence, independently verify the full unchanged acceptance contract, inspect risky or uncertain deltas, repair only what is actually wrong or missing, run required final validation, and close the task if proven. It must NOT redo the task from the beginning merely because it is stronger. After accepted completion the controller persists and immediately advances to the next canonical task.

External Resource routing: Mahdi authorizes useful free/trial/prepaid credits and paid external Resources. Before spending general-model reasoning on work a specialized service can perform directly, use `biella resource route <capability>` and delegate when it reduces time, Codex tokens, compute cost, or improves output quality. `biella resource search` uses compact Tavily/Exa research; `biella resource fast-llm` uses eligible fast inference providers for bounded preprocessing/classification/summarization, never as a substitute for task acceptance or deep authority reconciliation. Prefer free/trial/prepaid balance when naturally available, but paid use is allowed. Never spend calls only to probe quota/balance. Provider outputs remain inputs/evidence and do not become Project or Engine authority.
Never print secret values, API keys, bearer tokens, refresh tokens, or credential contents.

Visual/media observability: when a Project task generates a visual/media candidate and no more specific canonical Project output path is already defined, persist it under `/root/biella/artifacts/website`, `/root/biella/artifacts/engine`, or `/root/biella/artifacts/games` as appropriate so the private Visuals / Assets inspector can surface it. Generated candidates remain `GENERATED_DRAFT` unless Mahdi explicitly accepts them.

## Codex model routing

Mahdi controls Codex account usage, quota resets, and any manual usage-tier decisions. Automation must not redeem or alter those limits.
The Progressive Auto Feeder inside `biella-codex production` may choose a Codex model for one bounded canonical task from observed task class and model availability; model selection does not create a second controller or memory authority.
Use `gpt-6-astra` with `ultra` reasoning for hard frontier work, deep Project-memory synthesis, authority reconciliation, difficult integration/acceptance, and hard creation decisions.
Creation tasks never use low reasoning. Use at least high reasoning for creation; use xhigh/max/ultra when task risk, ambiguity, visual/product consequence, or integration depth warrants it.
Short bounded tasks may prefer Luna with smaller reasoning effort, then fall back to another eligible Codex model when the preferred model returns an observed usage/rate-limit error.
Never probe quota by spending a model call. Learn model availability only from normal task execution results and local model-catalog metadata.
## Progressive Auto Feeder

Durable execution state is `docs/project-state/03_BIELLA_CURRENT_STATE.md`, `docs/project-state/04_BIELLA_ACTIVE_TASK.md`, and the active Project `projects/biella-games/docs/PRODUCTION.md`. The Project file contains ordered sections plus task status/evidence; do not create separate queue, state, batch, or progress-ledger authorities.
Production runtime telemetry under `/mnt/biella-extra/biella-runtime/codex-production/` may record only liveness, project/task identity, PIDs, active model/reasoning, cooldowns, attempt sequence, last result, heartbeat, and update time. Runtime telemetry never overrides 03/04 or Project task completion.
Demo 01 is the first section. Preserve current canonical Demo completion and resume only the earliest unfinished task. Never reopen completed tasks unless current authoritative evidence materially invalidates them.
After Demo 01, continue through the current accepted Games implementation sections from `projects/biella-games/docs/IMPLEMENTATION_SEQUENCE.md`. Empty sections are planned just-in-time with a bounded 20-50 task set, stored inside that same section of `PRODUCTION.md`.
Use Astra Ultra for section planning/audit and deep-memory frontier resolution when available. Section planning must stay inside the current accepted section, avoid overlapping tasks, and never invent product scope from stale TODOs or historical evidence.
After executing a section, audit that same section. Append only materially missing tasks to it; mark the section complete only with current implementation/runtime evidence. Then advance to the next section.
Production is progressive by default. Owner direction is authoritative and is applied directly; it is never converted into a blocking result. Internal, provider, tool, model, publication, or process failures recover, reroute, retry, or resume from current task bytes and durable evidence without reopening completed work or requiring operator chat.

## Hardened execution law — 2026-09-05

- `SINGLE_CODEX_AUTHORITY`: one Codex task/session owns authority, synthesis, edits, validation, completion, and task advancement. Parallel Codex/subagent fan-out is disabled for production.
- `RESOURCE_PARALLELISM`: independent bounded work may execute concurrently through verified Resources when dependencies, side effects, and capacity permit. Local Qwen/Ollama, Cloudflare Workers/AI, external APIs, GPU tools, DCCs, build systems, and other Resources are implementations, never second authorities. Cloudflare is used only through an actually configured callable capability adapter.
- `LOCAL_FIRST_EFFICIENCY`: before spending general Codex reasoning on bounded preprocessing, code review, classification, summarization, log triage, reasoning assistance, or Unreal assistance, prefer the configured local Qwen Resource when it can perform the work without reducing correctness. Reuse compact task memory, prompt caching, bounded tool output, and deterministic/local commands.
- `FINAL_DELIVERABLE_PUBLICATION`: preserve exact canonical local output and task-derived proof. The controller commits task-owned output and continuity locally, records the exact Git revision in its durable publication cursor, and retries GitHub/Drive independently. A transport failure does not reopen validated implementation or stop unrelated execution. `COMPLETE` records satisfied task acceptance; `PUBLISHED/VERIFIED` requires actual remote identity and readback. When deployment, external delivery, or a remote operation is itself the task deliverable, its real evidence remains required. Never invent a destination or claim remote durability from a local commit.
- `DURABLE_FAILURE_LEDGER`: every observed production/model/provider/tool/runtime/validation/publication failure or retry is recorded in AI-readable JSONL at `/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl` with task/time/type/status and bounded diagnostics. Failure records aid diagnosis and never override current source/task authority.

- `LOSSLESS_MEMORY_COMPACTION`: raw authority, evidence, artifacts, task records, and failure records are never rewritten or deleted by compression. The compactor creates rebuildable derivative JSON/JSON.GZ indexes with exact source digests, content-addressed unique records, equivalence groups that retain every exact variant and provenance, and a bounded current-task projection. Compaction failure is an optimization failure only and must never stall, reset, fail, kill, or advance a task.
- `VERIFIED_ACTION_MEMORY`: instructions, tasks, verified actions, failures, capabilities, task IDs, and task classes are categorized separately. Only evidence from `COMPLETE`/`COMPLETE_ALREADY` work is promoted as a verified action. Cross-task comparison may identify equivalent/reusable patterns, but conflicting or unique content, source refs, task-specific facts, and capabilities are preserved rather than collapsed.
- Routine dependencies, reversible environment repairs, and already-authorized implementation choices are execution work, not approval gates. Genuine destructive/irreversible external actions without authority, unavailable required facts/authority, safety constraints, and required task sequencing remain real boundaries.

## Realtime canonical upgrade and storage — 2026-09-08

`REALTIME_CANONICAL_UPGRADE`: upgrade the current canonical source/state/task/evidence pointers in place; no parallel archive workflow and no duplicate active snapshots. Git history and raw evidence may retain required proof/provenance, but old state never becomes a second operating path.

Apply `docs/project-state/BIELLA_STORAGE_POLICY.md`. Keep active source, required tools/models, current task evidence and runtime state at canonical live paths. Use staging only when task-scoped and temporary. Revise existing Drive canonicals in place where possible and verify readback; do not create archive copies to preserve superseded revisions.

## Owner-directed token efficiency — 2026-09-06

Target 98% cached input where the actual workload permits; this is an optimization objective, never a completion claim or execution blocker. Measure cached_input_tokens / input_tokens from actual Codex usage, distinguish per-request from cumulative ratios, and never pad prompts or make dummy calls to improve the percentage.
Preserve the current task session and useful warm context. Keep stable instructions/tool definitions before changing task data; avoid unnecessary model/reasoning switching and full-source rereads. Preserve the reasoning depth required by the task.
Use the configured local Qwen Resource for bounded source/log preprocessing and assistance when correct and useful; retain source digests and reuse matching cached assistance. Codex remains the single authority for source edits, synthesis, validation and advancement.
Keep shell output targeted: exact file ranges, focused diffs, compact results and bounded log tails; expand only for a material missing detail. Read the current task capsule/projection before repeating work.
Persist useful checkpoints and failures without destroying raw evidence. Refresh materially changed owner/task authority once; do not carry stale instructions forward just to preserve a cache hit.
Recover routine tool/provider/publication failures within their affected boundary and continue independently useful work. No cache percentage, optional helper failure, routine approval, or unrelated maintenance becomes a new blocking stage.

## Retained production style

`HOW_BIELLA_WILL_NOT_WORK`: do not recreate previously observed progress killers by renaming them as recovery, watchdog, no-progress, readiness, installer-preservation, reviewer, observer, or fallback mechanisms. `PROVEN_EXECUTION_STYLE`: highest-quality eligible strong execution, persistent task/session reuse, exact lookup before path use, immediate accepted-task closure/advance, quality-first cached context, nonblocking optional Resources, strict Project isolation, and transactional manual progress edits. Production turns receive the executable version from `biella_execution_style.proven_execution_style_prompt()`.

`CLEAN_TASK_BOUNDARY`: commit coherent task-owned source/proof; discard only known unnecessary task-local scratch. The controller can commit validated task output directly before accepting completion, without another model turn merely to run Git. Unrelated dirty paths are preserved and excluded, never silently committed or deleted.

## Next-100 production execution

`docs/task-program/D_NEXT_100_TASKS.json` contains the next 100 existing task identities, normalized source sections/digests, dependencies, output contracts, and execution roots. It is not another queue. The runner injects only the active entry; `PRODUCTION.md` owns order/status and `D_TASK_LEDGER.json` is its derived projection. Reuse matching proof; no new gate, permanent agent, timer, or whole-program prompt load. Read `07_BIELLA_PRODUCTION_SYSTEM.md` for the implemented local-persistence/remote-publication split and inline source repair.

## Exact audit-repair semantics
Use the controller's exact task-owned path/digest set, never a whole-project prefix, for automatic commits. Preserve required task evidence even when ignored; do not include unrelated scratch. Use the existing task-class router and observed catalog; no global Reserve preference. Existing strong-route profiles and bounded-helper limits remain unchanged. Known source conflicts survive network errors. Website validation labels require real task-bound evidence, not shell keywords. Optional Qwen failure cannot prevent authoritative production restoration.

Routine Drive sync is every five completed canonical tasks, never every attempt/tool event. GitHub and local progress stay per-task. Transfer source/proof in <=3,800,000,000-byte parts with manifest and exact readback; the controller handles batching without pausing production. See 07 for package/delta restoration and final partial-batch behavior.

## Owner production priority — GAME_FIRST
Biella Games delivery is priority NUMBER 1. Follow physical Project PRODUCTION.md order, not numeric IDs or old website-before-game plans. Execute only the active task; game quality, native stability, packaging and content work precede unrelated website/business/pilot/investor work. Reuse accepted proof; only real consumed Engine dependencies take precedence. Keep required quality and external-evidence contracts; no extra gates or replay. The existing runner, ledger and five-task Drive routine remain the mechanisms.

## Installer assembly resources
Use `package.installer.debian` (dpkg-deb) and `package.installer.windows` (NSIS/makensis) through the existing resource registry. Read `ops/workstation/INSTALLERS.md`; these tools wrap already-built target payloads, do not provide Win64 game compilation/runtime, and do not add OS/desktop/Steam configuration. Keep installer recipes and outputs in their Project; preserve the active task and existing publication cadence.

## Windows build setup
For a Windows Unreal build requirement, use `ops/workstation/UNREAL_WIN64.md` and the setup/build PowerShell scripts. Reuse current toolchain evidence; a Win32 compiler probe is not Unreal/game qualification. Missing compatible engine/media/storage remains a scoped Resource gap, never a reason to replay Linux work or mislabel NSIS as a compiler.

VISUAL_PRIORITY: D17 FINAL_VISUAL_LAYER runs before resource-blocked D08; D08 remains pending and must close before D15/D16; create/fix missing production visuals against owner direction, then qualify. No review-only loop; preserve mechanics and accepted work.
## Visual final-layer quality execution
- `VISUAL_FINAL_LAYER_ACCEPTANCE`: D17 reads `projects/biella-games/docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md`; current D08 prototype captures are `NO_PASS_ON_CURRENT_D08_BASELINE`.
- `VISUAL_QUALITY_IS_EXECUTION_WORK_NOT_OWNER_WAIT`: create/fix/validate automatically; no owner-review stall. `VISUAL_DEFECT_BUDGET_ZERO_MAJOR` and raw gameplay evidence are required; do not lower quality to close a task.

RESOURCE_BLOCKER_PROGRESSIVE_ROUTING: an unchanged `REQUIRES_OTHER_RESOURCE` result never consumes repeated strong-model turns when later canonical tasks are dependency-runnable. Preserve the blocked task/status/evidence/session, move only its canonical row behind the contiguous runnable work in the same Project production source, continue immediately, and never treat deferral as completion.
EXECUTOR_OWNS_ROUTINE_BLOCKER_RESOLUTION: routine implementation/environment/tool/resource blockers belong to the executor. Use existing authorized Resources, reversible setup and bounded routing directly; never hand executor-doable setup back to Mahdi. Escalate only a genuine product decision, unavailable credential/entitlement, or authority for a new paid/external Resource, without blocking independent GAME_FIRST work.

## MINITZ_CONTINUOUS_EXECUTION_OWNER_DIRECTIVE_V1
Read `/root/biella/analysis/live_audit/MINITZ_CONTINUOUS_EXECUTION_OWNER_DIRECTIVE.json` before every MiniTZ production turn. This is owner execution policy only; `MINITZ_TASK_PROGRAM_ONLY` remains the sole task/order/status progression authority.
`ACTION_BEFORE_CONTINUE`: exact local lookup/read/tool/resource execution must be attempted before claiming source/evidence is unavailable. A plan, narration, or repeated inspection claim is not progress. Zero-action CONTINUE is forbidden unless an exact attempted operation failed or a real authority/resource boundary is observed and recorded.
`ASTRA_UNAVAILABLE_IS_NONBLOCKING`: after fallbacks/resources have proven all executable implementation and non-Astra validation done, with no known unsatisfied executable criterion and only Astra final confirmation unavailable, return `CONTINUE` whose summary begins exactly `REQUIRES_OTHER_RESOURCE: ASTRA_FINAL_CONFIRMATION_UNAVAILABLE`. Do not falsely mark the task complete. The existing controller-native resource-deferral path preserves the pending task/session/evidence and advances immediately to dependency-runnable canonical work.
`NO_TASK_REPLAY`: never restart a task from the beginning merely because a provider/session/process changed. Process recovery resumes preserved task/session/worktree/memory/evidence; redo only a materially invalidated boundary.
`CONTINUOUS_PRODUCTION`: ordinary model/provider/tool/publication failure triggers recover/reroute/resume, not a production wait. Intentional stop conditions are explicit owner sleep or pause. Preserve dependency order, acceptance quality, single completion authority, project isolation, and the no-quota-probe rule.

## MiniTZ permanent token/resource efficiency contract — 2026-09-10

Canonical owner contract: `/root/biella/analysis/live_audit/OWNER_CONTINUOUS_EFFICIENCY_RESOURCE_CONTRACT.md`
SHA-256: `5b172321ad762c0e17b386a701bf3970d63d1cff9e1638a959e03ebd79f1f7e0`

This is the current owner-authorized permanent MiniTZ efficiency/resource contract. It applies to every MiniTZ project/task/session while production is enabled. Resolve the live project/task/revision/source identities first. Read the canonical contract at task/session bootstrap and whenever its bound digest changes; thereafter keep a stable digest-bound pointer and use delta context rather than retransmitting the full contract every turn.

Enforce one canonical progression writer. Token efficiency, project/task-scoped memory, compacted memory, current-task projection, content-addressed reuse, Upstash duplicate suppression, provider-native caching when supported, task-fit live-registry resource routing, measured project/task/provider learning, truthful dashboard telemetry, self-recovery, and up to two useful independent non-authoritative boosters are mandatory operational mechanisms. Helpers/caches/learners/resources never own task status/order/completion. Claims of cache savings, quota, resource activity, effectiveness, or progress require machine evidence. Preserve the last proven configuration and current work; reject regressions and recover the smallest boundary. Explicit owner sleep/pause overrides continuous-operation liveness until a later explicit owner resume.

## MiniTZ project-aware continuous intelligence directive — 2026-09-10

Canonical latest owner directive: `/root/biella/analysis/live_audit/OWNER_PROJECT_AWARE_GAME_PRODUCTION_INTELLIGENCE_DIRECTIVE.json` (SHA-256 `15541d7ffcb3609302216b91689bfec1e116f5228742e5119ccaadb5316cd017`). Read the full directive only for production/resource/memory/experience/model-lab work or when its bound digest changes; normal task turns receive the compact Task Program binding to preserve token efficiency.

`LIVE_PRODUCTION_PLUS_READ_ONLY_LEARNING_PLANE`: production remains primary and continuous; only an explicit owner sleep or pause stops it. Preserve exact current task/session/worktree/memory/evidence and recover/reroute/resume the smallest failed boundary instead of restarting. One MiniTZ Task Program is the only progression authority and one canonical writer owns status/completion/advancement.

CURRENT_LIVENESS_PRECEDENCE: the older `UNIFY-04` donor/negative-control text `NO resume during this migration audit` is superseded for production liveness by Mahdi's later explicit `LIVE_PRODUCTION_PLUS_READ_ONLY_LEARNING_PLANE` resume authority. Do not stop, sleep, disable, restart, or describe production as forbidden-to-resume because of that stale donor sentence. Keep it only as historical provenance. Current task/source/evidence acceptance still applies unchanged.

The Experience plane is production-read-only and authority NONE. The Model Lab has no production access by default and authority NONE. Up to two boosters are a target only when two distinct useful independent subproblems exist; use one or zero otherwise. Boosters/resources never mutate canonical progression, independently close tasks, or block the writer when they fail.

The observed local baseline `qwen3-coder-next:biella` is immutable at manifest SHA-256 `31bba289521db8c0415229002d340ffde82e81f539737cc45a0a44f511f548df`, model layer `sha256:30e51a7cb1cf1333b9e298b90b4c7790fe2572d8736b002482a0ac96328a2ffb`. Candidates are separate artifacts and cannot replace the baseline without evaluation evidence and explicit promotion scope.

Continuous intelligence execution order is: read-only experience/trajectory compiler; corpus classification; frozen evaluation; untouched-Qwen benchmark; immutable Dataset V1; isolated parameter-efficient candidate training; champion/challenger evaluation; reject-or-shadow; non-authoritative canary; capability-specific promotion. Never train directly on moving live files, never leak customer/project data, never let learning become liveness/progression authority, and never claim learning/cache/model improvement without machine evidence.

## MiniTZ game-production execution-ready compilation contract — 2026-09-10

Canonical owner contract: `/root/biella/analysis/live_audit/OWNER_GAME_PRODUCTION_CAPABILITY_COMPILATION_CONTRACT.md` (SHA-256 `4530b3119131f65f8c6e059174ea7b56d6e9c4c8828dce6de7e3d3434d8e3f5e`). Machine binding: `/root/biella/analysis/live_audit/OWNER_GAME_PRODUCTION_CAPABILITY_COMPILATION_BINDING.json` (SHA-256 `161d7e197a124c907867b2da0ccbd93310ca6d891093e7ba8f42eaa8f1dd4172`). This extends the current project-aware intelligence directive without creating a second queue, scheduler, progression writer, or completion authority.

`VALUE_GATE_PASSED != EXECUTION_READY`. The 500 `GAME-PROD-*` donor obligations must not be executed from generic/title-only task semantics. Use the existing canonical path `TASKPROG-COMPILE -> PROGRAM-CUTOVER-GATE -> TASKPROG-APPLY` before `GAME-PROD-001`: compile exact live project/task/source truth into `minitz.execution_ready_game_task/v1` proposals; validate them; only the canonical Task Program writer may admit/mutate task definitions. Helpers/Commander/resource/model outputs are proposals with authority NONE.

An execution-ready GAME-PROD task must have task-specific desired/current/gap semantics, specific capability identities, exact inputs/outputs/deliverables, exact task-owned write paths, semantically classified dependencies, runtime scenario where applicable, non-empty task-derived validation, task-specific false-success/negative controls, expected failure signatures/recovery policy, evidence requirements, and a completion receipt bound to exact project/program/task/revision/source/output identities. Provider/model names are Resources, not capability identities. Unknown product facts remain UNKNOWN and cannot be invented.

The feeder may execute a GAME-PROD task only when its compiled definition is `EXECUTION_READY` and hard dependencies are complete. If a future GAME-PROD frontier is still preserved but uncompiled, invoke the canonical definition-compilation path and continue other dependency-runnable work; do not let the writer invent semantics mid-execution and do not falsely complete or serialize independent work. Preserve donor order as provenance only; convert an edge to `HARD` only when semantic validity actually requires it.
