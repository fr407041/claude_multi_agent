#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT="$(cd "${SKILL_DIR}/../.." && pwd)"

require_command() {
  local name="${1:?command name required}"
  if ! command -v "${name}" >/dev/null 2>&1; then
    echo "Required command not found: ${name}" >&2
    echo "Install it on Ubuntu 22.04, then rerun this script." >&2
    exit 1
  fi
}

require_command bash
require_command python3
require_command node
require_command npm

cd "${PROJECT_ROOT}"

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
fi

mkdir -p agent-runs results logs

bash scripts/doctor.sh
bash scripts/init-runtime.sh
python3 scripts/verify_install.py --strict --json

if [[ ! -d .claude/skills/research-task-orchestrator ]]; then
  echo "Operation skill missing: .claude/skills/research-task-orchestrator" >&2
  exit 1
fi

bash .claude/skills/research-task-orchestrator/scripts/install_dashboard.sh

cat <<EOF
Install completed.

Start dashboard:
  bash agent_os_mvp/start-dashboard.sh

Open:
  http://127.0.0.1:15174/

Health:
  http://127.0.0.1:18010/health

Run tasks with:
  Use the research-task-orchestrator skill to run: <your task>
EOF
