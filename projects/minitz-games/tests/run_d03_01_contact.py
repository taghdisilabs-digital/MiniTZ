#!/usr/bin/env python3
"""Native terrain-contact correction and gameplay cancellation evidence."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import pwd
import re
from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from run_d02_01 import identities, monitor, reject_material_fallbacks, runtime_has_task_error

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--disabled',action='store_true',help='Native correction-disabled negative control')
    a=p.parse_args(); out=a.output.resolve()
    assert not out.exists(), 'Use a fresh output directory'
    account=pwd.getpwnam('unreal'); ensure_runtime_output(out,account)
    protected=[PROJECT/'docs/PRODUCTION.md']
    def inputs(): return identities(DEFAULT_EDITOR)+[file_identity(Path(__file__))]
    report=dict(task_id='D03-01',result='FAIL',revision=source_revision(),scope='bounded terrain foot contact correction',
                capture_status='GENERATED_DRAFT', fixture='Population AI frozen; native game/input/movement/animation/rendering',
                identities_before=inputs(), protected_before=[file_identity(x) for x in protected])
    try:
        cmd=['runuser','-u','unreal','--','env','SDL_AUDIODRIVER=dummy','xvfb-run','-a','-s','-screen 0 1280x720x24',
             str(DEFAULT_EDITOR),str(PROJECT/'BiellaGames.uproject'),'/Game/Maps/BiellaGameplayMap','-game','-vulkan','-NoVSync',
             '-windowed','-ResX=1280','-ResY=720','-unattended','-AudioMixer','-nosplash','-stdout','-FullStdOutLogOutput',
             f'-AbsLog={out}/runtime.engine.log',f'-BiellaFootContactOutput={out}',
             '-ExecCmds=t.MaxFPS 0,r.VSync 0,r.MotionBlurQuality 0,r.DynamicRes.OperationMode 0,Automation RunTests BiellaGames.D03.FootContact; SoftQuit']
        if a.disabled: cmd.append('-BiellaContactDisabled')
        report['runtime']=monitor(cmd,out,210)
        log=(out/'runtime.stdout.log').read_text(errors='replace')
        result=json.loads((out/'result.json').read_text(encoding='utf-8-sig'))
        assert not report['runtime']['timed_out'] and report['runtime']['log_finalization']['closed'], 'Incomplete runtime'
        report['identities_after']=inputs(); report['protected_after']=[file_identity(x) for x in protected]
        assert report['identities_before']==report['identities_after'], 'Inputs changed during run'
        assert report['protected_before']==report['protected_after'], 'Stable Project production authority changed'
        assert report['runtime']['returncode']==0 and '**** TEST COMPLETE. EXIT CODE: 0 ****' in log, 'Unreal process failed'
        assert re.search(r'Result=\{Success\}.*Name=\{FootContact\}',log) and result['success'], 'Contact scenario failed'
        assert not runtime_has_task_error(log), 'Runtime error'
        reject_material_fallbacks(log)
        rows=list(csv.DictReader((out/'poses.csv').open(encoding='utf-8-sig')))
        checks=list(csv.DictReader((out/'checks.csv').open(encoding='utf-8-sig')))
        required={'flat','slope_positive','slope_negative','split_levels'}
        assert required <= {r['phase'] for r in checks}, 'Missing contact conditions'
        if a.disabled:
            split=[abs(float(r['sole_error'])) for r in checks if r['phase']=='split_levels']
            assert max(split)>8 and all(float(r['weight'])==0 for r in checks), 'Negative control did not expose missing correction'
            report['result']='EXPECTED_NEGATIVE_CONTROL'
        else:
            assert set(range(1,19)) <= {int(r['phase']) for r in rows}, 'Missing gameplay cancellation phases'
            qualified=[r for r in checks if r['phase'] not in {'steep_rejected','gap_rejected','missing_one_support'}]
            assert all(abs(float(r['sole_error']))<2 and float(r['normal_angle'])<8 and float(r['weight'])>.99 for r in qualified), 'Invalid contact/angle'
            report['result']='PASS'
        from PIL import Image
        labels=['flat','slope_positive','slope_negative','split_levels']
        if not a.disabled: labels+=['missing_one_support','jump','moving','after_seat']
        for label in labels:
            with Image.open(out/'captures'/f'{label}.png') as im:
                assert im.size==(1280,720) and max(hi-lo for lo,hi in im.convert('RGB').getextrema())>100, 'Invalid capture'
        report['pose_frames']=len(rows)
        report['captures']=[file_identity(out/'captures'/f'{label}.png') for label in labels]
        report['measurements']=[file_identity(out/name) for name in ('checks.csv','poses.csv','result.json')]
    except (AssertionError,OSError,ValueError,KeyError) as e:
        report['result']='FAIL'; report['error']=str(e)
    if report['result']=='FAIL':
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as f:
            f.write(json.dumps(dict(task_id='D03-01',time=datetime.now(timezone.utc).isoformat(),type='foot_contact_validation',
                                   status='CONTINUE',diagnostics=report.get('error','Contact validation failed'),evidence=str(out)))+'\n')
    write_json(out/'validation.json',report)
    print(json.dumps({k:report[k] for k in ('task_id','result','scope')} | {'output':str(out),'error':report.get('error')},indent=2))
    return 0 if report['result'] in ('PASS','EXPECTED_NEGATIVE_CONTROL') else 1

if __name__=='__main__': raise SystemExit(main())
