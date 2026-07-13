from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


class GithubRepoScoringCaseTests(unittest.TestCase):
    def test_prepare_case_records_every_file_context_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "prepared"
            proc = subprocess.run(
                [
                    PYTHON,
                    str(ROOT / "scripts" / "prepare_github_repo_scoring_case.py"),
                    "--source-dir",
                    str(ROOT / "tests" / "fixtures" / "github_repo_scoring" / "sample_source"),
                    "--dest",
                    str(dest),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            metadata = json.loads((dest / "repo_metadata.json").read_text(encoding="utf-8"))
            inventory = json.loads((dest / "repository_inventory.json").read_text(encoding="utf-8"))["files"]
            context = json.loads((dest / "file_context_manifest.json").read_text(encoding="utf-8"))["files"]
            self.assertEqual(metadata["total_files"], len(inventory))
            self.assertEqual({item["path"] for item in inventory}, {item["path"] for item in context})
            self.assertTrue((dest / "bounded_file_context.md").read_text(encoding="utf-8").strip())

    def test_verifier_accepts_complete_repo_scoring_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = ROOT / "tests" / "fixtures" / "github_repo_scoring" / "openhands_prepared"
            shutil.copytree(source, root, dirs_exist_ok=True)
            output = root / "repo-score"
            output.mkdir()
            total = json.loads((root / "repo_metadata.json").read_text(encoding="utf-8"))["total_files"]
            context_count = len(json.loads((root / "file_context_manifest.json").read_text(encoding="utf-8"))["files"])
            (output / "file-coverage.json").write_text(
                json.dumps(
                    {
                        "all_files_considered": True,
                        "total_files": total,
                        "inventory_files": total,
                        "context_manifest_files": context_count,
                        "context_guard_actions": ["full_read"],
                    }
                ),
                encoding="utf-8",
            )
            (output / "scorecard.json").write_text(
                json.dumps(
                    {
                        "overall_score": 80,
                        "categories": {
                            "architecture": {"score": 80},
                            "maintainability": {"score": 80},
                            "testing": {"score": 80},
                            "documentation": {"score": 80},
                            "security": {"score": 80},
                            "developer_experience": {"score": 80},
                        },
                        "recommendations": ["a", "b", "c", "d", "e"],
                    }
                ),
                encoding="utf-8",
            )
            (output / "improvement-plan.md").write_text("\n".join(f"{idx}. Improve area {idx}" for idx in range(1, 6)), encoding="utf-8")
            (output / "report.md").write_text("This report states limitations and safe-read token context guard evidence.", encoding="utf-8")
            proc = subprocess.run(
                [PYTHON, str(ROOT / "scripts" / "verify_github_repo_scoring_artifact.py"), str(root)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            report = json.loads(proc.stdout)
            self.assertTrue(report["all_passed"])


if __name__ == "__main__":
    unittest.main()
