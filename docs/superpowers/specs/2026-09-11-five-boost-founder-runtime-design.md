# MiniTZ Five-Boost Founder Runtime Design

## Authority

This design implements the owner's 2026-09-11 approved MiniTZ execution expansion.
The living MiniTZ Task Program remains the only production order/status/progression authority.
Boost workers, Commander lanes, browser slots, model sessions, runtime projections, caches, and website views have authority `NONE`.
Windows compatibility is outside this design; the driver domain is Linux-only.

## Five-Boost execution fabric

Every canonical MiniTZ task is projected into five derived sections without duplicating canonical task identity:

1. `BOOST-01 Contract/Authority`: CMD-01, CMD-02, CMD-03, CMD-12, CMD-20, CMD-28.
2. `BOOST-02 Core Engineering`: CMD-04, CMD-05, CMD-13, CMD-16, CMD-27, CMD-29.
3. `BOOST-03 Runtime/Integration`: CMD-06, CMD-14, CMD-15, CMD-18, CMD-19, CMD-21.
4. `BOOST-04 Qualification`: CMD-07, CMD-08, CMD-09, CMD-10, CMD-17, CMD-26.
5. `BOOST-05 Continuity/Delivery`: CMD-11, CMD-22, CMD-23, CMD-24, CMD-25, CMD-30.

All 30 Commander lanes are assigned exactly once. Boost workers may write only paths leased to their derived section; overlapping write scopes are forbidden.
## Shared state and worker continuity

Runtime coordination lives under `memory/boost-fabric/` beneath the existing production runtime root.
`task-plan.json` contains the full derived task lists; `current.json` is the shared current projection; assignments are task-digest bound; each worker writes only its own report.
A worker report must match Boost ID, canonical task ID, task-record SHA-256, and source Task Program SHA-256.
Stale or foreign reports are rejected and never advance the Task Program.

The start policy is `WITH_PRODUCTION_OWNER_RESUME` and initial runtime state is `ARMED_NOT_STARTED`.
Creating plans, installing source, or publishing status must not start production, local models, GPU residency, or browser workers.

## Reserved usage

`gpt-reserve` is an eligible preferred strong route only when present in observed catalog metadata.
Quota/balance probing is forbidden. Normal task execution evidence may change provider state or route eligibility.
Failure of the reserved route falls back to the existing task-class routing policy without changing authority or task identity.

## GPU residency

The observed NVIDIA L40S capacity is 46,068 MiB. MiniTZ reserves at least 2,048 MiB free.
The logic slot uses `qwen3-coder-next:biella`, 34 of 48 GPU blocks, with an estimated 35,246 MiB residency and hard budget of 35,828 MiB.
The visual-generation slot has an 8,192 MiB budget and remains `UNBOUND_NEEDS_QUALIFICATION` until real local weights pass functional validation.
The combined admitted maximum is 44,020 MiB. Actual VRAM readback, not the planning estimate, is authoritative.
## HAL, Founder Mode, trust and browser swarm

HAL qualification binds Linux-native hardware/driver resources to semantic MiniTZ capabilities. The current executing substrate remains the Linux kernel; no host-kernel-bypass claim is allowed until a future architecture can prove it.
Founder Mode maps qualified CPU topology, GPU/VRAM and I/O groups into explicit fenced Run leases with deterministic ownership/accounting rather than generic desktop scheduling assumptions.

Strict node trust is an inspectable set of boot-integrity, node/root identity, storage-policy and authenticated root/cloud-anchor checks. Raw credential values are never Task Program, Boost, cache, log, or website payload.
Missing trust anchors may degrade privileged execution but must preserve bounded provisioning/recovery.

The browser swarm target is 30 isolated automation slots behind MiniTZ resource routing. A target slot count is not a claim that 30 live browser processes exist. Readiness requires bounded handshake, lease, timeout and credential-isolation evidence.

## Validation and website projection

SHA-256 binds canonical task/program/source identities and worker reports. A 98% cache-efficiency value is a target only; observed efficiency remains unknown until measured.
The private `/control` surface shows five Boost groups, Commander lane states, current/next derived task sections, and reserved-route policy.
The public `/live` surface shows only sanitized aggregate Boost state and never private paths, credentials, task write scopes, provider secrets, or internal findings.

The canonical task extension adds seven owner-approved tasks after `RUNTIME-AI-01`: `HAL-LINUX-01`, `HAL-FOUNDER-01`, `TRUST-NODE-01`, `GPU-RESIDENCY-01`, `BOOST-FABRIC-01`, `BROWSER-SWARM-01`, and `SYSTEM-QUALIFY-01`.
Task-program insertion is transactional, digest-validated, idempotent for the exact same extension, and preserves current execution identity.
