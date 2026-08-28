# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P0-09
  global_number: 9
  phase: P0
  title: Durable Node/Run Execution State and Atomic Finalization
  state: READY_AFTER_P0_08_DURABLE_CLOSE
  exact_prompt:
    title: 09_P0-09_Durable_Node_Run_Execution_State_and_Atomic_Finalization.md.docx
    drive_id: 1_yBgxGdKjX88wA9gXk59NzN8No7srJZDRF0CGCIF90I
    canonical_text_sha256: 6d6ec80041a00035e1163f094cdc0de0b7b3f30c9c40277632c506aa2cc72412
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P0-08
    result_commit: 486c05f37a8deccfa786fe3781c9267fc96cc74b
    result_tree: 7abd3dc98a3689b2c3e0593d4dbdf1207733c67f
    remote_readback: VERIFIED
  numbered_successor: P0-10

goal:
  establish:
    - durable_Node_and_Run_execution_authority_state
    - dependency_and_condition_derived_Node_readiness
    - fenced_Node_lease_start_heartbeat_wait_failure_and_recovery
    - atomic_output_state_Event_finalization
    - durable_Run_completion_derived_from_current_Graph
  guarantee:
    - stale_expired_cancelled_and_superseded_work_cannot_finalize
    - completed_Nodes_are_not_reexecuted_after_restart
    - finalization_and_cancellation_races_have_one_coherent_authoritative_outcome
    - independent_Nodes_do_not_require_a_global_execution_lock

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
    - P0_08_exact_remote_handoff
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reuse_valid_earlier_implementation_and_results
    - reconcile_existing_equivalent_interfaces_by_semantics
    - missing_handoff_paperwork_is_not_a_blocker_when_exact_source_is_observable

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P0_09_canonical_prompt
    - P0_02_Project_interfaces
    - P0_04_Task_and_TaskRef_interfaces
    - P0_05_Run_ExecutionAttempt_leasing_fencing_and_cancellation_interfaces
    - P0_06_Artifact_and_ContentRef_interfaces
    - P0_07_Graph_Node_readiness_and_revision_interfaces
    - P0_08_Event_transaction_bound_append_and_Run_event_query_interfaces
    - directly_touched_repository_files
  conditional:
    - current_Biella_project_instructions
    - earlier_accepted_contracts_actually_used_by_this_task
  prohibited_by_default:
    - other_42_unopened_prompt_bodies
    - large_real_MiniTZ_backup
    - inactive_legacy_reuse_contract
    - unrelated_website_work
    - broad_historical_recovery_files
    - broad_Drive_GitHub_filesystem_audits

dependencies:
  P0_02:
    result_commit: 2847543e0b3f9bac04e0e879e4b81f748cab712c
    required_interfaces: [ProjectRef, ProjectAccess]
    required_semantics: [authenticated_Project_scope, cross_Project_access_fails_closed]
  P0_04:
    result_commit: 9b28ccf93c4cb8edd771f474903bcfa5e7592b1b
    required_interfaces: [Task, TaskRef, TaskRevisionService]
    required_semantics: [exact_immutable_Task_revision_digest_authority_and_acceptance_contract]
  P0_05:
    result_commit: 8f53a1fd641ad46c893239cd8279f310432086bc
    required_interfaces: [Run, RunRef, ExecutionAttempt, RunService]
    required_semantics:
      - exact_Project_and_Task_binding
      - append_only_Run_state_history
      - current_lease_and_fenced_authority
      - durable_cancellation
  P0_06:
    result_commit: 747a0b59a296890202be39128c455240d87274f2
    required_interfaces: [Artifact, ArtifactRef, ContentRef, ArtifactService]
    required_semantics:
      - exact_immutable_output_identity
      - current_fenced_authority_for_output_publication
      - provenance_and_record_integrity
  P0_07:
    result_commit: c420772708bc64054fdea2d8ed663ed7b550b13f
    required_interfaces: [Graph, GraphRef, Node, NodeRef, GraphService]
    required_semantics:
      - deterministic_dependency_and_condition_readiness
      - exact_current_Run_Graph_revision_binding
      - immutable_Node_contract_and_output_contract
      - superseded_Graph_revision_history
  P0_08:
    result_commit: 486c05f37a8deccfa786fe3781c9267fc96cc74b
    result_tree: 7abd3dc98a3689b2c3e0593d4dbdf1207733c67f
    required_interfaces: [Event, EventRef, EventLedger]
    required_semantics:
      - appendEvent_and_transaction_bound_append
      - per_Run_monotonic_sequence_and_explicit_idempotency
      - immutable_exact_object_and_payload_refs
      - atomic_Run_cancellation_and_Event

scope:
  in:
    - durable_NodeExecution_identity_attempts_statuses_outputs_failures_and_ownership
    - CREATED_QUEUED_READY_LEASED_RUNNING_WAITING_EXTERNAL_SUCCEEDED_FAILED_CANCELLED_STALE_semantics
    - readiness_from_current_Graph_dependencies_conditions_Task_authority_and_Run_state
    - atomic_Node_leasing_with_current_Graph_and_fence
    - start_and_heartbeat_under_live_current_authority
    - bounded_failure_reason_category_evidence_refs_and_retry_or_replan_signal
    - expired_worker_recovery_and_higher_fence_reallocation
    - current_Graph_supersession_staleness
    - atomic_Artifact_output_binding_Node_terminal_state_Event_and_Run_completion
    - cancelRun_and_Run_completion
    - restart_and_real_database_race_proofs
  out:
    - provider_model_browser_build_render_or_DCC_execution
    - intelligent_scheduler_or_fixed_repair_loop
    - resource_availability_as_readiness
    - remote_worker_dispatch_or_queue_transport
    - later_numbered_prompt_implementation
    - optional_domain_or_provider_specialization

required_interfaces:
  exact: [NodeExecution]
  required_APIs:
    - lease_Node
    - start_Node
    - heartbeat_Node
    - fail_Node
    - wait_Node
    - finalize_Node
    - recoverExpiredExecution
    - cancelRun
    - Run_completion
  rule:
    accepted_existing_semantic_equivalent_may_be_mapped: true
    do_not_duplicate_architecture_due_to_name_difference: true

node_execution_contract:
  status_semantics:
    - CREATED
    - QUEUED
    - READY
    - LEASED
    - RUNNING
    - WAITING_EXTERNAL
    - SUCCEEDED
    - FAILED
    - CANCELLED
    - STALE
  require:
    - exact_ProjectRef_TaskRef_RunRef_GraphRef_and_NodeRef
    - immutable_attempt_identity_and_monotonic_fence
    - bounded_owner_identity
    - durable_lease_expiry_using_database_time
    - append_only_attempt_and_state_history
    - exact_output_Artifact_or_Content_bindings
    - bounded_failure_and_waiting_evidence
    - explicit_idempotency_for_state_transitions_and_finalization
    - durable_record_and_head_integrity
  prohibit:
    - provider_model_hardware_or_domain_fields_in_universal_execution_identity
    - worker_clock_as_authority
    - mutable_overwrite_of_prior_attempts_or_terminal_history
    - QuarantineRef_as_active_input_output_or_evidence_identity

readiness:
  derive_from:
    - accepted_current_Graph_revision
    - dependency_terminal_states
    - Graph_conditions
    - exact_Task_authority
    - Run_cancellation_and_terminal_state
  require:
    - fan_out_independence
    - fan_in_waits_for_all_required_dependencies
    - false_optional_conditions_satisfy_dependency_semantics_without_execution
    - readiness_recomputed_from_durable_truth_after_restart
  prohibit:
    - worker_demand_as_readiness
    - resource_availability_as_readiness
    - stale_Graph_revision_as_current_readiness_authority

ownership_start_and_heartbeat:
  lease_require:
    - one_current_owner_per_Node_execution
    - exact_current_Graph_revision
    - Node_is_READY
    - Run_is_not_cancelled_or_terminal
    - atomic_owner_attempt_fence_and_lease_commit
  start_revalidate:
    - Project
    - Task_revision_and_digest
    - current_Run
    - current_Graph_revision
    - exact_Node
    - current_owner_attempt_and_fence
    - live_lease
    - cancellation
  heartbeat_require:
    - current_owner_attempt_and_fence
    - live_lease_and_database_time
    - stale_fence_cannot_be_revived
    - cancelled_or_superseded_work_cannot_be_renewed

atomic_finalization:
  transactionally_revalidate_immediately_before_mutation:
    - accessible_exact_Project
    - exact_Task_revision_and_digest
    - Run_not_improperly_terminal_or_cancelled
    - exact_accepted_current_Graph_revision
    - Node_belongs_to_current_Graph
    - current_execution_attempt_owner_and_fence
    - live_lease_where_required
    - Node_not_superseded_or_stale
    - required_dependency_states
    - exact_output_Artifact_or_Content_identity
    - output_contract_and_required_evidence
    - finalization_idempotency
  only_then_commit_together:
    - exact_output_bindings
    - terminal_Node_state
    - required_Event
    - ownership_close_or_release
    - derived_Run_completion_when_all_acceptance_conditions_hold
  prohibit:
    - checks_only_before_long_external_call
    - output_binding_before_final_authority_revalidation
    - terminal_state_without_required_Event
    - orphan_terminal_Event
    - duplicate_finalization_under_retry_or_race

failure_waiting_cancellation_and_recovery:
  failure_record_require:
    - exact_attempt
    - bounded_reason_and_category
    - exact_evidence_or_log_refs
    - retry_or_replan_technical_possibility
    - prior_attempt_history_preserved
  waiting_external_require:
    - bounded_durable_wait_reason
    - exact_evidence_or_checkpoint_refs_when_present
    - no_implicit_authority_extension
  cancellation_order:
    cancellation_commits_first: late_finalization_fails
    finalization_commits_first: preserve_actual_completed_output_and_ordering
    fabricate_cancellation_of_completed_output: false
  expired_worker_scenario:
    - Node_RUNNING_under_fence_N
    - lease_N_expires_after_worker_loss
    - recovery_marks_attempt_N_stale_as_appropriate
    - new_attempt_gets_fence_N_plus_1
    - late_result_from_N_is_rejected
    - current_result_from_N_plus_1_may_complete
  graph_supersession:
    - old_revision_live_lease_cannot_finalize_as_current
    - obsolete_current_work_becomes_STALE
    - completed_old_outputs_remain_historical_reusable_evidence_when_compatible
    - no_historical_output_deletion

run_completion:
  derive_from:
    - accepted_current_Graph_revision
    - all_required_productive_Node_terminal_states
    - Task_acceptance_conditions
    - exact_output_and_evidence_bindings
  require:
    - same_atomic_finalization_transaction_when_last_Node_completes
    - required_Run_completion_Event
    - restart_durable_terminal_state
    - idempotent_duplicate_completion
  prohibit:
    - worker_reported_done_as_sufficient_authority
    - one_Node_completion_as_automatic_Run_completion
    - terminal_state_regression

concurrency_and_recovery:
  require:
    - canonical_lock_order_for_Run_Node_Attempt_Artifact_and_Event_operations
    - real_database_concurrency_tests_where_supported
    - two_owner_Node_race_has_exactly_one_winner
    - two_finalizer_race_accepts_at_most_one
    - finalize_vs_cancel_race_has_one_coherent_authoritative_outcome
    - stale_fence_always_loses
    - independent_Nodes_can_be_current_simultaneously
    - no_global_execution_lock
    - restart_preserves_completed_ready_waiting_failed_and_expired_state
    - restart_never_reexecutes_SUCCEEDED_Node

failure_behavior:
  fail_closed_on:
    - scope_identity_or_exact_relationship_mismatch
    - stale_expired_or_mismatched_owner_attempt_or_fence
    - Run_cancellation_or_terminal_state_conflict
    - Graph_supersession
    - unmet_dependency_or_condition
    - invalid_output_or_evidence_identity
    - output_contract_mismatch
    - idempotency_conflict
    - persisted_state_attempt_output_Event_or_head_integrity_mismatch
  preserve: [durable_evidence, real_failure_cause, unaffected_required_work]
  prohibit: [fabricated_success, fabricated_missing_fact, weakened_architecture_for_unavailable_dependency]

required_test_matrix:
  - {id: T01, prove: all_required_NodeExecution_status_semantics_are_durable_and_validated}
  - {id: T02, prove: fan_in_readiness_waits_for_required_dependencies_and_conditions}
  - {id: T03, prove: two_owners_race_for_one_Node_and_exactly_one_wins}
  - {id: T04, prove: independent_ready_Nodes_can_be_leased_concurrently_without_global_lock}
  - {id: T05, prove: start_and_heartbeat_require_current_live_owner_fence_and_lease}
  - {id: T06, prove: expired_attempt_recovery_marks_stale_and_allocates_higher_fence}
  - {id: T07, prove: late_fence_N_result_is_rejected_after_fence_N_plus_1}
  - {id: T08, prove: cancelled_Run_rejects_Node_start_heartbeat_and_finalization}
  - {id: T09, prove: finalize_vs_cancel_race_has_one_coherent_authoritative_outcome}
  - {id: T10, prove: Graph_revision_v1_late_result_is_rejected_after_v2_supersession}
  - {id: T11, prove: finalization_revalidates_exact_Project_Task_Run_Graph_Node_owner_fence_lease_and_dependencies}
  - {id: T12, prove: finalization_atomically_binds_exact_outputs_Node_state_and_required_Event}
  - {id: T13, prove: injected_finalization_failure_rolls_back_outputs_state_Event_and_Run_completion}
  - {id: T14, prove: duplicate_finalization_retry_is_idempotent_and_conflicting_retry_fails}
  - {id: T15, prove: two_finalizers_race_and_at_most_one_result_is_authoritative}
  - {id: T16, prove: failure_preserves_attempt_bounded_reason_evidence_and_retry_or_replan_signal}
  - {id: T17, prove: WAITING_EXTERNAL_is_durable_bounded_and_does_not_extend_stale_authority}
  - {id: T18, prove: last_required_Node_finalization_atomically_completes_Run_and_appends_Event}
  - {id: T19, prove: Run_does_not_complete_when_required_work_or_Task_acceptance_is_unsatisfied}
  - {id: T20, prove: restart_preserves_completed_ready_waiting_failed_and_expired_state_without_reexecuting_success}
  - {id: T21, prove: state_attempt_output_and_head_tampering_fail_closed}
  - {id: T22, prove: no_provider_domain_resource_readiness_or_fixed_repair_loop_coupling_exists}

kpi:
  double_owned_nodes: 0
  accepted_stale_results: 0
  accepted_cancelled_results: 0
  terminal_state_regressions: 0
  completed_nodes_reexecuted_after_restart: 0
  orphan_terminal_events: 0

implementation_method:
  - verify_exact_P0_08_remote_handoff
  - inspect_exact_current_source_and_accepted_interfaces
  - write_failure_first_tests_for_readiness_ownership_fencing_recovery_finalization_and_cancellation
  - implement_minimum_complete_P0_09
  - define_and_enforce_canonical_Run_Node_Attempt_Artifact_Event_lock_order
  - use_existing_exact_identity_Graph_Artifact_Event_and_fenced_Run_seams
  - run_focused_tests
  - run_relevant_P0_01_through_P0_08_regressions
  - run_strict_typecheck
  - build_and_inspect_actual_package_artifact
  - inspect_persistence_schema_indexes_triggers_foreign_keys_and_transaction_boundaries

publication:
  when_implementation_complete:
    - record_source_commit
    - commit_coherent_P0_09_result
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
    - replace_04_with_exact_P0_10_packet
    - close_P0_09_before_opening_P0_10
  continue_numbered_prompts_one_at_a_time: true
  broad_real_historical_mining: false
```
