# Biella D-Series — Engine + Games

Canonical IDs: `D##-##`. Dependency edges are authoritative; legacy IDs are aliases only.

## D00 — Engine foundation and universal production system

| Task | Title | Status | Depends on | Legacy alias |
|---|---|---|---|---|
| `D00-01` | Clean Room Migration Firewall | `COMPLETE_REUSE_REQUIRED` | — | `P0-01` |
| `D00-02` | Universal Project Namespace and Isolation Contract | `COMPLETE_REUSE_REQUIRED` | D00-01 | `P0-02` |
| `D00-03` | Provider Neutral Capability Contract | `COMPLETE_REUSE_REQUIRED` | D00-02 | `P0-03` |
| `D00-04` | Universal Typed Task Contract | `COMPLETE_REUSE_REQUIRED` | D00-03 | `P0-04` |
| `D00-05` | Durable Run Identity, Attempts, Leases and Fencing | `COMPLETE_REUSE_REQUIRED` | D00-04 | `P0-05` |
| `D00-06` | Artifact and Source Identity Contract | `COMPLETE_REUSE_REQUIRED` | D00-05 | `P0-06` |
| `D00-07` | Immutable Revisioned Graph and Node Contracts | `COMPLETE_REUSE_REQUIRED` | D00-06 | `P0-07` |
| `D00-08` | Durable Append-Only Event Ledger | `COMPLETE_REUSE_REQUIRED` | D00-07 | `P0-08` |
| `D00-09` | Durable Node/Run Execution State and Atomic Finalization | `COMPLETE_REUSE_REQUIRED` | D00-08 | `P0-09` |
| `D00-10` | P0 Integration, Isolation, Contamination and Recovery Qualification | `COMPLETE_REUSE_REQUIRED` | D00-09 | `P0-10` |
| `D00-11` | Content-Addressed Object Store | `COMPLETE_REUSE_REQUIRED` | D00-10 | `P1-01` |
| `D00-12` | Durable Run Memory and Reconstruction | `COMPLETE_REUSE_REQUIRED` | D00-11 | `P1-02` |
| `D00-13` | Isolated Versioned Project Memory | `COMPLETE_REUSE_REQUIRED` | D00-12 | `P1-03` |
| `D00-14` | Versioned Engine Knowledge and Promotion Boundary | `COMPLETE_REUSE_REQUIRED` | D00-13 | `P1-04` |
| `D00-15` | Provider-Neutral Model and Tool Call Ledger | `COMPLETE_REUSE_REQUIRED` | D00-14 | `P1-05` |
| `D00-16` | Durable Checkpoint and Resume | `COMPLETE_REUSE_REQUIRED` | D00-15 | `P1-06` |
| `D00-17` | Dynamic Runtime Resource Inventory | `COMPLETE_REUSE_REQUIRED` | D00-16 | `P1-07` |
| `D00-18` | Concurrent Resource-Aware Graph Scheduler | `COMPLETE_REUSE_REQUIRED` | D00-17 | `P1-08` |
| `D00-19` | Capability, Model, Tool and Compute Routing | `COMPLETE_REUSE_REQUIRED` | D00-18 | `P1-09` |
| `D00-20` | Universal Filesystem Capability Adapter | `COMPLETE_REUSE_REQUIRED` | D00-19 | `P2-01` |
| `D00-21` | Bounded Shell and Managed Process Execution | `COMPLETE_REUSE_REQUIRED` | D00-20 | `P2-02` |
| `D00-22` | Exact-Revision Git Repository Adapter | `COMPLETE_REUSE_REQUIRED` | D00-21 | `P2-03` |
| `D00-23` | Replaceable Container and Isolated Runtime Adapter | `COMPLETE_REUSE_REQUIRED` | D00-22 | `P2-04` |
| `D00-24` | Universal HTTP/API Execution Adapter | `COMPLETE_REUSE_REQUIRED` | D00-23 | `P2-05` |
| `D00-25` | Provider-Neutral Model Execution Adapter Layer | `COMPLETE_REUSE_REQUIRED` | D00-24 | `P2-06` |
| `D00-26` | Durable Provider-Neutral Browser Automation Adapter | `COMPLETE_REUSE_REQUIRED` | D00-25 | `P2-07` |
| `D00-27` | PostgreSQL Project/Task Capability Adapter | `COMPLETE_REUSE_REQUIRED` | D00-26 | `P2-08` |
| `D00-28` | Replaceable Durable Object Storage Backends and Replicas | `COMPLETE_REUSE_REQUIRED` | D00-27 | `P2-09` |
| `D00-29` | Project-Scoped Context Compilation and Derived Retrieval | `COMPLETE_REUSE_REQUIRED` | D00-28 | `P2-10` |
| `D00-30` | Durable Candidate Workspace and Sandbox Execution | `COMPLETE_REUSE_REQUIRED` | D00-29 | `P2-11` |
| `D00-31` | Task-Derived Validation and Evaluation Primitives | `COMPLETE_REUSE_REQUIRED` | D00-30 | `P2-12` |
| `D00-32` | Software Engineering Production Pack | `COMPLETE_REUSE_REQUIRED` | D00-31 | `P3-01` |
| `D00-33` | Web Application Production Pack | `COMPLETE_REUSE_REQUIRED` | D00-32 | `P3-02` |
| `D00-34` | Engine-Neutral Game Production Pack | `COMPLETE_REUSE_REQUIRED` | D00-33 | `P3-03` |
| `D00-35` | Large-Scale AAA Multi-Domain Production Orchestration Pack | `COMPLETE_REUSE_REQUIRED` | D00-34 | `P3-04` |
| `D00-36` | 3D Modeling and Scene Production Pack | `COMPLETE_REUSE_REQUIRED` | D00-35 | `P3-05` |
| `D00-37` | Character Modeling, Rigging, Skinning and Character Asset Pack | `COMPLETE_REUSE_REQUIRED` | D00-36 | `P3-06` |
| `D00-38` | Animation Production Pack | `COMPLETE_REUSE_REQUIRED` | D00-37 | `P3-07` |
| `D00-39` | Environment and World Production Pack | `COMPLETE_REUSE_REQUIRED` | D00-38 | `P3-08` |
| `D00-40` | Rendering Production Pack | `COMPLETE_REUSE_REQUIRED` | D00-39 | `P3-09` |
| `D00-41` | VFX and Simulation Production Pack | `COMPLETE_REUSE_REQUIRED` | D00-40 | `P3-10` |
| `D00-42` | Image Production, Editing, Compositing and Texture Pack | `COMPLETE_REUSE_REQUIRED` | D00-41 | `P3-11` |
| `D00-43` | Audio Production, Processing, Mixing and Validation Pack | `COMPLETE_REUSE_REQUIRED` | D00-42 | `P3-12` |
| `D00-44` | Video Production, Editing, Compositing and Media Pipeline Pack | `COMPLETE_REUSE_REQUIRED` | D00-43 | `P3-13` |
| `D00-45` | Packaging, Publishing, Release and Durable Delivery Pack | `COMPLETE_REUSE_REQUIRED` | D00-44 | `P3-14` |
| `D00-46` | Controlled Evidence-Based Model Capability Comparison | `COMPLETE_REUSE_REQUIRED` | D00-45 | `P4-01` |
| `D00-47` | Agent, Skill, Prompt, Tool and Execution Strategy Evaluation | `COMPLETE_REUSE_REQUIRED` | D00-46 | `P4-02` |
| `D00-48` | Conditional Reversible Evidence-Based Routing Learning | `COMPLETE_REUSE_REQUIRED` | D00-47 | `P4-03` |
| `D00-49` | Cache, Locality, Residency and Resource Placement Learning | `COMPLETE_REUSE_REQUIRED` | D00-48 | `P4-04` |
| `D00-50` | Evidence-Based Failure Pattern and Repair Intelligence Learning | `COMPLETE_REUSE_REQUIRED` | D00-49 | `P4-05` |
| `D00-51` | Versioned Production Recipe Learning and Full P0–P4 Qualification | `DEFERRED_INCOMPLETE` | D00-50 | `P4-06` |

## D01 — Biella Games Demo 01 — protected active program

| Task | Title | Status | Depends on | Legacy alias |
|---|---|---|---|---|
| `D01-01` | Resolve live canonical Games execution root | `COMPLETE` | — | `D01-001` |
| `D01-02` | Verify GitHub authority and engine-repository separation | `COMPLETE` | D01-01 | `D01-002` |
| `D01-03` | Verify current Games Drive authority root and paths | `COMPLETE` | D01-02 | `D01-003` |
| `D01-04` | Verify UE 5.8.2, Unreal work, recovery material, and runtime host | `COMPLETE` | D01-03 | `D01-004` |
| `D01-05` | Reconcile workers and avoid overlapping active edits | `COMPLETE` | D01-04 | `D01-005` |
| `D01-06` | Create and persist single D01 queue/checkpoint | `COMPLETE` | D01-05 | `D01-006` |
| `D01-07` | Import valid Unreal recovery into canonical source | `COMPLETE` | D01-06 | `D01-007` |
| `D01-08` | Build UE 5.8.2 Editor and Game targets | `COMPLETE` | D01-07 | `D01-008` |
| `D01-09` | Launch canonical project and default map | `COMPLETE` | D01-08 | `D01-009` |
| `D01-10` | Establish gameplay world and mode ownership | `COMPLETE` | D01-09 | `D01-010` |
| `D01-11` | Establish player pawn mesh and collision baseline | `COMPLETE` | D01-10 | `D01-011` |
| `D01-12` | Add third-person camera boom and camera | `COMPLETE` | D01-11 | `D01-012` |
| `D01-13` | Add real Enhanced Input actions and mappings | `COMPLETE` | D01-12 | `D01-013` |
| `D01-14` | Wire movement, jump, locomotion state | `COMPLETE` | D01-13 | `D01-014` |
| `D01-15` | Wire look, aim orientation, obstruction safety | `COMPLETE` | D01-14 | `D01-015` |
| `D01-16` | Build real arena geometry, materials, lighting | `COMPLETE` | D01-15 | `D01-016` |
| `D01-17` | Add navigation/traversable-world support | `COMPLETE` | D01-16 | `D01-017` |
| `D01-18` | Add authoritative health/damage interfaces | `COMPLETE` | D01-17 | `D01-018` |
| `D01-19` | Add equipped weapon and real fire/hit resolution | `COMPLETE` | D01-18 | `D01-019` |
| `D01-20` | Add target reaction, defeat, combat state change | `COMPLETE` | D01-19 | `D01-020` |
| `D01-21` | Add combat readability feedback | `COMPLETE` | D01-20 | `D01-021` |
| `D01-22` | Add infected pawn/runtime actor | `COMPLETE` | D01-21 | `D01-022` |
| `D01-23` | Add infected perception/aggro | `COMPLETE` | D01-22 | `D01-023` |
| `D01-24` | Add infected navigation/chase | `COMPLETE` | D01-23 | `D01-024` |
| `D01-25` | Add infected melee damage timing | `COMPLETE` | D01-24 | `D01-025` |
| `D01-26` | Add infected hit reaction/death | `COMPLETE` | D01-25 | `D01-026` |
| `D01-27` | Add rival contestant pawn/runtime actor | `COMPLETE` | D01-26 | `D01-027` |
| `D01-28` | Add rival perception/target selection | `COMPLETE` | D01-27 | `D01-028` |
| `D01-29` | Add rival navigation/combat positioning | `COMPLETE` | D01-28 | `D01-029` |
| `D01-30` | Add rival weapon use/damage response | `COMPLETE` | D01-29 | `D01-030` |
| `D01-31` | Prove shared player/rival/infected interaction | `COMPLETE` | D01-30 | `D01-031` |
| `D01-32` | Add authoritative arena-pressure state | `COMPLETE` | D01-31 | `D01-032` |
| `D01-33` | Add pressure world consequence/responses | `ACTIVE` | D01-32 | `D01-033` |
| `D01-34` | Add objective manager/success condition | `PENDING` | D01-33 | `D01-034` |
| `D01-35` | Add failure/death state | `PENDING` | D01-34 | `D01-035` |
| `D01-36` | Add deterministic restart/reset path | `PENDING` | D01-35 | `D01-036` |
| `D01-37` | Add gameplay HUD core | `PENDING` | D01-36 | `D01-037` |
| `D01-38` | Add success/failure overlays/restart input | `PENDING` | D01-37 | `D01-038` |
| `D01-39` | Add deterministic playtest harness/telemetry | `PENDING` | D01-38 | `D01-039` |
| `D01-40` | Apply visual/readability pass | `PENDING` | D01-39 | `D01-040` |
| `D01-41` | Expose generated visuals through inspection layer | `PENDING` | D01-40 | `D01-041` |
| `D01-42` | Add event-driven audio/VFX feedback polish | `PENDING` | D01-41 | `D01-042` |
| `D01-43` | Run stability/soak qualification | `PENDING` | D01-42 | `D01-043` |
| `D01-44` | Measure native performance/resource behavior | `PENDING` | D01-43 | `D01-044` |
| `D01-45` | Repair lifecycle/GC/spawn cleanup | `PENDING` | D01-44 | `D01-045` |
| `D01-46` | Package playable build | `PENDING` | D01-45 | `D01-046` |
| `D01-47` | Launch clean package/capture run evidence | `PENDING` | D01-46 | `D01-047` |
| `D01-48` | Execute full end-to-end playable acceptance | `PENDING` | D01-47 | `D01-048` |
| `D01-49` | Commit/push canonical source/verify GitHub readback | `PENDING` | D01-48 | `D01-049` |
| `D01-50` | Publish Drive closure/verify exact readback | `PENDING` | D01-49 | `D01-050` |

## D02 — Biella Games Stage 2 — open-world/systemic expansion

| Task | Title | Status | Depends on | Legacy alias |
|---|---|---|---|---|
| `D02-01` | Open-world streaming and continuity | `PENDING_UNPLANNED` | D01-50 | `GAME-20-WORLD-STREAMING` |
| `D02-02` | Population and encounter scaling | `PENDING_UNPLANNED` | D02-01 | `GAME-21-POPULATION-SCALING` |
| `D02-03` | Vehicle runtime when explicitly approved | `PENDING_UNPLANNED` | D02-01 | `GAME-22-VEHICLES` |
| `D02-04` | Deeper interaction, destruction, and environment state | `PENDING_UNPLANNED` | D02-01 | `GAME-23-INTERACTION-DESTRUCTION` |

## D03 — Biella Games Stage 3 — production quality

| Task | Title | Status | Depends on | Legacy alias |
|---|---|---|---|---|
| `D03-01` | Production rendering, animation, VFX, and audio quality | `PENDING_UNPLANNED` | D02-01, D02-02, D02-04 | `GAME-30-PRODUCTION-QUALITY` |

## D04 — Biella Games Stage 4 — content multiplication

| Task | Title | Status | Depends on | Legacy alias |
|---|---|---|---|---|
| `D04-01` | Data-driven content system multiplication | `PENDING_UNPLANNED` | D03-01 | `GAME-40-CONTENT-MULTIPLICATION` |

## D05 — Biella Games Stage 5 — UI/settings/localization/accessibility

| Task | Title | Status | Depends on | Legacy alias |
|---|---|---|---|---|
| `D05-01` | UI, settings, localization, and accessibility | `PENDING_UNPLANNED` | D04-01 | `GAME-50-UI-ACCESSIBILITY` |

## D06 — Biella Games Stage 6 — cinematics/presentation

| Task | Title | Status | Depends on | Legacy alias |
|---|---|---|---|---|
| `D06-01` | Cinematic and presentation integration | `PENDING_UNPLANNED` | D04-01 | `GAME-60-CINEMATICS` |

## D07 — Biella Games Stage 7 — performance/stability/scalability

| Task | Title | Status | Depends on | Legacy alias |
|---|---|---|---|---|
| `D07-01` | Full performance, stability, and scalability qualification | `PENDING_UNPLANNED` | D03-01, D04-01, D05-01, D06-01 | `GAME-70-PERFORMANCE-QUALIFICATION` |

## D08 — Biella Games Stage 8 — delivery/release candidate

| Task | Title | Status | Depends on | Legacy alias |
|---|---|---|---|---|
| `D08-01` | Delivery, update, and release-candidate qualification | `PENDING_UNPLANNED` | D07-01 | `GAME-80-RELEASE-CANDIDATE` |
