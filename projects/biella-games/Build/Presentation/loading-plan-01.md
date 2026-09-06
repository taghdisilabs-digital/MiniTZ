# D03-01 bounded startup presentation increment

Current input: committed PSO scheduling comparison `7a2634de84d7ed783eebff62b262103c7a50db32`. Neither scheduler improved the measured startup wait. Preserve the default scheduler and disabled experimental file cache.

Implement a project Runtime module at Unreal's `PreLoadingScreen` phase, using `FPreLoadScreenBase` and Slate without loading game assets. Show Biella / Preparing your world with indeterminate motion, not invented completion percentages. Finish after engine loading and currently active native pipeline precompiles have completed, or when engine exit is requested. The screen does not assert that later gameplay cannot create new pipelines.

Use the manager's supported threaded loading lifecycle. Build widgets before registration; retain them until manager cleanup. Record render tick timestamps on the render thread, serialize after the manager joins it, and avoid game-thread mutation of Slate attributes. Optional telemetry must not define loading correctness.

Validation: incremental native Linux build; isolated native runtime with startup screen, subsequent existing surface/gameplay assertions, fresh and reused user caches; `-NoLoadingScreen` negative control; supported SM5 fallback. Capture the actual X11 display independently of render callback telemetry and inspect decoded frames. Any loader stall or lifecycle failure must be retained and repaired at the demonstrated boundary. No claim of improved startup latency without comparable measurements.

Retain exact source, descriptor, binary and package/candidate lineage. Reuse unchanged cooked content only after exact byte checks; a binary-overlay runtime candidate is not a newly qualified full cook. Keep prior evidence immutable. Persist results and locally commit the validated bounded increment; D03-01 remains open for remaining production presentation work. Auto Feeder owns remote publication and canonical task transition.
