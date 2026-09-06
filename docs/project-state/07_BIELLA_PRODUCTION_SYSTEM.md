# 07 — BIELLA PRODUCTION SYSTEM

```yaml
schema: biella.production_system/v2
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

## Volatile state and validation
- `03` and `04` are live continuity/observer records and may change while production remains valid.
- Gameplay/runtime validators must not use exact byte identity of `03` or `04` as a correctness gate.
- Stable project authority such as the active Project `PRODUCTION.md`, exact implementation inputs, artifacts, and task-derived evidence remain valid validation inputs.

## Persistent continuation
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

