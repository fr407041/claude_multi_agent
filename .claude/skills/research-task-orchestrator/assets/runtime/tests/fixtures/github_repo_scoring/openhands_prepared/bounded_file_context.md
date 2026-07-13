## File: docs/architecture.md
size_bytes: 161
context_guard_action: full_read
skipped_bytes: 0

# Architecture

The sample runtime separates planning from execution. Real deployments should
document tool boundaries, sandbox assumptions, and audit evidence.

## File: openhands/core.py
size_bytes: 374
context_guard_action: full_read
skipped_bytes: 0

from __future__ import annotations


class AgentRuntime:
    def __init__(self, tools: list[str]) -> None:
        self.tools = tools

    def can_use(self, tool: str) -> bool:
        return tool in self.tools


def plan_task(goal: str) -> dict[str, str]:
    if not goal.strip():
        raise ValueError("goal is required")
    return {"goal": goal, "status": "planned"}

## File: pyproject.toml
size_bytes: 103
context_guard_action: full_read
skipped_bytes: 0

[project]
name = "openhands-sample"
version = "0.1.0"

[tool.pytest.ini_options]
testpaths = ["tests"]

## File: README.md
size_bytes: 236
context_guard_action: full_read
skipped_bytes: 0

# OpenHands sample fixture

This fixture stands in for a GitHub repository during deterministic tests.
It includes application code, tests, and a deliberately large text file so the
safe-read guard must record bounded context behavior.

## File: tests/test_core.py
size_bytes: 238
context_guard_action: full_read
skipped_bytes: 0

from openhands.core import AgentRuntime, plan_task


def test_runtime_allows_configured_tool() -> None:
    assert AgentRuntime(["read"]).can_use("read")


def test_plan_task() -> None:
    assert plan_task("ship")["status"] == "planned"
