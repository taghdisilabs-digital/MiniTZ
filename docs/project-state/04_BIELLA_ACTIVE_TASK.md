# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 85
program_sha256: 6928ec8933c13acbe18e6683d9ccfa975012b10bd8d771dacceff29310012cbe

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: MINITZ-UX-OPS-01
  project: MiniTZ
  section: minitz
  class: medium
  title: Build the single normal-user MiniTZ OS surface and diagnostics
  status: PENDING
  runner: READY
  lane: Engine
  revision: 1
  task_sha256: 2260206d031d4f40f993a475f5af2e3529f1a0e6ddf8e0d1e362bec28d503ce3

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: MINITZ-SECURITY-PRIVACY-01
  predecessor_task_revision: 2
  predecessor_task_sha256: aa0320996354ed4287b1c0dee49d4399760dd11194fd02c4a0252a1af383ab6c
  predecessor_program_revision: 84
  predecessor_program_sha256: 63e5a2bd6a34c98db3e89ca7738c745d08426a1900a260e56349b13e96d9b785
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 3f03171338ddee96b5ee5322f63fa35c5c221fe4a7556ba2a86cab34570fcf14

stop: Execute only the current MiniTZ task MINITZ-UX-OPS-01; validate and persist before advancing.
```
