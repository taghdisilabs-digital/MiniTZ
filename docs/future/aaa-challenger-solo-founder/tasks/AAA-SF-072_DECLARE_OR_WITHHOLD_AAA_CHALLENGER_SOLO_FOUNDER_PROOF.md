# AAA-SF-072 — Declare or withhold AAA Challenger Solo Founder proof

Status: `FUTURE_BLOCKED`
Phase: `P9` — Investor-grade AAA challenger evidence closure
Project: Cross-project coordination
Repository: `NONE`
Predecessor: `AAA-SF-071` durably closed
Next task: PROGRAM_CLOSE

## Activation guard

- Do not execute this task while its predecessor is incomplete.
- Reobserve the smallest current source set needed for this task before writing.
- Preserve valid newer work; do not restart predecessor work because a session/model/worker changed.
- If current authority supersedes a premise in this file, record that premise as superseded and adapt only this task boundary without rewriting the whole program.

## Objective

Close the program only if the game, external player proof, repeatable production, founder leverage, Engine external replication, demand/commercial evidence, and live demonstration all meet their task contracts. Otherwise publish the exact remaining gaps and keep the declaration withheld.

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

Final AAA-SF closure record: VERIFIED declaration or explicit unresolved-gap record.

## Validation contract

All preceding AAA-SF tasks are durably complete and remotely readable; any missing requirement blocks the declaration without erasing completed evidence.

## Required evidence

Final closure record, Git/Drive identities, full evidence index.

## New declaration requirements

A positive declaration requires all six investor proof lanes to be durably evidenced in addition to the game/player/repeatable-production quality gates already defined by prior AAA-SF tasks. The declaration must identify the exact current evidence index revision and may not promote investor scenarios, historical candidates, or stale source snapshots into proof.

## Out of scope

- Reopening already verified predecessor work without an invalidation reason.
- Inventing unapproved game mechanics, canon, platforms, release dates, pricing promises, or technical targets.
- Treating generated media, plans, screenshots, configs, exit codes, HTTP success, or agent assertions as substitutes for the runtime/file/publication evidence required by this task.
- Creating game-specific systems inside Biella Engine or universal Engine infrastructure inside Biella Games.
- Starting a later `AAA-SF` task before this task has durable closure.

## Completion record

Record: task ID; current source commit/tree; changed paths; exact commands or execution path; validation result; artifact IDs/digests; Drive IDs/readback if used; unresolved failures; closure timestamp. Status becomes `COMPLETE` only when the validation contract and required evidence are both satisfied.
