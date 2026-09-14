#!/usr/bin/env python3
"""Enumerate the authenticated Saturn resources used by MiniTZ's MCP bridge."""

from __future__ import annotations

import dataclasses
import enum
import json
import sys
from typing import Any


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if dataclasses.is_dataclass(value):
        return jsonable(dataclasses.asdict(value))
    if isinstance(value, enum.Enum):
        return jsonable(value.value)
    for method_name in ("model_dump", "dict"):
        method = getattr(value, method_name, None)
        if callable(method):
            try:
                return jsonable(method())
            except TypeError:
                pass
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(item) for item in value]
    if hasattr(value, "__dict__"):
        return jsonable(vars(value))
    return str(value)


def main() -> int:
    try:
        from saturn_client import SaturnConnection
        from saturn_client.core import ServerOptionTypes
    except ImportError as exc:
        print(f"Saturn client import failed: {exc}", file=sys.stderr)
        return 2

    try:
        connection = SaturnConnection()
        resources = connection.list_resources()
        instance_types = connection.list_options(ServerOptionTypes.SIZES)
    except Exception as exc:  # The launcher reports this as a failed live probe.
        print(f"Saturn API enumeration failed: {exc}", file=sys.stderr)
        return 1

    json.dump(
        {
            "resources": jsonable(resources),
            "instance_types": jsonable(instance_types),
        },
        sys.stdout,
        indent=2,
        sort_keys=True,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
