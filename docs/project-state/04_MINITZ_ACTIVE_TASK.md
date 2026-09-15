# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /state/task-program/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 97
program_sha256: 65d5050ec91f8c7893467e29122367c2e8645e4acafd6f8d5a5c859e68d04490

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: MINITZ-SYSTEM-QUALIFY-01
  project: MiniTZ
  section: minitz
  class: medium
  title: Qualify the complete MiniTZ OS and exact boot artifact
  status: PENDING
  runner: READY
  lane: Engine
  revision: 1
  task_sha256: 685e3ced62fb2c62639454b5032b3a1754cf2a6852dd1afbfbecfe1555b319c1

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

stop: Execute only the current MiniTZ task MINITZ-SYSTEM-QUALIFY-01; validate and persist before advancing.
```
