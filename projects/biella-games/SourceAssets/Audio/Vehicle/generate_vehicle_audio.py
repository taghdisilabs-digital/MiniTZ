#!/usr/bin/env python3
"""Generate the editable original D02-03 vehicle engine loop master."""
import hashlib
import json
import math
from pathlib import Path
import struct
import wave

RATE = 48000
DURATION = 2.0
ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'S_VehicleEngine.wav'

values = []
count = round(RATE * DURATION)
for i in range(count):
    # Sample both exact loop endpoints so Unreal sees no discontinuity at wrap.
    t = DURATION * i / (count - 1)
    carrier = (0.58 * math.sin(2 * math.pi * 55 * t)
               + 0.25 * math.sin(2 * math.pi * 110 * t)
               + 0.11 * math.sin(2 * math.pi * 165 * t)
               + 0.06 * math.sin(2 * math.pi * 275 * t))
    pulse = 0.78 + 0.22 * math.sin(2 * math.pi * 4 * t)
    values.append(carrier * pulse)
peak = max(abs(v) for v in values)
scale = 32767 * (10 ** (-11.0 / 20)) / peak
pcm = [round(v * scale) for v in values]
with wave.open(str(OUT), 'wb') as wav:
    wav.setparams((1, 2, RATE, len(pcm), 'NONE', 'not compressed'))
    wav.writeframes(struct.pack('<' + 'h' * len(pcm), *pcm))
manifest = {
    'task_id': 'D02-03', 'status': 'GENERATED_DRAFT',
    'source': 'Original deterministic synthesis; no third-party samples',
    'format': '48000 Hz mono signed PCM16 WAV', 'duration_seconds': DURATION,
    'asset_path': '/Game/Vehicle/Audio/S_VehicleEngine',
    'source_sha256': hashlib.sha256(OUT.read_bytes()).hexdigest(),
    'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
(ROOT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, sort_keys=True))
