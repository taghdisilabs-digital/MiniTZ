# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P0-06
  global_number: 6
  phase: P0
  title: Artifact and Source Identity Contract
  state: READY_AFTER_P0_05_DURABLE_CLOSE
  exact_prompt:
    title: 06_P0-06_Artifact_and_Source_Identity_Contract.md.docx
    drive_id: 17l-QAoXQPl2QkE3B7BJqoeCVsJHybnrq8UQlRltu1as
    canonical_text_sha256: 6a28d180247ad33881e9b02e57cd9e1cd72e4f2cba619f96dafab0d217bf8bb7
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P0-05
    result_commit: 8f53a1fd641ad46c893239cd8279f310432086bc
    result_tree: ed4e97846d8c055a0e8967b83a8b100bef481ddf
    remote_readback: VERIFIED
  numbered_successor: P0-07

goal:
  establish:
    - Project_scoped_logical_Artifact_identity
    - exact_immutable_ContentRef_identity
    - exact_Project_scoped_SourceRef_identity
    - generic_immutable_ArtifactDerivation_provenance
    - exact_Task_input_and_Run_output_identity_seams
  guarantee:
    - logical_Artifact_identity_is_distinct_from_content_digest
    - physical_storage_location_is_not_Artifact_or_Content_identity
    - identical_bytes_never_collapse_Project_authorization
    - immutable_content_or_provenance_change_creates_a_new_Artifact_revision

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
    - P0_05_exact_remote_handoff
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reuse_valid_earlier_implementation_and_results
    - reconcile_existing_equivalent_interfaces_by_semantics
    - missing_handoff_paperwork_is_not_a_blocker_when_exact_source_is_observable

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P0_06_canonical_prompt
    - P0_01_quarantine_type_boundary
    - P0_02_Project_interfaces
    - P0_04_Task_and_TaskInputRef_interfaces
    - P0_05_Run_interfaces
    - directly_touched_repository_files
  conditional:
    - current_Biella_project_instructions
    - earlier_accepted_contracts_actually_used_by_this_task
  prohibited_by_default:
    - other_45_unopened_prompt_bodies
    - large_real_MiniTZ_backup
    - inactive_legacy_reuse_contract
    - unrelated_website_work
    - broad_historical_recovery_files
    - broad_Drive_GitHub_filesystem_audits

dependencies:
  P0_01:
    result_commit: fa442745b73e02cc2cd67ef0c029973de06bb773
    required_semantics:
      - QuarantineRef_is_migration_only_and_authority_distinct
      - identical_digest_does_not_activate_quarantined_material
  P0_02:
    result_commit: 2847543e0b3f9bac04e0e879e4b81f748cab712c
    required_interfaces:
      - Project
      - ProjectRef
      - ProjectAccess
    required_semantics:
      - authenticated_Project_scope
      - cross_Project_access_fails_closed
  P0_04:
    result_commit: 9b28ccf93c4cb8edd771f474903bcfa5e7592b1b
    required_interfaces:
      - Task
      - TaskRef
      - TaskInputRef
      - TaskRevisionService
    required_semantics:
      - exact_immutable_Task_inputs
      - immutable_Task_revisions
      - exact_Task_digest
  P0_05:
    result_commit: 8f53a1fd641ad46c893239cd8279f310432086bc
    result_tree: ed4e97846d8c055a0e8967b83a8b100bef481ddf
    required_interfaces:
      - Run
      - RunRef
      - RunService
    required_semantics:
      - exact_Project_and_Task_binding
      - stale_Run_authority_fails_closed
      - immutable_attempt_and_authority_history

scope:
  in:
    - opaque_stable_Project_scoped_Artifact_identity
    - positive_immutable_Artifact_revision
    - extensible_Artifact_role_and_type_metadata
    - exact_SHA_256_ContentRef_with_size_and_media_type
    - exact_Project_scoped_SourceRef_variants
    - generic_ArtifactDerivation_relationship
    - optional_producer_Run_or_future_Node_reference
    - immutable_content_source_and_derivation_bindings
    - durable_Artifact_revision_and_derivation_persistence
    - atomic_creation_and_revision
    - restart_durability
    - physical_location_independence
    - Task_and_Run_exact_identity_integration_seams
  out:
    - physical_object_storage_backend
    - remote_object_upload_or_download
    - storage_routing_or_replication
    - domain_or_game_specific_Artifact_enum
    - provider_or_hardware_specialization
    - new_Graph_Scheduler_or_resource_model
    - later_numbered_prompt_implementation

required_interfaces:
  exact:
    - Artifact
    - ArtifactRef
    - ContentRef
    - SourceRef
    - ArtifactDerivation
  accepted_service_name:
    - ArtifactService
  rule:
    accepted_existing_semantic_equivalent_may_be_mapped: true
    do_not_duplicate_architecture_due_to_name_difference: true

identity_contract:
  distinct:
    Artifact:
      meaning: logical_Project_scoped_produced_or_consumed_object_revision
      identity_must_not_be:
        - content_digest
        - filename
        - filesystem_path
        - storage_URI
        - object_store_location
    ContentRef:
      meaning: exact_immutable_byte_or_content_identity
      require:
        - algorithm_SHA_256
        - lowercase_digest
        - nonnegative_size
        - bounded_media_type_where_useful
    storage_location:
      meaning: mutable_physical_location_of_bytes
      fully_implemented_in_P0_06: false
      may_change_without_changing_Artifact_or_ContentRef: true

artifact_contract:
  require:
    - opaque_stable_artifact_id
    - exactly_one_ProjectRef
    - positive_immutable_revision
    - extensible_role_or_type_string
    - optional_exact_ContentRef
    - zero_or_more_exact_SourceRef_values
    - zero_or_more_exact_ArtifactDerivation_values
    - optional_producer_RunRef_where_applicable
    - generic_media_or_schema_metadata
    - timezone_aware_created_at
    - semantic_and_record_integrity_digests
  prohibit:
    - closed_game_media_or_domain_specific_kernel_enum
    - path_URL_filename_or_digest_as_logical_artifact_id
    - authorization_from_ContentRef_knowledge_alone

source_contract:
  every_source_is_Project_scoped: true
  represent_exactly_where_applicable:
    - Git_repository_plus_commit_and_tree
    - exact_file_ContentRef
    - database_or_source_revision
    - URL_or_object_identity_plus_retrieval_timestamp_when_no_exact_remote_version_exists
  prohibit:
    - mutable_branch_alone
    - mutable_path_alone
    - latest_object_without_exact_version_or_retrieval_evidence
    - cross_Project_source_without_future_explicit_sharing

derivation_contract:
  generic: true
  produced_Artifact_may_reference:
    - exact_source_ArtifactRef
    - exact_source_ContentRef
    - exact_SourceRef
    - producing_RunRef
    - future_Node_reference_when_interface_exists
  preserve_examples:
    - editable_source_to_export
    - source_tree_to_build_Artifact
    - copied_content_without_overwriting_provenance
  require:
    - exact_Project_scope
    - immutable_source_and_output_identity
    - append_only_durable_derivation
    - no_cross_Project_derivation

immutability:
  require:
    - bound_ContentRef_never_changes_in_place
    - bound_source_and_derivation_provenance_never_changes_in_place
    - material_change_creates_next_Artifact_revision
    - old_Artifact_revision_remains_readable_and_digest_stable
    - revisions_are_monotonic_and_gap_free_per_logical_Artifact
    - restart_preserves_all_verified_revisions_and_derivations
  prohibit:
    - UPDATE_or_DELETE_of_existing_Artifact_revision
    - UPDATE_or_DELETE_of_existing_derivation
    - silent_rebinding_to_different_bytes

project_isolation:
  require:
    - exact_Project_scope_on_every_Artifact_Source_and_derivation_query
    - same_ContentRef_may_back_distinct_Alpha_and_Beta_Artifacts
    - Artifact_ID_or_ContentRef_knowledge_does_not_grant_access
    - cross_Project_Artifact_source_or_derivation_binding_fails_privately
  quarantine_rule:
    QuarantineRef_is_ArtifactRef: false
    QuarantineRef_is_ContentRef: false
    identical_digest_grants_active_authority: false

task_and_run_integration:
  require:
    - Task_inputs_can_bind_exact_authorized_Artifact_Source_or_Content_identity
    - Runs_can_bind_or_record_exact_output_Artifact_Content_identity
    - expected_Task_revision_and_digest_mismatch_fails_closed
    - stale_Run_owner_or_fence_cannot_publish_authoritative_Artifact_output
  preserve:
    - P0_04_exact_Task_input_semantics
    - P0_05_assertCurrentRunAuthority_seam

persistence:
  require:
    - durable_Artifact_revisions
    - durable_ContentRef_bindings
    - durable_SourceRef_bindings
    - durable_ArtifactDerivation_records
    - exact_Project_scope_and_foreign_identity_constraints
    - append_only_update_delete_guards
    - record_digest_and_relationship_integrity_validation
    - atomic_initial_creation
    - atomic_new_revision_and_derivation_binding
    - restart_round_trip
    - no_half_created_revision_or_provenance
  schema_change:
    permitted_only_when_required_for_P0_06: true
    must_be_reported_exactly: true

failure_behavior:
  fail_closed_on:
    - malformed_ArtifactRef_ContentRef_or_SourceRef
    - missing_or_unauthorized_Project
    - digest_size_or_media_type_mismatch
    - nonexistent_source_Artifact_or_Run
    - expected_Task_revision_or_digest_mismatch
    - stale_Run_owner_or_fence
    - cross_Project_Artifact_source_or_derivation
    - QuarantineRef_masquerade
    - immutable_revision_conflict
    - persisted_integrity_or_relationship_mismatch
  preserve:
    - durable_evidence
    - real_failure_cause
  prohibit:
    - fabricated_success
    - fabricated_missing_facts
    - mocked_unavailable_storage_reported_as_real

concurrency_and_recovery:
  current_reality:
    Graph_Scheduler_and_resource_model_present: false
    do_not_fabricate_missing_later_interfaces: true
  require:
    - real_transactional_concurrency_in_existing_durable_database
    - independent_nonconflicting_Artifact_creation_can_complete
    - one_durable_winner_for_conflicting_same_revision
    - restart_preserves_verified_Artifact_and_derivation_history
    - stale_Run_authority_cannot_publish_or_replace_output_identity

required_test_matrix:
  - id: T01
    prove: exact_bytes_produce_expected_SHA_256_size_and_media_type_ContentRef
  - id: T02
    prove: changed_bytes_produce_changed_ContentRef
  - id: T03
    prove: identical_bytes_produce_equal_ContentRef_but_distinct_logical_Artifacts
  - id: T04
    prove: identical_bytes_across_Projects_preserve_separate_Artifact_authorization
  - id: T05
    prove: cross_Project_Artifact_source_and_derivation_attempts_fail_privately
  - id: T06
    prove: generic_derivation_chain_preserves_exact_source_and_output_identity
  - id: T07
    prove: immutable_content_or_provenance_change_creates_new_revision_and_preserves_old
  - id: T08
    prove: exact_Git_repository_commit_and_tree_SourceRef_round_trips
  - id: T09
    prove: mutable_branch_or_path_alone_is_rejected_as_exact_source
  - id: T10
    prove: QuarantineRef_cannot_masquerade_as_ArtifactRef_or_ContentRef
  - id: T11
    prove: physical_path_location_change_does_not_change_Artifact_or_ContentRef
  - id: T12
    prove: Task_input_can_bind_exact_authorized_Artifact_Source_or_Content_identity
  - id: T13
    prove: current_Run_authority_can_publish_exact_output_identity
  - id: T14
    prove: stale_Run_fence_and_Task_digest_mismatch_cannot_publish_output
  - id: T15
    prove: digest_size_and_expected_content_mismatch_fail_closed
  - id: T16
    prove: update_delete_tamper_and_partial_transaction_fail_closed
  - id: T17
    prove: restart_preserves_Artifact_revisions_sources_and_derivations
  - id: T18
    prove: no_storage_provider_hardware_or_domain_specific_kernel_coupling

kpi:
  artifact_without_project_scope: 0
  digest_mismatches_accepted: 0
  artifact_content_identity_conflation: 0
  cross_project_derivations: 0
  immutable_artifacts_silently_mutated: 0

implementation_method:
  - verify_exact_P0_05_remote_handoff
  - inspect_exact_current_source_and_accepted_interfaces
  - write_failure_first_tests_for_each_identity_isolation_and_provenance_boundary
  - implement_minimum_complete_P0_06
  - integrate_exact_Task_inputs_and_fenced_Run_outputs_without_later_architecture
  - run_focused_tests
  - run_relevant_P0_01_through_P0_05_regressions
  - run_strict_typecheck
  - build_and_inspect_actual_package_artifact
  - inspect_persistence_schema_indexes_triggers_foreign_keys_and_dependency_boundaries

publication:
  when_implementation_complete:
    - record_source_commit
    - commit_coherent_P0_06_result
    - push_main
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
    - replace_04_with_exact_P0_07_packet
    - close_P0_06_before_opening_P0_07
  continue_numbered_prompts_one_at_a_time: true
  broad_real_historical_mining: false
```
