#!/usr/bin/env bash
set -euo pipefail
exec pwsh -NoProfile -ExecutionPolicy Bypass -File "$(cd "$(dirname "$0")" && pwd)/run-live-validation.ps1"
