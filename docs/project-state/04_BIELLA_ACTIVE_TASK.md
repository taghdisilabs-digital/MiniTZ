# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v6

program_boundary:
  state: ACTIVE
  completed_predecessor: P3-09
  active_numbered_prompt: P3-10
  active_global_number: 41
  active_title: VFX and Simulation Production Pack
  active_prompt_drive_id: 12GmJFm2-6mL7QSjyyaySDWbBi2WrkljUF447XWsHnnI
  execution_started: true
  execution_authorized: true
  authorization_basis: MAHDI_STANDING_P3_06_THROUGH_P4_06
  spark_or_prep_dependency: NONE

P3_09_durable_close:
  status: COMPLETE_DURABLE
  result_commit: 39e51b95de130dddf2e8cde49670257742c0eaac
  result_tree: 772e20442cc4a2113361841614a080678e916685
  github_readback: EXACT_COMMIT_TREE_AND_REQUIRED_PATH_SHA256_CONFIRMED
  engine_run: run_3b6573ba49d140fbb66d09c400148a01
  engine_graph: graph://prj_fa4cdeecc0dc4bbabf8258bf67fc2c77/gph_08abf64d1a5641d787981537221f44ec/1
  validation_aggregate_sha256: 55c72416e31a2ea29049464effc91c9548d38ca776e7ef9d4455c2d7573e9934
  acceptance_event: event://prj_fa4cdeecc0dc4bbabf8258bf67fc2c77/evt_73257ef8a3fb44ba9d440f435bd76b8d
  canonical_drive_evidence_id: 1b0fHOflk3gQCVR2Gt-FdRxj9m2DrZrtY
  qualification_drive_id: 1DGkVgs707kqewC-Q__sGZwzKwp106wvq
  retained_real_drive_id: 1axZ9AI57hN1grrQVTPiGvFgZtES6S5OO
  engine_evidence_drive_id: 12_bAY27t05rz1cmDA40YquOuXc4p16jQ
  drive_readback: EXACT_BYTES_VERIFIED

active_frontier:
  ledger_task_id: ENG-P3-10
  dependency: ENG-P3-09
  ledger_state: READY
  title: P3-10 VFX and Simulation Production Pack durable repair
  exact_prompt_drive_id: 12GmJFm2-6mL7QSjyyaySDWbBi2WrkljUF447XWsHnnI
  completion_gap: full_simulation_adapter_ENOSPC_1_through_300_recovery_and_durable_evidence
  preservation_rule: preserve_unaffected_work_and_reuse_valid_REAL_evidence
  next_action: LOAD_EXACT_P3_10_PROMPT_AND_CLASSIFY_CURRENT_REQUIREMENTS
```
