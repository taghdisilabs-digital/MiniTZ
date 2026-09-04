# 03 - BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v5
state_class: VOLATILE
update_rule: replace_stale_values; do_not_append_history
observed_date: 2026-09-04

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
    implementation_commit: cb451cc221993efd5963727866873c2256c1090e
    implementation_tree: cfcf31f27db642aad1539a5a040f0b5059e828dd
    workflow_qualification_commit: cb451cc221993efd5963727866873c2256c1090e
    workflow_qualification_tree: cfcf31f27db642aad1539a5a040f0b5059e828dd
    evidence_commit: 1cd04275ee39dc7d2f8102b4daaa484718a2f974
    evidence_tree: 5043b79b9002619d05c70e14588e7770f09273b7
    evidence_blob_sha: 93f7b982442c9f0f0ccf24571c10e95c24848a08
    evidence_path: docs/project-state/evidence/P3_14_DELIVERY_QUALIFICATION_EVIDENCE.md
    qualification_record_source_commit: cb451cc221993efd5963727866873c2256c1090e
    qualification_record_source_tree: cfcf31f27db642aad1539a5a040f0b5059e828dd
    meaning: P3_14_COMPLETE_DURABLE_REFERENCE_CI
    github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATH_BLOB_CONFIRMED
    live_l40s_execution: NOT_RUN
    live_cloudflare_publish: NOT_RUN
    drive_publication: NOT_RUN
    canonical_drive_sync: VERIFIED
    canonical_drive_state_file_id: 1wiWcdWt4hmTf3narsLw4OqGu_ueKOSa4
    canonical_drive_task_file_id: 1liutA8evH6rPjk-U4tgR13l_kqBrx-DF
    drive_evidence_file_id: 1qm2gmf2RWwGelwUa9KUfyUFxrd5GW-Ug
    drive_artifact_file_id: 1Pp2P3-n0pP25PtiMB5Ba46fLfcb22iJf
    preserved_later_work_completion_authority: false
  preserved_worktree:
    path: src/biella/production_recipe_learning.py
    sha256: 01879237ebac6c96b985b0b05f822897d25b6f2dd9f8f13952e38d7e93cd5d2d
    meaning: INDEPENDENT_P4_06_PRODUCTIVE_WORK; NOT_PART_OF_P3_12

numbered_execution:
  durable_prompts_complete: 50
  durable_prompts_total: 51
  progress: "50 / 51 durable; non-contiguous audited; active frontier 51"
  phase: P4_EVIDENCE_BASED_LEARNING
  just_closed_prompt: P3-14
  just_closed_global_number: 45
  active_prompt: P4-06
  active_global_number: 51
  active_title: Versioned Production Recipe Learning and System Evidence Summary
  active_drive_prompt_id: 1vsxRXkhtv0n8eJdQ56AVqJJEl3k5hjtqJsrUIqFVeAA
  execution_started: false
  execution_authorized: true
  authorization_basis: MAHDI_STANDING_P3_06_THROUGH_P4_06

completion_audit_2026_09_04:
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
  P3_13: {durable_close: COMPLETE}
  P3_14: {durable_close: COMPLETE_DURABLE, evidence: docs/project-state/evidence/P3_14_DELIVERY_QUALIFICATION_EVIDENCE.md, result: REFERENCE_CI_PASS}
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

p3_13_durable_close:
  status: COMPLETE_DURABLE
  completed_at_utc: 2026-09-01T20:50:10Z
  exact_prompt_drive_id: 12_Z1RrJBW8fGVj5z76wnaphozu8J2DjSrHd2gJVrbmA
  repair_commit: 8133a5408babc142602f93e1af22cf8eb258a9db
  repair_tree: c1679d62ba3f7ad65143292a0b2dbd282ae37603
  workflow_qualification_commit: fef638d87ec0799e7f94d806cf01da307c5e543d
  workflow_qualification_tree: 566fa04e3cf080a96a44f9bab16d2785fc60d692
  github_actions_run: 33554959677
  github_actions_artifact: 9819033703
  l40s_package_gate: PASS
  engine_evidence:
    project_ref: prj_de760e9b27764d0f8754f7bcecc31c47
    run_ref: run_7dea687cfafe409bb132f7ff68fbd8e4
    run_status: SUCCEEDED
    graph_ref: graph://prj_de760e9b27764d0f8754f7bcecc31c47/gph_f189fc9a80c94bb881bdc2a1a1b36157/1
    validation_aggregate_sha256: 88adf5cc6cc6448e7fe2f3bfd6b4ca86e2d9d1c6a98da5d7fd1c10971f088707
    validation_status: PASS
    validation_freshness: CURRENT
    evidence_event_ref: event://prj_de760e9b27764d0f8754f7bcecc31c47/evt_30faa1b561ff4aa589558e01ddedc8c6
    acceptance_event_ref: event://prj_de760e9b27764d0f8754f7bcecc31c47/evt_3e4732a151834e53bcadd2849f367dda
  kpis:
    invalid_video_container_claimed_valid: 0
    source_video_destructively_mutated: 0
    global_frame_rate_or_resolution_policy: 0
    missing_frames_silently_replaced: 0
    frame_order_lost: 0
    audio_silently_stretched: 0
  drive_evidence:
    canonical_evidence_id: 15XWGE_7cSrXyDShiXmhFOqG5WbT1CSTg
    retained_real_archive_id: 11y5PsDydFy47HOuuk7oRaXYD5700Eyr9
    retained_real_archive_sha256: 32152eab780d65d27231f25d6f12993d16509d3065597bf1e5d2ee841efcf31f
    retained_real_archive_size_bytes: 1269361
    engine_evidence_id: 1NK1k_Cu3g4lTQCkG6f9_x2aTEZPG4lwA
    engine_evidence_sha256: 8ec7e88ea6500cea9f94bbad8187e9dce771bbb356cbf03cc06a10c20b7d122f
  canonical_ledger:
    task_status: COMPLETE
    successor_status: READY_ELIGIBLE
    readback: VERIFIED

p3_14_durable_close:
  status: COMPLETE_DURABLE
  completed_at_utc: 2026-09-04T14:36:11Z
  exact_prompt_drive_id: 1mkk0VYh14ut2Tz-7YKcdW35p0GJRtv7bVQeVSPVTzpE
  implementation_commit: cb451cc221993efd5963727866873c2256c1090e
  implementation_tree: cfcf31f27db642aad1539a5a040f0b5059e828dd
  workflow_qualification_commit: cb451cc221993efd5963727866873c2256c1090e
  workflow_qualification_tree: cfcf31f27db642aad1539a5a040f0b5059e828dd
  github_actions_run: 33884528731
  github_actions_job: 101060955843
  github_actions_result: SUCCESS
  focused_tests: 16_PASSED_1_SKIPPED
  focused_test_output_sha256: b93e684d200bb4d0f0bb14ff629f6f74115627ea0eec013c081e80fbb7b0880a
  strict_mypy: PASS
  compileall: PASS
  wheel_build: PASS
  wheel_sha256: fac6cc513b400b0668038fcb9959260b51a4c1401016a1f1e03252341bbb516a
  generated_evidence_json_sha256: a46d93fe124aed54390540c6da26ef09aa9e70bd1aa1d200a3fa2f7cdf7d4870
  artifact_id: 9941313281
  artifact_sha256: 9399ed9d797de916553a0db298f9e72b46d5150b557e6db742ba10424add59bb
  artifact_size_bytes: 896380
  evidence_commit: 1cd04275ee39dc7d2f8102b4daaa484718a2f974
  evidence_tree: 5043b79b9002619d05c70e14588e7770f09273b7
  evidence_blob_sha: 93f7b982442c9f0f0ccf24571c10e95c24848a08
  evidence_path: docs/project-state/evidence/P3_14_DELIVERY_QUALIFICATION_EVIDENCE.md
  qualification_record_source_commit: cb451cc221993efd5963727866873c2256c1090e
  qualification_record_source_tree: cfcf31f27db642aad1539a5a040f0b5059e828dd
  live_l40s_execution: NOT_RUN
  live_cloudflare_publish: NOT_RUN
  drive_publication: NOT_RUN
  canonical_drive_sync: VERIFIED
  canonical_drive_state_file_id: 1wiWcdWt4hmTf3narsLw4OqGu_ueKOSa4
  canonical_drive_task_file_id: 1liutA8evH6rPjk-U4tgR13l_kqBrx-DF
  drive_evidence_file_id: 1qm2gmf2RWwGelwUa9KUfyUFxrd5GW-Ug
  drive_artifact_file_id: 1Pp2P3-n0pP25PtiMB5Ba46fLfcb22iJf
  github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATH_BLOB_CONFIRMED
  completion_gap: CLOSED
continuation:
  active_task_id: ENG-P4-06
  active_task_title: P4-06 Versioned Production Recipe Learning and System Evidence Summary
  dependency: ENG-P3-14_COMPLETE_DURABLE
  ledger_state: READY_ELIGIBLE
  ledger_claim: NONE
  acceptance_state: LOAD_EXACT_PROMPT_AND_REOBSERVE_CURRENT_SOURCE_AND_EVIDENCE
  execution_started: false
  execution_authorized: true
  spark_or_prep_dependency: NONE
  ordered_frontier: P4-06_THEN_FOUNDATION_COMPLETE_THEN_BIELLA_GAMES
```
