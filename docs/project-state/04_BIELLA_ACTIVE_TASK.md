# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v12

task:
  id: D03-01
  project: Biella Games
  section: post_d01
  class: hard_creation
  title: Production rendering, animation, VFX, and audio quality
  status: RESUME_OWNER_REQUESTED
  runner: READY_TO_START

  authority:
    - Mahdi Taghdisi latest explicit instruction, 2026-09-07
    - current observed execution state
    - docs/project-state/03_BIELLA_CURRENT_STATE.md
    - projects/biella-games/docs/PRODUCTION.md

  continuity:
    completed_predecessor: D02-04
    production_source: projects/biella-games/docs/PRODUCTION.md
    observed_repository_head: 85cb956e3434ac363c2fbaa472a8f661c7eaf117
    observed_repository_tree: 655cce311debff38d93bf3a8a654d32d532d20ba
    implementation_commit: 85cb956e3434ac363c2fbaa472a8f661c7eaf117
    implementation_tree: 655cce311debff38d93bf3a8a654d32d532d20ba
    source_alignment_gate: VERIFIED_GITHUB_MAIN_PRE_EXECUTION_AND_POST_TURN_FAIL_CLOSED
    customer_handoff_mode: FIRST_CUSTOMER_CHECKPOINT_SLEEP_LAST_CUSTOMER_AUTOMATIC_RESTORE
    customer_resume_target: LOCAL_BIELLA_PRODUCTION_OLLAMA_QWEN_ACTIVE_ENABLED
    customer_handoff_checkpoint: null
    customer_handoff_checkpoint_sha256: null
    customer_handoff_running_customer_count: 0
    verified_external_broker_commit: cdb3c43071641e8e15979ad187b26517f5e6a9ab
    verified_external_broker_tree: 9826274a2518c48350e974e9cf34eb19bc4e820c
    external_broker_validation: 60_UNIT_PLUS_8_SUBTESTS_PLUS_9_HOST_ACCEPTANCE_PASS
    isolated_project_execution_bridge: docs/project-state/BIELLA_ISOLATED_PROJECT_EXECUTION_BRIDGE.yaml
    isolated_project_execution_bridge_sha256: b92b77ee6a4a7791217b0346225f8a893c1b7dad27c8f5c56d467621aac9d7be
    isolated_project_execution_bridge_drive_id: 1x35z0cZ-t3SM3Ma6mX5O4AMfFKnDcolv
    project_cell_execution_model: ISOLATED_PROJECT_CELL
    adopted_project_cells: [feiz-english-institute, feiz-english-institute-v4]
    project_cell_engine_database: /mnt/biella-extra/biella-runtime/project-cells/engine.sqlite3
    project_cell_engine_database_sha256: b0ea0710ddea4978907046d92d91c9b238b35a5ea3968dfa359f702d3793406b
    feiz_cell_checkpoint: chk_a26b612dabda492b9dcc704f7fa7a603
    feiz_cell_checkpoint_sha256: 0c359af4449ce7655a977bdfdb6c0ee895535e8daf07864bd1763c060d9162f8
    feiz_v4_cell_checkpoint: chk_c555f4e922484f86a175787da19550c0
    feiz_v4_cell_checkpoint_sha256: 8efc43f5e9a58ce8ae7c4d16b2979c1f2a6401e237a8e41670446ee016574f7c
    authoritative_persistent_task_session_id: null
    prior_invalidated_executor_session_id: 01a07931-fb65-7af1-830d-83afb2ee5d8d
    latest_bounded_fallback_session_id: 01a07a15-b528-7a43-afd7-e84ff3c1ccc9
    latest_attempt: 295
    model: gpt-reserve
    reasoning: max
    current_increment: PORTABLE_PSO_SEED_AND_LOADING_DISPLAY_COLD_START_QUALIFICATION
    task_memory: /mnt/biella-extra/biella-runtime/codex-production/task-memory/D03-01.json
    task_memory_sha256: 8fca27885e818c134a0815764b04a5a418a2c4c73a7ba2a90ff813c7935cb1fd
    compact_projection_sha256: 02f688e832e0a3cff879d1ab156f11977e75ac8a38223a5ec34cdff4a5af8012
    bounded_session_identity_guard: VERIFIED_BOUNDED_EXECUTOR_SESSION_NEVER_PERSISTS
    session_derivative_recovery_status: RECOVERED
    session_derivative_recovery_backup: /mnt/biella-extra/biella-runtime/codex-production/recovery/20260907T170250Z-bounded-session-derivative-repair
    superseded_sleep_order: /mnt/biella-extra/biella-runtime/codex-production/memory/owner-sleep-order.json
    superseded_sleep_order_sha256: 9b7f9fec7c9884b8339e1f0b805f4375d2da55dc853c2b992d981dcd92126345
    owner_resume_order: /mnt/biella-extra/biella-runtime/codex-production/memory/owner-resume-order.json
    owner_resume_order_sha256: 8af95d146bfbc191b062657f6be6058b82033e57053a5c0f98d4f6a7a09e5de9
    stale_owner_resume_session_id: 01a07de2-cfe7-7a52-a941-f0a0aa7f5bd5
    reserve_supported_reasoning: [low, medium, high, xhigh, max]
    reserve_ultra_supported: false

  preserve:
    - all completed predecessor tasks and exact evidence
    - all verified D03-01 increments including terrain contact, aim/action/hit/defeat, vehicle/seat, reconstruction, SM5/SM6 package/fallback, loading handoff, automatic-PSO observation and cosmetic ground/package qualification
    - current uncommitted D03-01 PSO/loading experiment bytes and all failed/success evidence
    - Engine P4-06 as INCOMPLETE_DEFERRED
    - one-repository/one-controller/one-current-task architecture
    - all registered useful capabilities and verified reusable methods unless materially invalidated
    - unrelated source/configuration without mutation

  execution_directive:
    mode: RUN_D03_01_OWNER_RESUMED_GPT_RESERVE_MAX
    execution: Start production now on GPT-Reserve max. The prior sleep order is superseded by Mahdi latest instruction; no customer resource lease is held. Continue only D03-01 and preserve all verified/uncommitted PSO-loading work.
    resume: Start a fresh strong session from current task memory plus task guide plus exact PSO/loading evidence. Do not reuse the stale attempt-295 session created from sleeping authority or the older invalidated context-blackhole session.
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
    role: REPLACEABLE_PROJECT_CELL_RUNTIME_RESOURCE_NOT_TASK_OR_ENGINE_AUTHORITY
    shared_capabilities_allowed: generic_compute_gpu_software_and_explicit_resource_proxy_methods
    prohibited_learning: [customer_brand, visual_guidance, copy, customer_rules, customer_source_bodies, customer_repository_identity]
    permitted_learning: SANITIZED_GENERIC_CODING_AND_ENGINEERING_METHODS_ONLY
    project_cell_execution_owner: BIELLA
    remote_assistance_provider: chatgpt_remote_REPLACEABLE_NON_CANONICAL

  stop: Owner resume is active. Customer cells are durably paused; production is authorized to run D03-01 on GPT-Reserve max until a new customer lease or newer owner instruction changes the state.
```
