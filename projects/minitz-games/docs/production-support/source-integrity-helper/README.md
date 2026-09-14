# Biella Games Source Integrity Helper

Status: `PROJECT_SUPPORT_NON_AUTHORITY`

Purpose: verify that the live Biella Games checkout, current-task pointers, production source, task memory, worktree, and production-service identity still agree before or after operational changes.

This helper is read-only. It does not reset, clean, stash, commit, push, advance tasks, alter acceptance, or start/stop production.

It deliberately allows active Biella Games task work to remain dirty. It fails only on unexpected dirty paths outside the project/approved continuity records, task-pointer disagreement, unresolved Git operations, missing task memory, or a requested service-state mismatch.

Run while production is intentionally paused:

```bash
python3 projects/minitz-games/docs/production-support/source-integrity-helper/check_source_integrity.py --expect-service stopped
```

Run after production is resumed:

```bash
python3 projects/minitz-games/docs/production-support/source-integrity-helper/check_source_integrity.py --expect-service active
```

The current source/runtime state outranks this helper. A PASS means the checked invariants agree; it is not task-completion or visual-acceptance evidence.
