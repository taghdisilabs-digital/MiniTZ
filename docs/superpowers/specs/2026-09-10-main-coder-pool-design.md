# MiniTZ Main Coder Pool Design

## Goal
Make Codex and Antigravity (AGR/`agy`) interchangeable main-coder backends under one MiniTZ production authority, continuity, memory, cache, policy, evidence, and task state.

## Authority
The MiniTZ production runner remains the only canonical progression controller. At most one main coder owns canonical source mutation at an instant. A second ACTIVE coder may run an independent read-only peer assist in parallel. Provider/model sessions never own task identity or completion.

## Shared continuity
Both coders consume the same Task Program record, current worktree bytes, task-memory capsule, compacted current-task projection, failure/evidence journals, resource registry, and AGENTS policy. Provider-native session IDs are stored per task and coder but are optional accelerators; cross-coder handoff always resumes from MiniTZ durable state.

## Four-state status
Each coder exposes exactly OFFLINE, ACTIVE, OUT_OF_CREDIT, or NEEDS_MODIFICATION. ACTIVE means currently usable and must be considered when helpful. OUT_OF_CREDIT is set only from observed provider usage/credit errors. NEEDS_MODIFICATION means the CLI/service is present/online but MiniTZ cannot successfully use it.

## Selection and failover
Preserve Codex as the initial canonical writer while it remains ACTIVE to avoid disturbing live production behavior. If its actual request hits usage exhaustion, checkpoint current task state and route the same task to AGR without replay. If AGR is unavailable, existing Codex/local/provider recovery continues. Once measured history exists, primary choice may become evidence-driven.

## Parallel behavior
When Codex and AGR are both ACTIVE, keep one canonical writer and dispatch a distinct non-overlapping read-only peer work unit to the other backend. Peer output is content-addressed assistance and never completion authority. No simultaneous uncontrolled edits to the dirty canonical tree.

## AGR adapter
Use `/root/.local/bin/agy` headless structured JSON. Prompt input must not be placed in process argv when avoidable; use stream-json stdin for persistent/large work or bounded print invocation only for controlled metadata. The adapter records conversation IDs when returned, handles model discovery, classifies eligibility/configuration failures as NEEDS_MODIFICATION, and classifies observed quota exhaustion as OUT_OF_CREDIT.

## Policy
AGR receives the same canonical MiniTZ execution policy used by Codex plus the nearest project AGENTS.md. No separately authored GEMINI policy may drift from AGENTS authority.

## Compatibility
Keep `/usr/local/bin/biella-codex` as a compatibility entrypoint while its production path becomes main-coder-pool aware. Preserve existing runtime keys during migration and add coder-scoped session/status fields backward-compatibly.

## Safety of current work
Do not reset, stash, clean, checkout, or overwrite unrelated dirty state. Current `UNIFY-04` remains the task and its task/session/worktree continuity must survive this provider integration.
