# P3-10 VFX simulation repair component evidence

```yaml
schema: biella.evidence/p3_10_vfx_simulation_repair_component/v2
observed_at_utc: 2026-09-01T16:24:00Z
status: PRELIMINARY_COMPONENT_EVIDENCE
completion_authority: false
prompt: P3-10
exact_prompt_drive_id: 12GmJFm2-6mL7QSjyyaySDWbBi2WrkljUF447XWsHnnI

remote_component:
  commit: e23794659f41d1bfeb008033ee5b0d0c3cbc1344
  tree: 2f9183cc89acf5d837a7a34df00e64ab7d2c9756
  result: deterministic ENOSPC recovery planner
  github_actions_run: 33530858428
  validation: 6 focused tests PASS; strict mypy PASS; compileall PASS; wheel PASS

current_repair:
  commit: 6c5154a0cfe9b0b58431b6a4190a5784bc648e8a
  tree: cff77e063359a7c5ce081d3b4e6afa19dec7d9b9
  result: authority-bound recovery plus corrected REAL continuation and game/render handoff
  focused_validation: recovery 9 PASS; REAL Blender 6 PASS; durable importer 6 PASS 1 environment skip; strict mypy PASS

remaining_before_durable_close:
  - retained REAL 1-300 ENOSPC archive and exact output readback
  - authoritative Engine Task/Run/Graph/Node/Artifact/Validation/Event import
  - package/install qualification
  - final GitHub and Drive publication/readback

kpi_claims: NOT_FINAL_UNTIL_RETAINED_REAL_AND_ENGINE_EVIDENCE
```
