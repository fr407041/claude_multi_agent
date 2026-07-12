#!/usr/bin/env bash
set -euo pipefail

TASK_FILE="$1"
RUN_DIR="$2"

cd "${MULTI_AGENT_REPO}"

python3 scripts/verify_install.py
if [[ "${RUN_REPO_SMOKE_ON_TASK:-true}" == "true" ]]; then
  python3 scripts/run_ai_company_task_harness.py docs/ai_specs/ai-company-release-readiness-strict-demo.json --mode mock
fi

TASK_TEXT="$(cat "${TASK_FILE}")"

if [[ "${TASK_EXECUTOR:-router-direct}" == "claude-code" ]]; then
  mkdir -p "${RUN_DIR}/ptt-stock-live"
  chmod -R a+rwx "${RUN_DIR}"
  PROMPT="You are running inside the dedicated test container. Complete the user task using live tools as needed.
Run directory: ${RUN_DIR}
Repository directory: ${MULTI_AGENT_REPO}
Do not use mock data. Do not rely on any crawler prewritten by the caller. If code is needed, create it yourself inside the run directory.
Write all task artifacts under ${RUN_DIR}/ptt-stock-live/.
${TASK_TEXT}"
  export PROMPT RUN_DIR MULTI_AGENT_REPO
  runuser --preserve-environment -u claudeagent -- env HOME=/home/claudeagent bash -lc '
    set -euo pipefail
    mkdir -p "$RUN_DIR/ptt-stock-live"
    cd "$RUN_DIR"
    printf "%s" "$PROMPT" | ccr default-claude-code cli -- \
      --print \
      --bare \
      --effort medium \
      --no-session-persistence \
      --dangerously-skip-permissions \
      --add-dir "$RUN_DIR" \
      --add-dir "$MULTI_AGENT_REPO"
  '
  exit 0
fi

if [[ "${TASK_EXECUTOR:-router-direct}" != "router-direct" ]]; then
  echo "Unsupported TASK_EXECUTOR=${TASK_EXECUTOR:-}. Supported: router-direct, claude-code." >&2
  exit 2
fi

PROMPT="/no_think
Use the research-task-orchestrator skill context. The repository verification and smoke harness already ran above. Do not call tools or emit tool JSON. Reply in plain text only. ${TASK_TEXT}"

export PROMPT MODEL_NAME ROUTER_PORT ROUTER_MAX_TOKENS
python3 - <<'PY'
import json
import os
import urllib.error
import urllib.request

payload = {
    "model": os.environ["MODEL_NAME"],
    "max_tokens": int(os.environ.get("ROUTER_MAX_TOKENS", "256")),
    "messages": [{"role": "user", "content": os.environ["PROMPT"]}],
}
req = urllib.request.Request(
    f"http://127.0.0.1:{os.environ.get('ROUTER_PORT', '3456')}/v1/messages",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "content-type": "application/json",
        "x-api-key": os.environ.get("ANTHROPIC_AUTH_TOKEN", "local-router-token"),
        "anthropic-version": "2023-06-01",
    },
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=600) as response:
        data = json.loads(response.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    detail = exc.read().decode("utf-8", errors="replace")[:2000]
    raise RuntimeError(f"CCR /v1/messages HTTP {exc.code}: {detail}") from exc

print("router_direct_response:")
for block in data.get("content", []):
    if block.get("type") == "text":
        print(block.get("text", ""))
print("router_direct_usage:")
print(json.dumps(data.get("usage", {}), ensure_ascii=False))
PY
