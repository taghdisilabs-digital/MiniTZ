# 03 — BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v7
state_class: VOLATILE
update_rule: replace_stale_values; do_not_append_history
observed_date: 2026-09-01

authority:
  if_conflict:
    - CURRENT_EXECUTION_STATE
    - CURRENT_GITHUB_SOURCE
    - CURRENT_CANONICAL_DRIVE
    - VERIFIED_HISTORICAL_EVIDENCE
    - REFERENCE_OR_PLAN
    - INFERENCE
  correction_rule: invalidate_only_conflicting_state; preserve_independently_valid_work

engine:
  repository: patrickminitz-web/biella-engine
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine

durable_source:
  current_result:
    commit: dd18a276c6f4ec58ade2d6231072d6965d60602d
    tree: 592ac9aff67347f2343dbe4c0d4c7901e3a2beb9
    meaning: P3_11_IMAGE_PRODUCTION_DURABLE_REPAIR_VALIDATION
    github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATHS_CONFIRMED
  previous_frontier_result:
    commit: e23794659f41d1bfeb008033ee5b0d0c3cbc1344
    tree: 2f9183cc89acf5d837a7a34df00e64ab7d2c9756
    meaning: P3_10_VFX_SIMULATION_REPAIR_IMPLEMENTATION
  branch_head_rule: continuity_commits_may_advance_after_this_record; preserve_current_productive_state_before_future_mutation

numbered_execution:
  durable_prompts_complete: 47
  durable_prompts_total: 51
  progress: "47 / 51 durable; non-contiguous audited; next repair frontier 43"
  phase: P3_DURABLE_REPAIR
  just_closed_prompt: P3-11
  just_closed_global_number: 42
  next_frontier: P3-12
  next_global_number: 43
  next_title: Audio Production, Processing, Mixing and Validation Pack
  next_drive_prompt_id: 1c8GEF9Z6pL9JKMkhXx6ZtsbcKnI5b_jY4k27ie3L1HI
  next_execution_started: false
  next_execution_requires_canonical_ledger_claim: true

execution_host_state:
  current_host:
    provider: AWS
    instance_id: i-0056cad38b67415c1
    region: eu-west-3
    instance_type: t2.xlarge
    public_ipv4: 13.38.217.245
    private_ipv4: 172.31.47.69
    state: RUNNING
    resource_note: LOWER_RESOURCE_REPLACEMENT_HOST
  canonical_root: /root/biella
  canonical_codex_home: /root/.codex
  canonical_checkout: /root/biella/repos/biella-engine

completion_audit_2026_09_01:
  authority: SUPERSEDES_CONFLICTING_COMPLETION_LABELS_AND_RECORDED_ASSERTIONS
  preservation_rule: preserve_all_later_source_and_results; invalidate_only_unsupported_durable_claims
  FOUNDATION_COMPLETE: INVALIDATED
  P3_06: {durable_close: COMPLETE}
  P3_07: {durable_close: COMPLETE}
  P3_08: {durable_close: COMPLETE}
  P3_09: {durable_close: COMPLETE, repaired_from: generic_renderer_adapter_final_recovery_and_durable_evidence}
  P3_10: {durable_close: COMPLETE, repaired_from: full_simulation_adapter_ENOSPC_1_through_300_recovery_and_durable_evidence}
  P3_11: {durable_close: COMPLETE, repaired_from: durable_image_production_evidence}
  P3_12: {durable_close: INCOMPLETE, missing: durable_evidence}
  P3_13: {durable_close: INCOMPLETE, missing: six_KPI_report_correction_and_durable_evidence}
  P3_14: {durable_close: INCOMPLETE, missing: phase_exit_provenance_and_Event_evidence}
  P4_01_through_P4_05: {durable_close: COMPLETE}
  P4_06:
    durable_close: INCOMPLETE
    missing: authoritative_Engine_evidence_and_combined_failure_scenario

p3_11_durable_repair:
  exact_prompt_drive_id: 1hZm2VC3xYefqwZBxvIhsChrIjCLcZXsTSoOCG3IKLhM
  task_id: ENG-P3-11
  source_before_task:
    commit: 7a4feb3b1ff32300be67be0c36f1fd923a288e6b
    tree: 5ce486ac3cc846c4dc2693861981e4bdb45a095c
  validation_result:
    commit: dd18a276c6f4ec58ade2d6231072d6965d60602d
    tree: 592ac9aff67347f2343dbe4c0d4c7901e3a2beb9
  changed_paths:
    - .github/workflows/p3-11-image-production-repair.yml
    - docs/project-state/evidence/P3_11_IMAGE_PRODUCTION_REPAIR_EVIDENCE.md
  preserved_implementation:
    - src/biella/image_pack.py
    - src/biella/image_tool.py
    - src/biella/cloudflare_image_model.py
    - tests/test_p3_11_image_pack.py
    - tests/test_p3_11_image_real.py
    - tests/test_p3_11_image_model.py
  fresh_verification:
    github_actions_run: 33532394221
    github_actions_job: 99938456554
    focused_tests: 27_PASS_1_SKIP_IN_62_00_SECONDS
    strict_mypy: 3_SOURCE_FILES_NO_ISSUES
    compileall: PASS
    wheel_build: PASS
    wheel_size_bytes: 894426
    wheel_sha256: db30a5b208302a9780776e678d2e8c6fccfed33af166c6bf5ac83f971a0f375d
    evidence_sha256: d86c01960abdef63ec5cb16cddd203cdf25c6d4c59542b5042a7b6ca85400132
  kpi_results:
    corrupt_image_accepted: 0
    source_image_destructively_mutated: 0
    project_visual_style_globalized: 0
    texture_channel_convention_implicit: 0
    color_space_silently_changed: 0
    provider_specific_image_kernel_architecture: 0
  reality_classification:
    deterministic_image_runtime: REAL
    p3_05_scheduler_support_paths: NON_EXECUTED_FIXTURE
    provider_contract_with_corrupt_output_rejection: REFERENCE_ADAPTER_TEST
    external_cloudflare_generation_in_ci: NOT_RUN
  boundary_checks:
    duplicate_scheduler_created: false
    duplicate_object_store_created: false
    duplicate_validation_framework_created: false
    game_or_website_mechanisms_modified: false
    raw_history_or_MiniTZ_activated: false
  evidence_file: docs/project-state/evidence/P3_11_IMAGE_PRODUCTION_REPAIR_EVIDENCE.md
  drive_evidence_readback_required_before_ledger_close: true

continuation:
  next_task_id: ENG-P3-12
  next_task_title: P3-12 Audio Production, Processing, Mixing and Validation Pack durable repair
  next_task_started: false
  rule: update_direct_dependency_to_READY_after_ENG_P3_11_ledger_COMPLETE; do_not_auto_start
```
