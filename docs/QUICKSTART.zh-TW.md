# Quickstart

## Ubuntu 22.04

```bash
bash skills/install-multi-agent-runtime/scripts/install.sh
bash agent_os_mvp/start-dashboard.sh
```

Open:

```text
http://127.0.0.1:15174/
```

Run a task:

```text
Use the research-task-orchestrator skill to run: <your task>
```

## What success looks like

- install verification passes
- dashboard health returns `ok`
- completed runs show `Review outputs`
- generated files appear in `Generated outputs`
- operation skill can run bounded tasks using the user's existing Claude/Router setup

## Advanced

Docker Compose is available for isolated reproduction only:

```bash
cd agent_os_mvp
docker compose up -d --build
```
