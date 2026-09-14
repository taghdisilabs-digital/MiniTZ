# D02-01 — Open-world streaming and continuity

The editable continuation map is `/Game/Maps/BiellaOpenWorldMap`. Open it in
Unreal Editor and Play, or launch the Development Editor with the project path,
that map path and `-game`. Normal third-person movement, camera, weapon,
pressure, HUD and restart behavior reuse the first playable slice. The default
Demo 01 map remains its existing entry point.

This is a connected streaming blockout, not an accepted city identity, final
district count, final art pass or shipping performance qualification. Six
4000 cm street sections connect a covered room, a ramp and a terrace. These
dimensions describe the current testable content, not the eventual city's
geography. Meshes, material instances, external actors, Data Layer, HLOD layer
and map are editable Unreal assets. Movable native lighting covers the indoor
route, and a persistent atmosphere/skylight keeps outdoor geometry readable.
The authoring script preserves existing
actor identities on rerun and can read the saved assets back in a fresh editor.

`Content/Python/author_open_world.py` creates or updates those assets through
Unreal's native editor APIs. Native World Partition owns cell residency and
external actor lifetimes; native HLOD owns distant static geometry. Collision
uses the near-field authored meshes, and dynamic Recast rebuilds from currently
resident geometry. The runtime does not create lookalike streaming regions or
replace world streaming with hidden actor visibility toggles.

`BiellaWorldContinuity.h/.cpp` provides the game-specific continuation behavior:

- A player streaming source prioritizes the upcoming route. Traversal waits
  when supporting collision or local navigation is unavailable. Swept floor
  following permits the connected ramp while retaining capsule obstruction.
- Explicit relocations request destination residency asynchronously, then
  require floor, navigation and a clear capsule before moving. Unavailable
  destinations time out observably and retain the current location; requests
  can be retried. Unprepared debug relocation into a void recovers to the last
  supported location. Defeat cancels a pending destination request so it cannot
  pin distant cells after the player has died.
- A match-local world subsystem stores stable actor identity, transform,
  health and defeat state independently of cell residency. On reentry, actors
  restore that state and consume the current authoritative pressure revision.
  Defeat reconstruction does not replay damage, effects or objective rewards.
- The bounded streamed encounter stays within its authored residency bounds.
  It can participate in local gameplay without chasing into a cell that does
  not own its lifetime. Population migration/scaling is a separate task.
- The first slice's objective continues to track its own encounter. The
  streamed continuity actor has separate identity and cannot become a new
  Demo objective target merely because a cell loads again.
- Persistent mission actors become dormant when their supporting terrain or
  navigation leaves residency. Their health and mission identity survive, but
  AI, movement, collision and combat participation stop until support returns.
  Restoring residency respects prior state and cannot resurrect a defeated
  actor. This permits native cells to unload without leaving live actors over
  missing collision.

The store lasts for one `UWorld`: ordinary cell unload/reload retains state;
map restart destroys it and starts a new match. It is not a disk save system.
No new city lore, weather, vehicle, population scale or platform target is
selected here.

Cosmetic role components disable navigation before assigning their mesh.
Unreal can queue mesh navigation data before component registration; assigning
the mesh first left obsolete geometry at world origin despite the components'
later navigation flags. The shared pawn initialization now prevents that stale
geometry, and the original Demo encounter remains covered by regression runs.

The live automation name is `BiellaGames.D02.WorldStreaming`. It requires a
fresh `-BiellaStreamingOutput=<directory>`, actual rendering and normal wall
time. It exercises possessed Enhanced Input traversal, interior and elevation
changes, collision and Recast routes, distant unload and return, damage and
defeat reconstruction, pressure continuity, relocation failure and retry.
The test records cell lifetimes, frame intervals, process memory and native
runtime captures. After automation discovery it reopens the actual map with a
pre-tick fixture that holds opponent movement and attacks. Player possession,
Enhanced Input, collision, navigation, pressure, objective, streaming and
rendering run normally. Initial capture waits for the actual shader compiler
to settle; the wait stays in the measured frame record. A focused transition
also verifies that previously active actor and movement ticks resume after
dormancy, including repeated calls. The fixture preserves authored encounter identities,
health and collision; it does not replace unloaded actors or reset their state.
These controls apply only inside automation; authored actors retain their
normal autonomous behavior for interactive play.

The task acceptance report under `Build/OpenWorld/` records the observed
results, exact tested file identities, reproduction commands and limitations.
Generated runtime captures remain `GENERATED_DRAFT` until owner acceptance.
