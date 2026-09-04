# Biella bounded local-AI runtime

This is the current Engine execution boundary for the three connected Biella
lanes: Website, Engine, and Games. It does not replace the current task ledger
or introduce another manager/reviewer/router hierarchy.

## Install and start

From a checkout of `patrickminitz-web/biella-engine`, as root:

```bash
bash ops/local-ai/install-biella-ai.sh
biella-ai-start
```

The first interactive start asks for the Saturn URL, the Saturn API token, and
an optional Cloudflare tunnel token. The URL/token values are written only to
`/root/.config/biella-ai/runtime.env`, owned by root with mode `0600`. No secret
belongs in Git, Drive, or the project manifest.

## Runtime contract

- Ollama uses the already-installed `qwen3-coder-next:biella` model only.
- The first request fixes `num_gpu=26`, `num_ctx=16384`, and `keep_alive=-1`.
- `/api/ps` must report positive Qwen VRAM residency below 30 GiB.
- The CPU-side model residency target is 86 GiB RAM.
- A missing model is a hard stop; the launcher never runs `ollama pull`.
- vLLM is not part of this path.
- Codex remains the controller; `biella-codex` invokes Codex OSS mode against
  the local Ollama model.
- Saturn is connected through the official Saturn MCP package and is probed
  through its API before the MCP entry is registered with Codex.
- Cloudflare is external ingress only. A managed token uses a root-only token
  file and systemd; an empty token reuses an active service or starts a quick
  tunnel to the existing localhost gateway. It never sits between Codex and
  Ollama.

The launcher does not perform a model unload/reload tuning loop. If the VRAM
bound fails, it stops and records the observed state for diagnosis.

## Preconditions

The target host must already provide Ollama, the exact model, Codex, Python 3,
and `curl`. Saturn probing needs either an installed `saturn-client` or `uv`;
the MCP bridge needs `uvx`. Cloudflare requires an installed `cloudflared`
binary unless an already-running tunnel service is available.
