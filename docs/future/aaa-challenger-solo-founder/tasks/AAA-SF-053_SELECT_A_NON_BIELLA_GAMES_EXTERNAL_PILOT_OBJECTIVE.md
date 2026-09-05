# AAA-SF-053 — Select a non-Biella-Games external pilot objective

Status: `FUTURE_BLOCKED`
Phase: `P7` — Biella Engine external replication
Project: Biella Engine
Repository: `patrickminitz-web/biella-engine`
Predecessor: `AAA-SF-052` durably closed
Next task: `AAA-SF-054`

## Activation guard

- Do not execute this task while its predecessor is incomplete.
- Reobserve the smallest current source set needed for this task before writing.
- Preserve valid newer work; do not restart predecessor work because a session/model/worker changed.
- If current authority supersedes a premise in this file, record that premise as superseded and adapt only this task boundary without rewriting the whole program.

## Objective

Bind one real outside-user/project objective that tests Biella as a universal execution system rather than a game-specific automation.

## Minimum current reads

- current Engine project instructions / `AGENTS.md` if present.
- current active numbered-task boundary and exact relevant source.
- directly touched Engine interfaces.
- current canonical Drive continuity only where needed.


## Execution

1. Bind the exact current inputs and identities required by the objective; mark unavailable required values `UNKNOWN` instead of guessing.
2. Reuse any predecessor output that is still valid under current inputs.
3. Produce only the task deliverable below. Do not start the next task in the same execution boundary unless a current owner instruction explicitly authorizes it.
4. Run the task-specific validation below against the real output/runtime/evidence.
5. Persist exact source/artifact/evidence identities needed to resume this task after interruption.
6. When repository publication is part of the deliverable: commit coherently, push the intended branch, and verify remote readback before closure.
7. When Drive publication is part of the deliverable: publish to the matching canonical project path and verify file/folder identity plus required content/readback.

## Required deliverable

Pilot brief with owner/user objective, project boundary, allowed resources, expected output contract, and acceptance evidence.

## Validation contract

Pilot does not import Biella Games canon into Engine behavior and does not depend on MiniTZ historical instructions.

## Required evidence

Pilot brief, project identity, accepted output contract.

## New source/reuse constraint

The pilot must run through the then-current public Biella execution path rather than a new pilot-specific controller. Normalized historical candidates may be reused only if they have already been admitted into current accepted Engine source; raw legacy material and transfer-staging candidates are not pilot authority.

## Out of scope

- Reopening already verified predecessor work without an invalidation reason.
- Inventing unapproved game mechanics, canon, platforms, release dates, pricing promises, or technical targets.
- Treating generated media, plans, screenshots, configs, exit codes, HTTP success, or agent assertions as substitutes for the runtime/file/publication evidence required by this task.
- Creating game-specific systems inside Biella Engine or universal Engine infrastructure inside Biella Games.
- Starting a later `AAA-SF` task before this task has durable closure.

## Completion record

Record: task ID; current source commit/tree; changed paths; exact commands or execution path; validation result; artifact IDs/digests; Drive IDs/readback if used; unresolved failures; closure timestamp. Status becomes `COMPLETE` only when the validation contract and required evidence are both satisfied.
