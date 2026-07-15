from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.fab_agent_policy import ROOT, load_audit_entries, resolve_fab_agent
from scripts.policy_action_guard import guard_action


class PolicyActionGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="policy-action-guard-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _resolve(self, example_name: str) -> Path:
        result = resolve_fab_agent(ROOT / "fab_agents" / "examples" / example_name, self.tmp / "resolved")
        self.assertTrue(result["passed"], result)
        return Path(result["output_dir"])

    def test_readonly_write_tool_is_blocked_before_tool_use(self) -> None:
        runtime_dir = self._resolve("fab_product_planner")
        entry = guard_action(
            runtime_dir,
            tool_name="Write",
            tool_input={"file_path": "worktree/shopping-site/app.js", "content": "blocked"},
            detail="readonly write should be blocked",
        )
        self.assertFalse(entry["allowed"])
        self.assertTrue(entry["blocked"])
        self.assertEqual(entry["action"], "write_project_file")
        self.assertEqual(entry["hook_output"]["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("not allowed", entry["reason"])

    def test_builder_write_tool_allowed_inside_output_glob(self) -> None:
        runtime_dir = self._resolve("fab_frontend_builder")
        entry = guard_action(
            runtime_dir,
            tool_name="Write",
            tool_input={"file_path": "worktree/shopping-site/app.js", "content": "allowed"},
        )
        self.assertTrue(entry["allowed"], entry)
        self.assertFalse(entry["blocked"])
        self.assertEqual({}, entry["hook_output"])

    def test_guard_cli_blocks_and_writes_audit(self) -> None:
        runtime_dir = self._resolve("fab_product_planner")
        out = self.tmp / "guard-result.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "policy_action_guard.py"),
                str(runtime_dir),
                "--tool-name",
                "Write",
                "--tool-input-json",
                json.dumps({"file_path": "worktree/shopping-site/app.js", "content": "blocked"}),
                "--out",
                str(out),
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 3, completed.stdout)
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(payload["blocked"])
        audit = load_audit_entries(runtime_dir)
        self.assertEqual(1, len(audit))
        self.assertTrue(audit[0]["blocked"])


if __name__ == "__main__":
    unittest.main()
