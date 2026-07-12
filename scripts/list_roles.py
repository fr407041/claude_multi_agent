#!/usr/bin/env python3
from __future__ import annotations

import json

from role_card_policy import load_roles


def main() -> int:
    roles = load_roles()
    print(
        json.dumps(
            {
                "passed": True,
                "roles": [
                    {
                        "id": role["id"],
                        "display_name": role.get("display_name", role["id"]),
                        "summary": role.get("user_summary", ""),
                        "can": role.get("can", []),
                        "cannot": role.get("cannot", []),
                    }
                    for role in roles.values()
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
