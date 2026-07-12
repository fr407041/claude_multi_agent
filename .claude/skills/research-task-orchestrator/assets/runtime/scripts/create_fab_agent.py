#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fab_agent_policy import FAB_AGENT_ROOT, load_capabilities, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Fab user-defined agent skeleton.")
    parser.add_argument("agent_id")
    parser.add_argument("--capability", required=True)
    parser.add_argument("--display-name", default="")
    args = parser.parse_args()
    capabilities = load_capabilities()
    if args.capability not in capabilities:
        print(json.dumps({"passed": False, "error": f"unknown capability: {args.capability}"}, ensure_ascii=False, indent=2))
        return 2
    agent_dir = FAB_AGENT_ROOT / args.agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        agent_dir / "agent.json",
        {
            "id": args.agent_id,
            "display_name": args.display_name or args.agent_id.replace("_", " ").title(),
            "capability": args.capability,
            "background_file": "background.md",
            "tone": "domain expert",
            "domain_context": [],
            "output_style": "concise memo",
        },
    )
    (agent_dir / "background.md").write_text(
        "Describe this Fab agent's background, domain expertise, and working style here.\n",
        encoding="utf-8",
    )
    print(json.dumps({"passed": True, "agent_dir": str(agent_dir)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
