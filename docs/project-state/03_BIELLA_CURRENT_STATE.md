# 03 - BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v11
state_class: VOLATILE
update_rule: replace_stale_values; preserve_valid_progress_capabilities_evidence
observed_date: 2026-09-07
observed_at_utc: 2026-09-07T22:05:35+00:00
observed_at_europe_amsterdam: 2026-09-08T00:05:35+02:00

authority:
  if_conflict: [CURRENT_EXECUTION_STATE, CURRENT_GITHUB_SOURCE, CURRENT_CANONICAL_DRIVE, VERIFIED_HISTORICAL_EVIDENCE, REFERENCE_OR_PLAN, INFERENCE]
  correction_rule: invalidate_only_conflicting_state; preserve_independently_valid_work
  source_pack_evolution: LOSSLESS_VALID_STATE

repository:
  repository: patrickminitz-web/biella-engine
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine
  observed_head_commit: 85cb956e3434ac363c2fbaa472a8f661c7eaf117
  observed_head_tree: 655cce311debff38d93bf3a8a654d32d532d20ba
  github_main_readback_commit: 85cb956e3434ac363c2fbaa472a8f661c7eaf117
  implementation_commit: 85cb956e3434ac363c2fbaa472a8f661c7eaf117
  implementation_tree: 655cce311debff38d93bf3a8a654d32d532d20ba
  source_alignment_gate: VERIFIED_GITHUB_MAIN_SAFE_FAST_FORWARD_OR_FAIL_CLOSED
  customer_handoff_mode: FIRST_CUSTOMER_CHECKPOINT_SLEEP_LAST_CUSTOMER_AUTOMATIC_RESTORE
  customer_resume_target: LOCAL_BIELLA_PRODUCTION_OLLAMA_QWEN_ACTIVE_ENABLED
  customer_handoff_checkpoint: null
  customer_handoff_checkpoint_sha256: null
  customer_handoff_running_customer_count: 0
  legacy_blanket_cooldown_reconciliation: ARMED_ON_NEXT_PRODUCTION_START
  production_runner_source: /root/biella/repos/biella-engine/ops/local-ai/biella_production_runner.py
  installer_sleep_preservation: VERIFIED_EXISTING_DISABLED_STATE_PRESERVED
  isolated_project_execution_bridge: docs/project-state/BIELLA_ISOLATED_PROJECT_EXECUTION_BRIDGE.yaml
  isolated_project_execution_bridge_sha256: b92b77ee6a4a7791217b0346225f8a893c1b7dad27c8f5c56d467621aac9d7be
  isolated_project_execution_bridge_drive_id: 1x35z0cZ-t3SM3Ma6mX5O4AMfFKnDcolv
  project_cell_execution_model: ISOLATED_PROJECT_CELL
  project_cell_runtime_command: /usr/local/bin/biella-project-cell
  worktree_state: DIRTY_ACTIVE_TASK_ONLY
  tracked_dirty_count: 1
  untracked_dirty_count: 75
  dirty_path_count: 76
  dirty_scope: projects/biella-games/D03-01_PSO_LOADING_ONLY
  preservation_rule: do_not_reset_clean_stash_overwrite_or_absorb_unrelated_work

active_execution:
  id: D03-01
  project: Biella Games
  section: post_d01
  state: RESUME_OWNER_REQUESTED
  controller: biella-codex
  controller_service_state: INACTIVE
  runner_process_state: STOPPED
  runner_pid: null
  codex_child_pid: null
  codex_child_process_state: STOPPED
  authoritative_persistent_task_session_id: null
  prior_invalidated_executor_session_id: 01a07931-fb65-7af1-830d-83afb2ee5d8d
  latest_bounded_fallback_session_id: 01a07a15-b528-7a43-afd7-e84ff3c1ccc9
  session_rotation_reason: CONTEXT_BLACKHOLE_AND_STALE_FRONTIER
  latest_attempt: 295
  active_model: null
  active_reasoning: null
  current_increment: PORTABLE_PSO_SEED_AND_LOADING_DISPLAY_COLD_START_QUALIFICATION
  task_memory_status: CONTINUE
  runtime_json_status: READY_FOR_FRESH_GPT_RESERVE_MAX_SESSION
  no_progress_model: qwen3-coder-next:biella
  no_progress_packet_id: d8667b37c1e5713dd82876a90d5ea7edf4eefa9f874a182265833840d4c84d99
  bounded_fallback_open_defect: RECOVERED_SELF_CONTAINED_BOUNDED_PACKET_EMBEDS_TASK_MEMORY_GUIDE_AND_PROJECTION
  bounded_fallback_defect_effect: ATTEMPT_294_EMPTY_MEMORY_STATEMENT_INVALIDATED; FUTURE_BOUNDED_PACKETS_SELF_CONTAINED_AND_NO_PROGRESS_DEDUPLICATED
  superseded_sleep_order: /mnt/biella-extra/biella-runtime/codex-production/memory/owner-sleep-order.json
  superseded_sleep_order_sha256: 9b7f9fec7c9884b8339e1f0b805f4375d2da55dc853c2b992d981dcd92126345
  owner_resume_order: /mnt/biella-extra/biella-runtime/codex-production/memory/owner-resume-order.json
  owner_resume_order_sha256: 8af95d146bfbc191b062657f6be6058b82033e57053a5c0f98d4f6a7a09e5de9
  stale_owner_resume_session_id: 01a07de2-cfe7-7a52-a941-f0a0aa7f5bd5
  forced_strong_route: gpt-reserve
  forced_strong_reasoning: max
  task_memory_sha256: 8fca27885e818c134a0815764b04a5a418a2c4c73a7ba2a90ff813c7935cb1fd
  compact_projection_sha256: 02f688e832e0a3cff879d1ab156f11977e75ac8a38223a5ec34cdff4a5af8012
  bounded_session_identity_guard: VERIFIED_BOUNDED_EXECUTOR_SESSION_NEVER_PERSISTS
  session_derivative_recovery_status: RECOVERED
  session_derivative_recovery_backup: /mnt/biella-extra/biella-runtime/codex-production/recovery/20260907T170250Z-bounded-session-derivative-repair


project_cells:
  engine_database: /mnt/biella-extra/biella-runtime/project-cells/engine.sqlite3
  engine_database_sha256: b0ea0710ddea4978907046d92d91c9b238b35a5ea3968dfa359f702d3793406b
  native_project_count: 2
  execution_owner: BIELLA
  runtime_provider: PROJECT_SANDBOX_BROKER_REPLACEABLE_RESOURCE
  remote_assistance_provider: chatgpt_remote
  remote_assistance_role: REPLACEABLE_DELEGATED_SUBTASK_PROVIDER_NON_CANONICAL
  cross_project_state_leakage: FORBIDDEN
  feiz-english-institute:
    state: PAUSED_OWNER_PREEMPTED_FOR_BIELLA_RESERVE
    manifest: /mnt/biella-extra/biella-runtime/project-cells/feiz-english-institute/manifest.json
    manifest_sha256: e541476e973bdb7d2ce223aa5f943ef9f22e92f1391a9daa931e7035518699ac
    engine_project_ref: prj_b66f0432825e403c92395afacf9f8667
    engine_task_ref: task://prj_b66f0432825e403c92395afacf9f8667/tsk_fe78fe6054954ceb92d3b12ba55b75bb/1
    engine_run_ref: run://prj_b66f0432825e403c92395afacf9f8667/run_891c7420cc4e486db4684d4b298cf40b
    task_id: UNVERIFIED
    objective: UNVERIFIED
    acceptance: UNVERIFIED
    checkpoint_id: chk_a26b612dabda492b9dcc704f7fa7a603
    checkpoint_sha256: 0c359af4449ce7655a977bdfdb6c0ee895535e8daf07864bd1763c060d9162f8
    repository_head: 58e153b7418a274259bca0e31fef4f1c84270890
    task_envelope: /mnt/biella-extra/biella-runtime/project-cells/feiz-english-institute/task-envelope.json
    task_envelope_sha256: 8929755dc92f0053a2c9c3e435ff52d43ad46bc5fa598494a0c609e0b4bcf6aa
    run_projection_sha256: 88915cba0cd2be2a5d145ce636ca70ef28f945f978800ee708ef23553f87f9d1
    remote_requests: 0
    remote_responses: 0
  feiz-english-institute-v4:
    state: PAUSED_OWNER_PREEMPTED_FOR_BIELLA_RESERVE
    manifest: /mnt/biella-extra/biella-runtime/project-cells/feiz-english-institute-v4/manifest.json
    manifest_sha256: ac86083819dec709b1031160b9b24f6ae8f1bced27f1192c347a5e1a1b76cbfc
    engine_project_ref: prj_4d45763d6d3641baa3d04ac1368300c9
    engine_task_ref: task://prj_4d45763d6d3641baa3d04ac1368300c9/tsk_607ebbdcbfcc4e47b390eb5c14191225/1
    engine_run_ref: run://prj_4d45763d6d3641baa3d04ac1368300c9/run_4e7c0a8c5d544d538f3c23a78c4dddd8
    task_id: UNVERIFIED
    objective: UNVERIFIED
    acceptance: UNVERIFIED
    checkpoint_id: chk_c555f4e922484f86a175787da19550c0
    checkpoint_sha256: 8efc43f5e9a58ce8ae7c4d16b2979c1f2a6401e237a8e41670446ee016574f7c
    repository_head: 8080bceed5ca815a32b473ba50f88d2eafa5e083
    task_envelope: /mnt/biella-extra/biella-runtime/project-cells/feiz-english-institute-v4/task-envelope.json
    task_envelope_sha256: 1017b648343674c350f8ff3b7ad640d9e62c0b75d2b3b1f74269230e61ed547e
    run_projection_sha256: 8e400c4ec146ec32e8ac3c24be67c966e6254a102b47153dfe65a3da024b395d
    remote_requests: 0
    remote_responses: 0

games:
  project_path: projects/biella-games
  production_source: projects/biella-games/docs/PRODUCTION.md
  current_section: post_d01
  current_task: D03-01
  production_completed_tasks: 59
  production_total_tasks: 168
  production_progress_percent: 35.1
  task_boundary: D03-01_RESUME_OWNER_REQUESTED_GPT_RESERVE_MAX
  current_frontier: portable_PSO_seed_plus_native_loading_display_cold_start
  qualification_retrieval_index: /root/biella/artifacts/games/D03-01/D03-01-qualification-retrieval-index.json
  qualification_retrieval_index_sha256: 158c8ea507739d6ad785355c243f46e0478b3f5fc74cfd1c8e9bb8eb27a27efe
  owner_support_guide: /root/biella/artifacts/games/D03-01/D03-01-owner-support-guide-01.json
  owner_support_guide_sha256: 8f8f86719ec6102320f34768032f9294c070cd09b9437ee605346cd2e6547e19
  unseeded_validation_sha256: ed1e4c9cfa92afae2fc754834dc36b60ed81f22fb8b01ee8f696f81819e0cba9
  seeded_validation_sha256: 1d1889667f0569ce19e951d5e66aeef1b3729da66363f8b4f3967fb7f8381f9d
  cold_start_motion_acceptance: longest_static_interval_lt_1_0s_and_no_unmeasured_loading_frames
  verified_reuse_boundary: [terrain_contact, aim_action_hit_defeat, vehicle_seat, reconstruction, sm5_sm6_package_fallback, loading_handoff, automatic_pso_observation, cosmetic_ground_package]

continuation_policy:
  queue_mode: CANONICAL_ORDER_CONTINUOUS
  active_task_count: ONE
  selection_rule: EARLIEST_UNFINISHED_IN_CANONICAL_ORDER
  advance_after: CURRENT_TASK_DURABLE_CLOSURE
  completed_work_reuse: REQUIRED
  no_rollback_or_redo_without_invalidation: true
  sleep_rule: NO_CUSTOMER_RESOURCE_LEASE_HELD; OWNER_RESUME_SUPERSEDES_PRIOR_SLEEP_ORDER
  resume_rule: START_FRESH_GPT_RESERVE_MAX_EXECUTOR_FROM_CURRENT_TASK_MEMORY_GUIDE_AND_EXACT_PSO_LOADING_FRONTIER
  strong_route_authority: ASTRA_TERRA_SOL_LUNA_OR_CATALOG_DISCOVERED_GPT_RESERVE_FULL_TASK_SYNTHESIS_AND_CLOSURE
  bounded_outage_fallback: SPARK_THEN_QWEN_ONE_SMALL_TECHNICAL_OUTCOME_PER_FRESH_PACKET
  bounded_whole_task_completion: FORBIDDEN
  bounded_section_planning: FORBIDDEN
  bounded_same_packet_no_progress_recall: FORBIDDEN
  bounded_quality_order: [correctness_and_evidence, continuity, speed, token_savings]
  quota_probe_forbidden: true

resources:
  provider_registry: ops/workstation/provider-registry.json
  provider_registry_sha256: c5c2f91f645b553b0164ade4ebfc3866649bb97e7ad82dbdbd7a9bc95781cb5d
  local_qwen_service: ACTIVE_AVAILABLE_AS_NON_AUTHORITATIVE_RESOURCE
  local_qwen_identity: qwen3-coder-next:biella
  qwen_reasoning_protocol: NONE_COMPATIBILITY_MODE_NORMAL_MODEL_INFERENCE_REMAINS
  external_project_sandbox_broker: VERIFIED_REPLACEABLE_PROJECT_CELL_RUNTIME_RESOURCE
  external_project_sandbox_repo: /root/project-sandbox-broker
  external_project_sandbox_verified_commit: cdb3c43071641e8e15979ad187b26517f5e6a9ab
  external_project_sandbox_verified_tree: 9826274a2518c48350e974e9cf34eb19bc4e820c
  external_project_sandbox_service: ACTIVE_LOOPBACK_127_0_0_1_8840
  external_project_sandbox_validation: 60_UNIT_PLUS_8_SUBTESTS_PLUS_9_HOST_ACCEPTANCE_PASS
  external_project_learning_firewall: GENERIC_CODING_ENGINEERING_LESSONS_ONLY_NO_BRAND_VISUAL_COPY_RULES_OR_CUSTOMER_SOURCE

control:
  public_live_url: https://biellagames.dev/live/
  public_live_snapshot_url: https://biellagames.dev/live-api/snapshot
  public_live_mode: READ_ONLY_OBSERVER
  authenticated_control_write_routes: DISABLED_405_CONTROL_READ_ONLY

engine_numbered_execution:
  P4_01_through_P4_05: COMPLETE_REUSE_REQUIRED
  P4-06: INCOMPLETE_DEFERRED
  FOUNDATION_COMPLETE: false

workspace:
  active_biella_repo_roots: [/root/biella/repos/biella-engine]
  active_dirty_scope: D03-01_ONLY
  external_project_roots_are_not_biella_roots: true
  historical_or_recovery_material_activation: FORBIDDEN_UNLESS_TASK_AUTHORIZES
```
