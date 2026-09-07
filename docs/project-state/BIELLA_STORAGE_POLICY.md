# Biella Realtime Canonical Upgrade and Storage Policy

Status: OWNER_DIRECTED_EXECUTION_POLICY
Authority: Mahdi Taghdisi, latest explicit direction 2026-09-08; this supersedes the prior cold-archive/offload workflow.
Scope: live source/state/evidence durability and storage placement; not a second task queue or history system.

## REALTIME_CANONICAL_UPGRADE

`REALTIME_CANONICAL_UPGRADE` is the operating rule. Upgrade the real canonical source, state, task packet, runtime contract, implementation, and Drive counterpart in place as verified truth changes. There is no parallel archive workflow and no duplicate active snapshot tree.

Replace stale volatile facts with higher-authority live facts immediately at the next safe durable boundary. Preserve independently valid progress, capabilities, reusable methods, task identity, verified outputs, and exact evidence while replacing only stale or invalidated content.

Git history and raw evidence provide provenance when proof is required. They are not a second active state, are not normal retrieval authority, and must not be copied into a parallel operational archive. Failure/event ledgers remain append-only proof because execution recovery depends on them.

## Canonical storage

Keep the canonical repository at `/root/biella/repos/biella-engine`, shared Codex home at `/root/.codex`, active runtime under `/mnt/biella-extra/biella-runtime`, and active Project artifacts at their current canonical Project paths. Use attached storage only as temporary task-scoped staging when materially useful; staging is never canonical authority.

For Drive-backed canonicals, revise the existing canonical file identity where possible and verify exact remote readback. Do not create a new dated/suffixed copy merely to preserve the previous revision. Drive/Git provider version history may exist as provider provenance, but production reads the current canonical identity.

## Evidence and cleanup

Do not delete unique evidence, required recovery state, accepted artifacts, or current task bytes merely to make the tree smaller. Rebuildable caches, redundant transient captures, temporary package workspaces, and superseded derivative indexes may be removed when current task/source references prove they are no longer required.

Do not create archive manifests, cold-storage indexes, restoration queues, duplicate status summaries, or parallel historical task packets. No parallel archive workflow may become a prerequisite for execution, recovery, publication, or source refresh.

Existing legacy historical material is inactive evidence only. Do not write new operational state into it, do not rehydrate it into current authority, and do not make production depend on it. Any destructive cleanup of legacy material remains a separate explicit task and must preserve currently required proof.

The rule is continuous: observe current truth -> upgrade canonical state/source in place -> validate -> persist Git/Drive/runtime identity -> continue execution.
