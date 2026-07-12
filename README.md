# Claude Multi Agent

Common-case multi-agent runtime for Claude Code users.

The project is designed for Ubuntu 22.04 users who already have their own
Claude Code / Router / LLM setup. This repository does not choose your model,
provider, router profile, or output-token settings. Your existing Claude
environment remains the source of truth.

## Quick Start: Ubuntu 22.04

Use the install skill first. It prepares this repository and the local dashboard.

```bash
bash skills/install-multi-agent-runtime/scripts/install.sh
```

Start the dashboard:

```bash
bash agent_os_mvp/start-dashboard.sh
```

Open:

```text
http://127.0.0.1:15174/
```

Health check:

```bash
curl http://127.0.0.1:18010/health
```

Stop:

```bash
bash agent_os_mvp/stop-dashboard.sh
```

## Two Skills, Two Jobs

### 1. Install skill

Path:

```text
skills/install-multi-agent-runtime/
```

Use this for first-time setup:

- create `.env` when missing
- create `agent-runs/`, `results/`, and `logs/`
- install dashboard backend/frontend dependencies locally
- run doctor and install verification
- confirm the operation skill exists

It must not modify global Claude Code, Claude Code Router, model, provider,
token, shell, npm, or Python configuration.

### 2. Operation skill

Path:

```text
.claude/skills/research-task-orchestrator/
```

Use this after installation:

```text
Use the research-task-orchestrator skill to run: <your task>
```

It handles bounded task planning, agent meeting, worker dispatch, artifact
verification, watchdog checks, and dashboard reporting. It assumes installation
has already been completed.

## Dashboard Behavior

The dashboard is a common task observer. It is not specific to websites, PTT,
stocks, or any one validation case.

Completed runs show:

- `Review outputs` as the primary action
- `Generated outputs` with real files/folders, type, size, modified time, and
  safe inline previews
- verification evidence and limitations
- meeting discussion and task plan when recorded

The dashboard uses manual refresh by default so users can inspect a result
without the page flickering between stale and live states.

Default local ports:

```env
DASHBOARD_BACKEND_PORT=18010
DASHBOARD_FRONTEND_PORT=15174
```

If ports conflict:

```bash
AGENT_OS_BACKEND_PORT=28010 \
AGENT_OS_FRONTEND_PORT=25174 \
AGENT_OS_PUBLIC_API_BASE_URL=http://127.0.0.1:28010 \
bash agent_os_mvp/start-dashboard.sh
```

## Verification

Common install verification:

```bash
python3 scripts/verify_install.py --strict --json
python3 scripts/run_ai_company_task_harness.py docs/ai_specs/ai-company-release-readiness-strict-demo.json --mode mock
```

Dashboard verification:

```bash
bash agent_os_mvp/smoke-dashboard.sh
```

Backend unit tests:

```bash
cd agent_os_mvp/backend
python3 -m unittest discover -s tests -v
```

Frontend build:

```bash
cd agent_os_mvp/frontend
npm run build
```

## Advanced: Docker Compose

Docker Compose is only for maintainers, CI, or isolated reproduction. It is not
the common user install path.

```bash
cd agent_os_mvp
docker compose up -d --build
```

Open:

```text
http://127.0.0.1:15174/
```

## Repository Contents

- `skills/install-multi-agent-runtime/`: install and doctor skill
- `.claude/skills/research-task-orchestrator/`: runtime operation skill
- `agent_os_mvp/`: dashboard backend/frontend package
- `scripts/verify_install.py`: repository verification
- `scripts/run_ai_company_task_harness.py`: mock/live task harness
- `scripts/run-agent-micro-gates.ps1`: precise live micro-gate runner
- `scripts/verify_agent_micro_gate.py`: deterministic micro-gate verifier

## Safety

Do not commit API keys, passwords, Docker images, model weights, runtime logs,
SQLite databases, `.venv`, `node_modules`, or generated result caches.
