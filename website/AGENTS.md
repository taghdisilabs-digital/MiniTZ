# Biella Universe Website Execution Authority

Status: `OWNER_DIRECTED_ACCEPTED_REQUIREMENT`
Authority: Mahdi Taghdisi
Scope: Website Project workspace on GitHub branch `website` in `patrickminitz-web/biella-engine`; this does not grant Website code authority over Engine `main`.

## Authority
1. Mahdi's latest explicit instruction.
2. Current accepted Website Project sources (`BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md`, 36x51 cross-map, asset manifest) plus this file.
3. Current `biella-engine/main` execution state for Engine implementation facts (`docs/project-state/03_BIELLA_CURRENT_STATE.md` + `04_BIELLA_ACTIVE_TASK.md`).
4. Current `biella-games/main` source/runtime evidence for Games implementation facts.
5. Canonical Drive Website/Games records.
6. Reference/history/inference.

Never synthesize conflicting claims or turn `UNKNOWN` into a guess.

## Project / Engine separation
Website code is Project scope. It may consume Engine capabilities but must not implement a second universal scheduler, memory, routing plane, object store, model layer, browser layer, validation framework, production system, publishing system, or learning system.

Do not mutate Engine `main` merely to implement Website work. The `website` branch is the isolated Website source workspace unless Mahdi explicitly establishes a separate repository later.

## Truth and game boundary
Concept art, generated images, rendered mockups, videos, interactive website demos, fake HUDs, canvas scenes, WebGL viewers, and website gameplay simulations do not prove Biella Games implementation.

BU-16 may publish an item as real game media only when `content/game-runtime-media.json` records `ACCEPTED_RUNTIME_MEDIA` tied to exact `biella-games` source commit/tree, exact runtime build identity, exact artifact SHA-256, origin `REAL_GAME_RUNTIME_CAPTURE`, and Mahdi acceptance.

## Website visual masters
The 50 Website visual slots are not migrated merely because a manifest filename exists. `MIGRATED_VERIFIED` requires exact source bytes, Drive file ID/path, SHA-256, GitHub publication path, and remote readback. Never guess a UUID-named/generated image match from prose or filename similarity.

## Execution
`MINIMUM_INSPECTION -> TEST/RED -> IMPLEMENT -> BUILD -> TEST -> BROWSER_VALIDATE -> PERSIST -> REMOTE_READBACK -> UPDATE EVIDENCE`

Preserve valid newer Website work. Recover only the smallest failed boundary. Do not start later BU tasks merely because the scaffold exists.

## Git durability
For Website source changes: observe `website` branch head/tree -> edit/test -> commit -> update branch -> fetch/read back exact result commit/tree and required files. Engine `main` remains untouched unless a separate Engine task explicitly owns the change.

## Drive durability
Canonical Website Drive root currently observed as `BIELLA_WEBSITE` ID `1btVF8nJbwGWhuEA4N9vmgZVckVDNv07V`. Preserve existing file IDs when revising canonicals where practical. Binary visual publication requires exact bytes/digest readback; Drive write success alone is not completion.

## Deployment evidence
Preview or production is complete only with remote deployment/version identity and HTTP readback from the deployed artifact. Cloudflare configuration, a workflow file, or a green build alone is not deployment proof.

Production target: `https://biellagames.dev`. Cloudflare Workers/Pages are replaceable hosting implementations; current Website source uses Workers static assets because current Cloudflare guidance treats Workers as the primary platform for new applications.

Rollback proof requires an observed prior successful production version/deployment, an actual rollback action, and readback proving the old version served. If Cloudflare account/project credentials are unavailable, report `BLOCKED_ON_REQUIRED_DEPLOYMENT_AUTHORITY`; never fake a rollback.

## Hardened execution law — 2026-09-05

- `SINGLE_CODEX_AUTHORITY`: one Codex task/session owns authority, synthesis, edits, validation, completion, and task advancement. Parallel Codex/subagent fan-out is disabled for production.
- `RESOURCE_PARALLELISM`: independent bounded work may execute concurrently through verified Resources when dependencies, side effects, and capacity permit. Local Qwen/Ollama, Cloudflare Workers/AI, external APIs, GPU tools, DCCs, build systems, and other Resources are implementations, never second authorities. Cloudflare is used only through an actually configured callable capability adapter.
- `LOCAL_FIRST_EFFICIENCY`: before spending general Codex reasoning on bounded preprocessing, code review, classification, summarization, log triage, reasoning assistance, or Unreal assistance, prefer the configured local Qwen Resource when it can perform the work without reducing correctness. Reuse compact task memory, prompt caching, bounded tool output, and deterministic/local commands.
- `FINAL_DELIVERABLE_PUBLICATION`: every final deliverable keeps an exact canonical local identity and, when current Project/task authority defines a canonical publication destination, the exact final file is published there and read back/verified before durable completion. Never invent a destination. Publication failure preserves the local file and remains retryable/`CONTINUE`; publication is never inferred from an attempted upload.
- `DURABLE_FAILURE_LEDGER`: every observed production/model/provider/tool/runtime/validation/publication failure or retry is recorded in AI-readable JSONL at `/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl` with task/time/type/status and bounded diagnostics. Failure records aid diagnosis and never override current source/task authority.

- `LOSSLESS_MEMORY_COMPACTION`: raw authority, evidence, artifacts, task records, and failure records are never rewritten or deleted by compression. The compactor creates rebuildable derivative JSON/JSON.GZ indexes with exact source digests, content-addressed unique records, equivalence groups that retain every exact variant and provenance, and a bounded current-task projection. Compaction failure is an optimization failure only and must never stall, reset, fail, kill, or advance a task.
- `VERIFIED_ACTION_MEMORY`: instructions, tasks, verified actions, failures, capabilities, task IDs, and task classes are categorized separately. Only evidence from `COMPLETE`/`COMPLETE_ALREADY` work is promoted as a verified action. Cross-task comparison may identify equivalent/reusable patterns, but conflicting or unique content, source refs, task-specific facts, and capabilities are preserved rather than collapsed.
- Routine dependencies, reversible environment repairs, and already-authorized implementation choices are execution work, not approval gates. Genuine destructive/irreversible external actions without authority, unavailable required facts/authority, safety constraints, and required task sequencing remain real boundaries.
