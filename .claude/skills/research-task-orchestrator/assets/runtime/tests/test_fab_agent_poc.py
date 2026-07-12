from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FabAgentPocTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="fab-agent-poc-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mock_poc_produces_outputs_and_enforcement_evidence(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "run_fab_agent_poc.py"),
                "--case",
                "shopping-site",
                "--mode",
                "mock",
                "--out-root",
                str(self.tmp),
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=120,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout[-2000:])
        summary = json.loads(completed.stdout)
        run_dir = Path(summary["run_dir"])
        self.assertEqual(summary["overall_status"], "pass")
        self.assertTrue(summary["acceptance"]["resolved_three_fab_agents"])
        self.assertTrue(summary["acceptance"]["blocked_readonly_project_write"])
        self.assertTrue(summary["acceptance"]["blocked_reviewer_project_edit"])
        self.assertTrue(summary["acceptance"]["shopping_site_verified"])
        self.assertGreaterEqual(len(summary["blocked_attempts"]), 2)
        for rel in [
            "worktree/shopping-site/index.html",
            "worktree/shopping-site/styles.css",
            "worktree/shopping-site/app.js",
            "worktree/shopping-site/README.md",
            "ai_company/meeting_decision.json",
            "ai_company/artifact_verify_report.json",
        ]:
            self.assertTrue((run_dir / rel).is_file(), rel)
        for policy in summary["effective_policies"]:
            self.assertEqual(policy["policy_source"], "CIM")
            self.assertNotIn("mcp_servers", policy)
            self.assertIsInstance(policy["effective_allowed_mcp_groups"], list)


if __name__ == "__main__":
    unittest.main()
