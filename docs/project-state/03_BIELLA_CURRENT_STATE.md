# MiniTZ Current State Projection

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false
authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/biella/analysis/live_audit/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 69
  program_sha256: 08f4dee8df9782439a36ea9e945257bc39c6195c02a99ec7bcc2498c8b91d549
repository:
  repository: /mnt/biella-extra/minitz-os-sandbox/workspace/repo
  branch: main
  canonical_checkout: /mnt/biella-extra/minitz-os-sandbox/workspace/repo
  remote: UNATTACHED_PRIVATE_MINITZOS
active_execution:
  id: MINITZ-STARTUP-FOUNDATION-01
  task_revision: 1
  task_sha256: 47c528f0a1bd4ef3b917726baa8635ef7566b682083730d32f062fb4a994a348
  state: WORKING
progress:
  completed_tasks: 22
  active_tasks: 14
  total_tasks: 36
execution_invariants:
  one_task_program: true
  one_canonical_source_tree: true
  one_active_branch_main: true
  private_github_required: true
  ubuntu_24_04_is_host_only: true
  ubuntu_26_04_is_minitz_build_target: true
  one_bootable_installable_artifact_required: true
```
