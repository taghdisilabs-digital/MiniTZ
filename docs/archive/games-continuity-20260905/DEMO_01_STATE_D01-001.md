# Demo 01 canonical state

Run: `demo01-50`  
Task: `D01-001` — Resolve canonical Games truth, active workers, Git/Drive/runtime state  
Observation date: `2026-09-04 UTC`  
Status: `TRUTH_RECONCILED_RUNTIME_ACCEPTANCE_PENDING`

This is a point-in-time reconciliation, not gameplay acceptance or a second task ledger. Mahdi's latest instruction and repository `AGENTS.md` control this run. Current implementation evidence supersedes older implementation-status prose; it does not silently change accepted product decisions.

## Execution and task authority

- Canonical game checkout: `/root/biella/repos/biella-games`.
- Canonical repository: `patrickminitz-web/biella-games`, `main`. Biella Engine remains a separate universal engine project.
- Controller: `biella-codex feed`, service `biella-codex-feed-demo01-50.service`; shared Codex home `/root/.codex`.
- Active queue: `/root/biella/work/demo01-codex-feeder/queue.json`.
- Active runtime state: `/root/biella/work/demo01-codex-feeder/state.json`.
- At observation, runtime state is `RUNNING`, task `D01-001`, completed list empty. Only the feeder consumes this task's final structured result and advances state; this audit does not edit it.
- Next queued task is `D01-002`, **Reconcile Demo-01 requirements with current verified evidence**. Recovery classification is `D01-003`; import is `D01-006`; editor build is `D01-007` in this run.

The untracked `docs/DEMO_01_QUEUE.md` is an older, incompatible numbering scheme. Its six early `COMPLETE_ALREADY` claims do not complete any corresponding IDs in this run. It also names the Spark Drive archive as authority. Those queue/authority claims are superseded here. The file is being edited by another session and has been preserved rather than overwritten. Use the feeder JSON and re-observe current work before continuing.

## Git and concurrent work

The audited published baseline is commit `71762b8f1e0e3f999f5a621559f1c63b6e5b56bb`, tree `646180382511fe05e48dc96435aa31bac8081169`. Live GitHub readback matched all 31 committed blobs and the project descriptor. Local main and cached origin/main matched at audit. No open pull requests were observed. Remote branch `automation/production-executor-v2` is two commits ahead with a separate executor; it is not part of this task or the active unified controller.

Real Unreal bootstrap source already exists, originally published at commit `13c24cd483df5759cb589ef3b411f2b6bbb79a16`, tree `9737514b53664951bb21706f3e6c357b7f050910`. Do not recreate it.

The checkout changed during this audit. Desktop Commander MCP service PID `1166930`, outside the current feeder, copied recovery source/config/map into it at `2026-09-04T23:02:01.123Z`. Its tool history also records queue/config edits. The upstream operator/model identity is `UNKNOWN`; identifying the tool endpoint does not establish product acceptance. Exact event hashes, file hashes and process ancestry are in the evidence bundle.

Preserve the imported `Source/`, `Config/`, `Content/Maps/`, `Build/` and queue changes. They are uncommitted candidate work, not the published baseline. The bootstrap structural verifier initially passed on the clean baseline, then failed on the changed checkout with `AssertionError: EnhancedInput`. This observed mismatch requires affected-source reconciliation; neither wholesale import nor weakening the verifier establishes correctness.

This audit's documentation is published from an isolated worktree, without staging or resetting the concurrent implementation. Before any subsequent source mutation, re-observe the checkout and writer activity. Do not overlap edits to shared paths, terminate an unidentified session, or assume that a log marker proves a feature.

## Canonical Drive identities

The live Games implementation records are under:

`Biella Capability Preparation / inbox / 00_DROP_HERE / 11_IMPLEMENTATION_WORKSPACE`

| Record | Drive identity |
|---|---|
| Current Games project storage subtree, `00_DROP_HERE` | `1JvqWL-_oguZsZfKxgmED2VRBZ9mh2m94` |
| Games implementation workspace folder | `1AaYeLieMpUkf_lWtWYZTDhG7bjbu9Yph` |
| `IMPLEMENTATION_HANDOVER.md` | `1g07rTDMqhxBC6qw9npyaCaToEQTW9ClP` |
| `IMPLEMENTATION_WORKSPACE.md` | `1zwUoe4K30RdDeZl8YNU0YKf1UpG6Yeot` |
| Project authority folder | `1QB_Yls4qDmomkrNFNFsoKHAvIIku-F4J` |
| Authority `docs` folder | `1eK0EBsIoTLxwpjXlmLoFZOFCEDumm36w` |
| Technical decision Google Doc | `1_ju1cqcszPxpw_m397uh0Yzxu2soLcJDAjpGZ8f4ERY` |
| Implementation sequence Google Doc | `1D_v6wVgfXpB27wzmiUIFCh7LQxUF2eUVkQ208IIVMQU` |
| Project source-of-truth folder | `1szQO03C1dYVx6iJybudtvtbvYpRRaxiT` |
| Authoritative concept input, 2026-08-28 | `1i6vqYsjsPcWxO7sJoKgSUY47xk6cPe1-7-AfZ-fWg8g` |
| Master product framework input, 2026-08-28 | `1_wLy65l02YTUmBzqqGZcgsl9DqQZS5bEQrq2Hn7WiAI` |
| Existing cross-project canonical task ledger | `1HZw4AOBf4ccVs_0f5BODrd3CFrX0RBxG7nWC2jmW-Cw` |

The handover and workspace contents explicitly identify the standalone canonical Games repository. Parent/child readback establishes their current placement. Their September 1 Git/host observations were stale. Technical decisions agree with current repository authority: UE 5.8.2, C++ with bounded Blueprint, Windows x64 first, DX12/SM6. Deferred decisions remain `UNKNOWN`.

The project README still declares former root `1dXkhgmnHWgFX8kMazvmF7pBaDtvzNXxL` (`ACTION_ROGUELITE_PROJECT_PREP`). Live readback shows that folder empty; use the observed current parent chain and existing file identities rather than creating a duplicate root.

`BIELLA_GAMES_SPARK_PRODUCTION`, ID `1SgvztxBMthMRbr6BPS-n9OXa2RYyXXDb`, is a separate experimental/recovery tree. Its START, source lock and authority snapshot explicitly describe protected Spark work, frozen canonical input and nonautomatic promotion. Its source lock is `PREPARED_NOT_FINAL`; old HOT/boot records remain pre-activation. Preserve them as historical evidence. Neither its directory name nor later task packs establish canonical acceptance. No Spark authority records were rewritten by this task.

## Runtime, builds and recovery

- Observed host: Linux x86_64 `biella-l40s-worker`, NVIDIA L40S, 46,068 MiB GPU memory. No Unreal Editor, UBT, UAT, game or shader-build process was observed in the runtime snapshot.
- `/opt/unreal/UE_5.8.2/Engine/Build/Build.version` reports 5.8.2, changelist `56702186`; native Linux editor/build/automation tools exist. The previous blanket claim that no Unreal installation is accessible is superseded.
- The accepted Windows x64/DX12 shipping baseline is unchanged. Linux tooling is observed capability, not evidence of a newly accepted shipping platform or Windows qualification.
- `/root/spark-biella-games` has no Git repository. Preserve its source, maps, map-generation scripts and build/log evidence as recovery candidates with file identities; do not adopt its authority files or replace canonical source wholesale.
- Recovery contains an editor module (221,200 bytes, rebuilt September 4 at 00:46) and a standalone Linux executable (297,889,592 bytes). Their existence and build success do not prove a packaged playable build.
- Earlier recovery log `Saved/Logs/BiellaGames-backup-2026.09.04-00.12.52.log` records map load, world startup, GameMode selection and character/controller BeginPlay under `-game -NullRHI -NoSound -NoWindow`. This is useful historical headless bootstrap evidence. Custom possession/PASS messages alone are not independent possession or gameplay proof. That session predates the latest source/module changes and is not acceptance of the current canonical revision.
- Latest recovery log `Saved/Logs/BiellaGames.log` reaches UE 5.8.2 initialization but exits with SDL initialization failure before world load. Repair the observed runtime boundary when build/launch tasks are reached.
- Recovery `BG-PROD-004/005=PASS` markers are unconditional. `BasicWorldGeometry` does not construct geometry; custom character/controller messages do not prove real input, traversal or collision. These markers cannot establish gameplay acceptance.
- Historical `PACKAGE_READY=YES` points to a missing Windows output directory and admits no built EXE/installer. The observed demo tarball contains Python demos and a README. No actual packaged Unreal Demo 01 has been verified.

## Completion and continuation

`D01-001` resolves authority, current work, runtime capability and evidence limits. It does not complete `GAME-00-BOOTSTRAP` or the vertical slice. No external dependency is needed to finish this reconciliation. Build/SDL/module problems are internal repair work at their queued boundaries.

Continue with `D01-002` using the current source and exact Drive source IDs above. Reconcile the active Desktop Commander import before any overlapping writes; preserve newer valid work. Then classify recovery, repair the required bootstrap pieces, build and launch the exact canonical revision, and produce real input/simulation/render/package evidence. Do not restart the historical Spark controller or transfer old queue completion flags.

Evidence: [D01-001 manifest](evidence/demo01-50/D01-001.json). Full readbacks and source/log hashes are retained under `/root/biella/artifacts/games/demo01-50/D01-001/`. Git and Drive publication receipts are recorded there after remote verification.
