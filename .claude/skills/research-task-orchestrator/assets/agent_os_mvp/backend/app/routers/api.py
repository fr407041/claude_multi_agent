from __future__ import annotations

import asyncio
import json
import os

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.db import get_db
from app.schemas import ChatRequest, ChatResponse, DashboardResponse, GoalCreate, GoalCreatedResponse, HookEventRequest
from app.services.ai_company_monitor import collect_ai_company_monitor, get_ai_company_run_detail
from app.services.agent_engine import create_goal, execute_task, plan_tasks
from app.services.common_runs import collect_common_runs, get_common_run_detail
from app.services.dashboard import collect_dashboard
from app.services.claude_session import run_chat
from app.services.session_store import append_event, ensure_session, session_dashboard


router = APIRouter(prefix="/api", tags=["agent-os"])


TERMINAL_AI_COMPANY_STATUSES = {"pass", "fail", "partial"}


def _normalize_user_status(value: str | None, running_count: int = 0, waiting_count: int = 0) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "pass":
        return "Completed"
    if normalized == "partial":
        return "Needs attention"
    if normalized == "fail":
        return "Failed"
    if running_count > 0 or waiting_count > 0:
        return "Working"
    return "Working"


def _build_progress_snapshot(run: dict) -> dict:
    final_verdict = run.get("final_run_verdict") or run.get("final_result", {}).get("final_run_verdict") or {}
    overall_status = final_verdict.get("overall_status") or run.get("overall_status")
    running_count = int(run.get("running_agent_count") or 0)
    waiting_count = int(run.get("waiting_agent_count") or 0)
    done_count = int(run.get("done_agent_count") or 0)
    failed_count = int(run.get("failed_agent_count") or 0)
    execution_jobs = int(run.get("execution_jobs_run") or 0)
    has_summary = bool((run.get("final_result") or {}).get("summary_markdown"))
    phase_index = 0
    current_step = "Preparing run"
    if run.get("meeting_status") or run.get("goal_dag", {}).get("plan"):
        phase_index = 1
        current_step = "Planning work"
    if running_count or waiting_count or execution_jobs:
        phase_index = 2
        current_step = "Running agents"
    if done_count or failed_count or run.get("review_verdicts"):
        phase_index = 3
        current_step = "Reviewing outputs"
    if has_summary or str(overall_status or "").lower() in TERMINAL_AI_COMPANY_STATUSES:
        phase_index = 4
        current_step = "Delivering result"
    phases = ["Plan", "Gather data", "Analyze", "Review", "Deliver"]
    total_steps = len(phases)
    return {
        "phase": phases[phase_index],
        "current_step": current_step,
        "completed_steps": phase_index if str(overall_status or "").lower() not in TERMINAL_AI_COMPANY_STATUSES else total_steps,
        "total_steps": total_steps,
        "percent": 100 if str(overall_status or "").lower() in TERMINAL_AI_COMPANY_STATUSES else round((phase_index / (total_steps - 1)) * 100),
    }


def _build_agent_snapshots(run: dict) -> list[dict]:
    board = run.get("agent_state_board") or {}
    agents = []
    for state_name, user_state in [
        ("running", "active"),
        ("waiting", "blocked"),
        ("done", "done"),
        ("failed", "failed"),
    ]:
        for item in board.get(state_name, []):
            agents.append(
                {
                    "id": item.get("task_id") or item.get("role") or item.get("owner_role") or "agent",
                    "name": item.get("role") or item.get("owner_role") or item.get("agent_profile") or "Agent",
                    "status": user_state,
                    "current_activity": item.get("verification_note") or item.get("fallback_plan") or item.get("task_id") or state_name,
                    "updated_at": run.get("started_at"),
                }
            )
    return agents[:12]


def _build_run_event(run_id: str, run: dict, event_type: str = "run_updated") -> dict:
    final_verdict = run.get("final_run_verdict") or run.get("final_result", {}).get("final_run_verdict") or {}
    overall_status = final_verdict.get("overall_status") or run.get("overall_status")
    running_count = int(run.get("running_agent_count") or 0)
    waiting_count = int(run.get("waiting_agent_count") or 0)
    return {
        "run_id": run_id,
        "event_type": event_type,
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "user_status": _normalize_user_status(overall_status, running_count, waiting_count),
        "progress": _build_progress_snapshot(run),
        "agents": _build_agent_snapshots(run),
    }


def _sse(data: dict, event: str = "message") -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/v1/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    try:
        return run_chat(payload.prompt, payload.session_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/v1/dashboard/config")
def dashboard_config():
    def enabled(name: str, default: bool = True) -> bool:
        return os.getenv(name, "1" if default else "0").strip().lower() not in {"0", "false", "no", "off"}
    return {
        "show_progress_bar": enabled("AGENT_OS_SHOW_PROGRESS_BAR"),
        "show_agent_logs": enabled("AGENT_OS_SHOW_AGENT_LOGS"),
        "show_artifacts": enabled("AGENT_OS_SHOW_ARTIFACTS"),
        "show_chat": enabled("AGENT_OS_SHOW_CHAT", default=False),
        "event_policy": "explicit_messages_tools_status_artifacts_only",
    }


@router.get("/v1/dashboard/{session_id}")
def session_detail(session_id: str):
    payload = session_dashboard(session_id)
    if payload["session"] is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return payload


@router.post("/v1/hooks/events")
def collect_hook_event(payload: HookEventRequest, x_agent_os_hook_token: str | None = Header(default=None)):
    expected = os.getenv("AGENT_OS_HOOK_TOKEN", "").strip()
    if expected and x_agent_os_hook_token != expected:
        raise HTTPException(status_code=401, detail="Invalid hook token")
    ensure_session(payload.session_id)
    append_event(payload.session_id, payload.event_type, payload.agent_role, payload.payload)
    return {"accepted": True, "session_id": payload.session_id}


@router.post("/goals", response_model=GoalCreatedResponse)
def create_goal_endpoint(payload: GoalCreate):
    with get_db() as connection:
        goal_id = create_goal(connection, payload.title, payload.description)
        plan_tasks(connection, goal_id, payload.title, payload.description)
        connection.commit()

        goal = connection.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        tasks = connection.execute(
            "SELECT * FROM tasks WHERE goal_id = ? ORDER BY priority ASC, id ASC",
            (goal_id,),
        ).fetchall()
        return {
            "goal": dict(goal),
            "tasks": [dict(task) for task in tasks],
        }


@router.post("/tasks/{task_id}/run")
def run_task_endpoint(task_id: int):
    with get_db() as connection:
        try:
            result = execute_task(connection, task_id)
            connection.commit()
            return result
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/goals/{goal_id}/run-all")
def run_goal_endpoint(goal_id: int):
    with get_db() as connection:
        goal = connection.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        if goal is None:
            raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
        pending_tasks = connection.execute(
            "SELECT id FROM tasks WHERE goal_id = ? AND status != 'done' ORDER BY priority ASC, id ASC",
            (goal_id,),
        ).fetchall()
        results = [execute_task(connection, row["id"]) for row in pending_tasks]
        connection.commit()
        return {"goal_id": goal_id, "executed": results}


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard():
    with get_db() as connection:
        return collect_dashboard(connection)


@router.get("/runs")
def common_runs():
    with get_db() as connection:
        return collect_common_runs(connection)


@router.get("/runs/events")
async def common_runs_events():
    async def event_stream():
        last_payload = ""
        for _ in range(900):
            with get_db() as connection:
                payload = collect_common_runs(connection)
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if encoded != last_payload:
                yield _sse(payload, event="common_runs_updated")
                last_payload = encoded
            await asyncio.sleep(2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/runs/{run_id}")
def common_run_detail(run_id: str):
    with get_db() as connection:
        try:
            return get_common_run_detail(run_id, connection)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found") from exc


@router.get("/ai-company-monitor")
def ai_company_monitor():
    with get_db() as connection:
        return collect_ai_company_monitor(connection)


@router.get("/ai-company-monitor/runs/{run_id}")
def ai_company_run_detail(run_id: str):
    with get_db() as connection:
        try:
            return get_ai_company_run_detail(connection, run_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found") from exc


@router.get("/ai-company-monitor/runs/{run_id}/events")
async def ai_company_run_events(run_id: str):
    async def event_stream():
        last_payload = ""
        for _ in range(600):
            with get_db() as connection:
                try:
                    run = get_ai_company_run_detail(connection, run_id)
                except FileNotFoundError:
                    yield _sse({"run_id": run_id, "event_type": "run_missing"}, event="error")
                    return
            payload = _build_run_event(run_id, run)
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if encoded != last_payload:
                yield _sse(payload, event=payload["event_type"])
                last_payload = encoded
            overall_status = str((run.get("final_run_verdict") or {}).get("overall_status") or run.get("overall_status") or "").lower()
            if overall_status in TERMINAL_AI_COMPANY_STATUSES:
                yield _sse(_build_run_event(run_id, run, event_type="result_updated"), event="result_updated")
                return
            await asyncio.sleep(3)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/demo/seed")
def seed_demo():
    demo_goal = GoalCreate(
        title="Prepare an internal release readiness summary",
        description="Create a small internal summary with research findings, implementation notes, QA concerns, and reviewer feedback.",
    )
    response = create_goal_endpoint(demo_goal)
    task_ids = [task["id"] for task in response["tasks"]]
    with get_db() as connection:
        results = [execute_task(connection, task_id) for task_id in task_ids]
        connection.commit()
    return {"goal_id": response["goal"]["id"], "executed": results}
