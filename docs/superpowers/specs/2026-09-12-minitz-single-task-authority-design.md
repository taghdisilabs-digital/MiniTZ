# MiniTZ Single Task Authority Design

## Authority

`/root/biella/analysis/live_audit/TASK_PROGRAM.json` is the only persisted task/order/status/progression authority.
`tasks[]` is the only persisted task list. Array order is canonical execution order.
No `current_execution`, derived ledger, projection, task-guidance file, runtime journal, Boost plan, or historical D-list may own task identity, order, status, or progression.

## Task state

Every task stores its complete executable contract in the task row: identity, objective, dependencies, procedure/guidance, inputs/source refs, outputs/deliverables, write scope, validation, acceptance, negative controls, required evidence, context policy, worker policy, status, and completion evidence.
Canonical lifecycle is `PENDING -> WORKING -> COMPLETE`; legacy terminal states remain readable for provenance.
At most one task may be `WORKING`.
If no task is `WORKING`, the first active row in array order is the only candidate; later rows may not leapfrog it.

## Worker state

A writer AI must claim the current task before write execution. The claim changes the task to `WORKING` and is stored in `tasks[].workers`.
Read-only AI helpers may join the same task row but have zero progression authority.
Worker participation is volatile execution state and does not change the immutable task-definition digest after the initial `PENDING -> WORKING` transition.
Validated task completion marks active worker records complete and changes the task to `COMPLETE` atomically.
## Context/token policy

Every active/future task has `context_policy.mode=TASK_LOCAL_MINIMUM`.
Default loading is the current task row plus exact HARD dependency completion identities and explicitly referenced source/evidence objects.
Whole-program prose, retired task ledgers, generated guidance files, and unrelated project history are forbidden as default prompt context.
Context expansion is by reference and only when the current task cannot be executed or validated from its bounded context.

## Compatibility

The Python adapter may synthesize `current_execution` in memory for old callers during migration, but `public_program()` must never persist it.
03/04 state documents may remain derived UI projections but never become execution inputs or progression authority.
Existing in-flight `UNIFY-10` definition/digest is preserved during the task-program evolution.

## Capability/package order

Future capability review/migration/qualification tasks complete before `CAP-CLOSE-01`.
`RELEASE-PACKAGE-01` has a HARD dependency on `CAP-CLOSE-01` plus required install/operator/doctor/system/legal/provider prerequisites.
`OS-LAUNCH-01` immediately follows `RELEASE-PACKAGE-01` and tests the produced package on a clean supported environment.
Release-level update/integrity/network/provider/privacy/performance/recovery qualification follows a successful launch gate.
