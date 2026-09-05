# AAA-SF-030 — Lock native frame-time and responsiveness targets from evidence

Status: `FUTURE_BLOCKED`
Phase: `P4` — Performance, stability, and release operations
Project: Biella Games
Repository: `patrickminitz-web/biella-games`
Predecessor: `AAA-SF-029` durably closed
Next task: `AAA-SF-031`

## Activation guard

- Do not execute this task while its predecessor is incomplete.
- Reobserve the smallest current source set needed for this task before writing.
- Preserve valid newer work; do not restart predecessor work because a session/model/worker changed.
- If current authority supersedes a premise in this file, record that premise as superseded and adapt only this task boundary without rewriting the whole program.

## Objective

Define target native FPS/frame-time/hitch/latency tiers only where representative measurements support a production decision.

## Minimum current reads

- current repository `AGENTS.md`.
- current task-relevant source/content.
- current `docs/TECHNICAL_DECISIONS.md` when the task depends on a technical decision.
- current canonical Drive evidence only where needed.


## Execution

1. Bind the exact current inputs and identities required by the objective; mark unavailable required values `UNKNOWN` instead of guessing.
2. Reuse any predecessor output that is still valid under current inputs.
3. Produce only the task deliverable below. Do not start the next task in the same execution boundary unless a current owner instruction explicitly authorizes it.
4. Run the task-specific validation below against the real output/runtime/evidence.
5. Persist exact source/artifact/evidence identities needed to resume this task after interruption.
6. When repository publication is part of the deliverable: commit coherently, push the intended branch, and verify remote readback before closure.
7. When Drive publication is part of the deliverable: publish to the matching canonical project path and verify file/folder identity plus required content/readback.

## Required deliverable

Updated performance decision entries and repeatable benchmark scenarios.

## Validation contract

Targets exclude generated frames as native performance and are tied to accepted hardware/scenario identities.

## Required evidence

Decision record, benchmark telemetry, source commit.

## Out of scope

- Reopening already verified predecessor work without an invalidation reason.
- Inventing unapproved game mechanics, canon, platforms, release dates, pricing promises, or technical targets.
- Treating generated media, plans, screenshots, configs, exit codes, HTTP success, or agent assertions as substitutes for the runtime/file/publication evidence required by this task.
- Creating game-specific systems inside Biella Engine or universal Engine infrastructure inside Biella Games.
- Starting a later `AAA-SF` task before this task has durable closure.

## Completion record

Record: task ID; current source commit/tree; changed paths; exact commands or execution path; validation result; artifact IDs/digests; Drive IDs/readback if used; unresolved failures; closure timestamp. Status becomes `COMPLETE` only when the validation contract and required evidence are both satisfied.
