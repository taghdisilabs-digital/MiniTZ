# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P0-04
  global_number: 4
  phase: P0
  title: Universal Typed Task Contract
  state: READY_AFTER_P0_03_DURABLE_CLOSE
  exact_prompt:
    title: 04_P0-04_Universal_Typed_Task_Contract.md.docx
    drive_id: 1weEvFdehM9SuMoCn8bTOwZ1ADO0vYyO319aDPDAeqaE
    canonical_text_sha256: 35d6054325de7df70c609703dc2cfa4b5c9f99ba99cddd81d455777055833947
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P0-03
    result_commit: 4288c792d8f5c1fe12ffd3af47deb7d3aab5d9f1
    result_tree: 26c62bdd4bf89f3c8cb4a604a89cd6193ed35068
    remote_readback: VERIFIED
  numbered_successor: P0-05

goal:
  establish:
    - durable_universal_typed_Task_primitive
    - immutable_Task_revisions
    - deterministic_canonical_Task_digest
    - exact_authorized_Task_inputs
  guarantee:
    - every_Task_belongs_to_exactly_one_Project
    - Task_expresses_desired_outcome_and_constraints_not_execution_topology
    - material_edits_create_new_revisions_without_mutating_history
    - raw_QuarantineRef_is_never_an_active_Task_input

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
    - P0_03_exact_remote_handoff
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reuse_valid_P0_01_through_P0_03_implementation_and_results
    - reconcile_existing_equivalent_interfaces_by_semantics
    - missing_handoff_paperwork_is_not_a_blocker_when_exact_source_is_observable

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P0_04_canonical_prompt
    - P0_02_Project_interfaces
    - P0_03_Capability_interfaces
    - P0_01_quarantine_and_active_runtime_boundary
    - directly_touched_repository_files
  conditional:
    - 00_BIELLA_PROJECT_OPERATING_CONTRACT.md
    - BIELLA_PROJECT_KNOWLEDGE_SOURCE.md
    - 02_BIELLA_ENGINE_FINAL_MIGRATION_PLAN_2026-08-27.md
    - 05_BIELLA_PROMPT_INDEX.yaml
    - 06_BIELLA_SOURCE_EVIDENCE_MAP.yaml
  prohibited_by_default:
    - other_47_unopened_prompt_bodies
    - large_real_MiniTZ_backup
    - inactive_legacy_reuse_contract
    - unrelated_website_work
    - broad_historical_recovery_files
    - broad_Drive_GitHub_filesystem_audits

dependencies:
  P0_01:
    result_commit: fa442745b73e02cc2cd67ef0c029973de06bb773
    required_semantics:
      - QuarantineRef_is_migration_only
      - active_runtime_rejects_raw_quarantine
  P0_02:
    result_commit: 2847543e0b3f9bac04e0e879e4b81f748cab712c
    required_interfaces:
      - Project
      - ProjectRef
      - ProjectAccess
      - ProjectScoped
    required_semantics:
      - authenticated_Project_scope
      - exact_Project_binding
      - cross_Project_access_fails_closed
  P0_03:
    result_commit: 4288c792d8f5c1fe12ffd3af47deb7d3aab5d9f1
    result_tree: 26c62bdd4bf89f3c8cb4a604a89cd6193ed35068
    required_interfaces:
      - Capability
      - CapabilityRef
      - CapabilityRegistry
    required_semantics:
      - immutable_versioned_Capability_identity
      - provider_neutral_semantic_contract
      - append_only_history

scope:
  in:
    - opaque_stable_Task_identity
    - exact_Project_ownership
    - positive_immutable_revision_number
    - extensible_task_type
    - bounded_objective
    - exact_TaskInputRef_collection
    - required_CapabilityRef_collection
    - generic_output_contract
    - generic_constraints
    - explicit_side_effect_authority
    - data_and_egress_policy_references
    - evidence_requirements
    - acceptance_criteria
    - generic_resource_hints
    - quality_latency_and_cost_constraints
    - idempotency_key
    - created_at
    - canonical_digest
    - durable_revision_and_idempotency_persistence
    - atomic_creation_and_revision
    - restart_durability
  out:
    - Run_implementation
    - attempts_leases_or_fencing
    - Graph_implementation
    - Scheduler_or_Resource_implementation
    - provider_selection
    - model_selection
    - compute_placement
    - fixed_agent_topology
    - maker_critic_validator_chain
    - fixed_pipeline
    - domain_specific_Task_subclasses
    - human_approval_bureaucracy
    - future_sharing_mechanism
    - P0_05_or_later_prompt_implementation

required_interfaces:
  exact:
    - Task
    - TaskRef
    - TaskInputRef
  required_service_semantics:
    - Task_revision_creation
    - deterministic_canonicalization
    - durable_read
    - idempotent_submission
  accepted_name:
    - TaskRevisionService
  rule:
    accepted_existing_semantic_equivalent_may_be_mapped: true
    do_not_duplicate_architecture_due_to_name_difference: true

task_contract:
  required:
    - stable_immutable_task_id
    - exactly_one_ProjectRef
    - positive_revision
    - extensible_task_type_string
    - bounded_objective
    - zero_or_more_valid_CapabilityRef_values
    - zero_or_more_exact_TaskInputRef_values
    - generic_output_contract
    - generic_constraints
    - explicit_side_effect_authority
    - evidence_requirements
    - acceptance_criteria
    - bounded_idempotency_key
    - timezone_aware_created_at
    - canonical_digest
  optional:
    - data_policy_ref
    - egress_policy_ref
    - resource_hints
    - quality_constraints
    - latency_constraints
    - cost_constraints
  prohibited_universal_fields:
    - provider
    - model_name
    - GPU
    - worker
    - fixed_agent_role
    - maker
    - critic
    - validator_chain
    - fixed_pipeline
    - game_engine

task_input_contract:
  require:
    - exact_immutable_identity
    - exactly_one_owning_ProjectRef
    - explicit_input_kind
    - stable_source_or_Artifact_reference
    - content_digest_or_immutable_revision_where_applicable
    - caller_Project_authorization_at_binding_boundary
  reject:
    - raw_QuarantineRef
    - ambiguous_latest_file
    - mutable_unversioned_path
    - malformed_identity
    - nonexistent_source
    - cross_Project_source_without_future_explicit_sharing
    - known_foreign_identifier_without_authority

capability_binding:
  require:
    - every_required_CapabilityRef_exists_in_durable_registry
    - exact_version_is_preserved
    - duplicate_semantically_irrelevant_order_is_canonicalized
  prohibit:
    - embedding_provider_or_resource_availability
    - mutating_Capability_semantics_from_Task
    - silently_resolving_unknown_or_latest_version

revision_semantics:
  immutable: true
  require:
    - revision_one_remains_byte_and_digest_stable_after_revision_two
    - material_change_creates_next_revision
    - same_task_id_is_preserved_across_revisions
    - revision_numbers_are_monotonic_and_gap_free_per_Task
    - prior_revisions_remain_readable_after_restart
  material_changes_include:
    - objective
    - task_type
    - input_refs
    - required_capabilities
    - output_contract
    - constraints
    - side_effect_authority
    - data_or_egress_policy
    - evidence_requirements
    - acceptance_criteria
    - resource_hints_or_requirements
    - quality_latency_or_cost_constraints
  prohibit:
    - UPDATE_of_existing_revision_semantics
    - deletion_of_prior_revision
    - same_revision_conflicting_contract

canonical_digest:
  deterministic: true
  require:
    - stable_field_ordering
    - stable_ordering_for_semantic_sets
    - explicit_null_and_absence_semantics
    - locale_independent_serialization
    - exact_Project_and_input_identity
    - nonfinite_number_rejection
    - repeated_reads_reproduce_same_canonical_representation_and_digest
    - equivalent_semantics_hash_identically
    - every_material_change_changes_digest
  exclude_as_nondeterministic_metadata:
    - created_at
  persisted_integrity:
    - semantic_digest
    - full_record_digest
    - append_only_database_guards

side_effect_authority:
  representative_values:
    - READ_ONLY
    - CANDIDATE_WRITE
    - PROJECT_WRITE
    - EXTERNAL_SIDE_EFFECT
  require:
    - explicit_value_on_every_Task
    - later_Graph_or_adapter_cannot_escalate_beyond_Task_authority
    - escalation_detection_seam_is_tested
  prohibit:
    - registration_itself_grants_external_credentials
    - human_approval_workflow_in_P0_04

idempotency:
  require:
    - scope_by_Project_and_idempotency_key
    - duplicate_same_semantics_returns_same_Task_revision
    - duplicate_conflicting_semantics_fails_closed
    - different_material_revision_is_not_collapsed
    - restart_preserves_deduplication_record

domain_neutrality:
  same_primitive_proof:
    software:
      intent: modify_exact_repository_revision_run_tests_produce_candidate
    three_d:
      intent: modify_or_create_exact_asset_scene_and_export_editable_interchange_output
  prohibit:
    - SoftwareTask
    - ThreeDTask
    - domain_specific_kernel_union

persistence:
  require:
    - durable_Task_revisions
    - durable_idempotency_records
    - canonical_digest_index
    - exact_Project_scope_on_every_query
    - atomic_initial_creation
    - atomic_new_revision_and_idempotency_binding
    - restart_round_trip
    - immutable_update_delete_guards
    - no_half_created_revision
  schema_change:
    permitted_only_when_required_for_Task_revision_service: true
    must_be_reported_exactly: true

failure_behavior:
  fail_closed_on:
    - malformed_TaskRef
    - missing_or_unauthorized_Project
    - malformed_or_cross_Project_TaskInputRef
    - raw_QuarantineRef_input
    - missing_or_invalid_CapabilityRef
    - nonfinite_or_malformed_structured_value
    - same_revision_conflicting_contract
    - idempotency_key_conflict
    - side_effect_authority_escalation
    - persisted_digest_or_record_integrity_mismatch
    - attempted_revision_update_or_delete
  error_privacy:
    - identify_technical_scope_or_contract_mismatch
    - do_not_leak_foreign_Project_private_payload
    - do_not_leak_more_existence_information_than_contract_permits

concurrency_and_recovery:
  current_reality:
    Graph_Scheduler_and_Resource_models_may_not_exist_yet: true
    do_not_fabricate_them_for_P0_04: true
  task_service_require:
    - transactionally_serialize_same_Task_revision_or_idempotency_key
    - allow_independent_nonconflicting_Task_creation
    - one_durable_winner_for_concurrent_conflicting_submission
    - restart_preserves_verified_revisions_and_deduplication
    - stale_or_conflicting_writer_cannot_replace_immutable_revision

required_test_matrix:
  - id: T01
    prove: create_and_read_minimal_valid_Task
  - id: T02
    prove: multi_Capability_Task_uses_exact_registered_versions
  - id: T03
    prove: TaskInputRef_binds_exact_authorized_Project_source
  - id: T04
    prove: cross_Project_input_binding_is_rejected_privately
  - id: T05
    prove: QuarantineRef_is_rejected_as_active_Task_input
  - id: T06
    prove: unknown_or_invalid_CapabilityRef_is_rejected
  - id: T07
    prove: canonical_digest_is_stable_across_semantically_irrelevant_order
  - id: T08
    prove: objective_input_output_side_effect_and_acceptance_changes_each_change_digest
  - id: T09
    prove: revision_two_preserves_revision_one_immutably
  - id: T10
    prove: output_contract_and_structured_fields_round_trip_after_restart
  - id: T11
    prove: identical_idempotent_duplicate_returns_same_revision
  - id: T12
    prove: conflicting_idempotent_duplicate_fails
  - id: T13
    prove: side_effect_escalation_detection_seam_fails_closed
  - id: T14
    prove: software_and_3D_intents_use_identical_Task_schema
  - id: T15
    prove: no_provider_model_GPU_worker_agent_critic_reviewer_pipeline_or_game_engine_fields
  - id: T16
    prove: nonfinite_or_malformed_structured_values_are_rejected
  - id: T17
    prove: direct_update_delete_and_digest_tampering_fail
  - id: T18
    prove: concurrent_conflicting_submission_has_one_durable_winner

kpi:
  unscoped_tasks: 0
  Task_revision_mutations: 0
  canonical_digest_instability: 0
  raw_quarantine_inputs_accepted: 0
  domain_specific_Task_variants: 0

implementation_method:
  - verify_exact_P0_03_remote_handoff
  - inspect_exact_current_source_and_accepted_interfaces
  - write_failure_first_tests_for_each_Task_contract_boundary
  - implement_minimum_complete_P0_04
  - run_focused_tests
  - run_relevant_P0_01_through_P0_03_regressions
  - run_strict_typecheck
  - build_and_inspect_actual_package_artifact
  - inspect_persistence_schema_indexes_triggers_and_dependency_boundaries
  - verify_no_provider_topology_domain_variant_or_raw_quarantine_coupling

publication:
  when_implementation_complete:
    - record_source_commit
    - commit_coherent_P0_04_result
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
    - replace_04_with_exact_P0_05_packet
    - close_P0_04_before_opening_P0_05
  continue_numbered_prompts_one_at_a_time: true
  broad_real_historical_mining: false
```
