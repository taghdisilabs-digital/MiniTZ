# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v12

task:
  id: D03-01
  project: Biella Games
  section: post_d01
  class: hard_creation
  title: Production rendering, animation, VFX, and audio quality
  status: SLEEPING_CUSTOMER_RESOURCE_HELD
  runner: SLEEPING

  authority:
    - Mahdi Taghdisi latest explicit instruction, 2026-09-07
    - current observed execution state
    - docs/project-state/03_BIELLA_CURRENT_STATE.md
    - projects/biella-games/docs/PRODUCTION.md

  continuity:
    completed_predecessor: D02-04
    production_source: projects/biella-games/docs/PRODUCTION.md
    observed_repository_head: ddc276fb7fc8e70a06813f45f19434fa9840c58c
    observed_repository_tree: 543da142a139cad1c6aeb3e25a1bb2b7352e943d
    implementation_commit: ddc276fb7fc8e70a06813f45f19434fa9840c58c
    implementation_tree: 543da142a139cad1c6aeb3e25a1bb2b7352e943d
    source_alignment_gate: VERIFIED_GITHUB_MAIN_PRE_EXECUTION_AND_POST_TURN_FAIL_CLOSED
    customer_handoff_mode: FIRST_CUSTOMER_CHECKPOINT_SLEEP_LAST_CUSTOMER_AUTOMATIC_RESTORE
    customer_resume_target: LOCAL_BIELLA_PRODUCTION_OLLAMA_QWEN_ACTIVE_ENABLED
    customer_handoff_checkpoint: /mnt/biella-extra/biella-runtime/customer-handoff/active.json
    customer_handoff_checkpoint_sha256: b8cf3a67307b78a6e15372b1ff27f08d43c022edd0d754babb56fda41e31ef1b
    customer_handoff_running_customer_count: 2
    verified_external_broker_commit: cdb3c43071641e8e15979ad187b26517f5e6a9ab
    verified_external_broker_tree: 9826274a2518c48350e974e9cf34eb19bc4e820c
    external_broker_validation: 60_UNIT_PLUS_8_SUBTESTS_PLUS_9_HOST_ACCEPTANCE_PASS
    authoritative_persistent_task_session_id: null
    prior_invalidated_executor_session_id: 01a07931-fb65-7af1-830d-83afb2ee5d8d
    latest_bounded_fallback_session_id: 01a07a15-b528-7a43-afd7-e84ff3c1ccc9
    latest_attempt: 294
    model: null
    reasoning: null
    current_increment: PORTABLE_PSO_SEED_AND_LOADING_DISPLAY_COLD_START_QUALIFICATION
    task_memory: /mnt/biella-extra/biella-runtime/codex-production/task-memory/D03-01.json
    task_memory_sha256: 412bc1ddcf2d0223f11d3e1df4f74cf2c1e20e3ebcde32312e7b35fcaab49f53
    compact_projection_sha256: d6bad4fbffd1d68e8941c997bfccc02bac1463027f87f4c305b4303851d82178
    bounded_session_identity_guard: VERIFIED_BOUNDED_EXECUTOR_SESSION_NEVER_PERSISTS
    session_derivative_recovery_status: RECOVERED
    session_derivative_recovery_backup: /mnt/biella-extra/biella-runtime/codex-production/recovery/20260907T170250Z-bounded-session-derivative-repair
    sleep_order: /mnt/biella-extra/biella-runtime/codex-production/memory/owner-sleep-order.json
    sleep_order_sha256: 9b7f9fec7c9884b8339e1f0b805f4375d2da55dc853c2b992d981dcd92126345

  preserve:
    - all completed predecessor tasks and exact evidence
    - all verified D03-01 increments including terrain contact, aim/action/hit/defeat, vehicle/seat, reconstruction, SM5/SM6 package/fallback, loading handoff, automatic-PSO observation and cosmetic ground/package qualification
    - current uncommitted D03-01 PSO/loading experiment bytes and all failed/success evidence
    - Engine P4-06 as INCOMPLETE_DEFERRED
    - one-repository/one-controller/one-current-task architecture
    - all registered useful capabilities and verified reusable methods unless materially invalidated
    - unrelated source/configuration without mutation

  execution_directive:
    mode: SLEEP_D03_01_WHILE_EXTERNAL_CUSTOMER_RESOURCE_LEASE_HELD
    execution: Do not start production, invoke Codex, advance the queue, or mutate D03 while any external customer resource lease is held. The last customer release automatically restores local Biella services and resumes this exact task under Mahdi latest instruction.
    resume: Start from current task memory plus task guide plus exact PSO/loading evidence. Do not reuse the invalidated context-blackhole session and do not trust the attempt-294 local-Qwen statement that task memory/projection were empty; direct file read proves both files exist and are non-empty.
    current_frontier: portable PSO seed plus native loading-display cold-start qualification
    task_guide: projects/biella-games/docs/task-guides/D03-01.md
    retrieval_index: /root/biella/artifacts/games/D03-01/D03-01-qualification-retrieval-index.json
    retrieval_index_sha256: 158c8ea507739d6ad785355c243f46e0478b3f5fc74cfd1c8e9bb8eb27a27efe
    owner_support: /root/biella/artifacts/games/D03-01/D03-01-owner-support-guide-01.json
    owner_support_sha256: 8f8f86719ec6102320f34768032f9294c070cd09b9437ee605346cd2e6547e19
    preservation: Reuse every verified output; never restart, rollback, reset, clean, stash, or redo without material invalidation.
    cold_start_acceptance: Preserve no-crash/lineage/handoff controls and longest sampled static interval <1.0s with no unmeasured loading frames; no threshold relaxation.
    seeded_failure_precision: 68 seeded file-cache tasks completed before LoadMap; later FinishDestroy timeout remains the observed boundary and direct causal attribution is forbidden without isolation evidence.
    diagnostic_gc_timeout: gc.MaxTimeForFinishDestroyGC=40 is diagnostic-only when matched and read back; never ship or qualify the override.
    display_motion_precision: distinguish continuous widget paint/geometry progression, render submission, and actual presented/display motion.
    remaining_after_current_frontier: [world_horizon_production_art, broader_vfx_audio_coverage, fine_native_temporal_performance_evidence, final_owner_visual_acceptance]
    progression: After real D03-01 durable closure, advance to earliest unfinished canonical task; never skip or invent order.

  bounded_outage_fallback:
    strong_routes: Astra/Terra/Sol/Luna and catalog-discovered gpt-reserve retain full-task synthesis and closure authority when available.
    bounded_routes: Spark then local Qwen may execute one small technical outcome per fresh executor packet when strong routes are unavailable from observed calls.
    quality_order: [correctness_and_evidence, continuity, speed, token_savings]
    packet_contract: SELF_CONTAINED retrieval-first embedded current task memory + task guide + compact projection with exact needed source/evidence references; no broad accumulated conversation replay
    current_open_defect: RECOVERED. Attempt 294 empty-memory/tool-access statement remains historical failed evidence only; current bounded packets embed task memory, task guide, and compact projection content.
    current_defect_containment: self-contained bounded packet plus no-progress ledger; unchanged bounded packets are deduplicated and cannot replace persistent strong-session identity.
    required_repair_before_relying_on_local_tool_work: COMPLETE_SELF_CONTAINED_PACKET_VERIFIED_BY_TEST; local bounded work remains non-authoritative and strong-route acceptance authority is preserved.
    whole_task_complete: FORBIDDEN
    section_planning: FORBIDDEN
    task_order_or_status_mutation: FORBIDDEN
    git_commit_push_publish: FORBIDDEN_INSIDE_BOUNDED_PACKET
    useless_artifact_rule: Do not create planning/status/summary artifacts merely to show progress.
    acceptance_rule: A bounded increment may be verified, but D03 remains CONTINUE until the full task-specific acceptance contract is satisfied.

  ordered_queue:
    source: projects/biella-games/docs/PRODUCTION.md
    current: D03-01
    completed: 59
    total: 168
    selection_rule: EARLIEST_UNFINISHED_IN_CANONICAL_ORDER
    concurrency: ONE_AUTHORITATIVE_TASK_WITH_SAFE_RESOURCE_PARALLELISM

  external_project_isolation:
    verified_neutral_broker: /root/project-sandbox-broker
    role: SEPARATE_HOST_RESOURCE_NOT_BIELLA_PROJECT_OR_ENGINE_AUTHORITY
    shared_capabilities_allowed: generic_compute_gpu_software_and_explicit_resource_proxy_methods
    prohibited_learning: [customer_brand, visual_guidance, copy, customer_rules, customer_source_bodies, customer_repository_identity]
    permitted_learning: SANITIZED_GENERIC_CODING_AND_ENGINEERING_METHODS_ONLY

  stop: Production remains asleep only while external customer resource use is active. Last-customer release automatically restores local Biella services and resumes D03-01 from preserved task memory/evidence; source-pack refresh alone never changes task progress.
```
