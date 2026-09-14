# MiniTZ Secret / Private-State Boundary

Task: `SECRET-01` revision 8
Authority: current MiniTZ Task Program + owner direction
Status: implementation contract; no lifecycle authority

## Purpose

MiniTZ keeps private memory and credential-bearing state inside explicit scopes while allowing privacy-safe identities, references, digests, and approved semantic results to cross into ordinary execution/evidence paths.

Raw API keys, passwords, login/refresh tokens, private keys, browser/session authentication material, and equivalent secret values never belong in ordinary prompts, Booster/Codex handoffs, semantic memory, general caches, task state, evidence, Git, Drive, public artifacts, or normal logs.

## State domains

- `OWNER_PRIVATE_MEMORY` — owner-private semantic state; no raw credential values; no universal projection.
- `OWNER_PRIVATE_CACHE` — private rebuildable acceleration; no raw credential values; no universal projection.
- `API_SECRET_VAULT` — protected raw API/provider authentication values.
- `CREDENTIAL_VAULT` — protected raw credentials and backend references.
- `PROJECT_MEMORY` — project-scoped memory; never universalized implicitly.
- `CUSTOMER_MEMORY` — customer-scoped memory; never universalized implicitly.
- `PUBLIC_ENGINE_KNOWLEDGE` — validated project-neutral knowledge safe for MiniTZ-wide use.

## Extractor routing

Ordinary extractors never receive raw bytes from owner-private or vault domains.

- Owner-private memory/cache and both vaults route to `OWNER_PRIVATE_ISOLATED`.
- Project memory routes only through `PROJECT_SCOPED` processing.
- Customer memory routes only through `CUSTOMER_SCOPED` processing.
- Public/engine knowledge may use `ORDINARY_SAFE` extraction.

A private extractor may emit only approved semantic results plus privacy-safe object fingerprints. Raw private bytes and plaintext paths are not emitted into ordinary evidence/logging.

## Private object discovery

Outside the protected boundary, discovery records only non-secret metadata needed for identity/provenance: content digest, path digest, size, file mode, domain, and safe semantic relations. The implementation must not echo object bytes or plaintext protected paths.

## Booster / Codex context

Booster and Codex handoffs may contain exact task identity/revision/digest, non-secret implementation references, capability/resource metadata, privacy-safe evidence references, credential references/IDs/digests, and bounded MiniTZ memory that already belongs to the task/system scope.

They must not contain raw credential values. Task-scoped memory must match the exact current task revision/digest; stale revisions and foreign-task memory are excluded. System-wide MiniTZ policy/memory remains MiniTZ-wide. Bounded projections have authority `NONE` and remain derivatives of lossless underlying evidence.

## Secret migration

Secret migration is not an ordinary filesystem rename or identity cutover. It is a separate owner-authorized transaction.

Required sequence:

1. owner supplies secret-unlock input interactively;
2. input is never persisted directly;
3. a policy-selected KDF derives a root key-encryption key (KEK);
4. independent domain keys are created for isolated secret/private domains;
5. protected values are imported encrypted through the credential subsystem;
6. references/consumers are rebound;
7. functional access is validated;
8. cutover is recorded with privacy-safe evidence;
9. unnecessary plaintext duplicates are retired only after successful cutover.

The current protected store is excluded from ordinary rename/migration work.

## Verification boundary

Exact comparison against configured raw credential values may occur only inside the private verifier execution boundary. Its ordinary receipt contains counts, digests, target identities, and PASS/FAIL/UNKNOWN status without returning raw secret values or secret variable names.

Host VPS OS references remain read-only. SECRET-01 does not start MiniTZ, local AI, Codex, Boost services, or any sleeping runtime service.
