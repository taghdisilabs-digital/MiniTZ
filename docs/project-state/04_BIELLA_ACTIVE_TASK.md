# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v6

program_boundary:
  state: ACTIVE_NUMBERED_REPAIR
  completed_predecessor: P3-05
  active_numbered_prompt: P3-06
  active_global_number: 37
  active_title: Character Modeling, Rigging, Skinning, and Character Asset Pack
  active_prompt_drive_id: 11Q0LKa5Zl_ctJ6_0tdn_6ezvxNeex6JufFBbDfu5NHM
  successor: P3-07
  successor_dependency: P3-06_DURABLE_CLOSE
  execution_authorized: true
  authorization_reason: STANDING_OWNER_AUTHORIZATION_P3_06_THROUGH_P4_06
  unresolved: P3_06_DURABLE_RUN_ARTIFACT_REPORT_EVIDENCE

accepted_source:
  implementation_commit: 78005b0a30fa7002eed8019a588731551e3d2c6b
  implementation_tree: 6737d32d10feae0dcaeb4024ece00f3aa64b20f0
  current_preserved_source_commit: b7a55142edea7de895f799b8bef074a2a02d916d
  current_preserved_source_tree: 6df2a4d4f04246713220aa2461a10e33ba1b93d1
  source_classification: COMPLETE_REUSE_WITHOUT_REIMPLEMENTATION

audit_invalidation:
  functional_source: COMPLETE
  missing:
    - durable_Task_Run_Graph_Node_Artifact_evidence_refs
    - retained_REAL_Blender_output_and_process_reports
    - exact_commands_and_named_six_KPI_results
    - published_wheel_identity_and_exact_readback
  optional_engine_import: NOT_REQUIRED

graph:
  revision: P3_06_EVIDENCE_REPAIR_R1
  nodes:
    - id: P3-06-L40S-REAL
      resource: biella-gpu
      status: RUNNING
      writes: /root/biella/jobs/p3-06-evidence-20260901
    - id: P3-06-ENGINE-EVIDENCE
      resource: controller
      status: READY
      dependency: P3-06-L40S-REAL
    - id: P3-06-PUBLISH-CLOSE
      resource: controller
      status: BLOCKED
      dependency: P3-06-ENGINE-EVIDENCE

execution_dependencies:
  spark: REMOVED
  prep: REMOVED
```
