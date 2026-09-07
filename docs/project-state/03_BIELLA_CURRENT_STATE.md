# 03 - BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v10
state_class: VOLATILE
update_rule: replace_stale_values; do_not_append_history
observed_date: 2026-09-07
observed_at_utc: 2026-09-07T02:41:27.192607+00:00

authority:
  if_conflict: [CURRENT_EXECUTION_STATE, CURRENT_GITHUB_SOURCE, CURRENT_CANONICAL_DRIVE, VERIFIED_HISTORICAL_EVIDENCE, REFERENCE_OR_PLAN, INFERENCE]
  correction_rule: invalidate_only_conflicting_state; preserve_independently_valid_work

repository:
  repository: patrickminitz-web/biella-engine
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine
  structure: ONE_REPOSITORY_MONOREPO
  implementation_commit: e6c997b0097651b0265cf6b4663049bc2eb65b30
  implementation_tree: ef26e47bfb606bd3e7a8b41f5249adb57203eee2
  github_readback: EXACT_IMPLEMENTATION_MAIN
  origin_main_implementation_commit: e6c997b0097651b0265cf6b4663049bc2eb65b30
  local_ahead_implementation_commit: 0
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
  state: SLEEPING_OWNER_REQUESTED
  controller: biella-codex
  controller_service_state: INACTIVE
  runner_process_state: STOPPED
  runner_pid: null
  codex_child_pid: null
  codex_child_process_state: STOPPED
  runtime_telemetry_status: SLEEPING_OWNER_REQUESTED
  task_session_id: null
  prior_invalidated_executor_session_id: 01a07931-fb65-7af1-830d-83afb2ee5d8d
  executor_session_rotation_reason: CONTEXT_BLACKHOLE_AND_STALE_FRONTIER
  attempt: 293
  active_model: null
  active_reasoning: null
  heartbeat_at: 2026-09-07T02:11:54.781114+00:00
  current_increment: PORTABLE_PSO_SEED_AND_LOADING_DISPLAY_COLD_START_QUALIFICATION
  task_memory_status: CONTINUE
  sleep_order: /mnt/biella-extra/biella-runtime/codex-production/memory/owner-sleep-order.json
  sleep_order_sha256: 9b7f9fec7c9884b8339e1f0b805f4375d2da55dc853c2b992d981dcd92126345
  task_memory_sha256: 8b03e7c7b81b8ad5ed811aa9ff9c015ce9d5f2f9c615daeec7525bc6f4255074
  compact_projection_sha256: 14ad53fefdc20e0aee47b07aa5a1c2da22eaca3f358c891135c6b50402be44aa

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

continuation_policy:
  queue_mode: CANONICAL_ORDER_CONTINUOUS
  active_task_count: ONE
  selection_rule: EARLIEST_UNFINISHED_IN_CANONICAL_ORDER
  advance_after: CURRENT_TASK_DURABLE_CLOSURE
  stop_between_tasks: false
  completed_work_reuse: REQUIRED
  no_rollback_or_redo_without_invalidation: true
  sleep_rule: DO_NOT_EXECUTE_OR_ADVANCE_UNTIL_MAHDI_EXPLICIT_WAKE_RESUME
  resume_rule: START_FRESH_EXECUTOR_FROM_CURRENT_TASK_MEMORY_AND_EXACT_PSO_LOADING_FRONTIER
  strong_route_authority: ASTRA_OR_LUNA_FULL_TASK_SYNTHESIS_AND_CLOSURE_WHEN_AVAILABLE
  bounded_outage_fallback: SPARK_THEN_QWEN_ONE_SMALL_TECHNICAL_OUTCOME_PER_FRESH_PACKET
  bounded_whole_task_completion: FORBIDDEN
  bounded_section_planning: FORBIDDEN
  bounded_workspace: PROJECT_WORKSPACE_WRITE_SANDBOX
  bounded_same_packet_no_progress_recall: FORBIDDEN
  bounded_quality_order: [correctness_and_evidence, continuity, speed, token_savings]
  quota_probe_forbidden: true

resources:
  dispatcher: /usr/local/bin/biella resource
  local_qwen: AVAILABLE_ON_DEMAND_BOUNDED_FALLBACK
  qwen_reasoning_protocol: NONE_COMPATIBILITY_MODE_NORMAL_MODEL_INFERENCE_REMAINS
  qwen_context_blackhole_old_session: INVALIDATED
  eager_local_assist_before_every_codex_turn: DISABLED_NONBLOCKING
  quota_probe_forbidden: true

control:
  public_live_url: https://biellagames.dev/live/
  public_live_snapshot_url: https://biellagames.dev/live-api/snapshot
  public_live_mode: READ_ONLY_OBSERVER
  website_control_engine_reaction: FORBIDDEN
  authenticated_control_write_routes: DISABLED_405_CONTROL_READ_ONLY

engine_numbered_execution:
  P4_01_through_P4_05: COMPLETE_REUSE_REQUIRED
  P4-06: INCOMPLETE_DEFERRED
  FOUNDATION_COMPLETE: false

workspace:
  active_repo_roots: [/root/biella/repos/biella-engine]
  active_dirty_scope: D03-01_ONLY
  historical_or_recovery_material_activation: FORBIDDEN_UNLESS_TASK_AUTHORIZES
```
