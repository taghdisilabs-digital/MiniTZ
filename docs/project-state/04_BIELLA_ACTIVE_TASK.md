# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 86
program_sha256: cd2821faaa98f7259b280581488015d4de4890280a664b9ca4745fc72ba35155

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
  status: WORKING
  runner: READY
  lane: Engine
  revision: 2
  task_sha256: 11b835dfa5a28a39b0586ff0dfbc4f532e4465e170fb98473974284d0ae2ae64

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
