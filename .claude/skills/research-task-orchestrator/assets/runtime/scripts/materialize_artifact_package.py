#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


PACKAGE_BEGIN = "ARTIFACT_PACKAGE_JSON_BEGIN"
PACKAGE_END = "ARTIFACT_PACKAGE_JSON_END"


class MaterializeError(ValueError):
    pass


def _extract_json_blob(text: str) -> str:
    if PACKAGE_BEGIN in text and PACKAGE_END in text:
        start = text.index(PACKAGE_BEGIN) + len(PACKAGE_BEGIN)
        end = text.index(PACKAGE_END, start)
        return text[start:end].strip()

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        return text[first : last + 1].strip()

    raise MaterializeError("NO_JSON_PACKAGE_FOUND")


def _safe_target(root: Path, rel_path: str) -> Path:
    if not isinstance(rel_path, str) or not rel_path.strip():
        raise MaterializeError("EMPTY_ARTIFACT_PATH")
    normalized = rel_path.replace("\\", "/").strip()
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        raise MaterializeError(f"ABSOLUTE_ARTIFACT_PATH:{rel_path}")
    parts = Path(normalized).parts
    if any(part == ".." for part in parts):
        raise MaterializeError(f"PATH_TRAVERSAL_ARTIFACT_PATH:{rel_path}")
    target = (root / normalized).resolve()
    root_resolved = root.resolve()
    if root_resolved not in [target, *target.parents]:
        raise MaterializeError(f"ARTIFACT_PATH_ESCAPE:{rel_path}")
    return target


def load_package(output_text: str) -> dict[str, Any]:
    blob = _extract_json_blob(output_text)
    try:
        package = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise MaterializeError(f"INVALID_JSON_PACKAGE:{exc}") from exc
    if not isinstance(package, dict):
        raise MaterializeError("PACKAGE_NOT_OBJECT")
    if package.get("schema_version") != "artifact-package.v1":
        raise MaterializeError("UNSUPPORTED_ARTIFACT_PACKAGE_SCHEMA")
    files = package.get("files")
    if not isinstance(files, list) or not files:
        raise MaterializeError("PACKAGE_FILES_EMPTY")
    return package


def materialize_package(output_text: str, root: Path) -> dict[str, Any]:
    package = load_package(output_text)
    root.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, Any]] = []
    for index, item in enumerate(package["files"]):
        if not isinstance(item, dict):
            raise MaterializeError(f"FILE_ENTRY_NOT_OBJECT:{index}")
        rel_path = item.get("path")
        content = item.get("content")
        if not isinstance(content, str):
            raise MaterializeError(f"FILE_CONTENT_NOT_STRING:{rel_path}")
        target = _safe_target(root, rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(
            {
                "path": rel_path,
                "target": str(target),
                "bytes": len(content.encode("utf-8")),
            }
        )
    return {
        "schema_version": "artifact-materializer-report.v1",
        "passed": True,
        "root": str(root),
        "file_count": len(written),
        "written_files": written,
        "final_answer": package.get("final_answer", ""),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize a model-produced artifact package into a bounded root.")
    parser.add_argument("--model-output", required=True, help="Text file containing model output with artifact-package.v1 JSON.")
    parser.add_argument("--root", required=True, help="Directory where relative artifact paths may be written.")
    parser.add_argument("--report", required=True, help="Path to write materializer JSON report.")
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    try:
        report = materialize_package(Path(args.model_output).read_text(encoding="utf-8", errors="replace"), Path(args.root))
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        report = {
            "schema_version": "artifact-materializer-report.v1",
            "passed": False,
            "failure_category": exc.args[0] if exc.args else exc.__class__.__name__,
            "error": str(exc),
            "root": args.root,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
