# AAA-SF-002 — Freeze current source and decision identities

Status: `FUTURE_BLOCKED`
Phase: `P0` — Activation and truth lock
Project: Cross-project coordination
Repository: `NONE`
Predecessor: `AAA-SF-001` durably closed
Next task: `AAA-SF-003`

## Activation guard

- Do not execute this task while its predecessor is incomplete.
- Reobserve the smallest current source set needed for this task before writing.
- Preserve valid newer work; do not restart predecessor work because a session/model/worker changed.
- If current authority supersedes a premise in this file, record that premise as superseded and adapt only this task boundary without rewriting the whole program.

## Objective

Capture the exact current Biella Games and Biella Engine source identities and only the accepted decisions required by this future proof program. Preserve UNKNOWN values rather than selecting them.

## Minimum current reads

- current accepted Games and Engine authority records needed by the task.
- exact referenced Git/Drive/artifact identities only.


## Execution

1. Bind the exact current inputs and identities required by the objective; mark unavailable required values `UNKNOWN` instead of guessing.
2. Reuse any predecessor output that is still valid under current inputs.
3. Produce only the task deliverable below. Do not start the next task in the same execution boundary unless a current owner instruction explicitly authorizes it.
4. Run the task-specific validation below against the real output/runtime/evidence.
5. Persist exact source/artifact/evidence identities needed to resume this task after interruption.
6. When repository publication is part of the deliverable: commit coherently, push the intended branch, and verify remote readback before closure.
7. When Drive publication is part of the deliverable: publish to the matching canonical project path and verify file/folder identity plus required content/readback.

## Required deliverable

Source-lock record containing repository, branch, commit, tree, relevant Drive source IDs/revisions, current technical decisions, and unresolved UNKNOWNs that could affect later tasks.

## Validation contract

Remote Git readback matches recorded commits/trees; Drive metadata/readback matches recorded IDs/revisions; no UNKNOWN is converted into an inferred requirement.

## Required evidence

Source-lock record with observed timestamps and remote identities.

## Out of scope

- Reopening already verified predecessor work without an invalidation reason.
- Inventing unapproved game mechanics, canon, platforms, release dates, pricing promises, or technical targets.
- Treating generated media, plans, screenshots, configs, exit codes, HTTP success, or agent assertions as substitutes for the runtime/file/publication evidence required by this task.
- Creating game-specific systems inside Biella Engine or universal Engine infrastructure inside Biella Games.
- Starting a later `AAA-SF` task before this task has durable closure.

## Completion record

Record: task ID; current source commit/tree; changed paths; exact commands or execution path; validation result; artifact IDs/digests; Drive IDs/readback if used; unresolved failures; closure timestamp. Status becomes `COMPLETE` only when the validation contract and required evidence are both satisfied.
