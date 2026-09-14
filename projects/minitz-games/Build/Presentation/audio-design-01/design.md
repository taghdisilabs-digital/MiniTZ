# D03-01 — critical cue audibility

The current feedback subsystem reserves pressure/result voices but leaves
competing combat at full budgeted gain. Add a 0.25 combat multiplier while a
critical voice is alive, applied before playback. Restore combat linearly over
0.20 seconds after the last critical voice finishes. Critical gain, existing
voice caps, spatialization, source assets and gameplay semantics stay intact.
The immediate attack protects the critical onset; the release avoids a sudden
return of surviving/new combat voices. Reset cancels the envelope.

Validation first: a native scenario fires actual accepted gameplay shots and
changes actual arena pressure. Record combat-only, critical-only and concurrent
Unreal mixer output. Fit the concurrent waveform against time-aligned solo
recordings to measure combat and critical gains; inspect residuals before using
the fit. The unmodified runtime must expose unducked combat. Check newly born
voices, monotonic release, dense damage, terminal replacement and reset.
Run the existing complete audio/VFX regression after the change.

Use the current canonical gameplay map as a controlled audio fixture. Freeze
autonomous population movement and pose ticking only within the fixture; the
audio device, mixer, sound decoding, gameplay events and Niagara remain native.
Software mixer capture is not physical speaker/headphone or shipping quality
qualification. D03-01 remains CONTINUE and captures remain GENERATED_DRAFT.

Resource routes found no configured audio authoring provider. Local Qwen
assistance is preserved in request.json/response.txt. Its timing and possible
nonlinear-mix cautions inform measurement; it incorrectly swapped combat and
critical event labels. No independent approval or sample-accurate envelope is
claimed. No new bus or middleware is needed for this bounded change.
