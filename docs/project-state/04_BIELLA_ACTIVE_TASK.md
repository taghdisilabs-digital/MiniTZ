# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P0-05
  global_number: 5
  phase: P0
  title: Durable Run Identity, Attempts, Leases, and Fencing
  state: READY_AFTER_P0_04_DURABLE_CLOSE
  exact_prompt:
    title: 05_P0-05_Durable_Run_Identity_Attempts_Leases_and_Fencing.md.docx
    drive_id: 1a_Xqlzv1HhPcuuI8PNHVVDYhpfQYX_bsm3fnCAYWXwQ
    canonical_text_sha256: 4efa15cf86b7133ef006d6e2a5bf0aca5e130d8e6422e7683f7ccc08999e1b08
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P0-04
    result_commit: 9b28ccf93c4cb8edd771f474903bcfa5e7592b1b
    result_tree: 45b6cffa2eed4f2540e856f7ad7700c4a9c21926
    remote_readback: VERIFIED
  numbered_successor: P0-06

goal:
  establish:
    - durable_Run_identity_bound_to_exact_Task_revision_and_digest
    - immutable_ExecutionAttempt_lineage
    - atomic_lease_ownership_with_monotonic_fencing
    - reusable_current_Run_authority_validation
    - durable_race_safe_cancellation
  guarantee:
    - Task_intent_is_separate_from_execution_lineage
    - stale_executors_cannot_mutate_current_Run_authority
    - owner_identity_reuse_never_restores_an_old_fence
    - lease_decisions_do_not_trust_worker_local_time

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
    - P0_04_exact_remote_handoff
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reuse_valid_earlier_implementation_and_results
    - reconcile_existing_equivalent_interfaces_by_semantics
    - missing_handoff_paperwork_is_not_a_blocker_when_exact_source_is_observable

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P0_05_canonical_prompt
    - P0_04_Task_interfaces
    - P0_02_Project_interfaces
    - directly_touched_repository_files
  conditional:
    - current_Biella_project_instructions
    - earlier_accepted_contracts_actually_used_by_this_task
  prohibited_by_default:
    - other_46_unopened_prompt_bodies
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
      - exact_Project_binding
      - cross_Project_access_fails_closed
  P0_04:
    result_commit: 9b28ccf93c4cb8edd771f474903bcfa5e7592b1b
    result_tree: 45b6cffa2eed4f2540e856f7ad7700c4a9c21926
    required_interfaces:
      - Task
      - TaskRef
      - TaskRevisionService
    required_semantics:
      - exact_Project_and_Task_revision_identity
      - deterministic_canonical_Task_digest
      - immutable_Task_revision_history

scope:
  in:
    - Run_bound_to_exact_Project_Task_id_Task_revision_and_Task_digest
    - immutable_append_only_ExecutionAttempt_lineage
    - current_Run_status_attempt_fence_owner_and_lease_state
    - atomic_Run_lease_acquire_renew_and_release
    - lease_expiration_and_authority_replacement
    - monotonically_increasing_fences
    - authoritative_durable_state_time
    - durable_cancellation_marker
    - assertCurrentRunAuthority_seam
    - transactional_concurrency_and_restart_recovery
    - durable_integrity_guards
  out:
    - Node_scheduler
    - resource_locks
    - global_heavyweight_or_GPU_lock
    - full_finalization
    - checkpoint_or_resume
    - routing
    - provider_or_hardware_categories
    - approval_workflow
    - P0_06_or_later_prompt_implementation

required_interfaces:
  exact:
    - Run
    - ExecutionAttempt
    - acquire_Run_lease
    - renew_Run_lease
    - release_Run_lease
    - assertCurrentRunAuthority
    - requestRunCancellation
  rule:
    accepted_existing_semantic_equivalent_may_be_mapped: true
    do_not_duplicate_architecture_due_to_name_difference: true

run_contract:
  bind_exactly:
    - ProjectRef
    - Task_id
    - Task_revision
    - Task_canonical_digest
  durable_state:
    - opaque_stable_run_id
    - status
    - current_attempt
    - current_fence
    - current_owner
    - current_lease
    - created_at
    - updated_at
    - cancellation_marker
  invariants:
    - later_Task_revision_never_changes_existing_Run_meaning
    - Run_identity_is_provider_resource_hardware_and_worker_neutral
    - exact_Task_revision_and_digest_are_revalidated_at_binding_and_authority_boundaries

execution_attempt_contract:
  immutable_append_only: true
  record:
    - opaque_stable_attempt_id
    - exact_Run_identity
    - positive_gap_free_attempt_number
    - monotonically_increasing_fence
    - owner_or_executor_ref
    - lease_acquired_at
    - lease_expires_at
    - started_at
    - completed_at
    - terminal_outcome
  preserve:
    - every_ownership_generation
    - every_fence_transition_across_restart
  prohibit:
    - destructive_attempt_counter_that_erases_history
    - mutation_or_deletion_of_prior_attempt_identity

lease_operations:
  acquire:
    - atomically_select_one_current_owner
    - increment_fence_monotonically_for_each_new_ownership_generation
    - create_attempt_and_current_authority_as_one_transaction
    - allow_expired_ownership_to_be_replaced
    - reject_live_competing_owner
    - reject_cancelled_or_terminal_Run
  renew:
    - require_exact_Project_Run_attempt_owner_and_fence
    - require_current_live_lease
    - reject_expired_stale_cancelled_or_terminal_authority
  release:
    - require_exact_Project_Run_attempt_owner_and_fence
    - require_current_live_lease
    - old_fence_cannot_release_newer_owner
  time_authority:
    source: authoritative_database_or_equivalent_durable_clock
    caller_or_worker_timestamp_decides_authority: false

fencing:
  monotonic: true
  authority_is_determined_by:
    - exact_Run_identity
    - exact_current_attempt
    - exact_current_fence
    - exact_current_owner_when_applicable
    - live_lease
    - noncancelled_nonterminal_state
  authority_is_not_restored_by:
    - owner_or_executor_name_reuse
    - late_result_from_expired_attempt
    - caller_supplied_wall_clock
  stale_fence_behavior: REJECT

authority_validator:
  interface: assertCurrentRunAuthority
  reusable_by_later_finalization_paths: true
  validate:
    - authenticated_Project_scope
    - exact_Run
    - exact_Task_revision_and_digest
    - current_attempt_and_fence
    - current_owner_when_applicable
    - lease_validity_by_durable_time
    - cancellation_state
    - terminal_state
  prohibit:
    - weaker_adapter_specific_fencing_checks
    - accepted_late_old_finalization

cancellation:
  durable: true
  race_safe: true
  after_authoritative_cancellation:
    - acquisition_cannot_revive_execution
    - renewal_cannot_revive_execution
    - late_results_cannot_pass_current_authority
    - attempt_history_remains_readable
  does_not_require:
    - global_approval_workflow

persistence:
  require:
    - durable_Run_identity_and_exact_Task_binding
    - durable_current_fence_owner_lease_and_cancellation
    - append_only_attempt_history
    - atomic_acquisition_attempt_and_fence_transition
    - atomic_renew_release_and_cancellation_transitions
    - exact_Project_scope_on_every_query
    - restart_round_trip
    - integrity_validation
    - no_partial_acquisition_state
  schema_change:
    permitted_only_when_required_for_P0_05: true
    must_be_reported_exactly: true

failure_behavior:
  fail_closed_on:
    - malformed_or_unauthorized_Project_scope
    - malformed_or_missing_Run_identity
    - missing_or_mismatched_Task_revision_or_digest
    - attempt_owner_or_fence_mismatch
    - stale_or_expired_lease
    - cancelled_or_terminal_Run
    - persisted_integrity_mismatch
    - transaction_fault
  preserve:
    - durable_attempt_and_fence_evidence
    - real_failure_cause
  prohibit:
    - fabricated_success
    - fabricated_missing_facts
    - mocked_unavailable_integration_reported_as_real

concurrency_and_recovery:
  require:
    - real_transactional_concurrency_where_durable_database_exists
    - two_owners_racing_for_one_Run_yield_exactly_one_current_owner
    - concurrent_independent_Runs_can_hold_independent_leases
    - expired_lease_can_be_replaced_with_higher_fence
    - stale_renew_and_release_cannot_change_newer_authority
    - restart_preserves_Run_attempt_fence_and_cancellation_history
    - transaction_fault_cannot_partially_commit_fence_owner_or_attempt
  prohibit:
    - global_heavyweight_resource_lock
    - GPU_global_execution_lock

required_test_matrix:
  - id: T01
    prove: create_Run_bound_to_exact_Project_Task_revision_and_digest
  - id: T02
    prove: changed_Task_revision_does_not_change_existing_Run_binding
  - id: T03
    prove: two_owners_race_for_one_Run_and_exactly_one_wins
  - id: T04
    prove: concurrent_independent_Runs_can_hold_independent_leases
  - id: T05
    prove: lease_expiry_then_new_owner_receives_higher_fence
  - id: T06
    prove: old_owner_and_fence_are_rejected_even_when_owner_identity_is_reused
  - id: T07
    prove: old_fence_renewal_fails
  - id: T08
    prove: old_fence_release_cannot_release_newer_owner
  - id: T09
    prove: late_old_finalization_authority_check_fails
  - id: T10
    prove: cancellation_blocks_renewal_acquisition_and_finalization_without_erasing_history
  - id: T11
    prove: transaction_fault_cannot_leave_fence_owner_attempt_partially_committed
  - id: T12
    prove: restart_preserves_attempt_and_fence_history
  - id: T13
    prove: caller_or_worker_timestamp_does_not_decide_lease_authority
  - id: T14
    prove: no_provider_hardware_worker_category_scheduler_resource_lock_or_routing_coupling

kpi:
  double_current_owners: 0
  accepted_stale_fences: 0
  stale_renewals_accepted: 0
  fence_regressions: 0
  partial_acquisition_transactions: 0
  worker_clock_used_as_authority: 0

implementation_method:
  - verify_exact_P0_04_remote_handoff
  - inspect_exact_current_source_and_accepted_interfaces
  - write_failure_first_tests_for_each_Run_ownership_boundary
  - implement_minimum_complete_P0_05
  - use_real_transactional_SQLite_concurrency_and_database_time
  - run_focused_tests
  - run_relevant_P0_01_through_P0_04_regressions
  - run_strict_typecheck
  - build_and_inspect_actual_package_artifact
  - inspect_persistence_schema_indexes_triggers_foreign_keys_and_dependency_boundaries

publication:
  when_implementation_complete:
    - record_source_commit
    - commit_coherent_P0_05_result
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
    - replace_04_with_exact_P0_06_packet
    - close_P0_05_before_opening_P0_06
  continue_numbered_prompts_one_at_a_time: true
  broad_real_historical_mining: false
```
