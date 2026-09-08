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

## Source alignment and inline repair
- Boot verifies the canonical local checkout and attempts a bounded fetch. Aligned/local-ahead source continues. Compatible non-overlapping remote updates fast-forward without reset, clean, stash or history rewrite.
- A network/authentication/transport failure is reported as `REMOTE_UNAVAILABLE_LOCAL_CONTINUATION`, not fabricated alignment. Valid retained local source remains executable; publication retries independently.
- A known source difference is `RECONCILIATION_REQUIRED`: the existing authoritative task/session receives the exact repair, preserves both revisions and current bytes, and uses an ordinary compatible merge/fast-forward. It does not stop/restart the production service or spin a known-stale push loop. Unresolved differences are not falsely accepted as aligned or complete.
- Bootstrap/controller source refresh preserves service enablement; the runner executes from the canonical repository. Source repair is task-scoped work, not a permanent extra reviewer or progress hook.

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
- Bounded packets must not create planning/status/summary artifacts merely to show activity. A bounded turn that changes no Project working bytes is only an observed no-change result; it does not block the task, route, packet, stronger models, local deterministic work, or later execution.
- Cache/dedup may avoid paying twice for identical reusable context, but cache state never creates a wait state or becomes task authority. Exact/raw source and evidence remain canonical.

## Volatile state and validation
- `03` and `04` are live continuity/observer records and may change while production remains valid.
- `03` and `04` do not persist attempt numbers, PIDs, child liveness, active model/reasoning, or point-in-time Git commit/tree snapshots. Those fast-changing facts are read from `runtime.json`, systemd and live Git so a restart cannot make canonical continuity files stale by construction.
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
- Implementation acceptance and remote publication are separate. Publication retry never fabricates remote completion and never reopens locally accepted implementation. Deployment/external-delivery tasks still require the real external outcome.

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

## Hardened continuous-cycle contract
- Boot path is `systemd -> Docker/broker reconciliation -> customer guard -> GitHub source alignment -> canonical production runner`; optional Qwen/Ollama, Website, browser, chat, and observer state never gate authoritative production startup.
- The steady loop is `RESOLVE CURRENT TASK -> LOAD BOUNDED CURRENT CONTEXT -> EXECUTE -> VALIDATE -> COMMIT CANONICAL TASK OUTPUT -> COMPLETE -> PERSIST/REMOTE READBACK -> ADVANCE -> NEXT TASK`. `CONTINUE` stays on the same task/session and must identify real unfinished work.
- `CLEAN_TASK_BOUNDARY`: finalize coherent validated task-owned source/proof into Git without another model turn merely to commit. Preserve and exclude unrelated dirty paths. Known unnecessary task-local scratch may be removed; required proof and unique outputs are never hidden or deleted to make Git look clean. A genuine local-write failure requires repair of that exact operation, not replay of passed work.
- Completion is controller-native and child-free: after a validated task result, commit task-owned output, update and commit canonical continuity, record the publication cursor, and immediately select the next unfinished task. Publish/read back GitHub/Drive through the controller-owned deterministic helper. No reviewer, inactivity timer, Website callback, browser, chat, Git hook, Qwen readiness check, or task-class label participates in advancement.
- Cache and local Qwen are accelerators only. Compact memory is rebuilt from current authority/evidence and may reduce rereads; Qwen may perform bounded assistance when useful. Cache/Qwen failure or non-use never creates a wait state and never lowers strong-route acceptance quality.
- Workstation/resource installer refreshes preserve any already-running Ollama/Qwen state as well as enablement. Installation may not silently turn an active optional Resource into downtime; it also does not auto-start a Resource that was intentionally inactive before the refresh.

## HOW BIELLA WILL NOT WORK

The following patterns are forbidden because they caused observed waste, stalls, incorrect continuation, or unnecessary resource use during the 2026-09-07/08 production window. They are failure patterns, not fallback modes.

- `post_acceptance_task_extension`: once Mahdi accepts the current task, no model may add another gate, experiment, polish pass, or continuation before canonical closure and advancement.
- `timer_executor_rotation`: model silence or lack of emitted events is never sufficient reason to kill, rotate, or restart a healthy executor/session.
- `no_progress_wait_state`: a no-change bounded/local result never creates a task wait state, suppresses later execution, or blocks stronger/local deterministic work.
- `optional_local_ai_startup_gate`: Ollama, Qwen, GPU residency, website/control, helpers, and optional providers never gate authoritative production startup.
- `installer_enablement_toggle`: source/controller refresh never silently enables or disables an existing production service; maintenance controls enablement explicitly.
- `concurrent_manual_progress_edit`: management never edits `03`, `04`, `PRODUCTION.md`, task order/status, or current-task pointers while the production child is executing.
- `format_by_renaming`: changing an extension never qualifies or converts a binary/artifact format; format/magic/schema and consumer contract must be verified before use.
- `guessed_path_without_lookup`: commands and edits use retrieved exact paths/symbols/interfaces; path guessing followed by repeated failed commands is forbidden.
- `request_time_full_asset_scan`: observer/API requests must not repeatedly rescan large asset trees or run expensive system probes when an incremental/cached read-only projection can serve current truth.
- `missing_bootstrap_auth`: production/customer source alignment must inherit or explicitly load the verified host GitHub identity required by that exact operation; authenticated host state may not be silently dropped at bootstrap.
- Historical raw evidence may record these failures, but none of these patterns may exist as an active controller mechanism, startup dependency, task state, or execution policy.

## PROVEN EXECUTION STYLE

`biella_execution_style.proven_execution_style()` (`ops/local-ai/biella_execution_style.py`) is the executable compact statement of the production style that is retained because it produced useful progress without lowering acceptance quality. `proven_execution_style_prompt()` injects the same rules into authoritative strong-task turns.

- Highest-quality eligible strong route for synthesis/closure; current owner policy may pin a specific verified route/reasoning level.
- Persistent task/session continuity and exact verified-work reuse instead of restarting from narrative history.
- Immediate canonical closure/advance after accepted completion; task class describes complexity only.
- Optional local/free/specialized resources are used when useful but never become startup or liveness dependencies.
- Stable compact/cached context and verified outputs are reused quality-first; cache reduces repeated token/work cost but never becomes authority or a wait condition.
- Exact source/path/interface retrieval precedes commands and edits when a value is retrievable; UNKNOWN remains UNKNOWN instead of becoming a guessed target.
- Manual progress/state edits are transactional: `SLEEP/FREEZE -> EDIT -> VALIDATE -> SYNC/READBACK -> RESUME` with the exact task/session and current working bytes preserved.
- Long deterministic resource work may run to completion without model polling loops; quiet strong-model reasoning is allowed to remain quiet.
- Project/customer isolation is preserved across cache, routing, delegation, artifacts and memory.
- This style is an execution rule, not a new scheduler, reviewer, agent hierarchy, progress ledger, or archive authority.

## Nonblocking publication and bounded task mapping
- `biella_publication.py` owns a single coalescing publication cursor inside the actual canonical Git directory. It is not a task queue, source authority, archive or separate service. Exact committed bytes are the retry source; current files are never guessed from stale chat.
- One helper thread inside the existing controller publishes and verifies GitHub and Drive independently of model execution. Network operations have bounded request timeouts; timeout does not kill, rotate or sleep the production task/session. The cursor survives controller restart and retries without a new model turn.
- `LOCAL_PERSISTED_PUBLICATION_PENDING` is not `PUBLISHED`. Every remote receipt records the exact revision and digest; publication failures remain observable. Newer canonical revisions coalesce the desired destination, preserving prior source/proof in Git rather than generating duplicate active snapshots.
- The next-100 map covers D05-01 through D23-05. It records actual canonical dependency edges and task contracts. The runner loads only one entry and uses its existing Games/Website/Engine execution directory. All task states still derive from `projects/biella-games/docs/PRODUCTION.md`; the ledger is regenerated from it, never a second mutable queue.
- Actual Windows packaging, independent-player feedback, contracted usage, external delivery, and required runtime evidence cannot be replaced by invented results. Finish all independent authorized work and route the exact missing operation to a compatible configured Resource. Unknown shipping budgets are not fabricated; measure/report when the existing contract permits it.
- Regression tests must not call the host's real service controls. Customer checkpoint uses the mockable service boundary; resume clears the acknowledged pause request before production starts so it cannot immediately pause again.
