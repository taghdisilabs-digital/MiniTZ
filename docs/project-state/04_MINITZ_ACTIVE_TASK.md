# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 112
program_sha256: 9df5cd3f6a0522ae0ec0f9c9654e85b2748d48357d3cf7cb305582356ad1913d

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: MINITZ-FINAL-CLOSURE-01
  project: MiniTZ
  section: minitz
  class: medium
  title: Close MiniTZ OS only when the one-OS final state is proven
  status: PENDING
  runner: READY
  lane: Engine
  revision: 5
  task_sha256: 01b64348a27aeabb1ec99a2b8e8be9f1f64b18256ab52059f8cfaff99866d5ff

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: MINITZ-OWNER-ACCEPTANCE-01
  predecessor_task_revision: 6
  predecessor_task_sha256: 21dd149a0495522c194507c4e047725bb1526e909a2973926f91a8fc0b34b8e5
  predecessor_program_revision: 111
  predecessor_program_sha256: 6e4058865ad8a240c55a43f4be9964b20a8ce62cdee70369dda67ddeace71ca6
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 1c1442dbfe5b208b5b786dc4ab4a95d921f585565df14872ea06210d2054e0b2

stop: Execute only the current MiniTZ task MINITZ-FINAL-CLOSURE-01; validate and persist before advancing.
```
