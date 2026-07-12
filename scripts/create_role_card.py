#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from role_card_policy import FAB_AGENT_ROOT, load_roles, slugify_name, write_role_card


def choose_role_interactively(roles: dict[str, dict]) -> str:
    print("Choose role:")
    ordered = list(roles.values())
    for idx, role in enumerate(ordered, start=1):
        print(f"  {idx}. {role.get('display_name', role['id'])} ({role['id']})")
    selected = input("Role: ").strip()
    if selected.isdigit() and 1 <= int(selected) <= len(ordered):
        return str(ordered[int(selected) - 1]["id"])
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a simple Fab Role Card.")
    parser.add_argument("--name", default="")
    parser.add_argument("--role", default="")
    parser.add_argument("--background", default="")
    parser.add_argument("--style", default="")
    parser.add_argument("--out", default="", help="Output Role Card path. Defaults to fab_agents/<name>/role-card.yaml")
    args = parser.parse_args()

    roles = load_roles()
    name = args.name.strip() or input("Agent name: ").strip()
    role = args.role.strip() or choose_role_interactively(roles)
    if role not in roles:
        print(json.dumps({"passed": False, "error": f"unknown role: {role}", "available_roles": sorted(roles)}, ensure_ascii=False, indent=2))
        return 2
    style = args.style.strip() or str(roles[role].get("default_style", "concise"))
    background = args.background.strip()
    if not background:
        print("Background:")
        background = input().strip()
    target = Path(args.out) if args.out else FAB_AGENT_ROOT / slugify_name(name) / "role-card.yaml"
    write_role_card(target, name=name, role=role, background=background, style=style)
    print(json.dumps({"passed": True, "role_card": str(target), "name": name, "role": role, "style": style}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
