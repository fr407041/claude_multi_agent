from openhands.core import AgentRuntime, plan_task


def test_runtime_allows_configured_tool() -> None:
    assert AgentRuntime(["read"]).can_use("read")


def test_plan_task() -> None:
    assert plan_task("ship")["status"] == "planned"
