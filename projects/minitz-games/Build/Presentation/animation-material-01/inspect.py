import json,os,unreal
from pathlib import Path
lib=unreal.MaterialEditingLibrary
m=unreal.load_asset('/Game/Characters/Mannequins/Materials/M_Mannequin')
r={'scalar_parameters':{str(n):lib.get_material_default_scalar_parameter_value(m,n) for n in lib.get_scalar_parameter_names(m)},'use_material_attributes':m.get_editor_property('use_material_attributes'),'inputs':{},'slots':[]}
for name in ['MP_BASE_COLOR','MP_EMISSIVE_COLOR','MP_MATERIAL_ATTRIBUTES']:
 n=lib.get_material_property_input_node(m,getattr(unreal.MaterialProperty,name))
 r['inputs'][name]=None if n is None else {'class':n.get_class().get_name(),'path':n.get_path_name()}
mesh=unreal.load_asset('/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple')
for slot in mesh.get_editor_property('materials'):
 mi=slot.get_editor_property('material_interface')
 r['slots'].append({'material':mi.get_path_name(),'parent':mi.get_editor_property('parent').get_path_name()})
Path(os.environ['BIELLA_D03_ANIMATION_REPORT']).write_text(json.dumps(r,indent=2)+'\n')
