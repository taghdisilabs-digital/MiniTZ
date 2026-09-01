# Biella Engine — Post-P4-06 Game + Website Integration Map

Status: `POST_P4_06_CONSUMER_MAP`
Owner/final authority: Mahdi Taghdisi
Engine repository: `patrickminitz-web/biella-engine`
Game repository: `patrickminitz-web/biella-games`
Website product: `biellagames.dev`
Activation: **only after P4-06 / global prompt 51 is durably complete and its exact GitHub commit/tree are remotely read back.**

## Boundary

The 51 P0–P4 prompts remain Biella Engine implementation authority. After prompt 51 closes, Game and Website consume the qualified Engine; they do **not** copy the 51 prompt bodies, create a second Engine, or reimplement universal scheduler/memory/routing/storage/model/browser/validation/learning mechanisms.

Post-51 handoff identity is:

`ENGINE_RESULT_COMMIT + ENGINE_RESULT_TREE + P4_06_QUALIFICATION_EVIDENCE + CAPABILITY/INTERFACE VERSION -> PROJECT CONSUMER TASKS`

`patrickminitz-web/biella-games` owns game source, assets, runtime, game requirements and playable acceptance. `biellagames.dev` owns website source, UX/content/brand, browser behavior and deployment. Engine owns reusable mechanisms only.

The existing detailed website mapping remains canonical for BU task IDs:
`docs/biellawebsite/BIELLA_UNIVERSE_36x51_ENGINE_CROSSMAP.md`.

## 51 Engine prompts -> Game + Website consumers

| # | Engine prompt | Biella Games consumer after P4-06 | Website consumer after P4-06 |
|---:|---|---|---|
| 01 | `P0-01` Clean-Room Migration Firewall | Admit historical/project donor material only through quarantine/classification before game use. | `BU-01`, `BU-02` |
| 02 | `P0-02` Project Namespace + Isolation | Keep game requirements/assets/memory isolated from Engine and other Projects. | `BU-01`, `BU-02`, `BU-12`, `BU-21`, `BU-26`, `BU-27` |
| 03 | `P0-03` Provider-Neutral Capability Contract | Express game/build/3D/render/model work as semantic capabilities, not fixed providers. | `BU-05`, `BU-12`, `BU-15`, `BU-19` |
| 04 | `P0-04` Universal Typed Task Contract | Version game production/build/play/render objectives and evidence contracts. | `BU-14`, `BU-15`, `BU-20` |
| 05 | `P0-05` Run Identity / Attempts / Leases / Fencing | Durable game-production runs; stale workers cannot finalize newer attempts. | `BU-15`, `BU-20`, `BU-35` |
| 06 | `P0-06` Artifact + Source Identity | Exact identity/provenance for game source, assets, builds, renders and captures. | `BU-01`, `BU-02`, `BU-03`, `BU-11`, `BU-12`, `BU-21`, `BU-23`, `BU-24`, `BU-25`, `BU-26` |
| 07 | `P0-07` Immutable Graph + Node Contracts | Compile game production tasks into dependency-safe, revisioned execution Graphs. | `BU-14`, `BU-15`, `BU-18`, `BU-20` |
| 08 | `P0-08` Append-Only Event Ledger | Record game build/play/render/asset state transitions and evidence. | `BU-14`, `BU-15`, `BU-18`, `BU-20`, `BU-24`, `BU-32` |
| 09 | `P0-09` Durable Node/Run State + Atomic Finalization | Resume long game/asset/render work without duplicate finalization. | `BU-15`, `BU-18`, `BU-20`, `BU-35` |
| 10 | `P0-10` P0 Integration Qualification | Base isolation/durability qualification consumed as Engine evidence. | `BU-15`, `BU-20` |
| 11 | `P1-01` Content-Addressed Object Store | Exact reusable storage for game asset/build/render content. | `BU-01`, `BU-11`, `BU-21`, `BU-23` |
| 12 | `P1-02` Durable Run Memory + Reconstruction | Reconstruct interrupted game-production runs without chat/process dependence. | `BU-20` |
| 13 | `P1-03` Isolated Versioned Project Memory | Store accepted game requirements, canon, decisions and project-specific facts. | `BU-03`, `BU-04`, `BU-05`, `BU-12`, `BU-17`, `BU-21`, `BU-25`, `BU-26` |
| 14 | `P1-04` Versioned Engine Knowledge | Reuse evaluated project-neutral production knowledge without importing game canon into Engine. | `BU-04`, `BU-17`, `BU-25`, `BU-26` |
| 15 | `P1-05` Model + Tool Call Ledger | Attribute AI/DCC/tool calls used for game production to exact runs and evidence. | `BU-17`, `BU-20`, `BU-27`, `BU-28`, `BU-29`, `BU-32`, `BU-35` |
| 16 | `P1-06` Durable Checkpoint + Resume | Resume long builds, renders, conversions and generation tasks from valid checkpoints. | `BU-20`, `BU-35` |
| 17 | `P1-07` Dynamic Runtime Resource Inventory | Represent CPU/GPU/VRAM/storage/toolchain availability for game production. | `BU-15`, `BU-19`, `BU-20`, `BU-28`, `BU-33`, `BU-34`, `BU-35` |
| 18 | `P1-08` Concurrent Resource-Aware Scheduler | Run independent game build/3D/render/media Nodes concurrently when safe. | `BU-15`, `BU-18`, `BU-20`, `BU-28` |
| 19 | `P1-09` Capability/Model/Tool/Compute Routing | Route game workloads to compatible implementations/resources after hard eligibility. | `BU-14`, `BU-15`, `BU-17`, `BU-18`, `BU-19`, `BU-20`, `BU-27`, `BU-28`, `BU-29`, `BU-33`, `BU-35` |
| 20 | `P2-01` Filesystem Adapter | Real game/project file inspection, creation and validation through bounded capability. | `BU-07`, `BU-11` |
| 21 | `P2-02` Shell + Managed Process | Build, run, render, encode and test game tooling as managed processes. | `BU-07`, `BU-11` |
| 22 | `P2-03` Exact-Revision Git Adapter | Pin game integration/build evidence to exact repository revisions. | `BU-01`, `BU-06`, `BU-07`, `BU-36` |
| 23 | `P2-04` Replaceable Isolated Runtime | Execute game/tool workloads in replaceable bounded runtime/container environments when useful. | `BU-07`, `BU-35` |
| 24 | `P2-05` HTTP/API Adapter | Use approved external/local APIs for game production without provider authority leakage. | `BU-06`, `BU-27`, `BU-28`, `BU-29`, `BU-30`, `BU-32`, `BU-35`, `BU-36` |
| 25 | `P2-06` Provider-Neutral Model Adapter | Run task-required models for game/code/art production through replaceable model implementations. | `BU-17`, `BU-27`, `BU-28`, `BU-29` |
| 26 | `P2-07` Browser Automation Adapter | Optional game web tooling/docs/portal validation; primary website browser execution. | `BU-07`, `BU-09`, `BU-10`, `BU-13`, `BU-22`, `BU-29`, `BU-31`, `BU-33`, `BU-34`, `BU-36` |
| 27 | `P2-08` PostgreSQL Adapter | Optional only if an accepted game task needs PostgreSQL-backed project/runtime data; not mandatory by existence. | None mandatory |
| 28 | `P2-09` Durable Object Storage Backends | Replicate durable game artifacts/builds/assets without changing logical identity. | `BU-01`, `BU-06`, `BU-11`, `BU-21`, `BU-23` |
| 29 | `P2-10` Project-Scoped Context + Retrieval | Compile exact game Project source/canon/reference context without raw-history contamination. | `BU-01`, `BU-02`, `BU-03`, `BU-04`, `BU-05`, `BU-12`, `BU-15`, `BU-17`, `BU-19`, `BU-21`, `BU-24`, `BU-25`, `BU-26`, `BU-27`, `BU-29` |
| 30 | `P2-11` Durable Candidate Workspace + Sandbox | Stage candidate game code/assets/tool outputs without making temporary workspace authoritative. | `BU-07`, `BU-20`, `BU-29` |
| 31 | `P2-12` Task-Derived Validation + Evaluation | Validate game source/build/play/runtime/3D/render/media according to each Task contract. | `BU-03` through `BU-36` where mapped; detailed list remains in canonical 36x51 cross-map |
| 32 | `P3-01` Software Engineering Production | Implement/test game code, tools, pipelines and supporting software. | `BU-07`, `BU-18` |
| 33 | `P3-02` Web Application Production | Optional game-facing web/tool surfaces; primary reusable website production owner. | `BU-05`–`BU-36` as mapped in canonical cross-map |
| 34 | `P3-03` Engine-Neutral Game Production | **Primary reusable game production capability** for playable source/build/run evidence. | `BU-16`, `BU-18`, `BU-22` |
| 35 | `P3-04` Large-Scale AAA Multi-Domain Orchestration | Coordinate large AAA game production across code, 3D, animation, world, render, VFX, audio and packaging. | `BU-18` |
| 36 | `P3-05` 3D Modeling + Scene Production | Build/edit/validate game meshes, scenes, props, vehicles and modular assets. | `BU-11`, `BU-16`, `BU-18`, `BU-22`, `BU-23` |
| 37 | `P3-06` Character Modeling / Rigging / Skinning | Produce editable runtime-ready player/rival/infected character assets. | `BU-18`, `BU-23` |
| 38 | `P3-07` Animation Production | Produce/integrate/validate runtime character, combat, vehicle and world animation. | `BU-18`, `BU-23` |
| 39 | `P3-08` Environment + World Production | Produce realistic navigable open-world city/environment source and states. | `BU-16`, `BU-18`, `BU-22`, `BU-23` |
| 40 | `P3-09` Rendering Production | Produce and validate real-time/offline game renders tied to exact source/config. | `BU-13`, `BU-16`, `BU-18`, `BU-22`, `BU-23` |
| 41 | `P3-10` VFX + Simulation Production | Produce runtime VFX/simulation/destruction/weather/effects where Project-approved. | `BU-18`, `BU-23` |
| 42 | `P3-11` Image / Editing / Compositing / Texture | Produce textures, materials, image derivatives, key art and validated image assets. | `BU-03`, `BU-08`, `BU-09`, `BU-11`, `BU-13`, `BU-16`, `BU-18`, `BU-22`, `BU-23`, `BU-31` |
| 43 | `P3-12` Audio Production | Produce/edit/mix/validate runtime game audio and website media derivatives. | `BU-11`, `BU-18`, `BU-22`, `BU-23` |
| 44 | `P3-13` Video Production | Produce gameplay capture, trailers, motion assets and website video derivatives from real Project source. | `BU-11`, `BU-13`, `BU-16`, `BU-18`, `BU-22`, `BU-23` |
| 45 | `P3-14` Packaging / Publishing / Durable Delivery | Package/publish game builds/assets/releases and website deployable artifacts with remote readback. | `BU-06`, `BU-07`, `BU-11`, `BU-16`, `BU-18`, `BU-21`, `BU-22`, `BU-23`, `BU-24`, `BU-25`, `BU-30`, `BU-31`, `BU-36` |
| 46 | `P4-01` Controlled Model Capability Comparison | Select/estimate model implementations for game production from scoped evidence, never universal rankings. | `BU-17`, `BU-27`, `BU-28` |
| 47 | `P4-02` Strategy / Skill / Tool Evaluation | Select execution strategies for game production from versioned measured evidence. | `BU-17`, `BU-27`, `BU-29` |
| 48 | `P4-03` Conditional Reversible Routing Learning | Rank eligible game production routes using conditional reversible evidence. | `BU-17`, `BU-19`, `BU-20`, `BU-27`, `BU-28`, `BU-29` |
| 49 | `P4-04` Cache / Locality / Residency / Placement Learning | Optimize L40S/model/tool/cache/workspace/artifact placement for game production without making cache authoritative. | `BU-28`, `BU-33` |
| 50 | `P4-05` Failure Pattern + Repair Learning | Reuse evidence-backed repair patterns for game builds/assets/renders while preserving deterministic fallback. | `BU-29`, `BU-33`, `BU-35` |
| 51 | `P4-06` Versioned Production Recipe Learning + Full Qualification | Export qualified reusable production recipes/evidence for Project Tasks; **activation gate for this post-51 map**. | `BU-15`, `BU-20`, `BU-36` |

## Post-51 handoff procedure

After `P4-06` is `COMPLETE_DURABLE`:

1. Read back and record the exact final Engine result commit/tree and P4-06 qualification evidence.
2. Freeze one versioned Engine consumer manifest containing only qualified interfaces/capabilities/recipes and their exact identities.
3. In `patrickminitz-web/biella-games`, pin that Engine identity and compile Project Tasks from current accepted game requirements, including the current AAA TPP runtime contracts. Do not copy Engine prompt authority into the game repository.
4. For `biellagames.dev`, continue the existing BU program using `docs/biellawebsite/BIELLA_UNIVERSE_36x51_ENGINE_CROSSMAP.md`; pin the same qualified Engine identity. Do not create a second universal Engine inside website code.
5. Game and website may execute concurrently after prompt 51 when their Project dependencies, write sets and Resources are independent.
6. Completion remains Project-specific: game = editable source + build/play/runtime evidence; website = source + build/runtime/browser/deployment evidence.
7. Any future Engine change creates a new Engine version/identity; Project consumers upgrade explicitly rather than silently following mutable state.

## Non-goals

- Do not start game or website production merely because this map exists.
- Do not start any post-51 consumer work before P4-06 durable closure unless a separate current Project task explicitly authorizes it.
- Do not duplicate all 51 prompt bodies into Game or Website.
- Do not treat NVIDIA, a game engine, DCC, model provider, browser, database or cloud as permanent Engine identity.
