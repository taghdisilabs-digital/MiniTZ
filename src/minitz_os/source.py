"""One content identity for canonical source, installed runtime and release.

An installed release is a derived immutable artifact, never another editable
Project Source library. Private state and credential stores are not source.
"""
from __future__ import annotations
import gzip
import hashlib
import hmac
import io
import json
import os
import re
import tarfile
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

CODE_ROOTS = ("src", "ops/local-ai", "ops/control_gateway", "ops/workstation", "ops/project-cell", "ops/connectors")
SUFFIXES = {".py", ".sh", ".service", ".target"}
EXTRA = ("pyproject.toml", "ops/workstation/provider-registry.json", "ops/workstation/minitz-gpu-residency.json",
         "ops/workstation/AGENTS.md", "ops/workstation/minitz-os-sandbox/Dockerfile",
         "ops/workstation/minitz-os-sandbox/ImageRootfs.Dockerfile",
         "ops/workstation/minitz-os-sandbox/preinstall.json",
         "ops/workstation/minitz-os-sandbox/accessibility-profile.json",
         "ops/project-cell/minitz-project-cell", "ops/project-cell/minitz-project-cell-contract.yaml")
PRIVATE = {".git", "__pycache__", ".venv", ".pytest_cache", "credentials", "state", "cache", "sessions"}
SECRET = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_REFERENCE = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_CONTINUITY_SCHEMA = "minitz.runtime-continuity/v1"
_INSTALL_STATE = "minitz-install.json"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _digest(value: object, field: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"{field} must be a SHA-256 digest")
    return value


def _key_bytes(value: bytes | bytearray | memoryview, field: str = "signing key") -> bytes:
    key = bytes(value)
    if len(key) < 16:
        raise ValueError(f"{field} is too short")
    return key


def _reference(value: object, field: str) -> str:
    if not isinstance(value, str) or _REFERENCE.fullmatch(value) is None:
        raise ValueError(f"{field} must be an absolute reference")
    return value


def _safe_continuity(value: object, path: str = "continuity") -> object:
    """Keep restart metadata useful while excluding raw credentials."""
    if value is None or isinstance(value, (bool, int, float)):
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            raise ValueError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, str):
        if len(value) > 4096 or SECRET.search(value.encode()):
            raise ValueError(f"{path} contains credential material")
        return value
    if isinstance(value, Mapping):
        if len(value) > 128:
            raise ValueError(f"{path} is too large")
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.-]{0,127}", key):
                raise ValueError(f"{path} has a malformed key")
            if key.lower() in {"api_key", "apikey", "password", "passwd", "secret", "token", "authorization"}:
                raise ValueError(f"{path}.{key} is a credential field")
            result[key] = _safe_continuity(item, f"{path}.{key}")
        return result
    if isinstance(value, (list, tuple)):
        if len(value) > 128:
            raise ValueError(f"{path} is too large")
        return [_safe_continuity(item, f"{path}[{index}]") for index, item in enumerate(value)]
    raise ValueError(f"{path} is not JSON-compatible")


def _atomic_json(path: Path, value: Mapping[str, object], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(canonical(value) + b"\n")
    temporary.chmod(mode)
    with temporary.open("rb") as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _install_state_path(system_root: Path) -> Path:
    return Path(system_root) / "state" / _INSTALL_STATE


def _read_install_state(system_root: Path) -> dict[str, Any]:
    path = _install_state_path(system_root)
    if not path.is_file():
        return {"schema": "minitz.install-state/v1", "active_source_sha256": None, "history": []}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("managed installation state is unreadable") from exc
    if not isinstance(state, dict) or state.get("schema") != "minitz.install-state/v1":
        raise ValueError("managed installation state contract mismatch")
    active = state.get("active_source_sha256")
    if active is not None:
        _digest(active, "active_source_sha256")
    artifact = state.get("active_artifact_sha256")
    if artifact is not None:
        _digest(artifact, "active_artifact_sha256")
    history = state.get("history", [])
    if not isinstance(history, list) or any(not isinstance(item, str) or _DIGEST.fullmatch(item) is None for item in history):
        raise ValueError("managed installation history is invalid")
    return state


def _continuity_path(system_root: Path) -> Path:
    return Path(system_root) / "state" / "continuity.json"


def source_manifest(root: Path) -> dict[str, Any]:
    root=Path(root).resolve()
    selected: set[str] = set()
    for name in CODE_ROOTS:
        base=root/name
        if not base.is_dir():
            continue
        for current, dirs, walk_files in os.walk(base, followlinks=False):
            for name in list(dirs):
                child=Path(current)/name
                if child.is_symlink():
                    raise ValueError("source symlink directory is not a distributable component: "+str(child.relative_to(root)))
            dirs[:]=[name for name in dirs if name not in PRIVATE]
            for name in walk_files:
                path=Path(current)/name
                if path.suffix in SUFFIXES or (not path.suffix and path.stat().st_mode & 0o111):
                    selected.add(path.relative_to(root).as_posix())
    selected.update(name for name in EXTRA if (root/name).is_file())
    if not selected:
        raise ValueError("source tree is empty")
    files: dict[str, dict[str, Any]] = {}
    for relative in sorted(selected):
        path=root/relative
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("source symlink crosses the canonical library: "+relative)
        raw=path.read_bytes()
        if SECRET.search(raw):
            raise ValueError("credential material blocks source distribution: "+relative)
        files[relative]={"sha256":hashlib.sha256(raw).hexdigest(), "size":len(raw),
                         "mode":0o755 if path.stat().st_mode & 0o111 else 0o644}
    identity={"schema":"minitz.source-content/v1", "files":files}
    return {"schema":"minitz.source-release/v1", "product":"MiniTZ OS",
        "source_authority":"source-library://minitz/main", "source_sha256":hashlib.sha256(canonical(identity)).hexdigest(),
        "base_os":"Ubuntu 26.04", "artifact_kind":"BOOTABLE_DISK_IMAGE",
        "bootable_disk_image":True, "installed_source_root":"/opt/minitz/source", "files":files,
        "private_state_included":False, "credential_values_included":False,
        "component_provenance":{"src/minitz_os/engine":"MiniTZ capability implementation package; predecessor provenance is retained only under docs/provenance",
                                "ops/local-ai":"Validated mechanisms are reused under MiniTZ control; no provider task authority"}}


def verify_source(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    root=Path(root).resolve()
    if manifest.get("schema")!="minitz.source-release/v1" or manifest.get("product")!="MiniTZ OS":
        raise ValueError("source release contract mismatch")
    rows=manifest.get("files")
    if not isinstance(rows,dict) or not rows:
        raise ValueError("source file manifest absent")
    expected=hashlib.sha256(canonical({"schema":"minitz.source-content/v1","files":rows})).hexdigest()
    if expected!=manifest.get("source_sha256"):
        raise ValueError("source manifest identity mismatch")
    for relative, record in rows.items():
        path=root/relative
        if Path(relative).is_absolute() or ".." in Path(relative).parts or path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("source member escapes the installed library")
        if not path.is_file() or sha(path)!=record["sha256"] or path.stat().st_size!=record["size"]:
            raise ValueError("source bytes mismatch: "+relative)
    if source_manifest(root)["source_sha256"] != expected:
        raise ValueError("source tree has unexpected files or mode changes")
    return {"verified":True, "product":"MiniTZ OS", "source_sha256":expected, "verified_files":len(rows)}


def build_release(root: Path, output: Path) -> dict[str, Any]:
    root=Path(root).resolve(); output=Path(output).resolve()
    manifest=source_manifest(root)
    release=output/manifest["source_sha256"]
    release.mkdir(parents=True,exist_ok=True)
    artifact=release/("MiniTZ-OS-"+manifest["source_sha256"][:16]+"-sandbox-runtime.tar.gz")
    receipt_path=release/"release.json"
    try:
        prior=json.loads(receipt_path.read_text())
        if prior.get("source_sha256")==manifest["source_sha256"] and artifact.is_file() and sha(artifact)==prior.get("artifact_sha256"):
            return {**prior,"cache_hit":True,"artifact_path":str(artifact)}
    except (OSError,ValueError):
        pass
    launcher=b'#!/bin/sh\nexport MINITZ_SOURCE_ROOT=/opt/minitz/source\nexport PYTHONPATH="$MINITZ_SOURCE_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"\nexec python3 -m minitz_os "$@"\n'
    fd,name=tempfile.mkstemp(prefix="minitz-rootfs-",suffix=".tmp",dir=release)
    try:
        with os.fdopen(fd,"wb") as stream:
            with gzip.GzipFile(filename="",mode="wb",fileobj=stream,mtime=0) as compressed:
                with tarfile.open(fileobj=compressed,mode="w",format=tarfile.PAX_FORMAT) as archive:
                    def add(member: str, data: bytes, mode: int) -> None:
                        info=tarfile.TarInfo(member); info.size=len(data); info.mode=mode
                        info.mtime=0; info.uid=info.gid=0; info.uname=info.gname=""
                        archive.addfile(info,io.BytesIO(data))
                    for relative,record in manifest["files"].items():
                        raw=(root/relative).read_bytes()
                        if hashlib.sha256(raw).hexdigest()!=record["sha256"]:
                            raise ValueError("source changed while packaging: "+relative)
                        add("opt/minitz/source/"+relative,raw,record["mode"])
                    add("etc/minitz/source.json",canonical(manifest)+b"\n",0o644)
                    add("usr/bin/minitz",launcher,0o755)
            stream.flush();os.fsync(stream.fileno())
        os.replace(name,artifact)
    finally:
        Path(name).unlink(missing_ok=True)
    result={"schema":"minitz.release-artifact/v1","product":"MiniTZ OS", "artifact_kind":"SOURCE_PAYLOAD",
        "bootable_disk_image":False,"final_release_target":"BOOTABLE_DISK_IMAGE",
        "source_sha256":manifest["source_sha256"],"source_files":len(manifest["files"]),
        "artifact_sha256":sha(artifact),"artifact_path":str(artifact),"cache_hit":False}
    receipt_path.write_bytes(canonical(result)+b"\n")
    (release/"source.json").write_bytes(canonical(manifest)+b"\n")
    return result


def _signed_payload(artifact_sha256: str, source_sha256: str) -> bytes:
    return canonical({
        "schema": "minitz.signed-update/v1",
        "product": "MiniTZ OS",
        "artifact_sha256": _digest(artifact_sha256, "artifact_sha256"),
        "source_sha256": _digest(source_sha256, "source_sha256"),
    })


def sign_release(
    artifact: Path,
    source_sha256: str,
    signing_key: bytes | bytearray | memoryview,
    *,
    key_ref: str = "credential://minitz/update-signing-key",
) -> dict[str, Any]:
    """Create a portable, digest-bound update receipt.

    The key is consumed by the credential boundary and is never written to the
    receipt. HMAC-SHA256 is used here because the MiniTZ base install has no
    third-party crypto dependency; deployment may provide the key through its
    credential Resource.
    """
    artifact = Path(artifact).resolve()
    if not artifact.is_file():
        raise ValueError("update artifact is unavailable")
    key_ref = _reference(key_ref, "key_ref")
    artifact_sha256 = sha(artifact)
    payload = _signed_payload(artifact_sha256, source_sha256)
    signature = hmac.new(_key_bytes(signing_key), payload, hashlib.sha256).hexdigest()
    return {
        "schema": "minitz.signed-update/v1",
        "product": "MiniTZ OS",
        "signature_algorithm": "HMAC-SHA256",
        "key_ref": key_ref,
        "artifact_path": str(artifact),
        "artifact_sha256": artifact_sha256,
        "source_sha256": _digest(source_sha256, "source_sha256"),
        "signature_hex": signature,
    }


def verify_signed_release(
    update: Mapping[str, object] | Path,
    artifact: Path | None,
    verification_key: bytes | bytearray | memoryview,
) -> dict[str, Any]:
    """Verify the update receipt before any installed generation is touched."""
    if isinstance(update, Path):
        try:
            update_value = json.loads(update.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError("signed update receipt is unreadable") from exc
    else:
        update_value = dict(update)
    if update_value.get("schema") != "minitz.signed-update/v1" or update_value.get("product") != "MiniTZ OS":
        raise ValueError("signed update contract mismatch")
    if update_value.get("signature_algorithm") != "HMAC-SHA256":
        raise ValueError("unsupported update signature algorithm")
    source_sha256 = _digest(update_value.get("source_sha256"), "source_sha256")
    artifact_sha256 = _digest(update_value.get("artifact_sha256"), "artifact_sha256")
    signature = update_value.get("signature_hex")
    if not isinstance(signature, str) or re.fullmatch(r"[0-9a-f]{64}", signature) is None:
        raise ValueError("signed update signature is malformed")
    candidate = Path(artifact).resolve() if artifact is not None else Path(str(update_value.get("artifact_path", ""))).resolve()
    if not candidate.is_file() or sha(candidate) != artifact_sha256:
        raise ValueError("signed update artifact digest mismatch")
    expected = hmac.new(_key_bytes(verification_key), _signed_payload(artifact_sha256, source_sha256), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("signed update verification failed")
    return {
        "verified": True,
        "product": "MiniTZ OS",
        "artifact_path": str(candidate),
        "artifact_sha256": artifact_sha256,
        "source_sha256": source_sha256,
        "key_ref": _reference(update_value.get("key_ref"), "key_ref"),
    }


def build_signed_update(
    root: Path,
    output: Path,
    signing_key: bytes | bytearray | memoryview,
    *,
    key_ref: str = "credential://minitz/update-signing-key",
) -> dict[str, Any]:
    """Build and sign an update from the same canonical source release."""
    release = build_release(root, output)
    signed = sign_release(Path(release["artifact_path"]), release["source_sha256"], signing_key, key_ref=key_ref)
    receipt = Path(release["artifact_path"]).with_name("update.json")
    _atomic_json(receipt, signed, 0o644)
    return {**release, **signed, "update_path": str(receipt)}


def provision_first_boot(
    system_root: Path,
    *,
    task_state: object | None = None,
    memory_state: object | None = None,
    resource_state: object | None = None,
) -> dict[str, Any]:
    """Create durable first-boot continuity metadata without copying secrets."""
    system_root = Path(system_root).resolve()
    path = _continuity_path(system_root)
    if path.is_file():
        return read_continuity(system_root) | {"first_boot": False}
    task = _safe_continuity(task_state if task_state is not None else {
        "task_program_ref": os.environ.get("MINITZ_TASK_PROGRAM_PATH", "task://minitz/current-program"),
        "current_task_ref": "task://minitz/current",
    }, "task_state")
    memory = _safe_continuity(memory_state if memory_state is not None else {
        "current_task_ref": "memory://minitz/current-task",
        "os_index_ref": "memory://minitz/os-index",
    }, "memory_state")
    resources = _safe_continuity(resource_state if resource_state is not None else {
        "registry_ref": "resource://minitz/registry",
        "observations_ref": "resource://minitz/observations",
    }, "resource_state")
    record: dict[str, Any] = {
        "schema": _CONTINUITY_SCHEMA,
        "product": "MiniTZ OS",
        "authority": "MINITZ_TASK_PROGRAM_ONLY",
        "task_state": task,
        "memory_state": memory,
        "resource_state": resources,
        "source_root": "/opt/minitz/source",
        "private_state_root": str(system_root / "state"),
        "restart_policy": "REUSE_DURABLE_STATE",
    }
    record["continuity_sha256"] = hashlib.sha256(canonical(record)).hexdigest()
    _atomic_json(path, record)
    return record | {"first_boot": True}


def read_continuity(system_root: Path) -> dict[str, Any]:
    path = _continuity_path(Path(system_root).resolve())
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("MiniTZ continuity state is unavailable") from exc
    if not isinstance(value, dict) or value.get("schema") != _CONTINUITY_SCHEMA:
        raise ValueError("MiniTZ continuity state contract mismatch")
    digest = value.pop("continuity_sha256", None)
    expected = hashlib.sha256(canonical(value)).hexdigest()
    value["continuity_sha256"] = digest
    if digest != expected:
        raise ValueError("MiniTZ continuity state integrity mismatch")
    return value


def recover_installation(system_root: Path) -> dict[str, Any]:
    """Read back the active generation and continuity state after a restart."""
    system_root = Path(system_root).resolve()
    current = system_root / "current"
    if not current.is_symlink():
        raise ValueError("managed MiniTZ installation is not active")
    manifest_path = current / "etc/minitz/source.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verification = verify_source(current / "opt/minitz/source", manifest)
    state = _read_install_state(system_root)
    continuity = read_continuity(system_root)
    if state.get("active_source_sha256") != verification["source_sha256"]:
        raise ValueError("managed installation state does not match active source")
    return {"recovered": True, "source": verification, "install_state": state, "continuity": continuity}


def rollback_installation(system_root: Path) -> dict[str, Any]:
    """Atomically activate the most recent verified prior generation."""
    system_root = Path(system_root).resolve()
    state = _read_install_state(system_root)
    current = system_root / "current"
    if current.exists() and not current.is_symlink():
        raise ValueError("active installation is not a managed pointer")
    active = state.get("active_source_sha256")
    history = list(state.get("history", []))
    while history:
        target = history.pop()
        candidate = system_root / "releases" / target
        if candidate.is_dir():
            manifest_path = candidate / "etc/minitz/source.json"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                verify_source(candidate / "opt/minitz/source", manifest)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            link = system_root / (f".rollback-{os.getpid()}")
            try:
                link.symlink_to(Path("releases") / target, target_is_directory=True)
                os.replace(link, current)
            finally:
                link.unlink(missing_ok=True)
            if active and active != target:
                history.append(active)
            state["active_source_sha256"] = target
            state["active_artifact_sha256"] = None
            state["history"] = history[-16:]
            _atomic_json(_install_state_path(system_root), state)
            return {"rolled_back": True, "source_sha256": target, "active_pointer": str(current)}
    raise ValueError("no verified previous generation is available for rollback")


def apply_signed_update(
    update: Mapping[str, object] | Path,
    system_root: Path,
    verification_key: bytes | bytearray | memoryview,
    *,
    artifact: Path | None = None,
) -> dict[str, Any]:
    """Verify a signed update, then install its immutable generation."""
    verified = verify_signed_release(update, artifact, verification_key)
    return install_release(Path(verified["artifact_path"]), system_root, verified["artifact_sha256"], signed_update=verified)



def install_release(
    artifact: Path,
    system_root: Path,
    expected_sha256: str,
    *,
    signed_update: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Validate and install one immutable rootfs; switch one active pointer."""
    import shutil
    artifact=Path(artifact).resolve(); system_root=Path(system_root).resolve()
    if not artifact.is_file() or sha(artifact)!=expected_sha256:
        raise ValueError("artifact digest mismatch; active installation preserved")
    with tarfile.open(artifact,"r:gz") as archive:
        members=archive.getmembers()
        names=[member.name for member in members]
        if len(names)!=len(set(names)) or any(not member.isfile() for member in members):
            raise ValueError("artifact contains duplicate or non-regular members")
        try:
            manifest_file = archive.extractfile("etc/minitz/source.json")
            if manifest_file is None:
                raise ValueError("artifact lacks source manifest")
            manifest=json.loads(manifest_file.read())
        except (KeyError,ValueError,AttributeError):
            raise ValueError("artifact lacks source manifest") from None
        identity=manifest.get("source_sha256", "")
        if not re.fullmatch(r"[0-9a-f]{64}",identity):
            raise ValueError("artifact source identity invalid")
        if signed_update is not None:
            if signed_update.get("verified") is not True or signed_update.get("artifact_sha256") != expected_sha256 or signed_update.get("source_sha256") != identity:
                raise ValueError("signed update verification is required")
        allowed={"opt/minitz/source/"+name for name in manifest.get("files",{})} | {"etc/minitz/source.json","usr/bin/minitz"}
        if set(names)!=allowed:
            raise ValueError("artifact member set does not match manifest")
        for member in members:
            if Path(member.name).is_absolute() or ".." in Path(member.name).parts or member.mode not in {0o644,0o755}:
                raise ValueError("artifact member escapes install contract")
        releases=system_root/"releases";releases.mkdir(parents=True,exist_ok=True)
        final=releases/identity
        cache_hit=final.is_dir()
        if cache_hit:
            verify_source(final/"opt/minitz/source",manifest)
        else:
            staging=Path(tempfile.mkdtemp(prefix=".install-",dir=releases))
            try:
                for member in members:
                    destination=staging/member.name
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    member_source = archive.extractfile(member)
                    if member_source is None:
                        raise ValueError("artifact member has no payload")
                    with member_source as source,destination.open("wb") as target:
                        shutil.copyfileobj(source,target)
                    destination.chmod(member.mode)
                verify_source(staging/"opt/minitz/source",manifest)
                os.replace(staging,final)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
    state = _read_install_state(system_root)
    current=system_root/"current"
    if current.exists() and not current.is_symlink():
        raise ValueError("active installation is not a managed pointer")
    prior_active = state.get("active_source_sha256")
    if prior_active is None and current.is_symlink():
        prior_active = current.resolve().name
        if _DIGEST.fullmatch(prior_active) is None:
            raise ValueError("active installation identity is invalid")
    if prior_active is not None and current.is_symlink() and current.resolve().name != prior_active:
        raise ValueError("managed installation state does not match active pointer")
    continuity = provision_first_boot(system_root)
    if prior_active is not None and prior_active != identity:
        history = [item for item in state.get("history", []) if item != identity]
        history.append(prior_active)
        state["history"] = history[-16:]
    state["schema"] = "minitz.install-state/v1"
    state["active_source_sha256"] = identity
    state["active_artifact_sha256"] = expected_sha256
    link=system_root/(".activate-"+str(os.getpid()))
    try:
        link.symlink_to(Path("releases")/identity,target_is_directory=True)
        os.replace(link,current)
    finally:
        link.unlink(missing_ok=True)
    _atomic_json(_install_state_path(system_root), state)
    return {"product":"MiniTZ OS","source_sha256":identity,"artifact_sha256":expected_sha256,
            "installation_root":str(final),"active_pointer":str(current),"cache_hit":cache_hit,
            "verification":verify_source(current/"opt/minitz/source",manifest),
            "signed_update": signed_update is not None,
            "continuity": continuity,
            "restart": recover_installation(system_root)}
