# Biella Durable Source and Synchronization Rules

Date: 2026-09-05

## Roles

- **GitHub** = durable code/source history and durable copies of accepted architecture/execution specifications required to rebuild/operate the project.
- **Google Drive** = live operator/project documents, current-state registers, prompt pack, migration ledgers, and chronological continuity.
- **ChatGPT management conversation** = exactly one owner-designated current human management channel; all other ChatGPT conversations/threads are `RETIRED_FROM_CURRENT_BIELLA_AUTHORITY` and may be used only as historical continuity/evidence. ChatGPT is never production liveness or execution state.
- **Canonical local workspace** = persistent execution/source and pending-publication output; never disposable while it holds unique current work. Only rebuildable worker copies and cache are disposable.
- **Cache** = disposable optimization only.

## Live-source currentness rule

For any mutable Biella fact that materially affects the active task, **read the current connected source before treating the fact as current**.

Mutable facts include:

- active task and current-state records;
- exact prompt status/body when executing that prompt;
- GitHub commit, tree, branch and relevant source paths;
- Drive live document/file contents and revisions;
- implementation/publication/completion status;
- runtime, provider, model, tool and Resource availability;
- task outputs that may have changed since the prior observation.

Rules:

1. A prior chat message, remembered value, earlier tool result, old Git commit, old Drive revision, or prior completion report is evidence of **past state** only until live currentness is established when the active task depends on it.
2. Read only the smallest relevant GitHub and/or Drive sources needed by the task; do not perform broad re-audits of unrelated stable material.
3. Local state/ledger and GitHub publication remain per-task. Routine Drive publication is every five additional completed tasks in parts capped at 3,800,000,000 bytes; recorded batching never means rollback or false synchronization.
4. If GitHub and Drive disagree, resolve by current project authority, exact revision/identity, and task relevance. Never synthesize conflicting claims.
5. If a required current fact cannot be observed, record `UNKNOWN` rather than infer it.
6. Chat/project history remains valuable for continuity and discovery, but current observed durable sources outrank remembered history for mutable facts.

## Promotion rule

```text
local implementation
→ task-derived validation
→ local source/proof and continuity commit
→ accepted task closure and next task

Independent publication:
GitHub per-task -> exact readback
Drive every five additional completions -> exact package/file readback
```

A local commit is not proof of off-machine replication. Local acceptance and remote publication are tracked separately; the publication cursor retries the latter without re-running the former.

## Project-document synchronization

When a project-level architecture/behavior/execution decision becomes active and materially affects future implementation:

1. record it in the appropriate Drive live document;
2. persist an equivalent durable GitHub spec/plan/state snapshot when future code execution depends on it;
3. record exact GitHub commit and Drive file/revision references;
4. do not allow old local-machine facts to override newer durable remote state;
5. preserve historical evidence instead of silently rewriting provenance.

## Failure semantics

Worker/workspace/cache loss MAY reduce speed or capacity.

Worker/workspace/cache loss MUST NOT destroy:

- accepted source;
- accepted contract/specification needed to reproduce source;
- Run/Event truth once those systems exist;
- Artifact identity/content where durability is required;
- Project/Engine Knowledge once promoted;
- prompt/execution boundary needed to resume work.

## Spot/ephemeral compute rule

Spot or otherwise reclaimable compute may be used only for disposable/rebuildable workers after durable state exists elsewhere.

It must not be the only location of canonical Biella source or accepted execution state.

## Historical P0-01 provenance — not execution authority

The previously observed local P0-01 SHA `b7cc3db0a9feb34d72764261d32163d2b05ac123` is retained as historical evidence only because its exact Git objects are not present in the connected GitHub history and the original Spot workspace is unavailable.

This missing historical object is not an instruction to reopen P0-01 or replace later accepted implementation. Current source and the canonical task ledger determine continuation. Preserve the historical identity for provenance only.

## Hardened execution law — 2026-09-05

- `SINGLE_CODEX_AUTHORITY`: one Codex task/session owns authority, synthesis, edits, validation, completion, and task advancement. Parallel Codex/subagent fan-out is disabled for production.
- `RESOURCE_PARALLELISM`: independent bounded work may execute concurrently through verified Resources when dependencies, side effects, and capacity permit. Local Qwen/Ollama, Cloudflare Workers/AI, external APIs, GPU tools, DCCs, build systems, and other Resources are implementations, never second authorities. Cloudflare is used only through an actually configured callable capability adapter.
- `LOCAL_FIRST_EFFICIENCY`: before spending general Codex reasoning on bounded preprocessing, code review, classification, summarization, log triage, reasoning assistance, or Unreal assistance, prefer the configured local Qwen Resource when it can perform the work without reducing correctness. Reuse compact task memory, prompt caching, bounded tool output, and deterministic/local commands.
- `FINAL_DELIVERABLE_PUBLICATION`: preserve exact canonical local output and task-derived proof. The controller commits task-owned output and continuity locally, records the exact Git revision in its durable publication cursor, and retries GitHub/Drive independently. A transport failure does not reopen validated implementation or stop unrelated execution. `COMPLETE` records satisfied task acceptance; `PUBLISHED/VERIFIED` requires actual remote identity and readback. When deployment, external delivery, or a remote operation is itself the task deliverable, its real evidence remains required. Never invent a destination or claim remote durability from a local commit.
- `DURABLE_FAILURE_LEDGER`: every observed production/model/provider/tool/runtime/validation/publication failure or retry is recorded in AI-readable JSONL at `/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl` with task/time/type/status and bounded diagnostics. Failure records aid diagnosis and never override current source/task authority.

- `LOSSLESS_MEMORY_COMPACTION`: raw authority, evidence, artifacts, task records, and failure records are never rewritten or deleted by compression. The compactor creates rebuildable derivative JSON/JSON.GZ indexes with exact source digests, content-addressed unique records, equivalence groups that retain every exact variant and provenance, and a bounded current-task projection. Compaction failure is an optimization failure only and must never stall, reset, fail, kill, or advance a task.
- `VERIFIED_ACTION_MEMORY`: instructions, tasks, verified actions, failures, capabilities, task IDs, and task classes are categorized separately. Only evidence from `COMPLETE`/`COMPLETE_ALREADY` work is promoted as a verified action. Cross-task comparison may identify equivalent/reusable patterns, but conflicting or unique content, source refs, task-specific facts, and capabilities are preserved rather than collapsed.
- Routine dependencies, reversible environment repairs, and already-authorized implementation choices are execution work, not approval gates. Genuine destructive/irreversible external actions without authority, unavailable required facts/authority, safety constraints, and required task sequencing remain real boundaries.

## Realtime canonical upgrade and storage — 2026-09-08

`REALTIME_CANONICAL_UPGRADE` supersedes the prior cold-archive/offload workflow. Update existing canonical Git/Drive/state identities in place at safe durable boundaries; no parallel archive workflow and no duplicate active snapshot tree. Git history and raw evidence may retain required proof/provenance. Rebuildable temporary data may be removed when no active source/task/evidence reference requires it.

## Next-100 production execution

`docs/task-program/D_NEXT_100_TASKS.json` contains the next 100 existing task identities, normalized source sections/digests, dependencies, output contracts, and execution roots. It is not another queue. The runner injects only the active entry; `PRODUCTION.md` owns order/status and `D_TASK_LEDGER.json` is its derived projection. Reuse matching proof; no new gate, permanent agent, timer, or whole-program prompt load. Read `07_BIELLA_PRODUCTION_SYSTEM.md` for the implemented local-persistence/remote-publication split and inline source repair.
