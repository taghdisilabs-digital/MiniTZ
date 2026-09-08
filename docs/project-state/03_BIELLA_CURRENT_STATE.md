# 03 - BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v12
state_class: VOLATILE_CURRENT
update_rule: REALTIME_CANONICAL_UPGRADE
observed_at_utc: 2026-09-08T00:20:56.594725+00:00
observed_at_europe_amsterdam: 2026-09-08T02:20:56.594725+02:00

authority:
  if_conflict: [CURRENT_EXECUTION_STATE, CURRENT_GITHUB_SOURCE, CURRENT_CANONICAL_DRIVE, VERIFIED_EVIDENCE, INFERENCE]
  rule: replace_stale_current_fields_in_place; keep_required_proof_in_git_or_raw_evidence; no_duplicate_active_state

repository:
  repository: patrickminitz-web/biella-engine
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine
  git_identity_source: LIVE_GIT_READ_REQUIRED
  source_alignment_state: ALIGNED
  source_alignment_commit: b9c57a23b713289eee182691f43f99d4b93a66c7
  source_alignment_tree: 1bc7097eab70463c49515122b55292406b20631b
  worktree_state: DIRTY_ACTIVE_TASK_ONLY
  tracked_dirty_count: 9
  untracked_dirty_count: 645
  dirty_path_count: 654
  dirty_scope: projects/biella-games/D03-01_ONLY
  preservation_rule: preserve_verified_and_current_D03_work; no_reset_clean_stash_or_rollback_without_material_invalidation

active_execution:
  id: D03-01
  project: Biella Games
  section: post_d01
  state: RUNNING
  controller: biella-codex
  controller_service_state: ACTIVE
  runner_process_state: RUNNING
  runner_pid: 2875373
  codex_child_pid: 2946158
  codex_child_process_state: RUNNING
  authoritative_persistent_task_session_id: 01a07de9-3d4f-79d3-bfe0-80bd52a21807
  latest_attempt: 299
  active_model: gpt-reserve
  active_reasoning: max
  runtime_json_status: RUNNING
  heartbeat_at: 2026-09-08T00:20:43.982936+00:00
  current_increment: STABLE_PSO_BUNDLE_COOK_AND_LOADING_DISPLAY_COLD_START_QUALIFICATION
  current_operation: "Continuing the same native cook to completion before package/runtime validation."
  current_result: PENDING_NATIVE_COOK_COMPLETION
  task_memory: /mnt/biella-extra/biella-runtime/codex-production/task-memory/D03-01.json
  task_memory_sha256: e6f178707cccaa1873108532cd1399ac41af1578fec34ba8cd5d3983e5321429
  compact_projection: /mnt/biella-extra/biella-runtime/codex-production/memory/current-task.json
  compact_projection_sha256: c71f655c8766c22400507d6e326d88792d1e3affbae279c262eafdd3500030b1
  bounded_session_identity_guard: VERIFIED
  forced_strong_route: gpt-reserve
  forced_strong_reasoning: max

customer_execution:
  running_customer_count: 0
  customer_handoff_checkpoint: null
  project_cell_execution_model: ISOLATED_PROJECT_CELL
  native_project_count: 2
  current_state: PAUSED_FOR_BIELLA_PRODUCTION

website:
  execution_model: NO_PERMANENT_WEBSITE_AGENT
  live_projection: DETERMINISTIC_READ_ONLY
  public_snapshot: https://biellagames.dev/live-api/snapshot
  public_events: https://biellagames.dev/live-api/events
  static_redeploy_trigger: WEBSITE_SOURCE_CHANGES_ONLY

games:
  project_path: projects/biella-games
  production_source: projects/biella-games/docs/PRODUCTION.md
  current_section: post_d01
  current_task: D03-01
  production_completed_tasks: 59
  production_total_tasks: 168
  production_progress_percent: 35.1
  current_frontier: stable_PSO_bundle_plus_native_loading_display_cold_start
  cold_start_acceptance: no_native_fatal_or_crash; exact_lineage_and_handoff; no_unmeasured_loading_frames; longest_static_interval_lt_1_0s
  verified_reuse_boundary: [terrain_contact, aim_action_hit_defeat, vehicle_seat, reconstruction, sm5_sm6_package_fallback, loading_handoff, automatic_pso_observation, cosmetic_ground_package]

resources:
  local_qwen_service: ACTIVE_NON_AUTHORITATIVE_FALLBACK
  local_qwen_identity: qwen3-coder-next:biella
  external_project_sandbox_broker: ACTIVE_REPLACEABLE_PROJECT_CELL_RESOURCE

engine_numbered_execution:
  P4_01_through_P4_05: COMPLETE_REUSE_REQUIRED
  P4-06: INCOMPLETE_DEFERRED
  FOUNDATION_COMPLETE: false
```
