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
