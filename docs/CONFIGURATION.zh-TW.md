# 設定

Common path 只管理本專案自己的路徑與 dashboard port，不管理 Claude/Router/model/provider/output token。

`.env.example`：

```env
RUNS_DIR=./agent-runs
RESULTS_DIR=./results
LOGS_DIR=./logs
DASHBOARD_BACKEND_PORT=8010
DASHBOARD_FRONTEND_PORT=5174
SKILLS_DIR=./skills
TASK_TIMEOUT_SECONDS=1800
```

## 不在 common config 管的東西

以下設定由使用者自己的 Claude Code / Router / LLM 環境決定：

- Claude model
- provider
- Router profile
- output token
- API key
- Ollama/model service endpoint

Repo 的 live 驗證只判斷任務是否真的產生 artifact，不替使用者選模型。
