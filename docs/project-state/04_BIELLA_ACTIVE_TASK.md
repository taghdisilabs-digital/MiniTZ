# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 81
program_sha256: d0368b1c2227eef33a1ccf27d78fcb86265952eeaa4aa410414ce69af9339ed3

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
  status: PENDING
  runner: READY
  lane: Engine
  revision: 1
  task_sha256: dbf3bf2849be97d0a82fac820bc4164e09af2e5db3d18a64d213661d0c9d653b

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
