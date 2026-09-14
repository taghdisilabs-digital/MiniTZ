from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _minitz_external_resource_test_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression tests never spend external provider quota unless explicitly opted in."""
