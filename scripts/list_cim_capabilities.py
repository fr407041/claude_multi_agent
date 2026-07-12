#!/usr/bin/env python3
from __future__ import annotations

import json
from fab_agent_policy import load_capabilities


def main() -> int:
    rows = []
    for capability in load_capabilities().values():
        rows.append(
            {
                "id": capability["id"],
                "display_name": capability.get("display_name", capability["id"]),
                "tool_policy": capability.get("tool_policy", ""),
                "mcp_groups": capability.get("allowed_mcp_groups", []),
                "skills": capability.get("allowed_skills", []),
            }
        )
    print(json.dumps({"capabilities": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
