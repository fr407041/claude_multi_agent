from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import get_db_path_warning, init_db
from app.routers.api import router as api_router
from app.services.ai_company_monitor import get_project_root, get_results_root
from app.services.session_store import init_session_store


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    init_session_store()
    yield


app = FastAPI(
    title="Agent OS MVP",
    version="0.1.0",
    description="Simplified internal Agent OS with Goals, Task Wall, fixed Agents, Reviews, and Audit Logs.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return checkout_marker()


app.include_router(api_router)


def checkout_marker():
    dashboard_root = Path(__file__).resolve().parents[2]
    project_root = get_project_root()
    micro_gates_root = os.getenv("MICRO_GATES_RUNS_ROOT", "").strip()
    if micro_gates_root:
        micro_root = Path(micro_gates_root).expanduser()
        if not micro_root.is_absolute():
            micro_root = project_root / micro_root
    else:
        micro_root = project_root / "agent-test-runs"
    fab_poc_root = os.getenv("FAB_AGENT_POC_RESULTS_ROOT", "").strip()
    if fab_poc_root:
        fab_root = Path(fab_poc_root).expanduser()
        if not fab_root.is_absolute():
            fab_root = project_root / fab_root
    else:
        fab_root = project_root / "results" / "fab_agent_poc"
    result_root = get_results_root()
    db_warning = get_db_path_warning()
    return {
        "status": "ok",
        "app": "agent_os_mvp",
        "app_version": app.version,
        "app_root": str(dashboard_root),
        "project_root": str(project_root),
        "result_root": str(result_root),
        "results_root": str(result_root),
        "micro_gates_root": str(micro_root),
        "fab_agent_poc_root": str(fab_root),
        "watched_roots": {
            "AI_COMPANY_RESULTS_ROOT": str(result_root),
            "MICRO_GATES_RUNS_ROOT": str(micro_root),
            "FAB_AGENT_POC_RESULTS_ROOT": str(fab_root),
        },
        "watched_root_exists": {
            "AI_COMPANY_RESULTS_ROOT": result_root.exists(),
            "MICRO_GATES_RUNS_ROOT": micro_root.exists(),
            "FAB_AGENT_POC_RESULTS_ROOT": fab_root.exists(),
        },
        "database_warning": db_warning,
    }
