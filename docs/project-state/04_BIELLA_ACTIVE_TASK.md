# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 36
program_sha256: 6e5d95e12196842e7d23bc88c4914db816312855835cedad1227ad30a8eff9ff

task:
  id: UNIFY-03
  project: MiniTZ
  section: minitz
  class: hard
  title: Attach validation mechanisms and live completion admission to one MiniTZ validation/completion family
  status: PENDING
  runner: READY
  lane: Engine
  revision: 5
  task_sha256: 6e0daf1219d34718f2e1fa3b5b74ebb001f705687f3592879e2b1def78df3597

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

stop: Execute only the current MiniTZ task UNIFY-03; validate and persist before advancing.
```
