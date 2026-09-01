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
    implementation_commit: 3a9c325ab821046e6a702011a213f2d9558dad16
    implementation_tree: 16b6eee8eb6fa16c6f8e234c566dbe0ef95b0113
    closure_commit: ccc32dbb2ad3cc9140845da14d0ff3e502650fa3
    closure_tree: 441ac66afaf00fae4bd1d761e4d0e901057ae442
    meaning: P3_10_COMPLETE_DURABLE
    github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATH_SHA256_CONFIRMED
    preserved_later_work_completion_authority: false
  preserved_worktree:
    path: src/biella/production_recipe_learning.py
    sha256: 01879237ebac6c96b985b0b05f822897d25b6f2dd9f8f13952e38d7e93cd5d2d
    meaning: INDEPENDENT_P4_06_PRODUCTIVE_WORK; NOT_PART_OF_P3_10

numbered_execution:
  durable_prompts_complete: 46
  durable_prompts_total: 51
  progress: "46 / 51 durable; non-contiguous audited; active repair frontier 42"
  phase: P3_DURABLE_REPAIR
  just_closed_prompt: P3-10
  just_closed_global_number: 41
  active_prompt: P3-11
  active_global_number: 42
  active_title: Image Production, Editing, Compositing and Texture Pack
  active_drive_prompt_id: 1hZm2VC3xYefqwZBxvIhsChrIjCLcZXsTSoOCG3IKLhM
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
  P3_11: {durable_close: REOBSERVE_PRESERVED_COMPLETE_CLAIM, audit_gap: durable_image_production_evidence}
  P3_12: {durable_close: INCOMPLETE, missing: durable_audio_production_evidence}
  P3_13: {durable_close: INCOMPLETE, missing: six_KPI_report_correction_and_durable_media_video_evidence}
  P3_14: {durable_close: INCOMPLETE, missing: phase_exit_provenance_Event_and_delivery_evidence}
  P4_01_through_P4_05: {durable_close: COMPLETE, reuse: REQUIRED}
  P4_06: {durable_close: INCOMPLETE, missing: authoritative_Engine_evidence_and_combined_failure_scenario}

p3_10_durable_close:
  exact_prompt_drive_id: 12GmJFm2-6mL7QSjyyaySDWbBi2WrkljUF447XWsHnnI
  implementation_commit: 3a9c325ab821046e6a702011a213f2d9558dad16
  implementation_tree: 16b6eee8eb6fa16c6f8e234c566dbe0ef95b0113
  closure_commit: ccc32dbb2ad3cc9140845da14d0ff3e502650fa3
  closure_tree: 441ac66afaf00fae4bd1d761e4d0e901057ae442
  github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATH_SHA256_CONFIRMED
  real_execution:
    archive_sha256: 0c34a996833be4dc8ffdb6263c569293840a4d09367978f445ddc6a2abf7761b
    archive_size_bytes: 1090235
    qualification: SIX_REAL_CHECKPOINTS; ENOSPC_RECOVERY; BAKE; PREVIEW; GLB; EXACT_GODOT_BIND; FORGED_REJECT
  engine_evidence:
    project_ref: prj_f0e75ef71b964949897f5c0fbc8db0d7
    task_ref: tsk_93b6eedef56f4830af846fe693f79952/1
    run_ref: run_bfa1a18ffeff4a1eacb8355fb9cb5955
    run_status: SUCCEEDED
    graph_ref: graph://prj_f0e75ef71b964949897f5c0fbc8db0d7/gph_9853a1a21ba441eab101e4109933e344/1
    retained_artifact_ref: artifact://prj_f0e75ef71b964949897f5c0fbc8db0d7/art_5bc4a19a1abf41e6853f813f487aee08/1
    validation_aggregate_sha256: 3b17909e017cfcc35b8af78520615a3aa2ab47281360a0f5c9bd614af9925eb2
    evidence_event_ref: event://prj_f0e75ef71b964949897f5c0fbc8db0d7/evt_ddd7fd35a8234b01919cec18cbc7bca7
    acceptance_event_ref: event://prj_f0e75ef71b964949897f5c0fbc8db0d7/evt_a0cc38b49fdf4ab48a4e9b7fada35564
  kpis:
    simulation_cache_used_as_only_authority: 0
    verified_segments_lost_after_failure: 0
    incompatible_checkpoint_resumes: 0
    dependent_solver_steps_parallelized_incorrectly: 0
    global_GPU_requirement_for_VFX: 0
  drive_evidence:
    canonical_evidence_id: 1_VXkRE-gQ3BRkrDO_UQk9Nl8qteczSAFm6Kl_hBsd2Y
    qualification_id: 1PsP12KJZO8k1RAiuweQ53MrGuSWR_fD1
    retained_real_archive_id: 1qxW-e8-szAsGWzwtOr5qlohBj3VIOnoT
    engine_evidence_id: 1wPdPhvf4wv-AmYdB_8RzoOiXJckukyj1
    wheel_id: 1G-Y8vbuE-TkjPS_r27fpKun6NarHh8Un
    wheel_qualification_id: 1oehemrHP28ZvRx8BPQLRokuv6KqxKiT8
    exact_byte_readback: VERIFIED

continuation:
  active_task_id: ENG-P3-11
  active_task_title: P3-11 Image Production, Editing, Compositing and Texture Pack durable repair
  dependency: ENG-P3-10_COMPLETE
  ledger_claim: COMPLETE
  acceptance_state: REOBSERVE_EXACT_PROMPT_AND_CURRENT_EVIDENCE
  execution_started: true
  spark_or_prep_dependency: NONE
```
