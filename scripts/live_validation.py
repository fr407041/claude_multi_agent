#!/usr/bin/env python3
"""Run fail-fast, live-only validation and preserve auditable evidence."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = "qwen3-coder:30b"
OLLAMA = "http://192.168.100.112:11435"
CCR = "http://127.0.0.1:3456"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def redact(text: str) -> str:
    for name in ("CCR_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        value = os.environ.get(name, "")
        if value and value != "local-router-token":
            text = text.replace(value, "[REDACTED]")
    return text


def request(url: str, *, payload: dict | None = None, anthropic: bool = False, timeout: int = 180) -> tuple[int, str]:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if anthropic:
        headers.update({"x-api-key": os.environ.get("CCR_API_KEY", "local-router-token"), "anthropic-version": "2023-06-01"})
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def main() -> int:
    run_id = os.environ.get("RUN_ID") or f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"
    artifacts = ROOT / "artifacts" / run_id
    logs = ROOT / "logs" / run_id
    results = ROOT / "results" / run_id
    # The host bootstrap owns logs/<run-id>/bootstrap before this container
    # phase starts. The random run ID still prevents cross-run overwrites.
    for directory in (artifacts, logs, results):
        directory.mkdir(parents=True, exist_ok=True)
    steps: list[dict] = []
    started = time.monotonic()

    def step(name: str, command: str, function) -> object:
        start_wall, start = utc(), time.monotonic()
        out, err, code, value = "", "", 0, None
        try:
            value, out = function()
        except Exception as exc:  # evidence must survive every gate failure
            code, err = 1, f"{type(exc).__name__}: {exc}\n"
        duration = round(time.monotonic() - start, 3)
        (logs / f"{name}.stdout.log").write_text(redact(out), encoding="utf-8")
        (logs / f"{name}.stderr.log").write_text(redact(err), encoding="utf-8")
        record = {"name": name, "command": command, "started_at": start_wall, "finished_at": utc(), "duration_seconds": duration, "exit_code": code,
                  "stdout": str(logs / f"{name}.stdout.log"), "stderr": str(logs / f"{name}.stderr.log")}
        steps.append(record)
        if code:
            raise RuntimeError(f"gate {name} failed: {err.strip()}")
        return value

    failure = ""
    try:
        def audit():
            config = json.loads((ROOT / "config/ccr/config.json").read_text(encoding="utf-8"))
            providers = config.get("Providers", [])
            expected_route = f"ollama,{MODEL}"
            assert len(providers) == 1 and providers[0]["name"] == "ollama"
            assert providers[0]["api_base_url"] == f"{OLLAMA}/v1/chat/completions"
            assert providers[0]["models"] == [MODEL]
            assert all(config["Router"].get(key) == expected_route for key in ("default", "background", "think", "longContext", "webSearch"))
            compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
            assert compose.count("services:") == 1 and "image: ollama" not in compose.lower()
            source_path = ROOT / "UPSTREAM_SOURCE.json"
            source = json.loads(source_path.read_text(encoding="utf-8")) if source_path.exists() else {}
            write_json(artifacts / "source-metadata.json", source)
            audit_result = {"provider_count": 1, "model": MODEL, "endpoint": OLLAMA, "mock": False, "source": source}
            return config, json.dumps(audit_result, indent=2)
        step("01-config-audit", "validate config/ccr/config.json and docker-compose.yml", audit)

        def versions():
            commands = [["claude", "--version"], ["npm", "list", "--global", "@musistudio/claude-code-router", "--depth=0"], ["node", "--version"], ["python3", "--version"]]
            lines = []
            for cmd in commands:
                proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
                lines.append(f"$ {' '.join(cmd)}\n{proc.stdout}{proc.stderr}")
                if proc.returncode:
                    raise RuntimeError(f"{' '.join(cmd)} exited {proc.returncode}")
            if shutil.which("ollama"):
                raise RuntimeError("ollama binary unexpectedly exists in validator image")
            return lines, "\n".join(lines) + "ollama binary: absent\n"
        step("02-runtime-audit", "claude/ccr/node/python versions; assert ollama absent", versions)

        def tags():
            errors = []
            for attempt in range(1, 6):
                try:
                    status, body = request(f"{OLLAMA}/api/tags", timeout=15)
                    break
                except urllib.error.URLError as exc:
                    errors.append(f"attempt {attempt}: {exc}")
                    if attempt == 5:
                        raise RuntimeError("; ".join(errors))
                    time.sleep(2)
            (artifacts / "ollama-tags.response.json").write_text(body, encoding="utf-8")
            parsed = json.loads(body)
            names = [item.get("name") for item in parsed.get("models", [])]
            if status != 200 or MODEL not in names:
                raise RuntimeError(f"HTTP {status}; exact model missing; visible={names}")
            return names, body
        step("03-ollama-model-visible", f"GET {OLLAMA}/api/tags", tags)

        nonce = f"LIVE-{secrets.token_hex(12)}"
        direct_payload = {"model": MODEL, "messages": [{"role": "user", "content": f"Reply with exactly: {nonce}"}], "stream": False, "options": {"temperature": 0}}
        write_json(artifacts / "direct-provider.request.json", direct_payload)
        def direct():
            required = os.environ.get("AI_COMPANY_REQUIRE_DIRECT_PROVIDER_COMPLETION") == "1"
            diagnostic = {
                "provider_diagnostic_status": "complete",
                "classification": "",
                "model_visibility": {"status": "pass", "url": f"{OLLAMA}/api/tags", "model": MODEL, "detail": ""},
                "direct_completion": {"status": "", "url": f"{OLLAMA}/v1/chat/completions", "required": required, "detail": ""},
                "next_action": "",
            }
            body = ""
            try:
                status, body = request(f"{OLLAMA}/v1/chat/completions", payload=direct_payload)
                (artifacts / "direct-provider.response.json").write_text(body, encoding="utf-8")
                if status == 200 and nonce in body:
                    diagnostic["direct_completion"]["status"] = "pass"
                    diagnostic["classification"] = "DIRECT_COMPLETION_PASSED"
                    diagnostic["next_action"] = "Direct provider completion passed; continue with router/Claude live validation."
                else:
                    diagnostic["direct_completion"]["status"] = "failed"
                    diagnostic["direct_completion"]["detail"] = f"HTTP {status}; nonce absent from live provider response"
                    diagnostic["classification"] = "MODEL_VISIBLE_BUT_COMPLETION_FAILED"
                    diagnostic["next_action"] = "Direct provider completion failed; continue through CCR/Claude unless direct completion is explicitly required."
            except (TimeoutError, socket.timeout) as exc:
                diagnostic["direct_completion"]["status"] = "timeout"
                diagnostic["direct_completion"]["detail"] = f"{type(exc).__name__}: timed out after 180s"
                diagnostic["classification"] = "MODEL_VISIBLE_BUT_COMPLETION_TIMEOUT"
                diagnostic["next_action"] = "Direct provider completion timed out. Continue validating through Claude Code Router/Claude CLI."
            except urllib.error.URLError as exc:
                diagnostic["direct_completion"]["status"] = "connection_error"
                diagnostic["direct_completion"]["detail"] = str(exc.reason)
                diagnostic["classification"] = "MODEL_VISIBLE_BUT_COMPLETION_FAILED"
                diagnostic["next_action"] = "Direct provider completion failed; continue through CCR/Claude unless direct completion is explicitly required."

            write_json(artifacts / "direct-provider.diagnostic.json", diagnostic)
            if required and diagnostic["direct_completion"]["status"] != "pass":
                raise RuntimeError(f"direct provider completion required but {diagnostic['classification']}: {diagnostic['direct_completion']['detail']}")
            return diagnostic, json.dumps(diagnostic, ensure_ascii=False, indent=2) + ("\n" + body if body else "")
        step("04-direct-provider-diagnostic", f"POST {OLLAMA}/v1/chat/completions model={MODEL} diagnostic; hard fail only when AI_COMPANY_REQUIRE_DIRECT_PROVIDER_COMPLETION=1", direct)

        ccr_nonce = f"CCR-{secrets.token_hex(12)}"
        ccr_payload = {"model": MODEL, "max_tokens": 128, "messages": [{"role": "user", "content": f"Reply with exactly: {ccr_nonce}"}]}
        write_json(artifacts / "ccr.request.json", ccr_payload)
        def ccr_message():
            health_status, health_body = request(f"{CCR}/health", timeout=15)
            if health_status != 200:
                raise RuntimeError(f"CCR health HTTP {health_status}: {health_body[:300]}")
            status, body = request(f"{CCR}/v1/messages", payload=ccr_payload, anthropic=True)
            (artifacts / "ccr.response.json").write_text(body, encoding="utf-8")
            if status != 200 or ccr_nonce not in body:
                raise RuntimeError(f"CCR HTTP {status}; nonce absent")
            return json.loads(body), health_body + "\n" + body
        step("05-ccr-live", f"GET {CCR}/health; POST {CCR}/v1/messages", ccr_message)

        claude_nonce = f"CLAUDE-{secrets.token_hex(12)}"
        def claude_cli():
            cmd = ["claude", "--bare", "--print", "--output-format", "json", "--model", MODEL]
            proc = subprocess.run(cmd, cwd=ROOT, input=f"Reply with exactly: {claude_nonce}\n", text=True, capture_output=True, timeout=240, check=False)
            (artifacts / "claude-code.response.json").write_text(proc.stdout, encoding="utf-8")
            if proc.returncode or claude_nonce not in proc.stdout:
                raise RuntimeError(f"Claude Code exit={proc.returncode}; nonce absent; stderr={proc.stderr[:500]}")
            return json.loads(proc.stdout), proc.stdout + proc.stderr
        step("06-claude-code-live", "printf '<nonce prompt>' | claude --bare --print --output-format json --model qwen3-coder:30b", claude_cli)

        skill_nonce = f"SKILL-{secrets.token_hex(12)}"
        skill_root = results / "skill-live-smoke"
        worktree, jobs = skill_root / "worktree", skill_root / "jobs"
        worktree.mkdir(parents=True)
        jobs.mkdir(parents=True)
        target_name = "skill_live_probe.txt"
        expected = skill_nonce + "\n"
        (worktree / target_name).write_text("", encoding="utf-8")
        job = {"id": "job-skill-live-probe", "owner_role": "executor_backend", "agent_profile": "executor_backend", "scope_path": str(worktree),
               "files": [target_name], "require_change": True, "worker_template": "managed_single_file",
               "instruction": f"Return exactly this content and nothing else: {skill_nonce}",
               "test_command": f"python3 -c \"from pathlib import Path; p=Path('{target_name}'); raise SystemExit(0 if p.read_text() == {expected!r} else 1)\""}
        write_json(jobs / "job-skill-live-probe.json", job)
        def skill_live():
            installer = ROOT / ".claude/skills/research-task-orchestrator/scripts/install_runtime.sh"
            install = subprocess.run(["bash", str(installer)], cwd=ROOT, text=True, capture_output=True, timeout=120, check=False)
            if install.returncode:
                raise RuntimeError(f"skill install failed: {install.stderr[:500]}")
            worker = ROOT / ".ai-company/runtime/current/scripts/worker_claude_router.py"
            proc = subprocess.run(["python3", str(worker), str(jobs / "job-skill-live-probe.json"), "managed"], cwd=ROOT, text=True, capture_output=True, timeout=300, check=False)
            target = worktree / target_name
            status_path = skill_root / "results/job-skill-live-probe.status.json"
            status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
            if proc.returncode or status.get("status") != "SUCCESS" or not target.exists() or target.read_text(encoding="utf-8") != expected:
                raise RuntimeError(f"skill live failed: exit={proc.returncode} status={status.get('status')} stderr={proc.stderr[:500]}")
            return status, install.stdout + install.stderr + proc.stdout + proc.stderr
        step("07-skill-live", "install research-task-orchestrator runtime; run managed live nonce job", skill_live)

        def provenance():
            ccr_logs = Path("/root/.claude-code-router/logs")
            copied = []
            if ccr_logs.exists():
                for source in ccr_logs.glob("*"):
                    if source.is_file():
                        target = logs / ("ccr-" + source.name)
                        target.write_text(redact(source.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
                        copied.append(str(target))
            config_hash = hashlib.sha256((ROOT / "config/ccr/config.json").read_bytes()).hexdigest()
            proof = {"configured_endpoint": OLLAMA, "configured_model": MODEL, "only_provider": "ollama", "ollama_binary_absent": shutil.which("ollama") is None,
                     "mock_used": False, "ccr_config_sha256": config_hash, "router_logs": copied}
            write_json(artifacts / "provider-proof.json", proof)
            return proof, json.dumps(proof, indent=2)
        step("08-provenance", "collect CCR logs and provider proof; assert no fallback/mock", provenance)
    except Exception as exc:
        failure = str(exc)

    status = "FAILED" if failure else "PASS"
    summary = {"run_id": run_id, "status": status, "live_mode": True, "mock_used": False, "provider": OLLAMA, "model": MODEL,
               "started_at": steps[0]["started_at"] if steps else utc(), "finished_at": utc(), "duration_seconds": round(time.monotonic() - started, 3),
               "exit_code": 1 if failure else 0, "failure_reason": failure, "artifacts_path": str(artifacts), "logs_path": str(logs), "results_path": str(results), "steps": steps}
    write_json(results / "run-summary.json", summary)
    report = [f"# Live Validation {status}", "", f"- Run ID: `{run_id}`", f"- Provider: `{OLLAMA}`", f"- Model: `{MODEL}`", f"- Duration: `{summary['duration_seconds']}s`", f"- Exit code: `{summary['exit_code']}`", f"- Failure: `{failure or 'none'}`", "", "## Steps", ""]
    report.extend(f"- {item['name']}: exit `{item['exit_code']}`, {item['duration_seconds']}s" for item in steps)
    (results / "final-report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
