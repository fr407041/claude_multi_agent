#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fab_agent_policy import resolve_fab_agent


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a Fab agent into CIM-managed effective runtime policy.")
    parser.add_argument("agent_dir")
    parser.add_argument("--out", required=True, help="Output directory for resolved runtime files.")
    args = parser.parse_args()
    report = resolve_fab_agent(Path(args.agent_dir), Path(args.out))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
