# Biella Build Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a durable, contract-first Biella build structure that can evolve from local development to fully offline high-end single-node and optional multi-node execution without changing kernel semantics.

**Architecture:** Biella keeps a narrow durable kernel and defines versioned language-neutral contracts before binding to local inference engines or deployment stacks. Model servers, storage systems, GPU runtimes and cluster tools are replaceable adapters/runtime profiles. Every accepted source change becomes durable only after push and remote readback.

**Tech Stack:** Git/GitHub for durable source; Google Drive for operator architecture/current-state records; JSON Schema/OpenAPI for initial language-neutral contracts; later local implementations may include vLLM, llama.cpp, TensorRT-LLM, PostgreSQL/pgvector, NVIDIA Container Toolkit and OpenTelemetry without making them kernel requirements.

**Spec:** `docs/superpowers/specs/2026-08-26-biella-build-structure-design.md`

## Global Constraints

- Never treat a local-only commit, workstation, VPS, cache, browser session, or provider session as durable accepted Biella source.
- Every accepted implementation commit must be pushed and read back from GitHub before Drive marks it durable/current.
- The durable kernel remains approximately Project, Task, Run, Capability, Graph, Node, Artifact, Resource, Event, Knowledge.
- Model/provider/GPU/runtime/storage/cluster choices remain adapters, runtime state, or deployment profiles.
- Do not reintroduce a fixed agent hierarchy, fixed global pipeline, fixed retry count, or cache as correctness authority.
- Do not use the lost Spot VPS P0-01 SHA as current durable source unless it is independently reconstructed into GitHub and verified.
- Keep `website/` and `docs/biellawebsite/` outside kernel implementation boundaries.

---

### Task 1: Reconcile durable source truth

**Files:**
- Verify: GitHub `main`
- Modify: Google Drive `10_BIELLA_CURRENT_STATE.md`
- Modify: Google Drive `11_BIELLA_REPOSITORY_STATE.md`
- Modify: Google Drive `16_BIELLA_RESOURCE_AND_RUNTIME_STATE.md`
- Modify: Google Drive `20_BIELLA_PROMPT_EXECUTION_STATUS.md`
- Modify: Google Drive `22_BIELLA_UNRESOLVED_FACTS.md`

**Interfaces:**
- Consumes: current GitHub repository metadata/history and current Drive living-state records.
- Produces: one consistent durable-source baseline and explicit stale/lost-runtime markers.

- [ ] **Step 1: Read current GitHub repository state**

Run/read equivalent remote operations for:

```text
repository: patrickminitz-web/biella-engine
default branch: main
recent commits
current main tree
presence/absence of previously recorded P0-01 commit b7cc3db0a9feb34d72764261d32163d2b05ac123
```

Expected: current remote state is authoritative for durable source; the lost VPS SHA is not accepted if GitHub cannot resolve it.

- [ ] **Step 2: Read the five Drive living-state records**

Confirm every statement that still names the terminated Spot VPS, `/home/ubuntu/biella-work/...` as current runtime, or `b7cc3db...` as durable canonical source.

Expected: stale assertions are identified explicitly rather than silently preserved.

- [ ] **Step 3: Rewrite current-state facts**

Record:

```text
terminated Spot instance: historical/unavailable runtime
old VPS filesystem: unavailable
GitHub main: durable source authority for code
Drive: durable operator/architecture/current-state record
P0-01/P0-02 implementation status: requires durable GitHub re-establishment before continuation
```

- [ ] **Step 4: Verify Drive readback**

Read the updated records again and ensure no current-state paragraph still treats the lost local P0-01 commit or dead VPS paths as current authoritative implementation.

- [ ] **Step 5: Record completion evidence**

Capture the GitHub commit at which the design/plan is stored and the Drive revision IDs after current-state reconciliation.

---

### Task 2: Establish remote-verified source durability discipline

**Files:**
- Create later when engine source root resumes: `AGENTS.md`
- Create later when engine source root resumes: `CURRENT_TASK.md`
- Create: `docs/operations/source-durability.md`
- Test/verify: remote GitHub readback

**Interfaces:**
- Consumes: canonical Git repository and owner work policy.
- Produces: explicit source-promotion rule used by every future Codex run.

- [ ] **Step 1: Create the durability document**

Required content:

```text
LOCAL WORK
→ focused tests
→ relevant regression tests
→ commit
→ push GitHub
→ remote fetch/readback of commit and tree
→ update Drive living state
→ mark accepted/durable
```

- [ ] **Step 2: Define machine-loss semantics**

Record exactly:

```text
worker/workspace/cache loss MAY reduce capacity or speed
worker/workspace/cache loss MUST NOT destroy accepted source, Run truth, Artifact identity, or Knowledge
```

- [ ] **Step 3: Commit and push**

Create one coherent GitHub commit containing the durability document.

- [ ] **Step 4: Remote verification**

Fetch the new file and exact commit from GitHub after push.

Expected: content matches the committed bytes and the remote commit resolves.

---

### Task 3: Create the versioned contract spine

**Files:**
- Create: `contracts/identity/execution-identity.schema.json`
- Create: `contracts/model/model-provider.schema.json`
- Create: `contracts/model/model-descriptor.schema.json`
- Create: `contracts/resource/resource-snapshot.schema.json`
- Create: `contracts/worker/worker-protocol.schema.json`
- Create: `contracts/context/context-receipt.schema.json`
- Create: `contracts/telemetry/telemetry-correlation.schema.json`
- Create: `contracts/deployment/runtime-profile.schema.json`
- Test: `tests/contract/`

**Interfaces:**
- Consumes: the accepted Biella architecture spec.
- Produces: language-neutral v1 contract schemas for future kernel/runtime implementations.

- [ ] **Step 1: Add execution identity schema**

Minimum shape:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://biella.local/contracts/identity/execution-identity.v1.schema.json",
  "type": "object",
  "required": ["project_id", "task_id", "task_revision", "run_id", "graph_id", "graph_revision", "node_id", "attempt", "fence", "executor_id"],
  "properties": {
    "project_id": {"type": "string", "minLength": 1},
    "task_id": {"type": "string", "minLength": 1},
    "task_revision": {"type": "integer", "minimum": 1},
    "run_id": {"type": "string", "minLength": 1},
    "graph_id": {"type": "string", "minLength": 1},
    "graph_revision": {"type": "integer", "minimum": 1},
    "node_id": {"type": "string", "minLength": 1},
    "attempt": {"type": "integer", "minimum": 1},
    "fence": {"type": "integer", "minimum": 1},
    "executor_id": {"type": "string", "minLength": 1}
  },
  "additionalProperties": false
}
```

- [ ] **Step 2: Add ModelProvider and ModelDescriptor schemas**

ModelProvider must normalize `health`, `list_models`, `resolve_model`, `infer`, `stream`, `cancel` semantics and evidence fields without embedding vLLM/llama.cpp/TensorRT-specific request types.

ModelDescriptor must include exact model/runtime revision identity and optional resource requirements.

- [ ] **Step 3: Add ResourceSnapshot schema**

Represent configured and measured/effective capacity separately. Include observation freshness and locality fields.

- [ ] **Step 4: Add WorkerProtocol schema**

Represent `register`, `heartbeat`, capability advertisement, ResourceSnapshot publication, lease/start/progress/checkpoint/cancel/finish/fail messages and fence identity.

- [ ] **Step 5: Add ContextReceipt, TelemetryCorrelation and RuntimeProfile schemas**

Do not put secrets or raw prompts into telemetry correlation fields.

- [ ] **Step 6: Add contract tests**

For each schema test:

```text
valid minimal object → accepted
missing required identity → rejected
unknown version → rejected or explicitly compatibility-handled
provider/GPU-specific field in kernel identity → rejected
```

- [ ] **Step 7: Commit, push and remote-readback**

Do not advance to kernel implementation until all schemas and contract tests are durable remotely.

---

### Task 4: Re-establish P0 implementation from durable Git truth

**Files:**
- Inspect/create under: `src/kernel/`
- Inspect/create under: `tests/unit/`, `tests/integration/`, `tests/fault/`, `tests/acceptance/`
- Read exact prompts: P0-01 through P0-10 from Drive

**Interfaces:**
- Consumes: versioned contract spine and exact P0 prompt contracts.
- Produces: durable P0 kernel implementation with remote-verifiable commits.

- [ ] **Step 1: Determine the actual engine implementation baseline**

Inspect GitHub tree instead of reconstructing from old chat logs. If P0-01 source is absent, classify it as absent and reimplement from the exact prompt/spec. If recoverable code exists, test it before reuse.

- [ ] **Step 2: Execute P0 prompts one at a time**

For each P0 prompt use:

```text
write failing focused test
→ run and observe intended failure
→ implement minimum task-scoped change
→ rerun focused test
→ run affected P0 regressions
→ inspect resulting state
→ commit
→ push
→ remote readback
→ Drive handoff update
→ stop
```

- [ ] **Step 3: Run P0 qualification**

Required evidence includes Project isolation, immutable Task/Graph revisions, stale-fence rejection, append-only Events, exact Artifact identity, restart durability, and zero provider/GPU/agent hierarchy in kernel.

---

### Task 5: Build P1 durability, cognition and resource routing

**Files:**
- Implement under: `src/services/memory/`, `src/services/recovery/`, `src/services/scheduler/`, `src/services/router/`
- Implement under: `src/runtime/resource-inventory/`, `src/runtime/model-registry/`
- Tests: `tests/integration/`, `tests/fault/`, `tests/performance/`

**Interfaces:**
- Consumes: P0 kernel + ModelProvider/ResourceSnapshot/WorkerProtocol contracts.
- Produces: resumable Runs, call accounting, measured resources, concurrent scheduling and routing.

- [ ] **Step 1: Implement content-addressed storage and memory scopes**
- [ ] **Step 2: Implement model/tool call ledger with token/cache provenance fields**
- [ ] **Step 3: Implement checkpoint/resume and fault tests**
- [ ] **Step 4: Implement measured ResourceSnapshot publication**
- [ ] **Step 5: Implement concurrent scheduler using hard constraints before ranking**
- [ ] **Step 6: Implement routing from Capability → implementation → runtime/model → Resource**
- [ ] **Step 7: Qualify provider/hardware replacement without Task changes**
- [ ] **Step 8: Commit/push/readback after each independently testable deliverable**

---

### Task 6: Implement local model providers behind the neutral contract

**Files:**
- Create: `src/adapters/model/vllm/`
- Create: `src/adapters/model/llamacpp/`
- Create when justified: `src/adapters/model/tensorrt-llm/`
- Tests: `tests/integration/model-provider/`

**Interfaces:**
- Consumes: ModelProvider, ModelDescriptor, ExecutionIdentity, ResourceSnapshot.
- Produces: interchangeable local inference implementations.

- [ ] **Step 1: Implement vLLM adapter**

Use the local vLLM OpenAI-compatible API but normalize responses into Biella model-call evidence. Keep vLLM-specific request extensions inside this adapter.

- [ ] **Step 2: Test model identity and token accounting**

Ensure exact configured model/runtime identity is recorded and unknown usage fields remain null/unknown rather than fabricated.

- [ ] **Step 3: Implement llama.cpp adapter**

Use OpenAI-compatible routes where possible and keep GGUF/runtime details adapter-local.

- [ ] **Step 4: Cross-provider contract test**

The same logical Biella request must execute against vLLM and llama.cpp without modifying Task/Capability contracts.

- [ ] **Step 5: Add TensorRT-LLM only after a measured need**

Add it as another adapter, never as a kernel branch.

---

### Task 7: Implement P2 execution fabric and local storage/retrieval profile

**Files:**
- Create/extend: `src/adapters/tools/`
- Create/extend: `src/adapters/storage/`
- Create/extend: `src/adapters/compute/`
- Create: `deploy/local-single-node/`
- Tests: `tests/integration/`, `tests/fault/`, `tests/offline/`

**Interfaces:**
- Consumes: P0/P1 kernel/services contracts.
- Produces: real filesystem/process/Git/container/HTTP/model/browser/database/object/context/workspace/validation execution.

- [ ] **Step 1: Implement filesystem/shell/Git/container/HTTP adapters**
- [ ] **Step 2: Implement PostgreSQL adapter and pgvector retrieval implementation**
- [ ] **Step 3: Implement durable ContentRef-preserving object-storage adapter**
- [ ] **Step 4: Implement ContextManifest/ContextArtifact/ContextReceipt pipeline**
- [ ] **Step 5: Implement workspace recreation after workspace loss**
- [ ] **Step 6: Qualify Task-derived validation without a global reviewer chain**

---

### Task 8: Add observability and recovery qualification

**Files:**
- Create: `src/observability/`
- Create: `deploy/local-single-node/observability/`
- Tests: `tests/fault/`, `tests/performance/`

**Interfaces:**
- Consumes: ExecutionIdentity and TelemetryCorrelation.
- Produces: correlated but non-authoritative traces/metrics/logs and recovery evidence.

- [ ] **Step 1: Add OpenTelemetry correlation**

Propagate non-secret identifiers required to correlate Project/Task/Run/Graph/Node/ModelCall/ToolCall while keeping Biella Events authoritative.

- [ ] **Step 2: Add NVIDIA metrics profile**

For NVIDIA runtime profiles, collect GPU/VRAM/utilization/health metrics through DCGM-compatible tooling or the current equivalent.

- [ ] **Step 3: Execute fault matrix**

Run:

```text
controller restart
worker kill
GPU inference process crash
model server restart
database restart
cache deletion
workspace deletion
network loss
machine loss
```

Expected: durable Run/source/Artifact truth remains recoverable.

---

### Task 9: Qualify the fully local high-end single-node profile

**Files:**
- Create/extend: `deploy/local-single-node/`
- Create: `tests/offline/`
- Create: `docs/operations/offline-qualification.md`

**Interfaces:**
- Consumes: complete P0-P2 execution stack and local model/storage adapters.
- Produces: proven internet-independent Biella operation on one high-end machine.

- [ ] **Step 1: Build runtime profile**

Profile may include Linux, NVIDIA driver, NVIDIA Container Toolkit, Docker/Compose + systemd, PostgreSQL/pgvector, CAS, vLLM, llama.cpp fallback, optional TensorRT-LLM, OpenTelemetry and GPU metrics. These remain deployment choices.

- [ ] **Step 2: Pre-stage exact model artifacts**

Record model/tokenizer/config digests and ensure runtime does not require network downloads.

- [ ] **Step 3: Disconnect internet**

Run the full offline acceptance sequence:

```text
Biella boots
local models load
Task executes
retrieval works
memory/state works
tools execute
Artifact persists
process restart recovers
```

- [ ] **Step 4: Change GPU allocation**

Verify 1→N GPU placement changes only Resource/runtime configuration and does not modify kernel/Task contracts.

---

### Task 10: Add optional multi-node profile only after single-node acceptance

**Files:**
- Create when required: `deploy/local-multi-node/`
- Tests: `tests/fault/multi-node/`, `tests/performance/multi-node/`

**Interfaces:**
- Consumes: WorkerProtocol, ResourceSnapshot, RuntimeProfile, durable ContentRef semantics.
- Produces: node placement and recovery without kernel changes.

- [ ] **Step 1: Add multi-node ResourceSnapshot aggregation**
- [ ] **Step 2: Add placement runtime (Ray/multiprocessing/other) as an adapter/profile choice**
- [ ] **Step 3: Add replicated/shared durable content strategy**
- [ ] **Step 4: Kill one node during execution and verify stale-fence rejection/recovery**
- [ ] **Step 5: Confirm single-node Task/Capability contracts are unchanged**

---

## Self-review result

- Spec coverage: source durability, contracts, P0, P1, local inference, P2, observability, offline qualification and optional multi-node scale are all mapped to independently testable tasks.
- Placeholder scan: no TBD/TODO/fill-later requirements are used.
- Type consistency: ExecutionIdentity, ModelProvider, ModelDescriptor, ResourceSnapshot, WorkerProtocol, ContextReceipt, TelemetryCorrelation and RuntimeProfile names match the design spec.
- Scope: implementation is intentionally phased; Task 1 is the immediate next executable boundary and must complete before engine code resumes.

## Execution handoff

Immediate next executable boundary: **Task 1 — Reconcile durable source truth.**

After Task 1, use task-by-task execution. Do not start P0 reconstruction until Drive and GitHub agree on durable source state.
