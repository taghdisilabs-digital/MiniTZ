#!/usr/bin/env python3
"""Exercise the mix validator with native captures and explicit bad derivatives.

Derived WAVs exist only in a temporary test directory. Original evidence is
read-only, and this check is not another gameplay capture.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import wave
import numpy as np
from verify_d03_01_audio_mix import measure, qualify_mix, read_wave


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--red', type=Path, required=True)
    parser.add_argument('--green', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve existing evidence'
    red, green = measure(args.red), measure(args.green)
    qualify_mix(red, expect_unducked=True)
    qualify_mix(green)
    controls = []

    def rejected(name, folder):
        try:
            qualify_mix(measure(folder))
        except AssertionError as error:
            controls.append(dict(name=name, rejected=True, reason=str(error)))
        else:
            raise AssertionError(f'Validator accepted {name}')

    rejected('actual unducked native baseline', args.red)
    with tempfile.TemporaryDirectory(prefix='biella-d03-audio-controls-') as tmp:
        folder = Path(tmp)
        for name in ('combat', 'critical', 'mixed'):
            shutil.copyfile(args.green / (name + '.wav'), folder / (name + '.wav'))
        actual, _ = read_wave(folder / 'mixed.wav')
        critical, _ = read_wave(folder / 'critical.wav')

        def write(data):
            with wave.open(str(folder / 'mixed.wav'), 'wb') as w:
                w.setnchannels(data.shape[1]); w.setsampwidth(2); w.setframerate(48000)
                w.writeframes(np.clip(np.rint(data * 32768), -32768, 32767).astype('<i2').tobytes())

        write(critical)
        rejected('combat absent; critical alone', folder)
        write(actual * 0.5)
        rejected('critical gain incorrectly halved', folder)
        write(np.zeros_like(actual))
        rejected('silent mixer output', folder)
        write(np.full_like(actual, 1.0))
        rejected('clipped mixer output', folder)
        noise = np.random.default_rng(301).normal(0, 0.007, actual.shape)
        write(actual + noise)
        rejected('uncorrelated contamination invalidates source fit', folder)
    result = dict(task_id='D03-01', result='PASS', red=red, green=green,
                  negative_controls=controls,
                  scope='Validator controls; synthetic mutations are not gameplay evidence')
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(result='PASS', negative_controls=len(controls), output=str(args.output))))


if __name__ == '__main__':
    main()
