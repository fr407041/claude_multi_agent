#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${AI_COMPANY_PYTHON_BIN:-${PYTHON:-python3}}"
"${PYTHON_BIN}" "${SCRIPT_DIR}/worker_claude_router.py" "${1:?Usage: worker_claude_router_managed_single_file.sh <job.json>}" managed
