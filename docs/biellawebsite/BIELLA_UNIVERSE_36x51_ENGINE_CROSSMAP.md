# Biella Universe — 36×51 Engine Capability Cross-Map

Status: CANONICAL OPTION C DEPENDENCY MAP  
Purpose: Map every Biella Universe website task to the Biella Engine prompt(s) that own reusable capability, so `biellagames.dev` never becomes a second engine.

## Reading rule

- `BU-*` owns only website/product-specific work.
- `P0-*` through `P4-*` own reusable Biella Engine mechanisms.
- This map is about **semantic ownership**, not proof that an engine prompt is complete.
- Actual completion must be read from `20_BIELLA_PROMPT_EXECUTION_STATUS.md` and current repository interfaces.
- If an engine owner is not implemented, use only a narrow website-local bridge when necessary, or a clearly labeled simulation for demos. Do not create a substitute universal subsystem in website code.

## A. All 36 BU tasks → engine capability owners

| BU task | Website outcome | Engine owners consumed |
|---|---|---|
| `BU-01` | Full Drive + GitHub Website Source Inventory | `P0-01`, `P0-02`, `P0-06`, `P1-01`, `P2-03`, `P2-09`, `P2-10` |
| `BU-02` | Website Source Classification Using the Migration Firewall | `P0-01`, `P0-02`, `P0-06`, `P2-10` |
| `BU-03` | Visual Canon and Asset Master Selection | `P0-06`, `P1-03`, `P2-10`, `P2-12`, `P3-11` |
| `BU-04` | Content and Story Canon | `P1-03`, `P1-04`, `P2-10`, `P2-12` |
| `BU-05` | Universe Information Architecture | `P0-03`, `P1-03`, `P2-10`, `P3-02` |
| `BU-06` | Cloudflare + GitHub Website Delivery Topology | `P2-03`, `P2-05`, `P2-09`, `P3-02`, `P3-14` |
| `BU-07` | Website Application Scaffold and Preview Deployment | `P2-01`, `P2-02`, `P2-03`, `P2-04`, `P2-07`, `P2-11`, `P2-12`, `P3-01`, `P3-02`, `P3-14` |
| `BU-08` | Biella Website Design System | `P2-12`, `P3-02`, `P3-11` |
| `BU-09` | Typography, Iconography and Accessibility Foundation | `P2-07`, `P2-12`, `P3-02`, `P3-11` |
| `BU-10` | Motion and Transition Language | `P2-07`, `P2-12`, `P3-02` |
| `BU-11` | Website Asset Migration and Web Derivatives | `P0-06`, `P1-01`, `P2-01`, `P2-02`, `P2-09`, `P3-05`, `P3-11`, `P3-12`, `P3-13`, `P3-14` |
| `BU-12` | Website Content Registry | `P0-02`, `P0-03`, `P0-06`, `P1-03`, `P2-10`, `P3-02` |
| `BU-13` | Cinematic Entry and Living Biella Core | `P2-07`, `P2-12`, `P3-02`, `P3-09`, `P3-11`, `P3-13` |
| `BU-14` | Home Journey — Objective to Delivery | `P0-04`, `P0-07`, `P0-08`, `P1-09`, `P2-12`, `P3-02` |
| `BU-15` | Biella Engine Product Experience | `P0-03`, `P0-04`, `P0-05`, `P0-07`, `P0-08`, `P0-09`, `P0-10`, `P1-07`, `P1-08`, `P1-09`, `P2-10`, `P2-12`, `P3-02`, `P4-06` |
| `BU-16` | Biella Games Product Experience | `P2-12`, `P3-02`, `P3-03`, `P3-05`, `P3-08`, `P3-09`, `P3-11`, `P3-13`, `P3-14` |
| `BU-17` | Intelligence Experience | `P1-03`, `P1-04`, `P1-05`, `P1-09`, `P2-06`, `P2-10`, `P2-12`, `P3-02`, `P4-01`, `P4-02`, `P4-03` |
| `BU-18` | Production Pipeline Experience | `P0-07`, `P0-08`, `P0-09`, `P1-08`, `P1-09`, `P2-12`, `P3-01`, `P3-03`, `P3-04`, `P3-05`, `P3-06`, `P3-07`, `P3-08`, `P3-09`, `P3-10`, `P3-11`, `P3-12`, `P3-13`, `P3-14` |
| `BU-19` | Capability Explorer | `P0-03`, `P1-07`, `P1-09`, `P2-10`, `P2-12`, `P3-02`, `P4-03` |
| `BU-20` | Interactive Orchestration Demonstration | `P0-04`, `P0-05`, `P0-07`, `P0-08`, `P0-09`, `P0-10`, `P1-02`, `P1-05`, `P1-06`, `P1-07`, `P1-08`, `P1-09`, `P2-11`, `P2-12`, `P3-02`, `P4-03`, `P4-06` |
| `BU-21` | Project and Showcase System | `P0-02`, `P0-06`, `P1-01`, `P1-03`, `P2-09`, `P2-10`, `P2-12`, `P3-02`, `P3-14` |
| `BU-22` | Game / World Gallery and Playable Embeds | `P2-07`, `P2-12`, `P3-02`, `P3-03`, `P3-05`, `P3-08`, `P3-09`, `P3-11`, `P3-12`, `P3-13`, `P3-14` |
| `BU-23` | 3D and Media Gallery | `P0-06`, `P1-01`, `P2-09`, `P2-12`, `P3-02`, `P3-05`, `P3-06`, `P3-07`, `P3-08`, `P3-09`, `P3-10`, `P3-11`, `P3-12`, `P3-13`, `P3-14` |
| `BU-24` | Interactive Timeline, News and Releases | `P0-06`, `P0-08`, `P2-10`, `P2-12`, `P3-02`, `P3-14` |
| `BU-25` | Public Documentation Hub | `P0-06`, `P1-03`, `P1-04`, `P2-10`, `P2-12`, `P3-02`, `P3-14` |
| `BU-26` | Public Website Search | `P0-02`, `P0-06`, `P1-03`, `P1-04`, `P2-10`, `P2-12`, `P3-02` |
| `BU-27` | Ask Biella Public Guide | `P0-02`, `P1-05`, `P1-09`, `P2-05`, `P2-06`, `P2-10`, `P2-12`, `P3-02`, `P4-01`, `P4-02`, `P4-03` |
| `BU-28` | NVIDIA Compute / Model Demonstration | `P1-05`, `P1-07`, `P1-08`, `P1-09`, `P2-05`, `P2-06`, `P2-12`, `P3-02`, `P4-01`, `P4-03`, `P4-04` |
| `BU-29` | Live Research / Tool Demonstration | `P1-05`, `P1-09`, `P2-05`, `P2-06`, `P2-07`, `P2-10`, `P2-11`, `P2-12`, `P3-02`, `P4-02`, `P4-03`, `P4-05` |
| `BU-30` | About, Partner, Investor and Contact Experience | `P2-05`, `P2-12`, `P3-02`, `P3-14` |
| `BU-31` | SEO, Social Preview and Discoverability | `P2-07`, `P2-12`, `P3-02`, `P3-11`, `P3-14` |
| `BU-32` | Analytics, Privacy and Product Insight | `P0-08`, `P1-05`, `P2-05`, `P2-12`, `P3-02` |
| `BU-33` | Performance, Caching and Core Web Vitals | `P1-07`, `P1-09`, `P2-07`, `P2-12`, `P3-02`, `P4-04`, `P4-05` |
| `BU-34` | Responsive, Browser, Device and Accessibility Qualification | `P1-07`, `P2-07`, `P2-12`, `P3-02` |
| `BU-35` | Website Resilience, Error and Cost Boundaries | `P0-05`, `P0-09`, `P1-05`, `P1-06`, `P1-07`, `P1-09`, `P2-04`, `P2-05`, `P2-12`, `P3-02`, `P4-05` |
| `BU-36` | Cloudflare Production Launch and Final Website Qualification | `P2-03`, `P2-05`, `P2-07`, `P2-12`, `P3-02`, `P3-14`, `P4-06` |

## B. All 51 engine prompts → Option C consumers

| Engine prompt | Reusable capability owner | BU consumers | Option C interpretation |
|---|---|---|---|
| `P0-01` | Clean-Room Migration Firewall | `BU-01`, `BU-02` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P0-02` | Project Namespace and Isolation | `BU-01`, `BU-02`, `BU-12`, `BU-21`, `BU-26`, `BU-27` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P0-03` | Capability Contract | `BU-05`, `BU-12`, `BU-15`, `BU-19` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P0-04` | Typed Task Contract | `BU-14`, `BU-15`, `BU-20` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P0-05` | Run Identity and Fencing | `BU-15`, `BU-20`, `BU-35` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P0-06` | Artifact and Source Identity | `BU-01`, `BU-02`, `BU-03`, `BU-11`, `BU-12`, `BU-21`, `BU-23`, `BU-24`, `BU-25`, `BU-26` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P0-07` | Graph and Node Contract | `BU-14`, `BU-15`, `BU-18`, `BU-20` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P0-08` | Event Ledger | `BU-14`, `BU-15`, `BU-18`, `BU-20`, `BU-24`, `BU-32` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P0-09` | Durable Execution State | `BU-15`, `BU-18`, `BU-20`, `BU-35` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P0-10` | P0 Integration Qualification | `BU-15`, `BU-20` | Consumed as qualification evidence; no BU reimplementation. |
| `P1-01` | Content-Addressed Object Store | `BU-01`, `BU-11`, `BU-21`, `BU-23` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P1-02` | Run Memory | `BU-20` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P1-03` | Project Memory | `BU-03`, `BU-04`, `BU-05`, `BU-12`, `BU-17`, `BU-21`, `BU-25`, `BU-26` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P1-04` | Engine Knowledge | `BU-04`, `BU-17`, `BU-25`, `BU-26` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P1-05` | Model/Tool Call Ledger | `BU-17`, `BU-20`, `BU-27`, `BU-28`, `BU-29`, `BU-32`, `BU-35` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P1-06` | Checkpoint and Resume | `BU-20`, `BU-35` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P1-07` | Resource Inventory | `BU-15`, `BU-19`, `BU-20`, `BU-28`, `BU-33`, `BU-34`, `BU-35` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P1-08` | Concurrent Scheduler | `BU-15`, `BU-18`, `BU-20`, `BU-28` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P1-09` | Routing | `BU-14`, `BU-15`, `BU-17`, `BU-18`, `BU-19`, `BU-20`, `BU-27`, `BU-28`, `BU-29`, `BU-33`, `BU-35` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P2-01` | Filesystem Adapter | `BU-07`, `BU-11` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P2-02` | Shell / Managed Process | `BU-07`, `BU-11` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P2-03` | Git Adapter | `BU-01`, `BU-06`, `BU-07`, `BU-36` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P2-04` | Isolated Runtime | `BU-07`, `BU-35` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P2-05` | HTTP/API Adapter | `BU-06`, `BU-27`, `BU-28`, `BU-29`, `BU-30`, `BU-32`, `BU-35`, `BU-36` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P2-06` | Model Provider Layer | `BU-17`, `BU-27`, `BU-28`, `BU-29` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P2-07` | Browser Adapter | `BU-07`, `BU-09`, `BU-10`, `BU-13`, `BU-22`, `BU-29`, `BU-31`, `BU-33`, `BU-34`, `BU-36` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P2-08` | PostgreSQL Adapter | None mandatory | No mandatory current Option C dependency; do not add it merely to use the capability. |
| `P2-09` | Object Storage Backends | `BU-01`, `BU-06`, `BU-11`, `BU-21`, `BU-23` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P2-10` | Context and Retrieval | `BU-01`, `BU-02`, `BU-03`, `BU-04`, `BU-05`, `BU-12`, `BU-15`, `BU-17`, `BU-19`, `BU-21`, `BU-24`, `BU-25`, `BU-26`, `BU-27`, `BU-29` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P2-11` | Workspace and Sandbox | `BU-07`, `BU-20`, `BU-29` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P2-12` | Validation and Evaluation | `BU-03`, `BU-04`, `BU-07`, `BU-08`, `BU-09`, `BU-10`, `BU-13`, `BU-14`, `BU-15`, `BU-16`, `BU-17`, `BU-18`, `BU-19`, `BU-20`, `BU-21`, `BU-22`, `BU-23`, `BU-24`, `BU-25`, `BU-26`, `BU-27`, `BU-28`, `BU-29`, `BU-30`, `BU-31`, `BU-32`, `BU-33`, `BU-34`, `BU-35`, `BU-36` | Consumed broadly for task-derived validation; no BU validator framework. |
| `P3-01` | Software Production | `BU-07`, `BU-18` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P3-02` | Web Production | `BU-05`, `BU-06`, `BU-07`, `BU-08`, `BU-09`, `BU-10`, `BU-12`, `BU-13`, `BU-14`, `BU-15`, `BU-16`, `BU-17`, `BU-19`, `BU-20`, `BU-21`, `BU-22`, `BU-23`, `BU-24`, `BU-25`, `BU-26`, `BU-27`, `BU-28`, `BU-29`, `BU-30`, `BU-31`, `BU-32`, `BU-33`, `BU-34`, `BU-35`, `BU-36` | Primary reusable web-production owner for Option C. |
| `P3-03` | Game Production | `BU-16`, `BU-18`, `BU-22` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P3-04` | Large-Scale / AAA Production | `BU-18` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P3-05` | 3D Production | `BU-11`, `BU-16`, `BU-18`, `BU-22`, `BU-23` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P3-06` | Character / Rigging | `BU-18`, `BU-23` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P3-07` | Animation | `BU-18`, `BU-23` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P3-08` | Environment | `BU-16`, `BU-18`, `BU-22`, `BU-23` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P3-09` | Rendering | `BU-13`, `BU-16`, `BU-18`, `BU-22`, `BU-23` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P3-10` | VFX / Simulation | `BU-18`, `BU-23` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P3-11` | Image | `BU-03`, `BU-08`, `BU-09`, `BU-11`, `BU-13`, `BU-16`, `BU-18`, `BU-22`, `BU-23`, `BU-31` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P3-12` | Audio | `BU-11`, `BU-18`, `BU-22`, `BU-23` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P3-13` | Video | `BU-11`, `BU-13`, `BU-16`, `BU-18`, `BU-22`, `BU-23` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P3-14` | Packaging / Publishing | `BU-06`, `BU-07`, `BU-11`, `BU-16`, `BU-18`, `BU-21`, `BU-22`, `BU-23`, `BU-24`, `BU-25`, `BU-30`, `BU-31`, `BU-36` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P4-01` | Model Comparison | `BU-17`, `BU-27`, `BU-28` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P4-02` | Strategy / Skill Comparison | `BU-17`, `BU-27`, `BU-29` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P4-03` | Learned Routing | `BU-17`, `BU-19`, `BU-20`, `BU-27`, `BU-28`, `BU-29` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P4-04` | Cache / Locality Learning | `BU-28`, `BU-33` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P4-05` | Failure / Repair Learning | `BU-29`, `BU-33`, `BU-35` | Consumed; BU tasks must not reimplement this reusable capability. |
| `P4-06` | Recipe Learning + Full Qualification | `BU-15`, `BU-20`, `BU-36` | Read-only engine qualification/recipe evidence when available; website must not implement it. |

## C. Duplicate implementation removed from the original BU wording

The revised master pack removes these duplicate responsibilities from website ownership:

- `BU-02` no longer owns a migration firewall; it applies `P0-01`.
- `BU-07` no longer owns generic filesystem/process/Git/runtime/browser/workspace/validation infrastructure; it builds one website using P2/P3 capabilities.
- `BU-11` no longer owns an object store, storage abstraction or generic media pipeline; it performs website asset migration/derivative creation.
- `BU-17` no longer owns model, retrieval, knowledge, call-ledger, routing or learning systems; it visualizes/consumes them.
- `BU-20` no longer owns Task/Run/Graph/Event/scheduler/routing infrastructure; it demonstrates it.
- `BU-26` no longer owns a search/retrieval engine; it configures public scope and builds the website search experience on `P2-10`.
- `BU-27` no longer owns model-provider, HTTP, retrieval, call-ledger, routing/evaluation/learning systems; it integrates a public guide.
- `BU-28` no longer owns resource inventory, scheduler, routing or model-provider infrastructure; it presents authorized NVIDIA/compute evidence.
- `BU-29` no longer owns HTTP/model/browser/retrieval/workspace/validation/learning infrastructure; it exposes one bounded public research/tool demo.
- `BU-33` no longer owns Resource/Browser/Validation/Cache-learning systems; it optimizes the website and consumes those capabilities/evidence.
- `BU-35` no longer owns durable execution, call accounting, routing, isolation, validation or failure-learning systems; it defines website-specific fallback/cost behavior.
- `BU-36` no longer owns Git/browser/validation/web-production/publishing/qualification systems; it performs the project deployment and verifies the result.

## D. Engine prompts intentionally not required by Option C today

`P2-08 PostgreSQL Adapter` has no mandatory current BU consumer. The approved Option C scope does not require an accounts/private-project database. If that product scope is added later, create a website task that **consumes** `P2-08`; do not silently add PostgreSQL to the current pack.

## E. Standing invariant

**Engine prompt = reusable mechanism.  
BU prompt = website-specific use of that mechanism.**

If a future BU task starts defining universal provider, model, storage, memory, scheduler, routing, validation, production or learning behavior, stop and move that work to the corresponding P0–P4 owner.
