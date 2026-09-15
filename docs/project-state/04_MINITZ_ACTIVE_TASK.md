# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 113
program_sha256: cbd5c08fb66f42aa64e454816acd9dd4a25bc1713b47d45914b60a7e33209daa

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
  status: WORKING
  runner: READY
  lane: Engine
  revision: 6
  task_sha256: 0c96033b1c0d570e963adcca177ab1ace7011781482acb18eb4d235d6f50e100

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
