#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_ROOT = ROOT / "configs" / "cim_capabilities"
FAB_AGENT_ROOT = ROOT / "fab_agents"

FORBIDDEN_FAB_AGENT_FIELDS = {
    "skills",
    "skill",
    "mcp",
    "mcp_servers",
    "mcpServers",
    "mcp_groups",
    "allowed_tools",
    "allowedTools",
    "tools",
    "hooks",
    "commands",
    "allowed_commands",
    "shell_commands",
}

BACKGROUND_OVERRIDE_PATTERNS = [
    r"ignore (?:all )?(?:previous|system|developer|cim|policy)",
    r"bypass (?:the )?(?:policy|verifier|permission|permissions)",
    r"use any (?:mcp|tool|skill)",
    r"install (?:a )?(?:package|dependency|tool)",
    r"disable (?:the )?(?:hook|hooks|verifier|policy)",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_capabilities(root: Path = CAPABILITY_ROOT) -> dict[str, dict[str, Any]]:
    capabilities: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        data = read_json(path)
        capability_id = str(data.get("id") or path.stem)
        data["id"] = capability_id
        data["_source_path"] = str(path)
        capabilities[capability_id] = data
    return capabilities


def load_fab_agent(agent_dir: Path) -> tuple[dict[str, Any], str]:
    config_path = agent_dir / "agent.json"
    if not config_path.is_file():
        raise FileNotFoundError(f"missing agent.json: {config_path}")
    agent = read_json(config_path)
    background_file = str(agent.get("background_file") or "background.md")
    background_path = agent_dir / background_file
    background = background_path.read_text(encoding="utf-8", errors="replace") if background_path.is_file() else ""
    return agent, background


def validate_fab_agent(agent_dir: Path, capabilities: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    capabilities = capabilities or load_capabilities()
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    agent, background = load_fab_agent(agent_dir)

    agent_id = str(agent.get("id") or agent_dir.name)
    illegal = sorted(field for field in agent.keys() if field in FORBIDDEN_FAB_AGENT_FIELDS)
    for field in illegal:
        errors.append({"code": "FAB_AGENT_POLICY_VIOLATION", "detail": f"{agent_id}: Fab agent cannot set {field}; choose a CIM capability instead."})

    capability_id = str(agent.get("capability") or "")
    capability = capabilities.get(capability_id)
    if not capability:
        errors.append({"code": "UNKNOWN_CIM_CAPABILITY", "detail": f"{agent_id}: capability {capability_id or '<missing>'} is not in configs/cim_capabilities."})

    if not background.strip():
        errors.append({"code": "MISSING_AGENT_BACKGROUND", "detail": f"{agent_id}: background file is missing or empty."})

    for pattern in BACKGROUND_OVERRIDE_PATTERNS:
        if re.search(pattern, background, flags=re.IGNORECASE):
            errors.append({"code": "FAB_AGENT_POLICY_VIOLATION", "detail": f"{agent_id}: background attempts to override CIM policy: {pattern}"})

    if capability and "write_project_file" in str(background).lower() and "write_project_file" not in set(capability.get("allowed_actions", [])):
        warnings.append({"code": "BACKGROUND_REQUESTS_BLOCKED_ACTION", "detail": f"{agent_id}: background mentions project writes but capability {capability_id} does not allow project-file writes."})

    return {
        "agent_id": agent_id,
        "agent_dir": str(agent_dir),
        "capability": capability_id,
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "blocked_user_fields": illegal,
    }


def resolve_fab_agent(agent_dir: Path, output_dir: Path, capabilities: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    capabilities = capabilities or load_capabilities()
    validation = validate_fab_agent(agent_dir, capabilities)
    if not validation["passed"]:
        return {"passed": False, "validation": validation}

    agent, background = load_fab_agent(agent_dir)
    capability = capabilities[str(agent["capability"])]
    agent_id = str(agent.get("id") or agent_dir.name)
    agent_out = output_dir / agent_id
    agent_out.mkdir(parents=True, exist_ok=True)
    mounted_skills = agent_out / "mounted-skills"
    mounted_skills.mkdir(exist_ok=True)
    skill_mounts = []
    for skill_name in capability.get("allowed_skills", []):
        source_path = ROOT / ".claude" / "skills" / str(skill_name)
        skill_mounts.append(
            {
                "name": str(skill_name),
                "source_path": str(source_path),
                "exists": source_path.is_dir(),
                "mount_path": str(mounted_skills / str(skill_name)),
                "managed_by": "CIM",
            }
        )
    (mounted_skills / "README.md").write_text(
        "This directory is a POC marker. Runtime must mount only CIM-approved skills here.\n",
        encoding="utf-8",
    )
    write_json(
        mounted_skills / "approved-skills.json",
        {
            "schema_version": "cim-approved-skills.v1",
            "agent_id": agent_id,
            "capability": capability["id"],
            "skills": skill_mounts,
        },
    )

    effective = {
        "schema_version": "fab-agent-effective.v1",
        "resolved_at_utc": utc_now(),
        "agent_id": agent_id,
        "display_name": agent.get("display_name") or agent_id,
        "user_defined_background": True,
        "background": background,
        "tone": agent.get("tone", ""),
        "domain_context": agent.get("domain_context", []),
        "output_style": agent.get("output_style", ""),
        "capability": capability["id"],
        "capability_display_name": capability.get("display_name", capability["id"]),
        "policy_source": "CIM",
        "capability_source_path": capability.get("_source_path", ""),
        "effective_allowed_skills": capability.get("allowed_skills", []),
        "effective_skill_mounts": skill_mounts,
        "effective_allowed_mcp_groups": capability.get("allowed_mcp_groups", []),
        "effective_tool_policy": capability.get("tool_policy", "none"),
        "allowed_actions": capability.get("allowed_actions", []),
        "blocked_actions": capability.get("blocked_actions", []),
        "allowed_output_globs": capability.get("allowed_output_globs", []),
        "blocked_user_fields": validation.get("blocked_user_fields", []),
        "validation_warnings": validation.get("warnings", []),
    }

    claude_settings = {
        "permissions": {
            "defaultMode": "deny",
            "allow": capability.get("allowed_actions", []),
            "deny": capability.get("blocked_actions", []),
        },
        "hooks": {
            "PreToolUse": ["cim-policy-audit"],
            "PostToolUse": ["artifact-audit"],
        },
    }
    mcp_config = {
        "mcpServers": {},
        "cim_mcp_groups": capability.get("allowed_mcp_groups", []),
        "note": "POC config exposes capability groups, not raw Fab-user-defined MCP servers.",
    }

    write_json(agent_out / "effective-agent.json", effective)
    write_json(agent_out / "claude-settings.json", claude_settings)
    write_json(agent_out / "mcp-config.json", mcp_config)
    (agent_out / "audit.log").write_text("", encoding="utf-8")
    return {
        "passed": True,
        "agent_dir": str(agent_dir),
        "output_dir": str(agent_out),
        "effective_policy_path": str(agent_out / "effective-agent.json"),
        "claude_settings_path": str(agent_out / "claude-settings.json"),
        "mcp_config_path": str(agent_out / "mcp-config.json"),
        "approved_skills_path": str(mounted_skills / "approved-skills.json"),
        "audit_log_path": str(agent_out / "audit.log"),
        "effective": effective,
        "validation": validation,
    }


def action_allowed(effective: dict[str, Any], action: str, path: str = "") -> tuple[bool, str]:
    if action not in set(effective.get("allowed_actions", [])):
        return False, f"action {action} is not allowed by capability {effective.get('capability')}"
    if action in {"write_project_file", "edit_project_file"} and path:
        allowed_globs = [str(item) for item in effective.get("allowed_output_globs", [])]
        if not any(fnmatch.fnmatch(path.replace("\\", "/"), pattern) for pattern in allowed_globs):
            return False, f"path {path} is outside allowed output globs"
    return True, "allowed"


def audit_action(agent_runtime_dir: Path, effective: dict[str, Any], action: str, path: str = "", detail: str = "") -> dict[str, Any]:
    allowed, reason = action_allowed(effective, action, path)
    entry = {
        "timestamp": utc_now(),
        "agent_id": effective.get("agent_id"),
        "capability": effective.get("capability"),
        "action": action,
        "path": path,
        "allowed": allowed,
        "blocked": not allowed,
        "reason": reason,
        "detail": detail,
    }
    log_path = agent_runtime_dir / "audit.log"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def load_audit_entries(agent_runtime_dir: Path) -> list[dict[str, Any]]:
    log_path = agent_runtime_dir / "audit.log"
    if not log_path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"malformed": line})
    return entries
