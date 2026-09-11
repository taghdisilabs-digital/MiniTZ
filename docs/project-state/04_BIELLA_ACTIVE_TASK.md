# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 47
program_sha256: 47df71628da6c4ff81fc37190940c4e8fa807dcbfbde660c0f5feee58c44dc3d

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: UNIFY-04
  project: MiniTZ
  section: minitz
  class: hard
  title: Attach kernel checkpoints, task-session memory and customer/maintenance continuity to one MiniTZ checkpoint family
  status: PENDING
  runner: READY
  lane: Engine
  revision: 5
  task_sha256: 7c2aa788be82e8c4f7520125edb6b9a3f4e8b0c49b7a145cfa31525b78e07e32

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

stop: Execute only the current MiniTZ task UNIFY-04; validate and persist before advancing.
```
