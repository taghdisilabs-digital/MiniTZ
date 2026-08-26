# Prompt 03 — Resource Adaptation and NVIDIA Implementation Map

## Objective

Make Biella adapt to real hardware without turning one machine, GPU vendor, cloud, or runtime into architecture. **Hardware is runtime state, not Capability identity.**

## Generic Resource observation

Represent identity, architecture/vendor/runtime, configured CPU/RAM/GPU/VRAM/storage/network and quotas, observed CPU/RAM/GPU/VRAM/disk/network/tool availability, locality (model/KV/toolchain/artifact/workspace/container/cache), health/freshness, and cost when observed. Configured capacity must not be presented as measured capacity.

## Resource-fit outcomes

`FIT`, `FIT_REDUCED`, `REQUIRES_OTHER_RESOURCE`, `TEMP_UNAVAILABLE`, `UNKNOWN`.

A missing GPU may make a GPU implementation `REQUIRES_OTHER_RESOURCE`; the semantic capability still exists.

## Current clean-host observation

Verified current Biella/Codex host: AWS `c5a.4xlarge`, 16 logical CPUs, 30 GiB RAM, 350 GiB EBS root, 64 GiB persistent swap. No NVIDIA software stack was installed as part of the CPU-host baseline. This is one Resource observation, not Biella's definition.

## Scheduler behavior

For each ready Node: filter implementations by capability/hard requirements; inspect current Resources; reject non-fit Resources; consider health/free capacity/queue/locality/latency/cost; reuse warm/local state only when identity is correct; execute independent work concurrently; route/provision another Resource when necessary; never delete a capability because one host is weak/unavailable.

Do not force artificial 100% utilization, but do not leave expensive available compute idle when ready useful work exists.

## NVIDIA research snapshot — 2026-08-26

NVIDIA technologies are implementation options, not Biella kernel owners.

### NVIDIA Dynamo

Current NVIDIA Dynamo documentation describes an open-source inference framework supporting multiple inference engines and deployment modes. Transferable ideas: live worker discovery, load-aware and KV-cache-aware routing, cache locality, independently scalable prefill/decode pools, topology awareness, and benchmark-driven deployment choice.

References:
- https://docs.nvidia.com/dynamo/
- https://docs.nvidia.com/dynamo/cli/kv-aware-routing/overview
- https://docs.nvidia.com/dynamo/cli/disaggregated-serving/overview

### Disaggregated inference

Prefill and decode have different compute/memory characteristics. Disaggregation may improve some sustained workloads but is not universally better. Biella should select topology from measured workload/resource evidence, not a universal threshold.

### Triton batching

Triton supports dynamic batching for stateless models and sequence batching for stateful workloads. Batching is a runtime optimization; measure latency/throughput and keep Task semantics independent of batch size.

Reference:
- https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/batcher.html

### DCGM / GPU telemetry

Useful GPU signals include utilization, framebuffer memory total/free/used, power, temperature, clocks, encoder/decoder utilization, ECC/error/XID signals and diagnostics. Map them into generic Resource fields plus optional vendor metadata.

References:
- https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/perf_analyzer/genai-perf/docs/gpu_telemetry.html
- https://docs.nvidia.com/aiperf/tutorials/metrics-analysis/gpu-telemetry-with-ai-perf

On non-NVIDIA/CPU hosts, use host-native telemetry. Missing DCGM is not a blocker.

## No GPU-installation drift

Do not install NVIDIA drivers/CUDA/DCGM on a CPU-only Resource to make documentation look complete. When a real NVIDIA GPU Resource appears, inspect actual GPU/driver/runtime, install only the matching required stack on that Resource, record telemetry, and register it dynamically.

## Execution prompt

> Observe the current hardware/runtime as Resource state. Do not inherit historical GPU/cloud assumptions. For every capability required by the current Task, determine whether the present Resource is FIT, FIT_REDUCED, REQUIRES_OTHER_RESOURCE, TEMP_UNAVAILABLE, or UNKNOWN. Route work accordingly. Treat NVIDIA Dynamo/Triton/DCGM as replaceable implementation/telemetry options. Use cache/locality/load signals when measured. Never remove a semantic capability because one Resource is unavailable.
