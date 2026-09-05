# Demo 01 event feedback audio

Task: D01-42. Content status: `GENERATED_DRAFT`; implementation validation does
not constitute Mahdi's final audio/art acceptance.

These original deterministic cues contain no third-party samples, voices or
soundtrack material. `biella resource route audio` returned no providers, so
local synthesis avoided an unnecessary external dependency. Editable layer
functions, cue seeds, durations and peak targets are in
`generate_feedback_audio.py`. `manifest.json` binds that source to every master
and native `/Game/Feedback/Audio` SoundWave identity.

| Native asset | Duration | Master peak | Character |
|---|---:|---:|---|
| S_ShotA | 0.240 s | -9.5 dBFS | Crack, low report, action tail |
| S_ShotB | 0.255 s | -9.5 dBFS | Different noise and resonances |
| S_ShotC | 0.225 s | -9.5 dBFS | Different noise and resonances |
| S_Impact | 0.180 s | -12 dBFS | Damp impact with a brief metallic resonance |
| S_Hurt | 0.260 s | -12 dBFS | Low body hit without vocal simulation |
| S_Pressure | 0.580 s | -15 dBFS | Two damped mechanical pulses |
| S_Success | 0.780 s | -14 dBFS | Restrained rising confirmation |
| S_Failure | 0.860 s | -14 dBFS | Restrained falling confirmation |

All masters are 48 kHz mono signed PCM16, with zero endpoints, short fades and
negligible DC. Native SoundWaves use lossless PCM and ForceInline loading to
avoid streaming latency for these short cues. Runtime code owns spatialization,
volume, pitch variation, priority, concurrency and event dispatch.

From the Project root:

```bash
python3 SourceAssets/Audio/Demo01/generate_feedback_audio.py
python3 tests/verify_d01_042_audio_assets.py
```

Then run `Content/Python/import_demo_feedback_audio.py` through the documented
Unreal Python commandlet. The first run creates missing assets; existing assets
are verified without mutation. After intentionally editing masters, pass
`-D01ReimportFeedbackAudio`. A fresh process with `-D01VerifyFeedbackAudio`
requires the saved native assets and checks imported format, duration, finite
playback, PCM codec, inline loading, source hash and exact native WAV export
PCM equality. `Build/Demo01/D01-042-audio-assets.json` records the readback.

The generator mirrors masters and an ordered audition with 350 ms gaps to
`/root/biella/artifacts/games/D01-042/audio/` for the private inspector. Those
copies and the audition remain draft supporting artifacts; gameplay uses the
event-triggered native assets. Actual mixer playback and VFX synchronization
are validated by the D01-42 runtime test, separately from source/native decode.
