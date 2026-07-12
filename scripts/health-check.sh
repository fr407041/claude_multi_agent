#!/usr/bin/env bash
set -euo pipefail

curl --fail --silent --show-error http://127.0.0.1:3456/health
tags="$(curl --fail --silent --show-error --max-time 15 http://192.168.100.112:11435/api/tags)"
python3 -c 'import json,sys; p=json.loads(sys.argv[1]); names=[m.get("name") for m in p.get("models",[])]; raise SystemExit(0 if "qwen3-coder:30b" in names else 1)' "$tags"
printf '\nCCR healthy; 112 reachable; qwen3-coder:30b visible\n'
