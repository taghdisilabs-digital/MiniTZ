# Reconstruction launch profiles

D03-01 adds version 1 launch profiles to the existing playable world. Both retain the project's Deferred, Nanite, Lumen and virtual-shadow-map baseline. They select the temporal reconstruction method at game-instance initialization.

| Launch argument | AA | Screen percentage | Temporal upsampling | Dynamic resolution |
| --- | --- | --- | --- | --- |
| `-BiellaRenderProfile=ProductionTSR` | TSR | 100 | Enabled | Disabled |
| `-BiellaRenderProfile=NativeTAA` | TAA | 100 | Disabled | Disabled |

Without the argument, supported project defaults remain in effect. Unreal's installed `SupportsTSR` capability check selects NativeTAA when the requested/default TSR path is unavailable. An unrecognized explicit profile also selects NativeTAA and emits `D03_RENDER_PROFILE_INVALID`. The `D03_RENDER_PROFILE version=1` diagnostic records the requested and selected profile plus effective AA and resolution cvars at initialization. Later explicit console commands retain Unreal's normal higher priority.

The optional `-BiellaRenderReadback=/absolute/path/native-views.csv` records constructed game-thread views belonging to this game instance and writes them when the instance shuts down. Records contain actual view AA, requested renderer cvars, capability/upscaler state, dimensions and `GFrameCounter`. Loading can produce several view families in one frame. The independent verifier retains all matching primary views when joining scenario frame IDs; it does not infer a rendered path from the profile name alone.

Run the existing world-surface or environment gameplay scenario through either profile:

```sh
python3 tests/run_d03_01_reconstruction.py --profile ProductionTSR --output Build/Presentation/reconstruction-tsr-fresh
python3 tests/run_d03_01_reconstruction.py --profile NativeTAA --output Build/Presentation/reconstruction-taa-fresh
python3 tests/run_d03_01_reconstruction.py --profile NativeTAA --scenario environment --output Build/Presentation/reconstruction-environment-fresh
```

Each output directory must be new. The runner saves exact source, module, content, configuration and verifier identities before/after execution, the launch command, closed raw logs, native frame and view CSVs, captures and an independently replayed validation report. `--profile InvalidFixture` tests the unknown-profile fallback. `--override-fxaa` deliberately overrides AA through the console and must fail reconstruction validation.

Qualification is bounded to the recorded Linux Vulkan Development build at 1280×720 on the observed L40S workstation, with existing development caches. Hardware reporting TSR unavailable has not been exercised. These profiles do not qualify a lower-feature renderer, another GPU/platform, cold shader/PSO launch, packaged play, generated frames or final production art. Surface cost windows exclude screenshot requests; reported native timings still include the opt-in view observer and this development environment.

See `Build/Presentation/D03-01-reconstruction-progress.md` for exact evidence and remaining D03 work.
