# Biella Recovery Runbooks

This index points to the current operational recovery/runbook documents for Biella infrastructure and replaceable production Resources.

## Authority

Recovery documentation records observed infrastructure behavior. It does not create new Biella architecture or project authority.

Current authority remains:

```text
CURRENT_EXECUTION_STATE
> CURRENT_GITHUB_SOURCE
> CURRENT_CANONICAL_DRIVE
> VERIFIED_HISTORICAL_EVIDENCE
> REFERENCE_OR_PLAN
> INFERENCE
```

Provider/model/GPU/worker identities are replaceable Resource state.

## Current runbooks

### L40S / Google Drive recovery and evacuation

```text
ops/google-drive-backup/README.md
ops/GOOGLE_DRIVE_LARGE_BINARY_UPLOAD.md
```

Records:

- current L40S recovery/backup identities;
- proven sequential large-file Drive upload procedure;
- fast evacuation vs optional byte-readback distinction;
- source-preservation rules.

### RTX5000 visual-production worker

```text
ops/RTX5000_RENDER_WORKER.md
```

Records the verified controller/worker boundary established on 2026-09-02:

```text
L40S controller
  owns current Biella source/state/task authority
  prepares task-scoped render work
        |
        | SSH / task-scoped transfer
        v
RTX5000 render worker
  Blender 5.2.1 LTS
  Quadro RTX 5000 / CUDA
  render/bake/visual processing only
        |
        | artifacts + logs
        v
L40S validates and integrates outputs
```

The RTX5000 worker is not a second autonomous source-writing authority.

### Bounded L40S local-AI runtime

```text
docs/project-state/BIELLA_LOCAL_AI_RUNTIME_DECISION_2026-09-04.md
docs/project-state/BIELLA_LOCAL_AI_RUNTIME_MANIFEST_2026-09-04.yaml
ops/local-ai/README.md
ops/local-ai/biella-ai-start.sh
```

This current runtime boundary uses the existing Ollama model
`qwen3-coder-next:biella` with 26 GPU layers, a 16K context, permanent
keep-alive, and a strict positive VRAM residency below 30 GiB. It has no model
download path and no vLLM path. Codex remains the controller; Saturn is exposed
through its official stdio MCP integration; Cloudflare is external ingress only
around the existing localhost gateway.

The launcher records live Saturn resource enumeration and service readiness
under `/var/lib/biella-ai/`, while credentials remain outside the repository
and Drive in root-only mode-`0600` runtime files.

## Secret handling

Never commit private keys, OAuth tokens, refresh tokens, Cloudflare credentials, `rclone.conf` contents, or similar secret material.

Current worker private-key material is intentionally outside Git and is referenced by path only in the render-worker runbook.

## Recovery rule

A new VPS, provider image, SSH session, GPU, model, or worker does not invalidate verified Biella work by itself.

Recover the smallest affected boundary, preserve valid outputs/source/evidence, reobserve replaceable Resource identity, then continue.
