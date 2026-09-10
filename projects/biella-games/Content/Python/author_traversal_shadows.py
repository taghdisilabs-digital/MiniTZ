"""Repair observed traversal VSM casters without changing gameplay geometry.

Only diagnostic-named actors may change mesh binding. The Engine cube is
duplicated into the Project; all geometry, collision and material bindings
are compared before/after and again in a fresh read-only native process.
"""
import hashlib, json, os, struct
from pathlib import Path
import unreal

PROJECT = Path(__file__).resolve().parents[2]
SPEC = PROJECT/'Build/AAA/D17-02/shadow-casters-01/diagnosis.json'
BASELINE = PROJECT/'Build/AAA/D17-02/shadow-casters-01/inspect-source-before-04/meshes.json'
REPORT = Path(os.environ['BIELLA_D17_SHADOW_REPORT'])
VERIFY = '-D17VerifyTraversalShadows' in unreal.SystemLibrary.get_command_line()
LIB = unreal.EditorAssetLibrary
MAT = unreal.MaterialEditingLibrary
MESH = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem) or unreal.get_default_object(unreal.StaticMeshEditorSubsystem)
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
WP = unreal.WorldPartitionBlueprintLibrary
CUBE = '/Game/Environment/Traversal/SM_RouteShadowCube'
USAGE = unreal.MaterialUsage.MATUSAGE_NANITE

def require(ok, message):
    if not ok: raise RuntimeError('D17_TRAVERSAL_SHADOWS FAIL: '+message)

def path(obj): return obj.get_path_name() if obj else None
def vector(obj, keys='xyz'): return [getattr(obj, k) for k in keys]

def actor_state(actor):
    c = actor.static_mesh_component
    return dict(path=path(actor), mesh=path(c.static_mesh),
        location=vector(actor.get_actor_location()),
        rotation=vector(actor.get_actor_transform().rotation, 'xyzw'),
        scale=vector(actor.get_actor_scale3d()),
        collision=str(c.get_collision_profile_name()),
        collision_enabled=str(c.get_collision_enabled()),
        materials=[path(m) for m in c.get_materials()],
        hidden=actor.get_editor_property('hidden'),
        cast_shadow=c.get_editor_property('cast_shadow'),
        mobility=str(c.get_editor_property('mobility')),
        tags=[str(t) for t in actor.get_editor_property('tags')])

def source_geometry(mesh):
    """Hash editable LOD0 positions and indexed triangles, not Nanite render bounds."""
    description = mesh.get_static_mesh_description(0)
    require(description is not None, 'Editable mesh description missing: '+path(mesh))
    vertices = description.get_vertex_count()
    triangles = description.get_triangle_count()
    positions = hashlib.sha256(); topology = hashlib.sha256()
    minimum = [float('inf')]*3; maximum = [float('-inf')]*3
    # Imported meshes are compact. Fail on holes instead of silently skipping data.
    for index in range(vertices):
        vertex = unreal.VertexID(); vertex.import_text('(IDValue=%d)' % index)
        require(description.is_vertex_valid(vertex), 'Noncompact source vertex IDs')
        position = vector(description.get_vertex_position(vertex))
        positions.update(struct.pack('<I3d', index, *position))
        minimum = [min(a,b) for a,b in zip(minimum,position)]
        maximum = [max(a,b) for a,b in zip(maximum,position)]
    for index in range(triangles):
        triangle = unreal.TriangleID(); triangle.import_text('(IDValue=%d)' % index)
        require(description.is_triangle_valid(triangle), 'Noncompact source triangle IDs')
        # UE 5.8 GetTriangleVertices pre-sizes then appends via Algo::Copy.
        # Read each corner explicitly to avoid that output-array defect.
        ids = [description.get_vertex_instance_vertex(description.get_triangle_vertex_instance(triangle, corner)).get_editor_property('id_value') for corner in range(3)]
        require(len(ids) == 3, 'Invalid source triangle')
        topology.update(struct.pack('<I3i', index, *ids))
    return dict(vertices=vertices, triangles=triangles, positions_sha256=positions.hexdigest(),
        topology_sha256=topology.hexdigest(), bounds_min=minimum, bounds_max=maximum,
        encoding='LOD0 compact IDs; little-endian uint32 index + xyz float64 / 3 int32 vertex IDs')

def render_bounds(mesh):
    bounds = mesh.get_bounds()
    return dict(origin=vector(bounds.origin), extent=vector(bounds.box_extent))

def mesh_state(mesh):
    body = mesh.get_editor_property('body_setup')
    return dict(triangles=mesh.get_num_triangles(0),
        source_geometry=source_geometry(mesh),
        materials=[path(m.material_interface) for m in mesh.get_editor_property('static_materials')],
        simple_collisions=MESH.get_simple_collision_count(mesh),
        convex_collisions=MESH.get_convex_collision_count(mesh),
        collision_geometry=body.get_editor_property('agg_geom').export_text() if body else None,
        collision_trace=str(body.get_editor_property('collision_trace_flag')) if body else None)

require(LEVEL.load_level('/Game/Maps/BiellaOpenWorldMap'), 'Map load failed')
WP.load_actors([d.guid for d in WP.get_actor_descs()])
actors = {a.get_actor_label(): a for a in ACTORS.get_all_level_actors() if isinstance(a, unreal.StaticMeshActor)}
labels = [t['label'] for t in json.loads(SPEC.read_text())['targets']]
require(set(labels) <= actors.keys(), 'Diagnostic actor missing')
before = {label: actor_state(a) for label, a in actors.items()}
engine_cube = LIB.load_asset('/Engine/BasicShapes/Cube')
engine_cube_before = mesh_state(engine_cube)
saved = json.loads(Path(os.environ.get('BIELLA_D17_SHADOW_AUTHOR', str(REPORT.parent/'author.json'))).read_text()) if VERIFY else None
if not LIB.does_asset_exist(CUBE):
    require(not VERIFY, 'Saved Project cube missing')
    LIB.make_directory('/Game/Environment/Traversal')
    require(LIB.duplicate_asset('/Engine/BasicShapes/Cube', CUBE), 'Project cube duplication failed')
cube = LIB.load_asset(CUBE)
require(mesh_state(cube) == engine_cube_before, 'Project cube changed original geometry/collision/materials')
meshes = {path(cube): cube}
for label in labels:
    actor = actors[label]; c = actor.static_mesh_component
    if c.static_mesh == engine_cube:
        require(not VERIFY, 'Saved actor still references Engine cube: '+label)
        actor.modify(); c.modify(); c.set_static_mesh(cube)
    require(path(c.static_mesh).startswith('/Game/'), 'Unexpected external mesh')
    meshes[path(c.static_mesh)] = c.static_mesh
mesh_before = {p: mesh_state(m) for p, m in meshes.items()}
render_bounds_before = {p: render_bounds(m) for p, m in meshes.items()}
baseline = json.loads(BASELINE.read_text())
for p, state in mesh_before.items():
    original = '/Engine/BasicShapes/Cube' if p == path(cube) else p.split('.')[0]
    require(state == baseline[original]['source'], 'Editable mesh differs from preserved pre-repair source: '+p)
material_parents = {}
for label in labels:
    for material in actors[label].static_mesh_component.get_materials():
        base = material
        while isinstance(base, unreal.MaterialInstance): base = base.get_editor_property('parent')
        require(isinstance(base, unreal.Material), 'Material parent unavailable')
        if path(base).startswith('/Game/'):
            material_parents[path(base)] = base
        # Engine defaults are never modified. Runtime logs check any fallback.
for material in material_parents.values():
    if not VERIFY:
        MAT.set_base_material_usage(material, USAGE, True)
        MAT.recompile_material(material)
        require(LIB.save_loaded_asset(material, only_if_is_dirty=False), 'Material save failed')
    require(material.get_editor_property('used_with_nanite'), 'Nanite material usage missing')
material_usage = {}
for label in labels:
    for material in actors[label].static_mesh_component.get_materials():
        if path(material).startswith('/Game/'):
            material_usage[path(material)] = MAT.has_material_usage(material, USAGE)
            require(material_usage[path(material)], 'Instance lacks Nanite shader usage: '+path(material))
nanite_settings = {}
mesh_after = {}
for p, mesh in meshes.items():
    settings = MESH.get_nanite_settings(mesh)
    if not VERIFY:
        settings.set_editor_property('enabled', True)
        settings.set_editor_property('keep_percent_triangles', 1.0)
        settings.set_editor_property('fallback_target', unreal.NaniteFallbackTarget.PERCENT_TRIANGLES)
        settings.set_editor_property('fallback_percent_triangles', 1.0)
        settings.set_editor_property('fallback_relative_error', 0.0)
        MESH.set_nanite_settings(mesh, settings, True)
        require(LIB.save_loaded_asset(mesh, only_if_is_dirty=False), 'Mesh save failed')
    settings = MESH.get_nanite_settings(mesh)
    state = {k: settings.get_editor_property(k) for k in ('enabled', 'keep_percent_triangles', 'fallback_percent_triangles', 'fallback_relative_error')}
    require(state == dict(enabled=True, keep_percent_triangles=1.0, fallback_percent_triangles=1.0, fallback_relative_error=0.0), 'Nanite detail changed')
    require(settings.get_editor_property('fallback_target') == unreal.NaniteFallbackTarget.PERCENT_TRIANGLES, 'Fallback mode changed')
    nanite_settings[p] = state
    mesh_after[p] = mesh_state(mesh)
    require(mesh_after[p] == mesh_before[p], 'Mesh source geometry/collision/materials changed: '+p)
require(mesh_state(engine_cube) == engine_cube_before, 'Engine cube changed')
after = {label: actor_state(a) for label, a in actors.items()}
require(before.keys() == after.keys(), 'Actor set changed')
edited = []
for label, state in after.items():
    expected = dict(before[label])
    if label in labels and expected['mesh'] == path(engine_cube):
        expected['mesh'] = path(cube)
        edited.append(label)
    require(state == expected, 'Actor transform/collision/material/presentation changed: '+label)
if not VERIFY:
    require(LEVEL.save_current_level(), 'Map save failed')
    require(unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True), 'Dirty package save failed')
else:
    require(saved['actors_after'] == after, 'Fresh actor readback differs')
    require(saved['meshes_after'] == mesh_after, 'Fresh mesh readback differs')
    require(saved['nanite_settings'] == nanite_settings, 'Fresh Nanite readback differs')
descs = {str(d.label): d for d in WP.get_actor_descs()}
report = dict(task_id='D17-02', mode='readback' if VERIFY else 'author',
    spec_sha256=hashlib.sha256(SPEC.read_bytes()).hexdigest(), labels=labels,
    baseline_sha256=hashlib.sha256(BASELINE.read_bytes()).hexdigest(),
    actors_before=before, actors_after=after, engine_cube=engine_cube_before,
    meshes_before=mesh_before, meshes_after=mesh_after,
    render_bounds_before=render_bounds_before, render_bounds_after={p: render_bounds(m) for p,m in meshes.items()},
    material_usage=material_usage,
    nanite_settings=nanite_settings, material_packages=sorted(material_parents),
    mesh_packages=sorted(p.split('.')[0] for p in meshes),
    edited_actor_packages=sorted(str(descs[label].actor_package) for label in edited),
    diagnostic_actor_packages=sorted(str(descs[label].actor_package) for label in labels),
    preservation='Every StaticMeshActor transform, material binding, collision profile, mobility, visibility and tag preserved. Editable LOD0 positions, triangle connectivity, source bounds and aggregate collision geometry unchanged. Derived Nanite render bounds recorded separately; they may expand after native rebuilding.',
    slice_acceptance=False)
REPORT.write_text(json.dumps(report, indent=2)+'\n')
unreal.log('D17_TRAVERSAL_SHADOWS COMPLETE')
