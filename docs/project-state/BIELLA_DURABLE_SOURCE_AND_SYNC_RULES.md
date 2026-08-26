# Biella Durable Source and Synchronization Rules

Date: 2026-08-26

## Roles

- **GitHub** = durable code/source history and durable copies of accepted architecture/execution specifications required to rebuild/operate the project.
- **Google Drive** = live operator/project documents, current-state registers, prompt pack, migration ledgers, and chronological continuity.
- **ChatGPT Project context** = interactive reasoning/context; it may help produce updates but is not a substitute for persisted Git/Drive state.
- **Worker/VPS/local workspace** = execution copy; disposable unless its outputs have been promoted durably.
- **Cache** = disposable optimization only.

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
