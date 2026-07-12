#!/usr/bin/env bash
set -euo pipefail

TASK_FILE="$1"
RUN_DIR="$2"
RUNTIME_OVERRIDE_ID="${RUNTIME_OVERRIDE_ID:-claude-multi-agent-repo-runtime-v2}"

cd "${MULTI_AGENT_REPO}"
mkdir -p "${RUN_DIR}"
printf "%s\n" "$RUNTIME_OVERRIDE_ID" > "${RUN_DIR}/runtime_override_id.txt"
echo "runtime_override_id=${RUNTIME_OVERRIDE_ID}"

python3 scripts/verify_install.py
if [[ "${RUN_REPO_SMOKE_ON_TASK:-true}" == "true" ]]; then
  python3 scripts/run_ai_company_task_harness.py docs/ai_specs/ai-company-release-readiness-strict-demo.json --mode mock
fi

TASK_TEXT="$(cat "${TASK_FILE}")"
export TASK_TEXT

if [[ "$TASK_TEXT" == *"Runtime override marker check"* ]]; then
  echo "RUNTIME_OVERRIDE_MARKER:${RUNTIME_OVERRIDE_ID}"
  exit 0
fi

if [[ "${TASK_EXECUTOR:-router-direct}" == "claude-code" ]]; then
  mkdir -p "${RUN_DIR}/ptt-stock-live"
  chmod -R a+rwx "${RUN_DIR}"

  detect_micro_gate() {
    python3 - <<'PY'
import os
import re
text = os.environ.get("TASK_TEXT", "")
match = re.search(r"Micro gate\s+([A-F])\b", text, re.IGNORECASE)
print(match.group(1).upper() if match else "")
PY
  }

  run_claude_attempt() {
    local attempt="$1"
    local prompt_text="$2"
    export PROMPT="$prompt_text" RUN_DIR MULTI_AGENT_REPO
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
    ' | tee "${RUN_DIR}/claude-attempt-${attempt}.stdout.log"
  }

  run_gate_verifier() {
    local gate="$1"
    local attempt="$2"
    python3 "${MULTI_AGENT_REPO}/scripts/verify_agent_micro_gate.py" \
      --gate "$gate" \
      --run-dir "$RUN_DIR" \
      --json | tee "${RUN_DIR}/micro-gate-${gate}-verifier-attempt-${attempt}.json"
  }

  expected_micro_gate_artifact() {
    local gate="$1"
    case "$gate" in
      A) printf "%s\n" "ptt-stock-live/proof.txt" ;;
      B) printf "%s\n" "ptt-stock-live/index.html" ;;
      C) printf "%s\n" "ptt-stock-live/urls.json" ;;
      D) printf "%s\n" "ptt-stock-live/article.json" ;;
      E|F) printf "%s\n" "ptt-stock-live/final.json" ;;
      *) printf "%s\n" "" ;;
    esac
  }

  expected_artifact_missing_or_empty() {
    local gate="$1"
    local rel
    rel="$(expected_micro_gate_artifact "$gate")"
    if [[ -z "$rel" ]]; then
      return 1
    fi
    [[ ! -s "${RUN_DIR}/${rel}" && ! -s "${RUN_DIR}/worktree/${rel}" ]]
  }

  build_no_artifact_repair_instructions() {
    local gate="$1"
    local rel
    rel="$(expected_micro_gate_artifact "$gate")"
    if [[ -z "$rel" ]]; then
      return 0
    fi
    cat <<EOF
NO_ARTIFACT_CREATED: the expected artifact is missing or empty.
Required path: ${RUN_DIR}/${rel}
Do not explain the failure. Use tools to create the file at the required path, then verify it exists and is non-empty before final output.
Only repair Micro gate ${gate}.
EOF
    case "$gate" in
      A)
        cat <<'EOF'
Required file content:
TOOL_EXECUTED_OK
EOF
        ;;
      B)
        cat <<'EOF'
Required artifact contract:
- Fetch https://www.ptt.cc/bbs/Stock/index.html yourself.
- Save the raw HTML to ptt-stock-live/index.html.
- The file must contain PTT Stock board markers and be larger than 500 bytes.
EOF
        ;;
      C)
        cat <<'EOF'
Required artifact contract:
- Parse exactly 5 unique latest PTT Stock article URLs.
- Save JSON to ptt-stock-live/urls.json as {"urls":["https://www.ptt.cc/bbs/Stock/M.<digits>.A.<id>.html", ...]}.
- Do not include board index URLs.
EOF
        ;;
      D)
        cat <<'EOF'
Required exact JSON schema:
{"title":"...","url":"https://www.ptt.cc/bbs/Stock/M.<digits>.A.<id>.html","author":"...","date":"...","body":"article body text at least 100 chars"}
If seed URLs are listed in the original task, use one of those URLs.
If raw HTML already exists in the artifact snapshot below, parse that existing raw HTML first.
If no raw HTML exists, create your own short parser in the run directory, run it, and make it write ptt-stock-live/article.json.
EOF
        ;;
      E|F)
        cat <<'EOF'
Required artifact contract:
- Save final JSON to ptt-stock-live/final.json.
- Include articles[], stocks[], evidence arrays, article URLs, and limitations.
- Do not output only prose.
EOF
        ;;
    esac
  }

  snapshot_artifacts() {
    local gate="$1"
    local attempt="$2"
    local phase="$3"
    export RUN_DIR gate attempt phase
    python3 - <<'PY'
import json
import os
from pathlib import Path

run_dir = Path(os.environ["RUN_DIR"])
artifact_dir = run_dir / "ptt-stock-live"
files = []
if artifact_dir.exists():
    for path in sorted(artifact_dir.rglob("*")):
        if path.is_file():
            files.append({
                "path": str(path.relative_to(run_dir)),
                "bytes": path.stat().st_size,
            })
payload = {
    "gate": os.environ["gate"],
    "attempt": os.environ["attempt"],
    "phase": os.environ["phase"],
    "artifact_dir": str(artifact_dir),
    "files": files,
}
out = run_dir / f"micro-gate-{os.environ['gate']}-artifact-snapshot-attempt-{os.environ['attempt']}-{os.environ['phase']}.json"
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY
  }

  GATE="$(detect_micro_gate)"
  BASE_PROMPT="You are running inside the dedicated test container. Complete the user task using live tools as needed.
Run directory: ${RUN_DIR}
Repository directory: ${MULTI_AGENT_REPO}
Do not use mock data. Do not rely on any crawler prewritten by the caller. If code is needed, create it yourself inside the run directory.
Write all task artifacts under ${RUN_DIR}/ptt-stock-live/.
${TASK_TEXT}"

  snapshot_artifacts "${GATE:-none}" "1" "before"
  run_claude_attempt "1" "$BASE_PROMPT"
  snapshot_artifacts "${GATE:-none}" "1" "after"
    if [[ -n "$GATE" ]]; then
    if run_gate_verifier "$GATE" "1"; then
      exit 0
    fi
    REPAIR_FEEDBACK="$(cat "${RUN_DIR}/micro-gate-${GATE}-verifier-attempt-1.json")"
    ARTIFACT_SNAPSHOT="$(cat "${RUN_DIR}/micro-gate-${GATE}-artifact-snapshot-attempt-1-after.json" 2>/dev/null || true)"
    EXTRA_REPAIR_INSTRUCTIONS=""
    if expected_artifact_missing_or_empty "$GATE"; then
      EXTRA_REPAIR_INSTRUCTIONS="$(build_no_artifact_repair_instructions "$GATE")"
    fi
    REPAIR_PROMPT="${BASE_PROMPT}

The deterministic verifier failed. Repair only Micro gate ${GATE}; do not rerun or discuss earlier gates.
Verifier JSON:
${REPAIR_FEEDBACK}
Artifact snapshot after the failed attempt:
${ARTIFACT_SNAPSHOT}
${EXTRA_REPAIR_INSTRUCTIONS}

You have one repair attempt. Create or correct the required artifact files under ${RUN_DIR}/ptt-stock-live/ and print only the gate-required final output."
    snapshot_artifacts "$GATE" "2" "before"
    run_claude_attempt "2" "$REPAIR_PROMPT"
    snapshot_artifacts "$GATE" "2" "after"
    if run_gate_verifier "$GATE" "2"; then
      exit 0
    fi
    FINAL_VERIFIER_PATH="${RUN_DIR}/micro-gate-${GATE}-verifier-attempt-2.json"
    export GATE FINAL_VERIFIER_PATH
    python3 - <<'PY'
import json
import os
from pathlib import Path
gate = os.environ["GATE"]
path = Path(os.environ["FINAL_VERIFIER_PATH"])
try:
    verifier = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:
    verifier = {"pass": False, "fail_reasons": [f"verifier result unreadable: {exc}"]}
failure_category = "ARTIFACT_CONTRACT_FAILED"
expected = {
    "A": "ptt-stock-live/proof.txt",
    "B": "ptt-stock-live/index.html",
    "C": "ptt-stock-live/urls.json",
    "D": "ptt-stock-live/article.json",
    "E": "ptt-stock-live/final.json",
    "F": "ptt-stock-live/final.json",
}.get(gate, "")
expected_paths = []
if expected:
    expected_paths = [path.parent / expected, path.parent / "worktree" / expected]
    if not any(item.exists() and item.stat().st_size > 0 for item in expected_paths):
        failure_category = "ARTIFACT_NOT_CREATED_BY_MODEL"
payload = {
    "status": "failed",
    "failure_category": failure_category,
    "failure_parent_category": "ARTIFACT_CONTRACT_FAILED",
    "gate": gate,
    "failed_checks": verifier.get("fail_reasons", []),
    "expected_artifact": expected,
    "expected_artifact_paths": [str(item) for item in expected_paths],
    "verifier_result_path": str(path),
    "artifact_snapshot_paths": [
        str(item)
        for item in sorted(path.parent.glob(f"micro-gate-{gate}-artifact-snapshot-attempt-*.json"))
    ],
    "repair_attempts": 1,
}
print("MICRO_GATE_CONTRACT_FAILURE:")
print(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    exit 1
  fi
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
