from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.sdk_policy_hook_poc import build_effective_policy, dry_run, pre_tool_use_hook_response


class SdkPolicyHookPocTests(unittest.TestCase):
    def test_readonly_write_returns_pre_tool_deny(self) -> None:
        effective = build_effective_policy("readonly_research")
        output = pre_tool_use_hook_response(
            effective,
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "worktree/shopping-site/app.js", "content": "blocked"},
            },
        )
        specific = output["hookSpecificOutput"]
        self.assertEqual("PreToolUse", specific["hookEventName"])
        self.assertEqual("deny", specific["permissionDecision"])
        self.assertIn("not allowed", specific["permissionDecisionReason"])

    def test_readonly_read_is_allowed(self) -> None:
        effective = build_effective_policy("readonly_research")
        output = pre_tool_use_hook_response(
            effective,
            {"tool_name": "Read", "tool_input": {"file_path": "README.md"}},
        )
        self.assertEqual({}, output)

    def test_dry_run_proves_write_edit_bash_blocked_and_no_file_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = dry_run(Path(tmp), "readonly_research")
            self.assertEqual("pass", result["overall_status"])
            self.assertTrue(result["acceptance"]["read_allowed"])
            self.assertTrue(result["acceptance"]["write_blocked_before_tool"])
            self.assertTrue(result["acceptance"]["edit_blocked_before_tool"])
            self.assertTrue(result["acceptance"]["bash_blocked_before_tool"])
            self.assertTrue(result["acceptance"]["powershell_blocked_before_tool"])
            self.assertTrue(result["acceptance"]["blocked_file_not_created"])
            self.assertFalse((Path(tmp) / "worktree" / "shopping-site" / "app.js").exists())


if __name__ == "__main__":
    unittest.main()
