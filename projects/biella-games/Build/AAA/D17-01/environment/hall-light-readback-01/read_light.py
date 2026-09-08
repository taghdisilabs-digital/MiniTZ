import unreal,json,os
from pathlib import Path
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert level.load_level('/Game/Maps/BiellaOpenWorldMap')
wp=unreal.WorldPartitionBlueprintLibrary
wp.load_actors([d.guid for d in wp.get_actor_descs()])
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
a=next(a for a in actors if a.get_actor_label()=='D02_Interior_Light')
c=a.light_component
props={}
for key in ('intensity','attenuation_radius','use_inverse_squared_falloff','source_radius','cast_shadows','use_temperature','temperature','specular_scale','indirect_lighting_intensity','volumetric_scattering_intensity'):
    props[key]=c.get_editor_property(key)
for key in ('intensity_units','mobility'):
    props[key]=str(c.get_editor_property(key))
color=c.get_light_color();location=a.get_actor_location()
props['color_linear']=[getattr(color,k) for k in ('r','g','b','a')]
props['location_cm']=[getattr(location,k) for k in ('x','y','z')]
props['actor_path']=a.get_path_name()
props['actor_package']=str(next(d.actor_package for d in wp.get_actor_descs() if str(d.label)=='D02_Interior_Light'))
Path(os.environ['BIELLA_HALL_LIGHT_REPORT']).write_text(json.dumps(dict(task_id='D17-01',read_only=True,properties=props),indent=2)+'\n')
unreal.log('D17_LIGHT_READBACK COMPLETE')
