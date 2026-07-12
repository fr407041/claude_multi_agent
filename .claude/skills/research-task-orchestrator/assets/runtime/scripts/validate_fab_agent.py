#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fab_agent_policy import validate_fab_agent


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Fab user-defined agent against CIM capability policy.")
    parser.add_argument("agent_dir")
    args = parser.parse_args()
    report = validate_fab_agent(Path(args.agent_dir))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
