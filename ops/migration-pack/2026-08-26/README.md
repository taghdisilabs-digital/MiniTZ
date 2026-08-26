# Biella Clean Migration Execution Pack — 2026-08-26

Status: **Canonical migration execution guidance pack**

Purpose: migrate useful MiniTZ-era capability, information, production experience, data, algorithms, tests, assets, and lessons into Biella **without importing MiniTZ identity, blockers, drift, fake state, permanent agent hierarchy, fixed hardware/provider assumptions, duplicated source, mechanical renaming, or chatbot-only behavior**.

This pack is intentionally split into small executable prompts. Use **one prompt at a time**. Do not load all prompts into one giant context unless a specific task requires it.

## Current durable baseline used by this pack

- GitHub authority: `patrickminitz-web/biella-engine`
- GitHub `main` observed before pack creation: `a112b2231ea76376a3bb170c2159f8772e57ba6a`
- Verified Biella/Codex host: root-owned workspace under `/root/biella`
- Codex home: `/root/.codex`
- Host: AWS EC2 `c5a.4xlarge`, Ubuntu 26.04.1 LTS, 16 logical CPUs, 30 GiB RAM
- Root EBS: 350 GiB; `/swapfile`: 64 GiB; `vm.swappiness=10`
- Installed execution toolchain includes Git/GitHub CLI, Node/npm, Python/pip, Rust/Cargo, Go, Java, Docker, PostgreSQL, AWS CLI, Codex, CMake/Ninja/Clang, FFmpeg, Blender, Pandoc, rclone
- Docker and PostgreSQL were observed active
- Ubuntu Pro: ESM Apps, ESM Infra and Livepatch enabled

These are **current Resource observations**, not permanent Biella capability requirements.

## Source-truth priority

When sources disagree:

1. **Current real execution state** — live repository/worktree, actual files, real process/service/runtime outputs, actual artifacts.
2. **Current GitHub durable source** — exact branch/commit/tree and versioned source.
3. **Current canonical Biella Drive material** — only the newest unique content that does not contradict newer execution/Git evidence.
4. **Verified historical evidence** — useful for lessons and migration, never current runtime truth.
5. **Planning text / old chats / superseded documents** — reference only.
6. **Guess/inference** — never promoted to fact without evidence.

One fact should have one active authority. Duplicate copies do not become additional authorities.

## Prompt order

1. `PROMPT_00_START_HERE_AND_SOURCE_TRUTH.md`
2. `PROMPT_01_CONTINUE_NO_REDO.md`
3. `PROMPT_02_CAPABILITY_AND_EXECUTION_MAP.md`
4. `PROMPT_03_RESOURCE_ADAPTATION_NVIDIA.md`
5. `PROMPT_04_PRODUCTION_INTELLIGENCE_FOUNDER_CTO.md`
6. `PROMPT_05_MIGRATION_FILTER_AND_LEDGER.md`

Supporting files:

- `SOURCE_MANIFEST.md`
- `PACK_MANIFEST.json`
- `SHA256SUMS`

## Minimal review rule

Do not create a permanent reviewer bureaucracy.

For each migration/execution unit:

`inspect current state -> execute bounded change -> verify required evidence -> persist result -> continue`

Use independent validation only when the Task/output/risk actually requires it.

## Core migration rule

Historical material follows:

`raw historical source -> quarantine -> semantic extraction -> classification -> contamination removal -> clean Biella-native candidate`

Never:

`MiniTZ -> rename strings -> Biella`

## Completion rule

Configuration, prose, a successful API response, or an agent saying “done” is not completion.

Primary evidence is the real requested output:
- source + tests/build/runtime when software is requested;
- editable asset/source + validation when production content is requested;
- exact artifact bytes/digest when a file is requested;
- remote read-back when publication is requested;
- measured runtime evidence when performance/resource claims are made.

## Desired operating character

Biella is designed as a founder-grade production/execution system: proactive, evidence-driven, multi-domain, persistent, resource-aware, and capable of completing real work. This is an engineering target that must be demonstrated by outputs; it is not a marketing claim that Biella is automatically superior to every human CTO or IT team.
