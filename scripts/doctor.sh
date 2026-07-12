#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

failures=0

check_path() {
  local path="$1"
  local label="$2"
  if [[ -e "${path}" ]]; then
    echo "ok: ${label} (${path})"
  else
    echo "missing: ${label} (${path})" >&2
    failures=$((failures + 1))
  fi
}

echo "multi_agent_claude_code doctor"
echo "root: ${ROOT}"
echo

check_path "README.md" "README"
check_path ".env.example" "common env example"
check_path ".claude/skills/research-task-orchestrator/SKILL.md" "runtime operation skill"
check_path "skills/install-multi-agent-runtime/SKILL.md" "install skill"
check_path "agent_os_mvp" "dashboard package"
check_path "scripts/verify_install.py" "install verifier"
check_path "scripts/run_ai_company_task_harness.py" "mock/live harness"

echo
if command -v python3 >/dev/null 2>&1; then
  echo "ok: python3 ($(command -v python3))"
elif command -v python >/dev/null 2>&1; then
  echo "ok: python ($(command -v python))"
else
  echo "missing: python3/python" >&2
  failures=$((failures + 1))
fi

if command -v docker >/dev/null 2>&1; then
  echo "ok: docker ($(command -v docker))"
else
  echo "info: docker not found; mock verification can still run without Docker"
fi

if command -v claude >/dev/null 2>&1; then
  echo "ok: claude ($(command -v claude)); project will use the user's existing Claude configuration"
else
  echo "info: claude not found; live agent runs require the user's own Claude setup"
fi

if [[ ${failures} -gt 0 ]]; then
  echo
  echo "doctor: FAILED (${failures} issue(s))" >&2
  exit 1
fi

echo
echo "doctor: PASS"
