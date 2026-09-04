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
Never print secret values, API keys, bearer tokens, refresh tokens, or credential contents.

Visual/media observability: when a Project task generates a visual/media candidate and no more specific canonical Project output path is already defined, persist it under `/root/biella/artifacts/website`, `/root/biella/artifacts/engine`, or `/root/biella/artifacts/games` as appropriate so the private Visuals / Assets inspector can surface it. Generated candidates remain `GENERATED_DRAFT` unless Mahdi explicitly accepts them.

## Codex model routing

Mahdi controls Codex account usage, quota resets, and any manual usage-tier decisions. Automation must not redeem or alter those limits.
The internal `biella-codex feed` path may choose a Codex model for a bounded task from observed task class and observed model availability; model selection does not create a second controller or memory authority.
Use `gpt-6-astra` with `ultra` reasoning for hard frontier work, deep Project-memory synthesis, authority reconciliation, difficult integration/acceptance, and hard creation decisions.
Creation tasks never use low reasoning. Use at least high reasoning for creation; use xhigh/max/ultra when task risk, ambiguity, visual/product consequence, or integration depth warrants it.
Short bounded tasks may prefer Luna with smaller reasoning effort, then fall back to another eligible Codex model when the preferred model returns an observed usage/rate-limit error.
Never probe quota by spending a model call. Learn model availability only from normal task execution results and local model-catalog metadata.
## Games production feeder

The active Games feeder has one durable production document: `/root/biella/work/games-production.json`. It contains ordered sections and task status in the same document; do not create separate queue, state, batch, or progress-ledger authorities.
Demo 01 is the first section. Preserve current canonical Demo completion and resume only the earliest unfinished task. Never reopen completed tasks unless current authoritative evidence materially invalidates them.
After Demo 01, continue through the current accepted Games implementation sections from `docs/IMPLEMENTATION_SEQUENCE.md`. Empty sections are planned just-in-time with a bounded 20-50 task set, stored inside that same section.
Use Astra Ultra for section planning/audit and deep-memory frontier resolution when available. Section planning must stay inside the current accepted section, avoid overlapping tasks, and never invent product scope from stale TODOs or historical evidence.
After executing a section, audit that same section. Append only materially missing tasks to it; mark the section complete only with current implementation/runtime evidence. Then advance to the next section.
When another controller owns the Demo 01 write boundary, the feeder may remain active only as `WAITING_DEMO_HANDOFF`: sync/read current Demo progress, execute no Demo task, write no Games source, and launch no Unreal process. When all Demo tasks are complete, the same feeder automatically advances to Stage 2.
