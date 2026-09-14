"""Win64 setup integration; compiler probes never establish game acceptance."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]

def test_setup_has_real_compiler_engine_sdk_and_install_paths():
    text=(ROOT/'ops/workstation/setup-unreal-win64.ps1').read_text()
    for value in ('vswhere.exe','VsDevCmd.bat','compiler-probe.cpp','Win64 VALID','Build.version','msiexec','/norestart','BuildToolsInstaller','EngineInstaller','UNREAL_NOT_FOUND','game_runtime_verified = $false'):
        assert value in text
    for value in ('Restart-Computer','Stop-Service','systemctl','Remove-Item -Recurse'):
        assert value not in text

def test_build_uses_real_platform_and_separate_configuration():
    text=(ROOT/'ops/workstation/build-unreal-win64.ps1').read_text()
    for value in ('RunUAT.bat','BuildCookRun','-platform=Win64','Development','Shipping','Get-FileHash','Win64 VALID','game_runtime_verified = $false'):
        assert value in text

def test_existing_d08_and_ledger_receive_current_setup_refs():
    guide=(ROOT/'projects/minitz-games/docs/task-guides/D08-01.md').read_text()
    assert 'setup-unreal-win64.ps1' in guide
    entry=next(x for x in json.loads((ROOT/'docs/task-program/D_NEXT_100_TASKS.json').read_text())['tasks'] if x['task_id']=='D08-01')
    refs={x['path']:x for x in entry['source_refs']}
    for name in ('setup-unreal-win64.ps1','build-unreal-win64.ps1','UNREAL_WIN64.md'):
        path='ops/workstation/'+name
        assert refs[path]['sha256']==hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    row=next(x for x in json.loads((ROOT/'docs/task-program/D_TASK_LEDGER.json').read_text())['tasks'] if x['task_id']=='D08-01')
    assert row['execution']['source_refs']==entry['source_refs']
    assert row['status_source'] == 'projects/minitz-games/docs/PRODUCTION.md'

def test_nsis_does_not_become_win64_compiler():
    registry=json.loads((ROOT/'ops/workstation/provider-registry.json').read_text())
    assert 'nsis' not in registry['routes'].get('unreal.build.win64',[])
