#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


FAILURE_CATEGORY = "TASK_OUTPUT_CONTRACT_FAILED"
NO_THINK_MARKER = "Unknown command: /no_think"


def _extract_json_object(text: str) -> Any | None:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\{\[]", text):
        try:
            value, _ = decoder.raw_decode(text[match.start() :])
        except json.JSONDecodeError:
            continue
        return value
    return None


def _expected_json_from_task(task_text: str) -> Any | None:
    env_value = os.getenv("EXPECTED_RESULT_JSON", "").strip()
    if env_value:
        return json.loads(env_value)

    patterns = [
        r"(?:reply|respond|output|return)\s+(?:with\s+)?(?:exactly\s+)?(?:this\s+)?(?:json|JSON)\s*[:：]?\s*(\{.*?\})",
        r"(?:exact|exactly)\s+(?:json|JSON)\s*[:：]?\s*(\{.*?\})",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, task_text, flags=re.IGNORECASE | re.DOTALL):
            candidate = match.group(1).strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return None


def _expected_exact_text_from_task(task_text: str) -> str:
    env_value = os.getenv("EXPECTED_RESULT_CONTAINS", "").strip()
    if env_value:
        return env_value

    patterns = [
        r"Reply with exactly this nonce in the final answer:\s*([A-Za-z0-9_.:\-]+)",
        r"Reply with exactly:\s*([^\r\n]+)",
        r"reply exactly:\s*([^\r\n]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, task_text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().strip("`")
    return ""


def verify_task_contract(task_text: str, response_text: str) -> dict[str, Any]:
    failures: list[str] = []
    expected_json = _expected_json_from_task(task_text)
    expected_text = _expected_exact_text_from_task(task_text)
    actual_json = _extract_json_object(response_text) if expected_json is not None else None

    if NO_THINK_MARKER in response_text:
        failures.append("model output contains unsupported /no_think command error")

    if expected_json is not None:
        if actual_json != expected_json:
            failures.append("response JSON does not match the requested exact JSON")

    if expected_text and expected_text not in response_text:
        failures.append("response text does not contain the requested exact text")

    contract_required = expected_json is not None or bool(expected_text)
    passed = not failures
    if not contract_required and not response_text.strip():
        failures.append("response text is empty")
        passed = False

    return {
        "passed": passed,
        "task_contract_status": "pass" if passed else "fail",
        "failure_category": "" if passed else FAILURE_CATEGORY,
        "contract_required": contract_required,
        "expected_json": expected_json,
        "expected_text": expected_text,
        "actual_json": actual_json,
        "response_length": len(response_text),
        "failed_checks": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify that a live task response satisfies the submitted task contract.")
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--response-file", required=True)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    task_text = Path(args.task_file).read_text(encoding="utf-8", errors="replace")
    response_text = Path(args.response_file).read_text(encoding="utf-8", errors="replace")
    report = verify_task_contract(task_text, response_text)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
