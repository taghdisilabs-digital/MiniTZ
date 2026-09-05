# Biella Universe Website

Real Website Project workspace for biellagames.dev, isolated on the website branch of patrickminitz-web/biella-engine so Engine main execution is not mutated by website work.

Build: npm run build
Contract tests: npm test
Browser qualification: npm run test:browser

The website consumes Engine and Games evidence. It never substitutes website visuals or interactions for Engine implementation or playable game runtime evidence.

## Private control console

The Website branch now contains a private /control/ browser console for the three Biella lanes:

- Website
- Engine
- Games

It provides Overview, Live dialog, Capabilities & Run, Connected services, Milestones, Hardware & API usage, Running workers, and Current files. It reads through the existing /v1/control gateway contract and does not invent project state. The operator and observer roles are enforced by that gateway.

The intended Cloudflare hostname is control.biellagames.dev. The existing public biellagames.dev site remains the public Website surface.
