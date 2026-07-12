# Getting Started：Ubuntu 22.04 Common Path

這份文件只描述一般使用者路徑：先安裝，再使用。你的 Claude Code / Router / LLM / output token 設定仍由你自己的環境決定，本專案不替你強制指定。

## 1. 安裝

在 repo root 執行：

```bash
bash skills/install-multi-agent-runtime/scripts/install.sh
```

安裝 skill 會做：

- 建立 `.env`
- 建立 `agent-runs/`、`results/`、`logs/`
- 執行 doctor / strict install verification
- 在 `agent_os_mvp/` 準備 dashboard backend/frontend
- 確認 operation skill 存在

安裝 skill 不會做：

- 修改全域 Claude Code 設定
- 修改 Router/provider/model/output token
- 安裝 Ollama 或下載模型

## 2. 啟動 dashboard

```bash
bash agent_os_mvp/start-dashboard.sh
```

打開：

```text
http://127.0.0.1:15174/
```

Dashboard 預設採手動 refresh，避免你正在看結果時畫面跳來跳去。

## 3. 使用 operation skill

安裝完成後，日常任務使用 operation skill：

```text
Use the research-task-orchestrator skill to run: <your task>
```

它負責 agent meeting、任務拆分、worker 執行、artifact 驗證與 dashboard 報告；不負責安裝 repo，也不修改你的 Claude 環境。

## 4. Common live demo

若要確認 live agent 可以「先討論、再產出、再驗證、再讓 dashboard 顯示結果」，使用 common demo：

```bash
bash scripts/run-shopping-site-common-demo.sh live
```

這個 demo 會要求 agent 產生一包靜態輸出：

- `shopping-site/index.html`
- `shopping-site/styles.css`
- `shopping-site/app.js`
- `shopping-site/README.md`

購物網站只是容易人工檢查的 common 生成任務範例，不代表 dashboard 或 runtime 只服務購物網站。

## 5. 驗證

```bash
python3 scripts/verify_install.py --strict --json
bash agent_os_mvp/smoke-dashboard.sh
```

PTT Stock micro-gates 保留為 legacy external-site stress test。它很適合抓弱模型與外部網站不穩問題，但不再作為一般安裝成功的唯一 live acceptance。
