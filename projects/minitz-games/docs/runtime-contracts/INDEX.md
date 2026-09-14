# Biella Games Runtime Contract Index

Status: `CANONICAL_RUNTIME_CONTRACT_INDEX`
Authority: Mahdi Taghdisi
Project: Biella Games
Repository: `patrickminitz-web/biella-engine`  
Project path: `projects/minitz-games`

## Purpose

This file identifies the single active source file for every accepted Biella Games runtime contract number currently defined in this repository.

Contract numbers are requirement identifiers and **not implementation order**. Execute the game according to `docs/IMPLEMENTATION_SEQUENCE.md`.

Each contract number has exactly one active physical authority file in the current tree. Superseded/overlapping compatibility files are not active contract authority.

## Active contract authority

| Contracts | Active source | Blob SHA |
|---|---|---|
| 01–10 | `AAA_TPP_RUNTIME_CONTRACTS_01_10.md` | `0372b32d6d49d023fe9235490524b9717e952a5a` |
| 11–20 | `AAA_TPP_RUNTIME_CONTRACTS_11_20.md` | `3af7ae682715d896fabdaeba62f68b748f66616a` |
| 21–23 | `AAA_TPP_RUNTIME_CONTRACTS_21_23.md` | `6ca7dc4b4bf0c35f59ecaae9efce9acadc065d6d` |
| 24–30 | `AAA_TPP_RUNTIME_CONTRACTS_24_30.md` | `1a0902517ea65071eb2f4fb64d7b9c4f56e2fb5f` |
| 31–39 | `AAA_TPP_RUNTIME_CONTRACTS_31_39.md` | `4fc9959e4b045c466212dd9196285894c3fdfa64` |
| 40–49 | `AAA_TPP_RUNTIME_CONTRACTS_40_49.md` | `6082123f04404677d965abfb4325e73f6f8ae955` |
| 50–59 | `AAA_TPP_RUNTIME_CONTRACTS_50_59.md` | `c7be7096ac283dc0dfca66e7648f501b365b777a` |

The active ranges cover Contracts **01 through 59 exactly once**.

Canonical range chain:

`01–10 -> 11–20 -> 21–23 -> 24–30 -> 31–39 -> 40–49 -> 50–59`

## Superseded 21–30 bridge

The historical `AAA_TPP_RUNTIME_CONTRACTS_21_30.md` bridge is explicitly **SUPERSEDED**. Its historical status was `SUPERSEDED_COMPATIBILITY_INDEX`.

It has been removed from the current active runtime-contract directory so there is no overlapping physical authority. Git history preserves it for recovery/provenance only.

Current active authority is:

- Contracts 21–23 -> `AAA_TPP_RUNTIME_CONTRACTS_21_23.md`
- Contracts 24–30 -> `AAA_TPP_RUNTIME_CONTRACTS_24_30.md`

Do not restore or use the historical 21–30 bridge as active authority unless an explicit owner instruction supersedes this index.

## Current implementation relationship

The existence of a runtime contract does not prove that feature is implemented.

Feature completion still requires the editable game/project source plus the task-derived runtime/build/play/evidence defined by the relevant contract and `AGENTS.md`.

The engine/runtime selection gate is satisfied by the accepted `docs/TECHNICAL_DECISIONS.md` baseline: Unreal Engine 5.8.2, C++ primary, Windows PC x64, DirectX 12 + Shader Model 6.

The repository still has no accepted engine-native editable game project. The required next implementation boundary is:

`CREATE REAL BiellaGames.uproject UNREAL ENGINE 5.8.2 C++ PROJECT -> CREATE Source/Content/Config/Plugins BOUNDARIES -> OPEN/LAUNCH IN UE 5.8.2 -> RECORD SOURCE/RUNTIME EVIDENCE -> BEGIN STAGE 1.1 PLAYER + CAMERA + INPUT`

No Contract 60 or later is active merely because 01–59 are indexed here.
