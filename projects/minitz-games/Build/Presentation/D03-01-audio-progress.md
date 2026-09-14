# D03-01 — critical-cue audibility increment

**Increment validation: PASS. Full D03-01: CONTINUE.**

Pressure, success and failure cues now reduce competing combat audio to 0.25
of its existing budgeted gain. The reduction applies before critical playback
and covers both existing and newly emitted combat voices. After the last
critical voice drains, combat recovers linearly over 0.20 game seconds. Reset
restores full gain. Critical authored volume, event semantics, spatialization,
source assets, the 12 combat / 2 critical voice limits and 24-effect cap remain.

This implements a bounded part of runtime contract 20. It does not establish
final sound design or complete production rendering, animation, VFX and audio.
Engine P4-06 remains `INCOMPLETE_DEFERRED`; no later task was started.

## Editable implementation and proof

`Source/BiellaGames/Private/BiellaGameplayFeedback.cpp` and its public header
own the envelope. `BiellaAudioMixTest.cpp` executes actual accepted weapon
fire, ammo/damage changes, arena pressure transitions, player damage and defeat
through the running game. The dedicated fixture freezes population and pose
movement to hold listener/source geometry stable; it uses the native renderer,
game audio device, mixer, sound assets and gameplay feedback subsystem.

`tests/run_d03_01_audio_mix.py` records combat-only, critical-only and concurrent
events. `verify_d03_01_audio_mix.py` aligns measured solo references and fits
both gains jointly against the original mixed PCM. Subtracting the fitted
critical reference is used only to locate quiet combat; no expected gain is
used to choose alignment. WAV bytes are never normalized, stretched or edited.

| Evidence under `Build/Presentation/` | Observed result |
| --- | --- |
| `audio-green-build-01/build.log` | Linux Development editor build succeeded, 16 actions, 16.76 seconds |
| `audio-red-runtime-05/validation.json` | Unmodified production baseline: exactly three expected native failures; measured combat 0.975270, critical 0.998039, residual 6.075% |
| `audio-runtime-02/validation.json` | Fresh GREEN PASS: combat 0.243774, critical 0.999915, residual 1.671% |
| `audio-runtime-03/` | Final validator bytes; native checks and mixer passed, but aggregate report retained FAIL after concurrent authority changes |
| `D03-01-audio-final-readback.json` | Separate final admission PASS: final native combat 0.243774, critical 0.999918, residual 1.757%; current inputs, raw captures and authority verified |
| `audio-finalization-01/validator-controls.json` | Six negative controls rejected; original native RED still fails GREEN bounds |
| `audio-feedback-regression-01/validation.json` | All 12 existing gameplay audio/VFX phases passed; 5 distinct unclipped cue WAVs, 6 rendered frames, 4 positive live-particle samples |
| `audio-finalization-01/regression-log-finalization.json` | Original log prefix preserved; late trace-server shutdown suffix verified after all writers closed |
| `D03-01-audio-preservation.json` | Prior rendering and animation manifest bytes match their commits; all 746 entries remain unchanged |

Native checks cover immediate attack, authored critical gain, a new combat
voice during release, monotonically bounded recovery, dense damage, reset,
real defeat, terminal replacement and finite voice drainage. The final release
CSV contains 24 samples and reaches full combat gain within 0.20 game seconds
of the observation point. Release is frame-quantized, not sample-accurate.

The separate regression also checks rejected events remain silent, actual
spatial combat events, pressure transition deduplication, success/failure once,
restart and lifecycle cleanup. Its dense rendered tick retains 24 effects and
192 live particles. These fixed-delta measurements are not shipping performance
qualification. Direct visual inspection covered the final audio fixture and
dense-combat frame; the blockout world, character resources and weapon remain
unfinished presentation. Every capture remains `GENERATED_DRAFT`.

## Retained failures and scope limits

All build, runtime, diagnostic and provider attempts remain at their original
paths. The failed initial launch required restoring executable/readable mode
on the root-built game module. Intentional RED assertions were registered as
expected errors to avoid Unreal's critical-error teardown path. Native NRT
recordings did not reliably retain isolated spatial combat in this fixture;
the dedicated mix test therefore uses the ordinary SDL mixer with a dummy
device. Its PCM is 48 kHz, 16-bit, six channels; this fixture uses the front pair.
Moving screenshot readback after the audible event avoided a measured 725 ms
recording disruption. An independent-correlation defect selected the wrong
combat lag under a dominant critical cue; residual alignment corrected it
without relaxing fit or gain thresholds. The original verifier and recordings
remain in `audio-diagnostics-01/` and their original run directories.

During final capture, another process temporarily changed 03/04, then restored
their exact pre-run bytes. The original failed report remains intact. Current
task identity, source/build/assets and authority were checked separately in
`audio-finalization-01/authority-reconciliation.json` and final readback. This
controller did not edit or restore those authority files. The latest explicit
resume instruction remains authoritative over their earlier paused directive.

The legacy regression runner hashed stdout before a trace-server descendant
finished writing its 770-byte shutdown suffix. Final readback detected this;
the old prefix matches exactly and the appended text reports clean daemon exit.
The complete unmodified log now has a separately verified final identity.

Audio authoring Resource routes returned no configured provider. Local Qwen
design/diagnostic assistance was inspected, with unsupported claims rejected;
the exact-diff review request timed out. Bounded controller review is preserved
in `audio-review-01/controller-review.md`; no provider approval is claimed.
Failures and repairs are recorded in the canonical runtime `failures.jsonl`.

Physical listening, arbitrary devices, pause/time-dilation, cooked packages and
launch hardware remain unqualified. The broader task still needs production
world/lighting and character/weapon art, foot placement/IK, aim/action/hit/defeat
layers, skeletal vehicle presentation, broader transitions/LOD/crowds, additional
production VFX/audio coverage and launch-platform validation.

Exact canonical local files are inventoried by `D03-01-audio-file-manifest.json`.
The increment is committed locally for the Auto Feeder, which owns GitHub/Drive
publication and canonical state transition under the current task instruction.
No remote publication or full task completion is inferred here.
