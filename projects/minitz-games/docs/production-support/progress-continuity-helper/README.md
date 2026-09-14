# Biella Games Progress Continuity Helper

Status: `PROJECT_SUPPORT_NON_AUTHORITY`

Purpose: expose the canonical production runner's own liveness state and compare explicit forward-progress markers across a pause/resume boundary.

This helper does not start, stop, schedule, advance, repair, or supervise production. It imports the existing `ops/local-ai/biella_production_runner.py` status function so it does not create a second watchdog or heartbeat policy.

Create a baseline snapshot:

```bash
python3 projects/minitz-games/docs/production-support/progress-continuity-helper/check_progress.py snapshot --output /tmp/biella-progress-baseline.json
```

After resume, verify liveness and continuity advancement:

```bash
python3 projects/minitz-games/docs/production-support/progress-continuity-helper/check_progress.py check --baseline /tmp/biella-progress-baseline.json --require-forward
```

Use `--require-material` when actual project/evidence progress must be proven. Material markers are Git identity change, newer task-owned evidence activity, or a newly completed attempt. Attempt/task-memory changes are reported separately as execution-continuity progress.

A fresh heartbeat proves liveness but is never promoted into material progress. Absence of a material marker is not called a stall while canonical liveness remains ACTIVE; callers can require material progress explicitly when the workflow demands it.
