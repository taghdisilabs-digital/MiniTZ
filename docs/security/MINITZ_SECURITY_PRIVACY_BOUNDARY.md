# MiniTZ Security / Privacy Boundary

Task identity: `MINITZ-SECURITY-PRIVACY-01`, revision `2`, task digest
`aa0320996354ed4287b1c0dee49d4399760dd11194fd02c4a0252a1af383ab6c`.

The canonical implementation is `src/biella/security_privacy.py`.  It is a
local MiniTZ policy boundary; providers, browsers, remote stores, and task
helpers are not authorities.

## Enforced contract

- Credentials enter the in-process `CredentialVault` only through a
  `credential://` reference.  Receipts expose the reference, scope, state,
  and SHA-256 digest; raw bytes cannot be returned from a credential consumer,
  serialized, or included in sanitized errors.
- `DataResidencyPolicy` rejects raw credential-bearing payloads and permits
  state export only to `minitz://` or `unix://` internal destinations.
- `TrustStore` verifies source bytes against local MiniTZ digest anchors.  A
  remote issuer or provider callback is never consulted.
- `NetworkPolicy` has explicit `ONLINE`/`OFFLINE` modes.  Internal routes are
  local; external routes require an exact local allowlist entry and are denied
  while offline.
- `IntegrityManifest` binds every recovery file to exact SHA-256, size, mode,
  and generation identity.  Symlinks, path traversal, missing files, changed
  files, and unverified manifests are rejected.
- `RecoveryManager` publishes generations through a temporary directory and
  atomic rename, verifies before activation, and rolls back only to the
  pointer's previously verified generation.
- `EvidenceRecorder` writes only privacy-safe, digest-bound evidence.  It does
  not emit raw credential values or create task/progression authority.

Task-specific executable coverage is in
`tests/test_security_privacy.py`; the lifecycle qualification test list runs
it as part of the canonical MiniTZ validation set.
