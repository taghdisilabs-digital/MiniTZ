# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 82
program_sha256: 9cb53b3c276c220ca8d03017fe6f853438007a3f6946ff11777c52e849c012fc

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: MINITZ-BROWSER-HUMAN-01
  project: MiniTZ
  section: minitz
  class: medium
  title: Complete persistent authenticated browser/computer/work and owner-attention capabilities
  status: WORKING
  runner: READY
  lane: Engine
  revision: 2
  task_sha256: 5e3a935674dc09b983801f7332412d56d54bfa9292cc82cb0420f1b9306d2d04

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: MINITZ-CAPABILITIES-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 67caa666b612a9381e1a6a4bc3b7f1ece837171d49a6ab7d3b88a503d953da1b
  predecessor_program_revision: 80
  predecessor_program_sha256: a0e18b284ef3cdb338c1e59bb84b59091955da6423f07dd4019dd4286c301ad0
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 6f86caec1ed07582f5228eff1f9f96f21cbe089ab1bc0063e6d984f0466a297b

stop: Execute only the current MiniTZ task MINITZ-BROWSER-HUMAN-01; validate and persist before advancing.
```
