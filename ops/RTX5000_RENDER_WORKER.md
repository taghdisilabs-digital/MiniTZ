# Biella RTX5000 Render Worker Runbook

This runbook records the verified controller/worker boundary established on 2026-09-02 for Biella visual production.

It is operational recovery documentation. It does **not** make the render worker a second Biella authority, scheduler, source-of-truth repository, or autonomous write agent.

## Roles

### L40S controller

Current controller identity:

- Hostname: `biella-l40s-worker`
- Public IP: `152.228.213.182`
- Last observed SSH user: `ubuntu`
- Root shell after login: `sudo -i`
- Active Biella workspace: `/root/spark-biella-games`

The L40S controller owns:

- current Biella source/state;
- task authority;
- dependency decisions;
- render-job preparation;
- artifact acceptance/validation;
- final persistence and integration.

The controller may use the RTX5000 only as a replaceable `Resource` for production work.

### RTX5000 render worker

Verified worker identity:

- Hostname: `rtx5000-28-2026-09-02-19-52`
- Public IP: `57.128.59.229`
- Private IP observed: `10.1.1.232`
- SSH user: `ubuntu`
- GPU: `Quadro RTX 5000`
- GPU memory: `15,360 MiB`
- RAM observed after bootstrap: `26 GiB`
- Root filesystem observed after bootstrap: `387G` total, about `370G` available
- OS image: Ubuntu 26.04 NVIDIA image, provider NVIDIA 595 branch
- Blender: official `Blender 5.2.1 LTS`
- Blender executable: `/usr/local/bin/blender`
- Accepted render backend: `CUDA`

Verified production root:

```text
/opt/biella-render/
  jobs/
  outputs/
  scenes/
  assets/
  cache/
  logs/
```

Verified smoke-render artifact:

```text
/opt/biella-render/outputs/rtx5000_cuda_smoke.png
```

The bootstrap completed with:

```text
MINITZ_RTX5000_RENDER_WORKER_READY=YES
BACKEND_REQUIRED=CUDA
NO_REBOOT_PERFORMED=YES
PROVIDER_NVIDIA_STACK_PRESERVED=YES
```

## Authority boundary

The worker has **no project authority**.

It may perform jobs such as:

- Blender headless rendering;
- beauty/normal/depth passes;
- texture/material baking;
- environment/character preview rendering;
- asset processing;
- other task-scoped GPU visual-production work that fits its resources.

It must not:

- become a second source-writing agent against the active Biella workspace;
- own project/task state;
- decide canon or acceptance;
- maintain a competing Git checkout as project authority;
- introduce a second scheduler, memory system, validation framework, or production authority;
- modify the provider NVIDIA stack merely to chase optional OptiX support when verified CUDA rendering is sufficient.

The normal data flow is:

```text
L40S current task/source
-> prepare task-scoped render job
-> transfer only required scene/assets/job inputs
-> RTX5000 renders/processes with Blender CUDA
-> return artifacts + logs
-> L40S validates and integrates outputs
-> authoritative project state remains on L40S/current source
```

## SSH material

The private key is intentionally **not stored in GitHub**.

Current key path on the L40S controller:

```text
/root/.ssh/biella-render.pem
```

Expected permissions:

```text
0600
```

Current readable local worker note on the L40S:

```text
/root/spark-biella-games/MINITZ_RENDER_WORKER_README.txt
```

Direct connection form from the L40S:

```bash
ssh -i /root/.ssh/biella-render.pem ubuntu@57.128.59.229
```

Root promotion on the worker was observed as:

```bash
sudo -i
```

Do not assume non-interactive root automation until it is separately verified. SSH transport itself is verified.

## Verified controller-to-worker health check

The L40S successfully executed this class of read-only check against the worker:

```bash
ssh \
  -o StrictHostKeyChecking=accept-new \
  -i /root/.ssh/biella-render.pem \
  ubuntu@57.128.59.229 \
  'hostname; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader; blender --version | head -1'
```

Observed result:

```text
rtx5000-28-2026-09-02-19-52
Quadro RTX 5000, 15360 MiB
Blender 5.2.1 LTS
```

## Bootstrap policy

The accepted worker bootstrap follows these constraints:

1. Wait for provider/cloud initialization and package-manager locks.
2. Verify `nvidia-smi` before installing anything.
3. Require the provider NVIDIA 595 branch; stop rather than silently replacing it.
4. Record provider NVIDIA package state.
5. Simulate base-package installation first and abort if the transaction would touch NVIDIA/CUDA packages.
6. Do **not** run `apt upgrade` as part of the render-worker bootstrap.
7. Do **not** install Ubuntu/DFSG Blender.
8. Install the official Blender Linux release directly under `/opt` and expose it via `/usr/local/bin/blender`.
9. Validate CUDA device enumeration.
10. Run a real CUDA Cycles smoke render and require a non-empty output artifact.
11. Treat OptiX as optional; CUDA is the accepted worker backend.
12. Do not reboot automatically.
13. Do not alter UVM/kernel/driver settings automatically after a failure; diagnose and stop instead.

The provider-supplied NVIDIA stack is considered a working input and must be preserved unless a separately observed active task proves it broken.

## Recovery procedure

After a worker replacement/reinstall:

1. Reobserve hostname/IP/user/GPU/driver.
2. Run the accepted worker bootstrap.
3. Require the real CUDA smoke-render artifact.
4. Reinstall/copy the SSH public-key authorization on the new worker as needed.
5. Keep the private key only on the controller/user-owned secure location; never commit it.
6. Run the controller-to-worker health check above.
7. Update this runbook only when observed worker identity or verified operating behavior changes.

A new VPS/session/image does not by itself change Biella architecture. The worker remains a replaceable production `Resource`.
