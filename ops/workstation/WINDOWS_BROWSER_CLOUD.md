# MiniTZ Windows Browser Cloud Resource

`windows-browser-cloud` is a non-authoritative MiniTZ Resource for authenticated browser work on the configured Windows VPS.

The transport is SSH to `minitz-windows-browser`. The Windows interactive bridge is `MiniTZBrowserBridge`; it processes bounded JSON requests from `C:\Users\Administrator\MiniTZ\browser_bridge` while the Administrator desktop session is available.

The Resource owns no Task status, order, completion, acceptance, memory, or progression authority. Browser state is evidence only after MiniTZ records and validates the observed result.

## Capabilities

- `browser.actions`
- `hosting.cpanel`

## Registered targets

The exact non-secret target identities are in `windows-browser-cloud-targets.json`.

- `crazcodez` -> `crazcodez.com` on `ircp1.my-servers.us:2083`
- `taghdisilabs` -> `taghdisilabs.digital` on `s1.my-servers.us:2083`

No cPanel session URL, cookie, password, API token, SSH private key, or browser credential is stored in the repository.

## Commands

`minitz-browser-cloud targets` lists configured non-secret targets.

`minitz-browser-cloud status` verifies SSH transport, bridge response, and current target-tab presence.

`minitz-browser-cloud activate <target>` selects the configured cPanel tab through the interactive bridge.

If the bridge is not responding, the adapter may start the existing `MiniTZBrowserBridge` scheduled task and retry. Provider failure is nonblocking for unrelated MiniTZ work.
