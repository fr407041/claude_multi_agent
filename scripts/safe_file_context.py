#!/usr/bin/env python3
"""Safe file context loader for managed agent runtimes.

This module is the enforceable read boundary for CIM-managed workers and the
local-model action executor. It stats files before reading content, uses the
shared bounded-context policy, and returns an auditable payload instead of a
raw full-file read.

It is not a sandbox for unrestricted shell access. If a caller grants a model
arbitrary shell tools, that caller must enforce file policy at the tool layer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from bounded_context_loader import context_budget_for, load_context_defaults, load_file_context
except ModuleNotFoundError:  # pragma: no cover - package import path
    from scripts.bounded_context_loader import context_budget_for, load_context_defaults, load_file_context


PATH_POLICY_VIOLATION = "PATH_POLICY_VIOLATION"


def _resolve_within(root: Path, rel_path: str) -> tuple[Path | None, str, str | None]:
    if not rel_path or Path(rel_path).is_absolute():
        return None, rel_path, f"path must be relative to context root: {rel_path!r}"
    root_resolved = root.resolve()
    target = (root_resolved / rel_path).resolve()
    if target != root_resolved and root_resolved not in target.parents:
        return None, rel_path, f"path escapes context root: {rel_path}"
    return target, target.relative_to(root_resolved).as_posix(), None


def _public_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in chunk.items() if key != "text"}


def safe_read_file(
    root: Path,
    rel_path: str,
    *,
    role: str = "default",
    defaults: dict[str, Any] | None = None,
    include_text: bool = False,
) -> dict[str, Any]:
    """Return bounded context for a file under *root*.

    Status values:
    - ok: content was loaded within the active policy, possibly chunked.
    - missing: target does not exist or is not a regular file.
    - INPUT_FILE_TOO_LARGE: file exceeded the configured hard limit.
    - PATH_POLICY_VIOLATION: path was absolute, empty, or escaped root.
    """

    target, normalized_rel, error = _resolve_within(root, rel_path)
    if error or target is None:
        return {
            "path": rel_path,
            "status": PATH_POLICY_VIOLATION,
            "error": error or "path policy violation",
            "context_guard_action": "blocked",
        }

    defaults = defaults or load_context_defaults()
    budget = context_budget_for(role, defaults)
    loaded = load_file_context(
        target,
        max_context_tokens=max(1, int(budget.get("input_tokens", 1))),
        soft_limit_bytes=int(defaults.get("file_soft_limit_bytes", 262144)),
        hard_limit_bytes=int(defaults.get("file_hard_limit_bytes", 2097152)),
        chunk_chars=int(defaults.get("context_chunk_chars", 4000)),
        overlap_chars=int(defaults.get("context_chunk_overlap_chars", 200)),
        max_chunks=int(defaults.get("max_chunks_per_file", 32)),
    )
    public = {key: value for key, value in loaded.items() if key not in {"text", "chunks"}}
    public["path"] = normalized_rel
    public["absolute_path"] = str(target)
    public["context_budget_tokens"] = int(budget.get("input_tokens", 0))
    public["chunks"] = [_public_chunk(chunk) for chunk in loaded.get("chunks", [])]
    if include_text:
        public["text"] = "\n".join(str(chunk.get("text", "")) for chunk in loaded.get("chunks", []))
    return public


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely read bounded file context under a root directory.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--role", default="default")
    parser.add_argument("--include-text", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = safe_read_file(Path(args.root), args.path, role=args.role, include_text=args.include_text)
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.json else None))
    return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
