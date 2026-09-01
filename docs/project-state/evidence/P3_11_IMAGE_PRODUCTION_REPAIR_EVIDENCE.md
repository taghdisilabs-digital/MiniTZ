# P3-11 Image Production Repair Evidence

```yaml
schema: biella.p3-11.durable-repair-evidence/v1
prompt: P3-11
status: QUALIFIED_PENDING_PUBLICATION
source:
  implementation_commit: 31c4aab5a72eaa8763d84537308c6ded7da23a73
  implementation_tree: 76593cefa6ed18669443e11dfaa31b7a5f7c4542
  workflow_commit: dfc20b302c4b1cb6ed6c8c0de8c74f5fd5cdb39b
  workflow_tree: 0de9fbd58db0b62c3abc9fe98685000cb37e0299
qualification:
  github_actions_run: 33541028147
  github_actions_job: 99967021851
  focused_tests: 41_passed_2_bounded_skips
  strict_mypy: PASS
  wheel_sha256: 9d3ff1a457dee52f5bb1bca222b7d1ee0a937d2a32da0313ab76380fc3863643
real_execution:
  cloudflare_model: model://cloudflare/flux-2-klein-4b
  cloudflare_runtime: runtime://cloudflare/workers-ai/v1
  cloudflare_run: run_441c410b45dc4368b8dfb0688e588d45
  cloudflare_generate_edit: 2_of_2_PASS
  cloudflare_decode: 4_of_4_PASS
  l40s_run: run_ba6dda8c32914803a7b46a816406aeb9
  l40s_outputs: 10_exact_operations_10_distinct_content_refs
  l40s_concurrency: producer_fence_2_measured_max_2
  package_import: 1_passed
engine:
  project: prj_659da64f27c742c1a7055a2dafa728af
  task: tsk_778f76e7a8714420a6daac44783b940a/1
  run: run_0001925f6b014896af64188d53062cb1
  graph: graph://prj_659da64f27c742c1a7055a2dafa728af/gph_3d3cbe85d9084f0aa429861fb343e247/1
  integration_node: node://prj_659da64f27c742c1a7055a2dafa728af/gph_3d3cbe85d9084f0aa429861fb343e247/1/nod_e73e964178704a268237a50a46dc837e
  evidence_artifact: artifact://prj_659da64f27c742c1a7055a2dafa728af/art_0bede7439ee24111b53cc706a40a6439/1
  evidence_content: content://sha256/98ee595b2ecfe338e42aec2f14ced8f6ee353a6600880936e12f38c374c05594?size=381904
  integration_artifact: artifact://prj_659da64f27c742c1a7055a2dafa728af/art_02b355aeef8e418ab08cb97ba394e9a0/1
  validation_plan: validation-plan://prj_659da64f27c742c1a7055a2dafa728af/vplan_dafdd7f3fa8b463d994263cda330a003
  validation_results: 11_PASS
  validation_aggregate: 3b9576c157cbb6eb7ba6253926bd6ba764114f26d496229386b85d19baac2808
  evidence_event: event://prj_659da64f27c742c1a7055a2dafa728af/evt_ecbfd621696d444384f73eed61acaf33
  acceptance_event: event://prj_659da64f27c742c1a7055a2dafa728af/evt_5770a8c8ba5b4554a2d6e3fc4c8b9566
kpis:
  corrupt_image_accepted: 0
  source_image_destructively_mutated: 0
  project_visual_style_globalized: 0
  texture_channel_convention_implicit: 0
  color_space_silently_changed: 0
  provider_specific_image_kernel_architecture: 0
artifacts:
  real_archive:
    sha256: 98ee595b2ecfe338e42aec2f14ced8f6ee353a6600880936e12f38c374c05594
    size: 381904
    drive_id: 1V-NGZHsh4bF8_lMW5jTnIdBb34qsGWMx
  engine_evidence:
    sha256: 1ede550ac57be1b54b0bae2595ad2e2509e0c945fc0473544615404708026923
    size: 8758
    drive_id: 11KmLmp_Wp99n96bu6yR00jacqYdfJdYS
  qualification:
    sha256: 2e6e7a78b97ef96311fc4e427569def715fadf23345f70a3b6710f6382121f93
    size: 3758
    drive_id: 13F5MskYW_lKpkaa_HWGwpbQceN_6Jgp0
  wheel:
    sha256: 80c0c29544706d2ce8b19fd68678b193882625e0713a87c832f2996f801fda20
    size: 897848
    drive_id: 1Ti5UwwGbLnXDMxUSPQQ7wyMzAekzXrpA
  cloudflare_qualification:
    sha256: f4bcf8ccd307bee7026d0f4bfef8481bbdc75400fa2f242b6035728cb3674207
    size: 5368
    drive_id: 1XOVDcD3oQjAMf2E45M9Pmi3F81hDUs2E
drive:
  canonical_evidence_document: 1Cd14c7J0wrxqIVAbDJT2IgjYFpGOCW1rXboUe6stny0
  artifact_readback: ALL_EXACT_BYTES_PASS
```
