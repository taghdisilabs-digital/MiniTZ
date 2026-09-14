# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 80
program_sha256: a0e18b284ef3cdb338c1e59bb84b59091955da6423f07dd4019dd4286c301ad0

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: MINITZ-CAPABILITIES-01
  project: MiniTZ
  section: minitz
  class: medium
  title: Implement and qualify the complete MiniTZ OS capability surface
  status: WORKING
  runner: READY
  lane: Engine
  revision: 2
  task_sha256: 67caa666b612a9381e1a6a4bc3b7f1ece837171d49a6ab7d3b88a503d953da1b

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: MINITZ-AI-RUNTIME-01
  predecessor_task_revision: 2
  predecessor_task_sha256: a1a168d510654dfef32cac82419e2b32258b4f1c96db712dd55b399f84c262ef
  predecessor_program_revision: 78
  predecessor_program_sha256: 1ea12742563168211131d5961a5e0b0f9a2b2d644b0061632a0c982f2cc9f762
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: ccace4af1118c20acebba6d333c59c6c038e29a02aadbf7ad4dc9e30fc380278

stop: Execute only the current MiniTZ task MINITZ-CAPABILITIES-01; validate and persist before advancing.
```
