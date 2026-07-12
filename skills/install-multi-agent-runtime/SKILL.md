---
name: install-multi-agent-runtime
description: Install, initialize, and verify this multi_agent_claude_code repository without changing the user's Claude Code, Router, model, provider, or token settings. Use for first-time setup, doctor checks, dashboard/runtime folder initialization, and explaining the install path.
---

# Install Multi-Agent Runtime

Use this skill only for repository installation and health checks. It is not the runtime operation skill used by backend agents to execute multi-agent tasks.

## What this skill may do

- Explain the common install path.
- Create a project-local `.env` from `.env.example`.
- Create local runtime output directories.
- Run project doctor checks.
- Run mock verification.
- Check that the operation skill exists at `.claude/skills/research-task-orchestrator`.
- Point users to dashboard start/stop commands.

## What this skill must not do

- Do not install Ollama or model weights.
- Do not modify Claude Code, Claude Code Router, provider, model, or output-token settings.
- Do not edit global shell, npm, Python, or Claude configuration.
- Do not run user business tasks; hand those to `research-task-orchestrator`.

## Common install commands

From the repository root:

```bash
bash scripts/doctor.sh
bash scripts/init-runtime.sh
python3 scripts/verify_install.py --strict --json
python3 scripts/run_ai_company_task_harness.py docs/ai_specs/ai-company-release-readiness-strict-demo.json --mode mock
```

After installation, use the operation skill:

```text
Use the research-task-orchestrator skill to run: <your task>
```

## Boundary

This install skill prepares the repository. The operation skill runs tasks after the repository is ready.
