# 07 — BIELLA PRODUCTION SYSTEM

```yaml
schema: biella.production_system/v3
mode: stable_reference
source_of_truth: current_GitHub_source_plus_observed_runtime
volatile_state_files: [03_BIELLA_CURRENT_STATE.md, 04_BIELLA_ACTIVE_TASK.md]
```

## Canonical execution shape
- One canonical repository: `/root/biella/repos/biella-engine`.
- One production controller owns progression and one authoritative Project task is active at a time.
- Independent Resources may run concurrently inside that task when dependencies, side effects, and capacity permit.
- Completed/verified work is reused. Reconnects, model/provider changes, viewer activity, and bounded failures do not invalidate it.
- Recovery is limited to the smallest invalidated boundary.
- No approval/reviewer/owner-decision gate is created for already-authorized work.

## Single ChatGPT management channel
- Exactly one owner-designated Biella ChatGPT conversation is the current human management channel. The conversation in which Mahdi explicitly designates or replaces that role is current; Project membership alone never grants authority.
- Every other ChatGPT conversation/thread is `RETIRED_FROM_CURRENT_BIELLA_AUTHORITY`: it may remain historical evidence, but it may not steer production, own task/session state, start/stop/advance work, or become a parallel controller.
- The management conversation is a control/decision interface only, never an executor or liveness dependency. Closing, reloading, logging out, or losing that browser conversation has zero effect on production.
- Production remains `systemd -> Biella controller -> persistent Codex task/session -> tasks`. Codex execution-session IDs are production continuity and are not ChatGPT conversation threads.
- No ChatGPT conversation ID is invented or stored when the platform does not expose one.

## Source alignment and fail-closed freshness
- Before the persistent production service starts, `origin/main` is fetched and the canonical checkout is verified on `main`. If GitHub is ahead and its changed paths do not overlap preserved dirty work, the checkout is fast-forwarded without reset, clean, stash, rebase, or history rewrite.
- Preserved local commits ahead of `origin/main` are valid in-flight task progress and are not rolled back. Divergence or any remote update overlapping dirty local work fails closed for reconciliation rather than guessing or overwriting bytes.
- The systemd unit executes `biella_production_runner.py` directly from the aligned canonical repository, so a successful startup does not continue from an older copied controller implementation.
- While production is running, the controller fetches/checks `origin/main` before selecting work and again after each model/section turn before accepting its result. If newer remote authority appears, no result or next-task transition is accepted; the runner exits for the systemd source-sync bootstrap to align and restart from current source.
- Persistence performs the same remote-source guard before commit/push. Source drift exits to the alignment bootstrap instead of spinning a known-stale push retry. Temporary transport/publication failures still retry without losing task state.
- Runtime status records the latest source-alignment receipt. `03` and `04` remain volatile observer/continuity records and their embedded historical Git identity fields are not execution freshness gates.

## Continuous ordered progression
- The canonical Project `PRODUCTION.md` list is the ordered source; there is no second mutable queue.
- Select the earliest unfinished canonical task.
- After real durable closure, immediately advance to the next earliest unfinished task without an inter-task stop.
- Never roll back or redo verified work unless a material input/source/artifact/validation/contract/authority change invalidates it.
- When the list is exhausted, request a new task from Mahdi. If none is supplied, perform bounded read-only discovery over current canonical projects and registered capabilities and expose legitimate candidates without inventing product direction.

## Nonblocking resource policy
- Local Qwen/Ollama is a replaceable, non-authoritative Resource. It may be used on demand but must not delay the start of the authoritative Codex turn.
- Optional provider/tool/resource failure does not stop unrelated work.
- Route cooldown polling is short and refreshes available routes rather than producing long dead intervals.
- Quota/balance probing remains forbidden.

## Bounded outage fallback
- Strong Codex routes retain full-task synthesis/closure authority. When normal strong routes are unavailable from observed call outcomes, Spark and local Qwen may execute only one small task-scoped technical outcome at a time.
- A bounded fallback turn uses a fresh executor session and a retrieval-first packet referencing current task memory, the compact projection, the task guide, and exact source/evidence. It does not resume or replace the preserved persistent task session and it never broad-rereads accumulated conversation history.
- Quality order is correctness/evidence, continuity, speed, then token savings. Bounded fallback may make and validate an exact source/test/evidence increment but may not plan sections, change task order/status, lower acceptance, or declare the whole task `COMPLETE`/`COMPLETE_ALREADY`.
- Bounded packets must not create planning/status/summary artifacts merely to show activity. If the model changes no Project working bytes, that exact model+task/worktree+guide packet is marked no-progress and is not called again until the packet identity changes; another eligible bounded model may be tried once, otherwise production waits without another model call for route/state change.
- Packet/no-progress bookkeeping is derivative controller state, not a second queue, scheduler, memory system, or task authority. Exact/raw source and evidence remain canonical.

## Volatile state and validation
- `03` and `04` are live continuity/observer records and may change while production remains valid.
- Gameplay/runtime validators must not use exact byte identity of `03` or `04` as a correctness gate.
- Stable project authority such as the active Project `PRODUCTION.md`, exact implementation inputs, artifacts, and task-derived evidence remain valid validation inputs.

## Persistent continuation
- Reinstalling/updating the controller preserves an already-disabled production service; owner/customer sleep is not silently re-enabled by the installer.
- Preserve task identity, Codex session identity when available, current worktree, task memory, failures, verified outputs, and continuation state.
- A pause/freeze/reconnect is not invalidation. Resume the same task/session where possible.
- `CONTINUE` means authorized work remains; `COMPLETE`/`COMPLETE_ALREADY` require task-appropriate evidence and durable source/output identity.

## Observer surfaces
- Public `/live/` and private control are read-only observers.
- Open/close/refresh/reconnect/login/logout must never signal, start, stop, pause, or advance production.
- Stale detection must allow more time than the normal production heartbeat interval so a healthy runner does not falsely oscillate to STALE.

## Durable completion
- Real editable output plus task-derived validation is required.
- Commit task implementation/evidence before `COMPLETE`.
- GitHub/Drive publication uses canonical destinations and remote readback where required.
- Publication failure preserves local work and remains `CONTINUE`; it never fabricates completion.

