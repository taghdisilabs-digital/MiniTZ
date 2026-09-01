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
    commit: 39e51b95de130dddf2e8cde49670257742c0eaac
    tree: 772e20442cc4a2113361841614a080678e916685
    meaning: P3_09_COMPLETE_DURABLE_MERGED_RESULT
    github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATH_SHA256_CONFIRMED
  preserved_later_source:
    commit: b7a55142edea7de895f799b8bef074a2a02d916d
    tree: 6df2a4d4f04246713220aa2461a10e33ba1b93d1
    meaning: PRESERVED_ACCEPTED_LATER_SOURCE; NOT_FOUNDATION_COMPLETION_AUTHORITY
  preserved_worktree:
    path: src/biella/production_recipe_learning.py
    sha256: 01879237ebac6c96b985b0b05f822897d25b6f2dd9f8f13952e38d7e93cd5d2d
    meaning: INDEPENDENT_P4_06_PRODUCTIVE_WORK; NOT_PART_OF_P3_09

numbered_execution:
  durable_prompts_complete: 45
  durable_prompts_total: 51
  progress: "45 / 51 durable; non-contiguous audited; active repair frontier 41"
  phase: P3_DURABLE_REPAIR
  just_closed_prompt: P3-09
  just_closed_global_number: 40
  active_prompt: P3-10
  active_global_number: 41
  active_title: VFX and Simulation Production Pack
  active_drive_prompt_id: 12GmJFm2-6mL7QSjyyaySDWbBi2WrkljUF447XWsHnnI
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
  P3_10: {durable_close: INCOMPLETE, missing: full_simulation_adapter_ENOSPC_1_through_300_recovery_and_durable_evidence}
  P3_11: {durable_close: INCOMPLETE, missing: durable_image_production_evidence}
  P3_12: {durable_close: INCOMPLETE, missing: durable_audio_production_evidence}
  P3_13: {durable_close: INCOMPLETE, missing: six_KPI_report_correction_and_durable_media_video_evidence}
  P3_14: {durable_close: INCOMPLETE, missing: phase_exit_provenance_Event_and_delivery_evidence}
  P4_01_through_P4_05: {durable_close: COMPLETE, reuse: REQUIRED}
  P4_06: {durable_close: INCOMPLETE, missing: authoritative_Engine_evidence_and_combined_failure_scenario}

p3_09_durable_close:
  exact_prompt_drive_id: 1FYsaztU8wwjl_6k8Nx4xJII4wId-MPflkLFUNwW4gRM
  result_commit: 39e51b95de130dddf2e8cde49670257742c0eaac
  result_tree: 772e20442cc4a2113361841614a080678e916685
  implementation:
    provider_neutral_contract: src/biella/render_pack.py
    blender_and_reference_adapters: src/biella/render_tool.py
    blender_driver: src/biella/_blender_render_driver.py
    duplicate_adapter_module: ABSENT
  real_execution:
    renderer_a: renderer://blender
    runtime_a: runtime://host/blender-5.0.1-cpu
    renderer_b: renderer://reference/v1
    output_count: 10
    final_frame_pass_outputs: 9
    recovery: INJECTED_FRAME_3_NORMAL_LOSS; EIGHT_PRESERVED; ONE_RESUMED
  engine_evidence:
    project_ref: prj_fa4cdeecc0dc4bbabf8258bf67fc2c77
    task_ref: tsk_c6c2af75925e4b12a0ccdcb6d2caeb56/1
    run_ref: run_3b6573ba49d140fbb66d09c400148a01
    run_status: SUCCEEDED
    graph_ref: graph://prj_fa4cdeecc0dc4bbabf8258bf67fc2c77/gph_08abf64d1a5641d787981537221f44ec/1
    integration_artifact_ref: artifact://prj_fa4cdeecc0dc4bbabf8258bf67fc2c77/art_69abdc0500c14d269446f8952058159f/1
    validation_aggregate_sha256: 55c72416e31a2ea29049464effc91c9548d38ca776e7ef9d4455c2d7573e9934
    event_ref: event://prj_fa4cdeecc0dc4bbabf8258bf67fc2c77/evt_f28b2e1bb85a48a29a52a9343fd208e3
    acceptance_event_ref: event://prj_fa4cdeecc0dc4bbabf8258bf67fc2c77/evt_73257ef8a3fb44ba9d440f435bd76b8d
  kpis:
    renderer_specific_kernel_fields: 0
    verified_frames_lost_after_failure: 0
    completed_frames_rerendered_due_only_to_restart: 0
    mixed_scene_versions_in_sequence: 0
    render_claimed_success_with_missing_output: 0
  qualification:
    strict_mypy: PASS
    focused_contract_tests: 7_PASS
    blender_5_data_pass_tests: 2_PASS
    durable_import_tests: 7_PASS
    installed_wheel_tests: 7_PASS
    project_isolation: PASS
    source_contamination: PASS
  l40s:
    status: RESOURCE_UNAVAILABLE
    cause: PRODUCTION_BWRAP_NAMESPACE_CANNOT_INITIALIZE_CUDA_OPTIX
    false_success_claimed: false
    p3_09_blocker: false
  drive_evidence:
    canonical_evidence_id: 1b0fHOflk3gQCVR2Gt-FdRxj9m2DrZrtY
    qualification_id: 1DGkVgs707kqewC-Q__sGZwzKwp106wvq
    retained_real_archive_id: 1axZ9AI57hN1grrQVTPiGvFgZtES6S5OO
    engine_evidence_id: 12_bAY27t05rz1cmDA40YquOuXc4p16jQ
    wheel_id: 1FDf2hihsJHwzk-DZxvf5-aw8VWL2Ybo6
    wheel_qualification_id: 1f9vOvSCHvnU5whULsGuYNQMrGI2mc0KY
    l40s_resource_evidence_id: 1lU_gM2cDHResm9ppb6RP4EkQIDI5j8ht
    exact_byte_readback: VERIFIED

continuation:
  active_task_id: ENG-P3-10
  active_task_title: P3-10 VFX and Simulation Production Pack durable repair
  dependency: ENG-P3-09_COMPLETE
  ledger_state: READY
  execution_started: true
  spark_or_prep_dependency: NONE
```
