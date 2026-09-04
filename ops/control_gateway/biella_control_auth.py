from __future__ import annotations

import getpass
import json
import os
import sys
from pathlib import Path

try:
    from .biella_control_gateway import password_record
except ImportError:
    from biella_control_gateway import password_record

DEFAULT_AUTH_FILE = Path("/root/.config/biella-control/auth.json")


def prompt_password(label: str) -> str:
    first = getpass.getpass(f"{label} password: ")
    second = getpass.getpass(f"Confirm {label} password: ")
    if first != second:
        raise SystemExit("passwords do not match")
    if len(first) < 12:
        raise SystemExit("password must be at least 12 characters")
    return first


def configure(path: Path) -> None:
    if os.geteuid() != 0:
        raise SystemExit("run as root")
    mahdi = prompt_password("mahdi/operator")
    patrick = prompt_password("patrick/observer")
    payload = {
        "schema": "biella-control-auth/v1",
        "users": {
            "mahdi": password_record(mahdi, "operator"),
            "patrick": password_record(patrick, "observer"),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.chmod(0o600)
    os.chown(tmp, 0, 0)
    tmp.replace(path)
    print("Biella control authentication configured.")


def status(path: Path) -> None:
    try:
        data = json.loads(path.read_text())
        users = data.get("users", {})
    except (OSError, json.JSONDecodeError):
        print("NOT_CONFIGURED")
        return
    for username in ("mahdi", "patrick"):
        role = users.get(username, {}).get("role")
        print(f"{username}={role or 'MISSING'}")


def main(argv: list[str]) -> int:
    path = Path(os.environ.get("BIELLA_CONTROL_AUTH_FILE", DEFAULT_AUTH_FILE))
    command = argv[1] if len(argv) > 1 else "status"
    if command == "configure":
        configure(path)
        return 0
    if command == "status":
        status(path)
        return 0
    print("usage: biella-control-auth [configure|status]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
