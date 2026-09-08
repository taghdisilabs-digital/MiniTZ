# D17-01 — service circuit candidate

**INCOMPLETE.** The editable candidate selects the existing open-world entry,
Street01 population, service bay, interior, raised terrace and Street03 return.
It binds the current owner visual direction in `scenario.json`. It does not yet
provide the required 10–20 minutes of representative gameplay.

Three fresh packaged-game runs used ordinary X11 movement/fire input, normal
third-person cameras and real-time simulation. Native objective success occurred
after 34.10, 12.81 and 9.41 simulation seconds, respectively. Success disables
movement/look, preventing the remaining route. The clips retain a two-second
terminal tail, which is excluded from active-play duration. No pressure transition
was observed. The first run's player shot and autonomous combat are recorded in
its input log, gameplay telemetry and unedited video. Different AI outcomes in
later runs are observations, not a claim that the HUD changed gameplay.

The sole native edit reduces the two upper HUD panels and removes their redundant
status heading. The Linux Development build and the existing live HUD and
localization/settings/accessibility regression tests pass. Those tests use
fixtures and are kept separately from the raw captures. The compact HUD remains
a partial improvement; placeholder characters, primitive sparse geometry, flat
surfaces, missing infection takeover and absent storm/practical-light contrast
still violate the final visual contract.

`qualification.json` indexes exact editable inputs, build receipts, raw video,
input, telemetry, regression evidence and the remaining criteria. Run
`python3 tests/qualify_d17_01.py` from the Project root to recheck current evidence
integrity and regenerate that index. This command reports incomplete acceptance;
it cannot turn the recorded short runs into a qualified slice.

The two HUD captures use the unchanged installed D08 Linux Development payload
with exactly one native executable overlaid read-only. Each run's
`resolved-package.json` lists every exposed file; its namespace verification
checks actual bytes and permissions before launch. `native-source.json` binds
the build to editable source. All cooked content, configuration and reflected
declarations match the baseline, so no recook was needed. No predecessor package
was copied or renamed. The exact native delta is retained at the canonical
artifact path recorded in the manifests. These are Linux diagnostics, with no
Win64 Shipping claim. The capture rate is the recorder's rate, not measured game
FPS. Raw clips have no audio track.

The baseline run predates the added namespace verification. It retains its exact
base-install verification, game command, input, logs and video. Its original
untracked harness version is identified by hash but is not recoverable as exact
source; later HUD runs retain matching harness snapshots. This does not change
the preserved baseline game package identity.

Resume D17-01 from these bytes. First resolve the selected route's early terminal
and player-reachable pressure integration using existing gameplay/content; do
not pad time, force pressure, reset actors or stitch restarts into proof. The next
independent visual creation boundary is the existing service-bay approach:
author its industrial surface, lighting and infection layer against the bound
owner direction while preserving accepted collision and gameplay. Rebuild only
affected inputs and capture the resulting normal gameplay. Both the continuous
duration/interaction criterion and zero-major visual-defect criterion must pass
before this task can close.

Local persistence belongs to this task commit. The Auto Feeder owns the existing
GitHub/Drive publication cursor and production-state transition; this record does
not claim remote publication or advance production.
