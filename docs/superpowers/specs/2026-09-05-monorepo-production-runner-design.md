# Biella Monorepo Production Runner Design

## Status
Approved architecture for replacing the legacy auto-feeder with one monorepo-native production runner.

## Authority and goal
Mahdi Taghdisi approved the single-repository/single-workspace structure and this production-runner rewrite. The goal is one resumable execution path that always derives work from canonical Biella state, preserves completed work, keeps live liveness accurate, and does not maintain a second queue or progress authority.

## Canonical durable state
Durable execution truth is limited to:
- `docs/project-state/03_BIELLA_CURRENT_STATE.md` — global current execution state.
- `docs/project-state/04_BIELLA_ACTIVE_TASK.md` — exact active task contract.
- `projects/<project>/docs/PRODUCTION.md` — Project section/task map and durable Project completion evidence.
- Git `main` and canonical Drive publication/readback remain source/publication evidence.

`runtime.json`, lock files, stdout/stderr logs, child PIDs, model cooldowns, timestamps, and attempt results are runtime telemetry/evidence only. They may never become a completion ledger or task authority.

## Public controller
`biella-codex` remains the only public AI/production controller. Replace the legacy `feed` surface with:

```text
biella-codex production run
biella-codex production start
biella-codex production status
biella-codex production stop
biella-codex production sync
```

There is one systemd production unit: `biella-codex-production.service`. No project-specific feeder service or second scheduler is permitted.
## Internal modules

The legacy 700+ line feeder is replaced by focused modules under `ops/local-ai/`:
- `biella_production_state.py` — read/validate/update 03, 04, and Project `PRODUCTION.md`; resolve the one current Project/task; preserve `COMPLETE_ALREADY` semantics.
- `biella_task_packet.py` — compile deterministic task packets from canonical state and scoped policy without duplicating global instructions.
- `biella_codex_routing.py` — Codex model/reasoning selection, observed cooldowns, and catalog discovery. Astra Ultra remains required for hard/deep-memory work; creation never routes below high reasoning.
- `biella_production_evidence.py` — structured result schema, evidence validation, durable completion/update helpers, and publication identity capture.
- `biella_production_runner.py` — single-flight lifecycle, child process execution, periodic heartbeat, retry/cooldown handling, section planning/audit, and systemd start/stop/status.

Provider-specific research/media/data execution remains behind the existing `biella resource` dispatcher. The runner may route specialized work there, but does not create provider workflows or duplicate provider state.

## Execution flow

1. Acquire one runtime lock.
2. Read current 03, 04, and the Project `PRODUCTION.md` once at the task boundary.
3. Reconcile the exact current task. If 04 is stale but Project evidence proves a completed task, update 03/04 to the next task rather than reopening work.
4. Compile one deterministic task packet.
5. Select the cheapest sufficient specialized Resource or Codex route; use Astra Ultra for hard/deep-memory/hard-creation classes.
6. Spawn one Codex child for one task boundary.
7. Refresh `runtime.json` heartbeat periodically while the child is alive.
8. Parse the structured result and validate task identity/status.
9. For `COMPLETE`/`COMPLETE_ALREADY`, persist Project completion evidence, update 03/04 to the next task, commit/push/read back when required by the task, then continue.
10. For `CONTINUE`, preserve current task and begin another bounded attempt.
11. For owner/external dependency, stop with that state visible in control.
12. When a section has no remaining task, audit/plan only that section and append only missing semantic delta tasks.

The runner never executes two overlapping task writers.
## Runtime telemetry and liveness

`runtime.json` contains only operational telemetry:

```json
{
  "status": "RUNNING",
  "project": "biella-games",
  "task_id": "D01-030",
  "attempt": 1,
  "pid": 123,
  "child_pid": 456,
  "active_model": "gpt-6-astra",
  "active_reasoning": "ultra",
  "heartbeat_at": "2026-09-05T02:00:00+00:00",
  "last_result": null,
  "cooldowns": {}
}
```

A heartbeat is refreshed at least every 30 seconds while a child is alive. `ACTIVE` requires both a running production service and a fresh heartbeat. `STALE` means service exists but heartbeat age exceeds 90 seconds. `WAITING`, `ERROR`, and `STOPPED` reflect the runner lifecycle. The Control UI reads this projection but does not own heartbeat state.

## Control integration

Update the control gateway to use `biella-codex production status`. The existing `Control | Work | Outputs | System` information architecture remains unchanged. `Work` continues to read Project `PRODUCTION.md`; `Control` uses runner telemetry plus canonical task state. No control endpoint may infer completion from telemetry alone.

## Resource configuration

The runtime provider file remains `/root/.config/biella-ai/runtime.env` mode `0600`. The supplied non-secret locators are:
- Supabase project URL: `https://jktmfmfxhynzickoaswt.supabase.co`
- Upstash account email: `patrickminitz@gmail.com`
- Cloudinary cloud name: `efex8ff4`

They are runtime configuration only and are never committed to Git or Drive. Existing credentials remain secret runtime Resources.

## Cutover and preservation

The currently running legacy feeder is not terminated mid-task. Its parent is frozen after D01-030 starts so no successor can launch. D01-030 must finish and publish normally. The new runner is installed only after that child exits and its result is reconciled into canonical `main`.

Cutover sequence:
1. Capture the final legacy task result and exact new `main` identity.
2. Stop/remove the legacy feeder service and stale runtime process.
3. Merge the production-runner implementation into current `main` without overwriting Games changes.
4. Install exact controller/runner bytes and shared policy.
5. Remove legacy `biella_codex_feeder.py`, `feed` CLI surface, legacy feeder unit naming, and obsolete runtime directories only after their unique evidence is preserved.
6. Start `biella-codex production start` from the canonical next task.
7. Prove fresh heartbeat, one child writer, correct next task, and Control `ACTIVE` readback.

No completed Games or Engine work may be invalidated by the rewrite. Runtime logs/results needed as evidence remain under the runtime evidence namespace or are referenced by durable Project evidence before cleanup.

## Failure handling

- Model/rate-limit failures create only runtime cooldown telemetry and retry the same canonical task with the next eligible route.
- Invalid structured result never advances canonical state.
- Git/Drive publication failure leaves the task incomplete unless its acceptance contract explicitly allows local-only closure.
- Process interruption reconstructs the next task from 03/04 + Project `PRODUCTION.md`; runtime JSON is not trusted as task authority.
- A stale task pointer is repaired from current completed Project evidence, not by replaying completed work.

## Acceptance

The rewrite is accepted only when:
- `biella-codex production` is the sole production CLI surface and `feed` is absent.
- one production systemd unit is the sole automatic writer authority.
- no `games-production.json` or equivalent mutable progress ledger exists.
- 03/04 + Project `PRODUCTION.md` deterministically resolve the same current task.
- long-running child attempts keep heartbeat fresh and Control remains `ACTIVE`.
- task completion advances Project state and 03/04 without reopening completed work.
- hard/deep-memory routes use Astra Ultra and creation never uses low reasoning.
- resource routing remains behind `biella resource` and no quota/reset probing occurs.
- full controller/runtime/control tests pass.
- a live resumed Games task starts from the exact canonical successor after cutover.
