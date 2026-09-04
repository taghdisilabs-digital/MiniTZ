# Biella AI Production Map + Task Contract Design

## Status
Research-grounded design for improving the existing Biella/Codex production feeder without creating a second scheduler, queue, memory, controller, or Project authority.

## Live baseline — 2026-09-05
- Canonical Engine checkout: `/root/biella/repos/biella-engine`.
- Observed local/remote `main`: `6485b8c5fefe1cc2be41de57fe2e3d76c39931a1`.
- Observed tree: `c083044227007ee35a3b501f618f3acbce515764`.
- Worktree observed clean and tracking `origin/main`.
- `biella-codex` is the only public AI/production controller.
- Games feeder authority is `/root/biella/work/games-production.json`.
- Feeder is `WAITING_DEMO_HANDOFF`; Demo 01 is 10/50 complete; current task is `D01-011`.
- Demo execution remains externally owned until all Demo 01 tasks close; feeder must not execute Demo work during that ownership window.

## Research result
The strongest shared pattern across current Biella source, Superpowers, and current Codex guidance is: give the agent a small navigable map, a bounded task contract, exact context pointers, executable validation, and durable evidence. Do not preload broad manuals or duplicate state.

OpenAI's current Codex guidance favors issue-like prompts with concrete file/component pointers, persistent repository instructions through `AGENTS.md`, and well-scoped tasks. Current harness-engineering guidance explicitly favors a map over a monolithic instruction manual. Biella already implements the correct foundation through progressive context and a single feeder authority.

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

## Fifteen concrete improvement tasks

### Phase 1
1. **Authority resolver** — derive Project/lane/task and exact current Git/Drive/runtime identities from existing sources.
2. **Context compiler** — select the minimum initial read set from scoped `AGENTS.md`, canonical task/state, and touched source.
3. **Context receipt** — record exact loaded identities and expansion reasons inside existing attempt/Event evidence.

### Phase 2
4. **Task-packet schema** — implement the ordered compact contract above with strict validation and `UNKNOWN` preservation.
5. **Canonical-to-packet compiler** — compile existing feeder section tasks and Engine numbered tasks without creating a second queue.
6. **Task lint** — reject ambiguous acceptance, missing write boundary, duplicate policy prose, invented dependencies, and missing stop conditions.

### Phase 3
7. **Feeder packet injection** — pass the packet and bounded current context to fresh Codex task execution.
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

## Non-negotiable integration constraints
- Do not replace `biella-codex` or add another public controller.
- Do not create another Games queue/state/progress authority beside `/root/biella/work/games-production.json`.
- Do not move global policy from scoped `AGENTS.md` into every task packet.
- Do not let packet compilation reopen completed work without material invalidation evidence.
- Do not let context optimization reduce semantic capability; it changes loading/routing, not what Biella can do.
- Do not serialize independent work unless dependencies, side effects, or Resources require it.
- Do not add a permanent reviewer/critic/repair chain. Validation remains task-derived.
- Do not use historical evidence as current authority.

## Current-state reconciliation rule
The checked-in `03_BIELLA_CURRENT_STATE.md` and `04_BIELLA_ACTIVE_TASK.md` still record Engine numbered frontier P4-06, while newer current source also contains the unified workstation/control/feeder implementation and an active Games Demo production document. These facts are not merged into a synthetic claim. Engine numbered-frontier truth and current Games production-controller truth remain separate until authoritative continuity explicitly reconciles them.

This design therefore does not declare P4-06 complete, Foundation complete, or Games Demo complete. It only improves how current and future tasks are described, loaded, executed, measured, and closed.

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
