# P3-11 — Image Production Durable Repair Evidence

schema: biella.github_evidence/p3_11_image_production_repair/v1
observed_at_utc: 2026-09-01T16:34:43Z
ledger_task_id: ENG-P3-11
prompt: 42/51 — P3-11 Image Production, Editing, Compositing and Texture Pack
prompt_drive_id: 1hZm2VC3xYefqwZBxvIhsChrIjCLcZXsTSoOCG3IKLhM
prompt_revision_id: ANLCKQmIktuk3kRr7yDnnjvM9TPCOM1LN6kv2ye8E1uO_NZncWXTg31-L7LTmJHUg0mKGrb8zJNuI3lfe0JNvkkrxFlyV_jPvSiApt1n9SI

## Source identity

source_before_task_commit: 7a4feb3b1ff32300be67be0c36f1fd923a288e6b
source_before_task_tree: 5ce486ac3cc846c4dc2693861981e4bdb45a095c
validation_commit: dd18a276c6f4ec58ade2d6231072d6965d60602d
validation_tree: 592ac9aff67347f2343dbe4c0d4c7901e3a2beb9

## Existing implementation preserved

- src/biella/image_pack.py — sha256 be25b560cbf7968d86498fc8834f869be37b8ffc21facf5392cb8ad7a9750b80
- src/biella/image_tool.py — sha256 a553919d0fd6d2abe44a1a54af75f01d3dffa2c604a90c92da8f21e679d122bd
- src/biella/cloudflare_image_model.py — sha256 302a798c66d9ab440ed9fde39cdf74955180d618eeb2ebef64e76de2d773394a
- tests/test_p3_11_image_pack.py — sha256 b5d8f5234fe06c356a3aebed170306bbfcc32e3760a82bb017a3e86c7a286e65
- tests/test_p3_11_image_real.py — sha256 b64a5b5fd7397336bbf1e3caafba73ef13ae9ee7cfb86f1478e3f19a325dff2b
- tests/test_p3_11_image_model.py — sha256 be95d86866697a6f81ceacf414557e4d9f8f1e179f655bd1c6e7873479ebbcd6

No image implementation module was rewritten. The durable repair added a focused GitHub Actions evidence workflow and only the CI support required to execute the preserved P3-11 suite on a hosted runner.

## Fresh validation

workflow: P3-11 Image Production Repair
successful_run: 33532394221
successful_job: 99938456554
commit_under_test: dd18a276c6f4ec58ade2d6231072d6965d60602d
conclusion: success
focused_tests: 27 passed, 1 skipped in 62.00s
strict_mypy: Success; no issues found in 3 source files
compileall: PASS
wheel_build: PASS
wheel_size_bytes: 894426
wheel_sha256: db30a5b208302a9780776e678d2e8c6fccfed33af166c6bf5ac83f971a0f375d
evidence_sha256: d86c01960abdef63ec5cb16cddd203cdf25c6d4c59542b5042a7b6ca85400132

The focused tests cover the prompt-required image contract, deterministic real image runtime, exact Artifact derivations, decode/corruption rejection, crop/resize/convert, mask/composite reproducibility, color/data-texture handling, texture channel/convention and material binding, Project/stale-fence rejection, concurrent map dispatch, and provider-boundary corrupt-output rejection.

## Failed-run diagnosis and bounded repair

initial_run: 33532113818
initial_job: 99937538775
initial_result: 7 failed, 20 passed, 1 skipped
root_cause: tests/test_p3_11_image_real.py reuses the accepted P3-05 scheduler environment helper, which hashes /usr/bin/blender, /usr/bin/bwrap, and the glTF exporter path while constructing Resource identity. Hosted GitHub runners lacked those paths, so seven tests failed before executing image behavior with FileNotFoundError for /usr/bin/blender.

repair: .github/workflows/p3-11-image-production-repair.yml creates explicit NON_EXECUTED_FIXTURE support paths solely for scheduler identity hashing. The blender/bwrap fixture executable always exits 97 with an error if invoked. Therefore the repair cannot masquerade as real Blender execution and any accidental execution fails closed. The P3-11 image operations remain the real Pillow/Artifact/Scheduler execution exercised by the tests.

## KPI results

corrupt_image_accepted: 0
source_image_destructively_mutated: 0
project_visual_style_globalized: 0
texture_channel_convention_implicit: 0
color_space_silently_changed: 0
provider_specific_image_kernel_architecture: 0

## Reality classification

deterministic_image_runtime: REAL
p3_05_scheduler_support_paths: NON_EXECUTED_FIXTURE
provider_contract_with_corrupt_output_rejection: REFERENCE_ADAPTER_TEST
external_cloudflare_generation_in_ci: NOT_RUN

The exact prompt permits a real model generate/edit path to be NOT_RUN when unavailable. No authenticated Cloudflare deployment/model integration was available in this execution, so no external model call is claimed.

## Boundary and durability checks

duplicate_scheduler_created: false
duplicate_object_store_created: false
duplicate_validation_framework_created: false
game_or_website_mechanisms_modified: false
raw_history_or_MiniTZ_activated: false
source_images_mutated_in_place: false
project_visual_authority_globalized: false

## Known limitations

- No external Cloudflare image generation was executed in CI; provider behavior was exercised through the existing replaceable adapter contract and corrupt-output rejection tests only.
- The P3-05 Blender/bwrap paths in the hosted workflow are explicit non-executed scheduler identity fixtures, not real 3D evidence.

## Next dependency

ENG-P3-12 — P3-12 Audio Production, Processing, Mixing and Validation Pack durable repair. It may become READY only after ENG-P3-11 is durably COMPLETE in the canonical ledger. Do not start it in this execution.
