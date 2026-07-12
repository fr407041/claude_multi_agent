# Agent OS MVP Dashboard

這是本機 dashboard，用來查看 multi-agent run artifacts。

它不啟動 LLM、不安裝 Ollama、不修改 Claude Code，也不改 Router 設定。它只讀目前專案內的 artifacts，並用 common task view 呈現。

## Ubuntu 22.04 common path

從 repo root 安裝：

```bash
bash skills/install-multi-agent-runtime/scripts/install.sh
```

啟動：

```bash
bash agent_os_mvp/start-dashboard.sh
```

打開：

```text
http://127.0.0.1:15174/
```

健康檢查：

```text
http://127.0.0.1:18010/health
```

停止：

```bash
bash agent_os_mvp/stop-dashboard.sh
```

## 畫面重點

- 任務狀態
- 進度 snapshot
- agent status
- primary result
- generated outputs
- verification summary
- meeting discussion / task plan
- technical details 收合顯示

完成任務的主行為是 `Review outputs`，不是直接開網頁。
`Generated outputs` 會顯示實際產物：檔案/資料夾是否存在、類型、大小、修改時間與安全預覽。

## Port

預設：

```env
DASHBOARD_BACKEND_PORT=18010
DASHBOARD_FRONTEND_PORT=15174
```

臨時覆蓋：

```bash
AGENT_OS_BACKEND_PORT=28010 \
AGENT_OS_FRONTEND_PORT=25174 \
AGENT_OS_PUBLIC_API_BASE_URL=http://127.0.0.1:28010 \
bash agent_os_mvp/start-dashboard.sh
```

## Smoke check

```bash
bash agent_os_mvp/smoke-dashboard.sh
```

## Advanced Docker mode

Docker Compose 只給 CI、維護者或隔離複現使用，不是 common install path。

```bash
cd agent_os_mvp
docker compose up -d --build
```
