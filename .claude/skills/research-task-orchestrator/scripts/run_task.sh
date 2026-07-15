#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="${AI_COMPANY_PROJECT_ROOT:-$(pwd)}"
RUNTIME="$PROJECT_ROOT/.ai-company/runtime/current"

if [[ ! -x "$RUNTIME/scripts/run_ai_company_task_harness.py" && ! -f "$RUNTIME/scripts/run_ai_company_task_harness.py" ]]; then
  AI_COMPANY_PROJECT_ROOT="$PROJECT_ROOT" bash "$SKILL_DIR/scripts/install_runtime.sh"
fi

if [[ $# -lt 1 ]]; then
  SPEC="$RUNTIME/docs/ai_specs/ai-company-release-readiness-strict-demo.json"
  shift 0
else
  SPEC="$1"
  shift
  if [[ "$SPEC" != /* ]]; then
    if [[ -f "$PROJECT_ROOT/$SPEC" ]]; then
      SPEC="$PROJECT_ROOT/$SPEC"
    elif [[ -f "$RUNTIME/$SPEC" ]]; then
      SPEC="$RUNTIME/$SPEC"
    fi
  fi
fi

export AI_COMPANY_PACKAGE_PROFILE=runtime
export AI_COMPANY_WORKSPACE_ROOT="$PROJECT_ROOT"
export AI_COMPANY_SKILL_ROOT="$SKILL_DIR"

if [[ "${REQUIRE_FAB_EFFECTIVE_POLICY:-false}" == "true" ]]; then
  FAB_POLICY_DIR="${FAB_AGENT_RUNTIME_DIR:-${AI_COMPANY_EFFECTIVE_AGENT_DIR:-}}"
  if [[ -z "$FAB_POLICY_DIR" ]]; then
    echo "EFFECTIVE_AGENT_POLICY_INVALID: set FAB_AGENT_RUNTIME_DIR or AI_COMPANY_EFFECTIVE_AGENT_DIR when REQUIRE_FAB_EFFECTIVE_POLICY=true." >&2
    exit 2
  fi
  python3 "$RUNTIME/scripts/verify_effective_agent_policy.py" "$FAB_POLICY_DIR" --json
fi

exec python3 "$RUNTIME/scripts/run_ai_company_task_harness.py" \
  "$SPEC" --out-root "$PROJECT_ROOT/results/ai_company_task_harness" "$@"
