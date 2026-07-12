# Dashboard 手動啟動

Dashboard package 位於：

```text
agent_os_mvp/
```

安裝 dashboard 依賴：

```bash
bash .claude/skills/research-task-orchestrator/scripts/install_dashboard.sh
```

啟動：

```bash
bash .claude/skills/research-task-orchestrator/scripts/start_dashboard.sh
```

預設 URL：

```text
Backend health: http://127.0.0.1:8010/health
Frontend:       http://127.0.0.1:5174
```

停止：

```bash
bash .claude/skills/research-task-orchestrator/scripts/stop_dashboard.sh
```

若 port 衝突，使用 project env 覆蓋 dashboard port；不要修改 Claude/Router/model 設定。
