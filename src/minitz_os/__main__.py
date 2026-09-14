"""MiniTZ's native command surface for the managed sandbox environment."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence
from .source import source_manifest, verify_source, build_release, install_release


def source_root() -> Path:
    return Path(os.environ.get("MINITZ_SOURCE_ROOT",str(Path(__file__).resolve().parents[2]))).resolve()


def installed_identity(root: Path) -> dict[str, Any]:
    path=Path(os.environ.get("MINITZ_SOURCE_MANIFEST","/etc/minitz/source.json"))
    if path.is_file():
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


def main(argv: Sequence[str] | None = None) -> int:
    parser=argparse.ArgumentParser(prog="minitz",description="MiniTZ OS managed system")
    sub=parser.add_subparsers(dest="command",required=True)
    for name in ("source","status","capabilities","serve"):
        sub.add_parser(name)
    build=sub.add_parser("build-release");build.add_argument("--output",type=Path,required=True)
    install=sub.add_parser("install-release");install.add_argument("--artifact",type=Path,required=True)
    install.add_argument("--sha256",required=True);install.add_argument("--system-root",type=Path,required=True)
    donor=sub.add_parser("donor-inventory");donor.add_argument("--donor",type=Path,required=True)
    donor.add_argument("--output",type=Path,required=True)
    resource=sub.add_parser("resource");resource.add_argument("arguments",nargs=argparse.REMAINDER)
    args=parser.parse_args(argv)
    root=source_root()
    for path in (root/"ops/local-ai",root/"ops/workstation",root/"ops/control_gateway"):
        sys.path.insert(0,str(path))
    identity=installed_identity(root)
    if args.command=="source":
        result=identity
    elif args.command=="build-release":
        result=build_release(root,args.output)
    elif args.command=="install-release":
        result=install_release(args.artifact,args.system_root,args.sha256)
    elif args.command=="donor-inventory":
        from .provenance import inventory
        full=inventory(args.donor,root,args.output)
        result={key:value for key,value in full.items() if key!="files"}
        result["evidence_path"]=str(args.output)
    elif args.command=="resource":
        return int(load_component(root,"ops/workstation/biella-resource.py","minitz_resource_adapter").main(args.arguments))
    elif args.command=="serve":
        return int(load_component(root,"ops/workstation/minitz-os-sandbox/startup.py","minitz_sandbox_startup").main())
    else:
        import minitz_task_program as tasks  # type: ignore[import-not-found]
        import minitz_local_quality as quality  # type: ignore[import-not-found]
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
