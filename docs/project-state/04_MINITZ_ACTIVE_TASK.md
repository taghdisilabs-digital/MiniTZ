# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /state/task-program/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 99
program_sha256: 0bb5b8d9ae4bdfe0a9c8beb8d2bf05206ecc66d3e523de4068091a6a3b4bf924

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: MINITZ-OWNER-ACCEPTANCE-01
  project: MiniTZ
  section: minitz
  class: medium
  title: Prove MiniTZ OS is usable capable recoverable and owner-controlled on a clean target
  status: PENDING
  runner: READY
  lane: Engine
  revision: 1
  task_sha256: 6daf33252c3e9cd8d67179301b36075618488c7cfc5e26ccf42b32abbf3a6a85

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: MINITZ-SYSTEM-QUALIFY-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 503b3ac5d475179b77f642ad31962bc114d69e24f919eda01fd110f909d5c914
  predecessor_program_revision: 98
  predecessor_program_sha256: a53707a16860c18ba71cc380c1ae7b15e9fe1813daafacaee4bf4c172ea47c7d
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 41613404a81879b927d2491f7b0308a2d2425645582bdbddc067bed8c35ed754

stop: Execute only the current MiniTZ task MINITZ-OWNER-ACCEPTANCE-01; validate and persist before advancing.
```
