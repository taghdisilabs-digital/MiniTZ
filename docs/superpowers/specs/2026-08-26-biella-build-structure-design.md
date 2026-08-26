# Biella Build Structure and Fully Local Runtime Design

Status: ACCEPTED DESIGN FOR BUILD PHASE
Date: 2026-08-26
Scope: Biella Engine build structure, durability, local inference, runtime profiles, observability, and scale-out boundaries.

## 1. Goal

Build Biella Engine so its durable kernel remains project-neutral and provider-neutral while the finished system can operate fully locally on high-end hardware with no internet dependency at runtime.

The build strategy is contract-first + runtime profiles:

1. Reconcile durable source truth before more engine work.
2. Define versioned execution contracts before binding implementation to one language, model server, GPU family, database, or cluster system.
3. Build P0/P1 kernel semantics against those contracts.
4. Add local inference servers as replaceable ModelProvider implementations.
5. Add P2 execution adapters without changing kernel semantics.
6. Qualify recovery, observability, offline operation, and high-end local deployment.
7. Add multi-node placement only when one node is insufficient.

## 2. Current source-truth correction

Current durable evidence is inconsistent and must be reconciled before engine implementation resumes.

- Google Drive living state records a P0-01 result at commit `b7cc3db0a9feb34d72764261d32163d2b05ac123` and tree `ec44bacc13e11f9c38c1b5ac7c3844ac74f24a11` from the lost VPS.
- Current GitHub cannot resolve that P0-01 SHA.
- The current `patrickminitz-web/biella-engine` repository is reachable and has newer durable website/document commits on `main`.
- Therefore the lost VPS commit cannot be treated as durable canonical Git state until reconstructed or independently recovered.
- P0-01/P0-02 status must be re-established from durable GitHub evidence and owner direction rather than from the lost local filesystem.

Durability rule:

```text
LOCAL WORK
→ test
→ commit
→ push GitHub
→ read back remote commit/tree
→ only then mark accepted/durable in Drive
```

No accepted Biella implementation may exist only on a workstation, VPS, model session, browser session, temporary disk, or cache.

## 3. Architectural thesis

Biella is a small durable universal execution kernel surrounded by replaceable capability implementations and runtime profiles.

The stable flow is:

```text
Project → Task → Run → Graph → Node → Capability → Implementation → Resource → Artifact/Event/Knowledge
```

The kernel must not depend permanently on vLLM, llama.cpp, TensorRT-LLM, Triton, NVIDIA hardware, Ray, Kubernetes, PostgreSQL, a fixed cloud, a fixed model family, or a fixed worker topology.

Those belong in adapters, runtime state, or deployment profiles.

## 4. Build-time repository structure

Do not choose the implementation language merely to create this layout. Durable contracts should be language-neutral where practical; the controller implementation language is selected from actual engineering requirements when canonical engine implementation resumes.

```text
biella-engine/
├── AGENTS.md
├── CURRENT_TASK.md
├── README.md
│
├── contracts/
│   ├── identity/
│   ├── project/
│   ├── task/
│   ├── run/
│   ├── capability/
│   ├── graph/
│   ├── artifact/
│   ├── event/
│   ├── resource/
│   ├── model/
│   ├── worker/
│   ├── context/
│   ├── telemetry/
│   └── deployment/
│
├── src/
│   ├── kernel/
│   │   ├── project/
│   │   ├── task/
│   │   ├── run/
│   │   ├── capability/
│   │   ├── graph/
│   │   ├── artifact/
│   │   ├── resource/
│   │   ├── event/
│   │   └── knowledge/
│   ├── services/
│   │   ├── scheduler/
│   │   ├── router/
│   │   ├── context/
│   │   ├── memory/
│   │   ├── recovery/
│   │   └── validation/
│   ├── adapters/
│   │   ├── model/
│   │   ├── storage/
│   │   ├── compute/
│   │   └── tools/
│   ├── runtime/
│   │   ├── resource-inventory/
│   │   ├── model-registry/
│   │   └── worker/
│   └── observability/
│
├── deploy/
│   ├── dev/
│   ├── local-single-node/
│   └── local-multi-node/
│
├── tests/
│   ├── contract/
│   ├── unit/
│   ├── integration/
│   ├── fault/
│   ├── acceptance/
│   ├── performance/
│   └── offline/
│
├── tools/
│   ├── bootstrap/
│   ├── verify/
│   ├── backup/
│   └── benchmark/
│
├── docs/
│   ├── architecture/
│   ├── decisions/
│   ├── operations/
│   ├── biellawebsite/
│   └── superpowers/
│       ├── specs/
│       └── plans/
│
└── website/
```

Boundary meanings:

- `contracts/` = stable versioned semantic envelopes and interfaces.
- `src/kernel/` = universal durable semantics only.
- `src/services/` = scheduling, routing, context, memory, recovery, validation behavior around kernel objects.
- `src/adapters/` = replaceable external implementations.
- `src/runtime/` = measured execution machinery and runtime registries.
- `deploy/` = machine/cluster-specific profiles.
- `website/` and `docs/biellawebsite/` = website product/documentation and explicitly not kernel code.

## 5. Contracts to define during the build phase

### 5.1 ExecutionIdentity

Every meaningful operation carries exact execution identity:

```text
project_id
task_id
task_revision
run_id
graph_id
graph_revision
node_id
attempt
fence
executor_id
```

This identity propagates through model calls, tool calls, Artifacts, Events, checkpoints, telemetry, and finalization.

### 5.2 ModelProvider

Define the neutral contract before implementing any local inference engine.

Required operations:

```text
health
list_models
resolve_model
infer
stream
cancel
```

Required normalized evidence where available:

```text
provider/runtime identity
model identity + revision
tokenizer/config/weight digests
modalities
context limit
tool-call support
structured-output support
embedding/reranking support
input tokens
output tokens
reasoning tokens
cached input/cache-write metrics
queue latency
execution latency
status/failure
```

Provider-specific request fields remain adapter-local.

### 5.3 ModelDescriptor

```text
model_id
family
revision
weight_digest
tokenizer_digest
config_digest
runtime
runtime_version
quantization
modalities
context_limit
required_ram
required_vram
local_path
compatibility
observed_benchmarks
```

A marketing/friendly model alias is not sufficient durable identity.

### 5.4 ResourceSnapshot

Track configured capacity separately from measured/effective capacity:

```text
CPU topology/load
RAM physical/effective
GPU devices/features
VRAM physical/effective
NVMe capacity/locality
network reachability/latency/bandwidth hints
loaded models
loaded toolchains
warm caches
Artifact locality
workspace locality
active allocations
queue pressure
health
cost where known
observation freshness
```

Hardware shortage changes routing, not Capability identity.

### 5.5 Artifact / ContentRef / StorageLocation

Keep these identities separate.

```text
Artifact != ContentRef != StorageLocation
```

Exact content identity should use cryptographic digests; multiple logical Artifacts may refer to identical bytes without collapsing Project authorization or provenance.

### 5.6 WorkerProtocol

Define before multi-GPU/multi-node implementation:

```text
register
heartbeat
advertise_capabilities
publish_resource_snapshot
lease
start
progress
checkpoint
cancel
finish
fail
```

A stale worker result cannot finalize after its fence has been superseded.

### 5.7 Context contracts

Use versioned:

```text
ContextManifest
ContextArtifact
ContextReceipt
```

Each retrieved item retains Project, source Artifact, content digest, source revision, chunk identity, index version, embedding implementation/runtime, score, and reranker identity where used.

### 5.8 TelemetryCorrelation

Correlate:

```text
Project → Task → Run → Graph → Node → ModelCall / ToolCall
```

Telemetry is observability/evidence only and never becomes Biella execution authority.

### 5.9 RuntimeProfile

```text
runtime_profile_id
host/runtime identity
resources
container runtime
model implementations
storage implementations
network topology
observability endpoints
offline capability
```

`local-single-node` and `local-multi-node` are deployment data/configuration, not different kernels.

### 5.10 DurabilityContract

```text
accepted source     → remotely verified Git commit/tree
durable metadata   → durable database + backup
Artifacts          → content-addressed storage + durable replica
model weights      → exact digest + durable local store
workspace          → disposable
cache              → disposable
worker             → disposable
```

A lost compute machine must reduce capacity, not destroy accepted Biella truth.

## 6. Build phases

### Phase 0 — Source truth and durability reset

- Inventory current GitHub tree and recent history.
- Reconcile stale Drive current-state/repository-state/prompt-status records.
- Mark the terminated Spot VPS and its paths as historical/unavailable runtime observations.
- Re-establish the real canonical engine baseline from durable GitHub content.
- Keep website work explicitly outside kernel paths.
- Enforce remote-readback after every accepted commit.

Exit gate:

- canonical baseline is remotely recoverable;
- no accepted code exists only on a worker disk;
- Drive current-state records agree with durable GitHub truth.

### Phase 1 — Versioned contract spine

Create language-neutral contract schemas for identity, Project, Task, Run, Capability, Graph/Node, Artifact, Event, Resource, ModelProvider, WorkerProtocol, Context, TelemetryCorrelation and RuntimeProfile.

Use JSON Schema/OpenAPI initially where appropriate. Do not introduce Protobuf solely for hypothetical future clustering.

Exit gate:

- contract tests establish versioning/compatibility behavior;
- provider/GPU/runtime changes do not alter Task/Capability semantics.

### Phase 2 — P0 durable kernel

Implement/reconstruct from durable Git truth:

1. Clean-Room Migration Firewall
2. Project Namespace / Isolation
3. Capability Contract
4. Task Contract
5. Run Identity / Attempts / Leases / Fencing
6. Artifact & Source Identity
7. Graph & Node Contract
8. Event Ledger
9. Durable Execution State
10. P0 Integration / Qualification

Exit gate includes Project isolation, immutable revisions, fencing, append-only Events, exact Artifact identity, restart durability, and zero provider/GPU/agent hierarchy in kernel.

### Phase 3 — P1 durability, cognition, resources and routing

Implement:

- content-addressed object store;
- Run Memory;
- Project Memory;
- Engine Knowledge promotion boundary;
- model/tool call ledger;
- checkpoint/resume;
- dynamic Resource inventory;
- concurrent scheduler;
- provider/resource-neutral routing.

Exit gate:

- Run reconstructs without chat/provider session;
- configured vs measured Resource state is distinct;
- provider/hardware swaps do not change Task/Capability semantics.

### Phase 4 — First real local model-provider implementations

Implement adapters behind the neutral ModelProvider contract:

```text
ModelProvider
├── local-vllm
├── local-llamacpp
├── local-trtllm     optional optimized path
└── hosted-*         optional adapters
```

Recommended first implementation: vLLM for high-throughput GPU serving.

Recommended fallback: llama.cpp for lightweight GGUF, CPU/GPU hybrid, and broad local hardware support.

TensorRT-LLM is optional for hot NVIDIA workloads where its optimization benefit is measured and justified.

Triton is not mandatory at this stage. Add it only when unified multi-model serving materially reduces operational complexity.

Exit gate:

- the same Biella Task/ModelProvider contract works across at least two local implementations;
- exact model/runtime identity and available token/cache metrics are recorded;
- model server change requires no kernel change.

### Phase 5 — P2 universal execution fabric

Implement replaceable adapters for filesystem, shell/process, Git, isolated/container runtime, HTTP/API, model provider, browser, PostgreSQL, durable object storage, context/retrieval, Workspace/Sandbox, and Task-derived validation/evaluation.

Exit gate:

- real adapter actions are attributable to exact Run/Graph/Node;
- workspace loss cannot destroy durable work;
- provider/runtime replacement does not alter kernel semantics.

### Phase 6 — Observability and recovery qualification

Use OpenTelemetry-style correlation for traces/metrics/logs across Biella execution identity while keeping telemetry non-authoritative.

For NVIDIA runtime profiles, expose GPU/resource measurements using DCGM-compatible metrics or equivalent current tooling.

Fault tests include:

```text
controller restart
worker kill
GPU process crash
model server restart
database restart
cache deletion
workspace deletion
network loss
machine loss
```

Exit gate:

- Run/Node/ModelCall/ToolCall correlation is observable;
- machine/process loss is recoverable from durable state;
- telemetry loss does not destroy execution truth.

### Phase 7 — High-end fully local single-node profile

Initial recommended profile:

```text
Linux
NVIDIA driver
NVIDIA Container Toolkit
Docker/Compose + systemd
Biella controller
PostgreSQL + pgvector implementation
content-addressed storage
local NVMe working storage
durable secondary replica
vLLM
llama.cpp fallback
optional TensorRT-LLM
OpenTelemetry
Prometheus/Grafana implementation
DCGM exporter or equivalent NVIDIA metrics
```

Do not make these products kernel dependencies.

Offline qualification:

```text
DISCONNECT INTERNET
→ Biella boots
→ local models load
→ Tasks execute
→ retrieval works
→ memory/state works
→ tools execute
→ Artifacts persist
→ restart/recovery works
```

Changing from one GPU to N GPUs must not require kernel changes.

### Phase 8 — Optional multi-node scale profile

Only after single-node correctness/durability is proven:

- multi-node ResourceSnapshots;
- resource placement across nodes;
- Ray/multiprocessing/other distributed runtime adapter where required;
- replicated/shared durable content;
- node-loss recovery tests.

Kubernetes, GPU Operator and Triton are optional deployment choices rather than kernel requirements.

## 7. Current external research applied

Current official/project documentation supports this adapter-first direction:

- vLLM exposes OpenAI-compatible completions, chat, Responses and embeddings endpoints and supports tensor/pipeline parallel serving. Current docs describe native multiprocessing for single-node and Ray as a common/default multi-node runtime.
- llama.cpp exposes an OpenAI-compatible local HTTP server, embeddings, reranking, continuous batching and broad local hardware support.
- TensorRT-LLM exposes `trtllm-serve`, an OpenAI-compatible NVIDIA-optimized serving path with tensor/pipeline/expert parallel options.
- Triton supports vLLM and TensorRT-LLM backends, making it useful as an optional unified serving layer rather than a universal kernel dependency.
- NVIDIA Container Toolkit provides GPU access for Docker/containerd/Podman environments.
- OpenTelemetry provides vendor-neutral traces, metrics, logs and baggage for observability correlation.
- pgvector supports exact nearest-neighbor search plus HNSW and IVFFlat approximate indexes, making PostgreSQL + pgvector a reasonable first local retrieval implementation without making it a kernel requirement.

## 8. Explicit non-goals / non-permanent structure

Do not permanently define Biella around:

```text
one provider
one model family
one inference server
one NVIDIA GPU generation
one GPU count
one cloud/VPS
Kubernetes
Ray
TensorRT/Triton
PostgreSQL in the kernel
one vector database
one fixed agent hierarchy
one critic/validator pipeline
one retry count
internet-required startup
cache as authority
workspace as durable state
```

## 9. Build discipline

For every numbered implementation unit:

```text
inspect current durable Git state
→ read exact active contract
→ create focused failing test
→ implement minimum change
→ run focused tests
→ run affected regressions
→ inspect artifacts/state
→ commit
→ push
→ read back remote commit/tree
→ update Drive living state
→ stop before next numbered prompt
```

This sequence is part of the build structure, not optional process ceremony: it prevents accepted source and state from being lost with an execution machine.

## 10. Acceptance of this design

This design is accepted when:

1. the repository structure preserves kernel/adapters/runtime/deploy boundaries;
2. durable contracts are defined before concrete local model servers become architectural assumptions;
3. local inference implementations can be replaced without changing Task/Capability semantics;
4. a single high-end local node can operate with internet disconnected;
5. machine loss cannot destroy accepted source, Run truth, Artifacts or Knowledge;
6. later multi-node scaling requires deployment/runtime additions rather than kernel rewrites.
