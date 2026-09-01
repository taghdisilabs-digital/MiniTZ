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
    implementation_commit: 31c4aab5a72eaa8763d84537308c6ded7da23a73
    implementation_tree: 76593cefa6ed18669443e11dfaa31b7a5f7c4542
    workflow_commit: dfc20b302c4b1cb6ed6c8c0de8c74f5fd5cdb39b
    workflow_tree: 0de9fbd58db0b62c3abc9fe98685000cb37e0299
    closure_commit: 117ee12c9eb5fa7da26148506f2701ad169890f5
    closure_tree: eb2777d371349b46115fafb18a945e21d1962104
    meaning: P3_11_COMPLETE_DURABLE
    github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATH_BLOB_CONFIRMED
    preserved_later_work_completion_authority: false
  preserved_worktree:
    path: src/biella/production_recipe_learning.py
    sha256: 01879237ebac6c96b985b0b05f822897d25b6f2dd9f8f13952e38d7e93cd5d2d
    meaning: INDEPENDENT_P4_06_PRODUCTIVE_WORK; NOT_PART_OF_P3_11

numbered_execution:
  durable_prompts_complete: 47
  durable_prompts_total: 51
  progress: "47 / 51 durable; non-contiguous audited; active repair frontier 43"
  phase: P3_DURABLE_REPAIR
  just_closed_prompt: P3-11
  just_closed_global_number: 42
  active_prompt: P3-12
  active_global_number: 43
  active_title: Audio Production, Processing, Mixing and Validation Pack
  active_drive_prompt_id: 1c8GEF9Z6pL9JKMkhXx6ZtsbcKnI5b_jY4k27ie3L1HI
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
  P3_12: {durable_close: INCOMPLETE, missing: durable_audio_production_evidence}
  P3_13: {durable_close: INCOMPLETE, missing: six_KPI_report_correction_and_durable_media_video_evidence}
  P3_14: {durable_close: INCOMPLETE, missing: phase_exit_provenance_Event_and_delivery_evidence}
  P4_01_through_P4_05: {durable_close: COMPLETE, reuse: REQUIRED}
  P4_06: {durable_close: INCOMPLETE, missing: authoritative_Engine_evidence_and_combined_failure_scenario}

p3_11_durable_close:
  exact_prompt_drive_id: 1hZm2VC3xYefqwZBxvIhsChrIjCLcZXsTSoOCG3IKLhM
  implementation_commit: 31c4aab5a72eaa8763d84537308c6ded7da23a73
  implementation_tree: 76593cefa6ed18669443e11dfaa31b7a5f7c4542
  workflow_commit: dfc20b302c4b1cb6ed6c8c0de8c74f5fd5cdb39b
  workflow_tree: 0de9fbd58db0b62c3abc9fe98685000cb37e0299
  closure_commit: 117ee12c9eb5fa7da26148506f2701ad169890f5
  closure_tree: eb2777d371349b46115fafb18a945e21d1962104
  github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATH_BLOB_CONFIRMED
  real_execution:
    retained_archive_sha256: 98ee595b2ecfe338e42aec2f14ced8f6ee353a6600880936e12f38c374c05594
    retained_archive_size_bytes: 381904
    l40s_outputs: 10_EXACT_OPERATIONS; 10_DISTINCT_CONTENT_REFS
    true_concurrency: PRODUCER_FENCE_2; MEASURED_MAXIMUM_2
    cloudflare_generate_edit: 2_OF_2_PASS
    cloudflare_decode: 4_OF_4_PASS
    l40s_truth: CPU_PILLOW_ON_L40S; NO_GPU_SUCCESS_CLAIM
  engine_evidence:
    project_ref: prj_659da64f27c742c1a7055a2dafa728af
    task_ref: tsk_778f76e7a8714420a6daac44783b940a/1
    run_ref: run_0001925f6b014896af64188d53062cb1
    run_status: SUCCEEDED
    graph_ref: graph://prj_659da64f27c742c1a7055a2dafa728af/gph_3d3cbe85d9084f0aa429861fb343e247/1
    retained_artifact_ref: artifact://prj_659da64f27c742c1a7055a2dafa728af/art_0bede7439ee24111b53cc706a40a6439/1
    integration_artifact_ref: artifact://prj_659da64f27c742c1a7055a2dafa728af/art_02b355aeef8e418ab08cb97ba394e9a0/1
    validation_aggregate_sha256: 3b9576c157cbb6eb7ba6253926bd6ba764114f26d496229386b85d19baac2808
    evidence_event_ref: event://prj_659da64f27c742c1a7055a2dafa728af/evt_ecbfd621696d444384f73eed61acaf33
    acceptance_event_ref: event://prj_659da64f27c742c1a7055a2dafa728af/evt_5770a8c8ba5b4554a2d6e3fc4c8b9566
  kpis:
    corrupt_image_accepted: 0
    source_image_destructively_mutated: 0
    project_visual_style_globalized: 0
    texture_channel_convention_implicit: 0
    color_space_silently_changed: 0
    provider_specific_image_kernel_architecture: 0
  drive_evidence:
    canonical_evidence_id: 1Cd14c7J0wrxqIVAbDJT2IgjYFpGOCW1rXboUe6stny0
    qualification_id: 13F5MskYW_lKpkaa_HWGwpbQceN_6Jgp0
    retained_real_archive_id: 1V-NGZHsh4bF8_lMW5jTnIdBb34qsGWMx
    engine_evidence_id: 11KmLmp_Wp99n96bu6yR00jacqYdfJdYS
    wheel_id: 1Ti5UwwGbLnXDMxUSPQQ7wyMzAekzXrpA
    cloudflare_qualification_id: 1XOVDcD3oQjAMf2E45M9Pmi3F81hDUs2E
    exact_byte_readback: VERIFIED

continuation:
  active_task_id: ENG-P3-12
  active_task_title: P3-12 Audio Production, Processing, Mixing and Validation Pack durable repair
  dependency: ENG-P3-11_COMPLETE
  ledger_claim: COMPLETE
  acceptance_state: LOAD_EXACT_PROMPT_AND_REOBSERVE_CURRENT_SOURCE_AND_EVIDENCE
  execution_started: true
  spark_or_prep_dependency: NONE
  ordered_frontier: P3-12_THEN_P3-13_THEN_P3-14_THEN_REUSE_P4-01_THROUGH_P4-05_THEN_P4-06_THEN_FOUNDATION_COMPLETE_THEN_BIELLA_GAMES
```
