# Biella AI Production Map + Task Contract Design

## Status
Research-grounded design for improving the existing Biella/Codex production runner without creating a second scheduler, queue, memory, controller, or Project authority.

## Current execution architecture
- Canonical repository/checkout: `patrickminitz-web/biella-engine` at `/root/biella/repos/biella-engine`.
- `biella-codex` is the only public AI/production controller.
- Durable execution state is `docs/project-state/03_BIELLA_CURRENT_STATE.md`, `docs/project-state/04_BIELLA_ACTIVE_TASK.md`, and the active Project `projects/biella-games/docs/PRODUCTION.md`.
- Runtime execution is owned by the monorepo-native `biella-codex production` runner; runtime JSON/logs are telemetry/evidence only.
- Historical prior-executor architecture is retained in Git history/archive evidence and is not current routing authority.

## Research result
The strongest shared pattern across current Biella source, Superpowers, and current Codex guidance is: give the agent a small navigable map, a bounded task contract, exact context pointers, executable validation, and durable evidence. Do not preload broad manuals or duplicate state.

OpenAI's current Codex guidance favors issue-like prompts with concrete file/component pointers, persistent repository instructions through `AGENTS.md`, and well-scoped tasks. Current harness-engineering guidance explicitly favors a map over a monolithic instruction manual. Biella already implements the correct foundation through progressive context and a single production authority.

## Design objective
Turn each canonical production task into a compact, deterministic AI execution packet that maximizes useful model context and production power while minimizing repeated prose, stale context, rediscovery, and token waste.

## Five-phase production map

### Phase 1 — Source Truth + Context Identity
Establish exact task authority and source identity before execution. Resolve only facts required by the active task. Produce a compact context receipt from current Git/Drive/runtime evidence; do not create another source-of-truth file.

### Phase 2 — AI/Codex Task Contract
Compile the canonical task into a token-efficient packet with stable field order and no duplicated policy prose. The packet describes outcome, exact context pointers, boundaries, writes, validation, durability, and stop condition.

### Phase 3 — Context + Execution Integration
Feed only the compiled packet plus directly required source into the existing `biella-codex` execution path. Expand context on demand. Preserve completed work and resume the earliest unfinished task. Permit concurrency only inside task/section boundaries when dependencies, side effects, and Resources allow it.

### Phase 4 — Evidence + Publication Closure
Bind completion to observed evidence. Tests/build/runtime/artifacts/publication must match the task contract. Commit/push and Drive publication require exact remote readback when the task publishes. Recover only the smallest failed boundary.

### Phase 5 — Measured Production Optimization
Measure useful context bytes/tokens, context expansion count, rediscovery, retries, execution duration, validation failures, reuse, and completion quality. Promote only evidence-backed improvements to routing/task patterns; never silently change Project truth or Engine invariants.

## Canonical AI task packet
Use a compact ordered structure. Fields omitted by the canonical source stay absent or `UNKNOWN`; they are not inferred.

```yaml
task:
  id: <durable task id>
  objective: <one outcome sentence>
  authority: [<exact current refs>]
  read: [<minimum required paths/IDs>]
  write: [<allowed output paths/interfaces>]
  preserve: [<existing valid work/invariants>]
  must: [<task-specific requirements>]
  must_not: [<task-specific exclusions only>]
  dependencies: [<real prerequisites>]
  resources: [<semantic requirements or observed routing facts>]
  acceptance: [<observable completion conditions>]
  validate: [<exact tests/build/runtime/readback>]
  persist: [<Git/Drive/artifact/evidence destinations>]
  stop: <exact execution boundary>
```

## Packet rules
1. `objective` describes the result, not worker choreography.
2. `authority` names exact revisions/IDs instead of copying large source text.
3. `read` is the initial context allowlist; expansion requires a specific unresolved fact.
4. `write` makes side effects and ownership machine-readable.
5. `preserve` prevents destructive restart and repeated completed work.
6. `must` contains only task-local requirements not already supplied by scoped `AGENTS.md`.
7. `must_not` contains only concrete failure modes relevant to this task.
8. `acceptance` is observable and artifact/runtime based; no vague "done" state.
9. `validate` contains commands/checks Codex can actually execute or evidence it can actually inspect.
10. `persist` separates local success from durable publication.
11. `stop` prevents accidental spill into the next numbered/section task.
12. Global execution policy stays in `AGENTS.md`; task packets do not restate it.

## Context receipt
A context receipt is execution evidence, not a second state authority. It should be embedded in the task attempt/result record or equivalent Engine Event and contain only identities needed to reproduce what the model saw:

```yaml
context_receipt:
  project: <project id/path>
  task: <task id/revision>
  source_commit: <sha|null>
  source_tree: <sha|null>
  authority_refs: [<path/id + digest/revision where material>]
  files_loaded: [<path + identity>]
  expansions: [<reason -> added ref>]
  generated_at: <timestamp>
```

The receipt must not become another queue, task ledger, mutable memory file, or authority layer.

## Production-map task sizing
A production task should be the smallest unit with its own meaningful acceptance/evidence boundary. Do not split setup, implementation, validation, and documentation into separate tasks when they exist only to deliver one inseparable result. Split when one result can be independently accepted or rejected without invalidating its neighbor.

## Twenty concrete improvement tasks

### Phase 1
1. **Authority resolver** — derive Project/lane/task and exact current Git/Drive/runtime identities from existing sources.
2. **Context compiler** — select the minimum initial read set from scoped `AGENTS.md`, canonical task/state, and touched source.
3. **Context receipt** — record exact loaded identities and expansion reasons inside existing attempt/Event evidence.

### Phase 2
4. **Task-packet schema** — implement the ordered compact contract above with strict validation and `UNKNOWN` preservation.
5. **Canonical-to-packet compiler** — compile existing Project production section tasks and Engine numbered tasks without creating a second queue.
6. **Task lint** — reject ambiguous acceptance, missing write boundary, duplicate policy prose, invented dependencies, and missing stop conditions.

### Phase 3
7. **Runner packet injection** — pass the packet and bounded current context to fresh Codex task execution.
8. **Demand context expansion** — add source only when a named unresolved fact blocks correct execution; record each expansion.
9. **Dependency/concurrency classification** — derive safe parallel-ready nodes inside a task/section without allowing overlapping writes or cross-boundary execution.

### Phase 4
10. **Evidence matcher** — map acceptance requirements to observed tests/build/runtime/artifact/evidence rather than generic success.
11. **Durable publication closure** — bind Git commit/tree and Drive/file identities to exact remote readback where publication occurs.
12. **Smallest-boundary recovery** — persist enough failed-unit evidence to retry only invalidated work while preserving verified outputs.

### Phase 5
13. **Context efficiency telemetry** — measure initial context size, expansions, repeated reads, and useful-source ratio.
14. **Execution efficiency telemetry** — measure retries, fallback/routing outcomes, reuse, validation failures, and task duration.
15. **Evidence-based task-pattern learning** — version successful packet/task patterns and routing lessons without modifying Project authority or universal invariants silently.

## AAA-challenger control surface
The private `/control/` console is the operator surface for the same production truth; it must not become another workflow, scheduler, queue, state authority, or task ledger. Its job is to make the current canonical production state understandable in seconds and to make solo-founder AAA-challenger production visibly credible.

### Information architecture
Use four primary sections only: **Control**, **Work**, **Outputs**, and **System**. `Website`, `Engine`, and `Games` are project context selectors, not a second navigation hierarchy. Remove primary pages whose information belongs inside these four sections: Live dialog becomes the Control command composer; Capabilities & Run becomes task-local actions; milestones become production-map progress; files and visuals become Outputs; services, workers, hardware, model/API state, and context controls become System.

### Automatic liveness and progress
The console continuously reads the existing gateway/controller/production-runner state so Mahdi never needs to ask whether production is active. The persistent header and Control view show `ACTIVE`, `WAITING`, `STALE`, `STOPPED`, or `ERROR`, plus current Project, section, exact task, model/reasoning, task/section progress, next task, last heartbeat, last evidence update, current Git identity, and Drive publication/readback state where relevant. A stale heartbeat must display `STALE`; the UI must never infer `ACTIVE` from an old status value. This is observability of existing state, not a new heartbeat authority.

### Control view
The default view answers, in order: **what is being built, what exact task is active, how far production has progressed, what model/resource is executing it, what happens next, and what current evidence proves progress**. Show one dominant current-task block, one production-map progress surface, latest validated evidence/output, and a compact recent-activity stream. Routine healthy infrastructure is visually quiet.

### Work view
Render the unified section/task graph from canonical production state. Show one row per canonical semantic task. Overlapping source task IDs appear as aliases/evidence behind that row, never as duplicate executable work. Completed tasks stay collapsed by default; current and blocked work get visual priority.

### Outputs view
Unify source, builds/packages, visuals/media, and evidence under one output browser with filters such as `All | Source | Builds | Visuals | Evidence`. Games should foreground real runtime screenshots, validated gameplay captures, environments, characters, VFX/UI, and packaged builds. Metadata is secondary to the production artifact, but exact identity/digest/status remains available. Generated visuals remain `GENERATED_DRAFT` until explicitly accepted.

### System view
Combine GPU/CPU/memory, Codex model availability/reasoning, API/provider health, workers, services, context limits, and failure state. Show exceptions and constraints first. Healthy systems should not dominate the operator screen. Codex usage/reset remains Mahdi-controlled; the UI may report observed availability but must never redeem/reset usage.

### AAA-challenger visual standard
Replace the generic neon AI/SaaS dashboard language with a restrained professional production-workstation language: near-black/graphite foundation, thin neutral separators, minimal elevation, one primary active-state accent, success/warning/error colors only for real state, stronger typography hierarchy, dense but readable technical metadata, and almost no decorative glow/gradient. Use actual project imagery and validated artifacts wherever visual context helps. The Games control surface should visually communicate `one founder -> one production system -> real editable work -> real builds -> measurable quality/progress`, not "AI dashboard" aesthetics.

Operator presentation is production-dense and fast. A proof/showcase presentation may use the same underlying data and artifacts for investor/external proof, but it is only another presentation of the same state and must not create a second workflow or evidence source.

### Control-surface implementation tasks
16. **Unified control projection** — project the same canonical task/section/evidence/system state into one frontend payload without a second state store.
17. **Four-section information architecture** — rebuild navigation/rendering around Control, Work, Outputs, and System and remove duplicated status surfaces.
18. **Automatic liveness** — expose heartbeat/freshness/current-task/model/progress/evidence timestamps and classify ACTIVE/WAITING/STALE/STOPPED/ERROR from current observed state.
19. **AAA-challenger visual system** — replace generic neon dashboard styling with the production-workstation hierarchy above and make real project artifacts first-class.
20. **Browser qualification** — verify desktop/mobile readability, task/progress comprehension, stale-state behavior, artifact inspection, accessibility, and that no control view invents or duplicates production authority.

## One canonical repository and workspace
The approved durable Git authority is one repository: `patrickminitz-web/biella-engine`. The canonical checkout remains `/root/biella/repos/biella-engine`; there must be no second active repo under `/root/biella/repos/` after migration.

### Repository ownership
- Reusable Engine kernel, capabilities, functions, APIs, providers, schemas, universal production knowledge, workstation/controller/production runner, website, and private control console live in the canonical repository.
- Biella Games remains a Project boundary inside `projects/biella-games/`: Unreal source, content/assets, Project requirements/canon, Games-specific evidence, and game-specific build/package logic stay Project-scoped.
- Sharing a Git repository never promotes Games-specific semantics into Engine capabilities. Reuse still requires explicit semantic extraction/admission.
- `capability_preparation` is migration input only. Reusable current material is normalized into Engine; dated research/registries remain reference/evidence; old repository policy files never become active instructions.
- AAA-SF remains a future blocked program and may be stored under a clearly future/reference namespace, never as a second live queue/controller.

### Progress-preserving migration
**Hard invariant: do not remove any progress done so far.** Progress includes source changes, completed tasks, partial work, commits, branches, worktrees, artifacts, test/build/runtime evidence, Drive records, recovery material, and provenance. Consolidation may change what is active, but not erase progress.

Before changing active routing for any source, commit/persist every dirty or divergent lane that contains work. Import the newest verified source bytes and evidence into the canonical repository, validate them in the new path, and push/read back the canonical commit. Superseded copies are archived or deactivated from active selection but are not deleted by this migration. A migration must never reset a completed task, overwrite newer work with an older branch, discard historical progress, or infer that a divergent branch is useless from ancestry alone.

### Semantic task deduplication
New or migrated tasks are compared by objective, write boundary, dependencies, acceptance, and evidence. Exact duplicates become aliases; contained tasks are absorbed; partial overlap becomes shared core plus missing delta; implementation, qualification, and external-proof tasks remain separate when they establish distinct evidence. Completed tasks do not reopen without material invalidation evidence.

### Production runner authority
The production runner is an executor, not a Project state authority. Durable task/section progress comes from canonical Project/current-state documents in the repository and their Drive identities. Production runtime JSON/logs may contain ephemeral cooldowns, attempts, heartbeat, and observed model state only. They must not become a second completion ledger. The legacy feeder is retired. The monorepo production runner starts only from verified canonical state and resumes the earliest unfinished task.

### Workspace lifecycle
Feature worktrees and branches are execution sandboxes, but their completed progress must remain recoverable. On completion, useful work is merged into canonical `main`; superseded worktrees/branches are deactivated from active routing and retained through durable commit/reference or archived snapshot. `/root/spark-biella-games`, `/root/biella/recovery`, `/root/biella/backups`, and similar recovery sources are never treated as active authority after supersession, but this consolidation does not delete them. Preserve all progress, evidence, and provenance unless Mahdi later explicitly authorizes deletion of a specific copy.

### Unified Drive navigation
Drive keeps one active Biella root. Active navigation is limited to `CURRENT`, `PROJECTS/GAMES`, `OUTPUTS`, and `ARCHIVE`. Preserve existing file IDs when moving/renaming canonicals. Current state and active task live under `CURRENT`; Games Project authority/evidence lives under `PROJECTS/GAMES`; generated/validated outputs live under `OUTPUTS`; superseded progress, recovery, backups, and provenance are moved or labeled under `ARCHIVE` rather than deleted. The active surface is simplified without erasing prior progress.

## Cost-aware external Resource routing
Mahdi explicitly authorizes use of already activated free tiers, trial credits, prepaid credits, and paid external services when they materially reduce completion time, Codex token use, compute cost, or improve task quality. Cost availability is a Resource property, never a reason to create another controller or workflow.

### Routing invariant
`biella-codex` remains the single controller. Before spending expensive general-model reasoning, execution should prefer the cheapest sufficient implementation in this order: deterministic/local tool; specialized connected API; fast/low-cost inference provider; high-reasoning Codex model when the task actually requires it. Quality/acceptance requirements override price. Paid use is allowed; there is no artificial prohibition on spending configured service credits.

Provider/model identity remains replaceable `Resource` state. A task asks for semantic capabilities such as `research.search`, `llm.fast`, `audio.transcribe`, `audio.speech`, `image.generate`, `vector.search`, `database.sql`, `cache.ephemeral`, `media.transform`, `compute.remote`, or `observability.query`; routing selects a currently configured implementation.

### Initial connected Resource map
- Research: Tavily for fresh search/crawl; Exa for semantic/code/paper retrieval; Pexels for external visual-reference discovery only.
- Fast inference: Groq, Cerebras, Mistral; OpenRouter for unique-model/fallback access; Cloudflare Workers AI when its model/runtime fits.
- Retrieval: Qdrant and Pinecone as replaceable vector backends; do not duplicate the same durable knowledge into both without task evidence.
- Audio: Deepgram for low-latency STT/audio processing, AssemblyAI for transcript/diarization analysis, ElevenLabs for production speech, Cloudflare audio adapters as an existing alternative.
- Visual/media: Stability AI for generation when Project authority permits; Cloudinary for transforms/delivery once its account locator is resolved; Pexels remains reference input rather than canon.
- Data: Neon for PostgreSQL tasks; Supabase for Project backend/auth/storage only when its project locator is resolved; Upstash for ephemeral cache/rate/coordination only, never canonical progress.
- Compute: Saturn and Modal as remote compute Resources selected by task requirements.
- Observability: Axiom when its configured token/permissions support the required query/ingest operation.

### Resource registry and dispatcher
Expose one compact machine-readable registry plus one `biella resource` dispatcher. The registry reports semantic capabilities, configured/connected/needs-locator/restricted state, cost preference (`free_credit_preferred`, `paid_allowed`), and safe provider metadata without credentials. The dispatcher owns provider-specific request formatting and response compaction so task agents do not repeatedly spend tokens reconstructing curl/API syntax or ingesting oversized provider responses.

Initial executable dispatcher operations are deliberately high-leverage: `status`, `route <capability>`, `search` (Tavily/Exa), and `fast-llm` (Groq/Cerebras/Mistral/OpenRouter-compatible providers). Media/audio/vector/database providers are represented immediately in the registry and are added to the same dispatcher when an active task needs that operation; they must not become separate public controllers.

### Cost and evidence
Routing may use paid services automatically under Mahdi's authorization. Prefer existing free/trial/prepaid balance when observable, but never perform quota-probing calls solely to inspect balances. Record provider, semantic capability, operation, latency, model where applicable, and usage/cost fields when the provider returns them. Provider success is not task acceptance; outputs still require task-derived validation.

### Locator rule
A credential without its required account/project locator is `NEEDS_LOCATOR`, not `CONNECTED`. Search existing authorized configuration for the locator before asking Mahdi and never infer a locator from a secret. The supplied Supabase URL, Upstash account email, and Cloudinary cloud name are now configured runtime locators. The supplied `endpoint` is the Qdrant cluster URL (`QDRANT_URL`), not a separate provider. Current Resource status therefore has no unresolved locator.

## Non-negotiable integration constraints
- Do not replace `biella-codex` or add another public controller.
- Do not create a durable runner queue/state/progress authority beside canonical 03/04/Project task sources; production runtime state is non-authoritative execution telemetry only.
- Do not move global policy from scoped `AGENTS.md` into every task packet.
- Do not let packet compilation reopen completed work without material invalidation evidence.
- Do not let context optimization reduce semantic capability; it changes loading/routing, not what Biella can do.
- Do not serialize independent work unless dependencies, side effects, or Resources require it.
- Do not add a permanent reviewer/critic/repair chain. Validation remains task-derived.
- Do not use historical evidence as current authority.

## Current-state reconciliation rule
Mahdi has now explicitly authorized repository/workflow consolidation. Preserve Engine P4-06 as `INCOMPLETE_DEFERRED`; do not claim it complete. Games Demo execution becomes the active Project frontier during consolidation, with the exact current Demo checkpoint reobserved before each state migration. The unified state must represent both facts without two competing active workflows.

## Success criteria
The production-map improvement is successful when:
- the same canonical task can compile deterministically into the same semantic packet for unchanged authority;
- a normal Codex task starts with materially less irrelevant context than broad preload;
- context expansion is reasoned and attributable;
- completed work is reused unless invalidated by current evidence;
- task acceptance maps to concrete validation/evidence;
- no duplicate controller/queue/state/memory authority is introduced;
- Git/Drive publication claims are tied to remote readback;
- task execution can resume after context/model/process changes from durable state;
- measured telemetry can distinguish context waste, execution failure, routing failure, and genuine task difficulty.
