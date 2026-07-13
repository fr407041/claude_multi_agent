#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from safe_file_context import safe_read_file


DEFAULT_REPO = "openhands/openhands"
BOUNDED_EVIDENCE_TOKEN_BUDGET = 12000
MAX_SNIPPET_CHARS_PER_FILE = 6000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_github_archive(repo: str, ref: str, dest: Path, max_bytes: int) -> dict[str, Any]:
    url = f"https://github.com/{repo}/archive/refs/heads/{ref}.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise SystemExit(f"GitHub archive exceeded bounded download limit: {max_bytes} bytes")
    dest.write_bytes(data)
    return {"archive_url": url, "archive_path": str(dest), "archive_sha256": hashlib.sha256(data).hexdigest(), "archive_bytes": len(data)}


def resolve_source(args: argparse.Namespace, work_dir: Path) -> tuple[Path, dict[str, Any]]:
    if args.source_dir:
        source = Path(args.source_dir).resolve()
        if not source.is_dir():
            raise SystemExit(f"source dir not found: {source}")
        return source, {"source_kind": "local_dir", "source_dir": str(source)}

    archive = work_dir / "source.zip"
    metadata = download_github_archive(args.repo, args.ref, archive, int(args.max_archive_bytes))
    extract_root = work_dir / "extracted"
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(extract_root)
    children = [item for item in extract_root.iterdir() if item.is_dir()]
    if not children:
        raise SystemExit("GitHub archive extraction produced no source directory")
    return children[0], {"source_kind": "github_archive", "repo": args.repo, "ref": args.ref, **metadata}


def language_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if path.name.lower() == "dockerfile":
        return "dockerfile"
    return suffix.lstrip(".") or "unknown"


def build_case(source_root: Path, dest: Path, source_meta: dict[str, Any], *, shard_size: int) -> dict[str, Any]:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shards_dir = dest / "inventory_shards"
    shards_dir.mkdir()

    inventory: list[dict[str, Any]] = []
    context_manifest: list[dict[str, Any]] = []
    bounded_blocks: list[str] = []
    copied_source = dest / "source"
    copied_source.mkdir()

    bounded_tokens_used = 0
    bounded_budget_exhausted = False

    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source_root).as_posix()
        size = path.stat().st_size
        target = copied_source / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        safe = safe_read_file(copied_source, rel)
        item = {
            "path": rel,
            "size_bytes": size,
            "sha256": sha256_file(path),
            "language": language_for(path),
            "safe_read_status": safe.get("status", "unknown"),
            "context_guard_action": safe.get("context_guard_action", "unknown"),
            "included_for_context": safe.get("status") == "ok",
        }
        inventory.append(item)
        context_manifest.append({key: value for key, value in safe.items() if key not in {"absolute_path", "chunks", "text"}})
        if safe.get("status") == "ok" and not bounded_budget_exhausted:
            text_payload = safe_read_file(copied_source, rel, include_text=True)
            snippet = str(text_payload.get("text", "")).strip()
            if snippet:
                snippet = snippet[:MAX_SNIPPET_CHARS_PER_FILE]
                snippet_tokens = max(1, len(snippet) // 4)
                if bounded_tokens_used + snippet_tokens > BOUNDED_EVIDENCE_TOKEN_BUDGET:
                    bounded_budget_exhausted = True
                    continue
                bounded_tokens_used += snippet_tokens
                bounded_blocks.append(
                    "\n".join(
                        [
                            f"## File: {rel}",
                            f"size_bytes: {size}",
                            f"context_guard_action: {safe.get('context_guard_action')}",
                            f"skipped_bytes: {safe.get('skipped_bytes', 0)}",
                            f"sha256: {item['sha256']}",
                            "",
                            snippet,
                        ]
                    )
                )

    shard_paths: list[str] = []
    for index in range(0, len(inventory), shard_size):
        shard = inventory[index : index + shard_size]
        shard_path = shards_dir / f"shard-{index // shard_size:03d}.json"
        shard_path.write_text(json.dumps({"files": shard}, ensure_ascii=False, indent=2), encoding="utf-8")
        shard_paths.append(shard_path.relative_to(dest).as_posix())

    status_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    skipped_bytes = 0
    for item in context_manifest:
        status = str(item.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
        action = str(item.get("context_guard_action", "unknown"))
        action_counts[action] = action_counts.get(action, 0) + 1
        skipped_bytes += int(item.get("skipped_bytes", 0) or 0)
    repo_metadata = {
        "schema_version": "github-repo-scoring-input.v1",
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_repo": source_meta.get("repo", DEFAULT_REPO),
        "target_ref": source_meta.get("ref", ""),
        "source": source_meta,
        "total_files": len(inventory),
        "inventory_files": len(inventory),
        "context_manifest_files": len(context_manifest),
        "context_status_counts": status_counts,
        "context_guard_action_counts": action_counts,
        "bounded_evidence_token_budget": BOUNDED_EVIDENCE_TOKEN_BUDGET,
        "bounded_evidence_estimated_tokens": bounded_tokens_used,
        "bounded_evidence_budget_exhausted": bounded_budget_exhausted,
        "skipped_bytes": skipped_bytes,
        "inventory_shards": shard_paths,
        "safe_read_policy": "Every file is inventoried and evaluated by the same deterministic safe_file_context policy. No manual file allowlist, denylist, extension list, or hand-selected split plan is used.",
    }
    (dest / "repo_metadata.json").write_text(json.dumps(repo_metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (dest / "repository_inventory.json").write_text(json.dumps({"files": inventory}, ensure_ascii=False, indent=2), encoding="utf-8")
    (dest / "file_context_manifest.json").write_text(json.dumps({"files": context_manifest}, ensure_ascii=False, indent=2), encoding="utf-8")
    evidence_header = "\n".join(
        [
            "# Bounded repository evidence",
            "",
            "This evidence is generated automatically from the file context guard.",
            "It is not a full raw repository prompt. Omitted, skipped, blocked, and chunked bytes are recorded in file_context_manifest.json.",
            f"Estimated evidence tokens: {bounded_tokens_used}",
            f"Evidence token budget: {BOUNDED_EVIDENCE_TOKEN_BUDGET}",
            "",
        ]
    )
    (dest / "bounded_file_context.md").write_text(evidence_header + "\n\n".join(bounded_blocks) + "\n", encoding="utf-8")
    return repo_metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a bounded every-file GitHub repo scoring input case.")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--ref", default="main")
    parser.add_argument("--source-dir", default="")
    parser.add_argument("--dest", required=True)
    parser.add_argument("--shard-size", type=int, default=200)
    parser.add_argument("--max-archive-bytes", type=int, default=200 * 1024 * 1024)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as temp:
        source_root, source_meta = resolve_source(args, Path(temp))
        report = build_case(source_root, Path(args.dest).resolve(), source_meta, shard_size=max(1, args.shard_size))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
