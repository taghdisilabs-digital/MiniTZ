# 03 — BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v5
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
    commit: 3b431a5f9c591a3e89bdd83ac3a9a5363dfd4f0d
    tree: b7bb982a67e6f414e7ff055df745b84f18fc1469
    meaning: P3_09_DURABLE_REPAIR_IMPLEMENTATION
    github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATHS_CONFIRMED
  preserved_later_source:
    commit: b7a55142edea7de895f799b8bef074a2a02d916d
    tree: 6df2a4d4f04246713220aa2461a10e33ba1b93d1
    meaning: PRESERVED_ACCEPTED_LATER_SOURCE; NOT_FOUNDATION_COMPLETION_AUTHORITY
  branch_head_rule: continuity_commits_may_advance_after_this record; preserve_current_productive_state_before_future_mutation

numbered_execution:
  durable_prompts_complete: 45
  durable_prompts_total: 51
  progress: "45 / 51 durable; non-contiguous audited; next repair frontier 41"
  phase: P3_DURABLE_REPAIR
  just_closed_prompt: P3-09
  just_closed_global_number: 40
  next_frontier: P3-10
  next_global_number: 41
  next_title: VFX and Simulation Production Pack
  next_drive_prompt_id: 12GmJFm2-6mL7QSjyyaySDWbBi2WrkljUF447XWsHnnI
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
  P3_09:
    durable_close: COMPLETE
    repaired_from: generic_renderer_adapter_final_recovery_and_durable_evidence
  P3_10:
    durable_close: INCOMPLETE
    missing: full_simulation_adapter_ENOSPC_1_through_300_recovery_and_durable_evidence
  P3_11: {durable_close: INCOMPLETE, missing: durable_evidence}
  P3_12: {durable_close: INCOMPLETE, missing: durable_evidence}
  P3_13: {durable_close: INCOMPLETE, missing: six_KPI_report_correction_and_durable_evidence}
  P3_14: {durable_close: INCOMPLETE, missing: phase_exit_provenance_and_Event_evidence}
  P4_01_through_P4_05: {durable_close: COMPLETE}
  P4_06:
    durable_close: INCOMPLETE
    missing: authoritative_Engine_evidence_and_combined_failure_scenario

p3_09_durable_repair:
  exact_prompt_drive_id: 1FYsaztU8wwjl_6k8Nx4xJII4wId-MPflkLFUNwW4gRM
  preserved_original_implementation:
    commit: b23195b82e20a568f22b8ebc7be401d5bb95c97e
    tree: c35e5a1f38d6c938828ec0556706a3ed0e3ca93a
  repair_result:
    commit: 3b431a5f9c591a3e89bdd83ac3a9a5363dfd4f0d
    tree: b7bb982a67e6f414e7ff055df745b84f18fc1469
  generic_renderer_adapter:
    required_operations:
      - inspect
      - renderFrame
      - renderSequence
      - renderPasses
      - cancel
      - describeRuntime
      - validateOutput
    implementation: src/biella/render_adapter.py
    provider_neutral_contract: src/biella/render_pack.py
  final_recovery:
    mechanism: PRESERVED_RENDER_FRAME_AND_RESULT_JOURNALS_PLUS_REPLAY
    duplicate_scheduler_created: false
    duplicate_process_runner_created: false
    current_render_tool_blob: 1c3edc2bd0f03249ab6d36901872e8aed6a59ac3
    preserved_real_render_tool_blob: 1c3edc2bd0f03249ab6d36901872e8aed6a59ac3
    current_real_test_blob: 705c841cb6c37c8fa61d599e2aff80a94db62d95
    preserved_real_test_blob: 705c841cb6c37c8fa61d599e2aff80a94db62d95
    reuse_basis: functional_source_was_explicitly_preserved_and_real_paths_are_byte-identical
  fresh_verification:
    github_actions_run: 33526038687
    github_actions_job: 99917005167
    focused_tests: 3_PASS_IN_1_23_SECONDS
    strict_mypy: 2_SOURCE_FILES_NO_ISSUES
    compileall: PASS
    wheel_build: PASS
    wheel_size_bytes: 885608
    wheel_sha256: ccf1b41636d7dfa56f39075dd0c2614abf360abfef644ea53be466448cdcbb15
  preserved_real_gate:
    tests: 12_GREEN_IN_151_62_SECONDS
    strict_mypy: 5_PATHS_GREEN
    evidence_scope: REAL_BLENDER_FRAME_SEQUENCE_PASS_RECOVERY_FANOUT_VERSION_SEPARATION
  drive_evidence:
    id: 1b0fHOflk3gQCVR2Gt-FdRxj9m2DrZrtY
    parent_30_EXECUTION: 1QVX7072SvqiJ88-tWK1gxuMzFE9TZQce
    readback_required_before_ledger_close: true

continuation:
  next_task_id: ENG-P3-10
  next_task_title: P3-10 VFX and Simulation Production Pack durable repair
  next_task_started: false
  rule: update_direct_dependency_to_READY_after_ENG_P3_09_ledger_COMPLETE; do_not_auto_start
```
