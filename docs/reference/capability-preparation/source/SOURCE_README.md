# capability_preparation

Isolated, versioned preparation material for future Biella capability, task, workflow, validation, knowledge, coding, visual, and game-production work.

## Authority and safety boundary

This repository is **not** the Biella Engine repository and does not contain current Biella Engine or Biella Games authority.

Every generated candidate remains:

```text
PREPARATION_CANDIDATE
```

The authoritative main Codex may later inspect and independently decide whether to reject, rewrite, test, or integrate a candidate.

## Research package

| Path | Purpose |
|---|---|
| `AGENTS.md` | Immediate operating contract for preparation Codex |
| `research/BIELLA_TRUSTED_CREATOR_AND_SOURCE_GUIDE_2026-08-29.md` | Human-readable source selection, verification method, and scoped findings |
| `research/BIELLA_PRODUCTION_WORKFLOW_PLAYBOOK_2026-08-29.md` | Detailed prompt, eval, model-selection, token, coding, visual, game, cloud, and publication workflow |
| `research/SOURCE_REGISTRY_2026-08-29.jsonl` | Machine-readable verified source records |
| `schemas/source_record.schema.json` | JSON Schema for each source registry record |
| `manifests/2026-08-29-trusted-community-research.json` | Publication, integrity, and verification evidence |

## Verified source coverage

The research package covers:

- OpenAI Developers, Cookbook, and Evals;
- Cloudflare Workers AI, AI Gateway, and official examples;
- prompt engineering and evaluation practice;
- tested coding-agent workflows;
- structured outputs and validation;
- context and token discipline;
- ComfyUI, InvokeAI, and Krita AI Diffusion;
- IP-Adapter technique material with a maintenance caveat;
- Unity/rendering education;
- game math and geometry;
- procedural coding projects;
- real-time shaders and effects;
- game programming patterns;
- OpenGL;
- RenderDoc graphics evidence;
- general language-model evaluation infrastructure.

Sources are selected for inspectable evidence, not popularity.

## How a preparation Codex should use this package

1. Read `AGENTS.md`.
2. Read the source guide and playbook.
3. Query `SOURCE_REGISTRY_2026-08-29.jsonl` by `source_id` or domain.
4. Refresh official sources before creating provider-specific production guidance.
5. Generate a small batch with explicit schemas, provenance, failures, and validation.
6. Keep all outputs project-noncanonical.
7. Commit preparation material only to this repository.
8. Do not touch the real Biella Engine.

## Registry example query

```bash
python3 -c 'import json; [print(json.loads(line)["source_id"]) for line in open("research/SOURCE_REGISTRY_2026-08-29.jsonl", encoding="utf-8") if "visual" in json.loads(line)["domains"] or "rendering" in json.loads(line)["domains"]]'
```

## Production standard

A candidate is not useful merely because it parses. It must have:

- a bounded objective;
- technically plausible inputs and constraints;
- expected artifacts;
- validation evidence;
- failure and recovery behavior;
- source provenance;
- version/currentness caveats;
- no invented Biella facts;
- no unresolved placeholder text.

## Canonical publication targets

- GitHub: `patrickminitz-web/capability_preparation`
- Google Drive folder: `1nVKKASTsqmCw8CT9P_qYaz8h65F5C6Dx`

GitHub is the canonical versioned preparation source. Drive is the matching readable publication surface.
