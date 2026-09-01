# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v6

program_boundary:
  state: ACTIVE_NUMBERED_REPAIR
  completed_predecessor: P3-08
  active_numbered_prompt: P3-09
  active_global_number: 40
  active_title: Rendering Production Pack
  active_prompt_drive_id: 1FYsaztU8wwjl_6k8Nx4xJII4wId-MPflkLFUNwW4gRM
  successor: P3-10
  successor_dependency: P3-09_DURABLE_CLOSE
  execution_authorized: true
  authorization_reason: STANDING_OWNER_AUTHORIZATION_P3_06_THROUGH_P4_06
  unresolved: P3_09_GENERIC_RENDERER_ADAPTER_FINAL_RECOVERY_AND_DURABLE_EVIDENCE

accepted_source:
  implementation_commit: b23195b82e20a568f22b8ebc7be401d5bb95c97e
  implementation_tree: c35e5a1f38d6c938828ec0556706a3ed0e3ca93a
  current_preserved_result_commit: b23195b82e20a568f22b8ebc7be401d5bb95c97e
  current_preserved_result_tree: c35e5a1f38d6c938828ec0556706a3ed0e3ca93a
  source_classification: PRESERVED_RESULT_REUSE; DURABLE_CLAIM_INVALIDATED

audit_invalidation:
  functional_source: PRESERVED_RESULT
  durable_close: INCOMPLETE
  missing:
    - generic_renderer_adapter
    - final_recovery
    - durable_evidence

graph:
  revision: P3_09_REPAIR_R1
  nodes:
    - id: P3-09-GAP-CLASSIFICATION
      resource: controller
      status: READY
      writes: NONE
    - id: P3-09-EXECUTE-REPAIR
      resource: controller
      status: BLOCKED
      dependency: P3-09-GAP-CLASSIFICATION
    - id: P3-09-L40S-REAL
      resource: biella-gpu
      status: BLOCKED
      dependency: P3-09-EXECUTE-REPAIR
    - id: P3-09-ENGINE-EVIDENCE
      resource: controller
      status: BLOCKED
      dependency: P3-09-L40S-REAL
    - id: P3-09-PUBLISH-CLOSE
      resource: controller
      status: BLOCKED
      dependency: P3-09-ENGINE-EVIDENCE

execution_dependencies:
  p3_08: VERIFIED
```
