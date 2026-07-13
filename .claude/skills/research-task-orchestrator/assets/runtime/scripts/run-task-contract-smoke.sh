#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:18080}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-900}"
EXPECTED_MARKER="${RUNTIME_OVERRIDE_ID:-claude-multi-agent-repo-runtime-v2}"

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

post_json() {
  local payload="$1"
  curl --fail --silent --show-error \
    -H 'Content-Type: application/json' \
    --data-binary @"$payload" \
    "$API_BASE/run-task"
}

get_json() {
  local run_id="$1"
  curl --fail --silent --show-error "$API_BASE/runs/$run_id"
}

wait_run() {
  local run_id="$1"
  local deadline=$((SECONDS + TIMEOUT_SECONDS + 60))
  local status_json="$tmp_dir/status-$run_id.json"
  while (( SECONDS < deadline )); do
    get_json "$run_id" > "$status_json"
    local status
    status="$(python3 - "$status_json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("status", ""))
PY
)"
    case "$status" in
      succeeded|failed|timeout|interrupted)
        cat "$status_json"
        return 0
        ;;
    esac
    sleep 5
  done
  echo "run timed out while polling: $run_id" >&2
  return 2
}

health="$(curl --fail --silent --show-error "$API_BASE/health")"
printf '%s\n' "$health" > "$tmp_dir/health.json"

cat > "$tmp_dir/marker-request.json" <<'JSON'
{
  "task": "Runtime override marker check. Print the mounted repository runtime marker and do not run a real task.",
  "timeout_seconds": 120
}
JSON

marker_initial="$(post_json "$tmp_dir/marker-request.json")"
printf '%s\n' "$marker_initial" > "$tmp_dir/marker-initial.json"
marker_run_id="$(python3 - "$tmp_dir/marker-initial.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("run_id", ""))
PY
)"
marker_final="$(wait_run "$marker_run_id")"
printf '%s\n' "$marker_final" > "$tmp_dir/marker-final.json"

marker_ok="$(python3 - "$tmp_dir/marker-final.json" "$EXPECTED_MARKER" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
expected = sys.argv[2]
text = json.dumps(payload, ensure_ascii=False)
print("1" if f"RUNTIME_OVERRIDE_MARKER:{expected}" in text else "0")
PY
)"
if [[ "$marker_ok" != "1" ]]; then
  echo "STALE_IMAGE_RUNTIME: /run-task is not executing the mounted repo runtime override." >&2
  echo "Mount ./agent-test-runtime/run_task.sh to /app/runtime/run_task.sh or rebuild the image." >&2
  echo "marker_run_id=$marker_run_id" >&2
  exit 10
fi

cat > "$tmp_dir/contract-request.json" <<'JSON'
{
  "task": "Return exact JSON only: {\"ok\":true,\"repo\":\"fr407041/claude_multi_agent\",\"contract\":\"exact_json\"}",
  "timeout_seconds": 900
}
JSON

contract_initial="$(post_json "$tmp_dir/contract-request.json")"
printf '%s\n' "$contract_initial" > "$tmp_dir/contract-initial.json"
contract_run_id="$(python3 - "$tmp_dir/contract-initial.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("run_id", ""))
PY
)"
contract_final="$(wait_run "$contract_run_id")"
printf '%s\n' "$contract_final" > "$tmp_dir/contract-final.json"

python3 - "$tmp_dir/contract-final.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
status = str(payload.get("status", ""))
text = json.dumps(payload, ensure_ascii=False) + "\n" + str(payload.get("result_text") or "")
has_contract_failure = "TASK_OUTPUT_CONTRACT_FAILED" in text
has_contract_pass = '"task_contract_status": "pass"' in text or '"task_contract_status":"pass"' in text
has_no_think = "Unknown command: /no_think" in text

if has_no_think:
    raise SystemExit("FALSE_SUCCESS_BLOCKED: output still contains Unknown command: /no_think")
if status == "succeeded" and not has_contract_pass:
    raise SystemExit("FALSE_SUCCESS_BLOCKED: run succeeded without task_contract_status=pass evidence")
if status != "succeeded" and not has_contract_failure:
    raise SystemExit("UNCLASSIFIED_CONTRACT_FAILURE: failed run did not expose TASK_OUTPUT_CONTRACT_FAILED")
print(json.dumps({
    "pass": True,
    "run_id": payload.get("run_id"),
    "status": status,
    "contract_enforced": True,
}, ensure_ascii=False, indent=2))
PY
