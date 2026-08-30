# 03 — BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v3
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

current_github:
  status: VERIFIED
  head: e228a7bb6db6f94af15dde4a8fb110b028eddbed
  tree: b407138ac05af441487aa6005700da98b8016906
  message: Record P3-04 closeout and open P3-05
  parent: 28fde1e9224236ce7b37b74434727463e96d9893
  rollback_reason: remove_post_GPT_5_6_execution_drift

numbered_execution:
  durable_prompts_complete: 35
  durable_prompts_total: 51
  progress: "35 / 51"
  phase: P3
  active_prompt: P3-05
  active_global_number: 36
  active_title: 3D Modeling and Scene Production Pack
  predecessor: P3-04
  predecessor_result_commit: 28fde1e9224236ce7b37b74434727463e96d9893
  predecessor_result_tree: d7efcc21cab8dc86488ef91963f48791dbe0dca0
  predecessor_remote_readback: VERIFIED
  successor: P3-06
  successor_execution_authorized: false

local_execution_state:
  host_state: STOPPED_AFTER_RECOVERY_CAPTURE
  last_verified_checkout_head: e228a7bb6db6f94af15dde4a8fb110b028eddbed
  last_verified_branch_upstream: main...origin/main
  last_verified_worktree: CLEAN_BEFORE_GPT_5_6_WORKTREE_RESTORE
  exact_current_worktree_after_next_boot: UNKNOWN_UNTIL_REOBSERVED

p3_05_recovery:
  status: CAPTURED_RESTORE_PENDING
  purpose: restore_last_valid_GPT_5_6_P3_05_worktree_before_continuing
  valid_execution_through: "2026-08-30T10:08:48.575Z"
  reject_execution_beginning: "2026-08-30T10:44:52Z"
  rejected_model_family_observed_after_boundary: gpt-5.3-codex-spark
  recovery_archive_name: GPT56_EXACT_RECOVERY_2026-08-30.tar.gz
  recovery_archive_sha256: 73052d6cffea8017bebee64750d8de532654ca6c7e8dffff62caa554efe30f0d
  recovery_archive_size_bytes: 26490936
  archive_contains_relevant_sessions: 13
  expected_recovered_dirty_paths:
    modified_tracked:
      - src/biella/__init__.py
      - src/biella/process.py
      - src/biella/production_pack.py
      - tests/test_p2_02_process.py
    untracked_p3_05:
      - src/biella/_blender_three_d_driver.py
      - src/biella/three_d_pack.py
      - src/biella/three_d_tool.py
      - tests/test_p3_05_three_d_pack.py
      - tests/test_p3_05_three_d_real.py
  path_set_is_not_content_authority: true
  content_authority: pre_10_44_52_GPT_5_6_recovery_evidence

next_execution:
  mode: SINGLE_END_TO_END_NUMBERED_EXECUTION
  first_action: reobserve_HEAD_and_worktree_then_restore_exact_GPT_5_6_P3_05_state
  do_not_reconstruct_from_scratch: true
  preserve_valid_newer_GPT_5_6_work: true
  do_not_import_post_boundary_mutations: true
  do_not_start_P3_06_before_P3_05_durable_close: true

context_policy:
  normal_load:
    - docs/project-state/03_BIELLA_CURRENT_STATE.md
    - docs/project-state/04_BIELLA_ACTIVE_TASK.md
    - exact_P3_05_canonical_prompt
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
```
