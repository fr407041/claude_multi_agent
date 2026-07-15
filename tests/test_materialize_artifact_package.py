from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.materialize_artifact_package import MaterializeError, materialize_package


def package_text(files: list[dict[str, str]]) -> str:
    payload = {
        "schema_version": "artifact-package.v1",
        "files": files,
        "final_answer": "done",
    }
    return "ARTIFACT_PACKAGE_JSON_BEGIN\n" + json.dumps(payload) + "\nARTIFACT_PACKAGE_JSON_END"


class MaterializeArtifactPackageTests(unittest.TestCase):
    def test_materializes_relative_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = materialize_package(
                package_text(
                    [
                        {"path": "shopping-site/index.html", "content": "<html>demo</html>"},
                        {"path": "shopping-site/app.js", "content": "console.log('demo')"},
                    ]
                ),
                root,
            )
            self.assertTrue(report["passed"])
            self.assertEqual(report["file_count"], 2)
            self.assertEqual((root / "shopping-site/index.html").read_text(encoding="utf-8"), "<html>demo</html>")

    def test_rejects_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(MaterializeError) as ctx:
                materialize_package(package_text([{"path": "/tmp/evil.txt", "content": "x"}]), Path(tmp))
            self.assertIn("ABSOLUTE_ARTIFACT_PATH", str(ctx.exception))

    def test_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(MaterializeError) as ctx:
                materialize_package(package_text([{"path": "../evil.txt", "content": "x"}]), Path(tmp))
            self.assertIn("PATH_TRAVERSAL_ARTIFACT_PATH", str(ctx.exception))

    def test_requires_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(MaterializeError) as ctx:
                materialize_package(json.dumps({"files": [{"path": "a.txt", "content": "x"}]}), Path(tmp))
            self.assertIn("UNSUPPORTED_ARTIFACT_PACKAGE_SCHEMA", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
