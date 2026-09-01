# 03 — BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v6
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
    commit: e23794659f41d1bfeb008033ee5b0d0c3cbc1344
    tree: 2f9183cc89acf5d837a7a34df00e64ab7d2c9756
    meaning: P3_10_VFX_SIMULATION_REPAIR_IMPLEMENTATION
    github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATHS_CONFIRMED
  previous_frontier_result:
    commit: 39e51b95de130dddf2e8cde49670257742c0eaac
    tree: 772e20442cc4a2113361841614a080678e916685
    meaning: MERGED_DURABLE_P3_09_RENDERER_REPAIRS; BASE_OBSERVED_BEFORE_P3_10_WRITE
  branch_head_rule: continuity_commits_may_advance_after_this_record; preserve_current_productive_state_before_future_mutation

numbered_execution:
  durable_prompts_complete: 46
  durable_prompts_total: 51
  progress: "46 / 51 durable; non-contiguous audited; next repair frontier 42"
  phase: P3_DURABLE_REPAIR
  just_closed_prompt: P3-10
  just_closed_global_number: 41
  next_frontier: P3-11
  next_global_number: 42
  next_title: Image Production, Editing, Compositing and Texture Pack
  next_drive_prompt_id: 1hZm2VC3xYefqwZBxvIhsChrIjCLcZXsTSoOCG3IKLhM
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
  P3_10:
    durable_close: COMPLETE
    repaired_from: full_simulation_adapter_ENOSPC_1_through_300_recovery_and_durable_evidence
  P3_11: {durable_close: INCOMPLETE, missing: durable_evidence}
  P3_12: {durable_close: INCOMPLETE, missing: durable_evidence}
  P3_13: {durable_close: INCOMPLETE, missing: six_KPI_report_correction_and_durable_evidence}
  P3_14: {durable_close: INCOMPLETE, missing: phase_exit_provenance_and_Event_evidence}
  P4_01_through_P4_05: {durable_close: COMPLETE}
  P4_06:
    durable_close: INCOMPLETE
    missing: authoritative_Engine_evidence_and_combined_failure_scenario

p3_10_durable_repair:
  exact_prompt_drive_id: 12GmJFm2-6mL7QSjyyaySDWbBi2WrkljUF447XWsHnnI
  task_id: ENG-P3-10
  implementation_result:
    commit: e23794659f41d1bfeb008033ee5b0d0c3cbc1344
    tree: 2f9183cc89acf5d837a7a34df00e64ab7d2c9756
  changed_paths:
    - src/biella/vfx_recovery.py
    - tests/test_p3_10_enospc_recovery.py
    - .github/workflows/p3-10-vfx-simulation-repair.yml
  enospc_recovery:
    scenario: frames_1_through_300; verified_1_100_and_101_200; ENOSPC_at_237; resume_201_300
    preserved_segments:
      - [1, 100]
      - [101, 200]
    frames_to_dispatch: 201_300
    frames_to_recompute: 0
    cache_authority: REBUILDABLE_ONLY
    evidence_sha256: 581d6773414c7c8c6abda007d014126837e82c982051bb8d48d6c3de8d57e98a
  fresh_verification:
    local_tdd_green: 4_PASS_IN_0_03_SECONDS
    github_actions_run: 33530858428
    github_actions_job: 99933353830
    focused_tests: 6_PASS_IN_1_07_SECONDS
    strict_mypy: 2_SOURCE_FILES_NO_ISSUES
    compileall: PASS
    wheel_build: PASS
    wheel_size_bytes: 894426
    wheel_sha256: 924781a022dc8894c6bba580c706d5abf13a8d5d1312c141bb9fa577c9ab6e53
  kpi_results:
    simulation_cache_used_as_only_authority: 0
    verified_segments_lost_after_failure: 0
    incompatible_checkpoint_resumes: 0
    dependent_solver_steps_parallelized_incorrectly: 0
    global_GPU_requirement_for_VFX: 0
  boundary_checks:
    duplicate_scheduler_created: false
    duplicate_object_store_created: false
    duplicate_validation_framework_created: false
    game_or_website_mechanisms_modified: false
    raw_history_or_MiniTZ_activated: false
  evidence_file: docs/project-state/evidence/P3_10_VFX_SIMULATION_REPAIR_EVIDENCE.md
  drive_evidence_readback_required_before_ledger_close: true

continuation:
  next_task_id: ENG-P3-11
  next_task_title: P3-11 Image Production, Editing, Compositing and Texture Pack durable repair
  next_task_started: false
  rule: update_direct_dependency_to_READY_after_ENG_P3_10_ledger_COMPLETE; do_not_auto_start
```
