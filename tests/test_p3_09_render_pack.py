from __future__ import annotations
from dataclasses import replace
import inspect
import pytest
import biella
from biella.render_pack import RenderConfig, RenderContractError, RenderFrameRef, RenderRequest, RenderSequenceManifest, RendererAdapter, render_production_pack
from biella.production_pack import ProductionPackRef
from biella.project import ProjectRef

CAPS={"inspect","preview","frame","sequence","batch","raster","raytrace","pathtrace","pass","composite_input","validate","performance"}
def _config(p:ProjectRef)->RenderConfig:return RenderConfig(p,"preview","config://render/preview/v1","a"*64,"preview",(640,480),"image/png",("rgba",),("beauty",),{"quality":"project"},{"resource":"project"},{"egress":"project"},30.0,True)
def _request(p:ProjectRef,c:RenderConfig)->RenderRequest:return RenderRequest(p,"task://render/v1","run://render/v1","node://render/v1","artifact://scene/v1","b"*64,"camera://main/v1",(1.0,)*16,"lens://main/v1","c"*64,1,1,1.0,"render.frame",c, "renderer://generic/v1","runtime://generic/v1","executor://generic/v1",())
def _frame(r:RenderRequest,artifact_ref:str,content_sha256:str,verified:bool=True,pass_id:str="beauty")->RenderFrameRef:return RenderFrameRef.from_request(r,artifact_ref,content_sha256,verified,pass_id,producer_attempt_id="natt_"+"1"*32,producer_fence=1,producer_attempt_record_sha256="2"*64,resource_ref="resource://render/unit/v1",resource_identity_sha256="3"*64,device_identity="device://cpu/unit/v1")
def test_render_pack_exact_capabilities() -> None:
 p=render_production_pack(); assert p.pack_ref==ProductionPackRef("render","1.0.0"); assert {x.capability_id for x in p.capability_definitions}=={f"render.{x}" for x in CAPS}; assert p.artifact_roles and p.validators and p.graph_recipes
 assert {"RendererAdapter","RenderContractError","RenderConfig","RenderRequest","RenderFrameRef","RenderSequenceManifest","render_production_pack"}<=set(biella.__all__)
 assert tuple(inspect.signature(RendererAdapter.render).parameters)==("self","access","attempt","request","scene_artifact_ref","root_ref","working_directory","idempotency_key","pass_id","resource_allocation_ref")
def test_render_frame_and_manifest_fail_closed() -> None:
 p=ProjectRef.new(); c=_config(p); r=_request(p,c); f=_frame(r,"artifact://frame/1/v1","d"*64)
 m=RenderSequenceManifest(p,r,(1,),(f,),(),"e"*64); assert m.require_frame(f) is f
 multi_r=replace(r,config=replace(c,passes=("beauty","z"))); multi=RenderSequenceManifest(p,multi_r,(1,),(_frame(multi_r,"artifact://frame/1/v1","d"*64),_frame(multi_r,"artifact://frame/1/depth/v1","f"*64,pass_id="z")),(),"e"*64); assert len(multi.completed_frames)==2
 child=replace(_frame(replace(r,config=replace(c,passes=("beauty","normal"))),"artifact://frame/1/child/v1","9"*64,pass_id="normal"),node_ref="node://render/child/v1",executor_ref="executor://worker/v1",dependencies=("dispatch://child/v1",)); assert len(RenderSequenceManifest(p,replace(r,config=replace(c,passes=("beauty","normal"))),(1,),(child,),(),"e"*64).completed_frames)==1
 with pytest.raises(RenderContractError):RenderSequenceManifest(p,r,(1,),(f,_frame(r,"artifact://frame/1/duplicate/v1","0"*64)),(),"e"*64)
 with pytest.raises(RenderContractError):m.require_frame(replace(f,scene_content_sha256="0"*64))
 with pytest.raises(RenderContractError):RenderSequenceManifest(p,r,(1,),(replace(f,verified=False),),(),"e"*64)


def test_render_config_derives_versioned_digest_from_immutable_canonical_content() -> None:
 p=ProjectRef.new(); supplied="a"*64; c=_config(p)
 assert c.config_version=="1.0.0"
 assert c.digest!=supplied
 assert replace(c,digest="f"*64).digest==c.digest
 assert replace(c,quality={"quality":"final"}).digest!=c.digest
 with pytest.raises(TypeError):c.quality["quality"]="changed"  # type: ignore[index]


def test_renderer_protocol_exposes_one_provider_neutral_surface_with_legacy_aliases() -> None:
 required={"inspect","renderFrame","renderSequence","renderPasses","cancel","describeRuntime","validateOutput","render","render_sequence"}
 assert required<={name for name in dir(RendererAdapter) if not name.startswith("_")}


def test_render_contract_carries_camera_config_resource_and_attempt_evidence() -> None:
 assert {"camera_object","camera_settings"}<=set(RenderRequest.__dataclass_fields__)
 assert {"camera_object","camera_settings_sha256","config_id","config_version","media_type","channels","required_passes","producer_attempt_id","producer_fence","resource_ref","resource_identity_sha256","device_identity"}<=set(RenderFrameRef.__dataclass_fields__)


def test_render_capabilities_bind_to_renderer_adapter_not_raw_process() -> None:
 pack=render_production_pack()
 assert set(pack.adapter_bindings.values())=={("adapter://renderer/v1",)}
 assert all("request" in capability.input_contract for capability in pack.capability_definitions)
def test_reference_adapter_reuses_canonical_renderer_contract() -> None:
    from biella.render_tool import RendererAdapter as ConcreteRendererAdapter
    from biella.render_tool import ReferenceRendererAdapter

    assert issubclass(ReferenceRendererAdapter, ConcreteRendererAdapter)
    assert ReferenceRendererAdapter.renderFrame is ConcreteRendererAdapter.renderFrame
    assert ReferenceRendererAdapter.renderPasses is ConcreteRendererAdapter.renderPasses
    assert ReferenceRendererAdapter.renderSequence is ConcreteRendererAdapter.renderSequence
