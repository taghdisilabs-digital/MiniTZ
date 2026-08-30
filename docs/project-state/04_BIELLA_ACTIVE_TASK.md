# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v6

active_task:
  id: P3-05
  global_number: 36
  phase: P3
  title: 3D Modeling and Scene Production Pack
  state: PROVISION_NEW_HOST_THEN_RESTORE_GPT_5_6_AND_EXECUTE_END_TO_END
  predecessor: P3-04
  predecessor_result_commit: 28fde1e9224236ce7b37b74434727463e96d9893
  predecessor_result_tree: d7efcc21cab8dc86488ef91963f48791dbe0dca0
  predecessor_remote_readback: VERIFIED
  successor: P3-06
  successor_authorized_before_close: false

exact_prompt:
  title: 36_P3-05_3D_Modeling_and_Scene_Production_Pack.md.docx
  local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P3/36_P3-05_3D_Modeling_and_Scene_Production_Pack.md.docx
  local_path_status: ABSENT_UNTIL_NEW_HOST_BOOTSTRAP
  drive_path: gdrive:BiellaEngine/40_PROMPTS/P3/36_P3-05_3D_Modeling_and_Scene_Production_Pack.md.docx
  drive_id: 1TIG3GggwGdu3ma1e5MeeIontVUO4pmSP4aggJKps0Kg
  local_docx_sha256: abb4255869736f571329e3e55409fc8675f927a4ab09bc50bbb6556bbd48c050
  live_drive_exported_docx_sha256: d411b17a37fc988eda9a563c0285515e9be478a12ba024c23dc6696da2c8c8e6
  canonical_text_sha256: e8688b4e820c7df1096f4a88a9e0bcda792fbe17c3e1690839a689bbcf6f46ed
  technical_dependencies: RESOLVE_FROM_EXACT_PROMPT_AND_CURRENT_SOURCE

recovery_boundary:
  durable_implementation_base: e228a7bb6db6f94af15dde4a8fb110b028eddbed
  durable_implementation_base_tree: b407138ac05af441487aa6005700da98b8016906
  preserve_execution_through: "2026-08-30T10:08:48.575Z"
  reject_execution_beginning: "2026-08-30T10:44:52Z"
  recovery_archive: GPT56_EXACT_RECOVERY_2026-08-30.tar.gz
  recovery_archive_sha256: 73052d6cffea8017bebee64750d8de532654ca6c7e8dffff62caa554efe30f0d
  recovery_archive_size_bytes: 26490936
  recovery_archive_drive_id: 1Y7aEStdGbCK5a0N9iA8s41l2olTWOUAE
  recovery_archive_drive_readback: VERIFIED_EXACT_BYTES
  recovery_archive_drive_readback_sha256: 73052d6cffea8017bebee64750d8de532654ca6c7e8dffff62caa554efe30f0d
  previous_execution_host: DESTROYED
  restore_status: PENDING_NEW_HOST_RESTORE
  rule: restore_exact_pre_boundary_file_contents; never_replay_rejected_session_mutations

execution_host:
  current_host: NONE
  previous_host_state: DESTROYED
  previous_host_paths_are_authority: false
  canonical_root_for_next_host: /root/biella
  canonical_codex_home_for_next_host: /root/.codex
  canonical_checkout_for_next_host: /root/biella/repos/biella-engine
  bootstrap_authorities:
    github_repository: patrickminitz-web/biella-engine
    github_branch: main
    drive_current_state_id: 1wiWcdWt4hmTf3narsLw4OqGu_ueKOSa4
    drive_active_task_id: 1liutA8evH6rPjk-U4tgR13l_kqBrx-DF
    drive_recovery_archive_id: 1Y7aEStdGbCK5a0N9iA8s41l2olTWOUAE
  rule: new_host_is_disposable_execution_resource; GitHub_and_Drive_hold_durable_authority

expected_recovered_path_set:
  modified_tracked:
    - src/biella/__init__.py
    - src/biella/process.py
    - src/biella/production_pack.py
    - tests/test_p2_02_process.py
  untracked_p3_05:
    - src/biella/_blender_three_d_driver.py
    - src/biella/three_d_pack.py
    - src/biella/three_d_tool.py
    - tests/test_p3_05_three_d_pack.py
    - tests/test_p3_05_three_d_real.py
  rule: path_set_is_integrity_expectation_only; recovery_evidence_controls_bytes

codex_execution_contract:
  language: biella.codex.end_to_end/v2
  mode: SINGLE_END_TO_END_NUMBERED_EXECUTION
  objective: maximize_durable_progress_per_model_token_without_lowering_engineering_or_validation_quality
  planning_method:
    superpowers_used_for: decomposition_and_plan_quality
    superpowers_is_runtime_dependency: false
    biella_authority_overrides_generic_skill_workflow: true
    no_permanent_reviewer_or_manager_hierarchy: true
  model_guard:
    intended_model: user_selected_non_Spark_Codex_model
    forbidden_silent_substitution: gpt-5.3-codex-spark
    if_intended_model_unavailable: stop_before_repository_write
  normal_context:
    - 03_BIELLA_CURRENT_STATE.md
    - 04_BIELLA_ACTIVE_TASK.md
    - exact_active_numbered_prompt
    - directly_touched_source_and_interfaces
  context_expansion_only_when_required:
    00: operational_edge_case
    01: architecture_or_semantic_scope
    02: sequence_or_plan_ambiguity
    05: exact_prompt_location
    06: source_evidence_or_migration_resolution
  do_not_preload:
    - old_Codex_sessions_after_recovery_is_complete
    - recovery_archive_after_exact_worktree_restoration
    - unrelated_prompt_bodies
    - historical_MiniTZ_material
    - broad_Drive_Git_or_filesystem_inventory
  tool_policy:
    use_only_task_relevant_tools: true
    AWS_MCP_default: OFF_FOR_NORMAL_CODE_EXECUTION
    Cloudflare_MCP_default: OFF
    NVIDIA_skill_bundle_default: OFF_UNLESS_REAL_GPU_SUBPATH_REQUIRES_IT
    generic_template_and_unrelated_workflow_bundles_default: OFF
  observation_policy:
    inspect_exact_state_once: true
    reuse_verified_outputs: true
    reread_unchanged_files: false
    reobserve_only_if_materially_invalidated: true
  output_policy:
    prefer_exact_ranges_symbols_paths_and_digests: true
    bound_terminal_output: true
    prohibit_binary_asset_dump_into_model_context: true
    prohibit_full_large_diff_dump_unless_required: true
    worker_handoffs_are_compact_structured_results_not_transcripts: true
  validation_policy:
    development_funnel:
      - exact_new_or_failing_test
      - focused_active_task_module
      - directly_affected_regression
    final_task_derived_gate: ONCE_AFTER_IMPLEMENTATION_STABILIZES
    after_final_failure: fix_smallest_affected_boundary_then_rerun_only_invalidated_gates
  usage_policy:
    check_status_before_execution: true
    usage_low_behavior: finish_current_node; run_its_exact_validation; persist_coherent_work; record_ready_blocked_nodes; do_not_start_new_node
    usage_exhaustion_is_not_invalidation: true
    session_or_model_restart_is_not_invalidation: true

multi_ai_execution:
  principle: workers_execute_exact_Graph_Nodes; workers_do_not_independently_consume_an_informal_TODO_list
  controller_authority:
    - exactly_one_numbered_prompt_active
    - compile_or_revise_Graph_from_exact_prompt_and_current_source
    - allocate_READY_nodes
    - enforce_dependency_resource_and_side_effect_constraints
    - integrate_results
    - authorize_durable_close
  worker_identity:
    exact_fields:
      - task_ref
      - graph_ref
      - graph_revision
      - node_ref
      - objective
      - required_capabilities
      - dependencies
      - exact_inputs
      - readable_context
      - owned_write_paths
      - allowed_tools
      - resource_requirements
      - side_effect_authority
      - output_contract
      - evidence_requirements
      - validation_command
      - idempotency_key
      - lease_owner
      - fence
  duplicate_prevention:
    one_current_owner_per_node: true
    atomic_claim_lease_fence_required: true
    overlapping_live_write_ownership: forbidden
    already_completed_exact_node: reuse_unless_invalidated
    validator_nodes_are_read_only: true
    repair_nodes_are_created_from_exact_failures_only: true
  graph_revision_policy:
    revisions_are_immutable: true
    discovered_required_work: compile_new_revision
    preserve_unaffected_completed_nodes: true
    later_prompt_work: record_for_future; do_not_execute
  agent_policy:
    default_parallel_workers: 0
    fan_out_only_after_M0_gap_map: true
    parallel_workers_only_if: independent_dependencies_and_nonoverlapping_side_effects_and_material_wall_clock_benefit
    no_mandatory_planner_critic_validator_chain: true
    no_permanent_named_agent_hierarchy: true

P3_05_graph:
  B0_NEW_HOST_BOOTSTRAP:
    mode: SERIAL_INFRASTRUCTURE
    depends_on: []
    objective: provision a fresh execution host and reconstruct canonical Biella roots from current GitHub and verified Drive authority
    required:
      - create_or_select_fresh_host
      - create_/root/biella_and_/root/.codex
      - clone_or_fetch_patrickminitz-web/biella-engine_main_into_/root/biella/repos/biella-engine
      - verify_GitHub_continuity_head_before_any_recovery_write
      - fetch_03_and_04_from_their_existing_Drive_file_IDs_when_needed_for_cross_check
      - download_recovery_archive_from_Drive_ID_1Y7aEStdGbCK5a0N9iA8s41l2olTWOUAE
      - verify_archive_size_26490936_and_sha256_73052d6cffea8017bebee64750d8de532654ca6c7e8dffff62caa554efe30f0d
    forbidden:
      - assume_previous_VPS_disk_or_/root_contents_exist
      - recreate_/srv/biella
      - revive_/home/ubuntu/biella-work
      - create_duplicate_active_checkout
      - treat_host_or_provider_as_architectural_authority
  R0_PRE_RUN_GUARD:
    mode: SERIAL_READ_ONLY
    depends_on: [B0_NEW_HOST_BOOTSTRAP]
    objective: verify intended model, canonical repository, branch, prompt identity, recovery archive identity, and source boundary
    stop_before_write_if:
      - wrong_repository_or_branch
      - intended_model_unavailable_or_silent_Spark_substitution
      - recovery_archive_digest_mismatch
      - unexplained_newer_implementation_source
  R1_RESTORE:
    mode: SERIAL_WRITE
    depends_on: [R0_PRE_RUN_GUARD]
    objective: restore exact GPT-5.6 P3-05 worktree and reject post-boundary mutations
    writes: expected_recovered_path_set_only
    checkpoint_after: CP0_RESTORED
  M0_GAP_MAP:
    mode: SERIAL_READ_MOSTLY
    depends_on: [R1_RESTORE]
    objective: inspect recovered P3-05 state once and derive COMPLETE FAILING MISSING BLOCKED map
    reads:
      - recovered_P3_05_files
      - exact_imported_interfaces_only
    writes: compact_gap_ledger_only
    checkpoint_after: CP1_GAP_MAP
  I1_PACK_API:
    mode: PARALLEL_WRITE
    depends_on: [M0_GAP_MAP]
    objective: complete ProductionPack, capability registration, package exports, Artifact roles, and pack validators
    owned_write_paths:
      - src/biella/three_d_pack.py
      - src/biella/production_pack.py
      - src/biella/__init__.py
      - tests/test_p3_05_three_d_pack.py
    forbidden_write_paths:
      - src/biella/three_d_tool.py
      - src/biella/_blender_three_d_driver.py
      - src/biella/process.py
      - tests/test_p3_05_three_d_real.py
  I2_THREED_CORE:
    mode: PARALLEL_WRITE
    depends_on: [M0_GAP_MAP]
    objective: complete generic ThreeD contract, durable exact identity/provenance, reference implementation, replay, recovery, and Project isolation
    owned_write_paths:
      - src/biella/three_d_tool.py
    invariants:
      - DCC_SDK_types_remain_adapter_local
      - no_DCC_specific_kernel_fields
      - no_global_style_poly_or_scale_rules
      - missing_DCC_affects_route_not_Capability
  I3_BLENDER_DRIVER:
    mode: PARALLEL_WRITE
    depends_on: [M0_GAP_MAP]
    objective: complete adapter-local real Blender editable-source, structured inspection, operation, export, reopen, and preview mechanics
    owned_write_paths:
      - src/biella/_blender_three_d_driver.py
    invariants:
      - render_or_preview_is_not_source_proof
      - effective_exporter_settings_and_units_axis_identity_are_observed
      - bpy_and_tool_specific_types_do_not_escape_adapter_boundary
  I4_PROCESS_SUBSTRATE:
    mode: PARALLEL_WRITE
    depends_on: [M0_GAP_MAP]
    objective: complete only Process substrate changes proven necessary by the restored real DCC path
    owned_write_paths:
      - src/biella/process.py
      - tests/test_p2_02_process.py
    invariants:
      - no_3D_or_Blender_domain_semantics_in_Process
      - no_Process_redesign
      - preserve_authority_isolation_evidence_and_recovery_contracts
  G1_INTEGRATION:
    mode: SERIAL_READ_ONLY_BY_DEFAULT
    depends_on:
      - I1_PACK_API
      - I2_THREED_CORE
      - I3_BLENDER_DRIVER
      - I4_PROCESS_SUBSTRATE
    objective: verify interfaces align before real acceptance expansion
    direct_source_writes: forbidden
    on_failure: create_exact_repair_node_for_original_owner
    checkpoint_after: CP2_INTEGRATED
  I5_REAL_ACCEPTANCE:
    mode: SERIAL_WRITE
    depends_on: [G1_INTEGRATION]
    objective: complete task-derived real/reference P3-05 acceptance workflow
    owned_write_paths:
      - tests/test_p3_05_three_d_real.py
    required_flow:
      - create_or_ingest_editable_mesh
      - structured_inspect
      - geometry_modify
      - topology
      - UV_when_Task_requires
      - material
      - scene
      - save_native_source
      - export
      - exact_ContentRef
      - reopen_or_parse
      - technical_validate
      - preview_secondary_evidence
      - durable_provenance
    required_negative_recovery_scope:
      - invalid_topology
      - missing_dependency
      - invalid_or_missing_UV_when_required
      - corrupt_export
      - DCC_unavailable
      - idempotent_replay
      - restart_recovery
      - stale_authority
      - Project_isolation
      - physical_output_collision
      - second_reference_or_real_implementation
    checkpoint_after: CP3_REAL_WORKFLOW
  G2_IMPLEMENTATION_FREEZE:
    mode: SERIAL_CONTROL
    depends_on: [I5_REAL_ACCEPTANCE]
    objective: prohibit optional scope expansion; only acceptance-blocking defects may create repair nodes
  V1_PACK_CONTRACT:
    mode: PARALLEL_READ_ONLY
    depends_on: [G2_IMPLEMENTATION_FREEZE]
    validates:
      - ProductionPack_descriptor
      - capability_registration
      - package_exports
      - Artifact_roles
      - pack_validators
      - static_KPI_invariants
  V2_REAL_OUTPUT_TRUTH:
    mode: PARALLEL_READ_ONLY
    depends_on: [G2_IMPLEMENTATION_FREEZE]
    validates:
      - real_editable_source
      - structured_inspection
      - tool_runtime_plugin_export_identity
      - export_reopen_parse
      - preview_secondary_only
      - dependency_and_material_provenance
  V3_ISOLATION_RECOVERY:
    mode: PARALLEL_READ_ONLY
    depends_on: [G2_IMPLEMENTATION_FREEZE]
    validates:
      - Project_Alpha_Beta_isolation
      - same_output_races
      - idempotency
      - stale_attempt_fence
      - restart_and_partial_failure_recovery
      - reference_implementation
      - DCC_unavailable_route_behavior
  F_REPAIR:
    mode: DYNAMIC_SERIAL_PER_OWNED_PATH
    depends_on:
      - V1_PACK_CONTRACT
      - V2_REAL_OUTPUT_TRUTH
      - V3_ISOLATION_RECOVERY
    create_only_if: exact_validator_failure_exists
    no_failure_state: SATISFIED_WITHOUT_WRITE
    ownership_rule: one_failure_one_original_owner_boundary; no_overlapping_live_repairs
    completion_rule: rerun_exact_failure_then_only_invalidated_validator_nodes
    checkpoint_after: CP4_REPAIR_CONVERGENCE
  V4_REGRESSION_GATE:
    mode: SERIAL_OR_SAFE_PARALLEL_READ_ONLY
    depends_on: [F_REPAIR]
    required_scope:
      - P3_05_pack
      - P3_05_real
      - P2_02_Process_if_touched
      - relevant_P3_03_Game_integration
      - relevant_ProductionPack_regressions
      - strict_mypy_on_touched_source_and_tests
      - compileall
      - complete_repository_suite_once_only_if_task_contract_requires_it
  V5_BUILD_RUNTIME_GATE:
    mode: SERIAL_REALITY_CHECK
    depends_on: [V4_REGRESSION_GATE]
    validates_where_applicable:
      - wheel_build
      - clean_installed_import
      - ThreeD_pack_registration
      - reference_adapter_smoke
      - real_DCC_executable_and_version
      - real_create_native_export_reopen_proof
    reality_classes:
      - REAL
      - REFERENCE
      - NOT_RUN
    checkpoint_after: CP5_FINAL_VALIDATION
  C0_DURABLE_CLOSE:
    mode: SERIAL_WRITE_AND_PUBLICATION
    depends_on: [V5_BUILD_RUNTIME_GATE]
    sequence:
      - final_intended_diff_readback
      - coherent_commit_or_commits
      - push_main
      - remote_commit_tree_required_path_readback
      - compute_prompt_KPIs_from_current_evidence
      - replace_03_with_exact_closed_state
      - replace_04_with_next_prompt_packet
      - publish_matching_Drive_continuity_preserving_file_identity
      - exact_Drive_readback
      - authorize_successor_only_after_all_required_evidence
    checkpoint_after: CP6_DURABLE_CLOSE

checkpoint_policy:
  checkpoints:
    CP0_RESTORED: exact_GPT_5_6_worktree_restored
    CP1_GAP_MAP: exact_remaining_work_compiled
    CP2_INTEGRATED: parallel_implementation_integrated
    CP3_REAL_WORKFLOW: task_real_workflow_implemented
    CP4_REPAIR_CONVERGENCE: focused_validators_converged
    CP5_FINAL_VALIDATION: final_task_gate_passed
    CP6_DURABLE_CLOSE: GitHub_and_Drive_readback_complete
  persistence:
    use_existing_Biella_checkpoint_or_Git_durability_mechanism_supported_by_current_source: true
    coherent_intermediate_commits_are_allowed_when_needed_for_recovery: true
    checkpoint_is_not_completion_claim: true
    temporary_state_must_not_be_only_copy_of_meaningful_work: true

worker_result_envelope:
  required_fields:
    - node_ref
    - status
    - files_read
    - files_changed
    - exact_tests_or_checks
    - exact_observed_results
    - output_contract_status
    - blockers
    - newly_discovered_required_work
    - invalidated_prior_evidence
  forbidden:
    - full_transcript_as_handoff
    - broad_architecture_summary_unrelated_to_node
    - completion_claim_without_evidence

P3_05_required_scope:
  capabilities:
    - 3d.inspect
    - 3d.model
    - 3d.mesh_edit
    - 3d.topology
    - 3d.uv
    - 3d.material
    - 3d.scene
    - 3d.convert
    - 3d.optimize
    - 3d.validate
    - 3d.preview
  interfaces:
    - ThreeDToolAdapter
    - 3D_ProductionPack_descriptor
    - 3D_pack_Artifact_roles_and_validators
  invariants:
    - DCC_SDK_types_stay_adapter_local
    - native_editable_source_is_preserved_where_meaningful
    - exports_bind_exact_source_target_exporter_version_settings_and_ContentRef
    - process_exit_alone_is_not_success
    - render_or_preview_is_not_editable_source_proof
    - Project_style_poly_scale_rules_remain_Project_scoped
    - missing_DCC_affects_route_not_Capability
    - independent_assets_may_run_concurrently_under_existing_scheduler
    - game_engine_is_not_3D_source_authority
    - no_domain_kernel_changes

completion_contract:
  software_and_adapter_source: required
  task_scoped_tests: required
  typecheck_build_runtime_or_DCC_evidence: task_derived_and_required_where_applicable
  exact_Git_commit_and_tree: required
  remote_readback_after_push: required
  current_Drive_continuity_readback: required
  completion_claim_without_matching_evidence: forbidden
```
