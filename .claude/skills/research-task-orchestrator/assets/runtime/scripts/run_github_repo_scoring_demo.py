#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SPEC_TEMPLATE = ROOT / "docs" / "ai_specs" / "github-repo-scoring-demo.json"
DEFAULT_OUT_ROOT = ROOT / "results" / "ai_company_task_harness"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def list_supplied_inputs(case_dir: Path) -> list[str]:
    required = [
        "repo_metadata.json",
        "repository_inventory.json",
        "file_context_manifest.json",
        "bounded_file_context.md",
    ]
    shards = sorted(path.relative_to(case_dir).as_posix() for path in (case_dir / "inventory_shards").glob("*.json"))
    return required + shards


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the GitHub repository scoring common demo.")
    parser.add_argument("--mode", choices=["mock", "live"], default="mock")
    parser.add_argument("--repo", default="openhands/openhands")
    parser.add_argument("--ref", default="main")
    parser.add_argument("--source-dir", default="", help="Use a local source directory instead of downloading GitHub archive.")
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--case-root", default=str(ROOT / "results" / "github_repo_scoring_inputs"))
    parser.add_argument("--max-archive-bytes", type=int, default=200 * 1024 * 1024)
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    case_dir = Path(args.case_root).resolve() / f"{stamp}-{args.repo.replace('/', '-')}-{args.ref}"
    prepare_cmd = [
        sys.executable,
        str(ROOT / "scripts" / "prepare_github_repo_scoring_case.py"),
        "--repo",
        args.repo,
        "--ref",
        args.ref,
        "--dest",
        str(case_dir),
        "--max-archive-bytes",
        str(args.max_archive_bytes),
    ]
    if args.source_dir:
        prepare_cmd.extend(["--source-dir", args.source_dir])
    subprocess.run(prepare_cmd, cwd=ROOT, check=True)

    spec = read_json(SPEC_TEMPLATE)
    spec["id"] = f"github-repo-scoring-{args.repo.replace('/', '-').lower()}"
    try:
        spec["scope_subdir"] = case_dir.relative_to(ROOT).as_posix()
        env_workspace = str(ROOT)
    except ValueError:
        spec["scope_subdir"] = "."
        env_workspace = str(case_dir)
    spec["goal"] = f"Score GitHub repository {args.repo}@{args.ref} using bounded every-file evidence and produce improvement recommendations."
    spec["goal_plan"]["goal"] = spec["goal"]
    spec["goal_plan"]["supplied_inputs"] = list_supplied_inputs(case_dir)
    generated_spec = case_dir / "github-repo-scoring.generated.json"
    write_json(generated_spec, spec)

    env = {**os.environ, "AI_COMPANY_WORKSPACE_ROOT": env_workspace}
    harness_cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run_ai_company_task_harness.py"),
        str(generated_spec),
        "--mode",
        args.mode,
        "--out-root",
        str(Path(args.out_root).resolve()),
    ]
    return subprocess.run(harness_cmd, cwd=ROOT, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
