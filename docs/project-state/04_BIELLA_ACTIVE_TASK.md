# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 87
program_sha256: cd0c9c70076fecbb1f37aab383a5c6eeb6341332d7d3aad56f0ff093c73edeef

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: MINITZ-INSTALL-UPDATE-01
  project: MiniTZ
  section: minitz
  class: medium
  title: Make the canonical MiniTZ source install update and recover itself
  status: PENDING
  runner: READY
  lane: Engine
  revision: 1
  task_sha256: 7197ad0d3ec727301e06576219b7a85e075ff9e9b689f4583a89f9b7fb30cd82

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: MINITZ-UX-OPS-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 11b835dfa5a28a39b0586ff0dfbc4f532e4465e170fb98473974284d0ae2ae64
  predecessor_program_revision: 86
  predecessor_program_sha256: cd2821faaa98f7259b280581488015d4de4890280a664b9ca4745fc72ba35155
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 623dc6941aedaee3507853201cf194e93bdd5936980e2f603a56a8abeac99519

stop: Execute only the current MiniTZ task MINITZ-INSTALL-UPDATE-01; validate and persist before advancing.
```
