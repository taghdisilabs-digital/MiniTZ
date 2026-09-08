# Biella Universe Website Execution Authority

Status: `OWNER_DIRECTED_ACCEPTED_REQUIREMENT`
Authority: Mahdi Taghdisi
Scope: `website/` in canonical `patrickminitz-web/biella-engine` branch `main`. Website tasks own website/product changes, not unrelated Engine or Games implementation.

## Authority
1. Mahdi's latest explicit instruction.
2. Current accepted Website Project sources (`BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md`, 36x51 cross-map, asset manifest) plus this file.
3. Current `biella-engine/main` execution state for Engine implementation facts (`docs/project-state/03_BIELLA_CURRENT_STATE.md` + `04_BIELLA_ACTIVE_TASK.md`).
4. Current `projects/biella-games/` source/runtime evidence in canonical `biella-engine/main` for Games implementation facts.
5. Canonical Drive Website/Games records.
6. Reference/history/inference.

Never synthesize conflicting claims or turn `UNKNOWN` into a guess.

## Project / Engine separation
Website code is Project scope. It may consume Engine capabilities but must not implement a second universal scheduler, memory, routing plane, object store, model layer, browser layer, validation framework, production system, publishing system, or learning system.

Use the existing `website/` subtree on canonical `main`; do not switch to a stale website branch or create a duplicate active checkout. Shared runtime changes must be directly required by the current task, with unrelated Project bytes preserved.

## Truth and game boundary
Concept art, generated images, rendered mockups, videos, interactive website demos, fake HUDs, canvas scenes, WebGL viewers, and website gameplay simulations do not prove Biella Games implementation.

BU-16 may publish an item as real game media only when `content/game-runtime-media.json` records `ACCEPTED_RUNTIME_MEDIA` tied to exact `biella-games` source commit/tree, exact runtime build identity, exact artifact SHA-256, origin `REAL_GAME_RUNTIME_CAPTURE`, and Mahdi acceptance.

## Website visual masters
The 50 Website visual slots are not migrated merely because a manifest filename exists. `MIGRATED_VERIFIED` requires exact source bytes, Drive file ID/path, SHA-256, GitHub publication path, and remote readback. Never guess a UUID-named/generated image match from prose or filename similarity.

## Deterministic live projection
`NO_PERMANENT_WEBSITE_AGENT`: production facts are never maintained by a permanent Website agent. The static Website shell changes only through explicit Website source tasks; current task/model/reasoning/progress/validation/system telemetry and eligible artifacts come from the read-only `/live-api/snapshot` + `/live-api/events` projection generated from canonical Biella runtime/evidence. Runtime progress must not require Website commits or redeploys. The observer may cache/index projections for performance but may never become production authority or mutate execution.

## Execution
`MINIMUM_INSPECTION -> TEST/RED -> IMPLEMENT -> BUILD -> TEST -> BROWSER_VALIDATE -> PERSIST -> REMOTE_READBACK -> UPDATE EVIDENCE`

Preserve valid newer Website work. Recover only the smallest failed boundary. Do not start later BU tasks merely because the scaffold exists.

## Git durability
For Website source changes: observe canonical `main` and `website/` -> edit/test/build/browser validation -> commit website-owned output -> controller publication/readback. Branch changes and a second repository are not prerequisites.

## Drive durability
Canonical Website Drive root currently observed as `BIELLA_WEBSITE` ID `1btVF8nJbwGWhuEA4N9vmgZVckVDNv07V`. Preserve existing file IDs when revising canonicals where practical. Binary visual publication requires exact bytes/digest readback; Drive write success alone is not completion.

## Deployment evidence
Preview or production is complete only with remote deployment/version identity and HTTP readback from the deployed artifact. Cloudflare configuration, a workflow file, or a green build alone is not deployment proof.

Production target: `https://biellagames.dev`. Cloudflare Workers/Pages are replaceable hosting implementations; use the currently verified deployment topology rather than replacing a working deployment solely because of provider guidance.

Rollback proof requires an observed prior successful production version/deployment, an actual rollback action, and readback proving the old version served. If required Cloudflare access is unavailable, preserve the exact build, record the missing delivery operation, use the configured compatible resource, and continue independent preparation. Never fake deployment or rollback evidence.

## Hardened execution law — 2026-09-05

- `SINGLE_CODEX_AUTHORITY`: one Codex task/session owns authority, synthesis, edits, validation, completion, and task advancement. Parallel Codex/subagent fan-out is disabled for production.
- `RESOURCE_PARALLELISM`: independent bounded work may execute concurrently through verified Resources when dependencies, side effects, and capacity permit. Local Qwen/Ollama, Cloudflare Workers/AI, external APIs, GPU tools, DCCs, build systems, and other Resources are implementations, never second authorities. Cloudflare is used only through an actually configured callable capability adapter.
- `LOCAL_FIRST_EFFICIENCY`: before spending general Codex reasoning on bounded preprocessing, code review, classification, summarization, log triage, reasoning assistance, or Unreal assistance, prefer the configured local Qwen Resource when it can perform the work without reducing correctness. Reuse compact task memory, prompt caching, bounded tool output, and deterministic/local commands.
- `FINAL_DELIVERABLE_PUBLICATION`: preserve exact canonical local output and task-derived proof. The controller commits task-owned output and continuity locally, records the exact Git revision in its durable publication cursor, and retries GitHub/Drive independently. A transport failure does not reopen validated implementation or stop unrelated execution. `COMPLETE` records satisfied task acceptance; `PUBLISHED/VERIFIED` requires actual remote identity and readback. When deployment, external delivery, or a remote operation is itself the task deliverable, its real evidence remains required. Never invent a destination or claim remote durability from a local commit.
- `DURABLE_FAILURE_LEDGER`: every observed production/model/provider/tool/runtime/validation/publication failure or retry is recorded in AI-readable JSONL at `/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl` with task/time/type/status and bounded diagnostics. Failure records aid diagnosis and never override current source/task authority.

- `LOSSLESS_MEMORY_COMPACTION`: raw authority, evidence, artifacts, task records, and failure records are never rewritten or deleted by compression. The compactor creates rebuildable derivative JSON/JSON.GZ indexes with exact source digests, content-addressed unique records, equivalence groups that retain every exact variant and provenance, and a bounded current-task projection. Compaction failure is an optimization failure only and must never stall, reset, fail, kill, or advance a task.
- `VERIFIED_ACTION_MEMORY`: instructions, tasks, verified actions, failures, capabilities, task IDs, and task classes are categorized separately. Only evidence from `COMPLETE`/`COMPLETE_ALREADY` work is promoted as a verified action. Cross-task comparison may identify equivalent/reusable patterns, but conflicting or unique content, source refs, task-specific facts, and capabilities are preserved rather than collapsed.
- Routine dependencies, reversible environment repairs, and already-authorized implementation choices are execution work, not approval gates. Genuine destructive/irreversible external actions without authority, unavailable required facts/authority, safety constraints, and required task sequencing remain real boundaries.

## Next-100 production execution

`docs/task-program/D_NEXT_100_TASKS.json` contains the next 100 existing task identities, normalized source sections/digests, dependencies, output contracts, and execution roots. It is not another queue. The runner injects only the active entry; `PRODUCTION.md` owns order/status and `D_TASK_LEDGER.json` is its derived projection. Reuse matching proof; no new gate, permanent agent, timer, or whole-program prompt load. Read `07_BIELLA_PRODUCTION_SYSTEM.md` for the implemented local-persistence/remote-publication split and inline source repair.

## Owner production priority — GAME_FIRST
Biella Games delivery is priority NUMBER 1. Existing website/live observers remain operational; website expansion follows the game work in the physical Project PRODUCTION.md order. Reuse existing website outputs rather than rebuilding completed work. Only an actual required game-delivery surface may be advanced as that exact task; do not let a website redesign preempt game production.
