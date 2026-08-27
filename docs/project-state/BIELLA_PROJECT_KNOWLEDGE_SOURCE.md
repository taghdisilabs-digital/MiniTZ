# 01 — BIELLA PROJECT KNOWLEDGE SOURCE

```yaml
schema: biella.project_knowledge_source/v2
version: 2026-08-27
mode: stable_reference
scope:
  - durable_architecture
  - memory_model
  - capability_model
  - migration_semantics
  - creation_intelligence
  - engine_project_boundaries
excludes:
  - current_commit
  - current_tree
  - current_ip
  - current_host_state
  - current_task
  - current_prompt_status
  - installed_tool_inventory
  - provider_availability
```

## 1. PURPOSE

This file defines stable Biella concepts that should survive changes in:
- repository revision;
- workstation;
- cloud;
- GPU/CPU topology;
- model/provider;
- project;
- runtime implementation;
- historical migration state.

Use it only when the active task requires architectural or semantic context.

Do not use this file as a current-state record, execution checklist, prompt body, or historical archive.

---

## 2. BIELLA CORE MODEL

Biella is a project-neutral durable execution and production engine.

It is not MiniTZ v2.

Permanent kernel concepts remain approximately:

```text
Project
Task
Run
Capability
Graph
Node
Artifact
Resource
Event
Knowledge
```

Stable execution relation:

```text
Project
→ Task
→ Run
→ Graph
→ Node
→ Capability
→ compatible implementation
→ Resource
→ Artifact / Event / scoped Knowledge
```

Add permanent kernel primitives only when a concept is universal across materially different projects and execution environments.

---

## 3. PROJECT

A Project is the isolation boundary for project-specific truth.

A Project may own:

```yaml
project_scope:
  - requirements
  - product_direction
  - assets
  - source
  - brand
  - visual_canon
  - content_canon
  - project_memory
  - project_specific_rules
  - acceptance_criteria
  - outputs
```

Project facts must never silently become Engine defaults.

A Project may use universal Engine capabilities without transferring its identity into the Engine.

---

## 4. TASK

A Task is a typed, durable, revisioned objective.

Conceptual fields may include:

```yaml
task:
  task_id: durable_identity
  project_namespace: isolation_boundary
  objective: desired_outcome
  input_refs: typed_sources_or_artifacts
  required_capabilities: semantic_requirements
  output_contract: required_result_shape
  constraints: task_constraints
  side_effect_class: execution_effect_level
  source_snapshot: exact_input_revisions_when_required
  data_policy: locality_confidentiality_egress
  resource_requirements: semantic_compute_requirements
  quality_budget: required_quality
  latency_budget: execution_timing
  cost_budget: optional_economic_limit
  evidence_requirements: completion_proof
  checkpoint_policy: continuation_requirements
  dependencies: graph_prerequisites
  routing_hints: non_authoritative_preferences
  idempotency_key: duplicate_execution_protection
```

A Task describes what must be achieved.

It does not hardcode:
- worker identity;
- provider;
- GPU model;
- cloud;
- machine path;
- permanent agent hierarchy.

---

## 5. RUN

A Run is exact execution lineage for a Task revision.

A durable Run must support:
- attempts;
- current ownership;
- leases/fencing;
- checkpoints;
- failures;
- resumption;
- stale-attempt rejection;
- finalization evidence.

A stale executor must not be able to finalize a newer Run.

Conversation context, a process, GPU memory, browser state, or temporary workspace must never be the only record of meaningful Run progress.

---

## 6. GRAPH AND NODE

A Graph is an immutable revisioned execution plan.

Replanning creates a new Graph revision.

Productive Node families may include:

```text
MODEL_CALL
SPECIALIST_TASK
TOOL_CALL
SHELL_EXECUTE
SANDBOX_EXECUTE
BROWSER_EXECUTE
COMPUTER_EXECUTE
BUILD
TEST
RENDER
ASSET_PROCESS
MEDIA_PROCESS
PACKAGE
TRANSFER
VALIDATE
EVALUATE
```

Lifecycle/control concerns such as:

```text
WAITING
CHECKPOINTING
CANCELLATION
RECOVERY
STALE_RESULT_HANDLING
FINALIZATION
```

are primarily durable execution-control semantics, not mandatory productive pipeline stages.

Independent Nodes may run concurrently when:
- dependencies permit;
- side effects do not conflict;
- Resource contention is acceptable.

Biella must not encode universal serial execution.

---

## 7. CAPABILITY MODEL

A Capability is a semantic ability independent of its implementation.

Examples:

```text
software.inspect
software.engineer
software.debug
software.test
web.build
browser.automate
game.build
game.run
3d.model
3d.rig
3d.animate
render.sequence
render.raytrace
image.generate
image.edit
audio.mix
video.transcode
model.infer
retrieval.embed
retrieval.rerank
research.execute
validation.runtime
evaluation.compare
```

Capability identifiers should be extensible registry data, not a closed giant kernel enum.

Implementations advertise which Capabilities they can execute.

---

## 8. IMPLEMENTATION / PROVIDER SEPARATION

Provider, model, tool, runtime, cloud and hardware are implementation or Resource concerns.

Examples of replaceable implementation classes:

```text
model provider
local model runtime
browser runtime
database adapter
container runtime
filesystem adapter
Git adapter
HTTP/API adapter
game engine adapter
3D/DCC adapter
renderer
media processor
cloud compute provider
object storage backend
```

No external platform owns Biella architecture.

Provider-specific optimizations may affect routing and performance but must not redefine:
- Project;
- Task;
- Run;
- Capability;
- Graph;
- Artifact;
- Knowledge.

---

## 9. RESOURCE MODEL

Hardware is runtime state, not software policy.

A Resource may expose observed/configured dimensions such as:

```yaml
resource:
  compute:
    - cpu
    - ram
    - gpu
    - vram
  io:
    - storage
    - network
  locality:
    - loaded_models
    - warm_prompt_or_kv_state
    - loaded_toolchains
    - artifact_locality
    - workspace_locality
  runtime:
    - queue_pressure
    - health
    - availability
    - cost
```

Resource-fit semantics may include:

```text
FIT
FIT_REDUCED
REQUIRES_OTHER_RESOURCE
TEMP_UNAVAILABLE
UNKNOWN
```

A Capability must not disappear because one current Resource cannot execute it.

Routing chooses a compatible implementation + Resource dynamically.

---

## 10. ARTIFACT / CONTENT IDENTITY

Keep distinct:

```text
Artifact
ContentRef
StorageLocation
```

Meaning:

```yaml
Artifact:
  role: logical_project_or_run_output

ContentRef:
  role: immutable_content_identity

StorageLocation:
  role: physical_replica_or_location
```

Exact bytes require cryptographic identity.

A logical Artifact can remain the same while storage replicas change.

Content-addressing enables:
- deduplication;
- exact provenance;
- safe transfer;
- checkpoint reuse;
- migration identity;
- reproducible evidence.

---

## 11. EVENT MODEL

Meaningful execution changes should be representable as durable Events.

Examples:

```text
TASK_CREATED
GRAPH_COMPILED
NODE_READY
NODE_STARTED
MODEL_CALLED
TOOL_CALLED
ARTIFACT_CREATED
DECISION_RECORDED
CHECKPOINT_CREATED
NODE_FINISHED
FAILURE_RECORDED
RUN_RESUMED
RUN_COMPLETED
```

Events are evidence of state transitions.

They are not a replacement for typed current state; together they allow reconstruction and diagnosis.

---

## 12. MEMORY MODEL

Memory scopes remain strictly separate:

```text
ENGINE_MEMORY
PROJECT_MEMORY
RUN_MEMORY
HISTORICAL_EVIDENCE
CACHE
```

### ENGINE_MEMORY

Contains only evaluated, reusable, project-neutral knowledge.

Examples:
- general execution techniques;
- reusable algorithms;
- validated routing lessons;
- reusable production recipes;
- general failure/repair patterns.

### PROJECT_MEMORY

Contains one Project's:
- requirements;
- decisions;
- assets;
- brand;
- visual/content canon;
- accepted project-specific facts;
- project-specific preferences.

### RUN_MEMORY

Contains exact execution state:
- Task revision;
- Graph revision;
- Node state;
- input/source revisions;
- artifacts;
- runtime/model/tool identity;
- checkpoints;
- failures;
- pending dependencies;
- continuation state.

### HISTORICAL_EVIDENCE

Contains:
- raw historical material;
- old outputs;
- rejected candidates;
- old project rules;
- old source packages;
- provenance.

Historical Evidence is never automatically instruction-active.

### CACHE

Contains rebuildable acceleration:
- embeddings;
- parsed documents;
- model/prompt/KV cache metadata;
- build cache;
- shader cache;
- render cache;
- thumbnails;
- local replicas.

Cache loss may cost time but cannot erase authoritative knowledge or Run state.

---

## 13. KNOWLEDGE PROMOTION

Run output must not write directly into Engine Memory.

Stable promotion flow:

```text
RUN OUTPUT
→ candidate observation
→ scope classification
→ evidence association
→ deduplication / contradiction handling
→ versioned knowledge candidate
→ ENGINE / PROJECT / HISTORICAL placement
```

A Knowledge record should be able to represent:

```yaml
knowledge:
  knowledge_id: durable_identity
  scope: ENGINE|PROJECT|HISTORICAL
  type: semantic_kind
  statement: normalized_claim_or_recipe
  applicability: conditions
  source_runs: evidence_lineage
  source_objects: content_lineage
  evidence: supporting_refs
  status: candidate|accepted|superseded|rejected
  supersedes: prior_knowledge_ref|null
```

Knowledge is versioned and supersedable.

Do not create giant mutable rule documents as the sole durable knowledge mechanism.

---

## 14. CLEAN-ROOM MIGRATION MODEL

Historical material enters Biella only through:

```text
RAW HISTORICAL SOURCE
→ IMMUTABLE QUARANTINE + PROVENANCE
→ SEMANTIC EXTRACTION
→ MIGRATION CLASSIFICATION
→ CONTAMINATION REMOVAL
→ NORMALIZATION
→ BIELLA-NATIVE CANDIDATE
→ TASK-SPECIFIC VERIFICATION
→ EXPLICIT DESTINATION
```

Raw historical bytes remain Historical Evidence.

They do not directly enter:
- Engine source;
- normal retrieval;
- Engine Memory;
- active Project Memory;
- executor/agent instructions.

---

## 15. MIGRATION CLASSIFICATION

Every historical candidate receives exactly one:

```text
UNIVERSAL_GOOD
UNIVERSAL_REWRITE
PROJECT_SPECIFIC
HISTORICAL_EVIDENCE
DUPLICATE
OBSOLETE_OR_DRIFT
```

Meaning:

```yaml
UNIVERSAL_GOOD:
  action: reusable_semantics_may_become_engine_candidate

UNIVERSAL_REWRITE:
  action: useful_semantics_exist_but_historical_coupling_must_be_removed

PROJECT_SPECIFIC:
  action: preserve_only_inside_correct_project_namespace

HISTORICAL_EVIDENCE:
  action: retain_for_provenance_learning_or_forensics_not_active_execution

DUPLICATE:
  action: link_to_existing_authority_do_not_create_second_active_copy

OBSOLETE_OR_DRIFT:
  action: retain_only_if_historical_value_exists_never_activate
```

Migration classification answers **how the candidate may be admitted**.

It does not describe what semantic content was extracted.

---

## 16. CREATION-INTELLIGENCE CONTENT MODEL

Useful historical production intelligence must survive independently from project contamination.

Supported semantic content kinds:

```text
CAPABILITY_KNOWLEDGE
LOGIC_PRIMITIVE
GENERATION_INSTRUCTION
PRODUCTION_RECIPE
PROJECT_BRAND_KNOWLEDGE
PROJECT_VISUAL_CANON
PROJECT_CONTENT_CANON
PROJECT_ASSET_REFERENCE
HISTORICAL_EVIDENCE
```

### CAPABILITY_KNOWLEDGE

Describes a reusable semantic ability.

Example:

```text
3d.retarget_animation
software.profile_runtime
render.sequence
```

### LOGIC_PRIMITIVE

A compact reusable decision/execution relation.

Examples:

```text
verified unchanged input + valid existing output -> reuse output
worker loss -> recover smallest affected boundary
insufficient resource -> route capability to compatible resource
project-specific candidate -> prohibit Engine promotion
```

Logic primitives are semantic relations, not provider token counts.

### GENERATION_INSTRUCTION

An instruction pattern that reliably produces or transforms an artifact.

Examples:
- modeling technique;
- image-generation/editing instruction;
- animation procedure;
- software implementation procedure;
- material/texture procedure;
- render setup;
- build/package procedure.

### PRODUCTION_RECIPE

A reusable multi-step creation workflow with explicit inputs, operations, outputs and validation.

A recipe is not a mandatory global pipeline.

### PROJECT_BRAND_KNOWLEDGE

Project-only:
- naming;
- voice;
- brand identity;
- positioning;
- terminology;
- prohibited motifs.

### PROJECT_VISUAL_CANON

Project-only accepted visual truth:
- palette roles;
- form/silhouette language;
- typography;
- materials;
- lighting;
- composition;
- UI density;
- iconography;
- motion;
- accepted/rejected references.

### PROJECT_CONTENT_CANON

Project-only content/story/product truth.

### PROJECT_ASSET_REFERENCE

Project-only references to approved or candidate assets, with content identity/provenance.

---

## 17. CONTENT_KIND != MIGRATION_CLASSIFICATION

These are independent axes.

Example:

```yaml
content_kind: LOGIC_PRIMITIVE
migration_classification: UNIVERSAL_REWRITE
destination_scope: ENGINE_CANDIDATE
```

Example:

```yaml
content_kind: PROJECT_VISUAL_CANON
migration_classification: PROJECT_SPECIFIC
destination_scope: PROJECT
```

Example:

```yaml
content_kind: GENERATION_INSTRUCTION
migration_classification: OBSOLETE_OR_DRIFT
destination_scope: HISTORICAL
```

This prevents useful technical knowledge from being discarded merely because its source contained historical contamination.

---

## 18. CONTAMINATION REMOVAL

Remove or neutralize historical coupling such as:

```text
MiniTZ brand as universal identity
fixed agent hierarchy
fixed critic/validator/repair chain
fixed provider/model
fixed GPU/machine
fixed paths
old Drive IDs
old host identities
global serial-worker assumptions
readiness ceremonies
arbitrary repair counts
project-specific visuals as Engine defaults
mechanical renaming
unverified success claims
```

Preserve underlying reusable semantics when they remain valid after coupling is removed.

Do not call a candidate clean merely because names changed.

---

## 19. PROJECT CREATION COMPOSITION

Biella creation should compose universal intelligence with current Project truth:

```text
CAPABILITY
+ LOGIC_PRIMITIVE
+ GENERATION_INSTRUCTION
+ PRODUCTION_RECIPE
+ PROJECT_OBJECTIVE
+ PROJECT_REQUIREMENTS
+ PROJECT_BRAND_KNOWLEDGE
+ PROJECT_VISUAL_CANON
+ PROJECT_CONTENT_CANON
+ APPROVED_PROJECT_ASSETS
+ CURRENT_RESOURCE_STATE
→ PROJECT-SPECIFIC GRAPH
→ REAL EDITABLE / USABLE OUTPUT
→ TASK-REQUIRED VALIDATION
→ PROJECT ARTIFACTS / MEMORY
```

This is the central separation:

```text
ENGINE learns HOW to create.
PROJECT defines WHAT this product is.
RESOURCE determines WHERE/HOW it runs now.
```

A Project's aesthetic or identity must never become Biella's universal aesthetic.

---

## 20. PRODUCTION CAPABILITY DOMAINS

Production domains should primarily enter through capability registrations, adapters and production packs.

Examples:

```text
software.*
web.*
browser.*
computer.*
game.*
3d.*
character.*
animation.*
environment.*
render.*
vfx.*
image.*
audio.*
video.*
media.*
data.*
artifact.*
build.*
package.*
model.*
retrieval.*
reasoning.*
research.*
validation.*
evaluation.*
repair.*
training.*
runtime.*
resource.*
```

These namespaces may evolve without changing kernel identity.

Domain packs reuse the same:
- Project isolation;
- Task/Run identity;
- Graph execution;
- Resource routing;
- Artifact identity;
- Memory boundaries;
- Event/evidence model.

A production pack must not introduce a second universal Engine.

---

## 21. AGENT / SPECIALIST MODEL

Do not create permanent organizational hierarchy.

An executable specialist may be dynamically constructed from:

```yaml
specialist:
  objective: bounded_goal
  capabilities: required_semantic_abilities
  context: project_and_run_context
  tools: allowed_implementations
  model_runtime: selected_execution_backend
  resource_allocation: selected_runtime_resources
  output_contract: required_result
```

Possible execution patterns:
- direct generalist;
- specialist-as-tool;
- handoff;
- parallel researchers;
- coding specialist;
- visual specialist;
- deterministic tool runner.

These are runtime patterns, not durable authority roles.

---

## 22. VALIDATION MODEL

Validation is derived from:

```text
output_contract
+ risk
+ side_effects
+ Project acceptance
+ evidence requirements
```

Possible validation classes:
- schema/content validation;
- deterministic tests;
- typecheck/build;
- runtime execution;
- structural asset validation;
- visual comparison;
- performance measurement;
- publication readback;
- optional independent review.

No universal:

```text
maker → critic → validator → repair
```

pipeline exists.

---

## 23. ENGINE VS PROJECT BOUNDARY

### ENGINE OWNS

```yaml
engine:
  - universal kernel contracts
  - execution identity
  - graphs
  - capability registry
  - resource model
  - routing semantics
  - artifact/content identity
  - event/evidence model
  - memory scope mechanisms
  - migration firewall
  - generic adapters
  - evaluated reusable knowledge
```

### PROJECT OWNS

```yaml
project:
  - product direction
  - requirements
  - source/assets
  - brand
  - visual canon
  - content/story canon
  - project-specific workflows
  - project-specific acceptance
  - project outputs
```

### IMPLEMENTATION / PROVIDER OWNS

```yaml
implementation:
  - model backend
  - browser backend
  - compute provider
  - storage backend
  - database
  - renderer
  - game engine
  - DCC
  - media tools
```

No one implementation may redefine Engine semantics.

---

## 24. WEBSITE / PRODUCT-SURFACE BOUNDARY

A website or other product surface is a Project consumer of Biella capabilities.

It may implement Project-local UI, content and adapters needed for that product.

It must not silently create a second universal:
- scheduler;
- memory system;
- routing plane;
- object store;
- model layer;
- browser system;
- validation framework;
- learning system.

If a universal Engine capability does not yet exist, a Project may use a narrow explicitly scoped bridge or simulation without claiming the Engine capability exists.

---

## 25. DURABLE DESIGN TEST

A proposed Biella rule belongs in the Engine only if it remains valid when all of these change:

```text
project
brand
visual style
provider
model
GPU
CPU
cloud
filesystem replica
game engine
renderer
browser
database
worker count
```

If the rule stops being valid when one Project or implementation changes, it belongs in Project scope, adapter/configuration, Resource state, or Historical Evidence—not the universal kernel.
