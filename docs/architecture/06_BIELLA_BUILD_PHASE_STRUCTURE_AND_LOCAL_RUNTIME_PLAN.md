# Biella Engine — Build Phase Structure and Fully Local Runtime Plan

Status: ACTIVE BUILD-PHASE ARCHITECTURE
Date: 2026-08-26

## Purpose

Define the structure Biella should establish during the build phase so the finished engine can operate fully locally on high-end hardware while remaining provider-neutral, hardware-neutral, and recoverable from machine loss.

## Immediate source-truth reset

Current durable evidence is inconsistent. The lost Spot VPS previously held a local P0-01-labelled commit `b7cc3db0a9feb34d72764261d32163d2b05ac123`, but current GitHub cannot resolve that SHA. Therefore the lost VPS commit cannot be treated as durable canonical source until independently recovered into GitHub.

Durability rule:

```text
LOCAL WORK
→ test
→ commit
→ push GitHub
→ read back remote commit/tree
→ only then mark accepted/durable in Drive
```

No accepted Biella implementation may exist only on a VPS, workstation, model session, browser session, temporary disk, or cache.

## Build strategy

Use contract-first + runtime profiles.

- Define stable semantic contracts before choosing inference engines or cluster systems.
- Keep the durable kernel narrow.
- Treat model servers, databases, GPU runtimes, container systems, telemetry backends and cluster managers as replaceable implementations or deployment profiles.
- Qualify one high-end fully local single-node profile before adding multi-node complexity.

## Repository structure

```text
biella-engine/
├── AGENTS.md
├── CURRENT_TASK.md
├── README.md
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
├── src/
│   ├── kernel/
│   ├── services/
│   ├── adapters/
│   ├── runtime/
│   └── observability/
├── deploy/
│   ├── dev/
│   ├── local-single-node/
│   └── local-multi-node/
├── tests/
│   ├── contract/
│   ├── unit/
│   ├── integration/
│   ├── fault/
│   ├── acceptance/
│   ├── performance/
│   └── offline/
├── tools/
│   ├── bootstrap/
│   ├── verify/
│   ├── backup/
│   └── benchmark/
└── docs/
    ├── architecture/
    ├── decisions/
    ├── operations/
    ├── project-state/
    ├── biellawebsite/
    └── superpowers/
```

Boundary meanings:

- contracts = stable versioned semantic envelopes/interfaces;
- kernel = universal durable semantics only;
- services = scheduling/routing/context/memory/recovery/validation behavior around kernel objects;
- adapters = replaceable external implementations;
- runtime = measured execution machinery and runtime registries;
- deploy = machine/cluster-specific profiles;
- website/document product work is non-kernel.

## Contracts to define during the build phase

### ExecutionIdentity

`project_id`, `task_id`, `task_revision`, `run_id`, `graph_id`, `graph_revision`, `node_id`, `attempt`, `fence`, `executor_id`.

### ModelProvider

Operations: `health`, `list_models`, `resolve_model`, `infer`, `stream`, `cancel`.

Normalize exact provider/runtime/model identity, revision/digests, modalities/context/capabilities, token/cache metrics where available, latency, status, and failure class. Provider-specific fields remain adapter-local.

### ModelDescriptor

`model_id`, `family`, `revision`, `weight_digest`, `tokenizer_digest`, `config_digest`, `runtime`, `runtime_version`, `quantization`, `modalities`, `context_limit`, `required_ram`, `required_vram`, `local_path`, `compatibility`, `observed_benchmarks`.

### ResourceSnapshot

Keep configured capacity separate from measured/effective CPU, RAM, GPU/VRAM, NVMe, network, loaded models/toolchains, warm caches, Artifact/workspace locality, allocations, queue pressure, health, cost where known, and observation freshness.

### Artifact identity

`Artifact != ContentRef != StorageLocation`.

### WorkerProtocol

`register`, `heartbeat`, `advertise_capabilities`, `publish_resource_snapshot`, `lease`, `start`, `progress`, `checkpoint`, `cancel`, `finish`, `fail`.

### Context

Use versioned `ContextManifest`, `ContextArtifact`, and `ContextReceipt` with source revision/digest, chunk identity, index version, embedding runtime, score, and reranker identity where used.

### TelemetryCorrelation

`Project → Task → Run → Graph → Node → ModelCall / ToolCall`.

Telemetry is evidence/observability, never execution authority.

### RuntimeProfile

Represent host/runtime identity, resources, container runtime, model/storage implementations, network topology, observability endpoints, and offline capability as configuration/state rather than kernel branches.

### DurabilityContract

```text
accepted source   → remotely verified Git commit/tree
durable metadata → durable database + backup
Artifacts        → CAS + durable replica
model weights    → exact digest + durable local store
workspace/cache/worker → disposable
```

## Build phases

### Phase 0 — Source truth and durability reset

Inventory GitHub, reconcile stale Drive records, mark the terminated Spot VPS unavailable, re-establish canonical engine baseline from durable GitHub evidence, and enforce remote readback after every accepted commit.

### Phase 1 — Versioned contract spine

Create language-neutral contract schemas for execution identity, ModelProvider/ModelDescriptor, ResourceSnapshot, WorkerProtocol, Context, telemetry correlation and RuntimeProfile. Use JSON Schema/OpenAPI initially where appropriate.

### Phase 2 — P0 durable kernel

Migration firewall, Project isolation, Capability, Task, Run/fencing, Artifact/source identity, Graph/Node, Event ledger, durable execution state, P0 qualification.

### Phase 3 — P1 durability/cognition/resources/routing

CAS, Run Memory, Project Memory, Engine Knowledge promotion, model/tool call ledger, checkpoint/resume, ResourceSnapshot, concurrent scheduler, routing.

### Phase 4 — Local model providers

```text
ModelProvider
├── local-vllm
├── local-llamacpp
├── local-trtllm optional
└── hosted-* optional
```

vLLM is the recommended first high-throughput GPU implementation. llama.cpp is the recommended lightweight/fallback implementation. TensorRT-LLM is optional for measured NVIDIA optimization. Triton is optional later for unified multi-model serving and is not a kernel requirement.

### Phase 5 — P2 execution fabric

Filesystem, shell/process, Git, isolated/container runtime, HTTP/API, model provider, browser, PostgreSQL, durable object storage, context/retrieval, workspace/sandbox, Task-derived validation/evaluation.

### Phase 6 — Observability and recovery qualification

Use OpenTelemetry-style correlation while keeping Biella Events authoritative. For NVIDIA profiles, expose GPU/VRAM/utilization/health through DCGM-compatible metrics or current equivalent.

Fault matrix: controller restart, worker kill, GPU process crash, model server restart, database restart, cache deletion, workspace deletion, network loss, machine loss.

### Phase 7 — High-end fully local single-node profile

Possible implementation profile:

Linux; NVIDIA driver; NVIDIA Container Toolkit; Docker/Compose + systemd; Biella controller; PostgreSQL + pgvector implementation; content-addressed storage; local NVMe working storage; durable secondary replica; vLLM; llama.cpp fallback; optional TensorRT-LLM; OpenTelemetry; Prometheus/Grafana; DCGM-compatible GPU metrics.

Offline acceptance:

DISCONNECT INTERNET → Biella boots → local models load → Tasks execute → retrieval works → memory/state works → tools execute → Artifacts persist → restart/recovery works.

### Phase 8 — Optional multi-node scale

Only after single-node correctness/durability. Add multi-node ResourceSnapshots, placement, optional distributed runtime adapters, durable replicated/shared content, and node-loss recovery. Kubernetes/GPU Operator/Triton remain optional deployment choices.

## Explicit non-permanent structure

Do not permanently define Biella around one provider, one model family, one inference server, one GPU generation/count, one cloud/VPS, Kubernetes, Ray, TensorRT/Triton, PostgreSQL in the kernel, one vector database, a fixed agent hierarchy, fixed critic/validator pipeline, fixed retry count, internet-required startup, cache as authority, or workspace as durable state.

## Build discipline

For every numbered implementation unit:

inspect current durable Git state → read exact active contract → focused failing test → minimum implementation → focused tests → affected regressions → inspect outputs/state → commit → push → read back remote commit/tree → update Drive living state → stop before next prompt.
