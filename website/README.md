# Biella Universe Website

Real Website Project workspace for biellagames.dev under `website/` in the canonical patrickminitz-web/biella-engine monorepo.

Build: npm run build
Contract tests: npm test
Browser qualification: npm run test:browser

The website consumes Engine and Games evidence. It never substitutes website visuals or interactions for Engine implementation or playable game runtime evidence.

## Private control console

The Website branch now contains a private /control/ browser console for the three Biella lanes:

- Website
- Engine
- Games

It provides read-only current production state, live task activity, outputs, services/resources, hardware, workers, and source identity. It reads through the existing `/v1/control` gateway contract and does not invent project state. Dialog and capability-run routes return `405 control_read_only` for every authenticated role, so opening or using the console as an observer cannot steer production.

The private observer hostname is control.biellagames.dev. The public biellagames.dev site includes the read-only `/live/` production theatre and periodic homepage showcase; neither public surface is a production input.
