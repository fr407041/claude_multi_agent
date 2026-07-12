from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.db import get_db, init_db
from app.services.agent_engine import create_goal, execute_task, plan_tasks
from app.services.common_runs import collect_common_runs, get_common_run_detail


class CommonRunsAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "agent_os.db"
        self.env_patch = patch.dict("os.environ", {"AGENT_OS_DB_PATH": str(self.db_path)}, clear=False)
        self.env_patch.start()
        init_db()

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.tempdir.cleanup()

    def test_empty_runs_are_generic(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            with patch.dict("os.environ", {"MICRO_GATES_RUNS_ROOT": tempdir, "AI_COMPANY_RESULTS_ROOT": str(Path(tempdir) / "results"), "FAB_AGENT_POC_RESULTS_ROOT": str(Path(tempdir) / "fab")}, clear=False):
                snapshot = collect_common_runs()
        self.assertEqual(0, snapshot["overview"]["total_runs"])
        self.assertEqual([], snapshot["recent_runs"])

    def test_micro_gate_failure_is_common_needs_attention_not_case_headline(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_set = root / "micro-gates-20260712T010203Z"
            run_set.mkdir()
            verifier = run_set / "gate-D" / "verifier-result.json"
            verifier.parent.mkdir()
            verifier.write_text(json.dumps({"pass": False}), encoding="utf-8")
            summary = {
                "run_set_id": run_set.name,
                "run_set_dir": str(run_set),
                "started_at_utc": "2026-07-12T01:02:03Z",
                "finished_at_utc": "2026-07-12T01:03:03Z",
                "pass": False,
                "failed_gate": "D",
                "gates": [
                    {"gate": "A", "api_status": "succeeded", "return_code": 0, "verifier_pass": True, "verifier_exit_code": 0, "run_dir": str(root / "run-a")},
                    {"gate": "D", "api_status": "succeeded", "return_code": 0, "verifier_pass": False, "verifier_exit_code": 1, "run_dir": str(root / "run-d"), "verifier_result_path": str(verifier)},
                ],
            }
            (run_set / "run-summary.json").write_text(json.dumps(summary), encoding="utf-8")

            with patch.dict("os.environ", {"MICRO_GATES_RUNS_ROOT": tempdir, "AI_COMPANY_RESULTS_ROOT": str(Path(tempdir) / "results"), "FAB_AGENT_POC_RESULTS_ROOT": str(Path(tempdir) / "fab")}, clear=False):
                snapshot = collect_common_runs()
                detail = get_common_run_detail(run_set.name)

        latest = snapshot["latest_run"]
        self.assertEqual("Needs attention", latest["user_status"])
        self.assertEqual("Validation failed at Gate D.", latest["headline"])
        self.assertNotIn("Stock", latest["headline"])
        self.assertNotIn("PTT", latest["headline"])
        self.assertEqual("single artifact creation", detail["technical_details"]["validation_details"][1]["capability"])
        self.assertEqual("ptt-stock-live/article.json", detail["technical_details"]["validation_details"][1]["expected_artifact"])
        actual = detail["technical_details"]["validation_details"][1]["actual_artifact"]
        self.assertFalse(actual["exists"])
        self.assertTrue(actual["path"].replace("\\", "/").endswith("/ptt-stock-live/article.json"))

    def test_micro_gate_artifact_not_created_gets_actionable_user_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_set = root / "micro-gates-20260712T030405Z"
            run_set.mkdir()
            run_dir = root / "run-b"
            run_dir.mkdir()
            summary = {
                "run_set_id": run_set.name,
                "run_set_dir": str(run_set),
                "started_at_utc": "2026-07-12T03:04:05Z",
                "finished_at_utc": "2026-07-12T03:05:05Z",
                "pass": False,
                "failed_gate": "B",
                "gates": [
                    {
                        "gate": "B",
                        "api_status": "failed",
                        "return_code": 1,
                        "verifier_pass": False,
                        "verifier_exit_code": 1,
                        "failure_category": "ARTIFACT_NOT_CREATED_BY_MODEL",
                        "run_dir": str(run_dir),
                    }
                ],
            }
            (run_set / "run-summary.json").write_text(json.dumps(summary), encoding="utf-8")

            with patch.dict("os.environ", {"MICRO_GATES_RUNS_ROOT": tempdir, "AI_COMPANY_RESULTS_ROOT": str(Path(tempdir) / "results"), "FAB_AGENT_POC_RESULTS_ROOT": str(Path(tempdir) / "fab")}, clear=False):
                detail = get_common_run_detail(run_set.name)

        gate = detail["technical_details"]["validation_details"][0]
        self.assertEqual("Agent did not create the expected file.", gate["failure_reason"])
        self.assertIn("do not accept prose-only output", gate["user_hint"])
        self.assertEqual("ARTIFACT_NOT_CREATED_BY_MODEL", gate["failure_category"])

    def test_micro_gate_windows_host_path_maps_to_watched_root(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_set = root / "micro-gates-20260712T040506Z"
            run_set.mkdir()
            run_dir = root / "run-c"
            artifact = run_dir / "ptt-stock-live" / "urls.json"
            artifact.parent.mkdir(parents=True)
            artifact.write_text(json.dumps(["https://www.ptt.cc/bbs/Stock/M.1234567890.A.ABC.html"] * 5), encoding="utf-8")
            verifier = run_set / "gate-C" / "verifier-result.json"
            verifier.parent.mkdir()
            verifier.write_text(json.dumps({"pass": True}), encoding="utf-8")
            summary = {
                "run_set_id": run_set.name,
                "run_set_dir": "D:\\repo\\agent-test-runs\\" + run_set.name,
                "started_at_utc": "2026-07-12T04:05:06Z",
                "finished_at_utc": "2026-07-12T04:06:06Z",
                "pass": True,
                "gates": [
                    {
                        "gate": "C",
                        "api_status": "succeeded",
                        "return_code": 0,
                        "verifier_pass": True,
                        "verifier_exit_code": 0,
                        "run_dir": "D:\\repo\\agent-test-runs\\run-c",
                        "verifier_result_path": "D:\\repo\\agent-test-runs\\" + run_set.name + "\\gate-C\\verifier-result.json",
                    }
                ],
            }
            (run_set / "run-summary.json").write_text(json.dumps(summary), encoding="utf-8")

            with patch.dict("os.environ", {"MICRO_GATES_RUNS_ROOT": tempdir, "AI_COMPANY_RESULTS_ROOT": str(root / "results"), "FAB_AGENT_POC_RESULTS_ROOT": str(root / "fab")}, clear=False):
                detail = get_common_run_detail(run_set.name)

        gate = detail["technical_details"]["validation_details"][0]
        actual = gate["actual_artifact"]
        self.assertTrue(actual["exists"])
        self.assertIn("original_candidate_paths", actual)
        self.assertEqual(str(artifact), actual["path"])
        run_directory = gate["technical_paths"][1]
        self.assertTrue(run_directory["exists"])
        self.assertIn("original_path", run_directory)

    def test_micro_gate_all_pass_is_completed(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_set = Path(tempdir) / "micro-gates-20260712T020304Z"
            run_set.mkdir()
            summary = {
                "run_set_id": run_set.name,
                "started_at_utc": "2026-07-12T02:03:04Z",
                "finished_at_utc": "2026-07-12T02:04:04Z",
                "pass": True,
                "gates": [
                    {"gate": "A", "api_status": "succeeded", "return_code": 0, "verifier_pass": True, "verifier_exit_code": 0},
                    {"gate": "B", "api_status": "succeeded", "return_code": 0, "verifier_pass": True, "verifier_exit_code": 0},
                ],
            }
            (run_set / "run-summary.json").write_text(json.dumps(summary), encoding="utf-8")
            with patch.dict("os.environ", {"MICRO_GATES_RUNS_ROOT": tempdir, "AI_COMPANY_RESULTS_ROOT": str(Path(tempdir) / "results"), "FAB_AGENT_POC_RESULTS_ROOT": str(Path(tempdir) / "fab")}, clear=False):
                snapshot = collect_common_runs()
        self.assertEqual("Completed", snapshot["latest_run"]["user_status"])
        self.assertEqual("pass", snapshot["latest_run"]["verification"]["status"])

    def test_direct_ai_company_failed_run_is_visible_without_db_sync_row(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run = root / "run-20260712-125855-shopping-site-common-demo"
            ai_dir = run / "ai_company"
            ai_dir.mkdir(parents=True)
            (run / "worktree").mkdir()
            (run / "results").mkdir()
            (ai_dir / "task_harness_report.json").write_text(
                json.dumps(
                    {
                        "run_dir": str(run),
                        "overall_status": "fail",
                        "kpis": {"goal": "Create a generated output package."},
                    }
                ),
                encoding="utf-8",
            )
            (ai_dir / "final_run_verdict.json").write_text(
                json.dumps({"overall_status": "fail", "failure_category": "ARTIFACT_NOT_CREATED_BY_MODEL"}),
                encoding="utf-8",
            )
            (ai_dir / "artifact_verify_report.json").write_text(
                json.dumps(
                    {
                        "parsed": {
                            "all_passed": False,
                            "score": 0.0,
                            "checks": [
                                {"label": "shopping-site/index.html exists", "status": "fail", "detail": "missing file"}
                            ],
                            "limitations": ["Verifier recorded missing generated output."],
                        }
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"AI_COMPANY_RESULTS_ROOT": tempdir, "MICRO_GATES_RUNS_ROOT": str(root / "micro"), "FAB_AGENT_POC_RESULTS_ROOT": str(root / "fab")}, clear=False):
                snapshot = collect_common_runs()
                detail = get_common_run_detail(run.name)

        self.assertEqual(run.name, snapshot["latest_run"]["run_id"])
        self.assertEqual("Failed", snapshot["latest_run"]["user_status"])
        self.assertEqual("fail", detail["verification"]["status"])
        self.assertEqual("shopping-site/index.html exists", detail["verification"]["checks"][0]["label"])

    def test_fab_agent_poc_run_exposes_capability_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run = root / "run-fab-agent-poc-20260712-120000-000001"
            (run / "ai_company").mkdir(parents=True)
            (run / "worktree" / "shopping-site").mkdir(parents=True)
            for rel, text in [
                ("worktree/shopping-site/index.html", "<html><body>Products</body></html>"),
                ("worktree/shopping-site/styles.css", "body{}"),
                ("worktree/shopping-site/app.js", "console.log('cart')"),
                ("worktree/shopping-site/README.md", "# Review"),
            ]:
                (run / rel).write_text(text, encoding="utf-8")
            summary = {
                "run_id": run.name,
                "run_type": "fab_agent_poc",
                "mode": "mock",
                "overall_status": "pass",
                "started_at_utc": "2026-07-12T12:00:00Z",
                "finished_at_utc": "2026-07-12T12:01:00Z",
                "run_dir": str(run),
                "worktree": str(run / "worktree"),
                "meeting": {"summary": "Agents discussed scope.", "discussion_log": [{"role": "planner", "round": 1, "summary": "Plan.", "proposed_actions": ["Build"], "decision_state": "recorded"}]},
                "effective_policies": [
                    {
                        "agent_id": "fab_product_planner",
                        "display_name": "Fab Product Planner",
                        "capability": "readonly_research",
                        "capability_display_name": "Readonly Research",
                        "policy_source": "CIM",
                        "effective_allowed_skills": ["research-task-orchestrator"],
                        "effective_allowed_mcp_groups": [],
                        "allowed_actions": ["read_project_file", "write_agent_artifact"],
                    }
                ],
                "blocked_attempts": [
                    {"agent_id": "fab_product_planner", "action": "write_project_file", "path": "worktree/shopping-site/app.js", "blocked": True, "reason": "not allowed"}
                ],
                "acceptance": {
                    "resolved_three_fab_agents": True,
                    "blocked_readonly_project_write": True,
                    "blocked_reviewer_project_edit": True,
                    "shopping_site_verified": True,
                    "live_generation_passed": True,
                },
                "verifier": {"all_passed": True},
            }
            (run / "fab_poc_summary.json").write_text(json.dumps(summary), encoding="utf-8")
            (run / "ai_company" / "fab_poc_summary.json").write_text(json.dumps(summary), encoding="utf-8")
            (run / "ai_company" / "meeting_decision.json").write_text(json.dumps(summary["meeting"]), encoding="utf-8")
            (run / "ai_company" / "artifact_verify_report.json").write_text(json.dumps({"all_passed": True}), encoding="utf-8")

            with patch.dict(
                "os.environ",
                {
                    "FAB_AGENT_POC_RESULTS_ROOT": tempdir,
                    "MICRO_GATES_RUNS_ROOT": str(root / "micro"),
                    "AI_COMPANY_RESULTS_ROOT": str(root / "ai-company"),
                },
                clear=False,
            ):
                snapshot = collect_common_runs()
                detail = get_common_run_detail(run.name)

        self.assertEqual(run.name, snapshot["latest_run"]["run_id"])
        self.assertEqual("fab_agent_poc", detail["run_type"])
        self.assertEqual("Completed", detail["user_status"])
        self.assertEqual("Review outputs", detail["next_action"]["label"])
        self.assertEqual("CIM", detail["technical_details"]["fab_agents"][0]["policy_source"])
        self.assertEqual(1, len(detail["technical_details"]["blocked_tool_attempts"]))
        self.assertTrue(any(item["label"] == "HTML deliverable" and item["exists"] for item in detail["artifacts"]))

    def test_malformed_micro_gate_summary_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_set = Path(tempdir) / "micro-gates-bad"
            run_set.mkdir()
            (run_set / "run-summary.json").write_text("{bad", encoding="utf-8")
            with patch.dict("os.environ", {"MICRO_GATES_RUNS_ROOT": tempdir, "AI_COMPANY_RESULTS_ROOT": str(Path(tempdir) / "results"), "FAB_AGENT_POC_RESULTS_ROOT": str(Path(tempdir) / "fab")}, clear=False):
                snapshot = collect_common_runs()
        self.assertEqual("Needs attention", snapshot["latest_run"]["user_status"])
        self.assertEqual("Validation run could not be read.", snapshot["latest_run"]["headline"])

    def test_agent_task_run_exposes_planning_collaboration_and_review(self) -> None:
        with get_db() as connection:
            goal_id = create_goal(connection, "Demo planning flow", "Show planner, workbuddy assignment, execution, and review.")
            tasks = plan_tasks(connection, goal_id, "Demo planning flow", "Show planner, workbuddy assignment, execution, and review.")
            for task in tasks:
                execute_task(connection, task["id"])
            connection.commit()

            snapshot = collect_common_runs(connection)
            detail = get_common_run_detail(f"agent-goal-{goal_id}", connection)

        self.assertEqual("agent_task", detail["run_type"])
        self.assertEqual("Completed", detail["user_status"])
        self.assertEqual("Task completed after planning and review.", detail["headline"])
        self.assertEqual("pass", detail["verification"]["checks"][0]["status"])
        self.assertGreaterEqual(len(detail["technical_details"]["meeting"]["collaboration_notes"]), 4)
        self.assertEqual(f"agent-goal-{goal_id}", snapshot["latest_run"]["run_id"])


if __name__ == "__main__":
    unittest.main()
