# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v6

program_boundary:
  state: ACTIVE
  completed_predecessor: P3-10
  active_numbered_prompt: P3-11
  active_global_number: 42
  active_title: Image Production, Editing, Compositing and Texture Pack
  active_prompt_drive_id: 1hZm2VC3xYefqwZBxvIhsChrIjCLcZXsTSoOCG3IKLhM
  execution_started: true
  execution_authorized: true
  authorization_basis: MAHDI_STANDING_P3_06_THROUGH_P4_06
  spark_or_prep_dependency: NONE

P3_10_durable_close:
  status: COMPLETE_DURABLE
  implementation_commit: 3a9c325ab821046e6a702011a213f2d9558dad16
  implementation_tree: 16b6eee8eb6fa16c6f8e234c566dbe0ef95b0113
  closure_commit: ccc32dbb2ad3cc9140845da14d0ff3e502650fa3
  closure_tree: 441ac66afaf00fae4bd1d761e4d0e901057ae442
  github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATH_SHA256_CONFIRMED
  engine_run: run_bfa1a18ffeff4a1eacb8355fb9cb5955
  engine_graph: graph://prj_f0e75ef71b964949897f5c0fbc8db0d7/gph_9853a1a21ba441eab101e4109933e344/1
  retained_artifact: artifact://prj_f0e75ef71b964949897f5c0fbc8db0d7/art_5bc4a19a1abf41e6853f813f487aee08/1
  validation_aggregate_sha256: 3b17909e017cfcc35b8af78520615a3aa2ab47281360a0f5c9bd614af9925eb2
  acceptance_event: event://prj_f0e75ef71b964949897f5c0fbc8db0d7/evt_a0cc38b49fdf4ab48a4e9b7fada35564
  canonical_drive_evidence_id: 1_VXkRE-gQ3BRkrDO_UQk9Nl8qteczSAFm6Kl_hBsd2Y
  qualification_drive_id: 1PsP12KJZO8k1RAiuweQ53MrGuSWR_fD1
  retained_real_drive_id: 1qxW-e8-szAsGWzwtOr5qlohBj3VIOnoT
  engine_evidence_drive_id: 1wPdPhvf4wv-AmYdB_8RzoOiXJckukyj1
  drive_readback: EXACT_BYTES_VERIFIED

active_frontier:
  ledger_task_id: ENG-P3-11
  dependency: ENG-P3-10
  ledger_claim: COMPLETE
  acceptance_state: REOBSERVE_REQUIRED
  title: P3-11 Image Production, Editing, Compositing and Texture Pack durable repair
  exact_prompt_drive_id: 1hZm2VC3xYefqwZBxvIhsChrIjCLcZXsTSoOCG3IKLhM
  completion_gap: durable_image_production_evidence
  preservation_rule: preserve_current_source_and_reuse_valid_REAL_evidence_when_inputs_are_unchanged
  next_action: LOAD_EXACT_P3_11_PROMPT_AND_CLASSIFY_CURRENT_REQUIREMENTS
```
