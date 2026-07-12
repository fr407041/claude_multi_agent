# Getting Started：Ubuntu 22.04 Common Path

本專案的預設使用者是 Ubuntu 22.04，並且已經用自己的方式管理 Claude Code / Router / LLM。

## 1. 安裝

從 repo root 執行：

```bash
bash skills/install-multi-agent-runtime/scripts/install.sh
```

這會：

- 建立 `.env`
- 建立 `agent-runs/`、`results/`、`logs/`
- 跑 doctor / strict install verification
- 安裝 dashboard backend/frontend 到 `agent_os_mvp/`
- 確認 operation skill 存在

不會：

- 修改 Claude Code 設定
- 修改 Router 設定
- 選 model/provider/output token
- 安裝 Ollama 或模型服務

## 2. 開 dashboard

```bash
bash agent_os_mvp/start-dashboard.sh
```

開啟：

```text
http://127.0.0.1:15174/
```

## 3. 執行任務

安裝完成後，使用 operation skill：

```text
Use the research-task-orchestrator skill to run: <your task>
```

任務產出的結果會落在專案內的 results / run artifacts，dashboard 會用 common view 顯示狀態、會議、產物、驗證與下一步。

## 4. 驗證

```bash
python3 scripts/verify_install.py --strict --json
bash agent_os_mvp/smoke-dashboard.sh
```

複雜 live case 請先拆成 micro gates，不要一次跑完整大任務才發現失敗。
