"""MiniTZ's native command surface for the managed sandbox environment."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence
from .operator import OperatorSurface, render_dashboard, render_doctor
from .source import (
    apply_signed_update,
    build_release,
    build_signed_update,
    install_release,
    provision_first_boot,
    recover_installation,
    rollback_installation,
    source_manifest,
    verify_source,
)


def source_root() -> Path:
    return Path(os.environ.get("MINITZ_SOURCE_ROOT",str(Path(__file__).resolve().parents[2]))).resolve()


def installed_identity(root: Path) -> dict[str, Any]:
    configured_manifest = os.environ.get("MINITZ_SOURCE_MANIFEST")
    path = Path(configured_manifest) if configured_manifest else None
    if path is None and root == Path("/opt/minitz/source"):
        path = Path("/etc/minitz/source.json")
    if path is not None and path.is_file():
        return verify_source(root,json.loads(path.read_text()))
    manifest=source_manifest(root)
    return {"verified":False,"state":"DEVELOPMENT_SOURCE_NOT_SEALED","product":"MiniTZ OS",
            "source_sha256":manifest["source_sha256"],"source_files":len(manifest["files"])}


def load_component(root: Path, relative: str, name: str) -> Any:
    path=root/relative
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise RuntimeError("MiniTZ component is missing: "+relative)
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value)
    return value


def key_bytes(path: Path) -> bytes:
    """Read a credential Resource without ever echoing its value."""
    value = path.read_bytes()
    if len(value) < 16:
        raise ValueError("update signing credential is unavailable")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser=argparse.ArgumentParser(prog="minitz",description="MiniTZ OS managed system")
    sub=parser.add_subparsers(dest="command",required=False)
    for name in ("source","status","capabilities","serve"):
        sub.add_parser(name)
    dashboard=sub.add_parser("dashboard", help="show the single normal-user MiniTZ surface")
    dashboard.add_argument("--json", action="store_true", help="emit the structured surface")
    surface=sub.add_parser("surface", help="alias for dashboard")
    surface.add_argument("--json", action="store_true", help="emit the structured surface")
    doctor=sub.add_parser("doctor", help="diagnose observed MiniTZ problems")
    doctor.add_argument("--json", action="store_true", help="emit the structured diagnostic report")
    build=sub.add_parser("build-release");build.add_argument("--output",type=Path,required=True)
    update=sub.add_parser("build-update");update.add_argument("--output",type=Path,required=True)
    update.add_argument("--key-file",type=Path,required=True);update.add_argument("--key-ref",default="credential://minitz/update-signing-key")
    install=sub.add_parser("install-release");install.add_argument("--artifact",type=Path,required=True)
    install.add_argument("--sha256",required=True);install.add_argument("--system-root",type=Path,required=True)
    first_boot=sub.add_parser("first-boot");first_boot.add_argument("--system-root",type=Path,required=True)
    apply_update=sub.add_parser("apply-update");apply_update.add_argument("--update",type=Path,required=True)
    apply_update.add_argument("--key-file",type=Path,required=True);apply_update.add_argument("--system-root",type=Path,required=True)
    rollback=sub.add_parser("rollback");rollback.add_argument("--system-root",type=Path,required=True)
    recover=sub.add_parser("recover");recover.add_argument("--system-root",type=Path,required=True)
    donor=sub.add_parser("donor-inventory");donor.add_argument("--donor",type=Path,required=True)
    donor.add_argument("--output",type=Path,required=True)
    resource=sub.add_parser("resource");resource.add_argument("arguments",nargs=argparse.REMAINDER)
    args=parser.parse_args(argv)
    root=source_root()
    for path in (root/"ops/local-ai",root/"ops/workstation",root/"ops/control_gateway"):
        sys.path.insert(0,str(path))
    if args.command in {None, "dashboard", "surface", "doctor"}:
        operator = OperatorSurface(
            root,
            Path(os.environ.get("MINITZ_STATE_ROOT", "/state")),
        )
        if args.command == "doctor":
            report = operator.doctor.report().as_dict()
            if getattr(args, "json", False):
                print(json.dumps(report, sort_keys=True, indent=2))
            else:
                print(render_doctor(report))
        else:
            snapshot = operator.snapshot()
            if getattr(args, "json", False):
                print(json.dumps(snapshot, sort_keys=True, indent=2))
            else:
                print(render_dashboard(snapshot))
        return 0
    identity=installed_identity(root)
    if args.command=="source":
        result=identity
    elif args.command=="build-release":
        result=build_release(root,args.output)
    elif args.command=="build-update":
        result=build_signed_update(root,args.output,key_bytes(args.key_file),key_ref=args.key_ref)
    elif args.command=="install-release":
        result=install_release(args.artifact,args.system_root,args.sha256)
    elif args.command=="first-boot":
        result=provision_first_boot(args.system_root)
    elif args.command=="apply-update":
        result=apply_signed_update(args.update,args.system_root,key_bytes(args.key_file))
    elif args.command=="rollback":
        result=rollback_installation(args.system_root)
    elif args.command=="recover":
        result=recover_installation(args.system_root)
    elif args.command=="donor-inventory":
        from .provenance import inventory
        full=inventory(args.donor,root,args.output)
        result={key:value for key,value in full.items() if key!="files"}
        result["evidence_path"]=str(args.output)
    elif args.command=="resource":
        return int(load_component(root,"ops/workstation/minitz-resource.py","minitz_resource_adapter").main(args.arguments))
    elif args.command=="serve":
        return int(load_component(root,"ops/workstation/minitz-os-sandbox/startup.py","minitz_sandbox_startup").main())
    else:
        import minitz_task_program as tasks  # type: ignore[import-untyped]
        import minitz_local_quality as quality  # type: ignore[import-untyped]
        program=tasks.load()
        state=Path(os.environ.get("MINITZ_STATE_ROOT","/state"))
        path=state/"qualification/sandbox-foundation.json"
        qualification: dict[str, Any] = json.loads(path.read_text()) if path.is_file() else {"state":"NOT_OBSERVED"}
        result={"product":"MiniTZ OS","source":identity,"task":program["current_execution"],
                "task_authority":tasks.program_identity(program),"startup_state":qualification.get("state"),
                "coder":qualification.get("coder",{}),"control":qualification.get("control",{}),
                "capacity":quality.snapshot(),"model_execution_location":qualification.get("model_execution_location"),
                "full_os_qualification":"NOT_COMPLETE"}
        if args.command=="capabilities":
            result["capabilities"]=qualification.get("qualification",{}).get("results",[])
            from .capabilities import CapabilitySurface
            result["capability_surface"] = CapabilitySurface().snapshot()
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
