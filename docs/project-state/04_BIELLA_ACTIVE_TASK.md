# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P0-10
  global_number: 10
  phase: P0
  title: P0 Integration, Isolation, Contamination, and Recovery Qualification
  state: READY_AFTER_P0_09_DURABLE_CLOSE
  exact_prompt:
    title: 10_P0-10_P0_Integration_Isolation_Contamination_and_Recovery_Qualification.md.docx
    drive_id: 1Xsx8tYhwvg29FTMkYEK-Sed5kjJHD40HJoFsXYS31IE
    canonical_text_sha256: c01eb2696e3e92425cf17d03372f3281af7bc6c6205071e0c335c4d8c93a51dc
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P0-09
    result_commit: ebcd4ca325ef0455cee91e2959935f6c063a16e3
    result_tree: 49453937a2037f1b17b5f4d68530d9bc33793eee
    remote_readback: VERIFIED
  numbered_successor: P1-01

goal:
  establish:
    - integrated_P0_01_through_P0_09_qualification_as_one_real_system
    - Project_isolation_and_cross_component_exact_identity_proof
    - migration_contamination_firewall_proof_across_all_active_admission_seams
    - recovery_concurrency_immutability_and_restart_qualification
    - evidence_based_READY_FOR_P1_exit_decision
  constrain:
    - fix_only_cross_component_defects_exposed_by_qualification
    - do_not_add_new_architecture_for_P0_ceremony
    - preserve_all_prior_durable_contracts

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
    - P0_09_exact_remote_handoff
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reuse_valid_earlier_implementation_and_results
    - reconcile_existing_equivalent_interfaces_by_semantics
    - missing_handoff_paperwork_is_not_a_blocker_when_exact_source_is_observable

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P0_10_canonical_prompt
    - P0_01_migration_firewall_interfaces
    - P0_02_Project_interfaces
    - P0_03_Capability_interfaces
    - P0_04_Task_interfaces
    - P0_05_Run_and_ExecutionAttempt_interfaces
    - P0_06_Artifact_ContentRef_and_Source_interfaces
    - P0_07_Graph_and_Node_interfaces
    - P0_08_Event_interfaces
    - P0_09_NodeExecution_and_atomic_finalization_interfaces
    - directly_touched_repository_files_and_P0_tests
  conditional:
    - current_Biella_project_instructions
    - earlier_accepted_contracts_actually_used_by_the_integration_test
  prohibited_by_default:
    - unopened_P1_through_P4_prompt_bodies
    - large_real_MiniTZ_backup
    - inactive_legacy_reuse_contract
    - unrelated_website_work
    - broad_historical_recovery_files
    - broad_Drive_GitHub_filesystem_audits

dependencies:
  P0_01:
    result_commit: fa442745b73e02cc2cd67ef0c029973de06bb773
    required_semantics:
      - raw_history_is_immutable_quarantined_and_inert
      - classification_and_provenance_are_explicit
      - active_runtime_has_zero_raw_QuarantineRef_dependency
  P0_02:
    result_commit: 2847543e0b3f9bac04e0e879e4b81f748cab712c
    required_semantics:
      - exact_authenticated_Project_scope
      - cross_Project_reads_writes_bindings_and_configuration_fail_closed
  P0_03:
    result_commit: 4288c792d8f5c1fe12ffd3af47deb7d3aab5d9f1
    required_semantics:
      - open_versioned_Capability_contract
      - arbitrary_future_Capability_is_data_not_kernel_change
  P0_04:
    result_commit: 9b28ccf93c4cb8edd771f474903bcfa5e7592b1b
    required_semantics:
      - exact_immutable_Task_revision_and_digest
      - active_inputs_are_exact_authorized_non_quarantine_refs
  P0_05:
    result_commit: 8f53a1fd641ad46c893239cd8279f310432086bc
    required_semantics:
      - durable_Run_identity_attempts_leases_fences_and_cancellation
      - stale_authority_cannot_commit
  P0_06:
    result_commit: 747a0b59a296890202be39128c455240d87274f2
    required_semantics:
      - exact_ContentRef_Artifact_Source_and_provenance_identity
      - cross_Project_and_corrupt_Artifact_evidence_fail_closed
  P0_07:
    result_commit: c420772708bc64054fdea2d8ed663ed7b550b13f
    required_semantics:
      - immutable_revisioned_Graph_and_Node_DAG
      - dependency_and_condition_readiness
      - exact_current_Run_Graph_binding_and_supersession
  P0_08:
    result_commit: 486c05f37a8deccfa786fe3781c9267fc96cc74b
    required_semantics:
      - immutable_append_only_Event_ledger
      - exact_refs_monotonic_Run_sequence_and_atomic_cancellation_Event
  P0_09:
    result_commit: ebcd4ca325ef0455cee91e2959935f6c063a16e3
    result_tree: 49453937a2037f1b17b5f4d68530d9bc33793eee
    required_semantics:
      - durable_NodeExecution_attempt_state_output_failure_and_ownership
      - fenced_lease_start_heartbeat_wait_fail_finalize_and_recovery
      - atomic_Node_output_Event_and_derived_Run_completion
      - terminal_acceptance_and_completion_Event_manifest_binding

scope:
  in:
    - two_unrelated_Projects_and_full_negative_cross_Project_attack_matrix
    - synthetic_hostile_quarantine_source_and_active_admission_contamination_matrix
    - arbitrary_future_Capability_unknown_to_hardcoded_domain_logic
    - software_like_Alpha_Task_with_exact_input_Artifact_or_Source
    - multi_branch_A_to_B_and_C_to_D_to_E_Graph
    - independent_B_and_C_real_database_readiness_and_concurrent_ownership
    - stale_owner_expiry_takeover_and_late_result_rejection
    - process_or_service_restart_with_durable_reconstruction
    - Graph_v1_v2_immutability_history_and_stale_result_rejection
    - Artifact_corruption_and_Event_immutability_failure_proofs
    - cancellation_finalization_race_with_one_serialized_outcome
    - active_kernel_historical_provider_domain_agent_hierarchy_and_global_lock_scan
    - fixes_only_for_real_cross_component_defects_found
    - exact_READY_FOR_P1_exit_decision
  out:
    - large_historical_backup_mining
    - memory_resource_router_or_provider_adapter_implementation
    - model_browser_build_render_or_DCC_execution
    - P1_feature_implementation
    - optional_domain_or_provider_specialization
    - new_architecture_not_required_to_fix_an_observed_P0_defect

required_interfaces:
  use_existing:
    - MigrationQuarantine_and_normalization_contracts
    - ProjectStore_ProjectRef_ProjectAccess
    - CapabilityRegistry_Capability_CapabilityRef
    - TaskRevisionService_Task_TaskRef
    - RunService_Run_RunRef_ExecutionAttempt
    - ArtifactService_Artifact_ArtifactRef_ContentRef_SourceRef
    - GraphService_Graph_GraphRef_Node_NodeRef
    - EventLedger_Event_EventRef
    - NodeExecutionService_NodeExecution_NodeExecutionAttempt
  new:
    - task_specific_types_services_or_adapters_only_if_an_observed_integration_defect_requires_them
  rule:
    expose_only_stable_semantics_needed_by_later_prompts: true
    do_not_duplicate_architecture_due_to_name_difference: true

fixtures:
  projects: [Alpha, Beta]
  hostile_quarantine_source: synthetic_only
  arbitrary_future_capability: required
  alpha_task_kind: software_like_without_domain_specific_kernel_type
  exact_input_identity: Artifact_or_Source
  graph:
    compact: A_to_B_and_C_to_D_to_E
    edges: [A_to_B, A_to_C, B_to_D, C_to_D, D_to_E]
    required_parallel_frontier: [B, C]
  rule:
    after_A_succeeds_B_and_C_independently_ready: true
    no_global_lock_for_B_and_C: true

migration_contamination_matrix:
  hostile_imperative_text_remains_inert_historical_evidence: true
  raw_quarantine_must_not_enter:
    - Project
    - Task_input
    - Artifact
    - normal_context_or_retrieval_seam
    - Project_Memory_seam
    - Engine_Knowledge_seam
    - Capability_registry
    - Graph_instructions

project_attack_matrix:
  projects: [Alpha, Beta]
  direct_and_indirect_reference_substitution:
    - Task
    - Run
    - Graph
    - Node
    - Artifact
    - Source
    - Event
    - lease_and_fence
    - configuration
  expected:
    - every_unauthorized_path_rejects
    - no_private_payload_leak
    - shared_digest_never_collapses_authorization

immutability_and_digest:
  verify:
    - Task_revision_digest
    - Graph_revision_digest
    - Artifact_ContentRef
    - Event_immutability
    - Source_identity
  mutation_attempts:
    - historical_Task_revision
    - historical_Graph_revision
    - Artifact_content_or_provenance
    - Event_record_or_sequence
    - Source_identity
  expected:
    - mutation_rejected_or_detected
    - legitimate_change_requires_new_revision
    - historical_revision_retained

concurrency:
  require:
    - B_and_C_acquired_through_independent_connections_or_transactions
    - real_database_classification_when_SQLite_is_used
    - no_purely_mocked_sequential_substitute_for_required_race
    - no_heavyweight_global_or_production_global_lock
    - independent_P0_work_not_globally_serialized_beyond_database_write_commit_boundary

worker_loss_and_recovery:
  scenario:
    - Node_RUNNING_under_fence_N
    - owner_N_lease_expires
    - recovery_marks_N_stale_as_appropriate
    - replacement_gets_fence_N_plus_1
    - late_N_result_is_rejected
    - N_plus_1_completes_with_exact_Event_and_output_identity
  preserve:
    - already_verified_durable_work
    - completed_Node_non_reexecution

cancellation_race:
  require:
    - real_database_finalize_vs_cancel_race
    - exactly_one_technically_valid_serialized_outcome
    - no_double_finalization
    - no_cancelled_Run_resurrection
    - actual_Event_order_matches_commit_order

graph_revision:
  require:
    - create_v1_then_bounded_v2_change
    - v1_immutable_and_history_retained
    - superseded_Node_cannot_mutate_current_execution
    - compatible_completed_Artifact_remains_historical_evidence

restart:
  reconstruct_without_chat_or_provider_session:
    - Projects
    - Task_revision
    - Run_and_fence
    - Graph
    - Node_states
    - Artifacts
    - Events

kernel_neutrality_scan:
  inspect_active_source_and_schema_for_semantic_coupling_to:
    - legacy_donor
    - Godot
    - Unreal
    - Unity
    - OpenAI
    - NVIDIA
    - H100
    - founder_or_workstation
    - mandatory_critic_or_validator
    - global_heavyweight_lock
    - provider_model_or_agent_hierarchy
  classification_rule:
    - distinguish_active_semantic_dependency_from_fixture_test_or_nonsemantic_comment
    - report_active_dependency_before_READY_FOR_P1
    - do_not_blindly_delete_legitimate_fixture_or_test_strings

failure_behavior:
  fail_closed_on:
    - Project_scope_or_identity_mismatch
    - quarantine_or_historical_content_active_binding
    - stale_expired_or_superseded_authority
    - immutable_record_or_digest_corruption
    - cancellation_or_terminal_conflict
    - Event_or_state_head_integrity_failure
  preserve: [durable_evidence, real_failure_cause, unaffected_required_work]
  prohibit: [fabricated_success, fabricated_missing_fact, weakened_architecture_for_unavailable_dependency]

required_test_matrix:
  - {id: T01, prove: Project_Alpha_Beta_negative_isolation_across_Task_Run_Graph_Node_Artifact_Source_Event_lease_fence_and_configuration}
  - {id: T02, prove: hostile_synthetic_quarantine_object_is_inert_across_all_active_admission_seams}
  - {id: T03, prove: arbitrary_future_Capability_executes_without_hardcoded_domain_kernel_change}
  - {id: T04, prove: A_to_B_and_C_to_D_to_E_readiness_is_exact_and_B_C_parallel_frontier_is_preserved}
  - {id: T05, prove: B_and_C_can_hold_current_ownership_through_real_independent_database_connections_without_global_lock}
  - {id: T06, prove: worker_loss_recovery_allocates_fence_N_plus_1_and_rejects_late_N_result}
  - {id: T07, prove: process_restart_reconstructs_all_P0_identity_authority_Graph_Node_Artifact_and_Event_state}
  - {id: T08, prove: Graph_v1_v2_history_is_immutable_and_superseded_Node_result_is_rejected}
  - {id: T09, prove: compatible_completed_Artifact_remains_exact_historical_evidence_after_Graph_supersession}
  - {id: T10, prove: Artifact_ContentRef_or_provenance_corruption_fails_closed}
  - {id: T11, prove: Event_update_delete_sequence_or_head_tampering_fails_closed}
  - {id: T12, prove: cancellation_finalization_race_has_one_coherent_serialized_outcome_without_resurrection}
  - {id: T13, prove: Task_Graph_Artifact_Event_and_Source_immutability_or_new_revision_semantics_hold_together}
  - {id: T14, prove: active_kernel_neutrality_scan_has_no_historical_provider_domain_agent_hierarchy_or_heavyweight_global_lock_dependency}
  - {id: T15, prove: full_P0_01_through_P0_09_regression_matrix_passes_together_without_skips_placeholders_or_TODO_tests}
  - {id: T16, prove: exact_remote_wheel_and_restart_smoke_preserve_the_integrated_P0_contract}

kpi:
  active_raw_legacy_donor_content: 0
  cross_project_reads: 0
  accepted_stale_results: 0
  mutated_Task_or_Graph_revisions: 0
  provider_specific_kernel_requirements: 0
  global_heavyweight_resource_lock: 0

exit_decision:
  READY_FOR_P1_only_when:
    - migration_firewall_holds
    - Project_isolation_holds
    - exact_identity_and_immutability_hold
    - fencing_and_recovery_hold
    - Events_and_durable_state_survive_restart
    - arbitrary_Capability_extensibility_holds
    - concurrent_independent_work_is_not_globally_serialized
    - kernel_neutrality_scan_has_no_active_coupling
  otherwise:
    - record_exact_failed_condition
    - fix_only_observed_P0_cross_component_defect_when_possible
    - do_not_weaken_exit_criteria

implementation_method:
  - verify_exact_P0_09_remote_handoff
  - inspect_exact_current_source_tests_schema_and_accepted_interfaces
  - add_task_scoped_integration_qualification_tests_before_any_defect_fix
  - exercise_real_P0_services_as_one_system
  - use_real_SQLite_connections_transactions_races_and_restart
  - fix_only_cross_component_defects_exposed_by_red_qualification
  - run_focused_P0_10_tests
  - run_full_P0_01_through_P0_09_regressions
  - run_strict_typecheck_compileall_and_build
  - inspect_actual_wheel_and_clean_install_smoke
  - run_kernel_neutrality_and_raw_QuarantineRef_dependency_scans
  - inspect_schema_indexes_triggers_foreign_keys_and_transaction_boundaries
  - obtain_independent_changed_code_review_before_publication

publication:
  when_qualification_complete:
    - record_source_commit
    - commit_coherent_P0_10_result
    - push_main
    - remote_readback_result_commit
    - remote_readback_result_tree
    - verify_required_remote_paths_and_bytes
    - record_exact_READY_FOR_P1_or_non_ready_decision
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
    - replace_04_with_exact_P1_01_packet_only_after_P0_10_durable_close
    - close_P0_10_before_opening_P1_01
  continue_numbered_prompts_one_at_a_time: true
  broad_real_historical_mining: false
```
