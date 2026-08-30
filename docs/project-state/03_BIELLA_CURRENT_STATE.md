# 03 — BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v5
state_class: VOLATILE
update_rule: replace_stale_values; do_not_append_history
observed_date: 2026-08-30

authority:
  if_conflict:
    - CURRENT_EXECUTION_STATE
    - CURRENT_GITHUB_SOURCE
    - CURRENT_CANONICAL_DRIVE
    - VERIFIED_HISTORICAL_EVIDENCE
    - REFERENCE_OR_PLAN
    - INFERENCE
  correction_rule: invalidate_only_conflicting_state; preserve_independently_valid_work

engine:
  repository: patrickminitz-web/biella-engine
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine

durable_source:
  current_implementation_base:
    commit: e228a7bb6db6f94af15dde4a8fb110b028eddbed
    tree: b407138ac05af441487aa6005700da98b8016906
    meaning: P3_04_closed_and_P3_05_open_before_recovered_GPT_5_6_dirty_work
  current_execution_map:
    commit: 360e35d84c216e632683e711955e90606787d798
    file: docs/project-state/04_BIELLA_ACTIVE_TASK.md
    schema: biella.active_task/v6
    language: biella.codex.end_to_end/v2
    status: VERIFIED_GITHUB_WRITE
  branch_head_rule: continuity_commits_can_be_newer_than_implementation_base; reobserve_origin_main_before_next_host_write
  rejected_history:
    first_rejected_execution_time: "2026-08-30T10:44:52Z"
    rejected_post_boundary_completion_claims: P3_05_THROUGH_P3_09

numbered_execution:
  durable_prompts_complete: 35
  durable_prompts_total: 51
  progress: "35 / 51"
  phase: P3
  active_prompt: P3-05
  active_global_number: 36
  active_title: 3D Modeling and Scene Production Pack
  successor: P3-06
  successor_execution_authorized: false
  future_activation_shells_prepared: P3_06_THROUGH_P4_06
  future_internal_graphs_precompiled: false
  future_graph_rule: compile_each_from_exact_prompt_and_current_source_only_when_activated

execution_host_state:
  current_host: NONE
  previous_host: DESTROYED
  previous_host_paths_are_current_state: false
  previous_checkout_observation:
    head: e228a7bb6db6f94af15dde4a8fb110b028eddbed
    upstream: main...origin/main
    worktree: CLEAN_BEFORE_GPT_5_6_WORKTREE_RESTORE
    evidence_state: HISTORICAL_AFTER_HOST_DESTRUCTION
  next_host:
    state: NOT_YET_PROVISIONED
    canonical_root: /root/biella
    canonical_codex_home: /root/.codex
    canonical_checkout: /root/biella/repos/biella-engine
    bootstrap_order:
      - provision_new_disposable_execution_host
      - create_canonical_roots
      - clone_current_GitHub_main_into_canonical_checkout
      - verify_current_GitHub_03_04_and_branch_head
      - fetch_recovery_archive_from_verified_Drive_ID
      - verify_archive_exact_size_and_sha256
      - restore_exact_GPT_5_6_P3_05_worktree
      - never_hard_reset_after_restoration

p3_05_recovery:
  status: CAPTURED_RESTORE_PENDING
  valid_execution_through: "2026-08-30T10:08:48.575Z"
  reject_execution_beginning: "2026-08-30T10:44:52Z"
  recovery_archive_name: GPT56_EXACT_RECOVERY_2026-08-30.tar.gz
  recovery_archive_sha256: 73052d6cffea8017bebee64750d8de532654ca6c7e8dffff62caa554efe30f0d
  recovery_archive_size_bytes: 26490936
  recovery_archive_drive_id: 1Y7aEStdGbCK5a0N9iA8s41l2olTWOUAE
  recovery_archive_drive_readback: VERIFIED_EXACT_BYTES
  recovery_archive_drive_readback_sha256: 73052d6cffea8017bebee64750d8de532654ca6c7e8dffff62caa554efe30f0d
  restore_target_host: NEW_HOST_NOT_YET_PROVISIONED
  archive_contains_relevant_sessions: 13
  expected_recovered_dirty_paths_count: 9
  path_set_is_not_content_authority: true
  content_authority: pre_10_44_52_GPT_5_6_recovery_evidence

approved_execution_program:
  language: biella.codex.end_to_end/v2
  mode: SINGLE_END_TO_END_NUMBERED_EXECUTION
  active_graph_location: docs/project-state/04_BIELLA_ACTIVE_TASK.md
  active_graph:
    serial_front:
      - B0_NEW_HOST_BOOTSTRAP
      - R0_PRE_RUN_GUARD
      - R1_RESTORE
      - M0_GAP_MAP
    parallel_implementation:
      - I1_PACK_API
      - I2_THREED_CORE
      - I3_BLENDER_DRIVER
      - I4_PROCESS_SUBSTRATE
    integration_and_acceptance:
      - G1_INTEGRATION
      - I5_REAL_ACCEPTANCE
      - G2_IMPLEMENTATION_FREEZE
    parallel_read_only_validation:
      - V1_PACK_CONTRACT
      - V2_REAL_OUTPUT_TRUTH
      - V3_ISOLATION_RECOVERY
    repair_and_close:
      - F_REPAIR
      - V4_REGRESSION_GATE
      - V5_BUILD_RUNTIME_GATE
      - C0_DURABLE_CLOSE
  duplicate_prevention:
    exact_Node_identity_and_claim: required
    one_current_owner_per_Node: true
    overlapping_live_write_paths: forbidden
    validators_read_only: true
    repairs_derive_from_exact_failure_and_original_owner_boundary: true
  checkpoints:
    - CP0_RESTORED
    - CP1_GAP_MAP
    - CP2_INTEGRATED
    - CP3_REAL_WORKFLOW
    - CP4_REPAIR_CONVERGENCE
    - CP5_FINAL_VALIDATION
    - CP6_DURABLE_CLOSE
  token_efficiency:
    inspect_once_then_reobserve_only_invalidated_facts: true
    compact_worker_result_envelopes: true
    full_worker_transcript_handoffs: forbidden
    irrelevant_tools_and_skill_bundles_default_off: true
    usage_low_starts_no_new_Node: true
  superpowers_alignment:
    used_for_plan_decomposition_and_self_review: true
    runtime_dependency: false
    generic_subagent_or_reviewer_ceremony_overrides_Biella: false

context_policy:
  normal_load:
    - docs/project-state/03_BIELLA_CURRENT_STATE.md
    - docs/project-state/04_BIELLA_ACTIVE_TASK.md
    - exact_active_numbered_prompt
    - directly_touched_source_and_interfaces
  read_only_if_required:
    - 00_operational_edge_cases
    - 01_architecture_or_semantic_scope
    - 02_sequence_or_plan_ambiguity
    - 05_exact_prompt_location
    - 06_source_evidence_or_migration_resolution
  prohibited_default_reloads:
    - unchanged_files
    - all_51_prompt_bodies
    - historical_recovery_sessions_after_restoration
    - broad_Drive_Git_or_filesystem_audits
    - raw_MiniTZ_history

truth:
  P3_04_durable_close: VERIFIED
  P3_05_durable_close: NOT_YET_VERIFIED
  P3_06_or_later_completion_claims_from_rejected_execution: REJECTED
  exact_recovered_P3_05_worktree_contents: UNKNOWN_UNTIL_RESTORED_AND_REOBSERVED
  multi_AI_execution_map_approved_by_user: true
  future_numbered_activation_queue_prepared: true
  previous_VPS_destroyed: VERIFIED_USER_REPORT
  current_execution_host_exists: false
  Drive_recovery_archive_exact_readback: VERIFIED
```
