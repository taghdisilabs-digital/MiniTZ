# MiniTZ Games Project Execution Authority

This subtree is the current MiniTZ Games project inside the single MiniTZ OS source tree. MiniTZ OS owns task, resource, memory, capability and execution authority. Game-specific Unreal source/assets remain project scope.

## Serialized compatibility boundary

Existing Unreal module/package/class/map names that contain the predecessor product name are compatibility identifiers only. They have zero product or architecture authority and must not be mechanically renamed while referenced by serialized `.uasset`/`.umap` content. Removal requires an Unreal-aware redirect/resave migration with asset readback. See `docs/MINITZ_UNREAL_COMPATIBILITY.json`.

## Project rules

Preserve working gameplay, Unreal assets, runtime contracts, test evidence and accepted project behavior. Reuse MiniTZ OS capabilities instead of creating duplicate schedulers, memory systems, routing planes, object stores, validation engines or provider authorities in this project. Windows is not an execution worker unless the owner explicitly re-enables it.
