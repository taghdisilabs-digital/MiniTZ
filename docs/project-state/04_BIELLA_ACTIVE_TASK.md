# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P2-05
  global_number: 24
  phase: P2
  title: Universal HTTP/API Execution Adapter
  state: READY_AFTER_P2_04_DURABLE_CLOSE
  exact_prompt:
    title: 24_P2-05_Universal_HTTP_API_Execution_Adapter.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P2/24_P2-05_Universal_HTTP_API_Execution_Adapter.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P2/24_P2-05_Universal_HTTP_API_Execution_Adapter.md.docx
    drive_id: 11zmSVb23RA5InBxAVWCD_KAqHFn_vLtXrnuublFGvHQ
    local_docx_sha256: 85552c3db45994bf2f0fe3970d46085ea29d400bd15bc8550800b11851bb2e63
    live_drive_exported_docx_sha256: 897e74518ff56df57eb58c159241c2496103228e092d20245c0d20cbafdd3de4
    canonical_text_sha256: f9fc9032c1a8456167c5786127eff102d8b4b782ff2e654988bb9e2a209e5b88
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P2-04
    result_commit: 7aaf3e83847d87538ec033fb9a043ea83bcbdf95
    result_tree: ec205b0e33c05b2a9bcd8fe6e2e5b8919c0daffc
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_type_build_installed_restart_and_full_regression: VERIFIED
  numbered_successor: P2-06

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P2_05_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_Project_Task_Run_Graph_NodeAttempt_EgressPolicy_DataPolicy_ContentRef_Artifact_ToolCall_Event_and_transport_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P2_06_or_later_prompt_bodies_before_P2_05_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_Artifact_ContentRef_ToolCall_Event_ResourceAllocation_and_managed_process_identity
    - P2_01_authorized_root_path_streaming_atomic_IO_idempotency_and_Project_isolation_contracts
    - P2_02_direct_argv_explicit_shell_bounded_output_timeout_cancellation_process_ownership_and_truthful_policy_contracts
    - P2_03_exact_revision_dirty_source_preservation_candidate_isolation_Git_safety_diff_commit_and_explicit_push_contracts
    - P2_04_immutable_image_authorized_mount_network_limit_secret_output_cleanup_and_owned_orphan_runtime_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |-
  PROMPT 24/51 - P2-05

  TITLE

  Universal HTTP/API Execution Adapter

  PHASE

  P2 - Universal execution fabric

  GOAL

  Provide controlled outbound HTTP/API transport with explicit destinations, egress policy, credential separation, redirect control, streaming/bounds, timeout/cancel, binary-safe Artifact evidence.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Execute real filesystem/process/Git/runtime/network/model/browser/database/retrieval/workspace work through replaceable adapters with Task-derived validation.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 23/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Define HttpDestination and HttpExecutionRequest with origin/path policy, auth ref, data policy, response cap, redirect policy, Task/Run/Node binding.

  - Validate every redirect target; reachability/credentials never override egress permission.

  - Resolve credentials only at execution and redact secret headers/cookies.

  - Stream upload/download; large binary response becomes ContentRef/Artifact; HTTP status is transport/application response, not semantic Task acceptance.

  - Persist ToolCall destination/status/latency/safe metadata.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Define HttpDestination and HttpExecutionRequest with origin/path policy, auth ref, data policy, response cap, redirect policy, Task/Run/Node binding.

  - Validate every redirect target; reachability/credentials never override egress permission.

  - Resolve credentials only at execution and redact secret headers/cookies.

  - Stream upload/download; large binary response becomes ContentRef/Artifact; HTTP status is transport/application response, not semantic Task acceptance.

  - Persist ToolCall destination/status/latency/safe metadata.

  REQUIRED INTERFACES

  - HttpDestination

  - HttpAdapter

  - HttpExecutionRequest/Result

  DATA / STATE CHANGES

  - Destination config refs and ToolCall/Artifact receipts.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - GET/POST, streamed binary upload/download.

  - Response-size cap, timeout/cancel.

  - Same-origin allowed and forbidden cross-origin redirects.

  - Credentials injected but absent from ledger.

  - Egress-denied remote request blocked.

  - Project-scoped destination config.

  KPI

  - credential_leaks=0

  - egress_policy_bypasses=0

  - redirect_policy_bypasses=0

  - unbounded_response_materialization=0

  - timeouts_claimed_success=0

  - binary_content_corruption=0

  RESTORED LONG-FORM REQUIREMENTS

  HTTP REQUEST CONTRACT

  Implement a provider-neutral HTTP/API adapter with explicit destination/egress semantics.

  Conceptual destination:

  HttpDestination

  origin

  allowed path/prefix?

  auth profile ref?

  data/egress classification

  TLS requirements

  Request:

  method

  destination_ref / URL resolved under policy

  headers (non-secret + secret refs)

  body/content ref or stream

  timeouts

  redirect policy

  response size limit

  project/run/node attribution

  EGRESS BEFORE TRANSFER

  Before sending Project data:

  - resolve destination;

  - evaluate Project/Task egress policy;

  - evaluate data classification;

  - resolve credentials only after authorization.

  Technical reachability is not permission.

  REDIRECT POLICY

  Support explicit semantics such as:

  - NONE

  - SAME_ORIGIN

  - ALLOWLIST

  Do not follow arbitrary redirects by default when they could exfiltrate authenticated or Project-private data.

  Re-check egress/auth on redirect.

  AUTH

  Credentials are secret refs resolved at runtime.

  Do not persist authorization headers, cookies, API keys, signed URLs with secrets, or passwords in ordinary ToolCall/Event metadata.

  STREAMING REQUESTS

  Large uploads: stream from authorized ContentRef/Artifact.

  Do not load entire object into RAM unnecessarily.

  Record bytes transferred and exact source digest.

  STREAMING RESPONSES

  Bound:

  - max bytes;

  - timeout;

  - streaming to Object Store for large/binary responses.

  If limit exceeded, stop and record OUTPUT_LIMIT; do not truncate silently and call success.

  TRANSPORT VS SEMANTIC SUCCESS

  HTTP 2xx means transport/protocol response, not Task success.

  Persist:

  - status;

  - response headers subset;

  - output ContentRef;

  - timing;

  - destination identity.

  Higher-level adapter/Task validation determines semantic success.

  BINARY SAFETY

  Support exact binary upload/download.

  Verify downloaded bytes/digest when expected identity is known.

  TLS

  Do not disable certificate verification silently.

  Custom trust roots/config must be explicit.

  CANCELLATION / TIMEOUT

  Cancel network operation where supported, close streams, leave partial output non-authoritative.

  FAILURE CATEGORIES

  - EGRESS_DENIED;

  - AUTH_FAILED;

  - DNS/CONNECT_FAILED;

  - TLS_FAILED;

  - TIMEOUT;

  - REDIRECT_DENIED;

  - OUTPUT_LIMIT;

  - HTTP_ERROR;

  - CANCELLED;

  - CONTENT_INTEGRITY_FAILED.

  TESTS

  - permitted GET/POST;

  - query/header handling;

  - secret auth redaction;

  - egress-denied before body transfer;

  - SAME_ORIGIN redirect;

  - cross-origin redirect denied;

  - allowlisted redirect;

  - large streamed upload;

  - large streamed download;

  - response size cap;

  - binary exact bytes;

  - timeout/cancellation;

  - TLS invalid cert fixture where possible;

  - HTTP 200 with semantically invalid body remains transport success only;

  - Project isolation/destination scope;

  - ToolCall/Artifact attribution.

  Hosted model/browser/object-store adapters may reuse this HTTP substrate but cannot bypass its policy.

  USEFUL EVIDENCE — NON-GATING

  - HTTP becomes a safe provider-neutral transport for models/browsers/services without weakening Project policy.

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

  PROMPT: 24/51 - P2-05

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
