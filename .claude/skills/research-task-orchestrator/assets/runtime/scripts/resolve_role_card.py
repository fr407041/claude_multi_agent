#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from role_card_policy import resolve_role_card


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a Role Card into CIM-managed effective runtime policy.")
    parser.add_argument("role_card")
    parser.add_argument("--out", required=True)
    parser.add_argument("--agent-root", default="", help="Directory for materialized Fab agent config. Defaults to fab_agents/.")
    args = parser.parse_args()
    kwargs = {"agent_root": Path(args.agent_root)} if args.agent_root else {}
    report = resolve_role_card(Path(args.role_card), Path(args.out), **kwargs)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
