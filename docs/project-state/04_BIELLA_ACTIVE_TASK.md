# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v6

program_boundary:
  state: ACTIVE
  completed_predecessor: P3-13
  active_numbered_prompt: P3-14
  active_global_number: 45
  active_title: Packaging, Publishing, Release and Durable Delivery Pack
  active_prompt_drive_id: 1mkk0VYh14ut2Tz-7YKcdW35p0GJRtv7bVQeVSPVTzpE
  execution_started: false
  execution_authorized: true
  authorization_basis: MAHDI_STANDING_P3_06_THROUGH_P4_06
  spark_or_prep_dependency: NONE

P3_12_durable_close:
  status: COMPLETE_DURABLE
  repair_commit: c99cb2d57f7dd710e97465fed4d961286b72050c
  repair_tree: e0cf13164bc335342ef4d206569197f03366f710
  closure_commit: 4b7e6b6e48805392fadca69ef02470f6d4c3967d
  closure_tree: a0affdd0b81599c5eb9bb649f46488ed8955adc9
  github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATH_BLOB_CONFIRMED
  github_actions: 33549462937/SUCCESS
  github_artifact: 9817199535
  engine_run: run_20eb839e899c47428de78b991d319640
  engine_graph: graph://prj_508b975a98994bfb9dc6331ade2b2c11/gph_f062ff81113b48359b3c1f5be6fb9f5d/1
  retained_artifact: artifact://prj_508b975a98994bfb9dc6331ade2b2c11/art_be13bca5301945fbb98162a44a8ccc79/1
  validation_aggregate_sha256: 96f256154e7ab55678e8235864513a072a08df0a0d84319fa7463b7d034071dc
  acceptance_event: event://prj_508b975a98994bfb9dc6331ade2b2c11/evt_2734b8e54fdc47c18f7eeaee258de95e
  retained_archive_sha256: 2ec11b1fe23b9fd49aed4dbc4e31ad709fb56aac0dbbf19a4b6e292499d290f1
  canonical_drive_evidence_id: 1wPyWGSF9OpB9L47ZXOqECR1mtlcq_SMY
  retained_real_drive_id: 1RJFzKm16qIsYkHpyEDpzQn-QQwd7ll0A
  engine_evidence_drive_id: 10Ld2FhHzqvrHQxJBxv9MKPO4zWZKnsoV
  l40s_receipt_drive_id: 15Q_msefmw9EEcTczQV4sUjb_puYxFIkS
  github_ci_evidence_drive_id: 1829aDK2YRrF1ccBzx_V6IbxnSR83ZyvM
  drive_readback: EXACT_BYTES_AND_CANONICAL_LEDGER_VERIFIED

P3_13_durable_close:
  status: COMPLETE_DURABLE
  completed_at_utc: 2026-09-01T20:50:10Z
  repair_commit: 8133a5408babc142602f93e1af22cf8eb258a9db
  repair_tree: c1679d62ba3f7ad65143292a0b2dbd282ae37603
  workflow_qualification_commit: fef638d87ec0799e7f94d806cf01da307c5e543d
  workflow_qualification_tree: 566fa04e3cf080a96a44f9bab16d2785fc60d692
  github_actions_run: 33554959677
  github_actions_artifact: 9819033703
  canonical_drive_evidence_id: 15XWGE_7cSrXyDShiXmhFOqG5WbT1CSTg
  retained_real_drive_id: 11y5PsDydFy47HOuuk7oRaXYD5700Eyr9
  retained_archive_sha256: 32152eab780d65d27231f25d6f12993d16509d3065597bf1e5d2ee841efcf31f
  retained_archive_size_bytes: 1269361
  engine_evidence_drive_id: 1NK1k_Cu3g4lTQCkG6f9_x2aTEZPG4lwA
  engine_evidence_sha256: 8ec7e88ea6500cea9f94bbad8187e9dce771bbb356cbf03cc06a10c20b7d122f
  engine_run: run_7dea687cfafe409bb132f7ff68fbd8e4
  engine_run_status: SUCCEEDED
  engine_graph: graph://prj_de760e9b27764d0f8754f7bcecc31c47/gph_f189fc9a80c94bb881bdc2a1a1b36157/1
  validation_aggregate_sha256: 88adf5cc6cc6448e7fe2f3bfd6b4ca86e2d9d1c6a98da5d7fd1c10971f088707
  validation_status: PASS
  validation_freshness: CURRENT
  evidence_event: event://prj_de760e9b27764d0f8754f7bcecc31c47/evt_30faa1b561ff4aa589558e01ddedc8c6
  acceptance_event: event://prj_de760e9b27764d0f8754f7bcecc31c47/evt_3e4732a151834e53bcadd2849f367dda
  l40s_package_gate: PASS
  six_kpis: ZERO
  ledger_readback: P3-13_COMPLETE; P3-14_READY

active_frontier:
  ledger_task_id: ENG-P3-14
  dependency: ENG-P3-13
  ledger_state: READY_ELIGIBLE
  ledger_claim: NONE
  execution_started: false
  acceptance_state: LOAD_EXACT_PROMPT_AND_REOBSERVE_CURRENT_SOURCE_AND_EVIDENCE
  title: P3-14 Packaging, Publishing, Release and Durable Delivery durable repair
  exact_prompt_drive_id: 1mkk0VYh14ut2Tz-7YKcdW35p0GJRtv7bVQeVSPVTzpE
  completion_gap: phase_exit_provenance_Event_and_delivery_evidence
  preservation_rule: preserve_current_source_and_reuse_valid_REAL_evidence_when_inputs_are_unchanged
  next_action: LOAD_EXACT_PROMPT_AND_REOBSERVE_CURRENT_SOURCE_AND_EVIDENCE
  p4_reuse: P4-01_THROUGH_P4-05_COMPLETE_DO_NOT_REBUILD
  ordered_successors: REUSE_P4-01_THROUGH_P4-05_THEN_P4-06_THEN_FOUNDATION_COMPLETE_THEN_BIELLA_GAMES
```
