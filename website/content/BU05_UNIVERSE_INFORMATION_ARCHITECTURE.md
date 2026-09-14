# BU-05 — Universe Information Architecture

Task: `WEB-BU-05`
Status: `CANONICAL_WEBSITE_INFORMATION_ARCHITECTURE`
Prepared UTC: `2026-09-01T17:32:18Z`
Authority basis: canonical task ledger row `WEB-BU-05`; approved Option C Website program; durable `WEB-BU-04` content/story canon; current Website branch source readback.
Capability mode: `NOT_REQUIRED` for runtime implementation. BU-05 defines Website Project route, navigation, and content ownership only. It does not implement page components, routing code, deployment, Engine mechanisms, or Game runtime behavior.

## 1. Task boundary

This document defines the public information architecture for `biellagames.dev`.

It establishes:
- canonical public routes and stable route purposes;
- global navigation and discovery relationships;
- content responsibility for each public surface;
- source/truth-label requirements inherited from BU-04;
- ownership handoffs to later BU tasks.

It does not:
- build or deploy the website;
- create page UI, visual masters, or media derivatives;
- create a second Engine scheduler, memory, routing, model, retrieval, browser, storage, validation, publishing, or learning system;
- create or imply Biella Games runtime completion;
- promote missing visual bytes or generated candidates into canon;
- freeze volatile Engine/Game status values into permanent marketing copy.

## 2. Reobserved source snapshot

| Source | Identity used by BU-05 |
|---|---|
| Canonical task ledger | `MINITZ_CANONICAL_TASK_LEDGER` Drive `1HZw4AOBf4ccVs_0f5BODrd3CFrX0RBxG7nWC2jmW-Cw`; task `WEB-BU-05` |
| Website branch before BU-05 write | `patrickminitz-web/biella-engine` branch `website`, commit `e6001ca86e028a03ef1f77d49028070e845f974a`, tree `f6298a11d062e2e542b28b924e5a1dc84cf0b0b6` |
| Website execution authority | `website/AGENTS.md` blob `62d492b3788158b8b1c3b2dcdbeda53e2a61b9cd` |
| Website program authority | `docs/biellawebsite/MINITZ_UNIVERSE_36_TASK_MASTER_PACK.md` blob `421535f54c25f1383b5b7e62898eb3b6e9c28659` |
| Content/story predecessor | `website/content/BU04_CONTENT_AND_STORY_CANON.md` blob `3ebb3f235d8a9ec8e82f99f982d162ecb751d501`; Drive `1JV60TYXBX-jeneAHu41XmHooC7YNy66HAaSXTie504s` |
| Canonical Website Drive root | `MINITZ_WEBSITE` folder `1btVF8nJbwGWhuEA4N9vmgZVckVDNv07V` |

BU-04 contains volatile examples of Engine/Game status. BU-05 uses its story spine, labels, and claim guardrails but does not promote those time-sensitive examples into permanent route truth. Later page implementation must re-read current authoritative state before rendering current-status claims.

## 3. Canonical public route map

These eleven surfaces are the canonical top-level information architecture required by the approved Option C program.

| Surface | Canonical route | Primary purpose | Primary later owner |
|---|---|---|---|
| Home | `/` | Explain Biella's durable goal-to-output thesis and direct visitors to the four major product/story lanes. | `WEB-BU-13`, `WEB-BU-14` |
| Engine | `/engine` | Present Biella Engine as the project-neutral execution/production engine using current source-backed status and architecture. | `WEB-BU-15` |
| Games | `/games` | Present Biella Games as a separate real-time game project, with runtime/media claims gated by accepted Game evidence. | `WEB-BU-16` |
| Intelligence | `/intelligence` | Explain models, tools, scoped knowledge, research, routing, and clearly labeled live/demo intelligence surfaces. | `WEB-BU-17`, `WEB-BU-20`, `WEB-BU-27`, `WEB-BU-29` |
| Production | `/production` | Explain the multi-domain production pipeline across software, game, 3D, media, validation, recovery, and delivery. | `WEB-BU-18` |
| Capabilities | `/capabilities` | Expose semantic capabilities with explicit verified / implemented-not-qualified / blocked / planned states. | `WEB-BU-19` |
| Projects | `/projects` | Provide source-backed project/showcase entries without leaking one Project's truth into another. | `WEB-BU-21` |
| Galleries | `/galleries` | Entry point for accepted Game/world, 3D, image, audio, video, and other qualified media. | `WEB-BU-22`, `WEB-BU-23` |
| Docs | `/docs` | Publish approved public documentation with stable deep links and version/source context. | `WEB-BU-25`, `WEB-BU-26`, `WEB-BU-27` |
| Timeline | `/timeline` | Present source-backed milestones, news, releases, and planned items with explicit state distinctions. | `WEB-BU-24` |
| Contact | `/contact` | Provide the public contact/company-interest destination without unsourced team, funding, launch, pricing, customer, or partnership claims. | `WEB-BU-30` |

No additional top-level route is canonicalized by BU-05. Later tasks may add subordinate routes when their own contracts require them, while preserving these top-level identities.

## 4. Global navigation architecture

### 4.1 Desktop

Home is reached through the Biella mark/logo rather than consuming a persistent text slot.

Primary navigation:
1. `Engine` → `/engine`
2. `Games` → `/games`
3. `Intelligence` → `/intelligence`
4. `Production` → `/production`
5. `Explore` → disclosure containing:
   - `Capabilities` → `/capabilities`
   - `Projects` → `/projects`
   - `Galleries` → `/galleries`
   - `Timeline` → `/timeline`
6. `Docs` → `/docs`
7. `Contact` → `/contact`

This grouping keeps every canonical surface reachable from global navigation without forcing eleven equal-weight desktop items.

### 4.2 Mobile and narrow layouts

The mobile navigation preserves the same route identities. Grouping may collapse into an accessible menu, but the information hierarchy must not hide or rename canonical surfaces into unrelated marketing concepts.

### 4.3 Local navigation

- Product/story pages may use section navigation anchored within their canonical route.
- Deep collection pages must provide a stable path back to their top-level parent.
- Breadcrumbs are appropriate for Docs, Projects, Galleries, Capabilities, and Timeline detail pages.
- Search, when BU-26 exists, is a discovery mechanism over approved public content; it does not replace the route hierarchy.
- Query parameters are for filtering/view state, not canonical content identity. Canonical content receives stable paths.

## 5. Route content contracts

### 5.1 Home — `/`

Required content responsibilities:
- concise Biella thesis: durable AI production/execution rather than a chatbot-only story;
- clear entry to Engine, Games, Intelligence, and Production;
- visible distinction between verified current work and roadmap/demo material;
- project/showcase or capability teasers only when source-backed;
- no claim that the full Engine, game, or public product is complete unless current evidence supports it.

Home is an orientation surface, not a substitute for detail pages.

### 5.2 Engine — `/engine`

Required content responsibilities:
- project-neutral Engine identity and boundaries;
- core execution concepts such as Task, Run, Graph, Capability, Resource, Artifact, Event, evidence, and scoped knowledge when supported by current source;
- current implementation/qualification status sourced from current Engine authority rather than copied permanently into this IA;
- links to `/capabilities`, `/production`, `/docs`, and relevant `/timeline` entries;
- explicit separation from Website and Game project implementation.

### 5.3 Games — `/games`

Required content responsibilities:
- accepted Biella Games product direction from current Game authority;
- current editable-source/runtime status with unresolved evidence stated precisely;
- accepted runtime media only through the Game runtime-media admission lane;
- links to qualified Game/world gallery content and source-backed milestones when available;
- no screenshots, concept art, generated media, website interactions, or prerecorded footage presented as gameplay completion.

### 5.4 Intelligence — `/intelligence`

Required content responsibilities:
- explain replaceable models/tools/resources, research, retrieval/context, routing, and scoped knowledge only to the extent supported by current Engine evidence;
- distinguish `VERIFIED_CURRENT` behavior from `SIMULATED_DEMO`, `ROADMAP`, and `BLOCKED` behavior;
- route capability detail to `/capabilities`;
- route approved public documentation to `/docs`;
- dynamic demonstrations remain owned by later BU tasks and must not be implied by this architecture document.

### 5.5 Production — `/production`

Required content responsibilities:
- present the cross-domain creation path from objective to durable deliverable;
- organize software, web, game, 3D, rendering, VFX, image, audio, video, packaging, validation, and recovery as evidence-backed production areas;
- show incomplete production packs as incomplete rather than visually implying completion;
- link to qualified artifacts in `/galleries` and project results in `/projects`.

### 5.6 Capabilities — `/capabilities`

Required content responsibilities:
- capability catalog/explorer entry;
- explicit state per capability;
- separation of semantic capability from provider/model/tool/resource implementation;
- filters may be added later without changing canonical capability identity;
- capability existence must never be treated as proof that a compatible resource is currently available.

Detail route reserved for later implementation: `/capabilities/:capability-id`.

### 5.7 Projects — `/projects`

Required content responsibilities:
- project-scoped showcases and case studies with their own source/evidence context;
- no cross-project leakage of requirements, brand, visual canon, or acceptance;
- no project artifact shown as Engine-global truth.

Detail route reserved for later implementation: `/projects/:project-slug`.

### 5.8 Galleries — `/galleries`

Required content responsibilities:
- only accepted or explicitly labeled candidate/public-reference media;
- exact provenance for media that makes implementation/runtime claims;
- clear collection separation between Game/world media and broader 3D/media artifacts.

Reserved subordinate routes:
- `/galleries/game-world`
- `/galleries/3d-media`

Additional collection routes may be added only by the owning later task. Missing visual master slots remain gaps; BU-05 does not fill them.

### 5.9 Docs — `/docs`

Required content responsibilities:
- approved public documentation only;
- stable deep-linkable document identity;
- source/version context where relevant;
- explicit current/historical distinctions;
- search and Ask Biella enhancements remain later task responsibilities.

Detail route reserved for later implementation: `/docs/:doc-slug`.

### 5.10 Timeline — `/timeline`

Required content responsibilities:
- source-backed milestones, releases, news, and planned items;
- date plus source identity where available;
- explicit distinction between completed/released, current work, blocked work, roadmap, and historical reference;
- no stale snapshot promoted as current state.

Detail route reserved for later implementation when needed: `/timeline/:entry-slug`.

### 5.11 Contact — `/contact`

Required content responsibilities:
- public contact path and project/company-interest entry;
- founder/project authority identity only when source-backed;
- future partner/investor/about content may be surfaced here or through subordinate routes owned by `WEB-BU-30`;
- no invented team size, funding, customers, release date, pricing, partnerships, office/location, or business traction.

BU-05 does not canonicalize separate `/about`, `/partners`, or `/investors` routes; BU-30 may do so if its own accepted content contract requires them.

## 6. Truth-label and source contract

The BU-04 labels remain the Website content-state vocabulary:
- `VERIFIED_CURRENT`
- `IMPLEMENTED_NOT_QUALIFIED`
- `READY_FRONTIER`
- `RUNNING`
- `BLOCKED`
- `ROADMAP`
- `SIMULATED_DEMO`
- `CANDIDATE`
- `HISTORICAL_REFERENCE`
- `MISSING_SOURCE`

Route definitions are stable; volatile product status is not.

Rules:
1. Current-status modules must resolve current authoritative source/evidence at the time their owning implementation task builds or refreshes them.
2. A page may contain multiple labels because different claims on one route may have different evidence states.
3. A visual treatment must not erase the textual/semantic distinction between verified, blocked, roadmap, candidate, historical, and demo material.
4. `MISSING_SOURCE` media must not silently disappear into a guessed replacement that changes the claim.
5. Website-owned navigation/content structure never becomes Engine Memory, Project Memory for another project, or universal Engine policy.

## 7. Content hierarchy and cross-link rules

### Level 0 — global identity
`/`

### Level 1 — canonical public surfaces
`/engine`, `/games`, `/intelligence`, `/production`, `/capabilities`, `/projects`, `/galleries`, `/docs`, `/timeline`, `/contact`

### Level 2 — owned detail/collection routes
Examples reserved above, created only by the corresponding later BU owner.

Cross-link rules:
- Home may link to every Level 1 surface.
- Engine links naturally to Capabilities, Production, Docs, Projects, and Timeline.
- Games links naturally to Projects, Galleries, and Timeline.
- Intelligence links naturally to Capabilities, Docs, Projects, and Timeline.
- Production links naturally to Capabilities, Projects, Galleries, Docs, and Timeline.
- Capabilities/Projects/Galleries/Docs/Timeline may cross-link through exact typed identities, not title-string guessing.
- Contact is a terminal action surface and may be linked globally from any page.
- Cross-links never alter source authority or claim state.

## 8. Later-task ownership map

| BU task | IA destination owned or consumed |
|---|---|
| `WEB-BU-06` | Delivery topology for all canonical routes; does not change information ownership. |
| `WEB-BU-07` | Creates the actual application/router scaffold for these canonical route identities. |
| `WEB-BU-08`–`WEB-BU-10` | Apply design, typography/accessibility, and motion across the route system. |
| `WEB-BU-11` | Supplies qualified media assets consumed primarily by Home, Games, Production, Galleries, Projects, and social surfaces. |
| `WEB-BU-12` | Creates the typed content registry that binds route content to claim labels and source refs. |
| `WEB-BU-13`–`WEB-BU-14` | Own the Home experience. |
| `WEB-BU-15` | Owns `/engine`. |
| `WEB-BU-16` | Owns `/games`. |
| `WEB-BU-17` | Owns `/intelligence` core experience. |
| `WEB-BU-18` | Owns `/production`. |
| `WEB-BU-19` | Owns `/capabilities` explorer. |
| `WEB-BU-20` | Adds orchestration demonstration within an appropriate Intelligence/Engine context without creating a new top-level surface. |
| `WEB-BU-21` | Owns `/projects` and project detail pages. |
| `WEB-BU-22`–`WEB-BU-23` | Own `/galleries` collections and viewers. |
| `WEB-BU-24` | Owns `/timeline`. |
| `WEB-BU-25`–`WEB-BU-27` | Own `/docs`, search, and bounded public guide surfaces. |
| `WEB-BU-28`–`WEB-BU-29` | Add bounded demonstrations within Intelligence/Capabilities/Projects contexts; no new universal system. |
| `WEB-BU-30` | Owns `/contact` and any accepted subordinate company/partner/investor/about routes. |
| `WEB-BU-31`–`WEB-BU-36` | Discoverability, analytics, performance, qualification, resilience, and production launch across the same canonical route hierarchy. |

## 9. URL and content identity rules

- Canonical paths are lowercase.
- Canonical top-level route identity is path-based and stable.
- Hyphens are used for multiword path segments.
- Query parameters express filter/view state only.
- Fragment identifiers express in-page sections only.
- Redirects may preserve changed legacy links later, but BU-05 creates no legacy redirect contract.
- Page titles, navigation labels, and marketing headings may evolve without changing canonical route identity unless an owning later task explicitly migrates the route.
- Typed content records created by BU-12 must reference stable route/content identities rather than deriving authority from display strings.

## 10. Acceptance checks

BU-05 is satisfied when:
1. all eleven approved public surfaces have one canonical top-level route;
2. every surface has an explicit purpose and content responsibility;
3. global desktop/mobile/local navigation relationships are defined;
4. BU-04 truth labels and claim guardrails are preserved;
5. later BU ownership is mapped without beginning those tasks;
6. Game runtime/media evidence remains distinct from Website media;
7. Website architecture does not duplicate universal Engine mechanisms;
8. missing visual assets remain explicit gaps;
9. volatile current-status values are not frozen into the IA;
10. the exact document is durably published to Website GitHub source and canonical Website Drive with remote readback.
