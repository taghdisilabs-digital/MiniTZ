# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P2-09
  global_number: 28
  phase: P2
  title: Replaceable Durable Object Storage Backends and Replicas
  state: READY_AFTER_P2_08_DURABLE_CLOSE
  exact_prompt:
    title: 28_P2-09_Replaceable_Durable_Object_Storage_Backends_and_Replicas.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P2/28_P2-09_Replaceable_Durable_Object_Storage_Backends_and_Replicas.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P2/28_P2-09_Replaceable_Durable_Object_Storage_Backends_and_Replicas.md.docx
    drive_id: 1lv_zCYOyP8L3RZev-Wtlyy_RpMyOri4GETYCvO3eNHE
    local_docx_sha256: 6717f97c613371d35d45f08a20d7f08638125131f282cda653229383dd3b1b1a
    live_drive_exported_docx_sha256: 5f5d4efa6d1a45942362cc6abcee1d9ce86631511259225018f9681c8c42fe75
    canonical_text_sha256: ab9ab127347220ae14e98d43fcfe673fc446a088421090dc29e5262d405017c4
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P2-08
    result_commit: fcc954bfc2be3fae7f01986311eda2b6fd92e300
    result_tree: 3d54e11466499eb6d62729a50e0e29e9ba659da8
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_real_postgresql_type_build_installed_restart_and_full_regression: VERIFIED
  numbered_successor: P2-10

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P2_09_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_ContentRef_ContentLocation_ObjectStorageBackend_Artifact_Project_Task_policy_and_quarantine_firewall_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P2_10_or_later_prompt_bodies_before_P2_09_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_Artifact_ContentRef_ModelCall_ToolCall_Event_ResourceAllocation_and_managed_runtime_identity
    - P1_01_ContentRef_provider_neutral_object_storage_exact_digest_streaming_and_physical_location_separation_contracts
    - P2_01_through_P2_04_real_execution_adapter_isolation_streaming_fencing_and_durability_contracts
    - P2_05_destination_egress_credential_redirect_streaming_timeout_cancellation_TLS_and_transport_evidence_contracts
    - P2_06_provider_neutral_model_deployment_execution_health_tool_policy_fencing_and_provenance_contracts
    - P2_07_browser_session_generation_egress_origin_side_effect_upload_download_wait_secret_and_durable_evidence_contracts
    - P2_08_Project_database_scope_parameterization_bounded_streaming_transaction_truth_TLS_secret_and_internal_database_firewall_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |
  PROMPT 28/51 - P2-09

  TITLE

  Replaceable Durable Object Storage Backends and Replicas

  PHASE

  P2 - Universal execution fabric

  GOAL

  Extend P1 content storage across multiple durable physical backends/replicas while preserving one ContentRef identity and per-replica integrity/health.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Execute real filesystem/process/Git/runtime/network/model/browser/database/retrieval/workspace work through replaceable adapters with Task-derived validation.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 27/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Add/qualify a second backend such as S3-compatible/MinIO/reference using existing ObjectStorageBackend.

  - Track ContentLocation state per backend; replication streams from verified source, verifies target read-back, then marks AVAILABLE.

  - Read selects healthy verified replicas; corrupt/missing replica is isolated and another may serve/repair.

  - Interrupted/cancelled upload never becomes AVAILABLE; backend URI/ETag is not ContentRef authority.

  - Physical replica deletion remains distinct from logical Artifact/object deletion.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Add/qualify a second backend such as S3-compatible/MinIO/reference using existing ObjectStorageBackend.

  - Track ContentLocation state per backend; replication streams from verified source, verifies target read-back, then marks AVAILABLE.

  - Read selects healthy verified replicas; corrupt/missing replica is isolated and another may serve/repair.

  - Interrupted/cancelled upload never becomes AVAILABLE; backend URI/ETag is not ContentRef authority.

  - Physical replica deletion remains distinct from logical Artifact/object deletion.

  REQUIRED INTERFACES

  - ContentLocation

  - replicateContent

  - replica selection/verify/repair

  DATA / STATE CHANGES

  - Per-backend replica status/verification.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Local + second backend same ContentRef.

  - Replicate/read-back/restart.

  - Corrupt backend A falls back to B and is marked corrupt.

  - Interrupted upload safe.

  - Large streamed replication/cancel.

  - Quarantine/active authorization remains distinct even if physical bytes dedupe.

  KPI

  - content_identity_changes_across_backends=0

  - unverified_replica_AVAILABLE=0

  - corrupt_replica_served=0

  - partial_upload_AVAILABLE=0

  - Artifact_identity_tied_to_URI=0

  - backend_credentials_leaked=0

  RESTORED LONG-FORM REQUIREMENTS

  EXTEND P1 CONTENT STORE; DO NOT REDEFINE CONTENT IDENTITY

  P1-01 already owns ContentRef.

  P2-09 adds replaceable physical backends/replicas.

  Prove:

  Content identity != backend != URI

  Same bytes B always produce same SHA-256 ContentRef X across backends.

  BACKENDS

  At least:

  1.  P1 local filesystem backend;

  2.  a second independent durable/reference backend.

  Use real S3-compatible/MinIO/remote storage if available; otherwise use faithful second implementation and label evidence REFERENCE.

  CONTENT LOCATION

  Represent per-backend state:

  ContentLocation:

  content_digest

  backend_id

  storage_locator

  state

  size

  verified_at

  created_at

  failure_ref?

  States such as: AVAILABLE, VERIFYING, CORRUPT, MISSING, UPLOADING, FAILED.

  REPLICATION

  replicateContent(ref,target) should:

  1.  choose verified source replica;

  2.  stream;

  3.  upload to target as non-available/in-progress;

  4.  verify target content independently/read back;

  5.  mark AVAILABLE only after exact digest success.

  Do not trust provider success or ETag as SHA-256 unless provider explicitly guarantees equivalent digest semantics.

  READ SELECTION

  When multiple replicas:

  - only verified healthy replicas eligible;

  - deterministic current selection may consider local/remote availability;

  - corrupt replica marked CORRUPT;

  - fallback to another healthy replica.

  P4 learns ranking later.

  PARTIAL / INTERRUPTED UPLOAD

  Partial target never becomes AVAILABLE.

  Cancellation leaves FAILED/MISSING/incomplete state.

  CORRUPTION / REPAIR

  On digest mismatch:

  - record/mark replica CORRUPT;

  - do not serve it;

  - preserve evidence;

  - optionally repair from healthy verified replica.

  Do not overwrite corruption before recording the event/evidence.

  LOCAL + REMOTE ROLE

  Architecture should support:

  - local NVMe replica for high-I/O work;

  - remote durable warehouse replica.

  Do not force execution directly against remote warehouse.

  RESTORE

  Missing local replica + healthy remote: restore local with same ContentRef.

  No new logical Artifact.

  REPLICA DELETION VS LOGICAL DELETION

  Deleting physical replica is not deleting Artifact/ContentObject.

  Do not implement global GC/retention policy without reference completeness.

  PROJECT / QUARANTINE AUTHORIZATION

  Backend may dedupe bytes physically.

  Logical authorization remains through Artifact/Project/Quarantine type.

  Same digest in quarantine and active store does not activate historical content.

  CREDENTIALS / EGRESS

  Remote credentials are secret refs. Apply Project egress/network policy.

  METRICS

  Collect: upload/download bytes, throughput, verification/replication latency, failures, corruption, backend health.

  P4 may consume later.

  TESTS

  - same ContentRef local and backend B;

  - local→B replication;

  - target read-back;

  - restart/read B;

  - Artifact identity unchanged;

  - corrupt A then fallback B;

  - A marked CORRUPT;

  - repair A if implemented;

  - interrupted/cancelled upload never AVAILABLE;

  - unavailable target doesn't invalidate other replica;

  - large streaming;

  - replica deletion with another verified copy;

  - provider credential scan;

  - ETag not trusted as SHA;

  - quarantine authorization distinct;

  - Beta cannot use digest to bypass Artifact access.

  USEFUL EVIDENCE — NON-GATING

  - Identical bytes retain identical content identity across storage technologies; one replica failure does not destroy a healthy multi-replica object.

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

  PROMPT: 28/51 - P2-09

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
