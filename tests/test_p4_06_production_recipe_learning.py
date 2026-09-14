from __future__ import annotations
from pathlib import Path
import pytest
from minitz_os.engine.project import ProjectRef
from minitz_os.engine.run import RunRef

def test_recipe_normalizes_id_different_software_graphs_and_matches_compatible_task(tmp_path: Path) -> None:
 from minitz_os.engine.production_recipe_learning import ProductionRecipeLearningService,RecipeScope
 s=ProductionRecipeLearningService(tmp_path/'r.db'); a=ProjectRef.new(); r=s.extract_recipe(a,{"kind":"software"},({"nodes":["a","b"],"edges":[["a","b"]]},),(),(),scope=RecipeScope.PROJECT,applicability={},parameter_schema={},learning_evidence=())
 assert s.match_recipe(a,r,{"kind":"software"}).state.name in {'MATCH','PARTIAL_MATCH'}
 assert s.match_recipe(a,r,{"kind":"3d"}).state.name=='NO_MATCH'
def test_recipe_optional_branch_scope_and_engine_normalization_guards(tmp_path: Path) -> None:
 from minitz_os.engine.production_recipe_learning import ProductionRecipeLearningService,RecipeScope
 s=ProductionRecipeLearningService(tmp_path/'r.db'); a,b=ProjectRef.new(),ProjectRef.new(); r=s.extract_recipe(a,{"kind":"software"},(),(),(),scope=RecipeScope.PROJECT,applicability={},parameter_schema={},learning_evidence=())
 with pytest.raises(Exception): s.match_recipe(b,r,{"kind":"software"})
 assert 'prj_' not in repr(r)
def test_recipe_run_failure_stale_replacement_quarantine_and_restart_guards(tmp_path: Path) -> None:
 from minitz_os.engine.production_recipe_learning import ProductionRecipeLearningService,RecipeRunOutcome
 s=ProductionRecipeLearningService(tmp_path/'r.db'); p=ProjectRef.new(); r=s.extract_recipe(p,{"kind":"software"},(),(),(),applicability={},parameter_schema={},learning_evidence=())
 with pytest.raises(Exception): s.record_recipe_run(r,'run',RecipeRunOutcome.SUCCEEDED,(),r.canonical_digest,2,1)
 with pytest.raises(Exception): s.extract_recipe(p,{},(),('quarantine://raw/x',),(),applicability={},parameter_schema={},learning_evidence=())

def test_recipe_semantic_normalization_optional_branch_and_safe_parallelism(tmp_path: Path) -> None:
 from minitz_os.engine.production_recipe_learning import ProductionRecipeLearningService,RecipeMatchState
 s=ProductionRecipeLearningService(tmp_path/'r.db'); p=ProjectRef.new()
 r=s.extract_recipe(p,{"capability":"software.build"},({"nodes":[{"role":"build"},{"role":"test","optional":True}],"edges":[]},),(),(),applicability={"kind":"software"},parameter_schema={},learning_evidence=())
 assert s.match_recipe(p,r,{"capability":"software.build"}).state is RecipeMatchState.MATCH
 assert s.match_recipe(p,r,{"capability":"software"}).state is RecipeMatchState.PARTIAL_MATCH

def test_recipe_v2_supersession_failure_retention_and_evidence_projection(tmp_path: Path) -> None:
 from minitz_os.engine.production_recipe_learning import ProductionRecipeLearningService,RecipeRunOutcome
 s=ProductionRecipeLearningService(tmp_path/'r.db'); p=ProjectRef.new(); r=s.extract_recipe(p,{},(),(),(),applicability={},parameter_schema={},learning_evidence=())
 v2=s.supersede_recipe(p,r,applicability={"v":"2"},parameter_schema={},learning_evidence=())
 with pytest.raises(Exception): s.record_recipe_run(r,RunRef(p, "run_" + "a" * 32),RecipeRunOutcome.FAILED,('evidence://failure/v1',),r.canonical_digest,1,1,validation_evidence=())
 assert s.kpi_results()

def test_recipe_rejects_raw_quarantine_and_tampered_or_deleted_learning_state(tmp_path: Path) -> None:
 from minitz_os.engine.production_recipe_learning import ProductionRecipeLearningService
 s=ProductionRecipeLearningService(tmp_path/'r.db'); p=ProjectRef.new()
 for raw in ('quarantine://raw/x','raw://unclassified/x'):
  with pytest.raises(Exception): s.extract_recipe(p,{},(),(raw,),(),applicability={},parameter_schema={},learning_evidence=())
 with pytest.raises(Exception): s.build_system_evidence_summary(p,())

def test_failed_recipe_run_evidence_is_retained_after_restart(tmp_path: Path) -> None:
 from minitz_os.engine.production_recipe_learning import ProductionRecipeLearningService,RecipeRunOutcome
 project=ProjectRef.new(); db=tmp_path/'retained.db'; service=ProductionRecipeLearningService(db); recipe=service.extract_recipe(project,{},(),(),(),applicability={},parameter_schema={},learning_evidence=())
 run=RunRef(project,"run_"+"b"*32)
 service.record_recipe_run(recipe,run,RecipeRunOutcome.FAILED,("evidence://failure/retained/v1",),recipe.canonical_digest,1,1,validation_evidence=())
 assert len(ProductionRecipeLearningService(db).list_recipe_runs(recipe)) == 1
