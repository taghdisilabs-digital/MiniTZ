"""Author D01-42 editable Niagara bursts (GENERATED_DRAFT).

UnrealEditor BiellaGames.uproject -ExecutePythonScript=<this file>
  -EnablePlugins=PythonScriptPlugin,CascadeToNiagaraConverter -unattended
  -nullrhi -nosound -nop4 (Linux: run as unreal under xvfb-run)

Graph authoring needs the full editor because Niagara stack customization uses
Slate. Read-only verification may use -run=pythonscript -script=<this file>.

Epic's editor-only graph adapter authors ordinary Niagara modules; the saved
systems have no Cascade converter runtime dependency. Existing assets are
preserved. To intentionally rebuild, run the companion standalone Python helper
run_demo_feedback_vfx_authoring.py --rebuild; it validates fresh candidates
before replacing the three canonical assets. -D01VerifyFeedbackVFX checks
saved asset types/material depth policy without rewriting content.
"""
import json
import unreal as ue

ROOT = '/Game/Feedback'
LIB = ue.MaterialEditingLibrary
SYSTEMS = {
    'NS_Muzzle': [
        dict(name='WarmCore', count=1, lifetime=.075, size=(20., 12.), color=(5., 2.8, .9, .9), velocity=((0., 0., 0.), (0., 0., 0.))),
        dict(name='MuzzleSparks', count=4, lifetime=.12, size=(3.5, 3.5), color=(3., 1.8, .65, .8), velocity=((110., -45., -35.), (220., 45., 35.))),
    ],
    'NS_Impact': [
        dict(name='SurfaceSparks', count=6, lifetime=.24, size=(3.5, 3.5), color=(2.5, 2., 1.3, .9), velocity=((45., -80., -80.), (140., 80., 80.))),
        dict(name='SurfaceDust', count=5, lifetime=.36, size=(12., 12.), color=(.32, .30, .27, .22), velocity=((20., -28., -28.), (45., 28., 28.))),
    ],
}


def require(condition, message):
    if not condition:
        raise RuntimeError('D01_042_VFX FAIL: ' + message)


def material():
    path = ROOT + '/M_FeedbackParticle'
    mat = ue.load_asset(path)
    if mat is not None:
        return mat
    require(not VERIFY, 'Saved particle material missing')
    if mat is None:
        mat = ue.AssetToolsHelpers.get_asset_tools().create_asset(
            'M_FeedbackParticle', ROOT, ue.Material, ue.MaterialFactoryNew())
    LIB.delete_all_material_expressions(mat)
    mat.set_editor_property('blend_mode', ue.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property('shading_model', ue.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property('two_sided', True)
    mat.set_editor_property('disable_depth_test', False)
    mat.set_editor_property('used_with_niagara_sprites', True)
    def node(cls, x, y):
        return LIB.create_material_expression(mat, cls, x, y)
    def connect(a, output, b, input_name):
        require(LIB.connect_material_expressions(a, output, b, input_name), 'Material graph input ' + input_name)
    tex = node(ue.MaterialExpressionTextureCoordinate, -900, 100)
    center = node(ue.MaterialExpressionSubtract, -700, 100)
    center.set_editor_property('const_b', .5)
    connect(tex, '', center, 'A')
    length = node(ue.MaterialExpressionLength, -500, 100)
    connect(center, '', length, '')
    radius = node(ue.MaterialExpressionMultiply, -320, 100)
    radius.set_editor_property('const_b', 2.)
    connect(length, '', radius, 'A')
    invert = node(ue.MaterialExpressionOneMinus, -150, 100)
    connect(radius, '', invert, '')
    clamp = node(ue.MaterialExpressionSaturate, 30, 100)
    connect(invert, '', clamp, '')
    soft = node(ue.MaterialExpressionPower, 200, 100)
    soft.set_editor_property('const_exponent', 2.)
    connect(clamp, '', soft, 'Base')
    color = node(ue.MaterialExpressionParticleColor, -600, -200)
    age = node(ue.MaterialExpressionParticleRelativeTime, -600, 400)
    fade = node(ue.MaterialExpressionOneMinus, -400, 400)
    connect(age, '', fade, '')
    alpha = node(ue.MaterialExpressionMultiply, 380, 160)
    connect(soft, '', alpha, 'A')
    connect(color, 'A', alpha, 'B')
    lifetime = node(ue.MaterialExpressionMultiply, 540, 200)
    connect(alpha, '', lifetime, 'A')
    connect(fade, '', lifetime, 'B')
    depth = node(ue.MaterialExpressionDepthFade, 700, 200)
    depth.set_editor_property('fade_distance_default', 6.)
    connect(lifetime, '', depth, 'Opacity')
    require(LIB.connect_material_property(color, 'RGB', ue.MaterialProperty.MP_EMISSIVE_COLOR), 'Material emissive')
    require(LIB.connect_material_property(depth, '', ue.MaterialProperty.MP_OPACITY), 'Material opacity')
    require(not LIB.recompile_material(mat), 'Material compiler errors')
    require(ue.EditorAssetLibrary.save_loaded_asset(mat, only_if_is_dirty=False), 'Material save')
    return mat


def author(name, specs, mat):
    path = ROOT + '/' + name
    existing = ue.load_asset(path)
    if existing is not None:
        return existing
    require(not VERIFY, 'Missing ' + path)
    fx = ue.FXConverterUtilitiesLibrary
    category = ue.ScriptExecutionCategory
    type_ = ue.NiagaraScriptInputType
    system = ue.AssetToolsHelpers.get_asset_tools().create_asset(name, ROOT, ue.NiagaraSystem, ue.NiagaraSystemFactoryNew())
    require(system is not None, 'Cannot create ' + name)
    context = fx.create_system_conversion_context(system)
    try:
        for spec in specs:
            emitter = context.add_empty_emitter(spec['name'])
            emitter.set_local_space(True)
            emitter.set_sim_target(ue.NiagaraSimTarget.CPU_SIM)
            def module(label, path, stage, version=None):
                data = fx.create_asset_data(path)
                args = ue.CreateScriptContextArgs(data, version) if version else ue.CreateScriptContextArgs(data)
                return emitter.find_or_add_module_script(label, args, stage)
            def set_(script, key, input_):
                require(script.set_parameter(key, input_), spec['name'] + ' rejected ' + key)
            state = module('EmitterState', '/Niagara/Modules/Emitter/EmitterState.EmitterState', category.EMITTER_UPDATE, [1, 0])
            set_(state, 'Life Cycle Mode', fx.create_script_input_enum('/Niagara/Enums/ENiagaraEmitterLifeCycleMode.ENiagaraEmitterLifeCycleMode', 'Self'))
            set_(state, 'Inactive Response', fx.create_script_input_enum('/Niagara/Enums/ENiagaraInactiveMode.ENiagaraInactiveMode', 'Complete (Let Particles Finish then Kill Emitter)'))
            set_(state, 'Loop Behavior', fx.create_script_input_enum('/Niagara/Enums/ENiagara_EmitterStateOptions.ENiagara_EmitterStateOptions', 'Once'))
            set_(state, 'Loop Duration', fx.create_script_input_float(.01))
            burst = module('SingleBurst', '/Niagara/Modules/Emitter/SpawnBurst_Instantaneous.SpawnBurst_Instantaneous', category.EMITTER_UPDATE, [1, 1])
            set_(burst, 'Spawn Count', fx.create_script_input_int(spec['count']))
            set_(burst, 'Spawn Time', fx.create_script_input_float(0.))
            init = module('InitializeParticle', '/Niagara/Modules/Spawn/Initialization/V2/InitializeParticle.InitializeParticle', category.PARTICLE_SPAWN)
            set_(init, 'Lifetime', fx.create_script_input_float(spec['lifetime']))
            emitter.set_parameter_directly('Particles.SpriteSize', fx.create_script_input_vec2(ue.Vector2D(*spec['size'])), category.PARTICLE_SPAWN)
            random = fx.create_script_context(ue.CreateScriptContextArgs(fx.create_asset_data('/Niagara/DynamicInputs/UniformRange/V2/RandomRangeVector.RandomRangeVector')))
            set_(random, 'Minimum', fx.create_script_input_vector(ue.Vector(*spec['velocity'][0])))
            set_(random, 'Maximum', fx.create_script_input_vector(ue.Vector(*spec['velocity'][1])))
            emitter.set_parameter_directly('Particles.Velocity', fx.create_script_input_dynamic(random, type_.VEC3), category.PARTICLE_SPAWN)
            module('ParticleState', '/Niagara/Modules/Update/Lifetime/ParticleState.ParticleState', category.PARTICLE_UPDATE, [1, 1])
            # A direct assignment's color clipboard value remained default-white
            # in the first runtime dataset. Use Epic's supported Color-module
            # conversion path, with explicit RGB/alpha dynamic inputs, and apply
            # it after initialization on update so the saved authored values win.
            color_input = fx.create_script_context(ue.CreateScriptContextArgs(fx.create_asset_data(
                '/Niagara/DynamicInputs/LinearColor/MakeLinearColorFromVectorAndFloat.MakeLinearColorFromVectorAndFloat')))
            set_(color_input, 'Vector (RGB)', fx.create_script_input_vector(ue.Vector(*spec['color'][:3])))
            set_(color_input, 'Float (Alpha)', fx.create_script_input_float(spec['color'][3]))
            color_module = module('FeedbackColor', '/Niagara/Modules/Update/Color/Color.Color', category.PARTICLE_UPDATE)
            set_(color_module, 'Color', fx.create_script_input_dynamic(color_input, type_.LINEAR_COLOR))
            module('SolveVelocity', '/Niagara/Modules/Solvers/SolveForcesAndVelocity.SolveForcesAndVelocity', category.PARTICLE_UPDATE)
            renderer = ue.NiagaraSpriteRendererProperties()
            renderer.set_editor_property('material', mat)
            emitter.add_renderer('DepthTestedSprites', renderer)
        context.finalize()
        require(ue.EditorAssetLibrary.save_loaded_asset(system, only_if_is_dirty=False), 'System save ' + name)
        return system
    finally:
        context.cleanup()


command = ue.SystemLibrary.get_command_line()
VERIFY = '-D01VerifyFeedbackVFX' in command
require('-D01RebuildFeedbackVFX' not in command,
        'Use run_demo_feedback_vfx_authoring.py --rebuild to preserve rooted canonical assets')
mat = material()
require(isinstance(mat, ue.Material), 'Particle material type')
require(not mat.get_editor_property('disable_depth_test'), 'VFX must obey scene depth')
require(mat.get_editor_property('blend_mode') == ue.BlendMode.BLEND_TRANSLUCENT, 'Expected translucent sprites')
for name, specs in SYSTEMS.items():
    system = author(name, specs, mat)
    require(isinstance(system, ue.NiagaraSystem), name + ' type')
    ue.log('D01_042_VFX ASSET ' + json.dumps({'path': system.get_path_name(), 'authoring_spec': specs, 'authored_total_burst_particles': sum(s['count'] for s in specs), 'authored_maximum_particle_lifetime': max(s['lifetime'] for s in specs), 'forward_axis': '+X', 'local_space': True, 'status': 'GENERATED_DRAFT'}, sort_keys=True))
ue.log('D01_042_VFX PASS saved Niagara assets and depth-tested material')

if '-ExecutePythonScript=' in command:
    ue.SystemLibrary.quit_editor()
