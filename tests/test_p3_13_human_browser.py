"""Task-specific qualification for authenticated human browser work."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping

import pytest

from minitz_os.engine import (
    HumanActionType,
    HumanBoundaryReason,
    HumanBoundaryRequiredError,
    HumanBrowserAction,
    HumanBrowserPolicyError,
    HumanBrowserService,
    HumanBrowserStatus,
    OwnerAttentionAudio,
)


def _service(tmp_path: Path, provider: object | None = None) -> HumanBrowserService:
    return HumanBrowserService(
        tmp_path / "state.sqlite3",
        tmp_path / "profiles",
        OwnerAttentionAudio(tmp_path / "attention"),
        provider=provider,  # type: ignore[arg-type]
    )


def _open(service: HumanBrowserService) -> object:
    return service.open_session(
        task_ref="task://minitz/MINITZ-BROWSER-HUMAN-01/2",
        run_ref="run://minitz/browser-human/1",
        profile_ref="browser-profile://minitz/task-local",
        allowed_origins=("https://example.invalid",),
        credential_refs=("secret://credential/example-login",),
    )


def test_isolated_profile_persists_and_resumes_same_task_run(tmp_path: Path) -> None:
    first = _service(tmp_path)
    session = _open(first)
    assert session.status is HumanBrowserStatus.ACTIVE
    assert Path(session.profile_path).is_dir()
    assert session.foreground_browser is False
    assert session.credential_refs == ("secret://credential/example-login",)

    second = _service(tmp_path)
    resumed = second.open_session(
        task_ref=session.task_ref,
        run_ref=session.run_ref,
        profile_ref=session.profile_ref,
        allowed_origins=session.allowed_origins,
        credential_refs=session.credential_refs,
        session_ref=session.session_ref,
    )
    assert resumed.session_ref == session.session_ref
    assert resumed.task_ref == session.task_ref
    assert resumed.run_ref == session.run_ref
    assert resumed.profile_path == session.profile_path
    assert resumed.sequence > session.sequence


def test_foreground_patrick_and_raw_credentials_are_denied(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(HumanBrowserPolicyError):
        service.open_session(task_ref="task://x", run_ref="run://x", profile_ref="browser-profile://x", allowed_origins=("https://example.invalid",), owner_profile="Patrick")
    with pytest.raises(HumanBrowserPolicyError):
        service.open_session(task_ref="task://x", run_ref="run://x", profile_ref="browser-profile://x2", allowed_origins=("https://example.invalid",), foreground_browser=True)
    with pytest.raises(ValueError):
        service.open_session(task_ref="task://x", run_ref="run://x", profile_ref="browser-profile://x3", allowed_origins=("https://example.invalid",), credential_refs=("invalid-credential-input",))


def test_persistent_profile_cannot_cross_task_or_run(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _open(service)
    with pytest.raises(HumanBrowserPolicyError):
        service.open_session(
            task_ref="task://minitz/other/1",
            run_ref="run://minitz/other/1",
            profile_ref="browser-profile://minitz/task-local",
            allowed_origins=("https://example.invalid",),
        )


def test_contextual_action_requires_verified_readback_and_denies_financial_surface(tmp_path: Path) -> None:
    service = _service(tmp_path)
    session = _open(service)
    result = service.execute(HumanBrowserAction(
        action_ref="browser-action://minitz/fill-1",
        session_ref=session.session_ref,
        action_type=HumanActionType.FILL,
        label="Email address",
        value_ref="secret://credential/example-login-email",
        context={"purpose": "sign-in", "form": "account"},
    ))
    assert result.verified is True
    assert result.status.value == "SUCCEEDED"
    assert result.readback["interaction"] == "contextual-fill"
    with pytest.raises(HumanBrowserPolicyError):
        service.execute(HumanBrowserAction(
            action_ref="browser-action://minitz/payment-1",
            session_ref=session.session_ref,
            action_type=HumanActionType.NAVIGATE,
            url="https://billing.example.invalid/checkout",
        ))


class _BoundaryProvider:
    def open(self, session: object, *, resume: bool) -> str:
        return "boundary-provider"

    def execute(self, session: object, action: HumanBrowserAction) -> Mapping[str, object]:
        return {"verified": False, "human_boundary": "TWO_FACTOR", "interaction": "provider-paused"}


def test_human_boundary_audio_pause_and_resume_preserve_identity(tmp_path: Path) -> None:
    service = _service(tmp_path, _BoundaryProvider())
    session = _open(service)
    action = HumanBrowserAction(
        action_ref="browser-action://minitz/two-factor-1",
        session_ref=session.session_ref,
        action_type=HumanActionType.OBSERVE,
    )
    result = service.execute(action)
    assert result.status.value == "NEEDS_HUMAN"
    assert result.boundary_ref is not None
    paused = service.get_session(session.session_ref)
    assert paused.status is HumanBrowserStatus.PAUSED
    with pytest.raises(HumanBoundaryRequiredError):
        service.execute(action)
    resumed = service.resume_after_human(result.boundary_ref)
    assert resumed.status is HumanBrowserStatus.ACTIVE
    assert resumed.session_ref == session.session_ref
    assert resumed.task_ref == session.task_ref
    assert resumed.run_ref == session.run_ref
    audio_files = list((tmp_path / "attention").glob("*.wav"))
    assert len(audio_files) == 1
    assert audio_files[0].read_bytes()[:4] == b"RIFF"


def test_upload_and_download_require_digest_verified_readback(tmp_path: Path) -> None:
    service = _service(tmp_path)
    session = _open(service)
    source = tmp_path / "source.txt"
    source.write_bytes(b"task-scoped artifact")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    uploaded = service.upload(session.session_ref, source, lambda payload: {"verified": True, "content_sha256": hashlib.sha256(payload).hexdigest()})
    assert uploaded.operation == "upload"
    assert uploaded.content_sha256 == digest
    target = tmp_path / "downloads" / "result.txt"
    downloaded = service.download(session.session_ref, target, lambda: b"verified result", expected_sha256=hashlib.sha256(b"verified result").hexdigest())
    assert downloaded.operation == "download"
    assert target.read_bytes() == b"verified result"
