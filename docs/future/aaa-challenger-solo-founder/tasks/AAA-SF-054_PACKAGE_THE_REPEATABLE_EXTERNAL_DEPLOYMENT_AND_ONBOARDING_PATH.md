# AAA-SF-054 — Package the repeatable external deployment and onboarding path

Status: `FUTURE_BLOCKED`
Phase: `P7` — Biella Engine external replication
Project: Biella Engine
Repository: `patrickminitz-web/biella-engine`
Predecessor: `AAA-SF-053` durably closed
Next task: `AAA-SF-055`

## Activation guard

- Do not execute this task while its predecessor is incomplete.
- Reobserve the smallest current source set needed for this task before writing.
- Preserve valid newer work; do not restart predecessor work because a session/model/worker changed.
- If current authority supersedes a premise in this file, record that premise as superseded and adapt only this task boundary without rewriting the whole program.

## Objective

Reduce current Engine deployment/onboarding to a reproducible package or documented procedure that does not require reconstructing the founder environment by hand.

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

External deployment/onboarding package tied to an exact Engine commit.

## Validation contract

A fresh authorized environment can instantiate the required Engine services/state using the package without undocumented founder-only repair.

## Required evidence

Engine commit/tree, deployment logs, environment identity.

## New source/reuse constraint

Package the current accepted Engine deployment/onboarding surface. The observed 2026-09-05 public controller is `biella-codex`; do not introduce a second controller, queue, state ledger, memory system, or routing plane for externalization. Compile pilot work into the current task-packet contract and preserve exact authority/source identities.

## Out of scope

- Reopening already verified predecessor work without an invalidation reason.
- Inventing unapproved game mechanics, canon, platforms, release dates, pricing promises, or technical targets.
- Treating generated media, plans, screenshots, configs, exit codes, HTTP success, or agent assertions as substitutes for the runtime/file/publication evidence required by this task.
- Creating game-specific systems inside Biella Engine or universal Engine infrastructure inside Biella Games.
- Starting a later `AAA-SF` task before this task has durable closure.

## Completion record

Record: task ID; current source commit/tree; changed paths; exact commands or execution path; validation result; artifact IDs/digests; Drive IDs/readback if used; unresolved failures; closure timestamp. Status becomes `COMPLETE` only when the validation contract and required evidence are both satisfied.
