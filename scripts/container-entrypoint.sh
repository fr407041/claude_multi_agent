#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/artifacts /workspace/logs /workspace/results /root/.claude-code-router/logs
ccr start >/dev/null 2>&1

for _ in $(seq 1 30); do
  if curl --fail --silent http://127.0.0.1:3456/health >/dev/null; then
    exec tail -f /dev/null
  fi
  sleep 1
done

echo "CCR failed to become healthy" >&2
ccr status >&2 || true
exit 1
