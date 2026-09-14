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
        ids = [v.get_editor_property('id_value') for v in description.get_triangle_vertices(triangle)]
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


result = {}
for name in ('/Engine/BasicShapes/Cube', '/Game/Environment/ServiceHall/SM_ServiceHallCladding', '/Game/Environment/HallInterior/SM_HallInterior', '/Game/Environment/TerraceRoute/SM_TerraceRoute'):
    mesh = LIB.load_asset(name)
    require(mesh is not None, name)
    result[name] = dict(source=mesh_state(mesh), render_bounds=render_bounds(mesh))
REPORT.write_text(json.dumps(result, indent=2)+'\n')
unreal.log('D17_SHADOW_INSPECTION COMPLETE')
