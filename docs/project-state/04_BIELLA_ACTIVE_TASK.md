# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 71
program_sha256: 4371349753b3431c69e31734aa6ebe713e855e0511fb76388c35069e757c69aa

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: MINITZ-STARTUP-FOUNDATION-01
  project: MiniTZ
  section: minitz
  class: medium
  title: Bring up MiniTZ foundation in safe startup order without starting task execution
  status: WORKING
  runner: READY
  lane: Engine
  revision: 1
  task_sha256: 47c528f0a1bd4ef3b917726baa8635ef7566b682083730d32f062fb4a994a348

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: UNIFY-03
  predecessor_task_revision: 5
  predecessor_task_sha256: 9490672114da5b7cff9329fbf78a04ce27768982a4dd2191dd707cec29638d3f
  predecessor_program_revision: 60
  predecessor_program_sha256: 87abed8a842e10a735c2a30645310241b316aaf5b225e6d3181db9107c33a8fa
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 8b4985f54a56780b54131c63db75cc2f0180f09fcc6275cefcce8150de860d34

stop: Execute only the current MiniTZ task MINITZ-STARTUP-FOUNDATION-01; validate and persist before advancing.
```
