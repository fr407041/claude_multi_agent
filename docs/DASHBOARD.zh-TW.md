# Dashboard 使用說明

Dashboard 是 common agent task observer。它只讀取目前專案內的 artifacts，不負責啟動模型、不修改 Claude/Router，也不替使用者選 model。

## Ubuntu 22.04 common path

第一次安裝請用 install skill：

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

Smoke check：

```bash
bash agent_os_mvp/smoke-dashboard.sh
```

## 預設行為

- 手動 refresh，不自動輪詢造成畫面跳動。
- completed run 顯示 `Review outputs`。
- `Generated outputs` 顯示實際產物：存在狀態、類型、大小、修改時間、安全預覽。
- meeting / raw logs / verifier JSON 放在可展開技術細節。
- 沒有 run artifacts 時顯示空狀態，不視為 dashboard 失敗。

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

## Advanced: Docker Compose

Docker Compose 只給 CI、維護者或隔離複現使用，不是 common install path。

```bash
cd agent_os_mvp
docker compose up -d --build
```
