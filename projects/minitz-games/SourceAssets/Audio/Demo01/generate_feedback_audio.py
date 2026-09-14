#!/usr/bin/env python3
"""Editable deterministic Demo 01 feedback masters; Python standard library only.

48 kHz mono PCM16 keeps transients precise and supports runtime spatialization.
No sampled/licensed third-party content, voice, music or new soundtrack canon.
Edit CUES and layer functions, regenerate, verify, then explicitly reimport.
"""
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import struct
import wave


RATE = 48000
ROOT = Path(__file__).resolve().parent
CUES = {
    "S_ShotA": ("shot", 0.240, -9.5, 401),
    "S_ShotB": ("shot", 0.255, -9.5, 817),
    "S_ShotC": ("shot", 0.225, -9.5, 129),
    "S_Impact": ("impact", 0.180, -12.0, 613),
    "S_Hurt": ("hurt", 0.260, -12.0, 721),
    "S_Pressure": ("pressure", 0.580, -15.0, 314),
    "S_Success": ("success", 0.780, -14.0, 811),
    "S_Failure": ("failure", 0.860, -14.0, 917),
}


def tone(t, frequency, decay, start=0.0):
    t -= start
    if t < 0:
        return 0.0
    return math.sin(2 * math.pi * frequency * t) * math.exp(-t / decay) * min(t / 0.003, 1.0)


def synthesize(kind, duration, seed):
    rng = random.Random(seed)
    detune = rng.uniform(0.93, 1.07)
    samples = []
    low = 0.0
    previous_low = 0.0
    for index in range(round(duration * RATE)):
        t = index / RATE
        noise = rng.uniform(-1, 1)
        low += 0.18 * (noise - low)
        mid = low - previous_low
        previous_low += 0.016 * (low - previous_low)
        if kind == "shot":
            # Broadband crack, chest report, then a short metallic action tail.
            crack = 0.65 * noise * math.exp(-t / (0.009 * detune))
            report = 1.25 * mid * math.exp(-t / (0.040 * detune))
            body = 0.46 * tone(t, 108 * detune, 0.023)
            action = 0.055 * tone(t, 1780 * detune, 0.016, 0.029)
            sample = crack + report + body + action
        elif kind == "impact":
            sample = (0.85 * mid * math.exp(-t / 0.022)
                      + 0.21 * tone(t, 460, 0.012)
                      + 0.05 * tone(t, 1320, 0.019))
        elif kind == "hurt":
            # A body hit with a dull low report; deliberately no synthetic voice.
            sample = (0.55 * low * math.exp(-t / 0.032)
                      + 0.42 * tone(t, 74, 0.047)
                      + 0.13 * tone(t, 143, 0.026))
        elif kind == "pressure":
            # Two damped mechanical pulses distinguish state transition from fire.
            sample = (0.34 * tone(t, 122, 0.075)
                      + 0.17 * tone(t, 183, 0.045)
                      + 0.30 * tone(t, 122, 0.072, 0.220)
                      + 0.10 * tone(t, 183, 0.044, 0.220))
        elif kind == "success":
            # Restrained rising resonances, short enough to leave gameplay audible.
            sample = (0.30 * tone(t, 392, 0.125)
                      + 0.24 * tone(t, 587.33, 0.160, 0.135)
                      + 0.20 * tone(t, 784, 0.125, 0.270))
        elif kind == "failure":
            sample = (0.38 * tone(t, 196, 0.170)
                      + 0.28 * tone(t, 146.83, 0.170, 0.165)
                      + 0.24 * tone(t, 98, 0.160, 0.330)
                      + 0.04 * low * math.exp(-t / 0.140))
        else:
            raise ValueError(kind)
        samples.append(sample)
    # Remove weighted DC while preserving zero, smoothly faded endpoints.
    fades = [min(index / (RATE * 0.0015), 1.0)
             * min((len(samples) - 1 - index) / (RATE * 0.020), 1.0)
             for index in range(len(samples))]
    mean = sum(value * fade for value, fade in zip(samples, fades)) / sum(fades)
    return [(value - mean) * fade for value, fade in zip(samples, fades)]


def write_wave(path, values):
    with wave.open(str(path), "wb") as target:
        target.setparams((1, 2, RATE, len(values), "NONE", "not compressed"))
        target.writeframes(struct.pack("<" + "h" * len(values), *values))


def main():
    manifest = {"task_id": "D01-42", "status": "GENERATED_DRAFT",
                "source": "Original deterministic synthesis; no third-party samples",
                "format": "48000 Hz mono signed PCM16 WAV",
                "generator": Path(__file__).name,
                "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "resource_route": {"capability": "audio", "providers": []},
                "cues": {}}
    preview = []
    for name, (kind, duration, peak_db, seed) in CUES.items():
        raw = synthesize(kind, duration, seed)
        scale = 32767 * 10 ** (peak_db / 20) / max(abs(value) for value in raw)
        values = [round(value * scale) for value in raw]
        path = ROOT / (name + ".wav")
        write_wave(path, values)
        manifest["cues"][name] = {"kind": kind, "duration_seconds": len(values) / RATE,
                                 "target_peak_dbfs": peak_db, "seed": seed,
                                 "asset_path": "/Game/Feedback/Audio/" + name,
                                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        preview.extend(values)
        preview.extend([0] * int(0.35 * RATE))
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # Inspector candidates duplicate the canonical editable masters, never authority.
    artifacts = Path("/root/biella/artifacts/games/D01-042/audio")
    artifacts.mkdir(parents=True, exist_ok=True)
    for source in ROOT.glob("*.wav"):
        shutil.copy2(source, artifacts / source.name)
    shutil.copy2(ROOT / "manifest.json", artifacts / "manifest.json")
    write_wave(artifacts / "GENERATED_DRAFT-cue-audition.wav", preview)
    print(json.dumps({"masters": len(CUES), "source": str(ROOT), "inspector": str(artifacts)}))


if __name__ == "__main__":
    main()
