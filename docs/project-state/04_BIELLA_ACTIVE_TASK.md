# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P1-06
  global_number: 16
  phase: P1
  title: Durable Checkpoint and Resume
  state: READY_AFTER_P1_05_DURABLE_CLOSE
  exact_prompt:
    title: 16_P1-06_Durable_Checkpoint_and_Resume.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P1/16_P1-06_Durable_Checkpoint_and_Resume.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P1/16_P1-06_Durable_Checkpoint_and_Resume.md.docx
    drive_id: 116Lf3h6Ermqveds96ifQA3AneaC_7giEuMGddMhfimU
    local_docx_sha256: d39d16bf5302c602ce4d94884d30f879ab52384a7e77d3a9754d8bf05c520b18
    live_drive_exported_docx_sha256: a8888c0f0160b8a4f31533f941a49ef971d1bbe1dddec5d893a861dfb8211a41
    canonical_text_sha256: 6232b3676bf75f2e0109d30b003a1a0faca609c7b1e955446d8280b6fd4615b8
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P1-05
    result_commit: 02f89c0d17d2f08a6c7b03f7faa285993f452891
    result_tree: 7b8a976bf2a6d6b17a0b85359f6e9b6c570f7358
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    exact_remote_clone_functional_type_build_and_install: VERIFIED
  numbered_successor: P1-07

goal:
  establish:
    - immutable_verified_versioned_RunCheckpoint_continuation_evidence
    - content_addressed_Artifact_Event_and_latest_checkpoint_ref_binding
    - current_durable_state_wins_reconciliation
    - safe_resume_with_new_attempts_and_fences
    - smallest_safe_dependency_aware_reexecution_boundary
  preserve:
    - completed_valid_Node_outputs_across_worker_provider_cache_and_workspace_loss
    - newer_Run_Graph_Event_Node_call_and_failure_truth
    - exact_Project_Task_Run_Graph_Node_attempt_fence_and_capability_identity
    - migration_firewall_and_zero_active_raw_QuarantineRef_dependency
    - all_P0_through_P1_05_durability_isolation_provenance_and_authority_contracts

prewrite_observation:
  required:
    - actual_repository_or_worktree
    - branch
    - source_commit_and_tree
    - dirty_state
    - migrations_and_tests_if_present
    - AGENTS_policy_and_instruction_files_if_present
    - accepted_Run_Task_Graph_Node_execution_Artifact_ContentRef_Event_RunMemory_and_call_ledger_interfaces_directly_needed
    - exact_P1_05_remote_handoff
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reuse_valid_earlier_implementation_and_results
    - reconcile_existing_equivalent_interfaces_by_semantics
    - missing_handoff_paperwork_is_not_a_blocker_when_exact_source_is_observable

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P1_06_canonical_prompt
    - accepted_Run_Task_Graph_Node_and_execution_attempt_interfaces
    - accepted_Artifact_ContentRef_Event_and_RunMemory_interfaces
    - accepted_ModelCall_ToolCall_and_call_reference_interfaces_when_checkpointed
    - directly_touched_repository_files_and_required_regression_tests
  conditional:
    - current_Biella_project_instructions
    - earlier_accepted_contracts_actually_used_by_this_task
  prohibited_by_default:
    - unopened_P1_07_through_P4_prompt_bodies
    - broad_historical_backup_or_legacy_reuse_material
    - unrelated_website_work
    - broad_Drive_GitHub_or_filesystem_audits

dependencies:
  P1_05:
    result_commit: 02f89c0d17d2f08a6c7b03f7faa285993f452891
    result_tree: 7b8a976bf2a6d6b17a0b85359f6e9b6c570f7358
    required_semantics:
      - ModelCall_and_ToolCall_are_immutable_provider_neutral_exactly_execution_attributed_evidence
      - call_start_and_terminal_status_have_independent_Event_anchors
      - retry_and_parent_relationships_are_recursively_verified_and_fail_closed
      - Event_and_RunMemory_reconstruction_expose_exact_call_refs_without_provider_trace_dependency
      - secrets_and_large_payload_bodies_are_absent_from_call_rows
  earlier_accepted_contracts:
    required_semantics:
      - Project_identity_and_authorization_are_exact_and_fail_closed
      - Task_revision_Run_identity_Graph_revision_Node_attempt_owner_and_fence_are_durable_and_exact
      - Artifact_and_ContentRef_identity_and_provenance_are_immutable
      - Event_chronology_and_RunMemory_reconstruction_are_restart_durable
      - Node_execution_state_and_attempt_history_are_append_only_and_fenced

scope:
  in:
    - RunCheckpoint_versioned_schema
    - createCheckpoint
    - resumeRun
    - reconciliation_service
    - content_addressed_checkpoint_serialization
    - checkpoint_Artifact_Event_and_Run_latest_ref
    - exact_Task_Graph_Node_state_attempt_fence_source_output_call_failure_and_Event_sequence_refs
    - optional_provider_runtime_workspace_continuation_refs
    - current_durable_state_wins_comparison
    - completed_valid_Node_reuse
    - dependency_aware_source_change_invalidation
    - Graph_revision_compatibility_without_rollback
    - stale_lease_recovery_with_new_attempt_and_fence
    - process_provider_cache_and_workspace_loss_recovery
  out:
    - P1_07_resource_inventory
    - P1_08_scheduler_architecture
    - P1_09_routing_architecture
    - later_execution_adapters
    - provider_session_as_authoritative_checkpoint
    - arbitrary_global_checkpoint_frequency_or_interval
    - unrelated_domain_or_provider_specialization

required_interfaces:
  create_or_reconcile:
    - RunCheckpoint
    - createCheckpoint
    - resumeRun
    - checkpoint_reconciliation_service
    - latest_checkpoint_ref_seam
  RunCheckpoint_fields_or_equivalents:
    - checkpoint_id
    - schema_version
    - exact_Project_Run_Task_revision_and_digest
    - exact_Graph_revision_and_record_identity
    - checkpoint_sequence_and_created_at
    - Node_state_attempt_and_fence_summary_refs
    - completed_output_refs
    - source_refs
    - call_and_failure_refs
    - Event_high_water_mark
    - optional_workspace_snapshot_ref
    - optional_provider_or_runtime_continuation_refs
    - exact_ContentRef_and_ArtifactRef
  authority_rule:
    checkpoint_is_time_machine: false
    checkpoint_overwrites_newer_truth: false
    provider_session_is_required: false
    cache_is_authority: false
    workspace_materialization_is_authority: false
    terminal_or_cancelled_Run_can_resume: false

checkpoint_creation:
  require:
    - coherent_single_durable_snapshot
    - exact_current_Run_Task_Graph_Node_attempt_fence_and_Event_sequence
    - committed_outputs_only
    - content_addressed_versioned_serialization
    - immutable_checkpoint_Artifact_and_Event
    - atomic_enough_latest_checkpoint_reference_for_reconstruction
  prohibit:
    - uncommitted_output_claims
    - stale_fence_claims
    - large_opaque_checkpoint_body_in_normal_rows_or_Events
    - global_pause_of_unrelated_independent_work

resume_and_reconciliation:
  ordered_rules:
    - load_current_durable_Run_Task_Graph_and_Node_state
    - load_and_verify_candidate_checkpoint
    - verify_Project_Run_Task_and_schema_identity
    - verify_content_and_record_digests
    - compare_Graph_compatibility
    - preserve_all_newer_Events_and_state
    - reuse_only_still_valid_completed_work
    - invalidate_only_affected_source_dependent_work
    - acquire_new_attempts_and_fences_for_continuation
  current_durable_state_wins: true
  checkpoint_may_restore_older_Graph_over_newer_Graph: false
  late_old_fence_result_accepted: false

loss_and_failure_behavior:
  resume_must_not_require:
    - prior_conversation
    - live_provider_session
    - local_model_process
    - cache
    - browser_session
    - prior_workspace_materialization_when_durable_snapshot_exists
  fail_closed_on:
    - cross_Project_checkpoint_access
    - wrong_Run_or_Task_revision
    - corrupt_or_incompatible_schema_or_digest
    - incompatible_source_or_Graph
    - superseded_authority_or_stale_fence
    - terminal_or_cancelled_Run_resume
  preserve:
    - checkpoint_and_Event_evidence
    - current_newer_truth
    - completed_valid_nodes_and_outputs
    - unaffected_independent_branches
    - real_failure_cause
  prohibit:
    - fabricated_success_or_missing_fact
    - silent_destructive_repair
    - weakened_architecture_for_unavailable_dependency

mandatory_scenario:
  - Node_A_completes_with_valid_output
  - coherent_checkpoint_is_created
  - Node_B_begins_under_fence_N
  - worker_process_dies_and_lease_becomes_stale
  - restart_reconstructs_current_durable_state
  - Node_B_obtains_fence_N_plus_1
  - Node_A_is_not_rerun
  - late_Node_B_fence_N_result_is_rejected
  - continuation_completes

required_test_matrix:
  - {id: T01, prove: RunCheckpoint_has_versioned_provider_neutral_ID_and_exact_Project_Run_Task_Graph_Event_attribution}
  - {id: T02, prove: createCheckpoint_commits_content_addressed_Artifact_Event_and_latest_ref_from_one_coherent_snapshot}
  - {id: T03, prove: mandatory_multi_Node_process_death_resume_preserves_completed_A_and_recovers_B_with_new_fence}
  - {id: T04, prove: late_result_from_old_B_fence_is_rejected_after_resume}
  - {id: T05, prove: provider_session_cache_local_runtime_browser_and_workspace_loss_do_not_erase_Run_truth_or_block_safe_resume}
  - {id: T06, prove: Events_and_durable_state_newer_than_checkpoint_are_preserved_and_win}
  - {id: T07, prove: current_Graph_v2_wins_over_checkpoint_Graph_v1_while_compatible_exact_outputs_may_be_reused}
  - {id: T08, prove: corrupt_wrong_scope_wrong_Run_and_incompatible_checkpoint_fail_closed_without_current_state_damage}
  - {id: T09, prove: SUCCEEDED_FAILED_and_CANCELLED_terminal_Runs_cannot_be_resurrected}
  - {id: T10, prove: cross_Project_checkpoint_access_and_reference_binding_fail_closed}
  - {id: T11, prove: source_change_invalidates_only_semantically_dependent_work_and_records_exact_cause}
  - {id: T12, prove: concurrent_checkpoint_creation_is_idempotent_coherent_and_does_not_globally_serialize_unrelated_Runs}
  - {id: T13, prove: exact_source_output_ModelCall_ToolCall_failure_attempt_fence_and_optional_continuation_refs_round_trip}
  - {id: T14, prove: restart_RunMemory_Event_and_latest_checkpoint_reconstruction_are_cache_independent_and_tamper_evident}
  - {id: T15, prove: required_predecessor_regressions_typecheck_build_and_installed_wheel_restart_pass_without_skips_placeholders_or_TODO_tests}

kpi:
  checkpoint_digest_mismatches_accepted: 0
  completed_valid_nodes_rerun_due_only_to_restart: 0
  resume_requires_conversation: 0
  resume_requires_live_provider_session: 0
  cache_loss_causes_resume_failure: 0
  cancelled_runs_resurrected: 0

completion_gate:
  require:
    - checkpoint_is_immutable_versioned_content_addressed_and_exactly_attributed
    - checkpoint_Artifact_Event_and_latest_ref_are_reconstructable_after_restart
    - current_durable_state_always_wins_over_older_checkpoint_state
    - completed_valid_work_is_not_rerun_due_only_to_restart
    - source_invalidation_is_dependency_aware_and_evidence_backed
    - stale_fences_late_results_corruption_wrong_scope_and_terminal_resume_fail_closed
    - provider_cache_workspace_and_session_loss_do_not_define_Run_truth
    - all_required_tests_and_regressions_pass_without_skips_placeholders_or_TODOs

implementation_method:
  - verify_exact_P1_05_remote_handoff
  - inspect_exact_Run_Task_Graph_Node_execution_Artifact_ContentRef_Event_RunMemory_and_call_ledger_interfaces_directly_needed
  - add_task_scoped_failing_tests_before_implementation_or_defect_fix
  - implement_minimal_versioned_RunCheckpoint_exact_reference_and_content_contracts
  - implement_atomic_checkpoint_Artifact_Event_latest_ref_commit
  - implement_current_state_wins_reconciliation_dependency_aware_reuse_and_new_fence_resume
  - exercise_real_restart_stale_fence_newer_Event_Graph_revision_source_invalidation_corruption_loss_and_scope_cases
  - run_focused_P1_06_tests
  - run_relevant_predecessor_regressions_and_full_required_suite
  - run_strict_typecheck_compileall_and_build
  - inspect_actual_wheel_and_clean_install_restart_smoke
  - obtain_independent_changed_code_review_before_publication

publication:
  when_complete:
    - record_source_commit
    - commit_coherent_P1_06_result
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
    - replace_04_with_exact_P1_07_packet_only_after_P1_06_durable_close
    - close_P1_06_before_opening_P1_07
  continue_numbered_prompts_one_at_a_time: true
  broad_real_historical_mining: false
```
