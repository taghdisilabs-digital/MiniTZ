# Prompt 01 — Durable Continuation, Resume, and No-Redo Protocol

## Objective

Make “continue from what is already done” the default execution behavior. A process crash, SSH disconnect, model/provider/GPU/browser failure, or one failed Node must not force the entire Task to restart.

## Continuation invariant

For every meaningful work unit preserve enough identity to answer: Task revision, Graph revision, Node/work unit, exact inputs/source revisions, produced output/artifact, verification state, storage location, remaining work, changed dependencies, and current vs stale result. Conversation memory is never the only copy.

## Reuse before redo

Before executing a work unit: look for a prior verified result; compare input/source identity; verify artifact/digest; reuse it when valid; execute only missing or invalidated work.

Do not rerun a completed Node because a new Codex session started, tmux reattached, another provider was selected, an unrelated Node failed, a plan document reopened, or a new worker appeared.

## Idempotency concept

A productive work unit should eventually have a stable idempotency identity derived from material facts such as:

`project + task_revision + graph_revision + node + exact_input_refs + capability_version + relevant_tool/runtime_config`

Do not include unrelated ephemeral facts that cause pointless reruns.

## Failure recovery

Recover the smallest affected boundary. Preserve verified earlier render frames, completed audio stems, independent 3D assets, unrelated production branches, and durable Run truth. Retry/re-route only the bounded provider call or worker attempt that failed.

## Invalidation

Invalidate a completed result only when evidence shows a material dependency changed or the result is bad: changed input/source digest, changed contract, incompatible runtime when material, missing/corrupt artifact, or failed validation. Do not invalidate by ceremony.

## Durable vs cache

Durable: Task/Run/Graph state, accepted source, Artifacts/content identity, checkpoints, event/evidence records, Project knowledge, promoted Engine knowledge.

Rebuildable cache: embeddings, browser cache, compiler/build cache, shader/render cache, model weight replicas, KV/prefix cache, thumbnails/proxies.

Cache loss may cost time; it must not erase authoritative work.

## Concurrency

Independent work should execute concurrently when dependencies permit, resource contention is acceptable, and output/side effects do not conflict. Serial execution requires a real dependency/resource reason.

## Current workstation continuity

Reuse `/root/biella`, the installed toolchain, existing repository if present, and completed installation stages. Add only a specific missing dependency a real Task proves necessary.

## Execution prompt

> Resume the current Task from durable evidence. Inventory only work units relevant to the current objective, mark verified existing outputs reusable, identify the smallest missing/invalidated units, and execute only those. Persist each meaningful output/checkpoint as it completes. If one unit fails, continue independent unaffected work and recover the smallest failed boundary. Never reset or redo the whole Task merely because a process/session/provider/worker changed.
