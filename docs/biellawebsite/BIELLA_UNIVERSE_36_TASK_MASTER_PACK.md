# Biella Universe — 36-Task Website Master Pack

Status: APPROVED OPTION C EXECUTION PROGRAM
Target: https://biellagames.dev
Scope: Turn biellagames.dev into a living demonstration of Biella Engine and Biella Games rather than a conventional marketing site.

## Source rules

- Mine existing Google Drive and GitHub material before creating replacement content.
- Existing Biella website asset control: `docs/biellawebsite/BIELLA_WEBSITE_ASSET_MANIFEST.md`.
- Existing website document surfaces: `51_BIELLA_MARKDOWN_NOTES_WORKSPACE.md` through `60_BIELLA_DOCUMENT_EXPORT_PUBLISHING.md`.
- Preserve the Biella Visual Lock: deep graphite/navy surfaces, Biella violet primary, electric cyan secondary, semantic green/amber/red only, thin precision borders, subtle glass, restrained bloom, compact technical typography.
- Do not activate raw MiniTZ rules, prompts, or project identity. Historical material may be inspected only as source/reference evidence and must be explicitly classified before reuse.
- Do not regenerate an existing approved asset merely because it is easier than locating it.
- GitHub is source/history authority for website implementation.
- Google Drive is a major source library and archive; task 01 must inventory it broadly, not only the `biellawebsite` folder.
- Cloudflare is the target web delivery platform. For a new full-stack build, prefer current Workers Static Assets patterns; use R2 for large web/media objects where useful.
- OpenAI and NVIDIA capabilities are adapters for demonstrations, not permanent Biella architecture.
- Each task stops at its own acceptance boundary and records exact changed files, assets used, tests, and deployment evidence where applicable.

## Prompt template used for every task

Each task must produce:

1. **Source state** — Git branch/commit and Drive inputs used.
2. **Goal** — exact outcome for this task only.
3. **Inputs** — existing assets/specs/components it consumes.
4. **Implementation** — smallest complete change needed.
5. **Validation** — functional, visual, responsive, accessibility, and performance checks relevant to that task.
6. **Evidence** — screenshots/artifacts/test output/URLs as appropriate.
7. **Continuation** — exact next dependency; do not silently begin the next task.

---

# Phase U0 — Discover, classify, and lock the universe

## BU-01 — Full Drive + GitHub Website Source Inventory

**Goal:** Build a complete inventory of usable Biella website source material before any new design generation.

**Inputs:** Entire accessible Google Drive corpus; `docs/biellawebsite`; current repository tree; current live domain observation.

**Deliverables:**
- machine-readable inventory of candidate images, video, 3D, audio, Markdown, text, logos, screenshots, UI concepts, world/game concepts, brand material, research and website specifications;
- exact Drive IDs / GitHub paths / file sizes / modified dates when available;
- duplicate groups and missing-file references;
- explicit list of manifest assets 01–60 located vs not located.

**Acceptance:** No new visual generation is authorized until the inventory can answer where each known website source lives or explicitly mark it missing.

## BU-02 — Source Classification and Historical Firewall

**Goal:** Separate production-ready Biella material from superseded, duplicate, unrelated and historical material.

**Classifications:** `BIELLA_CANON`, `BIELLA_CANDIDATE`, `SUPERSEDED`, `DUPLICATE`, `HISTORICAL_REFERENCE`, `UNRELATED`, `MISSING`.

**Deliverables:** Classification ledger with source identity and reason.

**Acceptance:** No raw MiniTZ identity, rules or accidental visual drift can enter production website paths without an explicit Biella-native decision.

## BU-03 — Visual Canon and Asset Master Selection

**Goal:** Select the strongest existing visual material and lock the production visual canon.

**Inputs:** BU-01/02 inventory; `BIELLA_WEBSITE_ASSET_MANIFEST.md`; visual slots 01–50.

**Deliverables:**
- canonical asset selection per website surface;
- SHA-256/dimensions/format where bytes are accessible;
- desktop/mobile crop strategy;
- transparent-background compliance;
- replacement-needed list only for genuine gaps.

**Acceptance:** Every intended hero/gallery/demo visual has one canonical source or a documented creation gap.

## BU-04 — Content and Story Canon

**Goal:** Convert existing Biella Engine / Biella Games documentation into public-facing story and copy without exaggerating unimplemented capabilities.

**Deliverables:** Approved message hierarchy: what Biella is, what exists now, what is being built, Biella Games identity, capability language, project language, partner/investor language, calls to action.

**Acceptance:** Public copy clearly distinguishes verified current product state from roadmap/demo concepts.

## BU-05 — Universe Information Architecture

**Goal:** Define how a visitor moves through the Biella Universe.

**Primary experiences:** Home/Living Core, Engine, Games, Intelligence, Production, Capabilities, Projects, Worlds/Gallery, Docs/Knowledge, Timeline/News, About/Partners/Contact.

**Deliverables:** Route map, navigation model, page/experience ownership, cross-links, mobile navigation and deep-link rules.

**Acceptance:** Every content class from BU-03/04 has one clear home; no page exists merely to hold leftovers.

## BU-06 — Cloudflare/GitHub Delivery Architecture

**Goal:** Lock the web delivery approach before implementation.

**Preferred baseline:** GitHub-controlled source; Cloudflare Workers Static Assets for the web application; Worker logic only where dynamic behavior is required; R2 for large media/object delivery where beneficial; preview deployments before production.

**Deliverables:** Deployment topology, environments, domains/routes, asset strategy, secrets/bindings list, caching rules, rollback model, budget-sensitive limits.

**Acceptance:** A fresh deployment can be reproduced from GitHub without relying on a developer's local machine or Google Drive as the live filesystem.

---

# Phase U1 — Build the visual and technical foundation

## BU-07 — Website Application Scaffold and Preview Pipeline

**Goal:** Create the real website application structure and reproducible preview deployment path.

**Deliverables:** Website source tree, build scripts, Cloudflare configuration, preview build, baseline tests.

**Acceptance:** One command builds locally and one controlled Git workflow produces a preview deployment.

## BU-08 — Biella Design System

**Goal:** Turn the Visual Lock into reusable production components rather than one-off page styling.

**Deliverables:** Color tokens, surfaces, spacing, grid, borders, buttons, cards, panels, navigation, status, forms, responsive rules.

**Acceptance:** Core pages can be composed without inventing new colors/frames/styles per section.

## BU-09 — Typography, Iconography and Accessibility Foundation

**Goal:** Establish readable futuristic typography and icon behavior without sacrificing usability.

**Deliverables:** Font scale, heading/body/code styles, icon rules, contrast targets, focus states, keyboard baseline, semantic HTML rules.

**Acceptance:** Core component library passes agreed contrast/focus/keyboard checks.

## BU-10 — Motion and Transition System

**Goal:** Create the motion language that makes the site feel alive without becoming a noisy arcade HUD.

**Deliverables:** Entrance/exit transitions, scroll transitions, node/link animation, parallax limits, hover/tap behavior, loading states, reduced-motion mode.

**Acceptance:** Motion is reusable, performant, optional under reduced-motion preferences, and never blocks navigation.

## BU-11 — Asset Ingest, Optimization and Delivery Pipeline

**Goal:** Move selected production assets from source libraries into web-ready canonical storage without losing original identity.

**Deliverables:** Import mapping, original-byte archive references, optimized web derivatives, responsive variants, modern formats, R2/static-asset placement as selected by BU-06.

**Acceptance:** Every production asset can be traced to its source and is served in an appropriately optimized web format.

## BU-12 — Website Content Registry

**Goal:** Make site content data-driven instead of hard-coded across pages.

**Deliverables:** Typed registries for products, capabilities, projects, games/worlds, media, docs, timeline entries and external links.

**Acceptance:** Adding a new project/capability/timeline item does not require rewriting page structure.

---

# Phase U2 — Create the core Biella experience

## BU-13 — Cinematic Entry and Living Biella Core

**Goal:** Make the first screen immediately communicate that the visitor has entered a living system.

**Experience:** Biella identity, living core, subtle system activity, clear `ENTER BIELLA`/primary action, fast fallback for reduced motion/mobile.

**Acceptance:** Strong first impression without delaying meaningful content or harming Core Web Vitals.

## BU-14 — Home Journey: Research → Intelligence → Planning → Creation → Delivery

**Goal:** Build the main scroll/interaction story showing how Biella turns an objective into production work.

**Acceptance:** A non-technical visitor can understand the journey while an expert can inspect deeper details.

## BU-15 — Biella Engine Experience

**Goal:** Present Biella Engine as a living product with current state, architecture concepts, verified capabilities, roadmap and visual systems.

**Inputs:** Engine documentation and canonical dashboard assets.

**Acceptance:** No roadmap capability is presented as already implemented unless current source supports it.

## BU-16 — Biella Games Experience

**Goal:** Create a distinct Games destination for worlds, projects, playable material, production philosophy and future releases.

**Acceptance:** Games feels part of the same universe while having its own emotional identity.

## BU-17 — Intelligence Experience

**Goal:** Visualize research, evidence gathering, model/tool choice, knowledge and reasoning as an explorable system.

**Acceptance:** Demonstration can run with deterministic/sample data if live AI is unavailable; simulation must be labeled when simulated.

## BU-18 — Production Pipeline Experience

**Goal:** Show work moving through code, assets, 3D, rendering, testing, packaging and delivery.

**Acceptance:** Interactive pipeline remains understandable on touch devices and does not imply a fixed mandatory Biella pipeline.

---

# Phase U3 — Make the universe explorable

## BU-19 — Capability Explorer

**Goal:** Let visitors browse Biella capabilities by domain, status, inputs, outputs and connected tools/resources.

**Acceptance:** Clearly separate `available/verified`, `prototype/demo`, and `planned` capability states.

## BU-20 — Interactive Orchestration Demonstration

**Goal:** Let a visitor enter/select an objective and watch a safe demonstration of task decomposition and resource routing.

**Acceptance:** No secret/internal data is exposed; demo can run from synthetic scenarios; live mode is separately identified.

## BU-21 — Project and Showcase System

**Goal:** Build reusable project case-study pages with media, story, technologies, challenges, outputs, timeline and status.

**Acceptance:** New projects are data entries, not bespoke page rewrites.

## BU-22 — Game / World Gallery and Playable Embeds

**Goal:** Create a high-impact gallery for games, worlds and interactive prototypes.

**Acceptance:** Heavy experiences lazy-load; unsupported devices receive useful fallback media/content.

## BU-23 — 3D / Media Gallery

**Goal:** Present 3D, rendering, environment, character, VFX, image, audio and video work with premium presentation.

**Acceptance:** Asset viewer choices respect performance budgets and mobile constraints.

## BU-24 — Interactive Timeline, News and Releases

**Goal:** Show Biella's development as a living history rather than a static blog.

**Acceptance:** Timeline entries are source-backed, dateable and linkable; planned items are visually distinct from released work.

---

# Phase U4 — Turn knowledge and AI into a live product surface

## BU-25 — Public Documentation Hub

**Goal:** Convert relevant accepted documentation into a polished public technical knowledge experience.

**Inputs:** Existing website docs 51–60, especially documentation hub and publishing specifications.

**Acceptance:** Docs are searchable, deep-linkable, version-aware where needed and visually integrated with the Universe.

## BU-26 — Website Search and Retrieval

**Goal:** Provide fast search across public docs, projects, capabilities, releases and selected media metadata.

**Acceptance:** Results expose source page/path and never index quarantined/private/historical material accidentally.

## BU-27 — Ask Biella Interactive Assistant

**Goal:** Add an optional public AI guide that can explain the website, products and public documentation.

**Preferred adapter:** OpenAI Responses/Agents tooling where appropriate; keep provider boundary replaceable.

**Acceptance:** Assistant answers only from approved public context for project-specific claims, identifies uncertainty, and has rate/cost controls.

## BU-28 — NVIDIA Compute / Model Demonstration

**Goal:** Create a visually strong compute/model surface showing how Biella can work with replaceable GPU/model resources.

**Possible adapter evidence:** NVIDIA NIM-compatible model endpoints and health/metrics where an authorized runtime exists.

**Acceptance:** Hardware/model telemetry is live only when truly observed; otherwise it is an explicitly labeled demonstration.

## BU-29 — Live Research / Tool Execution Demonstration

**Goal:** Demonstrate safe web research/tool execution with a controlled public scenario.

**Possible adapter evidence:** OpenAI hosted web/file/code/image tools or equivalent provider implementations.

**Acceptance:** External calls are bounded, rate-limited, observable, and never expose internal project sources.

## BU-30 — About, Partner, Investor and Contact Experience

**Goal:** Convert fascination into clear next actions without reducing the site to a corporate contact page.

**Deliverables:** About/founder/company narrative, partnership paths, investor/press contact, general contact, relevant social/repository links.

**Acceptance:** Forms and links work; spam protection and delivery receipts are validated.

---

# Phase U5 — Make it launch-grade

## BU-31 — SEO, Social Preview and Discoverability

**Goal:** Make every important experience understandable to search engines and share previews.

**Deliverables:** Metadata, canonical URLs, structured data where appropriate, sitemap, robots policy, Open Graph/social images, semantic headings.

**Acceptance:** Automated validation finds no missing critical metadata on launch routes.

## BU-32 — Analytics, Privacy and Product Insight

**Goal:** Measure what visitors actually use without turning the site into a tracking-heavy product.

**Deliverables:** Privacy-conscious analytics, event taxonomy for major interactions, error/performance telemetry, documented retention/consent behavior where required.

**Acceptance:** Key journeys are measurable and no secret/project data is included in analytics payloads.

## BU-33 — Performance, Caching and Core Web Vitals

**Goal:** Make the cinematic experience fast despite rich assets.

**Deliverables:** bundle analysis, lazy loading, code splitting, asset budgets, caching, image/media optimization, preloading strategy, Worker/R2 cache rules where used.

**Acceptance:** Define and meet explicit desktop/mobile performance budgets before launch.

## BU-34 — Responsive, Browser, Device and Accessibility Qualification

**Goal:** Prove the experience works across phones, tablets, desktops, keyboard navigation and reduced-motion users.

**Acceptance:** Critical journeys pass on agreed browser/device matrix with no blocking accessibility defect.

## BU-35 — Resilience, Security, Error and Cost Controls

**Goal:** Ensure dynamic/AI features fail safely and cannot create uncontrolled cost or broken experiences.

**Deliverables:** 404/500/offline states, timeouts, rate limits, abuse controls, API error fallbacks, AI budget ceilings, media failure fallbacks, logging.

**Acceptance:** Intentionally failing each external dependency still leaves a usable website.

## BU-36 — Cloudflare Production Launch and Final Qualification

**Goal:** Launch biellagames.dev as the Biella Universe and prove the deployed system, not just the local build.

**Deliverables:** production deployment, domain/HTTPS verification, cache verification, smoke tests, analytics verification, rollback point, final visual QA, launch evidence bundle.

**Acceptance:** All critical routes and interactions work on production; the exact deployed Git commit is recorded; rollback is proven; no launch-critical blocker remains.

---

# Execution order

Default order: BU-01 → BU-36.

Parallel work is allowed only when dependencies are actually independent. In particular:

- BU-01 and source discovery must precede asset regeneration.
- BU-02/03/04/05/06 must be stable before broad page implementation.
- BU-07–12 establish shared foundations consumed by BU-13 onward.
- BU-27–29 are optional live adapters: the core site must remain complete if they are disabled.
- BU-31–36 qualify the finished production experience rather than substitute for unfinished product work.

# Initial target

**36 prompts/tasks.**

This count deliberately uses existing Drive/GitHub material to avoid redundant asset-creation prompts. New prompts should be added only when BU-01/02 reveals a genuine missing subsystem or when an implementation task proves too large to validate as one independent boundary.
