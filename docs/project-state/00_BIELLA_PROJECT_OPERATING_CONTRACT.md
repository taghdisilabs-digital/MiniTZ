# 00 — BIELLA PROJECT OPERATING CONTRACT

```yaml
schema: biella.operating_contract/v2
version: 2026-09-05
mode: reference_on_demand
authority:
  current_state: 03_BIELLA_CURRENT_STATE.md
  active_task: 04_BIELLA_ACTIVE_TASK.md
  sequencing_plan: 02_BIELLA_ENGINE_FINAL_MIGRATION_PLAN_2026-08-27.md
purpose: resolve execution edge cases without rereading or redesigning the project
```

## 1. SCOPE

This file defines only operational decision rules.

It does **not** define:
- current Git commit/tree/host state;
- the active numbered task;
- full Biella architecture;
- prompt bodies;
- historical migration contents.

Do not use this file to override newer observed execution state, current GitHub source, `03`, `04`, or the exact active prompt.

---

## 2. CONFLICT RESOLUTION

When required inputs disagree:

```text
observe smallest relevant current source
→ identify each claim's authority + revision/time
→ choose highest current evidence
→ mark superseded claim inactive
→ continue
```

Never:
- merge incompatible claims into a synthetic compromise;
- prefer a newer timestamp when the underlying content is older;
- treat copied/reuploaded historical text as current truth;
- convert `UNKNOWN` into a guess.

If the conflict does not affect the active task, do not investigate it.

---

## 3. REOBSERVATION TRIGGERS

Reobserve a fact only when at least one is true:

```yaml
reobserve_if:
  - active_task_requires_it
  - source_revision_may_have_changed
  - prior_value_is_UNKNOWN
  - current_output_contradicts_prior_state
  - publication_or_finalization_requires_fresh_identity
  - material_dependency_changed
```

Do not reobserve stable facts every turn.

Examples:
- recheck Git HEAD/tree immediately before writing/publishing;
- recheck push authentication when a push is required;
- do not re-audit installed host tooling for a source-only change.

---

## 4. REUSE / INVALIDATION

Default: reuse verified existing work.

A completed unit remains valid unless:

```yaml
invalidate_if:
  - material_input_digest_changed
  - required_source_revision_changed
  - artifact_missing_or_corrupt
  - current_required_validation_fails
  - contract_or_acceptance_requirement_changed
  - authoritative newer work supersedes_it
```

Do **not** invalidate because:
- ChatGPT/Codex restarted;
- SSH/tmux reconnected;
- a provider/model/worker changed;
- an unrelated node failed;
- a stale document describes an earlier state.

Before rerunning work, prove why reuse is unsafe or incorrect.

---

## 5. FAILURE / RECOVERY

Recovery boundary = smallest unit whose correctness is no longer established.

```text
failure
→ capture actual output/evidence
→ isolate failed dependency/unit
→ preserve verified unaffected outputs
→ repair/reroute failed scope
→ rerun affected validation
→ continue
```

Never convert a bounded failure into:
- full task restart;
- host reinstall;
- architecture rewrite;
- global provider change;
- mandatory new review stage.

If a dependency is optional, only dependent work may wait.

---

## 6. FILESYSTEM MUTATION

Before creating/moving/renaming a working path:

```yaml
require:
  - active_task_needs_change: true
  - canonical_existing_path_checked: true
  - duplicate_authority_not_created: true
  - continuation_or_reference_paths_updated_if_needed: true
```

Rules:
- mutate existing canonical paths instead of creating parallel replacements;
- never rename old concepts merely to make them look Biella-native;
- historical raw bytes remain quarantine/history objects;
- caches/tooling may be rebuilt; source/artifact/run authority must not depend on them;
- do not move working source for aesthetic organization alone.

A filesystem cleanup is not valid if it destroys provenance, breaks continuation, or creates two active copies.

---

## 7. CONTEXT EXPANSION

Default context is narrow.

Expand context only when the active task cannot be executed correctly from:
- Project Instructions;
- `03_BIELLA_CURRENT_STATE.md`;
- `04_BIELLA_ACTIVE_TASK.md`;
- exact active prompt;
- directly touched source/interfaces.

```yaml
expand_to_00_if: operational_rule_ambiguity
expand_to_01_if: architecture_or_scope_ambiguity
expand_to_02_if: sequencing_or_migration_plan_ambiguity
expand_to_history_if: bounded_evidence_or_migration_need
```

Never use broad context loading as a substitute for identifying the exact missing fact.

---

## 8. DURABLE PUBLICATION

Local success is not durable publication.

For GitHub source changes:

```text
local validation
→ commit
→ push
→ remote fetch/readback
→ verify exact remote commit
→ verify exact remote tree
→ verify required paths/artifacts remotely
```

For Drive publication:

```text
create/upload/update
→ list/fetch/readback target
→ verify identity/content required by task
```

For exact files:
- verify bytes/digest when identity matters.

Do not claim publication/sync from:
- command exit code alone;
- upload attempt;
- local commit;
- HTTP success alone;
- tool/agent statement.

---

## 9. STATE UPDATES

After a durable numbered-task transition:

```yaml
update:
  03_BIELLA_CURRENT_STATE.md:
    - only facts that changed
    - exact new commit/tree/evidence
    - new current boundary
  04_BIELLA_ACTIVE_TASK.md:
    - replace with next task packet
  canonical_drive_continuity:
    - only affected live records
```

Do not create:
- another current-state summary;
- another active-task file;
- duplicate source-of-truth documents.

`REALTIME_CANONICAL_UPGRADE`: update the live canonical record in place; no parallel archive workflow or duplicate active snapshots. Git history and raw evidence may retain required provenance/proof, but stale state is replaced rather than maintained as a second operational copy.

---

## 10. FINALIZATION SAFETY

Before marking a task closed, verify:

```yaml
finalization:
  task_contract_satisfied: required
  required_artifacts_exist: required
  required_validation_passed: required
  authoritative_source_identity_recorded: required
  publication_readback: required_if_published
  continuation_state_updated: required
  unrelated_next_task_started: false
```

If any required evidence is missing, status is not `COMPLETE`.

Use precise states such as:

```text
READY
RUNNING
BLOCKED_ON_REQUIRED_DEPENDENCY
FAILED_BOUNDED_SCOPE
COMPLETE_LOCAL_NOT_PUBLISHED
COMPLETE_DURABLE
UNKNOWN
```

Avoid vague states such as “basically done” or “should work”.

---

## 11. MIGRATION-SPECIFIC EDGE RULES

For any historical candidate, keep these dimensions separate:

```yaml
source_identity: exact raw provenance/content identity
content_kind: what useful semantic thing was extracted
migration_classification: how it may be admitted
destination_scope: engine/project/history/none
verification: evidence supporting the candidate
```

Useful logic or production knowledge may survive a contaminated source through `UNIVERSAL_REWRITE`.

Project brand/visual/content knowledge may survive only in its Project scope.

`DUPLICATE` and `OBSOLETE_OR_DRIFT` do not become active authority.

Unclassified material remains inactive.

---

## 12. EXECUTION DECISION TEMPLATE

When an operational ambiguity appears, resolve it using:

```yaml
decision:
  active_task: <id>
  required_fact: <fact>
  current_evidence: <source/ref>
  prior_evidence: <source/ref|null>
  conflict: <true|false>
  reobservation_required: <true|false>
  reuse_valid: <true|false>
  smallest_action: <action>
  required_validation: <checks>
  durable_writeback: <targets>
```

If this template can be filled from current evidence, execute. Do not add another planning/review cycle.

## Hardened execution law — 2026-09-05

- `SINGLE_CODEX_AUTHORITY`: one Codex task/session owns authority, synthesis, edits, validation, completion, and task advancement. Parallel Codex/subagent fan-out is disabled for production.
- `RESOURCE_PARALLELISM`: independent bounded work may execute concurrently through verified Resources when dependencies, side effects, and capacity permit. Local Qwen/Ollama, Cloudflare Workers/AI, external APIs, GPU tools, DCCs, build systems, and other Resources are implementations, never second authorities. Cloudflare is used only through an actually configured callable capability adapter.
- `LOCAL_FIRST_EFFICIENCY`: before spending general Codex reasoning on bounded preprocessing, code review, classification, summarization, log triage, reasoning assistance, or Unreal assistance, prefer the configured local Qwen Resource when it can perform the work without reducing correctness. Reuse compact task memory, prompt caching, bounded tool output, and deterministic/local commands.
- `FINAL_DELIVERABLE_PUBLICATION`: every final deliverable keeps an exact canonical local identity and, when current Project/task authority defines a canonical publication destination, the exact final file is published there and read back/verified before durable completion. Never invent a destination. Publication failure preserves the local file and remains retryable/`CONTINUE`; publication is never inferred from an attempted upload.
- `DURABLE_FAILURE_LEDGER`: every observed production/model/provider/tool/runtime/validation/publication failure or retry is recorded in AI-readable JSONL at `/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl` with task/time/type/status and bounded diagnostics. Failure records aid diagnosis and never override current source/task authority.

- `LOSSLESS_MEMORY_COMPACTION`: raw authority, evidence, artifacts, task records, and failure records are never rewritten or deleted by compression. The compactor creates rebuildable derivative JSON/JSON.GZ indexes with exact source digests, content-addressed unique records, equivalence groups that retain every exact variant and provenance, and a bounded current-task projection. Compaction failure is an optimization failure only and must never stall, reset, fail, kill, or advance a task.
- `VERIFIED_ACTION_MEMORY`: instructions, tasks, verified actions, failures, capabilities, task IDs, and task classes are categorized separately. Only evidence from `COMPLETE`/`COMPLETE_ALREADY` work is promoted as a verified action. Cross-task comparison may identify equivalent/reusable patterns, but conflicting or unique content, source refs, task-specific facts, and capabilities are preserved rather than collapsed.
- Routine dependencies, reversible environment repairs, and already-authorized implementation choices are execution work, not approval gates. Genuine destructive/irreversible external actions without authority, unavailable required facts/authority, safety constraints, and required task sequencing remain real boundaries.
