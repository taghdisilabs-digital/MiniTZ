# MiniTZ unified main-coder runtime

`minitz-codex` remains the compatibility/operator entrypoint for the single MiniTZ production controller. Codex is the canonical writer; configured MiniTZ peer/resource routes may provide bounded non-authoritative assistance using the same Task Program, memory, cache, policy, and resource environment.

## Install

From the canonical Engine checkout as root:

```bash
bash ops/local-ai/install-minitz-ai.sh
```

Normal interactive use starts from `/root`:

```bash
minitz-codex
```

Mahdi owns main-coder usage policy. The controller chooses Codex or AGR by task fit and observed availability, while continuing to use local Qwen/Ollama, L40S GPU, Unreal, GitHub, Drive, Cloudflare, Saturn, Modal, configured APIs, shell/build tools, and other project resources when useful.

## 30-Commander Assist Fabric

`minitz_commander_fabric.py` defines 30 stable read-only Commander lanes (`CMD-01`..`CMD-30`). The production runner launches missing content-addressed lane work without waiting, writes durable non-authoritative leases/results under `memory/commander-fabric/`, and gives the canonical writer only the current fabric index path. Commander work cannot mutate task state, completion, Git, Drive, or publication. Local Qwen remains reserved for the writer by default; external `llm.fast` Resources back Commander lanes when usable. Existing TaskBoosters remain separate.

## Progressive Auto Feeder

The Auto Feeder is the progressive production section of the same controller:

```bash
minitz-codex production sync
minitz-codex production status
minitz-codex production start
```

Durable execution state is:

```text
/root/attached-storage/minitz-os-sandbox/workspace/repo/docs/project-state/03_MINITZ_CURRENT_STATE.md
/root/attached-storage/minitz-os-sandbox/workspace/repo/docs/project-state/04_MINITZ_ACTIVE_TASK.md
/root/attached-storage/minitz-os-sandbox/workspace/repo/projects/minitz-games/docs/PRODUCTION.md
```

Runtime telemetry under `/root/attached-storage/minitz-os-sandbox/state/production/` contains liveness, current task/attempt, active coder/model, four-state coder availability, backend-scoped native session references, bounded diagnostics, cooldowns, last result, and heartbeat. It is not a completion ledger or memory authority.

`production start` reconstructs the earliest unfinished canonical task, resumes existing in-flight task bytes from shared MiniTZ continuity, executes one bounded canonical writer at a time through Codex or AGR, may use the other ACTIVE coder as a non-blocking read-only peer, refreshes heartbeat during long attempts, validates structured evidence, retries publication independently, advances canonical Project state, and continues automatically. Empty later sections are planned/audited just-in-time inside the same Project `PRODUCTION.md`. There is no separate active queue, batch ledger, model-specific project memory, or mutable progress authority.

## Game-first production priority
MINITZ_OS_ONLY is the current owner priority: the living MiniTZ Task Program is the sole task/order/status authority; game/website/end-user-edition material is provenance only unless migrated into an OS capability task.
