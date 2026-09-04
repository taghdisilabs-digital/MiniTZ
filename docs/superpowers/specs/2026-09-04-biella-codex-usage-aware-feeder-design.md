# Biella Codex Usage-Aware Feeder Design

## Goal
Keep `biella-codex` as the only AI/production entrypoint and run Games production from one durable sectioned document until the accepted game completion sequence is satisfied.

## One production state
The only active feeder authority is `/root/biella/work/games-production.json`. It contains run state, ordered sections, tasks, task completion/evidence, current section/task, model cooldowns, and the latest result. Do not create separate queue, state, batch, or progress-ledger files. Runtime attempt logs and the single-flight lock remain non-authoritative runtime evidence under `/mnt/biella-extra/biella-runtime/codex-feeder/`.

## Sections and continuation
`demo01` is the first section and imports current progress from `docs/DEMO_01_QUEUE.md` without downgrading already completed tasks. Stage 2 through Stage 8 are taken from current `docs/IMPLEMENTATION_SEQUENCE.md`. Empty stages are planned just-in-time into the same section with 20-50 bounded, non-overlapping tasks unless materially fewer are required. After each section executes, the same section is audited; only missing work is appended. Completion advances to the next section. Stage 8 audit is the game/release-candidate completion boundary.

## Routing
- `simple`: prefer Luna medium; observed usage/rate-limit failures fall back without quota probing.
- `medium`: prefer Luna high, then eligible alternatives.
- `creation`: never below high; normally xhigh/max.
- `hard`, `deep_memory`, `hard_creation`: Astra Ultra first.
- Section planning/audit is deep-memory work and therefore Astra Ultra first.

## Usage and context
The feeder never invokes `/usage`, redeems resets, or changes account quota. Availability is learned only from normal task results and local model catalog metadata. Each task runs in a fresh bounded context containing only its section/task and directly relevant current authority. Completed work is preserved unless current authoritative evidence materially invalidates it.

## Interface
`biella-codex` remains the only public controller. Internal feeder actions are `biella-codex feed init|sync|run|start|status|stop`. They operate on the single canonical production document; no queue path is passed around.

## Ownership
One feeder task runs at a time. While another controller owns Demo 01, the feeder remains in `WAITING_DEMO_HANDOFF`, performs only read/sync of Demo progress, and executes no Demo task or Unreal launch. Once all 50 Demo tasks are complete, the same service automatically advances into Stage 2.
