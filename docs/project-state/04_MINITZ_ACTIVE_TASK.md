# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /state/task-program/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 101
program_sha256: 238c1f1204aa37a8016e4a32cdaedb1e4fdbd335ec6de17ba10006931b8e6712

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
  revision: 1
  task_sha256: f27a7198239b86733774e9c486e38c5bb965737463dc5a30fac85a9edd9da8d3

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: MINITZ-OWNER-ACCEPTANCE-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 9b6cbdaa8f990bc7d6864e52aa6efc8422d414ba68fe969a502cda9c59d2120b
  predecessor_program_revision: 100
  predecessor_program_sha256: 2ebcabfe69efe4d8fcf796a8d62d72701f2e243ecc81972391f485dc57c49953
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: e28e324cf419ef1cff552a1a86025961e8b72c26298cbf0be93cbd3607cd714d

stop: Execute only the current MiniTZ task MINITZ-FINAL-CLOSURE-01; validate and persist before advancing.
```
