"""One content identity for canonical source, installed runtime and release.

An installed release is a derived immutable artifact, never another editable
Project Source library. Private state and credential stores are not source.
"""
from __future__ import annotations
import gzip
import hashlib
import io
import json
import os
import re
import tarfile
import tempfile
from pathlib import Path
from typing import Any

CODE_ROOTS = ("src", "ops/local-ai", "ops/control_gateway", "ops/workstation")
SUFFIXES = {".py", ".sh", ".service", ".target"}
EXTRA = ("pyproject.toml", "ops/workstation/provider-registry.json", "ops/workstation/minitz-gpu-residency.json",
         "ops/workstation/AGENTS.md", "ops/workstation/minitz-os-sandbox/Dockerfile",
         "ops/workstation/minitz-os-sandbox/ImageRootfs.Dockerfile")
PRIVATE = {".git", "__pycache__", ".venv", ".pytest_cache", "credentials", "state", "cache", "sessions"}
SECRET = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
                if path.suffix in SUFFIXES:
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
        "component_provenance":{"src/biella":"Donor implementation components, not a second product or authority",
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



def install_release(artifact: Path, system_root: Path, expected_sha256: str) -> dict[str, Any]:
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
    current=system_root/"current"
    if current.exists() and not current.is_symlink():
        raise ValueError("active installation is not a managed pointer")
    link=system_root/(".activate-"+str(os.getpid()))
    try:
        link.symlink_to(Path("releases")/identity,target_is_directory=True)
        os.replace(link,current)
    finally:
        link.unlink(missing_ok=True)
    return {"product":"MiniTZ OS","source_sha256":identity,"artifact_sha256":expected_sha256,
            "installation_root":str(final),"active_pointer":str(current),"cache_hit":cache_hit,
            "verification":verify_source(current/"opt/minitz/source",manifest)}
