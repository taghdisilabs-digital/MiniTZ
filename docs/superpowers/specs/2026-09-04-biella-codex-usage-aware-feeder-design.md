# Biella Codex Usage-Aware Feeder Design

## Goal
Keep `biella-codex` as the only AI/production entrypoint while adding an internal single-flight feeder that advances bounded tasks and chooses Codex models by task class and observed availability.

## Authority and boundaries
- The user controls only Codex account usage/reset decisions.
- The feeder must never invoke `/usage`, redeem a reset, buy credits, or alter account quota settings.
- Model/provider/tool choice after launch is execution routing, not a new authority hierarchy.
- One active feeder task at a time. Preserve verified work and never reset progress merely because a model/session changes.

## Routing
- `simple`: prefer `gpt-5.6-luna` with medium reasoning; fall back to other available Codex models without probing.
- `medium`: prefer Luna high/xhigh or Sol/Terra high depending on availability.
- `creation`: reasoning is never low; minimum high, normally xhigh/max.
- `hard` and `deep_memory`: prefer `gpt-6-astra` with `ultra` exactly.
- `hard_creation`: prefer `gpt-6-astra` with `ultra`.
- A usage/rate-limit failure on a real task marks only that model temporarily unavailable; the same task is retried on the next eligible model.

## Usage awareness
No quota-probing calls are allowed. Availability is learned only from normal task executions. If Codex returns a reset timestamp, persist it; otherwise use a bounded cooldown. A successful invocation clears stale cooldown state for that model.

## Context control
Each numbered task runs in a fresh `codex exec` context. The prompt contains only the task, compact global Demo-01 goal, directly relevant current state, and checkpoint contract. Hard/deep-memory tasks may expand context progressively and use Astra Ultra.

## Persistence
Queue definition and progress are durable files under `/root/biella/work/<run-id>/`. Runtime logs and locks live under `/mnt/biella-extra/biella-runtime/codex-feeder/<run-id>/`. Source code remains in the Engine repo.

## Interface
`biella-codex` remains the only public controller. It gains an internal `feed` subcommand: `biella-codex feed run|status|stop ...`. No model-specific launcher is created.

## Demo-01 start
The first run is a compact 50-task Demo-01 queue. Tasks are classified by difficulty/creation/deep-memory needs. The feeder runs automatically until all tasks are complete or an actual external/owner-level dependency is observed.
