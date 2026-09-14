#!/usr/bin/env python3
"""Check the fixed D01 readability camera's shadowed player lower-body region.

This detects the observed dark-silhouette regression at 720p and 1080p. It does
not qualify arbitrary world lighting, character art or accessibility.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image


def verify(captures):
    records = []
    for width, height in ((1280, 720), (1920, 1080)):
        resolution = f'{width}x{height}'
        path = captures / resolution / f'active_12m_{resolution}.png'
        with Image.open(path) as image:
            assert image.size == (width, height), 'Unexpected fixed-camera resolution'
            scale = width / 1280
            region = tuple(int(v * scale) for v in (495, 407, 568, 535))
            # This region excludes the bright floor behind the upper torso.
            pixels = list(image.convert('RGB').crop(region).getdata())
        luminance = [0.2126*r + 0.7152*g + 0.0722*b for r, g, b in pixels]
        count = sum(b > 1.2*r and b > 1.05*g and luma > 25
                    for (r, g, b), luma in zip(pixels, luminance))
        coverage = count / len(pixels)
        mean = sum(luminance) / len(luminance)
        records.append(dict(path=str(path.resolve()), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            resolution=resolution, region=region, readable_blue_fraction=coverage,
                            mean_luminance_8bit=mean, passed=coverage >= 0.08 and mean >= 8))
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--captures', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expect-dark-control', action='store_true')
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve existing evidence; select a fresh output file'
    records = verify(args.captures)
    passed = all(record['passed'] for record in records)
    result = 'EXPECTED_RED' if args.expect_dark_control and not passed else 'PASS' if passed and not args.expect_dark_control else 'FAIL'
    report = dict(task_id='D03-01', result=result, scope=__doc__.strip(),
                  thresholds=dict(readable_blue_fraction_min=0.08, mean_luminance_8bit_min=8), captures=records)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 1 if result == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
