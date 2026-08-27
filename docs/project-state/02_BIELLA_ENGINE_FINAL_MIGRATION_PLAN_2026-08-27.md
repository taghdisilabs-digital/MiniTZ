# Biella Engine Final Migration Plan

**Date:** 2026-08-27  
**Status:** Final execution plan from the last five-hour project state, current durable GitHub and Google Drive sources, and the supplied workstation-tree inventory  
**Authority:** Mahdi Taghdisi is the final authority for product direction, priorities, architecture, infrastructure use, acceptance, and work policy.  
**Workstation-tree coverage:** Mahdi reports the represented `/root/biella` tree as approximately 23 MB. The supplied `biella-tree.txt` is a 642-line, 33,425-byte path inventory with no per-file sizes and with `tooling/playwright/node_modules/` collapsed. It is used here as verified path/resource inventory; this plan does not claim that every underlying byte or file body in the 23 MB tree was read.

## 1. Final decision

Biella keeps the already-claimed architecture and execution structure. Migration begins from the existing `/root/biella` workstation layout and the existing GitHub repository. The captured workstation inventory shows no listed checkout; if that remains true at execution time, establish the single checkout at `/root/biella/repos/biella-engine`. This is not a new repository, host, workspace, or redesigned plan.

The immediate execution boundary is:

```text
CONFIRM ACCESS TO THE EXISTING /root/biella WORKSTATION
→ PRESERVE THE EXISTING HOST SCAFFOLD, TOOLING, LOGS, AND INSTALL STATE
→ CONFIRM ONCE WHETHER /root/biella/repos/ IS STILL EMPTY
→ IF EMPTY, ESTABLISH ONE CHECKOUT AT /root/biella/repos/biella-engine FROM CURRENT GITHUB MAIN
→ READ THAT CHECKOUT / CURRENT_TASK STATE ONCE
→ PRESERVE ANY REAL NEWER LOCAL WORK
→ OTHERWISE USE CURRENT GITHUB MAIN AS THE DURABLE BASELINE
→ EXECUTE P0-01 CLEAN-ROOM MIGRATION FIREWALL ONLY
→ TEST / TYPECHECK / BUILD
→ COMMIT / PUSH / REMOTE-READBACK COMMIT AND TREE
→ UPDATE DRIVE CONTINUITY STATE
→ STOP AT THE P0-01 BOUNDARY
```

Do not create or migrate work into `/srv/biella`. That path belongs to a superseded replacement-workspace plan. Do not reinstall the host toolchain, reprovision the instance, initialize a new repository, create a second checkout, add security architecture, extract the historical backup broadly, or add approval/reviewer ceremonies.

Current durable implementation status is **0/51**. Current GitHub `main` contains durable documentation, operational evidence, the VPS configurator package, and the clean migration execution pack, but no engine `src/` directory and no repository-root `package.json`. `/root/biella/tooling/playwright/package.json` and its lockfile are host browser tooling, not Biella Engine implementation. Therefore none of the 51 implementation prompts is durably complete on current GitHub `main`.

## 2. Source and authority order

When facts conflict, use this order without synthesizing incompatible claims:

1. **Current execution state** — the real workstation checkout, files, processes, outputs, and artifacts.
2. **Current GitHub durable source** — exact branch, commit, tree, and versioned files.
3. **Current unique canonical Drive material** — newest non-conflicting live project records.
4. **Verified historical evidence** — reusable lessons and evidence only.
5. **Planning text and old chats** — reference only.
6. **Unverified inference** — never promoted to fact.

One fact has one active authority. Chat context, RAM, GPU memory, caches, temporary workspaces, and worker disks are never the only durable copy of meaningful work.

## 3. Locked Biella architecture

The durable universal kernel remains approximately:

- Project
- Task
- Run
- Capability
- Graph
- Node
- Artifact
- Resource
- Event
- Knowledge

The stable execution flow remains:

```text
Project → Task → Run → Graph → Node → Capability
        → compatible implementation → Resource
        → Artifact / Event / scoped Knowledge
```

The following invariants do not change:

- Project namespaces and Project data are isolated.
- Tasks are typed and revisioned; they describe desired outcomes, not worker/provider topology.
- Graph revisions are immutable; replanning creates a new revision.
- Independent Nodes may execute concurrently when dependencies, side effects, and resources permit.
- Run attempts use leases and fencing; stale executors cannot finalize newer Runs.
- `Artifact != ContentRef != StorageLocation`.
- Exact bytes use cryptographic content identity.
- Engine Memory, Project Memory, Run Memory, Historical Evidence, and Cache remain separate.
- Run/agent output cannot write directly into Engine Knowledge.
- Capability is semantic; provider, model, tool, GPU, machine, cloud, and runtime are replaceable implementations or Resource state.
- Validation derives from the Task/output contract; there is no permanent reviewer or critic stage.
- Agents/workers are dynamic execution resources, not a permanent management hierarchy.
- Cache and workspace state are rebuildable and non-authoritative.
- Website and website-document work remain outside kernel boundaries.

## 4. Preserve both existing structures without conflating them

### 4.1 Canonical 51-prompt implementation program

This is the numbered implementation order and remains **P0 → P1 → P2 → P3 → P4**.

| Program phase | Prompts | Purpose | Entry condition | Exit condition |
|---|---:|---|---|---|
| P0 — Clean Kernel + Migration Firewall | 01–10 | Firewall, isolation, typed contracts, identity, Graphs, Events, durable execution | Current durable source and exact P0-01 contract | P0-10 integration qualification passes from observed evidence |
| P1 — Durable Cognition + Resources + Scheduler + Routing | 11–19 | CAS, scoped memory/knowledge, call ledger, resume, resources, concurrency, routing | P0-10 passes | P1-09 and relevant P1 integration pass |
| P2 — Universal Execution Fabric | 20–31 | Replaceable filesystem, process, Git, runtime, HTTP, model, browser, database, storage, retrieval, workspace, validation adapters | P1 passes | P2-12 passes with real attribution and durability evidence |
| P3 — Production Capability Packs | 32–45 | Software, web, game, 3D, media, rendering, packaging and publishing | P2 passes | P3-14 cross-domain durable delivery proof passes |
| P4 — Evidence-Based Learning + Qualification | 46–51 | Controlled comparison, routing/resource/repair/recipe learning and full qualification | P3 passes | P4-06 full P0–P4 qualification passes |

The exact prompt order is one numbered prompt at a time. Work inside a prompt may run concurrently where safe, but a later numbered prompt does not begin before the current prompt's required result is durably closed.

### 4.2 Accepted build/deployment overlay

The separate build-phase structure also remains unchanged:

| Build phase | Exact role |
|---:|---|
| 0 | Source truth and durability reset |
| 1 | Versioned contract spine |
| 2 | P0 durable kernel |
| 3 | P1 durability, cognition, resources and routing |
| 4 | First real local model-provider implementations |
| 5 | P2 universal execution fabric |
| 6 | Observability and recovery qualification |
| 7 | High-end fully local single-node profile |
| 8 | Optional multi-node scale profile |

This overlay does not rename, remove, or reorder P0–P4. The versioned contract spine is established through the exact numbered contract prompts and stable interfaces; it is not a new parallel architecture or an extra management phase inserted before P0-01.

### 4.3 Approved Option C — Biella Universe website program

Option C remains the approved product-delivery program for the public Biella Universe website at [`biellagames.dev`](https://biellagames.dev). It is not removed, postponed until all 51 engine prompts finish, or merged into the universal kernel.

The durable authorities are:

- `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` — approved 36-task execution program;
- `docs/biellawebsite/BIELLA_UNIVERSE_36x51_ENGINE_CROSSMAP.md` — bidirectional website-to-engine ownership map;
- `docs/biellawebsite/BIELLA_WEBSITE_ASSET_MANIFEST.md` — 60-slot visual/document control record.

The Option C sequence remains **U0 → U1 → U2 → U3 → U4 → U5**:

| Website phase | Tasks | Website-owned outcomes |
|---|---:|---|
| U0 — Discover and lock the universe | BU-01–BU-06 | Source inventory; firewall-based classification; visual canon; content/story canon; information architecture; Cloudflare/GitHub delivery topology |
| U1 — Visual and technical foundation | BU-07–BU-12 | Application scaffold/preview; design system; typography/icons/accessibility; motion language; asset migration/derivatives; typed content registry |
| U2 — Core Biella experience | BU-13–BU-18 | Cinematic Living Core; objective-to-delivery journey; Engine experience; Games experience; Intelligence experience; production-pipeline experience |
| U3 — Explorable universe | BU-19–BU-24 | Capability explorer; orchestration demonstration; project/showcase system; game/world gallery and playable embeds; 3D/media gallery; timeline/news/releases |
| U4 — Knowledge and AI product surfaces | BU-25–BU-30 | Documentation hub; public search; Ask Biella guide; NVIDIA compute/model demonstration; bounded research/tool demonstration; company/partner/investor/contact experience |
| U5 — Launch-grade delivery | BU-31–BU-36 | SEO/social discovery; analytics/product insight; Core Web Vitals; responsive/browser/device/accessibility qualification; resilience/error/cost behavior; Cloudflare production launch and verification |

Default execution order remains `BU-01 → BU-36`. Independent website work may run concurrently when its actual dependencies and output paths permit.

The ownership boundary is fixed:

```text
51 P0–P4 prompts = reusable Biella Engine mechanisms
36 BU prompts    = biellagames.dev website/product outcomes
```

Every BU task records its capability mode as `LIVE_ENGINE`, `PROJECT_LOCAL_BRIDGE`, `SIMULATED_DEMO`, or `NOT_REQUIRED`. When an engine owner is not yet implemented, Option C may use only a narrow website-local bridge or a clearly labeled deterministic demonstration. It must not create a second universal storage, memory, scheduler, routing, browser, model, validation, production, publishing, or learning subsystem. PostgreSQL/P2-08 is intentionally not required by the approved current Option C scope.

The approved visual direction remains: deep graphite/navy surfaces, dominant Biella violet, electric-cyan secondary accents, semantic green/amber/red only, thin precision borders, subtle glass and emissive edges, restrained bloom, compact typography, dense professional workstation UI, and a production-grade game-engine/editor aesthetic. Reject giant mechanical frames, surrounding scenery, and blue/orange arcade-HUD drift. Visual assets intended to float in the interface retain transparent backgrounds.

## 5. Verified current state and completed preparatory work

### 5.1 GitHub durable source

Repository: [`patrickminitz-web/biella-engine`](https://github.com/patrickminitz-web/biella-engine)  
Branch: `main`  
Current commit: `864434407341742a1b6abef49344607fb4271142`  
Current tree: `4c101f88af853f688c99036a88cb18aac7925227`  
Commit message: `Add clean Biella migration execution pack`

Durable commits completed during the recovered five-hour window:

| Commit | Completed durable artifact |
|---|---|
| `9f7cdd7309b0d26079538ab2700a6519a9dd4fc0` | Biella Universe 36-task website master pack |
| `20a06c8f41c831c5086734286be401060003b5f3` | 36×51 engine capability cross-map |
| `bb99c8e1a37c6c7516ce5f1f6bff8df65938f473` | Option C tasks cross-mapped to Biella Engine capabilities |
| `29ea9429f237a8065cc05cc05fc88fdd998cd977` | Next 10 execution steps; its `/srv/biella` infrastructure instructions are superseded by newer workstation state |
| `a112b2231ea76376a3bb170c2159f8772e57ba6a` | Verified Biella VPS configurator package and host evidence |
| `864434407341742a1b6abef49344607fb4271142` | Canonical clean migration execution pack |

The current GitHub recursive tree contains documentation and operational packages only. It has no durable engine `src/` path and no repository-root `package.json`.

The former Spot-local P0-01 result remains historical evidence only:

- commit `b7cc3db0a9feb34d72764261d32163d2b05ac123`
- tree `ec44bacc13e11f9c38c1b5ac7c3844ac74f24a11`
- prior evidence: 35/35 tests, typecheck PASS, build PASS

Those Git objects are not present in current GitHub history and are not current source. Do not reconstruct them from prose, import unrelated history, or claim P0-01 complete from that evidence.

### 5.2 Existing EC2 workstation

Verified baseline:

- instance `i-077ab197788b547b0`
- public IP `13.38.71.149`
- private IP `172.31.13.170`
- region `eu-west-3`
- `c5a.4xlarge`
- Ubuntu 26.04.1 LTS, kernel `7.0.0-1011-aws`
- 16 logical CPUs, 30 GiB RAM
- 350 GiB EBS root disk
- 64 GiB `/swapfile`, `vm.swappiness=10`
- existing root-owned Biella area under `/root/biella`
- Docker and PostgreSQL observed active
- installed Git/GitHub CLI, Node/npm, Python/pip, Rust/Cargo, Go, Java, AWS CLI, Codex, CMake/Ninja/Clang, FFmpeg, Blender, Pandoc, rclone, and Playwright Chromium
- evidence: `/root/biella/evidence/host-install.log` and `/root/biella/evidence/host-install-failures.log`

Docker and PostgreSQL were separately observed active during post-install host verification; recheck either service only when the active numbered prompt needs it. The post-install verification and host logs support the broad installed-tool inventory. The supplied tree inventory directly corroborates the Playwright/Chromium/FFmpeg payloads, not every installed executable.

The user-reported approximately 23 MB `/root/biella` tree is an initialized host scaffold, not a migrated Biella application. Its supplied path inventory records:

- 641 visible entries: 34 directories and 607 file-like entries, with `node_modules/` explicitly collapsed;
- the existing top-level lanes `.install-state/`, `artifacts/`, `backups/`, `cache/`, `checkpoints/`, `evidence/`, `migration/`, `objects/`, `projects/`, `quarantine/`, `repos/`, `runs/`, `tooling/`, and `work/`, plus `bootstrap-host.sh`;
- seven completion markers: `01-update.done` through `07-browser.done`;
- `evidence/bootstrap-20260826T213821Z.log`, `host-install.log`, and `host-install-failures.log`;
- `tooling/install-host.sh` and the Playwright package/lockfile;
- Playwright-managed `chromium-1234`, `chromium_headless_shell-1234`, and `ffmpeg-1011` payloads with installation/validation markers;
- no listed children in `repos/`, `projects/`, `work/`, `migration/`, `artifacts/`, `objects/`, `runs/`, `checkpoints/`, `backups/`, or `quarantine/`.

The visible inventory is dominated by browser-runtime files: 593 of 607 visible file-like entries are under `tooling/playwright-browsers/`. These files are reusable Resource state, not engine source or prompt completion. The `.done` files prove marker presence; the separate post-install verification supplies the corresponding host evidence.

The frozen VPS configurator package is recovery material for a clean replacement host, not a command to rerun on this host. Its stage-marker scheme differs from the captured host's marker scheme, so rerunning it could repeat completed stages. Use its read-only verifier when a prompt needs current host facts. The 80-byte `Biella_VPS.cmd` still targets the historical `ubuntu` login and is not the canonical continuation command; verified operating access is the existing root key path.

This is a CPU-only verified Resource. NVIDIA/CUDA was deliberately not installed. That does not reduce Biella's semantic capability; GPU-required implementations route to another Resource when needed.

Current narrow access facts:

- the user's Windows workstation successfully reached `root@13.38.71.149` with the existing `Biella.pem` key during the recovered window;
- a public SSH probe from the ChatGPT execution environment returned connection refused;
- this does not prove the instance is stopped;
- the host's `gh auth status` showed an invalid stored token at 2026-08-26 23:10 UTC.

Treat instance/SSH/sshd/network state and host push authentication as operational access facts to resolve at execution time. Restore only the existing access needed to continue; do not add a new authentication or security architecture.

### 5.3 Google Drive durable continuity

Canonical Biella Drive root: [`1Z6_qwN9hfHIheXZ_9pYCG8dRDMuRN-l7`](https://drive.google.com/drive/folders/1Z6_qwN9hfHIheXZ_9pYCG8dRDMuRN-l7)

Verified live structure:

```text
BiellaEngine/
├── 00_START_HERE/
├── 10_ARCHITECTURE/
├── 20_CURRENT_STATE/
├── 30_EXECUTION/
├── 40_PROMPTS/
│   ├── P0/  (10)
│   ├── P1/   (9)
│   ├── P2/  (12)
│   ├── P3/  (14)
│   └── P4/   (6)
└── 50_MIGRATION/
```

All 51 numbered prompts exist, are globally contiguous from 01 through 51, and have no missing or duplicate phase-local numbers.

Drive live-state files were updated through approximately 23:18 UTC with current GitHub/resource/status facts. The clean migration execution pack is also present at:

- folder `1_rbs7BnHg7LpNEAIUOz0qCn_LtB2TkU6`
- ZIP `Biella_Clean_Migration_Execution_Pack_2026-08-26.zip`, ID `1Iq7J-WxZ3FNit-S_zW4zlt02g_9LNCgD`
- Prompts 00–05 and README as individual Markdown files

A previous Drive-to-VPS copy verified 75/75 files with no transfer failures, complete SHA-256 coverage, prompt counts 10/9/12/14/6, and `STATUS: PASS`. Its local destination under `/home/ubuntu/biella-work/biella-drive` was on the terminated Spot host and is no longer a current workspace. The result remains validation evidence; the canonical Drive tree remains the live source, so the copy is not repeated as a migration prerequisite.

### 5.4 Historical donor corpus

Known historical MiniTZ backup:

- folder `20260824T120314Z__MINITZ_CLEAN_VPS_BACKUP.parts`
- Drive ID `1-H5R58cNlklGrmFNwa1QdHFiQYGRG5x_`

Its completeness, part sequence, and authoritative digest/manifest remain unresolved. It is a quarantine-only donor corpus. Do not reconstruct or mine it broadly before the firewall exists. An authorization URL or upload attempt is not upload completion evidence; only files confirmed by Drive listing/readback count as available resources.

### 5.5 External implementation references

- The isolated Cloudflare `/ai/chat` Workers AI experiment using `@cf/meta/llama-3.2-3b-instruct` is reference evidence only, not an implemented Biella adapter.
- NVIDIA Dynamo, Triton, TensorRT-LLM, DCGM, vLLM, and llama.cpp are candidate replaceable implementations or telemetry/runtime choices, not kernel dependencies.
- No current GPU deployment is claimed.
- The earlier proposed dedicated 200 GiB `/srv/biella` volume, S3-versioning operation, snapshot policy, and termination-protection steps are not treated as completed or required by this final plan.

### 5.6 Option C website state and visual resources

Durably completed Option C preparation:

- approved 36-task website master pack at commit `9f7cdd7309b0d26079538ab2700a6519a9dd4fc0`;
- canonical 36×51 Engine capability cross-map at commits `20a06c8f41c831c5086734286be401060003b5f3` and `bb99c8e1a37c6c7516ce5f1f6bff8df65938f473`;
- 60/60 album slots registered: 50 visual surfaces plus 10 document surfaces;
- document specifications 51–60 present on both GitHub and Drive;
- explicit superseded visual set excluded from website production.

Not yet proven complete:

- current GitHub has no `website/` application tree, build, preview, or production deployment evidence;
- none of BU-01–BU-36 is claimed complete solely from the planning documents;
- the asset manifest records 0/50 canonical visual files transferred into the Drive website archive and 0/50 transferred into `website/assets/images/album/` on GitHub;
- the exact canonical filenames for those 50 visual slots are not present in the current project-file inventory, so existing UUID-named/generated images must be matched by content during BU-01/BU-03 rather than guessed or silently renamed.

The visual concepts are real project resources, but a manifest entry or generated preview is not a finished website. Website completion requires the actual source, accepted visual implementation, working build/runtime, browser validation required by the BU task, and remote readback of the deployed revision.

## 6. Clean-room migration firewall

All historical material follows exactly this admission path:

```text
RAW HISTORICAL SOURCE
→ IMMUTABLE QUARANTINE OBJECT + PROVENANCE
→ SEMANTIC EXTRACTION
→ CLASSIFICATION
→ CONTAMINATION REMOVAL
→ NORMALIZATION
→ BIELLA-NATIVE CANDIDATE
→ TASK-SPECIFIC VERIFICATION
→ ACTIVE DESTINATION ONLY WHEN APPROPRIATE
```

Raw evidence remains raw historical evidence. It never becomes active source, instructions, normal retrieval, Project Memory, or Engine Knowledge directly.

Every candidate receives exactly one of:

- `UNIVERSAL_GOOD`
- `UNIVERSAL_REWRITE`
- `PROJECT_SPECIFIC`
- `HISTORICAL_EVIDENCE`
- `DUPLICATE`
- `OBSOLETE_OR_DRIFT`

Deduplication order:

```text
exact content digest
→ exact normalized content
→ semantic duplicate serving the same authority/purpose
→ conflicting variants resolved to one active authority
```

Reject from active Biella:

- mechanical MiniTZ-to-Biella renaming;
- raw prompts, policies, branding, lore, assets, paths, or agent hierarchies;
- fixed provider, model, GPU, cloud, or machine assumptions;
- imaginary agents/resources/services or unobserved completion claims;
- stale paths, hosts, SHAs, pricing, install instructions, or runtime snapshots;
- permanent manager/critic/validator/repair pipelines;
- approval or readiness ceremonies not required by the Task;
- global serialization without dependency/resource cause;
- cache/workspace as authority;
- project-specific rules embedded in the universal kernel;
- code that cannot satisfy its claimed test/build/output contract;
- silent fallback reported as success;
- duplicate schedulers, memory systems, authority systems, or kernel mechanisms inside capability packs.

## 7. Immediate execution packet

This is the only work packet that should begin now.

### Step 1 — Restore/confirm access without rebuilding

- Use the already-working operator route: `ssh -i "C:\Users\Administrator\.ssh\Biella.pem" root@13.38.71.149`.
- If that exact route fails now, resolve only the actual instance/SSH cause for `i-077ab197788b547b0`; do not redesign access.
- Enter and preserve the existing root-owned `/root/biella` workstation.
- Restore the existing GitHub push path only if it is still invalid when a push is required.
- Do not rerun either host installer/configurator, reinstall the toolchain, create `/srv/biella`, initialize a new repository, create more than the one required checkout under `/root/biella/repos/`, or add access-control layers.

**Exit:** the existing `/root/biella` workstation is reachable and the existing GitHub repository is readable; the required push path is usable before publication.

### Step 2 — Inspect the current continuation state exactly once

The captured inventory shows `repos/` and `work/` with no listed children, and a later host search found no Git repository under `/root`, `/srv`, or `/home`. Confirm once whether that changed. If it did not, establish the one checkout from the existing GitHub repository at `/root/biella/repos/biella-engine`; do not initialize a different repository or create a second checkout.

Within that one checkout, resolve only:

- branch, HEAD commit, HEAD tree, upstream, and worktree status;
- `AGENTS.md`, `CURRENT_TASK.md`, and any continuation record;
- presence/absence of `package.json`, `src/`, tests, and P0-01 interfaces;
- any valid local commits or dirty work newer than GitHub `864434407341742a1b6abef49344607fb4271142`.

**Decision:**

- If real newer implementation exists, preserve it and continue its latest incomplete numbered prompt.
- If no newer implementation exists, use current GitHub `main` at commit `864434407341742a1b6abef49344607fb4271142` and tree `4c101f88af853f688c99036a88cb18aac7925227` as the P0-01 source baseline; these values were remotely re-read on 2026-08-27 and must still be confirmed by the checkout before writing.

This is a continuation read, not a broad audit.

### Step 3 — Execute P0-01 only

Canonical prompt: `01_P0-01_Clean_Room_Migration_Firewall.md`  
Drive ID: `1Rqj1Vs-V_6xhq90NJRS2hnjIQiVYkER6xG2dJ5CJ2oI`

Implement from the exact contract:

- the minimal repository/package scaffold required to implement and prove this exact contract, because current GitHub `main` has no engine source/package root;
- generic historical-source/quarantine semantics;
- content-addressed quarantine with provenance;
- semantic extraction;
- six classifications;
- contamination-aware normalization;
- candidate-only output;
- active runtime/retrieval/memory exclusion;
- fail-closed invalid or unclassified admission;
- migration internals excluded from the normal package root.

Do not reuse `/root/biella/tooling/playwright` as the engine package and do not insert a separate setup phase before P0-01.

Use hostile **synthetic** historical fixtures for the firewall. Do not use the large real MiniTZ backup as the first test source.

### Step 4 — Close P0-01 durably

```text
focused failing tests
→ minimum task-scoped implementation
→ focused tests
→ affected regression tests
→ typecheck
→ build
→ inspect package exports and generated artifacts
→ commit
→ push
→ fetch/read back the exact remote commit and tree
→ update Drive current-state, repository-state, interface, and prompt-status records
→ stop
```

Report exact test counts, files changed, commit, tree, final worktree state, limitations, and next dependency. Do not begin P0-02 in the same numbered task.

### Step 5 — Register the real historical corpus after P0-01

After P0-01 is durably accepted:

- note that the captured local `backups/` and `quarantine/` lanes contain no listed parts;
- list the verified Drive multipart-backup objects and stage/register only the confirmed parts as immutable quarantine inputs without extraction;
- determine exact part continuity, sizes, available digests, and manifest/checksum presence;
- record immutable source identity and provenance;
- do not yet promote content into active Biella;
- keep broad semantic mining out of P0-02 through P0-10 unless a prompt explicitly requires a bounded fixture.

After P0-10 passes, historical extraction/classification can proceed in bounded, resumable batches alongside unaffected P1 work where dependencies and resources allow.

### Option C website lane — open immediately after P0-01 closes

P0-01 remains the only objective of the first engine execution session. Once its exact commit/tree and evidence are durably accepted, Option C begins as a separate project workstream while the engine continues with P0-02:

1. execute BU-01 against the current GitHub/Drive/project-file sources;
2. match the existing generated/UUID-named visual files to manifest slots by actual image content, dimensions, and digest—never by guess;
3. execute BU-02 using the real P0-01 interface;
4. lock BU-03 visual masters and BU-04 content/story canon;
5. continue U0→U5, consuming live engine interfaces where available and using only narrow project-local bridges or labeled simulations where they are not;
6. keep all website code and assets in the website project paths, outside the Engine kernel;
7. finish at BU-36 with the exact accepted website revision deployed to `biellagames.dev`, production behavior verified, deployed commit recorded, and rollback proven.

The website does not wait for P4-06 to become beautiful and usable. Only website surfaces that claim live Engine behavior wait for their mapped Engine interface; until then they remain clearly labeled project-local or simulated experiences.

## 8. Full numbered migration sequence

### P0 — Clean Kernel + Migration Firewall

| Global | Prompt | Exact task | Drive ID |
|---:|---|---|---|
| 01 | P0-01 | Clean Room Migration Firewall | `1Rqj1Vs-V_6xhq90NJRS2hnjIQiVYkER6xG2dJ5CJ2oI` |
| 02 | P0-02 | Universal Project Namespace and Isolation Contract | `1aINglpjh2qSuRbPrNT2dkTaBRRWNhLAAhriWTQ-kGwk` |
| 03 | P0-03 | Provider Neutral Capability Contract | `1HaRjLqtN9YgNKRJHm7VLIay80_o0qQVJeFXYeyvoJFs` |
| 04 | P0-04 | Universal Typed Task Contract | `1weEvFdehM9SuMoCn8bTOwZ1ADO0vYyO319aDPDAeqaE` |
| 05 | P0-05 | Durable Run Identity, Attempts, Leases and Fencing | `1a_Xqlzv1HhPcuuI8PNHVVDYhpfQYX_bsm3fnCAYWXwQ` |
| 06 | P0-06 | Artifact and Source Identity Contract | `17l-QAoXQPl2QkE3B7BJqoeCVsJHybnrq8UQlRltu1as` |
| 07 | P0-07 | Immutable Revisioned Graph and Node Contracts | `1e3EA4_bjuhbdn2dlcsRHpXR0-6snMlY3bL_q8bgxNRU` |
| 08 | P0-08 | Durable Append-Only Event Ledger | `1UtCBREk13USF2egMgZrqws_2PUCEAFeQ6VBfh3Y04aY` |
| 09 | P0-09 | Durable Node/Run Execution State and Atomic Finalization | `1_yBgxGdKjX88wA9gXk59NzN8No7srJZDRF0CGCIF90I` |
| 10 | P0-10 | P0 Integration, Isolation, Contamination and Recovery Qualification | `1Xsx8tYhwvg29FTMkYEK-Sed5kjJHD40HJoFsXYS31IE` |

P0 exits only when Project isolation, immutable identity, fencing, append-only Events, exact Artifact identity, restart durability, arbitrary Capability extensibility, concurrent independent readiness, and kernel neutrality all pass from observed evidence.

### P1 — Durable Cognition + Resources + Scheduler + Routing

| Global | Prompt | Exact task | Drive ID |
|---:|---|---|---|
| 11 | P1-01 | Content-Addressed Object Store | `1a8NV8vEPxyKCVhwk1MKSd3AXfhyB87vkpvPko0Ka45c` |
| 12 | P1-02 | Durable Run Memory and Reconstruction | `19Bifx_E0RPhs3gxi3srr7118_rnhdT1gSCH3Pyi8I3Y` |
| 13 | P1-03 | Isolated Versioned Project Memory | `1c_gu5vm-Zg4qmLk6fqipkS2s7RuHocrEJqG7Ce4S0mA` |
| 14 | P1-04 | Versioned Engine Knowledge and Promotion Boundary | `10yO_uSy2A5KrIw_8H6uU9SbnCUb0WZe39Ujq3wAbnYw` |
| 15 | P1-05 | Provider-Neutral Model and Tool Call Ledger | `1iKl6rJcmQENG9UolH86DFlj1y2kY5FR_ZPy2NMGmOzI` |
| 16 | P1-06 | Durable Checkpoint and Resume | `116Lf3h6Ermqveds96ifQA3AneaC_7giEuMGddMhfimU` |
| 17 | P1-07 | Dynamic Runtime Resource Inventory | `17jLplTvv6Fr1_1LBWFq93JWwjt3-zG-0FWCpBEbYUUc` |
| 18 | P1-08 | Concurrent Resource-Aware Graph Scheduler | `1cYQKnQeJWQ90Lv9AQQH_oGVAGKgtgvGitU7C3hhGKUo` |
| 19 | P1-09 | Capability, Model, Tool and Compute Routing | `1lyJ-tC8_kUy5yYuMftmEcPeNjsIBu8DRbZIU0VBhKDU` |

P1 exits only when a Run reconstructs without a chat/provider session, scoped cognition is enforced, configured and measured Resources are distinct, independent Nodes schedule concurrently, and swapping provider/hardware does not alter Task or Capability semantics.

### P2 — Universal Execution Fabric

| Global | Prompt | Exact task | Drive ID |
|---:|---|---|---|
| 20 | P2-01 | Universal Filesystem Capability Adapter | `1cNVwywxtOOlbmNkiZRBZn6jhP_WlnTleDVTieWRXw5U` |
| 21 | P2-02 | Bounded Shell and Managed Process Execution | `1FqsA8OT0qgDpNfGobSJcDudPVNpVkzAyCEeD1Ad0Ba8` |
| 22 | P2-03 | Exact-Revision Git Repository Adapter | `1508K_PyL7nVdCdvlRUgg0h4L-_whON9Sbyx07u0wYQY` |
| 23 | P2-04 | Replaceable Container and Isolated Runtime Adapter | `1ulpsBImXNT3HyP7G0GUfEjNjPXqCknY0uLdjoEn4xyA` |
| 24 | P2-05 | Universal HTTP/API Execution Adapter | `11zmSVb23RA5InBxAVWCD_KAqHFn_vLtXrnuublFGvHQ` |
| 25 | P2-06 | Provider-Neutral Model Execution Adapter Layer | `1z1EOJUTNn_-jd115J539vG8Auq969p55rAHlR0AXg7k` |
| 26 | P2-07 | Durable Provider-Neutral Browser Automation Adapter | `1jgWIpcDZVon6xUZWKDVnh7eIkz0sDKQ9udQiYDfn0iI` |
| 27 | P2-08 | PostgreSQL Project/Task Capability Adapter | `1uWBI_N66H-OlseBJkN-QnrLnN9x-0Vrti40ih_6kkfg` |
| 28 | P2-09 | Replaceable Durable Object Storage Backends and Replicas | `1lv_zCYOyP8L3RZev-Wtlyy_RpMyOri4GETYCvO3eNHE` |
| 29 | P2-10 | Project-Scoped Context Compilation and Derived Retrieval | `1x04_Hu20eHm8NwGu7Gliuhn4EVgPLkxzLxLzPkVZueM` |
| 30 | P2-11 | Durable Candidate Workspace and Sandbox Execution | `1iwOAJYyXNdyqdqEc5g3l6hq4ms8wmHaP14eG60ivWFI` |
| 31 | P2-12 | Task-Derived Validation and Evaluation Primitives | `1g3eSGdIQLg8b-DZdAwKm5dhUHudKgtlsBcRuGlzzbgo` |

P2 exits only when real adapter actions are attributable to exact execution identity, workspace loss cannot erase durable work, unsupported real integrations are classified honestly, and replacing implementations does not change kernel semantics.

### P3 — Production Capability Packs

| Global | Prompt | Exact task | Drive ID |
|---:|---|---|---|
| 32 | P3-01 | Software Engineering Production Pack | `1KqL3RzBspIr8HVFtuoFfS5ew1hwVLSOIhMMimuf-9OE` |
| 33 | P3-02 | Web Application Production Pack | `1tSP2q6J16nkag6m5j2rmLWIJRcKj9MncuMqriiio7sQ` |
| 34 | P3-03 | Engine-Neutral Game Production Pack | `1ZShgBxR5qDFBhLM38MEJCsYCxdlWRjpUgzEYmvQqHlw` |
| 35 | P3-04 | Large-Scale AAA Multi-Domain Production Orchestration Pack | `1NLikJ8cPQ3-4ybpMr8FvHN2sn43fPVw_trMet-Wx_HQ` |
| 36 | P3-05 | 3D Modeling and Scene Production Pack | `1TIG3GggwGdu3ma1e5MeeIontVUO4pmSP4aggJKps0Kg` |
| 37 | P3-06 | Character Modeling, Rigging, Skinning and Character Asset Pack | `11Q0LKa5Zl_ctJ6_0tdn_6ezvxNeex6JufFBbDfu5NHM` |
| 38 | P3-07 | Animation Production Pack | `1GzQxmCrvIv10WVv0KdoPxlKi7l79J2J6cS-zvoOv-Dk` |
| 39 | P3-08 | Environment and World Production Pack | `10wP9734umfbfCGfLvmf3gz_9IfT1h8kTjX06KmW0a54` |
| 40 | P3-09 | Rendering Production Pack | `1FYsaztU8wwjl_6k8Nx4xJII4wId-MPflkLFUNwW4gRM` |
| 41 | P3-10 | VFX and Simulation Production Pack | `12GmJFm2-6mL7QSjyyaySDWbBi2WrkljUF447XWsHnnI` |
| 42 | P3-11 | Image Production, Editing, Compositing and Texture Pack | `1hZm2VC3xYefqwZBxvIhsChrIjCLcZXsTSoOCG3IKLhM` |
| 43 | P3-12 | Audio Production, Processing, Mixing and Validation Pack | `1c8GEF9Z6pL9JKMkhXx6ZtsbcKnI5b_jY4k27ie3L1HI` |
| 44 | P3-13 | Video Production, Editing, Compositing and Media Pipeline Pack | `12_Z1RrJBW8fGVj5z76wnaphozu8J2DjSrHd2gJVrbmA` |
| 45 | P3-14 | Packaging, Publishing, Release and Durable Delivery Pack | `1mkk0VYh14ut2Tz-7YKcdW35p0GJRtv7bVQeVSPVTzpE` |

P3 packs use the same kernel, scheduler, memory, authority, and adapter seams. A pack cannot introduce a second engine or fixed project/provider behavior. Completion requires the real editable source/artifact and the Task-specific functional or visual evidence—not a configuration report or screenshot alone.

### P4 — Evidence-Based Learning + Qualification

| Global | Prompt | Exact task | Drive ID |
|---:|---|---|---|
| 46 | P4-01 | Controlled Evidence-Based Model Capability Comparison | `1V2VGta8GmM-6_UB4UwpdqKT-j_4NTRzcd3tXd1tKqOM` |
| 47 | P4-02 | Agent, Skill, Prompt, Tool and Execution Strategy Evaluation | `1IKlb4CPzng80VeJOPRo-_R5UdEIr7Vv4dz15x33JXfA` |
| 48 | P4-03 | Conditional Reversible Evidence-Based Routing Learning | `1kGNEBjMTBllbfqpiUGcNf7_TxhDZ7uDBvKf-jq5iqBw` |
| 49 | P4-04 | Cache, Locality, Residency and Resource Placement Learning | `1ND5zkrv09Jwxs8EDIRQwJ_QGRWAKP0u8lzfjA0ZJ0D4` |
| 50 | P4-05 | Evidence-Based Failure Pattern and Repair Intelligence Learning | `1zkyAQmBrWFVn5YU7A_up49Hd5DNA8-Xwic3TY9w0tm8` |
| 51 | P4-06 | Versioned Production Recipe Learning and Full P0–P4 Qualification | `1vsxRXkhtv0n8eJdQ56AVqJJEl3k5hjtqJsrUIqFVeAA` |

Learning is evidence-based, versioned, scoped, conditional, and reversible. It cannot silently mutate kernel invariants or convert one Project's preferences into Engine defaults.

## 9. Resource timing and routing

### Use now

- existing CPU EC2 workstation for source work, tests, PostgreSQL integration, deterministic tools, browser/runtime work supported by the installed environment, and orchestration;
- existing `/root/biella` lanes and evidence logs without changing their names or ownership;
- existing Playwright/Chromium/headless-shell/FFmpeg payloads when a numbered prompt actually needs browser execution;
- GitHub for durable code/source history and exact remote readback;
- Google Drive for live operator state, the 51 prompt contracts, migration ledger, and chronological continuity;
- the approved Option C master pack, 36×51 cross-map, 60-slot asset manifest, and document specifications as the website execution authorities;
- existing generated website visuals as BU-01/BU-03 matching candidates until their content identity, canonical filename, and accepted slot are verified;
- existing Docker/PostgreSQL/toolchain only when the current prompt needs them;
- the historical backup only through quarantine after P0-01.

### Add only when the prompt proves the need

- one On-Demand H100 80 GB or equivalent for real local ModelProvider/resource-routing qualification after P0-10 and the early P1 model/resource contracts exist;
- vLLM as the first high-throughput local implementation;
- llama.cpp as a lightweight/fallback local implementation;
- TensorRT-LLM only when measured benefit justifies it;
- Triton only when unified multi-model serving materially helps;
- DCGM-compatible telemetry only on an actual NVIDIA Resource;
- additional storage/backend/runtime providers as replaceable P2 implementations.

Do not install NVIDIA software on the CPU-only host for documentation completeness. Do not rent GPU compute before useful GPU-ready work exists. When expensive compute is used, keep ready independent work fed to it, checkpoint durable outputs, and release it when its bounded work is complete.

## 10. Execution and failure rules

For every numbered prompt:

```text
inspect only required current state
→ read the exact numbered contract
→ reproduce with a focused failing test when implementing behavior
→ implement the smallest complete task-scoped change
→ run focused tests
→ run affected regressions
→ typecheck/build/run/inspect the output required by the contract
→ commit and push
→ remotely read back exact commit/tree and requested artifacts
→ update Drive continuity records
→ stop at the prompt boundary
```

Independent work inside the active prompt runs concurrently when dependencies and real resources permit.

Failure handling is scoped:

```text
FAIL
→ ISOLATE THE AFFECTED BOUNDARY
→ PRESERVE VERIFIED WORK
→ FALL BACK OR REPAIR
→ RETRY OR USE ANOTHER ROUTE
→ CONTINUE UNAFFECTED WORK
```

There is no global stop because one optional provider, GPU, browser, or tool is unavailable. `OWNER_DECISION_REQUIRED` pauses only the affected materially expensive or product-direction decision. Mahdi remains the final authority; no additional approver, manager, security gate, or review chain is created.

## 11. Completion and acceptance

Do not claim a prompt complete from prose, installation, configuration, HTTP 200, exit code alone, agent report, mock result, or provider receipt.

Completion evidence follows the Task contract:

- software: source plus required tests/typecheck/build/runtime;
- web: source/build/runtime plus browser evidence when required;
- game: editable source plus build/play/runtime evidence;
- 3D: editable source plus structural and visual validation;
- render: decodable frames tied to exact source/configuration;
- image/audio/video: editable/project source plus decoded validated outputs;
- file: exact bytes and digest;
- publication: receipt plus remote readback;
- performance/resource claim: measured runtime evidence;
- migration candidate: source identity, classification, removed contamination, destination scope, artifact/object identity, and verification record.

Phase gates remain:

```text
P0 → P1 only after P0-10
P1 → P2 only after P1-09 and P1 integration
P2 → P3 only after P2-12
P3 → P4 only after P3-14 cross-domain durable delivery proof
Foundation complete only after P4-06 full qualification
```

Final fully local acceptance remains:

```text
DISCONNECT INTERNET
→ BIELLA BOOTS
→ LOCAL MODELS LOAD
→ TASKS EXECUTE
→ RETRIEVAL AND SCOPED MEMORY WORK
→ TOOLS EXECUTE
→ ARTIFACTS PERSIST
→ RESTART / PROCESS LOSS RECOVERS
```

Only after single-node correctness and durability pass may the optional multi-node Resource/placement profile be added. Multi-node scale changes deployment and runtime configuration, not kernel semantics.

## 12. Explicitly excluded work

This plan does not authorize or require:

- a new Biella architecture or altered P0–P4 ordering;
- restarting MiniTZ development;
- direct MiniTZ source/prompt/policy activation;
- importing MiniTZ Git ancestry into Biella;
- mechanical renaming;
- bulk historical mining before the firewall;
- rebuilding or reinstalling the existing workstation;
- rerunning the clean-host configurator on the current verified workstation;
- treating the approximately 23 MB host/tooling tree or Playwright package as migrated engine source;
- treating the historical `Biella_VPS.cmd` ubuntu-login command as current authority;
- creating `/srv/biella` or executing the superseded 200 GiB EBS plan;
- adding authentication layers, tunnels, token systems, permission architecture, security gates, or access-control designs;
- a mandatory reviewer, critic, validator, manager, or governance chain;
- a universal serial execution rule;
- a fixed retry or repair count;
- renting a GPU before a real prompt needs it;
- treating Cloudflare, NVIDIA, OpenAI, PostgreSQL, Docker, a game engine, renderer, or other provider/tool as permanent kernel identity;
- repeating the 75-file Drive copy merely to re-prove an already verified source inventory;
- broad audits unrelated to the active numbered prompt;
- claiming implementation from plans, prompts, configuration, or historical evidence.

## 13. Start command boundary

The next execution session should receive one objective only:

> Connect to the existing Biella workstation; preserve the current `/root/biella` tree; confirm once whether `/root/biella/repos/` is still empty; if so, establish the single checkout at `/root/biella/repos/biella-engine` from existing GitHub `main`; then inspect that checkout and continuation state once, preserve any newer valid work, and—only if P0-01 is still the actual missing boundary—execute `01_P0-01_Clean_Room_Migration_Firewall.md` completely from the exact Drive contract. Do not rerun the configurator, reinstall, initialize a new repository, create a second checkout, create `/srv/biella`, mine the real backup, add security layers, or start P0-02. Test, typecheck, build, commit, push, remotely read back the exact commit/tree, update Drive continuity, and stop.

After that P0-01 boundary is durably closed, the first separate Option C session should receive one objective only:

> Execute BU-01 — Full Drive + GitHub Website Source Inventory for `biellagames.dev`. Reconcile the 60 manifest slots to exact existing sources, including matching UUID-named/generated visuals by actual content and digest. Record each source as canonical, candidate, superseded, historical, unrelated, or missing. Do not build the website yet, create duplicate Engine mechanisms, silently rename images, or start BU-02. Persist the BU-01 result and stop.
