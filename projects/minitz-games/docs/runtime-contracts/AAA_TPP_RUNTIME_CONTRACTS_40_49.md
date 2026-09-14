# BIELLA GAMES — AAA TPP RUNTIME CONTRACTS 40–49

Status: `OWNER_DIRECTED_ACCEPTED_REQUIREMENT`
Authority: Mahdi Taghdisi, explicit current project direction, 2026-09-01
Project: Biella Games
Scope: measurable real-time runtime quality, diagnostics, scalability, and production evidence for the playable AAA realistic third-person game
Repository: `patrickminitz-web/biella-engine`  
Project path: `projects/minitz-games`
Part: `4`

This file defines Contracts 40–49 only. Contracts 01–39 are now represented by their current dedicated range files and are not redefined here. This file does not select a game engine, engine version, operating system, console/PC target, exact frame-rate tier, exact resolution tier, GPU vendor, upscaler, physics middleware, build service, or release platform unless separately approved.

The controlling game direction remains a genuinely playable real-time third-person AAA-quality realistic shooter/survival game. Static media, prerendered sequences, benchmark-only scenes, fake HUDs, scripted presentations, generated pictures, or website interactions cannot satisfy gameplay/runtime implementation.

## 40 — RUNTIME TELEMETRY + MEASURED EVIDENCE

Runtime quality claims must be supported by measurements from the actual running game or packaged build, tied to exact source/build/configuration identity where practical.

Required evidence capabilities, as applicable:
- timestamped frame-time and performance capture from representative gameplay;
- CPU and GPU timing sufficient to identify the current limiting stage rather than relying only on average FPS;
- memory/residency evidence for system RAM, VRAM and streaming pressure where observable;
- input/system latency evidence when responsiveness is being qualified;
- streaming, shader/pipeline compilation, asset-load and traversal hitch evidence;
- actor/system counts or equivalent workload context so a metric can be interpreted against the tested scene;
- logs/events sufficient to connect visible failure, hitch or state corruption to the runtime subsystem that produced it;
- exact quality settings, resolution/render scale, enabled reconstruction/frame-generation features and representative hardware/resource identity;
- native simulation/render metrics reported separately from generated/display-frame metrics;
- retained raw captures or machine-readable summaries when they materially support acceptance or regression diagnosis.

A single FPS counter, screenshot, average number, benchmark splash screen, vendor overlay or agent statement is insufficient evidence for production performance.

Acceptance requires a reproducible runtime capture showing workload context plus enough measurements to identify frame time, memory pressure and major runtime stalls relevant to the tested milestone.

## 41 — FRAME PACING + STUTTER + HITCH CONTROL

A visually impressive build that repeatedly stalls, hitches or produces unstable frame delivery is not an AAA real-time result.

Required:
- frame-time distribution is evaluated, not only average FPS;
- traversal, combat, spawning, VFX bursts, world streaming, save/checkpoint work, shader/pipeline creation and asset activation are tested for hitches when those systems are present;
- long blocking work on the gameplay/render-critical path is identified and reduced, moved, precomputed, cached or scheduled according to the selected runtime where technically appropriate;
- background work cannot starve gameplay-critical simulation or cause uncontrolled frame spikes;
- asset and world streaming are tested while the player moves at representative traversal speed rather than only from a stationary camera;
- expensive one-time initialization is distinguished from recurring runtime stutter;
- frame pacing remains stable through camera motion, dense encounters and world transitions appropriate to the milestone;
- asynchronous work must still preserve deterministic game-state ordering where authoritative state depends on it;
- quality reductions used to remove hitches are explicit and measurable rather than silently lowering the accepted visual target;
- generated/display frames must not conceal severe native-frame or simulation stalls in reported acceptance evidence.

Exact percentile budgets remain `UNKNOWN` until target platforms/tiers are approved, but the build must expose and track frame-time stability rather than treating it as optional polish.

Acceptance requires representative gameplay traces that reveal recurring and worst-case hitches and show that known production-blocking stalls are either removed or explicitly recorded as unresolved.

## 42 — INPUT LATENCY + CONTROL RESPONSIVENESS

Third-person shooter controls must respond to current player input through the live simulation and render path with measurable, stable behavior.

Required:
- input sampling, player/controller update, camera update, simulation, render submission and displayed result remain temporally coherent;
- camera motion, aiming, locomotion and combat controls must not feel detached because of avoidable buffering, frame queueing, excessive smoothing or inconsistent update timing;
- latency-sensitive controls are tested under representative GPU/CPU load, not only in an empty scene;
- frame generation or other display-side interpolation cannot be reported as a reduction in native simulation/input response unless measured evidence proves the actual latency path;
- control response remains valid when the renderer is GPU-bound and when the game thread is CPU-bound where those states are supported by the current build;
- pause/menu/loading states cannot accidentally continue gameplay input unless explicitly intended;
- device rebinding, dead-zone, sensitivity, acceleration and accessibility options remain Project/runtime settings rather than hardcoded universal assumptions;
- instrumentation must distinguish input-to-simulation timing from render/display timing when diagnosing responsiveness;
- supported low-latency technologies may be used as replaceable implementations without becoming game-semantic authority;
- exact acceptable latency targets remain tied to approved hardware/platform quality tiers rather than invented globally.

NVIDIA Reflex/Reflex 2 instrumentation or equivalent platform/vendor tooling may be used where supported to measure or reduce portions of the latency path. Such tooling supplements, rather than replaces, whole-game input/runtime validation.

Acceptance requires an interactive runtime test under representative load with observable input -> player/camera/game-state response and latency evidence appropriate to the selected platform/runtime.

## 43 — CPU + GPU + VRAM + RAM RESOURCE ACCOUNTING

The game must treat compute and memory as bounded runtime resources. High-detail content cannot be accepted on screenshot fidelity alone if representative gameplay exhausts or destabilizes the target resource profile.

Required:
- CPU cost is measured for gameplay, AI, animation, physics, audio, streaming and other material systems as they become present;
- GPU cost is measured for geometry, lighting, shadows, reflections, post-processing, VFX, reconstruction and other material passes as supported by the renderer;
- VRAM residency is measured for geometry, textures, render targets, acceleration structures, buffers and streamed content where observable;
- system RAM use is measured for world state, assets, caches, audio, navigation, runtime systems and tooling/runtime overhead relevant to the packaged game;
- temporary spikes are distinguished from stable residency and from leaks;
- memory exhaustion, allocator failure, residency thrash and uncontrolled resource growth are treated as runtime defects, not acceptable side effects of AAA quality;
- budget pressure may trigger explicit scalability or streaming behavior, but must not corrupt authoritative gameplay state;
- stale or non-critical resources may be evicted only when reconstructable or reloadable without losing required game state;
- measurements use representative playable workloads rather than editor-only or empty-scene conditions;
- exact numeric budgets remain `UNKNOWN` until target hardware/quality tiers are approved.

Acceptance requires measured CPU/GPU/RAM/VRAM evidence from representative play sufficient to identify the dominant resource constraints and any unresolved production-risk spikes or leaks.

## 44 — STREAMING STRESS + WORLD-TRAVERSAL CONTINUITY

Open-world streaming must survive real traversal and gameplay pressure without exposing fake world completion.

Required:
- world regions, geometry, textures, collision, navigation, audio, VFX and gameplay entities enter/leave residency through the selected runtime's real streaming system;
- high-speed traversal, camera rotation, teleport/debug relocation where used for testing, vehicle movement and boundary crossing are stress-tested as relevant;
- streaming cannot expose persistent voids, missing collision, untextured critical surfaces, duplicate actors, stale actors, unloaded mission objects or mismatched world state;
- required gameplay-critical content is prioritized ahead of non-critical distant detail when resource pressure requires prioritization;
- streaming boundaries preserve valid actor identity/state or use explicit reconstruction rules;
- navigation/collision cannot disappear before dependent actors or missions are safely transitioned;
- content loading and decompression cannot repeatedly block the critical frame path beyond approved budgets;
- failure/retry of streamed content is observable and must not be silently represented as successful loading;
- traversal testing includes representative world complexity and actor/system activity for the current milestone;
- deterministic test routes or recorded traces may be used to reproduce streaming regressions without turning them into scripted gameplay completion.

Acceptance requires live traversal across multiple streamed regions with valid rendering, collision, navigation and gameplay state while recording streaming and frame-time evidence.

## 45 — LOD / HLOD / CULLING / OCCLUSION CORRECTNESS

Scalability systems may reduce distant work but cannot falsify nearby gameplay or visibly collapse the realistic world.

Required:
- geometry detail uses the selected runtime's LOD/HLOD/virtualized-geometry or equivalent mechanisms where useful;
- texture/mip detail scales with projected importance and residency constraints without persistent unreadable near-field assets;
- culling/occlusion removes work only when the removed content is not required for the current rendered/gameplay result;
- LOD transitions preserve silhouette, scale, material identity and lighting continuity at gameplay distances;
- collision, navigation and gameplay-relevant bounds remain synchronized with the authoritative object state rather than blindly following visual LOD removal;
- actors, hazards, mission-critical objects and interactables cannot disappear or become non-functional solely because a visual culling heuristic misclassified them;
- foliage, crowds, infected, rivals, vehicles, props, lights, shadows and VFX may use distance/importance scalability without corrupting authoritative simulation;
- hysteresis/fade/transition strategies may be used to reduce popping where appropriate;
- aggressive culling cannot produce visible holes, shadow discontinuities, reflection contradictions or sudden gameplay readability loss;
- scalability behavior is validated during motion and rapid camera changes, not only from fixed screenshots.

Acceptance requires moving-camera runtime evidence through representative dense scenes showing correct visual transitions plus valid gameplay/collision behavior across the applied scalability systems.

## 46 — SHADER / PSO / MATERIAL PIPELINE STABILITY

Rendering features and materials must not depend on hidden editor warm state or uncontrolled runtime compilation that causes shipping-build instability.

Required:
- material/shader variants used by the approved playable content are reproducibly buildable from source/configuration;
- runtime pipeline/shader creation behavior is observable and profiled where it can stall or fail;
- precompilation, pipeline caches, warmup or equivalent runtime-specific mechanisms may be used when they measurably reduce production stutter;
- missing or incompatible shader/pipeline data must produce a diagnosable failure or supported fallback rather than silent corruption;
- material feature growth is bounded so content creation cannot accidentally cause uncontrolled permutation explosion;
- pipeline caches are treated as rebuildable acceleration unless the selected runtime explicitly defines a durable distribution format;
- cache invalidation follows relevant source/driver/runtime/configuration changes rather than accepting stale binary state as authority;
- packaged builds must not depend on one developer workstation's hidden local shader cache for normal operation;
- rendering fallback must preserve gameplay visibility even when an optional advanced feature is unavailable;
- temporal reconstruction, ray tracing and vendor-specific paths must integrate through supported runtime capability checks and compatible resource states.

Acceptance requires a clean or appropriately cold/warm launch test that exposes shader/pipeline preparation behavior and demonstrates that representative gameplay does not rely on undeclared editor-local compilation state.

## 47 — CRASH / HANG / ASSERT / DIAGNOSTIC EVIDENCE

Production stability failures are evidence, not noise to hide after a successful screenshot or partial play session.

Required:
- crashes, fatal errors, assertions, GPU/device loss, deadlocks/hangs and unrecoverable content-load failures are recorded with the best available exact source/build/configuration identity;
- runtime logs preserve sufficient timestamp/context to correlate failure with the active gameplay/world/loading state;
- crash dumps, call stacks, GPU diagnostics or equivalent platform evidence are retained when the selected runtime/platform supports them and they materially aid diagnosis;
- watchdog or hang detection may be used where appropriate to distinguish a stalled process from a long but progressing operation;
- repeated failures are grouped by evidence rather than hidden by automatic relaunch loops;
- recovery after a bounded failure must preserve valid durable game state and must not fabricate completion for the failed action;
- optional vendor features failing capability checks may disable/fallback explicitly, but core gameplay failure cannot be reported as a successful vendor fallback;
- production packages must not suppress fatal diagnostics solely to create clean promotional capture;
- exact reproduction steps, seed/route/save input and resource identity are retained when they materially improve reproducibility;
- unresolved stability defects remain listed against the affected build rather than disappearing when another scene happens to run.

NVIDIA Nsight Aftermath SDK or equivalent platform/vendor crash tooling may be used where supported to retain GPU mini-dump/diagnostic evidence. It remains an optional diagnostic implementation and never substitutes for exact game build/runtime evidence.

Acceptance requires at least the diagnostic pipeline needed by the selected runtime to retain actionable evidence from representative fatal/failure cases encountered during qualification.

## 48 — REPRODUCIBLE RUNTIME SCENARIOS + REGRESSION AUTOMATION

Automation supports runtime truth but cannot replace interactive gameplay acceptance where human input/readability/feel are part of the contract.

Required:
- representative test scenarios may use deterministic seeds, fixed saves, bounded test maps, scripted input traces or controlled spawn/world conditions where technically appropriate;
- a scenario records enough source/build/configuration/input identity to be rerun after changes;
- automated checks may validate launch, player/camera response, mission state, AI state transitions, collision, streaming, save/load, performance thresholds or visual/runtime invariants as supported by the current implementation;
- scripted automation must drive the real runtime systems rather than calling hidden success hooks that bypass normal gameplay rules;
- failed checks retain evidence and cannot be overwritten by a later retry reported as if the first run never failed;
- nondeterministic simulation is allowed where appropriate, but reproducibility should use bounded seeds/state capture/statistical expectations rather than pretending perfect determinism exists;
- automated rendering comparisons must tolerate intended temporal variation while still detecting material geometry, lighting, UI, streaming or corruption regressions;
- test fixtures remain Project-scoped and cannot become universal gameplay canon merely because automation uses them;
- regression suites should prioritize high-value runtime contracts and known failure classes rather than maximizing test count;
- manual play evidence remains required for contracts whose acceptance includes responsiveness, readability, feel or emergent interaction not adequately captured by automation.

Acceptance requires at least one reproducible real-runtime scenario capable of detecting a meaningful regression without bypassing the gameplay system under test.

## 49 — QUALITY SCALABILITY + VENDOR-NEUTRAL ADVANCED RENDERING

The game may use advanced GPU/vendor technologies to reach higher image quality or performance, but optional implementations cannot redefine gameplay correctness or make unsupported hardware appear complete.

Required:
- quality/scalability settings are explicit, versionable and attributable to the selected build/configuration;
- core gameplay remains valid when optional ray tracing, reconstruction, frame generation, low-latency or vendor-specific features are unavailable, unless a future approved platform requirement explicitly makes one mandatory;
- advanced features are enabled only after supported capability/resource checks;
- visual comparisons validate both static fidelity and motion/temporal behavior, including disocclusion, transparency, particles, reflections, fine geometry, UI/HUD separation and fast camera motion where relevant;
- upscaling/reconstruction quality is evaluated for shimmer, ghosting, instability, detail loss and motion artifacts rather than only still-frame sharpness;
- frame-generation output is reported separately from native rendered FPS and simulation rate;
- low-latency integration is measured rather than assumed from a feature toggle;
- ray/path-traced effects, if used, preserve gameplay readability and are profiled for representative world/actor/VFX workloads;
- fallback paths cannot silently switch to visibly broken materials, missing shadows/lighting or invalid gameplay visibility;
- quality tiers may trade resolution, ray count, shadow/reflection distance, VFX density, LOD and related rendering cost, but may not disable required gameplay state or collision/AI correctness merely to meet performance.

Current NVIDIA implementation families that may be evaluated where supported include DLSS 4.5 Super Resolution, Ray Reconstruction, Dynamic Multi Frame Generation / Multi Frame Generation 6X through supported Streamline or engine integrations, and NVIDIA Reflex/Reflex 2 latency technologies. These remain optional replaceable implementations; equivalent or future implementations may be used when they satisfy the same Task-derived quality and evidence contract.

Acceptance requires side-by-side or otherwise attributable runtime evidence for the enabled quality path and its supported fallback, including native frame time, generated/display frame reporting when applicable, temporal/motion quality and gameplay correctness.

## NVIDIA IMPLEMENTATION REFERENCES — NON-AUTHORITATIVE

Checked 2026-09-01 only to keep optional vendor examples aligned with current NVIDIA capabilities. These references do not make NVIDIA a permanent dependency or authority over Biella Games requirements.

- NVIDIA DLSS 4.5 developer overview: `https://developer.nvidia.com/rtx/dlss`
- NVIDIA Streamline SDK: `https://developer.nvidia.com/rtx/streamline`
- NVIDIA Reflex developer technology: `https://developer.nvidia.com/performance-rendering-tools/reflex`
- NVIDIA Nsight Aftermath SDK: `https://developer.nvidia.com/nsight-aftermath`

## COMMON COMPLETION RULE

For Contracts 40–49, `COMPLETE` requires editable source/configuration + actual game/runtime or packaged-runtime execution as applicable + task-derived measured evidence. Benchmark overlays, screenshots, offline renders, generated/display frames, vendor feature toggles, logs without the corresponding runtime behavior, and agent statements may support evidence but cannot substitute for the real playable result.

Contracts 01–39 remain owned by their current dedicated range files; this file does not redefine them or claim runtime implementation completion for them.
