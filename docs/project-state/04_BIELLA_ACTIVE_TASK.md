# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P3-02
  global_number: 33
  phase: P3
  title: Web Application Production Pack
  state: READY_AFTER_P3_01_DURABLE_CLOSE
  exact_prompt:
    title: 33_P3-02_Web_Application_Production_Pack.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P3/33_P3-02_Web_Application_Production_Pack.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P3/33_P3-02_Web_Application_Production_Pack.md.docx
    drive_id: 1tSP2q6J16nkag6m5j2rmLWIJRcKj9MncuMqriiio7sQ
    local_docx_sha256: 90f15637b5cd8922e2a6037faee4b59d65411684d41479d4662f1d3b0e0bf7ca
    live_drive_exported_docx_sha256: 3f360a5503541418cc7ac9709ffc9c13e942adaab0ae4d7279f0bf0ec32db838
    canonical_text_sha256: 387b7431659a466cee56f028edf94eb48522cb18467c5df1a5077b4b93464518
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P3-01
    result_commit: d1c578a467fb555835458c8ef42eb8cf31cfbcb4
    result_tree: 7ba19f32a3980f004f56f3c869cda4b0a30fedd6
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_type_build_installed_and_full_regression: VERIFIED
  numbered_successor: P3-03

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P3_02_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_ProductionPack_Software_Git_Workspace_Process_HTTP_Browser_PostgreSQL_Context_Validation_Artifact_Project_Resource_and_quarantine_firewall_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P3_03_or_later_prompt_bodies_before_P3_02_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_Artifact_ContentRef_ModelCall_ToolCall_Event_ResourceAllocation_Workspace_Validation_and_managed_runtime_identity
    - P1_ContentRef_object_storage_Project_Engine_Run_memory_graph_event_scheduler_routing_call_ledger_and_checkpoint_contracts
    - P2_adapter_execution_isolation_retrieval_workspace_validation_fencing_durability_and_quarantine_firewall_contracts
    - P3_01_provider_neutral_ProductionPack_Software_pack_exact_repository_candidate_build_runtime_provenance_recovery_and_Project_isolation_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |
  PROMPT 33/51 - P3-02

  TITLE

  Web Application Production Pack

  PHASE

  P3 - Production capability packs

  GOAL

  Build and validate real frontend/backend/full-stack web applications while framework, design system, database, runtime, and hosting remain Project/tool choices.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Prove the same kernel can produce real software, web, game, 3D, media, rendering, VFX, and packages without domain-specific kernel redesign.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 32/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Register web.inspect/frontend/backend/fullstack/component/route/api/build/run/test/browser_validate/performance/accessibility/package.

  - Discover actual framework/build/runtime from exact source instead of historical assumptions.

  - Reuse Software pack plus HTTP/Browser/PostgreSQL when applicable.

  - Separate build, live runtime, HTTP, browser interaction, visual, performance, and accessibility evidence according to Task.

  - Preserve Project visual/brand requirements and secrets; no universal React/CSS/DB/hosting preference.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Register web.inspect/frontend/backend/fullstack/component/route/api/build/run/test/browser_validate/performance/accessibility/package.

  - Discover actual framework/build/runtime from exact source instead of historical assumptions.

  - Reuse Software pack plus HTTP/Browser/PostgreSQL when applicable.

  - Separate build, live runtime, HTTP, browser interaction, visual, performance, and accessibility evidence according to Task.

  - Preserve Project visual/brand requirements and secrets; no universal React/CSS/DB/hosting preference.

  REQUIRED INTERFACES

  - Web ProductionPack descriptor

  - web graph recipes/validators

  DATA / STATE CHANGES

  - Web framework/design/database targets remain Project-scoped.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Real app inspect/modify/test/build/start; HTTP and browser validate live exact candidate.

  - Console/runtime failures captured when required.

  - Optional DB and accessibility/performance checks.

  - Browser/runtime crash recovery retains source/build.

  - Two Projects with different frameworks/configs coexist.

  KPI

  - framework_specific_kernel_fields=0

  - build_only_claimed_runtime_success=0

  - browser_validation_without_live_candidate=0

  - project_design_rules_globalized=0

  - database_assumption_globalized=0

  - cross_project_web_leaks=0

  RESTORED LONG-FORM REQUIREMENTS

  WEB PACK REUSES SOFTWARE + P2

  Implement web production through the same kernel/Workspace/Git/Process/HTTP/Browser/DB/Validation stack.

  Do not add a universal preferred:

  - React/Vue/Svelte/etc.;

  - backend framework;

  - CSS system;

  - database;

  - JS runtime;

  - hosting provider.

  Discover Project technology from exact source.

  CAPABILITIES

  Register:

  - web.inspect;

  - web.frontend;

  - web.backend;

  - web.fullstack;

  - web.component;

  - web.route;

  - web.api;

  - web.database_integrate;

  - web.build;

  - web.run;

  - web.test;

  - web.browser_validate;

  - web.performance;

  - web.accessibility;

  - web.package.

  FRAMEWORK DISCOVERY

  Inspect exact repository commit/tree for:

  - framework/runtime;

  - package manager;

  - build config;

  - routing;

  - frontend/backend structure;

  - tests;

  - DB dependencies;

  - environment conventions;

  - entrypoint.

  Repository evidence beats old Project assumptions.

  DESIGN AUTHORITY

  Visual/UI requirements come from Project Memory/Artifacts/approved references/Task.

  Biella does not apply its own generic web style.

  FRONTEND

  Support real component/page/style/state/data modifications using current framework.

  Do not rewrite framework without Task.

  BACKEND

  Support route/service/storage/auth/background logic according to Project architecture.

  Do not universally require REST/GraphQL/SQL.

  DYNAMIC GRAPH

  Representative: inspect -> parallel frontend/backend analysis -> candidate -> parallel tests/build/static -> runtime -> browser validation -> final Artifact.

  Remove branches that Task does not need.

  RUNTIME

  Start actual candidate through Process/IsolatedRuntime.

  Capture endpoint/port/runtime/logs/health.

  Do not claim "works" from build only.

  HTTP

  Use P2 HTTP adapter for API/health validation against exact live candidate.

  BROWSER

  Use live P2 browser for:

  - page load;

  - expected content;

  - navigation;

  - interaction/forms;

  - screenshot;

  - console/runtime errors;

  - visual checks when required.

  Screenshot alone is not proof of behavior.

  CONSOLE / NETWORK ERRORS

  Capture page errors/unhandled exceptions/failed network requests where Task requires clean runtime.

  Do not fail on irrelevant known third-party warnings unless Project criteria say so.

  DATABASE

  PostgreSQL only if Project uses it.

  Migrations require explicit Task authority and preferably test/staging DB.

  Never auto-run production migrations.

  SECRETS

  Do not put API/DB/session secrets into source, prompt, Event, or Artifact except intended secure placeholder/config refs.

  ACCESSIBILITY

  If required, run explicit semantic/keyboard/automated checks.

  Do not claim complete accessibility certification from one automated scan.

  PERFORMANCE

  Measure Project-defined latency/bundle/server/memory requirements.

  No global threshold.

  SCREENSHOTS

  Bind viewport, browser/version, URL, exact candidate identity.

  Compare against Project references when required.

  PACKAGE

  Produce real static/server/container/package output when requested.

  Do not deploy externally unless authorized.

  CONCURRENCY / RECOVERY

  Frontend/backend tests/build/accessibility/static can overlap.

  Browser crash does not lose source/build/test.

  Runtime crash reruns bounded runtime step.

  MULTI-PROJECT NEUTRALITY

  Project A React + PostgreSQL; Project B Svelte + no DB (or equivalent) should both use same pack/kernel without global preference.

  REAL INTEGRATION

  At least one runnable app: inspect -> modify -> test -> build -> start -> HTTP -> browser -> final package.

  Inject a defect and diagnose actual evidence.

  USEFUL EVIDENCE — NON-GATING

  - A real web Artifact/package is built and observed running without introducing framework-specific kernel architecture.

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

  PROMPT: 33/51 - P3-02

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
