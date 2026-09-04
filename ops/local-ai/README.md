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
biella-codex feed init
biella-codex feed sync
biella-codex feed status
biella-codex feed start
biella-codex feed stop
```

The feeder has one active durable production document:

```text
/root/biella/work/games-production.json
```

That document contains Demo 01 plus Stage 2 through Stage 8 as sections, with task completion/evidence stored in the section itself. There is no separate active queue, state file, batch ledger, or model-specific project memory.

While another controller owns Demo 01, the feeder can stay active in `WAITING_DEMO_HANDOFF`. It only syncs current Demo completion and performs no Demo task or Unreal launch. When Demo 01 is complete, the same service automatically continues into Stage 2.
