# Skill 分離：安裝 Skill vs 操作 Skill

本專案刻意分成兩個 skill，避免使用者同時理解 install、dashboard、runtime、agent task、verification。

## 安裝 skill

路徑：

```text
skills/install-multi-agent-runtime/
```

用途：

- 第一次 clone 後初始化 repo
- 建立 `.env`
- 建立 `agent-runs/`、`results/`、`logs/`
- 安裝 dashboard backend/frontend dependencies
- 跑 doctor 與 strict install verification
- 確認 operation skill 存在

Common command：

```bash
bash skills/install-multi-agent-runtime/scripts/install.sh
```

安裝 skill 不做：

- 不修改 Claude Code 設定
- 不修改 Claude Code Router 設定
- 不選 model/provider/output token
- 不安裝 Ollama 或模型服務
- 不執行使用者業務任務

## 操作 skill

路徑：

```text
.claude/skills/research-task-orchestrator/
```

用途：

- 接受使用者任務
- 開會議 / 分派 agent / 執行 bounded workflow
- 產生 artifacts
- 執行 verifier、watchdog、claim ledger
- 啟動或查看已安裝好的 dashboard

使用方式：

```text
Use the research-task-orchestrator skill to run: <your task>
```

操作 skill 不做：

- 不負責 repo 安裝
- 不替使用者改 Claude/Router/model/token
- 不把 process exit 0 當 verified success

## 架構差異

這不是重寫核心 runtime，而是把入口切清楚：

- install skill = 準備環境
- operation skill = 跑任務
- dashboard = 看 artifacts 與 verification
- Docker Compose = advanced isolated reproduction
