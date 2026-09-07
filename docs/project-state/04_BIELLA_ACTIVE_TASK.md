# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v11

task:
  id: D03-01
  project: Biella Games
  section: post_d01
  class: hard_creation
  title: Production rendering, animation, VFX, and audio quality
  status: SLEEPING_OWNER_REQUESTED
  runner: SLEEPING

  authority:
    - Mahdi Taghdisi latest explicit instruction, 2026-09-07
    - current observed execution state
    - docs/project-state/03_BIELLA_CURRENT_STATE.md
    - projects/biella-games/docs/PRODUCTION.md

  continuity:
    completed_predecessor: D02-04
    production_source: projects/biella-games/docs/PRODUCTION.md
    implementation_commit: e6c997b0097651b0265cf6b4663049bc2eb65b30
    implementation_tree: ef26e47bfb606bd3e7a8b41f5249adb57203eee2
    task_session_id: null
    prior_invalidated_executor_session_id: 01a07931-fb65-7af1-830d-83afb2ee5d8d
    session_rotation_reason: CONTEXT_BLACKHOLE_AND_STALE_FRONTIER
    attempt: 293
    model: null
    reasoning: null
    current_increment: PORTABLE_PSO_SEED_AND_LOADING_DISPLAY_COLD_START_QUALIFICATION
    task_memory: /mnt/biella-extra/biella-runtime/codex-production/task-memory/D03-01.json
    task_memory_sha256: 8b03e7c7b81b8ad5ed811aa9ff9c015ce9d5f2f9c615daeec7525bc6f4255074
    sleep_order: /mnt/biella-extra/biella-runtime/codex-production/memory/owner-sleep-order.json
    sleep_order_sha256: 9b7f9fec7c9884b8339e1f0b805f4375d2da55dc853c2b992d981dcd92126345

  preserve:
    - all completed predecessor tasks and exact evidence
    - all verified D03-01 increments including terrain contact, aim/action/hit/defeat, vehicle/seat, reconstruction, SM5/SM6 package/fallback, handoff, automatic-PSO observation and cosmetic ground/package qualification
    - current uncommitted D03-01 PSO/loading experiment bytes and all failed/success evidence
    - Engine P4-06 as INCOMPLETE_DEFERRED
    - one-repository/one-controller/one-current-task architecture
    - unrelated source/configuration without mutation

  execution_directive:
    authority: Mahdi Taghdisi explicit sleep-and-fix instruction, 2026-09-07
    mode: SLEEP_CURRENT_D03_01_PRESERVE_STATE
    execution: Do not start production, invoke Codex, advance the queue, or mutate D03 until Mahdi explicitly requests wake/resume.
    resume: Start a fresh executor session from current task memory, task guide, exact current source and PSO/loading evidence; do not reuse the invalidated context-blackhole session.
    current_frontier: portable PSO seed plus native loading-display cold-start qualification
    task_guide: projects/biella-games/docs/task-guides/D03-01.md
    retrieval_index: /root/biella/artifacts/games/D03-01/D03-01-qualification-retrieval-index.json
    owner_support: /root/biella/artifacts/games/D03-01/D03-01-owner-support-guide-01.json
    preservation: Reuse every verified output; never restart, rollback, reset, clean, stash, or redo without material invalidation.
    cold_start_acceptance: Preserve existing no-crash/lineage/handoff controls and longest sampled static interval <1.0s with no unmeasured loading frames; no threshold relaxation.
    seeded_failure_precision: 68 seeded file-cache tasks completed before LoadMap; later FinishDestroy timeout remains the observed boundary and direct causal attribution is forbidden without isolation evidence.
    diagnostic_gc_timeout: gc.MaxTimeForFinishDestroyGC=40 is diagnostic-only when matched and read back; never ship or qualify the override.
    display_motion_precision: distinguish continuous widget paint/geometry progression, render submission, and actual presented/display motion.
    progression: After real D03-01 durable closure, advance to earliest unfinished canonical task; never skip or invent order.

  bounded_outage_fallback:
    strong_routes: Astra/Luna retain full-task synthesis and closure authority when available.
    bounded_routes: Spark then local Qwen may execute one small technical outcome per fresh executor packet when strong routes are unavailable from observed calls.
    packet: retrieval-first current task memory + compact projection + task guide + exact needed source/evidence; no broad accumulated conversation replay.
    sandbox: workspace-write rooted at the Biella Games Project; bounded routes cannot freely mutate controller/authority files.
    whole_task_complete: FORBIDDEN
    section_planning: FORBIDDEN
    task_order_or_status_mutation: FORBIDDEN
    git_commit_push_publish: FORBIDDEN_INSIDE_BOUNDED_PACKET
    quality_order: [correctness_and_evidence, continuity, speed, token_savings]
    no_progress_rule: If a bounded model changes no Project working bytes, do not call that same model on the same task/worktree/guide packet again; try another eligible bounded model once, otherwise wait without another model call for state/route change.
    useless_artifact_rule: Do not create planning/status/summary artifacts merely to show progress.
    acceptance_rule: A bounded increment may be verified, but D03 remains CONTINUE until the full task-specific acceptance contract is satisfied by appropriate evidence and strong-model/owner boundaries where required.

  ordered_queue:
    source: projects/biella-games/docs/PRODUCTION.md
    current: D03-01
    completed: 59
    total: 168
    selection_rule: EARLIEST_UNFINISHED_IN_CANONICAL_ORDER
    concurrency: ONE_AUTHORITATIVE_TASK_WITH_SAFE_RESOURCE_PARALLELISM

  observer_surfaces:
    public_live: READ_ONLY
    private_control: READ_ONLY
    opening_closing_reconnecting: MUST_NOT_SIGNAL_OR_INTERRUPT_ENGINE

  stop: Production is sleeping by explicit owner request. Wake/resume only on Mahdi's explicit instruction; otherwise preserve state without model calls, queue advancement, token use, or generated busywork.
```
