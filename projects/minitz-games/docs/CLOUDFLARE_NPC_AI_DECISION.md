# Biella Games — Cloudflare Workers AI NPC Decision

Status: `ACTIVE_PROJECT_DECISION`
Authority: Mahdi Taghdisi
Accepted date: `2026-09-01`
Project: Biella Games
Repository: `patrickminitz-web/biella-engine`  
Project path: `projects/minitz-games`

## Accepted direction

Biella Games will use **Cloudflare Workers AI as the connected high-level NPC AI service** for the real Unreal Engine game.

Initial hosted model:

`@cf/nvidia/nemotron-3-120b-a12b`

The initial model is an implementation selection behind a replaceable Game-side adapter. Cloudflare Workers AI is the accepted connected NPC-AI service; the model may be replaced later from measured evidence without changing gameplay contracts.

This decision does not change the approved game direction:

**realistic, physically coherent, highly detailed AAA third-person real-time**.

## Runtime boundary

The connection architecture is:

`Unreal Engine 5.8.2 game -> asynchronous HTTPS -> Biella Games Cloudflare Worker -> Workers AI -> structured NPC decision -> Unreal gameplay validation/execution`

The Cloudflare Worker calls Workers AI using its AI binding / supported Workers AI API and returns a bounded structured decision to the game.

The game must not ship a Cloudflare account API token in the client. The Unreal client talks to the project Worker endpoint; the Worker owns the Workers AI invocation.

## What Workers AI owns

Workers AI may produce high-level NPC cognition such as:

- choose or revise a goal;
- select one allowed tactical intent;
- respond to observed player/rival/infected/world state;
- choose a route objective or target reference from game-provided candidates;
- decide whether to pursue, evade, investigate, regroup, loot, assist, communicate, or change strategy when those intents are enabled by the current game design;
- generate bounded dialogue or reaction text when requested;
- reason over compact NPC memory/state supplied by the game.

## What Unreal remains authoritative for

Workers AI does **not** directly execute or own real-time simulation.

Unreal remains authoritative for:

- actor existence and identity;
- world state;
- collision and physics;
- navigation/path execution;
- movement and locomotion;
- animation;
- aiming and weapon execution;
- combat timing;
- hit resolution;
- damage/health/death;
- inventory/equipment state;
- spawning/despawning;
- mission and arena state;
- save/reconstruction;
- frame-time-critical reactions.

The model returns intent/data. Unreal validates and executes only gameplay actions allowed by the current runtime state and contracts.

## Decision request contract

The Game-side adapter should send the smallest sufficient structured snapshot, conceptually including:

```json
{
  "npc_id": "stable runtime identity",
  "npc_archetype": "project-defined archetype",
  "session_id": "bounded AI conversation/session identity",
  "current_goal": "current high-level goal",
  "perception": {},
  "world_state": {},
  "memory_summary": {},
  "candidate_targets": [],
  "allowed_intents": [],
  "decision_context": {}
}
```

Do not stream the complete game world, raw source tree, or unrelated Project data into every inference request.

## Decision response contract

Workers AI output must be parsed as structured data against a Game-owned schema. Conceptually:

```json
{
  "decision_id": "request-correlated identity",
  "intent": "one of the allowed intents",
  "target_ref": "game-provided target reference or null",
  "parameters": {},
  "dialogue": "optional bounded text",
  "valid_for_ms": 0
}
```

The exact schema is implemented and versioned with the real Game adapter. Unknown intents, malformed responses, stale decision IDs, invalid target references, and responses that no longer match current runtime state are rejected rather than executed.

## Real-time execution rule

Do not call a large language model every frame.

Workers AI decisions are asynchronous and event/cadence driven. Local Unreal AI/runtime systems continue frame-critical behavior while a high-level decision is pending.

The implementation must prove that an unavailable, slow, rate-limited, or malformed AI response does not freeze the game thread or corrupt authoritative gameplay state.

Fallback behavior is a bounded local Game behavior/state path appropriate to the actor and current state. Fallback does not pretend that a Workers AI decision occurred.

## NPC coverage

The same adapter can serve multiple NPC classes, including rival contestants and infected/other NPC archetypes where model-driven cognition is useful. Each archetype gets Project-scoped prompts/context, allowed intents, response schema, cadence, and fallback behavior.

Do not force expensive model reasoning into an archetype when a deterministic local behavior is sufficient for the required gameplay result.

## Current Cloudflare/NVIDIA evidence

Verified on `2026-09-01` from Cloudflare's current Workers AI documentation:

- Workers AI provides REST and OpenAI-compatible chat-completions endpoints.
- Workers AI supports structured/JSON output and function calling for compatible models.
- `@cf/nvidia/nemotron-3-120b-a12b` is Cloudflare-hosted and currently advertises reasoning and function calling.
- Current published unit pricing for that model is `$0.50 / 1M input tokens` and `$1.50 / 1M output tokens`.

Vendor references:

- `https://developers.cloudflare.com/workers-ai/models/nemotron-3-120b-a12b/`
- `https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/`
- `https://developers.cloudflare.com/workers-ai/features/json-mode/`
- `https://developers.cloudflare.com/workers-ai/features/function-calling/`
- `https://developers.cloudflare.com/workers-ai/platform/pricing/`

## Required implementation tasks

1. Create the Biella Games Cloudflare Worker NPC decision endpoint and Workers AI binding.
2. Implement the versioned NPC request/response schema and validation.
3. Implement the Unreal asynchronous HTTP client/adapter.
4. Integrate the adapter first into one live rival contestant.
5. Integrate other NPC archetypes only through their own bounded Project behavior contract.
6. Add timeout/rate-limit/provider-failure local fallback behavior.
7. Measure request latency, token/Neuron usage, decision cadence, cache effectiveness where used, gameplay frame impact, and failure behavior using real gameplay scenarios.
8. Persist exact Worker revision/deployment identity and exact Game source revision for every completed integration milestone.

## Completion evidence

The connected-NPC feature is not complete from a Worker deployment or API response alone.

Minimum proof for the first integration is:

`live Unreal NPC -> real runtime observation/state -> Cloudflare Worker request -> Workers AI inference -> schema-valid decision -> Unreal validation -> real NPC gameplay action/state change`

Evidence must identify the exact Game source revision and exact deployed Worker revision used for the run.
