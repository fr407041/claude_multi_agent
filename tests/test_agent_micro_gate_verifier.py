from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_agent_micro_gate import verify_gate


class AgentMicroGateVerifierTests(unittest.TestCase):
    def test_gate_c_missing_urls_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "ptt-stock-live").mkdir()
            report = verify_gate("C", run_dir)
        self.assertFalse(report["pass"])
        self.assertTrue(any("urls.json" in item for item in report["fail_reasons"]))

    def test_gate_c_empty_urls_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            artifact_dir = run_dir / "ptt-stock-live"
            artifact_dir.mkdir()
            (artifact_dir / "urls.json").write_text("[]", encoding="utf-8")
            report = verify_gate("C", run_dir)
        self.assertFalse(report["pass"])
        self.assertIn("expected exactly 5 unique URLs", report["fail_reasons"])

    def test_gate_c_empty_urls_under_worktree_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            artifact_dir = run_dir / "worktree" / "ptt-stock-live"
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "urls.json").write_text("[]", encoding="utf-8")
            report = verify_gate("C", run_dir)
        self.assertFalse(report["pass"])
        self.assertEqual(report["details"]["artifact_dir"], str(artifact_dir))

    def test_gate_c_five_valid_unique_urls_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            artifact_dir = run_dir / "ptt-stock-live"
            artifact_dir.mkdir()
            urls = [f"https://www.ptt.cc/bbs/Stock/M.{index}.A.html" for index in range(5)]
            (artifact_dir / "urls.json").write_text(json.dumps({"urls": urls}), encoding="utf-8")
            report = verify_gate("C", run_dir)
        self.assertTrue(report["pass"], report["fail_reasons"])

    def test_gate_c_five_valid_unique_urls_under_worktree_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            artifact_dir = run_dir / "worktree" / "ptt-stock-live"
            artifact_dir.mkdir(parents=True)
            urls = [f"https://www.ptt.cc/bbs/Stock/M.{index}.A.html" for index in range(5)]
            (artifact_dir / "urls.json").write_text(json.dumps({"urls": urls}), encoding="utf-8")
            report = verify_gate("C", run_dir)
        self.assertTrue(report["pass"], report["fail_reasons"])

    def test_gate_e_missing_stock_schema_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            artifact_dir = run_dir / "ptt-stock-live"
            artifact_dir.mkdir()
            payload = {
                "source_board": "PTT Stock",
                "fetched_at_utc": "2026-07-12T00:00:00Z",
                "article_count": 3,
                "articles": [
                    {"url": f"https://www.ptt.cc/bbs/Stock/M.{index}.A.html"}
                    for index in range(3)
                ],
                "stocks": [{"ticker_or_name": "2330"}],
                "limitations": [],
            }
            (artifact_dir / "final.json").write_text(json.dumps(payload), encoding="utf-8")
            report = verify_gate("E", run_dir)
        self.assertFalse(report["pass"])
        self.assertTrue(any("invalid stance" in item or "missing bullish_evidence" in item for item in report["fail_reasons"]))


if __name__ == "__main__":
    unittest.main()
