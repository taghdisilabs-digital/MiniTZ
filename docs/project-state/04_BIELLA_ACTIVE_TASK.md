# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 90
program_sha256: 490f16264e5fd261d05254b0f6339d55970e6d1fcd09649ad809392031a39365

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: MINITZ-GITHUB-MAIN-01
  project: MiniTZ
  section: minitz
  class: medium
  title: Attach one private MiniTZ OS GitHub repository with main as the only active branch
  status: WORKING
  runner: READY
  lane: Engine
  revision: 2
  task_sha256: 144c652775eaaa55dd09fba5b5c356ae034b0c3507ac24d2b4d545144e6d903e

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: MINITZ-INSTALL-UPDATE-01
  predecessor_task_revision: 2
  predecessor_task_sha256: f8a451ce1d57258e239e26b2c407b02b17934952ae3ed7349ab8644b6a26a75e
  predecessor_program_revision: 88
  predecessor_program_sha256: 94295234a5cadb9f126615b844367f3fc5d4a4a5a0f5e220d559e93ee3374f1e
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 64e1049fc8c02638f994038c38cf3960adf6e52ad8459a0df3eb9fb8ef14f859

stop: Execute only the current MiniTZ task MINITZ-GITHUB-MAIN-01; validate and persist before advancing.
```
