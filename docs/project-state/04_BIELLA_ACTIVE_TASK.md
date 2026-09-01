# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v6

program_boundary:
  state: NEXT_FRONTIER_NOT_CLAIMED
  completed_predecessor: P3-09
  next_numbered_prompt: P3-10
  next_global_number: 41
  next_title: VFX and Simulation Production Pack
  next_prompt_drive_id: 12GmJFm2-6mL7QSjyyaySDWbBi2WrkljUF447XWsHnnI
  execution_started: false
  execution_authorized: false_until_canonical_ledger_claim

P3_09_durable_close:
  status: COMPLETE
  exact_prompt_drive_id: 1FYsaztU8wwjl_6k8Nx4xJII4wId-MPflkLFUNwW4gRM
  preserved_source:
    commit: b23195b82e20a568f22b8ebc7be401d5bb95c97e
    tree: c35e5a1f38d6c938828ec0556706a3ed0e3ca93a
  repair_result:
    commit: 3b431a5f9c591a3e89bdd83ac3a9a5363dfd4f0d
    tree: b7bb982a67e6f414e7ff055df745b84f18fc1469
  github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATHS_CONFIRMED
  generic_renderer_adapter:
    methods:
      - inspect
      - renderFrame
      - renderSequence
      - renderPasses
      - cancel
      - describeRuntime
      - validateOutput
  final_recovery: PRESERVED_FRAME_RESULT_JOURNAL_REPLAY_THROUGH_GENERIC_ADAPTER
  fresh_gate:
    workflow_run: 33526038687
    job: 99917005167
    focused_tests: 3_PASS_IN_1_23_SECONDS
    strict_mypy: 2_SOURCE_FILES_NO_ISSUES
    compileall: PASS
    wheel_build: PASS
    wheel_sha256: ccf1b41636d7dfa56f39075dd0c2614abf360abfef644ea53be466448cdcbb15
  preserved_real_evidence:
    render_tool_blob: 1c3edc2bd0f03249ab6d36901872e8aed6a59ac3
    real_test_blob: 705c841cb6c37c8fa61d599e2aff80a94db62d95
    historical_real_gate: 12_TESTS_GREEN_IN_151_62_SECONDS
  drive_evidence_id: 1b0fHOflk3gQCVR2Gt-FdRxj9m2DrZrtY

next_frontier:
  ledger_task_id: ENG-P3-10
  dependency: ENG-P3-09
  ledger_state_before_dependency_transition: BLOCKED
  required_transition_after_P3_09_COMPLETE: READY
  title: P3-10 VFX and Simulation Production Pack durable repair
  completion_gap: full_simulation_adapter_ENOSPC_1_through_300_recovery_and_durable_evidence
  do_not_start_in_this_execution: true
```
