# 03 - BIELLA CURRENT STATE

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
    implementation_commit: c99cb2d57f7dd710e97465fed4d961286b72050c
    implementation_tree: e0cf13164bc335342ef4d206569197f03366f710
    closure_commit: 4b7e6b6e48805392fadca69ef02470f6d4c3967d
    closure_tree: a0affdd0b81599c5eb9bb649f46488ed8955adc9
    meaning: P3_12_COMPLETE_DURABLE
    github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATH_BLOB_CONFIRMED
    preserved_later_work_completion_authority: false
  preserved_worktree:
    path: src/biella/production_recipe_learning.py
    sha256: 01879237ebac6c96b985b0b05f822897d25b6f2dd9f8f13952e38d7e93cd5d2d
    meaning: INDEPENDENT_P4_06_PRODUCTIVE_WORK; NOT_PART_OF_P3_12

numbered_execution:
  durable_prompts_complete: 48
  durable_prompts_total: 51
  progress: "48 / 51 durable; non-contiguous audited; active repair frontier 44"
  phase: P3_DURABLE_REPAIR
  just_closed_prompt: P3-12
  just_closed_global_number: 43
  active_prompt: P3-13
  active_global_number: 44
  active_title: Video Production, Editing, Compositing and Media Pipeline Pack
  active_drive_prompt_id: 12_Z1RrJBW8fGVj5z76wnaphozu8J2DjSrHd2gJVrbmA
  execution_authorized: true
  authorization_basis: MAHDI_STANDING_P3_06_THROUGH_P4_06

completion_audit_2026_09_01:
  authority: SUPERSEDES_CONFLICTING_COMPLETION_LABELS_AND_RECORDED_ASSERTIONS
  preservation_rule: preserve_all_later_source_and_results; invalidate_only_unsupported_durable_claims
  FOUNDATION_COMPLETE: INVALIDATED
  P3_06: {durable_close: COMPLETE}
  P3_07: {durable_close: COMPLETE}
  P3_08: {durable_close: COMPLETE}
  P3_09: {durable_close: COMPLETE}
  P3_10: {durable_close: COMPLETE}
  P3_11: {durable_close: COMPLETE}
  P3_12: {durable_close: COMPLETE}
  P3_13: {durable_close: INCOMPLETE, missing: six_KPI_report_correction_and_durable_media_video_evidence}
  P3_14: {durable_close: INCOMPLETE, missing: phase_exit_provenance_Event_and_delivery_evidence}
  P4_01_through_P4_05: {durable_close: COMPLETE, reuse: REQUIRED}
  P4_06: {durable_close: INCOMPLETE, missing: authoritative_Engine_evidence_and_combined_failure_scenario}

p3_12_durable_close:
  exact_prompt_drive_id: 1c8GEF9Z6pL9JKMkhXx6ZtsbcKnI5b_jY4k27ie3L1HI
  accepted_implementation_commit: 3dcc194253bb54d2a171cf7230877af95231ebe7
  accepted_implementation_tree: 8835d92e6651ea13ec5f02b87487f0520fb7bae6
  repair_commit: c99cb2d57f7dd710e97465fed4d961286b72050c
  repair_tree: e0cf13164bc335342ef4d206569197f03366f710
  closure_commit: 4b7e6b6e48805392fadca69ef02470f6d4c3967d
  closure_tree: a0affdd0b81599c5eb9bb649f46488ed8955adc9
  github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATH_BLOB_CONFIRMED
  qualification:
    local: 25_PASSED_2_SKIPPED; STRICT_MYPY_PASS
    github_run: 33549462937
    github_job: 99995052774
    github_result: SUCCESS; 24_PASSED_3_SKIPPED; STRICT_MYPY_PASS; WHEEL_PASS
    github_artifact: 9817199535
    github_wheel_sha256: 55d709417453795e9b79c0851795049352c6e3b0c649c7e027af8efa6330e24f
    l40s_result: EXACT_COMMIT_IMPORTER_PASS; CPU_ONLY_CUDA_HIDDEN; NO_GPU_CLAIM
    l40s_receipt_sha256: a4b0dc9b0b8e360880faee867170b383702ee2c86506bf0bb82c3631e334ae6d
    l40s_wheel_sha256: 124d2b27036ae5b00b9ae1ae097f49001a579e878639086c30c9191c520a1c1d
  real_execution:
    retained_archive_sha256: 2ec11b1fe23b9fd49aed4dbc4e31ad709fb56aac0dbbf19a4b6e292499d290f1
    retained_archive_size_bytes: 300400
    explicit_operations: 11
    processed_stems: 2
    mixes: 1
    successful_outputs: 15
    intentional_failures: 1
    true_concurrency: MEASURED_MAXIMUM_2
    cloudflare_aura_model_call: mcall_5c552cb17eed4afa98012c05276d17ff
    cloudflare_aura_result: SUCCEEDED; FULL_DECODE_PASS
    cloudflare_melotts_result: PROVIDER_HTTP_500_RETAINED_AS_INTENTIONAL_FAILURE
  engine_evidence:
    project_ref: prj_508b975a98994bfb9dc6331ade2b2c11
    task_ref: tsk_840b513f777042e6809d49fb8a4c3b48/1
    run_ref: run_20eb839e899c47428de78b991d319640
    run_status: SUCCEEDED
    graph_ref: graph://prj_508b975a98994bfb9dc6331ade2b2c11/gph_f062ff81113b48359b3c1f5be6fb9f5d/1
    graph_sha256: cb7718887e70d473d19a66e643ac1a5d1e25bde90f72fa2ac418b88fc7a1aca3
    retained_artifact_ref: artifact://prj_508b975a98994bfb9dc6331ade2b2c11/art_be13bca5301945fbb98162a44a8ccc79/1
    integration_artifact_ref: artifact://prj_508b975a98994bfb9dc6331ade2b2c11/art_67782ac61fbe4590a2179b05a5c8fe4f/1
    validation_aggregate_sha256: 96f256154e7ab55678e8235864513a072a08df0a0d84319fa7463b7d034071dc
    evidence_event_ref: event://prj_508b975a98994bfb9dc6331ade2b2c11/evt_0c36b8817b944c678f35a9562c06534e
    acceptance_event_ref: event://prj_508b975a98994bfb9dc6331ade2b2c11/evt_2734b8e54fdc47c18f7eeaee258de95e
    reconstruction: PASS
    unresolved_failures: 0
  kpis:
    invalid_audio_claimed_valid: 0
    source_audio_destructively_mutated: 0
    project_loudness_target_globalized: 0
    implicit_sample_rate_or_channel_conversion: 0
    mix_without_exact_stem_identity: 0
  drive_evidence:
    canonical_evidence_id: 1wPyWGSF9OpB9L47ZXOqECR1mtlcq_SMY
    retained_real_archive_id: 1RJFzKm16qIsYkHpyEDpzQn-QQwd7ll0A
    engine_evidence_id: 10Ld2FhHzqvrHQxJBxv9MKPO4zWZKnsoV
    l40s_receipt_id: 15Q_msefmw9EEcTczQV4sUjb_puYxFIkS
    l40s_wheel_id: 1nqxU2kM_EOpyT5SM4tDtuVCm8LPTR7J9
    github_wheel_id: 1J_FkQ5JCclF_HqhUXVKcW6_5X4Ceimy9
    github_ci_evidence_id: 1829aDK2YRrF1ccBzx_V6IbxnSR83ZyvM
    exact_byte_readback: VERIFIED
  canonical_ledger:
    task_status: COMPLETE
    dependency_status: SATISFIED
    completion_event: evt-ENG-P3-12-complete-20260901T194148Z
    successor_status: READY_ELIGIBLE

continuation:
  active_task_id: ENG-P3-13
  active_task_title: P3-13 Video Production, Editing, Compositing and Media Pipeline durable repair
  dependency: ENG-P3-12_COMPLETE
  ledger_claim: RUNNING
  acceptance_state: SOURCE_REPAIR_AND_REAL_EVIDENCE_EXECUTION
  execution_started: true
  spark_or_prep_dependency: NONE
  ordered_frontier: P3-13_THEN_P3-14_THEN_REUSE_P4-01_THROUGH_P4-05_THEN_P4-06_THEN_FOUNDATION_COMPLETE_THEN_BIELLA_GAMES
```
