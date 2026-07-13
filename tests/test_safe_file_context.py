from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.safe_file_context import PATH_POLICY_VIOLATION, safe_read_file


class SafeFileContextTests(unittest.TestCase):
    def test_rejects_path_traversal_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = safe_read_file(root, "../outside.txt")
        self.assertEqual(result["status"], PATH_POLICY_VIOLATION)
        self.assertEqual(result["context_guard_action"], "blocked")

    def test_chunks_file_above_soft_limit(self) -> None:
        defaults = {
            "role_context_budgets": {"default": {"input_tokens": 100, "output_tokens": 50}},
            "file_soft_limit_bytes": 64,
            "file_hard_limit_bytes": 100000,
            "context_chunk_chars": 40,
            "context_chunk_overlap_chars": 0,
            "max_chunks_per_file": 2,
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "large.txt").write_text("A" * 500, encoding="utf-8")
            result = safe_read_file(root, "large.txt", defaults=defaults)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["context_guard_action"], "chunked_context")
        self.assertGreater(result["skipped_bytes"], 0)
        self.assertLess(result["included_chars"], result["size_bytes"])
        self.assertNotIn("text", result)

    def test_blocks_file_above_hard_limit(self) -> None:
        defaults = {
            "role_context_budgets": {"default": {"input_tokens": 100, "output_tokens": 50}},
            "file_soft_limit_bytes": 32,
            "file_hard_limit_bytes": 64,
            "context_chunk_chars": 40,
            "context_chunk_overlap_chars": 0,
            "max_chunks_per_file": 2,
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "too-large.txt").write_text("B" * 200, encoding="utf-8")
            result = safe_read_file(root, "too-large.txt", defaults=defaults)
        self.assertEqual(result["status"], "INPUT_FILE_TOO_LARGE")
        self.assertEqual(result["skipped_bytes"], result["size_bytes"])
        self.assertEqual(result["chunks"], [])


if __name__ == "__main__":
    unittest.main()
