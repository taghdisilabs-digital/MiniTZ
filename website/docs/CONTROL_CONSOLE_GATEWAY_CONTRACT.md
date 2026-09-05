# Biella Control Console Gateway Contract

Status: implementation contract for the private control console.

## Purpose

The console is a browser client for the existing Biella control gateway. It is not a second gateway, a shell, or an independent execution manager. The gateway remains the authority for authentication, authorization, current state, capability approval, and writes.

The console serves three lanes:

- Website
- Engine
- Games

The console reads current data only. Legacy, historical, superseded, and unverified records are excluded from the active response contract.

## Browser routes

The static console is served at /control/.

The browser calls same-origin endpoints below. The deployed ingress may use control.biellagames.dev, while local inference remains on localhost.

- GET /v1/control/session
- POST /v1/control/session
- POST /v1/control/session/logout
- GET /v1/control/overview?lane=...
- GET /v1/control/capabilities?lane=...
- GET /v1/control/services?lane=...
- GET /v1/control/milestones?lane=...
- GET /v1/control/hardware?lane=...
- GET /v1/control/workers?lane=...
- GET /v1/control/files?lane=...
- GET /v1/control/events?lane=...
- POST /v1/control/dialog
- POST /v1/control/runs

The event endpoint is Server-Sent Events. Each event should be JSON when possible, with text or message fields suitable for the live dialog.

## Access roles

The server must enforce these roles:

- operator: may read current state, send live dialog messages, and run approved capabilities.
- observer: may read current state and live events. Dialog writes and capability runs must be rejected by the server.

The UI hides disabled actions for observers for clarity, but that is only a usability layer. The server remains authoritative.

The requested operator and observer accounts must be created in the gateway's protected credential store. Passwords must never be committed to GitHub, Drive, the Site source, browser code, or deployment metadata. Rotate any credential that has been pasted into a chat or terminal transcript before production.

## Run boundary

The console submits a lane, capability_id, and auto_run flag. The gateway must validate that the capability is approved for the selected lane and must reject arbitrary commands, paths, or unapproved services.

The local Qwen service is reached only through its local runtime path. Cloudflare is external ingress around the gateway and does not sit between Codex and local inference. Saturn is connected through its official API or MCP resources, not by treating a token as an inference endpoint.

## Current-state response shape

The gateway may add fields, but these stable fields are expected:

- overview: goal, active_task, status
- capabilities: items with id, title, description, status
- services: items with name, status, detail
- milestones: items with title, status, detail
- hardware: gpu, vram_used, ram_used, api_calls, usage
- workers: items with name, status, detail
- files: items with path, lane, commit, updated_at

All responses must identify the selected lane and must not silently promote old or unverified material into current state.

## Deployment boundary

The public Biella site remains at biellagames.dev. The private console is intended for control.biellagames.dev after the saved Site version and gateway ingress are available. Cloudflare DNS and tunnel configuration are operational changes and must be applied separately with protected credentials.

## Hardened execution law — 2026-09-05

- `SINGLE_CODEX_AUTHORITY`: one Codex task/session owns authority, synthesis, edits, validation, completion, and task advancement. Parallel Codex/subagent fan-out is disabled for production.
- `RESOURCE_PARALLELISM`: independent bounded work may execute concurrently through verified Resources when dependencies, side effects, and capacity permit. Local Qwen/Ollama, Cloudflare Workers/AI, external APIs, GPU tools, DCCs, build systems, and other Resources are implementations, never second authorities. Cloudflare is used only through an actually configured callable capability adapter.
- `LOCAL_FIRST_EFFICIENCY`: before spending general Codex reasoning on bounded preprocessing, code review, classification, summarization, log triage, reasoning assistance, or Unreal assistance, prefer the configured local Qwen Resource when it can perform the work without reducing correctness. Reuse compact task memory, prompt caching, bounded tool output, and deterministic/local commands.
- `FINAL_DELIVERABLE_PUBLICATION`: every final deliverable keeps an exact canonical local identity and, when current Project/task authority defines a canonical publication destination, the exact final file is published there and read back/verified before durable completion. Never invent a destination. Publication failure preserves the local file and remains retryable/`CONTINUE`; publication is never inferred from an attempted upload.
- `DURABLE_FAILURE_LEDGER`: every observed production/model/provider/tool/runtime/validation/publication failure or retry is recorded in AI-readable JSONL at `/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl` with task/time/type/status and bounded diagnostics. Failure records aid diagnosis and never override current source/task authority.

- `LOSSLESS_MEMORY_COMPACTION`: raw authority, evidence, artifacts, task records, and failure records are never rewritten or deleted by compression. The compactor creates rebuildable derivative JSON/JSON.GZ indexes with exact source digests, content-addressed unique records, equivalence groups that retain every exact variant and provenance, and a bounded current-task projection. Compaction failure is an optimization failure only and must never stall, reset, fail, kill, or advance a task.
- `VERIFIED_ACTION_MEMORY`: instructions, tasks, verified actions, failures, capabilities, task IDs, and task classes are categorized separately. Only evidence from `COMPLETE`/`COMPLETE_ALREADY` work is promoted as a verified action. Cross-task comparison may identify equivalent/reusable patterns, but conflicting or unique content, source refs, task-specific facts, and capabilities are preserved rather than collapsed.
- Routine dependencies, reversible environment repairs, and already-authorized implementation choices are execution work, not approval gates. Genuine destructive/irreversible external actions without authority, unavailable required facts/authority, safety constraints, and required task sequencing remain real boundaries.
