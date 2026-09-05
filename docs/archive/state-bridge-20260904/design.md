# GitHub + Drive Current-State Bridge Design

```yaml
id: BIELLA_GITHUB_DRIVE_CURRENT_STATE_BRIDGE_2026-09-04
status: APPROVED_FOR_IMPLEMENTATION
effective_at: 2026-09-04
owner: Mahdi Taghdisi
scope: Biella Engine + Website + Games current-state continuity
```

## Goal

Keep GitHub, canonical Google Drive current-state records, the L40S workstation, and the private browser control console on one verified current-state view without destructive synchronization or historical cleanup.

## Authority and direction

- Current execution state remains highest authority, followed by current GitHub source, then current canonical Drive.
- GitHub remains source truth for code, commits, branches, CI, and deployment evidence.
- Drive remains the durable current-state, active-task, navigation, and evidence publication layer.
- The bridge is one-way publication from verified current Git/source state to exact Drive records and the browser manifest.
- Existing archive, recovery, duplicate-title, historical, and reference records are never deleted or promoted automatically.
- Exact Drive file IDs, not titles, determine mutable canonical targets.

## Canonical Drive targets

The registry stores these exact current targets:

- Project root: `1Z6_qwN9hfHIheXZ_9pYCG8dRDMuRN-l7`.
- `20_CURRENT_STATE/03_BIELLA_CURRENT_STATE.md`: `1wiWcdWt4hmTf3narsLw4OqGu_ueKOSa4`.
- `30_EXECUTION/04_BIELLA_ACTIVE_TASK.md`: `1liutA8evH6rPjk-U4tgR13l_kqBrx-DF`.
- `00_START_HERE/BIELLA_PROJECT_CONTEXT_INDEX_CURRENT_2026-09-04.md`: `1h0roTID3ebR0xUwWeq5CZTh5V8hInzAO`.
- The generated `20_CURRENT_STATE/BIELLA_CURRENT_STATE_MANIFEST.json` receives one Drive ID on first publication; that ID is then committed to the registry and must remain stable.

Before overwriting any existing canonical target, the bridge resolves its path through `gdrive:` with the project root ID and requires the observed Drive ID to equal the registry ID. A mismatch aborts the write.

After every write, the bridge reads the exact Drive object back, compares SHA-256 bytes with the local publication artifact, and re-checks the Drive ID. A publication is not reported successful without both checks.

## Manifest

The local canonical generated manifest is `/var/lib/biella-state/current-state.json`. It is also published byte-for-byte to the exact Drive manifest target.

The manifest records:

- schema and generation time;
- Engine, Website, and Games local/remote branch and commit state;
- local/remote synchronization state (`MATCH`, `AHEAD`, `BEHIND`, or `DIVERGED` when determinable);
- current Engine task ID, title, ledger state, execution state, and exact prompt Drive ID from the current state/task records;
- latest observable GitHub CI result for each lane when available;
- Ollama, control gateway, and permanent tunnel service state;
- permanent control-console URL;
- exact canonical Drive source IDs and the manifest publication ID.

## Source and publication rules

`docs/project-state/03_BIELLA_CURRENT_STATE.md` and `04_BIELLA_ACTIVE_TASK.md` remain human-readable mutable source records in Git. The bridge parses their YAML blocks, requires them to be readable, and refuses publication when either source file has uncommitted changes.

The bridge publishes those exact committed files to their exact canonical Drive IDs. It also generates a concise current-only navigation index from the same manifest and publishes it to the existing context-index ID. This removes stale copied task text from the index while retaining navigation links and authority boundaries.

The bridge never scans Drive by filename to choose a mutable target and never deletes duplicate-title files. It may list/stat a known path only to prove that the path still resolves to the registered ID.

## GitHub validation

A focused GitHub Actions workflow runs the state-bridge unit tests and offline validation. CI generates an ephemeral manifest from repository state and verifies that:

- the source registry is structurally valid and contains the exact required canonical IDs;
- current state and active task schemas parse;
- the generated GitHub lane SHA matches the workflow SHA where applicable;
- generated manifest structure is valid;
- no Drive network write is attempted in CI.

Drive byte readback remains a VPS publication check because the canonical Drive OAuth remote is local to the workstation.

## Browser integration

The control gateway reads `/var/lib/biella-state/current-state.json` when present. Overview responses use the manifest commit/branch/task summary and expose a read-only state-manifest endpoint. If the manifest is missing or invalid, the existing direct live-state adapter remains the fallback.

A successful browser agent run that changes a lane HEAD triggers a bounded `biella-state-sync` publication attempt. Publication failure is reported as a state-sync event but does not undo the agent's verified code work.

## Terminal integration

`biella sync-state` performs a verified publication. `biella state` prints the compact local manifest when available.

`biella work` captures the current repository HEAD before and after a successful run. If the HEAD changed, it silently invokes state synchronization before printing the final low-noise agent result. A sync failure is material and is appended as a compact `STATE_SYNC:` line; ordinary successful synchronization adds no narration.

## Failure behavior

The bridge fails closed for canonical writes on unknown IDs, dirty mutable state files, missing source files, Drive readback mismatch, or inability to resolve a registered canonical target. It does not roll back valid Git commits because a publication dependency failed.

GitHub/Drive/service observations that are unavailable but do not affect canonical file identity are represented as `DEGRADED` or `UNKNOWN` in the manifest rather than invented.

The current `gdrive:` OAuth remote is used because it is the working authenticated Drive remote. The nonfunctional `drive:` ADC remote is not modified. No credential value is printed or copied into repository files.

## Non-goals

- No whole-repository backup or bidirectional Drive sync.
- No deletion or renaming of duplicate Drive ledgers.
- No automatic promotion of historical/recovery material into current truth.
- No new branch-protection policy.
- No broad GitHub workflow fan-out.
- No replacement of the existing active-task/current-state records.
