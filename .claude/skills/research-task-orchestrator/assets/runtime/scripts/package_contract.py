from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


PACKAGE_SCHEMA_VERSION = 1
RELEASE_ID = "2026.07.11-company.13"
MANIFEST_PATH = Path("release") / "ai_company_package_manifest.json"

CANONICAL_ROLES = [
    "meeting_coordinator",
    "planner_agent",
    "risk_reviewer",
    "decision_agent",
    "research_agent",
    "synthesis_agent",
    "reviewer_worker",
    "executor_backend",
    "executor_docs",
]

RUNTIME_REQUIRED_PATHS = [
    ".gitattributes",
    "scripts/package_contract.py",
    "scripts/task_contract.py",
    "scripts/validate_ai_company_spec.py",
    "scripts/verify_install.py",
    "scripts/verify_agent_micro_gate.py",
    "scripts/run_ai_company_task_harness.py",
    "scripts/materialize_ai_company_task_run.py",
    "scripts/run_ai_company_meeting.py",
    "scripts/run_ai_company_execution.py",
    "scripts/run_ai_company_reviewer_worker.py",
    "scripts/run_ai_company_watchdog.py",
    "scripts/main_agent_memory_guard.py",
    "scripts/subagent_claim_ledger.py",
    "scripts/agent_profile_resolver.py",
    "scripts/agent_token_ledger.py",
    "scripts/bounded_context_loader.py",
    "scripts/safe_file_context.py",
    "scripts/run_local_model_action_executor.py",
    "scripts/probe_provider_diagnostic.py",
    "scripts/goal_driven_workflow.py",
    "scripts/run_goal_driven_workflow.py",
    "scripts/run-shopping-site-common-demo.sh",
    "scripts/run-github-repo-scoring-demo.sh",
    "scripts/run_github_repo_scoring_demo.py",
    "scripts/run-task-contract-smoke.sh",
    "scripts/run-task-contract-smoke.ps1",
    "scripts/prepare_github_repo_scoring_case.py",
    "scripts/prepare_common_research_case.py",
    "scripts/verify_github_repo_scoring_artifact.py",
    "scripts/verify_common_research_artifact.py",
    "scripts/verify_generated_output_package.py",
    "scripts/verify_sens_summary_artifact.py",
    "scripts/worker_claude_router.py",
    "scripts/worker_claude_router.sh",
    "scripts/worker_claude_router_summary_template.sh",
    "scripts/worker_claude_router_managed_single_file.sh",
    "scripts/worker_claude_router_managed_multi_file.sh",
    "configs/ai_company/agent_profiles.json",
    "configs/ai_company/task_harness.defaults.json",
    "configs/ai_company/task_assignment.schema.json",
    "configs/cim_capabilities/artifact_reviewer.json",
    "configs/cim_capabilities/decision_maker.json",
    "configs/cim_capabilities/project_builder.json",
    "configs/cim_capabilities/readonly_research.json",
    "configs/cim_roles/builder.json",
    "configs/cim_roles/decision_maker.json",
    "configs/cim_roles/planner.json",
    "configs/cim_roles/researcher.json",
    "configs/cim_roles/reviewer.json",
    "docs/ai_specs/ai-company-release-readiness-strict-demo.json",
    "docs/ai_specs/goal-driven-dependency-recovery-mock.json",
    "docs/ai_specs/goal-driven-external-evidence-live.json",
    "docs/ai_specs/goal-driven-code-execute-repair-live.json",
    "docs/ai_specs/shopping-site-common-demo.json",
    "docs/ai_specs/github-repo-scoring-demo.json",
    "docs/GETTING_STARTED.zh-TW.md",
    "fab_agents/examples/fab_artifact_reviewer/agent.json",
    "fab_agents/examples/fab_artifact_reviewer/background.md",
    "fab_agents/examples/fab_frontend_builder/agent.json",
    "fab_agents/examples/fab_frontend_builder/background.md",
    "fab_agents/examples/fab_product_planner/agent.json",
    "fab_agents/examples/fab_product_planner/background.md",
    "fab_agents/templates/builder.role-card.yaml",
    "fab_agents/templates/decision-maker.role-card.yaml",
    "fab_agents/templates/planner.role-card.yaml",
    "fab_agents/templates/researcher.role-card.yaml",
    "fab_agents/templates/reviewer.role-card.yaml",
    "scripts/create_fab_agent.py",
    "scripts/create_role_card.py",
    "scripts/fab_agent_policy.py",
    "scripts/list_cim_capabilities.py",
    "scripts/list_roles.py",
    "scripts/resolve_fab_agent.py",
    "scripts/resolve_role_card.py",
    "scripts/role_card_policy.py",
    "scripts/run_fab_agent_poc.py",
    "scripts/validate_fab_agent.py",
    "scripts/validate_role_card.py",
    "tests/test_fab_agent_poc.py",
    "tests/test_fab_agent_policy.py",
    "tests/test_role_card_policy.py",
    "tests/fixtures/github_repo_scoring/openhands_prepared/repo_metadata.json",
    "tests/fixtures/github_repo_scoring/openhands_prepared/repository_inventory.json",
    "tests/fixtures/github_repo_scoring/openhands_prepared/file_context_manifest.json",
    "tests/fixtures/github_repo_scoring/openhands_prepared/bounded_file_context.md",
    "tests/fixtures/github_repo_scoring/openhands_prepared/inventory_shards/shard-000.json",
    "tests/fixtures/ai_company_release_readiness_demo/release_brief.md",
    "tests/fixtures/ai_company_release_readiness_demo/test_results.md",
    "tests/fixtures/ai_company_release_readiness_demo/risk_log.md",
    "tests/fixtures/ai_company_release_readiness_demo/known_issues.md",
    "tests/fixtures/ai_company_release_readiness_demo/artifact_requirements.json",
    "tests/fixtures/ai_company_release_readiness_demo/README.md",
    "tests/fixtures/ai_company_release_readiness_demo/research_brief.md",
    "tests/fixtures/ai_company_release_readiness_demo/evidence_summary.txt",
    "tests/fixtures/goal_driven_supplied/source.txt",
    "tests/fixtures/goal_driven_external/evidence.json",
    "tests/fixtures/goal_driven_code/requirements.md",
    *[
        f".claude/skills/research-task-orchestrator/agents/roles/{role}.md"
        for role in CANONICAL_ROLES
    ],
    *[
        f".claude/skills/research-task-orchestrator/agents/settings/{role}.json"
        for role in CANONICAL_ROLES
    ],
]

SKILL_REQUIRED_PATHS = [
    "SKILL.md",
    "agents/openai.yaml",
    "scripts/install_runtime.sh",
    "scripts/run_task.sh",
    "scripts/install_dashboard.sh",
    "scripts/start_dashboard.sh",
    "scripts/stop_dashboard.sh",
    "scripts/smoke_dashboard.sh",
    "assets/agent_os_mvp/backend/app/main.py",
    "assets/agent_os_mvp/backend/app/services/ai_company_monitor.py",
    "assets/agent_os_mvp/backend/app/services/session_store.py",
    "assets/agent_os_mvp/backend/app/services/claude_session.py",
    "assets/agent_os_mvp/backend/requirements.txt",
    "assets/agent_os_mvp/frontend/package.json",
    "assets/agent_os_mvp/frontend/package-lock.json",
    "assets/agent_os_mvp/frontend/src/App.jsx",
    "assets/agent_os_mvp/frontend/src/styles.css",
    "assets/agent_os_mvp/start-dashboard.sh",
    "assets/agent_os_mvp/stop-dashboard.sh",
    "assets/agent_os_mvp/smoke-dashboard.sh",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def crlf_diagnostic(path: Path, expected: str) -> dict[str, str | bool]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return {"line_ending_diagnostic": "unavailable", "detail": str(exc)}
    if b"\0" in data or b"\r\n" not in data:
        return {}
    normalized = data.replace(b"\r\n", b"\n")
    normalized_hash = _sha256_bytes(normalized)
    if normalized_hash != expected:
        return {}
    return {
        "line_ending_diagnostic": "CRLF_LINE_ENDING_CONVERSION",
        "probable_cause": "CRLF_LINE_ENDING_CONVERSION",
        "normalized_lf_matches": True,
        "normalized_lf_sha256": normalized_hash,
        "remediation": "Use the GitHub zip download or clone with: git -c core.autocrlf=false clone <repo-url>",
    }


def manifest_entries(root: Path, paths: Iterable[str]) -> list[dict[str, str]]:
    entries = []
    for rel in paths:
        path = root / rel
        if not path.is_file():
            continue
        entries.append({"path": rel, "sha256": sha256_file(path)})
    return entries


def build_manifest(repo_root: Path, skill_root: Path) -> dict[str, Any]:
    return {
        "package_schema_version": PACKAGE_SCHEMA_VERSION,
        "release_id": RELEASE_ID,
        "runtime_files": manifest_entries(repo_root, RUNTIME_REQUIRED_PATHS),
        "skill_files": manifest_entries(skill_root, SKILL_REQUIRED_PATHS),
    }


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST_PATH
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def verify_entries(root: Path, entries: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    missing: list[str] = []
    mismatches: list[dict[str, Any]] = []
    for entry in entries:
        rel = str(entry.get("path", ""))
        expected = str(entry.get("sha256", ""))
        path = root / rel
        if not path.is_file():
            missing.append(rel)
            continue
        actual = sha256_file(path)
        if not expected or actual != expected:
            item: dict[str, Any] = {"path": rel, "expected": expected, "actual": actual}
            item.update(crlf_diagnostic(path, expected))
            mismatches.append(item)
    return missing, mismatches


def verify_package(
    root: Path,
    *,
    profile: str = "repo",
    skill_root: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    manifest = load_manifest(root)
    missing_manifest = not bool(manifest)
    release_id = str(manifest.get("release_id", ""))
    schema_version = manifest.get("package_schema_version")

    runtime_entries = manifest.get("runtime_files", []) if isinstance(manifest.get("runtime_files"), list) else []
    runtime_missing, runtime_mismatches = verify_entries(root, runtime_entries)
    required_runtime_missing = [rel for rel in RUNTIME_REQUIRED_PATHS if not (root / rel).is_file()]
    runtime_missing = sorted(set(runtime_missing + required_runtime_missing))

    skill_missing: list[str] = []
    skill_mismatches: list[dict[str, Any]] = []
    if profile == "repo":
        resolved_skill_root = (skill_root or root / ".claude" / "skills" / "research-task-orchestrator").resolve()
        skill_entries = manifest.get("skill_files", []) if isinstance(manifest.get("skill_files"), list) else []
        skill_missing, skill_mismatches = verify_entries(resolved_skill_root, skill_entries)
        skill_missing = sorted(
            set(skill_missing + [rel for rel in SKILL_REQUIRED_PATHS if not (resolved_skill_root / rel).is_file()])
        )

    missing_files = sorted(set(runtime_missing + [f"skill:{item}" for item in skill_missing]))
    hash_mismatches = runtime_mismatches + [
        {**item, "path": f"skill:{item['path']}"}
        for item in skill_mismatches
    ]
    manifest_counts_match = (
        len(runtime_entries) == len(RUNTIME_REQUIRED_PATHS)
        and (profile != "repo" or len(manifest.get("skill_files", [])) == len(SKILL_REQUIRED_PATHS))
    )
    passed = bool(
        not missing_manifest
        and release_id
        and schema_version == PACKAGE_SCHEMA_VERSION
        and manifest_counts_match
        and not missing_files
        and not hash_mismatches
    )
    return {
        "package_integrity": "pass" if passed else "PACKAGE_INTEGRITY_FAILED",
        "passed": passed,
        "profile": profile,
        "release_id": release_id,
        "package_schema_version": schema_version,
        "manifest_file": MANIFEST_PATH.as_posix(),
        "manifest_missing": missing_manifest,
        "manifest_counts_match": manifest_counts_match,
        "missing_files": missing_files,
        "hash_mismatches": hash_mismatches,
    }
