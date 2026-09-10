# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 27
program_sha256: 7169769f48ce705b16ed547ad103470cc98263e07c6dbac9e6e24557daa3fb35

task:
  id: UNIFY-01
  project: MiniTZ
  section: minitz
  class: hard
  title: Attach scheduling/progression mechanisms to one MiniTZ progression family with exactly one active progression authority
  status: PENDING
  runner: READY
  lane: Engine
  revision: 3
  task_sha256: 4fbced8b814df3e5a70f651bfc8509a52e6757df77c7a41ca1158fe6af5a621f

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

stop: Execute only the current MiniTZ task UNIFY-01; validate and persist before advancing.
```
