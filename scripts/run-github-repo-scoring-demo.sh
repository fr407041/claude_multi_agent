#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-mock}"
REPO="${GITHUB_REPO_SCORING_TARGET:-All-Hands-AI/OpenHands}"
REF="${GITHUB_REPO_SCORING_REF:-main}"

python3 "${ROOT}/scripts/run_github_repo_scoring_demo.py" --mode "${MODE}" --repo "${REPO}" --ref "${REF}"
