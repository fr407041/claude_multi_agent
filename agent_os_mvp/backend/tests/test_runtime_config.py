from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.db import get_db, get_db_path_warning, init_db
from app.services.ai_company_monitor import REPO_ROOT, get_results_root


class RuntimeConfigTests(unittest.TestCase):
    def test_default_results_root(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_results_root(), REPO_ROOT / "results" / "ai_company_task_harness")

    def test_absolute_results_root_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"AI_COMPANY_RESULTS_ROOT": temp_dir}, clear=True):
                self.assertEqual(get_results_root(), Path(temp_dir).resolve())

    def test_relative_results_root_is_project_relative(self) -> None:
        with patch.dict(os.environ, {"AI_COMPANY_RESULTS_ROOT": "tmp/external-runs"}, clear=True):
            self.assertEqual(get_results_root(), (REPO_ROOT / "tmp" / "external-runs").resolve())

    def test_invalid_sqlite_parent_falls_back_instead_of_crashing(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            broken_parent = Path(temp_dir) / "data"
            broken_parent.write_text("not a directory", encoding="utf-8")
            fallback_dir = Path(temp_dir) / "fallback"
            with patch.dict(
                os.environ,
                {
                    "AGENT_OS_DB_PATH": str(broken_parent / "agent_os.db"),
                    "AGENT_OS_DB_FALLBACK_DIR": str(fallback_dir),
                },
                clear=False,
            ):
                init_db()
                warning = get_db_path_warning()
                with get_db() as connection:
                    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()

        self.assertIsNotNone(warning)
        self.assertEqual("DASHBOARD_DATA_PATH_INVALID", warning["code"])
        self.assertTrue((fallback_dir / "agent_os.db").exists())
        self.assertTrue(any(row["name"] == "goals" for row in rows))


if __name__ == "__main__":
    unittest.main()
