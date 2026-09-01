# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v7

program_boundary:
  state: NEXT_FRONTIER_NOT_CLAIMED
  completed_predecessor: P3-10
  next_numbered_prompt: P3-11
  next_global_number: 42
  next_title: Image Production, Editing, Compositing and Texture Pack
  next_prompt_drive_id: 1hZm2VC3xYefqwZBxvIhsChrIjCLcZXsTSoOCG3IKLhM
  execution_started: false
  execution_authorized: false_until_canonical_ledger_claim

P3_10_durable_close:
  status: COMPLETE
  ledger_task_id: ENG-P3-10
  exact_prompt_drive_id: 12GmJFm2-6mL7QSjyyaySDWbBi2WrkljUF447XWsHnnI
  source_before_task:
    commit: 39e51b95de130dddf2e8cde49670257742c0eaac
    tree: 772e20442cc4a2113361841614a080678e916685
  implementation_result:
    commit: e23794659f41d1bfeb008033ee5b0d0c3cbc1344
    tree: 2f9183cc89acf5d837a7a34df00e64ab7d2c9756
  github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATHS_CONFIRMED
  changed_paths:
    - src/biella/vfx_recovery.py
    - tests/test_p3_10_enospc_recovery.py
    - .github/workflows/p3-10-vfx-simulation-repair.yml
  enospc_1_300_recovery:
    failure_classification: RESOURCE_EXHAUSTED
    failed_frame: 237
    verified_segments_preserved:
      - [1, 100]
      - [101, 200]
    resume_frame_start: 201
    resume_frame_end: 300
    frames_to_dispatch_count: 100
    frames_to_recompute: 0
    cache_authority: REBUILDABLE_ONLY
    evidence_sha256: 581d6773414c7c8c6abda007d014126837e82c982051bb8d48d6c3de8d57e98a
  fresh_gate:
    local_tdd_green: 4_PASS_IN_0_03_SECONDS
    workflow_run: 33530858428
    job: 99933353830
    focused_tests: 6_PASS_IN_1_07_SECONDS
    strict_mypy: 2_SOURCE_FILES_NO_ISSUES
    compileall: PASS
    wheel_build: PASS
    wheel_sha256: 924781a022dc8894c6bba580c706d5abf13a8d5d1312c141bb9fa577c9ab6e53
  kpi_results:
    simulation_cache_used_as_only_authority: 0
    verified_segments_lost_after_failure: 0
    incompatible_checkpoint_resumes: 0
    dependent_solver_steps_parallelized_incorrectly: 0
    global_GPU_requirement_for_VFX: 0
  known_limitations:
    - focused GitHub Actions repair workflow did not run a real Blender bake; existing real Blender adapter source/test suite remains preserved.
  evidence_file: docs/project-state/evidence/P3_10_VFX_SIMULATION_REPAIR_EVIDENCE.md

next_frontier:
  ledger_task_id: ENG-P3-11
  dependency: ENG-P3-10
  ledger_state_before_dependency_transition: BLOCKED
  required_transition_after_P3_10_COMPLETE: READY
  title: P3-11 Image Production, Editing, Compositing and Texture Pack durable repair
  completion_gap: durable_evidence
  do_not_start_in_this_execution: true
```
