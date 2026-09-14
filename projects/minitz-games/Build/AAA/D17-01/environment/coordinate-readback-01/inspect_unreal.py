import unreal,json,hashlib
from pathlib import Path
out=Path(__file__).parent
project=Path(unreal.Paths.project_dir()).resolve()
spec=json.loads((project/'SourceAssets/Environment/service-bay.json').read_text())
rows=[]
for entry in spec['assets']:
 mesh=unreal.EditorAssetLibrary.load_asset('/Game/Environment/ServiceBay/'+entry['mesh'])
 assert isinstance(mesh,unreal.StaticMesh)
 b=mesh.get_bounds()
 origin=[b.origin.x,b.origin.y,b.origin.z]; extent=[b.box_extent.x,b.box_extent.y,b.box_extent.z]
 observed_min=[o-e for o,e in zip(origin,extent)];observed_max=[o+e for o,e in zip(origin,extent)]
 intended_min=entry['bounds_min'];intended_max=entry['bounds_max']
 matches=all(abs(a-b)<.02 for a,b in zip(observed_min+observed_max,intended_min+intended_max))
 reflected_min=[intended_min[0],-intended_max[1],intended_min[2]]
 reflected_max=[intended_max[0],-intended_min[1],intended_max[2]]
 reflected_matches=all(abs(a-b)<.02 for a,b in zip(observed_min+observed_max,reflected_min+reflected_max))
 rows.append(dict(asset=mesh.get_path_name(),bounds_origin=origin,bounds_min=observed_min,bounds_max=observed_max,
  intended_min=intended_min,intended_max=intended_max,authored_coordinate_match=matches,y_reflected_match=reflected_matches))
report=dict(task_id='D17-01',result='OBSERVED',meshes=rows,mutates_assets=False)
(out/'unreal.json').write_text(json.dumps(report,indent=2)+'\n')
unreal.log('D17_SERVICE_COORDINATES COMPLETE')
