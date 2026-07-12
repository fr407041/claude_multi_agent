#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SHOPPING_SITE_REQUIRED_FILES = [
    "shopping-site/index.html",
    "shopping-site/styles.css",
    "shopping-site/app.js",
    "shopping-site/README.md",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def file_check(root: Path, rel: str) -> dict[str, Any]:
    path = root / rel
    return {
        "label": f"{rel} exists",
        "status": "pass" if path.is_file() and path.stat().st_size > 0 else "fail",
        "path": str(path),
        "detail": f"{path.stat().st_size} bytes" if path.is_file() else "missing file",
    }


def text_has_any(text: str, patterns: list[str]) -> bool:
    lowered = text.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


def script_has_cart_behavior(script: str) -> dict[str, bool]:
    lowered = script.lower()
    return {
        "add_to_cart": bool(re.search(r"add(?:to)?cart|add-to-cart|cart\.push|cartitems", lowered)),
        "cart_count": bool(re.search(r"cart[-_ ]?count|cartcount|itemcount|quantity", lowered)),
        "total_update": bool(re.search(r"total|subtotal|reduce|sum", lowered)),
        "checkout_stub": bool("checkout" in lowered and text_has_any(lowered, ["demo only", "no real payment", "stub", "no real checkout", "no payment"])),
    }


def verify_shopping_site(root: Path) -> dict[str, Any]:
    checks = [file_check(root, rel) for rel in SHOPPING_SITE_REQUIRED_FILES]
    index = read_text(root / "shopping-site/index.html")
    styles = read_text(root / "shopping-site/styles.css")
    script = read_text(root / "shopping-site/app.js")
    readme = read_text(root / "shopping-site/README.md")
    combined = "\n".join([index, styles, script, readme])
    behavior = script_has_cart_behavior(script)
    product_markers = len(re.findall(r"product|card|item|price|add", combined, flags=re.IGNORECASE))
    semantic_checks = [
        {
            "label": "Product browsing UI is present",
            "status": "pass" if product_markers >= 6 and text_has_any(index, ["product", "shop", "store", "cart"]) else "fail",
            "detail": f"product-related markers={product_markers}",
        },
        {
            "label": "Stylesheet is connected",
            "status": "pass" if "styles.css" in index and len(styles.strip()) >= 80 else "fail",
            "detail": "index links styles.css and stylesheet has content",
        },
        {
            "label": "JavaScript app is connected",
            "status": "pass" if "app.js" in index and len(script.strip()) >= 120 else "fail",
            "detail": "index links app.js and script has content",
        },
        {
            "label": "Add-to-cart behavior exists",
            "status": "pass" if behavior["add_to_cart"] else "fail",
            "detail": "script includes add-to-cart flow",
        },
        {
            "label": "Cart count updates are implemented",
            "status": "pass" if behavior["cart_count"] else "fail",
            "detail": "script includes cart count or quantity logic",
        },
        {
            "label": "Cart total updates are implemented",
            "status": "pass" if behavior["total_update"] else "fail",
            "detail": "script includes total/subtotal calculation logic",
        },
        {
            "label": "Checkout is clearly a stub",
            "status": "pass" if behavior["checkout_stub"] else "fail",
            "detail": "demo must not imply real payment processing",
        },
        {
            "label": "README explains how to review outputs",
            "status": "pass" if text_has_any(readme, ["open", "index.html", "static", "demo"]) else "fail",
            "detail": "README should tell a user how to inspect the generated package",
        },
    ]
    all_checks = checks + semantic_checks
    failed = [item for item in all_checks if item["status"] != "pass"]
    return {
        "schema_version": "generated-output-package.v1",
        "profile": "shopping-site",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "expected_outputs": SHOPPING_SITE_REQUIRED_FILES,
        "all_passed": not failed,
        "score": round((len(all_checks) - len(failed)) / len(all_checks), 3) if all_checks else 0.0,
        "checks": all_checks,
        "failure_category": "" if not failed else "ARTIFACT_NOT_CREATED_BY_MODEL" if any(item["label"].endswith("exists") for item in failed) else "ARTIFACT_CONTRACT_FAILED",
        "failed_checks": [item["label"] for item in failed],
        "metrics": {
            "file_count": sum(1 for rel in SHOPPING_SITE_REQUIRED_FILES if (root / rel).is_file()),
            "product_markers": product_markers,
            **behavior,
        },
        "user_summary": "Generated output package is ready for review." if not failed else "Generated output package is incomplete or does not meet the common demo contract.",
        "limitations": [
            "This verifier checks static files and observable interaction code; it does not run a browser or process real payments.",
            "The shopping-site profile is a common generation demo, not a dashboard-specific assumption.",
        ],
    }


def verify_package(root: Path, profile: str) -> dict[str, Any]:
    if profile == "shopping-site":
        return verify_shopping_site(root)
    raise ValueError(f"unsupported profile: {profile}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify generated output packages for common live demos.")
    parser.add_argument("root", help="Run worktree/root that contains generated outputs.")
    parser.add_argument("--profile", default="shopping-site", choices=["shopping-site"])
    parser.add_argument("--json", action="store_true", default=True)
    args = parser.parse_args(argv)
    report = verify_package(Path(args.root), args.profile)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
