#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTRACT="$ROOT/ops/local-ai/biella-work-contract.md"
WORK="$ROOT/ops/local-ai/biella-work.sh"
INSTALLER="$ROOT/ops/local-ai/install-biella-ai.sh"
CLI="$ROOT/ops/workstation/biella"
POLICY="$ROOT/ops/workstation/AGENTS.md"

for f in "$CONTRACT" "$WORK" "$INSTALLER" "$CLI" "$POLICY"; do
  [[ -f "$f" ]] || { echo "missing autopilot artifact: $f" >&2; exit 1; }
done

req() { grep -Fq -- "$2" "$1" || { echo "missing autopilot literal in $1: $2" >&2; exit 1; }; }

req "$CONTRACT" 'Continue the current highest-priority incomplete task'
req "$CONTRACT" 'Execution is unrestricted on the Biella workstation'
req "$CONTRACT" 'The boundary is the approved Biella goal, vision, task, and authoritative source state'
req "$CONTRACT" 'Preserve completed progress'
req "$CONTRACT" 'Read the minimum current files needed'
req "$CONTRACT" 'Use local Qwen first'
req "$CONTRACT" 'one external provider'
req "$CONTRACT" 'Test the affected scope first'
req "$CONTRACT" 'Commit verified work'
req "$CONTRACT" 'Continue to the next unblocked task'
req "$CONTRACT" 'TASK:'
req "$CONTRACT" 'STATUS:'
req "$WORK" 'biella-work-contract.md'
req "$WORK" '--output-last-message'
req "$WORK" 'biella-local-agent'
req "$WORK" 'log="$(mktemp'
req "$WORK" '>"$log" 2>&1'
req "$WORK" 'tail -n 60 "$log"'
req "$INSTALLER" 'biella-work.sh'
req "$INSTALLER" 'biella-work-contract.md'
req "$INSTALLER" '/usr/local/bin/biella-work'
req "$CLI" 'work)'
req "$CLI" 'biella-work'
req "$POLICY" 'Execution is unrestricted on the Biella workstation'
req "$POLICY" 'goal, vision, task'
req "$POLICY" 'READ MINIMUM'
req "$POLICY" 'TEST AFFECTED SCOPE'
req "$POLICY" 'COMMIT VERIFIED WORK'
req "$POLICY" 'CONTINUE NEXT UNBLOCKED TASK'

bash -n "$WORK"
bash -n "$INSTALLER"
bash -n "$CLI"
echo 'low-noise autopilot contract: PASS'
