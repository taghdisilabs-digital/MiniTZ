# D01-44 — Native performance and resource measurement

The current Demo 01 produced reproducible native development-host frame/resource evidence at 1280×720 and 1920×1080, including a fresh-process 720p repeat. All three 120-second measurements passed capture, workload, process-identity and evidence-integrity validation: 23,153 measured frames over 360.023 wall seconds. These are measurements of the current playable content, with no accepted FPS, memory or hardware budget inferred.

Source baseline: `eb629ef0023aba37062bf1f7528587191ecf95c5`. Each run's `validation.json` preserves the exact tested source, configuration, content, Unreal executable and game-module binary hashes before and after execution; the baseline commit precedes the task's editable instrumentation. All three measurements use the same tested bytes.

## Measured results

All frame statistics below include every interval in the measurement window, including active play, terminal screens and map restart. FPS is native engine-frame count divided by measured wall time. Percentiles use linear interpolation at `(n−1) × p/100`. The 50 ms hitch threshold is a reporting bin, not an approved performance budget.

| Run | Measured seconds | Frames | Native engine FPS | p50 ms | p95 ms | p99 ms | Maximum ms | Frames >50 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 720p A | 120.013 | 8,410 | 70.08 | 14.10 | 16.58 | 18.82 | 104.42 | 25 |
| 1080p | 120.002 | 6,013 | 50.11 | 19.67 | 23.55 | 25.89 | 96.39 | 25 |
| 720p B | 120.008 | 8,730 | 72.75 | 13.77 | 16.19 | 18.34 | 96.73 | 26 |

The 720p repeats differ by 3.74% of their pair mean FPS, showing observed run-to-run variation without implying statistical confidence or an optimization between runs.

| Run | Game-thread mean ms | Render-thread mean ms | RHI-thread mean ms | GPU mean ms | Process CPU mean¹ | Device GPU utilization mean |
|---|---:|---:|---:|---:|---:|---:|
| 720p A | 3.78 | 13.35 | 2.41 | 4.93 | 338.37% | 36.04% |
| 1080p | 4.10 | 19.01 | 1.94 | 6.74 | 275.56% | 35.96% |
| 720p B | 3.75 | 12.85 | 2.30 | 4.67 | 344.41% | 35.78% |

¹ Process CPU 100% represents one logical core; it includes the Unreal process's threads. Engine thread/GPU counters are the latest completed asynchronous timings. They are not aligned stage durations for a single row and must not be added together or inverted into FPS. Utilization, power, temperature and clocks from NVIDIA's device telemetry describe the whole GPU; VRAM below is attributed to the exact Unreal graphics PID.

| Run | OS samples | Maximum sampled RSS MiB | First → last RSS window mean MiB² | RSS window delta MiB | Maximum sampled Unreal-PID VRAM MiB |
|---|---:|---:|---:|---:|---:|
| 720p A | 113 | 2,840.02 | 2,803.62 → 2,835.93 | +32.31 | 1,973 |
| 1080p | 113 | 2,867.62 | 2,860.73 → 2,856.83 | −3.90 | 2,415 |
| 720p B | 113 | 2,849.55 | 2,831.50 → 2,846.06 | +14.56 | 2,017 |

² Each window contains the first or last 10 in-window OS samples, approximately 10 seconds. These are sampled maxima, not guaranteed subsecond peaks. The separate `rss_hwm_mib` field in raw reports is the process-lifetime high-water mark observed during the window and can include startup/warmup.

## Findings and remaining limits

The strongest current bottleneck inference is CPU-side render-thread/presentation work on this host: the render timer is close to observed frame time and materially exceeds GPU work, while whole-device utilization averages about 36%. At 1080p both frame time and GPU time increase. This does not isolate a particular renderer pass, driver wait, compositor operation or scheduling cause; a CPU/GPU trace would be required for that diagnosis. The very small recorded swap timer also does not measure physical display latency.

Restart-related hitches remain visible. The runs contain 25, 25 and 26 measured intervals above 50 ms respectively, all ending within 0.20 seconds of a recorded restart request. Some reload intervals finish in an `active` state, so the report also identifies overlapping transition intervals and preserves preceding phase/cycle context. The maximum measured stalls are 104.42 ms across the 720p runs and 96.39 ms at 1080p. These are unresolved runtime costs, not trimmed outliers or an optimization claim. Raw warmup and post-measurement capture intervals retain screenshot/readback stalls separately.

The measured RSS window change differs across the runs. Caches, editor overhead, allocator behavior and the growing buffered frame capture all contribute; these observations neither identify a gameplay leak nor prove leak freedom. All runs record zero process swap and zero major page-fault increments during sampled measurement coverage. There is no approved RAM/VRAM budget, and this short, small-content experiment does not qualify long-term memory growth, full-world streaming pressure or worst-case residency.

The workload uses the existing authored four-pawn encounter with real Enhanced Input movement, camera rotation and fire, autonomous AI, collision-resolved combat, damage, objective/terminal transitions and the real map-restart API. It does not freeze AI, teleport participants, restore health or fabricate successful hits. The measured windows corroborate 70/69/70 player shots and 160/161/159 positive damage events for 720p A/1080p/720p B respectively. Per-frame positions, autonomous-pawn counts, health, ammo, pressure and audio/VFX component counts remain in the CSV; gameplay events remain in JSONL. This covers the current small playable scene, not full-scale content, pressure-reinforcement bursts, production visual quality or every gameplay state.

## Configuration and method

The host reports AMD EPYC 9124, 15 available logical CPUs, 88,380.38 MiB system RAM, NVIDIA L40S and driver `580.178.04`. Exact GPU UUID, CPU affinity, cgroup limits, device capacity and per-run process start identity are retained in each validation report. No competing graphics process was observed in the completed measurement windows.

Unreal Engine 5.8.2 runs the editable Development Editor target in `-game` mode, with Vulkan, an Xvfb window, and the authored `BiellaGameplayMap`. Effective beginning/end settings verify variable real-time timestep, no benchmarking, frame smoothing/fixed-framerate controls disabled for this experiment, `t.MaxFPS=0`, `r.VSync=0`, `r.ScreenPercentage=100` and dynamic resolution disabled. Recorded scalability groups are 3; TSR is enabled (`r.AntiAliasingMethod=4`, history screen percentage 200), with Nanite, Lumen GI/reflections and virtual shadow maps enabled and hardware ray tracing disabled. Exact effective cvars are preserved, rather than inferring them from launch flags. No frame-generation plugin is enabled in the captured project configuration; the queried optional generation controls are unavailable.

`OnEndFrame` records native engine-frame cadence against `FPlatformTime::Seconds`, with actual `GFrameCounter`, separate engine simulation delta, and engine game/render/RHI/GPU timers. The measurement begins on a recorded frame boundary after the requested 10-second warmup and ends after at least 120 wall seconds. Frame rows stay buffered in memory until measurement/captures finish; their allocation/formatting cost and ordinary synchronous gameplay telemetry overhead remain in the result. Initial and final PNG captures occur outside the measurement window, with final capture requested during active play.

An external approximately 1 Hz `/proc` and `nvidia-smi` monitor records process CPU/RSS/faults/I/O, exact graphics-process VRAM and whole-device measurements. It joins samples using Unreal's selected Linux clock ID and validates coverage, timestamp progress, PID/start-time continuity and GPU identity. The external sampling operation averages about 0.16 seconds per sample in all runs; this instrumentation is part of the observed host conditions. RAM/VRAM are not decomposed by asset/pass, and individual streaming/PSO/compiler stalls are not fully attributed by these aggregate timers and logs.

Audio uses the real Unreal software `NonRealtimeAudioRenderer`/mixer through `-DeterministicAudio`. Xvfb and software audio do not measure physical display scanout, speaker delivery or end-to-end input latency. These Linux/Vulkan results are not packaged Windows/DX12 qualification, an accepted shipping tier, a stability-soak replacement, a leak-free result or a full-content performance guarantee. Target hardware, resolution/FPS and percentile/memory budgets remain `UNKNOWN` in the accepted technical decisions.

## Editable outputs and evidence

- [Native runtime automation](../../Source/BiellaGames/Private/Tests/BiellaNativePerformanceTest.cpp), [module dependencies](../../Source/BiellaGames/BiellaGames.Build.cs), [runner and OS monitor](../../tests/run_d01_044.py), [capture verifier](../../tests/verify_d01_044.py), [frame/verifier tests](../../tests/test_d01_044.py), [resource tests](../../tests/test_d01_044_resources.py), [retained-evidence replay and summary](../../tests/summarize_d01_044.py).
- [720p A validation](D01-044-runs/20260905T095159.349031Z-1280x720/validation.json), [1080p validation](D01-044-runs/20260905T095503.680759Z-1920x1080/validation.json) and [720p B validation](D01-044-runs/20260905T095830.179104Z-1280x720/validation.json). Each run retains `frames.csv`, `perf.json`, `resources.jsonl`, gameplay telemetry, complete engine/stdout logs and decoded capture identities. [Aggregate evidence](D01-044-validation.json) is produced by replaying raw measurements, current-source and retained-evidence hashes, clocks, PID/start identities and protected metadata.
- Visual candidates remain `GENERATED_DRAFT` in `/root/biella/artifacts/games/D01-044/<run-id>/`. Portable repository evidence copies reside in each run's `captures/` directory; the images are evidence of the actual viewport, not visual/product acceptance.
- [Editor build](D01-044-editor-build.log): succeeded. [Adversarial validation](D01-044-verifier-tests-final.log): all 40 tests passed. [Predecessor regression](D01-044-predecessor-regression.log): two fresh-process D01-39 playtests passed; their [validation](D01-044-predecessor-regression/20260905T094604.366002Z-nullrhi-3fe5b7e7/validation.json) preserves exact evidence. The earlier [30-second smoke](D01-044-runs/20260905T094646.479673Z-1280x720/validation.json) remains `SMOKE_ONLY`.

The exact predecessor warning signatures remain disclosed in the validation reports: editor widget registration, obsolete authored navigation registration/crowd initialization, the motion-vector cvar warning and Vulkan shutdown's one-unfreed-allocation warning. No new warning signature, runtime error, crash, ensure or device-loss event was accepted. Retaining these known signatures does not establish warning-free runtime or leak freedom.

## Reproduction and task boundary

From `projects/biella-games`, after building the current Editor target, run sequentially:

```bash
python tests/run_d01_044.py --seconds 120 --warmup 10 --width 1280
python tests/run_d01_044.py --seconds 120 --warmup 10 --width 1920
python tests/run_d01_044.py --seconds 120 --warmup 10 --width 1280
python -m unittest discover -s tests -p 'test_d01_044*.py' -v
```

Each invocation creates a fresh run and inspector directory and retains failed attempts. The summary can be regenerated with `python tests/summarize_d01_044.py <720p-A-run-directory> <1080p-run-directory> <720p-B-run-directory>` using the exact directories linked above. Validation distinguishes capture correctness from performance-budget acceptance. [Preservation evidence](D01-044-preservation.json) records unchanged 03/04 and Project `PRODUCTION.md` bytes; run reports independently verify protected hashes before/after execution. Completed predecessors and Engine P4-06's `INCOMPLETE_DEFERRED` state are preserved. This task supplies local editable implementation and evidence only; the Auto Feeder owns publication and canonical status/next-task transition. No later task was executed.
