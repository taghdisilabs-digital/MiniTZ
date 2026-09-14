# MiniTZ Authenticated Human Browser Design

**Status:** Owner-approved design, implementation pending written-spec review.

## Goal

Make authenticated browser/UI operation a first-class MiniTZ OS capability so MiniTZ can complete normal user tasks even when no official API exists.

MiniTZ must be able to reuse an isolated logged-in browser session, understand the current page, act through the UI, verify the result, preserve useful state, and ask Mahdi only at genuine human-only boundaries.

## Product model

This is not a LinkedIn-specific bot. LinkedIn profile editing is one instance of the general capability `browser.authenticated_gui_action`.

MiniTZ owns intent, task/run identity, policy, resource selection, evidence, memory, credentials references, and outcome verification. Browser-Use, Playwright, Chromium, remote machines, or future browser engines are replaceable implementation Resources.

Default execution remains on the L40 MiniTZ environment. Windows VPS is never a MiniTZ worker; it is an owner-explicit auxiliary endpoint only.

## Session and profile isolation

Each authenticated automation identity uses its own persistent browser profile/user-data directory. Sessions, cookies, history, and site login state persist between runs without copying another human profile.

Mahdi automation sessions must remain isolated from Patrick and from Mahdi's ordinary interactive Chrome profile. MiniTZ must not focus, scroll, type into, navigate, or reuse the owner's foreground browser as a convenience path.

Background operation is the default. A headed visible browser is used only when observation or human intervention is materially required.
## Identity, credentials, and form filling

MiniTZ resolves email addresses, usernames, profile URLs, company data, and other reusable identity facts from MiniTZ-owned verified identity/context records with provenance and scope.

Raw passwords, API keys, refresh tokens, cookies, session tokens, and equivalent secrets never enter prompts, semantic memory, ordinary logs, task files, or evidence text. Browser sessions and credential subsystem references supply authentication without exposing secret values.

Form filling is contextual rather than template-driven. MiniTZ reads page meaning and fills only fields required for the current task. Optional or unknown fields are skipped unless materially required; MiniTZ does not invent facts.

Human-facing text must be task-specific and natural. It must not inject generic bot language or identify itself as an AI unless the task or service explicitly requires that disclosure.

## Interaction behavior

Preferred interaction order is structured browser state/DOM/accessibility semantics first, visual interaction when structured state is unavailable, and raw coordinate interaction only as a bounded fallback.

MiniTZ validates page state before and after meaningful actions, avoids rapid duplicate submissions, uses realistic waits for real state transitions, and never treats a click alone as proof of success.

Downloads and uploads use task-bounded directories and are verified by file identity/readback when completion matters.

CAPTCHA, 2FA, recovery prompts, consent decisions, identity confirmation, or other human-only friction pauses the automation. MiniTZ calls Mahdi through the owner-attention capability, waits for intervention, then resumes the same Task/Run/browser session.

MiniTZ does not implement CAPTCHA solving, anti-bot bypass, stealth-evasion, or security-control circumvention as a product capability.
## Safety and authority boundaries

Financial, billing, payment, card, purchase, transfer, and equivalent money surfaces are denied by default. Access requires an explicit current owner request naming the exact action and does not become reusable background authority.

Browser automation has no Task Program progression authority and no independent canonical memory. Every mutation is bound to the current MiniTZ Task/Run and evidence lineage.

MiniTZ chooses the best execution path for each task: direct API/connector when it is safer and more reliable, authenticated browser UI when an API is absent or insufficient, and local app/terminal/OS capabilities when those are the correct surface.

## Capability contract

The initial capability family is:

- `browser.authenticated_session.open|resume|close`
- `browser.authenticated_gui_action.observe|navigate|edit|submit|verify`
- `browser.identity.resolve`
- `browser.file.download|upload|verify`
- `owner.attention.request`
- `browser.human_boundary.pause|resume`

Action results use truthful `running`, `succeeded`, `failed`, `cancelled`, or `needs_human` states and preserve bounded raw evidence plus normalized state changes.

## Acceptance examples

A LinkedIn profile update without an official edit API is valid when MiniTZ resumes the isolated Mahdi session, navigates to the correct profile editor, changes only requested fields, saves, reloads/readbacks the profile, and records the verified result without touching Patrick or the owner's foreground browser.

The same capability must generalize to GitHub, Gmail, hosting panels, account settings, ordinary web forms, uploads, downloads, and comparable authenticated user workflows without service-specific authority becoming architecture.

## Qualification

Tests must prove profile isolation, persistent-session reuse, foreground-browser non-interference, contextual form filling, human-boundary pause/resume, download/upload verification, financial-surface denial, credential non-leakage, truthful failure reporting, and post-action readback verification.

Production/commercial MiniTZ must not depend on a non-commercial browser or voice model. Temporary non-commercial development Resources remain explicitly replaceable and disabled from commercial release qualification.