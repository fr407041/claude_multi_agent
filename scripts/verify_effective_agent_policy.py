#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


REQUIRED_EFFECTIVE_KEYS = {
    "schema_version",
    "agent_id",
    "capability",
    "policy_source",
    "effective_allowed_skills",
    "effective_skill_mounts",
    "effective_allowed_mcp_groups",
    "effective_tool_policy",
    "allowed_actions",
    "blocked_actions",
}


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"__read_error__": str(exc)}
    return payload if isinstance(payload, dict) else {"__read_error__": "JSON root must be an object"}


def project_root_candidates(extra_roots: list[Path] | None = None) -> list[Path]:
    roots: list[Path] = []
    for value in [
        os.environ.get("AI_COMPANY_PROJECT_ROOT", ""),
        os.environ.get("MULTI_AGENT_REPO", ""),
        os.environ.get("AI_COMPANY_WORKSPACE_ROOT", ""),
    ]:
        if value:
            roots.append(Path(value))
    roots.extend(extra_roots or [])
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            unique.append(root)
            seen.add(key)
    return unique


def resolve_skill_source(skill_name: str, source_path: str, project_roots: list[Path] | None = None) -> dict[str, Any]:
    source = Path(source_path)
    candidates = [source]
    for root in project_root_candidates(project_roots):
        candidates.append(root / ".claude" / "skills" / skill_name)
    for candidate in candidates:
        if candidate.is_dir():
            return {
                "name": skill_name,
                "source_path": source_path,
                "resolved_source_path": str(candidate),
                "exists": True,
                "used_fallback": str(candidate) != source_path,
            }
    return {
        "name": skill_name,
        "source_path": source_path,
        "resolved_source_path": "",
        "exists": False,
        "used_fallback": False,
    }


def verify_policy(runtime_dir: Path, project_roots: list[Path] | None = None) -> dict[str, Any]:
    runtime_dir = runtime_dir.resolve()
    effective_path = runtime_dir / "effective-agent.json"
    approved_skills_path = runtime_dir / "mounted-skills" / "approved-skills.json"
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not effective_path.is_file():
        errors.append({"code": "EFFECTIVE_AGENT_POLICY_MISSING", "detail": str(effective_path)})
        effective: dict[str, Any] = {}
    else:
        effective = read_json(effective_path)
        if "__read_error__" in effective:
            errors.append({"code": "EFFECTIVE_AGENT_POLICY_INVALID_JSON", "detail": effective["__read_error__"]})
            effective = {}

    if not approved_skills_path.is_file():
        errors.append({"code": "APPROVED_SKILLS_MANIFEST_MISSING", "detail": str(approved_skills_path)})
        approved_skills: dict[str, Any] = {}
    else:
        approved_skills = read_json(approved_skills_path)
        if "__read_error__" in approved_skills:
            errors.append({"code": "APPROVED_SKILLS_MANIFEST_INVALID_JSON", "detail": approved_skills["__read_error__"]})
            approved_skills = {}

    if effective:
        missing_keys = sorted(REQUIRED_EFFECTIVE_KEYS - set(effective))
        if missing_keys:
            errors.append({"code": "EFFECTIVE_AGENT_POLICY_INCOMPLETE", "detail": missing_keys})
        if effective.get("policy_source") != "CIM":
            errors.append({"code": "EFFECTIVE_AGENT_POLICY_NOT_CIM", "detail": effective.get("policy_source")})
        if effective.get("schema_version") != "fab-agent-effective.v1":
            errors.append({"code": "EFFECTIVE_AGENT_POLICY_SCHEMA_UNSUPPORTED", "detail": effective.get("schema_version")})

    effective_skills = [str(item) for item in effective.get("effective_allowed_skills", [])] if effective else []
    manifest_skills = approved_skills.get("skills", []) if isinstance(approved_skills.get("skills"), list) else []
    manifest_skill_names = [str(item.get("name", "")) for item in manifest_skills if isinstance(item, dict)]
    if effective and approved_skills and effective_skills != manifest_skill_names:
        errors.append(
            {
                "code": "APPROVED_SKILLS_MANIFEST_MISMATCH",
                "detail": {"effective_allowed_skills": effective_skills, "approved_skills": manifest_skill_names},
            }
        )

    missing_skill_mounts = []
    resolved_skill_sources = []
    for item in manifest_skills:
        if not isinstance(item, dict):
            errors.append({"code": "APPROVED_SKILLS_ENTRY_INVALID", "detail": item})
            continue
        resolved = resolve_skill_source(str(item.get("name", "")), str(item.get("source_path", "")), project_roots)
        resolved_skill_sources.append(resolved)
        if not resolved["exists"]:
            missing_skill_mounts.append({"name": item.get("name", ""), "source_path": str(item.get("source_path", ""))})
    if missing_skill_mounts:
        errors.append({"code": "APPROVED_SKILL_SOURCE_MISSING", "detail": missing_skill_mounts})

    if effective and effective.get("blocked_user_fields"):
        errors.append({"code": "FAB_AGENT_POLICY_VIOLATION", "detail": effective.get("blocked_user_fields")})

    if effective and not effective.get("effective_skill_mounts"):
        warnings.append({"code": "NO_APPROVED_SKILLS", "detail": "Capability exposes no skills."})

    return {
        "passed": not errors,
        "runtime_dir": str(runtime_dir),
        "effective_policy_path": str(effective_path),
        "approved_skills_path": str(approved_skills_path),
        "agent_id": effective.get("agent_id", ""),
        "capability": effective.get("capability", ""),
        "policy_source": effective.get("policy_source", ""),
        "approved_skill_count": len(manifest_skill_names),
        "resolved_skill_sources": resolved_skill_sources,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a resolved Fab agent effective policy before runtime use.")
    parser.add_argument("runtime_dir", help="Directory containing effective-agent.json and mounted-skills/approved-skills.json")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    report = verify_policy(Path(args.runtime_dir))
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json or not args.out:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
