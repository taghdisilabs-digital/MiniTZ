# MiniTZ unified main-coder runtime

`biella-codex` remains the compatibility/operator entrypoint for the single MiniTZ production controller. Codex and Antigravity/AGR are peer main-coder execution backends beneath that controller. Both use the same canonical Task Program, project authority, MiniTZ task memory/projection/cache/evidence, AGENTS policy, configured resource environment, and workstation resources; provider-native session/cache state remains backend-specific.

## Install

From the canonical Engine checkout as root:

```bash
bash ops/local-ai/install-biella-ai.sh
```

Normal interactive use starts from `/root`:

```bash
biella-codex
```

Mahdi owns main-coder usage policy. The controller chooses Codex or AGR by task fit and observed availability, while continuing to use local Qwen/Ollama, L40S GPU, Unreal, GitHub, Drive, Cloudflare, Saturn, Modal, configured APIs, shell/build tools, and other project resources when useful.

## Progressive Auto Feeder

The Auto Feeder is the progressive production section of the same controller:

```bash
biella-codex production sync
biella-codex production status
biella-codex production start
```

Durable execution state is:

```text
/root/biella/repos/biella-engine/docs/project-state/03_BIELLA_CURRENT_STATE.md
/root/biella/repos/biella-engine/docs/project-state/04_BIELLA_ACTIVE_TASK.md
/root/biella/repos/biella-engine/projects/biella-games/docs/PRODUCTION.md
```

Runtime telemetry under `/mnt/biella-extra/biella-runtime/codex-production/` contains liveness, current task/attempt, active coder/model, four-state coder availability, backend-scoped native session references, bounded diagnostics, cooldowns, last result, and heartbeat. It is not a completion ledger or memory authority.

`production start` reconstructs the earliest unfinished canonical task, resumes existing in-flight task bytes from shared MiniTZ continuity, executes one bounded canonical writer at a time through Codex or AGR, may use the other ACTIVE coder as a non-blocking read-only peer, refreshes heartbeat during long attempts, validates structured evidence, retries publication independently, advances canonical Project state, and continues automatically. Empty later sections are planned/audited just-in-time inside the same Project `PRODUCTION.md`. There is no separate active queue, batch ledger, model-specific project memory, or mutable progress authority.

## Game-first production priority
GAME_FIRST is the current owner priority: Biella Games delivery NUMBER 1. The runner reads the physical Project PRODUCTION.md order; existing task-class routing, preserved sessions and independent publication remain active. Do not sort work by numeric task IDs, create another feeder, or require unrelated website/business tasks before game work.
