#!/usr/bin/env python3
"""Record native X11 gameplay and ordinary input; never mutate the game world."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--height', type=int, required=True)
    parser.add_argument('--seconds', type=float, required=True)
    args = parser.parse_args()
    output = Path('/tmp/evidence')
    plan = json.loads(Path('/tmp/input-plan.json').read_text())
    resolved = json.loads(Path('/tmp/resolved-package.json').read_text())
    payload = Path('/tmp/package')
    actual_paths = sorted(str(p.relative_to(payload)) for p in payload.rglob('*') if p.is_file())
    assert actual_paths == sorted(row['path'] for row in resolved['files'])
    for row in resolved['files']:
        path = payload / row['path']
        assert not path.is_symlink() and path.stat().st_size == row['bytes']
        with path.open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == row['sha256']
        assert bool(path.stat().st_mode & 0o111) == row['executable']
    (output / 'exposed-package-verification.json').write_text(json.dumps({
        'runtime_id': resolved['runtime_id'], 'status': 'PASS',
        'scope': 'Exact membership, bytes and executable permissions inside native launch namespace',
        'files': len(actual_paths)}, indent=2) + '\n')
    command = ['/tmp/package/BiellaGames.sh', '/Game/Maps/BiellaOpenWorldMap',
               '-vulkan', '-NoVSync', '-windowed', f'-ResX={args.width}',
               f'-ResY={args.height}', '-unattended', '-AudioMixer', '-nosplash',
               '-stdout', '-FullStdOutLogOutput', '-NoAsyncLoadingThread',
               '-UserDir=/tmp/state/user/', '-AbsLog=/tmp/evidence/runtime.engine.log',
               '-ExecCmds=t.MaxFPS 60,r.VSync 0',
               '-BiellaTelemetry=/tmp/evidence/telemetry.jsonl']
    (output / 'game-command.json').write_text(json.dumps(command, indent=2) + '\n')
    events = (output / 'input.jsonl').open('x', buffering=1)
    start = time.monotonic()
    def event(kind, **fields):
        events.write(json.dumps(dict(event=kind, elapsed_seconds=time.monotonic()-start,
                                    **fields)) + '\n')
    game = subprocess.Popen(command, start_new_session=True)
    recorder = None
    result = {'status': 'INCOMPLETE', 'reason': 'startup_not_observed',
              'audio_capture': False, 'input_delivery': 'X11 keyboard/mouse',
              'world_mutation_or_automation_tests': False}
    try:
        log = output / 'runtime.engine.log'
        deadline = time.monotonic() + 100
        window = None
        while game.poll() is None and time.monotonic() < deadline:
            text = log.read_text(errors='replace') if log.exists() else ''
            candidates = subprocess.run(['xdotool', 'search', '--onlyvisible', '--name',
                                         'BiellaGames'], capture_output=True, text=True)
            if 'D01_SIGNAL CONTROLLER_READY' in text and candidates.stdout.strip():
                window = candidates.stdout.splitlines()[-1]
                break
            time.sleep(.1)
        if window is None:
            raise RuntimeError('Native game window/controller was not observed')
        subprocess.run(['xdotool', 'windowfocus', '--sync', window], check=True)
        subprocess.run(['xdotool', 'mousemove', str(args.width//2), str(args.height//2)], check=True)
        capture = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'warning',
                   '-f', 'x11grab', '-framerate', '30', '-video_size',
                   f'{args.width}x{args.height}', '-i', os.environ['DISPLAY'],
                   '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16',
                   '-pix_fmt', 'yuv420p', str(output / 'raw-gameplay.mkv')]
        (output / 'capture-command.json').write_text(json.dumps(capture, indent=2) + '\n')
        with (output / 'capture.log').open('x') as log_stream:
            recorder = subprocess.Popen(capture, stdout=log_stream, stderr=subprocess.STDOUT)
            start = time.monotonic()
            event('capture_started', window=window)
            next_action = 0
            result['reason'] = 'bounded_route_probe_finished'
            while game.poll() is None and time.monotonic()-start < args.seconds:
                elapsed = time.monotonic()-start
                text = log.read_text(errors='replace')
                if 'TERMINAL_INPUT_STATE terminal=true' in text:
                    event('native_terminal_observed')
                    result['reason'] = 'native_terminal_state'
                    break
                if recorder.poll() is not None:
                    raise RuntimeError('Raw recorder exited during gameplay')
                while next_action < len(plan['actions']) and plan['actions'][next_action]['at'] <= elapsed:
                    action = plan['actions'][next_action]
                    operation = action['input']
                    if operation[0] not in {'keydown', 'keyup', 'mousedown', 'mouseup', 'mousemove_relative'}:
                        raise ValueError('Only ordinary movement/look/fire input is permitted')
                    if any(key in {'r', 'R', 'grave', 'asciitilde'} for key in operation[1:]):
                        raise ValueError('Restart/console input is forbidden in the continuous run')
                    subprocess.run(['xdotool', *operation], check=True)
                    event('input_sent', planned_at=action['at'], input=operation,
                          intended_beat=action['beat'])
                    next_action += 1
                time.sleep(.05)
            result.update(status='CAPTURED', measured_input_run_seconds=time.monotonic()-start,
                          actions_sent=next_action, game_alive_at_capture_end=game.poll() is None)
            # Preserve the actual terminal state for two seconds; this is not active play duration.
            time.sleep(2)
            recorder.send_signal(signal.SIGINT)
            result['recorder_returncode'] = recorder.wait(timeout=30)
            recorder = None
    except Exception as exc:
        result.update(status='FAILED', error=f'{type(exc).__name__}: {exc}')
        event('failure', error=result['error'])
    finally:
        subprocess.run(['xdotool', 'keyup', 'w', 'a', 's', 'd', 'space', 'Shift_L',
                        'mouseup', '1'], capture_output=True)
        if recorder is not None and recorder.poll() is None:
            recorder.send_signal(signal.SIGINT)
            recorder.wait(timeout=30)
        if game.poll() is None:
            # Normal UE console exit is sent only after capture, never during proof.
            subprocess.run(['xdotool', 'key', 'grave'], capture_output=True)
            subprocess.run(['xdotool', 'type', '--clearmodifiers', 'quit'], capture_output=True)
            subprocess.run(['xdotool', 'key', 'Return'], capture_output=True)
            try:
                game.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(game.pid, signal.SIGTERM)
                game.wait(timeout=15)
                result['teardown'] = 'SIGTERM_after_capture'
        result['game_returncode'] = game.returncode
        (output / 'input-result.json').write_text(json.dumps(result, indent=2) + '\n')
        event('capture_finished', result=result)
        events.close()
    return 0 if result['status'] == 'CAPTURED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
