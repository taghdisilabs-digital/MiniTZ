# Biella Universe Website

Real Website Project workspace for biellagames.dev under `website/` in the canonical patrickminitz-web/biella-engine monorepo.

Build: npm run build
Contract tests: npm test
Browser qualification: npm run test:browser

The website consumes Engine and Games evidence. It never substitutes website visuals or interactions for Engine implementation or playable game runtime evidence.

## Private control console

The canonical website contains a private `/control/` browser observer for the one current production context. It no longer splits the observer into Website / Engine / Games sections.

It provides read-only current production state, live task activity, outputs, services/resources, hardware, workers, and source identity. It reads through the existing `/v1/control` gateway contract and does not invent project state. Dialog and capability-run routes return `405 control_read_only` for every authenticated role, so opening or using the console as an observer cannot steer production.

The private observer hostname is control.biellagames.dev. The public biellagames.dev site includes the read-only `/live/` production theatre and periodic homepage showcase; neither public surface is a production input.

## Live projection architecture

The public site does not use a permanent AI agent to keep production facts current. `/live/`, the homepage showcase, and investor execution metrics consume the read-only VPS projection (`/live-api/snapshot` + SSE `/live-api/events`). The static Website is rebuilt only for Website source/design changes; task progress, model changes, validations and new eligible runtime artifacts appear through the projection without a Website commit.
