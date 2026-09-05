# One-Repo Consolidation Provenance — 2026-09-05

Status: `VERIFIED`
Authority: Mahdi Taghdisi approved one canonical repository/workspace and no loss of completed or in-progress work.
Destination repository: `patrickminitz-web/biella-engine`
Destination checkout: `/root/biella/repos/biella-engine`

## Initial destination base

- commit: `086b79de3a5bf3f6ea00ced13cc1433c09c37a78`
- tree: `5340d28dd98d372afd590b4b25d4e528cac3c0e7`

## Admitted current Project progress

### Biella Games
- source repository: `patrickminitz-web/biella-games`
- initial preservation floor commit: `7152b533b7b26ebb6cca5ec67d7b85c4d59fac2f`
- initial preservation floor tree: `dfd183d8b60da26cfa2b5281a67bdcb4b38eb183`
- earlier frozen progress commit: `2193b769e61b43ebfc4f910f6380c68e6b828cd5`
- earlier frozen progress tree: `b80f2fcee95b3180d0a5a7b6664819876962ce6e`
- latest frozen progress commit: `f7e74205988cb48946e62efeffe5c5330ec6437b`
- latest frozen progress tree: `1324b3dd942927352abaa2ef70a463cbdfca53db`
- classification: `PROJECT_SPECIFIC`
- destination: `projects/biella-games/`
- initial full-import verification: `88/88 Git blobs matched exactly`.
- late delta import: `9/9 changed paths` imported from the exact latest preservation commit.
- Demo state at latest freeze: D01-001..D01-028 complete; D01-029 pending with partial navigation/positioning source and build/runtime evidence preserved but no completion claim.
- all parallel production workers were stopped before the final frozen snapshot was imported.

### Website/control
- source branch commit: `b621a0680c5586a1502558efb81ff084f8d1da74`
- source tree: `19b9e0e60b64d0b216fc09f5fb368eed26da447c`
- classification: `UNIVERSAL_GOOD` for Website/control project surface; no older Engine source overlay admitted.
- destination: `website/`, selected Website/control workflows, `.openai/hosting.json`.

## Reusable capability-preparation input

- source repository: `patrickminitz-web/capability_preparation`
- source commit: `aa718584a99c0cee1884488bb4dafec4d2e94c05`
- source tree: `d48af123ba3ba5fb0205091aad84c11156f67493`
- `schemas/source_record.schema.json`: `UNIVERSAL_GOOD` -> `schemas/source_record.schema.json`.
- dated playbook/source guide/registry/research manifest: `HISTORICAL_EVIDENCE` -> `docs/reference/capability-preparation/source/`.
- source `AGENTS.md`: `OBSOLETE_OR_DRIFT` as active policy; blob identity remains in the archived source repository and is not activated.
- source `README.md`: `HISTORICAL_EVIDENCE` -> `SOURCE_README.md`.

## Future AAA-SF program

- source Games branch commit: `297129637fded33dc0e3636954645e5655803928`
- source tree: `3fcb1657c0b70350a5bccdb8b24ce8a135f2bfd5`
- classification: `REFERENCE_OR_PLAN`; status remains `FUTURE_PROGRAM_BLOCKED`.
- destination: `docs/future/aaa-challenger-solo-founder/`.
- local `AAA_SF_TASKS_BUNDLE.zip` sha256: `6e40f62b2cb6e425a7be6aee11e299d9dcd862872b4512499f76f46b5132f4e4`.
- ZIP verification: all 78 files byte-match tracked source; classification `DUPLICATE`; redundant but preserved as archived/non-authoritative progress; do not delete during this migration.

## Preserved but not automatically activated

- Demo continuity commit: `44b9a90e9f9143b7f9c859682f5595d621955882`, tree `19fe536524075110f5229ab15bbf2b5098a26c96`; classification `HISTORICAL_EVIDENCE` unless a specific still-current delta survives comparison with the newer Demo queue.
- state-bridge preservation commit: `e50cb09a6d0b8f36da72ef16d4148620311a663c`, tree `e619ff08bb51a0ffab40efff47f56a4ca28a2c13`; classification `UNIVERSAL_REWRITE`. It contains design/test scaffold but no `biella_state_bridge.py` implementation, so no nonexistent implementation is promoted.
- former `/root/spark-biella-games`: recovery input only; moved without byte deletion to `/root/biella/archive/recovery/spark-biella-games` after monorepo qualification.

## Verified consolidation closure

- canonical active repository: `patrickminitz-web/biella-engine` / `/root/biella/repos/biella-engine`.
- verified implementation commit: `ee656b419bbd2ecf1fe5702c490355feea26b4e2`; tree `d598dfb928ca3e283d5b508c43f46fd69dde8eef`.
- latest Games preservation commit: `f7e74205988cb48946e62efeffe5c5330ec6437b`; D01-001..D01-028 complete, D01-029 pending.
- Engine GitHub active branches: `main` only. Fifteen removed branch heads are retained by exact `archive/branch/*` tags before branch deletion.
- `patrickminitz-web/biella-games` and `patrickminitz-web/capability_preparation` are archived/read-only, not active source authorities.
- old local Games repository moved to `/root/biella/archive/repos/biella-games-preserved-20260905`.
- Spark recovery moved to `/root/biella/archive/recovery/spark-biella-games`; it remains historical recovery, not active input.
- superseded `/root/biella/work/games-production.json` SHA256 `e23bd1634ae14cad059a8196f4e82dd6de982014c4892616348c2393ada18ecd` was removed after canonical `projects/biella-games/docs/PRODUCTION.md` became verified authority.
- temporary Games import copy plus obsolete local workstation recovery/backups/checkpoints were removed after current main/tests superseded them.
- Drive root `Biella` ID `1Z6_qwN9hfHIheXZ_9pYCG8dRDMuRN-l7` now exposes `CURRENT`, `PROJECTS`, `OUTPUTS`, `ARCHIVE`; Games folder ID `1SgvztxBMthMRbr6BPS-n9OXa2RYyXXDb` is preserved at `PROJECTS/GAMES`.
- historical Drive execution/handoff/recovery/capability-preparation trees were reparented under `ARCHIVE` without byte deletion.
- automated Games feeder remains `STOPPED_BY_OWNER`; no production task was advanced by the consolidation process.

## Preservation rule

No progress is deleted by this migration. Once a source copy is superseded, its active routing is disabled and its durable identity/location is archived. Canonical Git/Drive readback must be verified before any authority switch.
