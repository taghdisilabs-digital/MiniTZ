from __future__ import annotations

from dataclasses import replace
import inspect

import pytest

import biella
from biella.render_adapter import BlenderRendererAdapter, ReferenceRendererAdapter
from biella.render_pack import (
    RenderConfig,
    RenderContractError,
    RenderFrameRef,
    RenderRequest,
    RenderSequenceManifest,
    RendererAdapter,
    render_production_pack,
)
from biella.production_pack import ProductionPackRef
from biella.project import ProjectRef


CAPS = {
    "inspect",
    "preview",
    "frame",
    "sequence",
    "batch",
    "raster",
    "raytrace",
    "pathtrace",
    "pass",
    "composite_input",
    "validate",
    "performance",
}
GENERIC_OPERATIONS = {
    "inspect",
    "renderFrame",
    "renderSequence",
    "renderPasses",
    "cancel",
    "describeRuntime",
    "validateOutput",
}


def _config(p: ProjectRef) -> RenderConfig:
    return RenderConfig(
        p,
        "preview",
        "config://render/preview/v1",
        "a" * 64,
        "preview",
        (640, 480),
        "image/png",
        ("rgba",),
        ("beauty",),
        {"quality": "project"},
        {"resource": "project"},
        {"egress": "project"},
        30.0,
        True,
    )


def _request(p: ProjectRef, c: RenderConfig) -> RenderRequest:
    return RenderRequest(
        p,
        "task://render/v1",
        "run://render/v1",
        "node://render/v1",
        "artifact://scene/v1",
        "b" * 64,
        "camera://main/v1",
        (1.0,) * 16,
        "lens://main/v1",
        "c" * 64,
        1,
        1,
        1.0,
        "render.frame",
        c,
        "renderer://generic/v1",
        "runtime://generic/v1",
        "executor://generic/v1",
        (),
    )


def test_render_pack_exact_capabilities_and_generic_adapter_contract() -> None:
    p = render_production_pack()
    assert p.pack_ref == ProductionPackRef("render", "1.0.0")
    assert {x.capability_id for x in p.capability_definitions} == {
        f"render.{x}" for x in CAPS
    }
    assert p.artifact_roles and p.validators and p.graph_recipes
    assert {
        "RendererAdapter",
        "RenderContractError",
        "RenderConfig",
        "RenderRequest",
        "RenderFrameRef",
        "RenderSequenceManifest",
        "render_production_pack",
    } <= set(biella.__all__)
    assert GENERIC_OPERATIONS <= set(RendererAdapter.__dict__)
    assert GENERIC_OPERATIONS <= set(BlenderRendererAdapter.__dict__)
    assert GENERIC_OPERATIONS <= set(ReferenceRendererAdapter.__dict__)
    assert tuple(inspect.signature(RendererAdapter.renderFrame).parameters) == (
        "self",
        "access",
        "attempt",
        "request",
        "scene_artifact_ref",
        "root_ref",
        "working_directory",
        "idempotency_key",
        "pass_id",
        "resource_allocation_ref",
    )


def test_reference_renderer_is_schema_compatible_and_inert() -> None:
    project = ProjectRef.new()
    reference: RendererAdapter = ReferenceRendererAdapter(project)
    runtime = reference.describeRuntime()
    assert runtime["reality"] == "REFERENCE"
    assert reference.cancel(idempotency_key="reference-cancel") is False
    with pytest.raises(RenderContractError, match="cannot claim REAL"):
        reference.renderFrame(None, None, None)  # type: ignore[arg-type]


def test_render_frame_and_manifest_fail_closed() -> None:
    p = ProjectRef.new()
    c = _config(p)
    r = _request(p, c)
    f = RenderFrameRef.from_request(
        r, "artifact://frame/1/v1", "d" * 64, True
    )
    m = RenderSequenceManifest(p, r, (1,), (f,), (), "e" * 64)
    assert m.require_frame(f) is f
    multi = RenderSequenceManifest(
        p,
        r,
        (1,),
        (
            f,
            RenderFrameRef.from_request(
                r,
                "artifact://frame/1/depth/v1",
                "f" * 64,
                True,
                "depth",
            ),
        ),
        (),
        "e" * 64,
    )
    assert len(multi.completed_frames) == 2
    child = replace(
        RenderFrameRef.from_request(
            r,
            "artifact://frame/1/child/v1",
            "9" * 64,
            True,
            "normal",
        ),
        node_ref="node://render/child/v1",
        executor_ref="executor://worker/v1",
        dependencies=("dispatch://child/v1",),
    )
    assert (
        len(
            RenderSequenceManifest(
                p,
                r,
                (1,),
                (child,),
                (),
                "e" * 64,
            ).completed_frames
        )
        == 1
    )
    with pytest.raises(RenderContractError):
        RenderSequenceManifest(
            p,
            r,
            (1,),
            (
                f,
                RenderFrameRef.from_request(
                    r,
                    "artifact://frame/1/duplicate/v1",
                    "0" * 64,
                    True,
                ),
            ),
            (),
            "e" * 64,
        )
    with pytest.raises(RenderContractError):
        m.require_frame(replace(f, scene_content_sha256="0" * 64))
    with pytest.raises(RenderContractError):
        RenderSequenceManifest(
            p,
            r,
            (1,),
            (replace(f, verified=False),),
            (),
            "e" * 64,
        )
