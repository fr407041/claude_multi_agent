#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from fab_agent_policy import FAB_AGENT_ROOT, FORBIDDEN_FAB_AGENT_FIELDS, ROOT, load_capabilities, resolve_fab_agent, validate_fab_agent, write_json
except ModuleNotFoundError:  # pragma: no cover - used when imported as scripts.role_card_policy
    from .fab_agent_policy import FAB_AGENT_ROOT, FORBIDDEN_FAB_AGENT_FIELDS, ROOT, load_capabilities, resolve_fab_agent, validate_fab_agent, write_json


ROLE_ROOT = ROOT / "configs" / "cim_roles"
ROLE_CARD_FORBIDDEN_FIELDS = FORBIDDEN_FAB_AGENT_FIELDS | {
    "capability",
    "allowed_actions",
    "allowed_output_globs",
    "allowed_mcp_groups",
    "mcp_groups",
}
VALID_STYLES = {"concise", "detailed", "strict", "friendly"}


def slugify_name(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_").lower()
    return slug or "fab_agent"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_roles(root: Path = ROLE_ROOT) -> dict[str, dict[str, Any]]:
    roles: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        role = read_json(path)
        role_id = str(role.get("id") or path.stem)
        role["id"] = role_id
        role["_source_path"] = str(path)
        roles[role_id] = role
    return roles


def parse_role_card(path: Path) -> dict[str, Any]:
    """Parse the intentionally tiny Role Card YAML subset.

    Supported syntax:
      key: value
      background: |
        multiline text

    This avoids adding a YAML dependency for the common path.
    """
    data: dict[str, Any] = {}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    idx = 0
    while idx < len(lines):
        raw = lines[idx]
        idx += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if ":" not in raw:
            raise ValueError(f"invalid Role Card line: {raw}")
        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "|":
            block: list[str] = []
            while idx < len(lines):
                candidate = lines[idx]
                if candidate and not candidate.startswith((" ", "\t")):
                    break
                block.append(candidate[2:] if candidate.startswith("  ") else candidate.lstrip("\t"))
                idx += 1
            data[key] = "\n".join(block).rstrip() + "\n"
        else:
            data[key] = value.strip("\"'")
    return data


def write_role_card(path: Path, *, name: str, role: str, background: str, style: str = "concise") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized_background = background.strip() or "Describe this agent's background and working style."
    path.write_text(
        "\n".join(
            [
                f"name: {name}",
                f"role: {role}",
                f"style: {style}",
                "background: |",
                *[f"  {line}" for line in normalized_background.splitlines()],
                "",
            ]
        ),
        encoding="utf-8",
    )


def validate_role_card(path: Path, roles: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    roles = roles or load_roles()
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    try:
        card = parse_role_card(path)
    except Exception as exc:
        return {
            "passed": False,
            "role_card": str(path),
            "errors": [{"code": "ROLE_CARD_PARSE_ERROR", "detail": str(exc)}],
            "warnings": [],
        }

    illegal = sorted(field for field in card if field in ROLE_CARD_FORBIDDEN_FIELDS)
    for field in illegal:
        errors.append(
            {
                "code": "ROLE_CARD_POLICY_VIOLATION",
                "detail": f"Role Card cannot define {field}; skills, MCP, hooks, tools, and capabilities are managed by CIM role presets.",
            }
        )

    name = str(card.get("name") or "").strip()
    role_id = str(card.get("role") or "").strip()
    style = str(card.get("style") or "concise").strip()
    background = str(card.get("background") or "").strip()

    if not name:
        errors.append({"code": "ROLE_CARD_MISSING_NAME", "detail": "Role Card must include name."})
    if role_id not in roles:
        errors.append(
            {
                "code": "UNKNOWN_CIM_ROLE",
                "detail": f"Unknown role: {role_id or '<missing>'}. Available roles: {', '.join(sorted(roles))}",
            }
        )
    if style and style not in VALID_STYLES:
        warnings.append({"code": "UNKNOWN_STYLE", "detail": f"Unknown style '{style}'. Common styles: {', '.join(sorted(VALID_STYLES))}"})
    if not background:
        errors.append({"code": "ROLE_CARD_MISSING_BACKGROUND", "detail": "Role Card must include background."})

    return {
        "passed": not errors,
        "role_card": str(path),
        "name": name,
        "agent_id": slugify_name(name),
        "role": role_id,
        "style": style or roles.get(role_id, {}).get("default_style", "concise"),
        "background": background,
        "blocked_user_fields": illegal,
        "errors": errors,
        "warnings": warnings,
    }


def materialize_role_card_agent(role_card_path: Path, agent_root: Path = FAB_AGENT_ROOT) -> dict[str, Any]:
    roles = load_roles()
    validation = validate_role_card(role_card_path, roles)
    if not validation["passed"]:
        return {"passed": False, "validation": validation}
    role = roles[validation["role"]]
    agent_id = validation["agent_id"]
    agent_dir = agent_root / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        agent_dir / "agent.json",
        {
            "id": agent_id,
            "display_name": validation["name"],
            "capability": role["capability"],
            "background_file": "background.md",
            "tone": validation["style"],
            "domain_context": [],
            "output_style": validation["style"],
            "role": validation["role"],
            "role_card_file": str(role_card_path),
        },
    )
    (agent_dir / "background.md").write_text(validation["background"].rstrip() + "\n", encoding="utf-8")
    agent_validation = validate_fab_agent(agent_dir, load_capabilities())
    return {
        "passed": agent_validation["passed"],
        "agent_id": agent_id,
        "agent_dir": str(agent_dir),
        "role": validation["role"],
        "capability": role["capability"],
        "role_card_validation": validation,
        "agent_validation": agent_validation,
    }


def resolve_role_card(role_card_path: Path, output_dir: Path, agent_root: Path = FAB_AGENT_ROOT) -> dict[str, Any]:
    materialized = materialize_role_card_agent(role_card_path, agent_root=agent_root)
    if not materialized["passed"]:
        return {"passed": False, "materialized": materialized}
    resolved = resolve_fab_agent(Path(materialized["agent_dir"]), output_dir)
    if resolved.get("passed"):
        resolved["effective"]["role"] = materialized["role"]
        resolved["effective"]["role_display_name"] = load_roles()[materialized["role"]].get("display_name", materialized["role"])
        write_json(Path(resolved["effective_policy_path"]), resolved["effective"])
    return {
        "passed": bool(resolved.get("passed")),
        "materialized": materialized,
        "resolved": resolved,
    }
