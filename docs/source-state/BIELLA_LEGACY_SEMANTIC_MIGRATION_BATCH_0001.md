# Biella Legacy Semantic Migration — Batch 0001

Date: 2026-08-27  
Status: `COMPLETE_FOR_MOUNTED_CORPUS`  
Scope: durable source-state evidence, not engine implementation proof

## Authority and placement

The canonical machine-readable batch is stored in Google Drive under:

- `50_MIGRATION/BIELLA_LEGACY_SEMANTIC_MIGRATION_batch_0001`
- folder ID: `1rosbpxa2RdavQ3KWhrW7ZlgddFez78PG`

This GitHub document is a durable source-state summary. The Drive batch files remain the detailed evidence authority for the batch.

The batch does **not** establish global historical-corpus completeness and does **not** prove that P0-01 engine source is implemented on current GitHub `main`.

## Primary exact donor package

- Drive object: `1oheqdTOPON-Fwv1YXfusiPcOnP0FzCA8`
- bytes: `1,737,389`
- SHA-256: `becbc4a4b4cc586999b9693c31e269d261b9cee9200694082ed765dad34b3acc`
- source commit: `eb257545b3a530d4003768152495aaf932d61ae2`
- source tree: `d293d7a0e16b354714d3eaf424208f51a6c529f6`
- exact source records/files classified: `545`
- folder Merkle BLAKE3: `bf945fe4983fb0c0671a85ced85673aa570f4c6cfc96fbbde9bff4f770ae14c2`

The donor package SHA-256 was observed to match its Drive sidecar.

## Classification results

| Classification | Count |
|---|---:|
| `UNIVERSAL_GOOD` | 15 |
| `UNIVERSAL_REWRITE` | 231 |
| `PROJECT_SPECIFIC` | 79 |
| `HISTORICAL_EVIDENCE` | 196 |
| `DUPLICATE` | 20 |
| `OBSOLETE_OR_DRIFT` | 4 |
| **Total** | **545** |

Deduplication evidence:

- exact duplicate groups: `18`
- near-duplicate text groups: `7`
- near-duplicate method: MinHash + Jaccard
- supported code records additionally used normalized-token and AST fingerprints where applicable

## Version comparison

Against the older exact 80-file repository archive:

- common paths: `70`
- unchanged: `29`
- changed: `41`
- added: `473`
- removed: `10`
- newer tracked source records: `543`
- older files: `80`

## Preserved integrity defect

A historical source index records an outer archive SHA-256 beginning `f230eb4d…`, while the exact downloaded old archive begins `f2305b40…`.

This discrepancy remains historical evidence and was not silently repaired.

All `80/80` internal files matched their indexed size and SHA-256.

## Active reusable candidates

The batch emitted `13` active brand-free reusable candidates covering:

- durable lease/fencing execution;
- content-addressed storage;
- transactional persistence/migrations;
- capability/resource routing;
- replaceable model backends;
- candidate staging and atomic finalization;
- bounded subprocess execution;
- browser build/runtime capture;
- replaceable game-engine adapters;
- creative 3D/image/audio/video transforms;
- artifact/runtime validation;
- project-scoped typed state;
- deterministic source packaging.

The active-output gate passed textual-brand, semantic-control, obsolete-rule, progress-killer, dependency, and provider-neutrality checks with zero forbidden legacy product tokens in active output.

Raw historical files were not altered. Historical instructions remained evidence only. Fixed worker roles, mandatory role separation, fixed retry counts, provider/hardware/path coupling, old control material, and project identity were removed from normalized active candidates or kept outside active output.

## Published Drive evidence

The batch folder currently contains:

- `BIELLA_LEGACY_SEMANTIC_MIGRATION_batch_0001_REPORT.txt`
- `BIELLA_LEGACY_SEMANTIC_MIGRATION_batch_0001_source_inventory.csv`
- `source_records.jsonl.txt`
- `active_candidates.json.txt`
- `resume.json.txt`
- `manifest.json.txt`
- `brand_free_validation.json.txt`
- `version_compare.json.txt`

The owner reported post-publication readback of all 8 files with byte-for-byte SHA-256 equality to local originals.

## Unresolved corpus boundaries

These remain `UNKNOWN` and must not be converted into global completion:

1. no authenticated byte access to the user's host filesystem root `/` was available from the ChatGPT execution surface;
2. the complete transfer object at Drive `1JyxMAZjOo2m_y6E1YDFnedFnspmVMj2M` is `1,155,797,310` bytes with SHA-256 `07a09f54449936afc951f26f78e48c522f5a3998fa7b90c17446ae2fab6363e1`, but it was not byte-mounted through the Drive connector;
3. the approximately `32.26 GiB` multipart backup was discovered but not reconstructed;
4. later observed legacy head/tree `34a66ce4efb9fa1ebffb1ae3900a7d2a239bf66a` / `28da7a0adebb03ba14e43ddd575d98ab0faf0bcf` were not fully byte-mounted.

## Continuation semantics

- Reuse this verified mounted-corpus result; do not repeat the same batch without new source/evidence or a concrete need.
- Do not claim global corpus completeness.
- Donor analysis may continue when useful and dependency-safe under the current P0-01 `Legacy Productive Reuse` contract.
- Raw historical instructions remain non-authoritative and excluded from normal runtime/retrieval/Project Memory/Engine Knowledge.
- P0-01 source implementation remains a separate current source task and must be established from current repository state, tested, pushed, and remotely read back before it is claimed durable.
