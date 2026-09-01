# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v8

program_boundary:
  state: NEXT_FRONTIER_NOT_CLAIMED
  completed_predecessor: P3-11
  next_numbered_prompt: P3-12
  next_global_number: 43
  next_title: Audio Production, Processing, Mixing and Validation Pack
  next_prompt_drive_id: 1c8GEF9Z6pL9JKMkhXx6ZtsbcKnI5b_jY4k27ie3L1HI
  execution_started: false
  execution_authorized: false_until_canonical_ledger_claim

P3_11_durable_close:
  status: COMPLETE_PENDING_CANONICAL_LEDGER_READBACK
  ledger_task_id: ENG-P3-11
  exact_prompt_drive_id: 1hZm2VC3xYefqwZBxvIhsChrIjCLcZXsTSoOCG3IKLhM
  source_before_task:
    commit: 7a4feb3b1ff32300be67be0c36f1fd923a288e6b
    tree: 5ce486ac3cc846c4dc2693861981e4bdb45a095c
  validation_result:
    commit: dd18a276c6f4ec58ade2d6231072d6965d60602d
    tree: 592ac9aff67347f2343dbe4c0d4c7901e3a2beb9
  github_readback: EXACT_VALIDATION_COMMIT_TREE_AND_REQUIRED_PATHS_CONFIRMED
  changed_paths:
    - .github/workflows/p3-11-image-production-repair.yml
    - docs/project-state/evidence/P3_11_IMAGE_PRODUCTION_REPAIR_EVIDENCE.md
    - docs/project-state/03_BIELLA_CURRENT_STATE.md
    - docs/project-state/04_BIELLA_ACTIVE_TASK.md
  fresh_gate:
    workflow_run: 33532394221
    job: 99938456554
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
  known_limitations:
    - No external Cloudflare image generation was run in CI; exact prompt permits NOT_RUN when unavailable.
    - Hosted CI uses fail-closed non-executed Blender/bwrap scheduler identity fixtures; they are not real 3D evidence.
  evidence_file: docs/project-state/evidence/P3_11_IMAGE_PRODUCTION_REPAIR_EVIDENCE.md

next_frontier:
  ledger_task_id: ENG-P3-12
  dependency: ENG-P3-11
  ledger_state_before_dependency_transition: BLOCKED
  required_transition_after_P3_11_COMPLETE: READY
  title: P3-12 Audio Production, Processing, Mixing and Validation Pack durable repair
  completion_gap: durable_evidence
  do_not_start_in_this_execution: true
```
