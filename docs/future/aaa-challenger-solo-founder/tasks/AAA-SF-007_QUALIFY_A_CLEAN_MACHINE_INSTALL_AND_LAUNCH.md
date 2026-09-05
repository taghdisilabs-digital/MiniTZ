# AAA-SF-007 — Qualify a clean-machine install and launch

Status: `FUTURE_BLOCKED`
Phase: `P1` — Reproducible shippable build
Project: Biella Games
Repository: `patrickminitz-web/biella-games`
Predecessor: `AAA-SF-006` durably closed
Next task: `AAA-SF-008`

## Activation guard

- Do not execute this task while its predecessor is incomplete.
- Reobserve the smallest current source set needed for this task before writing.
- Preserve valid newer work; do not restart predecessor work because a session/model/worker changed.
- If current authority supersedes a premise in this file, record that premise as superseded and adapt only this task boundary without rewriting the whole program.

## Objective

Install or unpack the package on a machine/environment that does not depend on the development editor workspace and prove clean launch.

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

Clean-machine launch record including prerequisite handling and first-run behavior.

## Validation contract

Packaged executable launches outside the editor, reaches real playable runtime, accepts player input, and exits cleanly; no developer-only path is required.

## Required evidence

Target-machine identity, package digest, runtime log, and captured launch/play evidence.

## Out of scope

- Reopening already verified predecessor work without an invalidation reason.
- Inventing unapproved game mechanics, canon, platforms, release dates, pricing promises, or technical targets.
- Treating generated media, plans, screenshots, configs, exit codes, HTTP success, or agent assertions as substitutes for the runtime/file/publication evidence required by this task.
- Creating game-specific systems inside Biella Engine or universal Engine infrastructure inside Biella Games.
- Starting a later `AAA-SF` task before this task has durable closure.

## Completion record

Record: task ID; current source commit/tree; changed paths; exact commands or execution path; validation result; artifact IDs/digests; Drive IDs/readback if used; unresolved failures; closure timestamp. Status becomes `COMPLETE` only when the validation contract and required evidence are both satisfied.
