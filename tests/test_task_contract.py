from __future__ import annotations

import unittest

from scripts.task_contract import FAILURE_CATEGORY, verify_task_contract


class TaskContractTests(unittest.TestCase):
    def test_exact_json_contract_passes(self) -> None:
        report = verify_task_contract(
            'Reply exact JSON {"ok":true,"repo":"fr407041/claude_multi_agent"}',
            'router_direct_response:\n{"ok": true, "repo": "fr407041/claude_multi_agent"}\n',
        )
        self.assertTrue(report["passed"], report["failed_checks"])
        self.assertTrue(report["contract_required"])

    def test_return_exact_json_only_contract_passes(self) -> None:
        report = verify_task_contract(
            'Return exact JSON only: {"ok":true,"repo":"fr407041/claude_multi_agent","contract":"exact_json"}',
            '{"ok":true,"repo":"fr407041/claude_multi_agent","contract":"exact_json"}',
        )
        self.assertTrue(report["passed"], report["failed_checks"])
        self.assertTrue(report["contract_required"])

    def test_exact_json_contract_blocks_wrong_output(self) -> None:
        report = verify_task_contract(
            'Reply exact JSON {"ok":true,"repo":"fr407041/claude_multi_agent"}',
            "Install verification passed.\nI can help with that.\n",
        )
        self.assertFalse(report["passed"])
        self.assertEqual(FAILURE_CATEGORY, report["failure_category"])
        self.assertIn("response JSON does not match", report["failed_checks"][0])

    def test_no_think_error_blocks_success(self) -> None:
        report = verify_task_contract(
            "Say hello.",
            "Unknown command: /no_think\nHello.\n",
        )
        self.assertFalse(report["passed"])
        self.assertEqual(FAILURE_CATEGORY, report["failure_category"])

    def test_nonce_contract_is_enforced(self) -> None:
        report = verify_task_contract(
            "Reply with exactly this nonce in the final answer: AGENT-LIVE-abc123",
            "The final nonce is AGENT-LIVE-abc123.",
        )
        self.assertTrue(report["passed"], report["failed_checks"])

        failed = verify_task_contract(
            "Reply with exactly this nonce in the final answer: AGENT-LIVE-abc123",
            "done",
        )
        self.assertFalse(failed["passed"])


if __name__ == "__main__":
    unittest.main()
