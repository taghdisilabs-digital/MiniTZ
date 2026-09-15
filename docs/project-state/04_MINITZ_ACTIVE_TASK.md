# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 128
program_sha256: 6fe3d1e9c74c516a6e5553c758c7a29e4f40ce3f5dfd1c6dbd6dce3681fd2d46

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

task:
  id: NONE
  project: MiniTZ
  section: NONE
  class: NONE
  title: No active MiniTZ task
  status: COMPLETE
  runner: STOPPED

transition_receipt:
  predecessor_task_id: MINITZ-FINAL-CLOSURE-01
  predecessor_task_revision: 8
  predecessor_task_sha256: d5fff2506163cd5389093153513d6a9bda5eb7ad1077faf7b343c227804495b8
  predecessor_program_revision: 127
  predecessor_program_sha256: 5e35ce190dddeed89ad6f4045c55ee061ee7ae5a2af87c9a87a3100adf376a57
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 48f2107ee44fe51929170dbba458b4c1dfd981fde6e1bd6f8b21718a03612c5f

stop: No active MiniTZ task; validate and persist before advancing.
```
