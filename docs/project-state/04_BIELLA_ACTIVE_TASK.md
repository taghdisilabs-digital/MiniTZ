# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P2-10
  global_number: 29
  phase: P2
  title: Project-Scoped Context Compilation and Derived Retrieval
  state: READY_AFTER_P2_09_DURABLE_CLOSE
  exact_prompt:
    title: 29_P2-10_Project_Scoped_Context_Compilation_and_Derived_Retrieval.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P2/29_P2-10_Project_Scoped_Context_Compilation_and_Derived_Retrieval.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P2/29_P2-10_Project_Scoped_Context_Compilation_and_Derived_Retrieval.md.docx
    drive_id: 1x04_Hu20eHm8NwGu7Gliuhn4EVgPLkxzLxLzPkVZueM
    local_docx_sha256: 40f77067ba32bbc379be5fa5e7cd539206209f0eb423b7389859dd2372c075a2
    live_drive_exported_docx_sha256: ed07ff107e12340696bff86fdfe51ac106141fefd27f5c841ab5d851ba5a5a1e
    canonical_text_sha256: 52662218cf06d7c41c36c1fd1c22b01e9f850fed30af142391dd0f5421b9cffe
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P2-09
    result_commit: 03ea21dbd22466470d07a674fd330ad68009d756
    result_tree: 5663d2b02872fd0bdc1fb10320e2012e63122345
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_type_build_installed_restart_and_full_regression: VERIFIED
  numbered_successor: P2-11

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P2_10_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_Task_Run_Graph_Node_Artifact_ProjectKnowledge_EngineKnowledge_RunMemory_ModelCall_ContentRef_and_quarantine_firewall_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P2_11_or_later_prompt_bodies_before_P2_10_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_Artifact_ContentRef_ModelCall_ToolCall_Event_ResourceAllocation_and_managed_runtime_identity
    - P1_ContentRef_object_storage_Project_Engine_Run_memory_graph_event_scheduler_routing_and_checkpoint_contracts
    - P2_01_through_P2_04_real_execution_adapter_isolation_streaming_fencing_and_durability_contracts
    - P2_05_destination_egress_credential_redirect_streaming_timeout_cancellation_TLS_and_transport_evidence_contracts
    - P2_06_provider_neutral_model_deployment_execution_health_tool_policy_fencing_and_provenance_contracts
    - P2_07_browser_session_generation_egress_origin_side_effect_upload_download_wait_secret_and_durable_evidence_contracts
    - P2_08_Project_database_scope_parameterization_bounded_streaming_transaction_truth_TLS_secret_and_internal_database_firewall_contracts
    - P2_09_ContentRef_replica_state_streaming_independent_verification_corruption_fallback_repair_deletion_Project_egress_secret_and_stale_owner_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |
  PROMPT 29/51 - P2-10

  TITLE

  Project-Scoped Context Compilation and Derived Retrieval

  PHASE

  P2 - Universal execution fabric

  GOAL

  Compile exact model-visible context from permitted Task/Project/Run/Engine sources and build derived retrieval indexes with full provenance, Project/quarantine isolation, explicit context budgets, and rebuildability.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Execute real filesystem/process/Git/runtime/network/model/browser/database/retrieval/workspace work through replaceable adapters with Task-derived validation.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 28/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Create ContextManifest and ContextReceipt binding exact Task/Run/Node, included/excluded refs, Project/Engine Knowledge, Run state, tool outputs, retrieval scope, data/egress policy, token budget and content digest.

  - Implement source Artifact -> versioned extraction/chunking -> embedding -> index with exact source/chunker/model/runtime provenance; indexes are derived Cache.

  - Search must prefilter Project/source scope; optional rerank preserves candidate identity and ModelCalls.

  - Source revalidation prevents stale index activation; build->verify->activate keeps old valid index on failed replacement.

  - Context over-budget handling is explicit: exclusion/reduction evidence or CONTEXT_LIMIT, never silent truncation.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Create ContextManifest and ContextReceipt binding exact Task/Run/Node, included/excluded refs, Project/Engine Knowledge, Run state, tool outputs, retrieval scope, data/egress policy, token budget and content digest.

  - Implement source Artifact -> versioned extraction/chunking -> embedding -> index with exact source/chunker/model/runtime provenance; indexes are derived Cache.

  - Search must prefilter Project/source scope; optional rerank preserves candidate identity and ModelCalls.

  - Source revalidation prevents stale index activation; build->verify->activate keeps old valid index on failed replacement.

  - Context over-budget handling is explicit: exclusion/reduction evidence or CONTEXT_LIMIT, never silent truncation.

  REQUIRED INTERFACES

  - ContextManifest

  - ContextReceipt

  - RetrievalIndex

  - RetrievalReceipt

  - chunker/index/search/rerank services

  DATA / STATE CHANGES

  - Derived index/version/cache plus durable context/retrieval receipts.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Compile deterministic context and receipt.

  - Project Beta and quarantine hostile source never appear.

  - Index build/search/rerank with provenance.

  - Source changes during build -> stale/not activated.

  - Delete index/cache -> authoritative Memory/source survive and index rebuilds.

  - Budget overflow records exclusions/reduction.

  KPI

  - cross_project_retrieval_results=0

  - quarantine_retrieval_results=0

  - chunks_without_source_provenance=0

  - stale_indexes_activated=0

  - silent_context_truncations=0

  - cache_loss_causes_memory_loss=0

  RESTORED LONG-FORM REQUIREMENTS

  CONTEXT IS A COMPILED EXECUTION OBJECT

  Do not dump all memory/source into every model call.

  Compile only permitted context for exact Task/Node.

  Conceptual flow:

  Task + Node

  -> Context Requirements

  -> permitted explicit inputs

  -> Project Knowledge

  -> applicable Engine Knowledge

  -> Run state

  -> retrieval evidence

  -> Tool outputs

  -> budget/admission

  -> ContextManifest

  -> Context content object

  -> ContextReceipt

  CONTEXT MANIFEST

  Support fields equivalent to:

  - manifest ID;

  - Project/Task revision/Run/Graph/Node;

  - objective/input contract refs;

  - explicit input refs;

  - Project Knowledge refs;

  - Engine Knowledge refs;

  - Run refs;

  - retrieval scope;

  - Tool output refs;

  - data/egress policy;

  - context budget;

  - reduction policy;

  - deterministic manifest digest.

  Do not embed route/provider facts unless required semantically.

  CONTEXT RECEIPT

  Receipt describes exactly what actually reached model/tool:

  - manifest ID/digest;

  - context ContentRef/digest;

  - included refs;

  - excluded refs;

  - retrieval refs;

  - tool refs;

  - exact/estimated token count + source;

  - reduction evidence;

  - created_at.

  Significant ModelCall should reference ContextReceipt.

  Do not store giant prompt text directly in DB rows.

  CANONICALIZATION

  Deterministic ordering for set-like refs, stable serialization, no locale dependence. Reject malformed/duplicate refs as appropriate.

  PROJECT / QUARANTINE ISOLATION

  Alpha context cannot include Beta:

  - ProjectKnowledge;

  - Artifact;

  - Run Memory;

  - retrieval chunks;

  - Tool outputs.

  Normal Context Compiler must have no raw quarantine API path.

  Use hostile quarantine fixture and prove absence.

  RETRIEVAL PIPELINE

  Derived:

  authoritative source

  -> extract

  -> chunk

  -> embed

  -> index

  Every chunk retains:

  - Project;

  - source Artifact ID;

  - source digest/revision;

  - chunker version;

  - ordinal/offset;

  - chunk digest;

  - index version;

  - embedding implementation/runtime.

  RETRIEVAL INDEX

  Versioned RetrievalIndex with:

  - Project/source scope;

  - index/chunker version;

  - embedding capability/implementation/runtime;

  - dimension/metric;

  - BUILDING/READY/STALE/FAILED;

  - timestamps.

  Index is derived/cache-like.

  Deleting it cannot delete source truth.

  BUILD -> VERIFY -> ACTIVATE

  Build replacement index separately.

  If replacement fails, keep current READY index.

  If source changes during build, replacement must not activate current.

  SEARCH

  Scope comes from Project/Task/ContextManifest.

  Model/query cannot widen scope.

  Prefilter Project/source/current index before materializing candidates.

  Bound candidate count.

  EMBEDDING

  Use P2-06.

  Validate finite vectors, dimension, cardinality, exact deployment/runtime.

  RERANK

  Optional P2-06 rerank.

  Preserve candidate-set identity, reranker identity, order/scores, request receipt.

  Reranker cannot add out-of-scope candidates.

  RETRIEVAL RECEIPT

  Persist query ref, scope, index refs, candidates, reranked refs, embedding/reranker identities, scores, exact Run/Node.

  SOURCE REVALIDATION

  Around external embedding/rerank: bind source digest before; revalidate after if currentness required.

  Changed source -> stale/rebuild, no current activation.

  CONTEXT BUDGET

  Do not silently truncate.

  When over budget:

  - exclude according to explicit policy;

  - reduce/summarize only if allowed;

  - record exclusion/reduction evidence;

  - if required content cannot fit, return CONTEXT_LIMIT/BLOCKED.

  Never silently drop authority-critical requirements.

  TOKEN COUNT

  Exact tokenizer count when available, otherwise clearly labelled estimate.

  Do not call byte/4 exact.

  CACHE

  Chunks/embeddings/indexes/parses are rebuildable.

  Delete them: Project/Engine Memory and source Artifacts remain; retrieval rebuilds.

  CONCURRENCY / CANCEL

  Independent source ingestion/indexing can run concurrently.

  Cancel partial build -> index not READY.

  TEST MATRIX

  Cover Manifest/Receipt/digests; Alpha/Beta; hostile quarantine; ingest/chunk/embed; invalid embedding; source changes during build; failed replacement preserves old READY; index deletion/rebuild; scoped search; rerank validity; duplicate relative-path source roots; explicit context over-budget exclusions/reduction; no silent truncation; concurrent indexing; cancellation; ModelCall link.

  USEFUL EVIDENCE — NON-GATING

  - Every significant model-visible context can be explained by exact receipts; retrieval remains derived and Project-scoped.

  DELIVERABLES

  - Real implementation source and task-scoped tests; schema/migrations/config only when this prompt requires them.

  - Durable evidence/Artifacts required by the task.

  - A coherent commit in clean Biella history when repository write access is available and the implementation is complete.

  EVIDENCE TO REPORT

  - Exact commands/tests and pass/fail counts.

  - Exact files/modules/migrations/interfaces changed.

  - Observed KPI values and REAL/REFERENCE/MOCK/NOT_RUN classifications.

  - Exact source commit, result commit/tree, known limitations, unresolved facts, and next dependency.

  Use this result block:

  PROMPT: 29/51 - P2-10

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

  - Continue dependency-safe productive work when useful. Continue with the next dependency-safe task when useful.

  - Leave the repository/worktree in an understood state and report any intentional dirty/uncommitted files.

  - The next prompt must verify this handoff from actual repository state before editing.

```
