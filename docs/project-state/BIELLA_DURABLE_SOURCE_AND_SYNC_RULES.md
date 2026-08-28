# Biella Durable Source and Synchronization Rules

Date: 2026-08-28

## Roles

- **GitHub** = durable code/source history and durable copies of accepted architecture/execution specifications required to rebuild/operate the project.
- **Google Drive** = live operator/project documents, current-state registers, prompt pack, migration ledgers, and chronological continuity.
- **ChatGPT Project context / chat history** = interactive continuity, intent, prior decisions, and evidence-location context; it is not current-state authority when a fact may have changed.
- **Worker/VPS/local workspace** = execution copy; disposable unless its outputs have been promoted durably.
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
3. Every durable numbered-task transition is expected to be committed to GitHub and reflected in required Drive continuity, but that expectation never substitutes for live readback.
4. If GitHub and Drive disagree, resolve by current project authority, exact revision/identity, and task relevance. Never synthesize conflicting claims.
5. If a required current fact cannot be observed, record `UNKNOWN` rather than infer it.
6. Chat/project history remains valuable for continuity and discovery, but current observed durable sources outrank remembered history for mutable facts.

## Promotion rule

```text
local implementation
→ focused verification
→ regression verification
→ commit
→ push GitHub
→ remote commit/tree readback
→ update Drive current-state/execution ledger
→ accepted durable state
```

A local commit is not durable merely because a model, shell, or Git command reported success.

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

## Current P0-01 handling

The previously observed local P0-01 SHA `b7cc3db0a9feb34d72764261d32163d2b05ac123` is retained as historical evidence only because its exact Git objects are not present in the connected GitHub history and the original Spot workspace is unavailable.

Do not fabricate that source from completion reports. Re-establish P0-01 from the exact canonical contract and current durable source, then push and verify it normally.
