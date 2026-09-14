# D03-01 audio increment review

Review scope: the exact GameplayFeedback .cpp/.h change, native AudioMix fixture,
runner and waveform estimator. Local Qwen was routed through unreal.assist and
called with the exact diff; it returned TimeoutError. Its preserved response is
not a review approval. Controller source inspection and native measurements
supply the review evidence.

- Prune removes invalid/stopped/expired components before balancing. Emit adds a
  registered voice and balances before Play, so the new critical voice must count
  before IsPlaying becomes true. All component accesses follow these paths.
- Critical voices keep BaseVolume. Only combat receives the existing voice
  budget times the world-owned envelope. Old and new combat share it; terminal
  replacement preserves the same envelope, without changing gameplay events.
- Each tick prunes first, holds .25 if critical remains, otherwise advances the
  release once using nonnegative game delta. Release is linear in game time and
  frame-quantized; it is not sample-accurate or wall-clock based. Reset/deinitialize
  destroy voices and restore gain 1, avoiding inheritance across world teardown.
- Native coverage exercises accepted shot/ammo/damage, critical onset, newly born
  combat during release and dense combat, monotonic recovery, reset, actual
  defeat, terminal replacement and drainage. The existing regression separately
  checks success, restart, rejected events, live Niagara and all sound families.
- The mixer estimator uses measured solo references and actual native captures.
  Critical subtraction is used only to locate the quiet combat waveform; final
  gains fit both original references jointly. It uses no expected gain to select
  alignment. The unchanged raw RED capture must remain rejected by GREEN bounds.

No production correctness issue found in this bounded change. This is not final
sound design, physical listening, arbitrary-device, paused/time-dilation, packaged
build or launch-platform qualification. Simulation delta is fixed to 1/60 for the
fixture; ordinary SDL dummy audio follows wall time. Visual captures remain draft.
