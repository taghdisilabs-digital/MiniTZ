# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 127
program_sha256: 5e35ce190dddeed89ad6f4045c55ee061ee7ae5a2af87c9a87a3100adf376a57

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
  revision: 8
  task_sha256: d5fff2506163cd5389093153513d6a9bda5eb7ad1077faf7b343c227804495b8

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: MINITZ-BOOTABLE-IMAGE-01
  predecessor_task_revision: 4
  predecessor_task_sha256: ac02353555b069e178e697845b4f86e158b6aaa6acd72f9add19d8e18e6cbc91
  predecessor_program_revision: 96
  predecessor_program_sha256: dbb227888d2745eec7ff7cd47b78a4782955f9fb76b76240bf1078c4419f98d3
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 9daeb28d2eedca3db09615624c4d492a2477a0246846b9e4f42acd1d70414cbd

stop: Execute only the current MiniTZ task MINITZ-FINAL-CLOSURE-01; validate and persist before advancing.
```
