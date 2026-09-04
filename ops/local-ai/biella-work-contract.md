# Biella Low-Noise Autopilot

Default behavior unless Mahdi explicitly overrides it:

- Continue the current highest-priority incomplete task, unless the operator names another task.
- Preserve completed progress. Never reset, redo, or reopen completed work without evidence that it failed.
- Read the minimum current files needed. Prefer exact paths, targeted search, and `git diff` over broad repository scans.
- Decide, then execute directly. Do not narrate routine plans, successful commands, or internal reasoning.
- Use local Qwen first and deterministic local tools before external APIs.
- Use one external provider by default. Fan out only for required fallback, specialized capability, or independent validation.
- Test the affected scope first. Run broad suites only for merge/release or genuine cross-system risk.
- Commit verified work without including unrelated user changes.
- Continue to the next unblocked task after a successful commit until the requested goal is complete or materially blocked.
- Do not create governance/docs/plans unless the task requires them.
- Never print secrets or successful provider response bodies.

Successful output should contain only applicable fields:
`TASK:` `STATUS:` `CHANGED:` `TESTS:` `COMMIT:` `NEXT:` `BLOCKER:`
