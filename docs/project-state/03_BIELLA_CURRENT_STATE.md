# 03 — BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v2
state_timestamp_local: "2026-08-28 07:47 Europe/Amsterdam"
state_timestamp_iso: "2026-08-28T07:47:48+02:00"
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
    commit: 8f53a1fd641ad46c893239cd8279f310432086bc
    tree: ed4e97846d8c055a0e8967b83a8b100bef481ddf
    observed_date: 2026-08-28
    evidence: CURRENT_GITHUB_SOURCE
    observation_context: p0_05_implementation_post_push_exact_readback
    src_present: true
    root_package_json_present: false
    root_pyproject_present: true
    volatile_reobserve_before_next_write: true

  local:
    checkout_path: /root/biella/repos/biella-engine
    checkout_exists: true
    branch: main
    head: 8f53a1fd641ad46c893239cd8279f310432086bc
    tree: ed4e97846d8c055a0e8967b83a8b100bef481ddf
    upstream: origin/main
    worktree_status: CLEAN_AT_IMPLEMENTATION_READBACK
    newer_valid_work_present: false

  implementation:
    durable_prompts_complete: 5
    durable_prompts_total: 51
    phase: P0
    active_prompt: P0-06
    active_prompt_title: Artifact and Source Identity Contract
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
    id: P0-06
    title: Artifact and Source Identity Contract
    drive_id: 17l-QAoXQPl2QkE3B7BJqoeCVsJHybnrq8UQlRltu1as
    canonical_prompt_text_sha256: 6a28d180247ad33881e9b02e57cd9e1cd72e4f2cba619f96dafab0d217bf8bb7
    local_and_live_drive_prompt_text_equal: true

  inactive_reference_candidates:
    - title: Legacy Productive Reuse
      drive_id: 1P4uv74n0UI0JROi5J83ehrg9wDyWPg7FCt5dMMi9HTc
      state: INACTIVE_UNTIL_AFTER_P0_10_DURABLE_CLOSE
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
  stage: P0_01_DURABLY_COMPLETE
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
  execution_state: P0_05_GATE_CLEARED_NOT_STARTED
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
  id: P0-06
  title: Artifact and Source Identity Contract
  prompt_drive_id: 17l-QAoXQPl2QkE3B7BJqoeCVsJHybnrq8UQlRltu1as
  predecessor_result_commit: 8f53a1fd641ad46c893239cd8279f310432086bc
  predecessor_result_tree: ed4e97846d8c055a0e8967b83a8b100bef481ddf

next_transition:
  - verify_P0_05_handoff_from_exact_remote_commit_tree_and_required_paths
  - load_exact_P0_06_prompt_and_directly_required_files_only
  - implement_Artifact_ArtifactRef_ContentRef_SourceRef_and_ArtifactDerivation
  - prove_Project_scope_exact_content_source_derivation_and_immutable_revision_identity
  - run_required_focused_tests_regressions_typecheck_build
  - commit_and_push
  - remotely_read_back_exact_commit_and_tree
  - update_Drive_continuity_and_current_state
  - close_P0_06_before_opening_P0_07

prohibited_next_transition:
  - reinstall_host
  - rerun_vps_configurator
  - create_or_migrate_to_/srv/biella
  - duplicate_checkout
  - broaden_P0_06_into_physical_object_storage_backends_or_later_numbered_architecture
  - broad_historical_backup_extraction
  - raw_MiniTZ_activation
  - use_filename_path_storage_URI_or_content_digest_as_logical_Artifact_identity
  - collapse_cross_Project_authority_for_identical_content
  - accept_QuarantineRef_as_active_Artifact_or_ContentRef
  - start_P0_07_before_P0_06_durable_close
  - start_BU_01_in_same_P0_01_session
  - install_gpu_stack_on_cpu_host_for_completeness
  - add_unrequested_security_architecture
  - add_approval_or_reviewer_systems
  - treat_research_or_prompt_pack_documents_as_implemented_engine_code
```
