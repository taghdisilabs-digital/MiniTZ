# Biella Control Gateway Implementation Plan

**Goal:** Make the existing Website `/control/` console operational at `control.biellagames.dev` through a local VPS gateway and Cloudflare Tunnel.

**Architecture:** Python stdlib `ThreadingHTTPServer` on `127.0.0.1:8787` serves the verified Website build and same-origin `/v1/control/*` APIs. The gateway exposes only declared operations, uses scrypt password hashes and secure sessions, and invokes project-scoped Codex or exact approved commands. Cloudflare Tunnel is external ingress only.

**Source contract:** `website/docs/CONTROL_CONSOLE_GATEWAY_CONTRACT.md` at Website head `0130ab2`; Drive implementation record `BIELLA_CONTROL_CONSOLE_IMPLEMENTATION_2026-09-04.md`.

## Progress

- Task 1 — COMPLETED.
- Task 2 — COMPLETED.
- Task 3 — COMPLETED.
- Task 4 — COMPLETED.
- Task 5 — BLOCKED_CLOUDFLARE_TUNNEL_EDIT_PERMISSION; local gateway verified.
  - Temporary preview verified: https://streaming-vitamin-technological-looks.trycloudflare.com/control/
  - Gateway auth state: NOT_CONFIGURED; run `biella-control-auth configure` locally.
  - Browser local-agent path verified: `BROWSER_AGENT_READY`; Engine worktree remained clean.

### Task 1: Auth and HTTP contract
- [x] Add failing tests for role enforcement, session cookies, and no generic command route.
- [x] Implement scrypt auth store and secure in-memory sessions.
- [x] Implement static `/control/`, redirect `/`, and session routes.
- [x] Run tests and commit.

### Task 2: Current-state read APIs
- [x] Add failing tests for Website/Engine/Games lane validation and response shapes.
- [x] Implement overview, capabilities, services, milestones, hardware, workers, and files using current sources only.
- [x] Keep provider failures independent and exclude historical/superseded/unverified records.
- [x] Run tests and commit.

### Task 3: Dialog, runs, and SSE
- [x] Add failing tests for observer write rejection and approved capability allowlist.
- [x] Implement SSE event queues.
- [x] Implement project-scoped local Codex dialog jobs and exact approved run commands.
- [x] Run tests and commit.

### Task 4: VPS service and static deployment
- [x] Add systemd service and installer contract tests.
- [x] Install Website `dist` to `/var/lib/biella-control/site` without changing `biellagames.dev`.
- [x] Install gateway under `/usr/local/lib/biella-control` and enable `biella-control-gateway.service`.
- [x] Verify localhost `/control/` and API behavior; configure password hashes locally when available.

### Task 5: Cloudflare ingress and live verification
- [ ] Create a named Cloudflare Tunnel for `control.biellagames.dev` only.
- [ ] Route DNS to the tunnel without changing public `biellagames.dev` records.
- [ ] Install/enable cloudflared service with root-only tunnel credentials.
- [ ] Verify HTTPS static console, unauthenticated session behavior, login readiness, and localhost-only Qwen path.
- [ ] Merge gateway branch to Engine `main` only after all checks pass.
