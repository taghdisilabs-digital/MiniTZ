# 03 - BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v11
state_class: VOLATILE
update_rule: replace_stale_values; preserve_valid_progress_capabilities_evidence
observed_date: 2026-09-07
observed_at_utc: 2026-09-07T20:21:09+00:00
observed_at_europe_amsterdam: 2026-09-07T22:21:09+02:00

authority:
  if_conflict: [CURRENT_EXECUTION_STATE, CURRENT_GITHUB_SOURCE, CURRENT_CANONICAL_DRIVE, VERIFIED_HISTORICAL_EVIDENCE, REFERENCE_OR_PLAN, INFERENCE]
  correction_rule: invalidate_only_conflicting_state; preserve_independently_valid_work
  source_pack_evolution: LOSSLESS_VALID_STATE

repository:
  repository: patrickminitz-web/biella-engine
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine
  observed_head_commit: ddc276fb7fc8e70a06813f45f19434fa9840c58c
  observed_head_tree: 543da142a139cad1c6aeb3e25a1bb2b7352e943d
  github_main_readback_commit: ddc276fb7fc8e70a06813f45f19434fa9840c58c
  implementation_commit: ddc276fb7fc8e70a06813f45f19434fa9840c58c
  implementation_tree: 543da142a139cad1c6aeb3e25a1bb2b7352e943d
  source_alignment_gate: VERIFIED_GITHUB_MAIN_SAFE_FAST_FORWARD_OR_FAIL_CLOSED
  customer_handoff_mode: FIRST_CUSTOMER_CHECKPOINT_SLEEP_LAST_CUSTOMER_AUTOMATIC_RESTORE
  customer_resume_target: LOCAL_BIELLA_PRODUCTION_OLLAMA_QWEN_ACTIVE_ENABLED
  customer_handoff_checkpoint: /mnt/biella-extra/biella-runtime/customer-handoff/active.json
  customer_handoff_checkpoint_sha256: b8cf3a67307b78a6e15372b1ff27f08d43c022edd0d754babb56fda41e31ef1b
  customer_handoff_running_customer_count: 2
  legacy_blanket_cooldown_reconciliation: ARMED_ON_NEXT_PRODUCTION_START
  production_runner_source: /root/biella/repos/biella-engine/ops/local-ai/biella_production_runner.py
  installer_sleep_preservation: VERIFIED_EXISTING_DISABLED_STATE_PRESERVED
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
  state: SLEEPING_CUSTOMER_RESOURCE_HELD
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
  latest_attempt: 294
  active_model: null
  active_reasoning: null
  current_increment: PORTABLE_PSO_SEED_AND_LOADING_DISPLAY_COLD_START_QUALIFICATION
  task_memory_status: CONTINUE
  runtime_json_status: WAITING_FOR_STRONG_MODEL_STALE_WHILE_SERVICE_ASLEEP
  no_progress_model: qwen3-coder-next:biella
  no_progress_packet_id: d8667b37c1e5713dd82876a90d5ea7edf4eefa9f874a182265833840d4c84d99
  bounded_fallback_open_defect: RECOVERED_SELF_CONTAINED_BOUNDED_PACKET_EMBEDS_TASK_MEMORY_GUIDE_AND_PROJECTION
  bounded_fallback_defect_effect: ATTEMPT_294_EMPTY_MEMORY_STATEMENT_INVALIDATED; FUTURE_BOUNDED_PACKETS_SELF_CONTAINED_AND_NO_PROGRESS_DEDUPLICATED
  sleep_order: /mnt/biella-extra/biella-runtime/codex-production/memory/owner-sleep-order.json
  sleep_order_sha256: 9b7f9fec7c9884b8339e1f0b805f4375d2da55dc853c2b992d981dcd92126345
  task_memory_sha256: 412bc1ddcf2d0223f11d3e1df4f74cf2c1e20e3ebcde32312e7b35fcaab49f53
  compact_projection_sha256: d6bad4fbffd1d68e8941c997bfccc02bac1463027f87f4c305b4303851d82178
  bounded_session_identity_guard: VERIFIED_BOUNDED_EXECUTOR_SESSION_NEVER_PERSISTS
  session_derivative_recovery_status: RECOVERED
  session_derivative_recovery_backup: /mnt/biella-extra/biella-runtime/codex-production/recovery/20260907T170250Z-bounded-session-derivative-repair

games:
  project_path: projects/biella-games
  production_source: projects/biella-games/docs/PRODUCTION.md
  current_section: post_d01
  current_task: D03-01
  production_completed_tasks: 59
  production_total_tasks: 168
  production_progress_percent: 35.1
  task_boundary: D03-01_SLEEPING_OWNER_REQUESTED
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
  sleep_rule: DO_NOT_EXECUTE_OR_ADVANCE_WHILE_ANY_EXTERNAL_CUSTOMER_RESOURCE_LEASE_IS_HELD; LAST_CUSTOMER_RELEASE_AUTOMATICALLY_RESTORES_BIELLA
  resume_rule: LAST_CUSTOMER_RELEASE_RESTORES_LOCAL_SERVICES_AND_STARTS_FRESH_STRONG_EXECUTOR_FROM_CURRENT_TASK_MEMORY_GUIDE_AND_EXACT_PSO_LOADING_FRONTIER
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
  local_qwen_service: INACTIVE_CUSTOMER_ISOLATION
  local_qwen_identity: qwen3-coder-next:biella
  qwen_reasoning_protocol: NONE_COMPATIBILITY_MODE_NORMAL_MODEL_INFERENCE_REMAINS
  external_project_sandbox_broker: VERIFIED_SEPARATE_HOST_RESOURCE_NOT_BIELLA_ENGINE
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
