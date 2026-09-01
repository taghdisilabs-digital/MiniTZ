# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v6

program_boundary:
  state: ACTIVE
  completed_predecessor: P3-12
  active_numbered_prompt: P3-13
  active_global_number: 44
  active_title: Video Production, Editing, Compositing and Media Pipeline Pack
  active_prompt_drive_id: 12_Z1RrJBW8fGVj5z76wnaphozu8J2DjSrHd2gJVrbmA
  execution_started: true
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

active_frontier:
  ledger_task_id: ENG-P3-13
  dependency: ENG-P3-12
  ledger_claim: RUNNING
  acceptance_state: SOURCE_REPAIR_AND_REAL_EVIDENCE_EXECUTION
  title: P3-13 Video Production, Editing, Compositing and Media Pipeline durable repair
  exact_prompt_drive_id: 12_Z1RrJBW8fGVj5z76wnaphozu8J2DjSrHd2gJVrbmA
  completion_gap: six_KPI_report_correction_and_durable_media_video_evidence
  preservation_rule: preserve_current_source_and_reuse_valid_REAL_evidence_when_inputs_are_unchanged
  next_action: LOAD_EXACT_P3_13_PROMPT_AND_CLASSIFY_CURRENT_REQUIREMENTS
  p4_reuse: P4-01_THROUGH_P4-05_COMPLETE_DO_NOT_REBUILD
  ordered_successors: P3-14_THEN_REUSE_P4-01_THROUGH_P4-05_THEN_P4-06_THEN_FOUNDATION_COMPLETE_THEN_BIELLA_GAMES
```
