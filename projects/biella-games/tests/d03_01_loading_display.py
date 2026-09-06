#!/usr/bin/env python3
"""Capture the real X11 loading display; keep capture cost explicit in evidence."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    out = Path('/tmp/evidence')
    video = out/'loading-display.mp4'
    assert not video.exists()
    command = ['ffmpeg', '-nostdin', '-loglevel', 'warning', '-f', 'x11grab', '-framerate', '10',
               '-video_size', '1280x720', '-i', os.environ['DISPLAY'], '-t', '120', '-an',
               '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-threads', '2',
               '-pix_fmt', 'yuv420p', str(video)]
    start = time.monotonic()
    with (out/'loading-display.ffmpeg.log').open('xb') as stream:
        recorder = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
        time.sleep(0.5)
        assert recorder.poll() is None, 'X11 recorder failed to start'
        game_start = time.monotonic()
        game = subprocess.Popen(sys.argv[1:])
        stop_observed = None
        recorder_stopped = None
        gameplay_observed = None
        while game.poll() is None:
            log = out/'runtime.engine.log'
            if gameplay_observed is None and log.exists():
                # Read a bounded tail while the engine appends; never alter its log.
                with log.open('rb') as source:
                    source.seek(max(0, log.stat().st_size - 65536))
                    tail = source.read()
                    if stop_observed is None and b'D03_LOADING_STOP' in tail:
                        stop_observed = time.monotonic()
                    if b'Test Started.' in tail:
                        gameplay_observed = time.monotonic()
            if recorder_stopped is None and (recorder.poll() is not None or
                    (gameplay_observed is not None and time.monotonic() - gameplay_observed >= 2)):
                if recorder.poll() is None:
                    recorder.send_signal(signal.SIGINT)
                recorder_stopped = time.monotonic()
            time.sleep(0.25)
        if recorder.poll() is None:
            recorder.send_signal(signal.SIGINT)
        recorder_rc = recorder.wait(timeout=15)
    report = dict(command=command, game_command=sys.argv[1:], fps=10,
                  game_launch_seconds=game_start-start,
                  loading_stop_observed_seconds=stop_observed-start if stop_observed else None,
                  gameplay_observed_seconds=gameplay_observed-start if gameplay_observed else None,
                  recorder_stopped_seconds=recorder_stopped-start if recorder_stopped else None,
                  recorder_returncode=recorder_rc, game_returncode=game.returncode,
                  scope='Independent X11 capture at 10 Hz with lossy H264; capture instrumentation affects runtime; GENERATED_DRAFT')
    (out/'loading-display.json').write_text(json.dumps(report, indent=2)+'\n')
    return game.returncode


if __name__ == '__main__':
    raise SystemExit(main())
