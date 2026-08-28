# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P1-08
  global_number: 18
  phase: P1
  title: Concurrent Resource-Aware Graph Scheduler
  state: READY_AFTER_P1_07_DURABLE_CLOSE
  exact_prompt:
    title: 18_P1-08_Concurrent_Resource_Aware_Graph_Scheduler.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P1/18_P1-08_Concurrent_Resource_Aware_Graph_Scheduler.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P1/18_P1-08_Concurrent_Resource_Aware_Graph_Scheduler.md.docx
    drive_id: 1cYQKnQeJWQ90Lv9AQQH_oGVAGKgtgvGitU7C3hhGKUo
    local_docx_sha256: fa38650e05b2eb897a0b69cb257bb2d71f38feb7d03173b38073934e665643cd
    live_drive_exported_docx_sha256: f96c27f83e410afcd9bc78588c4664c839a14046646e68e2a8e332eb4ddf2ff7
    canonical_text_sha256: 62c4dfe4980347425e58b9c4321308e1b423c4a340ffd4e7ec689cc9bcc59977
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P1-07
    result_commit: eebcbfeeed692031657138626e7972f3829c8fd6
    result_tree: 25523deabb6bcaccfccd29404b74a0b4ab97d40e
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_functional_type_build_and_installed_restart: VERIFIED
  numbered_successor: P1-09

goal:
  establish:
    - durable_concurrent_scheduling_of_semantically_READY_Graph_Nodes
    - explicit_semantic_readiness_versus_current_resource_schedulability
    - fenced_leased_resource_scoped_ResourceAllocation
    - atomic_or_canonically_ordered_multi_resource_acquisition_without_partial_leaks
    - transparent_priority_deadline_fairness_and_aging
    - restart_durable_allocation_recovery_queue_pressure_and_scheduler_metrics
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_and_resource_identity
    - P1_07_measured_fresh_health_locality_and_fit_truth
    - completed_Node_outputs_and_terminal_Run_authority
    - independent_CPU_GPU_RAM_storage_and_network_utilization
    - semantic_Capability_identity
    - all_earlier_isolation_provenance_durability_and_quarantine_firewall_contracts

prewrite_observation:
  required:
    - actual_repository_or_worktree
    - branch
    - source_commit_and_tree
    - dirty_state
    - migrations_and_tests_if_present
    - AGENTS_policy_and_instruction_files_if_present
    - accepted_Graph_Node_Run_execution_attempt_fence_Event_checkpoint_and_Resource_interfaces_directly_needed
    - exact_P1_07_remote_handoff
    - actual_available_CPU_RAM_storage_network_cgroup_and_GPU_state
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reuse_valid_earlier_implementation_and_results
    - reconcile_existing_equivalent_interfaces_by_semantics
    - use_fresh_ResourceSnapshot_truth_instead_of_recorded_configuration_as_current_capacity
    - missing_handoff_paperwork_is_not_a_blocker_when_exact_source_is_observable

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P1_08_canonical_prompt
    - accepted_Graph_Node_Run_and_NodeExecution_interfaces
    - accepted_Resource_ResourceSnapshot_ResourceObserver_and_evaluateResourceFit_interfaces
    - accepted_Event_checkpoint_Artifact_and_workspace_identity_interfaces_when_directly_used
    - directly_touched_repository_files_and_required_regression_tests
  conditional:
    - current_Biella_project_instructions
    - existing_scheduler_or_queue_semantics_only_if_already_accepted_and_directly_needed
    - actual_concurrency_primitives_available_on_the_current_CPU_host
  prohibited_by_default:
    - unopened_P1_09_through_P4_prompt_bodies
    - provider_routing_from_later_numbered_prompts
    - learned_locality_policy
    - broad_historical_backup_or_legacy_reuse_material
    - unrelated_website_work
    - broad_Drive_GitHub_or_filesystem_audits

dependencies:
  P1_07:
    result_commit: eebcbfeeed692031657138626e7972f3829c8fd6
    result_tree: 25523deabb6bcaccfccd29404b74a0b4ab97d40e
    required_semantics:
      - Resource_identity_and_config_are_immutable_Project_scoped_and_provider_neutral
      - ResourceSnapshot_is_freshness_bounded_health_and_locality_evidence
      - configured_expected_is_distinct_from_observed_physical_effective_used_and_available
      - evaluateResourceFit_has_five_explicit_evidence_backed_results
      - unknown_or_stale_metrics_never_become_current_capacity
      - exact_Artifact_and_workspace_locality_is_scope_checked_and_durable
  earlier_accepted_contracts:
    required_semantics:
      - Project_identity_and_authorization_are_exact_and_fail_closed
      - Graph_is_immutable_and_deterministically_topological
      - Run_and_NodeExecution_attempt_fences_are_authoritative
      - terminal_state_and_late_stale_fence_results_are_rejected
      - completed_Artifact_outputs_and_checkpoint_resume_evidence_survive_restart
      - Event_chronology_and_RunMemory_reconstruction_are_restart_durable

scope:
  in:
    - Scheduler_service
    - ResourceAllocation
    - reservation_dispatch_release_heartbeat_and_recovery_APIs
    - scheduler_metrics
    - semantic_READY_state
    - current_resource_schedulability
    - multiple_dispatches_per_scheduler_cycle
    - resource_scoped_capacity_budgets
    - resource_scoped_exclusivity
    - atomic_database_multi_resource_reservation_or_documented_canonical_acquisition_order
    - priority
    - deadline
    - fairness
    - queue_age_and_aging
    - deterministic_current_locality_preference
    - side_effect_target_conflicts
    - allocation_generation_fence_lease_expiry_and_heartbeat
    - executor_loss_cancellation_terminal_release_and_restart_reconstruction
    - durable_queue_pressure_and_scheduler_metrics
  out:
    - P1_09_or_later_provider_routing
    - opaque_optimizer
    - learned_locality_policy
    - provider_specific_worker_categories
    - global_heavyweight_lock
    - silent_Task_acceptance_weakening
    - unrelated_domain_or_provider_specialization

required_interfaces:
  create_or_reconcile:
    - SchedulerService
    - ResourceAllocation
    - reservation_API
    - dispatch_API
    - release_or_recovery_API
    - SchedulerMetrics
  ResourceAllocation_fields_or_equivalents:
    - exact_Project_Run_Graph_Node_and_attempt_identity
    - current_execution_fence
    - exact_Resource_and_fresh_ResourceSnapshot_evidence
    - requested_and_effective_capacity_by_resource
    - exclusivity_or_conflict_identity
    - allocation_generation_or_fence
    - lease_expiry_and_heartbeat
    - created_updated_released_or_expired_timestamps
    - explicit_status
    - immutable_or_append_only_durable_evidence_identity
  scheduler_results_or_equivalents:
    - semantic_READY_but_waiting_for_resource
    - reserved
    - dispatched
    - not_currently_schedulable_with_exact_cause
    - terminal_or_cancelled_release
    - expired_or_recovered

readiness_and_fit:
  require:
    - Graph_dependency_readiness_is_computed_separately_from_resource_schedulability
    - only_fresh_exact_ResourceSnapshot_evidence_may_authorize_current_capacity
    - P1_07_FIT_or_explicitly_permitted_FIT_REDUCED_is_required_before_reservation
    - UNKNOWN_stale_unhealthy_or_insufficient_fit_never_becomes_silent_dispatch_authority
    - Resource_shortage_does_not_change_Graph_READY_or_Capability_identity
  prohibit:
    - treating_READY_as_already_allocated
    - treating_configured_capacity_as_observed_available
    - provider_category_shortcuts
    - silent_acceptance_weakening

allocation_contract:
  require:
    - one_atomic_SQLite_reservation_transaction_or_one_documented_canonical_resource_order_with_full_rollback
    - exact_capacity_accounting_against_fresh_effective_and_available_budgets
    - only_contested_capacity_or_exclusivity_serializes
    - allocation_fence_or_generation_is_monotonic
    - lease_and_heartbeat_use_durable_database_time_where_authoritative
    - release_is_idempotent_and_fence_aware
    - stale_allocation_or_execution_fence_cannot_finalize_new_work
  resource_scoped_conflicts:
    - GPU_or_VRAM_exclusivity
    - port
    - mutable_workspace_target
    - license_seat
    - exact_side_effect_target
  prohibit:
    - partial_multi_resource_hold
    - deadlock_by_disjoint_partial_acquisition
    - invalid_RAM_VRAM_CPU_storage_or_network_overcommit
    - exclusive_resource_double_allocation
    - heavyweight_global_lock

concurrent_dispatch:
  require:
    - schedule_more_than_one_independent_productive_Node_per_cycle_when_fit_allows
    - use_real_thread_or_process_overlap_evidence_not_sequential_fake_timestamps
    - CPU_work_may_continue_while_an_unrelated_GPU_is_exclusively_busy
    - different_GPU_or_resource_identities_may_overlap
    - same_exclusive_resource_waits_without_blocking_unrelated_resources
    - stability_and_acceptance_constraints_bound_utilization

ranking_fairness_and_locality:
  transparent_order:
    - hard_dependency_and_scope_authority
    - current_resource_fit
    - side_effect_and_exclusivity_conflict
    - explicit_priority_or_deadline_when_current_contracts_supply_them
    - queue_age_and_aging
    - Project_or_Task_fairness_where_relevant
    - deterministic_exact_current_locality_preference
  rules:
    - high_priority_never_bypasses_scope_resource_or_side_effect_constraints
    - lower_priority_work_avoids_indefinite_starvation_under_ordinary_load
    - locality_uses_exact_P1_07_evidence_only
    - queue_pressure_is_durable_and_observable

loss_and_failure_behavior:
  fail_closed_on:
    - scope_or_identity_mismatch
    - authority_attempt_or_fence_mismatch
    - stale_unknown_corrupt_or_incompatible_ResourceSnapshot
    - allocation_integrity_or_capacity_mismatch
    - exclusive_or_side_effect_conflict
    - late_stale_allocator_executor_or_completion
  preserve:
    - completed_Node_outputs
    - durable_allocation_lease_release_and_recovery_evidence
    - exact_failure_or_wait_cause
    - unaffected_independent_Node_progress
    - semantic_READY_and_Capability_identity
  prohibit:
    - fabricated_dispatch_completion_capacity_or_health
    - silent_destructive_repair
    - leaked_allocation_after_terminal_or_cancellation
    - weakened_architecture_for_unavailable_dependency

concurrency_and_recovery:
  require:
    - scheduler_or_worker_restart_reconstructs_current_allocations_and_queued_work
    - expired_lease_or_executor_loss_recovers_capacity_with_a_new_fence
    - cancellation_and_terminal_completion_release_capacity_idempotently
    - completed_outputs_remain_authoritative
    - stale_owner_allocation_or_result_remains_rejected
    - unrelated_resources_continue_during_slow_or_contended_work
  prohibit:
    - permanent_resource_leak
    - global_pause_for_one_contended_resource
    - resurrection_of_cancelled_or_terminal_work

required_test_matrix:
  - {id: T01, prove: SchedulerService_ResourceAllocation_reservation_dispatch_recovery_and_metrics_interfaces_are_exactly_identified_and_Project_scoped}
  - {id: T02, prove: semantic_READY_is_distinct_from_current_resource_schedulability_with_exact_wait_causes}
  - {id: T03, prove: independent_B_and_C_Nodes_dispatch_with_actual_productive_concurrency_greater_than_one}
  - {id: T04, prove: CPU_Node_overlaps_GPU_exclusive_Node_without_global_serialization}
  - {id: T05, prove: same_exclusive_GPU_or_VRAM_budget_serializes_only_the_conflicting_Node_then_runs_it}
  - {id: T06, prove: two_distinct_GPU_or_resource_identities_allow_overlap}
  - {id: T07, prove: CPU_GPU_network_and_CPU_Node_mix_uses_available_resources_concurrently_and_reports_allocation_evidence}
  - {id: T08, prove: RAM_or_other_capacity_overcommit_and_UNKNOWN_or_stale_snapshot_dispatch_are_rejected}
  - {id: T09, prove: atomic_multi_resource_acquisition_has_no_deadlock_partial_hold_or_leak_under_competing_orders}
  - {id: T10, prove: allocation_lease_expiry_executor_loss_and_new_fence_recovery_reject_late_old_allocator_or_executor_results}
  - {id: T11, prove: scheduler_restart_reconstructs_allocations_queues_pressure_and_completed_output_authority}
  - {id: T12, prove: cancellation_terminal_completion_and_duplicate_release_are_idempotent_fence_aware_and_leak_free}
  - {id: T13, prove: priority_and_deadline_ranking_are_transparent_and_never_bypass_hard_constraints}
  - {id: T14, prove: aging_and_fairness_prevent_indefinite_lower_priority_or_cross_Project_starvation_under_ordinary_load}
  - {id: T15, prove: exact_side_effect_target_conflicts_serialize_without_global_lock_and_all_predecessor_type_build_install_restart_gates_pass_without_skips_placeholders_or_TODO_tests}

kpi:
  independent_nodes_serialized_without_reason: 0
  exclusive_resource_double_allocations: 0
  invalid_resource_overcommit: 0
  resource_leaks_after_terminal: 0
  permanent_starvation_under_ordinary_load: 0
  global_heavyweight_lock: 0
  useful_non_gating_evidence:
    max_observed_productive_concurrency: record_actual_value
    resource_allocation_evidence: required

completion_gate:
  require:
    - durable_fenced_leased_ResourceAllocation_is_exactly_bound_to_execution_and_resource_evidence
    - semantic_READY_and_current_schedulability_are_distinct
    - independent_nodes_actually_overlap_when_resources_allow
    - only_contested_capacity_exclusivity_or_side_effect_targets_serialize
    - multi_resource_acquisition_is_atomic_or_canonically_ordered_and_leak_free
    - priority_deadline_fairness_aging_locality_and_pressure_are_transparent
    - expiry_executor_loss_cancellation_terminal_and_restart_recovery_are_durable_and_fence_safe
    - scheduler_metrics_and_max_productive_concurrency_are_evidence_backed
    - all_required_tests_and_regressions_pass_without_skips_placeholders_or_TODOs

implementation_method:
  - verify_exact_P1_07_remote_handoff
  - inspect_exact_Graph_Node_Run_execution_Event_checkpoint_Resource_and_locality_interfaces_directly_needed
  - reobserve_actual_local_CPU_RAM_storage_network_cgroup_and_GPU_state
  - add_task_scoped_failing_tests_before_implementation_or_defect_fix
  - implement_minimal_durable_ResourceAllocation_and_scheduler_contracts
  - implement_atomic_multi_resource_reservation_and_resource_scoped_conflicts
  - implement_multiple_dispatches_per_cycle_with_actual_concurrency_evidence
  - implement_priority_deadline_fairness_aging_locality_pressure_metrics_and_recovery
  - exercise_overlap_contention_overcommit_expiry_stale_fence_cancellation_restart_starvation_and_side_effect_cases
  - run_focused_P1_08_tests
  - run_relevant_predecessor_regressions_and_full_required_suite
  - run_strict_typecheck_compileall_and_build
  - inspect_actual_wheel_and_clean_install_restart_smoke
  - obtain_independent_changed_code_review_before_publication

publication:
  when_complete:
    - record_source_commit
    - commit_coherent_P1_08_result
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
  - MAX_OBSERVED_PRODUCTIVE_CONCURRENCY
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
    - replace_04_with_exact_P1_09_packet_only_after_P1_08_durable_close
    - close_P1_08_before_opening_P1_09
  continue_numbered_prompts_one_at_a_time: true
  broad_real_historical_mining: false
```
