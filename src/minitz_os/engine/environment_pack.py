"""Provider-neutral environment production-pack contracts."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math, re
from types import MappingProxyType
from .capability import Capability, CapabilityRef
from .production_pack import GraphRecipeRegistration, GraphRecipeStepRegistration, ProductionPack, ProductionPackRef, ValidatorRegistration
from .project import ProjectRef

_NAMES=("inspect","layout","terrain","structure","populate","vegetation","material","lighting_setup","collision","navigation_prepare","lod","optimize","partition","export","preview","validate")
_ROLES=("environment.source","environment.terrain","environment.structure","environment.prop","environment.vegetation","environment.material","environment.collision","environment.navigation","environment.partition","environment.export","environment.preview","environment.validation")
_REF=re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}"); _SHA=re.compile(r"[0-9a-f]{64}"); _ID=re.compile(r"[a-z0-9][a-z0-9-]{0,127}")
class EnvironmentContractError(ValueError): pass
def _ref(x:object,n:str)->str:
    if not isinstance(x,str) or not _REF.fullmatch(x): raise EnvironmentContractError(f"{n} must be reference")
    return x
def _sha(x:object,n:str)->str:
    if not isinstance(x,str) or not _SHA.fullmatch(x): raise EnvironmentContractError(f"{n} must be digest")
    return x
def _id(x:object,n:str)->str:
    if not isinstance(x,str) or not _ID.fullmatch(x): raise EnvironmentContractError(f"{n} malformed")
    return x
def _map(x:object,n:str,empty:bool=False)->Mapping[str,str]:
    if not isinstance(x,Mapping) or (not empty and not x): raise EnvironmentContractError(f"{n} missing")
    d={str(k):str(v) for k,v in x.items()}
    if len(d)!=len(x) or any(not k for k in d): raise EnvironmentContractError(f"{n} malformed")
    return MappingProxyType(dict(sorted(d.items())))
def _finite(x:object,n:str,l:int)->tuple[float,...]:
    if isinstance(x,(str,bytes)) or not isinstance(x,Sequence) or len(x)!=l: raise EnvironmentContractError(f"{n} dimension")
    try: r=tuple(float(i) for i in x)
    except (TypeError,ValueError): raise EnvironmentContractError(f"{n} numeric") from None
    if not all(math.isfinite(i) for i in r): raise EnvironmentContractError(f"{n} finite")
    return r

@dataclass(frozen=True)
class EnvironmentSpecification:
    project_ref:ProjectRef; environment_id:str; source_ref:str; content_sha256:str; units:str; coordinates:Mapping[str,str]; layout:Mapping[str,str]; gameplay_navigation:Mapping[str,str]; visual:Mapping[str,str]; asset_library_refs:tuple[str,...]; target_tool_engine:Mapping[str,str]; performance:Mapping[str,str]; partition:Mapping[str,str]; output_acceptance_refs:tuple[str,...]; representation_tags:tuple[str,...]
    def __post_init__(self)->None:
        if not isinstance(self.project_ref,ProjectRef): raise EnvironmentContractError("project")
        for n in ("environment_id","units"): object.__setattr__(self,n,_id(getattr(self,n),n))
        object.__setattr__(self,"source_ref",_ref(self.source_ref,"source_ref")); object.__setattr__(self,"content_sha256",_sha(self.content_sha256,"content_sha256"))
        for n in ("coordinates","layout","gameplay_navigation","visual","target_tool_engine","performance","partition"): object.__setattr__(self,n,_map(getattr(self,n),n))
        for n in ("asset_library_refs","output_acceptance_refs","representation_tags"):
            vals=tuple(_ref(v,n) for v in getattr(self,n))
            if not vals or len(set(vals))!=len(vals): raise EnvironmentContractError(f"{n} missing")
            object.__setattr__(self,n,tuple(sorted(vals)))
@dataclass(frozen=True)
class PlacedAsset:
    project_ref:ProjectRef; asset_id:str; source_ref:str; content_sha256:str; transform:tuple[float,...]; material_ref:str; variant:str; parent_ref:str|None; partition_id:str
    def __post_init__(self)->None:
        if not isinstance(self.project_ref,ProjectRef): raise EnvironmentContractError("project")
        for n in ("asset_id","variant","partition_id"): object.__setattr__(self,n,_id(getattr(self,n),n))
        for n in ("source_ref","material_ref"): object.__setattr__(self,n,_ref(getattr(self,n),n))
        object.__setattr__(self,"content_sha256",_sha(self.content_sha256,"content_sha256")); object.__setattr__(self,"transform",_finite(self.transform,"transform",16))
        if self.parent_ref is not None: object.__setattr__(self,"parent_ref",_ref(self.parent_ref,"parent_ref"))
@dataclass(frozen=True)
class ProceduralTerrain:
    project_ref:ProjectRef; terrain_id:str; generator_ref:str; generator_version:str; config:Mapping[str,str]; seed:int; terrain_ref:str; content_sha256:str
    def __post_init__(self)->None:
        if not isinstance(self.project_ref,ProjectRef) or not isinstance(self.seed,int): raise EnvironmentContractError("terrain project or seed")
        object.__setattr__(self,"terrain_id",_id(self.terrain_id,"terrain_id"))
        if not isinstance(self.generator_version,str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+",self.generator_version) is None: raise EnvironmentContractError("generator_version malformed")
        for n in ("generator_ref","terrain_ref"): object.__setattr__(self,n,_ref(getattr(self,n),n))
        object.__setattr__(self,"config",_map(self.config,"config")); object.__setattr__(self,"content_sha256",_sha(self.content_sha256,"content_sha256"))
@dataclass(frozen=True)
class EnvironmentIntegrationManifest:
    project_ref:ProjectRef; specification:EnvironmentSpecification; terrain:ProceduralTerrain; placed_assets:tuple[PlacedAsset,...]; structure_ref:str; prop_ref:str; vegetation_ref:str; material_ref:str; collision_ref:str; navigation_ref:str; partition_ref:str; tool_ref:str; runtime_ref:str; derivation_ref:str; content_sha256:str
    def __post_init__(self)->None:
        if not isinstance(self.project_ref,ProjectRef) or not isinstance(self.specification,EnvironmentSpecification) or not isinstance(self.terrain,ProceduralTerrain) or self.specification.project_ref!=self.project_ref or self.terrain.project_ref!=self.project_ref: raise EnvironmentContractError("manifest scope")
        assets=tuple(self.placed_assets)
        if not assets or not all(isinstance(a,PlacedAsset) and a.project_ref==self.project_ref for a in assets): raise EnvironmentContractError("manifest dependencies")
        object.__setattr__(self,"placed_assets",assets)
        for n in ("structure_ref","prop_ref","vegetation_ref","material_ref","collision_ref","navigation_ref","partition_ref","tool_ref","runtime_ref","derivation_ref"): object.__setattr__(self,n,_ref(getattr(self,n),n))
        object.__setattr__(self,"content_sha256",_sha(self.content_sha256,"content_sha256"))
    def require_specification(self,specification:EnvironmentSpecification)->EnvironmentSpecification:
        if not isinstance(specification,EnvironmentSpecification) or specification!=self.specification: raise EnvironmentContractError("specification stale")
        return specification
    def require_placed_assets(self,placed_assets:tuple[PlacedAsset,...])->tuple[PlacedAsset,...]:
        current=tuple(placed_assets)
        if current!=self.placed_assets:
            raise EnvironmentContractError("placed asset source is stale")
        return current
def _cap(n:str)->Capability:
    return Capability(CapabilityRef(f"environment.{n}","1.0.0"),f"Perform bounded environment {n.replace('_',' ')} work.",{"project":"minitz://contracts/project-ref/v1"},{"result":f"minitz://contracts/environment-{n.replace('_','-')}/v1"},("workspace.process.execute","workspace.filesystem.write","workspace.artifact.create"),"2026-08-31T00:00:00+00:00")
def environment_production_pack()->ProductionPack:
    caps=tuple(_cap(n) for n in _NAMES); refs={c.name:c.capability_ref for c in caps}; steps=tuple(GraphRecipeStepRegistration(n,refs[n],(() if i==0 else (_NAMES[i-1],))) for i,n in enumerate(_NAMES))
    return ProductionPack(ProductionPackRef("environment","1.0.0"),caps,(GraphRecipeRegistration("pack-recipe://environment/production@1.0.0",steps),),tuple(ValidatorRegistration(f"pack-validator://environment/{n}@1.0.0",refs[n],f"validation-check://artifact-role/{_ROLES[i%len(_ROLES)]}/v1") for i,n in enumerate(_NAMES)),_ROLES,{c.capability_ref.value:("adapter://artifact/v1","adapter://filesystem/v1","adapter://process/v1","adapter://three-d-tool/v1","adapter://workspace/v1") for c in caps},{c.capability_ref.value:"resource-profile://environment/project-configured/v1" for c in caps},"2026-08-31T00:00:00+00:00")
