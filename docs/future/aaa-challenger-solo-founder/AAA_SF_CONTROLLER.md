# AAA-SF Future Executor Controller

Status: `FUTURE_BLOCKED`
Program: `AAA-SF-001..AAA-SF-072`

## Purpose

Execute the post-defined-program AAA Challenger Solo Founder map through the current Biella production path without creating another controller, queue, memory, or Project authority.

## Loop

1. Until `AAA-SF-001` proves the then-authoritative predecessor closure set, no later AAA-SF task may activate.
2. Resolve current Project/lane/task authority from current source. The observed 2026-09-05 controller is `biella-codex` and Games feeder authority is `/root/biella/work/games-production.json`; if current accepted source later supersedes either, use the newer source.
3. Find the first AAA-SF task not durably closed. `AAA_SF_TASK_MANIFEST.json` is a map only, never a second queue.
4. Compile that one task into the current compact AI task packet: `id, objective, authority, read, write, preserve, must, must_not, dependencies, resources, acceptance, validate, persist, stop`.
5. Load only the packet, scoped `AGENTS.md`, and direct current source. Expand context only for a named unresolved fact.
6. Record a context receipt in existing attempt/Event evidence: project, task, source commit/tree, authority refs, files loaded, expansion reasons, timestamp. Do not create a separate mutable context authority.
7. Execute through the current public Biella controller; match acceptance to observed task-derived tests/build/runtime/artifacts/publication evidence.
8. On failure, preserve verified work and recover only the smallest invalidated boundary.
9. Persist closure evidence; Git/Drive publication requires exact remote readback. Advance only after durable closure.
10. When available, retain context/execution telemetry needed by `AAA-SF-045..052`: context size, expansions, repeated reads, retries, reuse, routing outcome, validation failures, duration, and accepted result.

## Source classes

- Current execution/Git/Drive authority: may drive the active packet.
- Stable architecture/operating rules: may constrain execution when still current.
- Normalized historical candidates: may be reused only after current accepted admission.
- Raw history, old state snapshots, investor scenarios, and generated drafts: evidence/reference only; never execution authority.

## Forbidden shortcuts

- No mass activation or preload of all 72 tasks.
- No assumption that a publication-time D01/BG-PROD/controller snapshot remains authoritative.
- No second controller, Games queue/state file, memory system, routing layer, or validation framework.
- No automatic promotion of `UNKNOWN`, historical candidates, or generated drafts.
- No permanent reviewer/critic/repair chain.
- No `AAA-SF-072` declaration without every required proof being durably readable.
