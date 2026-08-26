# Biella Engine — Durable Project Context Snapshot

Date: 2026-08-26
Status: CURRENT DURABLE CONTEXT SNAPSHOT

## Purpose

This file closes the gap between the richer Biella project context held in current project documents/conversations and the GitHub repository. It is a compact durable source for future Codex/ChatGPT sessions.

This file does **not** claim that missing local source code exists remotely. GitHub code/history remains authoritative for code that actually survived; Google Drive remains the live operator/project-document source.

## Authority and product identity

Biella Engine is a project-neutral universal AI production/execution engine.

The project owner is the final authority for product direction, priorities, architecture decisions, infrastructure use, acceptance, and work policy.

Biella is independent from historical MiniTZ assumptions. MiniTZ is historical/migration evidence only and may not become active Biella source, instructions, memory, rules, branding, or retrieval without the clean-room migration path.

## Durable kernel

The intended durable kernel is approximately:

- Project
- Task
- Run
- Capability
- Graph
- Node
- Artifact
- Resource
- Event
- Knowledge

Derived/non-kernel concepts include Agent, Provider, Model, Source, Checkpoint, Validation, Memory, Queue, Worker, Finalization, and Repair.

## Core invariants

- Every Project has an explicit namespace.
- Project-specific source, assets, architecture, requirements, preferences, acceptance, tools, visual identity, gameplay/content, domain knowledge, and publish destinations do not silently become universal behavior.
- Task states what a Project wants, not a provider/model/GPU/worker/hierarchy/fixed pipeline.
- Graph states one Run plan and is immutable per revision; replanning creates revision N+1.
- Node is productive work; independent Nodes may execute concurrently when dependencies/resources permit.
- Run/worker attempts use leases and fencing; a stale executor cannot finalize after a newer fence exists.
- Artifact != Content Object != Storage Location.
- Exact content identity uses cryptographic digests.
- Hardware is runtime state; missing hardware changes routing/concurrency/latency, not Capability identity.
- Routing follows Capability → compatible implementation → model/tool/runtime → Resource.
- Hard constraints are evaluated before learned ranking.
- Cache is rebuildable optimization only and is never authority.
- Validation is Task-derived rather than a permanent global reviewer/critic hierarchy.

## Memory scopes

- ENGINE MEMORY
- PROJECT MEMORY
- RUN MEMORY
- HISTORICAL EVIDENCE
- CACHE

Promotion path:

RUN OUTPUT → candidate observation → scope classification → evidence → dedup/contradiction → versioned knowledge candidate → ENGINE / PROJECT / HISTORICAL placement.

Direct Run/agent writes to Engine Knowledge are forbidden.

## Migration firewall

Historical source may enter only through:

READ → UNDERSTAND → EXTRACT SEMANTICS → CLASSIFY → REMOVE CONTAMINATION → REWRITE FROM SCRATCH → STORE AS BIELLA-NATIVE

Canonical classification values:

- UNIVERSAL_GOOD
- UNIVERSAL_REWRITE
- PROJECT_SPECIFIC
- HISTORICAL_EVIDENCE
- DUPLICATE
- OBSOLETE_OR_DRIFT

Firewall path:

RAW HISTORICAL → QUARANTINE → EXTRACTION → CLASSIFICATION → NORMALIZATION → CLEAN REIMPLEMENTATION → BIELLA-NATIVE

Mechanical MiniTZ→Biella renaming is forbidden.

## Current durable source reality

Repository: `patrickminitz-web/biella-engine`

Default branch: `main`

The current GitHub history contains website/document work, source-lineage reconciliation, Superpowers design/plan documents, and this durable context sync.

A previously observed local P0-01 implementation existed on the terminated Spot VPS at:

- commit `b7cc3db0a9feb34d72764261d32163d2b05ac123`
- tree `ec44bacc13e11f9c38c1b5ac7c3844ac74f24a11`

Those exact objects are not resolvable in the connected GitHub history. The Spot instance and its local filesystem were lost. Therefore this local P0-01 evidence is historical/non-durable evidence, not current GitHub code authority.

P0-02 has not been executed.

Current implementation boundary: **durable source reconciliation / P0-01 re-establishment before P0-02**.

Do not claim P0-01 current/accepted merely from old chat reports or old Drive status text. Re-establish the implementation from durable GitHub truth and the exact P0-01 contract, then push and remotely verify the resulting commit/tree.

## Lost Spot runtime

Terminated instance:

- instance `i-0c985a61d3ab2b42e`
- region `eu-west-3`
- Spot request `sir-fyf7gd2p`
- termination time `2026-08-26 07:19:10 GMT`
- reason `Server.SpotInstanceTermination`
- Spot status `instance-terminated-no-capacity`
- interruption behavior `terminate`

No surviving EBS volume or self-owned snapshot was found during recovery checks.

The following former paths are unavailable and must not be treated as current runtime state:

- `/home/ubuntu/biella-work/biella-engine`
- `/home/ubuntu/biella-work/biella-drive`
- `/home/ubuntu/biella-work/cloudflare-lab`
- `/home/ubuntu/biella-migration`

Future canonical workspaces must be recoverable from durable Git and durable state/storage. Ephemeral/Spot compute must never be the only copy of accepted source/state.

## Google Drive live project root

Root folder ID: `1Z6_qwN9hfHIheXZ_9pYCG8dRDMuRN-l7`

Current logical structure:

```text
BiellaEngine/
├── 00_START_HERE/
├── 10_ARCHITECTURE/
├── 20_CURRENT_STATE/
├── 30_EXECUTION/
├── 40_PROMPTS/
│   ├── P0/
│   ├── P1/
│   ├── P2/
│   ├── P3/
│   └── P4/
└── 50_MIGRATION/
```

No archive/reference/handbook layer belongs in the newborn live Biella source tree.

Prompt program counts:

- P0 = 10
- P1 = 9
- P2 = 12
- P3 = 14
- P4 = 6
- total = 51

## 51-prompt program

### P0 — Clean Kernel + Migration Firewall

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

### P1 — Durable Cognition + Resources + Scheduler + Routing

11. Content-Addressed Object Store
12. Run Memory
13. Project Memory
14. Engine Knowledge / Promotion Boundary
15. Model / Tool Call Ledger
16. Checkpoint & Resume
17. Dynamic Resource Inventory
18. Concurrent Resource-Aware Scheduler
19. Routing

### P2 — Universal Execution Fabric

20. Filesystem Adapter
21. Shell / Managed Process Adapter
22. Git Adapter
23. Isolated Runtime
24. HTTP/API Adapter
25. Model Provider Adapter
26. Browser Adapter
27. PostgreSQL Adapter
28. Replaceable Durable Object Storage
29. Context & Retrieval
30. Workspace / Sandbox
31. Task-Derived Validation & Evaluation

### P3 — Production Capability Packs

32. Software Production
33. Web Production
34. Game Production
35. Large-Scale / AAA Production
36. 3D Production
37. Character / Rigging
38. Animation
39. Environment
40. Rendering
41. VFX / Simulation
42. Image
43. Audio
44. Video
45. Packaging / Publishing

### P4 — Evidence-Based Learning + Qualification

46. Controlled Model Comparison
47. Strategy / Skill / Prompt / Tool Comparison
48. Evidence-Based Routing Learning
49. Cache / Locality / Residency / Placement Learning
50. Failure Pattern / Repair Learning
51. Production Recipe Learning + Full P0–P4 Qualification

## Build-phase structure

Current accepted build strategy is **contract-first + runtime profiles**.

Major repository boundaries to establish as implementation resumes:

```text
contracts/      stable versioned semantic envelopes/interfaces
src/kernel/     universal durable semantics
src/services/   scheduler/router/context/memory/recovery/validation
src/adapters/   replaceable model/storage/compute/tool implementations
src/runtime/    measured resource/model/worker runtime state
src/observability/
deploy/         dev/local-single-node/local-multi-node profiles
tests/          contract/unit/integration/fault/acceptance/performance/offline
tools/          bootstrap/verify/backup/benchmark
```

Model/provider/GPU/runtime/database/cluster choices are not permanent kernel primitives.

## Fully local target

The finished engine must be able to operate fully locally on high-end hardware with internet disconnected at runtime.

Recommended first deployment profile may use, without making them kernel requirements:

- Linux
- NVIDIA driver
- NVIDIA Container Toolkit
- Docker/Compose + systemd
- vLLM as first high-throughput local ModelProvider implementation
- llama.cpp as lightweight/fallback local implementation
- optional TensorRT-LLM for measured NVIDIA optimization
- optional Triton later for unified multi-model serving
- PostgreSQL + pgvector as an initial local durable/retrieval implementation
- content-addressed Artifact storage with durable replica
- local NVMe working/cache storage
- OpenTelemetry-style correlation
- Prometheus/Grafana implementation
- DCGM-compatible NVIDIA metrics

Offline qualification target:

DISCONNECT INTERNET → Biella boots → local models load → Tasks execute → retrieval works → memory/state works → tools execute → Artifacts persist → restart/recovery works.

## Current Cloudflare experiment evidence

A separate Cloudflare Worker experiment validated an isolated `/ai/chat` route using Workers AI model `@cf/meta/llama-3.2-3b-instruct` with real HTTP checks. This is external experiment evidence only and is not an implemented Biella kernel adapter.

Cloudflare/provider-specific behavior remains replaceable and must not enter the kernel.

## Build discipline

Every numbered implementation unit uses:

inspect current durable Git state
→ read exact active contract
→ focused failing test
→ minimum task-scoped implementation
→ focused tests
→ affected regressions
→ inspect outputs/state
→ commit
→ push GitHub
→ remote readback of commit/tree
→ update Drive living state
→ stop before next numbered prompt

A prompt/example/plan/copied agent report is not implementation evidence.

## Current next boundary

1. Keep current GitHub documentation/context durable.
2. Create the next persistent non-Spot/on-demand or fully local build environment from GitHub.
3. Re-establish P0-01 from the exact Drive prompt/spec against current GitHub source.
4. Test it from real source.
5. Push it.
6. Read back exact remote commit/tree.
7. Update Drive implementation status only after remote verification.
8. Keep P0-02 NOT_STARTED until P0-01 is durably re-established and accepted.
