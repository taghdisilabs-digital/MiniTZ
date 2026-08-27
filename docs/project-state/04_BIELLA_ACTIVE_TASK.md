# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P0-01
  global_number: 1
  phase: P0
  title: Clean-Room Migration Firewall
  state: READY_AFTER_MINIMAL_REOBSERVATION
  exact_prompt:
    title: 01_P0-01_Clean_Room_Migration_Firewall.md
    drive_id: 1Rqj1Vs-V_6xhq90NJRS2hnjIQiVYkER6xG2dJ5CJ2oI
  numbered_predecessor: null
  next_numbered_prompt_in_same_execution: forbidden

goal:
  establish:
    - clean_Biella_repository_or_package_boundary
    - quarantine_first_migration_subsystem
  guarantee:
    - raw_history_not_active_instructions
    - raw_history_not_active_memory
    - raw_history_not_normal_retrieval
    - raw_history_not_active_source
    - raw_history_not_capability_or_policy_definition

prewrite_observation:
  required:
    - actual_repository_or_worktree
    - branch
    - source_commit
    - source_tree
    - dirty_state
    - migrations_if_present
    - tests_if_present
    - AGENTS_policy_instruction_files_if_present
    - accepted_existing_interfaces
    - previous_numbered_prompt_handoff_if_any
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reconcile_existing_equivalent_interfaces_by_semantics
    - do_not_duplicate_architecture_due_to_name_difference

read_inactive_alternative_contract:
  title: Legacy Productive Reuse
  drive_id: 1P4uv74n0UI0JROi5J83ehrg9wDyWPg7FCt5dMMi9HTc
  state: INACTIVE_UNTIL_AFTER_P0_10_DURABLE_CLOSE
  active_authority: false
  load_by_default: false
  permitted_use_before_p0_10: none

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P0_01_Drive_prompt
    - directly_touched_repository_files
  conditional:
    - 00_BIELLA_PROJECT_OPERATING_CONTRACT.md
    - 01_BIELLA_PROJECT_KNOWLEDGE_SOURCE.md
    - 02_BIELLA_ENGINE_FINAL_MIGRATION_PLAN_2026-08-27.md
    - 05_BIELLA_PROMPT_INDEX.yaml
    - 06_BIELLA_SOURCE_EVIDENCE_MAP.yaml
  prohibited_by_default:
    - other_50_prompt_bodies
    - large_real_MiniTZ_backup
    - unrelated_website_work
    - broad_historical_recovery_files
    - broad_Drive_GitHub_filesystem_audits

scope:
  in:
    - minimum_clean_repository_or_package_boundary_if_absent
    - migration_quarantine_boundary
    - semantic_extraction_boundary
    - classification_boundary
    - normalization_boundary
    - exact_SHA256_identity_and_provenance_for_quarantined_bytes
    - QuarantineRef_type_incompatibility_with_active_refs
    - migration_only_read_extract_APIs
    - no_normal_runtime_raw_quarantine_search_or_import_path
  out:
    - reconstruct_or_mine_large_MiniTZ_backup
    - normal_retrieval_implementation
    - memory_system_implementation
    - scheduler_implementation
    - model_provider_implementation
    - production_adapter_implementation
    - P0_02_or_later_prompt_implementation
    - MiniTZ_Git_ancestry_import
    - mechanical_MiniTZ_to_Biella_rename

required_interfaces:
  exact:
    - MigrationSource
    - SemanticExtraction
    - MigrationClassification
    - NormalizedMigrationCandidate
    - QuarantineRef
  rule:
    accepted_existing_semantic_equivalent_may_be_mapped: true
    do_not_invent_additional_required_interfaces: true

classifications:
  exact:
    - UNIVERSAL_GOOD
    - UNIVERSAL_REWRITE
    - PROJECT_SPECIFIC
    - HISTORICAL_EVIDENCE
    - DUPLICATE
    - OBSOLETE_OR_DRIFT
  default_or_unknown_admissible: false

migration_source_requirements:
  preserve:
    - raw_SHA256
    - source_locator_or_manifest_identity_when_available
    - acquisition_or_import_time
    - source_type
    - immutable_provenance_metadata
  filename_is_sufficient_identity: false

semantic_extraction:
  imperative_text_grants_execution_authority: false
  role: meaning_as_data_only

normalized_candidate:
  require_explicit_classification: true
  require_provenance_chain_to_raw_source: true
  direct_raw_activation: false

fail_closed:
  reject:
    - digest_mismatch
    - provenance_missing
    - invalid_classification
    - missing_classification
    - malformed_source_identity
    - QuarantineRef_to_active_Artifact_conversion
    - raw_source_to_Engine_Knowledge
    - quarantine_in_normal_context_or_retrieval

idempotency:
  same_exact_bytes_same_source_identity:
    require: idempotent_or_deterministically_deduplicated
  same_filename_different_bytes:
    require: distinct_by_digest
  duplicate_active_authority_allowed: false

hostile_fixture:
  source: synthetic_only
  may_contain:
    - fake_owner_policy
    - forced_provider_choice
    - instruction_to_override_current_Biella_rules
  prove:
    - quarantine_can_store_and_read_bytes
    - migration_extraction_can_analyze
    - normal_runtime_cannot_retrieve_or_execute
    - cannot_become_Project_Memory_directly
    - cannot_become_Engine_Knowledge_directly
    - cannot_bind_as_normal_Task_input
    - cannot_register_capability
    - cannot_register_policy
  personal_or_private_human_media_fixture: forbidden

required_test_matrix:
  - id: T01
    prove: exact_raw_bytes_round_trip_through_quarantine
  - id: T02
    prove: SHA256_verification_succeeds_for_unchanged_data
  - id: T03
    prove: corrupted_bytes_fail_verification
  - id: T04
    prove: all_six_classifications_round_trip
  - id: T05
    prove: unclassified_candidate_normalization_rejected
  - id: T06
    prove: invalid_classification_rejected
  - id: T07
    prove: hostile_imperative_historical_content_inert
  - id: T08
    prove: raw_history_cannot_bind_Project_Memory
  - id: T09
    prove: raw_history_cannot_bind_Engine_Knowledge
  - id: T10
    prove: raw_history_cannot_enter_normal_Context_or_Task_input
  - id: T11
    prove: raw_history_cannot_enter_normal_retrieval_index
  - id: T12
    prove: active_runtime_dependency_scan_has_no_raw_quarantine_dependency
  - id: T13
    prove: duplicate_import_idempotent_or_deduplicated
  - id: T14
    prove: same_filename_different_bytes_remain_distinct
  - id: T15
    prove: repository_history_clean_no_imported_MiniTZ_ancestry

kpi:
  raw_sources_with_digest: "100%"
  raw_sources_with_provenance: "100%"
  unclassified_active_admissions: 0
  raw_history_in_normal_retrieval: 0
  raw_history_in_Project_or_Engine_memory: 0
  direct_runtime_dependency_on_quarantine: 0

implementation_method:
  - inspect_exact_current_source
  - write_focused_failure_first_tests_when_useful
  - implement_minimum_complete_P0_01
  - run_focused_tests
  - run_relevant_regression_gate
  - typecheck_if_repository_contract_has_typecheck
  - build_if_repository_contract_has_build
  - inspect_actual_outputs_exports_dependency_boundaries

publication:
  when_repository_write_access_available_and_implementation_complete:
    - record_source_commit
    - commit_coherent_P0_01_result
    - push
    - remote_readback_result_commit
    - remote_readback_result_tree
    - verify_required_remote_paths
  local_success_without_required_remote_readback: not_durable_complete

required_report:
  - PROMPT
  - STATUS
  - SOURCE_COMMIT
  - RESULT_COMMIT
  - RESULT_TREE
  - IMPLEMENTED
  - INTERFACES_CREATED_OR_CHANGED
  - MIGRATIONS_OR_STATE_CHANGES
  - TESTS_EXECUTED
  - KPI_RESULTS
  - REALITY_CLASSIFICATION
  - PROJECT_ISOLATION_CONTAMINATION_DURABILITY_CHECKS
  - KNOWN_LIMITATIONS
  - UNRESOLVED_FACTS
  - NEXT_DEPENDENCY

continuation:
  on_success:
    - leave_repository_worktree_understood
    - report_intentional_dirty_or_uncommitted_files
    - update_03_BIELLA_CURRENT_STATE
    - update_required_canonical_Drive_continuity
    - replace_04_with_P0_02_packet_in_separate_execution
  stop_after_P0_01: true
  start_P0_02_automatically: false
  broad_real_historical_mining_after_P0_01: false
```
