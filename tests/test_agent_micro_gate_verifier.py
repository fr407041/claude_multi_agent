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

    def test_gate_c_index_pages_are_not_article_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            artifact_dir = run_dir / "ptt-stock-live"
            artifact_dir.mkdir()
            urls = [
                "https://www.ptt.cc/bbs/Stock/M.1234567890.A.123.html",
                "https://www.ptt.cc/bbs/Stock/M.1234567891.A.123.html",
                "https://www.ptt.cc/bbs/Stock/M.1234567892.A.123.html",
                "https://www.ptt.cc/bbs/Stock/index.html",
                "https://www.ptt.cc/bbs/Stock/index10197.html",
            ]
            (artifact_dir / "urls.json").write_text(json.dumps(urls), encoding="utf-8")
            report = verify_gate("C", run_dir)
        self.assertFalse(report["pass"])
        self.assertIn("not all URLs are valid PTT Stock article URLs", report["fail_reasons"])

    def test_gate_c_five_valid_unique_urls_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            artifact_dir = run_dir / "ptt-stock-live"
            artifact_dir.mkdir()
            urls = [f"https://www.ptt.cc/bbs/Stock/M.{1234567890 + index}.A.{index}F0.html" for index in range(5)]
            (artifact_dir / "urls.json").write_text(json.dumps({"urls": urls}), encoding="utf-8")
            report = verify_gate("C", run_dir)
        self.assertTrue(report["pass"], report["fail_reasons"])

    def test_gate_c_five_valid_unique_urls_under_worktree_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            artifact_dir = run_dir / "worktree" / "ptt-stock-live"
            artifact_dir.mkdir(parents=True)
            urls = [f"https://www.ptt.cc/bbs/Stock/M.{1234567890 + index}.A.{index}F0.html" for index in range(5)]
            (artifact_dir / "urls.json").write_text(json.dumps({"urls": urls}), encoding="utf-8")
            report = verify_gate("C", run_dir)
        self.assertTrue(report["pass"], report["fail_reasons"])

    def test_gate_d_missing_article_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "ptt-stock-live").mkdir()
            report = verify_gate("D", run_dir)
        self.assertFalse(report["pass"])
        self.assertTrue(any("article.json" in item for item in report["fail_reasons"]))

    def test_gate_d_valid_article_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            artifact_dir = run_dir / "ptt-stock-live"
            artifact_dir.mkdir()
            payload = {
                "title": "[新聞] 測試文章",
                "url": "https://www.ptt.cc/bbs/Stock/M.1234567890.A.123.html",
                "author": "tester",
                "date": "Sun Jul 12 08:00:00 2026",
                "body": "這是一段測試用的 PTT Stock 文章正文。" * 10,
            }
            (artifact_dir / "article.json").write_text(json.dumps(payload), encoding="utf-8")
            report = verify_gate("D", run_dir)
        self.assertTrue(report["pass"], report["fail_reasons"])

    def test_gate_d_invalid_url_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            artifact_dir = run_dir / "ptt-stock-live"
            artifact_dir.mkdir()
            payload = {
                "title": "[新聞] 測試文章",
                "url": "https://example.com/not-ptt.html",
                "author": "tester",
                "date": "Sun Jul 12 08:00:00 2026",
                "body": "這是一段測試用的 PTT Stock 文章正文。" * 10,
            }
            (artifact_dir / "article.json").write_text(json.dumps(payload), encoding="utf-8")
            report = verify_gate("D", run_dir)
        self.assertFalse(report["pass"])
        self.assertIn("article URL invalid", report["fail_reasons"])

    def test_gate_d_short_body_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            artifact_dir = run_dir / "ptt-stock-live"
            artifact_dir.mkdir()
            payload = {
                "title": "[新聞] 測試文章",
                "url": "https://www.ptt.cc/bbs/Stock/M.1234567890.A.123.html",
                "author": "tester",
                "date": "Sun Jul 12 08:00:00 2026",
                "body": "too short",
            }
            (artifact_dir / "article.json").write_text(json.dumps(payload), encoding="utf-8")
            report = verify_gate("D", run_dir)
        self.assertFalse(report["pass"])
        self.assertIn("article body missing or too short", report["fail_reasons"])
        self.assertEqual("ARTIFACT_CONTENT_TOO_SHORT", report["failure_category"])
        self.assertEqual("ARTIFACT_CONTRACT_FAILED", report["failure_parent_category"])

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
                    {"url": f"https://www.ptt.cc/bbs/Stock/M.{1234567890 + index}.A.{index}F0.html"}
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
