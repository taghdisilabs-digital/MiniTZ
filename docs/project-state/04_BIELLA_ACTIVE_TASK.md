# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P2-12
  global_number: 31
  phase: P2
  title: Task-Derived Validation and Evaluation Primitives
  state: READY_AFTER_P2_11_DURABLE_CLOSE
  exact_prompt:
    title: 31_P2-12_Task_Derived_Validation_and_Evaluation_Primitives.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P2/31_P2-12_Task_Derived_Validation_and_Evaluation_Primitives.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P2/31_P2-12_Task_Derived_Validation_and_Evaluation_Primitives.md.docx
    drive_id: 1g3eSGdIQLg8b-DZdAwKm5dhUHudKgtlsBcRuGlzzbgo
    local_docx_sha256: 446391617cd5df67ab6846d7e9970cc0e2b310969c37c727421a99e88207cd01
    live_drive_exported_docx_sha256: fa82c20776415c3e46740ab8c2f37c166706b9594b98fb258abe3722fd021da6
    canonical_text_sha256: 47c6b5724455cb8f0fb8adffe3fae16ccd1a69119a2df88bfc1ad5ce6c3df7e0
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P2-11
    result_commit: e29bf2ef8aef14879b54ed35193775573487b527
    result_tree: abbea75d558a399a9aed359e32e362adc184c22c
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_type_build_installed_and_full_regression: VERIFIED
  numbered_successor: P3-01

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P2_12_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_Task_Project_Run_Graph_Node_Artifact_ContentRef_Workspace_ModelCall_ToolCall_Event_capability_and_quarantine_firewall_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P3_01_or_later_prompt_bodies_before_P2_12_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_Artifact_ContentRef_ModelCall_ToolCall_Event_ResourceAllocation_Workspace_and_managed_runtime_identity
    - P1_ContentRef_object_storage_Project_Engine_Run_memory_graph_event_scheduler_routing_and_checkpoint_contracts
    - P2_01_through_P2_11_adapter_execution_isolation_retrieval_workspace_snapshot_fencing_durability_and_quarantine_firewall_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |
  PROMPT 31/51 - P2-12

  TITLE

  Task-Derived Validation and Evaluation Primitives

  PHASE

  P2 - Universal execution fabric

  GOAL

  Implement reusable validation/evaluation so exact outputs are accepted according to actual Task/Project requirements, not a universal review hierarchy, and produce clean metrics for P4 learning.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Execute real filesystem/process/Git/runtime/network/model/browser/database/retrieval/workspace work through replaceable adapters with Task-derived validation.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 30/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Compile ValidationPlan from exact subject refs, Task output/evidence/acceptance/risk/side effects and Project criteria; checks can be required/optional with explicit independence/success rules.

  - Define ValidationResult PASS/FAIL/INCONCLUSIVE/ERROR and EvaluationResult with explicit metric definitions/measurement sources.

  - Support deterministic schema/provenance/test/build/runtime/performance/security/visual validators through capabilities; model/tool validators use call ledger.

  - Exact subject digest/current Graph/fence revalidated before current acceptance; stale validator result becomes historical evidence.

  - Independent checks may run concurrently; failed validation does not create fixed global repair count.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Compile ValidationPlan from exact subject refs, Task output/evidence/acceptance/risk/side effects and Project criteria; checks can be required/optional with explicit independence/success rules.

  - Define ValidationResult PASS/FAIL/INCONCLUSIVE/ERROR and EvaluationResult with explicit metric definitions/measurement sources.

  - Support deterministic schema/provenance/test/build/runtime/performance/security/visual validators through capabilities; model/tool validators use call ledger.

  - Exact subject digest/current Graph/fence revalidated before current acceptance; stale validator result becomes historical evidence.

  - Independent checks may run concurrently; failed validation does not create fixed global repair count.

  REQUIRED INTERFACES

  - ValidationPlan

  - ValidationResult

  - EvaluationResult

  - validation requirement compiler/aggregator

  DATA / STATE CHANGES

  - Validation/evaluation evidence and subject bindings.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Minimal schema-only Task gets no invented critic.

  - Code tests/build with exact candidate; process exit 0 + missing Artifact is not PASS.

  - Runtime-required Task cannot substitute build-only evidence.

  - Independent validator enforced only when requested.

  - Validator outage -> ERROR, not candidate FAIL/PASS.

  - Stale candidate validation rejected; Project criteria isolated.

  KPI

  - tasks_forced_through_unrequired_validation=0

  - required_validation_skipped=0

  - validator_transport_error_marked_PASS=0

  - stale_validation_accepted=0

  - mandatory_global_validator_hierarchy=0

  - opaque_composite_scores=0

  RESTORED LONG-FORM REQUIREMENTS

  VALIDATION VS EVALUATION

  Keep explicit:

  VALIDATION — does this exact subject satisfy the Task contract?

  EVALUATION — how well did a subject/implementation/strategy perform under explicit metrics?

  Benchmark/evaluation score is not acceptance unless Task says so.

  CAPABILITIES

  Extensible validation:

  - schema;

  - deterministic;

  - test;

  - build;

  - runtime;

  - visual;

  - performance;

  - security;

  - provenance;

  - independent_reasoning.

  Evaluation:

  - quality;

  - performance;

  - cost;

  - reliability;

  - comparison.

  Not a closed kernel enum.

  VALIDATION PLAN

  Compile Task-derived ValidationPlan from: Task output contract + Project requirements + evidence/side-effect/risk requirements.

  Conceptual:

  - plan ID;

  - Project/Task/Run;

  - exact subject refs;

  - required checks;

  - optional checks;

  - independence requirements;

  - evidence requirements;

  - success rule;

  - digest.

  This is not a permanent global pipeline.

  MINIMAL TASK

  A Task may require only:

  - schema;

  - Artifact exists;

  - digest.

  Do not invent critic/independent model/repair loop.

  STRONG TASK

  If Task requires tests + runtime + security + independent reasoning, enforce them.

  Strength is Task-specific.

  VALIDATION RESULT

  Persist:

  ValidationResult

  validation_id

  plan

  Project/Task/Run

  exact subject refs

  capability

  implementation/runtime

  verdict

  findings refs

  evidence refs

  metrics

  timestamps

  Verdicts at minimum: PASS, FAIL, INCONCLUSIVE, ERROR.

  Critical: ERROR != FAIL.

  Validator provider unavailable means infrastructure error/inconclusive; it is not proof candidate is wrong.

  Tool transport success is not PASS.

  EXACT SUBJECT

  Bind exact Artifact digest/workspace receipt/Git tree/build/model result.

  Never validate "latest path" without exact identity.

  Subject change invalidates previous current validation.

  DETERMINISTIC CHECKS

  Use deterministic methods for schema/digest/parse/file existence/build output where possible.

  Do not use model simply because available.

  TEST VALIDATION

  Bind exact candidate, test command/tool identity, Workspace, ToolCall, output refs, pass/fail counts.

  Never reuse unrelated historical tests.

  BUILD

  Exit 0 + missing expected Artifact is not PASS.

  Bind exact toolchain/runtime and build Artifact.

  RUNTIME

  If Task requires real executable/runtime proof, build/typecheck/unit tests alone are insufficient.

  Run exact Artifact and preserve observable evidence.

  VISUAL

  Project supplies visual references/criteria.

  Vision model/tool may implement visual validation, bound to exact subject/reference/model runtime.

  No global Biella visual style.

  PERFORMANCE

  Metrics may include latency/FPS/throughput/memory/size/GPU.

  Threshold is Project/Task-specific; no global 60 FPS/4K/X ms rule.

  PROVENANCE / SECURITY

  Provenance validates source/derivation/runtime/tool/required receipts.

  Security capability remains extensible across secret scan/static/dependency/sandbox tests; no one mandatory scanner.

  INDEPENDENCE

  If Task requires independent validator, express exact dimensions: different deployment/model/tool/strategy.

  Do not globally require independence.

  GRAPH

  Validation may compile to productive VALIDATE Nodes only when required.

  Independent tests/security/etc can run concurrently.

  No fixed produce→critic→validator sequence.

  REPAIR

  Failure may:

  - fail Run;

  - create Graph revision;

  - create repair Node;

  - route alternative;

  - return result.

  No hardcoded repair count.

  AGGREGATION

  Deterministic success_rule, e.g. ALL_REQUIRED_PASS.

  Optional failure does not necessarily fail Task.

  Missing required validation cannot be silently ignored.

  STALE RESULT

  Before accepting ValidationResult current, revalidate Project/Task/Run/Graph/subject/fence/currentness.

  Late result for superseded subject -> Historical Evidence, not current acceptance.

  LEDGER

  Model validators -> ModelCall. Tool validators -> ToolCall. Events contain refs, not giant findings.

  EVALUATION RESULT

  Persist raw dimensions separately: quality, latency, cost, resource, reliability.

  If composite score exists, formula/weights/components explicit.

  Do not create one opaque "quality_score".

  TEST MATRIX

  Include:

  - schema-only minimal Task/no extra reviewer;

  - valid/invalid schema;

  - review=false/no validator ModelCall;

  - code tests pass/fail;

  - stale test evidence;

  - build output missing despite exit 0;

  - runtime-required Task;

  - independent validator required/same implementation rejection;

  - validator unavailable ERROR;

  - parallel checks;

  - Project-specific visual/performance criteria;

  - provenance wrong digest;

  - required evidence missing;

  - aggregation;

  - stale candidate;

  - model/tool ledger;

  - separate evaluation dimensions;

  - Project isolation.

  P2 INTEGRATION CLOSURE

  Run representative flow: Git source -> HTTP research -> Context/Retrieval -> model reasoning -> Workspace -> candidate change -> tests/build -> validation -> exact Artifact.

  Inject process failure, stale source, provider unavailable, Workspace recovery, validation failure.

  Verify completed durable work retained, no Project/quarantine leakage, no provider-specific kernel changes, and Task/Run/Graph unchanged.

  P2 exits READY_FOR_P3 only from observed evidence.

  USEFUL EVIDENCE — NON-GATING

  - P2 closes with real multi-adapter flow from exact Git source through context/model/workspace/build/test to validated final Artifact, with failures injected and durable work retained.

  DELIVERABLES

  - Real implementation source and task-scoped tests; schema/migrations/config only when this prompt requires them.

  - Durable evidence/Artifacts required by the task.

  - A coherent commit in clean Biella history when repository write access is available and the implementation is complete.

  EVIDENCE TO REPORT

  - P2 integration scenario and REAL/REFERENCE/MOCK/NOT_RUN classification per adapter.

  Use this result block:

  PROMPT: 31/51 - P2-12

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
