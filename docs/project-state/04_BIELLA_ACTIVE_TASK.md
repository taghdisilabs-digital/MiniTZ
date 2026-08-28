# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P0-03
  global_number: 3
  phase: P0
  title: Provider-Neutral Capability Contract
  state: READY_AFTER_P0_02_DURABLE_CLOSE
  exact_prompt:
    title: 03_P0-03_Provider_Neutral_Capability_Contract.md.docx
    drive_id: 1HaRjLqtN9YgNKRJHm7VLIay80_o0qQVJeFXYeyvoJFs
    canonical_text_sha256: 83ca2cc81759b9e3330d53fdd70e7ac0a4bfa7a918d8dc52348768cd8e35772f
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P0-02
    result_commit: 2847543e0b3f9bac04e0e879e4b81f748cab712c
    result_tree: deedf652f4eafc16b901ea535a4d0adf0663a212
    remote_readback: VERIFIED
  numbered_successor: P0-04

goal:
  establish:
    - extensible_versioned_semantic_Capability_registry
    - provider_neutral_Capability_identity
    - generic_input_output_and_side_effect_contracts
  guarantee:
    - Capability_describes_what_is_needed_not_who_or_what_executes_it
    - semantic_existence_is_independent_from_current_implementation_or_resource_availability
    - arbitrary_future_Capability_registration_requires_no_kernel_enum_switch_or_schema_edit
    - historical_versions_are_preserved_instead_of_destructively_redefined

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
    - P0_02_exact_remote_handoff
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reuse_valid_P0_01_and_P0_02_implementation_and_results
    - reconcile_existing_equivalent_interfaces_by_semantics
    - missing_handoff_paperwork_is_not_a_blocker_when_exact_source_is_observable

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P0_03_canonical_prompt
    - P0_02_result_commit_and_required_interfaces
    - directly_touched_repository_files
  conditional:
    - 00_BIELLA_PROJECT_OPERATING_CONTRACT.md
    - BIELLA_PROJECT_KNOWLEDGE_SOURCE.md
    - 02_BIELLA_ENGINE_FINAL_MIGRATION_PLAN_2026-08-27.md
    - 05_BIELLA_PROMPT_INDEX.yaml
    - 06_BIELLA_SOURCE_EVIDENCE_MAP.yaml
  prohibited_by_default:
    - other_48_unopened_prompt_bodies
    - large_real_MiniTZ_backup
    - inactive_legacy_reuse_contract
    - unrelated_website_work
    - broad_historical_recovery_files
    - broad_Drive_GitHub_filesystem_audits

dependencies:
  P0_01:
    result_commit: fa442745b73e02cc2cd67ef0c029973de06bb773
    required_semantics:
      - clean_Biella_package_boundary
      - quarantine_isolation
      - active_runtime_has_no_raw_quarantine_dependency
  P0_02:
    result_commit: 2847543e0b3f9bac04e0e879e4b81f748cab712c
    result_tree: deedf652f4eafc16b901ea535a4d0adf0663a212
    required_semantics:
      - stable_opaque_Project_identity
      - authenticated_Project_scope
      - Project_configuration_is_scoped_and_cannot_mutate_global_semantics
    quarantine_rule:
      Capability_registry_dependency_on_raw_quarantine: forbidden

scope:
  in:
    - namespaced_string_Capability_identity
    - explicit_semantic_version_or_revision
    - immutable_contract_identity
    - bounded_description
    - generic_input_contract
    - generic_output_contract
    - side_effect_characteristics
    - deprecation_and_supersession_history
    - durable_registry_persistence
    - atomic_registration
    - restart_durability
    - arbitrary_future_registration
    - Project_preference_non_mutation_proof
  out:
    - provider_registry
    - model_registry
    - tool_registry
    - worker_registry
    - hardware_or_GPU_registry
    - implementation_or_adapter_registry
    - Resource_availability
    - provider_or_model_selection
    - compute_placement
    - scheduler_ranking
    - routing
    - Task_Run_or_Graph_kernel_implementation
    - bulk_registration_of_future_P3_capabilities
    - historical_donor_roles
    - P0_04_or_later_prompt_implementation

required_interfaces:
  exact:
    - Capability
    - CapabilityRef
    - CapabilityRegistry
  rule:
    accepted_existing_semantic_equivalent_may_be_mapped: true
    do_not_duplicate_architecture_due_to_name_difference: true

capability_contract:
  required_semantics:
    - stable_namespaced_string_identity
    - explicit_version_or_revision
    - immutable_semantic_contract_per_identity_and_version
    - bounded_human_description
    - generic_input_contract_or_schema_reference
    - generic_output_contract_or_schema_reference
    - side_effect_characteristics
    - optional_deprecation_or_supersession_metadata
    - timezone_aware_created_at
  representative_examples:
    - software.debug
    - 3d.model
    - model.infer
    - browser.navigate
    - render.frame
  prohibited_core_fields:
    - provider
    - model
    - tool
    - worker
    - GPU
    - hardware
    - command
    - agent_role
    - deployment_health
    - resource_availability
    - Project_preference

identity_and_versioning:
  identity_components:
    - namespace
    - name
    - version_or_revision
  required:
    - stable_CapabilityRef
    - unique_identity_and_version
    - same_version_same_contract_may_be_idempotent
    - same_version_conflicting_contract_fails_closed
    - new_version_with_changed_contract_is_allowed
    - old_versions_remain_readable_after_new_version
    - supersession_does_not_delete_predecessor
    - deprecation_does_not_erase_contract_history
  prohibited:
    - destructive_meaning_change_under_same_ref
    - closed_source_code_Capability_enum
    - central_switch_edit_for_new_namespace

extensible_registration:
  data_driven: true
  arbitrary_future_examples:
    - quantum.simulate
    - robotics.plan
    - biology.sequence_analyze
  require:
    - previously_unknown_namespace_and_name_register_through_normal_registry_API
    - no_kernel_source_edit_for_future_registration
    - no_Task_Run_Graph_schema_migration_for_future_registration

generic_io_contracts:
  semantic_not_physical: true
  may_describe:
    - semantic_input_roles
    - semantic_output_roles
    - schema_or_content_references
  require:
    - validation_where_contract_is_applicable
    - immutable_round_trip
    - no_domain_specific_kernel_union

side_effect_semantics:
  purpose:
    - express_possible_mutation_or_external_effect_requirements
    - allow_later_Task_Graph_validation_to_detect_impossible_escalation
  authorization_rule:
    registering_mutating_Capability_grants_external_side_effect_authority: false
  routing_rule:
    side_effect_metadata_selects_provider_worker_or_resource: false

availability_separation:
  require:
    - Capability_existence_survives_zero_implementations
    - Capability_existence_survives_zero_available_resources
    - unavailable_execution_is_reported_separately_when_that_layer_exists
  example:
    capability: render.frame
    semantic_existence_when_no_renderer_or_GPU_is_available: true
  prohibit:
    - deleting_Capability_due_to_resource_shortage
    - embedding_current_health_or_capacity_in_Capability
    - fabricating_Resource_or_adapter_availability

project_isolation:
  global_Capability_semantics_are_universal: true
  Project_may_reference_or_prefer_a_Capability_without_mutating_it: true
  reject:
    - Project_specific_contract_overwrite
    - Project_specific_version_redefinition
    - Project_specific_deletion_of_global_Capability
    - Project_capability_reference_with_authority_escalation

persistence:
  require:
    - durable_Capability_versions
    - durable_contract_identity
    - database_uniqueness_for_identity_and_version
    - atomic_registration
    - restart_round_trip
    - immutable_historical_versions
    - no_half_registered_contract
  schema_change:
    permitted_only_when_required_for_Capability_registry: true
    must_be_reported_exactly: true

failure_behavior:
  fail_closed_on:
    - malformed_namespace_or_name
    - malformed_version
    - malformed_generic_contract
    - malformed_side_effect_metadata
    - duplicate_identity_version_with_conflicting_contract
    - nonexistent_CapabilityRef
    - scope_identity_authority_or_integrity_mismatch
    - attempted_destructive_history_mutation
    - Project_specific_global_semantic_mutation
  evidence:
    preserve_durable_failure_cause: true
    do_not_fabricate_success_or_missing_facts: true
  privacy:
    do_not_leak_unrelated_Project_private_payload: true

concurrency_and_recovery:
  current_reality:
    Graph_Scheduler_and_Resource_models_may_not_exist_yet: true
    do_not_fabricate_them_for_P0_03: true
  registry_require:
    - transactionally_serialize_conflicting_registration
    - allow_independent_nonconflicting_registration
    - restart_preserves_verified_records
    - stale_or_conflicting_writers_cannot_replace_immutable_contract

required_test_matrix:
  - id: T01
    prove: register_software_debug_namespaced_version
  - id: T02
    prove: register_3d_model_namespaced_version
  - id: T03
    prove: register_previously_unknown_future_Capability_without_kernel_edit
  - id: T04
    prove: same_version_conflicting_contract_rejected
  - id: T05
    prove: new_version_with_changed_contract_succeeds_and_old_version_remains
  - id: T06
    prove: no_provider_model_hardware_tool_worker_or_agent_role_is_required
  - id: T07
    prove: Capability_exists_when_all_implementations_and_resources_are_unavailable
  - id: T08
    prove: generic_input_output_contract_validation_and_round_trip
  - id: T09
    prove: side_effect_metadata_round_trip_without_authorization
  - id: T10
    prove: deprecation_and_supersession_do_not_erase_history
  - id: T11
    prove: Project_preference_cannot_mutate_global_Capability
  - id: T12
    prove: duplicate_identical_registration_is_idempotent_and_restart_durable
  - id: T13
    prove: malformed_or_nonexistent_identity_fails_closed
  - id: T14
    prove: concurrent_conflicting_registration_has_one_durable_winner

kpi:
  new_capability_requires_kernel_change: 0
  closed_capability_enum_required: 0
  provider_fields_required: 0
  hardware_fields_required: 0
  capability_deleted_due_to_resource_shortage: 0

implementation_method:
  - verify_exact_P0_02_remote_handoff
  - inspect_exact_current_source_and_accepted_interfaces
  - write_failure_first_tests_for_each_Capability_contract_boundary
  - implement_minimum_complete_P0_03
  - run_focused_tests
  - run_relevant_P0_01_and_P0_02_regressions
  - run_strict_typecheck
  - build_and_inspect_actual_package_artifact
  - inspect_persistence_schema_indexes_and_dependency_boundaries
  - verify_no_closed_enum_provider_resource_or_Project_semantic_coupling

publication:
  when_implementation_complete:
    - record_source_commit
    - commit_coherent_P0_03_result
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
    - replace_04_with_exact_P0_04_packet
    - close_P0_03_before_opening_P0_04
  continue_numbered_prompts_one_at_a_time: true
  broad_real_historical_mining: false
```
