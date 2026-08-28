# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P0-02
  global_number: 2
  phase: P0
  title: Universal Project Namespace and Isolation Contract
  state: READY_AFTER_P0_01_DURABLE_CLOSE
  exact_prompt:
    title: 02_P0-02_Universal_Project_Namespace_and_Isolation_Contract.md.docx
    drive_id: 1aINglpjh2qSuRbPrNT2dkTaBRRWNhLAAhriWTQ-kGwk
    canonical_text_sha256: 2ee7a74cdb4f5f7b62c7b767eb85150be243f89f4536c7a89bc30bf1b0a86657
  numbered_predecessor:
    id: P0-01
    result_commit: fa442745b73e02cc2cd67ef0c029973de06bb773
    result_tree: 840c45a3cf04c28407e08e5c7e51f11d61e0dadb
    remote_readback: VERIFIED
  numbered_successor: P0-03

goal:
  establish:
    - small_durable_Project_primitive
    - universal_Project_namespace
    - reusable_ProjectScoped_access_and_persistence_contract
  guarantee:
    - project_identity_is_opaque_stable_and_immutable
    - namespace_is_an_authorization_and_data_isolation_boundary
    - project_scope_is_enforced_at_persistence_and_service_boundaries
    - quarantine_is_not_an_ordinary_Project

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
    - P0_01_exact_remote_handoff
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reuse_valid_P0_01_implementation_and_results
    - reconcile_existing_equivalent_interfaces_by_semantics
    - missing_handoff_paperwork_is_not_a_blocker_when_exact_source_is_observable

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P0_02_canonical_prompt
    - P0_01_result_commit_and_required_interfaces
    - directly_touched_repository_files
  conditional:
    - 00_BIELLA_PROJECT_OPERATING_CONTRACT.md
    - BIELLA_PROJECT_KNOWLEDGE_SOURCE.md
    - 02_BIELLA_ENGINE_FINAL_MIGRATION_PLAN_2026-08-27.md
    - 05_BIELLA_PROMPT_INDEX.yaml
    - 06_BIELLA_SOURCE_EVIDENCE_MAP.yaml
  prohibited_by_default:
    - other_49_unopened_prompt_bodies
    - large_real_MiniTZ_backup
    - inactive_legacy_reuse_contract
    - unrelated_website_work
    - broad_historical_recovery_files
    - broad_Drive_GitHub_filesystem_audits

dependencies:
  P0_01:
    result_commit: fa442745b73e02cc2cd67ef0c029973de06bb773
    result_tree: 840c45a3cf04c28407e08e5c7e51f11d61e0dadb
    required_semantics:
      - clean_Biella_package_boundary
      - quarantine_isolation
      - active_runtime_has_no_raw_quarantine_dependency
    quarantine_rule:
      ordinary_Project_storage: forbidden
      normal_Project_listing_search_context_exposure: forbidden

scope:
  in:
    - opaque_Project_identity
    - validated_unique_namespace
    - bounded_display_metadata_and_configuration_references
    - reusable_ProjectScoped_access_contract
    - Project_scoped_persistence_queries
    - atomic_Project_creation
    - stable_identity_across_metadata_updates
    - restart_durability
    - explicit_Project_deletion_retention_behavior
    - Alpha_Beta_isolation_attack_matrix
  out:
    - Task_implementation
    - Run_implementation
    - Artifact_implementation_beyond_minimum_isolation_fixture
    - Project_Memory_implementation
    - routing
    - domain_concepts
    - provider_model_GPU_engine_fields
    - historical_donor_roles
    - quarantine_as_Project
    - P0_03_or_later_prompt_implementation

required_interfaces:
  exact:
    - Project
    - ProjectRef
    - ProjectScoped
  ProjectScoped_semantics:
    - access_contract
    - persistence_contract
    - every_scoped_record_belongs_to_exactly_one_Project
  rule:
    accepted_existing_semantic_equivalent_may_be_mapped: true
    do_not_duplicate_architecture_due_to_name_difference: true

project_contract:
  required:
    - stable_immutable_project_id
    - validated_unique_namespace
    - mutable_display_metadata_without_identity_change
    - bounded_configuration_refs
    - data_policy_ref_when_implemented
    - artifact_namespace_ref_when_needed_for_isolation_proof
    - created_at
    - updated_at
  prohibited_universal_fields:
    - preferred_Godot_Unity_or_Unreal
    - OpenAI_or_other_provider
    - H100_or_other_worker
    - game_or_3D_mode
    - fixed_coding_agent
    - historical_legacy_donor_role

namespace_semantics:
  authorization_boundary: true
  data_isolation_boundary: true
  knowing_foreign_identifier_grants_access: false
  foreign_identifiers_include:
    - Artifact_ID
    - Task_ID
    - Run_ID
    - Graph_ID
    - database_connection_ID
    - object_digest
    - memory_key
  enforce_at:
    - persistence_queries
    - service_boundaries
    - API_boundaries_where_present
    - reference_binding

atomic_creation:
  require:
    - no_half_initialized_Project
    - namespace_and_required_roots_commit_together
    - injected_failure_rolls_back_every_partial_record
    - restart_preserves_committed_Project

two_project_proof:
  projects:
    - Alpha
    - Beta
  similar_human_readable_record_names: required
  prove_Beta_cannot:
    - read_Alpha_scoped_record_by_ID
    - update_Alpha_scoped_record
    - delete_Alpha_scoped_record
    - use_Alpha_Artifact_namespace
    - bind_Alpha_data_to_Beta_scope
    - resolve_Alpha_scoped_configuration
    - infer_access_from_shared_physical_content_digest
  prove:
    - Alpha_and_Beta_coexist
    - ordinary_independent_operations_succeed
    - both_remain_independently_addressable_after_restart

fail_closed:
  reject:
    - nonexistent_Project
    - malformed_namespace
    - duplicate_namespace
    - cross_Project_read
    - cross_Project_write
    - cross_Project_update
    - cross_Project_delete
    - cross_Project_reference_binding
    - cross_Project_configuration_resolution
    - quarantine_binding_as_Project_data
    - partial_Project_creation
  error_privacy:
    - identify_technical_scope_mismatch
    - do_not_leak_foreign_Project_private_payload
    - do_not_leak_more_existence_information_than_contract_permits

required_test_matrix:
  - id: T01
    prove: unique_Project_IDs_and_namespaces_for_Alpha_and_Beta
  - id: T02
    prove: duplicate_namespace_rejected
  - id: T03
    prove: malformed_namespace_rejected
  - id: T04
    prove: ProjectScoped_persistence_query_requires_Project_identity
  - id: T05
    prove: Beta_cannot_read_Alpha_record_by_ID
  - id: T06
    prove: Beta_cannot_write_or_update_Alpha_record
  - id: T07
    prove: Beta_cannot_delete_Alpha_record
  - id: T08
    prove: Alpha_reference_cannot_bind_to_Beta_scope
  - id: T09
    prove: Beta_cannot_resolve_Alpha_configuration
  - id: T10
    prove: Beta_cannot_use_Alpha_Artifact_namespace
  - id: T11
    prove: shared_physical_content_digest_does_not_collapse_authorization
  - id: T12
    prove: quarantine_is_not_listed_searched_or_bound_as_Project
  - id: T13
    prove: Project_metadata_update_preserves_project_id
  - id: T14
    prove: injected_creation_failure_rolls_back_without_partial_Project
  - id: T15
    prove: restart_preserves_Alpha_and_Beta
  - id: T16
    prove: deletion_retention_contract_does_not_orphan_or_cross_link_records

kpi:
  cross_project_reads: 0
  cross_project_writes: 0
  cross_project_reference_bindings: 0
  project_records_missing_scope: 0
  namespace_collisions_accepted: 0

implementation_method:
  - verify_exact_P0_01_remote_handoff
  - inspect_exact_current_source_and_accepted_interfaces
  - write_failure_first_tests_for_each_Project_isolation_boundary
  - implement_minimum_complete_P0_02
  - run_focused_tests
  - run_relevant_regression_gate
  - run_strict_typecheck
  - build_and_inspect_actual_package_artifact
  - inspect_persistence_schema_indexes_and_dependency_boundaries

publication:
  when_implementation_complete:
    - record_source_commit
    - commit_coherent_P0_02_result
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
    - replace_04_with_exact_P0_03_packet
    - close_P0_02_before_opening_P0_03
  continue_numbered_prompts_one_at_a_time: true
  broad_real_historical_mining: false
```
