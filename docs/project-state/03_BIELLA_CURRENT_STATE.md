# 03 — BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v2
state_timestamp_local: "2026-08-30 04:50 Europe/Amsterdam"
state_timestamp_iso: "2026-08-30T04:50:34+02:00"
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
    commit: f665445e1771b98f34e1d82746c5d4a9686e3138
    tree: 6a8c47f70fcd5df900381e05a93169a9aed25205
    observed_date: 2026-08-30
    evidence: CURRENT_GITHUB_SOURCE
    observation_context: p3_03_final_result_post_push_exact_readback
    src_present: true
    root_package_json_present: false
    root_pyproject_present: true
    volatile_reobserve_before_next_write: true

  local:
    checkout_path: /root/biella/repos/biella-engine
    checkout_exists: true
    branch: main
    head: f665445e1771b98f34e1d82746c5d4a9686e3138
    tree: 6a8c47f70fcd5df900381e05a93169a9aed25205
    upstream: origin/main
    worktree_status: CLEAN_AT_IMPLEMENTATION_READBACK
    newer_valid_work_present: false

  implementation:
    durable_prompts_complete: 34
    durable_prompts_total: 51
    progress: "34 / 51"
    phase: P3
    active_prompt: P3-04
    active_prompt_title: Large-Scale / AAA Multi-Domain Production Orchestration Pack
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
    p2_01_status: DURABLY_COMPLETE
    p2_01_source_commit: 383a24a25b44c287ee6e6757fda711c7d088975b
    p2_01_result_commit: bc728ce53160c8bbc0cad8ec0bbf9fb09db6b737
    p2_01_result_tree: d8b6f53385b35e77e4a8bb01d2e734568107137f
    p2_01_remote_readback: VERIFIED
    p2_01_implementation:
      production_modules_added: 1
      public_exports_added: 14
      focused_pytest_cases: 27
      installed_restart_programs_added: 2
      migrations_added: 0
      schema_tables_added: 6
      capability_surface: filesystem.read_write_list_stat_mkdir_copy_move_remove
      root_model: immutable_Project_bound_FilesystemRoot_with_explicit_PROJECT_or_GLOBAL_scope_and_READ_ONLY_READ_WRITE_or_TEMPORARY_mode
      path_model: canonical_relative_POSIX_paths_plus_descriptor_relative_O_NOFOLLOW_traversal_and_pinned_ancestry_revalidation
      streaming_model: bounded_1MiB_chunks_between_secure_descriptors_and_ObjectStorageBackend_without_large_read_materialization
      mutation_model: independently_authorized_roots_atomic_temp_fsync_digest_verify_replace_parent_fsync_and_explicit_remove_authority
      evidence_model: canonical_request_ContentRef_plus_exact_ToolCall_start_and_terminal_Events_plus_Run_produced_Artifact
      idempotency_model: immutable_attempt_scoped_claims_terminal_replay_and_claim_erasure_detection
    p2_01_validation:
      focused_pytest: "27 passed; 0 failed; 0 skipped; 25.62s final exact-tree run"
      predecessor_exact_T15: "1 passed; 14 deselected; 0 failed; 0 skipped; 961.65s; strict mypy, complete P1-08/P1-07 predecessor chain, exact wheel comparison, clean install, and separate installed writer/reader restart"
      broad_non_nested_regression: "389 passed; 20 nested qualification gates deselected; 127 subtests passed; 0 failed; 0 skipped; 115.44s"
      mypy_strict: "53 source/test files; 0 issues; mypy 2.3.1"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P2-01 skip, placeholder, TODO, FIXME, and NotImplemented executable-test hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      hardcoded_fallback_scan: "active provider fallback sequence hits: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 298b27669ce1a305cdcb88e9a8776519257e325128358b5e1900cc693cec60e8; filesystem.py source and packaged bytes sha256 ae0058e2b6646b2e1b4acf9dc9f7790bde0c1c35fa5959456315b0fd44bfe5b2 exactly matched"
      installed_wheel_restart: "separate installed-package writer and reader shared durable SQLite, physical FilesystemRoot, and filesystem ObjectStorageBackend; exact root, ContentRef, Artifact, ToolCall, and operation evidence survived"
      remote_required_paths_and_bytes: "GitHub branch, commit, tree, five blob IDs, sizes, SHA256 bytes, and exact decoded file contents independently read back and matched"
      adversarial_review: "PASS after root registry and operation claim erasure, parent-move race, symlink/special target, cross-Project, read-only, cancellation, digest corruption, and idempotency hardening"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; deterministic adversarial tests and static checks used"
    p2_01_kpi:
      authorized_root_escapes: 0
      unauthorized_writes: 0
      digest_mismatches_accepted: 0
      partial_writes_claimed_success: 0
      large_files_forced_full_memory: 0
      unattributed_filesystem_operations: 0
    p2_01_reality_classification:
      Linux_POSIX_dirfd_nofollow_ancestry_and_atomic_IO: REAL
      SQLite_root_registry_idempotency_and_operation_claims: REAL
      FilesystemObjectStorage_ContentRef_and_Artifact_publication: REAL
      installed_wheel_separate_process_restart: REAL
      Project_and_GLOBAL_scope_labels: REAL_with_both_remaining_exactly_Project_owner_bound
      Windows_junction_or_reparse_point_enforcement: UNSUPPORTED_BY_CURRENT_LINUX_IMPLEMENTATION_and_not_claimed
    p2_01_qualification:
      FilesystemAdapter: VERIFIED
      FilesystemRoot_and_FilesystemRootRef: VERIFIED
      filesystem_CapabilityImplementations_all_eight: VERIFIED
      PROJECT_and_GLOBAL_scope_and_all_three_modes: VERIFIED
      traversal_absolute_ambiguous_NUL_and_drive_path_rejection: VERIFIED
      symlink_special_target_and_parent_directory_move_race_containment: VERIFIED
      independent_source_destination_authorization: VERIFIED
      read_only_and_explicit_remove_side_effect_denial: VERIFIED
      atomic_write_fsync_digest_verification_and_cancellation_cleanup: VERIFIED
      large_streaming_read_and_write_without_ObjectStorage_read_materialization: VERIFIED
      exact_ContentRef_Artifact_ToolCall_and_Event_attribution: VERIFIED
      restart_idempotency_and_object_store_rematerialization_identity: VERIFIED
      registry_claim_trigger_bypass_tamper_and_total_erasure_detection: VERIFIED
      hostile_instruction_bytes_inertness: VERIFIED
      Project_scope_and_cross_Project_denial: VERIFIED
      raw_QuarantineRef_runtime_dependency: 0
    p2_01_schema_changes:
      - filesystem_roots
      - filesystem_root_idempotency
      - filesystem_root_registry_entries
      - filesystem_root_registry_heads
      - filesystem_root_registry_anchors
      - filesystem_operation_claims
      - immutable_gap_free_hash_chained_anchored_monotonic_and_claim_integrity_guards
    p2_01_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/filesystem.py
      - tests/fixtures/p2_01_installed_reader.py
      - tests/fixtures/p2_01_installed_writer.py
      - tests/test_p2_01_filesystem.py
    p2_01_remote_path_evidence:
      src_biella_init: "blob 3b33530ba030651d89d04611eb5d47fe7ccab47d; size 14415; sha256 cb915df3bd64f05943e3d6e0cc69155f1c7eaf80cb2e10ad0a8c73e11d2c1166"
      src_biella_filesystem: "blob bca0a54b56d5a26d7bdaec72f367646100596255; size 85407; sha256 ae0058e2b6646b2e1b4acf9dc9f7790bde0c1c35fa5959456315b0fd44bfe5b2"
      test_p2_01: "blob 52e72b4ffd6266e94bf3a246ee0fa75fd465fd51; size 36952; sha256 ab522bc99db43b23fae849932ad1fd1c9875218f5c6594b86bfc521f4089f426"
      installed_writer: "blob a44556d5f59b6d9b4e4d6b2c2f09424a662597e1; size 4049; sha256 37f206ef5b53f91fb92e56babba4f0f38d0dd6be559bb896c06124c1a6a93a8f"
      installed_reader: "blob c0d3f438a4f4f2ae12b1a47dae85f8293adbbc3d; size 1352; sha256 527891f0e1d264a9a71ab23abecc97eeaf8de6658ecbbb3839421617e430a3cf"
    p2_02_status: DURABLY_COMPLETE
    p2_02_source_commit: 50b54edce2b6d98849b3789e3a2769c32ebdafdc
    p2_02_result_commit: 0e61e36865339347ff52213e04ef22e21d44de6f
    p2_02_result_tree: dafa639eee961daa89a04d3c69d0a88d2c27f6b3
    p2_02_remote_readback: VERIFIED
    p2_02_implementation:
      production_modules_added: 1
      public_exports_added: 15
      focused_pytest_cases: 15
      installed_restart_programs_added: 2
      migrations_added: 0
      schema_tables_added: 3
      capability_surface: process.execute_and_explicit_process.shell
      request_model: exact_Project_FilesystemRoot_CWD_executable_argv_environment_secret_refs_stdin_ContentRef_timeout_output_network_resource_and_optional_ResourceAllocation
      ownership_model: Linux_boot_id_process_start_ticks_executable_digest_inode_isolated_session_process_group_and_live_pidfd_pin
      output_model: disk_backed_streaming_bounded_stdout_stderr_ContentRefs_with_preview_tail_secret_redaction_and_explicit_truncation
      termination_model: owned_process_group_TERM_then_KILL_parent_exits_first_detection_and_no_stale_PID_signal
      evidence_model: canonical_request_ContentRef_exact_ToolCall_start_terminal_Events_Run_produced_Artifact_result_manifest_and_process_identity
      idempotency_model: immutable_attempt_scoped_claims_terminal_replay_result_manifest_consistency_and_erasure_detection
    p2_02_validation:
      focused_pytest: "15 passed; 0 failed; 0 skipped; 35.99s final exact-tree run including build and separate installed restart"
      predecessor_exact_P2_01_T18: "1 passed; 26 deselected; 0 failed; 0 skipped; 3.11s"
      broad_non_nested_regression: "404 passed; 20 nested qualification gates deselected; 127 subtests passed; 0 failed; 0 skipped; 150.58s"
      mypy_strict: "57 source/test files; 0 issues; mypy 2.3.1"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P2-02 skip, placeholder, TODO, FIXME, and NotImplemented executable-test hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 b8973c295ecf2b985a1d26c464ceee2797fac81526b37fe59e665cad75ef9b01; process.py source and packaged bytes sha256 7b0d937f9dce3bd558e9dfc305e381ff2dceaa821e469ed1bf1755d2f82ea776 exactly matched"
      installed_wheel_restart: "separate installed-package writer and reader shared durable SQLite, authorized FilesystemRoot, object storage, stdin/output ContentRefs, Artifact, ToolCall, and managed process evidence"
      remote_required_paths_and_bytes: "GitHub branch, commit, tree, five blob IDs, sizes, SHA256 bytes, and exact decoded contents independently read back and matched"
      adversarial_review: "PASS after parent-exits-first child cleanup, forced escalation, PID reuse, quick overflow race, split secret output, manifest forgery, claim erasure, CWD escape, cross-Project, read-only, and stale allocation hardening"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; deterministic adversarial tests and static checks used"
    p2_02_kpi:
      unbounded_process_output: 0
      timeouts_reported_success: 0
      cancelled_processes_reported_success: 0
      wrong_process_terminated: 0
      secret_environment_values_persisted: 0
      unsupported_isolation_claimed_enforced: 0
    p2_02_reality_classification:
      direct_executable_plus_argv_and_explicit_shell_capabilities: REAL
      Linux_pidfd_session_process_group_timeout_and_cancellation: REAL
      SQLite_claim_identity_result_and_manifest_integrity: REAL
      FilesystemRoot_ContentRef_Artifact_ToolCall_and_Event_attribution: REAL
      installed_wheel_separate_process_restart: REAL
      RLIMIT_CPU_AS_FSIZE: REAL
      RLIMIT_NPROC_as_root: CONFIGURED_EFFECT_NOT_GUARANTEED
      local_network_NONE_or_RESTRICTED: UNSUPPORTED_POLICY_DENIED_and_not_claimed
      cgroup_or_container_containment_of_descendants_that_create_a_new_session: UNSUPPORTED_BY_LOCAL_ADAPTER_and_not_claimed
    p2_02_qualification:
      ProcessExecutionRequest: VERIFIED
      ManagedProcessAdapter_and_ManagedProcessIdentity: VERIFIED
      ProcessResult_ProcessStatus_and_ProcessFailure_taxonomy: VERIFIED
      direct_argv_metacharacter_inertness_and_explicit_shell: VERIFIED
      success_nonzero_missing_executable_and_exact_exit_signal: VERIFIED
      stdout_stderr_large_streaming_quick_overflow_and_explicit_truncation: VERIFIED
      stdin_ContentRef_and_generated_file_Artifact_capture: VERIFIED
      timeout_cancellation_forced_escalation_parent_exits_first_and_child_group_cleanup: VERIFIED
      boot_starttime_pidfd_process_group_ownership_and_stale_PID_denial: VERIFIED
      environment_allowlist_secret_refs_split_stream_redaction_and_zero_secret_persistence: VERIFIED
      authorized_CWD_read_only_and_Project_scope: VERIFIED
      network_policy_and_resource_limit_truthful_classification: VERIFIED
      optional_ResourceAllocation_exact_scope_and_unavailable_stale_denial: VERIFIED
      concurrent_processes_and_restart_idempotency: VERIFIED
      result_manifest_trigger_bypass_tamper_and_claim_erasure_detection: VERIFIED
      raw_QuarantineRef_runtime_dependency: 0
    p2_02_schema_changes:
      - managed_process_claims
      - managed_process_executions
      - managed_process_results
      - immutable_claim_identity_and_result_integrity_guards
    p2_02_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/process.py
      - tests/fixtures/p2_02_installed_reader.py
      - tests/fixtures/p2_02_installed_writer.py
      - tests/test_p2_02_process.py
    p2_02_remote_path_evidence:
      src_biella_init: "blob a7650add6235207cd7de9f0ed45a3d3b496f0995; size 15192; sha256 d6e046d4c76812af43c8a13e0b6d6f4e7c73766e95dcaf4f571c16857cab86cf"
      src_biella_process: "blob c1eb44a073ec7af3a1cea081296d5a0de676fa23; size 87579; sha256 7b0d937f9dce3bd558e9dfc305e381ff2dceaa821e469ed1bf1755d2f82ea776"
      installed_reader: "blob 7c2a0ee8a0fa51c7e31435964d1dd5ce430efe18; size 1640; sha256 69fd65b32dc35288932fbffbf3e6c0f3d2dd87822089347d6dc06e39f65afab2"
      installed_writer: "blob fefdfd3c86f8a6f65aa78fd9b331f3ddde916e62; size 4683; sha256 e22485279a4262c3bbe9bd5e6e48f5de8a6b91e45eb2a55779023af9ca241237"
      test_p2_02: "blob 9c869c7ad3dc941616540731402428f48dd63192; size 34042; sha256 6a047358b7852464821817fcec6b12ac28e798279a949518eef200877ca0c29e"
    p2_03_status: DURABLY_COMPLETE
    p2_03_source_commit: f066450ebd844435e727f2d6ae40f93559a8d9df
    p2_03_result_commit: d71c08a6da61713a1859bd9d1b8bb94652c41550
    p2_03_result_tree: abc9e6001d2b079b53c49850062d9d38bbbc3a55
    p2_03_remote_readback: VERIFIED
    p2_03_implementation:
      production_modules_added: 1
      public_exports_added: 15
      focused_pytest_cases: 14
      installed_restart_programs_added: 2
      migrations_added: 0
      schema_tables_added: 7
      capability_surface: git.inspect_status_diff_read_workspace_apply_commit_fetch_push
      repository_model: exact_Project_FilesystemRoot_commit_tree_object_format_submodule_config_digest_and_registration_time
      workspace_model: isolated_clone_exact_base_commit_tree_generation_and_current_commit_tree
      safety_model: managed_direct_argv_safe_config_no_hooks_no_global_or_system_config_no_prompts_no_ext_diff_no_textconv_no_implicit_submodule_or_LFS_materialization
      evidence_model: staged_unstaged_untracked_ContentRefs_high_level_Artifacts_exact_process_ToolCalls_and_immutable_receipt_manifests
      commit_model: explicit_parent_write_tree_commit_tree_atomic_update_ref_and_post_commit_commit_tree_status_observation
      side_effect_model: commit_without_push_fetch_network_governed_and_push_explicit_non_force_external_side_effect
      idempotency_model: immutable_attempt_scoped_claims_exact_terminal_replay_workspace_generation_history_manifest_consistency_and_erasure_detection
    p2_03_validation:
      focused_pytest: "14 passed; 0 failed; 0 skipped; 160.62s final exact-tree run including build and separate installed restart"
      predecessor_P2_02_T13_and_T15: "2 passed; 13 deselected; 0 failed; 0 skipped; 7.93s"
      predecessor_exact_P2_01_T18: "1 passed; 26 deselected; 0 failed; 0 skipped; 3.15s"
      broad_non_nested_regression: "418 passed; 20 nested qualification gates deselected; 127 subtests passed; 0 failed; 0 skipped; 314.09s"
      mypy_strict: "61 source/test files; 0 issues; mypy 2.3.1"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P2-03 skip, placeholder, TODO, FIXME, and NotImplemented executable-test hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 8d016cb7cc26d3b6c8ac80acc218fc350945b8049c7f1e8b3f7da15890f2b71f; git_adapter.py source and packaged bytes sha256 69a2a9249cc6ab1c3f518c51018b280e62d65f2a81a061d32356b716311049f8 exactly matched"
      installed_wheel_restart: "separate installed-package writer and reader shared durable SQLite, source and candidate roots, object storage, exact diff and commit receipts, Artifacts, ContentRefs, ToolCalls, commit, and tree evidence"
      remote_required_paths_and_bytes: "GitHub branch, commit, tree, seven blob IDs, sizes, SHA256 bytes, and exact decoded contents independently read back and matched"
      adversarial_review: "PASS after dirty source preservation, stale source and patch rejection, path escape and .git mutation denial, hook/filter/LFS safety, cross-Project scope, read-only push denial, network-governed fetch, replay after workspace advance, manifest forgery, and content erasure hardening"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; deterministic adversarial tests and static checks used"
    p2_03_kpi:
      repo_mutations_without_exact_base: 0
      unrelated_dirty_state_destroyed: 0
      source_checkout_modified_by_candidate: 0
      unsafe_Git_config_execution: 0
      implicit_pushes: 0
      unobserved_commit_claims: 0
    p2_03_reality_classification:
      exact_revision_repository_and_candidate_workspace: REAL
      managed_process_Git_CLI_execution: REAL
      staged_unstaged_untracked_ContentRef_and_Artifact_capture: REAL
      exact_commit_parent_tree_and_push_observation: REAL
      installed_wheel_separate_process_restart: REAL
      local_filesystem_fetch_and_explicit_safe_push: REAL
      remote_network_fetch_or_push: POLICY_GOVERNED_NOT_EXECUTED
      submodule_content_materialization: UNSUPPORTED_BY_THIS_ADAPTER_and_not_claimed
      LFS_filter_execution_or_object_materialization: UNSUPPORTED_POLICY_DENIED_and_not_claimed
    p2_03_qualification:
      RepositoryRef_and_RepositoryWorkspaceRef: VERIFIED
      GitAdapter_replaceable_capability_registration: VERIFIED
      exact_HEAD_commit_tree_status_and_dirty_state: VERIFIED
      isolated_candidate_without_source_checkout_mutation: VERIFIED
      exact_staged_unstaged_untracked_diff_evidence: VERIFIED
      stale_source_stale_patch_context_mismatch_and_path_escape_denial: VERIFIED
      hooks_filters_textconv_credentials_submodule_LFS_and_symlink_policy: VERIFIED
      exact_parent_commit_new_commit_tree_and_post_commit_observation: VERIFIED
      fetch_network_policy_and_push_external_authority: VERIFIED
      Project_scope_read_only_Task_and_cross_Project_denial: VERIFIED
      restart_idempotency_receipt_manifest_and_content_integrity: VERIFIED
      raw_QuarantineRef_runtime_dependency: 0
    p2_03_schema_changes:
      - git_repository_claims
      - git_repositories
      - git_workspace_claims
      - git_workspace_states
      - git_workspace_heads
      - git_operation_claims
      - git_operation_results
      - immutable_repository_workspace_claim_result_and_generation_integrity_guards
    p2_03_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/process.py
      - src/biella/git_adapter.py
      - tests/test_p2_02_process.py
      - tests/test_p2_03_git_adapter.py
      - tests/fixtures/p2_03_installed_writer.py
      - tests/fixtures/p2_03_installed_reader.py
    p2_03_remote_path_evidence:
      src_biella_init: "blob c613d0183c037d523cd2d69a34978c80b96b053e; size 15911; sha256 8502a6facde4b19da3bea3c2f0f9bac65dd4ddf19d1c231833c5fee13c8ad748"
      src_biella_process: "blob 84ccbf1f3c904b4161a02ece092f11cbdfae409c; size 87757; sha256 aeb31b60e54248e6cfc6c1b7839001b440e3a6cf6f4871be6028fee2a06912a9"
      src_biella_git_adapter: "blob 2af3e29b928f411f256bb94dcf8ccaf35fabf36d; size 124107; sha256 69a2a9249cc6ab1c3f518c51018b280e62d65f2a81a061d32356b716311049f8"
      test_p2_02: "blob fb1b51ab26eb59d8897135125cda729598dc49d6; size 34366; sha256 3c1b6f7e00bb649bfcdea806fc2c09617566207006dc8dbc7bd5c5d305b51ee6"
      test_p2_03: "blob 44390c5b18fc9ca3720c6e362fd88276ea84d563; size 34699; sha256 5aa4932c33d61583f411799c3349974b35b7567d582999a8523e356349c4efcc"
      installed_writer: "blob e5789110e9c61bad1e371888f576aa4c7e09436d; size 6542; sha256 b2ca51c11895f5567ee663932ab5d1de1b7e4832aac284be682309a4a7d11dfb"
      installed_reader: "blob 93017f99ea5999956158a607957593af776d29f7; size 1787; sha256 2b83acdfa4794dca4e66cfc190a6430c2b3cb767561c343488e435ff6823f2e0"
    p2_04_status: DURABLY_COMPLETE
    p2_04_source_commit: 800aa08e5aa6d86221c64ffaef667c5eab46b915
    p2_04_result_commit: 7aaf3e83847d87538ec033fb9a043ea83bcbdf95
    p2_04_result_tree: ec205b0e33c05b2a9bcd8fe6e2e5b8919c0daffc
    p2_04_remote_readback: VERIFIED
    p2_04_implementation:
      production_modules_added: 1
      public_exports_added: 23
      focused_pytest_cases: 11
      installed_restart_programs_added: 2
      migrations_added: 0
      schema_tables_added: 4
      capability_surface: runtime_create_start_execute_cancel_stop_inspect_collect_cleanup_describe
      runtime_contract: immutable_image_digest_entrypoint_direct_args_authorized_mounts_network_policy_CPU_RAM_GPU_storage_process_limits_environment_secret_refs_timeout_and_bounded_logs
      identity_model: exact_Project_Run_NodeAttempt_fence_optional_ResourceAllocation_adapter_image_runtime_host_boot_container_generation_and_start_time
      enforcement_model: requested_enforced_and_observed_limits_are_separate_with_NONE_network_read_only_rootfs_nonroot_user_cap_drop_no_new_privileges_CPU_RAM_and_PID_limits
      output_model: descriptor_safe_stream_capture_secret_scan_ContentRef_Artifact_and_receipt_persistence_before_cleanup
      recovery_model: exact_owned_label_image_container_generation_spec_NodeAttempt_and_fence_reconciliation_with_unknown_runtime_inertness
      idempotency_model: immutable_attempt_scoped_claims_monotonic_runtime_generations_exact_terminal_replay_receipt_manifest_consistency_and_erasure_detection
    p2_04_validation:
      focused_pytest: "11 passed; 0 failed; 0 skipped; 98.73s final exact-tree run including exact wheel build and separate installed restart"
      broad_non_nested_regression: "428 passed; 21 nested qualification gates deselected; 127 subtests passed; 0 failed; 0 skipped; 402.61s"
      mypy_strict: "65 source/test files; 0 issues; mypy 2.3.1"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P2-04 skip, placeholder, TODO, FIXME, and NotImplemented executable-test hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 3794a05e504d3739c86e3c8406f479d5cbdf0d4ae0258f9355d25606a8a2a4ee; isolated_runtime.py source and packaged bytes sha256 0ad258145099cc856b76706eb3cbb30640e989844e573277014e6433f984385e exactly matched"
      installed_wheel_restart: "separate installed-package writer and reader shared durable SQLite, object storage, exact runtime generations, ToolCalls, receipts, output Artifact, cleaned state, and restart reconstruction"
      remote_required_paths_and_bytes: "GitHub branch, commit, tree, five blob IDs, sizes, SHA256 bytes, and exact raw contents independently read back and matched"
      adversarial_review: "PASS after mutable image, cross-Project mount, host-root mount, unsupported network/storage/GPU, read-only mutation, hostile argv, secret persistence, timeout/cancel/stop/crash, premature cleanup, stale output, unknown orphan, receipt/state tamper, and content erasure hardening"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; deterministic adversarial tests, strict typing, and manual trust-boundary review used"
      post_test_owned_runtime_inventory: "0 Biella-labeled Docker containers"
    p2_04_kpi:
      forbidden_mount_access: 0
      network_policy_bypasses: 0
      secrets_in_normal_evidence: 0
      resource_leaks_after_terminal: 0
      unknown_runtimes_killed: 0
      provider_runtime_types_in_kernel: 0
    p2_04_reality_classification:
      Docker_OCI_reference_adapter: REAL
      immutable_Alpine_image_identity: REAL
      isolated_execution_and_binary_safe_output_Artifact: REAL
      network_NONE_enforcement: REAL
      CPU_RAM_and_process_limit_enforcement_and_observation: REAL
      secret_file_injection_and_managed_log_redaction: REAL
      timeout_cancel_stop_crash_cleanup_and_restart_reconciliation: REAL
      installed_wheel_separate_process_restart: REAL
      local_GPU_visibility: UNAVAILABLE_EXPLICITLY_REJECTED
      restricted_and_Project_policy_network: UNSUPPORTED_BY_THIS_ADAPTER_EXPLICITLY_REJECTED
      storage_quota: UNSUPPORTED_BY_THIS_ADAPTER_EXPLICITLY_REJECTED
    p2_04_qualification:
      IsolatedRuntimeSpec_IsolatedRuntimeAdapter_RuntimeRef_state_receipts_and_descriptor: VERIFIED
      exact_image_runtime_host_container_generation_NodeAttempt_Run_and_optional_ResourceAllocation_identity: VERIFIED
      provider_neutral_Task_Graph_contracts: VERIFIED
      authorized_read_only_writable_cross_Project_and_forbidden_host_mounts: VERIFIED
      network_NONE_and_unsupported_network_mode_rejection: VERIFIED
      requested_enforced_observed_CPU_RAM_process_and_explicit_GPU_storage_support: VERIFIED
      secret_refs_runtime_injection_redaction_and_normal_evidence_absence: VERIFIED
      output_ContentRef_and_Artifact_before_cleanup: VERIFIED
      timeout_cancel_stop_crash_and_owned_resource_release: VERIFIED
      restart_owned_orphan_recovery_and_unknown_runtime_inertness: VERIFIED
      stale_generation_output_and_scope_authority_denial: VERIFIED
      restart_idempotency_receipt_manifest_state_and_content_integrity: VERIFIED
      raw_QuarantineRef_runtime_dependency: 0
    p2_04_schema_changes:
      - isolated_runtime_states
      - isolated_runtime_heads
      - isolated_runtime_operation_claims
      - isolated_runtime_operation_results
      - immutable_state_claim_result_and_monotonic_generation_integrity_guards
    p2_04_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/isolated_runtime.py
      - tests/test_p2_04_isolated_runtime.py
      - tests/fixtures/p2_04_installed_writer.py
      - tests/fixtures/p2_04_installed_reader.py
    p2_04_remote_path_evidence:
      src_biella_init: "blob d3fe78aed9a2ec78819342eee92cebb241b37c9c; size 17215; sha256 4700e65f440494255a8f99fe0f6fbb313d3c1ec200e0716e39d00c1c0d39e128"
      src_biella_isolated_runtime: "blob b2770d53872ebe58e88fed646b4c6b95c3d52b18; size 132635; sha256 0ad258145099cc856b76706eb3cbb30640e989844e573277014e6433f984385e"
      test_p2_04: "blob 3c81ddba0c7a934f47d1a5cdbb12207792bfcdf1; size 38081; sha256 a5bd3f7b4c7609e28151cedcf4a57e8e0ceacb37b8e6bf579ab650fe3dbe390f"
      installed_writer: "blob d9783a4fdf2d3b3fadbf39bab0f88d3e32a833be; size 6128; sha256 759f539c6aa5e66c805741a0f2cf36d25478861c5180246c7096e93fc8d8d006"
      installed_reader: "blob 6d62d94a611f7741ad4af8798a09fa2bd6f4d556; size 2045; sha256 aabf26bfdf4eaa060e832e59705724a63514e334a632c259a0e384204e4fe7cb"
    p2_05_status: DURABLY_COMPLETE
    p2_05_source_commit: ff8e2d5800e64b67dee96928d4ae2feed189b87c
    p2_05_result_commit: de7864daff7fc9c8939872d0f45968a9f5d4b767
    p2_05_result_tree: c12614081948b7af3222b53add7a090d27e6c173
    p2_05_remote_readback: VERIFIED
    p2_05_implementation:
      production_modules_added: 1
      public_exports_added: 19
      focused_pytest_cases: 13
      installed_restart_programs_added: 2
      migrations_added: 0
      schema_tables_added: 5
      capability_surface: register_destination_get_destination_execute_get_result_cancel_describe
      destination_contract: exact_Project_origin_path_prefix_auth_profile_data_policy_egress_policy_TLS_and_redirect_allowlist_identity
      request_contract: exact_Project_Task_digest_Run_NodeAttempt_fence_destination_policy_method_path_query_headers_secret_refs_body_redirect_response_cap_timeout_and_expected_digest
      transport_model: verified_TLS_manual_redirects_streamed_64KiB_upload_and_download_binary_exactness_bounded_response_timeout_and_cancellation
      evidence_model: safe_HTTP_metadata_ContentRef_response_Artifact_receipt_Artifact_and_ToolCall_with_transport_only_success
      recovery_model: immutable_destination_execution_claim_result_and_cancellation_evidence_with_restart_replay_tamper_and_content_erasure_detection
      idempotency_model: exact_destination_and_execution_claim_digests_terminal_replay_and_conflicting_request_rejection
    p2_05_validation:
      focused_pytest: "13 passed; 0 failed; 0 skipped; 20.17s final exact-tree run including exact wheel build and separate installed restart"
      broad_non_nested_regression: "440 passed; 22 nested qualification gates deselected; 127 subtests passed; 0 failed; 0 skipped; 419.38s"
      mypy_strict: "69 source/test files; 0 issues; mypy 2.3.1"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P2-05 skip, placeholder, TODO, FIXME, and NotImplemented executable-test hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 8b66083fb649392eb2ffde721830aecccc3d8dd658cf9720dde1cff2ea7cdb4b; all packaged biella Python paths exactly matched source bytes"
      installed_wheel_restart: "separate installed-package writer and reader shared durable SQLite, object storage, exact HTTP result, response ContentRef and Artifact, ToolCall, receipt Artifact, and restart verification"
      remote_required_paths_and_bytes: "GitHub branch, commit, tree, five blob IDs, sizes, SHA256 bytes, and exact raw contents independently read back and matched"
      adversarial_review: "PASS after cross-Project destination/request/result, policy-before-secret/body, sensitive query/header, redirect exfiltration, output cap, digest mismatch, timeout/cancel, invalid TLS, idempotency, row tamper, and content erasure checks"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; deterministic adversarial tests, strict typing, and manual trust-boundary review used"
    p2_05_kpi:
      credential_leaks: 0
      egress_policy_bypasses: 0
      redirect_policy_bypasses: 0
      unbounded_response_materialization: 0
      timeouts_claimed_success: 0
      binary_content_corruption: 0
    p2_05_reality_classification:
      stdlib_HTTP_adapter: REAL
      loopback_GET_POST_binary_redirect_timeout_and_cancellation_transport: REAL
      verified_TLS_invalid_certificate_rejection: REAL
      streamed_ContentRef_upload_and_response_Artifact_download: REAL
      ToolCall_and_Artifact_durable_restart_evidence: REAL
      installed_wheel_separate_process_restart: REAL
      external_internet_provider_endpoint: NOT_RUN_NOT_REQUIRED_FOR_TRANSPORT_QUALIFICATION
      HTTP2_transport: UNSUPPORTED_BY_THIS_ADAPTER_and_not_claimed
      custom_TLS_trust_roots: UNSUPPORTED_BY_THIS_ADAPTER_and_not_claimed
    p2_05_qualification:
      HttpDestination_HttpAdapter_HttpExecutionRequest_HttpExecutionResult_and_descriptor: VERIFIED
      exact_Project_Task_Run_NodeAttempt_fence_data_and_egress_policy_binding: VERIFIED
      policy_authorization_before_credentials_body_or_network_transfer: VERIFIED
      NONE_SAME_ORIGIN_ALLOWLIST_redirect_reauthorization_and_cross_origin_secret_drop: VERIFIED
      streamed_upload_download_response_cap_timeout_cancel_and_binary_exactness: VERIFIED
      verified_TLS_and_invalid_certificate_fail_closed: VERIFIED
      transport_success_separate_from_HTTP_application_status_and_semantic_acceptance: VERIFIED
      safe_ToolCall_ContentRef_response_Artifact_receipt_Artifact_and_provenance_chain: VERIFIED
      restart_idempotency_claim_result_receipt_and_content_integrity: VERIFIED
      provider_neutral_Task_and_Graph_contracts: VERIFIED
      hostile_instruction_secret_and_sensitive_metadata_inertness: VERIFIED
      raw_QuarantineRef_runtime_dependency: 0
    p2_05_schema_changes:
      - http_destinations
      - http_destination_claims
      - http_execution_claims
      - http_execution_results
      - http_cancellations
      - immutable_destination_claim_result_and_cancellation_integrity_guards
    p2_05_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/http_adapter.py
      - tests/test_p2_05_http_adapter.py
      - tests/fixtures/p2_05_installed_writer.py
      - tests/fixtures/p2_05_installed_reader.py
    p2_05_remote_path_evidence:
      src_biella_init: "blob d807cb248be0c298ebaf5fbc32d6a2038c03651b; size 18167; sha256 7b418a3b6f0e0c784a517300d80a5fab390625a1861557075dc86fda441d1833"
      src_biella_http_adapter: "blob 47fccd46cbe9b0956aa7008ece2e2fd999242ec6; size 92981; sha256 383da7d6acb042f3149fa69e3175035e4d3196c12d3e9fed54977aea768ebb6b"
      test_p2_05: "blob a3d746f65fd079e54ee4a7008aa619656c2ab815; size 38778; sha256 2c6366f37b87c5ff4fce25b3c7a1041caca75897161e668930398e92c9fca51a"
      installed_writer: "blob 2cf31b69da46fd5c25f595b9a2e6e16b1dcea5c1; size 6544; sha256 44cdc65902d5cd0a196cac81faca5ce1e394772d686504bb1cda51bc414c0ff6"
      installed_reader: "blob d2cd9033c9798e30a4f4dab3a20034a263a07dce; size 1474; sha256 0ffbd098631317428a6fd00c8110968c598a186dfb8ffc9dbd73305741391e9e"
    p2_06_status: DURABLY_COMPLETE
    p2_06_source_commit: 0628d5d91dcdecaca4978f23f53e0a899bab0608
    p2_06_result_commit: 35edc349447868fd0be4250d5c071579df5e9650
    p2_06_result_tree: 5c1883b17a50117530f4cea9e1df1fc2d30e990c
    p2_06_remote_readback: VERIFIED
    p2_06_implementation:
      production_modules_added: 1
      public_exports_added: 33
      focused_pytest_cases: 12
      installed_restart_programs_added: 2
      migrations_added: 0
      schema_tables_added: 7
      adapter_classes: ReferenceModelAdapter_and_HostedHttpModelAdapter
      interface_surface: ModelDeployment_ModelAdapter_infer_embed_rerank_health_cancel_describeRuntime
      deployment_contract: exact_provider_model_revision_artifact_endpoint_capability_modality_context_tool_resource_data_egress_health_and_runtime_identity
      request_contract: exact_Project_Task_digest_Run_Graph_NodeAttempt_fence_Capability_deployment_ContextReceipt_inputs_parameters_schema_timeout_and_policy
      result_contract: exact_ModelCall_ContentRef_output_Artifact_receipt_Artifact_usage_timing_finish_provider_trace_runtime_identity_and_failure_classification
      tool_policy: provider_proposals_normalized_to_authorized_child_Biella_ToolCall_and_unauthorized_proposals_inert
      recovery_model: immutable_deployment_claim_health_history_execution_claim_result_and_cancellation_evidence_with_restart_replay_tamper_content_erasure_and_stale_fence_rejection
      idempotency_model: exact_deployment_and_request_digests_execution_identity_terminal_replay_and_conflicting_request_rejection
    p2_06_validation:
      focused_pytest: "12 passed; 0 failed; 0 skipped; 28.78s final exact-tree run including exact wheel and separate installed restart qualification"
      coupled_regression: "50 passed; 4 nested qualification gates deselected; 4 subtests passed; 0 failed; 0 skipped; 117.59s"
      broad_non_nested_regression: "451 passed; 23 nested qualification gates deselected; 127 subtests passed; 0 failed; 0 skipped; 444.62s"
      mypy_strict: "73 source/test files; 0 issues"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P2-06 skip, placeholder, TODO, FIXME, and NotImplemented executable-test hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 66e210be3e5210db2b31bbd8581b8b72bf293d0241f8f9ba91c752b1991f1c4b; all 26 packaged biella Python source paths exactly matched source bytes"
      installed_wheel_restart: "separate installed-package writer and reader shared durable SQLite/object storage and verified ModelDeployment, ModelCall, output ContentRef/Artifact, receipt Artifact, runtime identity, terminal replay, and restart readback"
      live_provider_probe: "Cloudflare Workers AI generic account ai/run returned HTTP 200 with exact provider call IDs and provider-reported usage; null content with length finish was rejected rather than fabricated as success"
      remote_required_paths_and_bytes: "GitHub branch, commit, tree, five blob IDs, sizes, SHA256 bytes, and exact raw contents independently read back and matched"
      adversarial_review: "PASS after cross-Project deployment/result, policy/egress/context authority, structured output, null provider output, embedding cardinality/dimension/NaN, rerank coverage/order, unauthorized tools, timeout/cancel, stale fence, idempotency, row tamper, content erasure, and provider-SDK/quarantine isolation checks"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; deterministic adversarial tests, strict typing, and manual trust-boundary review used"
    p2_06_kpi:
      Task_contract_changes_between_providers: 0
      provider_sdk_types_in_kernel: 0
      significant_model_calls_missing_ledger: 0
      fabricated_usage: 0
      malformed_outputs_treated_success: 0
      egress_violating_model_calls: 0
    p2_06_reality_classification:
      HostedHttpModelAdapter: REAL
      Cloudflare_Workers_AI_hosted_infer_route: REAL
      P2_05_HTTP_egress_credential_timeout_cancel_and_Artifact_path: REAL
      ReferenceModelAdapter_infer_embed_rerank: REFERENCE
      deterministic_loopback_hosted_infer_embed_rerank_and_tool_response_validation: REAL_transport_with_REFERENCE_provider_fixture
      local_real_model_runtime: NOT_RUN_UNAVAILABLE_on_current_CPU_host
      live_hosted_embedding_and_rerank_provider_calls: NOT_RUN_not_required_because_contract_and_real_HTTP_path_qualified
      exact_mutable_hosted_alias_revision: UNKNOWN_and_not_fabricated
    p2_06_qualification:
      ModelDeployment_ModelAdapter_infer_embed_rerank_request_result_runtime_health_identity_cancel_and_describeRuntime: VERIFIED
      exact_Project_Task_Run_Graph_NodeAttempt_fence_Capability_deployment_policy_and_ContextReceipt_binding: VERIFIED
      provider_replacement_without_Task_contract_change: VERIFIED
      ModelCall_ledger_for_every_execution_and_authorized_child_ToolCall_mapping: VERIFIED
      structured_output_embedding_and_rerank_fail_closed_validation: VERIFIED
      truthful_nullable_usage_finish_provider_trace_health_and_reality_classification: VERIFIED
      hosted_HTTP_egress_credentials_timeout_cancellation_and_late_stale_fence_rejection: VERIFIED
      output_ContentRef_Artifact_receipt_Artifact_and_exact_provenance_chain: VERIFIED
      restart_idempotency_claim_result_receipt_ModelCall_ToolCall_and_content_integrity: VERIFIED
      hostile_instruction_and_unauthorized_tool_inertness: VERIFIED
      provider_SDK_types_in_Task_Run_Graph_kernel_contracts: 0
      raw_QuarantineRef_runtime_dependency: 0
    p2_06_known_limitations:
      - structured_output_validation_supports_an_explicit_bounded_JSON_schema_subset_and_fails_closed_on_unsupported_keywords
      - hosted_response_parsing_supports_explicit_Cloudflare_and_OpenAI_compatible_shapes_with_exact_deployment_metadata
      - mutable_hosted_alias_revision_remains_null_when_provider_does_not_expose_an_exact_revision
      - tool_execution_uses_an_injected_authorized_executor_and_does_not_automatically_start_a_second_model_inference
      - no_REAL_local_model_runtime_is_available_on_the_current_CPU_host; the_required_REAL_class_is_hosted
    p2_06_schema_changes:
      - model_deployments
      - model_deployment_claims
      - model_health_observations
      - model_health_heads
      - model_execution_claims
      - model_execution_results
      - model_cancellations
      - immutable_deployment_claim_health_history_result_cancellation_and_monotonic_health_head_integrity_guards
    p2_06_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/model_adapter.py
      - tests/test_p2_06_model_adapter.py
      - tests/fixtures/p2_06_installed_writer.py
      - tests/fixtures/p2_06_installed_reader.py
    p2_06_remote_path_evidence:
      src_biella_init: "blob ddf6a429f9f4cfeab212d30a4d687459ff96aba5; size 19764; sha256 c73b62507ea6eca18305f6b552406b872a6733a970693602d29d30c3fc64159e"
      src_biella_model_adapter: "blob d1014b462d0b8757e525015351052c41ad34c8fa; size 125670; sha256 1be767c2082bd5c0672696962645e80f73b6451aa0c634c8cefdc53da6d5d7e4"
      test_p2_06: "blob 6b370198470faed92d2b4f3bd1c9162a4888b657; size 42937; sha256 b5627413eba4f3d6ec36027e54a6dc28230d83d7693dd8cc7258987030443b27"
      installed_writer: "blob 854d82c5af94168933e2cec3b37f064d5202c1c1; size 5831; sha256 e84678a7cfb55cadd1c7cba7a0dd96269b725703e68c4053b4e61198cdd1432b"
      installed_reader: "blob 6b45dc6a47506a766d4dea91871dff0011a83c11; size 1707; sha256 f3d2f0d852136e9310f7c587c70336157b92764482c9bf420ccfcebf9360d44f"
    p2_07_status: DURABLY_COMPLETE
    p2_07_source_commit: 2a1fcfbbafe0e2fad9efb85389802e8b9a808960
    p2_07_initial_implementation_commit: 0360d36e112ac105d7420ee811a1cf02c3409701
    p2_07_result_commit: f0bd9e7a03cc8ac1ce7d0555de14055190fede5b
    p2_07_result_tree: ead59ae03ab218c7b95cee9a93813836945aba2e
    p2_07_remote_readback: VERIFIED
    p2_07_implementation:
      production_modules_added: 1
      public_exports_added: 28
      focused_pytest_cases: 12
      installed_restart_programs_added: 2
      migrations_added: 0
      schema_tables_added: 7
      adapter_classes: ReferenceBrowserAdapter_and_WebDriverBrowserAdapter
      interface_surface: BrowserAdapter_BrowserSessionIdentity_BrowserPageRef_BrowserAction_BrowserActionResult_BrowserWaitCondition_and_BrowserFilesystemUploadSource
      capability_surface: browser_open_navigate_inspect_extract_click_type_select_upload_download_screenshot_evaluate_wait_for_condition_and_submit
      execution_contract: exact_Project_Task_digest_Run_Graph_NodeAttempt_fence_Capability_data_egress_destination_side_effect_session_generation_and_page_identity
      result_contract: exact_ToolCall_ContentRef_output_Artifact_receipt_Artifact_page_runtime_provider_trace_viewport_and_provenance
      recovery_model: immutable_session_generation_claim_state_head_action_claim_result_and_cancellation_evidence_with_crash_replacement_restart_replay_and_stale_rejection
      upload_model: authorized_Artifact_ContentRef_or_controlled_FilesystemRoot_only_with_streamed_disk_backed_ZIP_and_incremental_base64_WebDriver_transport
      wait_model: bounded_selector_URL_DOM_property_network_idle_and_explicit_event_conditions
      idempotency_model: exact_session_spec_and_action_request_digests_terminal_replay_and_conflicting_request_rejection
    p2_07_validation:
      focused_pytest: "12 passed; 0 failed; 0 skipped; 53.63s final exact-tree run including REAL Chromium, exact wheel, install, and separate installed restart"
      broad_non_nested_regression: "462 passed; 24 nested qualification gates deselected; 127 subtests passed; 0 failed; 0 skipped; 477.35s final rerun"
      mypy_strict: "77 source/test files; 0 issues"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P2-07 skip, placeholder, TODO, FIXME, and NotImplemented executable-test hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 554af3dd8f719e9d742d7109c02a196456be19b9402cd73a6594332e3674b84b; all 27 packaged biella Python source paths exactly matched source bytes"
      installed_wheel_restart: "separate installed-package writer and reader shared durable SQLite/object storage and verified active session identity plus terminal BrowserAction ContentRef/Artifact/receipt restart readback"
      real_browser_probe: "pinned selenium/standalone-chromium:4.47.0-20260808 image sha256:1d3d834a2ce93f26cc0d0ae3c61abd189755b32649f5c356c6c5cf9502aa397e; Chromium and ChromeDriver 151.0.7922.108; REAL redirect, inspect, extract, click, type, select, 4.1 MB streamed upload, screenshot, managed download, missing target, submit, and close passed"
      remote_required_paths_and_bytes: "GitHub branch, final commit, tree, five blob IDs, sizes, SHA256 bytes, and exact raw contents independently read back and matched"
      resolved_regression: "initial broad run found P0 identifier-level neutrality rejection of threading.Lock/provider_id; adapter-local guards and identifiers were reconciled to accepted semantics; isolated failure and two complete broad reruns passed"
      adversarial_review: "PASS after cross-Project session/Artifact, Task side-effect, path/origin/egress-before-secret, postcondition, hostile proposal, arbitrary path/JS, controlled root provenance, crash/replacement, late result, timeout/cancel, idempotency, row/content tamper, provider-page preflight, secret scan, and kernel/quarantine isolation checks"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; deterministic adversarial tests, strict typing, and manual trust-boundary review used"
    p2_07_kpi:
      browser_session_loss_causes_Run_loss: 0
      download_without_ContentRef: 0
      external_side_effect_without_Task_authority: 0
      credential_leaks: 0
      stale_browser_generation_results_accepted: 0
      browser_provider_types_in_kernel: 0
      unattributed_external_browser_mutations: 0
    p2_07_reality_classification:
      WebDriverBrowserAdapter: REAL
      pinned_Selenium_Chromium_container_and_W3C_control_transport: REAL
      managed_download_and_streamed_upload_transport: REAL
      ReferenceBrowserAdapter: REFERENCE
      host_installed_browser_or_provider_SDK: UNAVAILABLE_NOT_REQUIRED_containerized_W3C_fallback_used
      narrowed_path_policy_REAL_subresource_interception: UNSUPPORTED_AND_FAILS_CLOSED
    p2_07_qualification:
      BrowserAdapter_session_identity_page_ref_structured_action_result_wait_and_upload_source_contracts: VERIFIED
      exact_Project_Task_Run_Graph_NodeAttempt_fence_Capability_policy_destination_origin_and_side_effect_binding: VERIFIED
      session_generation_replacement_and_stale_action_result_rejection: VERIFIED
      durable_ToolCall_ContentRef_Artifact_receipt_and_source_provenance_chain: VERIFIED
      authorized_Artifact_ContentRef_and_controlled_FilesystemRoot_uploads_with_arbitrary_host_path_rejection: VERIFIED
      exact_and_interrupted_download_classification: VERIFIED
      bounded_structured_waits_screenshot_viewport_and_provider_runtime_identity: VERIFIED
      hostile_instruction_model_proposal_secret_cookie_and_provider_type_inertness: VERIFIED
      restart_idempotency_claim_result_receipt_session_generation_and_content_integrity: VERIFIED
      raw_QuarantineRef_runtime_dependency: 0
    p2_07_known_limitations:
      - REAL_Chromium_host_resolver_containment_accepts_only_full_origin_destination_path_authority; narrower_path_policies_fail_closed_until_a_policy_aware_subresource_interceptor_exists
      - managed_WebDriver_download_response_is_bounded_to_64_MiB_and_larger_downloads_fail_closed
      - explicit_event_wait_observes_events_after_listener_registration_and_does_not_fabricate_historical_events
      - browser_profile_cookie_and_session_storage_remain_ephemeral_runtime_sensitive_state_and_are_not_reconstructed_after_adapter_restart
    p2_07_schema_changes:
      - browser_session_generations
      - browser_session_claims
      - browser_session_states
      - browser_session_heads
      - browser_action_claims
      - browser_action_results
      - browser_cancellations
      - immutable_generation_claim_state_action_result_cancellation_and_monotonic_session_head_integrity_guards
    p2_07_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/browser_adapter.py
      - tests/test_p2_07_browser_adapter.py
      - tests/fixtures/p2_07_installed_writer.py
      - tests/fixtures/p2_07_installed_reader.py
    p2_07_remote_path_evidence:
      src_biella_init: "blob 0760f96415724efe490c2397b7663a043c13ba51; size 21245; sha256 181ccf3b3b0954ada6cfcca97973ea3fde9aa20417da9f5592f2320dc1f31d8a"
      src_biella_browser_adapter: "blob 3c62b405abd983d0d4b38f9053b34d0333bde433; size 171356; sha256 523335a1bca3fec30b2c252b3db109affd06d857f62736b0409c12afe8df47cd"
      test_p2_07: "blob 0c815210c9be17f8f0e962cd27dd76a4abb8b715; size 50525; sha256 50a05431514926696edcf27f1dbc72d18a4b0a8855ffe00e1441208a5f77d14e"
      installed_writer: "blob 20238d6205c04bdbdd7a1e880b651182ceae3bbd; size 6323; sha256 199d64f413523ffec18579348c6cbed595cdf686e037198fef7f8746b616a5e5"
      installed_reader: "blob 195b6f217c3e213a64b2e1b20ac418ed528a3731; size 2000; sha256 5014dcb461035447da3737888c8f735f89549f2f7de382f2bd1b811e9806b792"
    p2_08_status: DURABLY_COMPLETE
    p2_08_source_commit: e60fcf7b7074c0770ad35af3d5f12862d4545ed9
    p2_08_result_commit: fcc954bfc2be3fae7f01986311eda2b6fd92e300
    p2_08_result_tree: 3d54e11466499eb6d62729a50e0e29e9ba659da8
    p2_08_remote_readback: VERIFIED
    p2_08_implementation:
      production_modules_added: 1
      public_exports_added: 32
      focused_pytest_cases: 14
      installed_restart_programs_added: 2
      migrations_added: 0
      schema_tables_added: 6
      adapter_class: LibpqPostgreSQLAdapter
      interface_surface: DatabaseConnectionRef_DatabaseConnection_DatabaseExecutionBinding_query_connect_transaction_schema_migration_requests_results_and_PostgreSQLAdapter
      capability_surface: database_postgresql_connect_inspect_schema_query_transaction_execute_and_migrate
      execution_contract: exact_Project_Task_digest_Run_Graph_NodeAttempt_fence_Capability_connection_scope_mode_restriction_TLS_auth_profile_and_result_persistence_authority
      result_contract: exact_ToolCall_ContentRef_optional_Artifact_statement_parameter_digest_SQLSTATE_bounded_message_receipt_and_provenance
      transaction_model: append_only_OPEN_terminal_state_evidence_with_commit_observation_rollback_cancel_timeout_and_TRANSACTION_OUTCOME_UNKNOWN
      query_model: libpq_parameter_arrays_single_command_protocol_single_row_streaming_and_explicit_READ_ONLY_MUTATING_DDL_MIGRATION_modes
      storage_model: sensitive_query_rows_persist_only_when_exact_Task_requires_database_persist_result
      pooling_model: ephemeral_two_connection_pool_keyed_by_connection_ref_and_in_memory_auth_material_digest_never_durable_authority
    p2_08_validation:
      focused_pytest: "14 passed; 0 failed; 0 skipped; 16.82s final exact-tree run including REAL PostgreSQL, exact wheel, install, and separate installed restart"
      broad_non_nested_regression: "474 passed; 26 nested qualification gates deselected; 127 subtests passed; 0 failed; 0 skipped; 488.53s final rerun"
      mypy_strict: "81 source/test files; 0 issues"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P2-08 skip, placeholder, TODO, FIXME, and NotImplemented executable-test hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      neutrality_scan: "prohibited provider/model/agent/heavyweight-lock identifiers in postgresql_adapter.py: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 fb63f728e18409df46699ed5ac53a9133226e51402f410d5f404fb00735bb178; all 28 packaged biella Python source paths exactly matched source bytes"
      installed_wheel_restart: "separate installed-package writer and reader shared durable SQLite/object storage and REAL PostgreSQL; terminal query ContentRef, receipt, ToolCall status, and row count matched after adapter pool recreation"
      real_postgresql_probe: "PostgreSQL 18.6 and libpq 18.6; dedicated TCP role/database; connect/version, bad auth, parameterized hostile value, row/byte limits, 25000-row streamed result, mutation/read-only rejection, commit/rollback, timeout, explicit and concurrent cancel, unknown commit fixture, schema inspection, exact-Artifact migration success/failure/schema guard, isolation, secret scan, and restart passed"
      remote_required_paths_and_bytes: "GitHub main ref, final commit, tree, five blob IDs, sizes, SHA256 bytes, and exact raw contents independently read back and matched"
      resolved_findings: "explicit connect probes no longer borrow pooled auth; pool reuse is keyed by in-memory credential digest; concurrent cancellation has one rollback owner and one CANCELLED durable terminal state; unresolved custom TLS trust roots fail closed"
      adversarial_review: "PASS after cross-Project and infrastructure connection denial, internal database identity denial, read-only mislabeled write rejection, hostile parameter inertness, secret redaction, bounded streaming, cancellation race, ambiguous commit, stale schema migration, restart idempotency, receipt integrity, and kernel/quarantine isolation checks"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; deterministic adversarial tests, strict typing, and manual trust-boundary review used"
    p2_08_kpi:
      raw_DB_credentials_in_Task_or_ledger: 0
      cross_project_DB_access: 0
      read_only_write_bypasses: 0
      unbounded_query_results: 0
      failed_transactions_claimed_committed: 0
      internal_Biella_DB_accidentally_exposed: 0
    p2_08_reality_classification:
      LibpqPostgreSQLAdapter: REAL
      local_PostgreSQL_18_6_TCP_server: REAL
      installed_libpq_18_6_C_ABI_parameter_stream_cancel_TLS_and_SQLSTATE_path: REAL
      query_execute_transaction_schema_and_migration_operations: REAL
      ambiguous_commit_transport_loss_fixture: REFERENCE_fault_fixture_over_REAL_transaction_contract
      separate_Python_PostgreSQL_driver: UNAVAILABLE_NOT_REQUIRED_installed_libpq_fallback_used
      verified_remote_TLS_handshake: NOT_RUN_no_remote_TLS_database_required
      custom_TLS_root_ContentRef_resolution: UNAVAILABLE_AND_FAILS_CLOSED_WITH_POLICY_DENIED
    p2_08_qualification:
      DatabaseConnectionRef_Project_and_global_infrastructure_scope_with_no_raw_credentials: VERIFIED
      generic_Project_adapter_internal_database_and_global_infrastructure_boundary: VERIFIED
      exact_Project_Task_Run_Graph_NodeAttempt_fence_Capability_mode_and_connection_restriction_binding: VERIFIED
      parameterized_single_statement_only_and_hostile_instruction_inertness: VERIFIED
      bounded_single_row_streaming_optional_ContentRef_Artifact_persistence_and_provenance: VERIFIED
      ToolCall_query_parameter_digest_SQLSTATE_redaction_receipt_and_restart_integrity: VERIFIED
      transaction_begin_multiple_operations_commit_rollback_cancel_timeout_reset_and_unknown_outcome_truth: VERIFIED
      exact_Artifact_migration_before_after_schema_digest_and_production_denial: VERIFIED
      bounded_tables_columns_indexes_constraints_extensions_and_server_version_inspection: VERIFIED
      TLS_mode_minimum_protocol_explicit_loopback_plaintext_and_unresolved_custom_root_fail_closed: VERIFIED
      raw_QuarantineRef_runtime_dependency: 0
    p2_08_known_limitations:
      - exact_custom_TLS_root_certificate_refs_fail_POLICY_DENIED_until_a_ContentRef_to_ephemeral_libpq_sslrootcert_materializer_exists; VERIFY_FULL_without_a_custom_root_uses_libpq_system_trust
      - REAL_TLS_handshake_was_not_required_or_available_for_the_local_loopback_PostgreSQL_fixture; plaintext_was_explicitly_scoped_to_literal_loopback
      - result_cells_use_PostgreSQL_text_format_and_JSONL_encoding; binary_result_format_and_COPY_export_import_are_later_optional_operations
      - schema_inspection_is_bounded_to_the_requested_object_and_byte_limits_and_intentionally_excludes_row_data
      - production_connections_reject_automatic_migrate_even_when_the_Task_has_external_side_effect_authority
      - live_transactions_are_ephemeral_pool_state_and_cannot_resume_after_adapter_restart; durable_receipts_and_terminal_results_remain_readable
    p2_08_schema_changes:
      - postgresql_connections
      - postgresql_connection_claims
      - postgresql_operation_claims
      - postgresql_operation_results
      - postgresql_transaction_states
      - postgresql_transaction_heads
      - immutable_connection_claim_operation_result_and_transaction_state_integrity_guards
    p2_08_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/postgresql_adapter.py
      - tests/test_p2_08_postgresql_adapter.py
      - tests/fixtures/p2_08_installed_writer.py
      - tests/fixtures/p2_08_installed_reader.py
    p2_08_remote_path_evidence:
      src_biella_init: "blob 25fffaa1f13dc0b153b3ac3c87a7563fc7d94d48; size 23057; sha256 2cb9b5992bc2b15d97e1c56f6d3983b8a06274e4787345151cbafe3167171ff0"
      src_biella_postgresql_adapter: "blob c162861ee6d3d39694ab11dddb9637ec31ed7b22; size 150890; sha256 06c586d4ef23de25dc658d2dd522524f41f3d796b0e855d4f5424fc6cb1a3684"
      test_p2_08: "blob 762118d1bf549a6e3df1bbb72b8eb6838b8dee57; size 35737; sha256 f0babedd9044b959baeaa61752dfbaa5d7e07346894775d3c88901519c0ab04c"
      installed_writer: "blob d57024993bb1773a50aa2a4c35993d3113bed5a4; size 5759; sha256 14ee8e7eb167176788f73ee4f2b9f63d58440437b3c7e060bdc4cd329091bc5d"
      installed_reader: "blob 79b56495d1a8ed88ed552a2ca799a30f025aa648; size 1553; sha256 eacc3545f47398552e91029c9d3e14782a65a5b2de9cc1d24dcb21b59b79b87a"
    p2_09_status: DURABLY_COMPLETE
    p2_09_source_commit: eab63a9b743383beda8be2c6e39aeaa0381f1b31
    p2_09_result_commit: 03ea21dbd22466470d07a674fd330ad68009d756
    p2_09_result_tree: 5663d2b02872fd0bdc1fb10320e2012e63122345
    p2_09_remote_readback: VERIFIED
    p2_09_implementation:
      production_modules_added: 1
      existing_modules_extended: 2
      public_exports_added: 12
      focused_pytest_cases: 14
      installed_restart_programs_added: 2
      migrations_added: 0
      durable_state_tables_added: 7
      independent_reference_backend_tables_added: 1
      adapter_surface: FilesystemObjectStorageBackend_and_SQLiteObjectStorageBackend
      coordinator_surface: ReplicatedObjectStore_registerArtifactReplica_replicateContent_readArtifact_openArtifact_locations_observationHistory_repairReplica_deleteReplica_cancelReplication_and_metrics
      identity_contract: one_P1_ContentRef_across_all_backends_with_ContentLocation_physical_state_excluded_from_Artifact_and_ContentObject_identity
      authorization_contract: exact_ProjectAccess_and_ArtifactRef_gate_all_logical_reads_replication_repair_deletion_and_cancellation_with_no_digest_only_or_raw_quarantine_entrypoint
      replica_state_contract: append_only_UPLOADING_VERIFYING_AVAILABLE_CORRUPT_MISSING_FAILED_observations_with_integrity_digests_and_durable_heads
      concurrency_contract: durable_per_Project_content_target_fences_reject_superseded_uploaders_and_cancelled_or_stale_results_never_publish_AVAILABLE
      verification_contract: bounded_streaming_and_independent_target_readback_digest_and_size_verification_without_provider_success_ETag_or_verify_claim_authority
      backend_mapping: ContentLocation.storage_locator_semantics_use_accepted_P1_locator_field_and_size_semantics_use_size_bytes
    p2_09_validation:
      focused_pytest: "14 passed; 0 failed; 0 skipped; 3.55s final exact-tree run including durable restart, cancellation, concurrency fencing, exact wheel, install, and separate installed restart"
      predecessor_storage_regression: "34 passed; 26 subtests passed; 0 failed; 0 skipped; 59.68s across P1-01 and P2-09"
      broad_non_nested_regression: "487 passed; 27 recursive qualification gates deselected; 127 subtests passed; 0 failed; 0 skipped; 489.66s"
      mypy_strict: "85 source/test files; 0 issues"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P2-09 skip, placeholder, TODO, FIXME, and NotImplemented executable-test hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      credential_scan: "raw provider credential identifiers or values in P2-09 runtime and durable evidence: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 e47588bf76652a1204428c4ce8e25cb3469d70e9a5c57f2b96b60086b6c08387; all 29 packaged biella Python source paths exactly matched source bytes"
      installed_wheel_restart: "separate installed-package writer and reader shared durable Biella state, filesystem storage, and SQLite reference storage; local replica was physically deleted and exact Artifact and remote replica bytes remained readable after restart"
      remote_required_paths_and_bytes: "GitHub main ref, final commit, tree, six blob IDs, sizes, SHA256 bytes, and exact raw contents independently read back and matched"
      adversarial_review: "PASS after cross-Project Artifact denial, raw quarantine type denial, hostile-byte inertness, corruption-before-fallback, provider success and verify-claim distrust, unavailable target isolation, pre-request and live cancellation, stale-owner fencing, physical deletion guard, exact restart, credential-reference validation, and active-runtime quarantine scan"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; deterministic adversarial tests, strict typing, and manual trust-boundary review used"
    p2_09_kpi:
      content_identity_changes_across_backends: 0
      unverified_replica_AVAILABLE: 0
      corrupt_replica_served: 0
      partial_upload_AVAILABLE: 0
      Artifact_identity_tied_to_URI: 0
      backend_credentials_leaked: 0
    p2_09_reality_classification:
      ReplicatedObjectStore_coordination_and_durable_replica_state: REAL
      FilesystemObjectStorageBackend_local_replica: REAL
      SQLiteObjectStorageBackend_second_independent_durable_backend: REFERENCE
      S3_compatible_MinIO_or_remote_object_storage: UNAVAILABLE_NOT_REQUIRED_faithful_reference_backend_used
      provider_ETag_or_success_integrity_claim: REJECTED_AS_AUTHORITY
      fallow_static_review: NOT_RUN_CLI_UNAVAILABLE
    p2_09_qualification:
      P1_ContentRef_identity_across_filesystem_and_second_backend: VERIFIED
      ContentLocation_per_backend_state_size_locator_verified_created_and_failure_evidence: VERIFIED
      verified_source_stream_upload_independent_readback_and_AVAILABLE_only_after_exact_digest: VERIFIED
      deterministic_healthy_selection_corruption_recording_fallback_and_repair: VERIFIED
      missing_local_restore_with_same_ContentRef_and_no_new_Artifact: VERIFIED
      unavailable_interrupted_cancelled_and_stale_uploads_never_AVAILABLE: VERIFIED
      physical_replica_deletion_distinct_from_Artifact_or_ContentObject_deletion: VERIFIED
      exact_Project_Artifact_remote_egress_secret_ref_and_quarantine_firewall_authority: VERIFIED
      durable_restart_idempotency_observation_integrity_transfer_fencing_and_metrics: VERIFIED
      raw_QuarantineRef_runtime_dependency: 0
    p2_09_known_limitations:
      - no_reachable_scoped_S3_compatible_MinIO_or_remote_object_store_was_available; the_second_backend_is_an_explicit_durable_SQLite_REFERENCE_implementation_not_a_claimed_remote_service
      - provider_credential_resolution_and_network_transport_are_backend_responsibilities; network_registrations_require_exact_Project_secret_and_egress_refs_before_use
      - deterministic_replica_selection_uses_static_priority_then_backend_id; adaptive_cost_latency_and_locality_ranking_remain_for_P4
      - physical_replica_deletion_requires_another_verified_copy; global_GC_retention_and_reference_completeness_are_intentionally_not_implemented
      - SQLite_reference_storage_is_for_contract_fidelity_and_restart_evidence_not_remote_warehouse_performance
    p2_09_schema_changes:
      - replica_backends
      - content_replica_observations
      - content_replica_heads
      - replica_cancellations
      - replica_transfer_events
      - replica_transfer_heads
      - replica_metric_events
      - object_storage_objects_in_independent_reference_backend_database
      - append_only_observation_metric_and_transfer_event_guards_plus_monotonic_fenced_heads
    p2_09_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/object_store.py
      - src/biella/replicated_object_store.py
      - tests/test_p2_09_replicated_object_store.py
      - tests/fixtures/p2_09_installed_writer.py
      - tests/fixtures/p2_09_installed_reader.py
    p2_09_remote_path_evidence:
      src_biella_init: "blob d3dff59e51a5e7735e11b939ebde19293116d96a; size 23774; sha256 0b63b1dd2339f226907d7e42d3048d094a8178773d7d514ed7c795f4bebd4cb8"
      src_biella_object_store: "blob 542ec2643f38c23cc506909abad7f526d8c63808; size 28750; sha256 7ee1c8066277d85d5c00bb3a67ece0da75367140160eff14ae27ffdfcd4683f4"
      src_biella_replicated_object_store: "blob f2096e71e91f31466b39d0cf10aabaaecf71667b; size 63719; sha256 ce3f15caabb8932758526f78b91b73efdfc8c6338a4e97c111c966e310f9d545"
      test_p2_09: "blob 6b62cdf300c0e60f4388352d02dd114a4b72cd53; size 25595; sha256 04d3b67ecba921a179372076c7efb995ba04be8bf60fe6b8a568b2df8bb26b9f"
      installed_writer: "blob a7e227a19aebcc3f99e84c5d57b7308cf0d42755; size 2473; sha256 6ec22d521271b0c79f93e9451330b7c2463dd0016948bee777b4ea5f63438f43"
      installed_reader: "blob 243fa1f3fab0930a28f9fb43c704008c17c20911; size 2096; sha256 64ca275fb79fa68fd6071df9c51722a043a8bebb136e0f632f5965a76d07befe"
    p2_10_status: DURABLY_COMPLETE
    p2_10_source_commit: 1c6e7fd8a086df851d210e2c26aa918388e552ff
    p2_10_result_commit: df3b6987865aae2f94eaa9650636fae131e4e167
    p2_10_result_tree: 354127377184cc5901e58a2581fafadc17577e95
    p2_10_remote_readback: VERIFIED
    p2_10_implementation:
      production_modules_added: 1
      existing_modules_extended: 1
      public_export_bindings_created_or_changed: 29
      focused_pytest_cases: 11
      migrations_added: 0
      durable_state_tables_added: 12
      context_compilation_surface: ContextBudget_ContextCompileRequest_ContextCompiler_ContextLimitError_ContextManifest_ContextReceipt_reduction_evidence_policies_and_token_source
      retrieval_surface: IndexBuildRequest_IndexBuildResult_RetrievalIndex_RetrievalIndexState_RetrievalChunk_RetrievalCandidate_RetrievalReceipt_RetrievalSearchRequest_RetrievalService_and_SourceSnapshot
      source_contract: exact_ArtifactRef_to_UTF8_unicode_fixed_v1_chunks_to_P2_06_embedding_to_verified_READY_activation_with_source_chunker_model_deployment_runtime_dimension_and_vector_provenance
      search_contract: Project_and_source_prefilter_before_bounded_candidate_materialization_with_optional_rerank_preserving_candidate_identity_and_scope
      context_contract: exact_Task_Run_Graph_Node_attempt_fence_explicit_inputs_Project_Engine_Knowledge_RunMemory_retrieval_tool_policy_budget_reduction_and_content_digest_manifest
      budget_contract: caller_supplied_exact_token_count_requires_exact_tokenizer_identity_otherwise_explicit_unicode_segment_estimate_with_exclusion_reduction_or_CONTEXT_LIMIT_and_no_silent_truncation
      concurrency_contract: durable_build_and_compile_claims_source_revalidation_cancellation_and_stale_owner_fencing_preserve_last_READY_index
      cache_contract: index_cache_deletion_preserves_source_Artifact_Project_Engine_and_RunMemory_truth_and_allows_exact_rebuild
    p2_10_validation:
      focused_source_pytest: "11 passed; 0 failed; 0 skipped; 20.15s"
      exact_installed_wheel_pytest: "11 passed; 0 failed; 0 skipped; 20.13s; executed from /tmp against installed wheel only"
      broad_non_nested_regression: "505 passed; 20 recursive build/install qualification gates deselected; 137 subtests passed; 0 failed; 0 skipped; 509.83s; current installed-wheel qualification passed separately"
      diagnostic_regression: "initial relevant matrix found one deterministic build replay ordering failure after 157 passes; ordering fixed before final gates"
      mypy_strict: "87 source/test files; 0 issues"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P2-10 skip, xfail, placeholder, TODO, FIXME, NotImplemented, and executable-pass hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      public_export_check: "481 unique public export bindings"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 b1f0da226a8f205624257f75510c764790292054aa75c43732e9872c47a114ca; all 30 packaged biella Python paths exactly matched source bytes"
      remote_required_paths_and_bytes: "GitHub main ref, result commit, tree, three blob IDs, sizes, SHA256 bytes, and exact raw contents independently read back and matched"
      adversarial_review: "PASS for Alpha/Beta Project and source isolation, hostile instruction inertness, raw quarantine rejection, provenance chaining, source staleness, failed replacement, exact rebuild, rerank identity, idempotency, concurrency, cancellation, context limits, and ModelCall linkage"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; deterministic adversarial tests, strict typing, and manual trust-boundary review used"
    p2_10_kpi:
      cross_project_retrieval_results: 0
      quarantine_retrieval_results: 0
      chunks_without_source_provenance: 0
      stale_indexes_activated: 0
      silent_context_truncations: 0
      cache_loss_causes_memory_loss: 0
    p2_10_reality_classification:
      SQLite_durable_index_context_receipt_and_claim_state: REAL
      Filesystem_object_storage_source_and_compiled_context: REAL
      local_fixed_chunk_build_search_and_bounded_cosine: REAL_CPU
      P2_06_ReferenceModelAdapter_embedding_rerank_and_reduction: REFERENCE
      hosted_model_provider_or_external_ANN_service: NOT_RUN_NOT_REQUIRED
      fallow_static_review: NOT_RUN_CLI_UNAVAILABLE
    p2_10_qualification:
      exact_Project_Task_Run_Graph_Node_attempt_fence_and_source_identity: VERIFIED
      versioned_chunk_embedding_build_verify_activate_and_search_provenance: VERIFIED
      Project_and_source_prefilter_before_candidate_materialization: VERIFIED
      optional_rerank_preserves_candidate_set_identity_and_scope: VERIFIED
      deterministic_compilation_digest_explicit_inclusion_exclusion_and_budget_evidence: VERIFIED
      exact_tokenizer_identity_or_explicit_estimate_source: VERIFIED
      stale_cancelled_failed_and_superseded_builds_never_replace_READY: VERIFIED
      context_receipt_ContentRef_and_significant_ModelCall_provenance_chaining: VERIFIED
      cache_deletion_preserves_source_Artifact_RunMemory_and_rebuildability: VERIFIED
      hostile_instruction_bytes_remain_inert_data: VERIFIED
      raw_QuarantineRef_runtime_dependency: 0
    p2_10_known_limitations:
      - text_extraction_is_exact_UTF8_with_versioned_unicode_fixed_v1_character_chunking; other_media_and_chunkers_require_explicit_adapters
      - vectors_are_durable_SQLite_JSON_and_queried_by_bounded_local_cosine_not_an_external_production_ANN_service
      - model_qualification_used_the_P2_06_REFERENCE_provider; no_reachable_hosted_provider_was_required
      - exact_token_count_is_caller_supplied_with_exact_tokenizer_identity; otherwise_the_receipt_records_an_explicit_unicode_segment_estimate
      - accepted_global_EngineKnowledge_can_be_included_but_the_compiler_does_not_requery_global_promotion_authority; ProjectKnowledge_and_RunMemory_are_durably_revalidated
      - cache_deletion_and_rebuild_are_per_index; global_GC_is_not_implemented
      - fallow_CLI_was_unavailable
    p2_10_schema_changes:
      - retrieval_index_builds
      - retrieval_build_heads
      - retrieval_index_states
      - retrieval_index_state_heads
      - retrieval_active_heads
      - retrieval_chunks
      - retrieval_receipts
      - retrieval_search_claims
      - retrieval_build_cancellations
      - context_manifests
      - context_receipts
      - context_compile_claims
      - append_only_and_immutable_guards_plus_monotonic_fenced_heads
    p2_10_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/context_retrieval.py
      - tests/test_p2_10_context_retrieval.py
    p2_10_remote_path_evidence:
      src_biella_init: "blob c2b0e869e122777ea474cd21fedd51f1e8a6e80b; size 25303; sha256 63d20d51d411884096b7d6577ccc6ec7068d7629986413994aff528d8c8cac39"
      src_biella_context_retrieval: "blob 5c25236e9349923870bbd2f18224bacbadb82c58; size 143802; sha256 cec1daedbd2d8a05c204b52f84cb4055d9ee6c6077911802890433be588eb25d"
      test_p2_10: "blob 93cba1e7118b434135b0ae0dd962002ce6aa5355; size 46588; sha256 316ecd70df78e19db3416aadbe8f633a3638b218c94ecdaaaf4780051ebd5b3b"
    p2_11_status: DURABLY_COMPLETE
    p2_11_source_commit: a0a3109c092ff486b30ccaade86e4bf8a884ce81
    p2_11_result_commit: e29bf2ef8aef14879b54ed35193775573487b527
    p2_11_result_tree: abbea75d558a399a9aed359e32e362adc184c22c
    p2_11_remote_readback: VERIFIED
    p2_11_implementation:
      production_modules_added: 1
      existing_modules_extended: 3
      public_export_bindings_created_or_changed: 24
      focused_pytest_cases: 12
      migrations_added: 0
      durable_state_tables_added: 10
      workspace_surface: Workspace_WorkspaceRef_WorkspaceType_WorkspaceLifecycleState_WorkspaceExecutionPolicy_WorkspaceExecutionPolicyRef_WorkspaceRootGrant_WorkspaceFileSource_WorkspaceRepositorySource_WorkspaceSnapshot_WorkspaceSnapshotRef_CandidateWorkspaceReceipt_and_WorkspaceService
      lifecycle_surface: CREATE_MATERIALIZE_EXECUTE_CAPTURE_PERSIST_RECONSTRUCT_CLEAN_CANCEL_LOST_UNCAPTURED_and_CLEANUP_FAILED
      exact_identity_contract: Project_Task_revision_Run_Graph_revision_Node_NodeExecutionAttempt_fence_exact_base_revision_execution_policy_resource_allocation_candidate_root_and_snapshot_sequence
      materialization_contract: exact_Artifact_or_Repository_base_through_ObjectStorage_Filesystem_and_Git_adapters_into_cleanup_capable_Project_owned_candidate_roots_without_protected_source_mutation
      repository_snapshot_contract: exact_base_HEAD_tree_staged_and_unstaged_binary_diffs_filtered_untracked_manifest_candidate_only_Git_bundle_regular_file_modes_safe_symlink_state_and_ToolCall_provenance
      reconstruction_contract: disposable_local_path_recreated_from_exact_base_plus_content_addressed_snapshot_and_candidate_commit_bundle_with_exact_HEAD_index_worktree_untracked_manifest_and_byte_verification
      policy_contract: Project_root_grants_network_NONE_RESTRICTED_PROJECT_POLICY_allowed_capabilities_ResourceAllocation_secret_refs_secret_mounts_side_effect_boundary_timeout_and_process_limit
      concurrency_contract: per_Workspace_idempotency_claims_and_monotonic_heads_allow_independent_workspaces_without_global_lock
      cancellation_contract: valid_outputs_captured_before_cancel_exact_Run_Node_attempt_fenced_late_results_rejected_and_dispatched_ResourceAllocation_released_CANCELLED
      isolation_contract: canonical_relative_paths_symlink_and_special_object_rejection_cross_Project_scope_denial_cleanup_capable_root_requirement_secret_and_cache_exclusion_and_truthful_network_classification
    p2_11_validation:
      focused_source_pytest: "12 passed; 0 failed; 0 skipped; 91.84s final exact-source run"
      exact_installed_wheel_pytest: "12 passed; 0 failed; 0 skipped; 91.82s; isolated target import verified"
      diagnostic_adapter_regression: "51 passed; 2 recursive build/install qualification wrappers deselected; 0 failed; 0 skipped; pre-final Filesystem Git and P2-11 boundary matrix; final exact source covered by focused and broad gates"
      broad_non_nested_regression: "517 passed; 20 recursive build/install qualification gates deselected; 137 subtests passed; 0 failed; 0 skipped; 602.88s; current installed-wheel qualification passed separately"
      mypy_strict: "89 source/test files; 0 issues"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P2-11 skip, xfail, placeholder, TODO, NotImplemented, and executable-pass hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      public_export_check: "505 unique public export bindings; five required workspace APIs callable"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 bae6c627a27287016ecb20d533f836270e4f1d7520ea8fa53508151d6eeeb195; all 31 packaged biella Python paths exactly matched source bytes"
      remote_required_paths_and_bytes: "GitHub main ref, result commit, tree, five blob IDs, sizes, SHA256 bytes, and exact raw contents independently read back and matched"
      adversarial_review: "PASS for Project and path isolation, protected-root rejection, hostile instruction inertness, raw quarantine absence, provenance chaining, source staleness, idempotency, concurrent workspaces, uncaptured loss, exact snapshot recovery, candidate commits, staged index, safe symlinks, secrets, cancellation, late fencing, and resource release"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; deterministic adversarial tests, strict typing, and manual trust-boundary review used"
    p2_11_kpi:
      workspace_loss_causes_persisted_candidate_loss: 0
      candidate_changes_mutate_protected_source: 0
      ambiguous_base_revision: 0
      cross_project_workspace_access: 0
      direct_tool_execution_bypassing_adapter: 0
      global_single_workspace_lock: 0
    p2_11_reality_classification:
      SQLite_durable_workspace_policy_identity_state_snapshot_receipt_claim_and_ToolCall_evidence: REAL
      Filesystem_object_storage_manifest_file_diff_and_candidate_bundle_content: REAL
      managed_local_Filesystem_Process_and_Git_adapter_execution: REAL_CPU
      local_Git_candidate_commit_bundle_export_verify_restore_and_exact_index_replay: REAL_CPU
      Scheduler_and_ResourceAllocation_reservation_dispatch_cancellation_and_release: REAL_WITH_REFERENCE_OBSERVER_INPUT
      hosted_sandbox_or_external_model_provider: NOT_RUN_NOT_REQUIRED
      fallow_static_review: NOT_RUN_CLI_UNAVAILABLE
    p2_11_qualification:
      Workspace_WorkspaceExecutionPolicy_CandidateWorkspaceReceipt_and_five_required_APIs: VERIFIED
      exact_Project_Task_Run_Graph_Node_attempt_fence_base_policy_and_resource_identity: VERIFIED
      Object_Git_Filesystem_materialization_and_protected_source_immutability: VERIFIED
      adapter_only_runtime_and_ToolCall_accounting_in_active_Workspace_module: VERIFIED
      exact_manifest_changed_ContentRefs_Git_HEAD_tree_staged_unstaged_untracked_bundle_test_Artifact_and_tool_provenance: VERIFIED
      snapshot_delete_restart_reconstruct_and_continue_with_exact_bytes_Git_HEAD_index_worktree_symlink_and_untracked_state: VERIFIED
      uncaptured_local_loss_reported_without_fabrication: VERIFIED
      stale_authoritative_source_preserves_original_exact_base_without_rebase_or_relabel: VERIFIED
      independent_concurrent_workspaces_without_global_lock_or_cross_contamination: VERIFIED
      cancellation_captures_valid_outputs_rejects_late_results_and_releases_exact_allocation: VERIFIED
      secret_mount_cache_credential_path_and_raw_QuarantineRef_snapshot_exclusion: VERIFIED
      hostile_instruction_bytes_remain_inert_data: VERIFIED
      idempotency_and_immutable_monotonic_durable_evidence: VERIFIED
    p2_11_known_limitations:
      - non_repository_Workspaces_reject_symlinks; Repository_symlink_state_is_reconstructed_and_verified_through_exact_Git_diffs
      - candidate_commit_bundles_store_only_objects_after_the_exact_base_and_require_the_candidate_HEAD_to_descend_from_that_registered_base
      - execution_qualification_used_real_local_CPU_Filesystem_Process_Git_SQLite_and_Scheduler_paths; no_hosted_sandbox_or_model_provider_was_required
      - resource_measurement_used_the_accepted_FakeResourceObserver_reference_input_while_reservation_dispatch_cancellation_and_release_used_the_real_durable_scheduler
      - rebuildable_caches_and_secret_mounts_are_intentionally_absent_from_snapshots_and_must_be_rematerialized_by_their_own_authoritative_systems
      - fallow_CLI_was_unavailable
    p2_11_schema_changes:
      - workspace_policies
      - workspace_policy_claims
      - workspace_identities
      - workspace_create_claims
      - workspace_states
      - workspace_state_heads
      - workspace_operation_claims
      - workspace_snapshots
      - workspace_receipts
      - workspace_tool_evidence
      - immutable_policy_identity_snapshot_receipt_and_tool_evidence_guards_plus_monotonic_fenced_state_heads
    p2_11_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/filesystem.py
      - src/biella/git_adapter.py
      - src/biella/workspace.py
      - tests/test_p2_11_candidate_workspace.py
    p2_11_remote_path_evidence:
      src_biella_init: "blob fdf296fc09b0712c5cf993dafb72988f4df30a20; size 26628; sha256 d4933b18eb0385de8a7552fe1a9b97acb72565d8ac09a6993fa7b4ac7ceb225d"
      src_biella_filesystem: "blob 54727ea84f2e0dc964e9c15ffc7a242eca307d79; size 85532; sha256 695c6172d55cf8e76ce3e907e191011426f088e32daa6a5e23afb70b7f098761"
      src_biella_git_adapter: "blob 7d8c089003a3a9b8f3e872bfa426a58e524f0954; size 137358; sha256 d16ad337044a1cfb86b881183161cdb84d0ea5ed2faeb88696b03b6a66d26c00"
      src_biella_workspace: "blob f749af53be89eaadae8742158b50e17bba29221b; size 128508; sha256 092464c6432dc45a3dc67777746652a24b1fb7067f99bf28e7fe6e1782b356dc"
      test_p2_11: "blob 42d8214de42b34235bc20c3b4bb9fe4708c5f30c; size 35676; sha256 3f6c56a344cc3fe4c727d739aa2395b50f2e1df295b584c081266ee40016dfce"
    p2_12_status: DURABLY_COMPLETE
    p2_12_source_commit: 08cedd9d1c110418bb32aa22035a081f7a6f8fd9
    p2_12_result_commit: 575ff0683677234f4a8ff41e3eb703d4ea31112f
    p2_12_result_tree: 758f7a1e2bc67d7925307d5146fcdf4b6f52b046
    p2_12_remote_readback: VERIFIED
    p2_12_implementation:
      production_modules_added: 1
      existing_modules_extended: 2
      public_export_bindings_created_or_changed: 22
      focused_pytest_cases: 15
      migrations_added: 0
      durable_state_tables_added: 8
      validation_surface: ValidationPlan_ValidationResult_ValidationAggregate_EvaluationResult_ProjectValidationCriteria_ValidationSubject_ValidationCheck_MetricMeasurement_CompositeMetric_and_ValidationService
      verdict_surface: PASS_FAIL_INCONCLUSIVE_ERROR_with_CURRENT_or_HISTORICAL_evidence_state
      exact_identity_contract: Project_Task_revision_digest_Run_Graph_revision_record_Node_NodeExecutionAttempt_fence_exact_subject_refs_digests_plan_digest_validator_capability_implementation_runtime_dimensions_and_call_ledger_refs
      task_derived_contract: output_schema_Artifact_existence_digest_Task_evidence_acceptance_constraints_and_Project_criteria_compile_to_explicit_required_or_optional_checks_with_ALL_REQUIRED_PASS
      minimality_contract: schema_only_output_Task_compiles_only_schema_Artifact_existence_and_digest_without_invented_critic_model_or_repair_loop
      specialized_evidence_contract: build_runtime_and_Artifact_PASS_require_exact_durable_Artifact_evidence_and_model_or_tool_Artifact_evidence_must_be_exact_call_output
      independence_contract: requested_dimensions_are_proved_against_all_subject_producer_dimensions_and_are_not_enforced_when_unrequested
      current_authority_contract: exact_Task_Graph_active_head_Node_attempt_and_fence_are_revalidated_and_superseded_plan_results_remain_historical_non_accepting_evidence
      call_ledger_contract: tool_and_model_validators_require_exact_terminal_CallLedger_identity_and_provider_neutral_execution_dimensions; outages remain_ERROR
      evaluation_contract: explicit_named_finite_metrics_units_definitions_measurement_sources_and_visible_composite_formula_components_weights_score_with_current_attempt_authority
      concurrency_contract: independent_check_results_may_persist_concurrently_without_global_validator_lock_and_conflicting_current_claims_fail_closed
      isolation_contract: exact_Project_scope_for_plans_subjects_criteria_evidence_results_aggregates_evaluations_and_call_ledger_refs
    p2_12_validation:
      focused_source_pytest: "15 P2-12 cases plus exact P0 neutrality regression passed; 0 failed; 0 skipped; 19.46s final exact-source run"
      exact_installed_wheel_pytest: "15 passed; 0 failed; 0 skipped; 17.12s; isolated target import verified"
      diagnostic_call_workspace_validation_regression: "41 passed; 1 recursive predecessor build/install gate deselected; 4 subtests passed; 0 failed; 0 skipped; 114.25s"
      broad_non_nested_regression: "532 passed; 20 exact recursive build/install qualification gates deselected; 137 subtests passed; 0 failed; 0 skipped; 619.87s final exact-source rerun"
      mypy_strict: "91 source/test files; 0 issues"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P2-12 skip, xfail, placeholder, TODO, FIXME, NotImplemented, and executable-pass hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      public_export_check: "527 unique public export bindings; five required validation/evaluation interfaces callable"
      active_kernel_neutrality_regression: "PASS after provider-neutral CallLedger execution-dimension boundary; domain/provider coupling identifiers outside CallLedger accounting: 0"
      local_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; sha256 48959ea6411e3309ef020e3f4807b5e992c7e4def3969a0349781c835353a96d; all 32 packaged biella Python paths exactly matched source bytes"
      remote_required_paths_and_bytes: "GitHub main ref, result commit, tree, four blob IDs, sizes, SHA256 bytes, and exact raw contents independently read back and matched"
      adversarial_review: "PASS for minimal validation, explicit required/optional classification, hostile instruction inertness, build Artifact proof, runtime non-substitution, requested independence, provider outage ERROR, stale historical evidence, cross-Project denial, concurrent checks, visual/performance dimensions, exact metric sources and composites, immutable ledgers, call-state staleness, current evaluation authority, candidate Workspace integration, and idempotency"
      fallow_review: "NOT_RUN; fallow CLI unavailable on host; deterministic adversarial tests, strict typing, active-kernel neutrality, and manual trust-boundary review used"
    p2_12_kpi:
      tasks_forced_through_unrequired_validation: 0
      required_validation_skipped: 0
      validator_transport_error_marked_PASS: 0
      stale_validation_accepted: 0
      mandatory_global_validator_hierarchy: 0
      opaque_composite_scores: 0
      cross_project_validation_evidence_accepted: 0
      build_or_runtime_PASS_without_required_Artifact: 0
    p2_12_reality_classification:
      SQLite_durable_validation_plan_result_aggregate_evaluation_claim_and_head_evidence: REAL
      exact_Task_Graph_Node_attempt_fence_Artifact_Workspace_and_CallLedger_integration: REAL
      concurrent_result_persistence_and_deterministic_aggregation: REAL_CPU
      build_runtime_visual_performance_security_and_provenance_validator_semantics: REFERENCE_CAPABILITY_DRIVEN_WITH_REAL_DURABLE_EVIDENCE_GATES
      managed_model_provider_outage_execution: REFERENCE_LEDGER_FAILURE_NOT_EXTERNAL_PROVIDER_CALL
      exact_wheel_build_install_import_and_focused_execution: REAL_CPU
      fallow_static_review: NOT_RUN_CLI_UNAVAILABLE
    p2_12_qualification:
      ValidationPlan_ValidationResult_EvaluationResult_compiler_and_aggregator_interfaces: VERIFIED
      exact_subject_Task_Run_Graph_Node_attempt_fence_and_Project_criteria_binding: VERIFIED
      minimal_schema_Artifact_digest_plan_without_invented_critic: VERIFIED
      required_optional_classification_and_ALL_REQUIRED_PASS_aggregation: VERIFIED
      PASS_FAIL_INCONCLUSIVE_ERROR_are_distinct_and_ERROR_precedence_is_deterministic: VERIFIED
      build_missing_Artifact_never_PASS_and_runtime_requirement_not_substituted: VERIFIED
      requested_independence_only_with_explicit_producer_and_validator_dimensions: VERIFIED
      model_and_tool_validation_ledger_identity_provenance_and_terminal_state_staleness: VERIFIED
      stale_plan_results_historical_and_never_current_acceptance: VERIFIED
      explicit_quality_performance_cost_reliability_metrics_and_visible_composite: VERIFIED
      visual_performance_and_optional_failure_semantics: VERIFIED
      cross_Project_subject_criteria_and_evidence_isolation: VERIFIED
      candidate_Workspace_receipt_to_validation_end_to_end_P2_flow: VERIFIED
      hostile_Task_objective_remains_inert_data: VERIFIED
      idempotency_concurrency_immutability_restart_readback_and_tamper_guards: VERIFIED
    p2_12_known_limitations:
      - validator_capabilities_are_provider_neutral_registration_and_evidence_primitives; domain_specific_validator_implementations_remain_pack_or_Project_data
      - managed_provider_outage_behavior_was_verified_with_real_durable_CallLedger_failure_evidence_but_no_external_provider_call_was_required
      - visual_performance_security_build_and_runtime_execution_engines_remain_replaceable_existing_adapters_or_future_pack_registrations_not_kernel_specializations
      - ContentRef_subject_binding_proves_the_exact_self_describing_content_identity; byte_availability_must_be_proved_by_the_authoritative_object_storage_Artifact_or_adapter_when_the_Task_requires_it
      - fallow_CLI_was_unavailable
    p2_12_schema_changes:
      - validation_plans
      - validation_plan_claims
      - validation_plan_heads
      - validation_results
      - validation_result_claims
      - validation_aggregates
      - evaluation_results
      - evaluation_claims
      - immutable_plan_result_aggregate_evaluation_and_claim_guards_plus_monotonic_plan_heads
    p2_12_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/call_ledger.py
      - src/biella/validation.py
      - tests/test_p2_12_validation.py
    p2_12_remote_path_evidence:
      src_biella_init: "blob 6594f48f9809329085c1d9bd5f92ef0df5dc7637; size 27800; sha256 338383802f3e614b8fd0cb78f6b8ceee3bc078b3806f19f2bc84239adca20409"
      src_biella_call_ledger: "blob e25dbe365e5b010965a69a47e67b0a5099f5de4c; size 98550; sha256 4ed513fdfec2e1679898121e5b464d7b15a6d0ab51b92da0b6650f115b0a2be4"
      src_biella_validation: "blob 2ee1b214fe8a654f0a37edce4181722bdd138741; size 82086; sha256 f53bc467fe469336406c29d08b4e7c84e65b13ae9076837dc51eeb7ea131f721"
      test_p2_12: "blob 6e25135f860dd49397df8dff8ab730ea5d458f6b; size 34050; sha256 54e36443bf32420555c12bb234961c6411f65caccec2b06475bb8e5253937d98"
    p3_01_status: DURABLY_COMPLETE
    p3_01_source_commit: 1096a2787077cc32386f5e2e9d84606899747b04
    p3_01_preservation_commit: 26acd7bc46bc5ddf7cc2eaa58dcc2cc30ba9e078
    p3_01_result_commit: d1c578a467fb555835458c8ef42eb8cf31cfbcb4
    p3_01_result_tree: 7ba19f32a3980f004f56f3c869cda4b0a30fedd6
    p3_01_remote_readback: VERIFIED
    p3_01_implementation:
      production_modules_added: 2
      existing_modules_extended: 5
      focused_pytest_cases: 9
      migrations_added: 0
      durable_state_tables_added: 2
      pack_interface_surface: ProductionPackRef_GraphRecipeStepRegistration_GraphRecipeRegistration_ValidatorRegistration_ProductionPack_and_ProductionPackRegistry
      software_capability_surface: software.inspect_search_architecture_engineer_modify_debug_refactor_test_build_run_profile_package_and_validate
      registry_contract: immutable_bounded_provider_neutral_descriptor_with_atomic_Capability_pack_and_idempotency_registration
      recipe_contract: optional_pack_data_over_existing_Graph_Capability_adapter_and_resource_interfaces_without_fixed_plan_coder_critic_validator_hierarchy
      exact_source_contract: two_real_Project_scoped_Git_repositories_exact_base_commit_tree_unrelated_dirty_source_preservation_focused_retrieval_and_bounded_candidate_diff
      build_runtime_contract: controlled_red_green_unittest_real_build_output_Artifact_real_runtime_output_and_exact_candidate_commit_tree
      provenance_contract: one_same_required_role_exact_plan_subject_Artifact_must_chain_to_the_exact_candidate_Workspace_snapshot_Artifact
      recovery_contract: captured_candidate_failed_and_passing_tests_build_output_runtime_output_file_modes_and_repository_identity_survive_service_restart_and_reconstruction
      isolation_contract: repository_Workspace_context_configuration_and_evidence_remain_exact_Project_scoped
      neutrality_contract: no_SoftwareTask_SoftwareRun_CodeAgentManager_global_software_worker_language_framework_provider_or_hardware_kernel_default
    p3_01_validation:
      focused_contract_pytest: "8 passed; 1 real-repository E2E deselected for separate execution; 0 failed; 0 skipped; 0.40s"
      real_repository_e2e_pytest: "1 passed; 0 failed; 0 skipped; 91.01s"
      affected_filesystem_workspace_validation_regression: "53 passed; 1 recursive exact-wheel gate deselected; 0 failed; 0 skipped; 131.20s"
      broad_non_nested_regression: "542 passed; 19 exact recursive build/install qualification gates deselected; 137 subtests passed; 0 failed; 0 skipped; 734.64s"
      exact_wheel_install_restart_gate: "1 passed; 0 failed; 0 skipped; 2.67s; exact top-level source-to-wheel path and byte parity plus isolated install/restart"
      mypy_strict: "94 source/test files; 0 issues"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P3-01 skip, xfail, placeholder, TODO, FIXME, and NotImplemented hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      independent_review: "READY; no Critical or Important findings after atomicity, exact provenance, receipt integrity, mode recovery, adapter binding, focused context, and replay hardening"
      remote_required_paths_and_bytes: "GitHub main ref, result commit, tree, eight required blob IDs, sizes, SHA256 bytes, exact raw contents, and two obsolete path absences independently read back and matched"
    p3_01_kpi:
      source_changes_without_exact_base: 0
      unrelated_source_changes: 0
      tests_claimed_PASS_without_execution: 0
      build_claims_without_output: 0
      candidate_work_lost_after_recoverable_failure: 0
      domain_specific_kernel_changes: 0
    p3_01_reality_classification:
      SQLite_ProductionPack_Capability_and_idempotency_registry: REAL
      exact_two_Project_Git_repository_inspection_and_scope_denial: REAL_CPU
      focused_Retrieval_Context_compilation_with_ReferenceModelAdapter: REFERENCE_MODEL_WITH_REAL_CPU_DURABLE_EVIDENCE
      controlled_failing_test_repair_passing_test_build_runtime_and_candidate_commit_tree: REAL_CPU
      Workspace_capture_service_restart_reconstruction_and_file_mode_recovery: REAL_CPU
      exact_wheel_build_install_import_restart_and_byte_parity: REAL_CPU
      managed_model_or_hosting_provider_execution: NOT_RUN_NOT_REQUIRED
      fallow_static_review: NOT_RUN_CLI_UNAVAILABLE
    p3_01_qualification:
      provider_neutral_ProductionPack_descriptor_and_exact_software_capabilities: VERIFIED
      graph_recipes_validators_artifact_roles_adapter_bindings_and_resource_profiles_as_pack_data: VERIFIED
      atomic_registration_idempotency_concurrency_immutability_restart_and_corruption_guards: VERIFIED
      exact_base_commit_tree_unrelated_dirty_work_and_task_scoped_candidate_diff: VERIFIED
      focused_source_retrieval_and_context_without_full_repository_dump: VERIFIED
      controlled_red_green_test_build_output_runtime_and_exact_candidate_identity: VERIFIED
      build_exit_zero_without_required_output_never_accepted: VERIFIED
      exact_candidate_provenance_on_same_required_role_plan_subject_Artifact: VERIFIED
      Workspace_receipt_snapshot_hash_identity_and_Artifact_role_binding: VERIFIED
      legacy_replay_compatibility_and_exact_file_mode_recovery: VERIFIED
      cross_Project_repository_Workspace_context_and_configuration_isolation: VERIFIED
      captured_candidate_test_build_and_runtime_evidence_survives_restart: VERIFIED
      domain_specific_kernel_types_or_defaults: ZERO
    p3_01_known_limitations:
      - the_real_acceptance_application_used_Python_unittest_and_a_deterministic_local_build_script; language_and_framework_specific_implementations_remain_pack_or_Project_registrations
      - the_focused_Context_and_Retrieval_flow_used_the_provider_neutral_ReferenceModelAdapter; no_managed_model_provider_call_was_required
      - no_external_deploy_package_registry_or_hosting_action_was_required_or_authorized
      - fallow_CLI_was_unavailable; independent_adversarial_review_and_deterministic_graph_contract_tests_were_used
      - immutable_history_contains_the_automatic_preservation_commit_followed_by_the_reviewed_finalization_commit; no_history_rewrite_was_performed
    p3_01_schema_changes:
      - production_packs
      - production_pack_idempotency
      - immutable_pack_and_idempotency_guards
      - caller_owned_Capability_registry_transaction_path
      - exact_Workspace_receipt_snapshot_and_build_Artifact_provenance_validation
      - explicit_filesystem_write_mode_request_schema_v2_with_legacy_schema_v1_replay_compatibility
    p3_01_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/capability.py
      - src/biella/filesystem.py
      - src/biella/production_pack.py
      - src/biella/software_pack.py
      - src/biella/validation.py
      - src/biella/workspace.py
      - tests/test_p3_01_software_pack.py
    p3_01_remote_path_evidence:
      src_biella_init: "blob 6aafc178b09a5d7d3c58a6365637081154fa7866; size 28575; sha256 4582d2c94eb4978182c53c10a2b1d28f6f0dabcac73b2931fcb381b5c70e873e"
      src_biella_capability: "blob 8d734c96be7a25dd7735fb397317c1d63939605e; size 31688; sha256 458e4385a162c5ca8574dad0566fdc71e099fb28377b74cef0fc5d730e38b83c"
      src_biella_filesystem: "blob 079a9952634ffbb2b5004d54f00505b832cb2604; size 86583; sha256 65bbbf623d5315ca3ad22ee03963a6e555d4e47be9a738b2bf81f1296cfb38de"
      src_biella_production_pack: "blob 991e57c2d49493e5db478662f8a07bf41d41f026; size 31348; sha256 3510c0536c4bf68c57bdd77a2e5d54f98534fbd1f4d50a18a6166dd250b50a59"
      src_biella_software_pack: "blob aa94ff78161fc42a425497700da08963e20fc392; size 8224; sha256 c38e67bcb48846f1728ce4346beed5cb2a181e8c76e390f660e75f3618e7a078"
      src_biella_validation: "blob 74c001356cc9d2bb1ad34b2be3e6096dbf296763; size 90048; sha256 8240037ae40b0ade8f5e6d8c134d53206214c9cc4c0c45a40f2ca76f5e474f52"
      src_biella_workspace: "blob 3ad68478a0d3f3c83ccb7195b4c49d9c90fbd8ce; size 128738; sha256 0b9da6b7fa147e0028029b483712763099c7786d5b6aa3e7a1c8bedd319cb244"
      test_p3_01: "blob f6cf8164b028ab41e47805a914e135ebb690448e; size 46345; sha256 597ea138796736ef5f22659ff2243fc703738c40676f7f28ac16bbad51afc7ea"
      obsolete_src_biella_packs_init: ABSENT
      obsolete_src_biella_packs_software: ABSENT
    p3_02_status: DURABLY_COMPLETE
    p3_02_source_commit: 360170ca624f385f1d620ecb25781963b03dcdd4
    p3_02_result_commit: dfe1adc8b198841b17cdb75266c42b318b1db2ef
    p3_02_result_tree: dceceff0c80ed5128264b7c5d7ce2a0fe2ac2c1e
    p3_02_remote_readback: VERIFIED
    p3_02_implementation:
      production_modules_added: 1
      existing_modules_extended: 2
      focused_pytest_cases: 5
      migrations_added: 0
      durable_state_tables_added: 0
      web_capability_surface: web_inspect_frontend_backend_fullstack_component_route_api_database_integrate_build_run_test_browser_validate_performance_accessibility_and_package
      pack_descriptor_contract: 15_provider_neutral_capabilities_3_graph_recipes_7_validators_11_distinct_artifact_roles_15_exact_adapter_bindings_and_15_resource_profiles
      framework_neutrality_contract: framework_design_system_database_runtime_hosting_brand_and_visual_rules_remain_Project_or_Task_data
      exact_source_contract: two_real_Project_scoped_Git_repositories_with_distinct_configs_exact_base_commit_tree_bounded_candidate_changes_and_cross_Project_denial
      real_application_contract: controlled_red_green_repair_deterministic_build_runtime_crash_and_restart_live_HTTP_real_pinned_Chromium_DOM_interaction_screenshot_and_package
      http_provenance_contract: exact_http_execution_receipt_manifests_chain_into_runtime_http_validation_and_package_evidence
      browser_provenance_contract: exact_browser_session_generation_navigation_interaction_DOM_and_screenshot_receipts_chain_to_the_live_candidate
      recovery_contract: provider_loss_records_generation_1_loss_reopens_generation_2_and_preserves_source_test_build_runtime_HTTP_browser_and_package_evidence
      isolation_contract: repository_Workspace_runtime_port_HTTP_destination_browser_session_validation_and_package_evidence_remain_exact_Project_scoped
      hostile_instruction_contract: repository_embedded_instructions_remain_inert_data_and_never_override_Task_authority
    p3_02_validation:
      focused_contract_and_real_e2e_pytest: "5 passed; 0 failed; 0 skipped; 104.18s"
      final_real_e2e_after_http_receipt_hardening: "1 passed; 0 failed; 0 skipped; 103.59s"
      affected_contract_regression: "75 passed; 1 recursive exact-wheel gate deselected; 31 subtests passed; 0 failed; 0 skipped; 3.13s"
      broad_non_nested_regression: "547 passed; 19 exact recursive build/install qualification gates deselected; 137 subtests passed; 0 failed; 0 skipped; 838.56s"
      exact_wheel_install_restart_gate: "1 passed; 0 failed; 0 skipped; 3.28s; exact source-to-wheel install and restart"
      mypy_strict: "99 source/test files; 0 issues"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P3-02 skip, xfail, placeholder, TODO, FIXME, and NotImplemented hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      independent_review: "READY; no Critical or Important findings after exact HTTP execution receipt provenance hardening"
      remote_required_paths_and_bytes: "GitHub main ref, result commit, tree, nine required blob IDs, sizes, SHA256 bytes, exact raw contents, and obsolete web-pack path absence independently read back and matched"
    p3_02_kpi:
      web_framework_hardcoded_in_kernel: 0
      screenshot_only_validation: 0
      build_claimed_live_without_runtime: 0
      global_web_visual_or_performance_defaults: 0
      domain_specific_kernel_changes: 0
    p3_02_reality_classification:
      SQLite_ProductionPack_Capability_validation_Artifact_and_idempotency_registration: REAL
      exact_two_Project_Git_repository_inspection_candidate_changes_and_scope_denial: REAL_CPU
      red_green_test_build_package_and_managed_process_runtime_crash_restart: REAL_CPU
      live_HTTP_transport_response_and_execution_receipt_provenance: REAL_CPU_NETWORK_LOOPBACK
      pinned_Selenium_Chromium_DOM_interaction_screenshot_and_provider_loss_recovery: REAL_CONTAINER_BROWSER
      application_error_and_network_diagnostics: REAL_APPLICATION_INSTRUMENTATION
      native_browser_console_log_capture: NOT_AVAILABLE_IN_ACCEPTED_BROWSER_CONTRACT
      PostgreSQL_execution: NOT_RUN_NOT_REQUIRED_BY_SELECTED_PROJECTS
      external_deployment_or_managed_hosting: NOT_RUN_NOT_REQUIRED
    p3_02_qualification:
      provider_neutral_web_ProductionPack_and_exact_15_capability_registrations: VERIFIED
      graph_recipes_validators_artifact_roles_adapter_bindings_and_resource_profiles_as_pack_data: VERIFIED
      exact_framework_runtime_package_manager_build_routes_tests_environment_and_entrypoint_discovery: VERIFIED
      controlled_red_green_repair_test_build_start_HTTP_browser_and_package_flow: VERIFIED
      build_runtime_HTTP_browser_performance_accessibility_and_package_evidence_remain_distinct: VERIFIED
      exact_live_candidate_runtime_HTTP_and_browser_provenance_chaining: VERIFIED
      runtime_crash_and_browser_provider_loss_preserve_verified_source_test_build_and_package_evidence: VERIFIED
      cross_Project_repository_Workspace_runtime_destination_session_validation_and_package_isolation: VERIFIED
      hostile_repository_instruction_inertness: VERIFIED
      idempotency_conflict_and_restart_readback: VERIFIED
      framework_design_database_runtime_hosting_provider_and_domain_specific_kernel_defaults: ZERO
      raw_QuarantineRef_dependency_in_active_runtime: ZERO
    p3_02_known_limitations:
      - the_accepted_browser_adapter_has_no_native_console_log_API; early_page_error_and_unhandled_rejection_instrumentation_was_real_application_telemetry_not_native_console_capture
      - PostgreSQL_was_not_executed_because_the_selected_exact_Project_configs_did_not_use_a_database; the_provider_neutral_database_integration_binding_remains_registered
      - no_external_deployment_or_managed_hosting_action_was_required_or_authorized
      - nineteen_recursive_exact_build_install_tests_were_excluded_from_the_non_nested_regression_and_covered_by_the_separate_exact_wheel_install_restart_gate
    p3_02_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/capability.py
      - src/biella/web_pack.py
      - tests/test_p3_02_web_pack.py
      - tests/fixtures/p3_02_web_app/.gitignore
      - tests/fixtures/p3_02_web_app/build.py
      - tests/fixtures/p3_02_web_app/candidate_checks.py
      - tests/fixtures/p3_02_web_app/server.py
      - tests/fixtures/p3_02_web_app/web-project.json
    p3_02_remote_path_evidence:
      src_biella_init: "blob 1fca57153be6259399289c8b250816fb7f1265b6; size 28644; sha256 d8158ac98a56a0640c7726a9ab98eaa94bee99d42ec6329b7856af3084f3dbb8"
      src_biella_capability: "blob 85c006c3b7c443f704f266d4a5e1248168841dd1; size 31690; sha256 c2ca30af9d1e2ef043c1c143acd8ff23845d51a36d805df1cea89fadf3aba080"
      src_biella_web_pack: "blob 9f32c56f8a2749adf56fa05abed0c9f0660bde23; size 11323; sha256 f93c9ae581fae9920b438e0007bf58b501c4d3460214851274a3a8d8641b1bcf"
      test_p3_02: "blob 9cf14bdf9eea6733632fda02a7846b7b2bd38ade; size 77311; sha256 57ae0738084621fa6b2581a3ffd24cd665ce92b69cfe508ca93d02c24d92b8c6"
      fixture_gitignore: "blob 1be5bdb4c984f43e498ece5befabcf39edc9c10b; size 19; sha256 bf7224daa29be47cef87a50b0351d18e729d129be606faa8e4718116d6e51d87"
      fixture_build: "blob e229d1e7d22845b8895f771a673b9387ebec667e; size 1131; sha256 1bc29bc2e1bd8e992f4aaa49fde18a59f37df89380ec5b7d12dcbdddadf64d5e"
      fixture_candidate_checks: "blob 03604278c44961a0be75c9aeb9242cb500c197ab; size 233; sha256 16e16096c6603c6a0004b7db07fe953ed4d499ff2040415eae42a7743c0ff5b8"
      fixture_server: "blob 1666ce6ffe88f72ea425ed70ea49289f6a6b290d; size 3904; sha256 d4a0057938b27c67752d7cab073ff27d3079905edd8b6725f6a47d5e91d2ec67"
      fixture_web_project: "blob e9a771436db00142b986b6cf6520c1f35e48be8e; size 275; sha256 a5a354407af99b34c78c95927187841285e76ecd378787da05920217c5111afc"
      obsolete_src_biella_packs_web: ABSENT
    p3_03_status: DURABLY_COMPLETE
    p3_03_source_commit: ff77e10c95b9b84e29fe3dcc83e4538ec8328b04
    p3_03_result_commit: f665445e1771b98f34e1d82746c5d4a9686e3138
    p3_03_result_tree: 6a8c47f70fcd5df900381e05a93169a9aed25205
    p3_03_remote_readback: VERIFIED
    p3_03_implementation:
      production_modules_added: 2
      existing_modules_extended: 1
      focused_pytest_cases: 14
      migrations_added: 0
      durable_state_tables_added: 9
      game_capability_surface: game_inspect_import_modify_build_run_test_profile_capture_export_package_and_validate
      adapter_contract: GameEngineAdapter_with_detectProject_inspectProject_importProject_build_run_test_profile_capture_export_and_describeRuntime_semantics
      implementation_contract: IsolatedRuntimeGameEngineAdapter_REAL_and_ReferenceGameEngineAdapter_REFERENCE_share_the_same_provider_neutral_Task_Graph_Capability_and_Artifact_contract
      identity_contract: exact_Project_RepositoryRef_source_commit_tree_Workspace_snapshot_engine_executable_version_args_project_config_entry_scene_target_export_config_toolchain_runtime_cache_resource_and_output_identity
      candidate_contract: live_candidate_bytes_modes_and_exact_snapshot_identity_fail_closed_while_engine_generated_cache_and_output_paths_remain_rebuildable
      execution_contract: direct_REAL_engine_detection_import_build_native_test_run_profile_capture_export_and_deterministic_package_validation_with_build_never_substituting_for_runtime_proof
      provenance_contract: exact_candidate_build_asset_runtime_receipt_raw_output_domain_output_package_validation_and_aggregate_Artifact_chaining
      atomicity_contract: all_domain_outputs_publications_success_result_and_verified_detection_or_build_index_commit_in_one_live_Node_and_Run_fenced_transaction
      recovery_contract: semantic_detection_and_build_identity_excludes_only_worker_local_control_root_and_ResourceAllocation_while_preserving_exact_engine_candidate_runtime_output_and_publication_identity
      asset_seam_contract: exact_3D_character_animation_environment_image_audio_and_VFX_Artifact_refs_without_implementing_downstream_packs
      isolation_contract: Project_Repository_Workspace_runtime_Artifact_validation_cache_and_reference_evidence_remain_exact_Project_scoped
      hostile_instruction_contract: repository_embedded_hostile_instructions_remain_inert_bytes_and_never_override_Task_Node_Run_or_adapter_authority
    p3_03_validation:
      focused_pack_validation_and_prior_pack_regression: "27 passed; 0 failed; 0 skipped; 349.86s"
      final_byte_authoritative_real_Godot_e2e: "1 passed; 0 failed; 0 skipped; 431.29s; exact source, test, and five normalized fixture SHA256 values matched before and after; zero residual biella.runtime containers"
      affected_P0_contract_regression: "159 passed; 82 subtests passed; 0 failed; 0 skipped; 16.15s"
      affected_call_resource_scheduler_workspace_validation_regression: "69 passed; 4 recursive predecessor gates deselected; 4 subtests passed; 0 failed; 0 skipped; 129.34s"
      affected_filesystem_process_git_runtime_regression: "63 passed; 4 recursive exact-wheel gates deselected; 0 failed; 0 skipped; 290.23s; zero residual biella.runtime containers"
      exact_wheel_build: "biella_engine-0.1.0-py3-none-any.whl; size 502488; sha256 16c1d4652cc4145c1bc9b3cd4e77e3b98ed4b152a5303b5e1bed57333f521e71; required P3-03 paths present"
      installed_wheel_restart_gate: "isolated install; pip check PASS; two separate interpreter processes verified exact ten-method adapter surface, 11 capabilities, 11 validators, and zero active-runtime QuarantineRef"
      mypy_strict: "104 source/test files; 0 issues"
      compileall: PASS
      diff_check: PASS
      test_quality_scan: "P3-03 skip, xfail, placeholder, TODO, FIXME, and NotImplemented hits: 0"
      active_runtime_quarantine_scan: "raw QuarantineRef dependencies outside migration: 0"
      independent_review: "READY at exact game_engine sha256 bcf8b7a0d419d4b967234ebe3c573e8beb3a59a5b739bc6723fe45f43429a094 and game_pack sha256 2ec6d0b65b477e5ab9a0830d218f08647d385d742d8bbea7562648c4d0710280; no Critical or Important findings"
      remote_required_paths_and_bytes: "GitHub main ref, result commit, tree, 12 required blob IDs, sizes, SHA256 bytes, and exact raw contents independently read back and matched"
    p3_03_kpi:
      game_engine_hardcoded_in_kernel: 0
      build_claimed_playable_without_run: 0
      engine_cache_used_as_only_authority: 0
      global_game_performance_threshold: 0
      domain_specific_kernel_changes: 0
    p3_03_reality_classification:
      SQLite_ProductionPack_Capability_game_operation_detection_build_description_publication_and_idempotency_ledgers: REAL
      exact_Git_Repository_Workspace_candidate_snapshot_and_live_byte_mode_verification: REAL_CPU
      pinned_barichello_Godot_CI_image_and_Godot_4_3_detection_import_build_test_run_profile_capture_export: REAL_CPU_CONTAINER
      runtime_crash_cache_deletion_reimport_and_worker_replacement_detection_build_reuse: REAL_CPU_CONTAINER
      deterministic_ZIP_package_and_ValidationService_role_provenance_aggregates: REAL_CPU
      second_engine_semantic_contract: REFERENCE
      seven_downstream_asset_pack_seams: REAL_ARTIFACT_CONTRACT_WITHOUT_DOWNSTREAM_PACK_IMPLEMENTATION
      GPU_or_interactive_GUI_engine_execution: NOT_RUN_NOT_REQUIRED_ON_CURRENT_CPU_HEADLESS_PROJECT
      Unity_or_Unreal_execution: NOT_RUN_NOT_REQUIRED_SECOND_IMPLEMENTATION_PROVED_BY_REFERENCE_ADAPTER
      external_publish_or_managed_provider_execution: NOT_RUN_NOT_REQUIRED
    p3_03_qualification:
      provider_neutral_game_ProductionPack_and_exact_11_capability_registrations: VERIFIED
      exact_ten_method_GameEngineAdapter_and_REAL_REFERENCE_implementations: VERIFIED
      exact_source_engine_version_config_scene_target_export_toolchain_runtime_cache_resource_and_output_identity: VERIFIED
      direct_engine_detection_exact_version_line_and_runtime_backend_evidence: VERIFIED
      isolated_candidate_inspection_import_build_native_test_run_profile_capture_export_and_package: VERIFIED
      build_runtime_test_profile_capture_export_and_validation_evidence_remain_distinct: VERIFIED
      missing_output_forbidden_diagnostic_and_build_without_runtime_fail_closed: VERIFIED
      cache_deletion_rebuilds_without_source_loss_or_cache_authority: VERIFIED
      semantic_build_and_detection_adoption_across_changed_control_root_ResourceAllocation_and_Node_fence_without_reexecution: VERIFIED
      multi_output_publication_result_and_verified_index_atomicity: VERIFIED
      exact_candidate_build_asset_runtime_output_package_and_validation_provenance_chaining: VERIFIED
      cross_Project_repository_Workspace_runtime_Artifact_reference_and_validation_isolation: VERIFIED
      hostile_repository_instruction_inertness: VERIFIED
      exact_idempotent_replay_changed_semantics_conflict_and_same_key_inflight_exclusion: VERIFIED
      raw_QuarantineRef_dependency_in_active_runtime: ZERO
      Godot_Unity_Unreal_or_other_engine_kernel_types_defaults: ZERO
    p3_03_known_limitations:
      - the_REAL_adapter_was_qualified_with_Godot_4_3_headless_on_CPU_in_a_pinned_container; GPU_and_interactive_GUI_paths_were_not_required
      - Unity_and_Unreal_were_not_available_or_required; the_second_implementation_was_the_explicit_REFERENCE_adapter_and_never_claimed_runtime_observation
      - no_external_game_publish_store_or_managed_provider_action_was_required_or_authorized
      - eight_recursive_predecessor_build_install_gates_were_excluded_from_affected_regression_groups_and_replaced_by_the_final_exact_wheel_build_install_pip_check_and_two_process_restart_gate
      - fallow_CLI_was_unavailable; independent_graph_grounded_manual_review_and_executable_transaction_recovery_regressions_were_used
    p3_03_schema_changes:
      - game_engine_operation_claims
      - game_engine_operation_results
      - game_engine_operation_inflight
      - game_engine_verified_builds
      - game_engine_verified_detections
      - game_engine_runtime_description_claims
      - game_engine_runtime_descriptions
      - game_engine_runtime_description_inflight
      - game_engine_output_publications
      - immutable_claim_result_verified_build_verified_detection_runtime_description_and_output_publication_guards
    p3_03_required_remote_paths:
      - src/biella/__init__.py
      - src/biella/game_engine.py
      - src/biella/game_pack.py
      - tests/fixtures/p3_03_game_project/.gitignore
      - tests/fixtures/p3_03_game_project/export_presets.cfg
      - tests/fixtures/p3_03_game_project/main.gd
      - tests/fixtures/p3_03_game_project/main.tscn
      - tests/fixtures/p3_03_game_project/project.godot
      - tests/fixtures/p3_03_game_project/test_runner.gd
      - tests/test_p3_03_game_pack.py
      - tests/test_p3_03_game_real.py
      - tests/test_p3_03_game_validation.py
    p3_03_remote_path_evidence:
      src_biella_init: "blob cd9e045881645fa290c8db2e0aa6c3f8231fadf1; size 29793; sha256 a1c0af057dbba44cf38caec429f89c79855df3ff42451c1cab26ab73fdefc31e"
      src_biella_game_engine: "blob 83ecbc13a82c182de5504614ed1b4963249ea477; size 171452; sha256 bcf8b7a0d419d4b967234ebe3c573e8beb3a59a5b739bc6723fe45f43429a094"
      src_biella_game_pack: "blob 4ffe85c0489299ca153ed9f22919ef4afbcf4451; size 11505; sha256 2ec6d0b65b477e5ab9a0830d218f08647d385d742d8bbea7562648c4d0710280"
      fixture_gitignore: "blob f0238d63e81acc179a1975467e8227fcecbb9714; size 39; sha256 ef77b61caf3c83545487de6157a9bb770b2c1c9bf71e75dbcc969100a2aba6b8"
      fixture_export_presets: "blob 9ee59939112caf7e213f2591b0e2d82db7cf28f0; size 1181; sha256 1201747f52c264c25a2e8c9972bee3ab21f606e4460dbba7c54ea502e6b61464"
      fixture_main_gd: "blob 97b3277ecb881b3e4674a790a49f99f90620f26f; size 4149; sha256 118cb98afb6931a6ac2c7f6254784ccd7f4d898da510d29ffd7cb8b76a6021ab"
      fixture_main_tscn: "blob 40af25be3d468c44c4dc232cf69bf2c5ecbe94f6; size 1009; sha256 bb215832fc305d876d184214bb49b6d34ef15bda3b557263152e7f69bcddb750"
      fixture_project_godot: "blob cf08720ff71613aaa89bdd9a6296e11b1ee12c2b; size 605; sha256 d1ffc9084fdadc4a6870233e4bfd7f73589ca4064fddde62b32e2af04bd436d8"
      fixture_test_runner: "blob 59f9238b492038995cde42cd09a272c0205c0c9d; size 1500; sha256 71c40aa84e181e66de9b295a7a741eed26da8a1a7f0f372c9b0af22974345e94"
      test_p3_03_pack: "blob fa7b1581f34bcf2c1ed864133a0295ad684bbef6; size 35047; sha256 413399c6e9fe8fe2862371ab0ad4df29a23c78ebddb24c9c933448ca36859ef4"
      test_p3_03_real: "blob a309180da881a16ab59405d7fa1a85899d8c4323; size 56681; sha256 e59a653783ba412d879820a42090269ca399fb019dfe49950ff9e7ef19678e1b"
      test_p3_03_validation: "blob 70d5fb87632ffabc652dbaa9c6a0ce2b8831a265; size 16392; sha256 c45cb2d0ed356136ec3e799c08499e08d4a31f20e7772f399cd5c93ab5280e1d"
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
    id: P3-04
    title: Large-Scale / AAA Multi-Domain Production Orchestration Pack
    drive_id: 1NLikJ8cPQ3-4ybpMr8FvHN2sn43fPVw_trMet-Wx_HQ
    canonical_prompt_text_sha256: f7a4cd3552b2a2d889826eed6baedbc48131f8be270ed9244bf4884d07cf574a
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
  id: P3-04
  global_number: 35
  title: Large-Scale / AAA Multi-Domain Production Orchestration Pack
  prompt_drive_id: 1NLikJ8cPQ3-4ybpMr8FvHN2sn43fPVw_trMet-Wx_HQ
  predecessor_result_commit: f665445e1771b98f34e1d82746c5d4a9686e3138
  predecessor_result_tree: 6a8c47f70fcd5df900381e05a93169a9aed25205

next_transition:
  - verify_P3_03_handoff_from_exact_remote_commit_tree_12_required_paths_and_live_Drive_continuity
  - load_exact_P3_04_prompt_and_directly_required_ProductionPack_Software_Game_Graph_Scheduler_Resource_Artifact_Checkpoint_Workspace_Validation_Project_Run_Task_and_quarantine_firewall_interfaces_only
  - define_large_scale_ProductionPack_descriptor_and_multi_domain_graph_recipes_as_pack_data_without_new_kernel_or_controller_types
  - compose_software_game_3D_character_animation_environment_render_VFX_image_audio_video_and_package_capability_refs_with_downstream_unimplemented_packs_explicitly_REFERENCE_only
  - persist_ProductionIntegrationManifest_with_exact_Project_Task_Run_Graph_component_Artifact_integration_build_validation_refs_and_digest
  - represent_real_fan_out_fan_in_with_at_least_four_independent_productive_branches_and_Scheduler_as_the_only_resource_authority
  - prove_max_concurrent_productive_nodes_greater_than_one_when_current_resources_allow_without_ambiguous_global_serializing_targets
  - exercise_worker_or_branch_failure_while_retaining_completed_and_independent_running_branches_then_recover_only_the_affected_branch
  - create_bounded_Graph_v2_for_one_changed_branch_while_preserving_failed_v1_history_and_exact_unaffected_outputs
  - integrate_only_exact_component_Artifact_versions_and_invalidate_or_version_integration_when_an_upstream_Artifact_changes
  - compose_Task_derived_domain_validation_without_a_universal_final_critic_or_global_threshold
  - run_Project_Alpha_large_production_and_unrelated_Project_Beta_work_without_data_leakage
  - keep_Project_quality_art_direction_performance_and_resource_budgets_as_Project_or_Task_data
  - keep_domain_specific_second_scheduler_global_production_lock_unjustified_serialization_whole_Run_restart_and_ambiguous_latest_integration_at_zero
  - run_required_focused_tests_regressions_typecheck_build
  - commit_and_push
  - remotely_read_back_exact_commit_and_tree
  - update_Drive_continuity_and_current_state
  - close_P3_04_before_opening_P3_05

prohibited_next_transition:
  - reinstall_host
  - rerun_vps_configurator
  - create_or_migrate_to_/srv/biella
  - duplicate_checkout
  - create_AAAController_AAAFactoryManager_AAAApprovalPipeline_permanent_worker_hierarchy_or_second_orchestrator
  - create_AAATask_AAARun_AAAGraph_AAAScheduler_or_domain_specific_resource_reservation_authority
  - create_heavyweight_global_AAA_global_production_global_or_global_production_lock
  - serialize_independent_productive_branches_without_a_real_dependency_resource_or_mutable_target_conflict
  - restart_the_whole_Run_after_one_branch_or_worker_failure
  - erase_succeeded_or_independent_running_branch_evidence_during_recovery
  - resolve_latest_character_environment_build_validation_or_other_ambiguous_Artifact_during_integration
  - integrate_without_exact_Project_Task_Run_Graph_component_Artifact_version_and_digest_identity
  - claim_REFERENCE_downstream_pack_branches_as_REAL_production
  - implement_later_3D_character_animation_environment_render_VFX_image_audio_video_or_packaging_prompt_bodies
  - create_a_universal_final_critic_or_global_AAA_quality_gate
  - impose_global_art_direction_visual_style_performance_FPS_frame_time_CPU_GPU_RAM_VRAM_storage_network_or_package_thresholds
  - treat_specialist_agents_as_permanent_authority_or_a_required_team_hierarchy
  - bypass_the_existing_Graph_Scheduler_ResourceAllocation_Checkpoint_Workspace_Artifact_or_Validation_contracts
  - mutate_ambiguous_or_mutable_source_without_exact_RepositoryRef_Workspace_snapshot_and_Artifact_identity
  - overwrite_or_revert_unrelated_dirty_Project_work
  - accept_stale_Task_Run_Graph_revision_Node_attempt_fence_Workspace_checkpoint_Artifact_validation_or_resource_evidence
  - leak_component_Artifact_manifest_Workspace_Run_or_validation_evidence_across_Projects
  - broad_historical_backup_extraction
  - raw_MiniTZ_activation
  - weaken_or_mock_Run_Task_Graph_Node_Event_Artifact_fence_integrity_restart_or_Project_authorization
  - treat_fixture_or_comment_strings_as_active_kernel_coupling_without_semantic_inspection
  - start_P3_04_before_P3_03_durable_close
  - start_BU_01_in_same_P0_01_session
  - install_gpu_stack_on_cpu_host_for_completeness
  - add_unrequested_security_architecture
  - add_approval_or_reviewer_systems
  - treat_research_or_prompt_pack_documents_as_implemented_engine_code
```
