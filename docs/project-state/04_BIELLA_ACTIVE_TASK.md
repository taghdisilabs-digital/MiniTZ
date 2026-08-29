# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P2-07
  global_number: 26
  phase: P2
  title: Durable Provider-Neutral Browser Automation Adapter
  state: READY_AFTER_P2_06_DURABLE_CLOSE
  exact_prompt:
    title: 26_P2-07_Durable_Provider_Neutral_Browser_Automation_Adapter.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P2/26_P2-07_Durable_Provider_Neutral_Browser_Automation_Adapter.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P2/26_P2-07_Durable_Provider_Neutral_Browser_Automation_Adapter.md.docx
    drive_id: 1jgWIpcDZVon6xUZWKDVnh7eIkz0sDKQ9udQiYDfn0iI
    local_docx_sha256: 0631c9ccb7ee33838c944891a2ab9dc98eefdaced2408d5ac482b602c40f3d1c
    live_drive_exported_docx_sha256: a1dd83bb583a0339f36daba8a1f74bbc97947ebbf798084574b393881662019a
    canonical_text_sha256: 5e8c7762fbef9af2998351a61402eb8a839207cb8aa1d4e9010aee329661a196
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P2-06
    result_commit: 35edc349447868fd0be4250d5c071579df5e9650
    result_tree: 5c1883b17a50117530f4cea9e1df1fc2d30e990c
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_type_build_installed_restart_live_provider_and_full_regression: VERIFIED
  numbered_successor: P2-08

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P2_07_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_Project_Task_Run_Graph_NodeAttempt_Capability_Routing_ToolCall_ContentRef_Artifact_HTTP_Filesystem_Process_IsolatedRuntime_Resource_Event_and_policy_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P2_08_or_later_prompt_bodies_before_P2_07_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_Artifact_ContentRef_ModelCall_ToolCall_Event_ResourceAllocation_and_managed_runtime_identity
    - P2_01_through_P2_04_real_execution_adapter_isolation_streaming_fencing_and_durability_contracts
    - P2_05_destination_egress_credential_redirect_streaming_timeout_cancellation_TLS_and_transport_evidence_contracts
    - P2_06_provider_neutral_model_deployment_execution_health_tool_policy_fencing_and_provenance_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |-
  PROMPT 26/51 - P2-07

  TITLE

  Durable Provider-Neutral Browser Automation Adapter

  PHASE

  P2 - Universal execution fabric

  GOAL

  Operate real browser sessions/pages/actions while browser state remains ephemeral execution resource and all meaningful outputs/side effects remain durable Biella evidence.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Execute real filesystem/process/Git/runtime/network/model/browser/database/retrieval/workspace work through replaceable adapters with Task-derived validation.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 25/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Register browser open/navigate/inspect/extract/click/type/select/upload/download/screenshot/evaluate/wait/submit capabilities.

  - Define BrowserAdapter plus session/page generation identity so stale pre-crash actions/results cannot affect replacement sessions.

  - Downloads/screenshots/extractions persist as Artifacts; uploads come only from authorized refs/roots.

  - Read-only vs external mutation follows Task side-effect authority; browser egress cannot bypass HTTP/Project policy.

  - Secrets/cookies stay out of ordinary evidence; browser crash/session loss preserves completed durable work.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Register browser open/navigate/inspect/extract/click/type/select/upload/download/screenshot/evaluate/wait/submit capabilities.

  - Define BrowserAdapter plus session/page generation identity so stale pre-crash actions/results cannot affect replacement sessions.

  - Downloads/screenshots/extractions persist as Artifacts; uploads come only from authorized refs/roots.

  - Read-only vs external mutation follows Task side-effect authority; browser egress cannot bypass HTTP/Project policy.

  - Secrets/cookies stay out of ordinary evidence; browser crash/session loss preserves completed durable work.

  REQUIRED INTERFACES

  - BrowserAdapter

  - BrowserSessionIdentity

  - BrowserPageRef

  - structured BrowserAction

  DATA / STATE CHANGES

  - Session/runtime refs and durable ToolCall/Artifact receipts.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Navigate/inspect/extract/actions/screenshot.

  - Download exact digest; interrupted download rejected as complete.

  - Upload authorized Artifact; arbitrary host path rejected.

  - Read-only Task mutation rejected; authorized mutation gets durable receipt.

  - Session crash and generation replacement; stale result rejected.

  - Project/session/credential isolation.

  KPI

  - browser_session_loss_causes_Run_loss=0

  - download_without_ContentRef=0

  - external_side_effect_without_Task_authority=0

  - credential_leaks=0

  - stale_browser_generation_results_accepted=0

  - browser_provider_types_in_kernel=0

  RESTORED LONG-FORM REQUIREMENTS

  CAPABILITY SURFACE

  Register extensible capabilities equivalent to:

  browser.open

  browser.navigate

  browser.inspect

  browser.extract

  browser.click

  browser.type

  browser.select

  browser.upload

  browser.download

  browser.screenshot

  browser.evaluate

  browser.wait_for_condition

  browser.submit

  Do not make these a closed kernel enum. Future browser capabilities must register without changing Task/Run/Graph primitives.

  ADAPTER CONTRACT

  Implement a provider-neutral interface equivalent to:

  BrowserAdapter:

  createSession(spec)

  navigate(session, request)

  inspect(session, request)

  performAction(session, action)

  extract(session, request)

  captureScreenshot(session, request)

  upload(session, request)

  download(session, request)

  waitForCondition(session, request)

  cancel(session/request)

  closeSession(session)

  inspectSession(session)

  Implement at least one real browser implementation where current environment permits and a deterministic reference/test implementation where needed.

  Do not expose Playwright/Selenium/provider SDK objects in kernel contracts.

  SESSION GENERATION IDENTITY

  Persist runtime identity equivalent to:

  BrowserSessionIdentity:

  browser_adapter_id

  implementation_id

  browser_name

  browser_version

  runtime_version

  session_id

  executor/resource identity

  generation

  created_at

  Page refs include session/page/generation/current URL.

  A page/session ref is runtime state, not durable Project truth.

  If session generation 1 crashes and generation 2 replaces it, every late action/result from generation 1 is stale and rejected.

  SESSION LOSS

  After browser crash:

  - Run state survives;

  - completed ToolCalls survive;

  - downloaded Artifacts survive;

  - screenshots/extractions survive;

  - already confirmed external side-effect receipts survive;

  - incomplete current action fails/stales;

  - scheduler may start a new session.

  Do not reconstruct completed work from browser memory alone.

  EGRESS AND ORIGIN POLICY

  Navigation/upload/form submission must respect Project/Task data-egress policy.

  Browser reachability cannot bypass HTTP egress restrictions.

  When uploading Project-private data, validate destination/origin before transferring bytes.

  READ VS MUTATION

  Structured browser actions should declare side-effect class.

  READ_ONLY examples: navigate, inspect, screenshot, extract.

  EXTERNAL_SIDE_EFFECT examples: submit form, publish content, delete remote record, send message.

  A read-only Task cannot perform the latter.

  Do not create a universal human approval gate; enforce existing Task authority.

  DOM / EXTRACTION

  Inspection/extraction output should be:

  - bounded;

  - structured where practical;

  - bound to exact session/page/url/time;

  - persisted as ContentRef/Artifact when durable.

  Large DOM/snapshot -> Object Store, not giant database row.

  SCREENSHOT

  Screenshot result:

  - exact ContentRef;

  - Artifact;

  - ToolCall output ref;

  - viewport;

  - page identity;

  - URL;

  - timestamp;

  - browser implementation/runtime identity.

  Screenshot alone is not proof the requested interaction works unless validation says so.

  DOWNLOAD

  Required flow:

  authorized browser action

  → temporary controlled download

  → completion

  → digest

  → Object Store

  → Artifact

  → verification

  → durable success

  Temporary browser download path is not Artifact identity.

  Interrupted download cannot be accepted complete.

  UPLOAD

  Upload only:

  - authorized Artifact/ContentRef;

  - controlled FilesystemRoot.

  Reject arbitrary host path.

  Stream large uploads.

  STRUCTURED ACTION

  Use structured BrowserAction:

  - action_type;

  - target;

  - value_ref;

  - timeout;

  - expected pre/postcondition;

  - side-effect class.

  Avoid arbitrary JS when structured action exists.

  If browser.evaluate exists, treat as explicit bounded capability and do not turn browser JS into host execution privilege.

  WAIT

  Support bounded waits for:

  - selector;

  - URL;

  - DOM property;

  - network idle;

  - explicit event.

  Timeout remains timeout, not success.

  CREDENTIALS / COOKIES

  Credentials from secret refs.

  Do not persist password/token/cookie bytes in ordinary Events/ToolCalls.

  Browser profile/session storage is runtime-sensitive and not Project Memory.

  MODEL-GUIDED BROWSER

  Provider-native browser/computer action proposal:

  ModelCall -> proposed action -> Biella policy/tool validation -> BrowserAdapter -> ToolCall

  The model does not gain authority outside Task/Node policy.

  EVENTS

  Meaningful events may include:

  - BROWSER_SESSION_STARTED;

  - BROWSER_SESSION_REPLACED;

  - BROWSER_ARTIFACT_CREATED;

  - EXTERNAL_SIDE_EFFECT_RECORDED.

  Do not dump browser trace into Event Ledger.

  MANDATORY TEST MATRIX

  Cover session create/close/crash/replacement; navigation and redirects; egress denied; bounded inspect/extract; click/type/select; missing target; read-only mutation rejection; authorized mutation receipt; screenshot; exact download digest; interrupted download; upload Artifact; arbitrary path rejection; secret/cookie redaction; crash after completed download; resume with new session; model-proposed action validation; cross-Project session/Artifact denial.

  Target KPI includes: browser_session_loss_causes_Run_loss=0, stale_browser_generation_results_accepted=0, credential_leaks=0, unattributed_external_browser_mutations=0.

  USEFUL EVIDENCE — NON-GATING

  - Browser is a replaceable tool capability, not Run authority; session loss does not erase completed work.

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

  PROMPT: 26/51 - P2-07

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
