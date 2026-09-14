from __future__ import annotations

import json
import os
from pathlib import Path
import zipfile


def _entry(name: str, payload: bytes) -> tuple[zipfile.ZipInfo, bytes]:
    info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    return info, payload


output = Path("dist/minitz-web-candidate.zip")
output.parent.mkdir(parents=True, exist_ok=True)
manifest = json.dumps(
    {
        "candidate_commit": os.environ["MINITZ_CANDIDATE_COMMIT"],
        "candidate_tree": os.environ["MINITZ_CANDIDATE_TREE"],
        "entrypoint": "server.py",
        "project": json.loads(Path("web-project.json").read_text(encoding="utf-8")),
    },
    sort_keys=True,
    separators=(",", ":"),
).encode()
with zipfile.ZipFile(output, "w") as archive:
    for name, payload in (
        ("manifest.json", manifest),
        ("server.py", Path("server.py").read_bytes()),
        ("web-project.json", Path("web-project.json").read_bytes()),
    ):
        info, content = _entry(name, payload)
        archive.writestr(info, content)
print(output.as_posix())
