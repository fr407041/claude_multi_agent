# Agent OS MVP Dashboard

Local dashboard for viewing multi-agent run artifacts.

It does not start an LLM, install Ollama, modify Claude Code, or change Router
configuration. It reads project-local artifacts and presents a common task view.

## Ubuntu 22.04 common path

Install from the repository root:

```bash
bash skills/install-multi-agent-runtime/scripts/install.sh
```

Start:

```bash
bash agent_os_mvp/start-dashboard.sh
```

Open:

```text
http://127.0.0.1:15174/
```

Health:

```text
http://127.0.0.1:18010/health
```

Stop:

```bash
bash agent_os_mvp/stop-dashboard.sh
```

## What it shows

- current task status
- progress snapshot
- agent status
- primary result
- generated outputs
- verification summary
- meeting discussion and task plan when available
- technical details behind expandable sections

Completed runs use `Review outputs` instead of opening a webpage directly.
`Generated outputs` lists actual files/folders, existence, type, size, modified
time, and safe previews.

## Configuration

Default ports:

```env
DASHBOARD_BACKEND_PORT=18010
DASHBOARD_FRONTEND_PORT=15174
```

Runtime env overrides:

```bash
AGENT_OS_BACKEND_PORT=28010 \
AGENT_OS_FRONTEND_PORT=25174 \
AGENT_OS_PUBLIC_API_BASE_URL=http://127.0.0.1:28010 \
bash agent_os_mvp/start-dashboard.sh
```

The frontend reads `/runtime-config.json` at startup. The local start script and
the Docker image both generate it from the selected backend API URL, so changing
ports does not require editing frontend source code or rebuilding with a hard
coded Vite value.

## Smoke check

```bash
bash agent_os_mvp/smoke-dashboard.sh
```

## Advanced Docker mode

Docker Compose is for CI, maintainers, and isolated reproduction only.

```bash
cd agent_os_mvp
docker compose up -d --build
```

## Do not commit runtime outputs

Do not commit:

- `backend/.venv/`
- `frontend/node_modules/`
- `frontend/dist/`
- `logs/`
- `backend/data/`
- `*.db`
- `*.sqlite`
