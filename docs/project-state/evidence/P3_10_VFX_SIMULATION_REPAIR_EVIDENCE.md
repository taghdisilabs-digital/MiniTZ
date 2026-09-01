# P3-10 VFX and simulation durable repair evidence

```yaml
schema: biella.evidence/p3_10_vfx_simulation_repair/v3
observed_at_utc: 2026-09-01T17:26:01Z
status: COMPLETE_DURABLE
prompt: P3-10
exact_prompt_drive_id: 12GmJFm2-6mL7QSjyyaySDWbBi2WrkljUF447XWsHnnI

source:
  result_commit: 3a9c325ab821046e6a702011a213f2d9558dad16
  result_tree: 16b6eee8eb6fa16c6f8e234c566dbe0ef95b0113
  github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATH_SHA256_CONFIRMED

real_execution:
  archive_sha256: 0c34a996833be4dc8ffdb6263c569293840a4d09367978f445ddc6a2abf7761b
  archive_size_bytes: 1090235
  checkpoint_count: 6
  branches: 2
  ranges_per_branch: [1-100, 101-200, 201-300]
  injected_failure: ENOSPC_AT_FRAME_201
  recovery: VERIFIED_PREFIX_PRESERVED; STALE_ATTEMPT_REJECTED; FRESH_FENCE_RESUMED_201_300
  outputs: COMPLETE_BAKE; BLENDER_PREVIEW_256X256; GLB; EXACT_GODOT_BIND; FORGED_BIND_REJECTED
  cache_deletion: AUTHORITATIVE_SPEC_CHECKPOINT_BAKE_AND_HANDOFFS_SURVIVED
  l40s_post_state: NO_BLENDER_GODOT_COLLECTOR_OR_GPU_PROCESS; VRAM_ZERO
  gpu_claim: NONE

engine_evidence:
  project_ref: prj_f0e75ef71b964949897f5c0fbc8db0d7
  task_ref: tsk_93b6eedef56f4830af846fe693f79952/1
  run_ref: run_bfa1a18ffeff4a1eacb8355fb9cb5955
  run_status: SUCCEEDED
  graph_ref: graph://prj_f0e75ef71b964949897f5c0fbc8db0d7/gph_9853a1a21ba441eab101e4109933e344/1
  retained_artifact_ref: artifact://prj_f0e75ef71b964949897f5c0fbc8db0d7/art_5bc4a19a1abf41e6853f813f487aee08/1
  retained_content_ref: content://sha256/0c34a996833be4dc8ffdb6263c569293840a4d09367978f445ddc6a2abf7761b?size=1090235
  integration_artifact_ref: artifact://prj_f0e75ef71b964949897f5c0fbc8db0d7/art_ce0599faad634b41a187dd31abd2b647/1
  validation_plan_ref: validation-plan://prj_f0e75ef71b964949897f5c0fbc8db0d7/vplan_03b64b1c46be4426875f4e7342647933
  validation_results: 10
  validation_aggregate_sha256: 3b17909e017cfcc35b8af78520615a3aa2ab47281360a0f5c9bd614af9925eb2
  validation_aggregate_status: PASS_ACCEPTED
  evidence_event_ref: event://prj_f0e75ef71b964949897f5c0fbc8db0d7/evt_ddd7fd35a8234b01919cec18cbc7bca7
  acceptance_event_ref: event://prj_f0e75ef71b964949897f5c0fbc8db0d7/evt_a0cc38b49fdf4ab48a4e9b7fada35564

qualification:
  recovery_authority_tests: 9_PASS
  real_blender_regression: 6_PASS_IN_261_55_SECONDS
  durable_importer: 7_PASS_PLUS_PACKAGE_BACKED_1_PASS
  installed_wheel: 17_PASS_1_HONEST_ENVIRONMENT_SKIP
  strict_mypy: PASS
  github_actions_run: 33534787712
  github_actions_status: SUCCESS
  wheel_sha256: c39b52957506241ba686542230bdb5a2b3456a76686f0e53fd78051af17ebe6c

kpis:
  simulation_cache_used_as_only_authority: 0
  verified_segments_lost_after_failure: 0
  incompatible_checkpoint_resumes: 0
  dependent_solver_steps_parallelized_incorrectly: 0
  global_GPU_requirement_for_VFX: 0

drive:
  canonical_evidence_id: 1_VXkRE-gQ3BRkrDO_UQk9Nl8qteczSAFm6Kl_hBsd2Y
  qualification_id: 1PsP12KJZO8k1RAiuweQ53MrGuSWR_fD1
  real_archive_id: 1qxW-e8-szAsGWzwtOr5qlohBj3VIOnoT
  engine_evidence_id: 1wPdPhvf4wv-AmYdB_8RzoOiXJckukyj1
  wheel_id: 1G-Y8vbuE-TkjPS_r27fpKun6NarHh8Un
  wheel_qualification_id: 1oehemrHP28ZvRx8BPQLRokuv6KqxKiT8
  collector_result_id: 1yUE3v_DxXTs90o3_fBpwQ0-dYe-1sniW
  runtime_descriptor_id: 1m2SOCfhBOBeDYKHX-DtIxX2rARQLgjD7
  transfer_manifest_id: 1EowDp9qUwoqnR6SzMnBhFyE8zw_1E1OB
  canonical_content_readback: VERIFIED
  artifact_exact_byte_readback: VERIFIED

known_fact:
  blend_serialization: NON_BYTE_DETERMINISTIC_ACROSS_PROCESSES
  canonical_solver_state_and_artifact_provenance: DETERMINISTIC_AND_VALIDATED
```
