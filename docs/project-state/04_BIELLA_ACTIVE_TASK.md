# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v6

program_boundary:
  state: ACTIVE_NUMBERED_REPAIR
  completed_predecessor: P3-06
  active_numbered_prompt: P3-07
  active_global_number: 38
  active_title: Animation Production Pack
  active_prompt_drive_id: 1GzQxmCrvIv10WVv0KdoPxlKi7l79J2J6cS-zvoOv-Dk
  successor: P3-08
  successor_dependency: P3-07_DURABLE_CLOSE
  execution_authorized: true
  authorization_reason: STANDING_OWNER_AUTHORIZATION_P3_06_THROUGH_P4_06
  unresolved: P3_07_CONCURRENCY_AND_DURABLE_EVIDENCE

accepted_source:
  implementation_commit: 56de0cff151214c8a73a173be6c5c110d894d378
  implementation_tree: d23272291cabb25fdb1ac4971e73d868293e3024
  current_preserved_result_commit: 1d74abff81c9588aecfd933ec7733fb9afd098e4
  current_preserved_result_tree: 93326e98e57c1efc16fd05c4dcd938b2314e4c89
  source_classification: FUNCTIONAL_SOURCE_COMPLETE_REUSE

audit_invalidation:
  functional_source: COMPLETE
  durable_close: INCOMPLETE
  missing:
    - durable_Task_Run_Graph_Node_Artifact_Validation_Event_refs
    - retained_REAL_animation_outputs_and_process_reports
    - scheduler_separated_concurrency_for_independent_clips
    - exact_commands_five_KPI_values_and_wheel_readback
  observed_concurrency_defect: independent_clips_reuse_one_Node_attempt_and_allocation

graph:
  revision: P3_07_REPAIR_R1
  nodes:
    - id: P3-07-GAP-CLASSIFICATION
      resource: controller
      status: READY
      writes: NONE
    - id: P3-07-EXECUTE-REPAIR
      resource: controller
      status: BLOCKED
      dependency: P3-07-GAP-CLASSIFICATION
    - id: P3-07-L40S-REAL
      resource: biella-gpu
      status: BLOCKED
      dependency: P3-07-EXECUTE-REPAIR
    - id: P3-07-ENGINE-EVIDENCE
      resource: controller
      status: BLOCKED
      dependency: P3-07-L40S-REAL
    - id: P3-07-PUBLISH-CLOSE
      resource: controller
      status: BLOCKED
      dependency: P3-07-ENGINE-EVIDENCE

execution_dependencies:
  p3_06: VERIFIED
  spark: REMOVED
  prep: REMOVED
```
