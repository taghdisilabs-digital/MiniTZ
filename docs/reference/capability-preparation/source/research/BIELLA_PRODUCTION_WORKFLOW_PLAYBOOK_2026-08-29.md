# Biella Capability Preparation — Production Workflow Playbook

**Research date:** 2026-08-29  
**Status:** `PREPARATION_CANDIDATE`  
**Source registry:** `research/SOURCE_REGISTRY_2026-08-29.jsonl`

## 1. Operating purpose

This playbook converts verified external practice into a preparation workflow that Codex can execute without treating external creators as Biella authority.

The preparation worker generates realistic, structured candidates for later review. It does not modify the real Biella Engine, decide Biella Games canon, update milestones, or claim implementation status.

Use Biella-compatible vocabulary:

```text
Project → Task → Run → Graph → Node → Capability
        → compatible Resource / implementation
        → Artifact + Event + scoped Knowledge candidate
```

This vocabulary is a preparation interface. It does not authorize the worker to invent current Biella contracts.

## 2. Universal production loop

Every preparation batch follows this sequence.

### Step 1 — Define one bounded objective

A valid objective names the outcome, constraints, expected artifacts, and validation evidence.

Weak:

```text
Create a game workflow.
```

Useful:

```yaml
objective: >
  Prepare a provider-neutral workflow candidate for importing one glTF environment
  asset, validating topology and material bindings, building a runtime scene, and
  capturing frame and performance evidence.
constraints:
  - do not select a permanent game engine for Biella
  - preserve source asset identity
  - produce failure and recovery paths
expected_artifacts:
  - asset.source
  - asset.import_report
  - scene.runtime_candidate
  - validation.geometry
  - validation.material_bindings
  - validation.performance
status: PREPARATION_CANDIDATE
```

### Step 2 — Resolve source authority

For every external method, record one or more `source_id` values from the verified registry.

Use official documentation for current provider/software behavior. Use community sources for tested workflow patterns, educational concepts, or code-backed experiments.

If no verified source supports a technical claim, either:

- omit the claim;
- write it as an explicit experiment to run;
- record it as `UNRESOLVED_RESEARCH_QUESTION`.

Do not convert inference into production guidance.

### Step 3 — Define an output contract

The worker must know what machine-readable files it will create and how they will be validated.

Example:

```yaml
record_type: task_candidate
schema_version: "1.0.0"
task_id: "task-game-asset-import-0001"
domain: "game"
objective: "Validate one glTF environment asset through an engine-neutral import workflow."
required_capabilities:
  - "asset.inspect"
  - "asset.import"
  - "geometry.validate"
  - "material.validate"
  - "runtime.build"
  - "performance.measure"
expected_artifact_roles:
  - "asset.source"
  - "asset.import_report"
  - "scene.runtime_candidate"
  - "validation.geometry"
  - "validation.material_bindings"
  - "validation.performance"
validation:
  - "all expected artifact roles exist"
  - "source digest is preserved in import provenance"
  - "reported triangle and material counts are non-negative integers"
  - "runtime capture names the build, renderer, device, and driver"
status: "PREPARATION_CANDIDATE"
source_ids:
  - "community.jasper_flick.catlike_coding"
  - "community.baldur_karlsson.renderdoc"
```

### Step 4 — Select model and tools by evaluation

Do not choose a model from reputation alone.

Build a small representative eval before large generation. For structured preparation records, the eval should include:

- valid complex record;
- invalid input;
- ambiguous requirement;
- conflicting evidence;
- failure/recovery case;
- duplicate candidate;
- meaningful variant that must not be merged.

A model/tool configuration is acceptable only when it:

- follows the schema;
- preserves source IDs;
- does not invent Biella state;
- separates observation from inference;
- produces parseable output;
- handles negative cases;
- stays within cost/latency limits set for the batch.

Record the exact model/provider/date and evaluation result. Current model capabilities must be checked against official provider documentation.

### Step 5 — Execute a small batch

The first batch for a new domain should be deliberately small: enough records to expose schema and quality defects, not enough to create cleanup debt.

Recommended first batch:

- 3 capability candidates;
- 3 task candidates;
- 2 graph candidates;
- 2 validator candidates;
- 2 failure/recovery pairs;
- 2 knowledge decision examples.

Increase volume only after parse, duplicate, and usefulness checks pass.

### Step 6 — Validate

Run deterministic checks before qualitative review:

- JSON/JSONL/YAML parses;
- schema validation passes;
- IDs are unique;
- references resolve;
- all records contain `PREPARATION_CANDIDATE`;
- every external claim has a registered source ID;
- no forbidden Biella implementation claims appear;
- no placeholder strings appear;
- no absolute path points into `/root/biella`;
- exact duplicates are rejected;
- manifest file count and digests match.

Then review usefulness:

- Is the task technically meaningful?
- Does it produce evidence?
- Are failure and recovery paths concrete?
- Is the domain-specific behavior preserved?
- Could the main Codex evaluate it without reconstructing missing context?
- Does it avoid choosing Biella product canon?

### Step 7 — Publish preparation evidence

GitHub is the canonical versioned home for structured preparation records. Drive is the matching publication surface for human-readable guides and manifests when requested.

A publication report records:

- repository and branch;
- commit SHA;
- Drive folder and file IDs;
- exact filenames;
- byte sizes;
- SHA-256 digests;
- validation result;
- preparation status.

Publication does not make a candidate accepted Biella material.

## 3. Prompt design standard

A preparation prompt has six sections, in this order.

### 3.1 Role and boundary

State what the worker may do and what it may not claim.

```text
You are a capability-preparation worker. You create PREPARATION_CANDIDATE
records only. You do not access, modify, or describe the current Biella Engine.
```

### 3.2 Objective

Use one outcome statement.

```text
Create a code-backed preparation batch for diagnosing and validating one
real-time shader artifact.
```

### 3.3 Governing sources

List exact registry IDs and explain their roles.

```yaml
sources:
  - source_id: community.acerola.garrett_gunnell
    role: shader experiment and annotated code reference
  - source_id: community.baldur_karlsson.renderdoc
    role: observed frame and pipeline debugging evidence
  - source_id: community.joey_de_vries.learnopengl
    role: low-level rendering pipeline concepts
```

### 3.4 Inputs and constraints

Inputs must be explicit. Constraints should be testable.

```yaml
inputs:
  renderer_api: "Vulkan"
  symptom: "specular highlights disappear when the camera crosses the object origin"
  evidence_available:
    - "frame capture"
    - "vertex shader source"
    - "fragment shader source"
constraints:
  - "do not assume the shader is wrong before inspecting captured state"
  - "do not change artistic intent"
  - "record build, GPU, driver, and capture identity"
```

### 3.5 Output contract

Name schemas, record counts, IDs, and required evidence.

### 3.6 Acceptance and stop boundary

```yaml
acceptance:
  - "all records parse and validate"
  - "diagnosis candidates distinguish observation from hypothesis"
  - "each repair candidate names a validation capture"
stop_after:
  - "batch files, index entries, manifest, and validation report are written"
```

Do not append broad requests such as “improve anything else you notice.”

## 4. Model-selection protocol

Use a task-specific decision record backed only by observed eval output.

A valid model-selection record contains:

| Field | Required content |
|---|---|
| `selection_id` | Stable identity for one decision |
| `task_family` | Exact workload represented by the eval |
| `configuration_id` | Provider, model, reasoning, tool, and context configuration |
| `eval_set_ref` | Digest or repository reference for the exact eval cases |
| `case_count` | Observed number of cases executed |
| `passed` / `failed` | Observed counts |
| `failure_categories` | Categories derived from the failed cases |
| `usage` | Provider-reported or explicitly estimated token/cost fields |
| `latency` | Measured timing and measurement scope |
| `selected_configuration` | Configuration that met the contract |
| `selection_reason` | Comparison grounded in the recorded results |
| `source_ids` | Official capability sources and evaluation-method sources |
| `status` | `PREPARATION_CANDIDATE` |

Do not populate the record until the corresponding eval has run. Do not write fabricated example scores into production datasets.

Selection dimensions:

| Dimension | Required evidence |
|---|---|
| Instruction following | Task-specific pass/fail cases |
| Structured output | Schema validation and semantic checks |
| Coding | Project-specific tests plus code-editing evidence |
| Visual understanding/generation | Reference-specific quality and structural checks |
| Tool use | Exact tool-call outcomes and failure behavior |
| Context | Relevant information retained under the chosen budget |
| Cost | Provider-reported or clearly labeled estimate |
| Latency | Measured request/run timing |
| Cache | Provider-reported cached input/cache write when available |
| Reliability | Repeated representative trials |

## 5. Token and context discipline

### 5.1 Record distinct quantities

When the provider exposes usage, retain each field independently:

- input tokens;
- cached input tokens;
- cache-write tokens;
- reasoning tokens;
- output tokens;
- measurement source for each field;
- provider response or receipt that supplied the value.

A missing field remains unknown. Never derive it from an unrelated dashboard total or from subtraction unless the derivation is explicitly stored as `ADAPTER_DERIVED` with its formula and source values.

### 5.2 Treat cache correctly

Provider cache:

- accelerates repeated matching input;
- can reduce billed/effective fresh input;
- may expire;
- is not exportable durable knowledge;
- does not replace storing exact source, context, output, and provenance.

Biella preparation should preserve the deterministic ingredients of reusable context:

- instruction-set identity;
- source record IDs;
- schema version;
- serialized stable prefix;
- dynamic task suffix;
- tool schema identity;
- model/provider identity;
- full context digest;
- provider cache statistics.

### 5.3 Keep stable content stable

Put invariant instructions, schemas, and tool definitions before frequently changing task content when the provider’s caching model benefits from matching prefixes.

Do not reorder stable records randomly between calls. Do not duplicate the same guide text in every generated record; reference its version and digest.

### 5.4 Reduce context without deleting authority

Remove:

- repeated prose;
- irrelevant history;
- duplicate examples;
- stale output already represented by an exact artifact;
- low-level traces not needed for the current decision.

Keep:

- governing source identities;
- objective and acceptance;
- current task/run state;
- exact relevant failures;
- unresolved conflicts;
- referenced artifact identities;
- constraints that prevent contamination or destructive action.

## 6. Coding workflow

Derived from `community.aider.paul_gauthier`, `community.simon_willison.llm`,
`community.jason_liu.instructor`, and official evaluation sources.

### 6.1 Preparation coding task flow

```text
exact base identity
→ bounded objective
→ focused source retrieval
→ candidate change
→ formatter/linter/type checks
→ focused tests
→ relevant regression tests
→ build or runtime evidence
→ diff inspection
→ candidate result record
```

### 6.2 Required task fields

- repository or fixture identity;
- exact base revision;
- relevant files;
- observed failure or requested behavior;
- prohibited scope expansion;
- expected code and evidence artifacts;
- validation commands;
- failure categories;
- recovery action;
- completion boundary.

### 6.3 Coding anti-patterns

Reject candidates that recommend:

- editing without reading current source;
- changing architecture before diagnosing observed output;
- weakening tests to make a candidate pass;
- treating generated code as correct without execution;
- mixing unrelated cleanup into the change;
- claiming a push/deploy without remote evidence;
- selecting a model solely from a generic leaderboard.

## 7. Visual content workflow

Derived from `official.comfyui`, `community.acly.krita_ai_diffusion`,
`official.invokeai`, `community.cubiq.latent_vision_ipadapter`, and official
provider documentation.

### 7.1 Reproducible visual record

A production visual-workflow candidate is invalid unless it records all applicable observed values:

- record type and workflow ID;
- bounded objective;
- workflow system and exact installed version;
- model identity, digest, and license reference;
- exact input/reference content digests;
- seed, dimensions, sampler, scheduler, steps, and guidance values;
- exact node/plugin names and versions;
- editable source artifact;
- rendered candidate artifact;
- generation metadata artifact;
- validation checks and outcomes;
- source registry IDs;
- `PREPARATION_CANDIDATE` status.

Do not insert instructional filler such as “record exact version later.” Omit publication and report validation failure until the value is observed.

### 7.2 Visual execution loop

```text
source/reference classification
→ version-pinned workflow
→ small candidate set
→ structural and artistic comparison
→ editable correction
→ regenerate or reject major defects
→ retain workflow, metadata, source, and output
```

### 7.3 Visual validators

A visual candidate should be evaluated for the task’s actual contract. Possible checks include:

- dimensions and file integrity;
- alpha/transparency behavior;
- reference continuity;
- perspective and scale;
- topology/structural plausibility;
- repeated/fused artifact detection;
- text legibility;
- material consistency;
- gameplay-distance readability;
- editable source availability;
- license provenance.

Aesthetic preference is not a substitute for technical validity, and technical validity is not a substitute for project art direction.

## 8. Game and graphics workflow

Derived from Catlike Coding, Freya Holmér, Sebastian Lague, Acerola,
Game Programming Patterns, LearnOpenGL, and RenderDoc.

### 8.1 Meaningful generic game preparation

“Generic” means project-noncanonical but technically valuable.

Useful families:

- asset import and validation;
- environment assembly;
- procedural geometry;
- navigation and collision;
- animation state and retargeting;
- shader/material compilation;
- real-time effects;
- gameplay system implementation;
- save/load and state durability;
- deterministic simulation;
- profiling and regression;
- build/package/publish;
- screenshot/frame capture evidence;
- failure recovery.

Do not create disposable “make a platformer” examples unless the record tests a specific reusable capability and produces exact evidence.

### 8.2 Fully specified example

```yaml
record_type: graph_candidate
graph_id: "graph-procedural-mesh-validation-0001"
objective: >
  Generate a manifold grid-derived terrain mesh, build it in a test scene,
  measure runtime cost, and preserve topology and frame evidence.
nodes:
  - node_id: "inspect_constraints"
    capability: "geometry.inspect_requirements"
    depends_on: []
    expected_artifact_roles:
      - "geometry.requirements"
  - node_id: "generate_mesh"
    capability: "geometry.generate"
    depends_on:
      - "inspect_constraints"
    expected_artifact_roles:
      - "geometry.source_candidate"
  - node_id: "validate_topology"
    capability: "geometry.validate_topology"
    depends_on:
      - "generate_mesh"
    expected_artifact_roles:
      - "validation.topology"
  - node_id: "build_scene"
    capability: "game.scene.build"
    depends_on:
      - "validate_topology"
    expected_artifact_roles:
      - "scene.runtime_candidate"
  - node_id: "profile_runtime"
    capability: "runtime.profile"
    depends_on:
      - "build_scene"
    expected_artifact_roles:
      - "validation.performance"
  - node_id: "capture_frame"
    capability: "graphics.capture_frame"
    depends_on:
      - "build_scene"
    expected_artifact_roles:
      - "validation.frame_capture"
success_conditions:
  - "mesh topology validator reports manifold edges for the required closed regions"
  - "vertex and index counts match generated buffers"
  - "runtime profile records build, device, driver, scene, and sample window"
  - "frame capture resolves the exact runtime build"
failure_edges:
  - from: "validate_topology"
    to: "generate_mesh"
    condition: "non-manifold edge or invalid index"
  - from: "build_scene"
    to: "generate_mesh"
    condition: "runtime import rejects the mesh"
status: "PREPARATION_CANDIDATE"
source_ids:
  - "community.freya_holmer"
  - "community.jasper_flick.catlike_coding"
  - "community.joey_de_vries.learnopengl"
  - "community.baldur_karlsson.renderdoc"
```

### 8.3 Graphics evidence

For a frame-level problem, capture:

- exact executable/build identity;
- scene/project fixture;
- graphics API;
- GPU and driver;
- frame number;
- pipeline state;
- resources and shader versions;
- observed symptom;
- repair candidate;
- post-repair capture.

A screenshot alone is insufficient for pipeline diagnosis.

## 9. Content-creation workflow

For reports, guides, images, decks, video, or other content:

1. identify governing sources;
2. distinguish facts, owner decisions, external facts, and synthesis;
3. create a source ledger;
4. draft;
5. validate statements against sources;
6. validate output structure and technical requirements;
7. preserve editable source and final render/export;
8. retain generated work as a candidate until accepted.

Do not invent revenue, customers, implementation status, art approval, performance, release dates, licensing rights, or model capabilities.

## 10. Cloud operation workflow

### OpenAI-specific preparation

Use current OpenAI Developers documentation to check:

- model capability;
- model and API version;
- reasoning controls;
- structured output/tool support;
- image generation/edit behavior;
- context and usage fields;
- prompt-cache behavior.

Use task-specific evals before recommending a configuration.

### Cloudflare-specific preparation

Use current Cloudflare documentation to check:

- Workers AI model availability;
- AI Gateway cache semantics;
- cost observability and whether values are estimates;
- spend limits;
- fallback behavior;
- supported provider paths.

Record cache HIT/MISS as operational telemetry. Do not interpret exact-request caching as semantic equivalence.

## 11. Deduplication and database usability

Use three levels.

### Level 1 — Exact identity

If serialized canonical content has the same SHA-256 digest, store it once and reference it.

### Level 2 — Structural equivalence

If records have the same normalized type, objective, applicability, input/output contract, and constraints, flag them as possible duplicates.

Do not delete either until provenance and meaningful variants are compared.

### Level 3 — Semantic similarity

Use semantic retrieval only to find comparison candidates. Do not automatically merge records because embeddings are close.

Preserve separate records when they differ in:

- domain;
- provider;
- version;
- constraints;
- expected artifacts;
- failure mode;
- recovery behavior;
- validation;
- applicability;
- source authority.

The goal is not the smallest database. The goal is a corpus that remains complete, searchable, and usable.

## 12. Preparation Codex completion report

Every batch report must contain observed values for:

- workspace path;
- `PREPARATION_CANDIDATE` status;
- stable batch ID;
- exact relative paths created or changed;
- record counts by type;
- exact source registry IDs used;
- parse validation result;
- schema validation result;
- duplicate-check result;
- forbidden-marker scan result;
- real-Biella boundary scan result;
- actual unresolved items, or an empty list;
- `integration_performed: false`.

A report with missing, instructional, or assumed values fails validation. A batch is not complete because files exist; it is complete when the report is backed by observed validation output.
