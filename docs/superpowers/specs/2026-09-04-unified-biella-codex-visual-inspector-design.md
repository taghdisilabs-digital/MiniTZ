# Unified Biella Codex + Visual Inspector Design

Status: OWNER_APPROVED
Authority: Mahdi Taghdisi
Date: 2026-09-04

## Objective
Make `biella-codex` the only AI/production controller. The operator chooses only the Codex model/usage tier; Codex owns routing to local Qwen, APIs, GPU, Unreal, GitHub, Drive, Cloudflare, Modal, Saturn and production tools.

## Controller
- Active Codex home is `/root/.codex` for every controller model.
- `biella-codex` loads `/root/.config/biella-ai/runtime.env`, inherits the full shell environment, starts from `/root`, enables search, and runs with unrestricted execution.
- Model selection is passed through to Codex (`/model`, `-m`, or `--model`); model/provider choice does not create a new project-memory authority.
- Model-specific public launchers are removed from the installed production interface.
- Local Qwen/Ollama remains a Resource/tool Codex may invoke, not a separate production controller.
## Shared project memory and guidance
- Preserve Biella memory scopes: Engine Memory, Project Memory, Run Memory, Historical Evidence and Cache remain semantically distinct.
- Unify only the Codex access layer: all controller models use `/root/.codex`, the same project `AGENTS.md`, current Git/Drive authority and runtime environment.
- `.codex-local-qwen` is inactive model-specific history/cache. Do not promote its session logs/queues into Project Memory.
- Progressive context policy: start from the smallest authoritative project/task set, expand only when required, use targeted searches, bounded log tails, and checkpoint before context pressure.
- Changing model/session never resets verified project progress.

## Visual inspection layer
- Extend the existing private `/control/` console with a `Visuals / Assets` surface.
- Backend scans only allowlisted Project roots and returns current metadata plus explicit source class (`CURRENT`, `GENERATED_DRAFT`, `HISTORICAL_RECOVERY`, etc.).
- Images receive direct authenticated previews; video/audio/3D/Unreal assets expose metadata and preview support where practical.
- Filters: lane, type, status, current/unpublished/generated.
- No generated asset becomes accepted/canonical merely because it appears in the inspector.

## Completion
Require source tests, installed-controller verification, gateway API tests, website build/browser tests, live service restart, authenticated endpoint readback, exact Git remote readback, and no regression of existing control-console auth/tunnel behavior.