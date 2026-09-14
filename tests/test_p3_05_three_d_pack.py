"""P3-05 provider-neutral 3D production-pack qualification."""

from __future__ import annotations

from dataclasses import replace
import inspect
from pathlib import Path

import minitz_os.engine as minitz_engine
import pytest


THREE_D_CAPABILITIES = {
    f"3d.{name}"
    for name in (
        "inspect",
        "model",
        "mesh_edit",
        "topology",
        "uv",
        "material",
        "scene",
        "convert",
        "optimize",
        "validate",
        "preview",
    )
}

THREE_D_ADAPTER_METHODS = {
    "inspectAsset",
    "inspectScene",
    "createAsset",
    "modifyAsset",
    "executeOperation",
    "validate",
    "export",
    "preview",
    "describeRuntime",
}


def test_t01_public_pack_protocol_capabilities_and_roles_are_exact_neutral_data() -> None:
    assert {
        "ThreeDToolAdapter",
        "BlenderThreeDToolAdapter",
        "ReferenceThreeDToolAdapter",
        "three_d_production_pack",
    } <= set(minitz_engine.__all__)
    protocol = minitz_engine.ThreeDToolAdapter
    assert THREE_D_ADAPTER_METHODS <= {
        name for name in dir(protocol) if not name.startswith("_")
    }

    pack = minitz_engine.three_d_production_pack()
    assert pack.pack_ref == minitz_engine.ProductionPackRef("3d", "1.0.0")
    for malformed_id in ("", "-3d", "_3d", "3d!"):
        try:
            minitz_engine.ProductionPackRef(malformed_id, "1.0.0")
        except minitz_engine.ProductionPackContractError:
            pass
        else:
            raise AssertionError(f"malformed pack id accepted: {malformed_id!r}")
    assert {
        item.capability_id for item in pack.capability_definitions
    } == THREE_D_CAPABILITIES
    assert set(pack.adapter_bindings) == {
        item.capability_ref.value for item in pack.capability_definitions
    }
    assert set(pack.resource_profiles) == set(pack.adapter_bindings)
    assert {
        "adapter://artifact/v1",
        "adapter://filesystem/v1",
        "adapter://process/v1",
        "adapter://three-d-tool/v1",
        "adapter://validation/v1",
        "adapter://workspace/v1",
    } <= {
        reference
        for references in pack.adapter_bindings.values()
        for reference in references
    }
    assert {
        "3d.mesh",
        "3d.scene",
        "3d.material",
        "3d.texture-set",
        "3d.uv-data",
        "3d.lod-set",
        "3d.collision-mesh",
        "3d.interchange-export",
        "3d.preview",
        "3d.inspection",
        "3d.validation",
    } <= set(pack.artifact_roles)
    assert pack.graph_recipe_refs
    assert pack.validator_refs
    assert {
        item.capability_ref.capability_id for item in pack.validators
    } == THREE_D_CAPABILITIES
    assert pack.semantic_digest == minitz_engine.three_d_production_pack().semantic_digest
    assert not hasattr(minitz, "ThreeDTask")
    assert not hasattr(minitz, "ThreeDRun")


def test_t02_pack_registration_restart_and_composition_are_durable(
    tmp_path: Path,
) -> None:
    database = tmp_path / "three-d-pack.sqlite3"
    registry = minitz_engine.ProductionPackRegistry(database)
    software = registry.register(
        minitz_engine.software_production_pack(),
        idempotency_key="p3-05-software",
    )
    three_d = registry.register(
        minitz_engine.three_d_production_pack(),
        idempotency_key="p3-05-three-d",
    )
    assert registry.register(
        minitz_engine.three_d_production_pack(),
        idempotency_key="p3-05-three-d",
    ) == three_d
    restarted = minitz_engine.ProductionPackRegistry(database)
    assert restarted.get(three_d.pack_ref) == three_d
    assert {item.pack_ref for item in restarted.list_packs()} == {
        software.pack_ref,
        three_d.pack_ref,
    }
    assert not THREE_D_CAPABILITIES & {
        item.capability_id for item in software.capability_definitions
    }
    changed = replace(
        minitz_engine.three_d_production_pack(),
        artifact_roles=(*three_d.artifact_roles, "3d.custom-extension"),
    )
    with pytest.raises(minitz_engine.ProductionPackConflictError):
        restarted.register(changed, idempotency_key="p3-05-three-d")


def test_t03_dcc_sdk_roles_formats_and_project_criteria_stay_outside_kernel() -> None:
    root = Path(__file__).parents[1]
    tool_source = (root / "src/minitz_os/engine/three_d_tool.py").read_text(encoding="utf-8")
    driver_source = (root / "src/minitz_os/engine/_blender_three_d_driver.py").read_text(
        encoding="utf-8"
    )
    pack_source = (root / "src/minitz_os/engine/three_d_pack.py").read_text(encoding="utf-8")
    assert "import bpy" not in tool_source
    assert "import subprocess" not in tool_source
    assert "subprocess." not in tool_source
    assert "eval(" not in driver_source
    assert "exec(" not in driver_source
    assert "ThreeDArtifactRole" not in tool_source
    assert "ThreeDFormat" not in tool_source
    assert "global_polygon" not in tool_source + pack_source
    assert "default_axis" not in tool_source + pack_source
    assert "default_format" not in tool_source + pack_source
    assert "QuarantineRef" not in tool_source + pack_source + driver_source
    assert "NotImplemented" not in tool_source + pack_source + driver_source
    assert "TODO" not in tool_source + pack_source + driver_source

    universal = (
        "project.py",
        "task.py",
        "run.py",
        "graph.py",
        "scheduler.py",
        "resource.py",
        "artifact.py",
        "validation.py",
    )
    prohibited = ("Blender", "Houdini", "Maya", "ThreeDTool", "polygon_budget")
    for filename in universal:
        source = (root / "src/minitz" / filename).read_text(encoding="utf-8")
        assert not any(term in source for term in prohibited), filename

    annotations = " ".join(
        repr(inspect.signature(getattr(minitz_engine.ThreeDToolAdapter, method)))
        for method in THREE_D_ADAPTER_METHODS
    )
    assert "bpy" not in annotations


def test_t04_extension_roles_are_open_without_permitting_known_role_substitution() -> None:
    project_ref = minitz_engine.ProjectRef.new()
    identity = minitz_engine.ThreeDToolIdentity(
        project_ref=project_ref,
        adapter_ref="adapter://3d/blender/v1",
        tool_name="Blender",
        tool_version="5.0.1",
        executable_path="/usr/bin/blender",
        executable_sha256="1" * 64,
        driver_sha256="2" * 64,
        plugins=(),
        runtime_ref="runtime://host/blender-5.0.1-cpu",
    )
    extension_role = "3d.vendor-native-mesh"
    assert extension_role not in minitz_engine.three_d_production_pack().artifact_roles
    request = minitz_engine.ThreeDOperationRequest(
        operation=minitz_engine.ThreeDOperation.MODEL,
        identity=identity,
        candidate_snapshot_ref=minitz_engine.WorkspaceSnapshotRef(
            minitz_engine.WorkspaceRef.new(project_ref),
            1,
        ),
        control_root_ref=minitz_engine.FilesystemRootRef.new(project_ref),
        working_directory="candidate",
        source_artifact_refs=(),
        source_path=None,
        output_path="vendor-source.blend",
        output_role=extension_role,
        output_media_type="application/x-blender",
    )
    assert request.output_role == extension_role

    assert "3d.preview" in minitz_engine.three_d_production_pack().artifact_roles
    with pytest.raises(
        minitz_engine.ThreeDContractError,
        match="cannot substitute",
    ):
        replace(request, output_role="3d.preview")
