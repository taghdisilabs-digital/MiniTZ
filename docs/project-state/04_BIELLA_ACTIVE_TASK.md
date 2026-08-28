# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P1-01
  global_number: 11
  phase: P1
  title: Content-Addressed Object Store
  state: READY_AFTER_P0_10_DURABLE_CLOSE
  exact_prompt:
    title: 11_P1-01_Content_Addressed_Object_Store.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P1/11_P1-01_Content_Addressed_Object_Store.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P1/11_P1-01_Content_Addressed_Object_Store.md.docx
    drive_id: 1a8NV8vEPxyKCVhwk1MKSd3AXfhyB87vkpvPko0Ka45c
    local_docx_sha256: 473e3ec03804d36f7128e886da5b34157e5da680d5fd1948ee9199a48c142e92
    live_drive_exported_docx_sha256: 8b37be941582850ad4f905c27ad92c4fc1b5a287995bad9bf4b772e32a06c535
    canonical_text_sha256: 147ac60d73c0aeda3fe6f13f5e3e279d8abe145549b0ac98d5055e201a923760
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P0-10
    result_commit: 1573db1a1062bd311603945dd6d4a7323636d6a4
    result_tree: 8c4e6ad41fb12601f581affac3e005fe9ceb05a5
    exit_decision: READY_FOR_P1
    remote_readback: VERIFIED
  numbered_successor: P1-02

goal:
  establish:
    - physical_immutable_byte_store_behind_ContentRef
    - exact_content_integrity_across_process_loss
    - provider_neutral_replaceable_storage_backend
    - streaming_atomic_deduplicating_durable_storage
  preserve:
    - Project_isolation_and_logical_Artifact_authorization_above_content_storage
    - quarantine_and_active_logical_separation_even_when_physical_bytes_dedupe
    - all_P0_exact_identity_immutability_fencing_durability_validation_and_evidence_contracts

prewrite_observation:
  required:
    - actual_repository_or_worktree
    - branch
    - source_commit_and_tree
    - dirty_state
    - migrations_and_tests_if_present
    - AGENTS_policy_and_instruction_files_if_present
    - accepted_ContentRef_Artifact_and_storage_equivalent_interfaces
    - exact_P0_10_remote_handoff
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reuse_valid_earlier_implementation_and_results
    - reconcile_existing_equivalent_interfaces_by_semantics
    - missing_handoff_paperwork_is_not_a_blocker_when_exact_source_is_observable

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P1_01_canonical_prompt
    - P0_06_ContentRef_Artifact_Source_and_provenance_interfaces
    - Project_authorization_interfaces_directly_needed_by_logical_boundary_tests
    - directly_touched_repository_files_and_required_regression_tests
  conditional:
    - current_Biella_project_instructions
    - earlier_accepted_contracts_actually_used_by_this_task
  prohibited_by_default:
    - unopened_P1_02_through_P4_prompt_bodies
    - broad_historical_backup_or_legacy_reuse_material
    - unrelated_website_work
    - broad_Drive_GitHub_or_filesystem_audits

dependencies:
  P0_10:
    result_commit: 1573db1a1062bd311603945dd6d4a7323636d6a4
    result_tree: 8c4e6ad41fb12601f581affac3e005fe9ceb05a5
    required_semantics:
      - integrated_P0_contract_is_READY_FOR_P1
      - Project_isolation_quarantine_inertness_exact_identity_immutability_recovery_concurrency_and_kernel_neutrality_hold
  P0_06_and_earlier_accepted_contracts:
    required_semantics:
      - ContentRef_is_exact_content_identity
      - Artifact_and_Source_identity_and_provenance_are_immutable
      - logical_Project_authorization_does_not_collapse_when_digest_is_shared

scope:
  in:
    - provider_neutral_ObjectStorageBackend
    - immutable_ContentObject_metadata
    - real_durable_filesystem_backend
    - deterministic_in_memory_reference_backend
    - streaming_put_open_read_stat_exists_and_verify_semantics
    - incremental_SHA_256_and_exact_size_calculation
    - expected_digest_and_expected_size_validation
    - atomic_temporary_write_to_digest_derived_final_exposure
    - fsync_close_and_required_readback_integrity_verification
    - identical_byte_reuse_and_concurrent_first_writer_convergence
    - restart_exact_read_and_corruption_detection
    - physical_dedupe_with_logical_quarantine_active_and_Project_boundaries_preserved
  out:
    - replica_ranking
    - remote_or_S3_compatible_object_storage
    - global_garbage_collection_policy
    - retention_policy
    - evictable_authoritative_cache
    - later_numbered_prompt_architecture
    - unrelated_domain_or_provider_specialization

required_interfaces:
  create_or_reconcile:
    - ContentObject
    - ObjectStorageBackend
    - filesystem_backend
    - memory_or_reference_backend
    - streaming_put
    - streaming_open_or_read
    - stat
    - exists
    - verify
  content_object_conceptual_fields:
    - algorithm
    - digest
    - size
    - optional_media_type
    - created_at
  rule:
    storage_path_or_URI_is_not_logical_content_identity: true
    ContentLocation_or_replicas_are_separate_from_ContentObject: true
    logical_Artifact_authorization_remains_above_physical_content_layer: true

write_algorithm:
  required_sequence:
    - stream_bytes_to_backend_temporary_location
    - calculate_SHA_256_incrementally
    - calculate_exact_size
    - compare_expected_digest_and_size_when_supplied
    - fsync_and_close_as_required_by_filesystem_semantics
    - atomically_expose_under_digest_derived_path_or_key
    - independently_read_back_and_verify_before_durable_success_when_required
    - return_exact_ContentRef_or_semantically_equivalent_identity
  invariants:
    - partial_object_is_never_exposed_as_verified
    - interrupted_write_leaves_no_verified_final_object_or_misleading_metadata
    - concurrent_identical_writers_converge_on_one_exact_digest_identity
    - identical_existing_bytes_are_reused
    - user_supplied_filename_or_path_is_never_trusted_as_object_locator

read_and_integrity:
  require:
    - explicit_silent_corruption_detection_path
    - size_and_digest_verification_before_returning_authoritative_verified_bytes
    - corrupt_or_truncated_object_never_returned_as_verified_valid_content
    - large_content_streaming_without_full_bytes_in_memory

data_or_state_changes:
  allowed:
    - Content_object_or_location_registry_only_if_required_by_accepted_design
  prohibit:
    - storage_URI_as_ContentObject_identity
    - cache_eviction_that_can_destroy_authoritative_content
    - premature_GC_retention_or_replica_policy

failure_behavior:
  fail_closed_on:
    - expected_digest_mismatch
    - expected_size_mismatch
    - physical_digest_or_size_corruption
    - truncated_content
    - path_escape_or_untrusted_locator
    - logical_Project_scope_identity_or_authority_mismatch
    - quarantine_or_historical_content_active_binding
  preserve:
    - durable_evidence
    - real_failure_cause
    - unaffected_required_work
    - already_verified_durable_content
  prohibit:
    - fabricated_success
    - fabricated_missing_fact
    - mocked_real_infrastructure_classification
    - weakened_architecture_for_unavailable_dependency

concurrency_and_recovery:
  require:
    - concurrent_first_writer_race_uses_real_backend_semantics
    - duplicate_identical_writers_converge_without_corruption_or_duplicate_authoritative_identity
    - restart_reconstructs_and_verifies_exact_bytes_without_process_or_session_memory
    - stale_owners_or_results_remain_rejected_by_existing_authority_model
    - independent_work_is_not_globally_serialized_beyond_required_storage_or_database_commit_boundary

required_test_matrix:
  - {id: T01, prove: empty_object_exact_roundtrip}
  - {id: T02, prove: small_text_and_binary_exact_roundtrip}
  - {id: T03, prove: large_chunked_stream_roundtrip_without_full_RAM_requirement}
  - {id: T04, prove: expected_digest_mismatch_fails_closed_without_published_object}
  - {id: T05, prove: expected_size_mismatch_fails_closed_without_published_object}
  - {id: T06, prove: identical_bytes_dedupe_and_different_bytes_have_different_identity}
  - {id: T07, prove: concurrent_identical_puts_converge_on_one_exact_identity_and_valid_object}
  - {id: T08, prove: intentional_corruption_and_truncation_are_detected_and_never_returned_as_verified}
  - {id: T09, prove: interrupted_write_exposes_no_partial_verified_object_or_misleading_metadata}
  - {id: T10, prove: filesystem_restart_reads_and_verifies_exact_bytes}
  - {id: T11, prove: deterministic_memory_reference_backend_matches_provider_neutral_contract}
  - {id: T12, prove: quarantine_and_active_logical_boundary_survives_physical_dedupe}
  - {id: T13, prove: Project_Artifact_authorization_remains_enforced_above_physical_content_layer}
  - {id: T14, prove: path_escape_and_storage_URI_identity_coupling_are_absent}
  - {id: T15, prove: required_P0_regressions_typecheck_build_and_installed_wheel_restart_smoke_pass_without_skips_placeholders_or_TODO_tests}

kpi:
  content_roundtrip_exact: 100%
  content_corruption_detected: 100%
  partial_objects_published: 0
  path_escapes: 0
  object_identity_tied_to_storage_uri: 0
  cache_eviction_can_destroy_authority: 0

completion_gate:
  require:
    - verified_immutable_content_survives_restart
    - backend_is_replaceable_without_changing_ContentRef
    - Artifact_and_Project_authorization_remain_separate
    - concurrent_duplicate_writers_converge_without_partial_publication
    - corruption_is_detected_before_verified_bytes_are_returned
    - all_required_tests_and_regressions_pass_without_skips_placeholders_or_TODOs

implementation_method:
  - verify_exact_P0_10_remote_handoff
  - inspect_exact_ContentRef_Artifact_Project_interfaces_and_directly_relevant_tests
  - add_task_scoped_failing_tests_before_implementation_or_defect_fix
  - implement_minimal_provider_neutral_content_store_contract
  - exercise_real_filesystem_atomicity_concurrency_corruption_and_restart
  - run_focused_P1_01_tests
  - run_relevant_P0_regressions_and_full_required_suite
  - run_strict_typecheck_compileall_and_build
  - inspect_actual_wheel_and_clean_install_restart_smoke
  - obtain_independent_changed_code_review_before_publication

publication:
  when_complete:
    - record_source_commit
    - commit_coherent_P1_01_result
    - push_main
    - remote_readback_result_commit
    - remote_readback_result_tree
    - verify_required_remote_paths_and_bytes
    - update_03_BIELLA_CURRENT_STATE_and_exact_canonical_Drive_continuity
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
    - replace_04_with_exact_P1_02_packet_only_after_P1_01_durable_close
    - close_P1_01_before_opening_P1_02
  continue_numbered_prompts_one_at_a_time: true
  broad_real_historical_mining: false
```
