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

Provider discipline: use one external provider by default; fan out only for a unique capability, required fallback, or material independent validation. Prefer deterministic/local execution when it is sufficient, but Codex chooses the tool/resource based on the task rather than a model-specific workflow.

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
- `FINAL_DELIVERABLE_PUBLICATION`: every final deliverable keeps an exact canonical local identity and, when current Project/task authority defines a canonical publication destination, the exact final file is published there and read back/verified before durable completion. Never invent a destination. Publication failure preserves the local file and remains retryable/`CONTINUE`; publication is never inferred from an attempted upload.
- `DURABLE_FAILURE_LEDGER`: every observed production/model/provider/tool/runtime/validation/publication failure or retry is recorded in AI-readable JSONL at `/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl` with task/time/type/status and bounded diagnostics. Failure records aid diagnosis and never override current source/task authority.

- `LOSSLESS_MEMORY_COMPACTION`: raw authority, evidence, artifacts, task records, and failure records are never rewritten or deleted by compression. The compactor creates rebuildable derivative JSON/JSON.GZ indexes with exact source digests, content-addressed unique records, equivalence groups that retain every exact variant and provenance, and a bounded current-task projection. Compaction failure is an optimization failure only and must never stall, reset, fail, kill, or advance a task.
- `VERIFIED_ACTION_MEMORY`: instructions, tasks, verified actions, failures, capabilities, task IDs, and task classes are categorized separately. Only evidence from `COMPLETE`/`COMPLETE_ALREADY` work is promoted as a verified action. Cross-task comparison may identify equivalent/reusable patterns, but conflicting or unique content, source refs, task-specific facts, and capabilities are preserved rather than collapsed.
- Routine dependencies, reversible environment repairs, and already-authorized implementation choices are execution work, not approval gates. Genuine destructive/irreversible external actions without authority, unavailable required facts/authority, safety constraints, and required task sequencing remain real boundaries.

## Storage placement and cold archives — 2026-09-06

Apply `docs/project-state/BIELLA_STORAGE_POLICY.md` for storage/offload work. Keep active source, required tools/models, current task evidence and runtime state local; use attached storage for useful staging and verified Google Drive archives for genuinely cold packages, backups and superseded handoffs. Before deleting a selected local replica, verify the exact remote bytes and preserve its restore locator/provenance.

To find an offloaded item, read `/root/biella/archive/README.md` and `COLD_STORAGE_INDEX.json` first. Retrieve only what the current task needs. Archived instructions remain inactive historical evidence; do not rehydrate old workflows or reset completed work. This is storage placement, not a new task queue or background cleanup service.
