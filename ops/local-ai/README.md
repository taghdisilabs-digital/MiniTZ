# Biella unified Codex runtime

`biella-codex` is the single AI/production controller entrypoint on the Biella workstation. All Codex models use `/root/.codex`, the same project authority, the same configured API environment, and the same workstation resources.

## Install

From the canonical Engine checkout as root:

```bash
bash ops/local-ai/install-biella-ai.sh
```

Normal interactive use starts from `/root`:

```bash
biella-codex
```

Mahdi chooses Codex model/usage. After launch, Codex decides when to use local Qwen/Ollama, L40S GPU, Unreal, GitHub, Drive, Cloudflare, Saturn, Modal, configured APIs, shell/build tools, and other project resources.

## Games production feeder

The feeder is an internal section of the same controller:

```bash
biella-codex feed sync
biella-codex feed status
biella-codex feed start
biella-codex feed stop
```

Its one durable production source is:

```text
/root/biella/repos/biella-engine/projects/biella-games/docs/PRODUCTION.md
```

That Project file contains Demo 01 plus Stage 2 through Stage 8, with task completion/evidence stored in each section. Feeder runtime state under `/mnt/biella-extra/biella-runtime/codex-feeder/biella-games-production/` is telemetry only and contains no durable completion ledger.

`feed start` resumes the earliest unfinished task from the canonical Project source. `feed stop` stops execution without changing completed Project work. There is no separate active queue, batch ledger, model-specific project memory, or `games-production.json` authority.
