# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /state/task-program/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 135
program_sha256: 18f0a071f33620774f0ec1ed429ff938ae5e7bc21739a5f313ebb0e77cdf4f10

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: D17-03
  project: MiniTZ
  section: minitz
  class: medium
  title: Prove combat feel and consequence chain
  status: PENDING
  runner: READY
  lane: Games
  revision: 1
  task_sha256: b790a40977db8a36d3948bbe2a43eaffea3735341a4c29fe092e9d8e098b7403

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: D17-02
  predecessor_task_revision: 2
  predecessor_task_sha256: a4a56cb1c031979fd006ef521eb4e8673980b7440f5aea58f7e460b16aa36c75
  predecessor_program_revision: 134
  predecessor_program_sha256: f171ee415cd6e7a8b98f4908d434da2870ea2496993aaaa57c41e0927987f2ec
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 7e9b4bb20fb21af4ea3c8c2878b2081f6f072ad1d171c0d090469f27c9155675

stop: Execute only the current MiniTZ task D17-03; validate and persist before advancing.
```
