# Prompt 02 — Real Execution and Creation Capability Map

## Objective

Carry forward broad production intelligence while keeping the Biella kernel small, extensible, and project-neutral.

Core model:

`typed Task -> dynamic Graph -> productive Nodes -> capabilities -> implementations -> Resources -> durable Artifacts/Events/Knowledge`

Task and Capability are semantic. Provider, tool, model, GPU, cloud, and machine are implementation/runtime state.

## Productive Node families

`MODEL_CALL`, `SPECIALIST_TASK`, `TOOL_CALL`, `SHELL_EXECUTE`, `BROWSER_EXECUTE`, `COMPUTER_EXECUTE`, `BUILD`, `TEST`, `RENDER`, `ASSET_PROCESS`, `MEDIA_PROCESS`, `PACKAGE`, `TRANSFER`, `VALIDATE`, `EVALUATE`.

Waiting, cancellation, recovery, checkpointing, and finalization are primarily execution-control semantics, not mandatory productive stages.

## Execution modes

Direct execution for deterministic bounded work; tool loops for iterative model/tool work; compiled Graphs for dependent/independent multi-step work; persistent environments for long-running repository/browser/DCC/simulation/build/model work while durable Run state remains outside any one process.

## Capability namespaces

### Software
`software.inspect`, `software.search`, `software.architecture`, `software.engineer`, `software.modify`, `software.debug`, `software.refactor`, `software.test`, `software.build`, `software.run`, `software.profile`, `software.package`, `software.validate`

### Web
`web.inspect`, `web.frontend`, `web.backend`, `web.fullstack`, `web.component`, `web.route`, `web.api`, `web.build`, `web.run`, `web.test`, `web.browser_validate`, `web.performance`, `web.accessibility`, `web.package`

### Browser/computer
`browser.open`, `browser.navigate`, `browser.inspect`, `browser.extract`, `browser.click`, `browser.type`, `browser.upload`, `browser.download`, `browser.screenshot`, `browser.submit`

### Research
source discovery, web/literature research, repository research, comparative analysis, technology evaluation, architecture analysis, evidence synthesis

### Model/reasoning
`model.infer`, `model.reason`, `model.classify`, `model.extract`, `model.transform`, `model.generate_structured`

### Retrieval
`retrieval.extract`, `retrieval.chunk`, `retrieval.embed`, `retrieval.search`, `retrieval.rerank`, `retrieval.compile_context`

### Data/database
`database.inspect`, `database.query`, `database.transaction`, `database.migrate`, `database.export`, `database.import`, `data.transform`, `data.validate`

### Build/package/publish
`build.compile`, `build.bundle`, `build.test`, `package.assemble`, `package.verify`, `publish.upload`, `publish.deploy`, `publish.release`, `publish.verify`

### Game
`game.inspect`, `game.import`, `game.modify`, `game.build`, `game.run`, `game.test`, `game.profile`, `game.capture`, `game.export`, `game.package`. Game engine is an adapter.

### 3D
`3d.inspect`, `3d.model`, `3d.mesh_edit`, `3d.topology`, `3d.uv`, `3d.material`, `3d.scene`, `3d.convert`, `3d.optimize`, `3d.preview`, `3d.validate`. Retain editable source when required; a rendered image alone is not 3D-source proof.

### Character/rigging
`character.inspect`, `character.model`, `character.retopology`, `character.uv`, `character.material`, `character.skeleton`, `character.rig`, `character.skin`, `character.weight`, `character.deform_test`, `character.export`, `character.validate`

### Animation
`animation.inspect`, `animation.import`, `animation.generate`, `animation.edit`, `animation.keyframe`, `animation.retarget`, `animation.blend`, `animation.root_motion`, `animation.loop`, `animation.bake`, `animation.export`, `animation.validate`

### Environment/world
`environment.inspect`, `environment.layout`, `environment.terrain`, `environment.structure`, `environment.populate`, `environment.vegetation`, `environment.material`, `environment.collision`, `environment.navigation_prepare`, `environment.lod`, `environment.optimize`, `environment.partition`, `environment.export`, `environment.validate`

### Rendering
`render.inspect`, `render.preview`, `render.frame`, `render.sequence`, `render.batch`, `render.raster`, `render.raytrace`, `render.pathtrace`, `render.pass`, `render.validate`, `render.performance`. Persist frames individually.

### VFX/simulation
`vfx.inspect`, `vfx.particles`, `vfx.smoke`, `vfx.fire`, `vfx.fluid`, `vfx.cloth`, `vfx.hair`, `vfx.rigidbody`, `vfx.softbody`, `vfx.destruction`, `vfx.volumetric`, `vfx.simulate`, `vfx.bake`, `vfx.resume`, `vfx.export`, `vfx.validate`. Do not parallelize sequential solver dependencies incorrectly.

### Image
`image.inspect`, `image.generate`, `image.edit`, `image.inpaint`, `image.outpaint`, `image.mask`, `image.compose`, `image.crop`, `image.resize`, `image.convert`, `image.enhance`, `image.upscale`, `image.texture`, `image.texture_pack`, `image.validate`. Deterministic image work must not require a generative model.

### Audio
`audio.inspect`, `audio.generate`, `audio.edit`, `audio.trim`, `audio.segment`, `audio.resample`, `audio.clean`, `audio.filter`, `audio.normalize`, `audio.mix`, `audio.master`, `audio.convert`, `audio.analyze`, `audio.export`, `audio.validate`

### Video
`video.inspect`, `video.generate`, `video.edit`, `video.trim`, `video.sequence`, `video.compose`, `video.frame_extract`, `video.frame_process`, `video.audio_sync`, `video.subtitle`, `video.transcode`, `video.encode`, `video.mux`, `video.export`, `video.validate`

### Evaluation/learning
`evaluation.quality`, `evaluation.performance`, `evaluation.cost`, `evaluation.reliability`, `evaluation.comparison`. Validation decides whether current output satisfies the Task; evaluation collects comparative evidence.

## Dynamic specialization

A specialist is a runtime composition: `objective + required capabilities + Project/Run context + tools + model/runtime + Resources + output contract`. Patterns may include direct generalist, specialist-as-tool, parallel researchers, coding specialist, visual validator, deterministic tool runner. These are runtime patterns, not permanent authority roles.

## Production proof

Evidence must match the requested product: software source plus required tests/build/runtime; web build/runtime/browser evidence; game build plus play/runtime evidence when required; 3D editable source plus structural/preview checks; render decodable frames tied to source/config; publish upload receipt plus remote read-back.

## Execution prompt

> For the current migration source, extract only reusable semantic capability and production knowledge. Map it to extensible Biella capability names and output contracts. Do not recreate a permanent agent hierarchy or fixed pipeline. Preserve domain-specific expertise as capability/adapter/production-pack data. Identify independent work that can run concurrently, exact dependencies that must remain serial, and the real artifact/evidence required to prove each output.
