# Biella Games

This repository is the standalone implementation workspace for the Biella Games game project.

## Repository boundary

- This repository is game-project scope.
- `patrickminitz-web/biella-engine` is the separate Biella Engine repository and must not be used as a container for Biella Games game-specific implementation merely to avoid creating a game repository.
- Biella Engine may later be consumed through explicit replaceable integration boundaries where useful; game code, content, art direction, mechanics, environments, UI, branding, and project-specific data remain here.
- Historical MiniTZ and BoosTZ repositories are not implementation bases for this project.

## Current state

The repository now contains the accepted Biella Games execution authority, technical-decision registry, implementation sequence, and runtime contracts. The real engine-specific editable game project has not yet been created in this repository.

Read `AGENTS.md`, `docs/TECHNICAL_DECISIONS.md`, and `docs/IMPLEMENTATION_SEQUENCE.md` before implementation work.
