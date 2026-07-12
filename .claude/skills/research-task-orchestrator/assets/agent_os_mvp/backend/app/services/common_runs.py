from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Connection
from typing import Any

from app.services.ai_company_monitor import collect_ai_company_monitor, get_ai_company_run_detail, get_project_root, get_results_root


USER_STATUSES = {"Working", "Completed", "Needs attention", "Failed"}

MICRO_GATE_CAPABILITIES = {
    "A": "tool execution",
    "B": "external connectivity",
    "C": "structured URL extraction",
    "D": "single artifact creation",
    "E": "small-scope analysis",
    "F": "full-scope analysis",
}

MICRO_GATE_EXPECTED_ARTIFACTS = {
    "A": "ptt-stock-live/proof.txt",
    "B": "ptt-stock-live/index.html",
    "C": "ptt-stock-live/urls.json",
    "D": "ptt-stock-live/article.json",
    "E": "ptt-stock-live/final.json",
    "F": "ptt-stock-live/final.json",
}

ARTIFACT_NOT_CREATED_CATEGORIES = {"ARTIFACT_NOT_CREATED_BY_MODEL", "ARTIFACT_NOT_ATTEMPTED"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    errors: list[str] = []
    for encoding in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            return json.loads(path.read_text(encoding=encoding)), None
        except Exception as exc:  # pragma: no cover - exact parser messages vary by Python version
            errors.append(f"{encoding}: {exc}")
    return None, "; ".join(errors)


def _path_info(path: str | Path | None, label: str) -> dict[str, Any] | None:
    if not path:
        return None
    original = str(path)
    candidate = _normalize_artifact_path(original)
    exists = candidate.exists()
    kind = "directory" if exists and candidate.is_dir() else "file"
    info = {
        "label": label,
        "path": str(candidate),
        "exists": exists,
        "kind": kind,
        "type": _artifact_type(candidate, kind),
        "size_bytes": candidate.stat().st_size if exists and candidate.is_file() else None,
        "modified_at": datetime.fromtimestamp(candidate.stat().st_mtime, tz=timezone.utc).isoformat() if exists else None,
    }
    if original != str(candidate):
        info["original_path"] = original
    return info


def _normalize_artifact_path(path: str | Path) -> Path:
    candidate = Path(str(path))
    if candidate.exists():
        return candidate

    text = str(path).replace("\\", "/")
    mappings = [
        ("/agent-test-runs/", _micro_gates_root()),
        ("agent-test-runs/", _micro_gates_root()),
        ("/results/ai_company_task_harness/", get_results_root()),
        ("results/ai_company_task_harness/", get_results_root()),
    ]
    for marker, root in mappings:
        if marker in text:
            tail = text.split(marker, 1)[1].lstrip("/")
            mapped = root / tail
            if mapped.exists() or not candidate.is_absolute():
                return mapped
    return candidate


def _artifact_type(path: Path, kind: str = "file") -> str:
    if kind == "directory":
        return "folder"
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt", ".log"}:
        return "text"
    if suffix == ".json":
        return "json"
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix in {".css"}:
        return "stylesheet"
    if suffix in {".js", ".ts", ".tsx", ".jsx", ".py", ".sh", ".ps1"}:
        return "code"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        return "image"
    if suffix == ".pdf":
        return "pdf"
    return "file"


def _preview_text(path: Path, limit: int = 1200) -> str:
    if not path.exists() or not path.is_file():
        return ""
    if _artifact_type(path) not in {"text", "json", "html", "stylesheet", "code"}:
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return text[:limit] + ("..." if len(text) > limit else "")


def _micro_gates_root() -> Path:
    configured = os.getenv("MICRO_GATES_RUNS_ROOT", "").strip()
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_absolute() else get_project_root() / path
    return get_project_root() / "agent-test-runs"


def _user_status_from_micro_summary(summary: dict[str, Any]) -> str:
    if summary.get("pass") is True:
        return "Completed"
    if summary.get("failed_gate") or summary.get("pass") is False:
        return "Needs attention"
    return "Working"


def _micro_gate_status(gate: dict[str, Any]) -> str:
    if gate.get("verifier_pass") is True and str(gate.get("api_status", "")).lower() == "succeeded":
        return "Completed"
    if gate.get("verifier_pass") is False or gate.get("verifier_exit_code") not in (None, 0) or str(gate.get("api_status", "")).lower() in {"failed", "timeout", "interrupted"}:
        return "Needs attention"
    return "Working"


def _micro_gate_failure_reason(gate: dict[str, Any]) -> str:
    failure_category = str(gate.get("failure_category") or "")
    if failure_category in ARTIFACT_NOT_CREATED_CATEGORIES:
        return "Agent did not create the expected file."
    if gate.get("verifier_pass") is False:
        return "Agent did not create output that matched the expected artifact contract."
    if str(gate.get("api_status", "")).lower() in {"failed", "timeout", "interrupted"}:
        return f"Agent run ended with API status {gate.get('api_status')}."
    if gate.get("return_code") not in (None, 0):
        return f"Agent process exited with code {gate.get('return_code')}."
    return ""


def _micro_gate_hint(gate: dict[str, Any]) -> str:
    status = _micro_gate_status(gate)
    if status == "Completed":
        return "No action needed for this gate."
    expected = MICRO_GATE_EXPECTED_ARTIFACTS.get(str(gate.get("gate", "")).upper(), "the expected artifact")
    failure_category = str(gate.get("failure_category") or "")
    if failure_category in ARTIFACT_NOT_CREATED_CATEGORIES:
        return f"Rerun only this small gate with a narrow instruction: create {expected}; do not accept prose-only output."
    return f"Rerun this small gate and verify that the agent writes {expected}."


def _micro_gate_run_dir(gate: dict[str, Any]) -> Path | None:
    value = gate.get("run_dir")
    if not value:
        return None
    return _normalize_artifact_path(str(value))


def _micro_gate_original_run_dir(gate: dict[str, Any]) -> str | None:
    value = gate.get("run_dir")
    return str(value) if value else None


def _micro_gate_expected_artifact_info(gate: dict[str, Any]) -> dict[str, Any] | None:
    gate_name = str(gate.get("gate") or "").upper()
    expected = MICRO_GATE_EXPECTED_ARTIFACTS.get(gate_name)
    run_dir = _micro_gate_run_dir(gate)
    if not expected or run_dir is None:
        return None
    candidates = [run_dir / expected, run_dir / "worktree" / expected]
    existing = next((item for item in candidates if item.exists()), candidates[0])
    info = _path_info(existing, "expected artifact")
    if info is None:
        return None
    info["expected_path"] = expected
    info["candidate_paths"] = [str(item) for item in candidates]
    original_run_dir = _micro_gate_original_run_dir(gate)
    if original_run_dir and original_run_dir != str(run_dir):
        info["original_candidate_paths"] = [str(Path(original_run_dir) / expected), str(Path(original_run_dir) / "worktree" / expected)]
    return info


def _build_micro_gate_details(summary: dict[str, Any]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for gate in summary.get("gates") or []:
        gate_name = str(gate.get("gate") or "").upper()
        actual = _micro_gate_expected_artifact_info(gate)
        run_directory = _path_info(gate.get("run_dir"), "run directory")
        verifier_result = _path_info(gate.get("verifier_result_path"), "verifier result")
        details.append(
            {
                "name": f"Gate {gate_name}" if gate_name else "Gate",
                "capability": MICRO_GATE_CAPABILITIES.get(gate_name, "validation capability"),
                "status": _micro_gate_status(gate),
                "expected_artifact": MICRO_GATE_EXPECTED_ARTIFACTS.get(gate_name, "expected artifact"),
                "actual_artifact": actual,
                "failure_reason": _micro_gate_failure_reason(gate),
                "user_hint": _micro_gate_hint(gate),
                "failure_category": gate.get("failure_category") or "",
                "run_id": gate.get("run_id"),
                "technical_paths": [
                    item
                    for item in [
                        actual,
                        run_directory,
                        verifier_result,
                    ]
                    if item
                ],
                "raw": gate,
            }
        )
    return details


def _micro_gate_progress(summary: dict[str, Any], details: list[dict[str, Any]]) -> dict[str, Any]:
    total = max(len(details), 1)
    completed = len([item for item in details if item["status"] == "Completed"])
    failed = next((item for item in details if item["status"] != "Completed"), None)
    if summary.get("pass") is True:
        return {
            "phase": "Deliver",
            "current_step": "Validation completed",
            "completed_steps": total,
            "total_steps": total,
            "percent": 100,
            "latest_activity": "All small gates passed.",
        }
    if failed:
        return {
            "phase": "Verify",
            "current_step": f"{failed['name']} needs attention",
            "completed_steps": completed,
            "total_steps": total,
            "percent": round((completed / total) * 100),
            "latest_activity": failed.get("failure_reason") or "Waiting for valid artifact.",
        }
    return {
        "phase": "Run",
        "current_step": "Validation is running",
        "completed_steps": completed,
        "total_steps": total,
        "percent": round((completed / total) * 100),
        "latest_activity": "Waiting for the next gate result.",
    }


def _common_micro_gate_run(summary_path: Path) -> dict[str, Any]:
    summary, error = _load_json(summary_path)
    run_id = summary_path.parent.name
    if summary is None:
        return {
            "run_id": run_id,
            "run_type": "micro_gate",
            "user_status": "Needs attention",
            "headline": "Validation run could not be read.",
            "explanation": "The dashboard found a validation run, but its summary file is malformed.",
            "started_at": None,
            "updated_at": _now(),
            "progress": {"phase": "Verify", "current_step": "Read run summary", "completed_steps": 0, "total_steps": 1, "percent": 0},
            "agents": [],
            "primary_result": {"summary": "No trusted result is available.", "deliverables": [], "output_paths": []},
            "verification": {"status": "fail", "checks": [], "limitations": [error or "Unknown parse error."]},
            "artifacts": [_path_info(summary_path, "run summary")],
            "next_action": {"label": "Review run files", "detail": "Open the technical details and fix or rerun the validation flow."},
            "technical_details": {"warnings": [error], "source_path": str(summary_path)},
        }

    details = _build_micro_gate_details(summary)
    user_status = _user_status_from_micro_summary(summary)
    failed_gate = summary.get("failed_gate")
    headline = "Validation completed and verified." if user_status == "Completed" else f"Validation failed at Gate {failed_gate}." if failed_gate else "Validation is still running."
    progress = _micro_gate_progress(summary, details)
    artifacts = [_path_info(summary_path, "run summary"), _path_info(summary.get("run_set_dir"), "validation run set")]
    for gate in details:
        artifacts.extend(gate["technical_paths"])
    artifacts = [item for item in artifacts if item]
    verification_checks = [
        {
            "label": f"{gate['name']}: {gate['capability']}",
            "status": "pass" if gate["status"] == "Completed" else "fail",
            "detail": gate.get("failure_reason") or "Verified.",
        }
        for gate in details
    ]
    return {
        "run_id": summary.get("run_set_id") or run_id,
        "run_type": "micro_gate",
        "user_status": user_status,
        "headline": headline,
        "explanation": progress.get("latest_activity") or headline,
        "started_at": summary.get("started_at_utc"),
        "updated_at": summary.get("finished_at_utc") or summary.get("started_at_utc"),
        "progress": progress,
        "agents": [
            {
                "id": "agent",
                "name": "Task agent",
                "status": "done" if user_status == "Completed" else "failed" if user_status in {"Failed", "Needs attention"} else "active",
                "current_activity": headline,
                "updated_at": summary.get("finished_at_utc") or summary.get("started_at_utc"),
            }
        ],
        "primary_result": {
            "summary": "All validation gates passed." if user_status == "Completed" else "The task is not ready because validation found a blocking artifact issue.",
            "deliverables": ["Validation report"] if user_status == "Completed" else [],
            "output_paths": [str(item["path"]) for item in artifacts if item and item.get("exists")],
        },
        "verification": {
            "status": "pass" if user_status == "Completed" else "fail",
            "checks": verification_checks,
            "limitations": [] if user_status == "Completed" else ["The dashboard is showing verifier output; it does not repair the task itself."],
        },
        "artifacts": artifacts,
        "next_action": {
            "label": "Review outputs" if user_status == "Completed" else "Repair and continue",
            "detail": "Use the verifier details to rerun only the failing small gate." if user_status != "Completed" else "Review the verified artifacts.",
        },
        "technical_details": {
            "source_path": str(summary_path),
            "validation_details": details,
            "raw_summary": summary,
        },
    }


def _ai_status_to_user_status(status: str | None) -> str:
    normalized = str(status or "").strip().lower()
    if normalized == "pass":
        return "Completed"
    if normalized == "fail":
        return "Failed"
    if normalized == "partial":
        return "Needs attention"
    return "Working"


def _ai_run_root(run_id: str | None) -> Path | None:
    if not run_id:
        return None
    candidate = get_results_root() / str(run_id)
    return candidate if candidate.exists() else None


def _append_artifact(artifacts: list[dict[str, Any]], path: Path, label: str, role: str = "output", preview: bool = False) -> None:
    info = _path_info(path, label)
    if not info:
        return
    info["role"] = role
    if preview:
        info["preview"] = _preview_text(path)
    artifacts.append(info)


def _artifact_checks_to_list(artifact_checks: Any) -> list[dict[str, Any]]:
    if isinstance(artifact_checks, dict):
        return [
            {"label": str(name), "status": "pass" if passed else "fail", "detail": "Verified." if passed else "Verification failed."}
            for name, passed in artifact_checks.items()
        ]
    if isinstance(artifact_checks, list):
        checks: list[dict[str, Any]] = []
        for item in artifact_checks:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "").lower()
            checks.append(
                {
                    "label": str(item.get("label") or "Verification check"),
                    "status": "pass" if status == "pass" else "fail" if status == "fail" else status or "pending",
                    "detail": str(item.get("detail") or ""),
                }
            )
        return checks
    return []


def _build_ai_output_package(run: dict[str, Any], artifact_checks: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    run_root = _ai_run_root(run.get("run_id"))
    if not run_root:
        return [], []

    artifacts: list[dict[str, Any]] = []
    output_paths: list[str] = []

    worktree = run_root / "worktree"
    _append_artifact(artifacts, worktree, "Output folder", "output")
    if worktree.exists():
        # Keep the receipt compact and useful: show the first real generated files,
        # not every internal evidence file.
        for path in sorted([item for item in worktree.rglob("*") if item.is_file()])[:24]:
            rel = path.relative_to(run_root)
            label = "Generated output"
            if path.name.lower() == "summary.md":
                label = "Final summary"
            elif path.suffix.lower() in {".html", ".htm"}:
                label = "HTML deliverable"
            elif path.suffix.lower() in {".md", ".txt"}:
                label = "Documentation"
            elif path.suffix.lower() in {".js", ".css", ".py", ".json"}:
                label = "Implementation file"
            _append_artifact(artifacts, path, label, "output", preview=path.suffix.lower() in {".md", ".txt", ".json"})
            output_paths.append(str(rel))

    ai_dir = run_root / "ai_company"
    for filename, label in [
        ("artifact_verify_report.json", "Verification report"),
        ("final_run_verdict.json", "Final verdict"),
        ("meeting_decision.json", "Meeting decision"),
        ("task_harness_report.json", "Harness report"),
    ]:
        _append_artifact(artifacts, ai_dir / filename, label, "evidence", preview=filename in {"final_run_verdict.json", "artifact_verify_report.json"})

    if artifact_checks and not any(item.get("role") == "output" and item.get("exists") for item in artifacts):
        _append_artifact(artifacts, run_root, "Run folder", "output")

    return artifacts, output_paths


def _common_ai_company_run(run: dict[str, Any]) -> dict[str, Any]:
    user_status = _ai_status_to_user_status(run.get("overall_status"))
    final_result = run.get("final_result") or {}
    summary = final_result.get("summary_excerpt") or final_result.get("summary_markdown") or run.get("decision_summary") or ""
    artifact_checks = final_result.get("artifact_checks") or {}
    artifacts, output_paths = _build_ai_output_package(run, artifact_checks)
    checks = _artifact_checks_to_list(artifact_checks)
    agents = []
    board = run.get("agent_state_board") or {}
    for state_name, mapped in [("running", "active"), ("waiting", "waiting"), ("done", "done"), ("failed", "failed")]:
        for item in board.get(state_name, []):
            agents.append(
                {
                    "id": item.get("task_id") or item.get("role") or "agent",
                    "name": item.get("role") or item.get("owner_role") or "Agent",
                    "status": mapped,
                    "current_activity": item.get("verification_note") or item.get("fallback_plan") or item.get("task_id") or mapped,
                    "updated_at": run.get("started_at"),
                }
            )
    has_terminal = user_status in {"Completed", "Failed", "Needs attention"}
    meeting = run.get("meeting") or {}
    is_live_discussion = bool(meeting.get("live_meeting_used") or run.get("live_meeting_used"))
    headline = "Live discussion completed and verified." if user_status == "Completed" and is_live_discussion else "Task completed and verified." if user_status == "Completed" else "Task stopped before a trusted result." if user_status == "Failed" else "Task needs attention." if user_status == "Needs attention" else "Task is running."
    meeting_details = None
    if meeting:
        meeting_details = {
            "summary": run.get("decision_summary") or meeting.get("summary") or "Meeting details recorded.",
            "task_assignments": meeting.get("task_assignments") or [],
            "discussion_log": meeting.get("discussion_log") or [],
            "collaboration_notes": [],
            "live_meeting_used": bool(meeting.get("live_meeting_used") or run.get("live_meeting_used")),
            "live_turn_count": meeting.get("live_turn_count") or run.get("live_turn_count"),
            "live_transport": meeting.get("live_transport") or run.get("live_transport"),
        }
    return {
        "run_id": run.get("run_id"),
        "run_type": "ai_company",
        "user_status": user_status,
        "headline": headline,
        "explanation": summary or run.get("goal") or "No final answer has been recorded yet.",
        "started_at": run.get("started_at"),
        "updated_at": run.get("started_at"),
        "progress": {
            "phase": "Deliver" if has_terminal else "Run",
            "current_step": "Result available" if has_terminal else "Waiting for agent progress",
            "completed_steps": 5 if has_terminal else 2,
            "total_steps": 5,
            "percent": 100 if has_terminal else 40,
            "latest_activity": summary or run.get("meeting_status") or "Waiting for update.",
        },
        "agents": agents[:12],
        "primary_result": {
            "summary": summary or "The run has not produced a final summary yet.",
            "deliverables": [item.get("path") for item in artifacts if item.get("role") == "output" and item.get("exists")][:8] or (["Final summary"] if summary else []),
            "output_paths": output_paths,
        },
        "verification": {
            "status": "pass" if user_status == "Completed" else "fail" if user_status in {"Failed", "Needs attention"} else "pending",
            "checks": checks,
            "limitations": final_result.get("limitations") or [],
        },
        "artifacts": artifacts,
        "next_action": {
            "label": "Review outputs" if user_status == "Completed" else "Retry" if user_status == "Failed" else "Repair and continue" if user_status == "Needs attention" else "View progress",
            "detail": "Inspect the generated output package, verification evidence, and paths before opening anything externally." if user_status == "Completed" else "Inspect verification and technical details before rerunning.",
        },
        "technical_details": {"meeting": meeting_details, "raw_run": run},
    }


def _direct_ai_company_run(run_dir: Path) -> dict[str, Any] | None:
    ai_dir = run_dir / "ai_company"
    report_path = ai_dir / "task_harness_report.json"
    if not report_path.is_file():
        return None
    report, _ = _load_json(report_path)
    if report is None:
        return None
    meeting, _ = _load_json(ai_dir / "meeting_decision.json") if (ai_dir / "meeting_decision.json").is_file() else ({}, None)
    final_verdict, _ = _load_json(ai_dir / "final_run_verdict.json") if (ai_dir / "final_run_verdict.json").is_file() else ({}, None)
    artifact_report, _ = _load_json(ai_dir / "artifact_verify_report.json") if (ai_dir / "artifact_verify_report.json").is_file() else ({}, None)
    execution, _ = _load_json(ai_dir / "execution_summary.json") if (ai_dir / "execution_summary.json").is_file() else ({}, None)
    reviewer, _ = _load_json(ai_dir / "reviewer_verdicts.json") if (ai_dir / "reviewer_verdicts.json").is_file() else ({}, None)
    status_records = []
    for status_path in sorted((run_dir / "results").glob("*.status.json")):
        item, _ = _load_json(status_path)
        if item:
            status_records.append(item)
    parsed_artifact = artifact_report.get("parsed", {}) if isinstance(artifact_report, dict) else {}
    summary_text = _preview_text(run_dir / "worktree" / "summary.md", limit=4000)
    kpis = report.get("kpis", {}) if isinstance(report.get("kpis"), dict) else {}
    overall_status = final_verdict.get("overall_status") or report.get("overall_status") or ("fail" if parsed_artifact.get("all_passed") is False else "unknown")
    agents = []
    for item in status_records:
        status = str(item.get("status") or "").upper()
        mapped = "done" if status == "SUCCESS" else "failed" if status in {"FAILED", "ROUTER_ERROR", "CHILD_TIMEOUT", "BLOCKED_BY_DEPENDENCY"} else "waiting"
        agents.append(
            {
                "task_id": item.get("id") or "agent",
                "role": item.get("owner_role") or "Agent",
                "status": mapped,
                "verification_note": item.get("verification_note") or status,
            }
        )
    board = {
        "running": [item for item in agents if item["status"] == "active"],
        "waiting": [item for item in agents if item["status"] == "waiting"],
        "done": [item for item in agents if item["status"] == "done"],
        "failed": [item for item in agents if item["status"] == "failed"],
    }
    return {
        "run_id": report.get("run_dir", run_dir.name).split("/")[-1].split("\\")[-1],
        "overall_status": overall_status,
        "started_at": report.get("kpis", {}).get("started_at") or datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc).isoformat(),
        "goal": kpis.get("goal", ""),
        "decision_summary": meeting.get("decision_summary", ""),
        "meeting": meeting,
        "live_meeting_used": bool(meeting.get("live_meeting_used")),
        "live_turn_count": meeting.get("live_turn_count", 0),
        "live_transport": meeting.get("live_transport", ""),
        "agent_state_board": board,
        "execution_log": execution.get("execution_log", []) if isinstance(execution, dict) else [],
        "review_verdicts": reviewer.get("verdicts", []) if isinstance(reviewer, dict) else [],
        "final_result": {
            "summary_markdown": summary_text,
            "summary_excerpt": summary_text[:420],
            "artifact_score": parsed_artifact.get("score"),
            "artifact_checks": parsed_artifact.get("checks", {}),
            "all_passed": parsed_artifact.get("all_passed"),
            "limitations": parsed_artifact.get("limitations", []),
            "final_run_verdict": final_verdict,
            "overall_status": overall_status,
        },
    }


def _collect_direct_ai_company_runs() -> list[dict[str, Any]]:
    root = get_results_root()
    if not root.exists():
        return []
    runs: list[dict[str, Any]] = []
    for run_dir in sorted(root.glob("run-*"), key=lambda path: path.stat().st_mtime, reverse=True)[:40]:
        item = _direct_ai_company_run(run_dir)
        if item:
            runs.append(_common_ai_company_run(item))
    return runs


def _goal_user_status(goal: dict[str, Any], tasks: list[dict[str, Any]], reviews: list[dict[str, Any]]) -> str:
    if not tasks:
        return "Working"
    if any(task.get("status") == "pending" for task in tasks):
        return "Working"
    if reviews and any(str(review.get("verdict", "")).lower() == "needs_followup" for review in reviews):
        return "Needs attention"
    return "Completed"


def _common_agent_task_run(connection: Connection, goal_row: Any) -> dict[str, Any]:
    goal = dict(goal_row)
    tasks = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM tasks WHERE goal_id = ? ORDER BY priority ASC, id ASC",
            (goal["id"],),
        ).fetchall()
    ]
    agent_runs = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM agent_runs WHERE goal_id = ? ORDER BY id ASC",
            (goal["id"],),
        ).fetchall()
    ]
    workbuddies = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM workbuddies WHERE goal_id = ? ORDER BY id ASC",
            (goal["id"],),
        ).fetchall()
    ]
    reviews = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM reviews WHERE goal_id = ? ORDER BY id ASC",
            (goal["id"],),
        ).fetchall()
    ]
    audit_logs = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM audit_logs WHERE goal_id = ? ORDER BY id ASC",
            (goal["id"],),
        ).fetchall()
    ]
    user_status = _goal_user_status(goal, tasks, reviews)
    completed = len([task for task in tasks if task.get("status") == "done"])
    total = max(len(tasks), 1)
    has_planning = any(run.get("agent_role") == "Planner" for run in agent_runs) or any(log.get("action") == "task_plan_created" for log in audit_logs)
    has_review = bool(reviews)
    latest_output = next((task.get("result_summary") for task in reversed(tasks) if task.get("result_summary")), "")
    meeting_summary = "Planner created task breakdown and workbuddy pairings before execution." if has_planning else "No planning record found yet."
    agents = [
        {
            "id": f"task-{task['id']}",
            "name": task.get("agent_role") or "Agent",
            "status": "done" if task.get("status") == "done" else "active",
            "current_activity": task.get("result_summary") or task.get("title") or task.get("status"),
            "updated_at": task.get("updated_at"),
        }
        for task in tasks
    ]
    checks = [
        {"label": "Planning completed", "status": "pass" if has_planning else "pending", "detail": meeting_summary},
        {"label": "Agent tasks completed", "status": "pass" if completed == len(tasks) and tasks else "pending", "detail": f"{completed}/{len(tasks)} tasks completed."},
        {"label": "Review recorded", "status": "pass" if has_review else "pending", "detail": f"{len(reviews)} review record(s)."},
    ]
    collaboration_notes = [
        {
            "primary_role": item.get("primary_role"),
            "buddy_role": item.get("buddy_role"),
            "status": item.get("status"),
            "collaboration_note": item.get("collaboration_note"),
        }
        for item in workbuddies
    ]
    return {
        "run_id": f"agent-goal-{goal['id']}",
        "run_type": "agent_task",
        "user_status": user_status,
        "headline": "Task completed after planning and review." if user_status == "Completed" else "Task needs follow-up after agent review." if user_status == "Needs attention" else "Agents are discussing and executing the task.",
        "explanation": goal.get("title") or "Agent task",
        "started_at": goal.get("created_at"),
        "updated_at": goal.get("updated_at"),
        "progress": {
            "phase": "Deliver" if user_status in {"Completed", "Needs attention"} else "Analyze",
            "current_step": "Review completed" if has_review else "Agents are executing assigned work" if completed else "Planner is preparing task assignments",
            "completed_steps": 5 if user_status in {"Completed", "Needs attention"} else 2 if completed else 1,
            "total_steps": 5,
            "percent": 100 if user_status in {"Completed", "Needs attention"} else round((completed / total) * 80),
            "latest_activity": latest_output or meeting_summary,
        },
        "agents": agents[:12],
        "primary_result": {
            "summary": latest_output or goal.get("description") or "No final task output recorded yet.",
            "findings": [task.get("result_summary") for task in tasks if task.get("result_summary")][:5],
            "deliverables": ["Task breakdown", "Agent execution notes", "Review notes"] if agent_runs else ["Task plan"],
            "output_paths": [],
        },
        "verification": {
            "status": "pass" if user_status == "Completed" else "pending" if user_status == "Working" else "fail",
            "checks": checks,
            "limitations": ["This demo uses local mock tools; it demonstrates planning, assignment, execution, and review flow rather than live provider quality."],
        },
        "artifacts": [],
        "next_action": {
            "label": "Review outputs" if user_status == "Completed" else "Review follow-up",
            "detail": "Open technical details to inspect the planner breakdown, workbuddy pairings, and review notes.",
        },
        "technical_details": {
            "meeting": {
                "summary": meeting_summary,
                "task_assignments": [
                    {
                        "task_id": task.get("id"),
                        "owner_role": task.get("agent_role"),
                        "scope": [task.get("title")],
                        "depends_on": [],
                        "fallback_plan": "Use reviewer feedback to narrow or rerun the task.",
                    }
                    for task in tasks
                ],
                "collaboration_notes": collaboration_notes,
                "review_notes": reviews,
            },
            "raw_goal": goal,
            "raw_tasks": tasks,
            "raw_agent_runs": agent_runs,
            "raw_audit_logs": audit_logs,
        },
    }


def _sort_key(run: dict[str, Any]) -> str:
    return str(run.get("updated_at") or run.get("started_at") or "")


def _compact_run(run: dict[str, Any]) -> dict[str, Any]:
    verification = run.get("verification") or {}
    checks = verification.get("checks") or []
    primary = run.get("primary_result") or {}
    artifacts = run.get("artifacts") or []
    return {
        "run_id": run.get("run_id"),
        "run_type": run.get("run_type", "unknown"),
        "user_status": run.get("user_status", "Working"),
        "headline": run.get("headline", ""),
        "explanation": run.get("explanation", ""),
        "started_at": run.get("started_at"),
        "updated_at": run.get("updated_at"),
        "progress": run.get("progress") or {},
        "agents": (run.get("agents") or [])[:8],
        "primary_result": {
            "summary": primary.get("summary") or "",
            "findings": (primary.get("findings") or [])[:3],
            "deliverables": (primary.get("deliverables") or [])[:5],
            "output_paths": (primary.get("output_paths") or [])[:5],
        },
        "verification": {
            "status": verification.get("status", "pending"),
            "check_count": len(checks),
            "failed_check_count": len([item for item in checks if item.get("status") == "fail"]),
            "limitations": (verification.get("limitations") or [])[:2],
        },
        "artifacts": artifacts[:5],
        "next_action": run.get("next_action") or {},
    }


def collect_common_runs(connection: Connection | None = None) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    warnings: list[str] = []
    root = _micro_gates_root()
    if root.exists():
        summary_paths = sorted(root.glob("micro-gates-*/run-summary.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        for summary_path in summary_paths[:20]:
            runs.append(_common_micro_gate_run(summary_path))
    seen = {str(item.get("run_id")) for item in runs}
    for item in _collect_direct_ai_company_runs():
        if str(item.get("run_id")) not in seen:
            runs.append(item)
            seen.add(str(item.get("run_id")))
    if connection is not None:
        try:
            goal_rows = connection.execute("SELECT * FROM goals ORDER BY id DESC LIMIT 10").fetchall()
            for goal_row in goal_rows:
                runs.append(_common_agent_task_run(connection, goal_row))
        except Exception as exc:  # pragma: no cover - defensive adapter isolation
            warnings.append(f"Could not load agent task runs: {exc}")
    if connection is not None:
        try:
            monitor = collect_ai_company_monitor(connection)
            for item in monitor.get("recent_runs", [])[:10]:
                runs.append(_common_ai_company_run(item))
        except Exception as exc:  # pragma: no cover - defensive adapter isolation
            warnings.append(f"Could not load ai-company runs: {exc}")
    runs.sort(key=_sort_key, reverse=True)
    compact_runs = [_compact_run(item) for item in runs[:20]]
    latest_run = compact_runs[0] if compact_runs else None
    return {
        "schema_version": "common-runs.v1",
        "overview": {
            "total_runs": len(runs),
            "working_count": len([item for item in runs if item["user_status"] == "Working"]),
            "completed_count": len([item for item in runs if item["user_status"] == "Completed"]),
            "needs_attention_count": len([item for item in runs if item["user_status"] == "Needs attention"]),
            "failed_count": len([item for item in runs if item["user_status"] == "Failed"]),
        },
        "latest_run": latest_run,
        "recent_runs": compact_runs,
        "warnings": warnings,
    }


def get_common_run_detail(run_id: str, connection: Connection | None = None) -> dict[str, Any]:
    root = _micro_gates_root()
    micro_summary = root / run_id / "run-summary.json"
    if micro_summary.is_file():
        return _common_micro_gate_run(micro_summary)
    if connection is not None:
        if run_id.startswith("agent-goal-"):
            goal_id = run_id.removeprefix("agent-goal-")
            row = connection.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
            if row is None:
                raise FileNotFoundError(run_id)
            return _common_agent_task_run(connection, row)
        try:
            return _common_ai_company_run(get_ai_company_run_detail(connection, run_id))
        except FileNotFoundError:
            pass
    direct = _direct_ai_company_run(get_results_root() / run_id)
    if direct:
        return _common_ai_company_run(direct)
    raise FileNotFoundError(run_id)
