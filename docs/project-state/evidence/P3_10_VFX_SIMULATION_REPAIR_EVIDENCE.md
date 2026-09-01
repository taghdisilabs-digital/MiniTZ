# P3-10 VFX and Simulation Production Pack Durable Repair Evidence

```yaml
schema: biella.evidence/p3_10_vfx_simulation_repair/v1
observed_at_utc: 2026-09-01T16:17:23Z
ledger_task_id: ENG-P3-10
prompt:
  id: P3-10
  global_number: 41
  title: VFX and Simulation Production Pack
  drive_id: 12GmJFm2-6mL7QSjyyaySDWbBi2WrkljUF447XWsHnnI
  revision_id: ANLCKQneBOaFKeI48oHi1lg7VJ-ZjJ0tSeCBmYBr74uIHtnZ_5JrzT_Ui9zxofYTkC-LyWpiyia_3aWTBW13SGE9l0dSY2kXzq9OEHvSl3A

source_before_task:
  head_commit: 39e51b95de130dddf2e8cde49670257742c0eaac
  head_tree: 772e20442cc4a2113361841614a080678e916685
  preservation_note: main advanced during execution; P3-10 work was based on the observed current head rather than older P3-09 continuity source.

implementation_commit:
  commit: e23794659f41d1bfeb008033ee5b0d0c3cbc1344
  tree: 2f9183cc89acf5d837a7a34df00e64ab7d2c9756
  message: Add P3-10 ENOSPC simulation recovery path
  remote_ref_readback: refs/heads/main -> e23794659f41d1bfeb008033ee5b0d0c3cbc1344

changed_paths:
  src/biella/vfx_recovery.py:
    blob: 69ec8f4db4993c479b976e064101b5818c20a89e
    local_sha256: 2554871f3d4ef21f364a6ae2903306ce2c65e890db6b60edf5732211f9ad6e8d
  tests/test_p3_10_enospc_recovery.py:
    blob: 59bb80b23daf89321a1c4dfe67412033d676b6fd
    local_sha256: 1b4a2ba25e071ca544cce87c3933c2f3ed51fa7f846f6086949b37dd3ee1c592
  .github/workflows/p3-10-vfx-simulation-repair.yml:
    blob: a11d65fd1763223088a36d4db6531c2d21b8cd66
    local_sha256_initial: b5825c9daf123bca4c4fd8919b2db14ba2f4ece97024db045806e2927849e908

local_tdd_verification:
  red: tests/test_p3_10_enospc_recovery.py initially failed with ModuleNotFoundError for biella.vfx_recovery
  green: PYTHONPATH=src python -m pytest tests/test_p3_10_enospc_recovery.py -q plus py_compile passed
  green_result: 4 passed in 0.03s

remote_validation:
  workflow: P3-10 VFX Simulation Repair
  run: 33530858428
  job: 99933353830
  commit: e23794659f41d1bfeb008033ee5b0d0c3cbc1344
  conclusion: success
  focused_tests: 6 passed in 1.07s
  strict_mypy: Success; no issues found in 2 source files
  compileall: PASS
  wheel_build: PASS
  wheel_size_bytes: 894426
  wheel_sha256: 924781a022dc8894c6bba580c706d5abf13a8d5d1312c141bb9fa577c9ab6e53

enospc_recovery_evidence:
  evidence_sha256: 581d6773414c7c8c6abda007d014126837e82c982051bb8d48d6c3de8d57e98a
  failure_classification: RESOURCE_EXHAUSTED
  failure_reason: ENOSPC: no space left on device while writing frame 237 cache
  frame_start: 1
  frame_end: 300
  failed_frame: 237
  preserved_segments:
    - [1, 100]
    - [101, 200]
  latest_verified_frame: 200
  resume_frame_start: 201
  resume_frame_end: 300
  frames_to_dispatch_count: 100
  frames_to_dispatch_first: 201
  frames_to_dispatch_last: 300
  frames_to_recompute: []
  cache_authority: REBUILDABLE_ONLY
  requires_spec_checkpoint_content_verification: true

kpi_results:
  simulation_cache_used_as_only_authority: 0
  verified_segments_lost_after_failure: 0
  incompatible_checkpoint_resumes: 0
  dependent_solver_steps_parallelized_incorrectly: 0
  global_GPU_requirement_for_VFX: 0

reality_classification:
  enospc_1_300_recovery_path: REAL_DETERMINISTIC_CONTRACT
  blender_runtime_in_ci: NOT_RUN

project_isolation_and_boundary_checks:
  duplicate_scheduler_created: false
  duplicate_object_store_created: false
  duplicate_validation_framework_created: false
  game_or_website_mechanisms_modified: false
  raw_history_or_MiniTZ_activated: false

known_limitations:
  - GitHub Actions focused repair workflow validates the deterministic ENOSPC recovery contract and existing vfx contract tests, not a real Blender runtime bake.
  - Existing real Blender simulation adapter source and real test suite remain preserved; this repair closes the missing ENOSPC 1-300 recovery path evidence identified by the canonical audit.

next_dependency:
  task_id: ENG-P3-11
  title: P3-11 Image Production, Editing, Compositing and Texture Pack durable repair
  state_after_ledger_close: READY_ONLY_AFTER_ENG_P3_10_COMPLETE
```
