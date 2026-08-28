# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P0-08
  global_number: 8
  phase: P0
  title: Durable Append-Only Event Ledger
  state: READY_AFTER_P0_07_DURABLE_CLOSE
  exact_prompt:
    title: 08_P0-08_Durable_Append_Only_Event_Ledger.md.docx
    drive_id: 1UtCBREk13USF2egMgZrqws_2PUCEAFeQ6VBfh3Y04aY
    canonical_text_sha256: 3b1f7fb3bd8b239289daef3220f8ec78f5a334168b92a50dc5e0c97878964012
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P0-07
    result_commit: c420772708bc64054fdea2d8ed663ed7b550b13f
    result_tree: c284e6c00997b3e691dce0510c3f7ad421425d35
    remote_readback: VERIFIED
  numbered_successor: P0-09

goal:
  establish:
    - durable_append_only_meaningful_execution_Event_ledger
    - universal_extensible_Event_envelope
    - per_Run_monotonic_sequence
    - explicit_retry_idempotency
    - transaction_bound_state_plus_Event_append
    - restart_durable_meaningful_execution_chronology
  guarantee:
    - Event_history_survives_logs_provider_traces_worker_memory_and_chat
    - Events_are_evidence_not_a_second_mutable_state_authority
    - large_payloads_are_referenced_not_embedded
    - obvious_secrets_and_unbounded_blobs_do_not_enter_metadata

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
    - P0_07_exact_remote_handoff
  rules:
    - inspect_current_state_before_edit
    - preserve_valid_newer_local_work
    - reuse_valid_earlier_implementation_and_results
    - reconcile_existing_equivalent_interfaces_by_semantics
    - missing_handoff_paperwork_is_not_a_blocker_when_exact_source_is_observable

input_scope:
  required:
    - 03_BIELLA_CURRENT_STATE.md
    - exact_P0_08_canonical_prompt
    - P0_02_Project_interfaces
    - P0_04_Task_and_TaskRef_interfaces
    - P0_05_Run_ExecutionAttempt_and_fencing_interfaces
    - P0_06_Artifact_and_ContentRef_interfaces
    - P0_07_Graph_GraphRef_Node_and_NodeRef_interfaces
    - directly_touched_repository_files
  conditional:
    - current_Biella_project_instructions
    - earlier_accepted_contracts_actually_used_by_this_task
  prohibited_by_default:
    - other_43_unopened_prompt_bodies
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
    required_interfaces: [TaskRef, TaskRevisionService]
    required_semantics: [exact_immutable_Task_revision_and_digest]
  P0_05:
    result_commit: 8f53a1fd641ad46c893239cd8279f310432086bc
    required_interfaces: [Run, RunRef, ExecutionAttempt, RunService]
    required_semantics:
      - exact_Project_and_Task_binding
      - append_only_Run_state_history
      - current_fenced_authority
      - caller_owned_atomic_transaction_authority_seam
  P0_06:
    result_commit: 747a0b59a296890202be39128c455240d87274f2
    required_interfaces: [ArtifactRef, ContentRef]
    required_semantics:
      - exact_immutable_payload_identity
      - large_payload_storage_location_is_not_Event_identity
  P0_07:
    result_commit: c420772708bc64054fdea2d8ed663ed7b550b13f
    result_tree: c284e6c00997b3e691dce0510c3f7ad421425d35
    required_interfaces: [GraphRef, NodeRef]
    required_semantics:
      - exact_Project_Task_Run_and_Graph_revision_binding
      - immutable_Node_identity
      - Scheduler_and_resource_allocator_not_yet_present

scope:
  in:
    - opaque_Project_scoped_EventRef
    - immutable_extensible_Event
    - exact_optional_Task_Run_Graph_and_Node_refs_with_relationship_validation
    - durable_per_Run_monotonic_sequence_allocator
    - bounded_event_type_object_refs_metadata_and_payload_identity
    - optional_actor_identity_as_bounded_evidence_not_authority
    - explicit_idempotency_identity_for_logical_retry
    - appendEvent
    - transaction_bound_append
    - Run_event_query_in_sequence_order
    - append_only_update_delete_guards
    - record_digest_relationship_and_sequence_integrity
    - restart_concurrency_and_atomic_rollback
  out:
    - provider_model_worker_or_hardware_selection
    - new_Scheduler_or_resource_allocator
    - remote_execution_or_queue_dispatch
    - generic_log_telemetry_ingestion
    - Event_as_mutable_current_state_machine
    - physical_object_or_secret_storage
    - later_numbered_prompt_implementation

required_interfaces:
  exact: [Event, EventRef]
  required_APIs: [appendEvent, transaction_bound_append, Run_event_query]
  accepted_service_name: [EventLedger, EventService]
  rule:
    accepted_existing_semantic_equivalent_may_be_mapped: true
    do_not_duplicate_architecture_due_to_name_difference: true

event_contract:
  require:
    - opaque_stable_event_id
    - exact_ProjectRef
    - optional_exact_TaskRef
    - optional_exact_RunRef
    - optional_exact_GraphRef
    - optional_exact_NodeRef
    - positive_per_Run_sequence_for_Run_scoped_Event
    - extensible_bounded_event_type_string
    - bounded_exact_object_refs
    - bounded_small_metadata
    - immutable_payload_or_ContentRef_digest_identity_when_present
    - timezone_aware_durable_database_time
    - canonical_semantic_digest
    - durable_record_digest
    - explicit_bounded_idempotency_key
  relationship_rules:
    - all_present_refs_share_exact_Project_scope
    - Task_Run_Graph_Node_relationships_match_durable_records
    - Graph_and_Node_refs_imply_their_exact_Run_and_Task_bindings
    - payload_ContentRef_is_immutable_identity_not_embedded_large_content
  optional: [actor_identity_as_bounded_absolute_ref]
  prohibit:
    - closed_event_type_enum
    - provider_or_domain_specific_Event_subclasses
    - wall_clock_only_Run_ordering
    - QuarantineRef_as_active_object_or_payload_identity

append_only_ledger:
  require:
    - normal_API_has_no_Event_update_or_delete
    - database_update_delete_guards
    - per_Run_sequence_unique_monotonic_and_gap_checked
    - duplicate_idempotency_key_same_semantics_returns_same_Event
    - duplicate_idempotency_key_conflicting_semantics_fails
    - restart_preserves_exact_sequence_chronology_and_digests
    - operator_can_reconstruct_meaningful_Run_chronology_without_process_logs
  not_an_event:
    - duplicate_telemetry_line
    - generic_log_spam
    - unbounded_stdout
    - raw_provider_trace

transaction_bound_append:
  require:
    - caller_owned_existing_database_transaction
    - same_database_identity_validation
    - no_internal_commit_or_rollback_of_caller_transaction
    - exact_Project_Task_Run_scope_validation_inside_transaction
    - current_fenced_Run_authority_when_transition_requires_execution_authority
    - state_transition_and_Event_commit_or_rollback_together
    - injected_failure_leaves_neither_transition_nor_Event
    - retry_after_transient_failure_does_not_double_append_completion_Event
  current_required_proof:
    - one_real_existing_Run_state_transition_with_terminal_or_cancellation_Event
  prohibit:
    - fabricated_atomicity_across_separate_transactions
    - orphan_terminal_Event
    - terminal_state_without_its_required_Event

metadata_and_payload_boundary:
  small_metadata:
    - bounded_entry_count
    - bounded_keys_and_scalar_values
    - deterministic_JSON_canonicalization
  reject_or_sanitize_obvious_secret_fields:
    - credentials
    - passwords
    - raw_tokens
    - authorization_headers
    - api_keys
    - private_keys
  reject_from_ordinary_metadata:
    - giant_stdout
    - full_model_prompts
    - full_model_outputs
    - unbounded_or_nested_blobs
  large_payload_rule:
    - use_ArtifactRef_or_ContentRef
    - persist_only_exact_ref_and_digest_evidence_in_Event_row

failure_behavior:
  fail_closed_on:
    - malformed_EventRef_or_Event_envelope
    - missing_or_unauthorized_Project
    - nonexistent_cross_scope_or_mismatched_Task_Run_Graph_Node_ref
    - stale_or_mismatched_Run_authority_when_required
    - duplicate_Run_sequence
    - idempotency_conflict
    - obvious_secret_or_unbounded_metadata
    - oversized_embedded_payload
    - persisted_digest_relationship_sequence_or_head_mismatch
  preserve: [durable_evidence, real_failure_cause, unaffected_required_work]
  prohibit: [fabricated_success, mocked_real_infrastructure_claim, silently_dropped_required_completion_Event]

concurrency_and_recovery:
  current_reality:
    Graph_present: true
    Scheduler_present: false
    resource_allocator_present: false
    do_not_fabricate_missing_later_interfaces: true
  require:
    - real_transactional_concurrency_in_existing_durable_database
    - concurrent_Run_Event_appends_have_unique_ordered_sequences
    - independent_Run_ledgers_can_progress
    - one_durable_winner_for_conflicting_idempotency_identity
    - readers_observe_one_consistent_Event_ledger_snapshot
    - restart_preserves_verified_Event_history
    - stale_owners_cannot_append_authoritative_transition_Events

required_test_matrix:
  - {id: T01, prove: append_one_Project_scoped_Event_and_read_it_back}
  - {id: T02, prove: Run_event_query_returns_durable_monotonic_sequence_order_not_wall_clock_order}
  - {id: T03, prove: concurrent_appends_to_one_Run_allocate_unique_gap_free_sequences}
  - {id: T04, prove: independent_Run_event_appends_can_both_complete}
  - {id: T05, prove: normal_API_and_database_guards_reject_Event_update_and_delete}
  - {id: T06, prove: injected_state_plus_Event_failure_rolls_back_both}
  - {id: T07, prove: successful_state_transition_and_required_Event_commit_atomically}
  - {id: T08, prove: identical_idempotent_retry_returns_same_Event_without_double_append}
  - {id: T09, prove: conflicting_idempotency_retry_fails_closed}
  - {id: T10, prove: exact_Project_Task_Run_Graph_and_Node_refs_validate_and_cross_scope_refs_fail}
  - {id: T11, prove: arbitrary_future_event_type_requires_no_kernel_enum_change}
  - {id: T12, prove: large_payload_is_referenced_by_Artifact_or_Content_identity_not_embedded}
  - {id: T13, prove: obvious_secret_fields_and_unbounded_metadata_do_not_persist}
  - {id: T14, prove: stale_Run_owner_cannot_append_authoritative_transition_Event}
  - {id: T15, prove: restart_preserves_Event_records_sequences_idempotency_and_Run_chronology}
  - {id: T16, prove: persisted_digest_sequence_relationship_and_head_tampering_fail_closed}
  - {id: T17, prove: meaningful_Run_chronology_reconstructs_without_process_logs}
  - {id: T18, prove: log_spam_is_not_automatically_persisted_and_no_provider_domain_or_closed_type_coupling_exists}

kpi:
  mutable_events: 0
  duplicate_run_sequences: 0
  orphan_terminal_events: 0
  cross_project_event_leaks: 0
  obvious_secret_fields_persisted: 0

implementation_method:
  - verify_exact_P0_07_remote_handoff
  - inspect_exact_current_source_and_accepted_interfaces
  - write_failure_first_tests_for_identity_sequence_idempotency_scope_secrets_and_atomicity
  - implement_minimum_complete_P0_08
  - integrate_exact_Project_Task_Run_Graph_Node_Artifact_and_Content_identity
  - use_existing_fenced_Run_and_caller_transaction_seams_without_inventing_scheduler
  - run_focused_tests
  - run_relevant_P0_01_through_P0_07_regressions
  - run_strict_typecheck
  - build_and_inspect_actual_package_artifact
  - inspect_persistence_schema_indexes_triggers_foreign_keys_and_transaction_boundaries

publication:
  when_implementation_complete:
    - record_source_commit
    - commit_coherent_P0_08_result
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
    - replace_04_with_exact_P0_09_packet
    - close_P0_08_before_opening_P0_09
  continue_numbered_prompts_one_at_a_time: true
  broad_real_historical_mining: false
```
