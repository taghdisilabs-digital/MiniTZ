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

The first interactive start asks for the Saturn URL/token and the Cloudflare
Account ID plus Workers AI API token. An optional `CLOUDFLARE_TUNNEL_TOKEN`
may be supplied separately when external tunnel ingress is wanted. Provider
credentials are written only to `/root/.config/biella-ai/runtime.env`, owned by
root with mode `0600`. No secret belongs in Git, Drive, or the project manifest.

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
- Cloudflare Workers AI uses `CLOUDFLARE_ACCOUNT_ID` and
  `CLOUDFLARE_API_TOKEN`; startup verifies those credentials against the
  Workers AI account API. A tunnel token is optional external ingress only and
  never sits between Codex and Ollama.

The launcher does not perform a model unload/reload tuning loop. If the VRAM
bound fails, it stops and records the observed state for diagnosis.

## Preconditions

The target host must already provide Ollama, the exact model, Codex, Python 3,
and `curl`. Saturn probing needs either an installed `saturn-client` or `uv`;
the MCP bridge needs `uvx`. Cloudflare requires an installed `cloudflared`
binary unless an already-running tunnel service is available.
