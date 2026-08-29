# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P2-06
  global_number: 25
  phase: P2
  title: Provider-Neutral Model Execution Adapter Layer
  state: READY_AFTER_P2_05_DURABLE_CLOSE
  exact_prompt:
    title: 25_P2-06_Provider_Neutral_Model_Execution_Adapter_Layer.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P2/25_P2-06_Provider_Neutral_Model_Execution_Adapter_Layer.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P2/25_P2-06_Provider_Neutral_Model_Execution_Adapter_Layer.md.docx
    drive_id: 1z1EOJUTNn_-jd115J539vG8Auq969p55rAHlR0AXg7k
    local_docx_sha256: 5cb09d89aeee964d91f1c60cf3dc43d163fd1b06577949ce0bf22b144b2ebbc2
    live_drive_exported_docx_sha256: 956b39840a6ee3f610ba1141f136f931cb341fc6e1a175581d7ce90a1e4edc8c
    canonical_text_sha256: e3313ab5763d202f4f4c7ffb060dbb0972e5b3012654ec48518c1af48f459926
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P2-05
    result_commit: de7864daff7fc9c8939872d0f45968a9f5d4b767
    result_tree: c12614081948b7af3222b53add7a090d27e6c173
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_type_build_installed_restart_and_full_regression: VERIFIED
  numbered_successor: P2-07

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P2_06_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_Project_Task_Run_Graph_NodeAttempt_Capability_Routing_ModelCall_ToolCall_ContentRef_Artifact_HTTP_Process_IsolatedRuntime_Resource_and_policy_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P2_07_or_later_prompt_bodies_before_P2_06_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_Artifact_ContentRef_ModelCall_ToolCall_Event_ResourceAllocation_and_managed_runtime_identity
    - P2_01_through_P2_04_real_execution_adapter_isolation_streaming_fencing_and_durability_contracts
    - P2_05_destination_egress_credential_redirect_streaming_timeout_cancellation_TLS_and_transport_evidence_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |-
  PROMPT 25/51 - P2-06

  TITLE

  Provider-Neutral Model Execution Adapter Layer

  PHASE

  P2 - Universal execution fabric

  GOAL

  Execute model.infer, retrieval.embed, and retrieval.rerank through replaceable hosted/local implementations while keeping provider SDKs outside Task/Run/kernel contracts.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Execute real filesystem/process/Git/runtime/network/model/browser/database/retrieval/workspace work through replaceable adapters with Task-derived validation.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 24/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Define ModelDeployment/implementation identity: provider/model/revision/artifact/endpoint, capabilities/modalities/context/tool support, resource/data characteristics, health.

  - Implement provider-neutral ModelAdapter infer/embed/rerank and at least two implementation classes (real+reference if needed).

  - Every call uses P1 ModelCall ledger; structured output and embedding/rerank results are validated, usage remains truthful/nullable.

  - Provider-native tool requests map into Biella ToolCall policy; unauthorized tools are not executed.

  - Cancellation/timeouts/late responses respect fences; hosted routes reuse HTTP egress/credential controls; local runtime binds exact generation/resource identity.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Define ModelDeployment/implementation identity: provider/model/revision/artifact/endpoint, capabilities/modalities/context/tool support, resource/data characteristics, health.

  - Implement provider-neutral ModelAdapter infer/embed/rerank and at least two implementation classes (real+reference if needed).

  - Every call uses P1 ModelCall ledger; structured output and embedding/rerank results are validated, usage remains truthful/nullable.

  - Provider-native tool requests map into Biella ToolCall policy; unauthorized tools are not executed.

  - Cancellation/timeouts/late responses respect fences; hosted routes reuse HTTP egress/credential controls; local runtime binds exact generation/resource identity.

  REQUIRED INTERFACES

  - ModelDeployment

  - ModelAdapter

  - infer/embed/rerank request/result

  - runtime health/identity

  DATA / STATE CHANGES

  - Deployment registry/health plus ModelCall output refs.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Text inference, structured valid/invalid output, timeout/cancel/late response.

  - Provider replacement without Task change.

  - Embedding dimension/count/NaN checks and source digest provenance.

  - Rerank candidate coverage/order validation.

  - Tool-call normalization and unauthorized tool rejection.

  - Context limit and egress denial.

  KPI

  - Task_contract_changes_between_providers=0

  - provider_sdk_types_in_kernel=0

  - significant_model_calls_missing_ledger=0

  - fabricated_usage=0

  - malformed_outputs_treated_success=0

  - egress_violating_model_calls=0

  RESTORED LONG-FORM REQUIREMENTS

  MODEL DEPLOYMENT REGISTRY

  Represent model deployments separately from semantic capabilities and providers.

  Conceptual ModelDeployment should capture:

  - deployment ID;

  - provider/adapter;

  - model identity/name;

  - exact revision/Artifact where known;

  - endpoint/runtime ref;

  - supported capabilities;

  - modalities;

  - context limits;

  - structured-output support;

  - tool support;

  - required Resources for local;

  - health/current availability;

  - metadata/freshness.

  Do not pretend a mutable hosted alias has an exact revision if provider does not expose one.

  MODEL ADAPTER

  Provide provider-neutral operations equivalent to:

  infer(request)

  embed(request)

  rerank(request)

  health(deployment)

  cancel(request)

  describeRuntime()

  Not every deployment must support every operation.

  REQUEST / RESULT

  Model requests bind:

  - Project/Task/Run/Graph/Node;

  - Capability;

  - exact deployment;

  - ContextReceipt/input refs;

  - generation parameters;

  - output contract/schema;

  - timeout/cancellation.

  Results bind:

  - exact call ledger record;

  - output ContentRef/Artifact;

  - usage/timing;

  - finish/status;

  - model/runtime identity.

  MULTIPLE IMPLEMENTATION CLASSES

  P2-06 must prove provider neutrality with at least two implementation classes.

  If only one real provider is available:

  - real adapter A;

  - deterministic/reference adapter B.

  Report second as REFERENCE, not REAL.

  Do not create fake provider claims.

  HOSTED VS LOCAL

  Hosted implementation may use P2-05 HTTP.

  Local implementation may use process/isolated runtime and Resource identity.

  Both implement the same semantic model adapter contracts.

  STRUCTURED OUTPUT

  When Task requires schema:

  - request structured output where adapter supports;

  - validate result against exact schema/output contract;

  - malformed model output is not success merely because provider call succeeded.

  EMBEDDINGS

  Validate:

  - output count equals input count;

  - vector dimensions expected/current deployment metadata;

  - all values finite;

  - exact deployment/runtime provenance.

  Reject NaN/Infinity, missing vectors, dimension drift without explicit new identity.

  RERANK

  Validate:

  - every returned candidate refers to an input candidate;

  - no duplicate/missing IDs where contract forbids;

  - scores finite;

  - ordering complete/valid;

  - exact reranker deployment identity.

  PROVIDER TOOL CALLS

  Provider-native tool-call proposals are normalized to Biella semantics.

  A model may propose: tool name + structured args.

  Biella must:

  1.  map to permitted Tool Capability;

  2.  enforce Task/Project authority;

  3.  execute via Tool adapter;

  4.  persist ToolCall;

  5.  feed result back if strategy requires.

  Provider-native tool calling does not let model execute arbitrary host tools.

  CONTEXT LIMIT

  Detect context/token limit before/at call where possible and return explicit failure.

  Do not silently drop required context.

  P2-10 will implement richer context compilation.

  CANCELLATION / TIMEOUT

  Cancellation should cancel hosted/local work where supported, release Resources, and reject late stale result through execution fencing.

  EGRESS

  Private Project data may be sent only to permitted provider/destination under Project/Task policy.

  A capable model is ineligible if egress policy forbids it.

  HEALTH / AVAILABILITY

  Temporary provider/model outage affects current implementation availability, not semantic Capability.

  TESTS

  - real/reference infer;

  - same model.infer Task works across two adapter classes;

  - exact deployment identity;

  - structured valid output;

  - malformed structured output rejected;

  - embedding finite/dimension/cardinality checks;

  - rerank valid and invalid cases;

  - provider tool proposal -> Biella ToolCall;

  - unauthorized tool proposal rejected;

  - context limit;

  - provider unavailable;

  - cancellation/timeout;

  - stale generation result rejected;

  - egress denied;

  - local runtime Resource identity where implemented;

  - ModelCall ledger complete;

  - no provider SDK type in kernel.

  P2-06 establishes model execution as one replaceable capability implementation layer, not Biella architecture authority.

  USEFUL EVIDENCE — NON-GATING

  - Multiple model implementation classes share one semantic contract and exact evidence; provider/model choice remains routing data.

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

  PROMPT: 25/51 - P2-06

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
