# MiniTZ AI Peer Resources Design

Status: OWNER_APPROVED
Date: 2026-09-12
Canonical task binding: CODEX-L40-BRIDGE-01 rev 2, task digest bad155270bc76f93055d966a7711a84fe0b0900585e565792d02aa40887197d7, Task Program rev 66.

## Goal
Make additional AI systems useful to the canonical Codex writer by giving them the same exact MiniTZ task/capsule/current-projection/evidence context while keeping all helpers authority NONE.

## Architecture
Codex stays the canonical task writer. A peer-execution adapter binds every helper result to project scope, exact task revision/digest, task-state digest, capsule digest, projection digest, backend/model identity, and a structured result schema. Accepted peer results are evidence only and are consumed by Codex; they never complete or advance the Task Program.

The first full-agent peer is GitHub Copilot CLI already installed on the L40. Native Copilot is preferred when healthy. When native Copilot is unavailable, the same Copilot shell may use the already-connected Cloudflare OpenAI-compatible endpoint as a scoped BYOK fallback. Antigravity remains the already-integrated alternate full coder. Local Ollama/Qwen remains a direct MiniTZ local-intelligence Resource; it is not automatically placed behind the Copilot shell unless its persisted model profile exactly matches the active residency contract. Existing Groq/Cerebras/Mistral/OpenRouter/Gemini APIs stay behind the current MiniTZ resource/Commander layer rather than becoming parallel authorities.

## Context contract
Every peer receives only the current task-local truth: Task Program identity; task ID/revision/digest; task memory capsule; current projection; current policy refs; bounded failures/evidence; current source/worktree refs; exact objective; and output schema. Raw credential values are never embedded.

## Safety and authority
Peer execution uses authority NONE and progression_authority false. Read-only peer mode denies file-write and shell tools that can mutate state. Peer failure is nonblocking to Codex. Results are content-addressed and stale task/capsule/projection identities are rejected. No second scheduler, task list, memory authority, credential authority, or progression mechanism is introduced.

## Credential policy
Reuse existing MiniTZ credential references and process-boundary injection first. Native Copilot uses its existing authenticated credential store. Cloudflare fallback reads only the required existing account/token from MiniTZ protected private state at process launch and injects it only into the Copilot child environment. Local Qwen requires no API credential and remains direct MiniTZ local intelligence. Owner authorizes acquiring a missing provider API credential only when a required peer path cannot be satisfied by current healthy resources; any new raw secret must enter protected MiniTZ credential state and never semantic memory/logs/source.

## Routing
For a Codex primary turn, use at most one full-agent peer by default. Preserve an already-qualified ACTIVE Antigravity peer over an unqualified candidate. Otherwise use native Copilot first; if native Copilot has a genuine auth/quota/offline failure and the protected Cloudflare credential is available, use Copilot+Cloudflare. Local Qwen remains a separate direct MiniTZ helper unless its exact model/residency profile is compatible. Commander/API helpers remain independently bounded and deduplicated. Do not fan out equivalent peers merely to increase agent count.

## Acceptance
1. Native Copilot can consume exact task/capsule/projection identity and return schema-valid read-only peer evidence.
2. Copilot+Cloudflare can do the same using only the scoped existing protected Cloudflare credential.
3. A peer cannot mutate Task Program progression or the canonical workspace in read-only mode.
4. Stale task/capsule/projection results are rejected.
5. Peer failure never blocks the Codex writer.
6. Existing Antigravity, direct local-Qwen, and Commander/provider behavior remains compatible.
7. No raw secret enters peer prompts, evidence, source, or ordinary logs.

## Qualification correction — 2026-09-12
A generic Copilot+local-Qwen BYOK probe succeeded, but the exact current-task peer turn failed under live load. Root-cause evidence showed the `qwen3-coder-next:biella` persisted tag declares `num_gpu 26` while MiniTZ residency intentionally enforces 42 GPU blocks / 16384 context; Ollama repeatedly reloaded the runner and returned HTTP 500 `unexpected EOF`. MiniTZ therefore marks this Copilot-Qwen path unqualified rather than mutating healthy residency/model-store state. Copilot+Cloudflare was then functionally probed with the existing protected credential and returned the exact expected result with exit 0.
