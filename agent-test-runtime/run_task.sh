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

if [[ "${REQUIRE_FAB_EFFECTIVE_POLICY:-false}" == "true" ]]; then
  FAB_POLICY_DIR="${FAB_AGENT_RUNTIME_DIR:-${AI_COMPANY_EFFECTIVE_AGENT_DIR:-}}"
  if [[ -z "$FAB_POLICY_DIR" ]]; then
    cat > "${RUN_DIR}/effective-policy-preflight.json" <<'JSON'
{
  "passed": false,
  "errors": [
    {
      "code": "EFFECTIVE_AGENT_POLICY_DIR_MISSING",
      "detail": "Set FAB_AGENT_RUNTIME_DIR or AI_COMPANY_EFFECTIVE_AGENT_DIR when REQUIRE_FAB_EFFECTIVE_POLICY=true."
    }
  ]
}
JSON
    echo "EFFECTIVE_AGENT_POLICY_INVALID: missing FAB_AGENT_RUNTIME_DIR" >&2
    exit 2
  fi
  python3 scripts/verify_effective_agent_policy.py \
    "$FAB_POLICY_DIR" \
    --json \
    --out "${RUN_DIR}/effective-policy-preflight.json"
fi

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

  detect_site_lite_gate() {
    python3 - <<'PY'
import os
text = os.environ.get("TASK_TEXT", "")
print("site-lite" if "Shopping site lite gate" in text else "")
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

  run_site_lite_verifier() {
    local attempt="$1"
    python3 "${MULTI_AGENT_REPO}/scripts/verify_generated_output_package.py" \
      "${RUN_DIR}/worktree" \
      --profile shopping-site \
      --json | tee "${RUN_DIR}/site-lite-verifier-attempt-${attempt}.json"
  }

  materialize_artifact_package() {
    local attempt="$1"
    python3 "${MULTI_AGENT_REPO}/scripts/materialize_artifact_package.py" \
      --model-output "${RUN_DIR}/claude-attempt-${attempt}.stdout.log" \
      --root "${RUN_DIR}/worktree" \
      --report "${RUN_DIR}/artifact-materializer-attempt-${attempt}.json"
  }

  run_provider_artifact_attempt() {
    export RUN_DIR MODEL_NAME OLLAMA_BASE_URL TASK_TEXT
    python3 - <<'PY'
import json
import os
import urllib.request
from pathlib import Path

run_dir = Path(os.environ["RUN_DIR"])
model = os.environ.get("MODEL_NAME", "qwen3-coder:30b")
base = os.environ.get("OLLAMA_BASE_URL", "http://192.168.100.112:11435").rstrip("/")
prompt = f"""Generate a dependency-free static shopping website. Return only JSON, no markdown, no explanation.
Schema:
{{"schema_version":"artifact-package.v1","files":[{{"path":"shopping-site/index.html","content":"..."}},{{"path":"shopping-site/styles.css","content":"..."}},{{"path":"shopping-site/app.js","content":"..."}},{{"path":"shopping-site/README.md","content":"..."}}],"final_answer":"<repeat required nonce>"}}
Requirements: at least four products, product grid, add-to-cart buttons, cart count update, cart total update, checkout stub that clearly says no real payment is processed, README explains how to review outputs.
User task:
{os.environ.get("TASK_TEXT", "")}
"""
payload = {
    "model": model,
    "messages": [{"role": "user", "content": prompt}],
    "stream": False,
    "temperature": 0,
}
request_path = run_dir / "provider-artifact-request.json"
raw_path = run_dir / "provider-artifact-raw-response.json"
content_path = run_dir / "claude-attempt-provider.stdout.log"
request_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
req = urllib.request.Request(
    f"{base}/v1/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=360) as resp:
    raw = resp.read().decode("utf-8", "replace")
raw_path.write_text(raw, encoding="utf-8")
data = json.loads(raw)
content = data["choices"][0]["message"]["content"]
content_path.write_text(content, encoding="utf-8")
print(content)
PY
  }

  materialize_provider_artifact_package() {
    python3 "${MULTI_AGENT_REPO}/scripts/materialize_artifact_package.py" \
      --model-output "${RUN_DIR}/claude-attempt-provider.stdout.log" \
      --root "${RUN_DIR}/worktree" \
      --report "${RUN_DIR}/artifact-materializer-attempt-provider.json"
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
  SITE_GATE="$(detect_site_lite_gate)"
  ARTIFACT_INSTRUCTION="Write all task artifacts under ${RUN_DIR}/ptt-stock-live/."
  if [[ -n "$SITE_GATE" ]]; then
    mkdir -p "${RUN_DIR}/worktree/shopping-site"
    ARTIFACT_INSTRUCTION="Write all website artifacts under ${RUN_DIR}/worktree/shopping-site/."
  fi

  BASE_PROMPT="You are running inside the dedicated test container. Complete the user task using live tools as needed.
Run directory: ${RUN_DIR}
Repository directory: ${MULTI_AGENT_REPO}
Do not use mock data. Do not rely on any crawler prewritten by the caller. If code is needed, create it yourself inside the run directory.
${ARTIFACT_INSTRUCTION}
${TASK_TEXT}"

  if [[ -n "$SITE_GATE" ]]; then
    BASE_PROMPT="You are running inside the dedicated test container. Generate the requested website output package.
Run directory: ${RUN_DIR}
Repository directory: ${MULTI_AGENT_REPO}
Do not claim files were created unless they are present in the artifact package below.
Return only this bounded artifact package JSON. Do not call tools. Do not wrap it in markdown.
ARTIFACT_PACKAGE_JSON_BEGIN
{
  \"schema_version\": \"artifact-package.v1\",
  \"files\": [
    {\"path\": \"shopping-site/index.html\", \"content\": \"...complete HTML...\"},
    {\"path\": \"shopping-site/styles.css\", \"content\": \"...complete CSS...\"},
    {\"path\": \"shopping-site/app.js\", \"content\": \"...complete JavaScript...\"},
    {\"path\": \"shopping-site/README.md\", \"content\": \"...review instructions...\"}
  ],
  \"final_answer\": \"<repeat the required nonce from the user task>\"
}
ARTIFACT_PACKAGE_JSON_END
Content requirements: at least four products, product grid, add-to-cart buttons, cart count update, cart total update, checkout stub that clearly says no real payment is processed, and README review instructions.
User task:
${TASK_TEXT}"
  fi

  snapshot_artifacts "${GATE:-none}" "1" "before"
  run_claude_attempt "1" "$BASE_PROMPT"
  snapshot_artifacts "${GATE:-none}" "1" "after"
  if [[ -z "$GATE" ]]; then
    cp "${RUN_DIR}/claude-attempt-1.stdout.log" "${RUN_DIR}/claude-code-response.txt"
    if [[ -n "$SITE_GATE" ]]; then
      materialize_artifact_package "1" || true
      if run_site_lite_verifier "1"; then
        python3 scripts/task_contract.py \
          --task-file "${TASK_FILE}" \
          --response-file "${RUN_DIR}/claude-code-response.txt" \
          --out "${RUN_DIR}/task-contract.json"
        exit 0
      fi
      SITE_REPAIR_FEEDBACK="$(python3 - <<'PY'
import json
import os
from pathlib import Path
path = Path(os.environ["RUN_DIR"]) / "site-lite-verifier-attempt-1.json"
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    data = {}
print(json.dumps({
    "failure_category": data.get("failure_category", "ARTIFACT_CONTRACT_FAILED"),
    "failed_checks": data.get("failed_checks", [])[:12],
    "expected_outputs": data.get("expected_outputs", []),
}, ensure_ascii=False))
PY
)"
      SITE_REPAIR_PROMPT="${BASE_PROMPT}

The deterministic shopping-site verifier failed.
Verifier summary:
${SITE_REPAIR_FEEDBACK}

Repair only the generated output package. If live tool execution is unavailable, return an artifact package JSON instead.
Your response must contain only this bounded package format:
ARTIFACT_PACKAGE_JSON_BEGIN
{
  \"schema_version\": \"artifact-package.v1\",
  \"files\": [
    {\"path\": \"shopping-site/index.html\", \"content\": \"...complete HTML...\"},
    {\"path\": \"shopping-site/styles.css\", \"content\": \"...complete CSS...\"},
    {\"path\": \"shopping-site/app.js\", \"content\": \"...complete JavaScript...\"},
    {\"path\": \"shopping-site/README.md\", \"content\": \"...review instructions...\"}
  ],
  \"final_answer\": \"<repeat the required nonce from the original task>\"
}
ARTIFACT_PACKAGE_JSON_END
Rules: paths must be relative exactly as shown; content must be complete; include at least four products, add-to-cart behavior, cart count update, cart total update, and a checkout stub that says no real payment is processed."
      run_claude_attempt "2" "$SITE_REPAIR_PROMPT"
      cp "${RUN_DIR}/claude-attempt-2.stdout.log" "${RUN_DIR}/claude-code-response.txt"
      materialize_artifact_package "2" || true
      if run_site_lite_verifier "2"; then
        python3 scripts/task_contract.py \
          --task-file "${TASK_FILE}" \
          --response-file "${RUN_DIR}/claude-code-response.txt" \
          --out "${RUN_DIR}/task-contract.json"
        exit 0
      fi
      echo "SITE_LITE_CLAUDE_PATH_FAILED_TRYING_PROVIDER_ARTIFACT_FALLBACK"
      if run_provider_artifact_attempt; then
        cp "${RUN_DIR}/claude-attempt-provider.stdout.log" "${RUN_DIR}/claude-code-response.txt"
        materialize_provider_artifact_package || true
        if run_site_lite_verifier "provider"; then
          python3 scripts/task_contract.py \
            --task-file "${TASK_FILE}" \
            --response-file "${RUN_DIR}/claude-code-response.txt" \
            --out "${RUN_DIR}/task-contract.json"
          printf "%s\n" "direct_provider_artifact_package" > "${RUN_DIR}/site-lite-fallback-transport.txt"
          exit 0
        fi
      fi
      export RUN_DIR
      python3 - <<'PY'
import json
import os
from pathlib import Path
run_dir = Path(os.environ["RUN_DIR"])
verifier_path = run_dir / "site-lite-verifier-attempt-2.json"
try:
    verifier = json.loads(verifier_path.read_text(encoding="utf-8"))
except Exception as exc:
    verifier = {"failed_checks": [f"verifier unreadable: {exc}"], "failure_category": "SITE_LITE_VERIFIER_UNREADABLE"}
payload = {
    "status": "failed",
    "failure_category": verifier.get("failure_category") or "SITE_LITE_VERIFIER_FAILED",
    "failed_checks": verifier.get("failed_checks", []),
    "verifier_result_path": str(verifier_path),
    "repair_attempts": 1,
}
print("SITE_LITE_CONTRACT_FAILURE:")
print(json.dumps(payload, ensure_ascii=False, indent=2))
PY
      exit 1
    fi
    python3 scripts/task_contract.py \
      --task-file "${TASK_FILE}" \
      --response-file "${RUN_DIR}/claude-code-response.txt" \
      --out "${RUN_DIR}/task-contract.json"
    exit 0
  fi
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
if verifier.get("failure_category") and failure_category == "ARTIFACT_CONTRACT_FAILED":
    failure_category = str(verifier.get("failure_category"))
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

PROMPT="Use the research-task-orchestrator skill context. The repository verification and smoke harness already ran above. Do not call tools or emit tool JSON. Reply in plain text only. ${TASK_TEXT}"

export PROMPT MODEL_NAME ROUTER_PORT ROUTER_MAX_TOKENS RUN_DIR
python3 - <<'PY'
import json
import os
from pathlib import Path
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

response_text = "\n".join(
    block.get("text", "")
    for block in data.get("content", [])
    if block.get("type") == "text"
)
run_dir = Path(os.environ["RUN_DIR"])
(run_dir / "router-direct-response.raw.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
(run_dir / "router-direct-response.txt").write_text(response_text, encoding="utf-8")
print("router_direct_response:")
print(response_text)
print("router_direct_usage:")
print(json.dumps(data.get("usage", {}), ensure_ascii=False))
PY
python3 scripts/task_contract.py \
  --task-file "${TASK_FILE}" \
  --response-file "${RUN_DIR}/router-direct-response.txt" \
  --out "${RUN_DIR}/task-contract.json"
