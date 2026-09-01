# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v6

program_boundary:
  state: ACTIVE_NUMBERED_REPAIR
  completed_predecessor: P3-07
  active_numbered_prompt: P3-08
  active_global_number: 39
  active_title: Environment and World Production Pack
  active_prompt_drive_id: 10wP9734umfbfCGfLvmf3gz_9IfT1h8kTjX06KmW0a54
  successor: P3-09
  successor_dependency: P3-08_DURABLE_CLOSE
  execution_authorized: true
  authorization_reason: STANDING_OWNER_AUTHORIZATION_P3_06_THROUGH_P4_06
  unresolved: P3_08_EXACT_EXPORTED_ENVIRONMENT_TO_GODOT_LINKAGE_AND_TRUE_INDEPENDENT_BRANCHES

accepted_source:
  implementation_commit: 0da64ebea6aeb0a69fb73ae8c67317fd8d86c109
  implementation_tree: da7860a8c0890d3ae82b0ae3d4c9b545efa85759
  current_preserved_result_commit: 0da64ebea6aeb0a69fb73ae8c67317fd8d86c109
  current_preserved_result_tree: da7860a8c0890d3ae82b0ae3d4c9b545efa85759
  source_classification: PRESERVED_RESULT_REUSE; DURABLE_CLAIM_INVALIDATED

audit_invalidation:
  functional_source: PRESERVED_RESULT
  durable_close: INCOMPLETE
  missing:
    - exact_exported_environment_to_Godot_linkage
    - true_independent_branches

graph:
  revision: P3_08_REPAIR_R1
  nodes:
    - id: P3-08-GAP-CLASSIFICATION
      resource: controller
      status: READY
      writes: NONE
    - id: P3-08-EXECUTE-REPAIR
      resource: controller
      status: BLOCKED
      dependency: P3-08-GAP-CLASSIFICATION
    - id: P3-08-L40S-REAL
      resource: biella-gpu
      status: BLOCKED
      dependency: P3-08-EXECUTE-REPAIR
    - id: P3-08-ENGINE-EVIDENCE
      resource: controller
      status: BLOCKED
      dependency: P3-08-L40S-REAL
    - id: P3-08-PUBLISH-CLOSE
      resource: controller
      status: BLOCKED
      dependency: P3-08-ENGINE-EVIDENCE

execution_dependencies:
  p3_07: VERIFIED
```
