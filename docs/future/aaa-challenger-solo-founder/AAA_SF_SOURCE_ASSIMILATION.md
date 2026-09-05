# AAA-SF Source Assimilation — 2026-09-05

Status: `REFERENCE_INPUTS_BOUND_TO_CURRENT_AUTHORITY_AT_ACTIVATION`
Purpose: record newly discovered evidence that changes how the future AAA-SF program should execute, without turning snapshots or historical material into a second authority.

## 1. Current live Engine execution-map contract

Current Engine source added `docs/superpowers/specs/2026-09-05-biella-ai-production-map-task-contract-design.md` at commit `8fdfdf5c01b8ff07378422b284eb7f87380a4cc2`.

The important reusable execution facts are:

- use one public AI/production controller; observed current controller is `biella-codex`;
- do not create another Games queue/state authority; observed current Games feeder authority is `/root/biella/work/games-production.json`;
- compile work into a compact ordered task packet: `id, objective, authority, read, write, preserve, must, must_not, dependencies, resources, acceptance, validate, persist, stop`;
- load minimum context first and expand only for a named unresolved fact;
- record a `context_receipt` containing project/task/source identities, authority refs, files loaded, expansion reasons, and timestamp;
- match completion to real task-derived evidence and remote readback where publication occurs;
- recover the smallest invalidated boundary and preserve verified outputs;
- measure context efficiency, retries, reuse, validation failures, routing outcomes, duration, and completion quality.

These are execution-shape inputs. They do not change Biella Games product canon or replace any then-current accepted Engine interface.

## 2. Current coordination snapshot — informational only

At the Engine design observation, the Games feeder was `WAITING_DEMO_HANDOFF`, Demo 01 was `10/50` complete, and the active Demo task was `D01-011`.

This snapshot is not an AAA-SF activation dependency. `AAA-SF-001` must reobserve the real predecessor set when the future program activates.

The Engine numbered frontier and the Games production-controller frontier are distinct authorities and must not be merged into a synthetic state.

## 3. Older August state files

The supplied 2026-08-27 `03_BIELLA_CURRENT_STATE.md`, `04_BIELLA_ACTIVE_TASK.md`, and migration plan contain useful architecture/operating semantics but their execution-state values are older than the current September source.

Use stable semantics such as authority ordering, reuse/invalidation, durability, Engine/Project separation, migration firewall, and task-derived evidence. Do not use their historical P0-01/host/commit values to reset current execution.

## 4. Normalized historical intelligence already available

A completed mounted-corpus migration batch recorded 545 exact files and emitted 13 brand-free reusable candidates after classification/normalization. A separate transfer-target cleanup retained 10 productive candidates including production tools, Playwright specialist patterns, asset-license/rights records, creation/execution-intelligence pipelines, source code, and skills.

AAA-SF may use these only if, at activation, the relevant candidate has been admitted into current accepted Biella Engine or Project source through the migration firewall. Raw historical material never becomes task authority and AAA-SF must not re-mine the legacy corpus merely because these candidates exist.

## 5. Investor proof ladder already defined

The investor underwriting material defines six value-unlock proofs that AAA-SF should close with real evidence:

1. fresh objective -> execution -> validation -> persistence -> continuation;
2. external pilot replication;
3. cross-model/provider continuity;
4. durable recovery from interruption;
5. contracted or paid usage;
6. repeatable deployment without founder-by-founder reconstruction.

AAA-SF task mapping:

- live objective-to-outcome: `AAA-SF-068..069`;
- external replication: `AAA-SF-053..060`;
- cross-model continuity: `AAA-SF-051`;
- durable recovery: `AAA-SF-050` and external recovery `AAA-SF-058`;
- contracted/paid usage: `AAA-SF-065..066`;
- repeatable deployment: `AAA-SF-054..060`.

## 6. Non-drift rule

This file is a source map, not a queue, state ledger, memory system, or acceptance authority. Exact source identity is re-bound at the active task boundary. If current Engine source supersedes any observation above, use the newer accepted source and update only the affected task premise.
