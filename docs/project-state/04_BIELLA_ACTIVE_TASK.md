# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v12

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
    observed_repository_head: e6c8f372fdd6eb5de00d8efe37d58cc37cd25e93
    observed_repository_tree: 8e85a31086e8f07ccd593627ee8041d6b888d223
    implementation_commit: e6c997b0097651b0265cf6b4663049bc2eb65b30
    implementation_tree: ef26e47bfb606bd3e7a8b41f5249adb57203eee2
    authoritative_persistent_task_session_id: null
    prior_invalidated_executor_session_id: 01a07931-fb65-7af1-830d-83afb2ee5d8d
    latest_bounded_fallback_session_id: 01a07a15-b528-7a43-afd7-e84ff3c1ccc9
    latest_attempt: 294
    model: null
    reasoning: null
    current_increment: PORTABLE_PSO_SEED_AND_LOADING_DISPLAY_COLD_START_QUALIFICATION
    task_memory: /mnt/biella-extra/biella-runtime/codex-production/task-memory/D03-01.json
    task_memory_sha256: e22c06478ef27dec78992aedf7840d087020b91b6563f6f00ae3eb8c1d667cae
    compact_projection_sha256: b5c8094071a353cc4efcfd68fed84292215adf412ca5078680f7d53ef41cfb8e
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
    mode: SLEEP_CURRENT_D03_01_PRESERVE_STATE
    execution: Do not start production, invoke Codex, advance the queue, or mutate D03 until Mahdi explicitly requests wake/resume.
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
    strong_routes: Astra/Luna retain full-task synthesis and closure authority when available.
    bounded_routes: Spark then local Qwen may execute one small technical outcome per fresh executor packet when strong routes are unavailable from observed calls.
    quality_order: [correctness_and_evidence, continuity, speed, token_savings]
    packet_contract: retrieval-first exact current task memory + compact projection + task guide + exact needed source/evidence; no broad accumulated conversation replay
    current_open_defect: Attempt 294 local Qwen failed to consume referenced task memory/guide and made no project-byte progress.
    current_defect_containment: no-progress ledger blocks another identical Qwen packet; do not spin or spend tokens on unchanged input.
    required_repair_before_relying_on_local_tool_work: make bounded packet sufficiently self-contained or otherwise prove local Codex tool access against exact files; preserve strong-route acceptance authority.
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

  stop: Production remains asleep by explicit owner request. Source-pack refresh does not wake production, change D03 evidence, or advance the queue.
```
