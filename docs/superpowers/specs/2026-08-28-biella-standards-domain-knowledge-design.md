# Biella Engine — Standards & Domain Knowledge Design

**Date:** 2026-08-28  
**Status:** DESIGN APPROVED IN PRINCIPLE BY FOUNDER; AWAITING WRITTEN-SPEC REVIEW BEFORE IMPLEMENTATION  
**Scope:** Add formal standards knowledge, deep domain craft knowledge, legal/rights, product/business knowledge, accessibility/localization, privacy/security practice, and shared terminology/ontology to Biella without expanding the permanent kernel or introducing execution blockers.

## 1. Decision

Biella will add a **Knowledge-native Standards & Domain Knowledge System**.

It will **not** add `Standard` as a permanent kernel primitive.

The permanent kernel remains approximately:

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

Standards, professional craft knowledge, terminology, ontology, rights/compliance knowledge, product/business practice, accessibility/localization practice, and privacy/security practice are represented as **versioned Knowledge with typed namespaces and applicability**.

The system exists to make Biella better at producing correct, professional work across domains. It must not become a second engine, a governance hierarchy, or a universal gate that productive work must pass before execution.

## 2. Why this is needed

Biella already defines how work can be represented, decomposed, routed, executed, checkpointed, resumed, validated when required, preserved as Artifacts and Events, and learned from through scoped Knowledge.

The missing layer is a durable answer to questions such as:

- What does professional AAA character topology require?
- What makes a production-ready gameplay system?
- Which accessibility practices apply to a particular UI?
- How should localized assets and strings be structured?
- What rights information must travel with a third-party asset?
- What makes a software API contract professionally complete?
- Which security/privacy practices apply to a particular Task?
- Which product/business metrics are appropriate for a particular decision?
- What does a term mean consistently across Biella and all Projects?

These are **Knowledge problems**, not new execution primitives.

## 3. Alternatives considered

### Approach A — Add `Standard` to the permanent kernel

Rejected.

Advantages:
- explicit first-class object;
- easy to query separately.

Problems:
- expands the universal kernel for a concept that is ultimately a type of reusable Knowledge;
- encourages standards to acquire authority over Task/Graph execution;
- creates pressure to build separate persistence, lifecycle, versioning and dependency machinery that already belongs to Knowledge.

### Approach B — Build a separate global Standards hierarchy above Biella

Rejected.

Example:

```text
Constitution
→ Standards
→ Sub-standards
→ Rules
→ Procedures
→ Checklists
→ Quality Gates
→ Enforcement
→ Execution
```

Problems:
- can block real work while unrelated standards remain incomplete;
- recreates permanent approval/review machinery;
- duplicates Task-derived validation;
- risks artificial sequencing;
- creates a second orchestration/control system.

### Approach C — Knowledge-native standards and domain craft

Accepted.

```text
ENGINE / PROJECT KNOWLEDGE
        ↓
applicability resolution
        ↓
TASK / PROJECT requirements
        ↓
GRAPH compilation
        ↓
productive execution
        ↓
task-required validation
        ↓
Artifact + evidence + learning
```

This preserves the narrow kernel and makes professional knowledge available only where relevant.

## 4. New knowledge families

The system adds the following **knowledge families**, not kernel entities.

### 4.1 Formal standards knowledge

Namespace family:

```text
standards.*
```

Examples:

```text
standards.software.api
standards.software.testing
standards.ai.grounding
standards.game.performance
standards.3d.topology
standards.animation.retargeting
standards.render.delivery
standards.audio.loudness
standards.release.packaging
standards.research.citation
```

A standard defines reusable professional expectations and validation guidance.

A standard is not automatically mandatory merely because it exists.

### 4.2 Deep domain craft knowledge

Namespace family:

```text
craft.*
```

Examples:

```text
craft.game.combat
craft.game.level_design
craft.game.camera
craft.character.topology
craft.character.rigging
craft.animation.cleanup
craft.environment.worldbuilding
craft.render.lighting
craft.vfx.simulation
craft.audio.mix
craft.cinematic.shot_design
craft.visual.composition
craft.software.debugging
```

Craft knowledge captures practical production expertise that is deeper than a Capability definition.

A Capability answers:

> What semantic ability is required?

Craft Knowledge answers:

> What does expert execution of that ability look like?

### 4.3 Legal / rights knowledge

Namespace family:

```text
legal.*
rights.*
compliance.*
```

Examples:

```text
rights.asset.license
rights.music.usage
rights.font.license
rights.model.release
rights.third_party_attribution
compliance.distribution.requirements
legal.contract.reference
```

This knowledge may represent license terms, attribution requirements, usage boundaries, provenance, distribution restrictions, ownership/rights metadata, and expiry or territory conditions where relevant.

It does not make Biella a legal authority.

It preserves project-supplied and source-backed rights/compliance facts so Tasks can account for them when applicable.

### 4.4 Product / business knowledge

Namespace family:

```text
product.*
business.*
commercial.*
```

Examples:

```text
product.discovery
product.requirements
product.metrics
product.release
business.pricing
business.unit_economics
business.market_research
commercial.packaging
commercial.positioning
```

This allows Biella to retain reusable knowledge about product discovery, prioritization, requirement quality, release planning, business metrics, pricing models, commercial packaging, market evidence, and business decision frameworks.

Project-specific commercial strategy remains Project Knowledge.

General reusable methods may become Engine Knowledge after evaluation.

### 4.5 Accessibility / localization knowledge

Namespace family:

```text
accessibility.*
localization.*
internationalization.*
```

Examples:

```text
accessibility.web.contrast
accessibility.game.input
accessibility.game.subtitles
accessibility.ui.navigation
localization.text_expansion
localization.asset_pipeline
localization.subtitle_delivery
internationalization.string_externalization
```

This knowledge may include visual contrast guidance, input alternatives, captions/subtitles, navigation accessibility, readable motion/animation treatment, localization-safe UI layout, text expansion, fonts and glyph coverage, locale-aware formatting, string/resource separation, localized asset production, and language-specific QA guidance.

Only applicable requirements should enter a Task's validation plan.

### 4.6 Privacy / security practice knowledge

Namespace family:

```text
privacy.*
security.*
```

Examples:

```text
privacy.data_minimization
privacy.retention
privacy.locality
security.software.dependencies
security.web.session_handling
security.build.provenance
security.secret_handling
security.browser.execution
```

This layer contains reusable professional practice.

It does **not** create a universal security approval system or an unrequested access-control architecture.

Security/privacy knowledge can influence a Task when:
- the Task explicitly requires it;
- Project policy requires it;
- the output contract or side-effect class makes it applicable;
- an Engine invariant already requires it.

Missing unrelated security/privacy knowledge must not stop unrelated execution.

### 4.7 Shared terminology / ontology

Namespace family:

```text
terminology.*
ontology.*
taxonomy.*
```

A terminology record may define:

```yaml
term_id:
canonical_term:
definition:
aliases:
deprecated_aliases:
scope:
domain:
source_refs:
version:
status:
supersedes:
```

An ontology relation may define:

```yaml
subject:
relation:
object:
scope:
conditions:
source_refs:
version:
status:
```

Examples:

```text
Artifact IS_NOT ContentRef
Capability IMPLEMENTED_BY CapabilityImplementation
Task EXECUTED_AS Run
Run USES GraphRevision
Node REQUIRES Capability
CapabilityImplementation RUNS_ON Resource
Project OWNS ProjectKnowledge
EngineKnowledge MUST_BE project-neutral
```

The ontology helps retrieval, reasoning, schema evolution and human communication.

It must not become a giant prerequisite that must be complete before Biella can run.

## 5. Knowledge object model

Biella should keep one durable Knowledge abstraction and make its **kind/namespace extensible**.

Conceptual record:

```yaml
knowledge:
  knowledge_id: durable_identity

  scope:
    ENGINE | PROJECT | HISTORICAL

  namespace:
    standards.*
    craft.*
    legal.*
    rights.*
    compliance.*
    product.*
    business.*
    commercial.*
    accessibility.*
    localization.*
    internationalization.*
    privacy.*
    security.*
    terminology.*
    ontology.*
    taxonomy.*

  kind:
    reusable_semantic_kind

  version:
    semantic_version_or_revision

  status:
    candidate | accepted | superseded | rejected | deprecated

  statement_or_spec:
    normalized_content

  applicability:
    conditions

  requirements:
    optional_task_applicable_requirements

  recommendations:
    optional_guidance

  prohibited_practices:
    optional_prohibitions

  validation_guidance:
    optional_validation_mapping

  evidence_guidance:
    optional_evidence_requirements

  metrics:
    optional_measurements

  source_runs:
    evidence_lineage

  source_objects:
    exact_content_lineage

  references:
    external_or_internal_evidence

  supersedes:
    prior_knowledge_ref_or_null
```

Not every field is required for every Knowledge kind.

A terminology definition does not need the same shape as a rendering standard.

The common record carries identity, scope, provenance, status, applicability and versioning. Domain-specific payloads remain extensible.

## 6. Authority and applicability

Knowledge existence does not equal universal enforcement.

An applicable requirement can derive from:

```text
ENGINE INVARIANT
or
PROJECT POLICY
or
TASK / OUTPUT CONTRACT
or
EXPLICITLY ADOPTED STANDARD
```

Recommended classification:

```text
ENGINE_INVARIANT
PROJECT_REQUIRED
TASK_REQUIRED
RECOMMENDED
REFERENCE
```

`ENGINE_INVARIANT` remains rare and reserved for true Biella-wide properties such as project isolation, durable meaningful state, exact identity where required, stale execution rejection, and historical evidence remaining non-instruction-active.

Ordinary domain craft preferences must not be promoted to Engine invariants.

## 7. Applicability resolution

Add a **Knowledge Resolver** as an execution-support subsystem, not a new kernel primitive.

Conceptual flow:

```text
Task
+ Project
+ required Capabilities
+ output contract
+ side-effect class
+ input / Artifact types
+ Project-adopted policies
        ↓
Knowledge Resolver
        ↓
small applicable Knowledge set
        ↓
Graph compiler / Node context / ValidationPlan
```

The resolver should prefer the smallest relevant set.

Do not load the entire standards/craft corpus into every Task.

## 8. Non-blocking execution semantics

This system must not recreate blockers.

Rules:

1. An incomplete unrelated standard never blocks a ready Node.
2. Missing `RECOMMENDED` or `REFERENCE` knowledge never blocks execution.
3. A missing implementation of a professional practice does not remove the semantic Capability.
4. Applicable hard requirements must be traceable to Engine invariant, Project policy or Task/output contract.
5. Validation remains Task-derived.
6. No universal reviewer, standards board, supervisor or approval chain is introduced.
7. Independent work continues when one knowledge domain is unresolved and the work does not depend on it.
8. Unknown facts remain `UNKNOWN`; they do not become invented requirements.
9. Corrected authoritative knowledge invalidates only affected conclusions/work.
10. Unaffected valid Artifacts and results are preserved.

## 9. Task compilation integration

Biella's normal compilation becomes:

```text
PROJECT REQUEST
      ↓
TASK NORMALIZATION
      ↓
CAPABILITY REQUIREMENTS
      ↓
APPLICABLE KNOWLEDGE RESOLUTION
      ↓
DYNAMIC GRAPH
      ↓
IMPLEMENTATION + RESOURCE ROUTING
      ↓
DURABLE EXECUTION
      ↓
TASK-REQUIRED VALIDATION
      ↓
ARTIFACT + EVENT + RUN MEMORY
      ↓
KNOWLEDGE CANDIDATES
```

Applicable Knowledge can affect decomposition, implementation instructions, production recipe choice, Artifact expectations, validation criteria, evidence expectations, and routing preferences where professionally relevant.

It does not own execution authority.

## 10. Memory placement

### Engine Memory

May contain project-neutral standards, reusable professional craft knowledge, general terminology, shared ontology, source-backed rights/compliance patterns that genuinely generalize, evaluated accessibility/localization practices, evaluated security/privacy practices, and reusable product/business methods.

Engine Memory must not contain one Project's legal position, license inventory, pricing, localization strings, security preferences, or visual style.

### Project Memory

May contain adopted standards, project-specific rights/licenses, project-specific compliance requirements, product/business strategy, accessibility targets, supported locales, privacy requirements, security requirements, Project-specific terminology, and Project-specific ontology/canon extensions.

### Historical Evidence

Contains old standards, superseded policies, source documents and rejected interpretations.

They remain non-instruction-active until intentionally promoted.

## 11. Knowledge ingestion and promotion

New standards/craft knowledge may originate from current Biella implementation evidence, measured Runs, official standards/specifications, official vendor/tool documentation, maintained upstream source, Project decisions, external research, or historical evidence after clean-room migration.

Promotion flow:

```text
SOURCE
  ↓
exact source identity
  ↓
claim / method extraction
  ↓
scope classification
  ↓
contradiction detection
  ↓
normalization
  ↓
KnowledgeCandidate
  ↓
evidence association
  ↓
accepted Engine / Project / Historical placement
```

No agent or successful Run writes directly to accepted Engine Memory.

## 12. Contradiction and supersession

When authoritative evidence contradicts current Knowledge:

```text
identify affected Knowledge
        ↓
mark old version superseded / inapplicable
        ↓
create corrected version
        ↓
invalidate affected derived assumptions
        ↓
recompute affected Task/Graph decisions where still active
        ↓
preserve unrelated valid work
```

Sunk effort is not evidence.

Version history is preserved.

## 13. Domain coverage

The system should be able to grow across:

```text
knowledge.*
software.*
ai.*
agent.*
game.*
product.*
ux.*
visual.*
2d.*
3d.*
character.*
animation.*
environment.*
render.*
vfx.*
film.*
video.*
audio.*
writing.*
web.*
data.*
database.*
infrastructure.*
devops.*
security.*
privacy.*
qa.*
accessibility.*
internationalization.*
localization.*
performance.*
business.*
commercial.*
operations.*
documentation.*
artifact.*
research.*
legal.*
rights.*
compliance.*
release.*
observability.*
recovery.*
cost.*
terminology.*
ontology.*
taxonomy.*
```

These are registry namespaces, not mandatory implementation phases.

## 14. Relationship to Capability

Do not confuse Knowledge with Capability.

Example:

```text
Capability:
3d.character.rig
```

answers:

> Biella needs an implementation capable of rigging a character.

Relevant Knowledge might include:

```text
standards.3d.rigging
craft.character.rigging
craft.animation.deformation
accessibility.character.readability
```

The Capability can exist even if none of those Knowledge entries have been authored yet.

Likewise, knowledge about rigging does not prove a current DCC adapter can execute the Capability.

## 15. Relationship to production packs

Production packs should bundle references to useful Knowledge, Capabilities, adapters, Artifact types and reusable graph fragments.

Conceptually:

```yaml
production_pack:
  domain: game.character
  knowledge_refs:
    - craft.character.topology
    - craft.character.rigging
    - standards.3d.export
  capability_refs:
    - 3d.character.model
    - 3d.character.rig
    - 3d.character.skin
    - animation.validate
  artifact_roles:
    - editable_character
    - skeleton
    - rig
    - skinned_character
    - export_package
```

The pack is compositional.

It must not introduce a second scheduler, memory system or validation authority.

## 16. Legal / rights handling boundary

Biella should preserve legal/rights information as source-backed structured Knowledge and Artifact metadata.

Conceptual example:

```yaml
asset_rights:
  asset_ref:
  license_ref:
  rights_holder:
  usage_scope:
  attribution_required:
  modification_allowed:
  redistribution_allowed:
  project_scope:
  evidence_refs:
  status:
```

Biella may use this information to satisfy Task constraints.

It must not fabricate legal conclusions when the source does not support them.

Unknown remains unknown.

## 17. Accessibility / localization handling boundary

Accessibility and localization are cross-cutting professional knowledge, but not universal gates.

Examples:

```text
web accessibility Task
→ applicable accessibility standards required

internal rendering benchmark
→ accessibility knowledge likely irrelevant

game menu for eight languages
→ localization + accessibility knowledge applicable

binary Artifact transfer
→ neither domain necessarily applies
```

Applicability must be Task-specific.

## 18. Security / privacy handling boundary

Security/privacy practice can participate in Task compilation without becoming a separate approval organization.

Examples:

```text
public web authentication change
→ relevant security practice

Project handling restricted source
→ relevant privacy/locality practice

offline 3D render
→ unrelated web-session security guidance not loaded
```

The system should support professional security/privacy practice while preserving Biella's rule against unrelated global blockers.

## 19. Product / business handling boundary

Product/business knowledge can inform research, prioritization, pricing analysis, launch planning, product metrics, packaging, positioning, and commercial comparison.

It must remain evidence-bound.

Project-specific business strategy stays Project-scoped.

Biella should not promote one Project's pricing or market assumptions into Engine defaults.

## 20. Terminology / ontology behavior

The terminology/ontology system should improve schema naming, documentation consistency, retrieval, source disambiguation, cross-domain reasoning, migration normalization, compatibility and API clarity.

It should support canonical terms, aliases, deprecated aliases, term versioning, relationships, scope, source evidence and supersession.

It must never require the entire ontology to be complete before execution.

## 21. Persistence model

Knowledge records require durable identity and versioning.

Content payloads should be content-addressable where practical.

At minimum, persistent records must make it possible to answer:

- What Knowledge version did this Run use?
- What source supported it?
- Was it Engine or Project scoped?
- Was it required or recommended?
- Was it later superseded?
- Which active decisions depended on it?

A ContextReceipt should be able to reference exact Knowledge versions consumed by a Node.

## 22. Observability

Useful events may include:

```text
KNOWLEDGE_CANDIDATE_CREATED
KNOWLEDGE_ACCEPTED
KNOWLEDGE_SUPERSEDED
KNOWLEDGE_REJECTED
STANDARD_APPLICABILITY_RESOLVED
TERMINOLOGY_RESOLVED
RIGHTS_CONSTRAINT_APPLIED
PROJECT_STANDARD_ADOPTED
```

These are evidence events.

They do not create workflow stages.

## 23. Initial implementation seams

The eventual implementation should extend existing Biella concepts rather than creating new top-level architecture.

Expected seams:

```text
Knowledge repository / persistence
Knowledge namespace registry
Knowledge Resolver
Context Compiler
Task compiler / Graph planner
ValidationPlan compiler
Project policy/adoption records
Knowledge promotion pipeline
Event ledger
```

No current P0 implementation boundary should be displaced by this design.

This feature should enter implementation when the durable Knowledge and Project/Run foundations it depends on exist.

Research and candidate corpus construction can occur independently when it does not interfere with current P0 work.

## 24. Implementation ordering

This design does not create a new prerequisite before current P0.

Recommended later slices:

### DK-01 — Knowledge namespace extension
Add extensible namespace/kind support for the new Knowledge families.

### DK-02 — Terminology / ontology records
Implement canonical term and relation records.

### DK-03 — Standards / craft records
Support formal standards and deep craft payloads.

### DK-04 — Applicability resolver
Resolve the smallest relevant Knowledge set for a Task/Node.

### DK-05 — Project adoption / requirement mapping
Allow Project and Task requirements to explicitly activate applicable standards.

### DK-06 — Rights/compliance records
Add source-backed rights/license/compliance structures.

### DK-07 — Accessibility/localization records
Add cross-cutting production knowledge and applicability mapping.

### DK-08 — Security/privacy practice records
Add source-backed professional practice without universal gates.

### DK-09 — Product/business records
Add reusable methods and Project-scoped strategy knowledge.

### DK-10 — Promotion and contradiction learning
Integrate candidate promotion, supersession and evidence-backed improvement.

These are logical implementation slices, not mandatory sequential runtime stages.

Independent slices may be built concurrently once their actual dependencies exist.

## 25. Acceptance criteria

```text
new_permanent_kernel_primitives = 0

standards_as_universal_execution_gate = 0
mandatory_global_review_chain = 0
mandatory_standards_board = 0
unrelated_missing_standard_blocks_ready_work = 0

engine_project_knowledge_leakage = 0

knowledge_source_traceability = 100%
knowledge_version_traceability = 100%
applicable_required_knowledge_has_authority_source = 100%
unknown_facts_remain_unknown = 100%

task_derived_validation_preserved = 100%
capability_knowledge_separation_preserved = 100%

correction_conflict_detection_rate = 100%
conflicting_knowledge_retention_rate = 0%
unaffected_valid_result_preservation_rate = 100%
affected_decision_recomputation_rate = 100%
```

Functional acceptance examples:

1. A software Task can resolve software standards without loading unrelated film/audio standards.
2. A game localization Task can resolve localization/accessibility knowledge and add only required validation.
3. A 3D render Task continues even if a business-pricing standard is missing.
4. A Capability remains registered even when craft/standards knowledge for it is incomplete.
5. Project-specific license data cannot leak into another Project.
6. Superseding a terminology definition updates affected resolution without rewriting historical Run receipts.
7. A Run can identify exactly which Knowledge versions were supplied to each relevant Node.
8. No standard can create a global maker → critic → validator → approval pipeline merely by existing.

## 26. Existing Biella concepts reused

This design deliberately reuses:

- `Project` for scope/adoption;
- `Task` for requirements;
- `Run` for lineage;
- `Capability` for semantic abilities;
- `Graph` / `Node` for execution;
- `Artifact` / `ContentRef` for produced and source content;
- `Event` for durable evidence;
- `Knowledge` for all new standards/craft/domain intelligence;
- Engine/Project/Historical memory separation;
- Context receipts;
- task-derived validation;
- correction/supersession;
- provider/resource neutrality.

## 27. What this design does not do

It does not:

- change the active P0 task;
- introduce a new provider;
- introduce a new model;
- introduce a security gate;
- require full standards authoring before Biella can execute;
- create a permanent human approval hierarchy;
- create a permanent specialist/agent hierarchy;
- turn standards into capabilities;
- turn capabilities into standards;
- promote Project strategy into Engine defaults;
- activate historical material automatically;
- implement source code yet.

## 28. Final architecture relation

```text
                    BIELLA KERNEL
      Project / Task / Run / Capability / Graph
      Node / Artifact / Resource / Event / Knowledge
                           │
                           ▼
                 SCOPED KNOWLEDGE SYSTEM
        ┌─────────────────────────────────────┐
        │ standards.*                         │
        │ craft.*                             │
        │ terminology.* / ontology.*          │
        │ legal.* / rights.* / compliance.*   │
        │ product.* / business.*              │
        │ accessibility.* / localization.*    │
        │ privacy.* / security.*              │
        └─────────────────────────────────────┘
                           │
                  applicability resolution
                           │
                           ▼
                  TASK / GRAPH COMPILATION
                           │
                implementation + resource
                           │
                           ▼
                    DURABLE EXECUTION
                           │
                           ▼
                  TASK-DERIVED VALIDATION
                           │
                           ▼
               ARTIFACT + EVENT + RUN MEMORY
                           │
                           ▼
                EVIDENCE-BOUND KNOWLEDGE
```

The result is a broader and more professionally capable Biella without increasing the kernel or converting shared knowledge into bureaucracy.
