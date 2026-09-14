from pathlib import Path
from minitz_os import paths


def test_default_paths_are_owned_by_attached_drive_minitz():
    root = Path('/root/attached-storage/minitz-os-sandbox')
    assert paths.OS_ROOT == root
    assert paths.SOURCE_ROOT == root / 'workspace/repo'
    assert paths.STATE_ROOT == root / 'state'
    assert paths.RUNTIME_ROOT == root / 'state/production'
    assert paths.TASK_PROGRAM_PATH == root / 'state/task-program/TASK_PROGRAM.json'
    assert paths.CREDENTIAL_ROOT == root / 'state/credentials'
    assert paths.LOCAL_MODEL == 'qwen3-coder-next:minitz'
    rendered='\n'.join(map(str,(paths.OS_ROOT,paths.SOURCE_ROOT,paths.STATE_ROOT,paths.RUNTIME_ROOT,paths.TASK_PROGRAM_PATH,paths.CREDENTIAL_ROOT)))
    assert '/root/minitz' not in rendered and '/mnt/minitz-extra' not in rendered
