# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P2-08
  global_number: 27
  phase: P2
  title: PostgreSQL Project/Task Capability Adapter
  state: READY_AFTER_P2_07_DURABLE_CLOSE
  exact_prompt:
    title: 27_P2-08_PostgreSQL_Project_Task_Capability_Adapter.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P2/27_P2-08_PostgreSQL_Project_Task_Capability_Adapter.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P2/27_P2-08_PostgreSQL_Project_Task_Capability_Adapter.md.docx
    drive_id: 1uWBI_N66H-OlseBJkN-QnrLnN9x-0Vrti40ih_6kkfg
    local_docx_sha256: b7a63f454d92e54b87ebeadacf4c1ca6832801d1403f40d0904a4230f72b4121
    live_drive_exported_docx_sha256: 197dc0ae9ed93e2df74054a52caf015c4f63cc8435dc42caf619e67d2cd58f72
    canonical_text_sha256: e3d1f864f7adf56a86ba93ed191c2243426793627df214f35d97924ccfda623c
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P2-07
    result_commit: f0bd9e7a03cc8ac1ce7d0555de14055190fede5b
    result_tree: ead59ae03ab218c7b95cee9a93813836945aba2e
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_real_browser_type_build_installed_restart_and_full_regression: VERIFIED
  numbered_successor: P2-09

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P2_08_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_Project_Task_Run_Graph_NodeAttempt_Capability_Routing_ToolCall_ContentRef_Artifact_and_policy_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P2_09_or_later_prompt_bodies_before_P2_08_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_Artifact_ContentRef_ModelCall_ToolCall_Event_ResourceAllocation_and_managed_runtime_identity
    - P2_01_through_P2_04_real_execution_adapter_isolation_streaming_fencing_and_durability_contracts
    - P2_05_destination_egress_credential_redirect_streaming_timeout_cancellation_TLS_and_transport_evidence_contracts
    - P2_06_provider_neutral_model_deployment_execution_health_tool_policy_fencing_and_provenance_contracts
    - P2_07_browser_session_generation_egress_origin_side_effect_upload_download_wait_secret_and_durable_evidence_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |-
  PROMPT 27/51 - P2-08

  TITLE

  PostgreSQL Project/Task Capability Adapter

  PHASE

  P2 - Universal execution fabric

  GOAL

  Expose PostgreSQL to Project Tasks as a scoped adapter while keeping Biella internal durable-state database authority separate and inaccessible by default.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Execute real filesystem/process/Git/runtime/network/model/browser/database/retrieval/workspace work through replaceable adapters with Task-derived validation.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 26/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Define DatabaseConnectionRef with Project/global scope, endpoint/database identity, auth/TLS refs and restrictions; no raw credentials.

  - Implement bounded parameterized query/execute/transaction/schema/migration operations with Task side-effect enforcement.

  - Stream/bound results; store sensitive bodies only when Task requires; record query/parameter digests and ToolCall evidence.

  - Transactions report commit/rollback/unknown outcome truthfully; cancellation/timeouts reset/rollback safely.

  - Explicitly distinguish Project DB refs from Biella internal DB.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Define DatabaseConnectionRef with Project/global scope, endpoint/database identity, auth/TLS refs and restrictions; no raw credentials.

  - Implement bounded parameterized query/execute/transaction/schema/migration operations with Task side-effect enforcement.

  - Stream/bound results; store sensitive bodies only when Task requires; record query/parameter digests and ToolCall evidence.

  - Transactions report commit/rollback/unknown outcome truthfully; cancellation/timeouts reset/rollback safely.

  - Explicitly distinguish Project DB refs from Biella internal DB.

  REQUIRED INTERFACES

  - DatabaseConnectionRef

  - PostgreSQLAdapter

  - query/transaction/schema/migration requests/results

  DATA / STATE CHANGES

  - Connection refs and ToolCall/transaction evidence.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Parameterized SELECT and bounded large result.

  - Authorized mutation vs read-only rejection.

  - Transaction commit/rollback/cancel/connection-loss ambiguity.

  - Schema inspection and safe test migration if in scope.

  - Credential redaction, Project isolation, internal-DB boundary.

  KPI

  - raw_DB_credentials_in_Task_or_ledger=0

  - cross_project_DB_access=0

  - read_only_write_bypasses=0

  - unbounded_query_results=0

  - failed_transactions_claimed_committed=0

  - internal_Biella_DB_accidentally_exposed=0

  RESTORED LONG-FORM REQUIREMENTS

  PROJECT DATABASE VS BIELLA INTERNAL DATABASE

  PostgreSQL is a Project/Task capability adapter.

  Biella may itself use PostgreSQL internally; that does not mean a generic Project Task automatically receives access to the internal execution database.

  Represent connection refs so Project database connections and engine/infrastructure connections are distinguishable by scope.

  Generic database.postgresql.query must never silently resolve to Biella's own state DB.

  CAPABILITIES

  Support extensible semantics such as:

  - connect;

  - inspect_schema;

  - query;

  - transaction;

  - execute;

  - migrate;

  - export/import as later/optional bounded operations.

  Mutation requires Task authority.

  CONNECTION REF

  Conceptual:

  DatabaseConnectionRef:

  connection_id

  project/global-infrastructure scope

  adapter_id

  endpoint identity

  database identity

  auth_profile_ref

  TLS/security config

  capability restrictions

  timestamps

  Never store raw password/connection secret in Task/Run/Event/ToolCall.

  QUERY

  Use parameterized queries.

  Request binds:

  - connection ref;

  - statement/statement ref;

  - parameter refs;

  - mode;

  - timeout;

  - max rows/bytes;

  - transaction ref where applicable;

  - Project/Run/Node.

  Do not concatenate model/user values into SQL.

  READ / MUTATION / DDL

  Distinguish:

  - READ_ONLY;

  - MUTATING;

  - DDL/MIGRATION.

  Layer Task authority with database permissions/read-only connection profiles where practical.

  Do not rely solely on SQL parser classification for security.

  BOUNDED RESULTS

  Large results:

  - stream/paginate;

  - enforce row/byte limits;

  - persist as ContentRef/Artifact only when durability required.

  Do not automatically persist sensitive query bodies.

  ToolCall metadata may record: query digest, parameter digest/refs, mode, row count, duration, database identity, output ref.

  TRANSACTIONS

  Support:

  - begin;

  - multiple operations;

  - commit;

  - rollback;

  - cancellation;

  - timeout.

  Do not claim commit unless observed.

  If connection fails during commit and outcome cannot be proven, report TRANSACTION_OUTCOME_UNKNOWN, not success/failure fabrication.

  MIGRATION

  If implemented:

  - bind exact migration Artifact/digest;

  - target DB;

  - expected before schema/version;

  - observed after state.

  Do not automatically run repository migrations against unknown/production DB.

  SCHEMA INSPECTION

  Bounded metadata: tables, columns, indexes, constraints, extensions/version.

  No data dump/credentials.

  TIMEOUT / CANCELLATION

  Use driver cancellation and statement timeout where available; report enforcement layer.

  Cancelled transaction should rollback/reset safely.

  TLS

  Do not disable TLS verification silently.

  ERROR / SQLSTATE

  Preserve useful bounded SQLSTATE/provider error metadata while preventing secret/parameter leakage.

  Support categories including: CONNECTION_FAILED, AUTH_FAILED, TLS_FAILED, QUERY_FAILED, TIMEOUT, CANCELLED, RESULT_LIMIT, TRANSACTION_ABORTED, TRANSACTION_OUTCOME_UNKNOWN, SCHEMA_MISMATCH, MIGRATION_FAILED, POLICY_DENIED.

  TESTS

  Real PostgreSQL where available:

  - connect/version;

  - bad auth;

  - parameterized SELECT;

  - row/byte caps;

  - streamed large result;

  - authorized write;

  - read-only write rejection;

  - transaction commit;

  - rollback;

  - cancel/timeout rollback;

  - ambiguous commit outcome fixture;

  - schema inspect;

  - migration success/failure if in scope;

  - secret scan of ledger/events/checkpoints;

  - Beta cannot use Alpha connection;

  - Project connection cannot accidentally resolve internal Biella DB;

  - restart recreates pool while durable operation receipts remain.

  Pooling is optimization, not durable authority.

  USEFUL EVIDENCE — NON-GATING

  - PostgreSQL is an adapter capability, not a Project/kernel requirement; transaction truth and secrets are preserved.

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

  PROMPT: 27/51 - P2-08

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
