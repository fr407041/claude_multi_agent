#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if [[ ! -f ".env" ]]; then
  cp ".env.example" ".env"
  echo "created: .env"
else
  echo "exists: .env"
fi

set -a
# shellcheck disable=SC1091
source ".env"
set +a

mkdir -p "${RUNS_DIR:-./agent-runs}" "${RESULTS_DIR:-./results}" "${LOGS_DIR:-./logs}"

echo "initialized runtime directories:"
echo "  RUNS_DIR=${RUNS_DIR:-./agent-runs}"
echo "  RESULTS_DIR=${RESULTS_DIR:-./results}"
echo "  LOGS_DIR=${LOGS_DIR:-./logs}"
echo
echo "This script does not modify Claude, Router, model, provider, or output-token settings."
