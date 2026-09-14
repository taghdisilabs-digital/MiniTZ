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

### Current production and optional local-AI recovery

Use `docs/project-state/07_MINITZ_PRODUCTION_SYSTEM.md`, live `03`/`04`,
`ops/local-ai/README.md`, and the installed systemd/controller state.
`biella-codex production` is the production entrypoint. The existing task-class
router owns model selection; optional Qwen, Saturn, and other Resources do not
gate authoritative production. Preserve the current task/session and worktree.

Historical compatibility references, not startup instructions:

- `docs/project-state/MINITZ_LOCAL_AI_RUNTIME_DECISION_2026-09-04.md`
- `docs/project-state/MINITZ_LOCAL_AI_RUNTIME_MANIFEST_2026-09-04.yaml`

They remain at their existing paths for dependent references/tests. The old
six-step provisioning sequence is not the current production boot path.

## Secret handling

Never commit private keys, OAuth tokens, refresh tokens, Cloudflare credentials, `rclone.conf` contents, or similar secret material.

Current worker private-key material is intentionally outside Git and is referenced by path only in the render-worker runbook.

## Recovery rule

A new VPS, provider image, SSH session, GPU, model, or worker does not invalidate verified Biella work by itself.

Recover the smallest affected boundary, preserve valid outputs/source/evidence, reobserve replaceable Resource identity, then continue.
