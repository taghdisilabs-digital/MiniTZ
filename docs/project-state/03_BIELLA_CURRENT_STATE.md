# 03 - BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v10
state_class: VOLATILE
update_rule: replace_stale_values; do_not_append_history
observed_date: 2026-09-06
observed_at_utc: 2026-09-06T09:10:55.915110+00:00

authority:
  if_conflict: [CURRENT_EXECUTION_STATE, CURRENT_GITHUB_SOURCE, CURRENT_CANONICAL_DRIVE, VERIFIED_HISTORICAL_EVIDENCE, REFERENCE_OR_PLAN, INFERENCE]
  correction_rule: invalidate_only_conflicting_state; preserve_independently_valid_work

repository:
  repository: patrickminitz-web/biella-engine
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine
  structure: ONE_REPOSITORY_MONOREPO
  implementation_commit: b340cdd2c2774f9c904fb5041e95a0245a25c389
  implementation_tree: 4dc1820ae63f1d9637150b279504be364d00643d
  github_readback: EXACT_MAIN
  origin_main_commit: b340cdd2c2774f9c904fb5041e95a0245a25c389
  origin_main_tree: 4dc1820ae63f1d9637150b279504be364d00643d
  local_ahead_origin_main: 0
  worktree_state: DIRTY_ACTIVE_TASK_ONLY
  tracked_dirty_count: 3
  untracked_dirty_count: 8
  dirty_scope: projects/biella-games/D03-01
  preservation_rule: do_not_reset_clean_stash_overwrite_or_absorb_unrelated_work

active_execution:
  id: D03-01
  project: Biella Games
  section: post_d01
  state: RUNNING
  controller: biella-codex
  runner_process_state: RUNNING
  runner_pid: 2126038
  codex_child_pid: 2228063
  codex_child_process_state: RUNNING
  runtime_telemetry_status: RUNNING
  task_session_id: 01a07480-2c40-7d03-b649-d3f72807cc3e
  attempt: 42
  active_model: gpt-6-astra
  active_reasoning: ultra
  heartbeat_at: 2026-09-06T09:06:22.111621+00:00
  public_live_mode: READ_ONLY_OBSERVER
  current_increment: FOOT_CONTACT_CORRECTION_IN_PROGRESS
  prior_verified_audio_increment_commit: 1898b568bf6c6dceae9dcf6aa66ef7a45a6f6e1d
  prior_verified_audio_increment_tree: 02f4230c4b61b2b1027156ffdd34fb03d3468aba
  rollback_or_redo_without_invalidation: FORBIDDEN

games:
  project_path: projects/biella-games
  production_source: projects/biella-games/docs/PRODUCTION.md
  current_section: post_d01
  current_task: D03-01
  production_completed_tasks: 59
  production_total_tasks: 168
  production_progress_percent: 35.1
  task_boundary: D03-01_RUNNING

continuation_policy:
  queue_mode: CANONICAL_ORDER_CONTINUOUS
  active_task_count: ONE
  selection_rule: EARLIEST_UNFINISHED_IN_CANONICAL_ORDER
  advance_after: CURRENT_TASK_DURABLE_CLOSURE
  stop_between_tasks: false
  completed_work_reuse: REQUIRED
  no_rollback_or_redo_without_invalidation: true
  volatile_state_validation_rule: 03_AND_04_MUST_NOT_BE_BYTE_IDENTITY_GATES_FOR_GAMEPLAY_RUNTIME_TESTS
  list_exhausted:
    first: REQUEST_NEW_TASK_FROM_OWNER
    otherwise: DISCOVER_BOUNDED_CURRENT_PROJECTS_AND_REGISTERED_CAPABILITIES
    forbid: [INVENTED_PROJECT_DIRECTION, INVENTED_CAPABILITY_CLAIM, UNAUTHORIZED_EXTERNAL_MUTATION]

resources:
  dispatcher: /usr/local/bin/biella resource
  local_qwen: AVAILABLE_ON_DEMAND_NON_AUTHORITATIVE
  eager_local_assist_before_every_codex_turn: DISABLED_NONBLOCKING
  quota_probe_forbidden: true

control:
  public_live_url: https://biellagames.dev/live/
  public_live_snapshot_url: https://biellagames.dev/live-api/snapshot
  public_live_mode: READ_ONLY_OBSERVER
  website_control_engine_reaction: FORBIDDEN
  authenticated_control_write_routes: DISABLED_405_CONTROL_READ_ONLY
  stale_threshold_policy: MUST_EXCEED_NORMAL_HEARTBEAT_INTERVAL

engine_numbered_execution:
  P4_01_through_P4_05: COMPLETE_REUSE_REQUIRED
  P4-06: INCOMPLETE_DEFERRED
  FOUNDATION_COMPLETE: false

workspace:
  active_repo_roots: [/root/biella/repos/biella-engine]
  active_dirty_scope: D03-01_ONLY
  historical_or_recovery_material_activation: FORBIDDEN_UNLESS_TASK_AUTHORIZES
```
