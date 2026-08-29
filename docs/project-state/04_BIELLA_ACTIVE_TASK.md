# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P3-01
  global_number: 32
  phase: P3
  title: Software Engineering Production Pack
  state: READY_AFTER_P2_12_DURABLE_CLOSE
  exact_prompt:
    title: 32_P3-01_Software_Engineering_Production_Pack.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P3/32_P3-01_Software_Engineering_Production_Pack.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P3/32_P3-01_Software_Engineering_Production_Pack.md.docx
    drive_id: 1KqL3RzBspIr8HVFtuoFfS5ew1hwVLSOIhMMimuf-9OE
    local_docx_sha256: b5d3d83392c7d1546641f889673514c450ce5c3309015b58bfeb8ce44d3aecd9
    live_drive_exported_docx_sha256: 8b96eaa564b2957e06e816f27e465acb29f946bbd9d1d8ae881575d9e1061052
    canonical_text_sha256: 02bbdef4cfa4b965ddbf3ec61448a59c72961129eb325ff7cc5c02ea645b5ffd
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P2-12
    result_commit: 575ff0683677234f4a8ff41e3eb703d4ea31112f
    result_tree: 758f7a1e2bc67d7925307d5146fcdf4b6f52b046
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_type_build_installed_and_full_regression: VERIFIED
  numbered_successor: P3-02

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P3_01_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_Capability_Task_Project_Run_Graph_Node_Artifact_ContentRef_Git_Workspace_Process_Model_Context_Validation_Resource_and_quarantine_firewall_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P3_02_or_later_prompt_bodies_before_P3_01_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_Artifact_ContentRef_ModelCall_ToolCall_Event_ResourceAllocation_Workspace_Validation_and_managed_runtime_identity
    - P1_ContentRef_object_storage_Project_Engine_Run_memory_graph_event_scheduler_routing_call_ledger_and_checkpoint_contracts
    - P2_adapter_execution_isolation_retrieval_workspace_validation_fencing_durability_and_quarantine_firewall_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |
  PROMPT 32/51 - P3-01

  TITLE

  Software Engineering Production Pack

  PHASE

  P3 - Production capability packs

  GOAL

  Prove real software production on the universal substrate: inspect exact repositories, diagnose real failures, make bounded changes, test/build/run when required, and preserve exact candidate identities.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Prove the same kernel can produce real software, web, game, 3D, media, rendering, VFX, and packages without domain-specific kernel redesign.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 31/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Register software.inspect/search/architecture/engineer/modify/debug/refactor/test/build/run/profile/package/validate capabilities as pack data.

  - Reuse Git/Workspace/Process/Model/Context/Validation adapters; do not create a second coding-agent system.

  - Bind exact base commit/tree, preserve unrelated dirty work, use focused source retrieval/context and task-scoped candidate changes.

  - For bugs, reproduce/inspect evidence before redesign; use TDD where useful.

  - Tests/build/runtime claims require observed outputs; independent checks may run concurrently.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Register software.inspect/search/architecture/engineer/modify/debug/refactor/test/build/run/profile/package/validate capabilities as pack data.

  - Reuse Git/Workspace/Process/Model/Context/Validation adapters; do not create a second coding-agent system.

  - Bind exact base commit/tree, preserve unrelated dirty work, use focused source retrieval/context and task-scoped candidate changes.

  - For bugs, reproduce/inspect evidence before redesign; use TDD where useful.

  - Tests/build/runtime claims require observed outputs; independent checks may run concurrently.

  REQUIRED INTERFACES

  - Software ProductionPack descriptor

  - software capability/recipe/validator registrations

  DATA / STATE CHANGES

  - Project-specific software config remains Project data.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Real repository inspect -> bounded change -> failing evidence -> repair -> focused tests -> build/runtime when applicable -> exact candidate commit/tree.

  - Worker loss retains captured candidate/completed tests.

  - Project-specific framework/conventions do not become Engine defaults.

  KPI

  - source_changes_without_exact_base=0

  - unrelated_source_changes=0

  - tests_claimed_PASS_without_execution=0

  - build_claims_without_output=0

  - candidate_work_lost_after_recoverable_failure=0

  - domain_specific_kernel_changes=0

  RESTORED LONG-FORM REQUIREMENTS

  SOFTWARE PACK, NOT A SECOND CODING ARCHITECTURE

  Implement a production pack registered on the universal P0/P1/P2 substrate.

  Conceptual pack:

  ProductionPack

  pack_id = software

  version

  capability_definitions

  graph_recipe_refs

  validator_refs

  artifact_roles

  adapter bindings

  resource profiles

  Expected domain-specific kernel modifications: 0.

  Do not create SoftwareTask, SoftwareRun, CodeAgentManager, or a permanent coding-agent hierarchy.

  CAPABILITIES

  Register extensible capabilities equivalent to:

  - software.inspect;

  - software.search;

  - software.architecture;

  - software.engineer;

  - software.modify;

  - software.debug;

  - software.refactor;

  - software.test;

  - software.build;

  - software.run;

  - software.profile;

  - software.package;

  - software.validate.

  Language/framework-specific implementations may register beneath these semantics without changing kernel.

  EXACT SOURCE

  Software Task consumes exact RepositoryRef, base commit/tree, source Artifacts, requirements, Project architecture/acceptance.

  Never mutate against ambiguous mutable source when reproducibility matters.

  INSPECTION

  Collect only relevant:

  - repository identity;

  - commit/tree/status;

  - file structure;

  - language/toolchain/build/package manager;

  - tests;

  - runtime entry points;

  - architecture relevant to Task.

  Use Git/Filesystem/Context/Retrieval.

  Do not dump entire repository into a model by default.

  DEBUGGING

  For defect work:

  1.  inspect actual failure evidence;

  2.  reproduce when feasible;

  3.  identify smallest root defect/boundary;

  4.  implement bounded change in candidate Workspace;

  5.  run affected validation;

  6.  repair failures caused by change;

  7.  preserve unrelated behavior.

  Do not redesign before understanding the failure.

  TDD

  When feature/bug behavior benefits:

  - add failing test;

  - observe correct failure;

  - implement minimal change;

  - observe pass.

  Do not force TDD onto tasks where it provides no value.

  CANDIDATE WORK

  Use P2 Workspace.

  Preserve:

  - base commit/tree;

  - changed files;

  - candidate diff/tree/commit;

  - generated files;

  - tests/build receipts.

  Do not mutate protected source directly unless Task authorizes Project write.

  DYNAMIC GRAPH

  Small Task may be: inspect -> modify -> test.

  Large Task may include parallel analysis/build/static/runtime.

  Do not force plan/coder/critic/validator sequence.

  TEST DISCOVERY / REGRESSION

  Prefer:

  1.  focused affected tests;

  2.  broader regression at sensible completion boundary.

  Run full suite when Task/Project requires it.

  Record exact candidate identity and test command/tool.

  Never claim pass without observed execution.

  BUILD

  Bind exact candidate + toolchain/runtime/config.

  Exit 0 is insufficient if required build Artifact absent.

  RUNTIME

  If requested deliverable is working CLI/service/app, execute exact output and observe required behavior.

  Build success alone is not runtime proof.

  REFACTOR

  Refactor preserves external behavior unless Task explicitly changes behavior.

  No unrelated cleanup.

  DEPENDENCIES / MIGRATIONS

  Use existing package manager/lockfile.

  Do not switch frameworks/package manager without requirement.

  Creating migration file does not authorize executing production DB migration.

  PERFORMANCE

  Optimization work: baseline -> profile -> change -> remeasure.

  No "looks faster" claim.

  CONCURRENCY

  Independent checks/test partitions can run concurrently under scheduler.

  No global software worker.

  RECOVERY

  Captured Workspace/candidate/tests/build outputs survive model/worker/process loss.

  Do not repeat completed valid work solely due to worker failure.

  ENGINE KNOWLEDGE

  Software Run output remains Project/Run evidence until explicit knowledge promotion.

  Project architecture/conventions stay Project Memory.

  REAL END-TO-END TASK

  Use at least one real repository:

  - inspect;

  - bounded requested change;

  - actual modification;

  - relevant tests;

  - build if repository supports;

  - runtime if required;

  - exact candidate source/commit.

  Inject a controlled failure/failing test, diagnose from evidence, repair, rerun.

  Do not use only mocked code strings.

  PROJECT ISOLATION

  At least two repository Projects where practical; prove no cross-source/context/preferences.

  KPI

  No ambiguous base source, unrelated source changes, unexecuted PASS claims, build/runtime overclaims, lost recoverable candidate, globalized Project preferences, mandatory critic hierarchy, or domain-specific kernel changes.

  USEFUL EVIDENCE — NON-GATING

  - At least one real repository change is usable/tested and produced through normal Biella Task/Graph/Workspace/Artifact/Validation systems.

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

  PROMPT: 32/51 - P3-01

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
