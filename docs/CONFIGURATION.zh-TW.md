# Configuration

Common config 只管理本專案的 runtime 路徑與 dashboard port。

```env
RUNS_DIR=./agent-runs
RESULTS_DIR=./results
LOGS_DIR=./logs
DASHBOARD_BACKEND_PORT=18010
DASHBOARD_FRONTEND_PORT=15174
SKILLS_DIR=./skills
TASK_TIMEOUT_SECONDS=1800
```

## 不由本專案統一控制的項目

本專案不設定、不覆蓋：

- Claude Code model
- Claude Code Router provider/profile
- LLM endpoint
- output token
- API key/token
- Ollama 或其他模型服務

使用者自己的 Claude Code / Router / LLM 設定是權威來源。Live 驗證只判斷 agent 是否能產生可驗證 artifacts，不要求指定模型。
