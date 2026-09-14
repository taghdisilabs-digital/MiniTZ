# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 78
program_sha256: 1ea12742563168211131d5961a5e0b0f9a2b2d644b0061632a0c982f2cc9f762

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: MINITZ-AI-RUNTIME-01
  project: MiniTZ
  section: minitz
  class: medium
  title: Complete MiniTZ local AI, GPU, Codex and resource execution runtime
  status: WORKING
  runner: READY
  lane: Engine
  revision: 2
  task_sha256: a1a168d510654dfef32cac82419e2b32258b4f1c96db712dd55b399f84c262ef

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: MINITZ-KNOWLEDGE-TRANSFER-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 728ed29dce666d31d4ff5706bc063e5a27a735849b9244e45ae9ed4cf69d46f1
  predecessor_program_revision: 76
  predecessor_program_sha256: 6a37d4e974dcc934812fd629d27c35f7ffd1af871e6c02d0307c15943074af03
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 160b9693ee8926f52a9509e4d222a33fff099b5457f4d05c44f3e3c9cdff874f

stop: Execute only the current MiniTZ task MINITZ-AI-RUNTIME-01; validate and persist before advancing.
```
