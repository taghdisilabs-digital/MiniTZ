# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P1-02
  global_number: 12
  phase: P1
  title: Durable Run Memory and Reconstruction
  state: READY_AFTER_P1_01_DURABLE_CLOSE
  exact_prompt:
    title: 12_P1-02_Durable_Run_Memory_and_Reconstruction.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P1/12_P1-02_Durable_Run_Memory_and_Reconstruction.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P1/12_P1-02_Durable_Run_Memory_and_Reconstruction.md.docx
    drive_id: 19Bifx_E0RPhs3gxi3srr7118_rnhdT1gSCH3Pyi8I3Y
    local_docx_sha256: 0096d60b6a209758728ae7621fb1f82594c47aa8579bf95cbf267992cfd46afd
    live_drive_exported_docx_sha256: 7b182974fd3c628115b87036a9a77bf9cfc80a1c24cc94d035f419b7eb982c59
    canonical_text_sha256: 9b0a34a112743edee693683b8fe02d5689da29045b7ef0935f0863b9e2302323
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P1-01
    result_commit: 6cc8c6a69c9f2051bb3a9755272eff9dcc77da08
    result_tree: f9453145afb4d9083e17c4453c9b1f27600a74e2
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    exact_remote_archive_build_and_restart: VERIFIED
  numbered_successor: P1-03

goal:
  establish:
    - durable_RunMemory_reconstructable_without_conversation_process_worker_provider_cache_or_temporary_workspace_state
    - exact_meaningful_Run_execution_state_from_existing_authoritative_durable_records
    - divergence_detection_without_silent_fabrication_or_repair
    - checkpoint_and_model_or_tool_call_reference_seams_without_payload_duplication
  preserve:
    - exact_Task_and_Graph_revision_identity
    - historical_attempts_fences_failures_Events_and_Artifact_evidence
    - Project_isolation_and_existing_execution_authority
    - stale_owner_and_stale_result_rejection
    - all_P0_and_P1_01_identity_immutability_durability_validation_and_evidence_contracts

prewrite_observation:
  required:
    - actual_repository_or_worktree
    - branch
    - source_commit_and_tree
    - dirty_state
    - migrations_and_tests_if_present
    - AGENTS_policy_and_instruction_files_if_present
    - accepted_Run_Node_Event_Graph_Artifact_Task_and_storage_interfaces
    - exact_P1_01_remote_handoff
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reuse_valid_earlier_implementation_and_results
    - reconcile_existing_equivalent_interfaces_by_semantics
    - missing_handoff_paperwork_is_not_a_blocker_when_exact_source_is_observable

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P1_02_canonical_prompt
    - accepted_Run_and_Node_execution_state_interfaces
    - accepted_Event_Graph_Artifact_Task_and_Project_interfaces_directly_needed_by_reconstruction
    - P1_01_ContentRef_and_object_storage_interfaces_only_when_checkpoint_or_call_refs_require_them
    - directly_touched_repository_files_and_required_regression_tests
  conditional:
    - current_Biella_project_instructions
    - earlier_accepted_contracts_actually_used_by_this_task
  prohibited_by_default:
    - unopened_P1_03_through_P4_prompt_bodies
    - broad_historical_backup_or_legacy_reuse_material
    - unrelated_website_work
    - broad_Drive_GitHub_or_filesystem_audits

dependencies:
  P1_01:
    result_commit: 6cc8c6a69c9f2051bb3a9755272eff9dcc77da08
    result_tree: f9453145afb4d9083e17c4453c9b1f27600a74e2
    required_semantics:
      - exact_ContentRef_identity_and_durable_object_storage_are_available
      - physical_content_location_is_separate_from_logical_identity_and_authorization
      - restart_integrity_and_corruption_detection_hold
  earlier_accepted_contracts:
    required_semantics:
      - Run_binds_exact_Project_Task_revision_and_current_execution_authority
      - Graph_revisions_Node_dependencies_and_historical_supersession_are_durable
      - Node_attempt_lease_fence_state_failure_output_and_completion_evidence_are_authoritative
      - Event_ledger_is_chronological_evidence_not_mutable_current_state
      - Artifact_refs_and_provenance_are_exact_immutable_and_Project_scoped

scope:
  in:
    - RunMemory_immutable_reconstructed_view
    - get_or_reconstruct_RunMemory
    - consistency_validator
    - Project_Task_revision_digest_Run_and_current_Graph_revision_identity
    - Node_state_summary_current_attempt_owner_fence_and_historical_attempts
    - completed_outputs_failures_stale_cancelled_and_expired_state
    - Event_sequence_high_water_mark_and_meaningful_chronology
    - latest_compatible_checkpoint_reference_seam
    - optional_model_tool_or_provider_live_optimization_reference_seams
    - continuation_and_current_ready_set_inputs
    - superseded_Graph_history_without_current_authority
    - restart_cache_loss_and_provider_session_absence_reconstruction
    - deterministic_inconsistency_detection_or_resolution_by_authoritative_records
  out:
    - independent_mutable_RunMemory_authority
    - duplicated_checkpoint_model_tool_or_large_payload_bytes
    - provider_session_as_required_continuation_state
    - Scheduler_or_resource_model_replacement
    - later_numbered_prompt_architecture
    - unrelated_domain_or_provider_specialization

required_interfaces:
  create_or_reconcile:
    - RunMemory
    - get_or_reconstruct_RunMemory
    - RunMemory_consistency_validator
  reconstructable_fields_or_equivalents:
    - project_id
    - task_id_revision_and_digest
    - run_id
    - accepted_current_graph_and_revision
    - node_state_summary
    - current_attempts_owners_and_fences
    - historical_attempts_across_graph_revisions
    - completed_output_Artifact_refs
    - failed_stale_cancelled_and_expired_nodes
    - Event_sequence_high_water_mark
    - latest_compatible_checkpoint_ref
    - continuation_and_ready_set_inputs
  authority_rule:
    RunMemory_is_reconstruction_not_second_authority: true
    materialized_projection_if_any_is_rebuildable_and_non_authoritative: true
    newer_durable_execution_state_overrides_stale_projection: true
    contradictions_are_never_silently_merged: true

reconstruction_algorithm:
  required_sequence:
    - authenticate_exact_Project_scope_and_Run_identity
    - read_and_verify_exact_Run_and_bound_Task_revision
    - resolve_and_verify_current_accepted_Graph_revision
    - reconstruct_current_and_historical_Node_execution_attempt_fence_and_state_evidence
    - bind_completed_output_Artifacts_failures_and_terminal_evidence
    - reconstruct_ordered_Event_chronology_and_high_water_mark
    - select_latest_checkpoint_ref_compatible_with_current_Task_and_Graph
    - derive_current_continuation_and_ready_set_from_authoritative_state
    - validate_cross_record_consistency_and_fail_closed_on_unresolved_divergence
    - return_immutable_RunMemory_view
  invariants:
    - restart_or_cache_loss_cannot_erase_verified_work
    - conversation_or_provider_session_absence_cannot_block_reconstruction
    - Task_or_Graph_supersession_cannot_rewrite_existing_Run_history
    - expired_or_stale_owner_is_not_reported_as_current_indefinitely
    - Event_history_does_not_override_current_execution_authority
    - foreign_Project_identity_never_grants_RunMemory_access

consistency_and_failure_behavior:
  detect_or_deterministically_resolve:
    - missing_Event
    - stale_materialized_summary
    - superseded_Graph
    - output_Artifact_ref_mismatch
    - Task_or_Graph_identity_drift
    - attempt_fence_owner_or_terminal_state_divergence
  fail_closed_on:
    - Project_scope_mismatch
    - identity_authority_or_integrity_mismatch
    - contradictory_authoritative_records_without_defined_resolution
    - invalid_checkpoint_compatibility
  preserve:
    - durable_evidence
    - real_failure_cause
    - already_verified_durable_work
    - unaffected_required_work
  prohibit:
    - fabricated_success
    - fabricated_missing_fact
    - silent_repair_of_authoritative_state
    - mocked_real_infrastructure_classification
    - weakened_architecture_for_unavailable_dependency

concurrency_and_recovery:
  require:
    - reconstruction_uses_existing_Graph_Scheduler_and_resource_authority
    - independent_work_remains_concurrent_when_dependencies_side_effects_and_resources_allow
    - already_verified_durable_work_survives_recovery
    - stale_owners_and_results_remain_rejected
    - reconstruction_observes_one_consistent_authoritative_snapshot_or_fails_closed
    - no_global_serialization_beyond_existing_required_commit_boundaries

required_test_matrix:
  - {id: T01, prove: representative_multi_node_Run_reconstructs_identically_after_process_restart}
  - {id: T02, prove: exact_Task_revision_digest_and_current_Graph_revision_reconstruct}
  - {id: T03, prove: completed_failed_ready_expired_Node_attempt_owner_and_fence_states_reconstruct}
  - {id: T04, prove: output_Artifact_failure_and_terminal_evidence_refs_survive_restart}
  - {id: T05, prove: ordered_Events_and_sequence_high_water_mark_reconstruct_without_becoming_current_authority}
  - {id: T06, prove: latest_checkpoint_ref_is_compatible_with_current_Task_and_Graph_without_payload_duplication}
  - {id: T07, prove: cache_or_materialized_summary_deletion_does_not_lose_Run_state}
  - {id: T08, prove: provider_or_hosted_session_absence_does_not_block_reconstruction_or_continuation}
  - {id: T09, prove: Project_Beta_cannot_reconstruct_Alpha_RunMemory_by_known_Run_ID}
  - {id: T10, prove: terminal_Run_remains_terminal_and_expired_owner_is_not_current_indefinitely}
  - {id: T11, prove: superseded_Graph_history_is_available_without_becoming_current}
  - {id: T12, prove: missing_Event_stale_summary_superseded_Graph_and_output_ref_mismatch_do_not_silently_merge}
  - {id: T13, prove: newer_Task_revision_does_not_rewrite_existing_RunMemory}
  - {id: T14, prove: continuation_and_ready_set_follow_authoritative_dependencies_and_current_state}
  - {id: T15, prove: required_predecessor_regressions_typecheck_build_and_installed_wheel_restart_pass_without_skips_placeholders_or_TODO_tests}

kpi:
  run_state_lost_after_restart: 0
  conversation_dependency: 0
  provider_session_dependency: 0
  completed_nodes_lost: 0
  Task_revision_drift: 0
  RunMemory_divergence_silently_accepted: 0

completion_gate:
  require:
    - Run_can_answer_what_was_requested_which_Graph_is_current_what_completed_executes_failed_and_remains
    - reconstruction_uses_durable_state_alone
    - exact_sources_outputs_attempts_fences_and_chronology_are_preserved
    - restart_cache_loss_and_provider_session_absence_do_not_lose_verified_state
    - cross_Project_access_and_identity_drift_fail_closed
    - all_required_tests_and_regressions_pass_without_skips_placeholders_or_TODOs

implementation_method:
  - verify_exact_P1_01_remote_handoff
  - inspect_exact_Run_Node_Event_Graph_Artifact_Task_Project_interfaces_and_directly_relevant_tests
  - add_task_scoped_failing_tests_before_implementation_or_defect_fix
  - implement_minimal_immutable_RunMemory_reconstruction_contract
  - validate_one_consistent_authoritative_snapshot_and_defined_divergence_handling
  - exercise_real_restart_cache_loss_scope_denial_expiration_supersession_and_tampering
  - run_focused_P1_02_tests
  - run_relevant_predecessor_regressions_and_full_required_suite
  - run_strict_typecheck_compileall_and_build
  - inspect_actual_wheel_and_clean_install_restart_smoke
  - obtain_independent_changed_code_review_before_publication

publication:
  when_complete:
    - record_source_commit
    - commit_coherent_P1_02_result
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
    - replace_04_with_exact_P1_03_packet_only_after_P1_02_durable_close
    - close_P1_02_before_opening_P1_03
  continue_numbered_prompts_one_at_a_time: true
  broad_real_historical_mining: false
```
