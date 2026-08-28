# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P1-03
  global_number: 13
  phase: P1
  title: Isolated Versioned Project Memory
  state: READY_AFTER_P1_02_DURABLE_CLOSE
  exact_prompt:
    title: 13_P1-03_Isolated_Versioned_Project_Memory.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P1/13_P1-03_Isolated_Versioned_Project_Memory.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P1/13_P1-03_Isolated_Versioned_Project_Memory.md.docx
    drive_id: 1c_gu5vm-Zg4qmLk6fqipkS2s7RuHocrEJqG7Ce4S0mA
    local_docx_sha256: 25c6c26b471fe7f3826e9d2fc8741ca20a261458a219b2ab030a6c906be2fb65
    live_drive_exported_docx_sha256: 1c7461cc6e43c379de67599f574d62578e338d5b3af330e0f513333b6864ded5
    canonical_text_sha256: e81ff72e3fe027f13553de5f4790bd146f06105c0c048de071021bddb0606c99
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P1-02
    result_commit: 609fbeccb37592c4094a409f04134cc404a38073
    result_tree: feccfd5a33b951a3330adbb7e6b436852f6cfb75
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    exact_remote_archive_build_and_restart: VERIFIED
  numbered_successor: P1-04

goal:
  establish:
    - isolated_versioned_Project_scoped_knowledge_for_accepted_facts_requirements_decisions_preferences_asset_relationships_and_domain_knowledge
    - explicit_provenance_bound_placement_before_observations_become_Project_truth
    - non_destructive_supersession_and_conflict_aware_current_resolution
    - durable_authoritative_structured_memory_independent_from_future_derived_indexes
  preserve:
    - Project_isolation_and_exact_identity
    - migration_firewall_and_raw_QuarantineRef_rejection
    - immutable_Artifact_Run_Task_Graph_Event_and_RunMemory_evidence
    - no_automatic_Project_to_Engine_promotion
    - all_P0_through_P1_02_durability_validation_authority_and_evidence_contracts

prewrite_observation:
  required:
    - actual_repository_or_worktree
    - branch
    - source_commit_and_tree
    - dirty_state
    - migrations_and_tests_if_present
    - AGENTS_policy_and_instruction_files_if_present
    - accepted_Project_Artifact_Run_Task_and_migration_boundary_interfaces_directly_needed
    - exact_P1_02_remote_handoff
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reuse_valid_earlier_implementation_and_results
    - reconcile_existing_equivalent_interfaces_by_semantics
    - missing_handoff_paperwork_is_not_a_blocker_when_exact_source_is_observable

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P1_03_canonical_prompt
    - accepted_Project_scope_and_Project_record_interfaces
    - accepted_Artifact_ContentRef_Run_and_exact_provenance_interfaces_only_when_directly_needed
    - migration_firewall_admission_types_only_when_enforcing_raw_QuarantineRef_rejection
    - directly_touched_repository_files_and_required_regression_tests
  conditional:
    - current_Biella_project_instructions
    - earlier_accepted_contracts_actually_used_by_this_task
  prohibited_by_default:
    - unopened_P1_04_through_P4_prompt_bodies
    - broad_historical_backup_or_legacy_reuse_material
    - unrelated_website_work
    - broad_Drive_GitHub_or_filesystem_audits

dependencies:
  P1_02:
    result_commit: 609fbeccb37592c4094a409f04134cc404a38073
    result_tree: feccfd5a33b951a3330adbb7e6b436852f6cfb75
    required_semantics:
      - exact_Run_state_and_output_evidence_are_reconstructable_without_conversation_or_provider_session_state
      - immutable_projection_is_not_second_authority
      - restart_integrity_scope_denial_and_divergence_detection_hold
  earlier_accepted_contracts:
    required_semantics:
      - Project_identity_and_authorization_are_exact_and_fail_closed
      - Artifact_ContentRef_Run_Task_and_Event_provenance_are_immutable_and_Project_scoped
      - raw_QuarantineRef_is_not_an_active_runtime_identity

scope:
  in:
    - ProjectKnowledge_immutable_versioned_record
    - ProjectKnowledgeRef_exact_identity
    - knowledge_type_statement_or_payload_ref_applicability_sources_evidence_status_supersedes_and_contradicts
    - explicit_placement_from_permitted_observation_owner_decision_or_validated_Project_source
    - candidate_observation_that_does_not_auto_promote
    - non_destructive_versioning_and_supersession
    - unresolved_conflict_preservation_and_explicit_resolution
    - authoritative_structured_search_list_history_and_current_resolution
    - restart_and_cache_or_index_loss_durability
    - exact_cross_Project_denial
  out:
    - automatic_Run_model_or_tool_output_promotion
    - automatic_Project_to_Engine_Knowledge_promotion
    - raw_chat_or_model_output_as_authoritative_memory
    - raw_legacy_donor_or_QuarantineRef_admission
    - embeddings_vector_index_or_P2_retrieval
    - later_numbered_prompt_architecture
    - unrelated_domain_or_provider_specialization

required_interfaces:
  create_or_reconcile:
    - ProjectKnowledge
    - ProjectKnowledgeRef
    - explicit_placement_API
    - current_resolution_API
    - supersession_API
  reconstructable_fields_or_equivalents:
    - project_id
    - knowledge_id_and_version
    - knowledge_type_or_category
    - statement_value_or_exact_content_ref
    - applicability
    - source_and_evidence_refs
    - status_and_currentness
    - created_at
    - supersedes_ref
    - contradicts_refs
  authority_rule:
    ProjectKnowledge_requires_explicit_accepted_placement: true
    generated_observation_is_not_Project_truth: true
    ProjectKnowledge_never_becomes_Engine_Knowledge_automatically: true
    derived_index_is_rebuildable_and_non_authoritative: true

placement_and_resolution:
  required_sequence:
    - authenticate_exact_Project_scope
    - validate_explicit_placement_authority_and_idempotency
    - bind_exact_source_provenance_and_evidence_refs
    - reject_raw_QuarantineRef_and_unaccepted_generated_output
    - create_new_immutable_version_without_rewriting_history
    - record_supersedes_or_contradicts_relationships_exactly
    - resolve_current_only_when_authoritative_history_is_unambiguous_or_explicitly_resolved
    - preserve_all_conflicting_candidates_and_provenance
  invariants:
    - same_human_key_or_name_may_exist_independently_across_Projects
    - supersession_never_deletes_or_mutates_prior_version
    - unresolved_contradiction_never_becomes_arbitrary_last_write_wins_truth
    - future_index_deletion_cannot_delete_ProjectKnowledge
    - Run_model_or_tool_output_requires_explicit_acceptance_before_placement

consistency_and_failure_behavior:
  fail_closed_on:
    - Project_scope_mismatch
    - identity_authority_or_integrity_mismatch
    - raw_QuarantineRef_admission
    - provenance_or_evidence_mismatch
    - unresolved_current_conflict
    - invalid_supersession_or_contradiction_relationship
  preserve:
    - durable_evidence
    - real_failure_cause
    - historical_versions
    - conflicting_candidates_and_exact_provenance
    - unaffected_required_work
  prohibit:
    - fabricated_acceptance
    - fabricated_missing_fact
    - silent_destructive_repair
    - automatic_truth_from_generated_output
    - mocked_real_infrastructure_classification
    - weakened_architecture_for_unavailable_dependency

concurrency_and_recovery:
  require:
    - use_existing_Graph_Scheduler_and_resource_authority_when_execution_is_needed
    - independent_work_remains_concurrent_when_dependencies_side_effects_and_resources_allow
    - already_verified_durable_work_survives_recovery
    - stale_owners_and_results_remain_rejected
    - concurrent_conflicting_placements_preserve_one_coherent_authoritative_outcome_or_explicit_conflict
    - no_global_serialization_beyond_required_Project_memory_commit_boundaries

required_test_matrix:
  - {id: T01, prove: create_and_restart_versioned_ProjectKnowledge_with_exact_Project_identity}
  - {id: T02, prove: exact_statement_or_ContentRef_applicability_sources_evidence_and_created_identity_round_trip}
  - {id: T03, prove: Alpha_Unreal_and_Beta_Godot_preferences_coexist_without_global_default}
  - {id: T04, prove: cross_Project_read_by_known_ID_fails_privately}
  - {id: T05, prove: cross_Project_write_and_supersede_fail}
  - {id: T06, prove: v2_supersedes_v1_non_destructively_and_v1_remains_readable}
  - {id: T07, prove: current_resolution_returns_v2_only_when_history_is_unambiguous}
  - {id: T08, prove: unresolved_contradictory_current_facts_return_conflict_not_arbitrary_choice}
  - {id: T09, prove: explicit_conflict_resolution_preserves_both_candidates_and_chosen_currentness}
  - {id: T10, prove: Run_model_and_tool_output_remain_candidate_observations_without_automatic_promotion}
  - {id: T11, prove: explicit_permitted_placement_binds_exact_provenance_and_acceptance}
  - {id: T12, prove: raw_QuarantineRef_is_rejected_at_every_ProjectKnowledge_admission_seam}
  - {id: T13, prove: no_automatic_Project_to_Engine_Knowledge_promotion_or_global_default}
  - {id: T14, prove: cache_or_derived_index_deletion_does_not_remove_authoritative_ProjectKnowledge}
  - {id: T15, prove: required_predecessor_regressions_typecheck_build_and_installed_wheel_restart_pass_without_skips_placeholders_or_TODO_tests}

kpi:
  cross_project_ProjectMemory_reads: 0
  automatic_Run_output_to_Project_truth: 0
  automatic_Project_to_Engine_promotion: 0
  raw_quarantine_admissions: 0
  destructive_supersession: 0
  ambiguous_conflicts_silently_resolved: 0

completion_gate:
  require:
    - ProjectKnowledge_is_isolated_versioned_provenance_bound_and_restart_durable
    - explicit_placement_is_required_before_observation_becomes_accepted_Project_memory
    - old_versions_and_conflicting_candidates_remain_durably_readable
    - current_resolution_is_deterministic_or_reports_unresolved_conflict
    - raw_QuarantineRef_generated_output_and_cross_Project_authority_fail_closed
    - derived_index_absence_does_not_remove_or_change_authoritative_memory
    - all_required_tests_and_regressions_pass_without_skips_placeholders_or_TODOs

implementation_method:
  - verify_exact_P1_02_remote_handoff
  - inspect_exact_Project_Artifact_Run_and_migration_boundary_interfaces_directly_needed
  - add_task_scoped_failing_tests_before_implementation_or_defect_fix
  - implement_minimal_versioned_ProjectKnowledge_and_exact_reference_contracts
  - implement_explicit_placement_supersession_conflict_and_current_resolution
  - exercise_real_restart_scope_denial_quarantine_generated_output_and_index_loss_cases
  - run_focused_P1_03_tests
  - run_relevant_predecessor_regressions_and_full_required_suite
  - run_strict_typecheck_compileall_and_build
  - inspect_actual_wheel_and_clean_install_restart_smoke
  - obtain_independent_changed_code_review_before_publication

publication:
  when_complete:
    - record_source_commit
    - commit_coherent_P1_03_result
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
    - replace_04_with_exact_P1_04_packet_only_after_P1_03_durable_close
    - close_P1_03_before_opening_P1_04
  continue_numbered_prompts_one_at_a_time: true
  broad_real_historical_mining: false
```
