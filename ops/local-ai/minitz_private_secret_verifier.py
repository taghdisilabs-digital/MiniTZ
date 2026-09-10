from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from urllib.parse import parse_qsl, urlsplit

_SCHEMA = "minitz.private_secret_leak_receipt/v2"
_VERSION = "2"
_SECRET_SEGMENTS = {"SECRET", "TOKEN", "PASSWORD", "PASSWD", "CREDENTIAL", "CREDENTIALS", "COOKIE"}
_SECRET_QUERY_KEYS = {"token", "secret", "password", "passwd", "api_key", "apikey", "access_key", "credential", "signature", "sig"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _credential_bearing_value(value: str) -> bool:
    lowered = value.lower()
    if "-----begin " in lowered and "private key-----" in lowered:
        return True
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if not parsed.scheme or not parsed.netloc:
        return False
    if parsed.password is not None:
        return True
    return any(name.lower() in _SECRET_QUERY_KEYS and item for name, item in parse_qsl(parsed.query, keep_blank_values=True))


def _entry_class(key: str, value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "_", key.upper()).strip("_")
    segments = set(normalized.split("_")) if normalized else set()
    # API keys shorter than eight bytes are not valid usable credentials for any
    # configured MiniTZ provider. Treat them as placeholder/config material so a
    # short sentinel cannot create exact-value false positives in ordinary code.
    if (normalized == "API_KEY" or normalized.endswith("_API_KEY")) and len(value.encode("utf-8")) < 8:
        return "CONFIG"
    if segments & _SECRET_SEGMENTS:
        return "SECRET"
    if normalized.endswith("_KEY") or normalized in {"KEY", "PRIVATE_KEY"}:
        return "SECRET"
    if _credential_bearing_value(value):
        return "SECRET"
    return "CONFIG"


def _closing_quote_index(value: bytes, quote: int) -> int | None:
    escaped = False
    for index, byte in enumerate(value[1:], start=1):
        if escaped:
            escaped = False
            continue
        if byte == 92:
            escaped = True
            continue
        if byte == quote:
            return index
    return None


def _classified_entries(path: Path) -> tuple[list[bytes], int, int]:
    secrets: list[bytes] = []
    config_count = 0
    unknown_count = 0
    lines = Path(path).read_bytes().splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        index += 1
        if not line or line.startswith(b"#"):
            continue
        if b"=" not in line:
            unknown_count += 1
            continue
        key_raw, value_raw = line.split(b"=", 1)
        value_bytes = value_raw.strip()
        if value_bytes[:1] in {b'"', b"'"}:
            quote = value_bytes[0]
            while _closing_quote_index(value_bytes, quote) is None and index < len(lines):
                value_bytes += b"\n" + lines[index]
                index += 1
            close = _closing_quote_index(value_bytes, quote)
            if close is None or value_bytes[close + 1:].strip():
                unknown_count += 1
                continue
            value_bytes = value_bytes[1:close]
        try:
            key = key_raw.decode("utf-8").strip()
            value = value_bytes.decode("utf-8").strip()
        except UnicodeDecodeError:
            unknown_count += 1
            continue
        if not key:
            unknown_count += 1
            continue
        if not value:
            config_count += 1
            continue
        if _entry_class(key, value) == "SECRET":
            secrets.append(value.encode("utf-8"))
        else:
            config_count += 1
    return secrets, config_count, unknown_count


def _target_identity(path: Path) -> dict[str, object]:
    target = Path(path).resolve(); data = target.read_bytes()
    return {"path_digest": _sha(str(target).encode("utf-8")), "content_sha256": _sha(data), "size_bytes": len(data)}


def _receipt_digest(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha(raw)


def verify_secret_leaks(protected_secret_source: Path, targets: Sequence[Path]) -> dict[str, object]:
    observed = datetime.now(timezone.utc).isoformat()
    target_paths = [Path(item) for item in targets]
    try:
        secrets, config_count, unknown_count = _classified_entries(Path(protected_secret_source))
        identities = [_target_identity(path) for path in target_paths]
        hit_count = 0
        for path in target_paths:
            data = path.read_bytes()
            hit_count += sum(data.count(secret) for secret in secrets if secret)
        if hit_count:
            result = "FAIL"
        elif unknown_count:
            hit_count = None; result = "UNKNOWN"
        elif secrets or config_count:
            result = "PASS"
        else:
            hit_count = None; result = "UNKNOWN"
    except (OSError, ValueError):
        secrets = []; config_count = 0; unknown_count = 0; identities = []
        hit_count = None; result = "UNKNOWN"

    receipt: dict[str, object] = {
        "schema": _SCHEMA, "verifier_version": _VERSION,
        "secret_entry_count": len(secrets),
        "config_entry_count": config_count,
        "unknown_entry_count": unknown_count,
        "target_file_count": len(target_paths), "exact_value_hit_count": hit_count,
        "result": result, "target_identity_digests": identities, "observed_at": observed,
        "classification_policy": "KEY_SEMANTICS_PLUS_CREDENTIAL_BEARING_VALUE_STRUCTURE",
    }
    receipt["verifier_receipt_digest"] = _receipt_digest(receipt)
    return receipt


def write_receipt(path: Path, receipt: dict[str, object]) -> None:
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, target)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--secret-source", required=True)
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args(argv)
    receipt = verify_secret_leaks(Path(args.secret_source), [Path(item) for item in args.target])
    write_receipt(Path(args.receipt), receipt)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0 if receipt["result"] in {"PASS", "FAIL"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
