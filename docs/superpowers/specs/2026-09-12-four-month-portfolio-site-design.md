# Four-Month Portfolio Website Design

Status: owner-approved implementation direction
Date: 2026-09-12
Target: https://taghdisilabs.digital/

## Product statement
The site presents roughly four months of build-first work without making visitors decode the archive. The public experience has five simple destinations: Home, 4 Months, Projects, Visual Archive, and Live MiniTZ.

## Navigation and information architecture
- Home: understand the founder/work in under ten seconds.
- 4 Months: chronological story from May through September 2026.
- Projects: filterable evidence-backed portfolio, deduplicated by underlying creation.
- Visual Archive: deliberately dense media wall for scale and historical depth.
- Live MiniTZ: preserve the existing read-only production theatre at `/live/`.
- Keep `/investors/` and `/control/` working; they are secondary surfaces, not primary nav.

## Hero
Use `FOUR MONTHS.` as the dominant message. Explain the progression from first deployments and websites through games, production systems, client work, Biella, and the current MiniTZ OS. Do not say “years.”

## Portfolio truth model
Every portfolio record carries category, period/date, short description, evidence status, optional evidence link, and media refs. Duplicate backups/releases are provenance, not separate creations. Historical failures remain visible with labels such as FAILED ITERATION or SUPERSEDED.

G22/G25 must never be presented as owner-accepted complete games from package names alone. G26-G50 remain unrecovered/unknown. Missing media is shown as `SOURCE / EVIDENCE ONLY`, never replaced with unrelated art.

## Visual model
Use actual project media only. Historical/rough/failed visuals are allowed and labeled. Initial deployment may publish every currently recovered public-safe visual selected in the media manifest; the build supports adding more without redesigning pages.

## Visual language
Near-black/graphite base, warm ivory text, operational cyan, restrained amber/red for evidence states, oversized editorial typography, sharp media crops, large cinematic bands, dense archive grids, minimal rounded-card SaaS styling. Motion should clarify navigation, not decorate.

## Routes
- `/` — story + timeline + projects + archive preview + live teaser.
- `/archive/` — full filterable visual archive.
- `/live/` — existing MiniTZ live theatre unchanged except navigation back to portfolio where safe.
- `/investors/` — existing investor surface preserved.
- `/control/` — existing private observer preserved.

## Deployment safety
Preserve deployed release `e071c1bd1843389da16f6924bb88f5f062878196` and its byte-identical rollback snapshot under `/mnt/biella-extra/website-version-archive/2026-09-12-pre-portfolio-e071c1bd1843`.

New release must pass existing contract tests, new portfolio tests, build, desktop browser validation, mobile browser validation, deployment readback, and public HTTP readback. Deployment must create a new immutable release and leave the prior release intact.
