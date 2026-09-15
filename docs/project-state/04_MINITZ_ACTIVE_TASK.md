# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 110
program_sha256: 1926a36dd9485d1b6a062fc3136fe361a87d38ef1a9ec04ff0a6fea6a845faaf

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
  revision: 5
  task_sha256: a507a12939322f7d3fc8d28a2f004783cd1a2369628b25502a60556d7f79e427

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: MINITZ-SYSTEM-QUALIFY-01
  predecessor_task_revision: 7
  predecessor_task_sha256: fba4a08b59f91264317b1aa8e16929bc25ad81cc12144b6c4a0101e95dfe011f
  predecessor_program_revision: 109
  predecessor_program_sha256: e72929eab594a2e08cb0f088061b19cce7b4c615ecb30a9bfc249de762494513
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: becc10225e71456a5396f7abf9e48ca15aa20c02670f650557e5ca300f853ac2

stop: Execute only the current MiniTZ task MINITZ-OWNER-ACCEPTANCE-01; validate and persist before advancing.
```
