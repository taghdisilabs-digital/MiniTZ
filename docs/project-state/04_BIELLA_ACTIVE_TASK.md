# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P1-09
  global_number: 19
  phase: P1
  title: Capability, Model, Tool, and Compute Routing
  state: READY_AFTER_P1_08_DURABLE_CLOSE
  exact_prompt:
    title: 19_P1-09_Capability_Model_Tool_and_Compute_Routing.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P1/19_P1-09_Capability_Model_Tool_and_Compute_Routing.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P1/19_P1-09_Capability_Model_Tool_and_Compute_Routing.md.docx
    drive_id: 1lyJ-tC8_kUy5yYuMftmEcPeNjsIBu8DRbZIU0VBhKDU
    local_docx_sha256: fdcdaff2e616df3cffa0051299bc82c03b9a749075e530ba166a479c92ed3d04
    live_drive_exported_docx_sha256: fd5c9a66b64adf4ad93dee732be021251e891bfade947989aaf13ee1b8dfc979
    canonical_text_sha256: d145691200750438ce2ddb64749fef96d58b750e815ebe1903d2b0ce18a22e1d
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P1-08
    result_commit: ac5aca11af0866734862c709a537ad98b1ffb9d7
    result_tree: 282c46ffc1272adaa7ad4ca5c97104cb573f3f1a
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_functional_type_build_installed_restart_and_full_regression: VERIFIED
  numbered_successor: P2-01

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P1_09_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_Capability_Task_Node_Resource_Scheduler_policy_and_egress_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P2_01_or_later_prompt_bodies_before_P1_09_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_and_Resource_identity
    - P1_08_concurrent_scheduler_allocation_queue_metric_and_recovery_contracts
    - all_earlier_isolation_provenance_durability_and_quarantine_firewall_contracts

canonical_prompt_text: |-
  PROMPT 19/51 - P1-09

  TITLE

  Capability, Model, Tool, and Compute Routing

  PHASE

  P1 - Durable cognition + resources + routing

  GOAL

  Implement layered routing that resolves semantic Capability -> compatible implementation -> model/tool/runtime -> current compute/resource placement while preserving Project policy, egress, explainability, and deterministic fallback.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Make work resumable and observable, add memory scopes, call accounting, resource truth, concurrent scheduling, and provider-neutral routing.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 18/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Create CapabilityImplementation registry with adapter/provider/model/tool/runtime requirements only where applicable.

  - Hard constraints include capability/version/features, side effects, Project policy, egress, context/tool limits, health, and Resource fit.

  - Rank eligible implementations/resources using deterministic current evidence such as explicit Project preference, health, latency/cost hints, queue/load and locality.

  - Persist RoutingDecision with candidates, rejections/reasons, selected implementation/resource, ResourceSnapshot refs; scheduler revalidates before allocation.

  - No hardcoded local->H100->OpenAI or other historical sequence.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Create CapabilityImplementation registry with adapter/provider/model/tool/runtime requirements only where applicable.

  - Hard constraints include capability/version/features, side effects, Project policy, egress, context/tool limits, health, and Resource fit.

  - Rank eligible implementations/resources using deterministic current evidence such as explicit Project preference, health, latency/cost hints, queue/load and locality.

  - Persist RoutingDecision with candidates, rejections/reasons, selected implementation/resource, ResourceSnapshot refs; scheduler revalidates before allocation.

  - No hardcoded local->H100->OpenAI or other historical sequence.

  REQUIRED INTERFACES

  - CapabilityImplementation

  - implementation resolver

  - compute resolver

  - RoutingDecision

  - rejection reason codes

  DATA / STATE CHANGES

  - Implementation registry and durable route evidence.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Provider/model/resource replacement leaves Task unchanged.

  - Remote route rejected by egress policy even with credentials.

  - GPU shortage returns no-current-route/alternative without deleting Capability; route returns when hardware recovers.

  - New implementation with no history remains eligible.

  - Stable deterministic tie-break and structured reasons.

  KPI

  - Task_contract_changes_when_provider_changes=0

  - Capability_definition_changes_when_hardware_changes=0

  - egress_violating_routes=0

  - hard_constraint_bypasses=0

  - unexplained_routing_decisions=0

  - hardcoded_historical_fallback_sequences=0

  RESTORED LONG-FORM REQUIREMENTS

  ROUTING LAYERS

  Implement routing as separate decisions:

  required semantic Capability

  ↓

  compatible CapabilityImplementation

  ↓

  model/tool/runtime implementation selection

  ↓

  compute/resource placement

  Do not collapse these into a provider/model enum.

  CAPABILITY IMPLEMENTATION REGISTRY

  Represent deployable/executable implementations separately from semantic Capability.

  Conceptual fields:

  CapabilityImplementation

  implementation_id

  capability_ref/version

  implementation kind

  adapter/runtime ref

  compatible input/output/features

  hard requirements

  Project/data-policy characteristics

  current health/availability ref

  metadata/version

  Provider-specific fields should remain adapter metadata.

  HARD CONSTRAINTS FIRST

  Before ranking, reject candidates that fail:

  - Capability/version compatibility;

  - required modality/features;

  - Task Project/provider/tool restrictions;

  - data confidentiality/egress;

  - side-effect/runtime policy;

  - context/tool limits;

  - Resource fit;

  - current health/availability.

  A high historical score cannot override hard constraints.

  DETERMINISTIC P1 RANKING

  P4 learns routing later.

  P1 uses a simple deterministic explicit ranking based on current facts such as:

  - declared implementation priority;

  - exact compatibility;

  - current health;

  - Resource fit;

  - queue pressure;

  - static/current locality;

  - Project preference.

  Do not create learned opaque scoring.

  ROUTING DECISION EVIDENCE

  Persist a RoutingDecision/receipt containing:

  - requested Capability/Task/Node;

  - workload/input features needed for compatibility;

  - candidate implementations;

  - rejected candidates and structured reasons;

  - selected implementation;

  - selected/required Resource characteristics;

  - ranking factors/version;

  - timestamp/current Resource snapshot refs.

  This evidence is later used in P4.

  NO-ROUTE SEMANTICS

  If no current implementation fits: return an explicit result such as:

  - no eligible implementation;

  - Resource temporarily unavailable;

  - policy denied;

  - implementation unhealthy.

  Do not delete Capability or rewrite Task.

  FALLBACK

  Fallback may occur only among candidates that satisfy hard constraints.

  Do not hardcode historical chain such as: local -> H100 -> OpenAI.

  The available candidates are runtime registry data.

  COLD START

  A newly registered compatible implementation with no history must remain eligible under deterministic P1 rules.

  Do not require benchmark history to execute it.

  SCHEDULER REVALIDATION

  Routing chooses a candidate based on Resource observations that may become stale before execution.

  Scheduler/allocation must revalidate current fit/health before dispatch/finalization.

  RoutingDecision is evidence, not permanent Resource reservation.

  MODEL VS COMPUTE

  If model implementation can run on multiple Resources, model selection and compute placement remain separate.

  Changing GPU/worker should not require a new Task.

  TESTS

  - two implementations same Capability;

  - provider/model replacement without Task schema change;

  - best-ranked candidate rejected by egress -> next eligible;

  - Resource unavailable -> alternate Resource/implementation;

  - no route does not remove Capability;

  - new implementation with no history eligible;

  - structured rejection reasons;

  - model selection independent from compute placement;

  - scheduler revalidation catches changed Resource state;

  - Project Alpha restriction does not affect Beta globally;

  - no hardcoded provider/worker route chain.

  P1 exits when Tasks can remain semantic while current implementations/resources are selected dynamically.

  USEFUL EVIDENCE — NON-GATING

  - P2 adapters can plug in behind a provider-neutral route contract; P4 can later learn ranking without redesign.

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

  PROMPT: 19/51 - P1-09

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
