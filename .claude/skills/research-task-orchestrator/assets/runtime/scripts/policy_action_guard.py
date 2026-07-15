#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from fab_agent_policy import action_allowed, load_audit_entries, utc_now
    from verify_effective_agent_policy import verify_policy
except ModuleNotFoundError:  # pragma: no cover
    from .fab_agent_policy import action_allowed, load_audit_entries, utc_now
    from .verify_effective_agent_policy import verify_policy


TOOL_TO_ACTION = {
    "Read": "read_context",
    "Glob": "read_context",
    "Grep": "read_context",
    "Write": "write_project_file",
    "Edit": "edit_project_file",
    "MultiEdit": "edit_project_file",
    "Bash": "shell_command",
    "PowerShell": "shell_command",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extract_tool_path(tool_name: str, tool_input: dict[str, Any]) -> str:
    if tool_name in {"Write", "Edit", "MultiEdit", "Read"}:
        return str(tool_input.get("file_path") or tool_input.get("path") or "")
    if tool_name in {"Bash", "PowerShell"}:
        return str(tool_input.get("command") or "")
    return str(tool_input.get("path") or tool_input.get("file_path") or "")


def pre_tool_use_hook_response(allowed: bool, reason: str) -> dict[str, Any]:
    if allowed:
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def append_audit(runtime_dir: Path, entry: dict[str, Any]) -> None:
    log_path = runtime_dir / "audit.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def guard_action(
    runtime_dir: Path,
    *,
    action: str = "",
    path: str = "",
    tool_name: str = "",
    tool_input: dict[str, Any] | None = None,
    detail: str = "",
    audit: bool = True,
) -> dict[str, Any]:
    runtime_dir = runtime_dir.resolve()
    preflight = verify_policy(runtime_dir)
    if not preflight["passed"]:
        entry = {
            "timestamp": utc_now(),
            "agent_id": "",
            "capability": "",
            "action": action,
            "tool_name": tool_name,
            "path": path,
            "allowed": False,
            "blocked": True,
            "reason": "effective policy preflight failed",
            "detail": detail,
            "preflight": preflight,
            "hook_output": pre_tool_use_hook_response(False, "effective policy preflight failed"),
        }
        if audit:
            append_audit(runtime_dir, entry)
        return entry

    effective = read_json(runtime_dir / "effective-agent.json")
    tool_input = tool_input or {}
    mapped_action = action or TOOL_TO_ACTION.get(tool_name, "")
    target_path = path or extract_tool_path(tool_name, tool_input)
    if not mapped_action:
        allowed = False
        reason = f"tool {tool_name or '<missing>'} is not mapped to an approved CIM action"
    else:
        allowed, reason = action_allowed(effective, mapped_action, target_path)

    entry = {
        "timestamp": utc_now(),
        "agent_id": effective.get("agent_id", ""),
        "capability": effective.get("capability", ""),
        "action": mapped_action,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "path": target_path,
        "allowed": allowed,
        "blocked": not allowed,
        "reason": reason,
        "detail": detail,
        "policy_source": effective.get("policy_source", ""),
        "hook_output": pre_tool_use_hook_response(allowed, reason),
    }
    if audit:
        append_audit(runtime_dir, entry)
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description="Guard one runtime action/tool call against a resolved CIM effective policy.")
    parser.add_argument("runtime_dir")
    parser.add_argument("--action", default="")
    parser.add_argument("--path", default="")
    parser.add_argument("--tool-name", default="")
    parser.add_argument("--tool-input-json", default="")
    parser.add_argument("--detail", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-audit", action="store_true")
    args = parser.parse_args()

    tool_input: dict[str, Any] = {}
    if args.tool_input_json:
        payload = json.loads(args.tool_input_json)
        if not isinstance(payload, dict):
            raise SystemExit("--tool-input-json must decode to an object")
        tool_input = payload

    entry = guard_action(
        Path(args.runtime_dir),
        action=args.action,
        path=args.path,
        tool_name=args.tool_name,
        tool_input=tool_input,
        detail=args.detail,
        audit=not args.no_audit,
    )
    if args.out:
        write_json(Path(args.out), entry)
    if args.json or not args.out:
        print(json.dumps(entry, ensure_ascii=False, indent=2))
    return 0 if entry["allowed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
