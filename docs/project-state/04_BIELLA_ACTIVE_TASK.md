# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 31
program_sha256: 0761279a9bda1f16fee2a3d24f8a5b2f52b7054871a66b6716ebc8ce51f7d643

task:
  id: UNIFY-02
  project: MiniTZ
  section: minitz
  class: hard
  title: Attach kernel routing, routing learning and live provider routing to one MiniTZ routing family with scoped decision authority
  status: PENDING
  runner: READY
  lane: Engine
  revision: 5
  task_sha256: 8b84ce809c6aa10e349ac5aa7fb907be9479f1f7888e8866c321502c2191c47b

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

stop: Execute only the current MiniTZ task UNIFY-02; validate and persist before advancing.
```
