#!/usr/bin/env python3
"""Restore omitted Linux build dependencies without replacing installed UE headers.

Inputs are the digest-verified upstream archives preserved with D03 evidence.
This affects the local engine build support only, not gameplay or asset sources.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
from run_d01_039 import file_identity, write_json

ENGINE = Path('/opt/unreal/UE_5.8.2/Engine')
SDK = ENGINE/'Extras/ThirdPartyNotUE/SDKs/HostLinux/Linux_x64/v26_clang-20.1.8-rockylinux8/x86_64-unknown-linux-gnu'
ARCHIVES = {
    'mimalloc-v2.0.0.tar.gz': 'f6d01c178f8094a0d986642ca7fed632997a5606ddc619619225f2f8688d9232',
    'libsamplerate-0.2.2.tar.gz': '16e881487f184250deb4fcb60432d7556ab12cb58caea71ef23960aec6c0405a',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archives', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out, work = args.output.resolve(), args.workspace.resolve()
    out.mkdir(parents=True, exist_ok=False)
    work.mkdir(parents=True, exist_ok=False)
    report = dict(task_id='D03-01', result='FAIL', added_files=[])
    write_json(out/'validation.json', report)
    try:
        for name, digest in ARCHIVES.items():
            path = args.archives/name
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, f'Archive mismatch: {name}'
            with tarfile.open(path) as archive:
                archive.extractall(work, filter='data')
        mimalloc = ENGINE/'Source/ThirdParty/mimalloc/2.0.0'
        report['mimalloc_existing_before'] = [file_identity(f) for f in sorted(mimalloc.rglob('*')) if f.is_file()]
        for source in sorted((work/'mimalloc-2.0.0/src').rglob('*')):
            if not source.is_file():
                continue
            target = mimalloc/'src'/source.relative_to(work/'mimalloc-2.0.0/src')
            if target.exists():
                assert target.read_bytes() == source.read_bytes(), f'Existing source differs; preserve it: {target}'
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                report['added_files'].append(file_identity(target))
        for item in report['mimalloc_existing_before']:
            assert file_identity(Path(item['path'])) == item, 'Installed mimalloc header/source changed'
        build = work/'samplerate-build'
        commands = [
            ['cmake', '-S', str(work/'libsamplerate-0.2.2'), '-B', str(build),
             f'-DCMAKE_C_COMPILER={SDK}/bin/clang', f'-DCMAKE_SYSROOT={SDK}',
             f'-DCMAKE_FIND_ROOT_PATH={SDK}', '-DCMAKE_FIND_ROOT_PATH_MODE_LIBRARY=ONLY',
             '-DCMAKE_FIND_ROOT_PATH_MODE_INCLUDE=ONLY', '-DCMAKE_C_FLAGS=-fPIC',
             '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_SHARED_LIBS=OFF', '-DBUILD_TESTING=ON',
             '-DLIBSAMPLERATE_EXAMPLES=OFF', '-DLIBSAMPLERATE_INSTALL=OFF'],
            ['cmake', '--build', str(build), '-j', '8'],
            ['ctest', '--test-dir', str(build), '--output-on-failure'],
        ]
        write_json(out/'commands.json', commands)
        for index, command in enumerate(commands):
            with (out/f'step-{index}.log').open('xb') as stream:
                result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
            assert result.returncode == 0, f'Toolchain dependency step {index} failed'
        module = ENGINE/'Source/ThirdParty/libSampleRate'
        target_root = module/'D03Linux'
        assert not target_root.exists(), 'Preserve an existing repair; verify its receipt instead of replacing it'
        target_root.mkdir()
        for source in (work/'libsamplerate-0.2.2/include/samplerate.h', build/'src/libsamplerate.a',
                       work/'libsamplerate-0.2.2/COPYING'):
            shutil.copy2(source, target_root/source.name)
            report['added_files'].append(file_identity(target_root/source.name))
        rules = module/'UElibSampleRate.Build.cs'
        report['rules_before'] = file_identity(rules)
        shutil.copy2(rules, out/'UElibSampleRate.Build.cs.before')
        original = rules.read_text()
        anchor = '\t\tIWYUSupport = IWYUSupport.None;'
        assert original.count(anchor) == 1 and 'D03Linux' not in original, 'Unexpected engine module rules; preserve for diagnosis'
        addition = '''
		// D03-01: source distributions omit libsamplerate headers/objects.
		// Link the verified static Linux dependency built with this engine SDK.
		if (Target.Platform == UnrealTargetPlatform.Linux)
		{
			PublicSystemIncludePaths.Add(System.IO.Path.Combine(ModuleDirectory, "D03Linux"));
			PublicAdditionalLibraries.Add(System.IO.Path.Combine(ModuleDirectory, "D03Linux", "libsamplerate.a"));
		}
'''
        rules.write_text(original.replace(anchor, anchor+addition))
        report['rules_after'] = file_identity(rules)
        shutil.copy2(rules, out/'UElibSampleRate.Build.cs.after')
        report['mimalloc_existing_after'] = [file_identity(Path(item['path'])) for item in report['mimalloc_existing_before']]
        report['licenses'] = []
        for name, source in [('mimalloc-LICENSE.txt', work/'mimalloc-2.0.0/LICENSE'),
                             ('libsamplerate-COPYING.txt', work/'libsamplerate-0.2.2/COPYING')]:
            shutil.copy2(source, out/name)
            report['licenses'].append(file_identity(out/name))
        report['result'] = 'PASS'
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        report['error'] = str(error)
    finally:
        write_json(out/'validation.json', report)
    print(json.dumps(dict(result=report['result'], output=str(out), error=report.get('error'))))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
