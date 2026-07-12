#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_GATES = {"A", "B", "C", "D", "E", "F"}
PTT_STOCK_RE = re.compile(r"^https://www\.ptt\.cc/bbs/Stock/.+\.html$")
VALID_STANCES = {"bullish", "bearish", "mixed", "neutral", "insufficient_evidence"}
VALID_CONFIDENCE = {"low", "medium", "high"}


def to_array(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def read_json_file(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_url_list(payload: Any) -> list[str]:
    if isinstance(payload, list):
        return [str(item) for item in payload if item]
    if isinstance(payload, dict):
        if "urls" in payload:
            return [str(item) for item in to_array(payload.get("urls")) if item]
        if "articles" in payload:
            urls = []
            for item in to_array(payload.get("articles")):
                if isinstance(item, str):
                    urls.append(item)
                elif isinstance(item, dict) and item.get("url"):
                    urls.append(str(item["url"]))
            return urls
    return []


def unique(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def verify_gate(gate: str, run_dir: Path) -> dict[str, Any]:
    gate = gate.upper()
    if gate not in VALID_GATES:
        raise ValueError(f"unsupported gate: {gate}")

    artifact_dir = run_dir / "ptt-stock-live"
    reasons: list[str] = []
    details: dict[str, Any] = {
        "artifact_dir": str(artifact_dir),
        "artifact_dir_exists": artifact_dir.exists(),
    }

    if not run_dir.exists():
        reasons.append("run dir missing")
        return result(False, gate, run_dir, reasons, details)
    if not artifact_dir.exists():
        reasons.append("ptt-stock-live artifact dir missing")

    if gate == "A":
        proof = artifact_dir / "proof.txt"
        details["proof_path"] = str(proof)
        if not proof.is_file():
            reasons.append("proof.txt missing")
        else:
            content = proof.read_text(encoding="utf-8", errors="ignore").strip()
            details["proof_content"] = content
            if content != "TOOL_EXECUTED_OK":
                reasons.append("proof.txt content mismatch")

    elif gate == "B":
        index = artifact_dir / "index.html"
        details["index_path"] = str(index)
        if not index.is_file():
            reasons.append("index.html missing")
        else:
            html = index.read_text(encoding="utf-8", errors="ignore")
            byte_count = index.stat().st_size
            contains_marker = bool(re.search(r"/bbs/Stock/|r-ent|Stock", html))
            details["bytes"] = byte_count
            details["contains_stock_board_marker"] = contains_marker
            if byte_count < 500:
                reasons.append("index.html too small")
            if not contains_marker:
                reasons.append("index.html lacks PTT Stock markers")

    elif gate == "C":
        urls_file = artifact_dir / "urls.json"
        details["urls_path"] = str(urls_file)
        try:
            urls = [item for item in get_url_list(read_json_file(urls_file)) if item]
            unique_urls = unique(urls)
            valid_urls = [item for item in unique_urls if PTT_STOCK_RE.match(item)]
            details["url_count"] = len(urls)
            details["unique_url_count"] = len(unique_urls)
            details["valid_ptt_stock_url_count"] = len(valid_urls)
            if len(unique_urls) != 5:
                reasons.append("expected exactly 5 unique URLs")
            if len(valid_urls) != 5:
                reasons.append("not all URLs are valid PTT Stock article URLs")
        except Exception as exc:
            reasons.append(f"urls.json parse/check failed: {exc}")

    elif gate == "D":
        article_file = artifact_dir / "article.json"
        details["article_path"] = str(article_file)
        try:
            article = read_json_file(article_file)
            title = str(article.get("title") or "") if isinstance(article, dict) else ""
            url = str(article.get("url") or "") if isinstance(article, dict) else ""
            body = str(article.get("body") or "") if isinstance(article, dict) else ""
            details["title_length"] = len(title)
            details["body_length"] = len(body)
            details["url"] = url
            if not title.strip():
                reasons.append("article title missing")
            if not PTT_STOCK_RE.match(url):
                reasons.append("article URL invalid")
            if not body.strip() or len(body) < 100:
                reasons.append("article body missing or too short")
        except Exception as exc:
            reasons.append(f"article.json parse/check failed: {exc}")

    elif gate in {"E", "F"}:
        expected_count = 3 if gate == "E" else 20
        final_file = artifact_dir / "final.json"
        details["final_path"] = str(final_file)
        details["expected_article_count"] = expected_count
        try:
            final = read_json_file(final_file)
            if not isinstance(final, dict):
                raise ValueError("final.json root must be an object")
            articles = to_array(final.get("articles"))
            stocks = to_array(final.get("stocks"))
            urls = [str(item.get("url")) for item in articles if isinstance(item, dict) and item.get("url")]
            unique_urls = unique(urls)
            valid_urls = [item for item in unique_urls if PTT_STOCK_RE.match(item)]
            details["article_count_field"] = final.get("article_count")
            details["article_array_count"] = len(articles)
            details["unique_url_count"] = len(unique_urls)
            details["valid_url_count"] = len(valid_urls)
            details["stock_count"] = len(stocks)
            if int(final.get("article_count") or -1) != expected_count:
                reasons.append(f"article_count field is not {expected_count}")
            if len(articles) != expected_count:
                reasons.append(f"articles array count is not {expected_count}")
            if len(unique_urls) != expected_count:
                reasons.append(f"article URLs are not exactly {expected_count} unique URLs")
            if len(valid_urls) != expected_count:
                reasons.append("not all article URLs are valid PTT Stock URLs")
            if len(stocks) < 1:
                reasons.append("stocks array is empty")
            for stock in stocks:
                if not isinstance(stock, dict):
                    reasons.append("stock item is not an object")
                    continue
                name = str(stock.get("ticker_or_name") or "")
                if not name.strip():
                    reasons.append("stock ticker_or_name missing")
                if str(stock.get("stance") or "") not in VALID_STANCES:
                    reasons.append(f"invalid stance for stock: {name}")
                if str(stock.get("confidence") or "") not in VALID_CONFIDENCE:
                    reasons.append(f"invalid confidence for stock: {name}")
                for field in ["bullish_evidence", "bearish_evidence", "neutral_evidence", "article_urls"]:
                    if field not in stock:
                        reasons.append(f"missing {field} for stock: {name}")
                if len([item for item in to_array(stock.get("article_urls")) if item]) < 1:
                    reasons.append(f"empty article_urls for stock: {name}")
        except Exception as exc:
            reasons.append(f"final.json parse/check failed: {exc}")

    return result(len(reasons) == 0, gate, run_dir, reasons, details)


def result(pass_value: bool, gate: str, run_dir: Path, reasons: list[str], details: dict[str, Any]) -> dict[str, Any]:
    return {
        "pass": bool(pass_value),
        "gate": gate,
        "run_dir": str(run_dir),
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "fail_reasons": reasons,
        "details": details,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify dedicated live agent micro-gate artifacts.")
    parser.add_argument("--gate", required=True, choices=sorted(VALID_GATES))
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--json", action="store_true", default=True)
    args = parser.parse_args(argv)

    report = verify_gate(args.gate, Path(args.run_dir))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
