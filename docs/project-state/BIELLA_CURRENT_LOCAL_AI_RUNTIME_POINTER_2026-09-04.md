# Current local-AI runtime pointer — 2026-09-04

Status: `CURRENT / IMPLEMENTED_IN_REPOSITORY / RUNTIME_VALIDATION_PENDING`

This pointer identifies the current bounded L40S runtime for the three Biella
lanes: Website, Engine, and Games. It does not replace the current task ledger
and it does not promote historical, superseded, legacy, exploratory, or
unverified material into current filings.

Canonical execution package in Drive (`30_EXECUTION`):

- `BIELLA_LOCAL_AI_RUNTIME_DECISION_2026-09-04.md` — behavior and boundaries.
- `BIELLA_LOCAL_AI_RUNTIME_MANIFEST_2026-09-04.yaml` — machine-readable state.
- `RECOVERY_RUNBOOKS.md` — recovery index and secret-handling boundary.
- `ops/local-ai` package — installer, six-step launcher, Saturn API probe,
  official Saturn MCP bridge, and Codex local wrapper.

Repository source of record:

- GitHub repository: `patrickminitz-web/biella-engine`
- Commit: `274c4bf1dcb89233e4ac553292336e13dd9ded3b`
- Source paths: `docs/project-state/`, `ops/local-ai/`, and `tests/`

Runtime contract summary:

- Existing Ollama model only: `qwen3-coder-next:biella`.
- Fixed first load: 26 GPU layers, 16K context, permanent keep-alive.
- Positive reported Qwen VRAM must remain strictly below 30 GiB.
- CPU-side model residency target: 86 GiB RAM.
- Codex is the controller; Saturn is the official API/MCP integration.
- Cloudflare is external ingress only around the existing localhost gateway.
- Runtime credentials remain outside Git and Drive in root-only mode-`0600`
  files.
