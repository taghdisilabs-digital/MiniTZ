# 03 - BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v13
state_class: VOLATILE_CURRENT
update_rule: REALTIME_CANONICAL_UPGRADE

authority:
  if_conflict: [CURRENT_EXECUTION_STATE, CURRENT_GITHUB_SOURCE, CURRENT_CANONICAL_DRIVE, VERIFIED_EVIDENCE, INFERENCE]
  rule: replace_stale_current_fields_in_place; preserve accepted outputs; no_duplicate_active_state

repository:
  repository: patrickminitz-web/biella-engine
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine
  git_identity_source: LIVE_GIT_READ_REQUIRED
  source_alignment_gate: VERIFIED_GITHUB_MAIN_SAFE_FAST_FORWARD_OR_FAIL_CLOSED

  source_identity_source: LIVE_GIT_PLUS_RUNTIME
active_execution:
  id: D04-01
  project: Biella Games
  section: post_d01
  state: PENDING
  controller: biella-codex

  runner: READY
  runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json
customer_execution:
  project_cell_execution_model: ISOLATED_PROJECT_CELL

  runtime_state_source: DOCKER_PLUS_CUSTOMER_HANDOFF_RUNTIME
website:
  execution_model: NO_PERMANENT_WEBSITE_AGENT
  live_projection: DETERMINISTIC_READ_ONLY
  public_snapshot: https://biellagames.dev/live-api/snapshot
  public_events: https://biellagames.dev/live-api/events

games:
  production_source: projects/biella-games/docs/PRODUCTION.md
  current_section: post_d01
  current_task: D04-01
  completed_tasks: 60
  total_tasks: 168

  completed_demo_tasks: 50
  queued_successor: D04-01
  task_boundary: D04-01_PENDING
resources:
  strong_route_policy: HIGHEST_QUALITY_ELIGIBLE
  forced_route: gpt-reserve
  forced_reasoning: max
  cache_efficiency: ACTIVE_QUALITY_FIRST
  local_qwen: NON_AUTHORITATIVE_ON_DEMAND
  project_data_leakage: FORBIDDEN

execution_invariants:
  owner_acceptance_fast_path: ACTIVE
  task_class_is_not_a_blocker: true
  no_monitor_only_stall: true
  no_external_progress_hook_dependency: true
  automatic_advance_after_durable_completion: true
  realtime_canonical_upgrade: true
  proven_execution_style: ACTIVE
  active_progress_killer_audit: PASS
  forbidden_pattern_contract: HOW_BIELLA_WILL_NOT_WORK

engine_numbered_execution:
  P4_01_through_P4_05: COMPLETE_REUSE_REQUIRED
  P4-06: INCOMPLETE_DEFERRED
  FOUNDATION_COMPLETE: false
```
