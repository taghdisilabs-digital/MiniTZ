# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 84
program_sha256: 63e5a2bd6a34c98db3e89ca7738c745d08426a1900a260e56349b13e96d9b785

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: MINITZ-SECURITY-PRIVACY-01
  project: MiniTZ
  section: minitz
  class: medium
  title: Complete MiniTZ credentials secrets trust privacy integrity and recovery boundaries
  status: WORKING
  runner: READY
  lane: Engine
  revision: 2
  task_sha256: aa0320996354ed4287b1c0dee49d4399760dd11194fd02c4a0252a1af383ab6c

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: MINITZ-BROWSER-HUMAN-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 5e3a935674dc09b983801f7332412d56d54bfa9292cc82cb0420f1b9306d2d04
  predecessor_program_revision: 82
  predecessor_program_sha256: 9cb53b3c276c220ca8d03017fe6f853438007a3f6946ff11777c52e849c012fc
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 65244da93f1beb65a0e12dc6092879bf81fca3ab3a409079439f6b50bfffa60a

stop: Execute only the current MiniTZ task MINITZ-SECURITY-PRIVACY-01; validate and persist before advancing.
```
