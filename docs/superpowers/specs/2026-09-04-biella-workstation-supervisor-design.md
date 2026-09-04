# Biella Workstation Supervisor Design

Date: 2026-09-04
Status: APPROVED_FOR_IMPLEMENTATION

## Goal

Create one super-capable, low-friction Biella creation workstation on `biella-l40s-worker` that combines local Qwen/Codex, rented compute, free/paid APIs, production tools, and durable runtime supervision without turning provider availability into artificial restrictions.

## Verified baseline

- Ubuntu 24.04.4 LTS on AMD EPYC 9124 with 86.3 GiB RAM.
- NVIDIA L40S with 46,068 MiB VRAM; current Qwen residency is about 27.7 GB.
- `qwen3-coder-next:biella` is live in Ollama with 16K context and 26 GPU layers.
- Codex CLI 0.153.2, Modal 1.5.5, Gemini CLI 0.58.0, Docker, uv/uvx, GitHub CLI, rclone, and cloudflared are installed.
- Saturn MCP is registered with Codex.
- Cloudflare, Groq, Cerebras, OpenRouter, Mistral, and Tavily provider checks return HTTP 200; the provider registry also supports Exa, Pinecone, Qdrant, Deepgram, AssemblyAI, ElevenLabs, Stability AI, Supabase, Neon, Upstash, Cloudinary, Axiom, and Pexels.
- Modal token authentication is valid.
- Gemini credentials exist but Gemini API health is independently degraded and must not block the workstation.
- `/mnt/biella-extra` is a separate ext4 volume with about 343 GiB free.

## Operating principles

1. Local Qwen is the default inexpensive bulk worker, not the only allowed worker.
2. Codex is the primary interactive controller and may use any configured provider or production tool when useful.
3. Provider choice is capability-driven; no provider is globally forbidden because another provider exists.
4. Noise control reduces redundant calls and verbose logs but never removes capability.
5. Secrets remain in `/root/.config/biella-ai/runtime.env`, root-owned mode `0600`.
6. System services are preferred over ad-hoc `tmux`/background processes for durable runtime components.
7. Existing production/evidence data is not broadly moved or deleted during this cutover.
## Unified interface

Install a single `/usr/local/bin/biella` command with these stable subcommands:

- `biella up` — ensure Ollama is supervised, warm Qwen, and verify local readiness.
- `biella down` — stop only Biella-owned supervised services.
- `biella status` — compact local/provider status without secret output.
- `biella doctor` — deeper diagnostics for binaries, disk, GPU, providers, MCP, and runtime state.
- `biella agent` — fast local Codex/Qwen agent with provider environment loaded and eager Saturn MCP disabled.
- `biella codex` — full Codex controller with Saturn MCP enabled.
- `biella providers` — run the provider health checker.
- `biella modal` — delegate to the authenticated Modal CLI.
- `biella logs` — show compact recent Biella service logs.
- `biella cleanup` — remove only known temporary Biella diagnostic processes/caches.

## Runtime supervision

Replace the `tmux llm-router` ownership model with `biella-ollama.service`. The service runs as the existing `ollama` user and preserves the currently proven settings:

- `OLLAMA_HOST=127.0.0.1:11434`
- `OLLAMA_CONTEXT_LENGTH=16384`
- `OLLAMA_NUM_PARALLEL=1`
- `OLLAMA_MAX_LOADED_MODELS=1`
- `OLLAMA_FLASH_ATTENTION=1`
- `OLLAMA_KV_CACHE_TYPE=q8_0`
- `OLLAMA_KEEP_ALIVE=-1`

The supervisor warms `qwen3-coder-next:biella` with `num_gpu=26`, `num_ctx=16384`, and `keep_alive=-1`, then checks both native `/api/ps` and OpenAI-compatible `/v1/responses` paths.

## Provider environment

The controller sources the existing root-only runtime file and exposes configured credentials to child tools. The registry covers AI inference, search, vector stores, speech/audio, media, databases/runtime, observability, and stock-media APIs. Provider health is independent: live-safe checks report `CONNECTED`; credentials that are usable but have no non-billable probe report `CONFIGURED`; credentials missing a required non-secret project locator report `NEEDS_LOCATOR`; failures report `DEGRADED` without blocking healthy lanes.
## Agent modes and noise control

`biella agent` is the fast local-first creation mode. It delegates to the same `biella-codex` controller but supplies `mcp_servers.saturn.enabled=false` for startup so local work does not wait on MCP initialization. All configured provider credentials remain available to explicit tools and subprocesses.

`biella codex` is the full-controller mode and retains Saturn MCP registration.

A global Codex `AGENTS.md` policy applies across Biella work:

- execute directly when requirements are clear;
- prefer local Qwen for routine bulk work;
- use one external provider by default and fan out only when comparison or independent validation is useful;
- suppress repetitive command narration and successful provider response bodies;
- show concise summaries and full details only for failures or requested diagnostics;
- never print secret values;
- preserve project authority and current accepted state.

## Storage layout

Create `/mnt/biella-extra/biella-runtime/` with `cache/`, `tmp/`, `logs/`, `builds/`, and `models/` directories. New supervisor caches/logs/build scratch use this volume where practical. Existing Ollama model data and production/evidence trees are not moved during this implementation.

## Cleanup boundary

`biella cleanup` may stop only known temporary diagnostic processes owned by this workstation setup, including the legacy `tmux llm-router` after successful service cutover and the known temporary Python HTTP servers / quick tunnel. It must not kill Desktop Commander, SSH sessions, Docker, production jobs, or arbitrary processes.

## Acceptance

The implementation is accepted only when fresh checks prove:

- systemd-supervised Ollama is active and reboot-capable;
- Qwen native API and `/v1/responses` are healthy;
- VRAM residency remains positive and below 30 GiB;
- `biella agent` can invoke the local Codex/Qwen path without eager Saturn MCP;
- `biella codex` retains Saturn MCP;
- Modal auth is valid;
- the core verified provider set remains healthy and every additional configured provider is reported independently as `CONNECTED`, `CONFIGURED`, `NEEDS_LOCATOR`, or `DEGRADED`;
- Gemini/Google is either healthy or explicitly reported degraded with its observed cause;
- extra runtime storage exists on `/mnt/biella-extra`;
- temporary legacy processes are absent after cleanup;
- all repo tests added for the supervisor pass and the implementation branch is clean.
