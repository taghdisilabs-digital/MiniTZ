# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 52
program_sha256: 67be3611e10e3a79943fe600575a35dd472286b2c1ab22e7a86c2d6e4aec790d

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: UNIFY-06
  project: MiniTZ
  section: minitz
  class: hard
  title: Attach EventLedger, CallLedger and live event/failure journals to one MiniTZ evidence/event graph
  status: PENDING
  runner: READY
  lane: Engine
  revision: 5
  task_sha256: 0147f62c77f437ffd40953ddaff92504dbad81d8f2fedf772010d29933952623

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: UNIFY-04
  predecessor_task_revision: 6
  predecessor_task_sha256: 87051b6d2ea4bdb3a721f47c41d4fd7ac7bff996676d2ef5aacdd5e0a87b5cf1
  predecessor_program_revision: 51
  predecessor_program_sha256: 00db40a9a09fc6e6a032ef53410d0a992a72103c493f04e02521ba7ddcc8e82f
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: f29c98bf68288aed5f1f4d7158615c4ae3fe16e4a41c5567929e4413c2acdbf0

stop: Execute only the current MiniTZ task UNIFY-06; validate and persist before advancing.
```
