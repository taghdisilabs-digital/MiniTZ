GEC-1 - BIELLA GLOBAL EXECUTION CONTRACT
Apply this contract to every numbered Biella implementation prompt unless that prompt explicitly narrows a rule for technical reasons.
Project identity and authority
Biella Engine is a new, project-neutral, universal AI production/execution engine. It is not MiniTZ v2 and is not tied to any project, engine, provider, model, cloud, GPU family, operating system, fixed agent hierarchy, fixed pipeline, or historical topology. Mahdi Taghdisi is the sole owner and final work-policy/product authority. Current owner direction, the active task, accepted Biella source, and durable runtime state override historical material.
Direct execution
Execute clear implementation work directly. Inspect the real repository and current state first. Continue from accepted work; do not restart settled work. Ask only when essential information cannot be recovered or inferred. Diagnose failures from actual outputs, fix the smallest affected boundary, continue unaffected work, and never substitute planning or ceremony for implementation.
No AI management layer
Do not invent approval/readiness gates, mandatory maker/critic/validator chains, fixed repair counts, artificial qualification periods, provider-preparation ceremonies, blocker/governance layers, or low-resource restrictions unless the task explicitly requires a real technical condition. Validation is derived from output contracts, risk, side effects, Project acceptance, and required evidence.
Clean-history and migration firewall
Biella must have clean source history. MiniTZ is a retired historical/migration source, not Biella source ancestry or active authority. Raw historical material may enter only through: RAW SOURCE -> QUARANTINE -> SEMANTIC EXTRACTION -> CLASSIFICATION -> NORMALIZATION -> CLEAN REIMPLEMENTATION -> BIELLA-NATIVE OBJECT. Never mechanically rename MiniTZ to Biella. Do not mine/reconstruct large historical backups into active Biella before the quarantine firewall and destination schemas exist.


Allowed migration classifications: UNIVERSAL_GOOD, UNIVERSAL_REWRITE, PROJECT_SPECIFIC, HISTORICAL_EVIDENCE, DUPLICATE, OBSOLETE_OR_DRIFT. Raw MiniTZ prompts, instructions, memories, Project Instructions, AGENTS/rules/control/recovery/workflow material, branding/assets/lore/preferences, and blocker rules never become active Biella instructions or memory.
Source truth and exact identity
Preserve exact supplied repository names, branches, SHAs, paths, Drive IDs, object digests, runtime identities, source revisions, and hardware observations unless current evidence proves they changed. Never invent missing bytes, SHAs, credentials, benchmark results, provider metrics, or historical facts. latest, a filename, a mutable branch, a provider alias, a session ID, or a cache hit is not sufficient durable identity when exact identity is required.
Project isolation
Every Project is an explicit isolation namespace. Project source, assets, architecture, requirements, preferences, acceptance rules, secrets, tool choices, memories, retrieval sources, workspaces, destinations, and production outputs must not leak across Projects. Physical deduplication may share content bytes internally; logical authorization and Project identity remain separate.
Kernel neutrality
Keep the durable kernel narrow: approximately Project, Task, Run, Capability, Graph, Node, Artifact, Resource, Event, Knowledge. Providers, models, GPUs, engines, browsers, DCCs, build systems, databases, media tools, workers, checkpoints, validators, agents, caches, and production domains are implementations, adapters, data, or lifecycle semantics unless a universal invariant proves otherwise.
Tasks, graphs, agents, and validation
Tasks specify desired outcomes, constraints, evidence, and side-effect authority, not permanent execution topology. Tasks compile to immutable/revisioned dependency Graphs. Independent Nodes should execute concurrently when dependencies and resources permit. Agents are dynamic execution resources described by objective + capabilities + context + tools + model/runtime + resources + output contract. Named roles are optional patterns, not hierarchy. Validation must be Task-derived; do not impose a global maker -> critic -> validator -> repair sequence.
Durable execution and cognition
Useful work must not exist only in chat/model context, process RAM, GPU memory, provider sessions, cache, or temporary disk. Preserve durable Run state, Events, Graph revisions, execution attempts/fences, checkpoints where useful, content-addressed Artifacts, source identities, call/token accounting, failures/recovery, and versioned Knowledge. Cache deletion may reduce speed but must not destroy authoritative state.


Keep ENGINE MEMORY, PROJECT MEMORY, RUN MEMORY, HISTORICAL EVIDENCE, and CACHE distinct. Run/model output cannot write directly to supported Engine Knowledge. Promotion follows candidate observation -> scope classification -> evidence -> dedup/contradiction -> versioned Knowledge candidate -> Engine/Project/Historical placement.
Resource truth and concurrency
Hardware is runtime state. Measure effective CPU, RAM, GPU/VRAM, storage, network, loaded models/tools, locality, queue pressure, and health. Capability existence is independent of current hardware availability. Use resource-scoped leases/fences where needed; never recreate a global heavyweight lock. Use CPU/GPU/RAM/NVMe/network concurrently when useful, but never force artificial 100% utilization.
Adapters and side effects
Providers/tools are replaceable adapters. Credentials and mere technical reachability do not grant Project data egress or external side-effect permission. External mutations require the Task's declared authority. Secrets must stay out of Task payloads, Events, call ledgers, checkpoints, prompts where unnecessary, packages, and normal evidence.
Real-output rule
Never claim working, tested, fixed, built, rendered, packaged, uploaded, published, deployed, verified, or production-ready unless the relevant result was actually observed. Exit status alone is not enough where a usable output is required: inspect/reopen/decode/run/read-back/verify the resulting Artifact as appropriate. Classify evidence honestly as REAL, REFERENCE, MOCK, or NOT_RUN.
Implementation discipline
Inspect current code, migrations, tests, README/AGENTS/policy files, and accepted interfaces before modifying. Reconcile prompt interface names with accepted existing equivalents instead of duplicating architecture. Keep changes task-scoped. Prefer failure-first/TDD for bug and feature behavior when useful. Run focused tests first, then the relevant regression gate. Preserve unrelated user work and dirty state. Do not perform unrelated refactors.
Source control and handoff
For nontrivial work, use an isolated branch/worktree when practical. Commit coherent accepted work to Biella's clean history; do not import MiniTZ Git ancestry. Report exact source commit, result commit, result tree, migrations, tests, actual KPI values, limitations, unresolved facts, and next dependency. Stop after the requested numbered prompt; do not begin the next prompt automatically.
PROMPT 1/51 - P0-01
TITLE
Clean-Room Migration Firewall
PHASE
P0 - Clean kernel + migration firewall
GOAL
Establish the clean Biella repository/package boundary and a quarantine-first migration subsystem that can preserve and semantically mine historical sources without allowing raw history to become active instructions, memory, retrieval, source, or capability definitions.
CURRENT VERIFIED STATE
* Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.
* Read the previous numbered prompt handoff and verify that its claimed commits/tests/interfaces exist. Do not reconstruct missing work from memory.
* If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.
SOURCE ARCHITECTURE
* Establish clean identity, isolation, immutable contracts, fencing, artifacts, events, and durable execution before any historical mining.
* Apply the GEC-1 kernel, Project isolation, exact-identity, durability, validation, resource, provider-neutrality, and migration-firewall invariants.
DEPENDENCIES
* No numbered prompt dependency. Inspect current connected/source state first.
INPUTS
* Current Biella source and durable state.
* The exact Task/prompt requirements below.
* Previous prompt continuation evidence and exact IDs/refs needed by this task.
* Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.
IN SCOPE
* Create migration/quarantine, extraction, classification, normalization boundaries with one-way dependency toward clean Biella contracts.
* Implement exact SHA-256 identity/provenance for quarantined bytes and the six migration classifications.
* Make QuarantineRef type-incompatible with active Artifact/Task/context references.
* Provide migration-only read/extract APIs; normal runtime must have no raw-quarantine search/import path.
* If no clean Biella repository exists, bootstrap the minimum clean repository here rather than creating another setup phase.
OUT OF SCOPE
* Do not reconstruct/mine the large clean MiniTZ backup yet.
* Do not implement normal retrieval, memory, scheduling, model providers, or production adapters.
REQUIRED IMPLEMENTATION
* Create migration/quarantine, extraction, classification, normalization boundaries with one-way dependency toward clean Biella contracts.
* Implement exact SHA-256 identity/provenance for quarantined bytes and the six migration classifications.
* Make QuarantineRef type-incompatible with active Artifact/Task/context references.
* Provide migration-only read/extract APIs; normal runtime must have no raw-quarantine search/import path.
* If no clean Biella repository exists, bootstrap the minimum clean repository here rather than creating another setup phase.
REQUIRED INTERFACES
* MigrationSource
* SemanticExtraction
* MigrationClassification
* NormalizedMigrationCandidate
* QuarantineRef
DATA / STATE CHANGES
* Quarantine metadata/schema and exact source provenance.
FAILURE BEHAVIOR
* Digest mismatch, missing classification, provenance loss, or active-reference binding must fail closed.
CONCURRENCY / RECOVERY REQUIREMENTS
* Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.
* Recovery must preserve already verified durable work and reject stale owners/results.
TESTS
* Quarantine exact bytes and read them back.
* Corrupt bytes and prove verification fails.
* Require classification before normalization; reject unknown classifications.
* Use a synthetic hostile historical instruction and prove it remains inert to normal runtime admission.
* Static dependency test: active runtime does not import raw quarantine modules.
KPI
* raw_sources_with_digest=100%
* raw_sources_with_provenance=100%
* unclassified_active_admissions=0
* raw_history_in_normal_retrieval=0
* raw_history_in_Project_or_Engine_memory=0
* direct_runtime_dependency_on_quarantine=0
RESTORED LONG-FORM REQUIREMENTS
CLEAN-ROOM BOUNDARY
Before creating migration code, inspect the current workspace and determine whether a clean Biella repository already exists. If one does not exist, Prompt 1 owns creation of the minimum clean Biella repository/package boundary. Do not import MiniTZ Git ancestry, copy the MiniTZ tree, or initialize Biella from a MiniTZ checkout.


The dependency direction must be one-way:


historical/quarantine code


    can depend on neutral migration contracts


active Biella runtime


    MUST NOT depend on raw historical/quarantine readers


The normal Task, Project, Graph, Context, Memory, Capability, and runtime admission paths must have no method that accepts a raw historical object or QuarantineRef as if it were an active Artifact.
MIGRATION PIPELINE
Implement the migration flow explicitly:


RAW HISTORICAL BYTES


        ↓


MigrationSource / QuarantineRef


        ↓


SemanticExtraction


        ↓


MigrationClassification


        ↓


NormalizedMigrationCandidate


        ↓


later clean Biella-native implementation


Required classification values are exactly:


* UNIVERSAL_GOOD
* UNIVERSAL_REWRITE
* PROJECT_SPECIFIC
* HISTORICAL_EVIDENCE
* DUPLICATE
* OBSOLETE_OR_DRIFT


Do not introduce a default/unknown classification that can later be admitted automatically.


MigrationSource must preserve enough provenance to prove exactly what historical bytes were inspected, including SHA-256 of the raw bytes, source locator/manifest identity when available, acquisition/import time, source type, and immutable metadata needed for audit. Do not treat filename alone as identity.


SemanticExtraction describes meaning extracted from the source. It must not carry executable authority merely because the original text contained imperative language.


NormalizedMigrationCandidate must be impossible to create without an explicit classification and provenance chain back to the raw source.
HOSTILE INSTRUCTION INERTNESS
Create a synthetic historical fixture containing strong imperative content, for example instructions claiming to be owner policy, demanding provider choices, or telling the runtime to override current Biella rules.


Demonstrate that:


* quarantine can store/read the bytes;
* migration extraction can analyze them;
* the normal Biella runtime cannot retrieve or execute them;
* they cannot become Project Memory or Engine Knowledge directly;
* they cannot bind as ordinary Task input;
* they cannot register capabilities or policy;
* they remain data/evidence only.


This is a technical contamination test, not a prompt-warning comment.
FAIL-CLOSED SEMANTICS
Reject:


* digest mismatch;
* provenance missing;
* invalid classification;
* missing classification;
* malformed source identity;
* attempt to convert QuarantineRef directly into active Artifact;
* attempt to place raw source text in supported Engine Knowledge;
* attempt to include quarantine in normal context/retrieval.


Do not "best effort" around migration identity errors.
IDEMPOTENCY
Re-importing the same exact historical bytes under the same source identity must be idempotent or deterministically deduplicated. It must not create conflicting active candidates or duplicate authority.


Different bytes under the same human filename must remain distinct by digest.
SCOPE CONTROL
Do not start reconstructing or mining the large clean MiniTZ backup in this prompt. The purpose of P0-01 is to make later mining safe. Use only small synthetic/reference fixtures needed to prove the firewall.


Do not add provider/model/GPU/game-engine assumptions to migration contracts.
REQUIRED TEST MATRIX
At minimum prove:


1. exact raw bytes round-trip through quarantine;
2. SHA-256 verification succeeds for unchanged data;
3. corruption causes verification failure;
4. each of the six classifications round-trips;
5. unclassified candidate normalization is rejected;
6. invalid classification rejected;
7. hostile imperative historical content is inert;
8. raw history cannot bind to Project Memory;
9. raw history cannot bind to Engine Knowledge;
10. raw history cannot enter normal Context/Task input;
11. raw history cannot enter normal retrieval index;
12. active runtime package/module dependency scan finds no raw-quarantine dependency;
13. duplicate import is idempotent/deduplicated;
14. same filename with different bytes remains distinct;
15. repository history is clean and has no imported MiniTZ ancestry.
P0-01 EXIT
The migration system may preserve and study history, but no raw historical material has an active path into Biella. Only after this is true may later work consider large historical-source mining.
ACCEPTANCE CRITERIA
* Clean Biella history/boundary exists.
* Raw history can be quarantined and classified but not activated.
* Normalized candidates preserve provenance and cannot exist without classification.
* No MiniTZ source is copied or mechanically renamed into Biella.
DELIVERABLES
* Real implementation source and task-scoped tests; schema/migrations/config only when this prompt requires them.
* Durable evidence/Artifacts required by the task.
* A coherent commit in clean Biella history when repository write access is available and the implementation is complete.
EVIDENCE TO REPORT
* Hostile-instruction inertness test
* Quarantine dependency/admission test
* Exact source/result commit and migrations.


Use this result block:


PROMPT: 1/51 - P0-01


STATUS: COMPLETE / PARTIAL / BLOCKED


SOURCE COMMIT:


RESULT COMMIT:


RESULT TREE:


IMPLEMENTED:


INTERFACES CREATED/CHANGED:


MIGRATIONS/STATE CHANGES:


TESTS EXECUTED:


KPI RESULTS:


REALITY CLASSIFICATION:


PROJECT ISOLATION / CONTAMINATION / DURABILITY CHECKS:


KNOWN LIMITATIONS:


UNRESOLVED FACTS:


NEXT DEPENDENCY:
CONTINUATION STATE
* Stop after this prompt. Do not begin prompt 2 automatically.
* Leave the repository/worktree in an understood state and report any intentional dirty/uncommitted files.
* The next prompt must verify this handoff from actual repository state before editing.