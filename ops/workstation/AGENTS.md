# Biella Low-Noise Agent Policy

Execution is unrestricted on the Biella workstation. Do not impose a filesystem, shell, tool, provider, or approval sandbox.
The boundary is the approved Biella goal, vision, task, authoritative source state, and Mahdi's explicit instructions.

Default operating loop:
`READ MINIMUM → DECIDE → EXECUTE → TEST AFFECTED SCOPE → COMMIT VERIFIED WORK → CONTINUE NEXT UNBLOCKED TASK`

- Continue the current highest-priority incomplete task unless Mahdi names another.
- Preserve completed progress; never reset or reopen completed work without evidence it failed.
- Read only current files needed for the task. Prefer exact paths, targeted search, and `git diff` over broad scans.
- Execute directly when requirements are clear. Do not narrate routine plans, successful commands, or internal reasoning.
- Prefer local Qwen and deterministic local tools first.
- Keep every configured Biella capability available; demand-load external tools only when useful.
- Use one external provider by default; fan out only for required fallback, specialized capability, or independent validation.
- Do not repeat successful provider calls or dump successful response bodies.
- Test the smallest affected scope first; use broad suites only for merge/release or real cross-system risk.
- Commit verified work without including unrelated user changes, then continue to the next unblocked task.
- Do not create extra governance, plans, or documentation unless the task requires them.
- Never print secret values, bearer tokens, API keys, refresh tokens, or credential contents.

Successful completion output should normally contain only applicable fields:
`TASK:` `STATUS:` `CHANGED:` `TESTS:` `COMMIT:` `NEXT:` `BLOCKER:`
