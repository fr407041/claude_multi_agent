from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.fab_agent_policy import ROOT, resolve_fab_agent
from scripts.verify_effective_agent_policy import verify_policy


class EffectiveAgentPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="effective-agent-policy-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _resolved_builder_dir(self) -> Path:
        result = resolve_fab_agent(ROOT / "fab_agents" / "examples" / "fab_frontend_builder", self.tmp / "resolved")
        self.assertTrue(result["passed"], result)
        return Path(result["output_dir"])

    def test_valid_resolved_policy_passes(self) -> None:
        runtime_dir = self._resolved_builder_dir()
        report = verify_policy(runtime_dir)
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["policy_source"], "CIM")
        self.assertEqual(report["approved_skill_count"], 1)

    def test_missing_approved_skills_manifest_fails(self) -> None:
        runtime_dir = self._resolved_builder_dir()
        (runtime_dir / "mounted-skills" / "approved-skills.json").unlink()
        report = verify_policy(runtime_dir)
        self.assertFalse(report["passed"])
        self.assertIn("APPROVED_SKILLS_MANIFEST_MISSING", {item["code"] for item in report["errors"]})

    def test_missing_effective_policy_fails(self) -> None:
        runtime_dir = self._resolved_builder_dir()
        (runtime_dir / "effective-agent.json").unlink()
        report = verify_policy(runtime_dir)
        self.assertFalse(report["passed"])
        self.assertIn("EFFECTIVE_AGENT_POLICY_MISSING", {item["code"] for item in report["errors"]})

    def test_non_cim_policy_source_fails(self) -> None:
        runtime_dir = self._resolved_builder_dir()
        effective_path = runtime_dir / "effective-agent.json"
        effective = json.loads(effective_path.read_text(encoding="utf-8"))
        effective["policy_source"] = "FabUser"
        effective_path.write_text(json.dumps(effective, ensure_ascii=False, indent=2), encoding="utf-8")
        report = verify_policy(runtime_dir)
        self.assertFalse(report["passed"])
        self.assertIn("EFFECTIVE_AGENT_POLICY_NOT_CIM", {item["code"] for item in report["errors"]})

    def test_host_skill_source_path_can_resolve_through_project_root(self) -> None:
        runtime_dir = self._resolved_builder_dir()
        approved_path = runtime_dir / "mounted-skills" / "approved-skills.json"
        approved = json.loads(approved_path.read_text(encoding="utf-8"))
        approved["skills"][0]["source_path"] = "D:\\host\\checkout\\.claude\\skills\\research-task-orchestrator"
        approved_path.write_text(json.dumps(approved, ensure_ascii=False, indent=2), encoding="utf-8")
        report = verify_policy(runtime_dir, project_roots=[ROOT])
        self.assertTrue(report["passed"], report)
        self.assertTrue(report["resolved_skill_sources"][0]["used_fallback"])
        self.assertTrue(Path(report["resolved_skill_sources"][0]["resolved_source_path"]).is_dir())

    def test_cli_writes_preflight_report(self) -> None:
        runtime_dir = self._resolved_builder_dir()
        out = self.tmp / "preflight.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "verify_effective_agent_policy.py"),
                str(runtime_dir),
                "--json",
                "--out",
                str(out),
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(out.is_file())
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(payload["passed"], payload)


if __name__ == "__main__":
    unittest.main()
