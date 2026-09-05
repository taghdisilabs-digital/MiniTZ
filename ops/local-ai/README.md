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

Runtime telemetry under `/mnt/biella-extra/biella-runtime/codex-production/` contains only liveness, current attempt/model/PIDs, cooldowns, last result, and heartbeat. It is not a completion ledger.

`production start` reconstructs the earliest unfinished canonical task, resumes any existing in-flight task bytes, executes one bounded writer at a time, refreshes heartbeat during long Codex attempts, validates structured evidence, retries publication until durable, advances 03/04 plus Project state, and continues automatically. Empty later sections are planned/audited just-in-time inside the same Project `PRODUCTION.md`. There is no separate active queue, batch ledger, model-specific project memory, or mutable progress authority.
