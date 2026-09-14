#!/usr/bin/env python3
"""Native gameplay/mixer proof for critical-cue combat ducking."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import pwd
import re
from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from run_d02_01 import identities, monitor, reject_material_fallbacks, runtime_has_task_error
from verify_d03_01_audio_mix import measure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expect-unducked', action='store_true')
    args = parser.parse_args(); out = args.output.resolve()
    assert not out.exists(), 'Use a fresh output directory'
    ensure_runtime_output(out, pwd.getpwnam('unreal'))
    protected = [PROJECT.parents[1]/'docs/project-state/03_BIELLA_CURRENT_STATE.md',
                 PROJECT.parents[1]/'docs/project-state/04_BIELLA_ACTIVE_TASK.md', PROJECT/'docs/PRODUCTION.md']
    def inputs():
        return identities(DEFAULT_EDITOR)+[file_identity(Path(__file__)),file_identity(PROJECT/'tests/verify_d03_01_audio_mix.py')]
    report = dict(task_id='D03-01', result='FAIL', revision=source_revision(), scope='critical-cue combat ducking',
                  capture_status='GENERATED_DRAFT', fixture='Native gameplay/audio mixer; population and pose frozen, fixed simulation delta 1/60; not speaker or shipping qualification',
                  identities_before=inputs(), protected_before=[file_identity(x) for x in protected])
    try:
        command = ['runuser','-u','unreal','--','xvfb-run','-a','-s','-screen 0 1280x720x24',
                   str(DEFAULT_EDITOR),str(PROJECT/'BiellaGames.uproject'),'/Game/Maps/BiellaGameplayMap','-game','-vulkan',
                   '-NoVSync','-windowed','-ResX=1280','-ResY=720','-unattended','-AudioMixer','-DeterministicAudio',
                   '-UseFixedTimeStep','-FPS=60','-NoAsyncLoadingThread','-nosplash','-stdout','-FullStdOutLogOutput',
                   f'-AbsLog={out}/runtime.engine.log',f'-BiellaAudioMixOutput={out}',
                   '-ExecCmds=Automation RunTests BiellaGames.D03.AudioMix; SoftQuit']
        if args.expect_unducked: command.append('-BiellaExpectUnducked')
        report['runtime'] = monitor(command,out,180)
        log = (out/'runtime.stdout.log').read_text(errors='replace')
        result = json.loads((out/'result.json').read_text(encoding='utf-8-sig'))
        assert not report['runtime']['timed_out'] and report['runtime']['log_finalization']['closed'], 'Incomplete runtime'
        assert 'D03_AUDIO_COMPLETE' in log, 'Scenario incomplete'
        report['triggers'] = re.findall(r'LogTemp: Display: D03_AUDIO_TRIGGER ([^\n]+)', log)
        assert len(report['triggers']) == 3, 'Missing real gameplay recording triggers'
        report['mix'] = measure(out)
        report['identities_after'] = inputs(); report['protected_after'] = [file_identity(x) for x in protected]
        assert report['identities_before'] == report['identities_after'], 'Inputs changed'
        assert report['protected_before'] == report['protected_after'], 'Protected authority changed'
        mix = report['mix']
        assert mix['relative_residual'] < 0.12 and 0.85 < mix['critical_gain'] < 1.15, 'Solo waveform fit does not establish clean critical gain'
        if args.expect_unducked:
            assert result['success'] and report['runtime']['returncode'] == 0, 'Expected-error control did not pass all native assertions'
            assert not runtime_has_task_error(log), 'Unexpected native control errors'
            assert 0.85 < mix['combat_gain'] < 1.15, 'Original mixer does not match unducked control'
            report['result'] = 'EXPECTED_RED'
        else:
            assert result['success'] and report['runtime']['returncode'] == 0, 'Native audio assertions failed'
            assert not runtime_has_task_error(log), 'Native runtime errors'
            reject_material_fallbacks(log)
            assert 0.15 < mix['combat_gain'] < 0.35, 'Mixer output does not contain the requested combat ducking'
            from PIL import Image
            with Image.open(out/'mixed.png') as im:
                im.load(); assert im.size == (1280,720), 'Capture resolution differs'
            report['result'] = 'PASS'
    except (AssertionError, OSError, ValueError, KeyError) as error:
        report['error'] = str(error)
    if report['result'] != 'PASS':
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as f:
            f.write(json.dumps(dict(task_id='D03-01',time=datetime.now(timezone.utc).isoformat(),type='audio_validation',
                                   status=report['result'],diagnostics=report.get('error','Expected RED: original combat is not ducked'),evidence=str(out)))+'\n')
    write_json(out/'validation.json',report)
    print(json.dumps({k:report[k] for k in ('task_id','result')}|{'output':str(out),'error':report.get('error'),'mix':report.get('mix')},indent=2))
    return 0 if report['result'] in ('PASS','EXPECTED_RED') else 1


if __name__ == '__main__': raise SystemExit(main())
