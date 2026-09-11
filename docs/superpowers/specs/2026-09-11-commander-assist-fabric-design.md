# MiniTZ 30-Commander Assist Fabric Design

## Status
Owner-approved architectural implementation under current `UNIFY-04` helper/service continuity scope. This subsystem has authority `NONE` and does not change the canonical current task.

## Objective
Provide exactly 30 logical Commander assist lanes that can inspect one current MiniTZ task in parallel, share the same task memory/projection/evidence identity, and return bounded read-only findings to the canonical writer without becoming progression authorities.

## Invariants
- One MiniTZ Task Program remains the only progression authority.
- One canonical writer owns task mutation, validation admission, completion, commits, publication, and advancement.
- Commander lanes never edit files, execute mutating task actions, commit, push, publish, close tasks, change task status, or reorder tasks.
- Writer progress outranks all Commander activity; the writer never waits for lanes.
- Exactly 30 logical lanes exist (`CMD-01`..`CMD-30`). A lane may be unassigned while still structurally present.
- Existing two TaskBooster assists remain separate and unchanged.
- Commander work is content-addressed by task identity, task-state digest, projection digest, lane role, and requested provider. Duplicate work is suppressed.
- Provider/session/token caches remain provider-native; MiniTZ shares durable task memory, compacted projection, evidence, result cache and failure cache.
- Local Qwen is reserved for the canonical writer by default; Commander dispatch prefers external `llm.fast` resources.
- Top-level lane/provider status uses only `OFFLINE`, `ACTIVE`, `OUT_OF_CREDIT`, `NEEDS_MODIFICATION`. Activity/lease details are diagnostic fields, not competing statuses.

## Lane Roles
1 requirements, 2 task-boundary, 3 source-map, 4 architecture, 5 implementation, 6 integration, 7 tests, 8 regression, 9 validation, 10 failure-triage, 11 checkpoint-continuity, 12 memory-context, 13 cache-reuse, 14 provider-routing, 15 concurrency, 16 performance, 17 build, 18 runtime, 19 api-contract, 20 dependency, 21 data-flow, 22 observability, 23 evidence, 24 publication, 25 portability, 26 resilience, 27 simplification, 28 risk, 29 alternate-solution, 30 independent-review.

## Runtime Model
`minitz_commander_fabric.py` owns lane definitions, schemas, bounded context construction, cache keys, provider assignment, result validation, four-state classification, durable lease/index records, and safe stale-lease reconciliation.

`biella_production_runner.py` owns process lifecycle only: reap finished Commander workers, launch useful missing lanes nonblocking after the current compacted projection exists, include only the fabric index path in the canonical writer prompt, and terminate spawned Commander children on runner exit. It never waits for a Commander result.

Each lane invokes the existing `biella resource fast-llm` path with prompt on stdin. The prompt carries a compact bounded packet rather than raw project files or secrets. Results must be strict JSON and pass the Commander schema before entering the accepted cache.

## Provider Routing
Commander dispatch uses currently configured external `llm.fast` providers, excluding `ollama-qwen` by default so assist traffic cannot starve the writer. Provider selection is deterministic round-robin over eligible external routes. Each Commander lease is bound to exactly one requested provider with resource failover disabled for that call, so concurrency accounting cannot silently spill into another provider. An unproven provider starts with one useful canary lane; only a validated result promotes that provider to its configured lane cap. A quota/offline/config failure backs off all lanes assigned to that provider until a bounded retry time, without quota probes or writer waiting. Actual successful provider/model is recorded from routing evidence. A provider/lane failure never blocks another lane or the writer.

## Persistence
Runtime root: `memory/commander-fabric/`.
- `current.json`: current task-state fabric projection with all 30 lanes.
- `<cache-key>.lease.json`: durable non-authoritative lease.
- `<cache-key>.accepted.json`: validated result.
- `<cache-key>.rejected.json`: preserved failure/rejection.

Leases contain task/lane/cache identity, PID, requested provider and expiry. Dead/expired leases are reconciled without mutating task state.

## Public/Control Projection
The control projection exposes only a bounded Commander summary: total lanes, active/inflight/useful/rejected counts, and per-lane four-state/activity labels. It does not expose prompts, raw provider outputs, secrets, private file content, or model-native session identifiers. The public live page may show the aggregate `30 COMMANDER LANES` status/count but does not expose private findings.

## Acceptance
- Exactly 30 stable lane IDs and 30 unique roles.
- Content-addressed duplicate suppression.
- No mutation authority in schema or prompts.
- Writer prompt references Commander index non-authoritatively and stays bounded.
- Zero Commander results still permits normal production.
- Commander process/provider failures are preserved and nonblocking.
- Local writer Qwen is excluded from Commander dispatch by default.
- Stale leases recover safely after restart.
- Existing TaskBooster/main-coder tests remain green.
- Installed runtime modules match source digests after activation.
- Controlled service restart preserves `UNIFY-04` task identity and resumes heartbeat.
