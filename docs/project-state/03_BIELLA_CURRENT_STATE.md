# 03 — BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v2
state_timestamp_local: "2026-08-28 23:34 Europe/Amsterdam"
state_timestamp_iso: "2026-08-28T23:34:22+02:00"
state_class: VOLATILE
update_rule: replace_stale_values; do_not_append_history

authority:
  if_conflict:
    - CURRENT_EXECUTION_STATE
    - CURRENT_GITHUB_SOURCE
    - CURRENT_CANONICAL_DRIVE
    - VERIFIED_HISTORICAL_EVIDENCE
    - REFERENCE_OR_PLAN
    - INFERENCE
  correction_rule: invalidate_conflicting_assumption; recompute_only_affected_state; preserve_independently_valid_work

engine:
  repository: patrickminitz-web/biella-engine
  branch: main

  observed_remote:
    commit: 3508942cb7527dd0db43d19ae6ce31d937434192
    tree: 9126aa1f965b027c4f922e95f52ce35d2b3c0988
    observed_date: 2026-08-28
    evidence: CURRENT_GITHUB_SOURCE
    observation_context: p1_09_implementation_post_push_exact_readback
    src_present: true
    root_package_json_present: false
    root_pyproject_present: true
    volatile_reobserve_before_next_write: true

  local:
    checkout_path: /root/biella/repos/biella-engine
    checkout_exists: true
    branch: main
    head: 3508942cb7527dd0db43d19ae6ce31d937434192
    tree: 9126aa1f965b027c4f922e95f52ce35d2b3c0988
    upstream: origin/main
    worktree_status: CLEAN_AT_IMPLEMENTATION_READBACK
    newer_valid_work_present: false

  implementation:
    durable_prompts_complete: 19
    durable_prompts_total: 51
    phase: P2
    active_prompt: P2-01
    active_prompt_title: Universal Filesystem Capability Adapter
    p0_01_status: DURABLY_COMPLETE
    p0_01_source_commit: 007c38004e985c26e8ab732e9ef228de4bd409df
    p0_01_result_commit: fa442745b73e02cc2cd67ef0c029973de06bb773
    p0_01_result_tree: 840c45a3cf04c28407e08e5c7e51f11d61e0dadb
    p0_01_remote_readback: VERIFIED
    p0_01_validation:
      unittest: "23 passed; 0 failed; 0 skipped"
      pytest: "23 passed; 12 subtests passed; 0 failed; 0 skipped"
      mypy_strict: "4 source/test files; 0 issues"
      compileall: PASS
      wheel_build: "biella_engine-0.1.0-py3-none-any.whl; required paths inspected"
      installed_wheel_smoke: "runtime import isolated; durable restart round-trip; verified candidate factory"
      independent_review: "READY; no Critical, Important, or Minor findings"
    p0_01_required_remote_paths:
      - .gitignore
      - pyproject.toml
      - src/biella/__init__.py
      - src/biella/migration.py
      - src/biella/runtime.py
      - tests/test_p0_01_migration_firewall.py
    p0_02_status: DURABLY_COMPLETE
    p0_02_source_commit: e042e692d6be6ee797d545ec151f237b05ad589a
    p0_02_result_commit: 2847543e0b3f9bac04e0e879e4b81f748cab712c
    p0_02_result_tree: deedf652f4eafc16b901ea535a4d0adf0663a212
    p0_02_remote_readback: VERIFIED
    p0_02_validation:
      focused_unittest: "18 passed; 0 failed; 0 skipped"
      regression_unittest: "41 passed; 0 failed; 0 skipped"
      pytest: "41 passed; 34 subtests passed; 0 failed; 0 skipped"
      mypy_strict: "6 source/test files; 0 issues"
      compileall: PASS
      wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 cfc735c2a11f8fa85175dcdd2f69b2d43b3bcd48a3f783952941fbcb71e40ed0; required paths inspected"
      installed_wheel_smoke: "capability authorization; foreign-ID impersonation blocked; restart; schema integrity; raw access token at rest zero; Project quarantine dependency zero"
      independent_review: "READY; 0 Critical and 0 Important; sole Minor rollback-coverage gap resolved and all gates rerun"
    p0_02_kpi:
      cross_project_reads: 0
      cross_project_writes: 0
      cross_project_reference_bindings: 0
      project_records_missing_scope: 0
      namespace_collisions_accepted: 0
    p0_02_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/project.py
      - tests/test_p0_02_project_isolation.py
    p0_03_status: DURABLY_COMPLETE
    p0_03_source_commit: 8d2589f758dc4fc6c2a271e9d36cbea20c113473
    p0_03_result_commit: 4288c792d8f5c1fe12ffd3af47deb7d3aab5d9f1
    p0_03_result_tree: 26c62bdd4bf89f3c8cb4a604a89cd6193ed35068
    p0_03_remote_readback: VERIFIED
    p0_03_validation:
      focused_unittest: "20 passed; 0 failed; 0 skipped"
      regression_unittest: "61 passed; 0 failed; 0 skipped"
      pytest: "61 passed; 48 subtests passed; 0 failed; 0 skipped"
      mypy_strict: "8 source/test files; 0 issues"
      compileall: PASS
      wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 b7176c564cb80ffff999392b5ad99d84eb6a01c5eff6e0dc10d39d4933405364; required paths inspected"
      installed_wheel_smoke: "same-version conflict blocked; arbitrary future registration; version history; append-only lifecycle; schema integrity; prohibited coupling zero"
      independent_review: "READY; no Critical, Important, or Minor findings after durability hardening"
    p0_03_kpi:
      new_capability_requires_kernel_change: 0
      closed_capability_enum_required: 0
      provider_fields_required: 0
      hardware_fields_required: 0
      capability_deleted_due_to_resource_shortage: 0
    p0_03_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/capability.py
      - tests/test_p0_03_capability_contract.py
    p0_04_status: DURABLY_COMPLETE
    p0_04_source_commit: 6de13afc4b2c2702a8da4db93aaef445ceb9c26c
    p0_04_result_commit: 9b28ccf93c4cb8edd771f474903bcfa5e7592b1b
    p0_04_result_tree: 45b6cffa2eed4f2540e856f7ad7700c4a9c21926
    p0_04_remote_readback: VERIFIED
    p0_04_validation:
      focused_unittest: "19 passed; 0 failed; 0 skipped"
      regression_unittest: "80 passed; 0 failed; 0 skipped"
      pytest: "80 passed; 51 subtests passed; 0 failed; 0 skipped"
      mypy_strict: "10 source/test files; 0 issues"
      compileall: PASS
      wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 bcccc7c5374d56e75e6462bdcf98e51fad7a5d1829b05a255276289cc16264a0; required paths inspected"
      installed_wheel_smoke: "Task restart round-trip; exact input corruption detected; provider/topology/raw-QuarantineRef runtime dependency zero"
      independent_review: "READY; no Critical, Important, or Minor findings after exact-input durability hardening"
    p0_04_kpi:
      unscoped_tasks: 0
      Task_revision_mutations: 0
      canonical_digest_instability: 0
      raw_quarantine_inputs_accepted: 0
      domain_specific_Task_variants: 0
    p0_04_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/task.py
      - tests/test_p0_04_task_contract.py
    p0_05_status: DURABLY_COMPLETE
    p0_05_source_commit: cd923894087a4d240ebceb40e08197a51baf5ff2
    p0_05_result_commit: 8f53a1fd641ad46c893239cd8279f310432086bc
    p0_05_result_tree: ed4e97846d8c055a0e8967b83a8b100bef481ddf
    p0_05_remote_readback: VERIFIED
    p0_05_validation:
      focused_unittest: "22 passed; 0 failed; 0 skipped"
      regression_unittest: "102 passed; 0 failed; 0 skipped"
      pytest: "102 passed; 63 subtests passed; 0 failed; 0 skipped"
      mypy_strict: "12 source/test files; 0 issues"
      compileall: PASS
      concurrency_repeat: "same-Run acquisition, cancellation/renewal, and reader/writer snapshot races; 10 repeated passes"
      wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 cd04af6d2e66ba5bdbe018db5f18f10c60c8708588eb7e871be20477d431861e; required paths inspected"
      installed_wheel_smoke: "exact Task binding; restart; reused-owner stale fence rejection; append-only completion; cancellation/state-head anchoring; foreign-key check"
      independent_review: "READY; no Critical, Important, or Minor findings after completion, truncation, and read-snapshot hardening"
    p0_05_kpi:
      double_current_owners: 0
      accepted_stale_fences: 0
      stale_renewals_accepted: 0
      fence_regressions: 0
      partial_acquisition_transactions: 0
      worker_clock_used_as_authority: 0
    p0_05_schema_changes:
      - runs
      - execution_attempts
      - execution_attempt_completions
      - run_state_versions
      - run_state_heads
      - run_cancellations
      - exact_Task_revision_digest_foreign_binding
      - append_only_and_monotonic_integrity_triggers
    p0_05_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/run.py
      - tests/test_p0_05_run_leases.py
    p0_06_status: DURABLY_COMPLETE
    p0_06_source_commit: 4723d1502b18a17c75631104bfdfb67df35d6cbe
    p0_06_result_commit: 747a0b59a296890202be39128c455240d87274f2
    p0_06_result_tree: 585ef429b55eed8c261d4af87efe297e2c1a9c67
    p0_06_remote_readback: VERIFIED
    p0_06_validation:
      focused_unittest: "27 passed; 0 failed; 0 skipped"
      regression_unittest: "129 passed; 0 failed; 0 skipped"
      pytest: "129 passed; 80 subtests passed; 0 failed; 0 skipped"
      mypy_strict: "14 source/test files; 0 issues"
      compileall: PASS
      concurrency_repeat: "conflicting revision, independent creation, and publication/cancellation authority races; 10 repeated passes"
      wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 3f443d40208fc99aed70d3de84a3b7807c8ad60e3f9af8efcc8b904ca3b07d9f; required paths inspected"
      installed_wheel_smoke: "Artifact/Source/Derivation/Task/Run exact binding; restart; schema foreign-key integrity"
      independent_review: "READY; no Critical, Important, or Minor findings after byte identity, exact-record, provenance determinism, and physical-location separation hardening"
    p0_06_kpi:
      artifact_without_project_scope: 0
      digest_mismatches_accepted: 0
      artifact_content_identity_conflation: 0
      cross_project_derivations: 0
      immutable_artifacts_silently_mutated: 0
    p0_06_schema_changes:
      - artifact_revisions
      - artifact_heads
      - artifact_source_artifact_bindings
      - artifact_derivations
      - artifact_task_input_bindings
      - exact_source_and_Artifact_record_digest_foreign_bindings
      - append_only_monotonic_and_integrity_triggers
    p0_06_required_remote_paths:
      - pyproject.toml
      - src/biella/__init__.py
      - src/biella/artifact.py
      - src/biella/run.py
      - src/biella/runtime.py
      - src/biella/task.py
      - tests/test_p0_01_migration_firewall.py
      - tests/test_p0_06_artifact_identity.py
    p0_07_status: DURABLY_COMPLETE
    p0_07_source_commit: 92dd254b202cd28241c38b655e14db0ffc1d5728
    p0_07_result_commit: c420772708bc64054fdea2d8ed663ed7b550b13f
    p0_07_result_tree: c284e6c00997b3e691dce0510c3f7ad421425d35
    p0_07_remote_readback: VERIFIED
    p0_07_validation:
      focused_unittest: "28 passed; 0 failed; 0 skipped"
      regression_unittest: "157 passed; 0 failed; 0 skipped"
      pytest: "157 passed; 94 subtests passed; 0 failed; 0 skipped"
      mypy_strict: "16 source/test files; 0 issues"
      compileall: PASS
      concurrency_repeat: "27-test matrix including independent creation, conflicting revision, cancellation/publication authority, and reader/revision snapshot races; 10 repeated passes; final expanded matrix 28 passed"
      wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 c92dc07df517be3080d492f0c633248dc58522e9790f1746ce938fc0341068c0; embedded graph.py sha256 92ae9e1898ec03ac56555d026fd3638cd7f958b9b584eac9915df97f5b997fcf exactly matched source"
      installed_wheel_smoke: "Project/Capability/Task/Run current fence/Graph publication/active read/ready-set round-trip after clean wheel install"
      schema_inspection: "7 Graph and Run-Graph tables; 14 append-only/monotonic guards; exact Artifact record foreign binding; PRAGMA foreign_key_check empty"
      independent_review: "READY; no Critical, Important, or Minor findings after fenced publication, exact-Graph DAG scope, full-history, Artifact evidence, readiness, and exact Run-binding read hardening"
    p0_07_kpi:
      accepted_cycles: 0
      mutated_graph_revisions: 0
      Task_authority_escalations: 0
      parallel_nodes_forced_serial: 0
      mandatory_global_pipeline: 0
      graph_digest_instability: 0
    p0_07_schema_changes:
      - graph_revisions
      - graph_nodes
      - graph_dependencies
      - graph_input_bindings
      - graph_heads
      - run_graph_bindings
      - run_graph_heads
      - exact_Project_Task_Run_Artifact_record_foreign_bindings
      - append_only_monotonic_record_and_relationship_integrity_guards
    p0_07_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/graph.py
      - tests/test_p0_07_graph_contract.py
    p0_08_status: DURABLY_COMPLETE
    p0_08_source_commit: 8e03737c500a6570d1b2e108fde288eb3562986c
    p0_08_result_commit: 486c05f37a8deccfa786fe3781c9267fc96cc74b
    p0_08_result_tree: 7abd3dc98a3689b2c3e0593d4dbdf1207733c67f
    p0_08_remote_readback: VERIFIED
    p0_08_validation:
      focused_unittest: "24 passed; 0 failed; 0 skipped"
      regression_unittest: "181 passed; 0 failed; 0 skipped"
      pytest: "181 passed; 100 subtests passed; 0 failed; 0 skipped"
      mypy_strict: "18 source/test files; 0 issues"
      compileall: PASS
      concurrency_repeat: "same-Run sequence allocation, public cancellation idempotency, Artifact publication/cancellation, and Graph publication/cancellation races; 10 repeated passes"
      wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 a6ac60595e7525dcc57f9c9dc006b2cd23d3c323ddc5a9a9add6f5b80901d48e; embedded event.py sha256 0f6eeb4f251dd3f72515fef7a54b53c1029c33c9fe6b2017a66e664e5818de9e exactly matched source"
      installed_wheel_smoke: "Event/EventRef imports; EventLedger initialization; appendEvent, transaction-bound append, and Run event query interfaces"
      schema_inspection: "events, event_objects, and run_event_heads tables; 6 append-only/monotonic guards; exact Task/Run/Graph/Node/Artifact record foreign bindings; PRAGMA foreign_key_check empty"
      independent_review: "READY; no Critical, Important, or Minor findings after atomic public cancellation, actor byte-bound, common-secret filtering, scope, terminal-idempotency, and nullable-evidence hardening"
    p0_08_kpi:
      mutable_events: 0
      duplicate_run_sequences: 0
      orphan_terminal_events: 0
      cross_project_event_leaks: 0
      obvious_secret_fields_persisted: 0
    p0_08_schema_changes:
      - events
      - event_objects
      - run_event_heads
      - exact_Task_Run_Graph_Node_and_Artifact_record_foreign_bindings
      - append_only_monotonic_scope_sequence_and_record_integrity_guards
      - atomic_Run_cancellation_and_Event_transaction_path
    p0_08_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/event.py
      - src/biella/run.py
      - tests/test_p0_08_event_ledger.py
    p0_09_status: DURABLY_COMPLETE
    p0_09_source_commit: 75745ca434b78862a659aaa947610e46b12dc09e
    p0_09_result_commit: ebcd4ca325ef0455cee91e2959935f6c063a16e3
    p0_09_result_tree: 49453937a2037f1b17b5f4d68530d9bc33793eee
    p0_09_remote_readback: VERIFIED
    p0_09_validation:
      focused_unittest: "25 passed; 0 failed; 0 skipped"
      regression_unittest: "206 passed; 0 failed; 0 skipped"
      pytest: "206 passed; 100 subtests passed; 0 failed; 0 skipped"
      mypy_strict: "20 source/test files; 0 issues"
      compileall: PASS
      concurrency_repeat: "two-owner Node acquisition, finalize/cancel, two-finalizer, and direct Event-cancel/finalize races; 4 real SQLite races repeated 10 times; 40 passed"
      wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 74a8643d8ec66f9d1e64dc0cc251ef0ed8f30c33be8db82e3aa032441b9f762a; embedded execution.py sha256 a22f2a5b6a6081a018c24b033690fdc7b5ae5335bdcb9f88f51fbd8d0567c6a2 exactly matched source"
      installed_wheel_smoke: "NodeExecution and all lease/start/heartbeat/fail/wait/finalize/recoverExpiredExecution/cancelRun interfaces imported from clean wheel"
      schema_inspection: "10 Node execution/completion-manifest tables; immutable state/attempt/output/failure/condition/idempotency/manifest guards; exact Project/Task/Run/Graph/Node/Artifact/Event bindings; PRAGMA foreign_key_check empty"
      independent_review: "READY; no Critical, Important, or Minor findings after Graph-scoped acceptance, terminal acceptance/completion Event manifest binding, cancellation convergence, lock-order, and replay hardening"
      fallow_review: "live graph snapshot graph:0da34faf4b79fe4d postvalidated stale=false; no deterministic findings; Python project node_modules warning non-applicable"
    p0_09_kpi:
      double_owned_nodes: 0
      accepted_stale_results: 0
      accepted_cancelled_results: 0
      terminal_state_regressions: 0
      completed_nodes_reexecuted_after_restart: 0
      orphan_terminal_events: 0
    p0_09_schema_changes:
      - node_executions
      - node_execution_attempts
      - node_execution_attempt_completions
      - node_execution_state_versions
      - node_execution_heads
      - node_execution_bindings
      - node_execution_failures
      - node_condition_results
      - node_transition_idempotency
      - run_completion_manifests
      - completion_evidence_sha256_on_Run_state
      - exact_Project_Task_Run_Graph_Node_Artifact_and_Event_record_bindings
      - append_only_monotonic_manifest_and_transaction_integrity_guards
    p0_09_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/event.py
      - src/biella/execution.py
      - src/biella/run.py
      - tests/test_p0_09_execution_state.py
    p0_10_status: DURABLY_COMPLETE
    p0_10_source_commit: 89723860c4e811d9e81dd70ae9f143354165d072
    p0_10_result_commit: 1573db1a1062bd311603945dd6d4a7323636d6a4
    p0_10_result_tree: 8c4e6ad41fb12601f581affac3e005fe9ceb05a5
    p0_10_remote_readback: VERIFIED
    p0_10_exit_decision: READY_FOR_P1
    p0_10_implementation:
      production_source_changes: 0
      production_defects_found: 0
      qualification_tests_added: 16
      changed_path: tests/test_p0_10_p0_integration_qualification.py
      changed_path_git_blob: 6e844f984e7a04b6c42f7f5bfe5cd7ca3116517b
      changed_path_sha256: 7fe51fb5f1ac807f7841796be9dd6295a37d8a39ecd76246be763cee121f1377
    p0_10_validation:
      focused_unittest: "16 passed; 0 failed; 0 skipped; T15 executed all 206 predecessor cases internally"
      regression_unittest: "222 passed; 0 failed; 0 skipped"
      pytest: "222 passed; 100 subtests passed; 0 failed; 0 skipped"
      mypy_strict: "21 source/test files; 0 issues"
      compileall: PASS
      concurrency_repeat: "T05 independent ownership, T06 recovery fencing, and T12 cancellation/finalization race; 10 repeated passes each; 30 passed"
      schema_inspection: "41 tables; 12 explicit indexes; 74 triggers; WAL; PRAGMA foreign_key_check empty; prohibited schema coupling zero"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      test_quality_scan: "P0 skip, placeholder, TODO, and FIXME hits: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 478e33782bed31d3739d02c0ef888fe2cee0cdef8af671db422227058ca36a88; exact source module byte equality"
      remote_source_wheel: "built from exact GitHub commit archive; sha256 fe71a7b82a3b6130e496da80f4fdb6e62aa7d684dc43828ae2b26c81231997f6; separate writer/reader restart smoke passed"
      independent_review: "READY; no remaining findings after T01, T10, T12, T14, T15, and T16 hardening"
    p0_10_kpi:
      active_raw_legacy_donor_content: 0
      cross_project_reads: 0
      accepted_stale_results: 0
      mutated_Task_or_Graph_revisions: 0
      provider_specific_kernel_requirements: 0
      global_heavyweight_resource_lock: 0
      exact_identity_roundtrip: 100%
      durable_restart_roundtrip: 100%
    p0_10_qualification:
      required_interfaces: VERIFIED
      project_quarantine_isolation: VERIFIED
      explicit_classification: VERIFIED
      provenance_chaining: VERIFIED
      idempotency: VERIFIED
      hostile_instruction_inertness: VERIFIED
      active_runtime_raw_QuarantineRef_dependency: 0
      cancellation_finalization_serialization: VERIFIED
      graph_revision_and_artifact_history: VERIFIED
      kernel_neutrality: VERIFIED
    p0_10_required_remote_paths:
      - tests/test_p0_10_p0_integration_qualification.py
    p1_01_status: DURABLY_COMPLETE
    p1_01_source_commit: bdde4d5dcb5427160e841a4fa41d2148c6fc7d97
    p1_01_result_commit: 6cc8c6a69c9f2051bb3a9755272eff9dcc77da08
    p1_01_result_tree: f9453145afb4d9083e17c4453c9b1f27600a74e2
    p1_01_remote_readback: VERIFIED
    p1_01_implementation:
      production_modules_added: 1
      public_exports_changed: 9
      test_methods_added: 20
      schema_changes: 0
      atomic_object_layout: digest_sharded_content_and_checksummed_metadata_bundle
      development_gate: pinned_local_test_extra
    p1_01_validation:
      focused_unittest: "20 passed; 0 failed; 0 skipped; T15 executed all 222 P0 cases, strict mypy, exact wheel comparison, clean install, and separate-process restart"
      regression_unittest: "242 passed; 0 failed; 0 skipped"
      pytest: "242 passed; 126 subtests passed; 0 failed; 0 skipped"
      mypy_strict: "23 source/test files; 0 issues; mypy 2.3.1"
      compileall: PASS
      concurrency_and_fault_repeat: "7 high-risk cases repeated 10 times; 70 passed"
      test_quality_scan: "P1-01 skip, placeholder, TODO, FIXME, and NotImplemented hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 2fa46eb45393f7dd652def57f12936dff42830c2599d58bf04fb85fd315519f6; 12 source modules byte-identical; separate writer/reader restart passed"
      remote_commit_archive: "sha256 8b772a4b31e05a0a36a1bd49f5654e44c42cf800999749dbc7924c93d2826923"
      remote_source_wheel: "built from exact GitHub commit archive; sha256 122e852187916c4c992eb13ec6bcc135b4ae85affdcfc3189f226342aee3cff6; exact source module equality; separate writer/reader restart passed"
      independent_review: "READY; no Critical or Important findings after immutable snapshot, nonregular object, metadata integrity, strict-gate, and snapshot readback hardening"
    p1_01_kpi:
      content_roundtrip_exact: 100%
      content_corruption_detected: 100%
      partial_objects_published: 0
      path_escapes: 0
      object_identity_tied_to_storage_uri: 0
      cache_eviction_can_destroy_authority: 0
      cross_project_authorization_leaks: 0
    p1_01_qualification:
      ContentObject: VERIFIED
      ObjectStorageBackend: VERIFIED
      filesystem_backend: VERIFIED
      memory_reference_backend: VERIFIED
      streaming_and_expected_identity: VERIFIED
      atomic_deduplication_and_concurrent_first_writer: VERIFIED
      corruption_interruption_restart_and_metadata_integrity: VERIFIED
      quarantine_active_and_Project_authorization_separation: VERIFIED
      provider_and_session_dependency: 0
    p1_01_required_remote_paths:
      - .gitignore
      - pyproject.toml
      - src/biella/__init__.py
      - src/biella/object_store.py
      - tests/test_p1_01_object_store.py
    p1_02_status: DURABLY_COMPLETE
    p1_02_source_commit: 9358b4d474458463e01d2585f82fe6d54dc2817e
    p1_02_result_commit: 609fbeccb37592c4094a409f04134cc404a38073
    p1_02_result_tree: feccfd5a33b951a3330adbb7e6b436852f6cfb75
    p1_02_remote_readback: VERIFIED
    p1_02_implementation:
      production_modules_added: 1
      shared_execution_verifier_hardened: true
      public_exports_changed: 12
      test_methods_added: 20
      schema_changes: 0
      authority_model: immutable_projection_reconstructed_from_one_verified_SQLite_snapshot
      checkpoint_model_tool_payload_policy: reference_only
    p1_02_validation:
      focused_unittest: "20 passed; 0 failed; 0 skipped; T15 executed all 242 predecessors, strict mypy, exact wheel comparison, clean install, and separate-process representative multi-node restart"
      regression_unittest: "262 passed; 0 failed; 0 skipped"
      pytest: "262 passed; 126 subtests passed; 0 failed; 0 skipped"
      mypy_strict: "25 source/test files; 0 issues; mypy 2.3.1"
      compileall: PASS
      test_quality_scan: "P1-02 skip, placeholder, TODO, FIXME, and NotImplemented hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 193941aa997abe20bfd839ca22a699c78d1703ab8f3bedcbbdb826444e45aa61; 13 source modules byte-identical; separate representative writer/reader restart passed"
      remote_commit_archive: "sha256 f783bb18765f1f32823cd3f716fca35921578a68731be1522801fc97df223d5c"
      remote_source_wheel: "built from exact GitHub commit archive; sha256 6f67dd03783ded472033eccc65e8f5b616355939657323b90767554673db22c5; 13 source modules byte-identical; exact remote-source P1-02 gate 20 passed"
      independent_review: "READY; no Critical or Important findings after immutable projection, completion-state binding, uninitialized Graph, orphaned Graph, and subprocess restart hardening"
    p1_02_kpi:
      run_state_lost_after_restart: 0
      conversation_dependency: 0
      provider_session_dependency: 0
      completed_nodes_lost: 0
      Task_revision_drift: 0
      RunMemory_divergence_silently_accepted: 0
    p1_02_qualification:
      RunMemory: VERIFIED
      get_or_reconstruct_RunMemory: VERIFIED
      consistency_validator: VERIFIED
      exact_Project_Task_Run_Graph_identity: VERIFIED
      Node_attempt_owner_fence_failure_output_and_completion_history: VERIFIED
      Event_chronology_and_high_water_mark: VERIFIED
      checkpoint_model_and_tool_reference_seams: VERIFIED
      continuation_and_ready_set: VERIFIED
      one_snapshot_reconstruction_without_second_authority: VERIFIED
      accepted_uninitialized_Graph_state: VERIFIED
      cross_Project_scope_denial: VERIFIED
      provider_conversation_and_cache_dependency: 0
    p1_02_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/execution.py
      - src/biella/run_memory.py
      - tests/test_p1_02_run_memory.py
    p1_03_status: DURABLY_COMPLETE
    p1_03_source_commit: c9cb83f326580cee9221b017942abbd95b835033
    p1_03_result_commit: fafe35bdcabe436da65c6ef95c7376d6a303b07f
    p1_03_result_tree: 5546854ad7997b5c56a579a07de4d4681d007485
    p1_03_remote_readback: VERIFIED
    p1_03_implementation:
      production_modules_added: 1
      public_exports_changed: 12
      test_methods_added: 21
      migrations_added: 0
      schema_tables_added: 5
      authority_model: immutable_Project_scoped_candidates_versions_relations_and_monotonic_heads
      current_resolution_model: deterministic_single_head_or_explicit_conflict
    p1_03_validation:
      focused_unittest: "21 passed; 0 failed; 0 skipped; T15 executed all 262 predecessors, strict mypy, exact wheel comparison, clean install, and separate-process restart"
      independent_functional_unittest: "20 passed; 0 failed; 0 skipped"
      regression_unittest: "283 passed; 0 failed; 0 skipped; 435.919s"
      pytest: "283 passed; 126 subtests passed; 0 failed; 0 skipped; isolated rerun 437.29s"
      parallel_runner_diagnostic: "one pytest run encountered a shared build-directory Errno 17 while unittest built concurrently; isolated full rerun passed; product assertion failures: 0"
      mypy_strict: "27 source/test files; 0 issues; mypy 2.3.1"
      compileall: PASS
      test_quality_scan: "P1-03 skip, placeholder, TODO, FIXME, and NotImplemented hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 f90bbf84af83d268245007d9d46101a001d2495e0882596b5df22dadd275023f; 14 source modules byte-identical"
      remote_commit_archive: "sha256 924dadf5c646ec635dc1c3886e58c6fd79ec23f261041f605548097cdce35468"
      remote_source_wheel: "built from exact GitHub commit archive; sha256 6a3f7b18d0e022aa044e70ddd56476d3fe5c8b5a364762d2223683bfeaa44cb9; 14 source modules byte-identical"
      remote_source_gate: "fresh GitHub clone at exact commit/tree with full history; 21 passed; 0 failed; 0 skipped; 222.197s"
      archive_gate_environment_note: "archive product tests 20 passed; history-aware predecessor gate requires .git and therefore ran from exact fresh GitHub clone"
      independent_review: "READY; no Critical or Important findings after orphan-head integrity hardening; get, list, search, and placement fail closed on complete history deletion"
    p1_03_kpi:
      cross_project_ProjectMemory_reads: 0
      automatic_Run_output_to_Project_truth: 0
      automatic_Project_to_Engine_promotion: 0
      raw_quarantine_admissions: 0
      destructive_supersession: 0
      ambiguous_conflicts_silently_resolved: 0
    p1_03_qualification:
      ProjectKnowledge: VERIFIED
      ProjectKnowledgeRef: VERIFIED
      ProjectKnowledgeCandidate_and_candidate_ref: VERIFIED
      explicit_placement_API: VERIFIED
      supersession_API: VERIFIED
      conflict_aware_current_resolution_API: VERIFIED
      exact_statement_or_ContentRef_and_provenance: VERIFIED
      Project_isolation_and_private_known_ID_denial: VERIFIED
      non_destructive_history_and_conflict_preservation: VERIFIED
      explicit_observation_acceptance_boundary: VERIFIED
      cache_or_index_independence: VERIFIED
      append_only_restart_and_concurrent_head_integrity: VERIFIED
      Engine_promotion_dependency: 0
      raw_QuarantineRef_runtime_dependency: 0
    p1_03_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/project_memory.py
      - tests/test_p1_03_project_memory.py
    p1_04_status: DURABLY_COMPLETE
    p1_04_source_commit: 52eaefba7f577e605c448ab7cdda2e9e2e2d6dbc
    p1_04_result_commit: 757aff748f2156de918e4abeca2e317fc25208a2
    p1_04_result_tree: c6fec721da90759377fab91656ae4eb30199d76f
    p1_04_remote_readback: VERIFIED
    p1_04_implementation:
      production_modules_added: 1
      deployment_tools_added: 1
      public_exports_changed: 18
      test_methods_added: 22
      migrations_added: 0
      schema_tables_added: 12
      authority_model: deployment_provisioned_single_promotion_authority_with_immutable_candidate_decision_evidence_revision_relation_and_head_chains
      classification_model: explicit_ENGINE_PROJECT_or_HISTORICAL_decision_with_independent_cross_Project_scope_evidence_for_ENGINE
      current_resolution_model: deterministic_single_active_revision_or_explicit_conflict_with_non_destructive_history
    p1_04_validation:
      focused_pytest: "22 passed; 0 failed; 0 skipped; 443.50s; T15 executed all 283 predecessors, strict mypy, exact wheel comparison, clean install, deployment root provision, and separate-process restart"
      independent_functional_pytest: "21 passed; 0 failed; 0 skipped; 2.97s"
      regression_unittest: "305 passed; 0 failed; 0 skipped; 885.109s"
      pytest: "305 passed; 126 subtests passed; 0 failed; 0 skipped; 881.73s"
      p0_01_focused_regression: "23 passed; 12 subtests passed; 0 failed; 0 skipped"
      mypy_strict: "30 source/test/ops files; 0 issues; mypy 2.3.1"
      compileall: PASS
      test_quality_scan: "P1-04 skip, placeholder, TODO, FIXME, and NotImplemented executable-test hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 6987fd2064febeafc7676656fd669ad8397c62aa58bc83ef3892259a628484ff; 15 source modules byte-identical"
      remote_source_gate: "fresh GitHub clone at exact commit 757aff748f2156de918e4abeca2e317fc25208a2 and tree c6fec721da90759377fab91656ae4eb30199d76f; functional P1-04 gate 21 passed; 0 failed; 0 skipped"
      remote_source_wheel: "built from exact fresh GitHub clone; sha256 49cba1958bf1f77a90afbe2499389ee5b12ec07d822ca625b137822f714e5c46; 15 source modules"
      remote_required_paths_and_bytes: "GitHub branch, commit, tree, five blob IDs, sizes, and SHA256 bytes independently read back and matched"
      independent_review: "READY; no Critical or Important findings after authority first-caller, full-chain rehash, Run provenance, opaque-scope, crash-recovery, symlink, TOCTOU, prepared-file, and replacement-race hardening"
    p1_04_kpi:
      direct_agent_to_EngineKnowledge_writes: 0
      supported_knowledge_without_provenance: 0
      Project_facts_auto_globalized: 0
      raw_quarantine_promotions: 0
      destructive_knowledge_overwrites: 0
    p1_04_qualification:
      Knowledge: VERIFIED
      KnowledgeCandidate_and_exact_candidate_ref: VERIFIED
      promotion_or_placement_service: VERIFIED
      extensible_scope_classifier: VERIFIED
      deduplication_and_contradiction_resolver: VERIFIED
      ENGINE_PROJECT_and_HISTORICAL_scopes: VERIFIED
      independent_cross_Project_scope_evidence: VERIFIED
      exact_statement_or_ContentRef_and_provenance: VERIFIED
      source_Run_identity_round_trip_restart_and_tamper_detection: VERIFIED
      Project_private_path_ID_preference_endpoint_and_lore_denial: VERIFIED
      normalized_migration_mapping_and_full_provenance: VERIFIED
      hostile_candidate_and_migration_instruction_inertness: VERIFIED
      non_destructive_duplicate_contradiction_supersession_and_history: VERIFIED
      cache_or_index_independence: VERIFIED
      append_only_restart_concurrency_and_idempotency: VERIFIED
      deployment_only_root_provisioning_and_recovery: VERIFIED
      raw_QuarantineRef_runtime_dependency: 0
    p1_04_required_remote_paths:
      - ops/provision_knowledge_root.py
      - src/biella/__init__.py
      - src/biella/engine_memory.py
      - src/biella/runtime.py
      - tests/test_p1_04_engine_knowledge.py
    p1_05_status: DURABLY_COMPLETE
    p1_05_source_commit: 555fadaa4a5557598752e331d9003b0aa0e5b43a
    p1_05_result_commit: 02f89c0d17d2f08a6c7b03f7faa285993f452891
    p1_05_result_tree: 7b8a976bf2a6d6b17a0b85359f6e9b6c570f7358
    p1_05_remote_readback: VERIFIED
    p1_05_implementation:
      production_modules_added: 1
      public_exports_changed: 16
      RunMemory_reference_seam_changed: true
      test_methods_added: 15
      installed_restart_programs_added: 2
      migrations_added: 0
      schema_tables_added: 4
      authority_model: exact_live_NodeExecutionAttempt_owner_fence_Run_authority_and_Node_capability_required_for_every_call_start_and_terminal_transition
      integrity_model: immutable_start_and_terminal_Event_anchors_with_recursive_retry_parent_verification_cycle_depth_guards_and_monotonic_status_heads
      payload_model: exact_ContentRef_or_ArtifactRef_only_with_secret_safe_bounded_metadata_and_no_large_bodies
    p1_05_validation:
      focused_functional_pytest: "14 passed; 4 subtests passed; 0 failed; 0 skipped; 5.79s"
      focused_T15_unittest: "1 passed; 0 failed; 0 skipped; 890.631s; executed all 305 predecessors, strict mypy, tamper attacks, exact wheel comparison, clean install, separate installed writer and reader"
      focused_total: "15 passed; 0 failed; 0 skipped"
      predecessor_regression: "305 executed inside T15; 0 failed; 0 errors; 0 skipped"
      p1_02_nested_qualification: "1 passed; 242 predecessors plus build/install gate; 104.990s"
      mypy_strict: "33 source/test files; 0 issues; mypy 2.3.1"
      compileall: PASS
      test_quality_scan: "P1-05 skip, placeholder, TODO, FIXME, and NotImplemented executable-test hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 5980af58476f6194bb4e26e31eebb11abd0877bf77b5c02c91aee190bb7f7fb3; 16 source modules byte-identical"
      installed_wheel_restart: "separate installed-package writer and reader shared durable SQLite; FAILED predecessor, SUCCEEDED retry, nested ToolCall, Event mappings, RunMemory call refs, and restart reconstruction verified"
      remote_source_gate: "fresh GitHub clone at exact commit 02f89c0d17d2f08a6c7b03f7faa285993f452891 and tree 7b8a976bf2a6d6b17a0b85359f6e9b6c570f7358; 14 functional tests and 4 subtests passed; strict mypy and compileall passed"
      remote_source_wheel: "built and installed from exact fresh GitHub clone; sha256 92364ea18006e661617b10e60d779fc3d9812914d52dae755f09772f94502449"
      remote_required_paths_and_bytes: "GitHub branch, commit, tree, seven blob IDs, sizes, and SHA256 bytes independently read back and matched"
      independent_review: "READY; no Critical or Important findings after start-anchor, terminal-anchor, secret-form, zero-input RunMemory, linked-parent, linked-retry, cycle, and depth hardening"
    p1_05_kpi:
      significant_calls_without_call_id: 0
      calls_without_Run_Node_binding: 0
      fabricated_usage_metrics: 0
      raw_credentials_in_call_ledger: 0
      provider_trace_dependency: 0
      terminal_call_regressions: 0
    p1_05_qualification:
      ModelCall: VERIFIED
      ToolCall: VERIFIED
      provider_neutral_call_IDs: VERIFIED
      exact_Project_Task_Run_Graph_Node_attempt_fence_capability_attribution: VERIFIED
      nested_and_direct_ToolCall_authority: VERIFIED
      retry_purpose_and_new_ID_preservation: VERIFIED
      terminal_status_monotonicity: VERIFIED
      nullable_usage_cost_and_per_metric_source: VERIFIED
      ContentRef_and_ArtifactRef_payload_boundary: VERIFIED
      start_and_terminal_Event_anchors: VERIFIED
      Event_and_RunMemory_call_discoverability: VERIFIED
      provider_trace_independence: VERIFIED
      Project_isolation_and_foreign_output_denial: VERIFIED
      idempotency_concurrency_restart_and_recursive_link_integrity: VERIFIED
      secret_safety_and_credential_admission_denial: VERIFIED
      arbitrary_provider_model_tool_deployment_runtime_IDs: VERIFIED
      raw_QuarantineRef_runtime_dependency: 0
    p1_05_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/call_ledger.py
      - src/biella/run_memory.py
      - tests/fixtures/p1_05_installed_reader.py
      - tests/fixtures/p1_05_installed_writer.py
      - tests/test_p0_10_p0_integration_qualification.py
      - tests/test_p1_05_call_ledger.py
    p1_06_status: DURABLY_COMPLETE
    p1_06_source_commit: 8928f5cd4d6f55cfb05eee10315f12f0142b3eb9
    p1_06_result_commit: ec0bbdf9f9cbb0d64bf82bf0f8fa53471327060a
    p1_06_result_tree: e6020758dfeaf1e528ccaffbe32c78e0afd245c2
    p1_06_remote_readback: VERIFIED
    p1_06_implementation:
      production_modules_added: 1
      public_exports_changed: 18
      Event_atomic_Artifact_reference_seam_changed: true
      test_methods_added: 16
      installed_restart_programs_added: 2
      migrations_added: 0
      schema_tables_added: 2
      authority_model: exact_current_fenced_Run_authority_required_for_checkpoint_publication_and_resume
      checkpoint_model: immutable_versioned_content_addressed_RunCheckpoint_bound_atomically_to_Artifact_Event_and_monotonic_latest_head
      reconciliation_model: current_durable_state_wins_with_exact_completed_output_reuse_and_dependency_aware_invalidation
      storage_lock_model: object_reads_and_writes_staged_outside_SQLite_writer_transactions_then_exactly_revalidated_before_publication
    p1_06_validation:
      focused_functional_pytest: "15 passed; 1 T15 deselected; 7 subtests passed; 0 failed; 0 skipped; 18.13s"
      focused_T15_unittest: "1 passed; 0 failed; 0 skipped; 905.102s; executed all 15 P1-05 tests including the nested 305-test predecessor chain, strict mypy, exact wheel comparison, clean install, separate installed writer and reader, stale-fence recovery, and completed continuation"
      focused_total: "16 passed; 7 subtests passed; 0 failed; 0 skipped"
      predecessor_regression: "15 P1-05 tests executed inside T15; nested 305-test predecessor chain passed; 0 failed; 0 errors; 0 skipped"
      parallel_build_diagnostic: "one earlier T15 encountered shared build-directory Errno 17 while an independent reviewer ran the same wheel gate concurrently; source assertions did not fail; generated build directory moved intact; isolated stable-snapshot T15 passed"
      mypy_strict: "37 source/test files; 0 issues; mypy 2.3.1"
      compileall: PASS
      test_quality_scan: "P1-06 skip, placeholder, TODO, FIXME, and NotImplemented executable-test hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 85e7e51acb4640b8125a0a4a34046903e75c033882d65034049710f77cb30f08; source modules byte-compared inside T15"
      installed_wheel_restart: "separate installed-package writer and reader shared durable SQLite and filesystem object storage; completed A reused; expired B became STALE; B received fence N+1; continuation finalized; Run reached SUCCEEDED"
      storage_isolation: "checkpoint upload, verified checkpoint read, and resume-evidence upload blocked in deterministic backend while unrelated BEGIN IMMEDIATE succeeded"
      remote_required_paths_and_bytes: "GitHub branch, commit, tree, six blob IDs, sizes, and blob identities independently read back and matched"
      independent_review: "READY; no Critical or Important findings; all four prior findings resolved; 15 focused tests plus 7 hostile-input subtests passed"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; independent review and deterministic static checks used"
    p1_06_kpi:
      checkpoint_digest_mismatches_accepted: 0
      completed_valid_nodes_rerun_due_only_to_restart: 0
      resume_requires_conversation: 0
      resume_requires_live_provider_session: 0
      cache_loss_causes_resume_failure: 0
      cancelled_runs_resurrected: 0
    p1_06_qualification:
      RunCheckpoint: VERIFIED
      createCheckpoint: VERIFIED
      resumeRun: VERIFIED
      checkpoint_reconciliation_service: VERIFIED
      latest_checkpoint_ref_seam: VERIFIED
      immutable_versioned_content_addressed_checkpoint: VERIFIED
      exact_Project_Run_Task_Graph_Node_attempt_fence_and_Event_attribution: VERIFIED
      checkpoint_Artifact_Event_and_latest_head_restart_reconstruction: VERIFIED
      current_durable_state_wins: VERIFIED
      compatible_completed_output_durable_reuse: VERIFIED
      newer_Graph_success_preservation: VERIFIED
      dependency_aware_source_invalidation_with_exact_cause: VERIFIED
      stale_attempt_recovery_and_new_fence: VERIFIED
      late_old_fence_denial: VERIFIED
      wrong_scope_wrong_Run_corrupt_content_and_terminal_Run_denial: VERIFIED
      content_Artifact_Event_provenance_chaining: VERIFIED
      idempotency_concurrency_and_unrelated_writer_isolation: VERIFIED
      optional_continuation_reference_credential_denial: VERIFIED
      provider_cache_browser_conversation_and_workspace_authority_dependency: 0
      raw_QuarantineRef_runtime_dependency: 0
    p1_06_schema_changes:
      - run_checkpoints
      - run_checkpoint_heads
      - exact_Project_Run_Task_Graph_Artifact_Event_record_bindings
      - immutable_checkpoint_and_monotonic_head_guards
    p1_06_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/checkpoint.py
      - src/biella/event.py
      - tests/fixtures/p1_06_installed_reader.py
      - tests/fixtures/p1_06_installed_writer.py
      - tests/test_p1_06_checkpoint_resume.py
    p1_07_status: DURABLY_COMPLETE
    p1_07_source_commit: b443098e5738cb4a0db8613ff80fe4ef1f3ed559
    p1_07_result_commit: eebcbfeeed692031657138626e7972f3829c8fd6
    p1_07_result_tree: 25523deabb6bcaccfccd29404b74a0b4ab97d40e
    p1_07_remote_readback: VERIFIED
    p1_07_implementation:
      production_modules_added: 1
      public_exports_added: 27
      test_methods_added: 16
      installed_restart_programs_added: 2
      migrations_added: 0
      schema_tables_added: 4
      identity_model: immutable_Project_scoped_provider_neutral_Resource_configuration
      observation_model: immutable_freshness_bounded_ResourceSnapshot_chain_with_measured_derived_or_UNKNOWN_provenance
      observer_model: real_local_cgroup_aware_observer_and_deterministic_TEST_REFERENCE_observer
      locality_model: explicit_observed_dimensions_with_exact_Project_scoped_Artifact_and_workspace_evidence
      fit_model: five_evidence_backed_classifications_without_Task_or_Capability_mutation
    p1_07_validation:
      focused_functional_pytest: "15 passed; 1 T15 deselected; 0 failed; 0 skipped; 0.50s final prequalification run"
      focused_T15_pytest: "1 passed; 15 deselected; 0 failed; 0 skipped; 928.46s; strict mypy, complete P1-06 nested qualification, exact wheel comparison, clean install, separate installed writer and reader, stale rejection, and fresh restart observation"
      focused_total: "16 passed; 0 failed; 0 skipped"
      predecessor_regression_inside_T15: "16 P1-06 tests and 7 subtests passed; complete nested predecessor, type, build, install, and restart chain; 0 failed; 0 skipped"
      earlier_T15_diagnostic: "first isolated run proved all 16 P1-06 tests and 7 subtests passed in 929.73s, then failed only on stale expected text '15 passed'; assertion corrected to current exact count and complete T15 reran successfully"
      broad_non_nested_regression: "337 passed; 15 nested T15 gates deselected; 127 subtests passed; 0 failed; 0 skipped; 71.66s"
      mypy_strict: "41 source/test files; 0 issues; mypy 2.3.1"
      compileall: PASS
      test_quality_scan: "P1-07 skip, placeholder, TODO, FIXME, and NotImplemented executable-test hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 d35344ba3a282fa7e02cc1801940b8d0043030a3f585bc3a0ed08f08a736860d; resource.py source bytes exact"
      installed_wheel_restart: "separate installed-package writer and reader shared durable SQLite; immutable Resource identity/config survived; stale snapshot was rejected; new observation chained at sequence 2 and became current"
      remote_required_paths_and_bytes: "GitHub branch, commit, tree, five blob IDs, sizes, SHA256 bytes, and exact file contents independently read back and matched"
      independent_review: "READY; no Critical or Important findings after device-fit, host-attribution, Project locality, full-chain, scoped-evidence, and Artifact-integrity hardening; final targeted corrupt-admission/deletion checks passed"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; independent review and deterministic static checks used"
    p1_07_kpi:
      configured_as_observed_errors: 0
      stale_snapshots_used_as_fresh: 0
      capabilities_deleted_due_to_resource_shortage: 0
      unknown_metrics_fabricated: 0
      hardware_vendor_kernel_lockin: 0
    p1_07_qualification:
      Resource: VERIFIED
      ResourceSnapshot: VERIFIED
      ResourceObserver: VERIFIED
      evaluateResourceFit: VERIFIED
      configured_expected_vs_observed_physical_effective_used_available: VERIFIED
      actual_local_CPU_RAM_storage_network_runtime_and_cgroup_observation: VERIFIED
      zero_one_many_and_arbitrary_vendor_GPU_shapes: VERIFIED
      per_device_identity_health_features_VRAM_and_fit: VERIFIED
      explicit_UNKNOWN_and_observer_failure_cause: VERIFIED
      freshness_staleness_and_fresh_restart_observation: VERIFIED
      immutable_gap_free_snapshot_provenance_chain: VERIFIED
      exact_parent_and_Project_scoped_evidence: VERIFIED
      exact_Artifact_record_and_workspace_locality_scope: VERIFIED
      queue_allocation_pressure_and_known_cost_source_semantics: VERIFIED
      all_five_fit_classifications: VERIFIED
      Capability_unchanged_during_shortage_or_GPU_removal: VERIFIED
      observer_work_outside_SQLite_writer_transaction: VERIFIED_BY_IMPLEMENTATION_STRUCTURE
      raw_QuarantineRef_runtime_dependency: 0
    p1_07_schema_changes:
      - resources
      - resource_snapshots
      - resource_snapshot_heads
      - resource_snapshot_artifact_bindings
      - immutable_Resource_snapshot_binding_and_monotonic_head_guards
    p1_07_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/resource.py
      - tests/fixtures/p1_07_installed_reader.py
      - tests/fixtures/p1_07_installed_writer.py
      - tests/test_p1_07_resource_inventory.py
    p1_08_status: DURABLY_COMPLETE
    p1_08_source_commit: 875fb4882f1492e96e5ecf35f6d7513ae3eb274d
    p1_08_result_commit: ac5aca11af0866734862c709a537ad98b1ffb9d7
    p1_08_result_tree: 282c46ffc1272adaa7ad4ca5c97104cb573f3f1a
    p1_08_remote_readback: VERIFIED
    p1_08_implementation:
      production_modules_added: 1
      public_exports_added: 20
      test_methods_added: 15
      installed_restart_programs_added: 2
      migrations_added: 0
      schema_tables_added: 10
      scheduler_model: durable_Project_scoped_resource_aware_concurrent_Graph_scheduler
      allocation_model: immutable_identity_append_only_state_fenced_leased_exact_Run_Node_attempt_and_ResourceSnapshot_provenance
      reservation_model: one_BEGIN_IMMEDIATE_atomic_multi_resource_transaction_with_exact_capacity_device_and_side_effect_conflicts
      readiness_model: semantic_Graph_READY_is_explicitly_distinct_from_current_resource_schedulability
      dispatch_model: multiple_independent_Node_leases_and_real_productive_thread_overlap_without_global_heavyweight_lock
      queue_model: durable_gap_free_wait_dispatch_failure_history_with_verified_heads_and_exact_causes
      metric_model: immutable_hash_chained_gap_free_scheduler_cycle_evidence_with_verified_heads
      recovery_model: exact_attempt_fence_binding_idempotent_release_terminal_reconciliation_and_expiry_recovery
    p1_08_validation:
      focused_functional_pytest: "14 passed; 1 T15 deselected; 0 failed; 0 skipped; 13.92s final exact-tree run"
      focused_T15_pytest: "1 passed; 14 deselected; 0 failed; 0 skipped; 938.92s; strict mypy, complete P1-07 nested qualification, exact wheel comparison, clean install, separate installed writer and reader, and durable restart readback"
      focused_total: "15 passed; 0 failed; 0 skipped"
      predecessor_regression_inside_T15: "16 P1-07 tests passed with complete nested predecessor, type, build, install, and restart chain; 0 failed; 0 skipped"
      broad_non_nested_regression: "351 passed; 16 nested T15 gates deselected; 127 subtests passed; 0 failed; 0 skipped; 85.85s"
      mypy_strict: "45 source/test files; 0 issues; mypy 2.3.1"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P1-08 skip, placeholder, TODO, FIXME, and NotImplemented executable-test hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 942d28ecfd4f37c57ef3cdddc7af628366a22a8a2dd10de365f1d5d349a75d55; scheduler.py source and packaged bytes sha256 3aef08efa79f6b3c583d800fb93e0af10478dd39c53216bc3323a35cd6fd4f33 exactly matched"
      installed_wheel_restart: "separate installed-package writer and reader shared durable SQLite; exact allocation identity, ResourceSnapshot provenance, queue state, release, and restart reconstruction survived"
      remote_required_paths_and_bytes: "GitHub branch, commit, tree, five blob IDs, sizes, SHA256 bytes, and exact decoded file contents independently read back and matched"
      independent_review: "READY after dispatch claim, terminal reconciliation, stale-attempt, durable read snapshot, allocation/queue head, and metric completeness hardening"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; independent review and deterministic static checks used"
    p1_08_kpi:
      independent_nodes_serialized_without_reason: 0
      exclusive_resource_double_allocations: 0
      invalid_resource_overcommit: 0
      resource_leaks_after_terminal: 0
      permanent_starvation_under_ordinary_load: 0
      global_heavyweight_lock: 0
      max_observed_productive_concurrency: 2
    p1_08_reality_classification:
      CPU_thread_concurrency_and_SQLite_transactions: REAL
      local_CPU_RAM_storage_network_cgroup_observation: REAL
      GPU_shapes_and_contention: TEST_REFERENCE_on_CPU_only_host
      provider_or_model_routing: NOT_RUN_out_of_scope_until_P1_09
      installed_wheel_restart: REAL
    p1_08_qualification:
      SchedulerService: VERIFIED
      ResourceAllocation: VERIFIED
      reservation_dispatch_release_heartbeat_and_recovery_APIs: VERIFIED
      SchedulerMetrics: VERIFIED
      semantic_READY_vs_current_schedulability: VERIFIED
      exact_FIT_and_explicit_FIT_REDUCED_classification: VERIFIED
      atomic_multi_resource_acquisition_and_full_rollback: VERIFIED
      requested_vs_effective_capacity_by_exact_Resource: VERIFIED
      exclusive_device_and_side_effect_target_isolation: VERIFIED
      actual_productive_concurrency_greater_than_one: VERIFIED
      CPU_GPU_network_and_distinct_GPU_overlap: VERIFIED_BY_TEST_REFERENCE_RESOURCE_OBSERVATIONS
      priority_deadline_aging_fairness_and_current_locality_order: VERIFIED
      durable_queue_pressure_and_exact_wait_causes: VERIFIED
      append_only_allocation_queue_and_metric_integrity: VERIFIED
      restart_reconstruction_and_completed_output_authority: VERIFIED
      dispatch_idempotency_terminal_replay_and_exact_attempt_fence_binding: VERIFIED
      expiry_executor_loss_cancellation_terminal_and_stale_attempt_rejection: VERIFIED
      hostile_instruction_like_target_inertness: VERIFIED
      Project_scope_and_cross_Project_denial: VERIFIED
      raw_QuarantineRef_runtime_dependency: 0
    p1_08_schema_changes:
      - resource_allocations
      - resource_allocation_states
      - resource_allocation_heads
      - resource_allocation_reservations
      - resource_allocation_side_effects
      - scheduler_idempotency
      - scheduler_queue_events
      - scheduler_queue_heads
      - scheduler_cycle_metrics
      - scheduler_cycle_metric_heads
      - immutable_gap_free_hash_chained_and_monotonic_integrity_guards
    p1_08_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/scheduler.py
      - tests/fixtures/p1_08_installed_reader.py
      - tests/fixtures/p1_08_installed_writer.py
      - tests/test_p1_08_scheduler.py
    p1_09_status: DURABLY_COMPLETE
    p1_09_source_commit: 5d52c5f5575d2a8bbfb6c33ea0740b7791c0df5e
    p1_09_result_commit: 3508942cb7527dd0db43d19ae6ce31d937434192
    p1_09_result_tree: 9126aa1f965b027c4f922e95f52ce35d2b3c0988
    p1_09_remote_readback: VERIFIED
    p1_09_implementation:
      production_modules_added: 1
      public_exports_added: 24
      test_methods_added: 15
      installed_restart_programs_added: 2
      migrations_added: 0
      schema_tables_added: 8
      routing_layers: semantic_Capability_then_Project_scoped_CapabilityImplementation_then_model_tool_runtime_then_current_compute_Resource
      implementation_registry: immutable_idempotent_Project_scoped_registry_with_gap_free_hash_chain_verified_head_and_dedicated_immutable_anchor
      constraint_model: capability_features_Project_provider_runtime_data_egress_side_effect_context_tool_health_and_Resource_fit_before_ranking
      ranking_model: deterministic_explicit_Project_preference_priority_fit_pressure_cost_latency_locality_and_exact_identity_tie_breakers
      decision_model: immutable_idempotency_anchored_RoutingDecision_with_typed_canonical_request_policy_candidate_rejection_selection_and_snapshot_evidence
      persistence_model: one_BEGIN_IMMEDIATE_authority_Capability_Graph_registry_and_full_current_Resource_head_revalidation_before_receipt_insert
      scheduler_boundary: RoutingDecision_is_evidence_not_reservation_and_P1_08_Scheduler_revalidates_current_fit
    p1_09_validation:
      focused_functional_pytest: "14 passed; 1 T15 deselected; 0 failed; 0 skipped; 9.43s final exact-tree run"
      focused_T15_pytest: "1 passed; 14 deselected; 0 failed; 0 skipped; 959.40s; strict mypy, complete P1-08/P1-07 nested qualification, exact wheel comparison, clean install, separate installed writer and reader, and durable restart readback"
      focused_total: "15 passed; 0 failed; 0 skipped"
      predecessor_regression_inside_T15: "15 P1-08 tests passed with complete nested predecessor, type, build, install, and restart chain; 0 failed; 0 skipped"
      broad_non_nested_regression: "365 passed; 17 nested T15 gates deselected; 127 subtests passed; 0 failed; 0 skipped; 94.82s"
      mypy_strict: "49 source/test files; 0 issues; mypy 2.3.1"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P1-09 skip, placeholder, TODO, FIXME, and NotImplemented executable-test hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      hardcoded_fallback_scan: "local/H100/OpenAI, OpenAI, Anthropic, and provider-fallback routing sequences: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 0430c734749092df00ab56a7061cf14f5d9dc30cc62642eff08688adc183b80e; routing.py source and packaged bytes sha256 7603cbaf98531c8f5c8c78918783801e0bf37e46621a62ce8c216ef200e843fc exactly matched"
      installed_wheel_restart: "separate installed-package writer and reader shared durable SQLite; exact Project, CapabilityImplementation, Task, Run attempt, Graph/Node, ResourceSnapshot, RoutingDecision, request/policy, and selection evidence survived"
      remote_required_paths_and_bytes: "GitHub branch, commit, tree, five blob IDs, sizes, SHA256 bytes, and exact decoded file contents independently read back and matched"
      independent_review: "READY after four adversarial passes closed authority TOCTOU, active Graph, Capability, Resource head, registry erasure, typed evidence, idempotency anchor, and orphan deletion gaps; no Critical or Important findings"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; independent adversarial review and deterministic static checks used"
    p1_09_kpi:
      Task_contract_changes_when_provider_changes: 0
      Capability_definition_changes_when_hardware_changes: 0
      egress_violating_routes: 0
      hard_constraint_bypasses: 0
      unexplained_routing_decisions: 0
      hardcoded_historical_fallback_sequences: 0
    p1_09_reality_classification:
      routing_registry_decisions_and_SQLite_transactions: REAL
      current_CPU_ResourceSnapshot_ranking_and_scheduler_revalidation: REAL
      provider_model_tool_runtime_identities: TEST_REFERENCE_without_external_provider_execution
      GPU_shortage_and_recovery: TEST_REFERENCE_on_CPU_only_host
      installed_wheel_restart: REAL
    p1_09_qualification:
      CapabilityImplementation: VERIFIED
      CapabilityImplementationRegistry: VERIFIED
      ImplementationResolver: VERIFIED
      ComputeResolver: VERIFIED
      RoutingDecision_and_structured_rejection_reason_codes: VERIFIED
      provider_model_and_Resource_replacement_without_Task_mutation: VERIFIED
      egress_denial_even_with_credential_metadata: VERIFIED
      GPU_shortage_no_route_then_recovery_without_Capability_mutation: VERIFIED_BY_TEST_REFERENCE_RESOURCE_OBSERVATIONS
      new_implementation_without_history_eligible: VERIFIED
      model_selection_separate_from_compute_placement: VERIFIED
      scheduler_current_fit_revalidation: VERIFIED
      deterministic_tie_break_and_explicit_Project_preference: VERIFIED
      canonical_request_policy_and_exact_provenance_chaining: VERIFIED
      persistence_authority_Graph_Capability_registry_and_Resource_TOCTOU: VERIFIED
      trigger_bypass_tamper_deletion_and_total_registry_erasure_detection: VERIFIED
      hostile_instruction_like_metadata_inertness: VERIFIED
      Project_scope_and_cross_Project_denial: VERIFIED
      raw_QuarantineRef_runtime_dependency: 0
    p1_09_schema_changes:
      - capability_implementations
      - capability_implementation_idempotency
      - capability_implementation_registry_entries
      - capability_implementation_registry_heads
      - capability_implementation_registry_anchors
      - routing_decisions
      - routing_decision_candidates
      - routing_idempotency
      - immutable_gap_free_hash_chained_anchored_and_monotonic_integrity_guards
    p1_09_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/routing.py
      - tests/fixtures/p1_09_installed_reader.py
      - tests/fixtures/p1_09_installed_writer.py
      - tests/test_p1_09_routing.py
    historical_spot_local_p0_01_counts_as_current: false
    reconstruct_historical_p0_01_from_prose: false

host:
  execution_root: /root/biella
  codex_home: /root/.codex
  canonical_checkout_path: /root/biella/repos/biella-engine

  recorded_identity:
    provider: AWS
    instance_id: i-077ab197788b547b0
    region: eu-west-3
    instance_type: c5a.4xlarge
    public_ip: 13.38.71.149
    private_ip: 172.31.13.170

  recorded_resources:
    os: Ubuntu_26.04.1_LTS
    kernel: 7.0.0-1011-aws
    logical_cpu: 16
    ram_gib: 30
    root_ebs_gib: 350
    swap_gib: 64
    swappiness: 10
    local_gpu_present: false
    gpu_capability_semantic_effect: none

  workstation_initialized: true
  reinstall_required: false

  volatile:
    reachable: true
    ssh_state: UNKNOWN
    github_push_auth: VERIFIED

drive:
  canonical_root_id: 1Z6_qwN9hfHIheXZ_9pYCG8dRDMuRN-l7

  required_live_paths:
    start_here: 00_START_HERE
    architecture: 10_ARCHITECTURE
    current_state: 20_CURRENT_STATE
    execution: 30_EXECUTION
    prompts: 40_PROMPTS
    migration: 50_MIGRATION
    website: biellawebsite

  active_prompt_identity:
    id: P2-01
    title: Universal Filesystem Capability Adapter
    drive_id: 1cNVwywxtOOlbmNkiZRBZn6jhP_WlnTleDVTieWRXw5U
    canonical_prompt_text_sha256: a9a7f0c5246eec864eae3f44f6171ef389129b602141f7fb74d33f8655c34534
    local_and_live_drive_prompt_text_equal: true

  inactive_reference_candidates:
    - title: Legacy Productive Reuse
      drive_id: 1P4uv74n0UI0JROi5J83ehrg9wDyWPg7FCt5dMMi9HTc
      state: INACTIVE_UNLESS_EXPLICITLY_REQUIRED_BY_NUMBERED_PROMPT
      active_authority: false
      default_retrieval_allowed: false

  prompt_inventory:
    P0: 10
    P1: 9
    P2: 12
    P3: 14
    P4: 6
    total: 51

migration:
  stage: P0_FOUNDATION_DURABLY_COMPLETE
  firewall_implemented: true
  raw_history_active: false
  real_corpus_registered: false
  broad_extraction_allowed: false
  normal_retrieval_may_access_raw_history: false
  engine_memory_may_access_raw_history: false
  project_memory_may_access_raw_history: false

  after_p0_01:
    permitted:
      - register_verified_historical_multipart_objects_as_immutable_quarantine_inputs
      - record_part_identity_size_digest_provenance
    broad_extraction_allowed: false

  after_p0_10:
    permitted:
      - bounded_resumable_semantic_extraction
      - classification
      - contamination_removal
      - normalized_candidate_generation

  historical_material_rule:
    scope: HISTORICAL_EVIDENCE_OR_QUARANTINE
    direct_activation: false
    direct_copy_to_active_biella: false
    mechanical_rename_to_biella: false

website:
  program: BIELLA_UNIVERSE_OPTION_C
  public_target: biellagames.dev
  execution_state: P0_10_GATE_CLEARED_NOT_STARTED
  first_separate_task_after_p0_01: BU-01
  run_in_same_p0_01_session: false
  universal_engine_kernel_scope: false

volatile_reobserve_before_next_write:
  - current_host_reachability
  - current_ssh_state
  - canonical_checkout_existence
  - local_branch
  - local_head_tree_upstream
  - local_worktree_status
  - newer_valid_local_implementation
  - current_remote_main_commit_tree
  - github_push_auth_when_publication_required

next_boundary:
  id: P2-01
  global_number: 20
  title: Universal Filesystem Capability Adapter
  prompt_drive_id: 1cNVwywxtOOlbmNkiZRBZn6jhP_WlnTleDVTieWRXw5U
  predecessor_result_commit: 3508942cb7527dd0db43d19ae6ce31d937434192
  predecessor_result_tree: 9126aa1f965b027c4f922e95f52ce35d2b3c0988

next_transition:
  - verify_P1_09_handoff_from_exact_remote_commit_tree_and_required_paths
  - load_exact_P2_01_prompt_and_directly_required_Project_Task_Run_Graph_Node_attempt_Artifact_ContentRef_ToolCall_Event_and_routing_interfaces_only
  - implement_Project_scoped_authorized_FilesystemRoot_and_replaceable_FilesystemAdapter
  - register_filesystem_read_write_list_stat_mkdir_copy_move_remove_CapabilityImplementations
  - enforce_canonical_root_relative_paths_and_reject_traversal_absolute_symlink_special_target_and_cross_Project_escape
  - stream_large_reads_and_writes_with_cancellation_atomic_finalization_exact_digest_ContentRef_Artifact_and_ToolCall_Event_provenance
  - prove_read_only_side_effect_partial_output_restart_and_workspace_rematerialization_contracts
  - run_required_focused_tests_regressions_typecheck_build
  - commit_and_push
  - remotely_read_back_exact_commit_and_tree
  - update_Drive_continuity_and_current_state
  - close_P2_01_before_opening_P2_02

prohibited_next_transition:
  - reinstall_host
  - rerun_vps_configurator
  - create_or_migrate_to_/srv/biella
  - duplicate_checkout
  - grant_agents_or_models_arbitrary_host_path_authority
  - treat_path_as_Artifact_or_Content_identity
  - rely_on_string_prefix_checks_as_the_only_filesystem_sandbox
  - report_partial_or_cancelled_output_as_accepted_final_Artifact
  - broad_historical_backup_extraction
  - raw_MiniTZ_activation
  - weaken_or_mock_Run_Task_Graph_Node_Event_Artifact_fence_integrity_restart_or_Project_authorization
  - treat_fixture_or_comment_strings_as_active_kernel_coupling_without_semantic_inspection
  - start_P2_02_before_P2_01_durable_close
  - start_BU_01_in_same_P0_01_session
  - install_gpu_stack_on_cpu_host_for_completeness
  - add_unrequested_security_architecture
  - add_approval_or_reviewer_systems
  - treat_research_or_prompt_pack_documents_as_implemented_engine_code
```
