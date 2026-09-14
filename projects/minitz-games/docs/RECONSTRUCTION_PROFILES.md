# Reconstruction launch profiles

D03-01 adds version 1 launch profiles to the existing playable world. They select the temporal reconstruction method at game-instance initialization. Renderer settings retain the accepted Deferred, Nanite, Lumen and virtual-shadow-map baseline; actual feature availability also depends on the selected shader platform and hardware.

| Launch argument | AA | Screen percentage | Temporal upsampling | Dynamic resolution |
| --- | --- | --- | --- | --- |
| `-BiellaRenderProfile=ProductionTSR` | TSR | 100 | Enabled | Disabled |
| `-BiellaRenderProfile=NativeTAA` | TAA | 100 | Disabled | Disabled |

Without the argument, supported project defaults remain in effect. Unreal's installed `SupportsTSR` capability check selects NativeTAA when the requested/default TSR path is unavailable. An unrecognized explicit profile also selects NativeTAA and emits `D03_RENDER_PROFILE_INVALID`. The `D03_RENDER_PROFILE version=1` diagnostic records the requested and selected profile plus effective AA and resolution cvars at initialization. Later explicit console commands retain Unreal's normal higher priority.

The optional `-BiellaRenderReadback=/absolute/path/native-views.csv` records constructed game-thread views belonging to this game instance and writes them when the instance shuts down. Records contain actual view AA, requested renderer cvars, capability/upscaler state, dimensions and `GFrameCounter`. The added `feature_sm6`, `nanite_supported`, `nanite_enabled`, `vsm_enabled` and `lumen_supported` columns query the view's shader platform and Unreal renderer eligibility functions. These distinguish the requested `nanite`/`vsm` CVars from features available on that runtime. `D03_RENDER_CAPABILITIES` records the shader format. Loading can produce several view families in one frame. The independent verifier retains all matching primary views when joining scenario frame IDs; it does not infer a rendered path from the profile name alone.

Linux configuration targets SM6 in addition to the inherited SM5 fallback. Unreal tries the highest supported targeted Vulkan feature level first; `-sm5` explicitly selects the fallback. SM5 supports the temporal profiles and Lumen GI on this engine but does not support Nanite or VSM. The surface scenario also saves `render-primitives.csv`: one snapshot of loaded static meshes, their Nanite data and native scene-proxy type before measured phases. A loaded Nanite proxy does not prove visibility or final pixel contribution.

Run the existing world-surface or environment gameplay scenario through either profile:

```sh
python3 tests/run_d03_01_reconstruction.py --profile ProductionTSR --output Build/Presentation/reconstruction-tsr-fresh
python3 tests/run_d03_01_reconstruction.py --profile NativeTAA --output Build/Presentation/reconstruction-taa-fresh
python3 tests/run_d03_01_reconstruction.py --profile NativeTAA --scenario environment --output Build/Presentation/reconstruction-environment-fresh
python3 tests/run_d03_01_reconstruction.py --profile ProductionTSR --verify-feature-level sm6 --timeout 1500 --output Build/Presentation/sm6-default-fresh
python3 tests/run_d03_01_reconstruction.py --profile NativeTAA --feature-level sm5 --verify-feature-level sm5 --output Build/Presentation/sm5-fallback-fresh
```

Each output directory must be new. The runner saves exact source, module, content, configuration and verifier identities before/after execution, the launch command, closed raw logs, native frame and view CSVs, captures and an independently replayed validation report. `--profile InvalidFixture` tests the unknown-profile fallback. `--override-fxaa` deliberately overrides AA through the console and must fail reconstruction validation.

Qualification is bounded to the recorded Linux Vulkan Development editor build at 1280×720 on the observed L40S workstation, with existing development caches. The six-run matrix exercises automatic SM6 selection and explicit SM5 fallback, both temporal profiles, and environment gameplay/streaming. Hardware-triggered fallback and hardware reporting TSR unavailable have not been exercised. The SM6 runtime enables Nanite and VSM, but the sampled world contains zero static meshes with Nanite data or Nanite scene proxies; production geometry integration remains open. Surface cost windows exclude screenshot requests; reported native timings still include the opt-in view observer and this development environment.

See `Build/Presentation/D03-01-sm6-progress.md` for the matrix, exact build lineage and remaining work, and `Build/Presentation/D03-01-reconstruction-progress.md` for earlier profile controls. The earlier isolated SM5 Development package remains byte-exact and is qualified only against its preserved source in `Build/Presentation/D03-01-package-progress.md`. This matrix does not qualify an SM6 package, cold shader/PSO launch, another GPU/platform, generated frames or final production art.
