# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v6

program_boundary:
  state: ACTIVE
  completed_predecessor: P3-11
  active_numbered_prompt: P3-12
  active_global_number: 43
  active_title: Audio Production, Processing, Mixing and Validation Pack
  active_prompt_drive_id: 1c8GEF9Z6pL9JKMkhXx6ZtsbcKnI5b_jY4k27ie3L1HI
  execution_started: true
  execution_authorized: true
  authorization_basis: MAHDI_STANDING_P3_06_THROUGH_P4_06
  spark_or_prep_dependency: NONE

P3_11_durable_close:
  status: COMPLETE_DURABLE
  implementation_commit: 31c4aab5a72eaa8763d84537308c6ded7da23a73
  implementation_tree: 76593cefa6ed18669443e11dfaa31b7a5f7c4542
  workflow_commit: dfc20b302c4b1cb6ed6c8c0de8c74f5fd5cdb39b
  workflow_tree: 0de9fbd58db0b62c3abc9fe98685000cb37e0299
  closure_commit: 117ee12c9eb5fa7da26148506f2701ad169890f5
  closure_tree: eb2777d371349b46115fafb18a945e21d1962104
  github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATH_BLOB_CONFIRMED
  engine_run: run_0001925f6b014896af64188d53062cb1
  engine_graph: graph://prj_659da64f27c742c1a7055a2dafa728af/gph_3d3cbe85d9084f0aa429861fb343e247/1
  retained_artifact: artifact://prj_659da64f27c742c1a7055a2dafa728af/art_0bede7439ee24111b53cc706a40a6439/1
  validation_aggregate_sha256: 3b9576c157cbb6eb7ba6253926bd6ba764114f26d496229386b85d19baac2808
  acceptance_event: event://prj_659da64f27c742c1a7055a2dafa728af/evt_5770a8c8ba5b4554a2d6e3fc4c8b9566
  canonical_drive_evidence_id: 1Cd14c7J0wrxqIVAbDJT2IgjYFpGOCW1rXboUe6stny0
  qualification_drive_id: 13F5MskYW_lKpkaa_HWGwpbQceN_6Jgp0
  retained_real_drive_id: 1V-NGZHsh4bF8_lMW5jTnIdBb34qsGWMx
  engine_evidence_drive_id: 11KmLmp_Wp99n96bu6yR00jacqYdfJdYS
  drive_readback: EXACT_BYTES_AND_CANONICAL_DOC_VERIFIED

active_frontier:
  ledger_task_id: ENG-P3-12
  dependency: ENG-P3-11
  ledger_claim: COMPLETE
  acceptance_state: REOBSERVE_REQUIRED
  title: P3-12 Audio Production, Processing, Mixing and Validation Pack durable repair
  exact_prompt_drive_id: 1c8GEF9Z6pL9JKMkhXx6ZtsbcKnI5b_jY4k27ie3L1HI
  completion_gap: durable_audio_production_evidence
  preservation_rule: preserve_current_source_and_reuse_valid_REAL_evidence_when_inputs_are_unchanged
  next_action: LOAD_EXACT_P3_12_PROMPT_AND_CLASSIFY_CURRENT_REQUIREMENTS
  p4_reuse: P4-01_THROUGH_P4-05_COMPLETE_DO_NOT_REBUILD
  ordered_successors: P3-13_THEN_P3-14_THEN_REUSE_P4-01_THROUGH_P4-05_THEN_P4-06_THEN_FOUNDATION_COMPLETE_THEN_BIELLA_GAMES
```
