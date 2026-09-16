# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /state/task-program/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 137
program_sha256: a805f81dd35a7d7b41e41923f32df635eb9cb441500c2b1a81070df0331e4a1d

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: D17-04
  project: MiniTZ
  section: minitz
  class: medium
  title: Prove player, rival, infected, and arena interaction
  status: PENDING
  runner: READY
  lane: Games
  revision: 1
  task_sha256: c0b1dc0fd420b99a38369b065740ae9062f71837ae050462c1beff4d00b6a8e9

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: D17-03
  predecessor_task_revision: 2
  predecessor_task_sha256: 0da9ec2cda4ce1f0ecf67ffa67b9fab75da52684b4a0e99a444277f6afbe95c3
  predecessor_program_revision: 136
  predecessor_program_sha256: 8d70fd2b5a79163aa3bc70603e1013707589a6f72bd07a1a76f1bb07a8f3b814
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 441d10cf1a5d66622e5a4c887c00e9de37eb1a18d4b38e9bca56dc540a50331d

stop: Execute only the current MiniTZ task D17-04; validate and persist before advancing.
```
