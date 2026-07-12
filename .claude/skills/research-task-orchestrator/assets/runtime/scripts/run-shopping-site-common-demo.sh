#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-live}"
SPEC="${ROOT}/docs/ai_specs/shopping-site-common-demo.json"
OUT_ROOT="${AI_COMPANY_RESULTS_ROOT:-${ROOT}/results/ai_company_task_harness}"

if [[ "$MODE" != "live" && "$MODE" != "mock" ]]; then
  echo "Usage: $0 [live|mock]" >&2
  exit 2
fi

mkdir -p "$OUT_ROOT"

if [[ "$MODE" == "live" ]]; then
  export AI_COMPANY_MEETING_MODE="${AI_COMPANY_MEETING_MODE:-live}"
fi

python3 "${ROOT}/scripts/run_ai_company_task_harness.py" "$SPEC" --mode "$MODE" --out-root "$OUT_ROOT"
