# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P0-07
  global_number: 7
  phase: P0
  title: Immutable Revisioned Graph and Node Contracts
  state: READY_AFTER_P0_06_DURABLE_CLOSE
  exact_prompt:
    title: 07_P0-07_Immutable_Revisioned_Graph_and_Node_Contracts.md.docx
    drive_id: 1e3EA4_bjuhbdn2dlcsRHpXR0-6snMlY3bL_q8bgxNRU
    canonical_text_sha256: 6b3c67114e3ad15c8e5f75844202649d1d2aa02a69bca62795e5083d41b3e09e
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P0-06
    result_commit: 747a0b59a296890202be39128c455240d87274f2
    result_tree: 585ef429b55eed8c261d4af87efe297e2c1a9c67
    remote_readback: VERIFIED
  numbered_successor: P0-08

goal:
  establish:
    - dynamic_immutable_revisioned_Project_scoped_DAG
    - productive_extensible_Node_contract
    - structured_exact_NodeInputBinding
    - deterministic_DAG_validation_topological_and_ready_set_APIs
    - exact_Project_Task_Run_and_Graph_revision_binding
    - canonical_Graph_semantic_and_record_digests
  guarantee:
    - Graph_revision_N_is_never_mutated_by_replanning
    - parallel_siblings_remain_explicitly_parallel
    - Task_side_effect_authority_cannot_be_escalated_by_Graph_or_Node
    - no_mandatory_global_pipeline_or_closed_executor_enum

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
    - P0_06_exact_remote_handoff
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reuse_valid_earlier_implementation_and_results
    - reconcile_existing_equivalent_interfaces_by_semantics
    - missing_handoff_paperwork_is_not_a_blocker_when_exact_source_is_observable

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P0_07_canonical_prompt
    - P0_02_Project_interfaces
    - P0_03_Capability_interfaces
    - P0_04_Task_and_TaskInputRef_interfaces
    - P0_05_Run_and_fencing_interfaces
    - P0_06_Artifact_Source_and_Content_identity_interfaces
    - directly_touched_repository_files
  conditional:
    - current_Biella_project_instructions
    - earlier_accepted_contracts_actually_used_by_this_task
  prohibited_by_default:
    - other_44_unopened_prompt_bodies
    - large_real_MiniTZ_backup
    - inactive_legacy_reuse_contract
    - unrelated_website_work
    - broad_historical_recovery_files
    - broad_Drive_GitHub_filesystem_audits

dependencies:
  P0_02:
    result_commit: 2847543e0b3f9bac04e0e879e4b81f748cab712c
    required_interfaces:
      - Project
      - ProjectRef
      - ProjectAccess
    required_semantics:
      - authenticated_Project_scope
      - cross_Project_access_fails_closed
  P0_03:
    result_commit: 4288c792d8f5c1fe12ffd3af47deb7d3aab5d9f1
    required_interfaces:
      - CapabilityRef
      - CapabilityRegistry
    required_semantics:
      - exact_extensible_versioned_Capability_identity
      - Capability_existence_is_not_runtime_availability
  P0_04:
    result_commit: 9b28ccf93c4cb8edd771f474903bcfa5e7592b1b
    required_interfaces:
      - Task
      - TaskRef
      - TaskInputRef
      - TaskRevisionService
    required_semantics:
      - exact_immutable_Task_revision_and_digest
      - bounded_side_effect_authority
      - structured_inputs_outputs_constraints_and_evidence
  P0_05:
    result_commit: 8f53a1fd641ad46c893239cd8279f310432086bc
    required_interfaces:
      - Run
      - RunRef
      - RunService
    required_semantics:
      - exact_Project_and_Task_binding
      - immutable_Run_identity_and_state_history
      - current_fenced_authority
  P0_06:
    result_commit: 747a0b59a296890202be39128c455240d87274f2
    result_tree: 585ef429b55eed8c261d4af87efe297e2c1a9c67
    required_interfaces:
      - ArtifactRef
      - ContentRef
      - SourceRef
    required_semantics:
      - exact_Project_scoped_input_and_output_identity
      - immutable_Artifact_revision_and_provenance
      - physical_storage_location_is_not_semantic_identity

scope:
  in:
    - opaque_Project_scoped_GraphRef_and_NodeRef
    - immutable_positive_Graph_revision
    - exact_Project_Task_revision_digest_and_Run_binding
    - productive_Node_with_extensible_executor_kind
    - exact_required_CapabilityRef_values
    - dependency_NodeRef_values
    - structured_NodeInputBinding_to_Task_Artifact_Source_Content_or_prior_Node_output
    - output_contract_conditions_side_effects_resource_hints_and_evidence
    - dependency_existence_self_cycle_cycle_and_duplicate_validation
    - deterministic_topological_order_and_ready_set
    - fan_out_fan_in_and_conditional_optional_branches
    - canonical_Graph_digest_and_integrity_record
    - optional_compiler_identity_and_version_provenance
    - immutable_replanning_as_Graph_revision_N_plus_1
    - durable_atomic_persistence_restart_and_concurrency
    - Run_active_Graph_revision_binding_required_by_this_prompt
  out:
    - provider_model_worker_or_hardware_selection
    - resource_scheduler_or_capacity_allocator
    - remote_execution_or_queue_dispatch
    - lifecycle_operations_as_mandatory_productive_Nodes
    - fixed_maker_critic_validator_pipeline
    - physical_object_storage
    - later_numbered_prompt_implementation

required_interfaces:
  exact:
    - Graph
    - GraphRef
    - Node
    - NodeRef
    - NodeInputBinding
  required_APIs:
    - DAG_validator
    - deterministic_topological_order
    - deterministic_ready_set
  accepted_service_name:
    - GraphService
  rule:
    accepted_existing_semantic_equivalent_may_be_mapped: true
    do_not_duplicate_architecture_due_to_name_difference: true

graph_contract:
  exact_binding:
    - ProjectRef
    - TaskRef
    - exact_Task_canonical_digest
    - RunRef
    - positive_Graph_revision
  require:
    - opaque_stable_graph_id
    - immutable_Node_collection
    - canonical_semantic_digest
    - durable_record_digest
    - timezone_aware_created_at
    - optional_prior_GraphRef_for_replanning_provenance
    - optional_compiler_identity_and_version_metadata
  prohibit:
    - provider_model_worker_or_hardware_as_required_kernel_identity
    - graph_digest_dependent_on_input_mapping_or_set_order
    - mutation_of_prior_Graph_revision
    - fixed_global_pipeline_shape

node_contract:
  require:
    - opaque_node_id_unique_within_exact_Graph_revision
    - exact_parent_GraphRef
    - extensible_executor_kind_string
    - exact_required_CapabilityRef_values
    - exact_dependency_NodeRef_values
    - structured_input_bindings
    - output_contract
    - condition_contract_where_applicable
    - side_effect_requirement
    - resource_hints
    - evidence_and_validation_requirements
  lifecycle_rule:
    WAIT_CANCEL_RECOVER_CHECKPOINT_FINALIZE_mandatory_productive_nodes: false
  prohibit:
    - closed_executor_kind_enum
    - implicit_provider_model_or_worker_affinity
    - Node_side_effect_requirement_stronger_than_Task_authority

node_input_binding:
  may_bind_exact:
    - TaskInputRef
    - ArtifactRef
    - SourceRef
    - ContentRef
    - prior_NodeRef_output_contract_key
  require:
    - exact_Project_scope
    - immutable_source_identity
    - bounded_structured_binding
  prohibit:
    - QuarantineRef
    - mutable_path_branch_or_latest_object_identity
    - cross_Project_reference_without_future_explicit_sharing

dag_validation:
  fail_before_execution_on:
    - duplicate_Node_identity
    - missing_dependency
    - self_dependency
    - direct_or_indirect_cycle
    - dependency_from_another_Graph_revision
    - cross_Project_Node_or_binding
    - Task_side_effect_authority_escalation
  deterministic:
    - topological_order_for_semantically_equal_Graphs
    - ready_set_for_equal_terminal_state_and_condition_inputs
  preserve:
    - parallel_siblings_without_artificial_edges
    - fan_out
    - fan_in_waits_for_all_required_dependencies
    - conditional_optional_branch_semantics

ready_set:
  inputs:
    - exact_Graph_revision
    - current_durable_Node_terminal_states
    - deterministic_condition_results
    - exact_Task_authority
  node_is_ready_when:
    - all_required_dependencies_succeeded_or_are_satisfied
    - condition_is_true_or_absent
    - Task_authority_permits_Node_side_effect_requirement
    - node_is_not_already_terminal
  later_not_P0_07:
    - provider_availability
    - resource_capacity_scheduling
    - worker_assignment

immutability_and_replanning:
  require:
    - Graph_revision_1_remains_readable_after_revision_2
    - revision_2_has_exact_prior_GraphRef
    - material_replan_changes_semantic_digest
    - revisions_are_monotonic_and_gap_free
    - Node_contracts_are_immutable_with_their_Graph_revision
    - restart_preserves_all_Graph_revisions_and_digests
  prohibit:
    - UPDATE_or_DELETE_of_Graph_revision_or_Node_contract
    - silent_Node_dependency_output_or_authority_rewrite

persistence:
  require:
    - durable_Graph_revisions
    - durable_Node_contracts
    - durable_dependency_and_input_bindings
    - durable_Graph_heads_and_prior_revision_provenance
    - exact_Project_Task_Run_and_digest_foreign_bindings
    - Run_active_Graph_revision_binding
    - append_only_update_delete_guards
    - record_digest_and_relationship_integrity_validation
    - atomic_initial_creation
    - atomic_new_revision_and_all_Node_bindings
    - restart_round_trip
    - no_half_created_Graph_or_Node_set
  schema_change:
    permitted_only_when_required_for_P0_07: true
    must_be_reported_exactly: true

failure_behavior:
  fail_closed_on:
    - malformed_GraphRef_NodeRef_or_NodeInputBinding
    - missing_or_unauthorized_Project
    - nonexistent_or_mismatched_Task_revision_or_digest
    - nonexistent_or_mismatched_Run
    - duplicate_missing_self_or_cyclic_dependency
    - cross_Graph_revision_or_cross_Project_binding
    - unknown_required_CapabilityRef
    - Task_side_effect_authority_escalation
    - immutable_revision_conflict
    - persisted_digest_relationship_or_head_mismatch
  preserve:
    - durable_evidence
    - real_failure_cause
  prohibit:
    - fabricated_success
    - fabricated_scheduler_resource_or_executor_availability

concurrency_and_recovery:
  current_reality:
    Graph_Scheduler_and_resource_model_present_before_P0_07: false
    do_not_fabricate_missing_later_interfaces: true
  require:
    - real_transactional_concurrency_in_existing_durable_database
    - independent_Graph_creation_can_complete
    - one_durable_winner_for_conflicting_same_revision
    - readers_observe_one_consistent_Graph_revision_snapshot
    - restart_preserves_verified_Graph_Node_and_binding_history
    - stale_Run_authority_cannot_replace_active_Graph_binding

required_test_matrix:
  - id: T01
    prove: one_Node_Graph_validates_persists_and_round_trips
  - id: T02
    prove: sequential_Graph_has_deterministic_topological_and_ready_order
  - id: T03
    prove: fan_out_siblings_become_ready_together_without_artificial_serialization
  - id: T04
    prove: fan_in_Node_waits_for_all_required_dependencies
  - id: T05
    prove: direct_cycle_indirect_cycle_and_self_cycle_fail_before_persistence
  - id: T06
    prove: missing_dependency_and_duplicate_Node_identity_fail_atomically
  - id: T07
    prove: equivalent_semantics_produce_stable_digest_topology_and_ready_set
  - id: T08
    prove: conditional_optional_branch_changes_readiness_without_invalidating_DAG
  - id: T09
    prove: arbitrary_future_executor_kind_is_accepted_without_kernel_enum_change
  - id: T10
    prove: exact_registered_CapabilityRef_is_required_and_unknown_ref_fails
  - id: T11
    prove: Graph_or_Node_cannot_escalate_Task_side_effect_authority
  - id: T12
    prove: Graph_binds_exact_Project_Task_revision_digest_and_Run
  - id: T13
    prove: NodeInputBinding_accepts_exact_authorized_inputs_and_rejects_cross_scope_or_quarantine
  - id: T14
    prove: Graph_revision_2_preserves_immutable_revision_1_and_prior_ref
  - id: T15
    prove: update_delete_tamper_and_partial_transaction_fail_closed
  - id: T16
    prove: restart_preserves_Graph_Node_dependencies_inputs_digests_and_active_Run_binding
  - id: T17
    prove: independent_creation_and_conflicting_revision_concurrency_are_correct
  - id: T18
    prove: no_provider_hardware_scheduler_domain_or_mandatory_pipeline_coupling

kpi:
  accepted_cycles: 0
  mutated_graph_revisions: 0
  Task_authority_escalations: 0
  parallel_nodes_forced_serial: 0
  mandatory_global_pipeline: 0
  graph_digest_instability: 0

implementation_method:
  - verify_exact_P0_06_remote_handoff
  - inspect_exact_current_source_and_accepted_interfaces
  - write_failure_first_tests_for_each_DAG_identity_authority_and_revision_boundary
  - implement_minimum_complete_P0_07
  - integrate_exact_Task_Run_Capability_and_Artifact_identity_without_later_scheduler_architecture
  - run_focused_tests
  - run_relevant_P0_01_through_P0_06_regressions
  - run_strict_typecheck
  - build_and_inspect_actual_package_artifact
  - inspect_persistence_schema_indexes_triggers_foreign_keys_and_dependency_boundaries

publication:
  when_implementation_complete:
    - record_source_commit
    - commit_coherent_P0_07_result
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
    - replace_04_with_exact_P0_08_packet
    - close_P0_07_before_opening_P0_08
  continue_numbered_prompts_one_at_a_time: true
  broad_real_historical_mining: false
```
