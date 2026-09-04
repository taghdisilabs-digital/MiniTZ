# Biella local-AI runtime decision — 2026-09-04

Status: `IMPLEMENTED_IN_REPOSITORY / RUNTIME_VALIDATION_PENDING`

This is a bounded current-state decision for the Biella Engine execution
boundary. It applies across the three connected lanes — Biella Website, Biella
Engine, and Biella Games — without changing their ownership boundaries or the
current task ledger.

## Authoritative runtime behavior

1. Ollama loads the existing `qwen3-coder-next:biella` model only.
2. The first load request uses exactly 26 GPU layers, a 16K context, and
   `keep_alive=-1`.
3. The launcher accepts the load only when Ollama reports positive Qwen VRAM
   residency strictly below 30 GiB. The remaining model residency is allowed
   on CPU/RAM, with the target host allocation recorded as 86 GiB RAM.
4. A missing model is a hard stop. This runtime contains no model download,
   model creation, vLLM server, or unload/reload tuning loop.
5. Codex is the main controller. Qwen is its inexpensive local bulk worker.
6. Codex-to-Ollama traffic remains on localhost. Cloudflare is never inserted
   on that path.

## Saturn boundary

Saturn is connected as Saturn's actual API/MCP integration. The launcher asks
for `SATURN_BASE_URL` and `SATURN_TOKEN` on first start, writes them to a
root-owned mode-`0600` runtime file, performs a live resource and instance-type
enumeration, then registers the official Saturn stdio MCP bridge with Codex.

The bridge exposes Saturn operations through the official package, including
resource listing/inspection, start/stop, logs, and instance-type discovery.
There is no invented Saturn OpenAI-compatible endpoint and the token is never
treated as a model endpoint.

## Cloudflare boundary

Cloudflare is external ingress only. The configured origin is the existing
localhost gateway at `http://127.0.0.1:8787`; the launcher does not create that
gateway or change its routes. A supplied tunnel token is saved as a root-only
token file and used by a managed systemd service when systemd is available.
Pressing Enter at the token prompt reuses an active service or uses a quick
tunnel if `cloudflared` is installed.

The tunnel's remote ingress mapping remains a Cloudflare-side configuration.
The launcher reports tunnel process connectivity separately from gateway health
so a tunnel process is not mistaken for a healthy application origin.

## Startup sequence

```text
[1/6] Starting Ollama
[2/6] Loading Qwen with <=30 GiB VRAM
[3/6] Connecting Saturn
[4/6] Registering Saturn tools with Codex
[5/6] Starting Cloudflare
[6/6] Checking services
```

The final report includes Local Qwen, measured Qwen VRAM, Saturn enumeration
counts, Cloudflare mode, gateway health (`READY` or `NOT_VERIFIED`), and Codex
MCP registration. A failed bound or failed live connection stops startup.

## Current observations used for this decision

On the supplied 2026-09-04 L40S observation, the host reported NVIDIA L40S,
46,068 MiB total memory, 26,953 MiB used, and driver `580.178.04`. The local
port `8000` endpoint was not running, and the captured vLLM error treated the
local model path as a repository identifier. The bounded runtime therefore
uses the already-present Ollama model and refuses to invoke vLLM or download a
replacement.

The RTX5000 deletion is recorded here only as the current recovery trigger:
reported 2026-09-03 near the end of the day. It does not change the authority
of current GitHub source, current Drive state, or the L40S controller boundary.

## Secret and filing rules

- No Saturn or Cloudflare value is embedded in source, GitHub, Drive, manifests,
  logs, or the Codex registration command.
- Runtime credentials exist only in the root-owned runtime file; the managed
  Cloudflare service additionally reads a root-owned token file.
- Current filings contain only current verified/explicitly accepted state.
  Historical, superseded, legacy, exploratory, and unverified material is not
  promoted into this decision record.

## Implementation files

- `ops/local-ai/install-biella-ai.sh` — installs the bounded runtime commands.
- `ops/local-ai/biella-ai-start.sh` — six-step launcher and readiness checks.
- `ops/local-ai/biella-saturn-probe.py` — live Saturn resource enumeration.
- `ops/local-ai/biella-saturn-mcp.sh` — root-only official Saturn MCP bridge.
- `ops/local-ai/biella-codex.sh` — Codex local OSS invocation.
- `docs/project-state/BIELLA_LOCAL_AI_RUNTIME_MANIFEST_2026-09-04.yaml` —
  machine-readable current manifest.

## External implementation references

- [Saturn Cloud Claude Code integration](https://saturncloud.io/docs/user-guide/integrations/claude-code/)
- [Saturn Cloud official Claude plugin](https://github.com/saturncloud/claude-plugin)
- [Cloudflare Tunnel run parameters](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/run-parameters/)
- [Codex MCP configuration](https://developers.openai.com/codex/mcp)
