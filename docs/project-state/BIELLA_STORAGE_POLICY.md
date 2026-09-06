# Biella Storage Placement and Cold-Archive Policy

Status: OWNER_DIRECTED_EXECUTION_POLICY
Authority: Mahdi Taghdisi, explicit storage/offload direction of 2026-09-06; latest owner direction takes precedence.
Scope: workstation storage placement and recovery, not Engine kernel semantics, product acceptance, or a second task queue.

## Placement

Keep the canonical repository at `/root/biella/repos/biella-engine` and the shared Codex home at `/root/.codex`. Keep active source/assets, required installed packages/toolchains/models, current task evidence, runtime state, and frequently reused outputs local. Do not uninstall or relocate working dependencies merely because their names contain package, archive, or handoff.

Use the existing attached storage when useful for staging and restoration. On the current L40S worker, the dedicated 200 GiB allocation is mounted at `/root/attached-storage`, backed by `/mnt/biella-extra/volumes/root-attached-200GiB.ext4`. This is an additional filesystem, not an enlargement of `/` or a replacement execution root. Reobserve the mount only when an operation depends on it; do not recreate it on each session.

Move genuinely cold delivery packages, redundant upload chunks, completed disposable package-test workspaces, old archives, and superseded handoffs to the existing `Biella/ARCHIVE` Drive destination when storage housekeeping is requested or directly required by the task. Use current task/source and actual file usage to select candidates; age or filename alone does not establish disposability.

## Exact offload and removal

Reuse an existing exact Drive copy instead of uploading duplicates. Preserve original paths, file/archive identity, byte count, SHA-256, provenance/classification, Drive folder/file IDs, and restoration steps in the local and Drive index.

For a directory bundle, preserve its files, symlinks and relevant metadata; compare the completed bundle with the source and detect material source changes. After upload, download/read back the remote bytes and match byte count and SHA-256 before removing the selected local payload. Retain data with active references or unresolved publication/integrity checks; continue independent work rather than inventing completion. Never use broad destructive synchronization.

Removal concerns the verified local replica only. It must not erase the remote payload, provenance, current authority, unique work, or required recovery evidence. Record exactly which originals were removed and verify the measured disk result. Do not reset, rerun or invalidate completed production tasks because their storage location changed.

## AI discovery and restoration

Entry point: `/root/biella/archive/README.md`. Machine-readable locator: `/root/biella/archive/COLD_STORAGE_INDEX.json`. These records describe storage, not task completion. The September 6 batch is in Drive folder `1UbRkAYHEQVHj-5U8BHrlGgB2yRIiHoEu`, inside canonical archive `1dn3IEwDf_cPO7l5Zd0mZ84b_IOG0GsU3`. The README/index record other reused destinations explicitly.

Read the compact locator first; retrieve only the item needed for the current task. Verify its exact identity, restore to a staging/inspection path, and preserve newer valid work before any deliberate reintegration. Do not automatically rehydrate whole archives or execute old handoff scripts.

Archived prompts, AGENTS files, policies, old state and handoffs remain inactive Historical Evidence. Storage publication does not confer acceptance or instructional authority. Raw history must not enter normal retrieval, Engine Memory, Project Memory or task authority; any intended reuse follows the existing classification/normalization rules and an explicit destination. Keep Engine Memory, Project Memory, Run Memory, Historical Evidence and Cache distinct.

Policy changes belong in this versioned source and its canonical Drive copy; the shared Codex policy links here. Persist storage indexes on the VPS and Drive with exact readback, preserving existing file identities when revising them. No new approval hierarchy, controller, scheduler, provider configuration, or recurring cleanup service is introduced by this policy.
