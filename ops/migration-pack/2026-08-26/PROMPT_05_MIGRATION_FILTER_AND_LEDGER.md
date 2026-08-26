# Prompt 05 — Migration Filter, Deduplication, Drift Removal, and Source Ledger

## Objective

Move valuable historical material into Biella without moving historical contamination.

## Classification

Every historical item considered for active migration receives one of: `UNIVERSAL_GOOD`, `UNIVERSAL_REWRITE`, `PROJECT_SPECIFIC`, `HISTORICAL_EVIDENCE`, `DUPLICATE`, `OBSOLETE_OR_DRIFT`.

No unclassified historical item becomes active instruction/source, Project Memory, Engine Knowledge, or normal retrieval.

## Admission pipeline

`raw source -> immutable quarantine + provenance -> semantic extraction -> classification -> contamination removal -> normalization -> Biella-native candidate -> task-specific verification -> active destination when appropriate`

Raw source remains historical/quarantine evidence.

## Reject/block from active Biella

### Drift/stale infrastructure
Old VPS paths/IPs/machine names, old Spot assumptions, fixed Drive IDs in runtime logic, hardware snapshots as capability truth, stale Git heads as current, old provider availability/pricing, obsolete installation instructions.

### Blocker habits
Remove mandatory owner/reviewer/manager gates not required by the current Project, permanent maker/critic/validator/repair sequences, readiness ceremonies, arbitrary repair counts, global heavyweight locks, serial rules without dependency/resource reason, and stopping everything because one optional provider/resource is absent. A real technical dependency may block only affected scope; continue unaffected work.

### Fake/imaginary state
Reject nonexistent agents/model deployments/GPUs/services/repos/files, unobserved test/build/deploy success, and unverified synchronization. If useful, preserve only as `HISTORICAL_EVIDENCE`.

### Mechanical renaming
Reject migrations that only change MiniTZ names/paths/agents/providers/hardware/control-file locations while keeping historical architecture. Extract useful semantics and reimplement cleanly.

### Wrong code / bad habits
Do not promote code that cannot build/test under its claimed contract, hidden global mutable authority, cache as only authority, stale worker finalization, provider-specific Task/Capability identity, hardcoded project lore/assets in core, silent-success fallback, duplicate Biella mechanisms, or separate scheduler/memory/authority inside production packs.

### Chatbot behavior
Do not migrate instructions that force execution-capable systems to only explain/plan when actual execution is possible.

## Deduplication

Deduplicate by exact digest, normalized content, semantic duplicate, then conflict resolution. Keep one active authority; preserve only relevant superseded evidence. Do not keep multiple active copies “just in case.”

## Source precedence

GitHub `patrickminitz-web/biella-engine` is durable source/version history. Pack-creation `main` was `a112b2231ea76376a3bb170c2159f8772e57ba6a`; re-read current HEAD at execution time.

Canonical Drive root: `1Z6_qwN9hfHIheXZ_9pYCG8dRDMuRN-l7`. Useful live areas: `00_START_HERE`, `10_ARCHITECTURE`, `20_CURRENT_STATE`, `30_EXECUTION`, `40_PROMPTS`, `50_MIGRATION`, `biellawebsite`. Import unique semantic value, not every copy.

Historical MiniTZ is quarantine-only donor corpus. Vendor research informs adapters/resources but never overrides Biella authority.

## Known drift already detected

Mixed-era Drive statements include old `/home/ubuntu/biella-work/...`, superseded `/srv/biella` workspace instructions, older GitHub head `29ea...`, older CPU/runtime observations conflicting with the current AMD EPYC `c5a.4xlarge`, and stale status text that tries to force P0-01 before inspecting the active workstation's real repository/task. Never combine these into one current-truth record.

## Ledger fields

Record source ID/path/type/revision/digest/time, classification, semantic summary, contamination removed, duplicate/supersedes relationship, destination scope, output artifact/object ref, verification/evidence, and status.

## Delete/archive rule

Before deleting the only source of irreplaceable bytes: manifest them, create intended durable copy, verify digest/read-back, and confirm unique active knowledge/assets exist elsewhere. This is byte-safety, not approval bureaucracy.

## Execution prompt

> Process the selected migration source through quarantine, semantic extraction, classification, deduplication and contamination removal. Do not bulk-copy historical instructions into active Biella. Reject stale infrastructure, fake state, blocker ceremonies, permanent agent hierarchy, mechanical renames, duplicate mechanisms and chatbot-only behavior. Preserve real functional code/data/assets/knowledge/tests/benchmarks/failure lessons as evidence-backed Biella-native candidates. Record a compact source ledger and continue in batches without re-reviewing already classified unchanged items.
