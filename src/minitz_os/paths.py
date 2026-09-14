from __future__ import annotations
import os
from pathlib import Path

OS_ROOT = Path(os.environ.get("MINITZ_OS_ROOT", "/root/attached-storage/minitz-os-sandbox")).resolve()
SOURCE_ROOT = Path(os.environ.get("MINITZ_SOURCE_ROOT", str(OS_ROOT / "workspace/repo"))).resolve()
STATE_ROOT = Path(os.environ.get("MINITZ_STATE_ROOT", str(OS_ROOT / "state"))).resolve()
RUNTIME_ROOT = Path(os.environ.get("MINITZ_RUNTIME_ROOT", str(STATE_ROOT / "production"))).resolve()
TASK_PROGRAM_PATH = Path(os.environ.get("MINITZ_TASK_PROGRAM_PATH", str(STATE_ROOT / "task-program/TASK_PROGRAM.json"))).resolve()
CREDENTIAL_ROOT = Path(os.environ.get("MINITZ_CREDENTIAL_ROOT", str(STATE_ROOT / "credentials"))).resolve()
CONTROL_SITE_ROOT = Path(os.environ.get("MINITZ_CONTROL_SITE_ROOT", str(STATE_ROOT / "control/site"))).resolve()
CODEX_ACCOUNTS_ROOT = Path(os.environ.get("MINITZ_CODEX_ACCOUNTS_ROOT", str(CREDENTIAL_ROOT / "codex-accounts"))).resolve()
BOOST_ROOT = Path(os.environ.get("MINITZ_BOOST_ROOT", str(STATE_ROOT / "boost-work-program"))).resolve()
LOCAL_MODEL = str(os.environ.get("MINITZ_LOCAL_MODEL", "qwen3-coder-next:minitz")).strip()
