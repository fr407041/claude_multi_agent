from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_install import validate_repository_identity


class VerifyInstallIdentityTests(unittest.TestCase):
    def test_stale_repository_identity_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "PUBLISH_MANIFEST.json").write_text(
                json.dumps({"repository": "fr407041/multi_agent_claude_code"}),
                encoding="utf-8",
            )
            report = validate_repository_identity(root)
        self.assertFalse(report["passed"])
        self.assertTrue(any(item["code"] == "REPOSITORY_IDENTITY_MISMATCH" for item in report["errors"]))

    def test_current_repository_identity_passes_with_upstream_separated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "PUBLISH_MANIFEST.json").write_text(
                json.dumps(
                    {
                        "repository": "fr407041/claude_multi_agent",
                        "upstream_repository": "fr407041/multi_agent_claude_code",
                    }
                ),
                encoding="utf-8",
            )
            report = validate_repository_identity(root)
        self.assertTrue(report["passed"], report["errors"])


if __name__ == "__main__":
    unittest.main()
