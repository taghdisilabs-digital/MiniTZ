from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
from typing import Any


def _support() -> Any:
    path = Path(__file__).with_name("test_p3_12_audio_real.py")
    specification = importlib.util.spec_from_file_location("p3_12_audio_identity_support", path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_bound_audio_runtime_identity_matches_exact_executable_bytes(tmp_path: Path) -> None:
    support = _support()
    environment = support._environments(tmp_path)[0]
    dispatch = support._dispatch(environment)
    tool = support._tool(environment, dispatch)

    ffmpeg_sha256 = _sha256(Path("/usr/bin/ffmpeg"))
    ffprobe_sha256 = _sha256(Path("/usr/bin/ffprobe"))

    assert tool.tool_ref == f"tool://ffmpeg/sha256-{ffmpeg_sha256}"
    assert tool.runtime_ref == (
        f"runtime://audio/ffmpeg-sha256-{ffmpeg_sha256}-"
        f"ffprobe-sha256-{ffprobe_sha256}-cpu"
    )

    source = support._source(environment, support._wav())
    inspection = tool.inspect(source, "validator://audio/decode/v1")
    assert inspection.decoder == f"ffmpeg://sha256/{ffmpeg_sha256}/pcm_s16le"
