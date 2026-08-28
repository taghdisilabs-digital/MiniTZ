# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P1-07
  global_number: 17
  phase: P1
  title: Dynamic Runtime Resource Inventory
  state: READY_AFTER_P1_06_DURABLE_CLOSE
  exact_prompt:
    title: 17_P1-07_Dynamic_Runtime_Resource_Inventory.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P1/17_P1-07_Dynamic_Runtime_Resource_Inventory.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P1/17_P1-07_Dynamic_Runtime_Resource_Inventory.md.docx
    drive_id: 17jLplTvv6Fr1_1LBWFq93JWwjt3-zG-0FWCpBEbYUUc
    local_docx_sha256: 62ce3c5e5f58614c1b2fb2b1308f67e0d6da20561b75e1f0fba4fbe14fecc40a
    live_drive_exported_docx_sha256: 047d0ba7dcfb9b2a963fa74c8f22006322ea325ae297531aadd3d22d047019ea
    canonical_text_sha256: 4978af71f689d07ca1ba46abbf198ae5235352622fe9d04f2e9e8308e31b25e1
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P1-06
    result_commit: ec0bbdf9f9cbb0d64bf82bf0f8fa53471327060a
    result_tree: e6020758dfeaf1e528ccaffbe32c78e0afd245c2
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_functional_type_build_and_installed_restart: VERIFIED
  numbered_successor: P1-08

goal:
  establish:
    - provider_neutral_measured_Resource_truth
    - explicit_configured_expected_versus_observed_physical_effective_available_state
    - durable_fresh_health_and_locality_ResourceSnapshot_evidence
    - replaceable_real_local_and_deterministic_test_ResourceObserver_interfaces
    - technical_resource_fit_classification_without_Capability_mutation
  preserve:
    - exact_Project_runtime_host_and_resource_identity
    - unknown_metrics_as_unknown
    - zero_one_or_many_heterogeneous_GPU_support
    - semantic_Capability_identity_during_resource_shortage
    - P1_06_checkpoint_resume_and_all_earlier_isolation_identity_fence_provenance_and_durability_contracts

prewrite_observation:
  required:
    - actual_repository_or_worktree
    - branch
    - source_commit_and_tree
    - dirty_state
    - migrations_and_tests_if_present
    - AGENTS_policy_and_instruction_files_if_present
    - accepted_Capability_Artifact_workspace_runtime_Event_and_durable_evidence_interfaces_directly_needed
    - exact_P1_06_remote_handoff
    - actual_local_CPU_RAM_storage_network_container_or_cgroup_observation_sources
    - actual_GPU_presence_or_absence_without_assuming_vendor
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reuse_valid_earlier_implementation_and_results
    - reconcile_existing_equivalent_interfaces_by_semantics
    - remeasure_volatile_host_state_instead_of_treating_recorded_configuration_as_truth
    - missing_handoff_paperwork_is_not_a_blocker_when_exact_source_is_observable

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P1_07_canonical_prompt
    - accepted_Capability_identity_and_registry_interfaces
    - accepted_Artifact_ContentRef_Event_and_runtime_identity_interfaces_when_used
    - accepted_P1_06_checkpoint_and_resume_interfaces_when_directly_needed_for_restart_evidence
    - directly_touched_repository_files_and_required_regression_tests
  conditional:
    - current_Biella_project_instructions
    - existing_scheduler_or_resource_semantics_only_if_already_accepted_and_directly_needed
    - platform_specific_observation_sources_only_when_present_and_truthful
  prohibited_by_default:
    - unopened_P1_08_through_P4_prompt_bodies
    - broad_historical_backup_or_legacy_reuse_material
    - unrelated_website_work
    - broad_Drive_GitHub_or_filesystem_audits

dependencies:
  P1_06:
    result_commit: ec0bbdf9f9cbb0d64bf82bf0f8fa53471327060a
    result_tree: e6020758dfeaf1e528ccaffbe32c78e0afd245c2
    required_semantics:
      - RunCheckpoint_is_immutable_versioned_content_addressed_and_exactly_attributed
      - current_durable_state_wins_over_older_checkpoint_evidence
      - valid_completed_outputs_are_reused_without_stale_fence_acceptance
      - restart_does_not_require_provider_session_cache_conversation_or_prior_workspace_materialization
      - object_storage_latency_does_not_hold_the_global_SQLite_writer_lock
  earlier_accepted_contracts:
    required_semantics:
      - Project_identity_and_authorization_are_exact_and_fail_closed
      - Capability_is_open_versioned_semantic_identity_not_hardware_inventory
      - Artifact_and_ContentRef_identity_and_provenance_are_immutable
      - Event_chronology_and_RunMemory_reconstruction_are_restart_durable
      - Run_and_Node_execution_owners_attempts_and_fences_are_exact

scope:
  in:
    - Resource
    - ResourceSnapshot
    - ResourceObserver
    - evaluateResourceFit
    - configured_or_published_expected_capacity
    - observed_physical_effective_and_available_capacity
    - cgroup_and_container_limits
    - zero_one_and_multiple_heterogeneous_GPUs
    - arbitrary_GPU_vendors_models_and_features
    - CPU_topology_count_and_load
    - RAM_total_free_effective_and_available
    - GPU_VRAM_total_free_effective_and_available
    - local_storage_capacity_free_and_throughput_hints
    - network_reachability_latency_and_bandwidth_hints
    - runtime_and_container_capability
    - model_tool_Artifact_and_workspace_locality
    - queue_allocation_pressure_health_and_known_cost
    - snapshot_observation_time_freshness_and_staleness
    - real_local_observer
    - deterministic_fake_or_reference_observer_for_tests
    - durable_resource_observation_health_and_locality_evidence
  out:
    - P1_08_or_later_scheduler_architecture
    - routing_or_provider_selection_policy
    - later_locality_learning
    - Capability_deletion_or_redefinition_due_to_resource_shortage
    - NVIDIA_specific_or_other_vendor_locked_kernel_schema
    - silent_Task_acceptance_weakening
    - unrelated_domain_or_provider_specialization

required_interfaces:
  create_or_reconcile:
    - Resource
    - ResourceSnapshot
    - ResourceObserver
    - evaluateResourceFit
  Resource_fields_or_equivalents:
    - provider_neutral_resource_id
    - resource_kind
    - locality_host_or_runtime_identity
    - configured_or_static_attributes
    - ownership_and_scope_metadata
  ResourceSnapshot_fields_or_equivalents:
    - exact_resource_id
    - observed_at
    - freshness_or_expiration_semantics
    - health
    - measured_physical_effective_and_available_capacity
    - current_usage_and_pressure
    - runtime_and_container_limits
    - model_tool_Artifact_and_workspace_locality
    - known_cost_with_source_or_unknown
    - durable_record_or_evidence_identity
  fit_results:
    - FIT
    - FIT_REDUCED
    - REQUIRES_OTHER_RESOURCE
    - TEMPORARILY_UNAVAILABLE
    - UNKNOWN
  semantic_name_mapping:
    TEMP_UNAVAILABLE_in_restored_prompt_text: TEMPORARILY_UNAVAILABLE
    duplicate_fit_enum_value_required: false

configured_vs_observed:
  require:
    - configured_capacity_is_never_labeled_measured
    - observed_physical_capacity_is_distinct_from_effective_capacity
    - effective_capacity_accounts_for_container_or_cgroup_limits
    - available_capacity_accounts_for_current_usage_or_pressure
    - configured_GPU_VRAM_does_not_imply_free_VRAM
  prohibit:
    - historical_or_recorded_host_inventory_as_current_observation
    - absent_metric_as_zero
    - observer_failure_as_healthy
    - once_observed_hardware_as_permanent

observer_contract:
  real_local:
    - use_actual_host_or_runtime_information
    - classify_unavailable_platform_sources_honestly
    - support_CPU_only_and_no_GPU_without_error
    - preserve_unknowns_when_measurement_is_unavailable
  deterministic_test:
    - arbitrary_GPU_vendor
    - multi_GPU_and_changing_VRAM
    - cgroup_or_low_RAM
    - stale_and_fresh_snapshots
    - unhealthy_and_recovered_resource
    - locality_and_pressure_states
  failure:
    observer_error_result: UNKNOWN_or_stale_with_real_cause
    fabricated_zero_or_healthy_result: false

resource_fit:
  rules:
    - consume_exact_Resource_and_ResourceSnapshot_evidence
    - distinguish_current_unavailability_from_semantic_Capability_validity
    - return_UNKNOWN_when_required_metrics_are_unknown
    - return_TEMPORARILY_UNAVAILABLE_for_transient_health_pressure_or_availability_failure
    - return_REQUIRES_OTHER_RESOURCE_when_this_resource_cannot_satisfy_hard_technical_requirements
    - return_FIT_REDUCED_only_when_a_smaller_or_slower_variant_is_technically_possible_and_Task_permits_it
    - never_silently_weaken_Task_acceptance
    - never_modify_or_delete_Capability

loss_and_failure_behavior:
  fail_closed_on:
    - scope_or_identity_mismatch
    - authority_or_integrity_mismatch
    - corrupt_or_incompatible_durable_snapshot
    - stale_snapshot_presented_as_fresh
    - configured_value_presented_as_observed
  preserve:
    - durable_resource_observation_and_health_evidence
    - exact_unknown_values
    - Capability_definition_and_history
    - unaffected_resource_observations
    - real_observer_failure_cause
  prohibit:
    - fabricated_success_capacity_health_locality_cost_or_missing_fact
    - silent_destructive_repair
    - weakened_architecture_for_unavailable_dependency

concurrency_and_recovery:
  require:
    - independent_observation_or_work_may_proceed_when_dependencies_side_effects_and_resource_constraints_allow
    - restart_preserves_Resource_identity_and_config_where_appropriate
    - restart_takes_fresh_observations_instead_of_reusing_stale_measurements_as_current
    - existing_Run_Node_and_checkpoint_fences_remain_authoritative
    - stale_owners_or_results_remain_rejected
  prohibit:
    - global_pause_for_slow_independent_observer
    - observer_side_effects_on_Capability

required_test_matrix:
  - {id: T01, prove: Resource_ResourceSnapshot_ResourceObserver_and_evaluateResourceFit_interfaces_are_provider_neutral_and_exactly_identified}
  - {id: T02, prove: actual_local_CPU_RAM_storage_and_runtime_observer_reports_REAL_values_and_unknowns_without_fabrication}
  - {id: T03, prove: CPU_only_and_no_GPU_state_are_valid_observations}
  - {id: T04, prove: arbitrary_GPU_vendor_and_features_are_accepted_without_kernel_vendor_lockin}
  - {id: T05, prove: multiple_heterogeneous_GPUs_preserve_per_device_identity_capacity_health_and_VRAM}
  - {id: T06, prove: configured_physical_effective_used_and_available_capacity_remain_distinct}
  - {id: T07, prove: low_RAM_and_cgroup_or_container_limits_bound_effective_capacity_truthfully}
  - {id: T08, prove: observation_time_freshness_and_staleness_are_explicit_and_stale_is_never_used_as_fresh}
  - {id: T09, prove: changing_VRAM_usage_and_availability_produce_new_snapshots_without_mutating_history}
  - {id: T10, prove: observer_failure_and_unknown_metrics_remain_UNKNOWN_or_stale_with_real_cause_not_zero_or_healthy}
  - {id: T11, prove: loaded_model_tool_warm_cache_Artifact_and_workspace_locality_round_trip_as_observed_evidence}
  - {id: T12, prove: unhealthy_then_recovered_resource_preserves_history_and_current_health_truth}
  - {id: T13, prove: evaluateResourceFit_returns_all_five_classifications_with_exact_causes_and_no_Task_acceptance_weakening}
  - {id: T14, prove: resource_shortage_or_GPU_removal_does_not_delete_or_mutate_Capability}
  - {id: T15, prove: restart_preserves_Resource_identity_and_config_but_requires_fresh_observation_and_all_predecessor_type_build_install_gates_pass_without_skips_placeholders_or_TODO_tests}

kpi:
  configured_as_observed_errors: 0
  stale_snapshots_used_as_fresh: 0
  capabilities_deleted_due_to_resource_shortage: 0
  unknown_metrics_fabricated: 0
  hardware_vendor_kernel_lockin: 0

completion_gate:
  require:
    - Resource_identity_and_observation_evidence_are_durable_exact_and_provider_neutral
    - configured_expected_and_observed_physical_effective_available_values_are_distinct
    - actual_local_observer_reports_only_real_current_measurements_or_explicit_unknowns
    - fake_observer_is_deterministic_and_clearly_REFERENCE_or_TEST
    - zero_one_many_and_arbitrary_vendor_GPU_shapes_are_supported
    - freshness_health_locality_pressure_and_known_cost_semantics_are_explicit
    - all_five_resource_fit_results_are_evidence_backed
    - Capability_survives_shortage_unchanged
    - all_required_tests_and_regressions_pass_without_skips_placeholders_or_TODOs

implementation_method:
  - verify_exact_P1_06_remote_handoff
  - inspect_exact_Capability_Artifact_runtime_Event_and_durable_evidence_interfaces_directly_needed
  - reobserve_actual_local_CPU_RAM_storage_network_container_cgroup_and_GPU_state
  - add_task_scoped_failing_tests_before_implementation_or_defect_fix
  - implement_minimal_provider_neutral_Resource_and_ResourceSnapshot_contracts
  - implement_replaceable_real_local_and_deterministic_test_observers
  - implement_durable_observation_freshness_health_and_locality_evidence
  - implement_evidence_backed_evaluateResourceFit_without_Capability_mutation
  - exercise_CPU_only_no_GPU_arbitrary_vendor_multi_GPU_cgroup_stale_changing_locality_health_recovery_and_unknown_cases
  - run_focused_P1_07_tests
  - run_relevant_predecessor_regressions_and_full_required_suite
  - run_strict_typecheck_compileall_and_build
  - inspect_actual_wheel_and_clean_install_restart_smoke
  - obtain_independent_changed_code_review_before_publication

publication:
  when_complete:
    - record_source_commit
    - commit_coherent_P1_07_result
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
    - replace_04_with_exact_P1_08_packet_only_after_P1_07_durable_close
    - close_P1_07_before_opening_P1_08
  continue_numbered_prompts_one_at_a_time: true
  broad_real_historical_mining: false
```
