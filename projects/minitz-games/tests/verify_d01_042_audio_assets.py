#!/usr/bin/env python3
"""Decode D01-42 masters and verify source traceability/headroom/variation."""
import hashlib
import json
import math
from pathlib import Path
import struct
import wave


PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / "SourceAssets/Audio/Demo01"
NAMES = {"S_ShotA", "S_ShotB", "S_ShotC", "S_Impact", "S_Hurt",
         "S_Pressure", "S_Success", "S_Failure"}


def verify():
    assert (ROOT / "manifest.json").is_file(), "D01-42 audio masters have not been authored"
    manifest = json.loads((ROOT / "manifest.json").read_text())
    assert manifest["status"] == "GENERATED_DRAFT"
    assert hashlib.sha256((ROOT / manifest["generator"]).read_bytes()).hexdigest() == manifest["generator_sha256"], "Generator changed without regenerating masters"
    assert set(manifest["cues"]) == NAMES
    hashes = set()
    for name, expected in manifest["cues"].items():
        path = ROOT / (name + ".wav")
        identity = hashlib.sha256(path.read_bytes()).hexdigest()
        assert identity == expected["sha256"], f"{name}: source identity changed"
        hashes.add(identity)
        with wave.open(str(path)) as stream:
            assert (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) == (1, 2, 48000), name
            assert stream.getcomptype() == "NONE", name
            count = stream.getnframes()
            data = stream.readframes(count)
        assert len(data) == count * 2, f"{name}: incomplete PCM decode"
        values = struct.unpack("<" + "h" * count, data)
        peak = max(abs(value) for value in values) / 32768
        rms = math.sqrt(sum(value * value for value in values) / count) / 32768
        assert 0.05 < peak < 0.36, f"{name}: insufficient headroom or silence"
        assert rms > 0.005, f"{name}: cue inaudible"
        assert abs(sum(values) / count / 32768) < 0.001, f"{name}: DC offset"
        assert values[0] == values[-1] == 0, f"{name}: discontinuous endpoint"
        assert abs(count / 48000 - expected["duration_seconds"]) < 1 / 48000, name
        assert 0.08 <= count / 48000 <= 1.0, f"{name}: uncontrolled cue length"
        print(f"PASS {name} duration={count / 48000:.3f}s peak={20 * math.log10(peak):.2f}dBFS rms={20 * math.log10(rms):.2f}dBFS")
    assert len(hashes) == len(NAMES), "Repeated cues require genuine source variation"
    return {"task_id": "D01-42", "result": "PASS", "count": len(hashes), "status": "GENERATED_DRAFT"}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
