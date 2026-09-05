"""Author and verify D01-42 native candidates before replacing canonical assets.

python3 Content/Python/run_demo_feedback_vfx_authoring.py --rebuild
python3 Content/Python/run_demo_feedback_vfx_authoring.py --verify

A temporary moduleless editor context avoids gameplay CDO-rooted assets and
Niagara delete/recreate name collisions. It authors the same /Game/Feedback
package names in empty temporary Content, reads them back in a fresh process,
then copies only the three verified task assets to canonical Content. There is
no second production project, controller, or retained source/asset authority.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile

ASSETS = ['M_FeedbackParticle.uasset', 'NS_Muzzle.uasset', 'NS_Impact.uasset']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--rebuild', action='store_true')
    mode.add_argument('--verify', action='store_true')
    parser.add_argument('--engine', type=Path, default=Path('/opt/unreal/UE_5.8.2'))
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[2]
    destination = project / 'Content/Feedback'
    script = project / 'Content/Python/build_demo_feedback_vfx.py'
    prefix = ['runuser', '-u', 'unreal', '--'] if os.geteuid() == 0 else []
    common = ['-unattended', '-nullrhi', '-nosound', '-nop4', '-stdout', '-FullStdOutLogOutput']
    def verify(editor_project):
        return subprocess.run(prefix + [str(args.engine / 'Engine/Binaries/Linux/UnrealEditor-Cmd'),
            str(editor_project), '-run=pythonscript', '-script=' + str(script),
            '-EnablePlugins=PythonScriptPlugin', '-D01VerifyFeedbackVFX'] + common, check=False).returncode
    if args.verify:
        return verify(project / 'BiellaGames.uproject')
    if not args.rebuild and all((destination / name).exists() for name in ASSETS):
        return verify(project / 'BiellaGames.uproject')
    with tempfile.TemporaryDirectory(prefix='biella-d01-042-vfx-authoring-') as folder:
        transient = Path(folder)
        content = transient / 'Content/Feedback'
        content.mkdir(parents=True)
        for directory in [transient, transient / 'Content', content]:
            if os.geteuid() == 0:
                account = pwd.getpwnam('unreal')
                os.chown(directory, account.pw_uid, account.pw_gid)
            directory.chmod(0o755)
        editor_project = transient / 'BiellaVFXAuthoring.uproject'
        editor_project.write_text(json.dumps({'FileVersion': 3, 'Plugins': [
            {'Name': name, 'Enabled': True} for name in ['Niagara', 'PythonScriptPlugin']]}, indent=2) + '\n')
        editor_project.chmod(0o644)
        command = prefix + ['xvfb-run', '-a', '-s', '-screen 0 1280x720x24',
            str(args.engine / 'Engine/Binaries/Linux/UnrealEditor'), str(editor_project),
            '-ExecutePythonScript=' + str(script),
            '-EnablePlugins=PythonScriptPlugin,CascadeToNiagaraConverter'] + common
        result = subprocess.run(command, check=False).returncode
        print('D01_042_VFX_AUTHOR_PROCESS_EXIT=' + str(result), flush=True)
        # The observed Linux editor allocator teardown failure occurs after saves.
        # Preserve that result; require independent candidate readback before copy.
        if result not in (0, 139) or not all((content / name).exists() for name in ASSETS):
            return result or 1
        verified = verify(editor_project)
        if verified:
            return verified
        destination.mkdir(parents=True, exist_ok=True)
        for name in ASSETS:
            target = destination / name
            if target.exists() and not args.rebuild:
                continue
            staging = destination / (name + '.d01-042-tmp')
            shutil.copyfile(content / name, staging)
            staging.chmod(0o644)
            os.replace(staging, target)
        return verify(project / 'BiellaGames.uproject')


if __name__ == '__main__':
    raise SystemExit(main())
