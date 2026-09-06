# D03-01 bounded ground support

Observed: the packaged runtime capture `automatic-pso-visual-review-01/default-01-frame-0064.png` shows black margins beside existing floors and under façades. `author_open_world.py` supplies no ground in those regions.

Add a single nonspatial, noncolliding static support mesh with an editable dimensional/material recipe beneath existing floors. Keep every preexisting asset/actor byte, lighting, HLOD and gameplay system intact. No new traversable routes or terrain-completion claim. The existing filtered PBR master supports the new neutral ground material. The cube is an existing engine primitive, not a newly claimed authored mesh.

Validate fresh editor probe/author/readback, existing-asset byte preservation, a native missing/hidden-support control, matching SM6/TSR and SM5/TAA runtime captures and frame times, and affected traversal/environment behavior. Inspect the captures to decide whether remaining horizon edges need a further bounded change. Existing cached editor runs do not qualify a new cooked package.

Local Qwen timed out once and returned on bounded retry. Its broad claims about every camera ray, water tables and renderer coverage are not accepted. Reuse only the suggestion to isolate collision and streaming invariants; exact source/readback/runtime evidence decides acceptance.

Observed save exception: `ground-author-01` failed its initial all-asset-byte gate because Unreal resaved the main map. Preserve that failed receipt. Audit the exact baseline/authored map copies and DiffAssets exports in `ground-map-audit-01`; the engine PostLoad/FixupHLODSetup recreates the non-spatial HLOD partition with an incidental name/debug color. All other preexisting assets must remain byte-identical, existing actor invariants must match, and spatial grid/HLOD/game-mode/navigation settings must match after only that narrow normalization. The task permits this audited map resave; it does not permit arbitrary map changes. Fresh readback must write no asset bytes.
