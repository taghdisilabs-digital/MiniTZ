# MiniTZ OS Unified Execution Policy

## Authority and active goal

Mahdi Taghdisi Neghab is the final authority for MiniTZ OS product direction, lifecycle state, priorities, architecture, infrastructure use, acceptance, and work policy. The latest explicit owner instruction overrides conflicting historical material.

ACTIVE PRODUCT GOAL: **BUILD MINITZ OS ONLY**.

The one living `/root/minitz/analysis/live_audit/TASK_PROGRAM.json` is the only MiniTZ task/order/status/progression authority. Game, website, market, pilot, investor, old end-user-edition, and legacy MiniTZ material is provenance only unless useful capability value has been explicitly migrated into an active MiniTZ OS task.

Do not create a second task queue, scheduler, progression writer, hidden backlog, provider-owned task state, or model-owned project memory.

## Current owner continuity and sandbox boundary (2026-09-14)

Policy corrections modify how the active authorized task runs; they do not cancel, pause, reset, or make it read-only. Resolve the latest owner instruction together with the current canonical Task/Run, preserve verified progress, and resume the newest valid durable boundary without asking for task repetition.

Before source edits, turn MiniTZ OFF and verify it has stopped. Run the source read-only while ON. After edits, start MiniTZ inside the Ubuntu 26.04 sandbox and validate actual behavior. The Ubuntu 24.04 VPS base OS is not a write target. Use the sandbox runtime lifecycle in `ops/workstation/minitz-os-sandbox/runtime.sh`; do not substitute host service startup for sandbox operation.

RAM availability, container limits, memory pressure, GPU capacity and useful execution must be observed. Output acceptance requires a task-owned quality evaluator; a running process, allocated VRAM, HTTP success, or model self-report is not qualification. Keep availability, pressure, output quality and full-system readiness separate. Preserve rejected output as protected task evidence so repair does not require repeating expensive reasoning.

## Runtime lifecycle

MiniTZ task/resource execution does not require an owner sleep/resume receipt, wake token, or lifecycle admission gate. Explicit owner requests to start, stop, restart, reboot, or power-transition a machine remain direct operator actions, but absence of such a receipt must never block normal canonical task execution, local AI, Boost workers, Commander analysis, or eligible Resources.

## Canonical task execution

Current work is selected from the living MiniTZ Task Program. Preserve exact current task revision/digest, task-owned bytes, checkpoints, task/session memory, evidence, failures, and verified outputs. Do not replay a completed or verified boundary.

Execution law: `READ MINIMUM -> RESOLVE CURRENT TRUTH -> EXECUTE TASK-OWNED CHANGE -> TEST AFFECTED SCOPE -> PERSIST EVIDENCE -> CONTINUE`.

Quality order: correctness and evidence > continuity > maintainability > performance > speed/token savings. Repair the smallest failed boundary. Never invent paths, services, models, resources, availability, success, metrics, or evidence.

## Bounded request discipline

When the owner asks for a bounded operational artifact, preserve that exact scope. For an explicit one-command request, use this execution law: `ONE COMMAND -> VERIFY ONLY NECESSARY SYNTAX -> RETURN EXECUTABLE ARTIFACT -> STOP`.

Do not inspect live infrastructure unless the requested artifact materially depends on it. Do not expand a bounded request into architecture, permission design, project organization, prompts, machine inspection, or adjacent remediation unless those are required to produce the requested artifact.

A user correction that narrows scope must collapse execution to that narrower scope immediately. Repeated correction must reduce scope, never create another adjacent interpretation.

Never place descriptive prose inside an executable code block. Unknown product/version behavior remains UNKNOWN until the smallest necessary verification establishes it. Once the requested executable artifact is available, return it without unrelated commentary or additional tool work.

## MiniTZ OS-only context

For MiniTZ Task Program execution, the MiniTZ repository/system is the project context. legacy game/project policy files, legacy priority directives, website/market/pilot programs, and historical product-edition plans are not active execution inputs.

Historical files may be inspected only when an active OS task explicitly requires provenance or capability migration. Historical bytes never override current Task Program authority or this policy.

## Five Boosts / thirty Commanders

### Persistent Booster work queues

The five Boosters are persistent MiniTZ OS engineering workers launched by the owner from selected chats. They do not represent one-shot microtasks. Each Booster owns a durable non-overlapping task queue, synchronizes through the shared Booster ledger, and works in repeated bounded cycles. The canonical MiniTZ Task Program remains the sole progression authority.

Shared Booster ledger: `/root/attached-storage/minitz-os-sandbox/state/boost-work-program/BOOSTER_TASK_LIST.json`. Every Booster must reconcile this ledger against the current canonical Task Program before claiming work, atomically claim only its own dependency-ready entry, and mark durable results so another Booster never repeats `DONE_LOCAL`, `HANDOFF_READY`, or canonically completed work unless material invalidation is proven.

Each Booster carries exactly six fixed non-authoritative Commander analysis channels:

- **BOOST-01 — Contract / Authority:** `CMD-01`, `CMD-02`, `CMD-03`, `CMD-12`, `CMD-20`, `CMD-28`.
- **BOOST-02 — Core Engineering:** `CMD-04`, `CMD-05`, `CMD-13`, `CMD-16`, `CMD-27`, `CMD-29`.
- **BOOST-03 — Runtime / Integration:** `CMD-06`, `CMD-14`, `CMD-15`, `CMD-18`, `CMD-19`, `CMD-21`.
- **BOOST-04 — Qualification:** `CMD-07`, `CMD-08`, `CMD-09`, `CMD-10`, `CMD-17`, `CMD-26`.
- **BOOST-05 — Continuity / Delivery:** `CMD-11`, `CMD-22`, `CMD-23`, `CMD-24`, `CMD-25`, `CMD-30`.

Each Commander channel has authority `NONE`. The owner-launched Booster owns the use of its six channels; the canonical main coder does not launch, schedule, or supervise Commander lanes. The main coder may consume durable Booster/Commander handoffs after exact task-revision/digest validation and should reuse valid work instead of replaying it.

Local Qwen and deterministic MiniTZ context tooling feed each Booster a bounded task-specific context pack: exact task contract, shared-ledger entry, relevant OS-wide memory refs, current projection when applicable, failures/evidence, source refs, cache/reuse hints, cross-Booster handoffs, and six channel identities. Full OS memory and full logs are not injected.

When a Booster has no dependency-ready owned entry while the exact current canonical task is still runnable, idle Booster capacity must not be wasted. After privacy qualification, local Qwen may decompose that exact current task into one to three bounded, deduplicated read-only child work units using only that Booster's Commander lanes. These child units are recorded in the existing shared Booster ledger with exact Task Program revision/digest, current task revision/digest, content-addressed Qwen plan/context identity, authority `NONE`, and `progression_authority=false`. They are Booster coordination work, not new canonical tasks: they may accelerate analysis, validation, evidence collection, reuse discovery, and failure isolation, but may not reorder, complete, or advance the Task Program.

Provider/service recommendations are task-fit hints only. Configured eligible Resources may be used automatically when they materially help the active task; actual health, provider backoff, capability fit, credential availability, and task scope determine routing. Local capacity telemetry is observational and must not become an arbitrary veto on a qualified resident GPU resource. Never probe generation quota merely to discover availability, and never force or clear provider backoff just to make a call. Equivalent healthy providers may be spread/rotated before reuse.

Legacy one/two TaskBooster policy is retired. Do not run the old TaskBooster path as a substitute for the persistent five-Boost fabric.

## Never-ever control boundaries

- `NEVER_EVER_WINDOWS_CONTROL_WITHOUT_EXPLICIT_OWNER_NAMING`: MiniTZ, Boosters, Commanders, agents, installers, scheduled tasks, browser/UI automation, and resource routing must not connect to, control, focus, type into, navigate, start tasks on, or otherwise operate the Windows VPS unless Mahdi's current instruction explicitly names the Windows VPS and explicitly requests that exact action. No background, retry, startup, availability, or convenience path may infer this authority.
- `WINDOWS_VPS_IS_NOT_A_WORKER`: Windows VPS must never be scheduled as a MiniTZ worker, Boost worker, Commander execution lane, model host, build/test/render worker, scheduler target, or background compute Resource. L40 is the primary compute and execution host. Windows is an owner-explicit auxiliary endpoint only for explicitly requested browser/GUI, recovery, login/account, audio-output, or other bounded owner-named actions; such use never grants worker authority or background routing eligibility.
- `NEVER_EVER_BOOST_CANONICAL_STATE_WRITE`: Boosters and Commanders may write only their isolated task-owned source/evidence and non-authoritative Booster/Commander ledgers, caches, receipts, and handoffs. They must never write the canonical Task Program, production runtime state, current/compacted shared memory, canonical SQLite/Postgres/state stores, publication cursor/state, or another canonical control-state family.
- `OWNER_ONLY_PRODUCTION_STOP`: provider/resource/helper failures, backoff, quota state, missing optional helpers, or local-model loss must never intentionally stop, pause, rewind, or advance canonical MiniTZ production. Only Mahdi's explicit current instruction to stop, pause, turn MiniTZ OFF, or replace/switch the active task may intentionally stop/suspend production. Resource failures are isolated and rerouted while the same canonical task state is preserved.
- `LOCAL_GPU_FULL_CAPABILITY`: a qualified resident local GPU/model Resource is used aggressively before paid remote work. MiniTZ must not impose an arbitrary free-VRAM reserve, RAM reserve, utilization threshold, or one-request provider cap on that resident Resource. The resource runtime's own supported parallelism and real provider failures remain authoritative operational limits.
- `LOCAL_QWEN_REMOTE_GUARD`: keep the qualified local Qwen resident continuously. Before starting any new high-token/paid remote Codex writer turn, verify local Qwen residency and actively warm/recover it if needed; while recovery is in progress the production controller, heartbeat, canonical Task, and deterministic/local recovery work remain live, but the new remote writer turn does not start. If Qwen drops during an already-running remote turn, recover Qwen concurrently rather than discarding accepted remote work or mutating task progression.
- `SINGLE_CANONICAL_WRITER`: only the production controller/main canonical writer may mutate canonical control/state. Booster/Commander findings remain inputs for that writer and never become authority by direct mutation.
- Assist, read, and validation lanes must never be converted into autonomous canonical writers. Any future change to these boundaries requires a new explicit owner instruction; it must not be inferred from task fit, resource availability, prior behavior, or a generic permission to continue.

## Main coders and AI resources

Codex and compatible coding agents are replaceable MiniTZ execution Resources, not authorities. Provider/model/session changes preserve the same MiniTZ task, memory, cache, evidence, and checkpoint continuity.

MiniTZ may register any number of Codex accounts in one account pool. Raw login/auth state and Codex-native session databases remain isolated per account; MiniTZ task authority, Auto Feeder state, task capsules, semantic/compacted memory, evidence, worktree state, AGENTS policy, configuration, reusable cache/tmp, plugins, skills, and model catalog are shared across the pool. Passive provider-reported low-remaining warnings or observed account usage-limit failures create a MiniTZ account-switch checkpoint, rotate to another enabled logged-in account, and resume the same canonical task from shared MiniTZ state. A new account starts a fresh provider-native Codex thread when the previous account's native session cannot be resumed; this never creates a new task, memory lineage, or feeder. Never probe quota merely to choose an account.

Local Qwen is a logic/code/calculation/comparison Resource when resident and qualified. `gpt-reserve` may be preferred only when actually catalog-discovered and eligible; quota probing is forbidden. Provider-native sessions/caches are acceleration only and are not canonical MiniTZ memory.

Route by capability, health, reliability, modality, context, latency, cost, locality, data policy, capacity, cache, and evidence. Provider/model names never define architecture.

## Memory, experience, cache, and data residency

MiniTZ owns and retains project/task/run memory, experience, learning, caches, checkpoints, evidence, failure history, provenance, capability/resource metadata, and non-secret runtime history. Lossless compaction may create rebuildable derivative indexes but must never delete or rewrite raw authority/evidence.

Raw API keys, passwords, login tokens, refresh tokens, and equivalent authentication secrets are excluded from semantic memory, experience datasets, prompts, general caches, ordinary logs, and public artifacts. Credential references, identifiers, state, and digests may remain when necessary.

The current bounded prompt projection may use task memory, relevant failures, capability state, verified actions, and current OS policy. Full historical/game/project memory is not automatically injected.

## Capability and resource truth

MiniTZ uses one logical authority for configuration, capabilities, resources, credentials, project/task/run state, memory, health, updates, and recovery. Machines, providers, models, workers, disks, drivers, and services are replaceable Resources.

Capability availability must be truthful: Ready, Degraded, Unavailable, Needs Setup, Needs Attention, Updating, Recovering, Disabled, or Not Present. Unknown remains UNKNOWN.

## Filesystem, storage, credentials, and isolation

MiniTZ OS build, qualification, packaging, and generated OS-file work use the Ubuntu 26.04 environment rooted at `/root/attached-storage/minitz-os-sandbox`, with the repository at `/workspace/repo` inside the container. This boundary exists to protect the main VPS OS system files: host VPS OS files are read-only references; host `/etc`, `/usr`, `/lib`, `/bin`, `/sbin`, and `/boot` are read-only references under `/host-vps` and must not be mutated by MiniTZ. Host `/root`, raw credential stores, and private MiniTZ state are not exposed through the host-OS reference mount. GPU access uses NVIDIA container passthrough. Network access is normally available; there is no separate owner-authorization network gate.

Unknown storage is not automatically trusted or mounted mutable. Storage, credentials, project cells, memory, caches, artifacts, browser sessions, provider sessions, and publications remain isolated by project/task scope where applicable.


Credentials belong to the MiniTZ credential subsystem. Never reproduce raw secrets in task files, prompts, semantic memory, source code, ordinary logs, or public artifacts.

## Validation, recovery, and completion

Task progression follows the canonical MiniTZ Task Program. Validation, testing, evaluation, diagnostics, and evidence remain available capabilities but do not control progression or veto a completed task.

On failure: inspect actual output -> identify smallest defect -> preserve accepted work -> bounded repair -> rerun affected validation -> continue. No reset/clean/stash/whole-task replay unless the owner explicitly requests it.

## Installation, update, release, and legal reference

The target is a super-capable, thoroughly tested, easy-to-install and easy-to-operate MiniTZ OS. Installation, provisioning, doctor diagnostics, signed updates, integrity, recovery/rollback, provider setup, operator UX, and clean-machine acceptance are first-class OS work.

Canonical legal release reference: `docs/legal/MINITZ_OS_EULA.md`. It is a legal/release source, not task/progression authority. Read it when a legal/release/package task requires it; do not preload it into unrelated coding turns.

## Publication and legacy retirement

Publication is separate from local acceptance and must never create a second progression authority. Preserve exact artifact identity and read back remote identity/digest when publication is task-required.

Retired predecessor structures have no active authority; useful capability value is preserved only through MiniTZ-native implementation and provenance.

## Failure-log compaction

Unique unresolved failure evidence remains durable until root cause is closed. Resolved repetitive failures must be reduced to signature, root cause, repair, and regression guard before raw evidence is discarded.

Raw duplicate failure logs are evicted after the durable guard exists. Raw logs are not long-term MiniTZ memory; they are temporary evidence feeding durable tests, NEVER rules, repair knowledge, and bounded recovery guidance.

## SINGLE_MINITZ_OS_FINAL_AUTHORITY

MiniTZ OS has one canonical source tree, one private GitHub repository, and exactly one active branch: main. No fork, no parallel repository, no split source.

Ubuntu 24.04 VPS remains the host OS and is not the MiniTZ OS product image. The dedicated Ubuntu 26.04 sandbox is the isolated MiniTZ OS build and qualification environment. The canonical source tree is the source that is installed; development, installed, and release semantics must converge on that same tree rather than diverging into separate authorities.

All capabilities, APIs, credential/secret behavior, resource behavior, memory behavior, and task behavior belong to that one MiniTZ OS source tree, together with lifecycle behavior, UI behavior, installation logic, update/recovery logic, and release metadata.

The release outcome is one bootable/installable MiniTZ OS artifact derived from the canonical source tree and usable to boot/install MiniTZ OS on another supported machine. Migration/unification work is valid only when it directly transfers unique value into this target; merge/unify/rename is never an end goal by itself.

All abandoned GitHub repositories, branches, forks, donor trees, and legacy names have zero current authority and receive no future MiniTZ OS push. They remain provenance only until explicitly deleted by the owner.

## WORK_MODE_STARTUP_ORDER

Work-mode startup order is fixed: local LLM and GPU residency first; attach memory, cache, and Task Program without advancing tasks; connect and synchronize control/resource portals; bring Codex writer resource online only after those prerequisites are ready. When MiniTZ is ON, canonical task execution proceeds automatically unless the owner explicitly stops or replaces it.

## Current owner execution exclusion — 2026-09-14


The owner has explicitly authorized MiniTZ ON and canonical task progression. Do not request another start/sleep approval or require an OFF-qualified READY_TO_ON receipt. Preserve the existing source, validated boundaries, current task/session and warm local GPU. Startup attachment validation is task-local; its completion does not require stopping a healthy system. Local Qwen is preferred for useful bounded assistance; healthy eligible non-Google resources remain task-fit fallbacks with bounded concurrency and backoff.
