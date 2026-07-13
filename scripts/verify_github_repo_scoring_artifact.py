#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_OUTPUTS = [
    "repo-score/file-coverage.json",
    "repo-score/scorecard.json",
    "repo-score/improvement-plan.md",
    "repo-score/report.md",
]
REQUIRED_SCORE_CATEGORIES = {"architecture", "maintainability", "testing", "documentation", "security", "developer_experience"}


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def output_check(root: Path, rel: str) -> dict[str, Any]:
    path = root / rel
    return {
        "label": f"{rel} exists",
        "status": "pass" if path.is_file() and path.stat().st_size > 0 else "fail",
        "path": str(path),
        "detail": f"{path.stat().st_size} bytes" if path.is_file() else "missing file",
    }


def improvement_count(text: str) -> int:
    return len(re.findall(r"(?m)^\s*(?:[-*]|\d+[.)])\s+", text))


def verify(root: Path) -> dict[str, Any]:
    root = root.resolve()
    metadata = read_json(root / "repo_metadata.json")
    inventory = read_json(root / "repository_inventory.json")
    context = read_json(root / "file_context_manifest.json")
    coverage = read_json(root / "repo-score/file-coverage.json")
    scorecard = read_json(root / "repo-score/scorecard.json")
    improvement = read_text(root / "repo-score/improvement-plan.md")
    report = read_text(root / "repo-score/report.md")

    inventory_files = inventory.get("files", []) if isinstance(inventory.get("files"), list) else []
    context_files = context.get("files", []) if isinstance(context.get("files"), list) else []
    inventory_paths = {str(item.get("path")) for item in inventory_files if isinstance(item, dict)}
    context_paths = {str(item.get("path")) for item in context_files if isinstance(item, dict)}
    total_files = int(metadata.get("total_files") or len(inventory_files))
    status_values = {str(item.get("status")) for item in context_files if isinstance(item, dict)}
    guard_actions = {str(item.get("context_guard_action")) for item in context_files if isinstance(item, dict)}

    categories = scorecard.get("categories", {})
    category_keys = set(categories.keys()) if isinstance(categories, dict) else set()
    recommendations = scorecard.get("recommendations", [])

    checks: list[dict[str, Any]] = [output_check(root, rel) for rel in REQUIRED_OUTPUTS]
    checks.extend(
        [
            {
                "label": "repository metadata exists",
                "status": "pass" if metadata.get("schema_version") == "github-repo-scoring-input.v1" else "fail",
                "detail": str(root / "repo_metadata.json"),
            },
            {
                "label": "every inventory file has a context status",
                "status": "pass" if total_files > 0 and inventory_paths == context_paths else "fail",
                "detail": f"inventory={len(inventory_paths)} context={len(context_paths)} total={total_files}",
            },
            {
                "label": "safe-read guard evidence is present",
                "status": "pass" if guard_actions and not ({""} & guard_actions) else "fail",
                "detail": ", ".join(sorted(guard_actions)),
            },
            {
                "label": "coverage artifact states every file was considered",
                "status": "pass"
                if coverage.get("all_files_considered") is True
                and int(coverage.get("total_files", -1)) == total_files
                and int(coverage.get("context_manifest_files", -2)) == len(context_files)
                else "fail",
                "detail": json.dumps(
                    {
                        "coverage_total": coverage.get("total_files"),
                        "metadata_total": total_files,
                        "context_manifest_files": coverage.get("context_manifest_files"),
                    },
                    ensure_ascii=False,
                ),
            },
            {
                "label": "scorecard has required categories",
                "status": "pass" if REQUIRED_SCORE_CATEGORIES.issubset(category_keys) else "fail",
                "detail": ", ".join(sorted(category_keys)),
            },
            {
                "label": "scorecard has numeric overall score",
                "status": "pass" if isinstance(scorecard.get("overall_score"), (int, float)) and 0 <= float(scorecard["overall_score"]) <= 100 else "fail",
                "detail": str(scorecard.get("overall_score")),
            },
            {
                "label": "scorecard includes improvement recommendations",
                "status": "pass" if isinstance(recommendations, list) and len(recommendations) >= 5 else "fail",
                "detail": f"recommendations={len(recommendations) if isinstance(recommendations, list) else 0}",
            },
            {
                "label": "improvement plan gives at least five actions",
                "status": "pass" if improvement_count(improvement) >= 5 else "fail",
                "detail": f"actions={improvement_count(improvement)}",
            },
            {
                "label": "human report mentions limitations and token guard",
                "status": "pass" if "limit" in report.lower() and re.search(r"token|context|safe-read|safe read", report, re.I) else "fail",
                "detail": "report should not imply full raw repo was loaded into one prompt",
            },
        ]
    )
    failed = [item for item in checks if item["status"] != "pass"]
    return {
        "schema_version": "github-repo-scoring-verifier.v1",
        "profile": "github-repo-scoring",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "target_repo": metadata.get("target_repo", ""),
        "expected_outputs": REQUIRED_OUTPUTS,
        "all_passed": not failed,
        "score": round((len(checks) - len(failed)) / len(checks), 3) if checks else 0.0,
        "checks": checks,
        "failure_category": "" if not failed else "REPO_SCORING_CONTRACT_FAILED",
        "failed_checks": [item["label"] for item in failed],
        "metrics": {
            "total_files": total_files,
            "context_manifest_files": len(context_files),
            "context_statuses": sorted(status_values),
            "context_guard_actions": sorted(guard_actions),
            "recommendation_count": len(recommendations) if isinstance(recommendations, list) else 0,
        },
        "user_summary": "Repository scoring package is ready for review." if not failed else "Repository scoring package is incomplete or not supported by safe-read evidence.",
        "limitations": [
            "Verifier checks the scoring package and every-file coverage evidence; it does not judge whether every recommendation is objectively optimal.",
            "Large files are assessed through bounded context metadata and snippets, not a single full-context prompt.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify GitHub repository scoring output package.")
    parser.add_argument("root")
    args = parser.parse_args(argv)
    report = verify(Path(args.root))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
