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
- Runtime status records the latest source-alignment receipt. After source alignment the bootstrap refreshes installed controller/unit bytes from the exact aligned canonical checkout while preserving service enablement state. `03` and `04` remain volatile observer/continuity records and their embedded historical Git identity fields are not execution freshness gates.

## Continuous ordered progression
- The canonical Project `PRODUCTION.md` list is the ordered source; there is no second mutable queue.
- Select the earliest unfinished canonical task.
- After real durable closure, immediately advance to the next earliest unfinished task without an inter-task stop.
- Never roll back or redo verified work unless a material input/source/artifact/validation/contract/authority change invalidates it.
- When the list is exhausted, request a new task from Mahdi. If none is supplied, perform bounded read-only discovery over current canonical projects and registered capabilities and expose legitimate candidates without inventing product direction.


## Isolated Project cell execution and external resource handoff
- `ISOLATED_PROJECT_CELL` is the canonical customer/project execution model. Biella owns each cell's task/run/checkpoint/blocker/provider-routing/validation/continuation state; the external sandbox broker, Docker container, GPU, browser/cloud node and `chatgpt_remote` remain replaceable Resource/provider implementations. Project-specific source, credentials, brand/content/rules and runtime payloads remain in the cell namespace and never become Engine Memory or cross-project state.
- The exact machine guidance is `docs/project-state/BIELLA_ISOLATED_PROJECT_EXECUTION_BRIDGE.yaml` (SHA-256 `b92b77ee6a4a7791217b0346225f8a893c1b7dad27c8f5c56d467621aac9d7be`). Current observed execution and Mahdi's latest instruction continue to outrank it when volatile facts differ.
- `chatgpt_remote` may receive only minimum task-scoped context and credential-free excerpts for online/current/external gaps. Responses are classified and persisted inside the originating Project/run before affecting continuation; remote provider prose never becomes canonical authority by itself.

## External customer resource handoff
- The first running external customer acquires one durable Biella customer-resource checkpoint before the customer container is started. If production is active, the runner cooperatively acknowledges the pause only at a no-child task boundary; dirty worktree bytes, task memory, compact projection, Git HEAD/tree, task identity, and exact service active/enabled states are recorded before protected services sleep.
- Protected services are `biella-codex-production.service`, `biella-qwen-residency.service`, and `biella-ollama.service`. All three have a root-only customer guard, so manual/boot starts are skipped while any `psb-*` customer container is running. Production also orders after Docker and the external broker so broker reconciliation occurs first after reboot.
- Multiple simultaneous customer sandboxes share the same checkpoint. No intermediate customer may resume Biella. The last customer stop verifies no customer remains, source-aligns the canonical repo, verifies the preserved dirty-worktree fingerprint, and restores the checkpointed service enablement/active state in dependency order.
- Customer containers use `restart=unless-stopped`. Broker reconciliation reacquires a missing runtime lease when customer containers survive a broker/host restart, and releases an orphaned lease only when no customer remains.
- A finished or highly blocked customer may submit only coding/engineering lesson records accepted by the external sanitizer. The Biella handoff revalidates them independently and stores them as digest-addressed `PROJECT_NEUTRAL_CANDIDATE_NOT_ACTIVE_AUTHORITY`; customer identity, repository/URL/path, source bodies, brand/visual/copy/rules/requirements never enter Biella authority or task memory.
- Customer private Git uses repo-scoped deploy keys generated per repository. Host GitHub OAuth credentials are used only on the host to attach a public deploy key; they are never copied into customer containers. Customer Cloudflare credentials remain customer-account scoped and are never substituted with Biella/host credentials.

## Nonblocking resource policy
- Local Qwen/Ollama is a replaceable, non-authoritative Resource. It may be used on demand but must not delay the start of the authoritative Codex turn.
- Optional provider/tool/resource failure does not stop unrelated work.
- Route cooldown polling is short and refreshes available routes rather than producing long dead intervals. Account-limit cooldowns apply only to the model that produced the observed limit; legacy blanket cooldown state is reconciled on runner startup.
- Catalog-discovered `gpt-reserve` is a strong recovery route when actually present and eligible; it is not assumed or synthesized when absent.
- Quota/balance probing remains forbidden.

## Bounded outage fallback
- Strong Codex routes retain full-task synthesis/closure authority. When normal strong routes are unavailable from observed call outcomes, Spark and local Qwen may execute only one small task-scoped technical outcome at a time.
- A bounded fallback turn uses a fresh executor session and a self-contained retrieval-first packet embedding bounded current task memory, task guide, and compact projection plus exact source/evidence references. It does not resume or replace the preserved persistent task session; bounded executor session IDs are never written into persistent task-session identity. It never broad-rereads accumulated conversation history.
- Quality order is correctness/evidence, continuity, speed, then token savings. Bounded fallback may make and validate an exact source/test/evidence increment but may not plan sections, change task order/status, lower acceptance, or declare the whole task `COMPLETE`/`COMPLETE_ALREADY`.
- Bounded packets must not create planning/status/summary artifacts merely to show activity. If the model changes no Project working bytes, that exact model+task/worktree+guide packet is marked no-progress and is not called again until the packet identity changes; another eligible bounded model may be tried once, otherwise production waits without another model call for route/state change.
- Packet/no-progress bookkeeping is derivative controller state, not a second queue, scheduler, memory system, or task authority. Exact/raw source and evidence remain canonical.

## Volatile state and validation
- `03` and `04` are live continuity/observer records and may change while production remains valid.
- Gameplay/runtime validators must not use exact byte identity of `03` or `04` as a correctness gate.
- Stable project authority such as the active Project `PRODUCTION.md`, exact implementation inputs, artifacts, and task-derived evidence remain valid validation inputs.

## Realtime canonical upgrade
- `REALTIME_CANONICAL_UPGRADE`: production upgrades the current canonical source/state/task/evidence pointers in place at safe durable boundaries; there is no parallel archive workflow and no duplicate active state tree.
- Git history and raw evidence may retain required proof/provenance, but production never starts from a stale archived snapshot when newer verified live state exists.
- Derived/rebuildable temporary outputs may be discarded once no current task/source/evidence reference requires them; unique verified proof and active task bytes remain durable.

## Persistent continuation
- Reinstalling/updating the controller preserves an already-disabled production service; owner/customer sleep is not silently re-enabled by the installer.
- Preserve task identity, Codex session identity when available, current worktree, task memory, failures, verified outputs, and continuation state.
- A pause/freeze/reconnect is not invalidation. Resume the same task/session where possible.
- `CONTINUE` means authorized work remains; `COMPLETE`/`COMPLETE_ALREADY` require task-appropriate evidence and durable source/output identity.

## Observer surfaces
- `NO_PERMANENT_WEBSITE_AGENT`: current Website production facts are a deterministic read-only projection of canonical Biella runtime/evidence through `/live-api/snapshot` and `/live-api/events`. Website source/design changes require explicit Website work; task/model/progress/validation/artifact updates do not require an agent, Website commit, or redeploy. Projection caching/indexing may improve performance but never becomes execution authority.
- Public `/live/` and private control are read-only observers.
- Open/close/refresh/reconnect/login/logout must never signal, start, stop, pause, or advance production.
- Stale detection must allow more time than the normal production heartbeat interval so a healthy runner does not falsely oscillate to STALE.

## Durable completion
- Real editable output plus task-derived validation is required.
- Commit task implementation/evidence before `COMPLETE`.
- GitHub/Drive publication uses canonical destinations and remote readback where required.
- Publication failure preserves local work and remains `CONTINUE`; it never fabricates completion.

## Nonblocking acceptance and execution quality
- `OWNER_ACCEPTANCE_FAST_PATH`: Mahdi's explicit acceptance of the current task is applied immediately through the canonical completion transition; no additional model turn, reviewer, approval hook, or task-class delay is permitted. The transition persists Git/Drive continuity and advances to the next canonical task automatically.
- `TASK_CLASS_IS_NOT_A_BLOCKER`: `hard`, `hard_creation`, `deep_memory`, and other task classes describe complexity only. They never create a wait state, extra approval requirement, or permission to expand acceptance scope.
- `NO_MONITOR_ONLY_STALL`: a model may wait on an already-running productive external process, but it must not spend repeated reasoning/tool turns merely polling or narrating progress. Long deterministic work is treated as a Resource wait; the model must not create polling/narration loops while that Resource is already productive.
- `NO_EXTERNAL_PROGRESS_HOOK_DEPENDENCY`: task completion/advancement is controller-native. Browser state, chat lifecycle, git hooks, website events, and external observer callbacks are never required for liveness or progression.
- `CACHE_EFFICIENCY_QUALITY_FIRST`: reuse the persistent task session, compact task memory, verified outputs, prompt-cache-friendly stable context and cached local-assist results. Prefer deterministic/local/specialized/free-fit Resources before general-model work when they preserve correctness. Never pad prompts, probe quota, or reduce reasoning/acceptance quality merely to save tokens.
- Authoritative synthesis and closure use the highest-quality eligible strong route and its highest supported reasoning level under current owner policy; bounded/local fallbacks cannot lower acceptance or self-promote to task authority.
- `PROJECT_DATA_LEAKAGE_FORBIDDEN`: Engine/Project/customer namespaces remain isolated; token/cache optimization never broadens context across Project boundaries or copies credentials/customer source into shared memory.

## Maintenance progress transaction
- `MAINTENANCE_PROGRESS_TRANSACTION`: manual/management progress edits use `SLEEP/FREEZE -> EDIT -> VALIDATE -> SYNC/READBACK -> RESUME`.
- Progress authority includes `03`, `04`, `PRODUCTION.md`, current-task pointers, task status and task order.
- No manual progress mutation is allowed concurrently with an active Codex child turn.
- Controller-native completion/advancement occurs only after the child turn exits, so it is already a safe child-free progress transaction.
- The maintenance transaction is explicit and owner/management initiated; it must never be triggered by an inactivity timer, watchdog, no-progress marker, optional local model readiness, reviewer hook, website observer, or chat lifecycle.
