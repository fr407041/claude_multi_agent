# Bounded repository evidence

This evidence is generated automatically from the file context guard.
It is not a full raw repository prompt. Omitted, skipped, blocked, and chunked bytes are recorded in file_context_manifest.json.
Estimated evidence tokens: 275
Evidence token budget: 12000
## File: docs/architecture.md
size_bytes: 161
context_guard_action: full_read
skipped_bytes: 0
sha256: 76194698d82b192bf32b1c502c833f2d6bf910bd8bba361bab3cabe35cce5cb6

# Architecture

The sample runtime separates planning from execution. Real deployments should
document tool boundaries, sandbox assumptions, and audit evidence.

## File: openhands/core.py
size_bytes: 374
context_guard_action: full_read
skipped_bytes: 0
sha256: 27fb6d19210e0c5234deed68def91a251a2df38804c04ee62be94a882a61317f

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
sha256: 2f097e25b3dec2185edb0c7f7d449b1b04becab3de45e395e39f78c86f7d33c6

[project]
name = "openhands-sample"
version = "0.1.0"

[tool.pytest.ini_options]
testpaths = ["tests"]

## File: README.md
size_bytes: 236
context_guard_action: full_read
skipped_bytes: 0
sha256: 0189ee7585636555b633defb4602e08e27507a04afd2785adaa433a28fa41f5d

# OpenHands sample fixture

This fixture stands in for a GitHub repository during deterministic tests.
It includes application code, tests, and a deliberately large text file so the
safe-read guard must record bounded context behavior.

## File: tests/test_core.py
size_bytes: 238
context_guard_action: full_read
skipped_bytes: 0
sha256: c3770943f836bde1d738668530743d8eefa27bdbaca8bf198bcbf1ae0014d09f

from openhands.core import AgentRuntime, plan_task


def test_runtime_allows_configured_tool() -> None:
    assert AgentRuntime(["read"]).can_use("read")


def test_plan_task() -> None:
    assert plan_task("ship")["status"] == "planned"
