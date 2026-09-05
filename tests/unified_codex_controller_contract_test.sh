#!/usr/bin/env bash
set -Eeuo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
wrapper="$root/ops/local-ai/biella-codex.sh"
installer="$root/ops/local-ai/install-biella-ai.sh"
runner="$root/ops/local-ai/biella_production_runner.py"
cli="$root/ops/workstation/biella"
policy="$root/ops/workstation/AGENTS.md"

for f in "$wrapper" "$installer" "$runner" "$cli" "$policy"; do
  [[ -f "$f" ]] || { echo "missing $f"; exit 1; }
done

grep -Fq 'CODEX_HOME="/root/.codex"' "$wrapper"
grep -Fq 'source "$RUNTIME_ENV"' "$wrapper"
grep -Fq -- '--dangerously-bypass-approvals-and-sandbox' "$wrapper"
grep -Fq 'shell_environment_policy.inherit' "$wrapper"
grep -Fq -- '--search' "$wrapper"
grep -Fq 'cd /root' "$wrapper"
grep -Fq 'BIELLA_PRODUCTION_RUNNER' "$wrapper"
grep -Fq '"${1:-}" == "production"' "$wrapper"
! grep -Fq '"${1:-}" == "feed"' "$wrapper"
if grep -Fq 'biella_codex_feeder.py' "$installer"; then echo 'legacy feeder installer reference remains' >&2; exit 1; fi
grep -Fq 'biella_production_runner.py' "$installer"
grep -Fq 'biella_task_ids.py' "$installer"
grep -Fq 'biella_task_ledger.py' "$installer"
grep -Fq '## Progressive Auto Feeder' "$root/ops/local-ai/README.md"
! grep -Fq 'biella-codex production stop' "$root/ops/local-ai/README.md"
grep -Fq '## Progressive Auto Feeder' "$root/ops/workstation/AGENTS.md"
! grep -Fq 'OWNER_DECISION' "$runner"
! grep -Fq 'EXTERNAL_DEPENDENCY' "$runner"
! grep -Fq -- '--oss' "$wrapper"
! grep -Fq 'qwen3-coder-next:biella' "$wrapper"
! grep -Fq 'gpt-5.6-luna' "$wrapper"
! grep -Fq 'gpt-6-astra' "$wrapper"
grep -Fq '/usr/local/bin/biella-codex' "$installer"
for obsolete in LOCAL_AGENT_LINK WORK_LINK MODEL_LINK LUNA_LINK ASTRA_LINK START_LINK; do
  ! grep -Fq "$obsolete" "$installer"
done
for obsolete_script in biella-local-agent.sh biella-work.sh biella-model.sh biella-luna.sh biella-astra.sh; do
  ! grep -Fq '"$SOURCE_DIR/'"$obsolete_script"'"' "$installer"
done
for obsolete_case in 'agent)' 'work)' 'model)' 'luna)' 'astra)' 'codex)'; do
  ! grep -Fq "$obsolete_case" "$cli"
done

grep -Fq 'single active Codex home' "$policy"
grep -Fq 'progressive context' "$policy"
grep -Fq 'checkpoint before context pressure' "$policy"
grep -Fq 'Codex chooses local Qwen' "$policy"
grep -Fq 'gpt-6-astra' "$policy"
grep -Fq 'ultra' "$policy"
grep -Fq 'Creation tasks never use low reasoning' "$policy"
grep -Fq 'Mahdi controls Codex account usage' "$policy"
grep -Fq 'Durable execution state is' "$policy"
grep -Fq '03_BIELLA_CURRENT_STATE.md' "$policy"
grep -Fq '04_BIELLA_ACTIVE_TASK.md' "$policy"
grep -Fq 'projects/biella-games/docs/PRODUCTION.md' "$policy"
! grep -Fq '/root/biella/work/games-production.json' "$policy"
grep -Fq 'runtime telemetry' "$policy"
grep -Fq 'codex-production' "$policy"
grep -Fq 'do not create separate queue, state, batch, or progress-ledger authorities' "$policy"
grep -Fq '20-50 task set' "$policy"

bash -n "$wrapper"
bash -n "$installer"
bash -n "$cli"
echo 'unified codex controller contract: PASS'