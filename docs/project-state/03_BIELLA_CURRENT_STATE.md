# 03 - BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v6
state_class: VOLATILE
update_rule: replace_stale_values; do_not_append_history
observed_date: 2026-09-05

authority:
  if_conflict:
    - CURRENT_EXECUTION_STATE
    - CURRENT_GITHUB_SOURCE
    - CURRENT_CANONICAL_DRIVE
    - VERIFIED_HISTORICAL_EVIDENCE
    - REFERENCE_OR_PLAN
    - INFERENCE
  correction_rule: invalidate_only_conflicting_state; preserve_independently_valid_work

repository:
  repository: patrickminitz-web/biella-engine
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine
  target_structure: ONE_REPOSITORY_MONOREPO

active_execution:
  id: BIELLA-CONSOLIDATION-2026-09-05
  state: IN_PROGRESS
  authority: MAHDI_EXPLICIT_APPROVAL
  working_branch: monorepo-unification-20260905
  base_commit: 086b79de3a5bf3f6ea00ced13cc1433c09c37a78
  feeder: STOPPED_BY_OWNER
  next_after_consolidation: D01-027

games:
  project_path: projects/biella-games
  production_source: projects/biella-games/docs/PRODUCTION.md
  section: demo01
  completed_demo_tasks: 26
  total_demo_tasks: 50
  queued_successor: D01-027
  preserved_source_commit: 2193b769e61b43ebfc4f910f6380c68e6b828cd5
  preserved_source_tree: b80f2fcee95b3180d0a5a7b6664819876962ce6e
  import_readback: 88_OF_88_BLOBS_MATCHED_BEFORE_PATH_EDITS
  imported_snapshot_state: CURRENT_PRESERVED_IMPORT
  external_writer_state: STOPPED_FOR_CONSOLIDATION
  external_live_observation: D01-001_THROUGH_D01-026_COMPLETE_D01-027_PENDING_PARTIAL_PRESERVED

engine_numbered_execution:
  P4_01_through_P4_05: COMPLETE_REUSE_REQUIRED
  P4-06: INCOMPLETE_DEFERRED
  P4-06_missing: authoritative_Engine_evidence_and_combined_failure_scenario
  FOUNDATION_COMPLETE: false
  deferred_reason: MAHDI_EXPLICIT_WORKFLOW_CONSOLIDATION_AND_GAMES_EXECUTION_DIRECTION

preserved_inputs:
  website_control_commit: b621a0680c5586a1502558efb81ff084f8d1da74
  capability_preparation_commit: aa718584a99c0cee1884488bb4dafec4d2e94c05
  aaa_sf_commit: 297129637fded33dc0e3636954645e5655803928
  aaa_sf_state: FUTURE_PROGRAM_BLOCKED

drive:
  canonical_root_id: 1Z6_qwN9hfHIheXZ_9pYCG8dRDMuRN-l7
  current_state_file_id: 1wiWcdWt4hmTf3narsLw4OqGu_ueKOSa4
  active_task_file_id: 1liutA8evH6rPjk-U4tgR13l_kqBrx-DF
  production_map_doc_id: 1aRnEdxQwe-Dn3VRh29CMkTXlxHOjcCjtfR-GNxQpp6s
  games_current_root_id: 1SgvztxBMthMRbr6BPS-n9OXa2RYyXXDb
  navigation_state: CONSOLIDATION_PENDING

evidence:
  p3_14: docs/project-state/evidence/P3_14_DELIVERY_QUALIFICATION_EVIDENCE.md
  migration_provenance: docs/migration/ONE_REPO_PROVENANCE_2026-09-05.md
  games_monorepo_qualification: docs/migration/evidence/MONOREPO_GAMES_QUALIFICATION_2026-09-05.md
  prior_durable_state: GIT_HISTORY_AND_DEDICATED_EVIDENCE_FILES

pruning:
  rule: REMOVE_ONLY_AFTER_UNIQUE_VALUE_MIGRATED_OR_REJECTED_AND_REMOTE_READBACK_VERIFIED
  spark_recovery: UNRESOLVED_KEEP
  old_worktrees: PENDING_COMPARE_AFTER_CANONICAL_PUBLISH
  old_repositories: PENDING_ARCHIVE_AFTER_CANONICAL_PUBLISH
```
