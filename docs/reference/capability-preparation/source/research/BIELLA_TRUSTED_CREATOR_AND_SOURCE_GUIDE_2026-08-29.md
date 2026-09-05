# Biella Capability Preparation — Verified Creator and Source Guide

**Research date:** 2026-08-29  
**Status:** `PREPARATION_CANDIDATE`  
**Audience:** preparation Codex workers and the authoritative main Biella Codex  
**Machine registry:** `research/SOURCE_REGISTRY_2026-08-29.jsonl`

## 1. Purpose and boundary

This guide identifies community creators, open-source projects, and official platform sources that provide inspectable, testable material for:

- prompt design and evaluation;
- model selection and token/cost discipline;
- coding-agent operation;
- structured content generation;
- reproducible visual-AI workflows;
- game development, graphics, shaders, simulation, and debugging;
- cloud AI operations through OpenAI and Cloudflare.

The sources are **inputs to preparation**, not Biella authority. Their methods may be converted into `PREPARATION_CANDIDATE` capabilities, tasks, validators, examples, or knowledge records. The authoritative main Biella Codex must compare candidates against current Biella source and runtime evidence before integration.

No source is labeled globally “trusted.” Each source is verified only for the scopes recorded in the registry.

## 2. Verification method

A source was retained only when at least one primary, inspectable artifact existed:

1. maintained official documentation;
2. a versioned source repository;
3. runnable examples or notebooks;
4. explicit tests, evaluations, or benchmarks;
5. code accompanying educational claims;
6. release history and issue tracking;
7. clearly stated limitations, versions, or maintenance status.

Popularity, subscriber count, visual polish, or repeated community quotation were not accepted as evidence.

Each source record contains:

- exact primary URLs;
- the evidence basis used;
- what the source is verified for;
- cautions and maintenance/version constraints;
- uses that remain outside its authority;
- licensing notes;
- the date checked.

## 3. Source hierarchy for preparation work

Use the narrowest applicable source in this order:

1. **Current official provider or software documentation** for exact APIs, current models, limits, caching, pricing behavior, supported operations, and platform-specific semantics.
2. **Official versioned example repositories** for implementation syntax and reproducible integration patterns.
3. **Community tools with code, tests, evaluations, or release history** for workflow and operational practices.
4. **Code-backed educational creators** for concepts, task examples, and experiment design.
5. **Opinion or synthesis material** only when its claims are translated into measurable preparation candidates.

A community source never overrides current official documentation about a provider API. Official documentation does not prove that a model or workflow succeeds on a Biella workload; representative evaluation still decides that.

## 4. Selected source map

### Official platform anchors

| Source ID | Best use | Strongest evidence | Principal caution |
|---|---|---|---|
| `official.openai.developers` | Current OpenAI models, reasoning controls, image model, token/cache semantics | First-party current documentation | Refresh before production; provider capability is not workload acceptance |
| `official.openai.cookbook` | Runnable OpenAI API patterns | Versioned first-party notebooks and examples | Examples can age and need production hardening |
| `official.openai.evals` | Evaluation-first prompt/model selection | Open evaluation framework and task definitions | Benchmark validity is limited to its represented workload |
| `official.cloudflare.ai` | Workers AI and AI Gateway operation | First-party cache, cost, spend, fallback, and model docs | Cost can be estimated; exact-request cache is not semantic memory |
| `official.cloudflare.ai_examples` | Deployable Cloudflare examples | First-party versioned code | Example deployment is not a full operating model |

### Prompting, evaluation, and coding-agent practice

| Source ID | Best use | Strongest evidence | Principal caution |
|---|---|---|---|
| `community.dair.prompt_engineering_guide` | Technique taxonomy and research discovery | Maintained repository, papers, notebooks | Older prompt techniques can degrade newer models |
| `community.aider.paul_gauthier` | Tested code-editing workflow and model comparison | Open tool plus 225-problem multilingual code-editing benchmark | Aider scores do not generalize to every coding task |
| `community.simon_willison.llm` | Local prompt provenance, provider plugins, deterministic tests | Open CLI and `llm-echo` | Prompt logging requires private-data discipline |
| `community.hamel_husain.evals` | Representative eval sets and error analysis | Public technical material and code | Advice must become explicit datasets and checks |
| `community.jason_liu.instructor` | Typed, validated structured output | Tests, typed schemas, bounded retry patterns | Schema validity is not semantic correctness |
| `community.dex_horthy.12_factor_agents` | Context ownership and inspectable control flow | Versioned open guide with code-oriented patterns | Opinionated synthesis, not a universal architecture |
| `community.eleutherai.lm_eval_harness` | Reproducible general benchmark execution | Open evaluation framework | Must be paired with project-specific evals |

### Reproducible visual creation

| Source ID | Best use | Strongest evidence | Principal caution |
|---|---|---|---|
| `official.comfyui` | Graph-based reproducible image workflows | JSON workflows, metadata, official examples, releases | Pin versions; custom nodes can break |
| `community.acly.krita_ai_diffusion` | Editable artist-in-the-loop AI workflow | Open Krita integration with paint/edit controls | Backend and model versions must be pinned |
| `official.invokeai` | Alternative canvas and node workflow | Open code, tests, docs, releases | Workflow compatibility is version-dependent |
| `community.cubiq.latent_vision_ipadapter` | IP-Adapter and reference-conditioning research | Open examples and detailed tutorials | Maintenance-only; use only with pinned versions |

### Game, graphics, and visual programming

| Source ID | Best use | Strongest evidence | Principal caution |
|---|---|---|---|
| `community.jasper_flick.catlike_coding` | Version-aware Unity rendering tasks | Source-backed tutorials with update history | Older series can target obsolete Unity APIs |
| `community.freya_holmer` | Game math, geometry, shaders, technical visualization | Long-form instruction plus production library context | Convert video/course knowledge into explicit checks |
| `community.sebastian_lague` | Non-trivial procedural and simulation projects | Public code repositories accompanying projects | Educational projects need version/performance revalidation |
| `community.acerola.garrett_gunnell` | Real-time graphics, shaders, post-processing | Annotated public graphics repositories | Experimental code is not automatically production architecture |
| `community.robert_nystrom.game_programming_patterns` | Game software trade-offs and patterns | Complete public book and source | Patterns are options, not mandatory architecture |
| `community.joey_de_vries.learnopengl` | Low-level rendering and shader fundamentals | Runnable source accompanying detailed tutorials | OpenGL code is API-specific |
| `community.baldur_karlsson.renderdoc` | Graphics evidence and failure diagnosis | Active open graphics debugger and technical docs | Captures are hardware/build/driver-specific |

## 5. Why these sources are useful to Biella preparation

### 5.1 Prompting is treated as an evaluated component

The combined lesson from OpenAI Evals, Aider, Hamel Husain, Instructor, DAIR.AI, and 12-Factor Agents is not “find one perfect prompt.” It is:

1. define a representative task and acceptance evidence;
2. make inputs, source authority, constraints, and output contract explicit;
3. run the prompt/model/tool combination;
4. capture exact results;
5. classify failures;
6. change one material variable;
7. rerun and compare.

Preparation records should therefore describe prompts as versioned candidates linked to tasks and eval evidence, not as universal advice.

### 5.2 Model selection must remain task-specific

OpenAI model documentation and Cloudflare model catalogs establish what providers currently offer. Aider and evaluation frameworks demonstrate how to compare behavior. The selection rule is:

> Choose the least expensive and fastest configuration that passes the representative task contract with acceptable reliability.

Do not select a model because it is newest, largest, most expensive, or ranked first on an unrelated aggregate leaderboard.

A model-selection candidate must record:

- model and provider identity;
- exact task/eval set;
- prompt/context version;
- tool availability;
- input, cached input, cache-write, reasoning, and output usage when exposed;
- latency and cost source;
- pass/fail result;
- failure categories;
- version/date.

### 5.3 Token efficiency is an engineering property

Official OpenAI and Cloudflare documentation support measuring cache and usage behavior. Community workflow sources support owning context and avoiding unnecessary repetition.

Preparation guidance should distinguish:

- **unique durable information** from cumulative model input;
- **provider prompt-cache reuse** from Biella knowledge;
- **stable context prefixes** from dynamic task suffixes;
- **exact provider-reported usage** from estimates;
- **raw evidence** from promoted knowledge.

Do not describe cached input as stored knowledge. Do not remove necessary context merely to minimize token count. Optimize after the task passes.

### 5.4 Coding work should produce repository evidence

Aider’s tested workflow, OpenAI examples/evals, Simon Willison’s inspectable local tooling, and Instructor’s schema validation support a coding loop built around:

- exact repository/base revision;
- bounded objective and acceptance;
- focused source retrieval;
- smallest task-scoped change;
- lint/type/test/build checks relevant to the change;
- inspectable diff;
- commit identity and remote readback when publication is required;
- failure evidence retained instead of hidden.

Preparation accounts may generate such task examples, but may not touch or claim facts about the real Biella Engine.

### 5.5 Visual work should be reproducible and editable

ComfyUI, InvokeAI, and Krita AI Diffusion show different useful properties:

- a serialized workflow graph;
- exact node/model/version identity;
- seed and generation settings;
- output metadata;
- artist-editable correction;
- local or controlled execution;
- repeatable iteration.

Latent Vision’s IP-Adapter material is valuable for technique study, but its maintenance-only status makes it a pinned historical/conditional source, not a default dependency.

A visual preparation record should preserve:

- workflow identity and version;
- model and model-license reference;
- seed and generation parameters;
- input/reference image identities;
- node/plugin versions;
- editable source artifact;
- rendered candidate;
- validation evidence;
- known structural or rights limitations.

### 5.6 Game and graphics tasks must connect theory to observed output

Freya Holmér, Catlike Coding, LearnOpenGL, Sebastian Lague, Acerola, Robert Nystrom, and RenderDoc cover complementary layers:

- mathematics and geometry;
- rendering pipeline fundamentals;
- engine-specific implementation;
- procedural and simulation projects;
- shader and post-processing experiments;
- architecture trade-offs;
- frame-level debugging evidence.

A useful preparation task is therefore not “make a game.” It is a bounded, evidence-producing workload such as:

- implement and profile a procedural mesh generator against explicit topology constraints;
- reproduce a lighting technique at an exact engine/version and validate frame output;
- diagnose a rendering artifact using a captured frame and shader state;
- compare two spatial data structures on one measured scene;
- build an editable material workflow and retain source, runtime, and capture artifacts.

## 6. Exclusion rules

Do not promote material when the only basis is:

- follower/subscriber count;
- screenshots without source or workflow data;
- anonymous prompt collections with no tests;
- a single successful output with no failure examples;
- copied prompts lacking model/date/task context;
- outdated tutorials presented as current without version qualification;
- closed claims that cannot be inspected;
- benchmark screenshots without task definitions;
- AI-generated summaries that do not link to the underlying primary source.

Do not copy protected tutorials, courses, or videos into the corpus. Record concise findings, source identity, and a link. Code reuse must follow the source license.

## 7. Updating the registry

When a source changes:

1. re-open the primary source;
2. record the checked date;
3. update only affected fields;
4. preserve materially different version-specific guidance;
5. mark abandoned or superseded material explicitly;
6. do not silently rewrite historical preparation batches;
7. regenerate the verification manifest and file digests.

The registry is not a popularity list. It is an evidence-scoped map for preparation work.
